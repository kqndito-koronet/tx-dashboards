#!/usr/bin/env python3
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRIDAY = ROOT / "tx-strategy-v2" / "data" / "tx_friday_generated_queue.csv"
OUTPUT = ROOT / "tx-strategy-v2" / "data" / "tx_friday_readback_seed.csv"

FIELDS = [
    "readback_id",
    "source_ledger_id",
    "initiative",
    "account",
    "meeting_status",
    "decision_or_commitment",
    "owner",
    "due_date",
    "expected_outcome",
    "expected_learning",
    "actual_result",
    "actual_learning",
    "blocker",
    "route_next",
    "next_surface",
]


def read_rows(path):
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def readback_row(row, index):
    initiative = row.get("initiative", "")
    account = row.get("account", "")
    owner = row.get("next_action_owner") or row.get("owner_lane", "")
    return {
        "readback_id": f"TXR-{index:03d}",
        "source_ledger_id": row.get("ledger_id", ""),
        "initiative": initiative,
        "account": account,
        "meeting_status": "Pending Friday review",
        "decision_or_commitment": row.get("decision_needed", ""),
        "owner": owner,
        "due_date": row.get("due_date", ""),
        "expected_outcome": row.get("expected_outcome", ""),
        "expected_learning": row.get("expected_learning", ""),
        "actual_result": "",
        "actual_learning": "",
        "blocker": row.get("objection_or_blocker", ""),
        "route_next": row.get("next_action", ""),
        "next_surface": row.get("downstream_artifact", ""),
    }


def main():
    rows = read_rows(FRIDAY)
    output_rows = [readback_row(row, i + 1) for i, row in enumerate(rows)]
    with OUTPUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)


if __name__ == "__main__":
    main()
