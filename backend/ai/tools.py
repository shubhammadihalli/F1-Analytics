"""Tool schemas + dispatch registry for the agentic AI Analyst.

Each entry pairs an OpenAI/Groq-style JSON tool schema (what the model sees)
with a Python callable that runs the actual query (``backend.ai.context``).
The agent loop (``backend.ai.agent``) sends ``TOOL_SCHEMAS`` to the model and,
when the model asks to call one, routes it through ``dispatch``.

Tool callables all take ``(db, **kwargs)`` and return a plain string — the
text the model reads back as tool output.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from backend.ai import context

# The default season is injected by the agent when the model omits ``year``;
# it keeps the schemas honest (year is genuinely optional to the model) while
# still grounding queries in the active season.

# ---- tool schemas (what the model sees) --------------------------------

# Typed as list[Any] so the Groq SDK accepts it as ChatCompletionToolParam.
TOOL_SCHEMAS: list[Any] = [
    {
        "type": "function",
        "function": {
            "name": "get_season_standings",
            "description": (
                "Get the current driver championship standings and recent race "
                "podiums for a season. Use this for questions about who is leading, "
                "championship battles, or season-wide form."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "Championship year, e.g. 2026."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_races",
            "description": (
                "List the sessions of a season with their session_key, circuit and "
                "date. Call this FIRST to resolve a Grand Prix name (e.g. 'British "
                "GP', 'Silverstone') into the session_key that get_race_results needs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "Championship year, e.g. 2026."},
                    "session_type": {
                        "type": "string",
                        "description": "Session type filter. Defaults to 'Race'.",
                        "enum": ["Race", "Qualifying", "Sprint", "Practice 1", "Practice 2", "Practice 3"],
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_race_results",
            "description": (
                "Get full results for one race session: classification, fastest laps, "
                "tyre strategy, pit stops and weather. Requires a session_key — if you "
                "only know the GP name, call list_races first to find it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "session_key": {"type": "integer", "description": "The race session key from list_races."},
                },
                "required": ["session_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_driver",
            "description": (
                "Look up drivers by name or 3-letter acronym to get their "
                "driver_number. Call this to resolve a name (e.g. 'Leclerc', 'ANT') "
                "before calling get_driver_summary or compare_drivers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Driver name, surname, or acronym."},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_driver_summary",
            "description": (
                "Get one driver's season: race results, points, wins, podiums and "
                "qualifying positions. Requires a driver_number — use find_driver if "
                "you only know the name."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "driver_number": {"type": "integer", "description": "The driver number from find_driver."},
                    "year": {"type": "integer", "description": "Championship year, e.g. 2026."},
                },
                "required": ["driver_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_drivers",
            "description": (
                "Compare two drivers head-to-head across a season: points, wins, "
                "podiums, average finish and a race-by-race breakdown. Requires both "
                "driver_numbers — use find_driver to resolve names first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "driver_a": {"type": "integer", "description": "First driver_number."},
                    "driver_b": {"type": "integer", "description": "Second driver_number."},
                    "year": {"type": "integer", "description": "Championship year, e.g. 2026."},
                },
                "required": ["driver_a", "driver_b"],
            },
        },
    },
]


# ---- dispatch registry -------------------------------------------------

def _get_season_standings(db: Session, *, year: int) -> str:
    return context.season_context(db, year)


def _list_races(db: Session, *, year: int, session_type: str = "Race") -> str:
    return context.list_races(db, year, session_type)


def _get_race_results(db: Session, *, session_key: int) -> str:
    return context.race_context(db, session_key)


def _find_driver(db: Session, *, name: str) -> str:
    return context.find_driver(db, name)


def _get_driver_summary(db: Session, *, driver_number: int, year: int) -> str:
    return context.driver_context(db, driver_number, year)


def _compare_drivers(db: Session, *, driver_a: int, driver_b: int, year: int) -> str:
    return context.h2h_context(db, driver_a, driver_b, year)


# Which tool args should default to the agent's active season when the model
# omits them. Keeps prompts simple without forcing the model to remember a year.
_YEAR_ARG = {
    "get_season_standings": "year",
    "list_races": "year",
    "get_driver_summary": "year",
    "compare_drivers": "year",
}

_REGISTRY: dict[str, Callable[..., str]] = {
    "get_season_standings": _get_season_standings,
    "list_races": _list_races,
    "get_race_results": _get_race_results,
    "find_driver": _find_driver,
    "get_driver_summary": _get_driver_summary,
    "compare_drivers": _compare_drivers,
}


def dispatch(name: str, args: dict[str, Any], db: Session, *, default_year: int) -> str:
    """Run a tool by name and return its text output.

    Never raises for expected failures — unknown tools, bad args, or missing
    data are returned as strings so the model can read the error and recover
    (retry with different args, call a resolver tool, etc.).
    """
    fn = _REGISTRY.get(name)
    if fn is None:
        return f"Error: unknown tool '{name}'."

    args = dict(args)
    year_arg = _YEAR_ARG.get(name)
    if year_arg and not args.get(year_arg):
        args[year_arg] = default_year

    try:
        return fn(db, **args)
    except context.DataNotFound as exc:
        return f"Error: {exc}"
    except TypeError as exc:
        # Wrong / missing arguments from the model.
        return f"Error calling {name}: {exc}. Check the required arguments and try again."
    except Exception as exc:  # noqa: BLE001 - surface any query error to the model
        return f"Error running {name}: {exc}"
