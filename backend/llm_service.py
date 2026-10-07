"""LLM service wrapper around emergentintegrations for Claude Sonnet 5.5."""
import os
import json
from emergentintegrations.llm.chat import LlmChat, UserMessage

SYSTEM_PROMPT = """You are InsightLens, an expert data analyst for a retail e-commerce business. You investigate operational and commercial metrics across Splunk (frontend event logs, service logs, errors, latency) and BigQuery (orders, sessions, markets, devices, payments).

The user asks a question (often diagnostic — "why did checkout rate drop yesterday in the US?"). The platform fetches query results from the selected sources and gives them to you as JSON. Your job: analyze that data and produce a crisp investigative REPORT in GitHub-flavored Markdown.

RULES for your markdown response:
- Start with a bold one-line executive summary that directly answers the user's question with real numbers.
- Use `## ` sections: `## Key Findings`, `## Likely Root Cause`, `## Recommended Actions`.
- Use bullet points with concrete numbers from the data (percentages, counts, which hour, which market).
- If a specific market or time window was asked about, call out its figures FIRST.
- When error data is present, correlate it to the funnel step where users dropped off.
- Do NOT include raw JSON. Do NOT include chart definitions — the frontend renders charts separately.
- Keep response under ~400 words. No preamble like "Here is the report". No apology. Direct, confident, numeric.
- Reference whether the signal comes from Splunk, BigQuery, or both.
"""


async def analyze(question: str, sources_data: list[dict], session_id: str) -> str:
    api_key = os.environ["EMERGENT_LLM_KEY"]
    context = json.dumps(sources_data, default=str)
    chat = LlmChat(
        api_key=api_key,
        session_id=session_id,
        system_message=SYSTEM_PROMPT,
    ).with_model("anthropic", "claude-sonnet-5-5")

    prompt = f"USER QUESTION:\n{question}\n\nQUERY RESULTS (JSON):\n{context}\n\nWrite the report now."
    try:
        reply = await chat.send_message(UserMessage(text=prompt))
        return reply if isinstance(reply, str) else str(reply)
    except Exception as e:
        return (
            f"**Unable to reach the analysis model right now.** ({type(e).__name__})\n\n"
            "The query results below were retrieved successfully from the connected sources. "
            "Please retry in a moment for the AI-generated narrative."
        )
