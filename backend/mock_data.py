"""Mock data generators for Splunk and BigQuery queries — retail e-commerce flavoured.
Deterministically generates realistic-looking results based on question keywords, including
market/region filters (e.g. "US", "EMEA") and relative time windows ("yesterday", "last week")."""
import random
import re
from datetime import datetime, timezone, timedelta
from typing import Optional


MARKETS = ["US", "CA", "UK", "DE", "FR", "IN", "AU", "JP", "BR"]
MARKET_WEIGHTS = {"US": 1.0, "CA": 0.35, "UK": 0.55, "DE": 0.5, "FR": 0.45, "IN": 0.4, "AU": 0.25, "JP": 0.3, "BR": 0.3}


def _seed(q: str):
    random.seed(abs(hash(q.lower())) % (10**8))


def _detect_market(q: str) -> Optional[str]:
    ql = q.lower()
    aliases = {
        "US": ["us", "u.s", "usa", "united states", "america"],
        "UK": ["uk", "u.k", "britain", "england"],
        "DE": ["de", "germany", "deutschland"],
        "FR": ["france", "fr "],
        "IN": [" india", "in market", "india market"],
        "CA": ["canada"],
        "AU": ["australia"],
        "JP": ["japan"],
        "BR": ["brazil"],
    }
    for code, keys in aliases.items():
        for k in keys:
            if k in ql:
                return code
    return None


def _detect_window(q: str) -> tuple[str, int]:
    """Returns ('days'|'hours', count)."""
    ql = q.lower()
    if "yesterday" in ql:
        return "hours", 24  # intraday for yesterday
    if m := re.search(r"last\s+(\d+)\s+day", ql):
        return "days", int(m.group(1))
    if m := re.search(r"last\s+(\d+)\s+week", ql):
        return "days", int(m.group(1)) * 7
    if "last week" in ql:
        return "days", 7
    if "last month" in ql:
        return "days", 30
    if "today" in ql or "last 24" in ql or "last day" in ql:
        return "hours", 24
    return "days", 14


def _hours_series(hours: int, generator):
    now = datetime.now(timezone.utc)
    out = []
    for i in range(hours):
        row = {"time": (now - timedelta(hours=hours - i - 1)).strftime("%H:00")}
        row.update(generator(i))
        out.append(row)
    return out


def _days_series(days: int, generator):
    now = datetime.now(timezone.utc)
    out = []
    for i in range(days):
        row = {"date": (now - timedelta(days=days - i - 1)).strftime("%b %d")}
        row.update(generator(i))
        out.append(row)
    return out


def splunk_mock(question: str) -> dict:
    _seed("splunk:" + question)
    q = question.lower()
    market = _detect_market(question)
    unit, span = _detect_window(question)

    # Checkout / cart / funnel focused — Splunk sees frontend event logs
    if any(k in q for k in ["checkout", "cart", "funnel", "conversion", "abandon", "purchase flow"]):
        def gen(i):
            # Yesterday US dip scenario: inject a visible drop around hour 14-18
            base_rate = random.uniform(2.6, 3.4)
            if unit == "hours" and 14 <= i <= 19 and (market == "US" or market is None):
                base_rate *= random.uniform(0.45, 0.65)  # 35-55% drop
            cart_starts = random.randint(1800, 4200)
            completed = int(cart_starts * (base_rate / 100))
            return {
                "cart_starts": cart_starts,
                "checkouts_completed": completed,
                "conversion_rate_pct": round(base_rate, 2),
            }
        series = _hours_series(span, gen) if unit == "hours" else _days_series(span, gen)

        # Funnel step dropoff
        funnel = [
            {"step": "product_view", "users": random.randint(42000, 68000)},
            {"step": "add_to_cart", "users": random.randint(14000, 22000)},
            {"step": "checkout_started", "users": random.randint(6500, 9500)},
            {"step": "payment_entered", "users": random.randint(3200, 5000)},
            {"step": "order_placed", "users": random.randint(1200, 2800)},
        ]
        # Top errors driving abandonment
        err = [
            {"error": e, "events": random.randint(80, 1200), "pct_of_abandons": round(random.uniform(2, 24), 1)}
            for e in ["PaymentDeclined:AVS_MISMATCH", "AddressValidation:timeout", "Stripe:3DS_challenge_failed", "InventoryHold:out_of_stock", "Shipping:zone_unavailable"]
        ]
        err.sort(key=lambda x: -x["events"])
        return {
            "source": "splunk",
            "spl": f'index=prod_web event IN (checkout_started, order_placed) {"market=" + market if market else ""} earliest=-{span}{"h" if unit=="hours" else "d"} | timechart count by event',
            "market_filter": market,
            "time_series": series,
            "funnel": funnel,
            "top_errors": err[:5],
        }

    # Error / failure
    if any(k in q for k in ["error", "fail", "exception", "crash", "5xx", "500"]):
        def gen(i):
            return {"errors": random.randint(10, 180), "warnings": random.randint(5, 60)}
        series = _hours_series(24 if unit == "hours" else span, gen) if unit == "hours" else _days_series(span, gen)
        top = [
            {"service": s, "count": random.randint(40, 500), "p95_ms": random.randint(120, 1900)}
            for s in ["checkout-api", "payments-gateway", "catalog-service", "cart-service", "inventory-sync", "fulfillment-worker"]
        ]
        top.sort(key=lambda x: -x["count"])
        return {
            "source": "splunk",
            "spl": "index=prod_web sourcetype=app_log level IN (ERROR, FATAL) earliest=-24h | stats count by service",
            "time_series": series,
            "top_services": top[:6],
        }

    # Latency
    if any(k in q for k in ["latency", "slow", "performance", "p95", "p99", "response time"]):
        services = ["checkout-api", "payments-gateway", "catalog-service", "cart-service", "inventory-sync"]
        return {
            "source": "splunk",
            "spl": 'index=prod_web sourcetype=access_log | stats perc95(response_time) as p95 by service',
            "latency_table": [
                {"service": s, "p50_ms": random.randint(40, 220), "p95_ms": random.randint(300, 1800), "p99_ms": random.randint(900, 3200), "requests": random.randint(1500, 90000)}
                for s in services
            ],
        }

    # Default: event volume
    def gen(i):
        return {"page_views": random.randint(1200, 6400), "sessions": random.randint(400, 2800)}
    series = _hours_series(span, gen) if unit == "hours" else _days_series(span, gen)
    return {
        "source": "splunk",
        "spl": f"index=prod_web earliest=-{span}{'h' if unit=='hours' else 'd'} | timechart span=1{'h' if unit=='hours' else 'd'} count",
        "time_series": series,
    }


def bigquery_mock(question: str) -> dict:
    _seed("bq:" + question)
    q = question.lower()
    market = _detect_market(question)
    unit, span = _detect_window(question)

    # Checkout / conversion
    if any(k in q for k in ["checkout", "cart", "funnel", "conversion", "abandon"]):
        def gen(i):
            base_cr = random.uniform(2.4, 3.2)
            if unit == "hours" and 14 <= i <= 19 and (market == "US" or market is None):
                base_cr *= random.uniform(0.4, 0.6)
            sessions = random.randint(2200, 5600)
            orders = int(sessions * (base_cr / 100))
            aov = round(random.uniform(58, 142), 2)
            return {"sessions": sessions, "orders": orders, "checkout_rate_pct": round(base_cr, 2), "revenue_usd": round(orders * aov, 2)}
        series = _hours_series(span, gen) if unit == "hours" else _days_series(span, gen)

        # Market breakdown — if a specific market was asked, order it to the top
        regions = []
        for m in MARKETS:
            w = MARKET_WEIGHTS[m]
            base_cr = random.uniform(2.4, 3.4)
            if m == "US" and ("yesterday" in q or market == "US"):
                base_cr *= random.uniform(0.55, 0.75)  # US dipped
            regions.append({
                "market": m,
                "sessions": int(random.randint(12000, 90000) * w),
                "orders": int(random.randint(300, 2600) * w),
                "checkout_rate_pct": round(base_cr, 2),
                "aov_usd": round(random.uniform(55, 160), 2),
                "revenue_usd": round(random.uniform(18000, 310000) * w, 2),
            })
        if market:
            regions.sort(key=lambda r: 0 if r["market"] == market else 1)
        else:
            regions.sort(key=lambda r: -r["revenue_usd"])

        # Device / payment breakdown
        devices = [
            {"device": d, "sessions": random.randint(3000, 42000), "checkout_rate_pct": round(random.uniform(1.4, 4.1), 2)}
            for d in ["desktop", "mobile_web", "ios_app", "android_app"]
        ]
        payments = [
            {"method": p, "attempts": random.randint(500, 8000), "success_rate_pct": round(random.uniform(74, 97.5), 2)}
            for p in ["card", "apple_pay", "google_pay", "paypal", "klarna"]
        ]
        time_frame = "HOUR" if unit == "hours" else "DAY"
        market_filter = f' AND market="{market}"' if market else ""
        sql = (
            f"SELECT market, COUNT(DISTINCT session_id) sessions, COUNTIF(event='order_placed') orders, "
            f"SAFE_DIVIDE(COUNTIF(event='order_placed'), COUNT(DISTINCT session_id))*100 cr "
            f"FROM `retail.events` WHERE event_ts BETWEEN "
            f"TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {span} {time_frame}) AND CURRENT_TIMESTAMP()"
            f"{market_filter} GROUP BY market"
        )
        return {
            "source": "bigquery",
            "sql": sql,
            "market_filter": market,
            "time_series": series,
            "markets": regions,
            "devices": devices,
            "payment_methods": payments,
        }

    # Revenue / sales
    if any(k in q for k in ["revenue", "sales", "order", "purchase", "transaction", "gmv"]):
        def gen(i):
            return {"revenue_usd": round(random.uniform(12000, 48000), 2), "orders": random.randint(180, 920)}
        series = _days_series(span if unit == "days" else 14, gen)
        regions = [
            {"market": m, "revenue_usd": round(random.uniform(50000, 320000) * MARKET_WEIGHTS[m], 2), "aov_usd": round(random.uniform(45, 180), 2)}
            for m in MARKETS
        ]
        regions.sort(key=lambda x: -x["revenue_usd"])
        return {
            "source": "bigquery",
            "sql": "SELECT market, SUM(amount_usd) revenue, AVG(amount_usd) aov FROM `retail.orders` WHERE order_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY) GROUP BY market",
            "time_series": series,
            "markets": regions,
            "total_revenue_usd": round(sum(s["revenue_usd"] for s in series), 2),
        }

    # Users / signups / activity
    if any(k in q for k in ["user", "signup", "active", "dau", "mau", "retention"]):
        def gen(i):
            return {"new_users": random.randint(80, 420), "dau": random.randint(1800, 6200)}
        series = _days_series(span if unit == "days" else 14, gen)
        return {
            "source": "bigquery",
            "sql": "SELECT DATE(event_ts) d, COUNTIF(event='signup') new_users, COUNT(DISTINCT user_id) dau FROM `retail.events` WHERE event_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY) GROUP BY d",
            "time_series": series,
        }

    # Default: channel breakdown
    cats = ["organic", "paid_search", "social", "email", "referral", "direct"]
    rows = [{"channel": c, "sessions": random.randint(2000, 48000), "conversions": random.randint(50, 1800)} for c in cats]
    rows.sort(key=lambda x: -x["sessions"])
    return {
        "source": "bigquery",
        "sql": "SELECT channel, COUNT(*) sessions, COUNTIF(converted) conversions FROM `retail.sessions` WHERE session_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY) GROUP BY channel",
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
            title_suffix = f" — {d['market_filter']}" if d.get("market_filter") else ""
            artifacts.append({
                "type": "chart",
                "chart_type": "bar" if src == "splunk" else "line",
                "title": f"{src.upper()} — Trend{title_suffix}",
                "x_key": x_key,
                "y_keys": keys,
                "data": d["time_series"],
            })
        if "funnel" in d:
            artifacts.append({"type": "table", "title": "Checkout funnel", "rows": d["funnel"]})
        if "top_errors" in d:
            artifacts.append({"type": "table", "title": "Top errors driving abandonment", "rows": d["top_errors"]})
        if "top_services" in d:
            artifacts.append({"type": "table", "title": "Top services by error count", "rows": d["top_services"]})
        if "latency_table" in d:
            artifacts.append({"type": "table", "title": "Service latency", "rows": d["latency_table"]})
        if "markets" in d:
            artifacts.append({"type": "table", "title": "Market breakdown", "rows": d["markets"]})
        if "devices" in d:
            artifacts.append({"type": "table", "title": "Device breakdown", "rows": d["devices"]})
        if "payment_methods" in d:
            artifacts.append({"type": "table", "title": "Payment method performance", "rows": d["payment_methods"]})
        if "channel_breakdown" in d:
            artifacts.append({"type": "table", "title": "Channel breakdown", "rows": d["channel_breakdown"]})
        q = d.get("spl") or d.get("sql")
        if q:
            artifacts.append({"type": "query", "title": f"{src.upper()} query", "language": "spl" if src == "splunk" else "sql", "code": q})
    return artifacts
