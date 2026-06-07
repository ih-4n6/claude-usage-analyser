#!/usr/bin/env python3
"""claude-usage-analyser - extraction engine.

Walks every *.jsonl transcript under the local Claude Code projects directory
(default ~/.claude/projects, override with --projects-dir), restricts to a
rolling window, de-duplicates replayed/forked history, and prices the ACTUAL
recorded tokens at first-party Claude API rates (caching was already active, so
cache reads/writes are billed as-is). Emits a single data.json.

It reads ONLY the local transcript store. It never opens your actual project
source folders, and it sends nothing anywhere except an optional GET to the
public Anthropic pricing page (see PRICING_URL) to fetch current rates.

Pricing is resolved deterministically:
    network  -> parse the live pricing page, cache the snapshot
    cache    -> reuse the last cached snapshot (pricing_cache.json)
    bundled  -> a dated in-code fallback (last resort, offline)
The chosen source + date is recorded in data.json and shown in the report.

Usage:
    python analyze.py [--days N] [--projects-dir PATH] [--out data.json]
                      [--pricing auto|network|cache|bundled] [--offline]
"""
import json, os, glob, datetime, collections, re, argparse, sys, urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# --------------------------------------------------------------- pricing source
# The only external host this tool ever contacts. Public, unauthenticated.
PRICING_URL = "https://platform.claude.com/docs/en/about-claude/pricing.md"

# Cache write/read multipliers relative to base input (per the pricing page).
# Used only to derive cache rates for fast-mode rows; standard rows read their
# explicit per-column prices straight from the table.
CACHE_MULT = dict(w1h=2.0, w5m=1.25, read=0.1)

# Last-resort offline fallback. Dated so staleness is obvious. NOT authoritative
# - prefer network/cache. Per million tokens, USD.
BUNDLED_PRICING_DATE = "2026-06-07"
BUNDLED_PRICING_MTOK = {
    # key: [input, 5m_write, 1h_write, cache_read, output]
    "opus-4-8":   [5, 6.25, 10, 0.50, 25],
    "opus-4-7":   [5, 6.25, 10, 0.50, 25],
    "opus-4-6":   [5, 6.25, 10, 0.50, 25],
    "opus-4-5":   [5, 6.25, 10, 0.50, 25],
    "sonnet-4-6": [3, 3.75, 6, 0.30, 15],
    "sonnet-4-5": [3, 3.75, 6, 0.30, 15],
    "haiku-4-5":  [1, 1.25, 2, 0.10, 5],
}
BUNDLED_FAST_MTOK = {"opus-4-8": [10, 50], "opus-4-7": [30, 150], "opus-4-6": [30, 150]}

WEB_SEARCH_COST = 0.01   # $10 / 1000 searches
CHARS_PER_TOKEN = 4
CORE_TOOLS = {"Bash","Read","Edit","Write","Grep","Glob","Task","TodoWrite",
              "WebFetch","WebSearch","NotebookEdit","MultiEdit","Skill","PowerShell"}

# --------------------------------------------------------------- helpers
def normalize_model(name):
    """'Claude Opus 4.8' or 'claude-opus-4-8-20251001' -> 'opus-4-8'."""
    s = name.strip().lower()
    s = re.sub(r"-\d{8}$", "", s)            # drop a trailing -YYYYMMDD date
    s = s.replace("claude", " ")
    s = re.sub(r"[.\s_]+", "-", s)           # dots/spaces/underscores -> dash
    s = re.sub(r"-+", "-", s).strip("-")
    return s

def parse_pricing_md(text):
    """Parse the model-pricing table (5 price columns) and the fast-mode table
    (2 price columns) from the pricing markdown. Returns (standard, fast) where
    each maps normalized-model-key -> per-MTok list."""
    price_re = re.compile(r"\$\s*([\d]+(?:\.\d+)?)\s*/\s*MTok", re.I)
    standard, fast = {}, {}
    heading = ""
    for line in text.splitlines():
        st = line.strip()
        if st.startswith("#"):
            heading = st.lower()
            continue
        if not st.startswith("|"):
            continue
        cells = [c.strip() for c in st.strip("|").split("|")]
        if not cells:
            continue
        prices = price_re.findall(st)
        name_cell = re.split(r"[\(\[]", cells[0])[0].strip()   # text before any (deprecated)/[link]
        if not name_cell.lower().startswith("claude"):
            continue
        key = normalize_model(name_cell)
        if len(prices) == 5:                                   # standard model table
            standard[key] = [float(x) for x in prices]
        elif len(prices) == 2 and "fast" in heading:           # fast-mode table
            fast[key] = [float(x) for x in prices]
    return standard, fast

def per_token(mtok_list):
    inp, w5m, w1h, read, out = mtok_list
    return dict(inp=inp/1e6, w5m=w5m/1e6, w1h=w1h/1e6, read=read/1e6, out=out/1e6)

def resolve_pricing(mode, cache_path, offline):
    """Returns (pricing, fast, provenance). pricing: key->per-token dict."""
    def from_mtok(std_mtok, fast_mtok, source, extra):
        pricing = {k: per_token(v) for k, v in std_mtok.items()}
        fastp = {}
        for k, (i, o) in (fast_mtok or {}).items():
            fastp[k] = dict(inp=i/1e6, out=o/1e6,
                            w1h=CACHE_MULT["w1h"]*i/1e6, w5m=CACHE_MULT["w5m"]*i/1e6,
                            read=CACHE_MULT["read"]*i/1e6)
        prov = dict(source=source, **extra)
        return pricing, fastp, prov

    want_net = (mode in ("auto", "network")) and not offline
    if want_net:
        try:
            req = urllib.request.Request(PRICING_URL, headers={
                "User-Agent": "claude-usage-analyser (+https://github.com/)"})
            with urllib.request.urlopen(req, timeout=25) as r:
                body = r.read().decode("utf-8", "replace")
            std, fast = parse_pricing_md(body)
            if not std:
                raise ValueError("no standard pricing table found")
            fetched = datetime.datetime.now(datetime.timezone.utc).isoformat()
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(dict(fetched_at=fetched, url=PRICING_URL,
                                   standard_mtok=std, fast_mtok=fast), f, indent=2)
            except Exception:
                pass
            return from_mtok(std, fast, "network",
                             dict(url=PRICING_URL, fetched_at=fetched, models=len(std)))
        except Exception as e:
            if mode == "network":
                raise SystemExit(f"pricing fetch failed and --pricing network was forced: {e}")
            print(f"[pricing] network fetch failed ({e}); falling back", file=sys.stderr)

    if mode in ("auto", "cache") and os.path.exists(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as f:
                c = json.load(f)
            return from_mtok(c["standard_mtok"], c.get("fast_mtok"), "cache",
                             dict(url=c.get("url"), fetched_at=c.get("fetched_at"),
                                  models=len(c["standard_mtok"])))
        except Exception as e:
            print(f"[pricing] cache unusable ({e}); using bundled", file=sys.stderr)

    return from_mtok(BUNDLED_PRICING_MTOK, BUNDLED_FAST_MTOK, "bundled",
                     dict(snapshot_date=BUNDLED_PRICING_DATE, models=len(BUNDLED_PRICING_MTOK)))

def tool_bucket(name):
    if not name: return "other"
    if name in CORE_TOOLS: return name
    if name.startswith("mcp__"):
        parts = name.split("__")
        return "mcp:" + (parts[1] if len(parts) > 1 else "?")
    return name if name[:1].isupper() else "other"

def result_text_len(content):
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        tot = 0
        for b in content:
            if isinstance(b, dict):
                if b.get("type") == "text": tot += len(b.get("text") or "")
                elif b.get("type") == "image": tot += 4000
            elif isinstance(b, str): tot += len(b)
        return tot
    return 0

def derive_project(objs, rel):
    """Project label = basename of the session's launch directory, taken from the
    transcript's own `cwd` field (shortest cwd = the root). Falls back to the
    encoded directory name. No host paths are hardcoded; nothing is assumed."""
    cwds = set()
    for o in objs:
        c = o.get("cwd")
        if isinstance(c, str) and c:
            cwds.add(c)
    if cwds:
        root = min(cwds, key=len)                 # shortest = launch dir
        base = re.split(r"[\\/]", root.rstrip("\\/"))[-1]
        if base:
            return base
    return rel.replace("\\", "/").split("/")[0]    # generic fallback

def new_proj():
    return dict(cost=0.0, out_cost=0.0, inp=0, out=0, cw=0, cr=0, rows=0,
                sessions=set(), user_turns=0, compactions=0,
                tools=collections.defaultdict(lambda: dict(calls=0, result_tokens=0)),
                tool_result_tokens=0)

# --------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Price local Claude Code usage at API rates.")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--projects-dir",
                    default=os.path.join(os.path.expanduser("~"), ".claude", "projects"),
                    help="Local Claude Code transcript store (default ~/.claude/projects).")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports", "data.json"))
    ap.add_argument("--baseline-monthly", type=float, default=200.0)
    ap.add_argument("--pricing", choices=["auto","network","cache","bundled"], default="auto")
    ap.add_argument("--pricing-cache",
                    default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "pricing_cache.json"))
    ap.add_argument("--offline", action="store_true", help="Never hit the network.")
    args = ap.parse_args()

    projects_dir = os.path.expanduser(args.projects_dir)
    if not os.path.isdir(projects_dir):
        raise SystemExit(f"projects dir not found: {projects_dir}\n"
                         f"Point --projects-dir at your Claude Code transcript store.")

    PRICING, FAST, prov = resolve_pricing(
        "bundled" if args.offline and args.pricing == "auto" else args.pricing,
        args.pricing_cache, args.offline)
    print(f"[pricing] source={prov['source']} models={prov.get('models')} "
          f"{prov.get('fetched_at') or prov.get('snapshot_date') or ''}")

    NOW = datetime.datetime.now(datetime.timezone.utc)
    CUTOFF = NOW - datetime.timedelta(days=args.days)
    files = glob.glob(os.path.join(projects_dir, "**", "*.jsonl"), recursive=True)

    seen_uuid, seen_costkey = set(), set()
    rows = dupes = synthetic = unsplit_cache_tokens = fast_rows = web_searches = 0
    unpriced = collections.defaultdict(int)

    by_project = collections.defaultdict(new_proj)
    by_day   = collections.defaultdict(lambda: dict(cost=0.0, inp=0, out=0, cw=0, cr=0, rows=0))
    by_model = collections.defaultdict(lambda: dict(cost=0.0, inp=0, out=0, cw=0, cr=0, rows=0))
    by_proj_model = collections.defaultdict(lambda: collections.defaultdict(float))
    daily_project = collections.defaultdict(lambda: collections.defaultdict(float))
    cost_components = dict(fresh_input=0.0, cache_write=0.0, cache_read=0.0, output=0.0, web_search=0.0)
    tok_totals = dict(fresh_input=0, cache_write=0, cache_read=0, output=0)
    global_tools = collections.defaultdict(lambda: dict(calls=0, result_tokens=0))

    for fp in files:
        rel = os.path.relpath(fp, projects_dir)
        try:
            with open(fp, encoding="utf-8") as fh:
                objs = []
                for line in fh:
                    if '"timestamp"' not in line:
                        continue
                    try: objs.append(json.loads(line))
                    except Exception: pass
        except Exception:
            continue
        if not objs:
            continue
        proj = derive_project(objs, rel)
        tool_names = {}

        for o in objs:
            ts = o.get("timestamp")
            if not ts: continue
            try: t = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception: continue
            if t < CUTOFF or t > NOW + datetime.timedelta(hours=1): continue

            uid = o.get("uuid")
            if uid:
                if uid in seen_uuid: continue
                seen_uuid.add(uid)

            if o.get("isCompactSummary") or o.get("type") == "summary":
                by_project[proj]["compactions"] += 1

            msg = o.get("message")
            if not isinstance(msg, dict): continue
            content = msg.get("content")

            if msg.get("role") == "assistant" and isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        tb = tool_bucket(b.get("name"))
                        by_project[proj]["tools"][tb]["calls"] += 1
                        global_tools[tb]["calls"] += 1
                        if b.get("id"): tool_names[b["id"]] = tb
            if msg.get("role") == "user":
                if isinstance(content, list):
                    had_tr = False
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "tool_result":
                            had_tr = True
                            tb = tool_names.get(b.get("tool_use_id"), "other")
                            toks = result_text_len(b.get("content")) // CHARS_PER_TOKEN
                            by_project[proj]["tools"][tb]["result_tokens"] += toks
                            by_project[proj]["tool_result_tokens"] += toks
                            global_tools[tb]["result_tokens"] += toks
                    if not had_tr: by_project[proj]["user_turns"] += 1
                elif isinstance(content, str):
                    by_project[proj]["user_turns"] += 1

            u = msg.get("usage")
            if not isinstance(u, dict): continue
            model_id = msg.get("model")
            if not model_id or not str(model_id).lower().startswith("claude"):
                synthetic += 1; continue
            mk = normalize_model(model_id)
            speed = (u.get("speed") or u.get("service_tier") or "standard")
            if speed == "fast" and mk in FAST:
                p = FAST[mk]; fast_rows += 1
            else:
                p = PRICING.get(mk)
            if p is None:
                unpriced[model_id] += 1; continue

            ck = f"{msg.get('id')}:{o.get('requestId')}"
            if msg.get("id") and o.get("requestId"):
                if ck in seen_costkey: dupes += 1; continue
                seen_costkey.add(ck)

            inp = int(u.get("input_tokens") or 0)
            out = int(u.get("output_tokens") or 0)
            cread = int(u.get("cache_read_input_tokens") or 0)
            cc = u.get("cache_creation") or {}
            w1h = int(cc.get("ephemeral_1h_input_tokens") or 0)
            w5m = int(cc.get("ephemeral_5m_input_tokens") or 0)
            cc_total = int(u.get("cache_creation_input_tokens") or 0)
            if cc_total and (w1h + w5m) == 0:
                w1h = cc_total; unsplit_cache_tokens += cc_total
            cw = w1h + w5m

            c_fresh = inp * p["inp"]; c_cw = w1h * p["w1h"] + w5m * p["w5m"]
            c_cr = cread * p["read"]; c_out = out * p["out"]
            stu = u.get("server_tool_use") or {}
            wsr = int(stu.get("web_search_requests") or 0)
            c_ws = wsr * WEB_SEARCH_COST; web_searches += wsr
            cost = c_fresh + c_cw + c_cr + c_out + c_ws

            cost_components["fresh_input"] += c_fresh
            cost_components["cache_write"] += c_cw
            cost_components["cache_read"]  += c_cr
            cost_components["output"]      += c_out
            cost_components["web_search"]  += c_ws
            tok_totals["fresh_input"] += inp; tok_totals["cache_write"] += cw
            tok_totals["cache_read"]  += cread; tok_totals["output"]    += out

            day = t.date().isoformat(); sid = o.get("sessionId") or ""
            pa = by_project[proj]
            pa["cost"] += cost; pa["out_cost"] += c_out; pa["inp"] += inp; pa["out"] += out
            pa["cw"] += cw; pa["cr"] += cread; pa["rows"] += 1; pa["sessions"].add(sid)
            da = by_day[day]
            da["cost"] += cost; da["inp"] += inp; da["out"] += out
            da["cw"] += cw; da["cr"] += cread; da["rows"] += 1
            ma = by_model[mk]
            ma["cost"] += cost; ma["inp"] += inp; ma["out"] += out
            ma["cw"] += cw; ma["cr"] += cread; ma["rows"] += 1
            by_proj_model[proj][mk] += cost
            daily_project[day][proj] += cost
            rows += 1

    total_cost = sum(cost_components.values())

    def derive(proj, a):
        rows_ = a["rows"] or 1
        cr, cw, inp, out = a["cr"], a["cw"], a["inp"], a["out"]
        total_in = cr + cw + inp
        cache_hit = cr / total_in if total_in else 0.0
        ctx_per_call = total_in / rows_
        output_share = (a["out_cost"] / a["cost"]) if a["cost"] else 0.0
        sessions = len([s for s in a["sessions"] if s]) or 1
        tools = sorted(
            [dict(name=n, calls=td["calls"], result_tokens=td["result_tokens"]) for n, td in a["tools"].items()],
            key=lambda x: x["result_tokens"], reverse=True)
        trt = a["tool_result_tokens"] or 1
        calls_per_session = rows_ / sessions
        flags = []
        if ctx_per_call >= 120_000:
            flags.append(dict(code="large-context", sev="high",
                detail=f"Average {ctx_per_call/1000:.0f}K tokens of context per API call - long sessions re-reading a big working set. Cache reads are the single largest cost line here."))
        elif ctx_per_call >= 60_000:
            flags.append(dict(code="large-context", sev="med",
                detail=f"Average {ctx_per_call/1000:.0f}K tokens of context per API call."))
        if cache_hit < 0.80 and total_in > 1_000_000:
            flags.append(dict(code="cache-churn", sev="med",
                detail=f"Cache reuse {cache_hit*100:.0f}%: {cw/1e6:.1f}M tokens (re)written vs {cr/1e6:.1f}M read. Frequent large context changes keep invalidating the cache, and each 1h write costs 2x base input."))
        if output_share >= 0.30 and a["cost"] > 5:
            flags.append(dict(code="high-output", sev="med",
                detail=f"Output tokens are ~{output_share*100:.0f}% of this project's cost ({out/1e6:.1f}M generated). Verbose responses or large multi-file edits/rewrites."))
        if tools and tools[0]["result_tokens"] / trt > 0.45 and tools[0]["result_tokens"] > 200_000:
            top = tools[0]
            flags.append(dict(code="tool-context", sev="med",
                detail=f"{top['name']} fed ~{top['result_tokens']/1e6:.1f}M tokens ({top['result_tokens']/trt*100:.0f}% of tool output) into context across {top['calls']} calls. Large tool outputs become cached input on every subsequent turn."))
        if calls_per_session >= 250:
            flags.append(dict(code="long-sessions", sev="low",
                detail=f"~{calls_per_session:.0f} API calls per session. Each turn re-reads the whole conversation; clearing/compacting sooner caps the cache-read tail."))
        return dict(project=proj, cost=a["cost"], inp=inp, out=out, cw=cw, cr=cr, rows=a["rows"],
            sessions=sessions, user_turns=a["user_turns"], compactions=a["compactions"],
            cache_hit_ratio=round(cache_hit,4), reads_per_call=round(cr/rows_,1),
            ctx_per_call=round(ctx_per_call,1), output_share=round(output_share,4),
            cost_per_session=round(a["cost"]/sessions,2), calls_per_session=round(calls_per_session,1),
            tool_result_tokens=a["tool_result_tokens"], tools=tools[:8], flags=flags)

    proj_list = sorted([derive(p, a) for p, a in by_project.items() if a["rows"] > 0],
                       key=lambda x: x["cost"], reverse=True)

    def dump_simple(agg, keyname):
        out = [dict([(keyname, k)] + list(a.items())) for k, a in agg.items()]
        out.sort(key=lambda x: x["cost"], reverse=True)
        return out

    pricing_mtok = {k: {kk: round(vv*1e6, 4) for kk, vv in v.items()} for k, v in PRICING.items()}
    data = dict(
        generated_at=NOW.isoformat(), window_start=CUTOFF.isoformat(), window_end=NOW.isoformat(),
        window_days=args.days, total_cost=total_cost,
        rows=rows, dupes=dupes, synthetic=synthetic, files_scanned=len(files),
        fast_rows=fast_rows, unsplit_cache_tokens=unsplit_cache_tokens, web_searches=web_searches,
        unpriced_models=dict(unpriced),
        cost_components=cost_components, tok_totals=tok_totals,
        by_project=proj_list,
        by_day=dump_simple(by_day, "day"), by_model=dump_simple(by_model, "model"),
        by_proj_model={p: dict(m) for p, m in by_proj_model.items()},
        daily_project={d: dict(p) for d, p in daily_project.items()},
        global_tools=sorted([dict(name=n, **td) for n, td in global_tools.items()],
                            key=lambda x: x["result_tokens"], reverse=True),
        pricing=pricing_mtok, pricing_provenance=prov,
        available_models=sorted(PRICING.keys()),
        baseline_monthly=args.baseline_monthly,
    )
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    bw = args.baseline_monthly * args.days / 30.44
    print(f"window {CUTOFF:%Y-%m-%d %H:%M} -> {NOW:%Y-%m-%d %H:%M} UTC ({args.days}d)")
    print(f"files {len(files)}  calls {rows}  dupes {dupes}  synthetic {synthetic}"
          + (f"  UNPRICED {dict(unpriced)}" if unpriced else ""))
    print(f"TOTAL ${total_cost:,.2f}   baseline/{args.days}d ${bw:,.2f}   x{total_cost/bw:.1f}")
    print("per-project (cost / cacheHit / ctxPerCall / topTool / flags):")
    for p in proj_list[:12]:
        tt = p["tools"][0]["name"] if p["tools"] else "-"
        print(f"  {p['project'][:30]:30s} ${p['cost']:8,.2f}  hit={p['cache_hit_ratio']*100:3.0f}%  "
              f"ctx/call={p['ctx_per_call']/1000:5.0f}K  top={tt:10s}  {[f['code'] for f in p['flags']]}")
    print(f"wrote {args.out}")

if __name__ == "__main__":
    main()
