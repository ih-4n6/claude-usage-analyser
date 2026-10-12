#!/usr/bin/env python3
"""claude-usage-analyser — report builder.

Merges the deterministic extraction (data.json) with the analyst layer
(insights.json) into a single self-contained index.html. Data is inlined so the
file opens anywhere (file:// can't fetch a sibling JSON).

Usage:
    python build_report.py [--data data.json] [--insights insights.json] [--out index.html]
"""
import json, os, datetime, argparse

HERE = os.path.dirname(os.path.abspath(__file__))

REPORTS = os.path.join(HERE, "reports")
ap = argparse.ArgumentParser()
ap.add_argument("--data", default=os.path.join(REPORTS, "data.json"))
ap.add_argument("--insights", default=os.path.join(REPORTS, "insights.json"))
ap.add_argument("--out", default=os.path.join(REPORTS, "index.html"))
args = ap.parse_args()

with open(args.data, encoding="utf-8") as f:
    d = json.load(f)
insights = {}
if os.path.exists(args.insights):
    with open(args.insights, encoding="utf-8") as f:
        insights = json.load(f)

ws = datetime.datetime.fromisoformat(d["window_start"])
we = datetime.datetime.fromisoformat(d["window_end"])
window_label = f"{ws:%d %b %Y, %H:%M} - {we:%d %b %Y, %H:%M} UTC"
gen_label = f"{we:%d %b %Y %H:%M} UTC"
baseline_week = d["baseline_monthly"] * d.get("window_days", 7) / 30.44
multiplier = d["total_cost"] / baseline_week if baseline_week else 0

payload = {
    "windowLabel": window_label, "genLabel": gen_label, "windowDays": d.get("window_days", 7),
    "totalCost": d["total_cost"], "baselineMonthly": d["baseline_monthly"],
    "baselineWeek": baseline_week, "multiplier": multiplier,
    "rows": d["rows"], "dupes": d["dupes"], "filesScanned": d["files_scanned"],
    "webSearches": d["web_searches"], "fastRows": d["fast_rows"],
    "components": d["cost_components"], "tokens": d["tok_totals"],
    "byProject": d["by_project"], "byDay": d["by_day"], "byModel": d["by_model"],
    "byProjModel": d["by_proj_model"], "dailyProject": d["daily_project"],
    "globalTools": d.get("global_tools", []), "pricing": d["pricing"],
    "pricingProvenance": d.get("pricing_provenance", {}),
    "unpricedModels": d.get("unpriced_models", {}),
    "availableModels": d.get("available_models", []),
    "insights": insights,
}
DATA_JS = json.dumps(payload)

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude Code - Usage & Cost Analysis</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{
  --paper:#FBFAF7; --surface:#FFFFFF; --ink:#1A1A18; --muted:#6B6862;
  --faint:#9A958C; --hair:#E6E2D9; --hair-2:#EFECE4; --grid:#ECE8DF;
  --accent:#C2410C; --accent-soft:#E0814F; --accent-wash:#F6E9E0; --good:#3F6B3F;
  --sev-high:#C2410C; --sev-med:#B5852A; --sev-low:#7A8A6F;
  --sp1:4px;--sp2:8px;--sp3:12px;--sp4:16px;--sp5:24px;--sp6:32px;--sp7:48px;--sp8:64px;
  --maxw:1120px;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"IBM Plex Sans",system-ui,sans-serif;font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased}
.wrap{max-width:var(--maxw);margin:0 auto;padding:var(--sp7) var(--sp5) var(--sp8)}
.mono,.num{font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums;font-feature-settings:"tnum" 1}
h1,h2,h3{font-family:"Newsreader",Georgia,serif;font-weight:500;letter-spacing:-0.01em;margin:0}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}

.masthead{border-bottom:2px solid var(--ink);padding-bottom:var(--sp4);margin-bottom:var(--sp6)}
.kicker{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:0.22em;text-transform:uppercase;color:var(--accent);font-weight:600}
.masthead h1{font-size:clamp(30px,5.5vw,52px);line-height:1.02;margin:var(--sp3) 0;font-weight:600}
.dateline{display:flex;flex-wrap:wrap;gap:var(--sp2) var(--sp5);font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--muted)}
.dateline b{color:var(--ink);font-weight:500}

.verdict{display:grid;grid-template-columns:1.1fr 0.9fr;gap:var(--sp7);align-items:start;margin:var(--sp7) 0}
@media(max-width:720px){.verdict{grid-template-columns:1fr;gap:var(--sp5)}}
.bignum{font-family:"IBM Plex Mono",monospace;font-weight:600;font-size:clamp(48px,11vw,92px);line-height:0.92;letter-spacing:-0.03em;color:var(--accent);font-variant-numeric:tabular-nums}
.bignum small{font-size:0.34em;color:var(--ink);letter-spacing:0;display:inline-block;vertical-align:0.55em;margin-left:6px}
.verdict .lede{font-family:"Newsreader",Georgia,serif;font-size:clamp(18px,2.5vw,23px);line-height:1.42}
.verdict .lede em{font-style:italic;color:var(--accent)}
.verdict .sub{margin-top:var(--sp4);font-size:13.5px;color:var(--muted);line-height:1.5}
.compare{margin-top:var(--sp4)}
.compare .row{display:grid;grid-template-columns:96px 1fr auto;align-items:center;gap:var(--sp3);margin:var(--sp2) 0}
.compare .lbl{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:0.04em;text-transform:uppercase;color:var(--muted);text-align:right}
.compare .track{display:block;height:22px;background:var(--hair-2);overflow:hidden}
.compare .fill{display:block;height:100%}
.compare .fill.api{background:var(--accent)}.compare .fill.sub{background:var(--ink)}
.compare .val{font-family:"IBM Plex Mono",monospace;font-size:13px;font-weight:600;min-width:64px;text-align:right}

.sec{margin-top:var(--sp8)}
.sec-head{display:flex;align-items:baseline;justify-content:space-between;gap:var(--sp4);border-bottom:1px solid var(--hair);padding-bottom:var(--sp2);margin-bottom:var(--sp5)}
.sec-head h2{font-size:24px}
.sec-head .meta{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:0.04em;color:var(--faint);text-transform:uppercase}
.sec-note{font-size:13px;color:var(--muted);max-width:64ch;margin:-8px 0 var(--sp5)}

.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--hair);border:1px solid var(--hair)}
@media(max-width:720px){.stats{grid-template-columns:repeat(2,1fr)}}
.stat{background:var(--surface);padding:var(--sp4)}
.stat .k{font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:0.1em;text-transform:uppercase;color:var(--muted)}
.stat .v{font-family:"IBM Plex Mono",monospace;font-size:26px;font-weight:600;margin-top:6px;letter-spacing:-0.02em}
.stat .d{font-size:12px;color:var(--faint);margin-top:2px}

.compbar{height:46px;display:flex;width:100%;border:1px solid var(--hair);overflow:hidden;margin-bottom:var(--sp4)}
.compbar .seg{height:100%;position:relative}
.complegend{display:grid;grid-template-columns:repeat(2,1fr);gap:var(--sp3) var(--sp6)}
@media(max-width:560px){.complegend{grid-template-columns:1fr}}
.legrow{display:grid;grid-template-columns:14px 1fr auto auto;gap:var(--sp3);align-items:baseline;padding:var(--sp2) 0;border-bottom:1px solid var(--hair-2)}
.legrow .sw{width:12px;height:12px;margin-top:3px;border-radius:2px}
.legrow .nm{font-size:13.5px}
.legrow .pc{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--muted);min-width:48px;text-align:right}
.legrow .dl{font-family:"IBM Plex Mono",monospace;font-size:13px;font-weight:600;min-width:74px;text-align:right}

.daily{width:100%;height:240px}
.axis text{font-family:"IBM Plex Mono",monospace;font-size:10px;fill:var(--faint)}
.bar{fill:var(--ink)}.bar.peak{fill:var(--accent)}
.barval{font-family:"IBM Plex Mono",monospace;font-size:11px;fill:var(--ink);font-weight:600}
.gridline{stroke:var(--grid);stroke-width:1}

/* findings */
.findings{display:grid;grid-template-columns:repeat(2,1fr);gap:1px;background:var(--hair);border:1px solid var(--hair)}
@media(max-width:720px){.findings{grid-template-columns:1fr}}
.finding{background:var(--surface);padding:var(--sp5)}
.finding .ft{font-family:"Newsreader",serif;font-size:18px;font-weight:600;margin-bottom:var(--sp2);display:flex;gap:var(--sp2);align-items:baseline}
.finding .fn{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--accent);font-weight:600}
.finding .fd{font-size:13.5px;color:var(--ink);line-height:1.5}
.finding .fl{margin-top:var(--sp3);font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:0.04em;text-transform:uppercase;color:var(--muted);border-top:1px solid var(--hair-2);padding-top:var(--sp2)}
.lede-block{font-family:"Newsreader",serif;font-size:clamp(17px,2.2vw,20px);line-height:1.5;max-width:74ch;margin:0 0 var(--sp5);color:var(--ink)}

/* heatmap */
.heat{width:100%;border-collapse:collapse;font-size:12px}
.heat th{font-family:"IBM Plex Mono",monospace;font-size:10px;letter-spacing:0.04em;text-transform:uppercase;color:var(--muted);font-weight:500;padding:0 6px var(--sp2);text-align:center}
.heat th.l{text-align:left;padding-left:0}
.heat td{padding:0;border:1px solid var(--paper)}
.heat td.l{font-size:12.5px;padding:0 var(--sp3) 0 0;border:none;white-space:nowrap;font-weight:500}
.heat .cell{display:block;height:30px;line-height:30px;text-align:center;font-family:"IBM Plex Mono",monospace;font-size:10.5px;color:var(--ink)}
.heat .rowtot{font-family:"IBM Plex Mono",monospace;font-weight:600;text-align:right;padding-left:var(--sp3);border:none}
.heat-leg{display:flex;align-items:center;gap:var(--sp2);font-family:"IBM Plex Mono",monospace;font-size:10.5px;color:var(--muted);margin-top:var(--sp3)}
.heat-leg .sw{width:22px;height:11px;display:inline-block}

/* tables */
table.dt{width:100%;border-collapse:collapse;font-size:13.5px}
.dt thead th{font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:0.08em;text-transform:uppercase;color:var(--muted);font-weight:500;text-align:right;padding:0 var(--sp3) var(--sp2);border-bottom:1px solid var(--ink);white-space:nowrap}
.dt thead th.l{text-align:left}
.dt tbody td{padding:var(--sp3);border-bottom:1px solid var(--hair-2);text-align:right;vertical-align:middle}
.dt tbody td.l{text-align:left}
.dt tbody tr:hover{background:#FCFBF8}
.rank{font-family:"IBM Plex Mono",monospace;color:var(--faint);font-size:12px;width:26px}
.minibar{height:8px;background:var(--accent);display:inline-block;vertical-align:middle;min-width:1px}
.spark{display:block}
.mtag{font-family:"IBM Plex Mono",monospace;font-size:10px;letter-spacing:0.04em;color:var(--muted)}
.cost-cell{font-family:"IBM Plex Mono",monospace;font-weight:600}
.totrow td{border-top:1px solid var(--ink);border-bottom:none;font-weight:600;padding-top:var(--sp3)}
.totrow .cost-cell{color:var(--accent)}

/* deep dives */
.dive{border:1px solid var(--hair);background:var(--surface);margin-bottom:var(--sp3)}
.dive>summary{list-style:none;cursor:pointer;padding:var(--sp4) var(--sp5);display:grid;grid-template-columns:26px 1fr 130px 90px 110px;gap:var(--sp3);align-items:center}
.dive>summary::-webkit-details-marker{display:none}
.dive>summary:hover{background:#FCFBF8}
.dive .dname{font-weight:600;font-size:15px}
.dive .dshare{height:8px;background:var(--hair-2);position:relative;overflow:hidden}
.dive .dshare i{position:absolute;left:0;top:0;bottom:0;background:var(--accent)}
.dive .dcost{font-family:"IBM Plex Mono",monospace;font-weight:600;text-align:right}
.dive .dpc{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--muted);text-align:right}
.dive .chev{font-family:"IBM Plex Mono",monospace;color:var(--faint);font-size:12px;transition:transform .15s}
.dive[open] .chev{transform:rotate(90deg)}
.dive .body{padding:0 var(--sp5) var(--sp5);border-top:1px solid var(--hair-2);margin-top:0}
.metrics{display:grid;grid-template-columns:repeat(6,1fr);gap:1px;background:var(--hair);border:1px solid var(--hair);margin:var(--sp4) 0}
@media(max-width:720px){.metrics{grid-template-columns:repeat(3,1fr)}}
.metric{background:var(--surface);padding:var(--sp3)}
.metric .mk{font-family:"IBM Plex Mono",monospace;font-size:9.5px;letter-spacing:0.06em;text-transform:uppercase;color:var(--muted)}
.metric .mv{font-family:"IBM Plex Mono",monospace;font-size:17px;font-weight:600;margin-top:3px}
.dive .col2{display:grid;grid-template-columns:1fr 1fr;gap:var(--sp6)}
@media(max-width:720px){.dive .col2{grid-template-columns:1fr;gap:var(--sp4)}}
.subh{font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:0.08em;text-transform:uppercase;color:var(--muted);margin:var(--sp3) 0 var(--sp2)}
.toolrow{display:grid;grid-template-columns:90px 1fr auto;gap:var(--sp2);align-items:center;margin:5px 0;font-size:12px}
.toolrow .tn{font-family:"IBM Plex Mono",monospace}
.toolrow .tt{height:7px;background:var(--hair-2);overflow:hidden}
.toolrow .tt i{display:block;height:100%;background:var(--accent-soft)}
.toolrow .tv{font-family:"IBM Plex Mono",monospace;color:var(--muted);text-align:right;min-width:58px}
.flag{display:flex;gap:var(--sp2);align-items:baseline;font-size:12.5px;margin:var(--sp2) 0;line-height:1.45}
.flag .sv{font-family:"IBM Plex Mono",monospace;font-size:9.5px;letter-spacing:0.05em;text-transform:uppercase;font-weight:600;padding:1px 5px;border-radius:2px;white-space:nowrap;color:#fff}
.sv.high{background:var(--sev-high)}.sv.med{background:var(--sev-med)}.sv.low{background:var(--sev-low)}
.recs{margin:var(--sp2) 0 0;padding-left:1.05em}
.recs li{margin:6px 0;font-size:13px;line-height:1.45}
.analyst-summary{font-size:13.5px;line-height:1.5;color:var(--ink);background:var(--accent-wash);border-left:2px solid var(--accent);padding:var(--sp3) var(--sp4);margin:var(--sp4) 0}
.no-insight{font-size:12.5px;color:var(--faint);font-style:italic}

.method{background:var(--surface);border:1px solid var(--hair);padding:var(--sp5)}
.method h3{font-size:18px;margin-bottom:var(--sp3)}
.method ul{margin:0 0 var(--sp4);padding-left:1.1em}
.method li{margin:var(--sp2) 0;font-size:13.5px}
.method li b{font-weight:600}
.pricegrid{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:var(--sp2)}
.pricegrid th,.pricegrid td{text-align:right;padding:6px var(--sp3);border-bottom:1px solid var(--hair-2);font-family:"IBM Plex Mono",monospace}
.pricegrid th{color:var(--muted);font-weight:500;font-size:10.5px;letter-spacing:0.06em;text-transform:uppercase}
.pricegrid td.l,.pricegrid th.l{text-align:left}

footer{margin-top:var(--sp7);padding-top:var(--sp4);border-top:1px solid var(--hair);font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--faint);display:flex;justify-content:space-between;flex-wrap:wrap;gap:var(--sp3)}
@media print{body{background:#fff}.wrap{padding:0}.stat,.method,.compbar,.dive,.finding{break-inside:avoid}.dive .body{display:block!important}}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
</head>
<body>
<div class="wrap">

  <header class="masthead">
    <div class="kicker">Usage &amp; Cost Analysis · Claude Code · Pay-as-you-go API equivalent</div>
    <h1 id="mast-h1">What this period of Claude Code would cost on the API — and where to trim it</h1>
    <div class="dateline">
      <span>Window&nbsp; <b id="dl-window"></b></span>
      <span>Pricing&nbsp; <b>first-party API, prompt-caching on</b></span>
      <span>Generated&nbsp; <b id="dl-gen"></b></span>
    </div>
  </header>

  <section class="verdict">
    <div><div class="bignum" id="v-total"></div><div class="compare" id="v-compare"></div></div>
    <div><p class="lede" id="v-lede"></p><p class="sub" id="v-sub"></p></div>
  </section>

  <section class="sec" id="sec-findings">
    <div class="sec-head"><h2>The efficiency picture</h2><span class="meta">analyst findings</span></div>
    <p class="lede-block" id="findings-lede"></p>
    <div class="findings" id="findings"></div>
  </section>

  <section class="sec">
    <div class="sec-head"><h2>Where the money goes</h2><span class="meta">cost composition</span></div>
    <p class="sec-note">Priced from the tokens the transcripts actually recorded. Caching was already active, so cache reads and writes are billed at their real multipliers (read 0.1×, 1-hour write 2×).</p>
    <div class="compbar" id="comp-bar"></div>
    <div class="complegend" id="comp-legend"></div>
  </section>

  <section class="sec">
    <div class="sec-head"><h2>Cost by day</h2><span class="meta">rolling window</span></div>
    <svg class="daily" id="daily" viewBox="0 0 1000 240" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Daily API-equivalent cost"></svg>
  </section>

  <section class="sec">
    <div class="sec-head"><h2>Cost by project &amp; day</h2><span class="meta">per-day drill-down</span></div>
    <p class="sec-note">Each cell is one project's API-equivalent spend on one day. Darker = more. This is the full per-day-per-project matrix.</p>
    <div style="overflow-x:auto"><table class="heat" id="heat"></table></div>
    <div class="heat-leg" id="heat-leg"></div>
  </section>

  <section class="sec">
    <div class="sec-head"><h2>Where context comes from</h2><span class="meta">tool output fed into context</span></div>
    <p class="sec-note">Tokens each tool returned into the conversation. Whatever lands in context is cached (a 1-hour write at 2× base) and then re-read on every later turn — so the biggest context-fillers drive both the write and the read lines.</p>
    <div id="tools-chart"></div>
  </section>

  <section class="sec">
    <div class="sec-head"><h2>Token volume</h2><span class="meta">what was processed</span></div>
    <div class="stats" id="tok-stats"></div>
  </section>

  <section class="sec">
    <div class="sec-head"><h2>Project deep-dives</h2><span class="meta" id="proj-meta"></span></div>
    <p class="sec-note">Ranked by spend. Click a project for its cache economics, the tools filling its context, computed efficiency flags, and recommendations. Flags are derived by the analyser; the summary &amp; recommendations are analyst commentary on top of the numbers.</p>
    <div id="dives"></div>
  </section>

  <section class="sec">
    <div class="sec-head"><h2>By model</h2><span class="meta">tokens · cost</span></div>
    <table class="dt" id="model-table">
      <thead><tr><th class="l">Model</th><th>Fresh in</th><th>Cache read</th><th>Cache write</th><th>Output</th><th>API calls</th><th>Cost</th></tr></thead>
      <tbody></tbody>
    </table>
  </section>

  <section class="sec">
    <div class="method">
      <h3>Method &amp; assumptions</h3>
      <ul id="method-list"></ul>
      <h3 style="margin-top:var(--sp5)">API rates applied (USD per million tokens)</h3>
      <table class="pricegrid" id="price-grid">
        <thead><tr><th class="l">Model</th><th>Input</th><th>Cache read</th><th>5m write</th><th>1h write</th><th>Output</th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </section>

  <footer><span>Self-contained report · claude-usage-analyser</span><span id="ft-gen"></span></footer>
</div>

<script>
const DATA = __DATA__;
const I = DATA.insights || {};
const fmtUSD=(n,dp=2)=>'$'+n.toLocaleString('en-US',{minimumFractionDigits:dp,maximumFractionDigits:dp});
const fmtUSD0=n=>'$'+Math.round(n).toLocaleString('en-US');
const fmtInt=n=>n.toLocaleString('en-US');
const fmtTok=n=>{if(n>=1e9)return (n/1e9).toFixed(2)+'B';if(n>=1e6)return (n/1e6).toFixed(1)+'M';if(n>=1e3)return (n/1e3).toFixed(0)+'K';return ''+n;};
const esc=s=>(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const labelOf=k=>{const p=String(k||'').split('-');if(!p.length)return k;
  const fam=p[0].charAt(0).toUpperCase()+p[0].slice(1);const ver=p.slice(1).join('.');return ver?fam+' '+ver:fam;};

document.getElementById('mast-h1').textContent=`What ${DATA.windowDays} days of Claude Code would cost on the API — and where to trim it`;
document.getElementById('dl-window').textContent=DATA.windowLabel;
document.getElementById('dl-gen').textContent=DATA.genLabel;
document.getElementById('ft-gen').textContent='Generated '+DATA.genLabel;

// verdict
document.getElementById('v-total').innerHTML=fmtUSD(DATA.totalCost)+'<small>over '+DATA.windowDays+' days</small>';
document.getElementById('v-lede').innerHTML='On metered API pricing, the same week of work would have cost <em>'+fmtUSD(DATA.totalCost)+'</em> — about <em>'+DATA.multiplier.toFixed(0)+'×</em> the cost of the Max&nbsp;20× subscription.';
document.getElementById('v-sub').innerHTML='Max&nbsp;20× runs '+fmtUSD0(DATA.baselineMonthly)+'/month, ~'+fmtUSD(DATA.baselineWeek)+' for a '+DATA.windowDays+'-day slice. The subscription absorbed '+fmtUSD0(DATA.totalCost-DATA.baselineWeek)+' of usage you never paid for à la carte.';
const cmax=Math.max(DATA.totalCost,DATA.baselineWeek);
document.getElementById('v-compare').innerHTML=`
  <div class="row"><span class="lbl">API metered</span><span class="track"><span class="fill api" style="width:${(DATA.totalCost/cmax*100).toFixed(1)}%"></span></span><span class="val">${fmtUSD(DATA.totalCost)}</span></div>
  <div class="row"><span class="lbl">Max 20× / wk</span><span class="track"><span class="fill sub" style="width:${Math.max(DATA.baselineWeek/cmax*100,1.2).toFixed(1)}%"></span></span><span class="val">${fmtUSD(DATA.baselineWeek)}</span></div>`;

// findings
(function(){
  const g=I.global||{};
  document.getElementById('findings-lede').textContent=g.headline||'';
  const fs=g.findings||[];
  document.getElementById('findings').innerHTML=fs.map((f,i)=>`
    <div class="finding"><div class="ft"><span class="fn">${String(i+1).padStart(2,'0')}</span> ${esc(f.title)}</div>
      <div class="fd">${esc(f.detail)}</div><div class="fl">${esc(f.lever||'')}</div></div>`).join('');
  if(!fs.length) document.getElementById('sec-findings').style.display='none';
})();

// composition
const COMP=[['cache_read','Cache reads','var(--accent)'],['cache_write','Cache writes','var(--accent-soft)'],['output','Output tokens','#5C5852'],['fresh_input','Fresh input','#B8B2A6'],['web_search','Web search','#1A1A18']];
(function(){
  const tot=Object.values(DATA.components).reduce((a,b)=>a+b,0);
  let bar='',leg='';
  COMP.forEach(([k,nm,c])=>{const v=DATA.components[k]||0;const pc=tot?v/tot*100:0;
    if(pc>0.05)bar+=`<div class="seg" style="width:${pc}%;background:${c}" title="${nm}: ${fmtUSD(v)}"></div>`;
    leg+=`<div class="legrow"><span class="sw" style="background:${c}"></span><span class="nm">${nm}</span><span class="pc">${pc.toFixed(1)}%</span><span class="dl">${fmtUSD(v)}</span></div>`;});
  document.getElementById('comp-bar').innerHTML=bar;document.getElementById('comp-legend').innerHTML=leg;
})();

// daily chart
(function(){
  const days=DATA.byDay.slice().sort((a,b)=>a.day<b.day?-1:1);
  const W=1000,H=240,mL=46,mR=16,mT=22,mB=34,iw=W-mL-mR,ih=H-mT-mB;
  const max=Math.max(...days.map(d=>d.cost),1),niceMax=Math.ceil(max/50)*50;
  const seg=iw/days.length,x=i=>mL+i*seg+seg*0.16,bw=seg*0.68,y=v=>mT+ih-(v/niceMax)*ih;
  let s='';
  for(let g=0;g<=4;g++){const val=niceMax*g/4,yy=y(val);
    s+=`<line class="gridline" x1="${mL}" y1="${yy}" x2="${W-mR}" y2="${yy}"/><text class="axis" x="${mL-8}" y="${yy+3}" text-anchor="end">$${Math.round(val)}</text>`;}
  const peak=Math.max(...days.map(d=>d.cost));
  days.forEach((d,i)=>{const h=(d.cost/niceMax)*ih;
    s+=`<rect class="bar ${d.cost===peak?'peak':''}" x="${x(i)}" y="${y(d.cost)}" width="${bw}" height="${h}"/>`;
    s+=`<text class="barval" x="${x(i)+bw/2}" y="${y(d.cost)-6}" text-anchor="middle">$${Math.round(d.cost)}</text>`;
    const dt=new Date(d.day+'T00:00:00Z');
    s+=`<text class="axis" x="${x(i)+bw/2}" y="${H-mB+18}" text-anchor="middle">${dt.toLocaleDateString('en-US',{weekday:'short',timeZone:'UTC'})+' '+dt.getUTCDate()}</text>`;});
  document.getElementById('daily').innerHTML=s;
})();

// heatmap (per-day-per-project)
(function(){
  const days=DATA.byDay.map(d=>d.day).sort();
  const projs=DATA.byProject.slice(0,12);
  let max=0;
  projs.forEach(p=>days.forEach(dy=>{const v=(DATA.dailyProject[dy]||{})[p.project]||0;if(v>max)max=v;}));
  const shade=v=>{if(v<=0)return 'background:var(--surface);color:var(--faint)';
    const t=Math.pow(v/max,0.5); // sqrt scale so small values stay visible
    const a=(0.10+t*0.85).toFixed(3);
    const col=t>0.55?'#fff':'var(--ink)';
    return `background:rgba(194,65,12,${a});color:${col}`;};
  let head='<thead><tr><th class="l">Project</th>';
  days.forEach(dy=>{const dt=new Date(dy+'T00:00:00Z');head+=`<th>${dt.toLocaleDateString('en-US',{weekday:'short',timeZone:'UTC'})}<br>${dt.getUTCDate()}</th>`;});
  head+='<th>Total</th></tr></thead>';
  let body='<tbody>';
  projs.forEach(p=>{
    body+=`<tr><td class="l">${esc(p.project)}</td>`;
    days.forEach(dy=>{const v=(DATA.dailyProject[dy]||{})[p.project]||0;
      body+=`<td><span class="cell" style="${shade(v)}" title="${esc(p.project)} · ${dy}: ${fmtUSD(v)}">${v>=0.5?'$'+Math.round(v):(v>0?'·':'')}</span></td>`;});
    body+=`<td class="rowtot">${fmtUSD(p.cost)}</td></tr>`;});
  body+='</tbody>';
  document.getElementById('heat').innerHTML=head+body;
  document.getElementById('heat-leg').innerHTML=`<span>less</span>
    <span class="sw" style="background:rgba(194,65,12,0.12)"></span><span class="sw" style="background:rgba(194,65,12,0.4)"></span>
    <span class="sw" style="background:rgba(194,65,12,0.7)"></span><span class="sw" style="background:rgba(194,65,12,0.95)"></span><span>more · top 12 projects</span>`;
})();

// tools chart (global)
(function(){
  const tools=DATA.globalTools.filter(t=>t.result_tokens>0).slice(0,9);
  const max=Math.max(...tools.map(t=>t.result_tokens),1);
  document.getElementById('tools-chart').innerHTML=tools.map(t=>`
    <div class="toolrow" style="grid-template-columns:110px 1fr 150px;margin:7px 0">
      <span class="tn">${esc(t.name)}</span>
      <span class="tt" style="height:14px"><i style="width:${(t.result_tokens/max*100).toFixed(1)}%"></i></span>
      <span class="tv">${fmtTok(t.result_tokens)} tok · ${fmtInt(t.calls)} calls</span></div>`).join('');
})();

// token stats
(function(){
  const t=DATA.tokens;
  const cards=[['Cache reads',fmtTok(t.cache_read),fmtInt(t.cache_read)+' tokens · billed 0.1×'],
    ['Cache writes',fmtTok(t.cache_write),fmtInt(t.cache_write)+' tokens · 1h write 2×'],
    ['Output',fmtTok(t.output),fmtInt(t.output)+' generated'],
    ['Fresh input',fmtTok(t.fresh_input),fmtInt(t.fresh_input)+' uncached']];
  document.getElementById('tok-stats').innerHTML=cards.map(([k,v,dd])=>`<div class="stat"><div class="k">${k}</div><div class="v">${v}</div><div class="d">${dd}</div></div>`).join('');
})();

// deep dives
(function(){
  const projs=DATA.byProject;
  const maxCost=Math.max(...projs.map(p=>p.cost),1);
  const days=DATA.byDay.map(d=>d.day).sort();
  document.getElementById('proj-meta').textContent=projs.length+' projects active';
  const pins=(I.projects)||{};
  let html='';
  projs.forEach((p,i)=>{
    const pc=p.cost/DATA.totalCost*100;
    const ins=pins[p.project];
    // tools mini
    const tmax=Math.max(...p.tools.map(t=>t.result_tokens),1);
    const toolsHtml=p.tools.filter(t=>t.result_tokens>0||t.calls>0).slice(0,6).map(t=>`
      <div class="toolrow"><span class="tn">${esc(t.name)}</span><span class="tt"><i style="width:${(t.result_tokens/tmax*100).toFixed(1)}%"></i></span>
      <span class="tv">${fmtTok(t.result_tokens)}·${fmtInt(t.calls)}c</span></div>`).join('') || '<span class="no-insight">no tool output recorded</span>';
    // flags
    const flagsHtml=(p.flags||[]).map(f=>`<div class="flag"><span class="sv ${f.sev}">${f.sev}</span><span>${esc(f.detail)}</span></div>`).join('')||'<span class="no-insight">no efficiency flags raised</span>';
    // metrics
    const M=[['Cache hit',(p.cache_hit_ratio*100).toFixed(0)+'%'],['Ctx / call',fmtTok(Math.round(p.ctx_per_call))],
      ['Calls / sess',p.calls_per_session.toFixed(0)],['$ / session',fmtUSD(p.cost_per_session)],
      ['Output share',(p.output_share*100).toFixed(0)+'%'],['Sessions',p.sessions]];
    const metricsHtml=M.map(([k,v])=>`<div class="metric"><div class="mk">${k}</div><div class="mv">${v}</div></div>`).join('');
    // analyst
    const summaryHtml=ins?`<div class="analyst-summary">${esc(ins.summary)}</div>`:'';
    const recsHtml=ins&&ins.recommendations?`<div class="subh">Recommendations</div><ul class="recs">${ins.recommendations.map(r=>`<li>${esc(r)}</li>`).join('')}</ul>`:(ins?'':'<span class="no-insight">No analyst commentary for this project.</span>');
    html+=`<details class="dive"${i===0?' open':''}>
      <summary>
        <span class="rank">${String(i+1).padStart(2,'0')}</span>
        <span class="dname">${esc(p.project)} <span class="chev">▸</span></span>
        <span class="dshare"><i style="width:${(p.cost/maxCost*100).toFixed(1)}%"></i></span>
        <span class="dpc">${pc.toFixed(1)}%</span>
        <span class="dcost">${fmtUSD(p.cost)}</span>
      </summary>
      <div class="body">
        <div class="metrics">${metricsHtml}</div>
        ${summaryHtml}
        <div class="col2">
          <div><div class="subh">Where context came from</div>${toolsHtml}</div>
          <div><div class="subh">Efficiency flags (computed)</div>${flagsHtml}</div>
        </div>
        ${recsHtml}
      </div></details>`;
  });
  document.getElementById('dives').innerHTML=html;
})();

// model table
(function(){
  document.querySelector('#model-table tbody').innerHTML=DATA.byModel.map(m=>`<tr>
    <td class="l" style="font-weight:500">${labelOf(m.model)}</td>
    <td class="mono">${fmtTok(m.inp)}</td><td class="mono">${fmtTok(m.cr)}</td><td class="mono">${fmtTok(m.cw)}</td>
    <td class="mono">${fmtTok(m.out)}</td><td class="mono">${fmtInt(m.rows)}</td><td class="cost-cell">${fmtUSD(m.cost)}</td></tr>`).join('');
})();

// method
(function(){
  const prov=DATA.pricingProvenance||{};
  const provDate=prov.fetched_at?prov.fetched_at.slice(0,10):(prov.snapshot_date||'');
  const provText={network:`fetched live from <a href="${esc(prov.url||'')}">the Anthropic pricing page</a>`,
                  cache:`reused a cached snapshot of the Anthropic pricing page`,
                  bundled:`an in-code dated fallback snapshot (offline)`}[prov.source]||prov.source;
  const unpriced=DATA.unpricedModels||{};
  const unpricedKeys=Object.keys(unpriced);
  const items=[
    `<b>Source.</b> ${fmtInt(DATA.filesScanned)} Claude Code transcript files in the local transcript store, including subagent (Task-tool) transcripts. No project source folders are opened; nothing is uploaded.`,
    `<b>Window.</b> Rolling ${DATA.windowDays*24} hours: ${DATA.windowLabel}.`,
    `<b>De-duplication.</b> Each log line counted once by uuid (drops replayed/forked history); cost double-checked per unique message id + request id, skipping ${fmtInt(DATA.dupes)} duplicate billed lines. ${fmtInt(DATA.rows)} genuine API calls priced.`,
    `<b>Pricing.</b> ${provText}${provDate?` (${provDate})`:''} — ${prov.models||Object.keys(DATA.pricing).length} models. Prices are not hardcoded per run; the only network call this tool makes is this public, unauthenticated pricing lookup.`,
    `<b>Caching is real, not assumed.</b> Sessions already ran with prompt caching on, so recorded cache-read/write tokens are exactly what the API would bill — no re-simulation.`,
    `<b>Cache split.</b> Writes priced per the recorded 1h / 5m ephemeral split. Reads at the cache-hit rate. All taken from the resolved price table below.`,
    `<b>Project names.</b> Derived from each session's recorded working directory (basename only) — not from any hardcoded path.`,
    `<b>Context attribution.</b> "Where context comes from" measures tool_result text fed back into the conversation (~chars ÷ 4 tokens); it shows what enters context, which then recurs as cached input on later turns.`,
    `<b>Not included.</b> Subscription seat fees, server-tool surcharges beyond web search (${fmtInt(DATA.webSearches)} searches), Batch-API discount (n/a to interactive use). Fast-mode rows: ${fmtInt(DATA.fastRows)}.`
      + (unpricedKeys.length?` <b style="color:var(--accent)">Unpriced models skipped:</b> ${esc(unpricedKeys.join(', '))}.`:''),
    `<b>Baseline.</b> Max 20× at ${fmtUSD0(DATA.baselineMonthly)}/month, pro-rated to ${fmtUSD(DATA.baselineWeek)} for ${DATA.windowDays} days.`,
    `<b>Analyst layer.</b> Efficiency flags are computed by the analyser; per-project summaries and recommendations are Claude-authored commentary on those numbers (insights.json).`,
  ];
  document.getElementById('method-list').innerHTML=items.map(i=>`<li>${i}</li>`).join('');
  // price grid: only models actually used this window, priced from the resolved table (per MTok)
  const used=DATA.byModel.map(m=>m.model).filter(k=>DATA.pricing[k]);
  document.querySelector('#price-grid tbody').innerHTML=used.map(k=>{const p=DATA.pricing[k];
    const c=v=>'$'+Number(v).toFixed(2);
    return `<tr><td class="l">${labelOf(k)}</td><td>${c(p.inp)}</td><td>${c(p.read)}</td><td>${c(p.w5m)}</td><td>${c(p.w1h)}</td><td>${c(p.out)}</td></tr>`;}).join('');
})();
</script>
</body>
</html>"""

html = HTML.replace("__DATA__", DATA_JS)
os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
with open(args.out, "w", encoding="utf-8") as f:
    f.write(html)
print(f"wrote {args.out} ({len(html):,} bytes)")
print(f"total ${payload['totalCost']:,.2f} | baseline/wk ${baseline_week:,.2f} | x{multiplier:.1f} | projects {len(d['by_project'])}")
