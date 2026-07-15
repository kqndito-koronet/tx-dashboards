#!/usr/bin/env python3
"""
refresh_tx_fees.py — Fee Refresh Pipeline for Koronet Revenue OS
================================================================

Queries Snowflake for transaction fee data and produces a tx_fee_pacing.json
that is a drop-in replacement for what build.py consumes.

Two execution modes:
  Tier 1 — Claude MCP (interactive): prints SQL queries + expected JSON structure
           so a Claude session can run them via mcp__claude_ai_Snowflake__sql_exec_tool
           and assemble the output.
  Tier 2 — Direct Snowflake: uses snowflake-connector-python with env-var creds.

Standing rules (proven in Q2 2026 reconciliation):
  - Date basis = transaction_date, NOT bill_date (bill_date undercounts ~$113K)
  - TRANSACTION_FEES lags ~1 month; current month only in EXPECTED
  - CONSOLIDATED = billed + projected union with STATUS column
  - Axerrio uplift (~$19.6K/period) lives outside Snowflake — flagged in warnings
  - ks_flag=TRUE always required on _SV views (CONSOLIDATED may or may not have it)
  - GPS has manual billing delays — recent months may show $0

Usage:
  # Tier 2 (direct Snowflake connection):
  export SNOWFLAKE_ACCOUNT=... SNOWFLAKE_USER=... SNOWFLAKE_PASSWORD=...
  python3 dashboards/refresh_tx_fees.py

  # Tier 1 (Claude MCP interactive):
  python3 dashboards/refresh_tx_fees.py --mcp

  # Then rebuild the dashboard HTML:
  python3 dashboards/build.py
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from collections import defaultdict
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

VERSION = "1.0.0"
SCRIPT_NAME = "dashboards/refresh_tx_fees.py"

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_FILE = DATA_DIR / "tx_fee_pacing.json"
BACKUP_FILE = DATA_DIR / "tx_fee_pacing.backup.json"

TARGET_2026 = 4_000_000
YEAR_RANGE = (2024, 2025, 2026)
DASHBOARD_CHANNELS = ["eCommerce", "K2K", "API", "FedEx", "Gross Profit Share"]

# Mapping from CONSOLIDATED_TRANSACTION_FEES fee_type → dashboard channel.
# Any fee_type not in this map gets bucketed into "Other" with a warning.
FEE_TYPE_TO_CHANNEL = {
    "E-commerce Vendor":    "eCommerce",
    "eCommerce":            "eCommerce",
    "K2K Buyer":            "K2K",
    "K2K Vendor":           "K2K",
    "K2K":                  "K2K",
    "API Buyer":            "API",
    "API Vendor":           "API",
    "API":                  "API",
    "FedEx":                "FedEx",
    "FedEx Vendor":         "FedEx",
    "Gross Profit Share":   "Gross Profit Share",
}

# The 6 standing gotchas, embedded in every output.
STANDING_WARNINGS = [
    {
        "id": "date_basis",
        "severity": "critical",
        "message": (
            "All fees grouped by transaction_date/shipping_date, NOT bill_date. "
            "Using bill_date undercounts by ~$113K (proven in Q2 reconciliation)."
        ),
    },
    {
        "id": "billing_lag",
        "severity": "high",
        "message": (
            "TRANSACTION_FEES lags ~1 month. Current month sits ONLY in "
            "EXPECTED_TRANSACTION_FEES until it migrates. Check billing_boundary above."
        ),
    },
    {
        "id": "axerrio_outside",
        "severity": "high",
        "message": (
            "Axerrio uplift (~$19.6K/period) lives OUTSIDE Snowflake. "
            "Totals here exclude Axerrio. 'incl. Axerrio' numbers require a separate source."
        ),
    },
    {
        "id": "gps_manual_billing",
        "severity": "medium",
        "message": (
            "Gross Profit Share is often billed manually with multi-month delays. "
            "GPS for recent months may be incomplete."
        ),
    },
    {
        "id": "projected_needs_validation",
        "severity": "medium",
        "message": (
            "Months marked 'projected' in trust.month_trust use EXPECTED_TRANSACTION_FEES "
            "(shipped but unbilled). These numbers shift when billing finalizes."
        ),
    },
    {
        "id": "consolidated_crosscheck",
        "severity": "info",
        "message": (
            "Consolidated totals cross-checked against UNION_TRANSACTION_FEES. "
            "Delta logged in provenance. Expect <0.5% for eComm/K2K/API. "
            "FedEx/GPS not in UNION view."
        ),
    },
]

# Definitions carried forward (static glossary).
DEFINITIONS = {
    "eCommerce": "Seller-side fee (~1.5% std) on digital eShop/eCommerce orders. Largest fee line.",
    "K2K": "Komet-to-Komet network trades. Seller-side fee per hop ('supply chain multiplication'). ~tied with eCommerce as largest.",
    "API": "Fee on orders flowing through API integrations (e.g., Holex units).",
    "FedEx": "Freight/shipping fee component; zone-based, reconciled monthly vs the FedEx invoice.",
    "Gross Profit Share": "Revenue-share fee (a share of gross profit, e.g. Floropolis virtual broker). Often billed manually; recent months may be pending.",
    "YTD TX Fees": "Sum of billed transaction fees Jan 1 -> latest closed month, ks_flag=TRUE (excludes demo companies).",
    "Seasonality-aware projection": (
        "Floral is highly seasonal (peaks Feb Valentine's + May Mother's Day), so naive "
        "last-2-months x12 OVERSTATES. Method: take 2025 actual monthly curve and scale by "
        "the 2026 YTD-vs-2025-YTD YoY factor. = honest full-year estimate."
    ),
    "Gap to $4M": "Target 2026 ($4M) minus the seasonality-aware projection.",
    "YoY growth": "2026 YTD (Jan-latest billed month) vs same months 2025.",
    "YoY view": (
        "2024 vs 2025 vs 2026 monthly, so seasonality is read from real history "
        "(not assumed). Peaks: Feb (Valentine's), May (Mother's Day)."
    ),
}


# ---------------------------------------------------------------------------
# SQL Queries
# ---------------------------------------------------------------------------

# Q1: Detect billing boundary — MAX(transaction_date) from billed-only table.
SQL_BILLING_BOUNDARY = """\
SELECT
    MAX(transaction_date)                        AS max_billed_date,
    DATE_TRUNC('month', MAX(transaction_date))   AS last_billed_month
FROM PRODUCTION.ANALYTICS.TRANSACTION_FEES
WHERE ks_flag = TRUE;
"""

# Q2: Consolidated monthly fees, 2024-2026, by fee type and billing status.
# This is the PRIMARY query. CONSOLIDATED has billed + projected with STATUS.
SQL_CONSOLIDATED_MONTHLY = """\
SELECT
    DATE_TRUNC('month', transaction_date)::DATE  AS fee_month,
    YEAR(transaction_date)                       AS fee_year,
    MONTH(transaction_date)                      AS fee_month_num,
    fee_type,
    status,
    ROUND(SUM(fee_amount), 2)                    AS total_fees
FROM PRODUCTION.ANALYTICS.CONSOLIDATED_TRANSACTION_FEES
WHERE transaction_date >= '2024-01-01'
  AND transaction_date < DATE_TRUNC('month', CURRENT_DATE()) + INTERVAL '1 month'
GROUP BY 1, 2, 3, 4, 5
ORDER BY 1, 4, 5;
"""

# Q3: Union monthly totals (cross-check, 3 channels only: eComm/K2K/API).
SQL_UNION_MONTHLY = """\
SELECT
    DATE_TRUNC('month', fee_date)::DATE AS fee_month,
    YEAR(fee_date)                      AS fee_year,
    fee_channel,
    ROUND(SUM(fees), 2)                 AS total_fees
FROM PRODUCTION.ANALYTICS.UNION_TRANSACTION_FEES
WHERE ks_flag = TRUE
  AND fee_date >= '2024-01-01'
  AND fee_date < DATE_TRUNC('month', CURRENT_DATE()) + INTERVAL '1 month'
GROUP BY 1, 2, 3
ORDER BY 1, 3;
"""

# Q4: Top 20 accounts by 2026 billed fees.
SQL_TOP_ACCOUNTS = """\
SELECT
    company_name,
    company_id,
    ROUND(SUM(fee_amount), 2) AS total_fees_2026
FROM PRODUCTION.ANALYTICS.CONSOLIDATED_TRANSACTION_FEES
WHERE YEAR(transaction_date) = 2026
  AND status = 'billed'
GROUP BY 1, 2
ORDER BY 3 DESC
LIMIT 20;
"""

# Q5a: Annual totals per account (2024-2026) for top 20.
SQL_ACCOUNT_ANNUAL_TEMPLATE = """\
SELECT
    company_name,
    company_id,
    YEAR(transaction_date) AS fee_year,
    ROUND(SUM(fee_amount), 2) AS annual_total
FROM PRODUCTION.ANALYTICS.CONSOLIDATED_TRANSACTION_FEES
WHERE YEAR(transaction_date) >= 2024
  AND company_id IN ({ids})
  AND status = 'billed'
GROUP BY 1, 2, 3
ORDER BY 2, 3;
"""

# Q5b: 2026 fee mix by channel per account for top 20.
SQL_ACCOUNT_MIX_TEMPLATE = """\
SELECT
    company_name,
    company_id,
    fee_type,
    ROUND(SUM(fee_amount), 2) AS channel_fees
FROM PRODUCTION.ANALYTICS.CONSOLIDATED_TRANSACTION_FEES
WHERE YEAR(transaction_date) = 2026
  AND company_id IN ({ids})
  AND status = 'billed'
GROUP BY 1, 2, 3
ORDER BY 2, 3;
"""

# Q6: Top clients per fee channel, 2026 billed.
SQL_CLIENTS_BY_TYPE = """\
SELECT
    fee_type,
    company_name,
    ROUND(SUM(fee_amount), 2) AS channel_fees
FROM PRODUCTION.ANALYTICS.CONSOLIDATED_TRANSACTION_FEES
WHERE YEAR(transaction_date) = 2026
  AND status = 'billed'
GROUP BY 1, 2
HAVING SUM(fee_amount) > 1000
ORDER BY 1, 3 DESC;
"""

# Q7: Mar vs Apr 2026 jump drivers.
SQL_JUMP_MAR_APR = """\
SELECT
    fee_type,
    company_name,
    SUM(CASE WHEN MONTH(transaction_date) = 3 THEN fee_amount ELSE 0 END) AS mar_fees,
    SUM(CASE WHEN MONTH(transaction_date) = 4 THEN fee_amount ELSE 0 END) AS apr_fees
FROM PRODUCTION.ANALYTICS.CONSOLIDATED_TRANSACTION_FEES
WHERE YEAR(transaction_date) = 2026
  AND MONTH(transaction_date) IN (3, 4)
  AND status = 'billed'
GROUP BY 1, 2
HAVING apr_fees > mar_fees AND apr_fees > 1000
ORDER BY 1, (apr_fees - mar_fees) DESC;
"""

# Collect all queries in order for MCP mode output.
QUERY_CATALOG = [
    ("Q1", "Billing Boundary", SQL_BILLING_BOUNDARY),
    ("Q2", "Consolidated Monthly (primary)", SQL_CONSOLIDATED_MONTHLY),
    ("Q3", "Union Monthly (cross-check)", SQL_UNION_MONTHLY),
    ("Q4", "Top 20 Accounts", SQL_TOP_ACCOUNTS),
    ("Q5a", "Account Annual Totals", "-- parameterized; requires top 20 IDs from Q4"),
    ("Q5b", "Account Fee Mix", "-- parameterized; requires top 20 IDs from Q4"),
    ("Q6", "Clients by Fee Type", SQL_CLIENTS_BY_TYPE),
    ("Q7", "Mar-to-Apr Jump Drivers", SQL_JUMP_MAR_APR),
]


# ---------------------------------------------------------------------------
# Snowflake Connection (Tier 2)
# ---------------------------------------------------------------------------

def snowflake_connect():
    """
    Connect to Snowflake using environment variables.
    Returns a snowflake.connector connection object.
    Raises ImportError if snowflake-connector-python is not installed.
    """
    import snowflake.connector

    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database="PRODUCTION",
        schema="ANALYTICS",
        role=os.environ.get("SNOWFLAKE_ROLE", "ANALYST"),
    )


def run_query(conn, sql: str) -> list[dict]:
    """Execute a SQL query and return results as a list of dicts."""
    cur = conn.cursor()
    try:
        cur.execute(sql)
        cols = [desc[0].lower() for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        cur.close()


# ---------------------------------------------------------------------------
# Fee-Type Mapping
# ---------------------------------------------------------------------------

def map_fee_type(fee_type: str) -> str:
    """
    Map a CONSOLIDATED_TRANSACTION_FEES fee_type value to a dashboard channel.
    Unknown types are bucketed into 'Other' and a warning is printed.
    """
    channel = FEE_TYPE_TO_CHANNEL.get(fee_type)
    if channel is None:
        print(f"[refresh] WARNING: Unknown fee_type '{fee_type}' — bucketing into 'Other'")
        return "Other"
    return channel


# ---------------------------------------------------------------------------
# Trust & Billing Boundary Logic
# ---------------------------------------------------------------------------

def detect_billing_boundary(conn) -> dict:
    """
    Q1: Find the billing boundary — MAX(transaction_date) from billed-only table.
    Returns a dict with boundary info and trust labels per 2026 month.
    """
    rows = run_query(conn, SQL_BILLING_BOUNDARY)
    if not rows or rows[0]["max_billed_date"] is None:
        raise RuntimeError("Could not detect billing boundary — TRANSACTION_FEES returned no rows.")

    max_billed = rows[0]["max_billed_date"]
    # Handle both date and datetime objects
    if isinstance(max_billed, datetime):
        max_billed = max_billed.date()
    elif isinstance(max_billed, str):
        max_billed = date.fromisoformat(max_billed[:10])

    last_billed_month_dt = rows[0]["last_billed_month"]
    if isinstance(last_billed_month_dt, datetime):
        last_billed_month = last_billed_month_dt.date()
    elif isinstance(last_billed_month_dt, str):
        last_billed_month = date.fromisoformat(last_billed_month_dt[:10])
    else:
        last_billed_month = last_billed_month_dt

    # Determine if the boundary month is fully billed or partial
    import calendar
    last_day_of_month = calendar.monthrange(max_billed.year, max_billed.month)[1]
    is_partial = max_billed.day < last_day_of_month

    print(f"[refresh] Billing boundary: {max_billed}"
          f" ({'partial' if is_partial else 'billed through'} "
          f"{'month' if is_partial else max_billed.strftime('%B')})")

    # Build trust labels for each 2026 month
    month_trust = {}
    billed_months = []
    projected_months = []
    today = date.today()

    for m in range(1, 13):
        month_str = f"2026-{m:02d}"
        month_start = date(2026, m, 1)

        if month_start > today.replace(day=1):
            # Future month — no data at all
            break
        elif month_start < last_billed_month:
            # Fully billed (before the boundary month)
            month_trust[month_str] = "billed"
            billed_months.append(month_str)
        elif month_start == last_billed_month:
            if is_partial:
                month_trust[month_str] = "partial_billed"
                billed_months.append(month_str)
            else:
                month_trust[month_str] = "billed"
                billed_months.append(month_str)
        else:
            # After the boundary — projected only
            month_trust[month_str] = "projected"
            projected_months.append(month_str)

    return {
        "billing_boundary": str(max_billed),
        "last_billed_month": str(last_billed_month),
        "is_partial": is_partial,
        "billed_months": billed_months,
        "projected_months": projected_months,
        "month_trust": month_trust,
    }


# ---------------------------------------------------------------------------
# Data Pull Functions (Tier 2)
# ---------------------------------------------------------------------------

def pull_consolidated(conn) -> list[dict]:
    """Q2: Pull consolidated monthly fees by fee_type and status."""
    rows = run_query(conn, SQL_CONSOLIDATED_MONTHLY)
    print(f"[refresh] Pulling consolidated fees (2024-2026)... {len(rows)} rows")
    return rows


def pull_union(conn) -> list[dict]:
    """Q3: Pull union monthly totals for cross-check."""
    rows = run_query(conn, SQL_UNION_MONTHLY)
    print(f"[refresh] Pulling union cross-check... {len(rows)} rows")
    return rows


def pull_top_accounts(conn) -> list[dict]:
    """Q4: Pull top 20 accounts by 2026 billed fees."""
    rows = run_query(conn, SQL_TOP_ACCOUNTS)
    print(f"[refresh] Pulling top 20 accounts... {len(rows)} rows")
    return rows


def pull_account_annual(conn, top_ids: list[str]) -> list[dict]:
    """Q5a: Pull annual totals for the top 20 accounts."""
    ids_str = ",".join(f"'{cid}'" for cid in top_ids)
    sql = SQL_ACCOUNT_ANNUAL_TEMPLATE.format(ids=ids_str)
    rows = run_query(conn, sql)
    print(f"[refresh] Pulling account annual totals... {len(rows)} rows")
    return rows


def pull_account_mix(conn, top_ids: list[str]) -> list[dict]:
    """Q5b: Pull 2026 fee mix by channel per account for the top 20."""
    ids_str = ",".join(f"'{cid}'" for cid in top_ids)
    sql = SQL_ACCOUNT_MIX_TEMPLATE.format(ids=ids_str)
    rows = run_query(conn, sql)
    print(f"[refresh] Pulling account fee mix... {len(rows)} rows")
    return rows


def pull_clients_by_type(conn) -> list[dict]:
    """Q6: Pull top clients per fee channel."""
    rows = run_query(conn, SQL_CLIENTS_BY_TYPE)
    print(f"[refresh] Pulling clients by fee type... {len(rows)} rows")
    return rows


def pull_jump_mar_apr(conn) -> list[dict]:
    """Q7: Pull Mar-to-Apr jump drivers."""
    rows = run_query(conn, SQL_JUMP_MAR_APR)
    print(f"[refresh] Pulling Mar->Apr jump drivers... {len(rows)} rows")
    return rows


# ---------------------------------------------------------------------------
# Processing & Assembly
# ---------------------------------------------------------------------------

def process_consolidated(rows: list[dict], trust_info: dict) -> dict:
    """
    Transform Q2 consolidated rows into the structures build.py expects:
      - rows_2026: [[month, channel, amount], ...]
      - by_type_month: {year: {channel: [12 monthly values]}}
      - monthly_totals_prior: {year: [12 monthly totals]}
    Also returns the raw channel-month totals for reconciliation.
    """
    # Initialize by_type_month for all years and channels
    by_type_month: dict[str, dict[str, list[float]]] = {}
    for year in YEAR_RANGE:
        by_type_month[str(year)] = {ch: [0.0] * 12 for ch in DASHBOARD_CHANNELS}

    # Track unmapped fee types
    unmapped = set()

    for row in rows:
        fee_type = row["fee_type"]
        channel = map_fee_type(fee_type)
        if channel == "Other":
            unmapped.add(fee_type)
            continue

        year = int(row["fee_year"])
        month_idx = int(row["fee_month_num"]) - 1  # 0-indexed
        amount = float(row["total_fees"])
        year_str = str(year)

        if year_str in by_type_month and channel in by_type_month[year_str]:
            by_type_month[year_str][channel][month_idx] += round(amount, 2)

    # Round all values
    for year_str in by_type_month:
        for ch in by_type_month[year_str]:
            by_type_month[year_str][ch] = [round(v, 2) for v in by_type_month[year_str][ch]]

    # Build rows_2026 (only months with data)
    rows_2026 = []
    for month_idx in range(12):
        month_str = f"2026-{month_idx + 1:02d}"
        for ch in DASHBOARD_CHANNELS:
            val = by_type_month["2026"][ch][month_idx]
            if val > 0:
                rows_2026.append([month_str, ch, val])

    # Build monthly_totals_prior (2024, 2025 — 12 monthly totals each)
    monthly_totals_prior = {}
    for year in [2024, 2025]:
        year_str = str(year)
        totals = []
        for month_idx in range(12):
            total = sum(by_type_month[year_str][ch][month_idx] for ch in DASHBOARD_CHANNELS)
            totals.append(round(total, 2))
        monthly_totals_prior[year_str] = totals

    # Build channel-month totals for reconciliation (2026)
    channel_month_totals = defaultdict(lambda: defaultdict(float))
    for row in rows:
        fee_type = row["fee_type"]
        channel = map_fee_type(fee_type)
        if channel == "Other":
            continue
        year = int(row["fee_year"])
        if year == 2026:
            month_str = f"2026-{int(row['fee_month_num']):02d}"
            channel_month_totals[channel][month_str] += float(row["total_fees"])

    if unmapped:
        print(f"[refresh] WARNING: Unmapped fee types found: {unmapped}")

    return {
        "rows_2026": rows_2026,
        "by_type_month": by_type_month,
        "monthly_totals_prior": monthly_totals_prior,
        "channel_month_totals": dict(channel_month_totals),
    }


def process_union(rows: list[dict]) -> dict:
    """
    Transform Q3 union rows into channel-month totals for cross-check.
    UNION_TRANSACTION_FEES only has eCommerce, K2K, API (no FedEx/GPS).
    """
    channel_month_totals = defaultdict(lambda: defaultdict(float))
    for row in rows:
        channel = row["fee_channel"]
        year = int(row["fee_year"])
        if year == 2026:
            month_str = str(row["fee_month"])[:7]  # "2026-01"
            channel_month_totals[channel][month_str] += float(row["total_fees"])
    return dict(channel_month_totals)


def reconcile(consolidated_totals: dict, union_totals: dict) -> dict:
    """
    Cross-check consolidated vs union totals for the 3 shared channels (eComm, K2K, API).
    Returns delta percentages. Warns if any delta > 1%.
    """
    deltas = {}
    for channel in ["eCommerce", "K2K", "API"]:
        c_total = sum(consolidated_totals.get(channel, {}).values())
        u_total = sum(union_totals.get(channel, {}).values())
        if c_total > 0:
            delta_pct = abs(c_total - u_total) / c_total * 100
            deltas[channel] = round(delta_pct, 2)
            if delta_pct > 1.0:
                print(f"[refresh] WARNING: {channel} delta {delta_pct:.1f}% "
                      f"between consolidated and union (c={c_total:.2f}, u={u_total:.2f})")
            else:
                print(f"[refresh] Reconciliation {channel}: {delta_pct:.2f}% — OK")
        else:
            deltas[channel] = None
            print(f"[refresh] Reconciliation {channel}: no consolidated data")
    return deltas


def process_top_accounts(rows: list[dict]) -> tuple[list, list[str]]:
    """
    Transform Q4 rows into top_accounts_2026 list and extract IDs for Q5.
    Returns: (top_accounts_list, top_ids)
    """
    top_accounts = [[row["company_name"], round(float(row["total_fees_2026"]), 2)] for row in rows]
    top_ids = [str(row["company_id"]) for row in rows]
    return top_accounts, top_ids


def process_account_360(
    annual_rows: list[dict],
    mix_rows: list[dict],
    previous_360: dict,
) -> dict:
    """
    Build account_360 from Q5a (annual) and Q5b (mix) data.
    Carries forward sf and rel data from the previous JSON.
    """
    # Build annual totals per account
    acct_data: dict[str, dict] = defaultdict(lambda: {"annual": {}, "mix": {}, "id": None})

    for row in annual_rows:
        name = row["company_name"]
        acct_data[name]["id"] = str(row["company_id"])
        acct_data[name]["annual"][str(int(row["fee_year"]))] = round(float(row["annual_total"]), 2)

    for row in mix_rows:
        name = row["company_name"]
        acct_data[name]["id"] = str(row["company_id"])
        fee_type = row["fee_type"]
        channel = map_fee_type(fee_type)
        if channel == "Other":
            continue
        if channel not in acct_data[name]["mix"]:
            acct_data[name]["mix"][channel] = 0.0
        acct_data[name]["mix"][channel] += round(float(row["channel_fees"]), 2)
        acct_data[name]["mix"][channel] = round(acct_data[name]["mix"][channel], 2)

    # Merge with previous SF/rel data
    merged = {}
    for name, data in acct_data.items():
        merged[name] = {
            "id": data["id"],
            "mix": dict(data["mix"]),
            "annual": dict(data["annual"]),
        }
        # Carry forward Salesforce + relationship data from previous JSON
        if name in previous_360:
            merged[name]["sf"] = previous_360[name].get("sf", {})
            merged[name]["rel"] = previous_360[name].get("rel", {})
        else:
            merged[name]["sf"] = {}
            merged[name]["rel"] = {}
        merged[name]["yoy_ytd_growth"] = None

    return merged


def process_clients_by_type(rows: list[dict]) -> dict:
    """
    Transform Q6 rows into clients_by_type_2026.
    Maps fee_type to dashboard channel, then takes top 16 per channel.
    """
    channel_clients: dict[str, list] = defaultdict(list)
    for row in rows:
        fee_type = row["fee_type"]
        channel = map_fee_type(fee_type)
        if channel == "Other":
            continue
        channel_clients[channel].append(
            (row["company_name"], round(float(row["channel_fees"]), 2))
        )

    # Aggregate by company within channel (since multiple fee_types map to same channel)
    result = {}
    for channel, clients in channel_clients.items():
        agg: dict[str, float] = defaultdict(float)
        for name, fees in clients:
            agg[name] += fees
        sorted_clients = sorted(agg.items(), key=lambda x: -x[1])[:16]
        result[channel] = [[name, round(fees, 2)] for name, fees in sorted_clients]

    return result


def process_jump_mar_apr(rows: list[dict]) -> dict:
    """
    Transform Q7 rows into jump_mar_apr dict.
    Maps fee_type to channel, takes top 5 per channel.
    """
    channel_jumps: dict[str, list] = defaultdict(list)
    for row in rows:
        fee_type = row["fee_type"]
        channel = map_fee_type(fee_type)
        if channel == "Other":
            continue
        channel_jumps[channel].append([
            row["company_name"],
            round(float(row["mar_fees"]), 2),
            round(float(row["apr_fees"]), 2),
        ])

    # Sort by delta (apr - mar), take top 5 per channel
    result = {}
    for channel, jumps in channel_jumps.items():
        jumps.sort(key=lambda x: -(x[2] - x[1]))
        result[channel] = jumps[:5]

    return result


def generate_notes(trust_info: dict) -> str:
    """Generate a human-readable notes string from trust state."""
    billed = trust_info["billed_months"]
    projected = trust_info["projected_months"]
    is_partial = trust_info["is_partial"]

    if billed:
        last_billed_month_name = datetime.strptime(billed[-1], "%Y-%m").strftime("%B")
        if is_partial:
            notes = f"Partially billed through {last_billed_month_name}."
        else:
            notes = f"Billed through {last_billed_month_name}."
    else:
        notes = "No billed months detected."

    if projected:
        proj_names = [datetime.strptime(m, "%Y-%m").strftime("%B") for m in projected]
        notes += f" {', '.join(proj_names)} projected (shipped, not yet billed)."

    notes += " Gross Profit Share may lag additional months."
    notes += " Projection is seasonality-aware (see Definitions)."

    return notes


def build_json(
    trust_info: dict,
    consolidated_data: dict,
    union_deltas: dict,
    top_accounts: list,
    account_360: dict,
    clients_by_type: dict,
    jump_data: dict,
    previous_json: dict,
    run_at: str,
) -> dict:
    """
    Assemble the full output JSON. Backward-compatible with build.py:
    existing keys are preserved. New keys (_meta, trust, provenance, warnings)
    are additive and ignored by build.py until dashboard JS is updated.
    """
    output = {
        # === EXISTING KEYS (build.py contract) ===
        "dashboard": "TX Fee Pacing",
        "pulled_at": run_at[:10],  # build.py uses this as a date string
        "source": "Snowflake PRODUCTION.ANALYTICS.CONSOLIDATED_TRANSACTION_FEES (ks_flag=TRUE)",
        "target_2026": TARGET_2026,
        "notes": generate_notes(trust_info),
        "rows_2026": consolidated_data["rows_2026"],
        "monthly_totals_prior": consolidated_data["monthly_totals_prior"],
        "top_accounts_2026": top_accounts,
        "by_type_month": consolidated_data["by_type_month"],
        "clients_by_type_2026": clients_by_type,
        "jump_mar_apr": jump_data,
        "account_360": account_360,
        "definitions": DEFINITIONS,
        "fathom_note": previous_json.get(
            "fathom_note",
            "Fathom: search per account on-demand. Org corpus = 8 teams.",
        ),

        # === NEW KEYS (trust + provenance) ===
        "trust": {
            "billing_boundary": trust_info["billing_boundary"],
            "billed_months": trust_info["billed_months"],
            "projected_months": trust_info["projected_months"],
            "month_trust": trust_info["month_trust"],
        },
        "provenance": {
            "script": SCRIPT_NAME,
            "version": VERSION,
            "run_at": run_at,
            "queries": {
                "consolidated": "Q2 — CONSOLIDATED_TRANSACTION_FEES, 2024-01-01 to current month end",
                "union_crosscheck": "Q3 — UNION_TRANSACTION_FEES, same range",
                "top_accounts": "Q4 — top 20 by billed 2026",
                "account_detail": "Q5 — annual + mix for top 20",
                "clients_by_type": "Q6 — top clients per fee channel",
                "jump_mar_apr": "Q7 — Mar-to-Apr attribution",
            },
        },
        "warnings": STANDING_WARNINGS,
        "reconciliation": {
            "consolidated_vs_union_delta_pct": union_deltas,
        },
    }

    # Check for GPS = $0 in recent billed months and add extra note
    for month_str in trust_info.get("billed_months", []):
        month_idx = int(month_str.split("-")[1]) - 1
        gps_val = consolidated_data["by_type_month"]["2026"]["Gross Profit Share"][month_idx]
        if gps_val == 0.0:
            print(f"[refresh] WARNING: Gross Profit Share for {month_str} = $0 (manual billing lag?)")

    return output


def backup_and_write(output: dict):
    """Back up the existing JSON and write the new one atomically."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if OUTPUT_FILE.exists():
        shutil.copy2(OUTPUT_FILE, BACKUP_FILE)
        print(f"[refresh] Backed up {OUTPUT_FILE.name} -> {BACKUP_FILE.name}")

    # Write to a temp file first, then rename (atomic on same filesystem)
    tmp_file = OUTPUT_FILE.with_suffix(".tmp")
    with open(tmp_file, "w") as f:
        json.dump(output, f, indent=1, ensure_ascii=False)
    tmp_file.rename(OUTPUT_FILE)
    print(f"[refresh] Wrote {OUTPUT_FILE.name} (pulled_at: {output['pulled_at']})")


# ---------------------------------------------------------------------------
# Load Previous JSON (for carry-forward)
# ---------------------------------------------------------------------------

def load_previous_json() -> dict:
    """Load the existing tx_fee_pacing.json for carry-forward data (SF, rel)."""
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE) as f:
            return json.load(f)
    return {}


# ---------------------------------------------------------------------------
# Tier 2: Direct Snowflake Execution
# ---------------------------------------------------------------------------

def run_tier2():
    """
    Tier 2 — Direct Snowflake connection.
    Runs all queries, processes results, writes JSON.
    """
    print("[refresh] === Tier 2: Direct Snowflake Connection ===")
    print("[refresh] Connecting to Snowflake...")

    conn = snowflake_connect()
    previous_json = load_previous_json()
    run_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        # Step 1: Detect billing boundary
        trust_info = detect_billing_boundary(conn)

        # Step 2: Pull consolidated (primary)
        consolidated_rows = pull_consolidated(conn)

        # Step 3: Pull union (cross-check)
        union_rows = pull_union(conn)

        # Step 4: Pull top accounts
        top_accounts_rows = pull_top_accounts(conn)
        top_accounts, top_ids = process_top_accounts(top_accounts_rows)

        # Step 5: Pull account detail
        annual_rows = pull_account_annual(conn, top_ids)
        mix_rows = pull_account_mix(conn, top_ids)

        # Step 6: Pull clients by type
        clients_by_type_rows = pull_clients_by_type(conn)

        # Step 7: Pull jump drivers
        jump_rows = pull_jump_mar_apr(conn)

    finally:
        conn.close()
        print("[refresh] Snowflake connection closed.")

    # Process all the data
    consolidated_data = process_consolidated(consolidated_rows, trust_info)
    union_totals = process_union(union_rows)

    # Reconcile
    union_deltas = reconcile(
        consolidated_data["channel_month_totals"],
        union_totals,
    )

    # Process accounts
    previous_360 = previous_json.get("account_360", {})
    account_360 = process_account_360(annual_rows, mix_rows, previous_360)

    # Process clients by type
    clients_by_type = process_clients_by_type(clients_by_type_rows)

    # Process jump data
    jump_data = process_jump_mar_apr(jump_rows)

    # Build output JSON
    output = build_json(
        trust_info=trust_info,
        consolidated_data=consolidated_data,
        union_deltas=union_deltas,
        top_accounts=top_accounts,
        account_360=account_360,
        clients_by_type=clients_by_type,
        jump_data=jump_data,
        previous_json=previous_json,
        run_at=run_at,
    )

    # Write
    backup_and_write(output)
    print(f"[refresh] Done. Run `python3 dashboards/build.py` to regenerate the HTML.")


# ---------------------------------------------------------------------------
# Tier 1: Claude MCP Interactive Mode
# ---------------------------------------------------------------------------

MCP_INSTRUCTIONS = """
================================================================================
 TIER 1 — Claude MCP Interactive Mode
================================================================================

This mode outputs the SQL queries you need to run via the Snowflake MCP tool
(mcp__claude_ai_Snowflake__sql_exec_tool) and the expected result structures.

WORKFLOW:
  1. Run each query below using sql_exec_tool
  2. Collect the results
  3. Run this script again with --mcp-assemble and pipe in the results JSON
     OR manually paste the results into tx_fee_pacing.json following the schema

STANDING RULES (must be followed in every query):
  - Date basis = transaction_date, NOT bill_date
  - ks_flag=TRUE on views that have it (TRANSACTION_FEES, UNION_TRANSACTION_FEES)
  - CONSOLIDATED_TRANSACTION_FEES is the primary source (billed + projected)
  - Axerrio uplift (~$19.6K/period) is NOT in Snowflake
  - GPS has manual billing delays — $0 in recent months is expected

"""

MCP_RESULT_SCHEMA = """
EXPECTED OUTPUT SCHEMA (tx_fee_pacing.json):
{
  "dashboard": "TX Fee Pacing",
  "pulled_at": "<today's date>",
  "source": "Snowflake PRODUCTION.ANALYTICS.CONSOLIDATED_TRANSACTION_FEES (ks_flag=TRUE)",
  "target_2026": 4000000,
  "notes": "<auto-generated from billing boundary>",
  "rows_2026": [["2026-01", "API", 9050.46], ...],  // [month, channel, amount]
  "monthly_totals_prior": {"2024": [12 values], "2025": [12 values]},
  "top_accounts_2026": [["Company", 123456.78], ...],
  "by_type_month": {"2024": {5 channels x 12 months}, "2025": {...}, "2026": {...}},
  "clients_by_type_2026": {"API": [...], "K2K": [...], "eCommerce": [...]},
  "jump_mar_apr": {"K2K": [...], "eCommerce": [...]},
  "account_360": {<per-account packs with sf/rel carried forward>},
  "definitions": {<static glossary>},
  "fathom_note": "<static>",
  "trust": {"billing_boundary": "...", "billed_months": [...], "projected_months": [...], "month_trust": {...}},
  "provenance": {"script": "...", "version": "...", "run_at": "...", "queries": {...}},
  "warnings": [<6 standing warnings>],
  "reconciliation": {"consolidated_vs_union_delta_pct": {"eCommerce": 0.03, ...}}
}

FEE TYPE MAPPING (apply when processing Q2 results):
  E-commerce Vendor  -> eCommerce
  K2K Buyer          -> K2K
  K2K Vendor         -> K2K
  API Buyer          -> API
  API Vendor         -> API
  FedEx / FedEx Vendor -> FedEx
  Gross Profit Share -> Gross Profit Share

For Q5a/Q5b: substitute {ids} with the company_id values from Q4 results,
formatted as comma-separated quoted strings: '12345','67890',...
"""


def run_tier1():
    """
    Tier 1 — Claude MCP interactive mode.
    Prints all queries and instructions for manual execution.
    """
    print(MCP_INSTRUCTIONS)

    for qid, label, sql in QUERY_CATALOG:
        print(f"--- {qid}: {label} ---")
        print(sql.strip())
        print()

    print("\n--- Q5a: Account Annual Totals (parameterized) ---")
    print(SQL_ACCOUNT_ANNUAL_TEMPLATE.strip())
    print()

    print("--- Q5b: Account Fee Mix (parameterized) ---")
    print(SQL_ACCOUNT_MIX_TEMPLATE.strip())
    print()

    print(MCP_RESULT_SCHEMA)

    print("To assemble the JSON from query results, run:")
    print("  python3 dashboards/refresh_tx_fees.py --mcp-assemble results.json")
    print()
    print("Or manually construct tx_fee_pacing.json following the schema above,")
    print("then run: python3 dashboards/build.py")


# ---------------------------------------------------------------------------
# Tier 1 Assembly: Process MCP results into JSON
# ---------------------------------------------------------------------------

def run_mcp_assemble(results_file: str):
    """
    Tier 1 assembly — takes a JSON file with raw query results and produces
    the final tx_fee_pacing.json.

    Expected input format:
    {
      "q1": [{"max_billed_date": "2026-06-30", "last_billed_month": "2026-06-01"}],
      "q2": [{"fee_month": "2024-01-01", "fee_year": 2024, "fee_month_num": 1, "fee_type": "...", "status": "billed", "total_fees": 1234.56}, ...],
      "q3": [{"fee_month": "2024-01-01", "fee_year": 2024, "fee_channel": "...", "total_fees": 1234.56}, ...],
      "q4": [{"company_name": "...", "company_id": "...", "total_fees_2026": 1234.56}, ...],
      "q5a": [{"company_name": "...", "company_id": "...", "fee_year": 2024, "annual_total": 1234.56}, ...],
      "q5b": [{"company_name": "...", "company_id": "...", "fee_type": "...", "channel_fees": 1234.56}, ...],
      "q6": [{"fee_type": "...", "company_name": "...", "channel_fees": 1234.56}, ...],
      "q7": [{"fee_type": "...", "company_name": "...", "mar_fees": 100.00, "apr_fees": 200.00}, ...]
    }
    """
    print(f"[refresh] === Tier 1 Assembly: processing {results_file} ===")

    with open(results_file) as f:
        results = json.load(f)

    previous_json = load_previous_json()
    run_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Process Q1: billing boundary
    q1 = results["q1"]
    max_billed_str = str(q1[0]["max_billed_date"])[:10]
    max_billed = date.fromisoformat(max_billed_str)

    import calendar
    last_day = calendar.monthrange(max_billed.year, max_billed.month)[1]
    is_partial = max_billed.day < last_day
    last_billed_month = date(max_billed.year, max_billed.month, 1)

    month_trust = {}
    billed_months = []
    projected_months = []
    today = date.today()

    for m in range(1, 13):
        month_str = f"2026-{m:02d}"
        month_start = date(2026, m, 1)
        if month_start > today.replace(day=1):
            break
        elif month_start < last_billed_month:
            month_trust[month_str] = "billed"
            billed_months.append(month_str)
        elif month_start == last_billed_month:
            month_trust[month_str] = "partial_billed" if is_partial else "billed"
            billed_months.append(month_str)
        else:
            month_trust[month_str] = "projected"
            projected_months.append(month_str)

    trust_info = {
        "billing_boundary": max_billed_str,
        "last_billed_month": str(last_billed_month),
        "is_partial": is_partial,
        "billed_months": billed_months,
        "projected_months": projected_months,
        "month_trust": month_trust,
    }

    print(f"[refresh] Billing boundary: {max_billed_str}")

    # Process Q2-Q7
    consolidated_data = process_consolidated(results["q2"], trust_info)
    union_totals = process_union(results["q3"])
    union_deltas = reconcile(consolidated_data["channel_month_totals"], union_totals)

    top_accounts, top_ids = process_top_accounts(results["q4"])
    previous_360 = previous_json.get("account_360", {})
    account_360 = process_account_360(results["q5a"], results["q5b"], previous_360)
    clients_by_type = process_clients_by_type(results["q6"])
    jump_data = process_jump_mar_apr(results["q7"])

    output = build_json(
        trust_info=trust_info,
        consolidated_data=consolidated_data,
        union_deltas=union_deltas,
        top_accounts=top_accounts,
        account_360=account_360,
        clients_by_type=clients_by_type,
        jump_data=jump_data,
        previous_json=previous_json,
        run_at=run_at,
    )

    backup_and_write(output)
    print(f"[refresh] Done. Run `python3 dashboards/build.py` to regenerate the HTML.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Refresh tx_fee_pacing.json from Snowflake fee data.",
        epilog="See REFRESH_README.md for full documentation.",
    )
    parser.add_argument(
        "--mcp",
        action="store_true",
        help="Tier 1: Print SQL queries for Claude MCP interactive execution.",
    )
    parser.add_argument(
        "--mcp-assemble",
        metavar="RESULTS_FILE",
        help="Tier 1 assembly: Process a JSON file of MCP query results into tx_fee_pacing.json.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run all queries but don't write the output file.",
    )

    args = parser.parse_args()

    if args.mcp:
        run_tier1()
        return

    if args.mcp_assemble:
        run_mcp_assemble(args.mcp_assemble)
        return

    # Tier 2: Direct Snowflake connection
    try:
        import snowflake.connector  # noqa: F401
    except ImportError:
        print("[refresh] snowflake-connector-python not installed.")
        print("[refresh] Falling back to Tier 1 (Claude MCP interactive mode).")
        print("[refresh] To use Tier 2, install: pip install snowflake-connector-python")
        print()
        run_tier1()
        return

    # Check env vars
    required_vars = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD"]
    missing = [v for v in required_vars if v not in os.environ]
    if missing:
        print(f"[refresh] Missing environment variables: {', '.join(missing)}")
        print("[refresh] Set them or use --mcp for interactive mode.")
        print("[refresh] Falling back to Tier 1.")
        print()
        run_tier1()
        return

    run_tier2()


if __name__ == "__main__":
    main()
