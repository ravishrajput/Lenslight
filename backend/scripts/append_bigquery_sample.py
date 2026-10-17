"""Append deterministic synthetic recent orders to the configured BigQuery table."""

import argparse
import random
import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
MARKETS = ("US", "UK", "DE", "CA")
PAYMENT_METHODS = ("card", "paypal", "apple_pay", "google_pay")
REQUIRED_APP_FIELDS = {"transaction_timestamp", "order_id", "market", "order_value"}


def generate_demo_orders(
    days: int,
    orders_per_day: int,
    seed: int,
    end_date: date,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    orders = []
    start_date = end_date - timedelta(days=days - 1)
    for day_offset in range(days):
        order_date = start_date + timedelta(days=day_offset)
        for order_index in range(orders_per_day):
            order_id = f"lenslight-demo-{order_date:%Y%m%d}-{order_index + 1:05d}"
            timestamp = datetime.combine(
                order_date,
                time(hour=rng.randrange(24), minute=rng.randrange(60), second=rng.randrange(60)),
                tzinfo=timezone.utc,
            )
            orders.append({
                "transaction_timestamp": timestamp,
                "order_id": order_id,
                "market": rng.choice(MARKETS),
                "order_value": round(rng.uniform(24.5, 480.0), 2),
                "payment_method": rng.choice(PAYMENT_METHODS),
                "currency": "USD",
            })
    return orders


def _serialize_for_schema(order: dict[str, Any], schema: list[Any]) -> dict[str, Any]:
    row = {}
    for field in schema:
        name = field.name
        value = order.get(name)
        if value is None:
            if field.mode == "REQUIRED":
                raise ValueError(
                    f"Table requires unsupported field {name!r}; refusing to insert incomplete sample rows."
                )
            continue

        field_type = field.field_type.upper()
        if name == "transaction_timestamp":
            if field_type == "DATE":
                value = value.date().isoformat()
            elif field_type == "DATETIME":
                value = value.replace(tzinfo=None).isoformat(sep=" ")
            else:
                value = value.isoformat().replace("+00:00", "Z")
        elif field_type in {"NUMERIC", "BIGNUMERIC"}:
            value = str(value)
        elif field_type in {"FLOAT", "FLOAT64"}:
            value = float(value)
        elif field_type in {"INTEGER", "INT64"}:
            value = int(value)
        elif field_type == "STRING":
            value = str(value)
        row[name] = value
    return row


def _configured_table_parts() -> tuple[str, str, str]:
    import os

    project = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise ValueError("Set GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT in backend/.env.")

    dataset = os.getenv("BQ_DATASET", "lenslight")
    table = os.getenv("BQ_TABLE", "orders")
    if "." in table:
        parts = table.split(".")
        if len(parts) == 2:
            dataset, table = parts
        elif len(parts) == 3:
            project, dataset, table = parts
        else:
            raise ValueError("BQ_TABLE must be a table name, dataset.table, or project.dataset.table.")
    for identifier in (project, dataset, table):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", identifier):
            raise ValueError(f"Invalid BigQuery identifier: {identifier!r}")
    return project, dataset, table


def append_orders(days: int, orders_per_day: int, seed: int, dry_run: bool = False) -> int:
    from google.cloud import bigquery
    from google.api_core.exceptions import NotFound

    project, dataset, table_name = _configured_table_parts()
    client = bigquery.Client(project=project)
    table_id = f"{project}.{dataset}.{table_name}"
    try:
        table = client.get_table(table_id)
    except NotFound as exc:
        raise RuntimeError(f"BigQuery table {table_id} does not exist.") from exc

    schema_names = {field.name for field in table.schema}
    missing = REQUIRED_APP_FIELDS - schema_names
    if missing:
        raise ValueError(
            f"Table {table_id} is missing fields required by Lenslight: {', '.join(sorted(missing))}."
        )

    orders = generate_demo_orders(days, orders_per_day, seed, datetime.now(timezone.utc).date())
    order_ids = [order["order_id"] for order in orders]
    existing = set()
    for offset in range(0, len(order_ids), 500):
        batch = order_ids[offset:offset + 500]
        job = client.query(
            f"SELECT order_id FROM `{table_id}` WHERE order_id IN UNNEST(@order_ids)",
            job_config=bigquery.QueryJobConfig(
                query_parameters=[bigquery.ArrayQueryParameter("order_ids", "STRING", batch)]
            ),
        )
        existing.update(row.order_id for row in job.result())

    rows = [
        _serialize_for_schema(order, table.schema)
        for order in orders
        if order["order_id"] not in existing
    ]
    if not rows:
        print(f"No rows to append; all {len(orders)} deterministic sample IDs already exist in {table_id}.")
        return 0

    if dry_run:
        print(f"Dry run: would append {len(rows)} synthetic orders to {table_id}.")
        return len(rows)

    errors = client.insert_rows_json(
        table_id,
        rows,
        row_ids=[row["order_id"] for row in rows],
    )
    if errors:
        raise RuntimeError(f"BigQuery rejected {len(errors)} row(s): {errors[:5]}")

    print(f"Appended {len(rows)} synthetic orders to {table_id}.")
    return len(rows)


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv(ROOT_DIR / ".env")
    parser = argparse.ArgumentParser(
        description="Append synthetic, recent order rows to the configured BigQuery orders table."
    )
    parser.add_argument("--days", type=int, default=7, help="Number of recent calendar days (1-365).")
    parser.add_argument("--orders-per-day", type=int, default=100, help="Synthetic orders generated per day.")
    parser.add_argument("--seed", type=int, default=20261017, help="Seed for repeatable generated data.")
    parser.add_argument("--dry-run", action="store_true", help="Check the table and report the insert count without writing.")
    args = parser.parse_args()

    if not 1 <= args.days <= 365:
        parser.error("--days must be between 1 and 365.")
    if not 1 <= args.orders_per_day <= 10000:
        parser.error("--orders-per-day must be between 1 and 10000.")

    append_orders(args.days, args.orders_per_day, args.seed, args.dry_run)


if __name__ == "__main__":
    main()
