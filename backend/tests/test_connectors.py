import asyncio

import pytest

from data_sources import (
    _bigquery_table_ref,
    _build_bigquery_sql,
    fetch_sources_for_question,
    fetch_local_logs_data,
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


def test_splunk_address_question_includes_validation_outcomes():
    from data_sources import _build_splunk_query

    query = _build_splunk_query("Why is the shipping address not getting added?")
    assert "event IN (address_added, address_validation_failed)" in query
    assert "stats count by event, source, market" in query


def test_local_csv_address_analysis_includes_outcomes_and_error_examples(tmp_path, monkeypatch):
    csv_path = tmp_path / "events.csv"
    csv_path.write_text(
        "timestamp,event,level,response_time,source,market,session_id,order_id,order_value,error_code,error_message\n"
        "2026-10-12T10:00:00Z,address_added,INFO,120,checkout-api,US,s-1,,, ,\n"
        "2026-10-12T10:01:00Z,address_validation_failed,ERROR,1800,checkout-api,US,s-2,,,ADDRESS_POSTAL_MISMATCH,Postal code mismatch\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LOCAL_LOGS_CSV", str(csv_path))

    result = asyncio.run(fetch_local_logs_data("Why is the address not getting added in the US?"))

    assert result["source"] == "local_logs"
    assert {row["event"] for row in result["funnel"]} == {"address_added", "address_validation_failed"}
    assert result["total_errors"] == 1
    assert result["log_examples"][0]["error_code"] == "ADDRESS_POSTAL_MISMATCH"


def test_legacy_source_ids_use_local_csv(tmp_path, monkeypatch):
    csv_path = tmp_path / "events.csv"
    csv_path.write_text(
        "timestamp,event,level,response_time,source,market,session_id,order_id,order_value,error_code,error_message\n"
        "2026-10-12T10:00:00Z,address_added,INFO,120,checkout-api,US,s-1,,,,\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LOCAL_LOGS_CSV", str(csv_path))

    result = asyncio.run(fetch_sources_for_question("Analyze address activity", ["splunk", "bigquery"]))

    assert [source["source"] for source in result] == ["local_logs"]


def test_splunk_requires_real_config():
    with pytest.raises(RuntimeError, match="real Splunk"):
        asyncio.run(fetch_splunk_data("Why did checkout rate drop yesterday in the US?"))


def test_bigquery_requires_real_config():
    with pytest.raises(RuntimeError, match="real BigQuery"):
        asyncio.run(fetch_bigquery_data("Summarize revenue by market last week"))
