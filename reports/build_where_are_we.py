#!/usr/bin/env python3
"""Build Where Are We v2 dashboard (standalone HTML, Chart.js CDN, embedded data)."""
from pathlib import Path
import json

D = Path(__file__).parent
CSS = open(D / "ecosystem_map.html").read().split("</style>")[0].split("<style>")[1]
CSS = "<style>" + CSS + """
.cls{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:14px 0}
.clsbox{border-radius:10px;padding:12px;font-size:12px}
.out{background:#13301f;border:1px solid #2f7d4f}.lead{background:#13283b;border:1px solid #2f5f7d}
.unk{background:#2e2a12;border:1px solid #7d6a2f}.rsk{background:#301414;border:1px solid #7d2f2f}
.clsbox h4{margin:0 0 6px;font-size:11px;text-transform:uppercase;letter-spacing:.04em}
.clsbox ul{margin:0;padding-left:15px;color:#cdd9e5}.clsbox li{margin:2px 0}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line)}
th{color:var(--mut);font-weight:500;font-size:11px}
.num{text-align:right;font-variant-numeric:tabular-nums}
.warn{color:#fbbd23}.dn{color:#f87272}.up{color:#36d399}
@media(max-width:760px){.cls{grid-template-columns:1fr 1fr}}</style>"""

def m(x):
    return "$" + format(round(x), ",")

channel = [("eCommerce", 554334, 1.27), ("K2K", 502541, 1.84), ("API", 70979, 0.15),
           ("FedEx", 5904, None), ("GPS", 879, None)]
rate = [("2024", "1.44%"), ("2025", "1.34%"), ("2026 YTD", "1.32%")]
conc = [("Sole Farms", 110711, "9.7% of fees — near 10% board threshold"),
        ("Jet Fresh", 77632, ""), ("Fresca Farms", 64724, ""), ("Kennicott (KBC)", 58044, ""),
        ("Royal Flowers", 48482, ""), ("FloraLink", 48434, ""), ("Continental", 46356, ""),
        ("Choice Farms", 43928, ""), ("Rosaprima", 36795, "+128% YoY"), ("Allure Farms", 36783, "")]
hilo = [("We Got Flowers", 4678869, "11", "FCS / Felipe target"),
        ("JFS Wholesale", 1225519, "~0", "FCS cohort"),
        ("Riverside Wholesale KY", 519548, "~530", "FCS cohort"),
        ("Flora Fresh", 529000, "355", "FCS / Felipe target")]

chrows = "".join(
    f"<tr><td>{n}</td><td class=num>{m(v)}</td><td class=num>{(str(r)+'%') if r else '—'}</td></tr>"
    for n, v, r in channel)
concrows = "".join(
    f"<tr><td>{n}</td><td class=num>{m(v)}</td><td class={'warn' if note else ''}>{note}</td></tr>"
    for n, v, note in conc)
hilorows = "".join(
    f"<tr><td>{n}</td><td class=num>{m(v)}</td><td class=num>${f}</td><td>{tag}</td></tr>"
    for n, v, f, tag in hilo)

ratelabels = json.dumps([r[0] for r in rate])

html = f"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Where Are We v2 - Koronet OS</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>{CSS}</head>
<body><div class=wrap>
<div class=crumbs><a href="index.html">Koronet OS</a> &rsaquo; Where Are We v2</div>
<h1>Where Are We &mdash; TX fees (take-rate rail)</h1>
<div class=sub>Snowflake TRANSACTION_FEES + SALE_DETAILS &middot; ks_flag=TRUE &middot; reconciled to Chris data-state &middot; <b class=warn>NOT board-ready</b> (see caveats)</div>

<div class=note><h3>What this is for</h3>Measure where we are, where fees come from, and where the opportunity is &mdash; <b>without</b> settling the 2.8-vs-4.0 target debate. Every figure here is <b>operational</b> (Snowflake live), pending reconciliation to the official Metabase/OKR definition. Figures = YoY-YTD unless noted.</div>

<div class=kpis>
 <div class=kpi><div class=kpi-label>TX fees 2026 YTD</div><div class=kpi-val>$1.13M</div><div class=kpi-sub>thru May &middot; take-rate rail</div></div>
 <div class=kpi><div class=kpi-label>YoY-YTD</div><div class="kpi-val up">+32%</div><div class=kpi-sub>vs ~$0.86M same period 2025</div></div>
 <div class=kpi><div class=kpi-label>2025 full year</div><div class=kpi-val>$1.92M</div><div class=kpi-sub>fees (take-rate rail)</div></div>
 <div class=kpi><div class=kpi-label>Gap to target</div><div class="kpi-val warn">parked</div><div class=kpi-sub>2.8&rarr;4.0 debate deferred</div></div>
</div>

<div class=card><h2>Metric Classification <span class=hint style="font-weight:400">(mandatory frame &mdash; what each number is allowed to claim)</span></h2>
<div class=cls>
 <div class="clsbox out"><h4>&#127919; Outcome</h4><ul><li>TX fees</li><li>Fee-bearing GMV</li><li>Repeat fee-bearing transactions</li></ul></div>
 <div class="clsbox lead"><h4>&#128200; Validated leading indicator</h4><ul><li>Channel mix (eComm/K2K/API)</li><li>High-offline / low-digital accounts</li><li>K2K growth</li></ul></div>
 <div class="clsbox unk"><h4>&#10067; Unknown</h4><ul><li>Offline GMV &mdash; until &ldquo;Offline&rdquo; definition confirmed</li></ul></div>
 <div class="clsbox rsk"><h4>&#9888; Risk</h4><ul><li>Top-account concentration</li><li>Take-rate compression</li><li>API denominator confusion</li></ul></div>
</div></div>

<div class=card><h2>1 &middot; Channel mix (2026 YTD fees + effective rate)</h2>
<table><tr><th>Channel</th><th class=num>Fees</th><th class=num>Eff. rate</th></tr>{chrows}</table>
<div class=hint>eCommerce + K2K = 93% of fees. K2K carries the best rate (1.84%). API rate is denominator-sensitive &mdash; see caveats. <b>Class: validated leading indicator.</b></div></div>

<div class=card><h2>2 &middot; Take-rate compression</h2><canvas id=rate height=90></canvas>
<div class=hint>Effective seller-side rate 1.44% &rarr; 1.34% &rarr; 1.32%. INTERPRETATION: mix-shift toward lower-rate eCommerce, not a deliberate rate cut. <b>Class: risk.</b></div></div>

<div class=card><h2>3 &middot; Top account concentration / risk</h2>
<table><tr><th>Seller (2026 YTD fees)</th><th class=num>Fees</th><th>Flag</th></tr>{concrows}</table>
<div class=hint>Importers dominate the fee leaderboard; Sole sits near the 10% board-disclosure threshold. <b>Class: risk.</b></div></div>

<div class=card><h2>4 &middot; Offline visible conversion pool</h2>
<div class=kpi-val style="font-size:30px">~$623M</div>
<div class=hint><span class=warn>&#9888; UNKNOWN:</span> ~$623M of visible &ldquo;Offline&rdquo; GMV at ~0% fee = the conversion TAM behind the W&rarr;R thesis. The definition of &ldquo;Offline&rdquo; is NOT confirmed and GMV is capped at $200k/line to strip corrupt rows. Do not treat as board-ready. <b>Class: unknown.</b></div></div>

<div class=card><h2>5 &middot; High-offline / low-digital accounts (conversion targets)</h2>
<table><tr><th>Account</th><th class=num>Offline GMV</th><th class=num>TX fee</th><th>Note</th></tr>{hilorows}</table>
<div class=hint>Large offline books, ~$0 TX fee &rarr; the per-account W&rarr;R digital-conversion opportunity. <b>Class: validated leading indicator.</b></div></div>

<div class=note style="border-color:#7d6a2f;background:#1c1810"><h3>6 &middot; Open questions / NOT board-ready caveats</h3><ul>
 <li><b>&ldquo;Offline&rdquo; definition unconfirmed</b> (Q002/Q004 &mdash; Sofia/Dan own it).</li>
 <li><b>API &ldquo;rate&rdquo; depends on denominator:</b> 0.15% of sales-channel GMV vs 1.23% of fee-bearing GMV. Most API channel volume is NOT fee-bearing &mdash; confirm why before quoting a rate.</li>
 <li><b>Operational vs official:</b> Snowflake figures NOT yet reconciled to the official Metabase / Company-OKR definition (Lau&rsquo;s cleaning logic).</li>
 <li><b>SaaS-vs-TX split</b> uses Salesforce ARR as a proxy, not the Intacct GL.</li>
 <li><b>Offline GMV is capped/cleaned</b> &mdash; dirty source dates and values.</li>
</ul></div>

<div style="color:var(--mut);font-size:12px;margin-top:14px">Koronet OS &middot; re-run via build_where_are_we.py after each refresh &middot; claim labels per 00_CHARTER.md</div>
</div>
__SCRIPT__</body></html>"""

script = """<script>
const gc='#2a3543',tc='#8b98a9';
new Chart(document.getElementById('rate'),{type:'line',
 data:{labels:__LABELS__,datasets:[{label:'Effective take-rate %',data:[1.44,1.34,1.32],
  borderColor:'#f87272',backgroundColor:'#f8727222',tension:.3,fill:true,pointRadius:4}]},
 options:{plugins:{legend:{display:false}},scales:{
  x:{grid:{color:gc},ticks:{color:tc}},
  y:{grid:{color:gc},ticks:{color:tc,callback:v=>v+'%'},suggestedMin:1.2,suggestedMax:1.5}}}});
</script>""".replace("__LABELS__", ratelabels)
html = html.replace("__SCRIPT__", script)

(D / "where_are_we.html").write_text(html)

idx = (D / "index.html").read_text()
if "where_are_we.html" not in idx:
    anchor = '<a class=card href="ecosystem_map.html">'
    card = ('<a class=card href="where_are_we.html"><b>0 &middot; Where Are We v2</b> '
            '<span class=s>v2</span><div class=n>TX fees state: YTD/YoY, channel mix, take-rate '
            'compression, concentration, offline pool, metric classification</div></a>\n')
    idx = idx.replace(anchor, card + anchor, 1)
    (D / "index.html").write_text(idx)
    print("indexed")
print("Wrote", D / "where_are_we.html")
