#!/usr/bin/env python3
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVE_LEDGER = ROOT / "tx-strategy-v2" / "data" / "tx_active_ledger.csv"
SEED_LEDGER = ROOT / "tx-strategy-v2" / "data" / "tx_execution_ledger_seed_2026-07-15.csv"
OUT_DIR = ROOT / "tx-strategy-v2" / "data"
FRIDAY = OUT_DIR / "tx_friday_generated_queue.csv"
MONDAY = OUT_DIR / "tx_monday_generated_queue.csv"

FIELDS = [
    "ledger_id",
    "initiative",
    "account",
    "read_safe_summary",
    "conversation_expected",
    "expected_outcome",
    "expected_learning",
    "kpi_or_leading_indicator",
    "objection_or_blocker",
    "before_friday_owner_task",
    "owner_lane",
    "approval_state",
    "trust_label",
    "decision_needed",
    "next_action",
    "next_action_owner",
    "due_date",
    "downstream_artifact",
    "status",
]


def read_ledger():
    ledger = ACTIVE_LEDGER if ACTIVE_LEDGER.exists() else SEED_LEDGER
    if not ledger.exists():
        return []
    with ledger.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDS})


def visible(rows, field):
    return [row for row in rows if (row.get(field) or "").strip().lower() == "yes"]


def main():
    rows = read_ledger()
    write(FRIDAY, visible(rows, "friday_visible"))
    write(MONDAY, visible(rows, "monday_visible"))


if __name__ == "__main__":
    main()
