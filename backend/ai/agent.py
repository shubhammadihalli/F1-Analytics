"""The tool-calling agent loop.

This is the heart of the agentic AI Analyst.  Rather than pre-fetching a fixed
context block, we hand the model a set of tools and let it drive:

    question
      → model decides it needs standings   → call get_season_standings
      → model decides it needs a race       → call list_races, get_race_results
      → model has enough                    → writes the final answer

Each turn we send the running message history plus ``TOOL_SCHEMAS`` to Groq.
If the model returns ``tool_calls`` we execute them, append the results as
``role="tool"`` messages, and loop.  When it returns plain content instead, that
is the answer and we stop.  A hard iteration cap prevents runaway loops.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from groq import NOT_GIVEN, BadRequestError, Groq
from sqlalchemy.orm import Session

from backend.ai import tools
from backend.core.logging import get_logger

logger = get_logger(__name__)

# The model is allowed this many tool-calling rounds before we force it to
# answer with whatever it has. Real questions here resolve in 1–3 rounds; the
# cap only exists to bound cost and latency if the model loops.
MAX_ITERATIONS = 6

SYSTEM_PROMPT = (
    "You are ApexGrid AI, an expert Formula 1 analyst with deep knowledge of F1 "
    "regulations, tyre behaviour, race strategy, and driver performance.\n\n"
    "You have TOOLS that fetch REAL data from a PostgreSQL database. Decide which "
    "tools you need to answer the user's question, call them, and reason over the "
    "results. You may call several tools in sequence — for example, use list_races "
    "to turn a Grand Prix name into a session_key before get_race_results, or "
    "find_driver to turn a name into a driver_number before get_driver_summary or "
    "compare_drivers.\n\n"
    "Rules:\n"
    "- Only cite numbers that appear in tool results. Never invent statistics.\n"
    "- If a tool returns an error, read it and recover (e.g. call a resolver tool).\n"
    "- Once you have enough data, give a direct, analytical answer like an F1 "
    "pundit — not a textbook. Reference specific lap times, tyre compounds and race "
    "context where available. Keep answers concise (150–300 words) unless asked for "
    "deeper analysis."
)


@dataclass
class ToolCall:
    """One tool invocation, recorded for the reasoning trace shown in the UI."""

    tool: str
    arguments: dict
    result_preview: str


@dataclass
class AgentResult:
    answer: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    iterations: int = 0
    tokens_used: int = 0
    model: str = ""


def _preview(text: str, limit: int = 240) -> str:
    text = text.strip().replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + "…"


def run_agent(
    *,
    client: Groq,
    model: str,
    db: Session,
    question: str,
    default_year: int,
    max_iterations: int = MAX_ITERATIONS,
) -> AgentResult:
    """Drive the model through tool calls until it produces a final answer."""
    messages: list[Any] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"(The current F1 season is {default_year}. Assume this year "
                f"unless the question names a different one.)\n\n{question}"
            ),
        },
    ]

    trace: list[ToolCall] = []
    total_tokens = 0

    for iteration in range(1, max_iterations + 1):
        # On the last permitted round, drop the tools so the model is forced to
        # answer from what it has gathered rather than requesting more data.
        use_tools = iteration < max_iterations
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools.TOOL_SCHEMAS if use_tools else NOT_GIVEN,
                tool_choice="auto" if use_tools else NOT_GIVEN,
                temperature=0.4,
                max_tokens=800,
            )
        except BadRequestError as exc:
            # Groq's Llama occasionally emits a malformed tool call
            # (`tool_use_failed`). Rather than 500, force one final tool-free
            # completion so the model answers from what it has already gathered.
            if "tool_use_failed" not in str(exc):
                raise
            logger.warning("tool_use_failed; forcing tool-free answer")
            completion = client.chat.completions.create(
                model=model,
                messages=messages + [{
                    "role": "system",
                    "content": "Answer now using only the data already gathered. Do not call tools.",
                }],
                temperature=0.4,
                max_tokens=800,
            )
            if completion.usage:
                total_tokens += completion.usage.total_tokens
            return AgentResult(
                answer=completion.choices[0].message.content or "",
                tool_calls=trace,
                iterations=iteration,
                tokens_used=total_tokens,
                model=model,
            )

        if completion.usage:
            total_tokens += completion.usage.total_tokens

        msg = completion.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None)

        if not tool_calls:
            return AgentResult(
                answer=msg.content or "",
                tool_calls=trace,
                iterations=iteration,
                tokens_used=total_tokens,
                model=model,
            )

        # Record the assistant's tool-call request verbatim so the follow-up
        # tool messages line up with their tool_call_id.
        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in tool_calls
                ],
            }
        )

        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            logger.info("agent tool call: %s %s", name, args)

            result = tools.dispatch(name, args, db, default_year=default_year)
            trace.append(ToolCall(tool=name, arguments=args, result_preview=_preview(result)))
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    # Exhausted iterations without a plain-content answer. Surface whatever the
    # last message held rather than nothing.
    return AgentResult(
        answer=msg.content or "I gathered data but ran out of reasoning steps before answering.",
        tool_calls=trace,
        iterations=max_iterations,
        tokens_used=total_tokens,
        model=model,
    )
