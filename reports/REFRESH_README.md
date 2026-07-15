# TX Fee Refresh Pipeline

`refresh_tx_fees.py` queries Snowflake for transaction fee data and produces a `data/tx_fee_pacing.json` that is a drop-in replacement for what `build.py` consumes.

## Two Execution Modes

### Tier 1 — Claude MCP Interactive

Use when you don't have a direct Snowflake connection (no `snowflake-connector-python` or no credentials). The script prints all SQL queries with instructions to run them manually via the Snowflake MCP tool (`mcp__claude_ai_Snowflake__sql_exec_tool`).

```bash
python3 dashboards/refresh_tx_fees.py --mcp
```

This outputs:
- 8 SQL queries (Q1-Q7, with Q5a/Q5b parameterized)
- The fee type mapping (CONSOLIDATED fee_type -> dashboard channel)
- The expected output JSON schema

**Workflow:**
1. Run the `--mcp` command to see the queries
2. Execute each query using `sql_exec_tool` in a Claude session
3. Collect results into a JSON file with keys `q1` through `q7`
4. Run assembly:

```bash
python3 dashboards/refresh_tx_fees.py --mcp-assemble results.json
```

**Assembly input format** (`results.json`):
```json
{
  "q1": [{"max_billed_date": "2026-06-30", "last_billed_month": "2026-06-01"}],
  "q2": [{"fee_month": "2024-01-01", "fee_year": 2024, "fee_month_num": 1, "fee_type": "K2K Buyer", "status": "billed", "total_fees": 1234.56}, ...],
  "q3": [{"fee_month": "2024-01-01", "fee_year": 2024, "fee_channel": "K2K", "total_fees": 1234.56}, ...],
  "q4": [{"company_name": "Acme", "company_id": "12345", "total_fees_2026": 50000.00}, ...],
  "q5a": [{"company_name": "Acme", "company_id": "12345", "fee_year": 2024, "annual_total": 40000.00}, ...],
  "q5b": [{"company_name": "Acme", "company_id": "12345", "fee_type": "K2K Buyer", "channel_fees": 20000.00}, ...],
  "q6": [{"fee_type": "K2K Buyer", "company_name": "Acme", "channel_fees": 20000.00}, ...],
  "q7": [{"fee_type": "K2K Buyer", "company_name": "Acme", "mar_fees": 5000.00, "apr_fees": 8000.00}, ...]
}
```

### Tier 2 — Direct Snowflake Connection

Use when `snowflake-connector-python` is installed and credentials are available. Runs all queries automatically and writes the JSON.

```bash
# Set credentials
export SNOWFLAKE_ACCOUNT=your_account
export SNOWFLAKE_USER=your_user
export SNOWFLAKE_PASSWORD=your_password
# Optional:
export SNOWFLAKE_WAREHOUSE=COMPUTE_WH   # default
export SNOWFLAKE_ROLE=ANALYST            # default

# Run
python3 dashboards/refresh_tx_fees.py

# Rebuild the dashboard
python3 dashboards/build.py
```

**Auto-fallback:** If you run without `--mcp` but the Snowflake connector is missing or credentials aren't set, the script falls back to Tier 1 (prints queries).

## What It Produces

`data/tx_fee_pacing.json` with:

- **Existing keys** (backward-compatible, `build.py` unchanged): `dashboard`, `pulled_at`, `source`, `target_2026`, `notes`, `rows_2026`, `monthly_totals_prior`, `top_accounts_2026`, `by_type_month`, `clients_by_type_2026`, `jump_mar_apr`, `account_360`, `definitions`, `fathom_note`
- **New keys** (additive, ignored by current `build.py`):
  - `trust`: billing boundary, billed/projected months, per-month trust labels
  - `provenance`: script version, run timestamp, queries used
  - `warnings`: 6 standing gotchas (date_basis, billing_lag, axerrio, GPS, projected, crosscheck)
  - `reconciliation`: consolidated-vs-union delta percentages

Before overwriting, the script backs up the existing JSON to `data/tx_fee_pacing.backup.json`.

## Fee Type Mapping

CONSOLIDATED_TRANSACTION_FEES has granular fee_type values. The script maps them to 5 dashboard channels:

| fee_type (Snowflake) | Dashboard channel |
|---|---|
| E-commerce Vendor | eCommerce |
| K2K Buyer, K2K Vendor | K2K |
| API Buyer, API Vendor | API |
| FedEx, FedEx Vendor | FedEx |
| Gross Profit Share | Gross Profit Share |

Unknown fee_types are logged as warnings and excluded from the dashboard channels.

## Standing Gotchas

These are hard-coded rules, proven in the Q2 2026 fee-spine reconciliation:

1. **Date basis = transaction_date, NOT bill_date.** bill_date undercounts by ~$113K.
2. **Billing lag ~1 month.** TRANSACTION_FEES has no rows for the current month. It lives in EXPECTED_TRANSACTION_FEES until billing runs.
3. **Axerrio outside Snowflake.** The ~$19.6K/period Axerrio uplift is not in any Snowflake table. Totals exclude it.
4. **GPS manual billing.** Gross Profit Share is billed manually with multi-month delays. Recent months may show $0.
5. **ks_flag=TRUE always.** Filters out demo companies. Required on _SV views and UNION_TRANSACTION_FEES.
6. **Complementary tables.** A month is either 100% billed (in TRANSACTION_FEES) or 100% projected (in EXPECTED). No overlap. CONSOLIDATED unions them with a STATUS column.

## Dependencies

```
snowflake-connector-python>=3.6.0   # Tier 2 only
python-dotenv>=1.0.0                # optional, for .env file support
```

Standard library only for Tier 1 (json, datetime, pathlib, argparse, os).
