#!/usr/bin/env python3
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "tx-strategy-v2" / "data" / "tx_github_issue_capture.json"
OUTPUT = ROOT / "tx-strategy-v2" / "data" / "tx_issue_ledger_candidates.csv"

FIELDS = [
    "candidate_id",
    "issue_number",
    "issue_url",
    "issue_state",
    "issue_title",
    "issue_labels",
    "created_at",
    "updated_at",
    "author",
    "account",
    "initiative",
    "what_happened",
    "result_or_learning",
    "blocker_or_objection",
    "next_action_owner_date",
    "need_from_facu_or_system",
    "directly_said",
    "read_safe_interpretation",
    "trust_label",
    "routing",
    "promotion_state",
]


def labels(issue):
    return ",".join(label.get("name", "") for label in issue.get("labels", []))


def section_map(body):
    sections = {}
    current = None
    buffer = []
    for line in (body or "").splitlines():
        match = re.match(r"^###\s+(.+?)\s*$", line)
        if match:
            if current:
                sections[current] = "\n".join(buffer).strip()
            current = normalize(match.group(1))
            buffer = []
            continue
        if current:
            if line.strip() == "_No response_":
                continue
            buffer.append(line)
    if current:
        sections[current] = "\n".join(buffer).strip()
    return sections


def normalize(label):
    label = label.lower().strip()
    label = re.sub(r"[^a-z0-9]+", "_", label)
    return label.strip("_")


def first(sections, *names):
    for name in names:
        value = sections.get(normalize(name), "")
        if value:
            return value
    return ""


def row(issue):
    sections = section_map(issue.get("body", ""))
    number = issue.get("number", "")
    return {
        "candidate_id": f"ISSUE-{number}",
        "issue_number": number,
        "issue_url": issue.get("url", ""),
        "issue_state": issue.get("state", ""),
        "issue_title": issue.get("title", ""),
        "issue_labels": labels(issue),
        "created_at": issue.get("createdAt", ""),
        "updated_at": issue.get("updatedAt", ""),
        "author": (issue.get("author") or {}).get("login", ""),
        "account": first(sections, "Account / object", "Account / meeting"),
        "initiative": first(sections, "Initiative"),
        "what_happened": first(sections, "What happened?"),
        "result_or_learning": first(sections, "Result or learning"),
        "blocker_or_objection": first(sections, "Blocker", "Objections / blockers"),
        "next_action_owner_date": first(sections, "Next action / owner / date", "Tasks / owner / due date"),
        "need_from_facu_or_system": first(sections, "Need from Facu / system"),
        "directly_said": first(sections, "Directly said"),
        "read_safe_interpretation": first(sections, "Read-safe interpretation"),
        "trust_label": first(sections, "Trust label", "Visibility"),
        "routing": first(sections, "Routing / downstream artifact"),
        "promotion_state": "Needs review before ledger promotion",
    }


def main():
    issues = json.loads(INPUT.read_text()) if INPUT.exists() else []
    rows = [row(issue) for issue in issues]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
