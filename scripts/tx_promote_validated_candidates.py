#!/usr/bin/env python3
import csv
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tx-strategy-v2" / "data"
SEED = DATA / "tx_execution_ledger_seed_2026-07-15.csv"
CANDIDATES = DATA / "tx_issue_ledger_candidates.csv"
VALIDATION = DATA / "tx_ledger_candidate_validation.csv"
ACTIVE_LEDGER = DATA / "tx_active_ledger.csv"
PROMOTION_LOG = DATA / "tx_ledger_promotion_log.csv"

APPROVAL_LABEL = "tx-approved-for-ledger"

PROMOTION_FIELDS = [
    "candidate_id",
    "issue_number",
    "issue_url",
    "can_promote",
    "approval_label_present",
    "promotion_result",
    "reason",
    "promoted_ledger_id",
    "promoted_at",
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


def validation_by_candidate():
    return {row.get("candidate_id", ""): row for row in read_rows(VALIDATION)}


def has_approval_label(candidate):
    labels = (candidate.get("issue_labels") or "").lower()
    return APPROVAL_LABEL in {label.strip() for label in labels.split(",")}


def split_owner_date(value):
    value = (value or "").strip()
    if not value:
        return "", ""
    for separator in ["|", " - ", " by ", " due "]:
        if separator in value:
            left, right = value.split(separator, 1)
            return left.strip(), right.strip()
    return value, ""


def candidate_to_ledger(candidate, index, fieldnames):
    owner, due_date = split_owner_date(candidate.get("next_action_owner_date", ""))
    promoted_at = date.today().isoformat()
    row = {field: "" for field in fieldnames}
    row.update({
        "ledger_id": f"TXL-ISSUE-{candidate.get('issue_number') or index:0>4}",
        "created_at": candidate.get("created_at", "")[:10] or promoted_at,
        "source_type": "github_issue",
        "source_link": candidate.get("issue_url", ""),
        "read_safe_summary": candidate.get("read_safe_interpretation") or candidate.get("what_happened") or candidate.get("result_or_learning", ""),
        "initiative": candidate.get("initiative", ""),
        "conversation_expected": candidate.get("conversation_expected", ""),
        "expected_outcome": candidate.get("expected_outcome", ""),
        "expected_learning": candidate.get("expected_learning", ""),
        "kpi_or_leading_indicator": candidate.get("kpi_or_leading_indicator", ""),
        "objection_or_blocker": candidate.get("blocker_or_objection", ""),
        "before_friday_owner_task": candidate.get("need_from_facu_or_system", ""),
        "account": candidate.get("account", ""),
        "hypothesis": "",
        "workflow": "tx_feedback_issue_promotion",
        "owner_lane": owner or candidate.get("routing", ""),
        "value_prop_required": "yes" if candidate.get("value_prop_signals") else "",
        "value_prop_link": "",
        "evidence_link": candidate.get("source_link") or candidate.get("issue_url", ""),
        "trust_label": candidate.get("trust_label", ""),
        "approval_state": "Approved for ledger",
        "decision_needed": candidate.get("need_from_facu_or_system", ""),
        "next_action": candidate.get("next_action_owner_date", ""),
        "next_action_owner": owner,
        "due_date": due_date,
        "friday_visible": "yes",
        "monday_visible": "yes" if "monday" in (candidate.get("routing") or "").lower() else "no",
        "downstream_artifact": candidate.get("routing", ""),
        "status": "Promoted",
        "last_updated_at": promoted_at,
    })
    return row


def main():
    seed_rows = read_rows(SEED)
    fieldnames = list(seed_rows[0].keys()) if seed_rows else []
    if not fieldnames:
        raise SystemExit("Seed ledger is missing or has no header.")

    validations = validation_by_candidate()
    active_rows = list(seed_rows)
    log_rows = []

    for index, candidate in enumerate(read_rows(CANDIDATES), start=1):
        candidate_id = candidate.get("candidate_id", "")
        validation = validations.get(candidate_id, {})
        can_promote = (validation.get("can_promote") or "").strip().lower() == "yes"
        approved = has_approval_label(candidate)
        issue_url = candidate.get("issue_url", "")
        promoted_id = ""

        if can_promote and approved:
            promoted = candidate_to_ledger(candidate, index, fieldnames)
            promoted_id = promoted["ledger_id"]
            active_rows.append(promoted)
            result = "promoted"
            reason = "Validation passed and approval label present."
        elif can_promote:
            result = "held"
            reason = f"Validation passed but missing {APPROVAL_LABEL} label."
        else:
            result = "rejected"
            reason = validation.get("missing_fields") or "Validation failed or candidate missing validation row."

        log_rows.append({
            "candidate_id": candidate_id,
            "issue_number": candidate.get("issue_number", ""),
            "issue_url": issue_url,
            "can_promote": "yes" if can_promote else "no",
            "approval_label_present": "yes" if approved else "no",
            "promotion_result": result,
            "reason": reason,
            "promoted_ledger_id": promoted_id,
            "promoted_at": date.today().isoformat() if promoted_id else "",
        })

    write_rows(ACTIVE_LEDGER, fieldnames, active_rows)
    write_rows(PROMOTION_LOG, PROMOTION_FIELDS, log_rows)


if __name__ == "__main__":
    main()
