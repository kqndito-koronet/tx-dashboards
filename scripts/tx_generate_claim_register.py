#!/usr/bin/env python3
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tx-strategy-v2" / "data"
OUTPUT = DATA / "tx_claim_register.csv"

FIELDS = [
    "claim_id",
    "claim",
    "source",
    "source_link",
    "trust_label",
    "caveat",
    "decision_supported",
    "required_action",
    "owner_lane",
    "stale_date",
    "board_ready",
    "status",
]

CLAIMS = [
    {
        "claim_id": "CLAIM-001",
        "claim": "Q3 requires acceleration: $670K / +54.5% YoY.",
        "source": "OKR diagnostic / Q3 projection",
        "source_link": "/tx-dashboards/okr-diagnostic.html",
        "trust_label": "Source-backed",
        "caveat": "Target basis comes from current OKR diagnostic; official finance reconciliation still useful.",
        "decision_supported": "Explains urgency without making Friday finance-only.",
        "required_action": "Keep in current read; refresh with Rose before leadership/board use.",
        "owner_lane": "Rose",
        "stale_date": "2026-07-18",
        "board_ready": "No",
        "status": "Use with caveat",
    },
    {
        "claim_id": "CLAIM-002",
        "claim": "July is directionally pacing well, but still needs caveats.",
        "source": "OKR diagnostic / Jul 1-13 operating read",
        "source_link": "/tx-dashboards/okr-diagnostic.html",
        "trust_label": "Directional",
        "caveat": "Same-day normalized; Axerrio inclusion/exclusion and date basis must remain visible.",
        "decision_supported": "Use as positive signal, not proof the strategic problem is solved.",
        "required_action": "Rose to refresh July-to-date and explicitly label Axerrio in/out.",
        "owner_lane": "Rose",
        "stale_date": "2026-07-16",
        "board_ready": "No",
        "status": "Needs Rose refresh",
    },
    {
        "claim_id": "CLAIM-003",
        "claim": "Fee growth has benefited from monetizing existing value; durability still depends on growing more digital GMV.",
        "source": "Current read + driver decomposition request",
        "source_link": "/tx-dashboards/tx-strategy-v2/current-read-data-backing.html",
        "trust_label": "Interpretation",
        "caveat": "Needs Rose decomposition of volume vs rate/mix/API/pricing/Axerrio before stronger use.",
        "decision_supported": "Frames why short-term monetization cannot replace BUY/LIST/SELL/GROW learning.",
        "required_action": "Rose to produce driver decomposition with permanence tags.",
        "owner_lane": "Rose",
        "stale_date": "2026-07-18",
        "board_ready": "No",
        "status": "Needs backing pack",
    },
    {
        "claim_id": "CLAIM-004",
        "claim": "Durable TX growth requires growing ecosystem GMV, especially wholesaler-to-retailer GMV, moving repeat transactions online, and reducing leakage.",
        "source": "Facu-approved strategy language + ecosystem map",
        "source_link": "/tx-dashboards/reports/ecosystem_map.html",
        "trust_label": "Strategic canonical",
        "caveat": "Layer sizing still needs Rose freshness/trust labels before board-style use.",
        "decision_supported": "Defines the long-term strategy: GMV -> Digital GMV -> Monetize.",
        "required_action": "Keep as strategy framing; attach metric spine when Rose refreshes.",
        "owner_lane": "Socrates + Rose",
        "stale_date": "2026-07-22",
        "board_ready": "No",
        "status": "Approved framing",
    },
    {
        "claim_id": "CLAIM-005",
        "claim": "Digitalization is not a product-only problem; it must be learned through BUY -> LIST -> SELL -> GROW.",
        "source": "Facu-approved strategy language",
        "source_link": "/tx-dashboards/tx-strategy-v2/index.html",
        "trust_label": "Strategic canonical",
        "caveat": "Initiative pages still need owner validation and lead-list sharpening.",
        "decision_supported": "Keeps Friday focused on execution, learning, blockers, and next actions.",
        "required_action": "Use in stakeholder comms; do not attach final lead lists without owner validation.",
        "owner_lane": "Socrates",
        "stale_date": "2026-07-22",
        "board_ready": "Yes",
        "status": "Approved framing",
    },
    {
        "claim_id": "CLAIM-006",
        "claim": "K2K fee language must not use the old double-charge framing.",
        "source": "Dave correction noted in OKR/current read",
        "source_link": "/tx-dashboards/tx-strategy-v2/current-read-data-backing.html",
        "trust_label": "Correction noted",
        "caveat": "Needs canonical propagation across legacy L2/flywheel pages.",
        "decision_supported": "Prevents the BUY narrative from using incorrect fee mechanics.",
        "required_action": "Nahua/Codex to quarantine or patch old contradictory pages.",
        "owner_lane": "Nahua + Codex",
        "stale_date": "2026-07-18",
        "board_ready": "No",
        "status": "Needs canonical cleanup",
    },
    {
        "claim_id": "CLAIM-007",
        "claim": "Rate catches help Q3 but create future durability risk.",
        "source": "OKR diagnostic / rate catch calendar",
        "source_link": "/tx-dashboards/okr-diagnostic.html",
        "trust_label": "Inferred",
        "caveat": "Timing inferred from monthly take-rate changes, not contract records.",
        "decision_supported": "Explains why hitting Q3 does not mean the strategic issue is solved.",
        "required_action": "Rose/finance to validate rate-change dates and expiry risk.",
        "owner_lane": "Rose",
        "stale_date": "2026-07-18",
        "board_ready": "No",
        "status": "Use with caveat",
    },
    {
        "claim_id": "CLAIM-008",
        "claim": "Offline GMV is a real opportunity signal but not board-ready as currently defined.",
        "source": "Where Are We / ecosystem map",
        "source_link": "/tx-dashboards/reports/where_are_we.html",
        "trust_label": "Not board-ready",
        "caveat": "Offline definition, dirty rows, caps, account exclusions, and date basis need reconciliation.",
        "decision_supported": "Supports discovery around LIST/SELL without overstating TAM.",
        "required_action": "Rose to publish metric spine and board-readiness flag.",
        "owner_lane": "Rose",
        "stale_date": "2026-07-18",
        "board_ready": "No",
        "status": "Evidence only",
    },
    {
        "claim_id": "CLAIM-009",
        "claim": "Lead lists are suggested starting points, not assigned execution targets.",
        "source": "V2 review readiness + weekly action queue",
        "source_link": "/tx-dashboards/tx-strategy-v2/weekly-action-queue.html",
        "trust_label": "Owner validation needed",
        "caveat": "CS/Implementation owners must validate account facts, priority, and next action.",
        "decision_supported": "Avoids forcing Cata/Christine into bad or unapproved account asks.",
        "required_action": "Use lead filters/signals for review; promote only after owner acceptance.",
        "owner_lane": "Mercurio + Pablito",
        "stale_date": "2026-07-17",
        "board_ready": "No",
        "status": "Needs owner validation",
    },
]


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(CLAIMS)


if __name__ == "__main__":
    main()
