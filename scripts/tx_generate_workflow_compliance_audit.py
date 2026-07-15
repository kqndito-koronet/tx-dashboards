#!/usr/bin/env python3
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tx-strategy-v2" / "data"

ACTIVE_LEDGER = DATA / "tx_active_ledger.csv"
CANDIDATES = DATA / "tx_issue_ledger_candidates.csv"
CANDIDATE_VALIDATION = DATA / "tx_ledger_candidate_validation.csv"
AGENT_QUEUE = DATA / "tx_agent_lane_queues.csv"
READBACK = DATA / "tx_friday_readback_completed.csv"
OUTPUT = DATA / "tx_workflow_compliance_audit.csv"

FIELDS = [
    "compliance_id",
    "source_file",
    "source_id",
    "gate",
    "severity",
    "status",
    "owner_lane",
    "initiative",
    "account",
    "issue",
    "required_fix",
    "due_date",
    "downstream_artifact",
]


def read_rows(path):
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def present(value):
    return bool((value or "").strip())


def add(rows, source_file, source_id, gate, severity, status, owner_lane, initiative, account, issue, required_fix, due_date="", downstream_artifact=""):
    rows.append(
        {
            "source_file": source_file,
            "source_id": source_id,
            "gate": gate,
            "severity": severity,
            "status": status,
            "owner_lane": owner_lane,
            "initiative": initiative,
            "account": account,
            "issue": issue,
            "required_fix": required_fix,
            "due_date": due_date,
            "downstream_artifact": downstream_artifact,
        }
    )


def audit_active_ledger(output):
    rows = read_rows(ACTIVE_LEDGER)
    for row in rows:
        source_id = row.get("ledger_id", "")
        owner = row.get("owner_lane") or row.get("next_action_owner") or "Unassigned"
        initiative = row.get("initiative", "")
        account = row.get("account", "")
        due = row.get("due_date", "")
        artifact = row.get("downstream_artifact", "")
        required = {
            "source": row.get("source_link") or row.get("evidence_link"),
            "owner": owner if owner != "Unassigned" else "",
            "due date": due,
            "trust label": row.get("trust_label", ""),
            "approval state": row.get("approval_state", ""),
            "workflow": row.get("workflow", ""),
            "next action": row.get("next_action", ""),
        }
        missing = [name for name, value in required.items() if not present(value)]
        if missing:
            add(
                output,
                ACTIVE_LEDGER.name,
                source_id,
                "active_ledger_minimum_fields",
                "P0" if any(name in missing for name in ["owner", "due date", "next action"]) else "P1",
                "Needs fix",
                owner,
                initiative,
                account,
                f"Active row is missing: {', '.join(missing)}.",
                "Complete the missing fields or demote the row to seed/review-ready.",
                due,
                artifact,
            )
        if (row.get("friday_visible") or "").lower() == "yes":
            friday_required = {
                "expected outcome": row.get("expected_outcome", ""),
                "expected learning": row.get("expected_learning", ""),
                "KPI / leading indicator": row.get("kpi_or_leading_indicator", ""),
                "before-Friday owner task": row.get("before_friday_owner_task", ""),
            }
            friday_missing = [name for name, value in friday_required.items() if not present(value)]
            if friday_missing:
                add(
                    output,
                    ACTIVE_LEDGER.name,
                    source_id,
                    "friday_visibility_gate",
                    "P0",
                    "Needs owner validation",
                    owner,
                    initiative,
                    account,
                    f"Friday-visible row is missing: {', '.join(friday_missing)}.",
                    "Complete fields before sending the owner Friday ask.",
                    due,
                    "Friday generated queue",
                )
        if (row.get("monday_visible") or "").lower() == "yes" and not present(row.get("decision_needed", "")):
            add(
                output,
                ACTIVE_LEDGER.name,
                source_id,
                "monday_leadership_gate",
                "P1",
                "Needs decision framing",
                owner,
                initiative,
                account,
                "Monday-visible row has no decision needed.",
                "Add the leadership decision/question or remove from Monday view.",
                due,
                "Monday leadership prefill",
            )


def audit_candidate_validation(output):
    rows = read_rows(CANDIDATE_VALIDATION)
    for row in rows:
        status = (row.get("validation_status") or row.get("status") or "").lower()
        source_id = row.get("candidate_id") or row.get("issue_number") or row.get("ledger_id") or ""
        owner = row.get("owner_lane") or "Pablito"
        if "fail" in status or "missing" in status or "needs" in status:
            add(
                output,
                CANDIDATE_VALIDATION.name,
                source_id,
                "candidate_validation",
                "P0",
                "Held from active ledger",
                owner,
                row.get("initiative", ""),
                row.get("account", ""),
                row.get("validation_notes") or row.get("issue") or "Candidate did not pass validation.",
                "Patch the source issue/call packet with required fields before promotion.",
                row.get("due_date", ""),
                "Ledger candidates",
            )
        elif "pass" in status and "tx-approved-for-ledger" not in (row.get("labels") or "").lower():
            add(
                output,
                CANDIDATE_VALIDATION.name,
                source_id,
                "approval_label_gate",
                "P1",
                "Awaiting explicit approval",
                owner,
                row.get("initiative", ""),
                row.get("account", ""),
                "Candidate passed validation but is not explicitly approved for active ledger.",
                "Add GitHub label tx-approved-for-ledger after human review.",
                row.get("due_date", ""),
                "Promotion readiness",
            )


def audit_queue(output, path, gate, required_fields, default_owner):
    for row in read_rows(path):
        source_id = row.get("ledger_id") or row.get("queue_id") or row.get("readback_id") or ""
        missing = [name for name, field in required_fields.items() if not present(row.get(field, ""))]
        if missing:
            add(
                output,
                path.name,
                source_id,
                gate,
                "P1",
                "Incomplete generated row",
                row.get("owner_lane") or row.get("agent_lane") or row.get("next_action_owner") or default_owner,
                row.get("initiative", ""),
                row.get("account", ""),
                f"Generated row missing: {', '.join(missing)}.",
                "Patch upstream ledger/readback source; do not patch the generated view manually.",
                row.get("due_date", ""),
                path.name,
            )


def audit_readback(output):
    for row in read_rows(READBACK):
        source_id = row.get("readback_id") or row.get("ledger_id") or ""
        completion_signal = any(
            present(row.get(field, ""))
            for field in ["actual_result", "actual_learning", "next_surface", "meeting_status"]
        )
        if completion_signal and not present(row.get("ledger_id", "")):
            add(
                output,
                READBACK.name,
                source_id,
                "readback_traceability",
                "P0",
                "Cannot write back",
                row.get("owner_lane") or "Pablito",
                row.get("initiative", ""),
                row.get("account", ""),
                "Completed readback row has no ledger_id.",
                "Attach the readback to a ledger row before applying it.",
                row.get("due_date", ""),
                "Friday readback apply log",
            )
        if (row.get("meeting_status") or "").lower() not in ["", "pending", "not reviewed"] and not (
            present(row.get("actual_result", "")) or present(row.get("actual_learning", ""))
        ):
            add(
                output,
                READBACK.name,
                source_id,
                "readback_learning_gate",
                "P1",
                "Needs result or learning",
                row.get("owner_lane") or "Pablito",
                row.get("initiative", ""),
                row.get("account", ""),
                "Meeting status changed but no actual result or learning was captured.",
                "Add what happened or what we learned before closing the row.",
                row.get("due_date", ""),
                "Friday readback",
            )


def main():
    output = []
    audit_active_ledger(output)
    audit_candidate_validation(output)
    # Friday and Monday generated queues are derived from the active ledger. Audit the source ledger
    # to avoid duplicate noise; use derived queue audits only for fields created by that queue.
    audit_queue(
        output,
        AGENT_QUEUE,
        "agent_queue_generated_fields",
        {"lane": "agent_lane", "acceptance criteria": "acceptance_criteria", "source": "source_link", "trust label": "trust_label", "due date": "due_date"},
        "Codex",
    )
    audit_readback(output)

    if not output:
        add(
            output,
            "system",
            "WF-OK",
            "all_generated_controls",
            "OK",
            "No open generated compliance gaps",
            "Codex",
            "System",
            "",
            "All audited generated controls passed.",
            "Keep running this after issue/readback sync.",
            "",
            "Workflow compliance",
        )

    for index, row in enumerate(output, start=1):
        row["compliance_id"] = f"WFC-{index:03d}"

    with OUTPUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output)


if __name__ == "__main__":
    main()
