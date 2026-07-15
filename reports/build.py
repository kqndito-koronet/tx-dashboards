#!/usr/bin/env python3
"""Render Koronet OS dashboards as standalone HTML (Chart.js via CDN).
Reads dashboards/data/*.json (pulled live) -> writes HTML you open in a browser.
v3 (Facu feedback): YoY comparison drives seasonality; drill BY FEE TYPE first
(trend + clients + Mar->Apr attribution); account drawer shows characteristics;
every term defined. Data is embedded as a JSON blob; JS is static (no escape bugs).
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

HEAD = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TX Fee Pacing — Koronet OS</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
:root{--bg:#0f1419;--card:#1a2230;--ink:#e6edf3;--mut:#8b98a9;--line:#2a3543;--acc:#4f9dff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1160px;margin:0 auto;padding:24px}
.crumbs{color:var(--mut);font-size:12px;margin-bottom:8px}.crumbs a{color:var(--acc);text-decoration:none;cursor:pointer}
h1{font-size:22px;margin:0 0 2px}.sub{color:var(--mut);font-size:13px;margin-bottom:18px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}
.kpi-label{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.04em}
.kpi-val{font-size:24px;font-weight:700;margin:5px 0 3px}.kpi-sub{color:var(--mut);font-size:11px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;margin-bottom:18px}
.card h2{font-size:15px;margin:0 0 3px;font-weight:600}.hint{color:var(--mut);font-size:12px;margin-bottom:12px}
.tabs{display:inline-flex;background:#121925;border:1px solid var(--line);border-radius:8px;overflow:hidden;margin-bottom:12px}
.tabs button{background:none;border:none;color:var(--mut);padding:7px 14px;cursor:pointer;font-size:13px}
.tabs button.on{background:var(--acc);color:#04101f;font-weight:600}
.tcards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}
.tcard{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;cursor:pointer;transition:.15s}
.tcard:hover{border-color:var(--acc);transform:translateY(-2px)}
.tcard .nm{font-size:13px;color:var(--mut)}.tcard .v{font-size:21px;font-weight:700;margin:3px 0}.tcard .yo{font-size:12px}
.up{color:#36d399}.dn{color:#f87272}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line)}
th{color:var(--mut);font-weight:500;font-size:12px}.num{text-align:right;font-variant-numeric:tabular-nums}
tr.drill{cursor:pointer}tr.drill:hover{background:#222d3d}.chev{color:var(--mut);text-align:right;width:18px}
.t{position:relative;border-bottom:1px dotted var(--mut);cursor:help}.t sup{color:var(--acc)}
.t:hover::after{content:attr(data-tip);position:absolute;left:0;bottom:135%;width:270px;background:#0b0f14;border:1px solid var(--line);color:var(--ink);padding:9px 11px;border-radius:8px;font-size:12px;font-weight:400;z-index:20;box-shadow:0 6px 24px #0008;white-space:normal}
.gdef{display:flex;gap:12px;padding:7px 0;border-bottom:1px solid var(--line);font-size:13px}.gdef b{min-width:175px;color:var(--acc)}.gdef span{color:var(--mut)}
.drawer{position:fixed;top:0;right:0;height:100%;width:420px;max-width:100%;background:#141b27;border-left:1px solid var(--line);padding:22px;transform:translateX(102%);transition:.25s;overflow:auto;box-shadow:-12px 0 40px #0009;z-index:30}
.drawer.open{transform:none}.x{position:absolute;top:12px;right:16px;cursor:pointer;color:var(--mut);font-size:22px}
.pill{display:inline-block;background:#202b3b;border:1px solid var(--line);border-radius:20px;padding:3px 10px;font-size:11px;color:var(--mut);margin:3px 4px 3px 0}
.nxt{display:block;background:#202b3b;border:1px solid var(--line);border-radius:8px;padding:10px;margin-top:8px;color:var(--ink);text-decoration:none;font-size:13px;cursor:pointer}.nxt:hover{border-color:var(--acc)}.nxt small{color:var(--mut)}
.bars{margin:6px 0}.barrow{display:flex;align-items:center;gap:8px;margin:4px 0;font-size:12px}.barrow .lbl{width:90px;color:var(--mut)}.barrow .bx{height:14px;border-radius:3px}
@media(max-width:760px){.kpis,.tcards{grid-template-columns:repeat(2,1fr)}.drawer{width:100%}}
</style></head><body><div class="wrap">
"""

# JS is a plain string (NOT f-string): ${...} and {} are literal JS.
JS = r"""
<div class="drawer" id="dw"><span class="x" onclick="document.getElementById('dw').classList.remove('open')">&times;</span><div id="dwb"></div></div>
<script>
const D=window.DATA, MM=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const TYPES=["eCommerce","K2K","API","FedEx","Gross Profit Share"];
const PAL={eCommerce:"#4f9dff",K2K:"#36d399",API:"#fbbd23",FedEx:"#a78bfa","Gross Profit Share":"#f87272"};
const $=(id)=>document.getElementById(id);
const m=(x)=>"$"+Math.round(x).toLocaleString();
const gc="#2a3543",tc="#8b98a9";
const BT=D.by_type_month;
const yt=(y)=>MM.map((_,i)=>TYPES.reduce((s,t)=>s+((BT[y]&&BT[y][t]?BT[y][t][i]:0)||0),0));
const t26=yt("2026"),t25=yt("2025"),t24=yt("2024");
const closed=[];for(let i=0;i<12;i++)if(t26[i]>0)closed.push(i);
const last=closed[closed.length-1],n=closed.length;
const ytd=closed.reduce((s,i)=>s+t26[i],0), ytd25=closed.reduce((s,i)=>s+t25[i],0);
const yoy=ytd25?ytd/ytd25:1;
let rem=0;for(let i=0;i<12;i++)if(!closed.includes(i))rem+=t25[i];
const proj=ytd+rem*yoy, gap=D.target_2026-proj;
const naive=n>=2?((t26[closed[n-1]]+t26[closed[n-2]])/2)*12:proj;

function tip(term){const d=(D.definitions[term]||"").replace(/"/g,"&quot;");return `<span class="t" data-tip="${d}">${term}<sup>?</sup></span>`;}
$("kpis").innerHTML=[
 ["2026 YTD TX Fees",m(ytd),"thru "+MM[last]+" · "+n+" mo · ","YTD TX Fees"],
 ["Seasonality-aware proj.",m(proj),Math.round(proj/D.target_2026*100)+"% of $4M · ","Seasonality-aware projection"],
 ["Gap to $4M",m(gap),"vs projection · ","Gap to $4M"],
 ["YoY growth (YTD)","+"+Math.round((yoy-1)*100)+"%","naive ×12="+m(naive)+" (overstated) · ","YoY view"]
].map(([l,v,s,term])=>`<div class="kpi"><div class="kpi-label">${l}</div><div class="kpi-val">${v}</div><div class="kpi-sub">${s}${tip(term)}</div></div>`).join("");

// fee-type cards (click -> type drawer). YoY hover shows the underlying YTD comparison.
$("tcards").innerHTML=TYPES.filter(t=>t!=="Gross Profit Share").map(t=>{
 const v26=closed.reduce((s,i)=>s+BT["2026"][t][i],0);
 const v25=closed.reduce((s,i)=>s+(BT["2025"][t][i]||0),0);
 const v24=closed.reduce((s,i)=>s+(BT["2024"][t][i]||0),0);
 const g=v25?(v26/v25-1)*100:0;
 const tipTxt=`${t}: 2026 YTD ${m(v26)} vs 2025 same-months ${m(v25)} (2024: ${m(v24)}). Growth ${g>=0?'+':''}${Math.round(g)}% YoY. Click for trend + clients + Mar→Apr drivers.`;
 return `<div class="tcard" onclick="typeDrill('${t}')"><div class="nm">${t}</div><div class="v">${m(v26)}</div>
   <div class="yo t ${g>=0?'up':'dn'}" data-tip="${tipTxt.replace(/"/g,'&quot;')}">${g>=0?'+':''}${Math.round(g)}% YoY<sup>?</sup> ›</div></div>`;}).join("");

// charts
let mainBar,mainLine;
function drawType(){
 if(mainLine){mainLine.destroy();mainLine=null;}
 if(mainBar){mainBar.destroy();}
 const ds=TYPES.map(t=>({label:t,data:BT["2026"][t].map(x=>Math.round(x)),backgroundColor:PAL[t],stack:"f"}));
 mainBar=new Chart($("mainc"),{type:"bar",data:{labels:MM,datasets:ds},
  options:{responsive:true,onClick:(e,el)=>{if(el.length)typeDrill(TYPES[el[0].datasetIndex])},
   plugins:{legend:{labels:{color:"#e6edf3"}}},scales:{x:{stacked:true,grid:{color:gc},ticks:{color:tc}},y:{stacked:true,grid:{color:gc},ticks:{color:tc,callback:v=>"$"+(v/1000)+"K"}}}}});
}
function drawYoY(){
 if(mainBar){mainBar.destroy();mainBar=null;}
 if(mainLine){mainLine.destroy();}
 const mk=(lab,arr,col,dash)=>({label:lab,data:arr.map(x=>x?Math.round(x):null),borderColor:col,backgroundColor:col+"22",tension:.3,spanGaps:false,borderDash:dash||[]});
 mainLine=new Chart($("mainc"),{type:"line",data:{labels:MM,datasets:[
   mk("2024",t24,"#5b6675",[3,3]),mk("2025",t25,"#8b98a9"),mk("2026",t26,"#36d399")]},
  options:{responsive:true,plugins:{legend:{labels:{color:"#e6edf3"}}},scales:{x:{grid:{color:gc},ticks:{color:tc}},y:{grid:{color:gc},ticks:{color:tc,callback:v=>"$"+(v/1000)+"K"}}}}});
}
let view="type";
function setView(v){view=v;$("tabType").classList.toggle("on",v==="type");$("tabYoY").classList.toggle("on",v==="yoy");
 $("mainhint").innerHTML=v==="type"?"Stacked monthly 2026 by fee type. Click a segment (or a card above) to drill into that fee type.":"Total monthly fees 2024 vs 2025 vs 2026 — seasonality read from real history (Feb &amp; May peaks). 2026 (green) running +"+Math.round((yoy-1)*100)+"% YoY.";
 v==="type"?drawType():drawYoY();}

// drawer
const dw=$("dw"),dwb=$("dwb");
function open(html){dwb.innerHTML=html;dw.classList.add("open");}
let dchart;
function typeDrill(t){
 const tot=closed.reduce((s,i)=>s+BT["2026"][t][i],0);
 const v25=closed.reduce((s,i)=>s+(BT["2025"][t][i]||0),0);
 const g=v25?Math.round((tot/v25-1)*100):0;
 const clients=(D.clients_by_type_2026[t]||[]);
 const crows=clients.map(([c,v])=>`<tr class="drill" onclick="acctDrill('${c.replace(/'/g,"\\'")}')"><td>${c}</td><td class="num">${m(v)}</td><td class="chev">›</td></tr>`).join("");
 let jump="";const jp=D.jump_mar_apr[t];
 if(jp){jump=`<h4 style="margin:16px 0 6px">Mar → Apr jump (who moved)</h4><div class="hint">Broad seasonal ramp (Mother's Day) — top accounts ~doubled, not one driver.</div>
   <table><tr><th>Account</th><th class="num">Mar</th><th class="num">Apr</th></tr>${jp.slice(0,6).map(([c,a,b])=>`<tr><td>${c}</td><td class="num">${m(a)}</td><td class="num">${m(b)}</td></tr>`).join("")}</table>`;}
 open(`<div class="crumbs">TX Pacing › ${t}</div><h3>${t} — ${m(tot)} YTD <span class="${g>=0?'up':'dn'}" style="font-size:14px">(+${g}% YoY)</span></h3>
  <div class="hint">${(D.definitions[t]||"")}</div>
  <canvas id="dc" height="150"></canvas>
  <h4 style="margin:16px 0 6px">Top clients in ${t} (2026)</h4>
  <table><tr><th>Account</th><th class="num">TX fees</th><th></th></tr>${crows}</table>${jump}`);
 if(dchart)dchart.destroy();
 const mk=(lab,arr,col,dash)=>({label:lab,data:arr.map(x=>x?Math.round(x):null),borderColor:col,tension:.3,spanGaps:false,pointRadius:0,borderDash:dash||[]});
 dchart=new Chart($("dc"),{type:"line",data:{labels:MM,datasets:[mk("2024",BT["2024"][t],"#5b6675",[3,3]),mk("2025",BT["2025"][t],"#8b98a9"),mk("2026",BT["2026"][t],PAL[t])]},
  options:{plugins:{legend:{labels:{color:"#e6edf3",font:{size:10}}}},scales:{x:{grid:{color:gc},ticks:{color:tc,font:{size:9}}},y:{grid:{color:gc},ticks:{color:tc,font:{size:9},callback:v=>"$"+(v/1000)+"K"}}}}});
}
// ACCOUNT 360 — real data across Snowflake (TX trend/mix) + Salesforce (profile) + Fathom (on-demand)
function bars(obj,total){return Object.entries(obj).filter(([k,v])=>v>0).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`<div class="barrow"><span class="lbl">${k}</span><span class="bx" style="width:${Math.max(5,v/total*210)}px;background:${PAL[k]||'#4f9dff'}"></span><span>${m(v)}</span></div>`).join("");}
function acctDrill(name){
 const a=D.account_360[name];
 if(!a){open(`<div class="crumbs">TX Pacing › Account</div><h3>${name}</h3><p class="hint">Full 360 was pulled for the top 15 accounts. For this one, say the word and I'll pull its pack (Snowflake trend + SF profile + Fathom).</p>`);return;}
 const s=a.sf||{}, rel=a.rel||{}, an=a.annual, t26=an["2026"]||0, t25=an["2025"]||0, t24=an["2024"]||0;
 const arr=s.ARR__c||0, ratio=arr?(t26/arr):0;
 const yoyFull=t25?((t26/t25-1)*100):0; // 2026 YTD vs 2025 FULL year (partial-year caveat)
 const maxY=Math.max(t24,t25,t26)||1;
 const yoyBars=[["2024",t24,"#5b6675"],["2025",t25,"#8b98a9"],["2026 YTD",t26,"#36d399"]].map(([y,v,c])=>`<div class="barrow"><span class="lbl">${y}</span><span class="bx" style="width:${Math.max(5,v/maxY*210)}px;background:${c}"></span><span>${m(v)}</span></div>`).join("");
 const mixTot=Object.values(a.mix).reduce((x,y)=>x+y,0);
 const ec=a.mix["eCommerce"]||0;
 let flags=[];
 if(s.API_Fee_Percentage__c && s.API_Fee_Percentage__c<1.5) flags.push(["#fbbd23",`Rate concession: ${s.API_Fee_Percentage__c}% (vs 1.5% std)`]);
 if(s.Segment__c && /(Sleep|Attention)/i.test(s.Segment__c)) flags.push(["#f87272",`Churn watch — segment "${s.Segment__c}"`]);
 if(s.Komet_E_commerce__c && ec < t26*0.05) flags.push(["#4f9dff","eCommerce module ON but ~0 eComm fees → activation opportunity"]);
 if(ratio>=2) flags.push(["#36d399",`High TX leverage: TX fees are ${ratio.toFixed(1)}× SaaS ARR`]);
 if(rel.days_to_renewal!=null && rel.days_to_renewal>=0 && rel.days_to_renewal<=60) flags.push(["#f87272",`Renewal in ${rel.days_to_renewal} days (${rel.renewal})`]);
 const flagHtml=flags.map(([c,t])=>`<div style="border-left:3px solid ${c};padding:5px 9px;margin:5px 0;background:#1c2533;border-radius:4px;font-size:12px">${t}</div>`).join("")||"<div class='hint'>no auto-flags</div>";
 const yn=(b)=>b?"✓":"✗";
 open(`<div class="crumbs">TX Pacing › ${s.Name||name}</div><h3>${s.Name||name}</h3>
  <div><span class="pill">${s.Business_Type__c||"—"}</span><span class="pill">${s.Segment__c||"—"}</span><span class="pill">${s.Account_Status__c||"—"}</span></div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:12px 0">
   <div class="kpi"><div class="kpi-label">2026 TX (YTD)</div><div class="kpi-val" style="font-size:20px">${m(t26)}</div></div>
   <div class="kpi"><div class="kpi-label">SaaS ARR</div><div class="kpi-val" style="font-size:20px">${m(arr)}</div></div>
   <div class="kpi"><div class="kpi-label">TX ÷ ARR</div><div class="kpi-val" style="font-size:20px">${ratio?ratio.toFixed(1)+"×":"—"}</div></div>
   <div class="kpi"><div class="kpi-label">MRR</div><div class="kpi-val" style="font-size:20px">${m(s.MRR__c||0)}</div></div>
  </div>
  <h4 style="margin:6px 0 4px">Flags</h4>${flagHtml}
  <h4 style="margin:14px 0 4px">TX fees YoY</h4>${yoyBars}
  <h4 style="margin:14px 0 4px">2026 fee mix</h4>${bars(a.mix,mixTot)}
  <h4 style="margin:14px 0 4px">Salesforce profile</h4>
  <div class="hint" style="line-height:1.9">Users: ${s.Komet_Users__c??"—"} · Locations: ${s.Komet_Locations__c??"—"}<br>
   Products: Core ${yn(s.Komet_Core__c)} · eCommerce ${yn(s.Komet_E_commerce__c)}<br>
   Fees on: K2K ${yn(s.K2K_Fee__c)} · eComm ${yn(s.E_commerce_Fee__c)} · API ${yn(s.API_Fee__c)} (${s.API_Fee_Percentage__c??"—"}%)<br>
   Komet CompanyId: ${a.id}</div>
  <h4 style="margin:14px 0 4px">Relationship &amp; renewal</h4>
  <div class="hint" style="line-height:1.9">Owner: ${rel.owner||"—"} · AM: ${rel.am||"—"} · CSA: ${rel.csa||"—"}<br>
   SLA: ${rel.sla||"—"} · Renewal: ${rel.renewal||"—"}${rel.days_to_renewal!=null?" ("+rel.days_to_renewal+"d)":""}${rel.go_live?" · Go-live: "+rel.go_live:""}${rel.churn_reason?" · Churn: "+rel.churn_reason:""}</div>
  <a class="nxt" onclick="alert('Fathom: searching org calls for ${(s.Name||name).replace(/'/g,"")} — # conversations, objections, fee sensitivity. (FloraLink had 1 recent mention.)')">Conversations / objections (Fathom) →<br><small>pull on demand</small></a>
  <p class="hint" style="margin-top:10px">Deeper layers: account → channel/leg → month → transaction.</p>`);
}
// top accounts table click
document.querySelectorAll("tr.acctrow").forEach(r=>r.onclick=()=>acctDrill(r.dataset.acct));
// glossary tooltips already inline
setView("type");
</script></body></html>"""

def money(x): return "${:,.0f}".format(x)

def build_tx_fee_pacing():
    d = json.loads((DATA/"tx_fee_pacing.json").read_text())
    acct_rows = "".join(
        f'<tr class="drill acctrow" data-acct="{a.strip()}"><td>{i+1}</td><td>{a}</td><td class="num">{money(v)}</td><td class="chev">›</td></tr>'
        for i,(a,v) in enumerate(d["top_accounts_2026"]))
    gloss = "".join(f'<div class="gdef"><b>{k}</b><span>{v}</span></div>' for k,v in d["definitions"].items())
    body = f"""
 <div class="crumbs"><a onclick="alert('Dashboard index — coming as the other 5 are built')">Koronet OS</a> › TX Fee Pacing</div>
 <h1>TX Fee Pacing — path to $4M (2026)</h1>
 <div class="sub">{d['source']} · pulled {d['pulled_at']} · {d['notes']}</div>
 <div class="kpis" id="kpis"></div>
 <div class="tcards" id="tcards"></div>
 <div class="card">
   <div class="tabs"><button id="tabType" class="on" onclick="setView('type')">By fee type (2026)</button><button id="tabYoY" onclick="setView('yoy')">YoY 2024–26</button></div>
   <div class="hint" id="mainhint"></div><canvas id="mainc" height="110"></canvas>
 </div>
 <div class="card"><h2>Top accounts driving 2026 TX fees</h2><div class="hint">Click an account → characteristics (spend, mix, growth, conversations). Top 15.</div>
   <table><thead><tr><th>#</th><th>Account</th><th class="num">2026 TX fees</th><th></th></tr></thead><tbody>{acct_rows}</tbody></table></div>
 <div class="card"><h2>Definitions</h2>{gloss}</div>
 <div style="color:var(--mut);font-size:12px">Koronet OS · re-run <code>python3 dashboards/build.py</code> after a data refresh.</div>
</div>
<script>window.DATA={json.dumps(d)};</script>
"""
    return HEAD + body + JS

def main():
    (ROOT/"tx_fee_pacing.html").write_text(build_tx_fee_pacing())
    print("Wrote", ROOT/"tx_fee_pacing.html")

if __name__ == "__main__":
    main()
