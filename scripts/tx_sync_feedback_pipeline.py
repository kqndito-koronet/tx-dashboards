#!/usr/bin/env python3
"""Run the TX V2 feedback/call ingestion pipeline end to end.

This script intentionally does not fetch GitHub issues. The GitHub Action owns
that read step with gh issue list. Local/manual runs can update
tx_github_issue_capture.json first, then run this pipeline to regenerate every
downstream operating surface.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STEPS = [
    ("issue capture -> ledger candidates", "scripts/tx_issue_capture_to_ledger.py"),
    ("candidate validation", "scripts/tx_validate_ledger_candidates.py"),
    ("candidate promotion", "scripts/tx_promote_validated_candidates.py"),
    ("Friday readback apply", "scripts/tx_apply_friday_readback.py"),
    ("Friday/Monday review queues", "scripts/tx_generate_review_queues.py"),
    ("Friday readback page data", "scripts/tx_generate_friday_readback.py"),
    ("Monday leadership prefill", "scripts/tx_generate_monday_prefill.py"),
    ("agent lane queues", "scripts/tx_generate_agent_lane_queues.py"),
    ("workflow compliance audit", "scripts/tx_generate_workflow_compliance_audit.py"),
    ("claim register", "scripts/tx_generate_claim_register.py"),
]


def main() -> int:
    print("TX feedback pipeline starting")
    for label, script in STEPS:
        print(f"- {label}: {script}")
        subprocess.run([sys.executable, script], cwd=ROOT, check=True)
    print("TX feedback pipeline complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
