import base64
import asyncio
import csv
import json
import logging
import os
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

import httpx

log = logging.getLogger(__name__)


def _question_lower(question: str) -> str:
    return (question or "").lower()


def _local_logs_path() -> Path:
    default_path = Path(__file__).resolve().parent / "data" / "splunk_events.csv"
    return Path(os.getenv("LOCAL_LOGS_CSV", str(default_path)))


def _filter_local_logs(question: str, rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[str]]:
    q = _question_lower(question)
    filters = []
    address_question = any(term in q for term in ("address", "postal", "postcode", "zip code"))
    checkout_question = any(term in q for term in ("checkout", "cart", "conversion", "funnel"))

    if address_question:
        rows = [row for row in rows if row["event"] in {"address_added", "address_validation_failed"}]
        filters.append("address outcomes")
    elif checkout_question:
        checkout_events = {
            "add_to_cart",
            "checkout_started",
            "address_added",
            "address_validation_failed",
            "shipping_info_entered",
            "payment_info_entered",
            "order_placed",
        }
        rows = [row for row in rows if row["event"] in checkout_events]
        filters.append("checkout events")

    if any(term in q for term in ("error", "exception", "fail", "failure")):
        rows = [row for row in rows if row["level"] in {"ERROR", "FATAL"}]
        filters.append("error-level events")

    selected_market = next(
        (market for market in ("US", "UK", "DE", "CA") if re.search(rf"\b{market.lower()}\b", q)),
        None,
    )
    if selected_market:
        rows = [row for row in rows if row["market"] == selected_market]
        filters.append(f"market {selected_market}")

    days_match = re.search(r"(?:last|past)\s+(\d+)\s+days?", q)
    days = int(days_match.group(1)) if days_match else None
    if days is None and any(term in q for term in ("last week", "past week", "this week")):
        days = 7
    if "yesterday" in q:
        days = 1
    if days and rows:
        latest_day = date.fromisoformat(max(row["timestamp"][:10] for row in rows))
        start_day = latest_day - timedelta(days=days - 1)
        rows = [row for row in rows if date.fromisoformat(row["timestamp"][:10]) >= start_day]
        filters.append(f"last {days} days in the CSV")

    return rows, filters or ["all events"]


def _summarize_local_logs(question: str, rows: list[dict[str, str]]) -> dict[str, Any]:
    filtered_rows, filters = _filter_local_logs(question, rows)
    event_groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    market_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    daily_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    error_groups: dict[tuple[str, str, str, str], int] = Counter()

    for row in filtered_rows:
        event_groups[(row["event"], row["source"], row["market"])].append(row)
        market_groups[row["market"]].append(row)
        daily_groups[row["timestamp"][:10]].append(row)
        if row["level"] in {"ERROR", "FATAL"}:
            key = (row["error_code"], row["error_message"], row["source"], row["market"])
            error_groups[key] += 1

    event_summary = []
    for (event, source, market), group in sorted(event_groups.items()):
        latencies = [int(row["response_time"]) for row in group if row["response_time"]]
        event_summary.append({
            "event": event,
            "source": source,
            "market": market,
            "count": len(group),
            "failures": sum(row["level"] in {"ERROR", "FATAL"} for row in group),
            "avg_response_time_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0,
        })

    markets = []
    for market, group in sorted(market_groups.items()):
        checkouts = sum(row["event"] == "checkout_started" for row in group)
        orders = [row for row in group if row["event"] == "order_placed" and row["level"] == "INFO"]
        revenue = sum(float(row["order_value"]) for row in orders if row["order_value"])
        markets.append({
            "market": market,
            "checkout_starts": checkouts,
            "orders": len(orders),
            "address_failures": sum(row["event"] == "address_validation_failed" for row in group),
            "completion_rate_pct": round(len(orders) / checkouts * 100, 1) if checkouts else 0,
            "revenue_usd": round(revenue, 2),
        })

    time_series = []
    for day, group in sorted(daily_groups.items()):
        orders = [row for row in group if row["event"] == "order_placed" and row["level"] == "INFO"]
        time_series.append({
            "date": day,
            "events": len(group),
            "errors": sum(row["level"] in {"ERROR", "FATAL"} for row in group),
            "orders": len(orders),
            "revenue_usd": round(sum(float(row["order_value"]) for row in orders if row["order_value"]), 2),
        })

    top_errors = [
        {"error_code": code, "error_message": message, "source": source, "market": market, "events": count}
        for (code, message, source, market), count in sorted(error_groups.items(), key=lambda item: item[1], reverse=True)
    ]
    examples = [
        {key: row[key] for key in ("timestamp", "event", "level", "source", "market", "session_id", "error_code", "error_message")}
        for row in filtered_rows
        if row["level"] in {"ERROR", "FATAL"}
    ][:12]

    return {
        "source": "local_logs",
        "spl": f"CSV filters: {', '.join(filters)}",
        "filters": filters,
        "total_events": len(filtered_rows),
        "total_errors": sum(row["level"] in {"ERROR", "FATAL"} for row in filtered_rows),
        "event_summary": event_summary,
        "funnel": event_summary,
        "top_errors": top_errors,
        "markets": markets,
        "time_series": time_series,
        "log_examples": examples,
    }


async def fetch_local_logs_data(question: str) -> dict[str, Any]:
    path = _local_logs_path()
    try:
        with path.open(newline="", encoding="utf-8") as csv_file:
            rows = list(csv.DictReader(csv_file))
    except OSError as exc:
        raise RuntimeError(f"Local logs CSV could not be read: {path}") from exc
    if not rows:
        raise RuntimeError(f"Local logs CSV has no events: {path}")
    return _summarize_local_logs(question, rows)


def build_local_anomaly_dashboard(rows: list[dict[str, str]], days: int) -> dict[str, Any]:
    """Compare the latest available days in the local event log with the prior equal window."""
    dated_rows: dict[date, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        dated_rows[date.fromisoformat(row["timestamp"][:10])].append(row)

    if not dated_rows:
        raise RuntimeError("Local logs CSV has no dated events")

    latest_day = max(dated_rows)
    current_start = latest_day - timedelta(days=days - 1)
    baseline_end = current_start - timedelta(days=1)
    baseline_start = baseline_end - timedelta(days=days - 1)
    current_available = all(
        current_start + timedelta(days=offset) in dated_rows
        for offset in range(days)
    )
    baseline_available = all(
        baseline_start + timedelta(days=offset) in dated_rows
        for offset in range(days)
    )

    def period_metrics(start: date, end: date) -> dict[str, float]:
        period_rows = [
            row
            for day, daily_rows in dated_rows.items()
            if start <= day <= end
            for row in daily_rows
        ]
        error_count = sum(row["level"] in {"ERROR", "FATAL"} for row in period_rows)
        order_count = sum(
            row["event"] == "order_placed" and row["level"] == "INFO"
            for row in period_rows
        )
        checkout_count = sum(row["event"] == "checkout_started" for row in period_rows)
        latencies = [
            float(row["response_time"])
            for row in period_rows
            if row.get("response_time")
        ]
        return {
            "events": float(len(period_rows)),
            "errors": float(error_count),
            "error_rate_pct": error_count / len(period_rows) * 100 if period_rows else 0.0,
            "orders": float(order_count),
            "revenue_usd": sum(
                float(row["order_value"])
                for row in period_rows
                if row["event"] == "order_placed" and row.get("order_value")
            ),
            "avg_response_time_ms": sum(latencies) / len(latencies) if latencies else 0.0,
            "checkout_completion_pct": order_count / checkout_count * 100 if checkout_count else 0.0,
        }

    current = period_metrics(current_start, latest_day)
    baseline = period_metrics(baseline_start, baseline_end)
    candidates = (
        ("Error rate", "error_rate_pct", "increase", 25.0, 1.0, "%", 3.0),
        ("Orders", "orders", "decrease", 25.0, 0.0, "", 50.0),
        ("Revenue", "revenue_usd", "decrease", 25.0, 0.0, " USD", 50.0),
        ("Average response time", "avg_response_time_ms", "increase", 25.0, 100.0, " ms", 50.0),
        ("Checkout completion", "checkout_completion_pct", "decrease", 20.0, 5.0, "%", 40.0),
    )
    anomalies = _detect_dashboard_anomalies(
        current,
        baseline,
        candidates,
        current_available and baseline_available,
    )

    daily = []
    for offset in range(days):
        day = current_start + timedelta(days=offset)
        day_rows = dated_rows.get(day, [])
        orders = [
            row for row in day_rows
            if row["event"] == "order_placed" and row["level"] == "INFO"
        ]
        daily.append({
            "date": day.isoformat(),
            "events": len(day_rows),
            "errors": sum(row["level"] in {"ERROR", "FATAL"} for row in day_rows),
            "orders": len(orders),
            "revenue_usd": round(sum(float(row["order_value"]) for row in orders if row.get("order_value")), 2),
        })

    return {
        "source": "local_logs",
        "latest_data_date": latest_day.isoformat(),
        "period": {"start": current_start.isoformat(), "end": latest_day.isoformat()},
        "baseline_period": {"start": baseline_start.isoformat(), "end": baseline_end.isoformat()},
        "current_available": current_available,
        "baseline_available": baseline_available,
        "current_metrics": {key: round(value, 2) for key, value in current.items()},
        "baseline_metrics": {key: round(value, 2) for key, value in baseline.items()},
        "daily": daily,
        "anomalies": anomalies,
    }


def _detect_dashboard_anomalies(
    current: dict[str, float],
    baseline: dict[str, float],
    candidates: tuple[tuple[str, str, str, float, float, str, float], ...],
    baseline_available: bool,
) -> list[dict[str, Any]]:
    if not baseline_available:
        return []

    anomalies = []
    for label, key, direction, relative_threshold, absolute_threshold, unit, high_threshold in candidates:
        current_value = current[key]
        baseline_value = baseline[key]
        delta = current_value - baseline_value
        adverse_delta = delta if direction == "increase" else -delta
        relative_change = adverse_delta / baseline_value * 100 if baseline_value else None
        if adverse_delta <= 0 or adverse_delta < absolute_threshold:
            continue
        if baseline_value and (relative_change or 0) < relative_threshold:
            continue
        if not baseline_value and current_value < absolute_threshold:
            continue

        severity = "high" if (relative_change or 0) >= high_threshold else "medium"
        anomalies.append({
            "metric": label,
            "key": key,
            "severity": severity,
            "direction": direction,
            "current": round(current_value, 2),
            "baseline": round(baseline_value, 2),
            "change_pct": round(relative_change, 1) if relative_change is not None else None,
            "unit": unit,
        })
    return anomalies


async def fetch_local_anomaly_dashboard(days: int) -> dict[str, Any]:
    path = _local_logs_path()
    try:
        with path.open(newline="", encoding="utf-8") as csv_file:
            rows = list(csv.DictReader(csv_file))
    except OSError as exc:
        raise RuntimeError(f"Local logs CSV could not be read: {path}") from exc
    if not rows:
        raise RuntimeError(f"Local logs CSV has no events: {path}")
    return build_local_anomaly_dashboard(rows, days)


def build_bigquery_anomaly_dashboard(daily_rows: list[dict[str, Any]], days: int) -> dict[str, Any]:
    dated_metrics = {
        date.fromisoformat(str(row["date"])[:10]): {
            "orders": float(row["orders"] or 0),
            "revenue_usd": float(row["revenue_usd"] or 0),
            "avg_order_value_usd": float(row["avg_order_value_usd"] or 0),
        }
        for row in daily_rows
    }
    if not dated_metrics:
        return {
            "source": "bigquery",
            "status": "no_data",
            "error": "The configured BigQuery orders table contains no dated rows.",
        }

    latest_day = max(dated_metrics)
    current_start = latest_day - timedelta(days=days - 1)
    baseline_end = current_start - timedelta(days=1)
    baseline_start = baseline_end - timedelta(days=days - 1)
    current_dates = [current_start + timedelta(days=offset) for offset in range(days)]
    baseline_dates = [baseline_start + timedelta(days=offset) for offset in range(days)]
    earliest_day = min(dated_metrics)
    current_available = earliest_day <= current_start
    baseline_available = earliest_day <= baseline_start

    def aggregate(period_dates: list[date]) -> dict[str, float]:
        rows = [dated_metrics[day] for day in period_dates if day in dated_metrics]
        order_count = sum(row["orders"] for row in rows)
        revenue = sum(row["revenue_usd"] for row in rows)
        weighted_average = (
            sum(row["avg_order_value_usd"] * row["orders"] for row in rows) / order_count
            if order_count else 0.0
        )
        return {
            "orders": order_count,
            "revenue_usd": revenue,
            "avg_order_value_usd": weighted_average,
        }

    current = aggregate(current_dates)
    baseline = aggregate(baseline_dates)
    candidates = (
        ("Orders", "orders", "decrease", 25.0, 0.0, "", 50.0),
        ("Revenue", "revenue_usd", "decrease", 25.0, 0.0, " USD", 50.0),
        ("Average order value", "avg_order_value_usd", "decrease", 20.0, 5.0, " USD", 40.0),
    )
    complete_periods = current_available and baseline_available
    daily = [
        {
            "date": day.isoformat(),
            **dated_metrics.get(day, {"orders": 0.0, "revenue_usd": 0.0, "avg_order_value_usd": 0.0}),
        }
        for day in current_dates
    ]
    return {
        "source": "bigquery",
        "status": "available",
        "latest_data_date": latest_day.isoformat(),
        "period": {"start": current_start.isoformat(), "end": latest_day.isoformat()},
        "baseline_period": {"start": baseline_start.isoformat(), "end": baseline_end.isoformat()},
        "current_available": current_available,
        "baseline_available": baseline_available,
        "coverage_note": "Dates with no order rows are treated as zero orders and zero revenue.",
        "current_metrics": {key: round(value, 2) for key, value in current.items()},
        "baseline_metrics": {key: round(value, 2) for key, value in baseline.items()},
        "daily": daily,
        "anomalies": _detect_dashboard_anomalies(current, baseline, candidates, complete_periods),
    }


def _query_bigquery_anomaly_days(days: int) -> dict[str, Any]:
    from google.cloud import bigquery

    project = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise RuntimeError("BigQuery is not configured: set GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT.")

    table_ref = _bigquery_table_ref()
    if not table_ref:
        raise RuntimeError("BigQuery is not configured: no destination table was selected.")

    client = bigquery.Client(project=project)
    table = client.get_table(table_ref)
    field_names = {field.name for field in table.schema}
    missing_fields = {"transaction_timestamp", "order_value"} - field_names
    if missing_fields:
        raise RuntimeError(
            f"BigQuery table {table_ref} is missing required dashboard fields: "
            f"{', '.join(sorted(missing_fields))}."
        )

    timestamp_type = next(
        field.field_type.upper()
        for field in table.schema
        if field.name == "transaction_timestamp"
    )
    if timestamp_type not in {"TIMESTAMP", "DATETIME", "DATE"}:
        raise RuntimeError(
            f"BigQuery field transaction_timestamp must be TIMESTAMP, DATETIME, or DATE, not {timestamp_type}."
        )

    latest_query = (
        f"SELECT MAX(DATE(transaction_timestamp)) AS latest_date "
        f"FROM `{table_ref}` WHERE transaction_timestamp IS NOT NULL"
    )
    latest_row = next(iter(client.query(latest_query).result()), None)
    latest_value = latest_row["latest_date"] if latest_row else None
    if latest_value is None:
        return {"source": "bigquery", "status": "no_data", "error": "BigQuery table has no dated rows."}

    latest_day = latest_value if isinstance(latest_value, date) else date.fromisoformat(str(latest_value)[:10])
    baseline_start = latest_day - timedelta(days=(days * 2) - 1)
    daily_query = (
        "SELECT DATE(transaction_timestamp) AS date, "
        "COUNT(*) AS orders, "
        "SUM(CAST(order_value AS FLOAT64)) AS revenue_usd, "
        "AVG(CAST(order_value AS FLOAT64)) AS avg_order_value_usd "
        f"FROM `{table_ref}` "
        "WHERE DATE(transaction_timestamp) BETWEEN @start_date AND @end_date "
        "GROUP BY date ORDER BY date"
    )
    query_config = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("start_date", "DATE", baseline_start),
        bigquery.ScalarQueryParameter("end_date", "DATE", latest_day),
    ])
    rows = [dict(row) for row in client.query(daily_query, job_config=query_config).result()]
    return build_bigquery_anomaly_dashboard(rows, days)


async def fetch_bigquery_anomaly_dashboard(days: int) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(_query_bigquery_anomaly_days, days)
    except Exception as exc:
        log.warning("BigQuery dashboard query failed: %s", exc)
        return {"source": "bigquery", "status": "unavailable", "error": str(exc)}


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
    table = (table_name or _bq_table()).strip()
    if not table:
        table = _bq_table()
    if "." in table:
        parts = table.split(".")
        if len(parts) == 2:
            dataset, table = parts
        elif len(parts) == 3:
            project, dataset, table = parts
        else:
            return ""
    else:
        dataset = _bq_dataset()
    if not project:
        return ""
    return f"{project}.{dataset}.{table}"


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
        log.warning("BigQuery query failed: %s", exc)
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
    selected = selected_sources or ["local_logs", "bigquery"]
    result = []

    # Treat the old Splunk source ID as local CSV for clients with a cached frontend.
    if "local_logs" in selected or "splunk" in selected:
        result.append(await fetch_local_logs_data(question))

    if "bigquery" in selected:
        try:
            result.append(await fetch_bigquery_data(question))
        except Exception as exc:
            log.warning("BigQuery unavailable; continuing with other selected sources: %s", exc)
            result.append({
                "source": "bigquery",
                "status": "unavailable",
                "error": str(exc),
                "time_series": [],
            })

    return result
