import csv
import random
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_PATHS = (
    ROOT_DIR / "samples" / "splunk_events.csv",
    ROOT_DIR / "backend" / "data" / "splunk_events.csv",
)
START_DATE = date(2026, 4, 13)
END_DATE = date(2026, 10, 13)
MARKETS = ("US", "UK", "DE", "CA")
EVENTS = (
    ("add_to_cart", "web-frontend"),
    ("checkout_started", "checkout-api"),
    ("address_added", "checkout-api"),
    ("shipping_info_entered", "checkout-api"),
    ("payment_info_entered", "payment-api"),
    ("order_placed", "checkout-api"),
)
ERROR_DETAILS = {
    "add_to_cart": ("CART_WRITE_TIMEOUT", "Cart update timed out"),
    "checkout_started": ("CHECKOUT_SESSION_FAILED", "Could not create checkout session"),
    "shipping_info_entered": ("SHIPPING_QUOTE_UNAVAILABLE", "Shipping quote service unavailable"),
    "payment_info_entered": ("PAYMENT_GATEWAY_TIMEOUT", "Payment gateway timed out"),
    "order_placed": ("ORDER_COMMIT_FAILED", "Order could not be committed"),
}
FIELDNAMES = (
    "timestamp",
    "event",
    "level",
    "response_time",
    "source",
    "market",
    "session_id",
    "order_id",
    "order_value",
    "error_code",
    "error_message",
)


def generate_events():
    rng = random.Random(20261013)
    current_date = START_DATE
    session_number = 0

    while current_date <= END_DATE:
        for market in MARKETS:
            session_number += 1
            session_id = f"sess-{current_date:%Y%m%d}-{market.lower()}"
            start = datetime.combine(current_date, time(8 + rng.randrange(12), rng.randrange(60)), tzinfo=timezone.utc)
            incident_day = current_date.toordinal() % 19 == 0
            failure_chance = 0.34 if incident_day else 0.22
            failure_at = rng.choices((0, 1, 2, 3, 4, None), weights=(1, 2, 3, 3, 1, 10))[0] if rng.random() < failure_chance else None

            for event_index, (event_name, source) in enumerate(EVENTS):
                if failure_at is not None and event_index > failure_at:
                    break

                failed = event_index == failure_at
                error_code = ""
                error_message = ""
                if failed:
                    level = "FATAL" if rng.random() < 0.15 else "ERROR"
                    response_time = rng.randint(1200, 4200 if incident_day else 3000)
                    if event_name == "address_added":
                        event_name = "address_validation_failed"
                        error_code, error_message = rng.choice((
                            ("ADDRESS_POSTAL_MISMATCH", "Postal code does not match the selected market"),
                            ("ADDRESS_LINE_REQUIRED", "Street address is required"),
                            ("ADDRESS_VALIDATION_TIMEOUT", "Address validation service timed out"),
                        ))
                    else:
                        error_code, error_message = ERROR_DETAILS[event_name]
                else:
                    level = "INFO"
                    response_time = rng.randint(70, 650)

                order_id = ""
                order_value = ""
                if event_name == "order_placed" and not failed:
                    order_id = f"ord-{session_number:06d}"
                    order_value = f"{rng.uniform(24.5, 480.0):.2f}"

                yield {
                    "timestamp": (start + timedelta(seconds=event_index * rng.randint(8, 24))).isoformat().replace("+00:00", "Z"),
                    "event": event_name,
                    "level": level,
                    "response_time": response_time,
                    "source": source,
                    "market": market,
                    "session_id": session_id,
                    "order_id": order_id,
                    "order_value": order_value,
                    "error_code": error_code,
                    "error_message": error_message,
                }

        current_date += timedelta(days=1)


def main():
    rows = list(generate_events())
    for output_path in OUTPUT_PATHS:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
    print(f"Generated six months of local log events: {len(rows)} rows")


if __name__ == "__main__":
    main()
