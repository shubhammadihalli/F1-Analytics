"""Data-fetching functions that turn Postgres rows into LLM-ready text.

Each function returns a compact, structured string describing one slice of F1
data.  They power both the legacy fixed-context endpoint and the agentic tool
layer (``backend.ai.tools``) — in the agentic path the model calls these itself
via ``get_race_results`` / ``compare_drivers`` / etc. and reads the returned
text back as tool output.

Kept in their own module (rather than in the endpoint file) so the endpoint,
the tools, and the agent can all import them without an import cycle.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from models.circuit import Circuit
from models.driver import Driver
from models.lap import Lap
from models.pitstop import PitStop
from models.result import Result
from models.session import Session as SessionModel
from models.stint import Stint
from models.weather import Weather


class DataNotFound(Exception):
    """Raised when a requested entity (driver/session) does not exist.

    The agent catches this and feeds the message back to the model as tool
    output so it can recover (e.g. call ``list_races`` to find a valid key),
    while the legacy endpoint maps it to an HTTP 404.
    """


# ---- shared helpers ----------------------------------------------------

def _driver_name(db: Session, driver_number: int) -> str:
    d = db.get(Driver, driver_number)
    return (d.full_name or f"#{driver_number}") if d else f"#{driver_number}"


def _circuit_names(db: Session) -> dict[int, str]:
    return {
        key: name or ""
        for key, name in db.execute(select(Circuit.circuit_key, Circuit.circuit_short_name))
    }


# ---- resolver tools ----------------------------------------------------
# These have no equivalent in the legacy endpoint: because the agent is no
# longer handed a pre-selected session/driver, it needs a way to turn the
# names people actually say ("British GP", "Leclerc") into the keys the data
# tools require.

def list_races(db: Session, year: int, session_type: str = "Race") -> str:
    """List sessions for a season so the model can resolve a name to a key."""
    circuits = _circuit_names(db)
    rows = db.execute(
        select(SessionModel)
        .where(SessionModel.year == year, SessionModel.session_type == session_type)
        .order_by(SessionModel.date_start)
    ).scalars().all()

    if not rows:
        return f"No {session_type} sessions found for {year}."

    lines = [f"## {year} {session_type} sessions (session_key → circuit, date)\n"]
    for r in rows:
        circuit = circuits.get(r.circuit_key or 0, "Unknown")
        lines.append(
            f"session_key={r.session_key}: {circuit} — {r.session_name} "
            f"({str(r.date_start)[:10]})"
        )
    return "\n".join(lines)


def find_driver(db: Session, name: str) -> str:
    """Look up drivers by (partial) name or 3-letter acronym → driver_number."""
    term = f"%{name.strip()}%"
    rows = db.execute(
        select(Driver)
        .where(
            or_(
                Driver.full_name.ilike(term),
                Driver.last_name.ilike(term),
                Driver.name_acronym.ilike(term),
                Driver.broadcast_name.ilike(term),
            )
        )
        .order_by(Driver.driver_number)
    ).scalars().all()

    if not rows:
        return f"No driver found matching '{name}'."

    lines = [f"## Drivers matching '{name}' (driver_number → name, team)\n"]
    for d in rows:
        lines.append(
            f"driver_number={d.driver_number}: {d.full_name} ({d.name_acronym}) — "
            f"{d.team_name or 'Unknown team'}"
        )
    return "\n".join(lines)


# ---- context / data builders -------------------------------------------

def season_context(db: Session, year: int) -> str:
    """Driver standings + recent race podiums for a season."""
    circuits = _circuit_names(db)

    podiums = db.execute(
        select(Result, Driver.full_name, Driver.name_acronym,
               SessionModel.circuit_key, SessionModel.session_name, SessionModel.date_start)
        .join(Driver, Driver.driver_number == Result.driver_number)
        .join(SessionModel, SessionModel.session_key == Result.session_key)
        .where(SessionModel.year == year, SessionModel.session_type == "Race", Result.position <= 3)
        .order_by(SessionModel.date_start, Result.position)
    ).all()

    standings = db.execute(
        select(Result.driver_number, Driver.full_name, Driver.name_acronym,
               func.sum(Result.points).label("points"),
               func.count().filter(Result.position == 1).label("wins"))
        .join(Driver, Driver.driver_number == Result.driver_number)
        .join(SessionModel, SessionModel.session_key == Result.session_key)
        .where(SessionModel.year == year, SessionModel.session_type == "Race")
        .group_by(Result.driver_number, Driver.full_name, Driver.name_acronym)
        .order_by(func.sum(Result.points).desc())
    ).all()

    lines = [f"## {year} F1 Season — Driver Standings\n"]
    for i, row in enumerate(standings[:15], 1):
        lines.append(f"P{i}. {row.full_name} ({row.name_acronym}) — {row.points:.0f} pts, {row.wins} wins")

    lines.append("\n## Recent Race Podiums\n")
    for result, full_name, name_acronym, circuit_key, session_name, date_start in podiums[-30:]:
        circuit = circuits.get(circuit_key or 0, "Unknown")
        lines.append(
            f"P{result.position}: {full_name} ({name_acronym}) — {circuit} "
            f"({session_name}, {str(date_start)[:10]})"
        )

    return "\n".join(lines)


def race_context(db: Session, session_key: int) -> str:
    """Full race results + fastest laps + tyre stints + pit stops + weather."""
    session = db.get(SessionModel, session_key)
    if not session:
        raise DataNotFound(
            f"Session {session_key} not found. Call list_races to find a valid session_key."
        )

    results = db.execute(
        select(Result, Driver.full_name, Driver.name_acronym)
        .join(Driver, Driver.driver_number == Result.driver_number)
        .where(Result.session_key == session_key)
        .order_by(Result.position)
    ).all()

    # Fastest laps per driver
    fastest = db.execute(
        select(Lap.driver_number, Driver.name_acronym, func.min(Lap.lap_duration).label("fastest"))
        .join(Driver, Driver.driver_number == Lap.driver_number)
        .where(Lap.session_key == session_key, Lap.lap_duration.is_not(None))
        .group_by(Lap.driver_number, Driver.name_acronym)
        .order_by(func.min(Lap.lap_duration))
    ).all()

    # Tyre stints
    stints = db.execute(
        select(Stint, Driver.name_acronym)
        .join(Driver, Driver.driver_number == Stint.driver_number)
        .where(Stint.session_key == session_key)
        .order_by(Driver.name_acronym, Stint.stint_number)
    ).all()

    # Pit stops
    pit_stops = db.execute(
        select(PitStop, Driver.name_acronym)
        .join(Driver, Driver.driver_number == PitStop.driver_number)
        .where(PitStop.session_key == session_key)
        .order_by(PitStop.lap_number)
    ).all()

    # Weather (first + last sample)
    weather_rows = db.execute(
        select(Weather).where(Weather.session_key == session_key).order_by(Weather.date)
    ).scalars().all()

    circuits = _circuit_names(db)
    circuit_name = circuits.get(session.circuit_key or 0, "Unknown Circuit")

    lines = [
        f"## {circuit_name} — {session.session_name} {session.year}\n",
        f"Date: {str(session.date_start)[:10]}\n",
        "### Race Classification\n",
    ]
    for r, name, code in results:
        status_str = "DNF" if r.dnf else ("DSQ" if r.dsq else "Finished")
        gap = f"+{r.gap_to_leader:.3f}s" if r.gap_to_leader and r.gap_to_leader > 0 else "WINNER"
        lines.append(
            f"P{r.position or 'DNF'}: {name} ({code}) — {r.number_of_laps} laps, "
            f"{r.points:.0f} pts, {gap}, {status_str}"
        )

    lines.append("\n### Fastest Laps\n")
    for row in fastest[:10]:
        m, s = divmod(row.fastest or 0, 60)
        lines.append(f"{row.name_acronym}: {int(m)}:{s:06.3f}")

    lines.append("\n### Tyre Strategy\n")
    stint_by_driver: dict[str, list[str]] = {}
    for s, code in stints:
        stint_by_driver.setdefault(code, []).append(
            f"{s.compound or 'UNKNOWN'} laps {s.lap_start}–{s.lap_end or '?'} "
            f"(age {s.tyre_age_at_start})"
        )
    for code, s_list in stint_by_driver.items():
        lines.append(f"{code}: {' → '.join(s_list)}")

    lines.append("\n### Pit Stops\n")
    for p, code in pit_stops:
        lines.append(f"{code} lap {p.lap_number}: {p.pit_duration:.2f}s" if p.pit_duration else f"{code} lap {p.lap_number}")

    if weather_rows:
        w_start, w_end = weather_rows[0], weather_rows[-1]
        lines.append(
            f"\n### Weather\n"
            f"Start — Air {w_start.air_temperature:.0f}°C, Track {w_start.track_temperature:.0f}°C, "
            f"Humidity {w_start.humidity:.0f}%\n"
            f"End   — Air {w_end.air_temperature:.0f}°C, Track {w_end.track_temperature:.0f}°C"
        )

    return "\n".join(lines)


def driver_context(db: Session, driver_number: int, year: int) -> str:
    """Per-driver season race results + qualifying positions."""
    driver = db.get(Driver, driver_number)
    if not driver:
        raise DataNotFound(
            f"Driver #{driver_number} not found. Call find_driver to look up a driver_number."
        )

    circuits = _circuit_names(db)

    results = db.execute(
        select(Result, SessionModel.circuit_key, SessionModel.session_name, SessionModel.date_start)
        .join(SessionModel, SessionModel.session_key == Result.session_key)
        .where(Result.driver_number == driver_number, SessionModel.year == year,
               SessionModel.session_type == "Race")
        .order_by(SessionModel.date_start)
    ).all()

    quali_results = db.execute(
        select(Result, SessionModel.circuit_key, SessionModel.date_start)
        .join(SessionModel, SessionModel.session_key == Result.session_key)
        .where(Result.driver_number == driver_number, SessionModel.year == year,
               SessionModel.session_type == "Qualifying")
        .order_by(SessionModel.date_start)
    ).all()

    lines = [f"## {driver.full_name} ({driver.name_acronym}) — {year} Season\n",
             f"Team: {driver.team_name}\n",
             "### Race Results\n"]
    total_pts = 0.0
    wins = podiums = 0
    for r, circuit_key, session_name, date in results:
        circuit = circuits.get(circuit_key or 0, "Unknown")
        status_str = "DNF" if r.dnf else ("DSQ" if r.dsq else f"P{r.position}")
        pts = r.points or 0.0
        total_pts += pts
        if r.position == 1:
            wins += 1
        if r.position and r.position <= 3:
            podiums += 1
        lines.append(f"{circuit} ({str(date)[:10]}, {session_name}): {status_str} — {pts:.0f} pts")

    lines.append(f"\nSeason total: {total_pts:.0f} pts, {wins} wins, {podiums} podiums\n")

    lines.append("### Qualifying Positions\n")
    for r, circuit_key, date in quali_results:
        circuit = circuits.get(circuit_key or 0, "Unknown")
        lines.append(f"{circuit} ({str(date)[:10]}): Q{r.position or 'DNQ'}")

    return "\n".join(lines)


def h2h_context(db: Session, driver_a: int, driver_b: int, year: int) -> str:
    """Side-by-side stats for two drivers across shared race sessions."""
    circuits = _circuit_names(db)

    def driver_race_rows(drv: int) -> list[Any]:
        return list(db.execute(
            select(Result, SessionModel.circuit_key)
            .join(SessionModel, SessionModel.session_key == Result.session_key)
            .where(Result.driver_number == drv, SessionModel.year == year,
                   SessionModel.session_type == "Race", SessionModel.session_name == "Race")
            .order_by(SessionModel.date_start)
        ).all())

    rows_a = driver_race_rows(driver_a)
    rows_b = driver_race_rows(driver_b)

    def aggregate(rows: list[tuple[Result, int | None]]) -> dict[str, float | str]:
        pts = sum(r.points or 0 for r, _ in rows)
        wins = sum(1 for r, _ in rows if r.position == 1)
        pods = sum(1 for r, _ in rows if r.position and r.position <= 3)
        positions = [r.position for r, _ in rows if r.position]
        avg = round(sum(positions) / max(1, len(positions)), 1)
        return {"points": pts, "wins": wins, "podiums": pods, "avg_finish": avg}

    agg_a, agg_b = aggregate(rows_a), aggregate(rows_b)
    name_a = _driver_name(db, driver_a)
    name_b = _driver_name(db, driver_b)

    lines = [f"## Head to Head: {name_a} vs {name_b} — {year}\n",
             f"{'Metric':<20} {name_a:<25} {name_b}\n" + "-" * 60]
    for key, label in [("points", "Points"), ("wins", "Wins"), ("podiums", "Podiums"), ("avg_finish", "Avg Finish")]:
        lines.append(f"{label:<20} {str(agg_a[key]):<25} {agg_b[key]}")

    lines.append("\n### Race-by-Race\n")
    for (ra, circuit_key), (rb, _) in zip(rows_a, rows_b):
        circuit = circuits.get(circuit_key or 0, "Unknown")
        pos_a = f"P{ra.position}" if ra.position else "DNF"
        pos_b = f"P{rb.position}" if rb.position else "DNF"
        lines.append(f"{circuit}: {name_a} {pos_a} vs {name_b} {pos_b}")

    return "\n".join(lines)
