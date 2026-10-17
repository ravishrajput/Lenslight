"""LLM service for Gemini analysis with Anthropic fallback support."""
import asyncio
import json
import os
from typing import Optional

try:
    from google import genai as google_ai
    from google.genai import types as google_types
except Exception:  # pragma: no cover
    google_ai = None
    google_types = None

try:
    import google.generativeai as genai
except Exception:  # pragma: no cover
    genai = None

try:
    from anthropic import AsyncAnthropic
except Exception:  # pragma: no cover
    AsyncAnthropic = None

SYSTEM_PROMPT = """You are Lenslight, an expert data analyst for a retail e-commerce business. You investigate operational and commercial metrics across local CSV event logs (frontend events, service errors, address validation, latency) and BigQuery (orders, sessions, markets, devices, payments).

The user asks a question (often diagnostic — "why did checkout rate drop yesterday in the US?"). The platform fetches query results from the selected sources and gives them to you as JSON. Your job: analyze that data and produce a crisp investigative REPORT in GitHub-flavored Markdown.

RESPONSE STYLE:
- Answer the exact question first in 1-2 sentences, using the most relevant numbers.
- Be crisp by default: 3-6 sentences, at most 120 words. Use up to 3 short bullets only when they improve readability.
- Include only findings needed to answer the question. Do not dump metrics, repeat the question, add generic background, or force headings/sections.
- Mention a likely cause or recommended action only when supported by the results or requested; label uncertain explanations as hypotheses.
- If a specific market or time window was asked about, prioritize it. When error data is present, connect it to a funnel drop-off only when the evidence supports that connection.
- Use both sources when relevant, comparing only compatible dimensions and time ranges. Do not claim record-level joins unless shared keys are present.
- If a source is unavailable or returns an error, state that briefly and base conclusions only on available data.
- Do NOT include raw JSON or chart definitions — the frontend renders charts separately.
- No preamble or apology. Attribute the key signal to Splunk, BigQuery, or both only when useful.
- Expand beyond this concise format only when the user explicitly asks for detail.
"""


def _build_prompt(question: str, sources_data: list[dict]) -> str:
    context = json.dumps(sources_data, default=str)
    return f"USER QUESTION:\n{question}\n\nQUERY RESULTS FROM LOCAL CSV AND/OR BIGQUERY (JSON):\n{context}\n\nWrite the report now."


def _gemini_api_key() -> Optional[str]:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def _gemini_model() -> str:
    return os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")


def _claude_model() -> str:
    return os.environ.get("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")


def _configure_gemini():
    api_key = _gemini_api_key()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is not configured")

    if google_ai is not None:
        return google_ai.Client(api_key=api_key)

    if genai is None:
        raise RuntimeError("No compatible Google Gemini SDK is installed")

    genai.configure(api_key=api_key)
    return None


async def _analyze_with_gemini(question: str, sources_data: list[dict]) -> str:
    client = _configure_gemini()
    prompt = _build_prompt(question, sources_data)

    if client is not None and google_ai is not None:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=_gemini_model(),
            contents=prompt,
            config=google_types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
        )
        text = getattr(response, "text", None) or str(response)
        return text.strip()

    if genai is not None:
        model = genai.GenerativeModel(model_name=_gemini_model(), system_instruction=SYSTEM_PROMPT)
        response = await asyncio.to_thread(model.generate_content, prompt)
        text = getattr(response, "text", None) or str(response)
        return text.strip()

    raise RuntimeError("No compatible Google Gemini SDK is installed")


async def _stream_with_gemini(question: str, sources_data: list[dict]):
    response = await _analyze_with_gemini(question, sources_data)
    yield response


async def _analyze_with_anthropic(question: str, sources_data: list[dict]) -> str:
    if AsyncAnthropic is None:
        raise RuntimeError("anthropic package is not installed")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    client = AsyncAnthropic(api_key=api_key)
    response = await client.messages.create(
        model=_claude_model(),
        max_tokens=1200,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_prompt(question, sources_data)}],
    )
    chunks = []
    for block in getattr(response, "content", []):
        if getattr(block, "type", None) == "text":
            chunks.append(block.text)
    text = "".join(chunks).strip()
    if not text:
        return str(response)
    return text


async def _stream_with_anthropic(question: str, sources_data: list[dict]):
    if AsyncAnthropic is None:
        raise RuntimeError("anthropic package is not installed")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    client = AsyncAnthropic(api_key=api_key)
    async with client.messages.stream(
        model=_claude_model(),
        max_tokens=1200,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_prompt(question, sources_data)}],
    ) as stream:
        async for text in stream.text_stream:
            yield text


async def analyze(question: str, sources_data: list[dict], session_id: str) -> str:
    try:
        if _gemini_api_key():
            return await _analyze_with_gemini(question, sources_data)
        if os.environ.get("ANTHROPIC_API_KEY"):
            return await _analyze_with_anthropic(question, sources_data)
        raise RuntimeError("No LLM API key configured")
    except Exception as e:
        return (
            f"**Unable to reach the analysis model right now.** ({type(e).__name__})\n\n"
            "The query results below were retrieved successfully from the connected sources. "
            "Please retry in a moment for the AI-generated narrative."
        )


async def stream_analyze(question: str, sources_data: list[dict], session_id: str):
    """Yields text chunks as the LLM produces them."""
    try:
        if _gemini_api_key():
            async for chunk in _stream_with_gemini(question, sources_data):
                yield chunk
            return
        if os.environ.get("ANTHROPIC_API_KEY"):
            async for chunk in _stream_with_anthropic(question, sources_data):
                yield chunk
            return
        raise RuntimeError("No LLM API key configured")
    except Exception:
        fallback = "\n\n**Model stream interrupted.** The query results are still shown below."
        yield fallback
