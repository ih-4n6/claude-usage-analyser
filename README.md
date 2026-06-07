# claude-usage-analyser

Work out what your Claude Code usage **would have cost on the metered API** (with
prompt caching, exactly as it actually ran), break it down by project, day, model
and tool, and surface **where the token spend went, with concrete efficiency
recommendations** — rendered into a single self-contained HTML report.

It reads only your **local Claude Code transcript store** and prices the **actual
recorded tokens** at first-party API rates. Because those sessions already ran
with caching on, the recorded cache reads/writes are precisely what the API would
have billed — no hypotheticals.

## What it touches (privacy)

- **Reads:** transcript JSON-L under your local Claude projects directory (default
  `~/.claude/projects`, override with `--projects-dir`), *including* subagent
  transcripts. That store is all it needs.
- **Does NOT read your project source.** It never opens the actual code/workspace
  folders your sessions ran in. Project names are taken from each session's
  recorded working directory (basename only) — nothing is hardcoded.
- **Network (the scripts):** exactly one optional, unauthenticated GET, to fetch
  current prices:
  - `https://platform.claude.com/docs/en/about-claude/pricing.md`

  That Anthropic/Claude domain is the **only** site the analyser scripts contact.
  Run with `--offline` and they make no network calls at all (cached or bundled
  price snapshot). No transcript content ever leaves your machine.
- **Network (the report, when opened in a browser):** `index.html` requests web
  fonts from Google Fonts (`fonts.googleapis.com`, `fonts.gstatic.com`). This is
  cosmetic only — the layout falls back to system fonts offline. No data is sent;
  it's a standard `<link>` font request. Remove the `<link>` tags in
  `build_report.py` if you want a zero-external-call report.

## Design intent — two halves

| Half | Owner | Where |
| --- | --- | --- |
| **Deterministic extraction** — parsing, de-dup, pricing, aggregates, tool/context attribution, efficiency *flags* | scripts (repeatable) | `analyze.py` |
| **Interpretation** — the narrative, cross-cutting findings, per-project recommendations | a **Claude session**, grounded in the numbers | `insights.json` |

The build merges both and labels which is which, so computed facts and analyst
commentary are never confused. Run it **inside a Claude session** (below): the
scripts do the heavy lifting; Claude adds the judgement a script can't.

## Run it in a Claude session (recommended)

Open a Claude Code session in this folder and paste:

> Run the claude-usage-analyser end to end for the last 7 days. Follow AGENTS.md:
> run `analyze.py`, read `data.json`, copy `insights.template.json` to
> `insights.json` and fill it grounded in the real numbers, then run
> `build_report.py`. Open the report and confirm the totals reconcile. If you need
> to look at any actual project source to sharpen a recommendation, ask me first.

Claude will execute the scripts, write the analyst layer, and verify the output.
The "ask me first" line matters: the tool itself never needs your project source,
so any access beyond the transcript store should be an explicit, approved step.

## Run it by hand

All generated/personal output lands in `reports/` (gitignored).

```bash
# 1. extract — prices the last 7 days -> reports/data.json (fetches live pricing)
python analyze.py                       # --days N  --projects-dir PATH  --baseline-monthly 200
                                        # --pricing auto|network|cache|bundled  --offline

# 2. analyst layer — copy the template, then fill reports/insights.json (ideally via Claude)
cp insights.template.json reports/insights.json

# 3. build the report -> reports/index.html (data inlined; opens with file://)
python build_report.py
```

Pure Python standard library — no third-party dependencies. Refresh numbers
against existing commentary any time: `python analyze.py && python build_report.py`.

## Deterministic, current pricing

Rates are **not hardcoded per run**. `analyze.py` resolves them in this order and
records the source + date in `data.json` (shown in the report appendix):

1. **network** — parse the live Anthropic pricing page, then cache the snapshot.
2. **cache** — reuse the last fetched snapshot (`pricing_cache.json`).
3. **bundled** — a dated in-code fallback, last resort / offline.

The model list and every per-model rate (input, 5-minute write, 1-hour write,
cache read, output) come from that table. Models found in your transcripts that
aren't in the table are reported as *unpriced* and excluded (never silently $0).

## What the report contains

- **Headline** — period API-equivalent cost vs a subscription baseline.
- **The efficiency picture** — cross-cutting findings, each tagged with the cost line it targets.
- **Cost composition** — fresh input / cache write / cache read / output / web search.
- **Cost by day** and a **per-day-per-project heatmap** (the full drill-down matrix).
- **Where context comes from** — tool output (Read, Bash, …) fed back into context.
- **Project deep-dives** — per project: cache economics, context-filling tools, computed efficiency flags, and recommendations.
- **By model** and a **method & pricing** appendix (with pricing provenance).

## How cost is computed

- Walks every `*.jsonl` under the transcript store, **including subagent transcripts**.
- De-duplicates by log-line `uuid` (drops replayed/forked history); cost cross-checked per unique `message.id` + `requestId`.
- Prices each call's recorded tokens: input, output, cache reads, and cache writes split by the recorded 1-hour / 5-minute ephemeral breakdown — all at the resolved table's rates.

## Files

```
analyze.py               extraction engine     -> reports/data.json   (generated)
build_report.py          report builder        -> reports/index.html  (generated)
insights.template.json   analyst-layer schema  (committed)
AGENTS.md                how a Claude session runs this end to end
pricing_cache.json       fetched price snapshot (gitignored)
reports/                 all your output (gitignored):
  data.json                generated extraction
  index.html               the report
  insights.json            your filled analyst layer (your project names)
```

Nothing project-specific or generated is committed — only the scripts, the
template, and docs. Everything in `reports/` (plus `pricing_cache.json`) is
gitignored. See `.gitignore`.
