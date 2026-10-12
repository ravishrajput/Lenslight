"""Weekly digest: synthesizes last-week mock data, calls Claude, builds email HTML,
and emails it with a deep-link back into the app."""
import os
import random
from datetime import datetime, timezone, timedelta
from html import escape
from typing import Optional
from data_sources import fetch_splunk_data, fetch_bigquery_data
from llm_service import analyze
from email_service import send_email


FRONTEND_URL = os.environ.get("FRONTEND_URL", "")


def _detect_anomalies(sources_data: list[dict]) -> list[dict]:
    """Pick numeric highlights from the mock sources to show as KPI cards."""
    kpis = []
    for d in sources_data:
        src = d["source"]
        # Revenue
        if "total_revenue_usd" in d:
            kpis.append({"label": "Revenue (last 7d)", "value": f"${d['total_revenue_usd']:,.0f}", "src": src})
        # Markets
        if "markets" in d and d["markets"]:
            top = d["markets"][0]
            kpis.append({"label": f"Top market — {top['market']}", "value": f"${top.get('revenue_usd', 0):,.0f}", "src": src})
            # weakest
            weakest = min(d["markets"], key=lambda r: r.get("checkout_rate_pct", 99))
            if "checkout_rate_pct" in weakest:
                kpis.append({"label": f"Weakest CR — {weakest['market']}", "value": f"{weakest['checkout_rate_pct']}%", "src": src})
        # Payment methods
        if "payment_methods" in d and d["payment_methods"]:
            worst = min(d["payment_methods"], key=lambda r: r["success_rate_pct"])
            kpis.append({"label": f"Lowest payment success — {worst['method']}", "value": f"{worst['success_rate_pct']}%", "src": src})
        # Top errors
        if "top_errors" in d and d["top_errors"]:
            e = d["top_errors"][0]
            kpis.append({"label": f"Top error — {e['error'][:28]}", "value": f"{e['events']} events", "src": src})
        if "time_series" in d and d["time_series"]:
            # pick metric with largest swing
            keys = [k for k in d["time_series"][0].keys() if k not in ("time", "date")]
            if keys:
                k0 = keys[0]
                vals = [row.get(k0, 0) for row in d["time_series"] if isinstance(row.get(k0), (int, float))]
                if vals:
                    kpis.append({"label": f"{k0} range", "value": f"{min(vals):,} - {max(vals):,}", "src": src})
    return kpis[:6]


def _kpi_row_html(kpis: list[dict]) -> str:
    if not kpis:
        return ""
    rows = ""
    for i in range(0, len(kpis), 2):
        pair = kpis[i:i+2]
        cells = ""
        for k in pair:
            accent = "#F24E1E" if k["src"] == "splunk" else "#007AFF"
            cells += (
                f'<td width="50%" valign="top" style="padding:10px;border:1px solid #e5e5e5;background:#fafafa">'
                f'<div style="font-family:Arial,sans-serif;font-size:10px;letter-spacing:0.14em;color:#737373;text-transform:uppercase;margin-bottom:6px">'
                f'<span style="display:inline-block;width:6px;height:6px;background:{accent};margin-right:6px;vertical-align:middle"></span>'
                f'{escape(k["label"])}</div>'
                f'<div style="font-family:Arial,sans-serif;font-size:22px;font-weight:700;color:#111">{escape(str(k["value"]))}</div>'
                f'</td>'
            )
        if len(pair) == 1:
            cells += '<td width="50%"></td>'
        rows += f'<tr>{cells}</tr>'
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="4" style="margin:16px 0">{rows}</table>'


def _markdown_to_simple_html(md: str) -> str:
    """Minimal, email-safe markdown rendering (headings, bold, bullets, paragraphs)."""
    lines = md.splitlines()
    out = []
    in_list = False
    for raw in lines:
        s = raw.rstrip()
        if not s:
            if in_list:
                out.append("</ul>")
                in_list = False
            continue
        if s.startswith("## "):
            if in_list:
                out.append("</ul>"); in_list = False
            out.append(f'<h3 style="font-family:Arial,sans-serif;font-size:14px;letter-spacing:0.1em;color:#737373;text-transform:uppercase;margin:22px 0 8px">{escape(s[3:])}</h3>')
            continue
        if s.startswith("# "):
            out.append(f'<h2 style="font-family:Arial,sans-serif;font-size:18px;color:#111;margin:18px 0 8px">{escape(s[2:])}</h2>')
            continue
        if s.startswith("- "):
            if not in_list:
                out.append('<ul style="font-family:Arial,sans-serif;font-size:14px;color:#333;line-height:1.6;padding-left:18px;margin:4px 0">')
                in_list = True
            text = _inline_bold(escape(s[2:]))
            out.append(f"<li>{text}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        text = _inline_bold(escape(s))
        out.append(f'<p style="font-family:Arial,sans-serif;font-size:14px;color:#333;line-height:1.6;margin:6px 0">{text}</p>')
    if in_list:
        out.append("</ul>")
    return "".join(out)


def _inline_bold(s: str) -> str:
    import re as _re
    return _re.sub(r"\*\*(.+?)\*\*", r'<strong style="color:#111">\1</strong>', s)


def _build_email_html(user_name: str, markdown: str, kpis: list[dict], app_url: str) -> str:
    kpi_html = _kpi_row_html(kpis)
    body_html = _markdown_to_simple_html(markdown)
    footer_note = (
        "Sent by Lenslight because you turned on the weekly digest. "
        "We never ask for your password or payment details by email."
    )
    cta = (
        f'<p style="margin:24px 0"><a href="{escape(app_url)}" '
        f'style="background:#111;color:#ffffff;padding:12px 18px;'
        f'font-family:Arial,sans-serif;font-size:13px;letter-spacing:0.08em;'
        f'text-transform:uppercase;text-decoration:none;display:inline-block">'
        f'Open Lenslight</a></p>'
        if app_url.startswith("https://") else ""
    )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:#f5f5f5;padding:24px 0">'
        f'<tr><td align="center">'
        f'<table role="presentation" width="620" cellpadding="0" cellspacing="0" '
        f'style="background:#ffffff;max-width:620px"><tr><td style="padding:28px 32px">'
        f'<div style="font-family:Arial,sans-serif;font-size:11px;letter-spacing:0.3em;color:#737373;text-transform:uppercase;margin-bottom:8px">'
        f'<span style="display:inline-block;width:8px;height:8px;background:#F24E1E;margin-right:8px;vertical-align:middle"></span>'
        f'Lenslight / Weekly Digest</div>'
        f'<h1 style="font-family:Arial,sans-serif;font-size:26px;color:#111;margin:0 0 6px">Your week in one page.</h1>'
        f'<p style="font-family:Arial,sans-serif;font-size:14px;color:#737373;margin:0 0 8px">'
        f'Hey {escape(user_name)} — here is the auto-detected checkout, cart, and revenue read for the last 7 days.</p>'
        f'{kpi_html}'
        f'{body_html}'
        f'{cta}'
        f'<hr style="border:none;border-top:1px solid #e5e5e5;margin:28px 0 12px">'
        f'<p style="font-family:Arial,sans-serif;font-size:11px;color:#999;margin:0">{escape(footer_note)}</p>'
        f'</td></tr></table></td></tr></table>'
    )


async def generate_and_send_digest(user: dict) -> Optional[str]:
    """Query sources for last-week retail KPIs, synthesize report, email it."""
    question = "Summarize last week's checkout rate, cart abandonment, and revenue anomalies across markets."
    random.seed()
    sources = [await fetch_splunk_data(question), await fetch_bigquery_data(question)]
    markdown = await analyze(question, sources, session_id=f"digest_{user['user_id']}_{datetime.now(timezone.utc).strftime('%Y%W')}")
    kpis = _detect_anomalies(sources)
    html = _build_email_html(user.get("name") or user["email"], markdown, kpis, FRONTEND_URL)
    subject = f"Lenslight — Weekly digest for {datetime.now(timezone.utc).strftime('%b %d')}"
    return await send_email(to=user["email"], subject=subject, html=html)
