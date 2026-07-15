#!/usr/bin/env python3
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tx-strategy-v2" / "data"
ACTIVE_LEDGER = DATA / "tx_active_ledger.csv"
OUTPUT = DATA / "tx_agent_lane_queues.csv"

FIELDS = [
    "queue_id",
    "agent_lane",
    "ledger_id",
    "initiative",
    "account",
    "input_signal",
    "conversation_expected",
    "expected_outcome",
    "expected_learning",
    "output_expected",
    "first_move",
    "acceptance_criteria",
    "review_gate",
    "due_date",
    "source_link",
    "trust_label",
    "approval_state",
    "status",
]


def read_rows(path):
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def lane(row):
    owner = (row.get("owner_lane") or row.get("next_action_owner") or "").strip()
    lower = owner.lower()
    if "rose" in lower:
        return "Rose"
    if "mercury" in lower or "mercurio" in lower:
        return "Mercurio"
    if "socrates" in lower:
        return "Socrates"
    if "pablito" in lower:
        return "Pablito"
    if "nahua" in lower:
        return "Nahua"
    if "codex" in lower:
        return "Codex"
    if "facu" in lower:
        return "Facu"
    return owner or "Unassigned"


def acceptance(row):
    initiative = (row.get("initiative") or "").lower()
    artifact = (row.get("downstream_artifact") or "").lower()
    if lane(row) == "Rose":
        return "Source/date/trust label present; claim can be shown as verified, directional, or not-board-ready."
    if lane(row) == "Mercurio":
        return "Account action includes target, value prop, expected result, expected learning, owner, and due date."
    if lane(row) == "Socrates":
        return "Message uses approved framing, no unsupported claims, and links back to source rows."
    if lane(row) == "Pablito":
        return "Owner/date/action completeness checked; overdue or blocked rows routed before review."
    if lane(row) == "Nahua":
        return "Canonical/workflow issue classified, patch path proposed, stale or conflicting memory quarantined."
    if "strategic" in initiative or "account" in artifact:
        return "One next account conversation, blocker, owner, metric, and date are visible."
    return "Output has source, owner, due date, next action, and review gate."


def first_move(row):
    lane_name = lane(row)
    initiative = (row.get("initiative") or "").strip()
    account = (row.get("account") or "").strip() or "the relevant object"
    if lane_name == "Rose":
        return f"Confirm source/date/trust label for {initiative or 'this claim'} and mark missing data."
    if lane_name == "Mercurio":
        return f"Convert {account} into an account action proposal only if owner/data validation exists."
    if lane_name == "Socrates":
        return "Turn the approved row into short stakeholder-facing copy with links and caveats."
    if lane_name == "Pablito":
        return "Check owner/date/action completeness and add missing fields to the readback queue."
    if lane_name == "Nahua":
        return "Classify whether this is workflow-backed, missing, patched, parked, or quarantined."
    if lane_name == "Facu":
        return "Approve, change, or park the decision; avoid silent strategy drift."
    return "Clarify owner, next action, and review gate before execution."


def review_gate(row):
    approval = (row.get("approval_state") or "").strip()
    trust = (row.get("trust_label") or "").strip()
    if "approved" in approval.lower():
        return "Can proceed if owner/date/action are current."
    if "facu" in approval.lower():
        return "Needs Facu review before stakeholder-facing use."
    if "owner" in approval.lower():
        return "Needs initiative/account owner validation before active execution."
    if "rose" in approval.lower() or "data" in trust.lower():
        return "Needs Rose/source validation before stronger claim."
    return "Keep as draft/review row until approval state is explicit."


def row_to_queue(row, index):
    return {
        "queue_id": f"AGQ-{index:03d}",
        "agent_lane": lane(row),
        "ledger_id": row.get("ledger_id", ""),
        "initiative": row.get("initiative", ""),
        "account": row.get("account", ""),
        "input_signal": row.get("read_safe_summary") or row.get("decision_needed", ""),
        "conversation_expected": row.get("conversation_expected", ""),
        "expected_outcome": row.get("expected_outcome", ""),
        "expected_learning": row.get("expected_learning", ""),
        "output_expected": row.get("next_action") or row.get("decision_needed", ""),
        "first_move": first_move(row),
        "acceptance_criteria": acceptance(row),
        "review_gate": review_gate(row),
        "due_date": row.get("due_date", ""),
        "source_link": row.get("evidence_link") or row.get("source_link", ""),
        "trust_label": row.get("trust_label", ""),
        "approval_state": row.get("approval_state", ""),
        "status": row.get("status", ""),
    }


def main():
    rows = read_rows(ACTIVE_LEDGER)
    output = [row_to_queue(row, i + 1) for i, row in enumerate(rows) if (row.get("status") or "").lower() != "done"]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output)


if __name__ == "__main__":
    main()
