"""Tests for the agentic AI Analyst — tool dispatch and the agent loop.

Tool dispatch runs against the real local Postgres (consistent with the rest
of the suite). The agent loop is driven by a scripted fake Groq client so we
can assert the tool-calling / recovery behaviour without any network calls or
token cost.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import pytest
from groq import BadRequestError, Groq

from backend.ai import tools
from backend.ai.agent import run_agent
from database.session import SessionLocal


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ---- tool dispatch -----------------------------------------------------

def test_dispatch_defaults_year_when_omitted(db) -> None:
    out = tools.dispatch("get_season_standings", {}, db, default_year=2026)
    assert "2026 F1 Season" in out


def test_dispatch_find_driver_resolves_name(db) -> None:
    out = tools.dispatch("find_driver", {"name": "Leclerc"}, db, default_year=2026)
    assert "driver_number=" in out
    assert "Leclerc".upper() in out.upper()


def test_dispatch_unknown_tool_returns_error_string(db) -> None:
    out = tools.dispatch("does_not_exist", {}, db, default_year=2026)
    assert out.startswith("Error: unknown tool")


def test_dispatch_missing_data_returns_recoverable_error(db) -> None:
    out = tools.dispatch("get_race_results", {"session_key": 999999}, db, default_year=2026)
    assert "not found" in out.lower()
    assert "list_races" in out  # tells the model how to recover


# ---- fake Groq client for the agent loop -------------------------------

@dataclass
class _FakeFunction:
    name: str
    arguments: str


@dataclass
class _FakeToolCall:
    id: str
    function: _FakeFunction


@dataclass
class _FakeMessage:
    content: str | None = None
    tool_calls: list[_FakeToolCall] | None = None


@dataclass
class _FakeUsage:
    total_tokens: int = 10


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeCompletion:
    choices: list[_FakeChoice]
    usage: _FakeUsage


class _FakeCompletions:
    def __init__(self, script: list[Any]) -> None:
        self._script = list(script)

    def create(self, **_kwargs: Any) -> _FakeCompletion:
        step = self._script.pop(0)
        if isinstance(step, Exception):
            raise step
        return _FakeCompletion(choices=[_FakeChoice(message=step)], usage=_FakeUsage())


class _FakeChat:
    def __init__(self, script: list[Any]) -> None:
        self.completions = _FakeCompletions(script)


class _FakeGroq:
    def __init__(self, script: list[Any]) -> None:
        self.chat = _FakeChat(script)


def _fake_client(script: list[Any]) -> Groq:
    """A scripted stand-in for the Groq client (cast for the type checker)."""
    return cast(Groq, _FakeGroq(script))


class _FakeBadRequest(BadRequestError):
    """BadRequestError shim: constructing the real one needs an httpx response.

    The agent only inspects ``str(exc)`` for the ``tool_use_failed`` code, so a
    plain Exception subclass carrying the message is enough.
    """

    def __init__(self, message: str) -> None:
        Exception.__init__(self, message)


# ---- agent loop --------------------------------------------------------

def test_agent_executes_tool_then_answers(db) -> None:
    """Model asks for one tool, reads the result, then answers."""
    script = [
        _FakeMessage(tool_calls=[
            _FakeToolCall(id="c1", function=_FakeFunction("get_season_standings", "{}")),
        ]),
        _FakeMessage(content="Antonelli leads the championship."),
    ]
    result = run_agent(
        client=_fake_client(script), model="fake", db=db, question="Who is leading?", default_year=2026,
    )
    assert result.answer == "Antonelli leads the championship."
    assert result.iterations == 2
    assert [t.tool for t in result.tool_calls] == ["get_season_standings"]
    assert result.tool_calls[0].result_preview  # trace captured a preview
    assert result.tokens_used == 20


def test_agent_chains_resolver_then_data_tool(db) -> None:
    """Two-hop: find_driver → get_driver_summary → answer."""
    script = [
        _FakeMessage(tool_calls=[
            _FakeToolCall(id="c1", function=_FakeFunction("find_driver", '{"name": "Leclerc"}')),
        ]),
        _FakeMessage(tool_calls=[
            _FakeToolCall(id="c2", function=_FakeFunction("get_driver_summary", '{"driver_number": 16}')),
        ]),
        _FakeMessage(content="Leclerc has had a strong season."),
    ]
    result = run_agent(
        client=_fake_client(script), model="fake", db=db,
        question="How is Leclerc doing?", default_year=2026,
    )
    assert result.iterations == 3
    assert [t.tool for t in result.tool_calls] == ["find_driver", "get_driver_summary"]


def test_agent_recovers_from_tool_use_failed(db) -> None:
    """A malformed tool call (Groq tool_use_failed) forces a tool-free answer."""
    script = [
        _FakeBadRequest("tool_use_failed: bad generation"),
        _FakeMessage(content="Here is my best answer without more data."),
    ]
    result = run_agent(
        client=_fake_client(script), model="fake", db=db, question="Anything?", default_year=2026,
    )
    assert "best answer" in result.answer
    assert result.tool_calls == []
