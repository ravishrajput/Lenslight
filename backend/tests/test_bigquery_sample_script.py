from datetime import date, datetime, timezone
from types import SimpleNamespace

from scripts.append_bigquery_sample import _serialize_for_schema, generate_demo_orders


def test_demo_orders_are_repeatable_and_cover_requested_days():
    first = generate_demo_orders(2, 2, 42, date(2026, 10, 17))
    second = generate_demo_orders(2, 2, 42, date(2026, 10, 17))

    assert first == second
    assert len(first) == 4
    assert {row["transaction_timestamp"].date() for row in first} == {
        date(2026, 10, 16),
        date(2026, 10, 17),
    }
    assert len({row["order_id"] for row in first}) == len(first)


def test_schema_serialization_respects_bigquery_field_types():
    order = {
        "transaction_timestamp": datetime(2026, 10, 17, tzinfo=timezone.utc),
        "order_id": "lenslight-demo-20261017-00001",
        "market": "US",
        "order_value": 123.45,
    }
    schema = [
        SimpleNamespace(name="transaction_timestamp", field_type="TIMESTAMP", mode="REQUIRED"),
        SimpleNamespace(name="order_id", field_type="STRING", mode="REQUIRED"),
        SimpleNamespace(name="market", field_type="STRING", mode="REQUIRED"),
        SimpleNamespace(name="order_value", field_type="NUMERIC", mode="REQUIRED"),
    ]

    row = _serialize_for_schema(order, schema)

    assert row == {
        "transaction_timestamp": "2026-10-17T00:00:00Z",
        "order_id": "lenslight-demo-20261017-00001",
        "market": "US",
        "order_value": "123.45",
    }


def test_schema_serialization_refuses_unknown_required_columns():
    schema = [
        SimpleNamespace(name="required_customer_id", field_type="STRING", mode="REQUIRED"),
    ]

    try:
        _serialize_for_schema({"transaction_timestamp": datetime.now(timezone.utc)}, schema)
    except ValueError as exc:
        assert "required_customer_id" in str(exc)
    else:
        raise AssertionError("Expected unsupported required field to fail explicitly")
