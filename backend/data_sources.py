import base64
import json
import logging
import os
from typing import Any, Optional

import httpx

log = logging.getLogger(__name__)


def _question_lower(question: str) -> str:
    return (question or "").lower()


def _has_real_splunk() -> bool:
    return bool(os.getenv("SPLUNK_HOST") and (os.getenv("SPLUNK_TOKEN") or (os.getenv("SPLUNK_USERNAME") and os.getenv("SPLUNK_PASSWORD"))))


def _has_real_bigquery() -> bool:
    return bool(os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT"))


def _bq_dataset() -> str:
    return os.getenv("BQ_DATASET", "lenslight")


def _bq_table() -> str:
    return os.getenv("BQ_TABLE", "orders")


def _bigquery_table_ref(table_name: Optional[str] = None) -> str:
    project = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project:
        return ""
    table = (table_name or _bq_table()).strip()
    if not table:
        table = _bq_table()
    return f"{project}.{_bq_dataset()}.{table}"


def _build_bigquery_sql(question: str, table_name: Optional[str] = None) -> str:
    q = _question_lower(question)
    if table_name is None:
        table_name = "checkout_events" if any(k in q for k in ["checkout", "funnel", "conversion", "shipping", "payment_info", "order_placed", "cart"]) else _bq_table()
    table_ref = f"`{_bigquery_table_ref(table_name)}`"

    if any(k in q for k in ["checkout", "funnel", "conversion", "shipping", "payment_info", "order_placed", "cart"]):
        return (
            "SELECT "
            "event_name, "
            "COUNT(DISTINCT session_id) AS unique_sessions, "
            "ROUND(COUNT(DISTINCT session_id) / FIRST_VALUE(COUNT(DISTINCT session_id)) OVER (ORDER BY CASE "
            "WHEN event_name = 'checkout_start' THEN 1 "
            "WHEN event_name = 'shipping_info_entered' THEN 2 "
            "WHEN event_name = 'payment_info_entered' THEN 3 "
            "WHEN event_name = 'order_placed' THEN 4 END) * 100, 2) AS completion_rate_from_start "
            f"FROM {table_ref} "
            "GROUP BY event_name "
            "ORDER BY CASE "
            "WHEN event_name = 'checkout_start' THEN 1 "
            "WHEN event_name = 'shipping_info_entered' THEN 2 "
            "WHEN event_name = 'payment_info_entered' THEN 3 "
            "WHEN event_name = 'order_placed' THEN 4 END"
        )

    if any(k in q for k in ["market", "revenue", "sales", "order", "payment", "payment_method", "volume"]):
        if "payment" in q or "method" in q:
            return (
                "SELECT "
                "market, payment_method, COUNT(*) AS transaction_count, "
                "ROUND(SUM(order_value), 2) AS revenue_share "
                f"FROM {table_ref} "
                "GROUP BY 1, 2 "
                "ORDER BY market, transaction_count DESC"
            )
        return (
            "SELECT "
            "market, COUNT(order_id) AS total_orders, "
            "ROUND(SUM(order_value), 2) AS total_revenue, "
            "ROUND(AVG(order_value), 2) AS avg_order_value "
            f"FROM {table_ref} "
            "GROUP BY market "
            "ORDER BY total_revenue DESC"
        )

    return (
        "SELECT DATE(transaction_timestamp) AS date, SUM(order_value) AS revenue_usd "
        f"FROM {table_ref} WHERE transaction_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY) "
        "GROUP BY DATE(transaction_timestamp) ORDER BY date"
    )


def _build_splunk_query(question: str) -> str:
    q = _question_lower(question)
    filters = []
    address_question = any(k in q for k in ("address", "postal", "postcode", "zip code"))
    if address_question:
        filters.append("event IN (address_added, address_validation_failed)")
    elif "checkout" in q or "cart" in q or "conversion" in q:
        filters.append("event IN (checkout_started, order_placed, add_to_cart)")
    if "error" in q or "exception" in q or "fail" in q:
        filters.append("level IN (ERROR, FATAL)")
    if "latency" in q or "slow" in q or "performance" in q:
        filters.append("response_time>0")
    if not filters:
        filters.append("*")
    breakdown = "event, source, market" if address_question else "source, market"
    return "search " + " ".join(filters) + f" | stats count by {breakdown}"


async def _fetch_splunk_real(question: str) -> Optional[dict[str, Any]]:
    if not _has_real_splunk():
        return None

    host = os.environ["SPLUNK_HOST"].rstrip("/")
    token = os.getenv("SPLUNK_TOKEN")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        username = os.environ.get("SPLUNK_USERNAME")
        password = os.environ.get("SPLUNK_PASSWORD")
        if username and password:
            token_value = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {token_value}"

    if "Authorization" not in headers:
        return None

    query = _build_splunk_query(question)
    url = f"{host}/services/search/jobs/export"
    params = {"search": query, "output_mode": "json"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            payload = resp.json()
        return {
            "source": "splunk",
            "spl": query,
            "time_series": payload.get("results", []) or [{"time": "now", "count": 0}],
            "market_filter": None,
        }
    except Exception as exc:
        log.warning("Splunk real source failed; falling back to mock data: %s", exc)
        return None


async def _fetch_bigquery_real(question: str) -> Optional[dict[str, Any]]:
    if not _has_real_bigquery():
        return None

    project = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project:
        return None

    q = _question_lower(question)
    if "checkout" in q or "funnel" in q or "conversion" in q or "shipping" in q or "payment_info" in q or "order_placed" in q:
        target_table = "checkout_events"
    else:
        target_table = _bq_table()

    table_ref = _bigquery_table_ref(target_table)
    if not table_ref:
        return None

    try:
        from google.cloud import bigquery
    except Exception as exc:
        log.warning("BigQuery dependency not installed: %s", exc)
        return None

    sql = _build_bigquery_sql(question, target_table)

    try:
        client = bigquery.Client(project=project)
        rows = client.query(sql).result()
        results = [dict(row) for row in rows]
        return {
            "source": "bigquery",
            "sql": sql,
            "time_series": results,
            "market_filter": None,
            "total_revenue_usd": sum(float(r.get("revenue_usd", 0)) for r in results if r.get("revenue_usd") is not None),
        }
    except Exception as exc:
        log.warning("BigQuery real source failed; falling back to mock data: %s", exc)
        return None


async def fetch_splunk_data(question: str) -> dict[str, Any]:
    real = await _fetch_splunk_real(question)
    if real is not None:
        return real
    raise RuntimeError("No real Splunk configuration is available; mock mode is disabled.")


async def fetch_bigquery_data(question: str) -> dict[str, Any]:
    real = await _fetch_bigquery_real(question)
    if real is not None:
        return real
    raise RuntimeError("No real BigQuery configuration is available; mock mode is disabled.")


async def fetch_sources_for_question(question: str, selected_sources: list[str]) -> list[dict[str, Any]]:
    result = []
    if "splunk" in selected_sources:
        result.append(await fetch_splunk_data(question))
    if "bigquery" in selected_sources:
        result.append(await fetch_bigquery_data(question))
    return result
