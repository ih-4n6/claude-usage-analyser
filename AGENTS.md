# Running claude-usage-analyser as a Claude session

This tool is designed to be driven by a Claude Code session. The scripts are
deterministic and repeatable; **your job is the value-add layer** — turning the
extracted numbers into honest, specific insight. Don't let the scripts do your
thinking, and don't let your thinking drift from the numbers.

## Scope & permission

- The analyser reads **only the local transcript store** (default
  `~/.claude/projects`). That is all it needs for the full report.
- It does **not** read the user's actual project source folders, and you should
  not either, by default. If looking at real code would genuinely sharpen a
  recommendation, **ask the user's permission first** and name the path — unless
  you're running under an auto-approve mode the user has already set.
- The only network egress is the pricing fetch (a public Anthropic URL). Nothing
  from the transcripts is sent anywhere.

## The loop

1. **Extract.**
   ```bash
   python analyze.py            # --days N to change the window (default 7)
                                # --offline / --pricing cache|bundled if no network
   ```
   Writes `reports/data.json` and prints a summary, including the **pricing source**
   (network / cache / bundled) and any **unpriced models** encountered. If pricing
   came from `bundled`, say so in your findings — the rates may be stale.

2. **Read `reports/data.json` properly** before writing a word:
   - `pricing_provenance` — where rates came from and when.
   - `cost_components` — which line dominates (usually cache reads).
   - per-project `cache_hit_ratio`, `ctx_per_call`, `calls_per_session`,
     `output_share`, `compactions`, and `tools` (what fills context).
   - `global_tools` — the biggest context-fillers across everything.
   - the `flags` already raised per project.

3. **Author `reports/insights.json`.** Copy the schema:
   ```bash
   cp insights.template.json reports/insights.json
   ```
   Then fill it. Rules of the road:
   - Use the **exact project names** as they appear in `reports/data.json` (they're
     basenames of session working directories).
   - **Quote the real numbers** ($, %, token counts, calls). Specific beats vague.
   - **Diagnose, don't assume.** High cache-read cost with a 95%+ hit ratio is
     *not* a caching problem — it's a context-size / session-length problem. Read
     the metrics before prescribing.
   - **Rank recommendations** by likely saving; tie each to a cost line.
   - Cover the top projects by cost; the tail can be skipped (the report still
     shows their flags + metrics).
   - Don't invent savings percentages you can't support.
   - `reports/` is gitignored (it contains the user's project names and outputs).
     The committed artifact is the template only.

4. **Build & verify.**
   ```bash
   python build_report.py
   ```
   Open `reports/index.html` (or serve + screenshot via the preview tooling). Confirm:
   totals reconcile, pricing provenance shows, findings render, heatmap populated,
   deep-dives show your summaries + recommendations.

## Boundaries

- `analyze.py` / `build_report.py` are deterministic — change them only to add a
  metric or fix extraction, never to bake in interpretation.
- Pricing comes from the live table (`PRICING_URL`) with cache + dated bundled
  fallbacks. If models or rates change upstream, the tool picks them up on the
  next network run; the bundled snapshot in `analyze.py` is only a last resort —
  update its date if you refresh it.
- Keep the report's clarity and density. The scripting exists for repeatability,
  **not** to flatten the presentation or the insight.
- Everything stays local; no transcript content is sent anywhere.
