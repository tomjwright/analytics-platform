"""Chaos generator for Customer File Drops.

Replays Olist Customers as one full CSV snapshot per day: a Customer appears from the
day of their first Order. Duplicates, malformed rows and address changes are injected at
seeded rates, so the same arguments always give byte-identical File Drops.

Usage: python -m analytics_platform.customer_drops --start 2017-01-01 --days 7 --out data/landing
"""

import argparse
import csv
import json
import random
import sys
import urllib.request
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path

# Pinned to a commit, so the source data can never change under a seed.
OLIST_COMMIT = "d9e49802f3e92d09ee94ab9ccc5e457f207a8959"
OLIST_URL = f"https://raw.githubusercontent.com/olist/work-at-olist-data/{OLIST_COMMIT}/datasets"
COLUMNS = ["customer_unique_id", "zip_code_prefix", "city", "state", "updated_at"]
FAULTS = ["missing_id", "bad_zip", "bad_date"]


@dataclass(frozen=True)
class ChaosRates:
    """Chance, per row per day, of each fault. All zero gives clean snapshots."""

    duplicate: float = 0.0
    malformed: float = 0.0
    address_change: float = 0.0


@dataclass(frozen=True)
class Customer:
    unique_id: str
    zip_code_prefix: str
    city: str
    state: str
    updated_at: date


def download(name: str, cache_dir: Path, base_url: str = OLIST_URL) -> Path:
    """Download one Olist file into cache_dir, unless it is already there."""
    url = f"{base_url}/{name}"
    if not url.startswith(("https://", "file://")):
        raise ValueError(f"refusing to download from {url}")
    path = cache_dir / name
    if not path.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        # Download beside the target, then rename: an interrupted download never looks cached.
        partial = path.with_name(f"{name}.part")
        urllib.request.urlretrieve(url, partial)  # noqa: S310  # nosemgrep: dynamic-urllib-use-detected
        partial.replace(path)
    return path


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))


def load_customers(customers_csv: Path, orders_csv: Path) -> list[Customer]:
    """One Customer per customer_unique_id, as at the day of their first Order."""
    order_day: dict[str, date] = {}
    for row in read_csv(orders_csv):
        order_day[row["customer_id"]] = date.fromisoformat(row["order_purchase_timestamp"][:10])

    first: dict[str, Customer] = {}
    for row in read_csv(customers_csv):
        customer = Customer(
            unique_id=row["customer_unique_id"],
            zip_code_prefix=row["customer_zip_code_prefix"],
            city=row["customer_city"],
            state=row["customer_state"],
            updated_at=order_day[row["customer_id"]],
        )
        earlier = first.get(customer.unique_id)
        if earlier is None or customer.updated_at < earlier.updated_at:
            first[customer.unique_id] = customer
    return sorted(first.values(), key=lambda c: c.unique_id)


def to_row(customer: Customer) -> dict[str, str]:
    return {
        "customer_unique_id": customer.unique_id,
        "zip_code_prefix": customer.zip_code_prefix,
        "city": customer.city,
        "state": customer.state,
        "updated_at": customer.updated_at.isoformat(),
    }


def malform(row: dict[str, str], fault: str) -> dict[str, str]:
    """A copy of the row with one fault that Silver must quarantine."""
    broken = dict(row)
    if fault == "missing_id":
        broken["customer_unique_id"] = ""
    elif fault == "bad_zip":
        broken["zip_code_prefix"] = "not-a-zip"
    else:
        broken["updated_at"] = "not-a-date"
    return broken


def generate(
    customers: list[Customer], start: date, days: int, rates: ChaosRates, seed: int
) -> dict[date, list[dict[str, str]]]:
    """The rows of each day's snapshot, from start for the given number of days."""
    rng = random.Random(seed)  # noqa: S311  # repeatable test data, not security
    current: dict[str, Customer] = {}  # the source system's state: unique_id -> Customer
    drops: dict[date, list[dict[str, str]]] = {}
    for offset in range(days):
        day = start + timedelta(days=offset)

        # Existing Customers move before today's new Customers arrive.
        for unique_id in sorted(current):
            if rng.random() < rates.address_change:
                new_address = rng.choice(customers)
                current[unique_id] = replace(
                    current[unique_id],
                    zip_code_prefix=new_address.zip_code_prefix,
                    city=new_address.city,
                    state=new_address.state,
                    updated_at=day,
                )
        for customer in customers:
            if customer.updated_at <= day and customer.unique_id not in current:
                current[customer.unique_id] = customer

        rows = []
        for unique_id in sorted(current):
            row = to_row(current[unique_id])
            if rng.random() < rates.malformed:
                row = malform(row, rng.choice(FAULTS))
            rows.append(row)
            if rng.random() < rates.duplicate:
                rows.append(dict(row))
        drops[day] = rows
    return drops


def write_drop(out: Path, day: date, rows: list[dict[str, str]]) -> Path:
    day_str = day.isoformat()
    path = out / "customers" / f"ingest_date={day_str}" / f"customers_{day_str}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=Path("data/olist"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--duplicate-rate", type=float, default=0.01)
    parser.add_argument("--malformed-rate", type=float, default=0.005)
    parser.add_argument("--address-change-rate", type=float, default=0.001)
    args = parser.parse_args(argv)

    customers = load_customers(
        download("olist_customers_dataset.csv", args.cache),
        download("olist_orders_dataset.csv", args.cache),
    )
    rates = ChaosRates(args.duplicate_rate, args.malformed_rate, args.address_change_rate)
    for day, rows in generate(customers, args.start, args.days, rates, args.seed).items():
        path = write_drop(args.out, day, rows)
        log = {"event": "customer_drop", "ingest_date": day.isoformat(), "rows": len(rows), "path": str(path)}
        print(json.dumps(log))
    return 0


if __name__ == "__main__":
    exit_code = main(sys.argv[1:])
    if exit_code != 0:
        sys.exit(exit_code)
