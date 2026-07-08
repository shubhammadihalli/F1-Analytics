"""Agentic AI layer — tool definitions and the tool-calling agent loop.

The AI Analyst is built around Groq's native function/tool calling.  Instead
of pre-selecting a fixed context block, the model is handed a set of tools
(``backend.ai.tools``) and decides for itself which F1 data to fetch, calling
them in a loop (``backend.ai.agent``) until it can answer the question.
"""
