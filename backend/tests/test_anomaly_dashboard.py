import asyncio
from datetime import date

import server
from data_sources import build_bigquery_anomaly_dashboard, build_local_anomaly_dashboard


def _row(timestamp, event="browse", level="INFO", response_time="100", order_value=""):
    return {
        "timestamp": timestamp,
        "event": event,
        "level": level,
        "response_time": response_time,
        "order_value": order_value,
    }


def test_dashboard_flags_measured_changes_against_previous_period():
    rows = [
        *[_row("2026-10-16T10:00:00Z") for _ in range(10)],
        _row("2026-10-16T10:01:00Z", "checkout_started"),
        _row("2026-10-16T10:02:00Z", "checkout_started"),
        _row("2026-10-16T10:03:00Z", "order_placed", order_value="100"),
        _row("2026-10-16T10:04:00Z", "order_placed", order_value="100"),
        *[_row("2026-10-17T10:00:00Z", response_time="300") for _ in range(7)],
        *[_row("2026-10-17T10:01:00Z", level="ERROR", response_time="300") for _ in range(3)],
        _row("2026-10-17T10:02:00Z", "checkout_started", response_time="300"),
        _row("2026-10-17T10:03:00Z", "order_placed", response_time="300", order_value="100"),
    ]

    result = build_local_anomaly_dashboard(rows, days=1)

    assert result["period"] == {"start": "2026-10-17", "end": "2026-10-17"}
    assert result["baseline_period"] == {"start": "2026-10-16", "end": "2026-10-16"}
    assert {anomaly["key"] for anomaly in result["anomalies"]} == {
        "error_rate_pct",
        "orders",
        "revenue_usd",
        "avg_response_time_ms",
    }


def test_dashboard_does_not_flag_stable_metrics():
    rows = [
        _row("2026-10-16T10:00:00Z", "checkout_started"),
        _row("2026-10-16T10:01:00Z", "order_placed", order_value="100"),
        _row("2026-10-17T10:00:00Z", "checkout_started"),
        _row("2026-10-17T10:01:00Z", "order_placed", order_value="100"),
    ]

    result = build_local_anomaly_dashboard(rows, days=1)

    assert result["anomalies"] == []


def test_dashboard_does_not_compare_when_baseline_day_is_missing():
    rows = [_row("2026-10-17T10:00:00Z", level="ERROR")]

    result = build_local_anomaly_dashboard(rows, days=1)

    assert result["baseline_available"] is False
    assert result["anomalies"] == []


def test_bigquery_dashboard_flags_orders_and_revenue_changes():
    daily_rows = [
        {"date": date(2026, 10, 16), "orders": 100, "revenue_usd": 10000, "avg_order_value_usd": 100},
        {"date": date(2026, 10, 17), "orders": 50, "revenue_usd": 4000, "avg_order_value_usd": 80},
    ]

    result = build_bigquery_anomaly_dashboard(daily_rows, days=1)

    assert result["source"] == "bigquery"
    assert result["status"] == "available"
    assert result["current_available"] is True
    assert result["baseline_available"] is True
    assert {anomaly["key"] for anomaly in result["anomalies"]} == {
        "orders",
        "revenue_usd",
        "avg_order_value_usd",
    }


def test_bigquery_dashboard_does_not_flag_incomplete_comparison_window():
    daily_rows = [
        {"date": date(2026, 10, 17), "orders": 2, "revenue_usd": 200, "avg_order_value_usd": 100},
    ]

    result = build_bigquery_anomaly_dashboard(daily_rows, days=1)

    assert result["status"] == "available"
    assert result["baseline_available"] is False
    assert result["anomalies"] == []


def test_dashboard_endpoint_analyzes_and_returns_both_sources(monkeypatch):
    async def local_result(_days):
        return {
            "source": "local_logs",
            "latest_data_date": "2026-10-17",
            "period": {"start": "2026-10-17", "end": "2026-10-17"},
            "baseline_period": {"start": "2026-10-16", "end": "2026-10-16"},
            "baseline_available": True,
            "current_metrics": {"orders": 4},
            "baseline_metrics": {"orders": 5},
            "daily": [],
            "anomalies": [],
        }

    async def bigquery_result(_days):
        return {
            "source": "bigquery",
            "status": "available",
            "latest_data_date": "2026-10-17",
            "period": {"start": "2026-10-17", "end": "2026-10-17"},
            "baseline_period": {"start": "2026-10-16", "end": "2026-10-16"},
            "baseline_available": True,
            "current_metrics": {"orders": 7},
            "baseline_metrics": {"orders": 8},
            "daily": [],
            "anomalies": [],
        }

    analyzed = {}

    async def analyze(question, sources, session_id):
        analyzed["question"] = question
        analyzed["sources"] = sources
        return "Both sources analyzed."

    monkeypatch.setattr(server, "fetch_local_anomaly_dashboard", local_result)
    monkeypatch.setattr(server, "fetch_bigquery_anomaly_dashboard", bigquery_result)
    monkeypatch.setattr(server, "analyze", analyze)

    result = asyncio.run(
        server.dashboard_anomalies(days=1, user={"user_id": "test-user"})
    )

    assert [source["source"] for source in result["sources"]] == ["local_logs", "bigquery"]
    assert all(source["status"] == "available" for source in result["sources"])
    assert analyzed["sources"] == result["sources"]
    assert result["summary"] == "Both sources analyzed."


def test_dashboard_endpoint_keeps_local_data_when_bigquery_is_unavailable(monkeypatch):
    async def local_result(_days):
        return {
            "source": "local_logs",
            "latest_data_date": "2026-10-17",
            "period": {"start": "2026-10-17", "end": "2026-10-17"},
            "baseline_period": {"start": "2026-10-16", "end": "2026-10-16"},
            "current_metrics": {},
            "baseline_metrics": {},
            "daily": [],
            "anomalies": [],
        }

    async def bigquery_result(_days):
        return {"source": "bigquery", "status": "unavailable", "error": "Credentials missing"}

    async def analyze(_question, sources, session_id):
        assert sources[1]["status"] == "unavailable"
        return "Local source analyzed; BigQuery is unavailable."

    monkeypatch.setattr(server, "fetch_local_anomaly_dashboard", local_result)
    monkeypatch.setattr(server, "fetch_bigquery_anomaly_dashboard", bigquery_result)
    monkeypatch.setattr(server, "analyze", analyze)

    result = asyncio.run(
        server.dashboard_anomalies(days=1, user={"user_id": "test-user"})
    )

    assert [source["status"] for source in result["sources"]] == ["available", "unavailable"]
    assert result["summary"] == "Local source analyzed; BigQuery is unavailable."
