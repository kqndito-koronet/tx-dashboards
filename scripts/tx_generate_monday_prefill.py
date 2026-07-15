#!/usr/bin/env python3
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tx-strategy-v2" / "data"
ACTIVE_LEDGER = DATA / "tx_active_ledger.csv"
MONDAY_QUEUE = DATA / "tx_monday_generated_queue.csv"
FRIDAY_READBACK = DATA / "tx_friday_readback_seed.csv"
OUTPUT = DATA / "tx_monday_leadership_prefill.csv"

FIELDS = [
    "prefill_id",
    "source",
    "surface",
    "initiative",
    "account",
    "decision_or_question",
    "why_monday",
    "recommendation_or_next_action",
    "owner",
    "due_date",
    "evidence_or_link",
    "trust_label",
    "status",
]


def read_rows(path):
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(rows):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def monday_reason(row):
    initiative = (row.get("initiative") or "").lower()
    trust = (row.get("trust_label") or "").lower()
    artifact = (row.get("downstream_artifact") or "").lower()
    if "strategic" in initiative or "account" in artifact:
        return "Strategic account or cross-lane decision."
    if "system" in initiative or "canonical" in artifact or "workflow" in artifact:
        return "System/canonical risk that can confuse execution."
    if "rose" in (row.get("owner_lane") or "").lower() or "dashboard" in artifact or "pending reconciliation" in trust:
        return "Data proof or metric definition needed before stronger claims travel."
    return "Leadership-visible item carried from active ledger."


def from_monday_queue(row, index):
    return {
        "prefill_id": f"MON-{index:03d}",
        "source": "active_ledger",
        "surface": row.get("downstream_artifact", ""),
        "initiative": row.get("initiative", ""),
        "account": row.get("account", ""),
        "decision_or_question": row.get("decision_needed") or row.get("conversation_expected", ""),
        "why_monday": monday_reason(row),
        "recommendation_or_next_action": row.get("next_action", ""),
        "owner": row.get("next_action_owner") or row.get("owner_lane", ""),
        "due_date": row.get("due_date", ""),
        "evidence_or_link": row.get("evidence_link") or row.get("source_link", ""),
        "trust_label": row.get("trust_label", ""),
        "status": row.get("status", ""),
    }


def from_readback(row, index):
    account = row.get("account", "")
    decision = row.get("decision_or_commitment", "")
    return {
        "prefill_id": f"FCO-{index:03d}",
        "source": "friday_readback_seed",
        "surface": row.get("next_surface", ""),
        "initiative": row.get("initiative", ""),
        "account": account,
        "decision_or_question": decision,
        "why_monday": "Friday carryover requiring leadership visibility or re-route.",
        "recommendation_or_next_action": row.get("route_next", ""),
        "owner": row.get("owner", ""),
        "due_date": row.get("due_date", ""),
        "evidence_or_link": row.get("source_ledger_id", ""),
        "trust_label": "Pending Friday readback",
        "status": row.get("meeting_status", ""),
    }


def dedupe(rows):
    seen = set()
    out = []
    for row in rows:
        key = (
            row.get("source", ""),
            row.get("initiative", ""),
            row.get("account", ""),
            row.get("decision_or_question", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def main():
    rows = []
    for index, row in enumerate(read_rows(MONDAY_QUEUE), start=1):
        rows.append(from_monday_queue(row, index))

    offset = len(rows) + 1
    for index, row in enumerate(read_rows(FRIDAY_READBACK), start=offset):
        # Keep Friday carryover visible but separate from Monday active ledger items.
        rows.append(from_readback(row, index))

    write_rows(dedupe(rows))


if __name__ == "__main__":
    main()
