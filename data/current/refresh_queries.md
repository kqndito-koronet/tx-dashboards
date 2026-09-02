# TX Dashboard — Cube Refresh Queries

**Generated:** 2026-08-07
**Source:** koronet-network/koronet-data-catalog (wiki/models/ + wiki/raw/)
**Scope:** sell_monthly, buy_monthly, fees_monthly
**Rules:** ks_flag = TRUE always · Aggregation in SQL (never pull raw rows) · Semantic views (_SV) where available

---

## Important: _SV Suffix Clarification

The data catalog uses `PRODUCTION.ANALYTICS` as the schema for all mart tables. The wiki SCHEMA.md states that **only mart models backed by a semantic_view get a wiki page** — but the actual table names in verified queries are `PRODUCTION.ANALYTICS.SALE_DETAILS`, `PRODUCTION.ANALYTICS.TRANSACTION_FEES`, etc. (no _SV suffix). The `_SV` suffix appears in dbt's `models/semantic_view/` layer but maps to the same `PRODUCTION.ANALYTICS` schema.

**Conclusion:** Use `PRODUCTION.ANALYTICS.<TABLE_NAME>` directly. Do NOT append `_SV` to table names in Snowflake queries — this is an internal dbt materialization classification, not a physical suffix on the table name.

---

## Pagination Problem & Solutions

The Snowflake MCP tools return paginated results. Only the first partition comes through. Current cube sizes:

| Cube | Current Rows | Fits in 1 partition? |
|---|---|---|
| sell_monthly | 4,732 | NO — needs chunking |
| buy_monthly | 3,312 | NO — needs chunking |
| fees_monthly | 362 | YES (was YTD; monthly grain ~600–700 est.) |

**Strategy A — Chunk by month (preferred for sell_monthly and buy_monthly):** One query per month. ~275–415 rows per month. Each fits in one partition. 12 calls × 2 cubes = 24 calls total for a full 12-month refresh.

**Strategy B — Chunk by company_id range:** Divide the ~400–430 companies into N batches using `WHERE company_id BETWEEN X AND Y`. Less readable but works if month-chunking fails.

**Strategy C — Reduce grain:** For fees_monthly, a single YTD query (362 rows) fits. If monthly grain is needed, chunk by month (12 calls × ~50–60 rows each — trivial).

---

## Cube 1: sell_monthly

**Grain:** company × month × channel (Online/Offline only — K2K and API not in current data)
**Fields:** company_id, company_name, month, channel, sell_gmv
**Source:** `PRODUCTION.ANALYTICS.SALE_DETAILS`
**MCP tool:** `mcp__claude_ai_Snowflake__sales-query`

### Current data state

The current sell_monthly.json has channels `Online` and `Offline` only (no K2K, no API). The data catalog shows `sales_channel` values of `eCommerce, K2K, API, Offline`. The eShops context confirms that for sell-side, K2K and API are separate channels billed differently — they appear in sale_details but are currently NOT separated in the cube. If K2K and API need to be added as separate channels, that requires a query change.

### Base query (one month at a time)

```sql
-- sell_monthly: chunk by month
-- Replace :target_month with e.g. '2026-07'
SELECT
    company_id,
    company_name,
    DATE_TRUNC('month', shipping_date)::DATE AS month,
    CASE
        WHEN sales_channel = 'eCommerce' THEN 'Online'
        WHEN sales_channel = 'Offline'   THEN 'Offline'
        WHEN sales_channel = 'K2K'       THEN 'K2K'
        WHEN sales_channel = 'API'       THEN 'API'
        ELSE sales_channel
    END AS channel,
    SUM(sales) AS sell_gmv,
    COUNT(DISTINCT sale_number) AS order_count
FROM PRODUCTION.ANALYTICS.SALE_DETAILS
WHERE ks_flag = TRUE
  AND DATE_TRUNC('month', shipping_date) = DATE_TRUNC('month', :target_month::DATE)
  AND (
      (sale_order_type = 'Invoice' AND sale_status = 'Confirmed')
      OR sale_order_type = 'Prebook'
  )
GROUP BY 1, 2, 3, 4
ORDER BY company_id, month, channel;
```

### Full-year query (WARNING: ~4,700 rows — will paginate)

Use only if pagination is fixed or results are reassembled from 12 monthly chunks.

```sql
SELECT
    company_id,
    company_name,
    DATE_TRUNC('month', shipping_date)::DATE AS month,
    CASE
        WHEN sales_channel = 'eCommerce' THEN 'Online'
        WHEN sales_channel = 'Offline'   THEN 'Offline'
        WHEN sales_channel = 'K2K'       THEN 'K2K'
        WHEN sales_channel = 'API'       THEN 'API'
        ELSE sales_channel
    END AS channel,
    SUM(sales) AS sell_gmv,
    COUNT(DISTINCT sale_number) AS order_count
FROM PRODUCTION.ANALYTICS.SALE_DETAILS
WHERE ks_flag = TRUE
  AND shipping_date >= DATEADD('month', -12, DATE_TRUNC('month', CURRENT_DATE))
  AND shipping_date < DATE_TRUNC('month', CURRENT_DATE)
  AND (
      (sale_order_type = 'Invoice' AND sale_status = 'Confirmed')
      OR sale_order_type = 'Prebook'
  )
GROUP BY 1, 2, 3, 4
ORDER BY company_id, month, channel;
```

### Chunking strategy

**Recommended: chunk by month.** Run 12 queries, one per month, with `:target_month` = each of the 12 months in the window. Expected ~385–415 rows per query — all under 1,000.

```
Month list for T12M refresh (as of Aug 2026):
2025-08, 2025-09, 2025-10, 2025-11, 2025-12,
2026-01, 2026-02, 2026-03, 2026-04, 2026-05, 2026-06, 2026-07
```

### Gotchas

| Rule | Detail |
|---|---|
| `SALE_STATUS` is case-sensitive | Use `'Confirmed'` with capital C. `'confirmed'` returns zero rows silently. |
| Do NOT filter `SALE_ORDER_TYPE = 'Invoice'` only | Drops all eSuite prebook orders. Always include the OR PREBOOK clause. |
| `ks_flag = TRUE` is mandatory | Excludes test/demo accounts. |
| eCommerce ≠ storefront | `sales_channel = 'eCommerce'` includes all ERP data for eCommerce-enabled accounts — not just web orders. For storefront-only orders, add `WEB_ORDER_ID > 0`. Current cube does NOT apply this filter — includes all eCommerce-flagged transactions. |
| Mayesh exclusion | The eShops context excludes `COMPANY_NAME NOT ILIKE '%mayesh%'` for eShops analysis. The current sell_monthly cube does NOT appear to apply this filter (Mayesh appears in fees data). Confirm with Rose/Codex before adding. |
| Date field | Use `shipping_date` for monthly buckets. `created_on_date` is for order-creation trends. Do NOT use `ORDER_DATE` (does not exist). |
| `COMPANY_IS_ACTIVE` | Not applied in the current cube (inactive companies may have historical data). Apply `AND company_is_active = TRUE` only if the cube is scoped to active companies only. |

---

## Cube 2: buy_monthly

**Grain:** company × month
**Fields:** company_id, company_name, month, buy_gmv, buy_online, buy_offline
**Source:** `PRODUCTION.ANALYTICS.PROCUREMENT_DETAILS`
**MCP tool:** `mcp__claude_ai_Snowflake__procurements-query`

### Important: buy_monthly is procurement (KP), not eCommerce sell-side

The current buy_monthly tracks what companies buy through Koronet Procurement, not their eCommerce purchases. `buy_gmv = SUM(total_cost)` from PROCUREMENT_DETAILS. `buy_online` and `buy_offline` in the current data suggest a further breakdown — but PROCUREMENT_DETAILS does not have an `Online/Offline` split natively (it has `sales_channel`). The current breakdown likely uses `sales_channel = 'Procurement'` for online and a secondary channel for offline. Verify with the source query in `buy_domain_v2.json` before rebuilding.

**Revenue field:** `TOTAL_COST` (not `SALES` — do NOT mix the two).
**Order count field:** `COUNT(DISTINCT purchase_order_number)`.

### Base query — all procurement (no online/offline split)

```sql
-- buy_monthly: chunk by month
-- Replace :target_month with e.g. '2026-07'
SELECT
    pd.company_id,
    pd.company_name,
    DATE_TRUNC('month', pd.shipping_date)::DATE AS month,
    SUM(pd.total_cost) AS buy_gmv,
    COUNT(DISTINCT pd.purchase_order_number) AS po_count
FROM PRODUCTION.ANALYTICS.PROCUREMENT_DETAILS pd
WHERE pd.sales_channel = 'Procurement'
  AND pd.ks_flag = TRUE
  AND DATE_TRUNC('month', pd.shipping_date) = DATE_TRUNC('month', :target_month::DATE)
GROUP BY 1, 2, 3
ORDER BY company_id, month;
```

### Base query — with online/offline split

If the cube needs buy_online and buy_offline breakdowns (matching current schema), the split logic is not documented in the catalog. **Do not invent this split** — read `buy_domain_v2.json` first to confirm the original logic. Below is a placeholder using `sales_channel` values as proxy:

```sql
-- buy_monthly with channel split (VERIFY AGAINST buy_domain_v2.json FIRST)
SELECT
    pd.company_id,
    pd.company_name,
    DATE_TRUNC('month', pd.shipping_date)::DATE AS month,
    SUM(pd.total_cost) AS buy_gmv,
    SUM(CASE WHEN pd.sales_channel = 'Procurement' THEN pd.total_cost ELSE 0 END) AS buy_online,
    SUM(CASE WHEN pd.sales_channel != 'Procurement' THEN pd.total_cost ELSE 0 END) AS buy_offline,
    COUNT(DISTINCT pd.purchase_order_number) AS po_count
FROM PRODUCTION.ANALYTICS.PROCUREMENT_DETAILS pd
WHERE pd.ks_flag = TRUE
  AND DATE_TRUNC('month', pd.shipping_date) = DATE_TRUNC('month', :target_month::DATE)
GROUP BY 1, 2, 3
ORDER BY company_id, month;
```

**WARNING:** The channel split CASE above is a hypothesis — read `buy_domain_v2.json` to confirm the actual logic before using.

### With active-companies filter (stricter, KP-only accounts)

```sql
-- buy_monthly with active KP companies filter (excludes test/internal accounts)
WITH active_companies AS (
    SELECT DISTINCT
        company_id,
        company_name
    FROM PRODUCTION.ANALYTICS.COMPANIES
    WHERE system_type LIKE '%Koronet Procurement%'
      AND is_active = TRUE
      AND company_id NOT IN (
          13804, 256252, 469537, 376170, 581383, 644249,
          531246, 666205, 55326, 730096, 726492, 677351,
          101905, 768945
      )
)
SELECT
    pd.company_id,
    pd.company_name,
    DATE_TRUNC('month', pd.shipping_date)::DATE AS month,
    SUM(pd.total_cost) AS buy_gmv,
    COUNT(DISTINCT pd.purchase_order_number) AS po_count
FROM PRODUCTION.ANALYTICS.PROCUREMENT_DETAILS pd
INNER JOIN active_companies ac ON pd.company_id = ac.company_id
WHERE pd.sales_channel = 'Procurement'
  AND pd.ks_flag = TRUE
  AND DATE_TRUNC('month', pd.shipping_date) = DATE_TRUNC('month', :target_month::DATE)
GROUP BY 1, 2, 3
ORDER BY company_id, month;
```

### Full-year query (WARNING: ~3,312 rows — will paginate)

Use only if pagination is fixed or chunking by month.

```sql
SELECT
    pd.company_id,
    pd.company_name,
    DATE_TRUNC('month', pd.shipping_date)::DATE AS month,
    SUM(pd.total_cost) AS buy_gmv,
    COUNT(DISTINCT pd.purchase_order_number) AS po_count
FROM PRODUCTION.ANALYTICS.PROCUREMENT_DETAILS pd
WHERE pd.sales_channel = 'Procurement'
  AND pd.ks_flag = TRUE
  AND pd.shipping_date >= DATEADD('month', -12, DATE_TRUNC('month', CURRENT_DATE))
  AND pd.shipping_date < DATE_TRUNC('month', CURRENT_DATE)
GROUP BY 1, 2, 3
ORDER BY company_id, month;
```

### Chunking strategy

**Recommended: chunk by month.** ~270–290 rows per month — all under 1,000. Same 12-month list as sell_monthly.

### Gotchas

| Rule | Detail |
|---|---|
| `sales_channel = 'Procurement'` is mandatory | Other channels exist on the same table (eCommerce, ERP). Without this filter you get non-KP data. |
| `ks_flag = TRUE` is mandatory | Forgetting inflates KP volume. |
| Revenue field is `total_cost` | Not `sales`. These are purchase costs, not sell prices. Mixing with SALE_DETAILS.sales is wrong. |
| 14-ID internal exclusion list | When joining COMPANIES for company-level metadata, always exclude the 14 internal/test company IDs. Omitting inflates active-buyer counts by ~5x in some windows. |
| `AUDIT_CREATION_DATE` needs cast | For date grouping: `TO_DATE(TO_TIMESTAMP_LTZ(AUDIT_CREATION_DATE))`. The current query uses `shipping_date` — confirm which date field the current cube used. |
| Vendor name is buyer-local | `VENDOR_NAME` differs per buyer for the same canonical vendor. Do not use for canonical vendor analysis. Use K2K join pattern (see procurement_context.md). |
| KP billing is NOT in TRANSACTION_FEES | KP uses subscription/threshold billing. `TRANSACTION_FEES` is for eCommerce fees only. |

---

## Cube 3: fees_monthly

**Grain:** company × month × fee_channel (ecom/k2k/api)
**Fields:** company_id, company_name, period (month or YTD), fee_channel, fee_amount
**Source:** `PRODUCTION.ANALYTICS.CONSOLIDATED_TRANSACTION_FEES` (preferred — billed + projected)
**Alt source:** `PRODUCTION.ANALYTICS.TRANSACTION_FEES` (billed only, more columns)
**MCP tool:** `mcp__claude_ai_Snowflake__consolidated-taxes-query` or `mcp__claude_ai_Snowflake__transaction-fees-query`

**Note on MCP tools:** The available tools are `consolidated-taxes-query` and `transaction-fees-query`. The first maps to `consolidated_transaction_fees`, the second to `transaction_fees`. Use `consolidated-taxes-query` for the current-month window (it includes projected fees). Use `transaction-fees-query` for historical billed months.

### Current data state

fees_monthly.json is currently YTD grain (362 rows, fits in one partition). Monthly grain would be ~50–70 rows per month × 12 months = 600–700 rows total — still fits in one partition if queried all at once. Monthly chunking is optional for fees.

### Consolidated query (billed + projected, monthly grain)

```sql
-- fees_monthly: all channels, monthly grain, all months in window
-- ~600-700 rows for T12M — should fit in one partition
SELECT
    company_id,
    company_name,
    DATE_TRUNC('month', transaction_date)::DATE AS month,
    fee_channel,
    SUM(fee_amount) AS fee_amount
FROM PRODUCTION.ANALYTICS.CONSOLIDATED_TRANSACTION_FEES
WHERE ks_flag = TRUE
  AND transaction_date >= DATEADD('month', -12, DATE_TRUNC('month', CURRENT_DATE))
  AND transaction_date < DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month')
GROUP BY 1, 2, 3, 4
ORDER BY company_id, month, fee_channel;
```

**Note:** `CONSOLIDATED_TRANSACTION_FEES` has `status` = 'Billed' or 'Projected'. The above query combines both. To separate:

```sql
-- fees_monthly: billed only
SELECT
    company_id,
    company_name,
    DATE_TRUNC('month', transaction_date)::DATE AS month,
    fee_channel,
    status,
    SUM(fee_amount) AS fee_amount
FROM PRODUCTION.ANALYTICS.CONSOLIDATED_TRANSACTION_FEES
WHERE ks_flag = TRUE
  AND status = 'Billed'
  AND transaction_date >= DATEADD('month', -12, DATE_TRUNC('month', CURRENT_DATE))
GROUP BY 1, 2, 3, 4, 5
ORDER BY company_id, month, fee_channel;
```

### Transaction fees only (billed, more column detail)

```sql
-- fees_monthly from TRANSACTION_FEES (billed history only)
-- transaction_type maps to fee_channel: K2K, eCommerce, API, FedEx, Gross Profit Share
SELECT
    company_id,
    company_name,
    DATE_TRUNC('month', bill_date)::DATE AS month,
    transaction_type AS fee_channel,
    SUM(fee_amount) AS fee_amount
FROM PRODUCTION.ANALYTICS.TRANSACTION_FEES
WHERE ks_flag = TRUE
  AND bill_date >= DATEADD('month', -12, DATE_TRUNC('month', CURRENT_DATE))
GROUP BY 1, 2, 3, 4
ORDER BY company_id, month, fee_channel;
```

**Column note:** In `TRANSACTION_FEES`, the fee channel field is `transaction_type`. In `CONSOLIDATED_TRANSACTION_FEES`, it is `fee_channel`. Values are the same: K2K, eCommerce, API, FedEx, Gross Profit Share.

**Mapping to cube values:** The current fees_monthly.json uses `fee_channel` values of `ecom`, `k2k`, `api`. These are normalized labels. The raw values from Snowflake are `eCommerce`, `K2K`, `API`. Apply LOWER/mapping in the transform layer, not in SQL.

### YTD query (matches current fees_monthly.json grain — 362 rows, fits in one partition)

```sql
-- fees_ytd: current year aggregate (no monthly breakdown)
SELECT
    company_id,
    company_name,
    fee_channel,
    SUM(fee_amount) AS fee_amount
FROM PRODUCTION.ANALYTICS.CONSOLIDATED_TRANSACTION_FEES
WHERE ks_flag = TRUE
  AND YEAR(transaction_date) = YEAR(CURRENT_DATE)
GROUP BY 1, 2, 3
ORDER BY company_id, fee_channel;
```

### Chunking strategy

**Not required.** T12M monthly grain (~600–700 rows) fits in one partition. YTD grain (362 rows) definitely fits.

If monthly grain grows beyond 1,000 rows in future (unlikely given current 227 fee-paying companies), chunk by month: ~50–60 rows per query.

### Gotchas

| Rule | Detail |
|---|---|
| `ks_flag = TRUE` is mandatory | Excludes test accounts. |
| `TRANSACTION_FEES` is for eCommerce fees only (KP billing is separate) | KP billing is subscription/threshold-based. It does NOT appear in `TRANSACTION_FEES`. KP fees = `procurement_subscription_fee` + threshold logic on COMPANIES. |
| Fees are billed in arrears | `TRANSACTION_FEES` will NOT have current-month data until billing runs. Use `CONSOLIDATED_TRANSACTION_FEES` (status = 'Projected') for current-month estimates. |
| `EXPECTED_TRANSACTION_FEES` loads current + previous month | Only loads prior month if queried in the first 3 days of a new month. After the 4th, it only has the current month. Use this for current-month fee estimates only. |
| `company_id` is TEXT in TRANSACTION_FEES | It's a NUMBER in SALE_DETAILS and PROCUREMENT_DETAILS. If joining across tables, cast carefully. |
| fee_channel vs transaction_type | `TRANSACTION_FEES` uses `transaction_type`. `CONSOLIDATED_TRANSACTION_FEES` uses `fee_channel`. Same values, different column names. |
| FedEx and Gross Profit Share channels | The current fees_monthly.json only has `ecom`, `k2k`, `api`. FedEx and Gross Profit Share fees exist in the data but may have been filtered out in the original cube. Add `AND fee_channel IN ('eCommerce', 'K2K', 'API')` if reproducing current behavior. |

---

## eShops Context Rules (mandatory for sell_monthly)

Sourced from `wiki/raw/eshops_context.md`. Apply to all SALE_DETAILS queries that touch eCommerce channel data.

### Always-on filters for eCommerce channel

```sql
WHERE SALES_CHANNEL = 'eCommerce'
  AND KS_FLAG = TRUE
  AND COMPANY_IS_ACTIVE = TRUE
  AND COMPANY_NAME NOT ILIKE '%mayesh%'
  AND (
      (SALE_ORDER_TYPE = 'Invoice' AND SALE_STATUS = 'Confirmed')
      OR SALE_ORDER_TYPE = 'Prebook'
  )
```

| Filter | Why |
|---|---|
| `SALES_CHANNEL = 'eCommerce'` | Scopes to eShops accounts |
| `KS_FLAG = TRUE` | Excludes test/demo accounts |
| `COMPANY_IS_ACTIVE = TRUE` | Active vendors only |
| `COMPANY_NAME NOT ILIKE '%mayesh%'` | Mayesh is API-only, tagged eCommerce for accounting — inflates eCommerce numbers |
| `SALE_ORDER_TYPE = 'Invoice' AND SALE_STATUS = 'Confirmed'` | Standard completed invoices |
| `OR SALE_ORDER_TYPE = 'Prebook'` | Real storefront orders — do NOT filter by status on prebooks |

### Critical: SALE_STATUS is case-sensitive

`'Confirmed'` (capital C) returns correct rows. `'confirmed'` (lowercase) returns zero rows silently.

### eCommerce ≠ web storefront

`SALES_CHANNEL = 'eCommerce'` tags all transactions for accounts with eCommerce enabled — including historical ERP invoices going back to 2014.

- `WEB_ORDER_ID > 0` = order placed through the eShops web UI (true storefront scope)
- `WEB_ORDER_ID = 0` = junk bucket (~$7.8M across 27 vendors). Exclude from storefront analysis.
- `WEB_ORDER_ID IS NULL` = historical ERP invoices for eCommerce-enabled accounts. NOT web orders.

The current sell_monthly cube does NOT apply a `WEB_ORDER_ID` filter — it captures all eCommerce-flagged GMV. This is intentional for sell-side GMV tracking (includes both web + ERP for eCommerce accounts). If you want storefront-only GMV, add `AND WEB_ORDER_ID > 0`.

### Tables to avoid for sell-side analysis

| Table | Why |
|---|---|
| `STG_ESHOPS` | Only 4,578 transactions from May 2025+. Incomplete. Do not use as primary source. |
| `STG_WEB_ORDERS` | Reference metadata only (733K rows). Not a transaction source. |

---

## Procurement Context Rules (mandatory for buy_monthly)

Sourced from `wiki/raw/procurement_context.md`.

### Base filters (always)

```sql
WHERE SALES_CHANNEL = 'Procurement'
  AND KS_FLAG = TRUE
```

### 14-ID internal exclusion (apply when joining COMPANIES)

```sql
AND COMPANY_ID NOT IN (
    13804, 256252, 469537, 376170, 581383, 644249,
    531246, 666205, 55326, 730096, 726492, 677351,
    101905, 768945
)
```

Omitting this inflates active-buyer counts and GMV by ~5x in some windows.

### Date field for KP

Use `shipping_date` for expected/actual ship date (matches current buy_monthly cube). Use `AUDIT_CREATION_DATE` for order-creation date (must cast: `TO_DATE(TO_TIMESTAMP_LTZ(AUDIT_CREATION_DATE))`).

### Vendor name warning

`PROCUREMENT_DETAILS.VENDOR_NAME` is buyer-local. Each buyer's ERP names the same canonical vendor independently. For canonical vendor analysis, use the K2K join pattern (deduplicated — see procurement_context.md). For company-level buy GMV aggregation (which is what buy_monthly does), `VENDOR_NAME` is not used.

---

## Model-Level Rules That Affect All Queries

| Rule | Source | Impact |
|---|---|---|
| `ks_flag = TRUE` always | All models | Excludes test/demo. Missing this is the #1 silent error. |
| Aggregation in SQL | System rule | Never pull raw rows. Always GROUP BY. |
| No `SELECT *` | System rule | Name all columns explicitly. |
| `SALE_STATUS = 'Confirmed'` is case-sensitive | eshops_context.md | Lowercase returns zero rows. |
| Revenue field varies by model | Multiple models | SALE_DETAILS uses `sales`. PROCUREMENT_DETAILS uses `total_cost`. TRANSACTION_FEES uses `fee_amount`. Never mix. |
| Date fields are not interchangeable | Multiple models | `shipping_date` ≠ `created_on_date` ≠ `bill_date` ≠ `transaction_date`. Pick the right one for the cube's business definition. |
| `company_id` type varies | Multiple models | NUMBER in SALE_DETAILS/PROCUREMENT_DETAILS. TEXT in TRANSACTION_FEES/CONSOLIDATED_TRANSACTION_FEES. Cast when joining. |
| Demo companies are excluded by ks_flag | All models | But the 14-ID exclusion list for KP is ADDITIONAL to ks_flag — both are needed for buy_monthly. |

---

## MCP Tool Mapping

| Cube | Table | MCP Tool |
|---|---|---|
| sell_monthly | `PRODUCTION.ANALYTICS.SALE_DETAILS` | `mcp__claude_ai_Snowflake__sales-query` |
| buy_monthly | `PRODUCTION.ANALYTICS.PROCUREMENT_DETAILS` | `mcp__claude_ai_Snowflake__procurements-query` |
| fees_monthly (consolidated) | `PRODUCTION.ANALYTICS.CONSOLIDATED_TRANSACTION_FEES` | `mcp__claude_ai_Snowflake__consolidated-taxes-query` |
| fees_monthly (billed only) | `PRODUCTION.ANALYTICS.TRANSACTION_FEES` | `mcp__claude_ai_Snowflake__transaction-fees-query` |

---

## Refresh Execution Plan (Monthly)

For a full T12M refresh (e.g., rolling to add the newest month):

1. **fees_monthly:** 1 query, all months — fits in one partition. Use `consolidated-taxes-query`.
2. **sell_monthly:** 1 query for the new month only (incremental) — ~400 rows. Use `sales-query`.
3. **buy_monthly:** 1 query for the new month only (incremental) — ~280 rows. Use `procurements-query`.

For a full rebuild from scratch:
1. **fees_monthly:** 1 query (T12M, ~600–700 rows — fits).
2. **sell_monthly:** 12 sequential queries, one per month. ~400 rows each.
3. **buy_monthly:** 12 sequential queries, one per month. ~280 rows each.

Total MCP calls for full rebuild: 25 (1 + 12 + 12).

---

## Open Questions (verify before production use)

1. **sell_monthly: K2K and API channels** — current cube has only Online/Offline. Confirm with source `sell_domain_v2.json` whether K2K was deliberately excluded or was missing. The eShops context indicates K2K eCommerce ($12M T12M) is significant.

2. **buy_monthly: online/offline split logic** — current cube has `buy_online` and `buy_offline` fields but PROCUREMENT_DETAILS does not have a simple online/offline flag. Verify the split logic in `buy_domain_v2.json` before rebuilding.

3. **sell_monthly: Mayesh exclusion** — current cube may or may not exclude Mayesh. The eShops context mandates excluding Mayesh for eCommerce analysis. Confirm with the source data.

4. **fees_monthly: FedEx and Gross Profit Share** — current cube only shows ecom/k2k/api. Confirm whether FedEx and GPS fees are intentionally excluded.

5. **company_id type in CONSOLIDATED_TRANSACTION_FEES** — documented as TEXT. Verify before joining to SALE_DETAILS (NUMBER) or COMPANIES (NUMBER).
