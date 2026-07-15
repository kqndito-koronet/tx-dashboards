#!/usr/bin/env python3
import csv
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tx-strategy-v2" / "data"
ACTIVE_LEDGER = DATA / "tx_active_ledger.csv"
COMPLETED_READBACK = DATA / "tx_friday_readback_completed.csv"
APPLY_LOG = DATA / "tx_friday_readback_apply_log.csv"

LOG_FIELDS = [
    "readback_id",
    "source_ledger_id",
    "apply_result",
    "reason",
    "ledger_status_after",
    "applied_at",
]

COMPLETED_FIELDS = [
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


def write_rows(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def has_completed_signal(row):
    status = (row.get("meeting_status") or "").strip().lower()
    if status and status not in {"pending friday review", "pending", "not reviewed"}:
        return True
    return any((row.get(field) or "").strip() for field in ["actual_result", "actual_learning"])


def apply_readback(ledger_row, readback):
    actual_result = (readback.get("actual_result") or "").strip()
    actual_learning = (readback.get("actual_learning") or "").strip()
    blocker = (readback.get("blocker") or "").strip()
    next_action = (readback.get("route_next") or "").strip()
    owner = (readback.get("owner") or "").strip()
    due_date = (readback.get("due_date") or "").strip()

    summary_parts = []
    if actual_result:
        summary_parts.append(f"Result: {actual_result}")
    if actual_learning:
        summary_parts.append(f"Learning: {actual_learning}")

    if summary_parts:
        ledger_row["read_safe_summary"] = " | ".join(summary_parts)
    if blocker:
        ledger_row["objection_or_blocker"] = blocker
    if next_action:
        ledger_row["next_action"] = next_action
    if owner:
        ledger_row["next_action_owner"] = owner
    if due_date:
        ledger_row["due_date"] = due_date
    if readback.get("next_surface"):
        ledger_row["downstream_artifact"] = readback.get("next_surface", "")

    ledger_row["status"] = "Updated from Friday readback"
    ledger_row["last_updated_at"] = date.today().isoformat()
    return ledger_row


def main():
    ledger_rows = read_rows(ACTIVE_LEDGER)
    if not ledger_rows:
        write_rows(APPLY_LOG, LOG_FIELDS, [])
        return

    fieldnames = list(ledger_rows[0].keys())
    by_id = {row.get("ledger_id", ""): row for row in ledger_rows}
    log_rows = []

    completed_rows = read_rows(COMPLETED_READBACK)
    for readback in completed_rows:
        readback_id = readback.get("readback_id", "")
        source_id = readback.get("source_ledger_id", "")
        if not has_completed_signal(readback):
            log_rows.append({
                "readback_id": readback_id,
                "source_ledger_id": source_id,
                "apply_result": "held",
                "reason": "No completed signal: meeting_status pending and actual result/learning blank.",
                "ledger_status_after": by_id.get(source_id, {}).get("status", ""),
                "applied_at": "",
            })
            continue
        if source_id not in by_id:
            log_rows.append({
                "readback_id": readback_id,
                "source_ledger_id": source_id,
                "apply_result": "rejected",
                "reason": "Source ledger row not found.",
                "ledger_status_after": "",
                "applied_at": "",
            })
            continue

        by_id[source_id] = apply_readback(by_id[source_id], readback)
        log_rows.append({
            "readback_id": readback_id,
            "source_ledger_id": source_id,
            "apply_result": "applied",
            "reason": "Completed readback updated active ledger row.",
            "ledger_status_after": by_id[source_id].get("status", ""),
            "applied_at": date.today().isoformat(),
        })

    write_rows(ACTIVE_LEDGER, fieldnames, [by_id[row.get("ledger_id", "")] for row in ledger_rows])
    write_rows(APPLY_LOG, LOG_FIELDS, log_rows)

    if not COMPLETED_READBACK.exists():
        write_rows(COMPLETED_READBACK, COMPLETED_FIELDS, [])


if __name__ == "__main__":
    main()
