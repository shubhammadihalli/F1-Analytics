"""AI Analyst endpoint — natural language Q&A grounded in real F1 data.

Fetches relevant race/driver/season data from Postgres, formats it as
structured context, then calls Groq's Llama 3.3 70B model to produce a
natural language answer.  Groq is free-tier (no credit card, 14 400
req/day) and returns answers at ~400 tokens/second — fast enough for a
live dashboard.
"""

from __future__ import annotations

import textwrap
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from groq import Groq
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.dependencies import get_db
from models.circuit import Circuit
from models.driver import Driver
from models.lap import Lap
from models.pitstop import PitStop
from models.result import Result
from models.session import Session as SessionModel
from models.stint import Stint
from models.weather import Weather

router = APIRouter(tags=["ai"])
logger = get_logger(__name__)

# ---- request / response schemas ----------------------------------------

ContextType = Literal["season", "race", "driver", "head_to_head"]


class AnalyzeRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500, description="Natural language question about F1 data.")
    context_type: ContextType = Field("season", description="What data to pull as context.")
    race_session_key: int | None = Field(None, description="Race session key (required when context_type='race').")
    driver_number: int | None = Field(None, description="Driver number (required when context_type='driver').")
    driver_number_b: int | None = Field(None, description="Second driver for head_to_head context.")
    year: int = Field(2026, ge=2023, le=2030)


class AnalyzeResponse(BaseModel):
    answer: str
    context_type: str
    data_sources: list[str]
    model: str
    tokens_used: int


# ---- context builders --------------------------------------------------

def _driver_name(db: Session, driver_number: int) -> str:
    d = db.get(Driver, driver_number)
    return (d.full_name or f"#{driver_number}") if d else f"#{driver_number}"


def _circuit_names(db: Session) -> dict[int, str]:
    return {
        key: name or ""
        for key, name in db.execute(select(Circuit.circuit_key, Circuit.circuit_short_name))
    }


def _season_context(db: Session, year: int) -> tuple[str, list[str]]:
    """Driver standings + constructor standings + completed race results."""
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

    return "\n".join(lines), ["driver_standings", "race_results (top 3)", "sessions"]


def _race_context(db: Session, session_key: int) -> tuple[str, list[str]]:
    """Full race results + lap summary + tyre stints + weather snapshot."""
    session = db.get(SessionModel, session_key)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_key} not found.")

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

    return "\n".join(lines), ["race_results", "lap_times", "tyre_stints", "pit_stops", "weather"]


def _driver_context(db: Session, driver_number: int, year: int) -> tuple[str, list[str]]:
    """Per-driver season results, qualifying, and lap pace."""
    driver = db.get(Driver, driver_number)
    if not driver:
        raise HTTPException(status_code=404, detail=f"Driver #{driver_number} not found.")

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

    return "\n".join(lines), ["race_results", "qualifying_results"]


def _h2h_context(db: Session, driver_a: int, driver_b: int, year: int) -> tuple[str, list[str]]:
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

    return "\n".join(lines), ["race_results (both drivers)", "sessions"]


# ---- system prompt -----------------------------------------------------

_SYSTEM_PROMPT = textwrap.dedent("""
    You are ApexGrid AI, an expert Formula 1 analyst with deep knowledge of
    F1 regulations, tyre behaviour, race strategy, and driver performance.

    You are given REAL data fetched live from a PostgreSQL database.
    Never make up statistics. Only cite numbers that appear in the context.
    Be direct, analytical, and insightful — like an F1 pundit, not a
    textbook. Use specific lap times, tyre compounds, and race context
    where available.  Keep answers concise (150–300 words) unless asked
    for a deeper analysis.
""").strip()


# ---- endpoint ----------------------------------------------------------

@router.post("/ai/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest, db: Session = Depends(get_db)) -> AnalyzeResponse:
    if not settings.groq_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Analyst is not configured — set GROQ_API_KEY in your environment.",
        )

    # Build context from DB
    if req.context_type == "race":
        if not req.race_session_key:
            raise HTTPException(status_code=422, detail="race_session_key is required for context_type='race'.")
        context, sources = _race_context(db, req.race_session_key)
    elif req.context_type == "driver":
        if not req.driver_number:
            raise HTTPException(status_code=422, detail="driver_number is required for context_type='driver'.")
        context, sources = _driver_context(db, req.driver_number, req.year)
    elif req.context_type == "head_to_head":
        if not req.driver_number or not req.driver_number_b:
            raise HTTPException(status_code=422, detail="driver_number and driver_number_b are required for head_to_head.")
        context, sources = _h2h_context(db, req.driver_number, req.driver_number_b, req.year)
    else:
        context, sources = _season_context(db, req.year)

    # Call Groq
    try:
        client = Groq(api_key=settings.groq_api_key)
        completion = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"### F1 Data Context\n\n{context}\n\n### Question\n\n{req.question}"},
            ],
            temperature=0.5,
            max_tokens=600,
        )
    except Exception as exc:
        logger.exception("Groq API call failed")
        raise HTTPException(status_code=502, detail=f"AI service error: {exc}") from exc

    answer = completion.choices[0].message.content or ""
    tokens = completion.usage.total_tokens if completion.usage else 0

    return AnalyzeResponse(
        answer=answer,
        context_type=req.context_type,
        data_sources=sources,
        model=settings.groq_model,
        tokens_used=tokens,
    )
