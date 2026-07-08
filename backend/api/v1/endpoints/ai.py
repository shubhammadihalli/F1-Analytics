"""AI Analyst endpoints — natural language Q&A grounded in real F1 data.

Two endpoints, both backed by Groq's Llama 3.3 70B (free-tier, ~400 tok/s):

* ``POST /ai/agent`` — the agentic path. The model is given TOOLS and decides
  for itself which F1 data to fetch, calling them in a loop until it can answer.
  See ``backend.ai.agent`` and ``backend.ai.tools``.
* ``POST /ai/analyze`` — the legacy fixed-context path. The caller pre-selects a
  context type (season/race/driver/head_to_head); we fetch that block once and
  make a single, tool-free completion. Kept for backwards compatibility.

The data-fetching logic is shared via ``backend.ai.context``.
"""

from __future__ import annotations

import textwrap
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from groq import Groq
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.ai import context
from backend.ai.agent import run_agent
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.dependencies import get_db

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


class AgentRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500, description="Natural language question about F1 data.")
    year: int = Field(2026, ge=2023, le=2030, description="Default season used when the model omits a year.")


class AgentToolCall(BaseModel):
    tool: str
    arguments: dict
    result_preview: str


class AgentResponse(BaseModel):
    answer: str
    tool_calls: list[AgentToolCall]
    iterations: int
    model: str
    tokens_used: int


# ---- system prompt (legacy fixed-context endpoint) ---------------------

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


def _require_groq() -> None:
    if not settings.groq_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Analyst is not configured — set GROQ_API_KEY in your environment.",
        )


# ---- agentic endpoint --------------------------------------------------

@router.post("/ai/agent", response_model=AgentResponse)
async def agent(req: AgentRequest, db: Session = Depends(get_db)) -> AgentResponse:
    """Answer a question by letting the model autonomously call data tools."""
    _require_groq()

    try:
        client = Groq(api_key=settings.groq_api_key)
        result = run_agent(
            client=client,
            model=settings.groq_model,
            db=db,
            question=req.question,
            default_year=req.year,
        )
    except Exception as exc:
        logger.exception("Agentic AI call failed")
        raise HTTPException(status_code=502, detail=f"AI service error: {exc}") from exc

    return AgentResponse(
        answer=result.answer,
        tool_calls=[
            AgentToolCall(tool=t.tool, arguments=t.arguments, result_preview=t.result_preview)
            for t in result.tool_calls
        ],
        iterations=result.iterations,
        model=result.model,
        tokens_used=result.tokens_used,
    )


# ---- legacy fixed-context endpoint -------------------------------------

@router.post("/ai/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest, db: Session = Depends(get_db)) -> AnalyzeResponse:
    _require_groq()

    # Build context from DB
    try:
        if req.context_type == "race":
            if not req.race_session_key:
                raise HTTPException(status_code=422, detail="race_session_key is required for context_type='race'.")
            ctx = context.race_context(db, req.race_session_key)
            sources = ["race_results", "lap_times", "tyre_stints", "pit_stops", "weather"]
        elif req.context_type == "driver":
            if not req.driver_number:
                raise HTTPException(status_code=422, detail="driver_number is required for context_type='driver'.")
            ctx = context.driver_context(db, req.driver_number, req.year)
            sources = ["race_results", "qualifying_results"]
        elif req.context_type == "head_to_head":
            if not req.driver_number or not req.driver_number_b:
                raise HTTPException(status_code=422, detail="driver_number and driver_number_b are required for head_to_head.")
            ctx = context.h2h_context(db, req.driver_number, req.driver_number_b, req.year)
            sources = ["race_results (both drivers)", "sessions"]
        else:
            ctx = context.season_context(db, req.year)
            sources = ["driver_standings", "race_results (top 3)", "sessions"]
    except context.DataNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Call Groq
    try:
        client = Groq(api_key=settings.groq_api_key)
        completion = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"### F1 Data Context\n\n{ctx}\n\n### Question\n\n{req.question}"},
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
