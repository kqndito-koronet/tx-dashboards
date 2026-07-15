# dashboards/shared/ — Shared Dashboard Components

Reusable building blocks for Koronet OS dashboards. These exist so new dashboards start with provenance, freshness, and a consistent theme out of the box, while existing dashboards keep working untouched.

---

## Files

| File | What it does | Language |
|------|-------------|----------|
| `envelope.py` | Wraps data payloads in a provenance envelope (`_meta` + `data`) | Python |
| `freshness.js` | Renders a freshness badge from `_meta` in the browser | JavaScript |
| `theme.css` | Dark-theme design system (tokens, cards, tables, drawer, responsive) | CSS |

---

## envelope.py

Creates and validates the provenance envelope that every data file should carry.

### Quick start

```python
from shared.envelope import wrap, validate, read_envelope, write_envelope

# Wrap new data
envelope = wrap(
    data={"rows": [...]},
    source_description="Snowflake PRODUCTION.ANALYTICS.CONSOLIDATED_TRANSACTION_FEES",
    pulled_by="claude:fee_pacing",
    trust_level="trusted",
    known_gaps=["Axerrio uplift NOT included"],
    freshness_window_hours=168,  # 1 week
)

# Validate
errors = validate(envelope)
assert errors == []

# Write to disk
write_envelope(envelope, "dashboards/data/tx_fees.json")

# Read back (handles legacy files without _meta gracefully)
envelope = read_envelope("dashboards/data/tx_fees.json")
print(envelope["_meta"]["pulled_at"])
print(envelope["data"]["rows"][0])
```

### Trust levels

| Level | Meaning |
|-------|---------|
| `trusted` | Reconciled against an external source |
| `needs_validation` | From a live system, not yet reconciled |
| `partial` | Incomplete or estimated data |
| `blocked` | Data source is unavailable |

Aliases accepted: `verified` -> `trusted`, `operational` -> `needs_validation`, `estimated` -> `partial`, `draft` -> `needs_validation`.

### Utility functions

- `is_stale(envelope)` -- Returns `True` if data is past its `freshness_window_hours`.
- `age_hours(envelope)` -- Returns the age of the data in hours (or `None`).
- `read_envelope(path)` -- Reads a JSON file; wraps bare payloads in a minimal envelope for backward compatibility.
- `write_envelope(envelope, path)` -- Writes an envelope to a JSON file (warns if validation fails).

---

## freshness.js

JavaScript module that reads `_meta` from embedded data and renders a visual freshness badge.

### Usage in a dashboard HTML file

```html
<!-- 1. Add a container where you want the badge -->
<div id="freshness"></div>

<!-- 2. After your data script, call renderFreshnessBadge -->
<script>window.DATA = { "_meta": {...}, "data": {...} };</script>
<script>
  renderFreshnessBadge('freshness', window.DATA._meta);
</script>
```

### Badge states

| State | Color | When |
|-------|-------|------|
| Green | `#36d399` border | Data is within `freshness_window_hours` |
| Amber | `#fbbd23` border | Data is past its freshness window |
| Red | `#f87272` border | Data is blocked, or `pulled_at` is missing |

### What the badge shows

```
Last refreshed: Jul 2, 2026 02:30 PM (3h ago)
Trust: Trusted | Gaps: Axerrio uplift NOT included
Source: Snowflake PRODUCTION.ANALYTICS.CONSOLIDATED_TRANSACTION_FEES
```

### Multiple data sources

If a dashboard combines multiple data files, render a badge per source:

```html
<div id="freshness-fees"></div>
<div id="freshness-accounts"></div>
<script>
  renderFreshnessBadge('freshness-fees', feeData._meta);
  renderFreshnessBadge('freshness-accounts', accountData._meta);
</script>
```

---

## theme.css

The dark-theme design system extracted from the existing dashboards. Contains CSS custom properties (tokens), layout, card/KPI/table/drawer/tooltip/pill/responsive styles.

### Usage in a new dashboard build script

```python
# In your build script, inline theme.css into the HTML:
theme_css = (ROOT / "shared" / "theme.css").read_text()
freshness_js = (ROOT / "shared" / "freshness.js").read_text()

html = f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8">
<style>{theme_css}</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
</head><body>
<div class="wrap">
  <div id="freshness"></div>
  <!-- dashboard content here -->
</div>
<script>window.DATA = {json.dumps(envelope)};</script>
<script>{freshness_js}</script>
<script>renderFreshnessBadge('freshness', window.DATA._meta);</script>
</body></html>"""
```

### Design tokens (CSS custom properties)

```
--bg:   #0f1419    page background
--card: #1a2230    card / panel background
--ink:  #e6edf3    primary text
--mut:  #8b98a9    muted / secondary text
--line: #2a3543    borders, dividers
--acc:  #4f9dff    accent / links
--up:   #36d399    positive / growth
--dn:   #f87272    negative / decline
--warn: #fbbd23    warning / amber
```

---

## Backward compatibility

These shared components are additive. Existing dashboards (`tx_fee_pacing.html`, `where_are_we.html`, etc.) keep their inline CSS and work exactly as before. The shared files are used by:

1. **New dashboards** -- use `theme.css` + `freshness.js` from the start.
2. **Progressive migration** -- when an existing dashboard is next modified, its build script can switch to inlining `theme.css` instead of duplicating the CSS.

No existing file is modified or broken by the existence of these shared components.

---

## How build scripts use these components

The pattern is: **inline at build time, not link at runtime.** The build script reads the shared files and embeds their contents directly into the standalone HTML. The final HTML has zero external dependencies (except Chart.js CDN). This preserves the "open in any browser, works offline" property.

```
shared/theme.css ──┐
shared/freshness.js──┤── build.py reads these ──→ standalone .html (everything inlined)
data/tx_fees.json ──┘
```
