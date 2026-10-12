import asyncio

import pytest

from data_sources import (
    _bigquery_table_ref,
    _build_bigquery_sql,
    fetch_bigquery_data,
    fetch_splunk_data,
)


def test_bigquery_ref_uses_lenslight_orders_table_by_default(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "lenslight-511415")
    monkeypatch.setenv("BQ_DATASET", "lenslight")
    monkeypatch.setenv("BQ_TABLE", "orders")
    assert _bigquery_table_ref() == "lenslight-511415.lenslight.orders"


def test_bigquery_sql_uses_checkout_events_for_funnel_questions(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "lenslight-511415")
    monkeypatch.setenv("BQ_DATASET", "lenslight")
    monkeypatch.setenv("BQ_TABLE", "orders")
    sql = _build_bigquery_sql("How is the checkout funnel converting across the funnel steps?")
    assert "checkout_events" in sql
    assert "event_name" in sql
    assert "session_id" in sql


def test_splunk_requires_real_config():
    with pytest.raises(RuntimeError, match="real Splunk"):
        asyncio.run(fetch_splunk_data("Why did checkout rate drop yesterday in the US?"))


def test_bigquery_requires_real_config():
    with pytest.raises(RuntimeError, match="real BigQuery"):
        asyncio.run(fetch_bigquery_data("Summarize revenue by market last week"))
