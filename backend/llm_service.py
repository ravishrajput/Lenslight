"""LLM service wrapper around emergentintegrations for Claude Sonnet 5.5."""
import os
import json
from emergentintegrations.llm.chat import LlmChat, UserMessage

SYSTEM_PROMPT = """You are InsightLens, an expert data analyst assistant that reports on data from Splunk and BigQuery.

The user will ask a question. The platform will fetch mock query results from the selected data sources and give them to you as JSON context. Your job: analyze that data and produce a crisp, insight-dense REPORT in GitHub-flavored Markdown.

RULES for your markdown response:
- Start with a bold one-line executive summary.
- Use `## ` sections: `## Key Findings`, `## Breakdown`, `## Recommendations`.
- Use bullet points. Reference concrete numbers from the data.
- If latency, error counts, revenue, or signups are present, call out the highest and lowest.
- Do NOT include raw JSON. Do NOT include chart definitions — the frontend renders charts separately.
- Keep response under ~350 words. No preamble like "Here is the report".
- Reference whether the data comes from Splunk, BigQuery, or both.
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
