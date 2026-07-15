#!/usr/bin/env python3
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "tx-strategy-v2" / "data" / "tx_issue_ledger_candidates.csv"
OUTPUT = ROOT / "tx-strategy-v2" / "data" / "tx_ledger_candidate_validation.csv"

REQUIRED_FIELDS = [
    "candidate_id",
    "issue_url",
    "account",
    "initiative",
    "next_action_owner_date",
    "trust_label",
    "routing",
    "conversation_expected",
    "expected_outcome",
    "expected_learning",
    "kpi_or_leading_indicator",
]

OUTPUT_FIELDS = [
    "candidate_id",
    "issue_number",
    "account",
    "initiative",
    "can_promote",
    "missing_fields",
    "validation_notes",
    "recommended_owner",
    "recommended_route",
]


def rows(path):
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def missing(row):
    return [field for field in REQUIRED_FIELDS if not (row.get(field) or "").strip()]


def route_owner(row):
    route = (row.get("routing") or "").lower()
    initiative = (row.get("initiative") or "").lower()
    if "rose" in route or "dashboard" in route or "report" in initiative:
        return "Rose"
    if "value" in route:
        return "Lautaro / Facu"
    if "workflow" in route or "system" in initiative:
        return "Nahua / Codex"
    if "facu" in route or "approval" in route:
        return "Facu"
    if "sell" in initiative:
        return "Christine / Pablito"
    if "buy" in initiative or "list" in initiative:
        return "Cata / CS"
    if "grow" in initiative:
        return "Facu / Mercury"
    return "Pablito triage"


def validate(row):
    missing_fields = missing(row)
    can_promote = not missing_fields
    notes = "Ready for human promotion review." if can_promote else "Cannot promote until missing fields are completed."
    return {
        "candidate_id": row.get("candidate_id", ""),
        "issue_number": row.get("issue_number", ""),
        "account": row.get("account", ""),
        "initiative": row.get("initiative", ""),
        "can_promote": "yes" if can_promote else "no",
        "missing_fields": "; ".join(missing_fields),
        "validation_notes": notes,
        "recommended_owner": route_owner(row),
        "recommended_route": row.get("routing", ""),
    }


def main():
    candidate_rows = rows(INPUT)
    validation_rows = [validate(row) for row in candidate_rows]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(validation_rows)


if __name__ == "__main__":
    main()
