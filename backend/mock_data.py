"""Mock data generators for Splunk and BigQuery queries.
Deterministically generates realistic-looking results based on question keywords."""
import random
from datetime import datetime, timezone, timedelta


def _seed(q: str):
    random.seed(abs(hash(q.lower())) % (10**8))


def splunk_mock(question: str) -> dict:
    _seed("splunk:" + question)
    q = question.lower()

    # Error / failure focused query
    if any(k in q for k in ["error", "fail", "exception", "crash", "5xx", "500"]):
        hours = 24
        now = datetime.now(timezone.utc)
        series = [
            {
                "time": (now - timedelta(hours=hours - i - 1)).strftime("%H:00"),
                "errors": random.randint(10, 180),
                "warnings": random.randint(5, 60),
            }
            for i in range(hours)
        ]
        top = [
            {"service": s, "count": random.randint(40, 500), "p95_ms": random.randint(120, 1900)}
            for s in ["payments-api", "auth-svc", "search-indexer", "cart-service", "inventory-sync", "notification-worker"]
        ]
        top.sort(key=lambda x: -x["count"])
        return {
            "source": "splunk",
            "spl": f'index=prod sourcetype=app_log level IN (ERROR, FATAL) earliest=-24h | stats count by service',
            "total_events": sum(p["errors"] for p in series),
            "time_series": series,
            "top_services": top[:6],
        }

    # Latency / performance
    if any(k in q for k in ["latency", "slow", "performance", "p95", "p99", "response time"]):
        services = ["payments-api", "auth-svc", "search-indexer", "cart-service", "inventory-sync"]
        return {
            "source": "splunk",
            "spl": 'index=prod sourcetype=access_log | stats perc95(response_time) as p95 by service',
            "latency_table": [
                {"service": s, "p50_ms": random.randint(40, 220), "p95_ms": random.randint(300, 1800), "p99_ms": random.randint(900, 3200), "requests": random.randint(1500, 90000)}
                for s in services
            ],
        }

    # Default: event volume
    hours = 12
    now = datetime.now(timezone.utc)
    series = [
        {"time": (now - timedelta(hours=hours - i - 1)).strftime("%H:00"), "events": random.randint(400, 2800)}
        for i in range(hours)
    ]
    return {
        "source": "splunk",
        "spl": "index=prod earliest=-12h | timechart span=1h count",
        "time_series": series,
        "total_events": sum(p["events"] for p in series),
    }


def bigquery_mock(question: str) -> dict:
    _seed("bq:" + question)
    q = question.lower()

    # Revenue / sales focused
    if any(k in q for k in ["revenue", "sales", "order", "purchase", "transaction"]):
        days = 14
        now = datetime.now(timezone.utc)
        series = [
            {"date": (now - timedelta(days=days - i - 1)).strftime("%b %d"), "revenue_usd": round(random.uniform(12000, 48000), 2), "orders": random.randint(180, 920)}
            for i in range(days)
        ]
        regions = [
            {"region": r, "revenue_usd": round(random.uniform(50000, 320000), 2), "aov_usd": round(random.uniform(45, 180), 2)}
            for r in ["NA-East", "NA-West", "EMEA", "APAC", "LATAM"]
        ]
        regions.sort(key=lambda x: -x["revenue_usd"])
        return {
            "source": "bigquery",
            "sql": "SELECT DATE(order_ts) d, SUM(amount_usd) revenue, COUNT(*) orders FROM `analytics.orders` WHERE order_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY) GROUP BY d ORDER BY d",
            "time_series": series,
            "regions": regions,
            "total_revenue_usd": round(sum(s["revenue_usd"] for s in series), 2),
        }

    # Users / signups / activity
    if any(k in q for k in ["user", "signup", "active", "dau", "mau", "retention"]):
        days = 14
        now = datetime.now(timezone.utc)
        series = [
            {"date": (now - timedelta(days=days - i - 1)).strftime("%b %d"), "new_users": random.randint(80, 420), "dau": random.randint(1800, 6200)}
            for i in range(days)
        ]
        return {
            "source": "bigquery",
            "sql": "SELECT DATE(event_ts) d, COUNTIF(event='signup') new_users, COUNT(DISTINCT user_id) dau FROM `analytics.events` WHERE event_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY) GROUP BY d",
            "time_series": series,
        }

    # Default: generic aggregate
    cats = ["organic", "paid_search", "social", "email", "referral", "direct"]
    rows = [{"channel": c, "sessions": random.randint(2000, 48000), "conversions": random.randint(50, 1800)} for c in cats]
    rows.sort(key=lambda x: -x["sessions"])
    return {
        "source": "bigquery",
        "sql": "SELECT channel, COUNT(*) sessions, COUNTIF(converted) conversions FROM `analytics.sessions` WHERE session_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY) GROUP BY channel",
        "channel_breakdown": rows,
    }


def build_artifacts(sources_data: list[dict]) -> list[dict]:
    """Translate raw mock data into frontend-renderable artifacts (charts + tables)."""
    artifacts = []
    for d in sources_data:
        src = d["source"]
        if "time_series" in d and d["time_series"]:
            keys = [k for k in d["time_series"][0].keys() if k not in ("time", "date")]
            x_key = "time" if "time" in d["time_series"][0] else "date"
            artifacts.append({
                "type": "chart",
                "chart_type": "bar" if src == "splunk" else "line",
                "title": f"{src.upper()} — Trend",
                "x_key": x_key,
                "y_keys": keys,
                "data": d["time_series"],
            })
        if "top_services" in d:
            artifacts.append({"type": "table", "title": "Top services by error count", "rows": d["top_services"]})
        if "latency_table" in d:
            artifacts.append({"type": "table", "title": "Service latency", "rows": d["latency_table"]})
        if "regions" in d:
            artifacts.append({"type": "table", "title": "Revenue by region", "rows": d["regions"]})
        if "channel_breakdown" in d:
            artifacts.append({"type": "table", "title": "Channel breakdown", "rows": d["channel_breakdown"]})
        # Query artifact
        q = d.get("spl") or d.get("sql")
        if q:
            artifacts.append({"type": "query", "title": f"{src.upper()} query", "language": "spl" if src == "splunk" else "sql", "code": q})
    return artifacts
