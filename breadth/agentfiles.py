"""Agent inputs for the Decision Cards: what the Catalyst and Macro agents read, and how their answers get saved.

Claude scheduled tasks can't write repo files directly, but they can dispatch workflows (same as breadth.story).

    python -m breadth.agentfiles worklist                      # JSON: card date + the tickers to research
    python -m breadth.agentfiles schema catalysts|macro_brief   # the exact JSON the agent must write
    python -m breadth.agentfiles publish --kind K --file F --push   # validate, then dispatch .github/workflows/agent.yml
    python -m breadth.agentfiles save --kind K --b64 B64          # (inside agent.yml) validate + write docs/agent/K.json

Validation is strict on shape and lenient on content: unknown tickers are dropped, strings are trimmed, every claim
needs a source URL. A file that fails validation is never written, so the page keeps working with "not checked".
"""
import argparse
import base64
import json
import re
import subprocess
import sys
from datetime import datetime, timezone

from . import config

REPO = "az123-stack/breadth-monitor"
KINDS = ("catalysts", "macro_brief", "review", "plan", "reclass")
WEEKLY = ("review", "plan", "reclass")      # weekly agents: not tied to a card date / entry cutoff
FULL_RESEARCH = 15        # first N carded tickers get full catalyst research; the rest get an earnings-date check only
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL = re.compile(r"^https?://\S+$")

SCHEMA = {
    "catalysts": {
        "for_date": "YYYY-MM-DD — copy `for_date` from the worklist",
        "stocks": {"TICKER": {
            "why": "one or two plain sentences: what is actually driving the stock now (or 'no clear catalyst found')",
            "direction": "positive | negative | mixed | none — what the news means for a LONG swing trade over the next 1-2 weeks (a pending cash takeover = negative: the upside is capped)",
            "quality": "strong (fresh hard news: earnings beat/raise, FDA, contract, M&A) | real (genuine but older or softer) | weak (rumour, sympathy only) | none | unknown",
            "earnings_date": "YYYY-MM-DD of the NEXT earnings report if found, else null",
            "red_flags": ["short list: offering/dilution, downgrade, lawsuit, guidance cut, short report, insider selling... [] if none"],
            "depth": "full | earnings_only — copy from the worklist",
            "sources": ["https://... at least one URL you actually used"]}},
    },
    "plan": {
        "for_date": "YYYY-MM-DD — today's date",
        "summary": "2-4 plain sentences for Adam: what's new in the research and the single most valuable next step",
        "items": [{
            "title": "short name of the proposal",
            "cards": ["R-... ids of the finding cards it builds on"],
            "verdict": "build (ready: evidence passed) | test_first (promising, needs the test below) | watch (needs more data) "
                       "| duplicate (already covered by a layer: say which) | reject (evidence says no)",
            "where": "where it plugs in: which layer id / tab / card / setup / exit rule / sizing / new layer",
            "how": "2-4 sentences: what exactly would be built, in plain words",
            "test": "the test that would prove it (data, entry/exit, both halves, t >= 2) — or the evidence that already did",
            "kill": "the result that would make us drop it",
            "effort": "S | M | L",
            "priority": "1 = do first"}],
        "new_agents": [{"name": "...", "job": "what it does each run", "schedule": "when (ET)", "inputs": "what it reads",
                        "outputs": "what it writes (file / schema)", "cost": "rough runs x minutes / searches",
                        "why": "which layer or card needs it", "kill": "when to retire it"}],
        "retire": [{"target": "layer id or agent name", "why": "evidence"}],
        "registry_updates": [{"layer": "id", "to": "proposed status on the ladder", "why": "evidence"}],
        "card_updates": [{"card": "R-...", "integrated": "yes | partly | no | rejected", "why": "..."}],
    },
    "reclass": {
        "for_date": "YYYY-MM-DD — copy `for_date` from `python -m breadth.reclass worklist`",
        "summary": "2-4 plain sentences for Adam: how many tickers you checked and the moves that matter most",
        "checked": "number of worklist tickers you researched",
        "moves": [{
            "t": "TICKER (must be on the worklist)",
            "action": "add (unclassified → a sub-theme) | move (to a better sub-theme) | remove (dead / delisted / acquired) "
                      "| rename (ticker changed; put the new ticker in `to`) | keep (checked: current home is right)",
            "from": "current sub-theme exactly as in the worklist, or null",
            "to": "an existing sub-theme name exactly as listed (without the [group]), or 'NEW: Group / Sub-theme name'; "
                  "for rename the new ticker; null for remove / keep",
            "theme_add": "optional: an existing theme name (from `themes`) to also add the stock to, else null",
            "confidence": "high | medium | low",
            "why": "one or two plain sentences: what the company actually does and why it belongs there",
            "sources": ["https://... at least one URL you used (not needed for keep)"]}],
    },
    "review": {
        "for_date": "YYYY-MM-DD — the latest official date (worklist for_date)",
        "summary": "2-4 plain sentences for Adam: what the evidence says this week",
        "findings": ["one line each (max 300 characters): a layer and what its evidence shows (numbers from `python -m breadth.layers report`)"],
        "proposals": ["one line each (max 300 characters): a concrete change to consider, and the evidence; or 'no changes yet: not enough data'"],
        "sources": ["data/layer_evidence.json", "data/decision_log.csv"],
    },
    "macro_brief": {
        "for_date": "YYYY-MM-DD — copy `for_date` from the worklist",
        "headline": "one sentence: the macro story traders care about today",
        "risk": "low | medium | high (high = a scheduled or ongoing event that can move the whole market today or tomorrow)",
        "rates": "one sentence on yields / the Fed path", "fed": "Fed speakers or decisions this week, one sentence",
        "oil": "one sentence on oil and why", "geo": "one sentence on geopolitics/policy shocks, or 'nothing major'",
        "events": [{"date": "YYYY-MM-DD", "time": "8:30 AM ET", "name": "CPI", "impact": "high | medium"}],
        "sources": ["https://..."],
    },
}


def _data():
    h = (config.DOCS_DIR / "index.html").read_text()
    i = h.index("const DATA = ") + len("const DATA = ")
    return json.JSONDecoder().raw_decode(h[i:])[0]


def worklist():
    D = _data()
    dec = (D.get("themes") or {}).get("decision") or {}
    cards = dec.get("cards") or []
    T = D.get("themes") or {}
    # Oct 27 2026 (Adam): the headline picks are now Launch picks + Lined-up buys, so they get the full research first; then the
    # BUY / ready theme tickers; the old Decision-Card names (still logged quietly) only fill the rest.
    first = []
    for c in (T.get("launch") or {}).get("picks") or []:
        first.append({"t": c["t"], "role": "launch", "name": c.get("name"), "setup": "Launch pick", "price": c.get("close")})
    for r in (T.get("lifecycle") or {}).get("live") or []:
        first.append({"t": r["t"], "role": "lineup", "name": None, "setup": "Lined-up buys (" + str(r.get("g")) + ")", "price": r.get("c")})
    for g in (T.get("lifecycle") or {}).get("rows") or []:
        if g.get("buy") or g.get("ready"):
            for p in g.get("picks") or []:
                first.append({"t": p["t"], "role": "theme_buy", "name": None, "setup": "Theme BUY (" + str(g.get("g")) + ")", "price": p.get("c")})
    seen, merged = set(), []
    for c in first + [{"t": c["t"], "role": c["role"], "name": c.get("name"), "setup": c.get("setup_name") or c.get("setup"),
                       "price": c.get("price")} for c in cards]:
        if c["t"] in seen:
            continue
        seen.add(c["t"])
        merged.append(c)
    stocks = [dict(c, depth="full" if k < FULL_RESEARCH else "earnings_only") for k, c in enumerate(merged[:45])]
    from datetime import datetime, timezone
    from . import nyse
    fd = dec.get("date")
    today = datetime.now(nyse.ET).date()
    expected = nyse.prev_session(today)              # last completed session before today
    cutoff = nyse.entry_cutoff(fd) if fd else None
    return {"for_date": fd, "expected_date": expected.isoformat(), "fresh": fd == expected.isoformat(),
            "market_open_today": nyse.is_session(today),
            "entry_cutoff": cutoff.isoformat() if cutoff else None,
            "past_cutoff": bool(cutoff and datetime.now(timezone.utc) >= cutoff),
            "tickers": stocks,
            "note": "for_date is the last official close; research news up to now. Keep the order: picks first. "
                    "depth=full: full catalyst research; depth=earnings_only: find the next earnings date only "
                    "(why='earnings date check only', direction none, quality unknown). fresh=false means the overnight data is "
                    "late. past_cutoff=true means ideas for for_date have already been bought at the open: research for them "
                    "can no longer be logged, so publish refuses it."}


def _date_ok(v):
    try:
        from datetime import date as _d
        _d.fromisoformat(str(v))
        return bool(DATE.match(str(v)))
    except (TypeError, ValueError):
        return False


def _list(v):
    """A string becomes a one-item list (never one item per character); non-lists become []."""
    if isinstance(v, str):
        return [v]
    return v if isinstance(v, list) else []


def _s(v, n=400):
    """Clean one-line text: no < or >, single spaces, cut at a word boundary with "…" if longer than n."""
    if v is None:
        return None
    t = re.sub(r"\s+", " ", re.sub(r"[<>]", "", str(v))).strip()
    if len(t) <= n:
        return t
    cut = t[:n - 1]
    return (cut.rsplit(" ", 1)[0] if " " in cut[n // 2:] else cut).rstrip(" ,;:") + "…"


def _urls(v):
    return [u.strip() for u in _list(v) if isinstance(u, str) and URL.match(u.strip())][:6]


def validate(kind, js, allowed=None):
    """Return a clean dict or raise ValueError."""
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind}")
    if not isinstance(js, dict) or not _date_ok(js.get("for_date")):
        raise ValueError("for_date (YYYY-MM-DD, a real date) missing")
    out = {"for_date": js["for_date"], "written": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")}
    if kind == "catalysts":
        st = js.get("stocks")
        if not isinstance(st, dict) or not st:
            raise ValueError("stocks must be a non-empty object")
        clean = {}
        for t, c in st.items():
            t = str(t).upper().strip()
            if allowed is not None and t not in allowed:
                continue
            if not isinstance(c, dict):
                continue
            src = _urls(c.get("sources"))
            if not src:
                continue                                   # no source, no claim
            d = str(c.get("direction", "")).lower()
            q = str(c.get("quality", "")).lower()
            ed = c.get("earnings_date")
            clean[t] = {"why": _s(c.get("why"), 300) or "no clear catalyst found",
                        "direction": d if d in ("positive", "negative", "mixed", "none") else "none",
                        "quality": q if q in ("strong", "real", "weak", "none", "unknown") else "unknown",
                        "depth": c.get("depth") if c.get("depth") in ("full", "earnings_only") else (
                            "earnings_only" if str(c.get("why") or "").lower().startswith("earnings date check only") else "full"),
                        "earnings_date": ed if isinstance(ed, str) and _date_ok(ed) else None,
                        "red_flags": [_s(x, 120) for x in _list(c.get("red_flags")) if isinstance(x, str) and _s(x)][:4],
                        "sources": src}
        if not clean:
            raise ValueError("no valid tickers (each needs a source URL)")
        out["stocks"] = clean
    elif kind == "plan":
        out["summary"] = _s(js.get("summary"), 800)
        if not out["summary"]:
            raise ValueError("summary is required")
        V = ("build", "test_first", "watch", "duplicate", "reject")
        items = []
        for it in _list(js.get("items"))[:12]:
            if not isinstance(it, dict) or not _s(it.get("title")):
                continue
            v = str(it.get("verdict", "")).lower()
            pr = it.get("priority")
            if isinstance(pr, str) and pr.strip().isdigit():
                pr = int(pr.strip())                  # agents often write "1"
            if isinstance(pr, float) and pr.is_integer():
                pr = int(pr)
            items.append({"title": _s(it.get("title"), 120), "verdict": v if v in V else "watch",
                          "cards": [_s(c, 60) for c in _list(it.get("cards")) if isinstance(c, str)][:8],
                          **{k: _s(it.get(k), 600) for k in ("where", "how", "test", "kill")},
                          "effort": it.get("effort") if it.get("effort") in ("S", "M", "L") else None,
                          "priority": pr if isinstance(pr, int) and 0 < pr < 100 else None})
        out["items"] = sorted(items, key=lambda x: x["priority"] or 99)
        out["new_agents"] = [{k: _s(a.get(k), 400) for k in ("name", "job", "schedule", "inputs", "outputs", "cost", "why", "kill")}
                             for a in _list(js.get("new_agents"))[:4] if isinstance(a, dict) and _s(a.get("name"))]
        out["retire"] = [{k: _s(a.get(k), 300) for k in ("target", "why")}
                         for a in _list(js.get("retire"))[:6] if isinstance(a, dict) and _s(a.get("target"))]
        out["registry_updates"] = [{k: _s(a.get(k), 300) for k in ("layer", "to", "why")}
                                   for a in _list(js.get("registry_updates"))[:20] if isinstance(a, dict) and _s(a.get("layer"))]
        out["card_updates"] = [{k: _s(a.get(k), 300) for k in ("card", "integrated", "why")}
                               for a in _list(js.get("card_updates"))[:40] if isinstance(a, dict) and _s(a.get("card"))]
        if not items:
            raise ValueError("at least one item is required (use verdict 'watch' if nothing is ready)")
    elif kind == "reclass":
        out["summary"] = _s(js.get("summary"), 800)
        if not out["summary"]:
            raise ValueError("summary is required")
        from . import reclass
        subs = {r["subtheme"] for r in reclass._read_csv(reclass.SUB_FILE)[1]}
        themes = {r["theme"] for r in reclass._read_csv(reclass.THEME_FILE)[1]}
        moves, seen = [], set()
        for m in _list(js.get("moves"))[:80]:
            if not isinstance(m, dict):
                continue
            tk = str(m.get("t") or "").upper().strip()
            act = str(m.get("action") or "").lower().strip()
            if not tk or tk in seen or act not in ("add", "move", "remove", "rename", "keep"):
                continue
            if allowed is not None and tk not in allowed:
                continue
            to = _s(m.get("to"), 120) or ""
            if act in ("add", "move"):
                if to.upper().startswith("NEW:"):
                    g, _, nm = to[4:].partition("/")
                    if not g.strip() or not nm.strip():
                        continue
                    to = f"NEW: {g.strip()} / {nm.strip()}"
                elif to not in subs:
                    continue                                  # unknown sub-theme name: never guess
            elif act == "rename":
                to = to.upper()
                if not re.match(r"^[A-Z][A-Z0-9.\-]{0,9}$", to):
                    continue
            else:
                to = ""
            src = _urls(m.get("sources"))
            if act != "keep" and not src:
                continue                                      # no source, no move
            conf = str(m.get("confidence") or "").lower()
            th = _s(m.get("theme_add"), 120)
            seen.add(tk)
            moves.append({"t": tk, "action": act, "from": _s(m.get("from"), 120) or None, "to": to or None,
                          "theme_add": th if th in themes and act in ("add", "move") else None,
                          "confidence": conf if conf in ("high", "medium", "low") else "low",
                          "why": _s(m.get("why"), 300) or "", "sources": src})
        order = {"remove": 0, "rename": 1, "move": 2, "add": 3, "keep": 4}
        moves.sort(key=lambda x: (order[x["action"]], {"high": 0, "medium": 1, "low": 2}[x["confidence"]]))
        for k, m in enumerate(moves, 1):
            m["id"] = k
        out["moves"] = moves
        ck = js.get("checked")
        out["checked"] = int(ck) if isinstance(ck, (int, float)) or (isinstance(ck, str) and ck.isdigit()) else len(moves)
        if not moves:
            raise ValueError("no valid moves (each needs a worklist ticker, a known sub-theme or 'NEW: Group / Name', and a source)")
    elif kind == "review":
        out["summary"] = _s(js.get("summary"), 700)
        out["findings"] = [_s(x, 300) for x in _list(js.get("findings")) if isinstance(x, str) and _s(x)][:10]
        out["proposals"] = [_s(x, 300) for x in _list(js.get("proposals")) if isinstance(x, str) and _s(x)][:6]
        if not out["summary"]:
            raise ValueError("summary is required")
    else:
        r = str(js.get("risk", "")).lower()
        if r not in ("low", "medium", "high"):
            raise ValueError("risk must be low, medium or high")
        out.update({"headline": _s(js.get("headline"), 240), "risk": r,
                    **{k: _s(js.get(k), 300) for k in ("rates", "fed", "oil", "geo")}})
        ev = []
        for e in _list(js.get("events")):
            if isinstance(e, dict) and _date_ok(e.get("date")) and _s(e.get("name")):
                imp = str(e.get("impact", "")).lower()
                ev.append({"date": e["date"], "time": _s(e.get("time"), 20), "name": _s(e.get("name"), 80),
                           "impact": imp if imp in ("high", "medium") else "medium"})
        out["events"] = sorted(ev, key=lambda e: e["date"])[:12]
        out["sources"] = _urls(js.get("sources"))
        if not out["headline"] or not out["sources"]:
            raise ValueError("headline and at least one source URL are required")
    return out


def _allowed(kind):
    if kind == "reclass":
        from . import reclass
        W = reclass.worklist()
        return {r["t"] for k in ("unclassified", "poor_fit", "stale") for r in W.get(k) or []} or None
    return {x["t"] for x in worklist()["tickers"]} or None


def save(kind, js):
    agent_dir = config.DOCS_DIR / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    allowed = None
    try:
        allowed = _allowed(kind)
    except Exception:
        pass
    clean = validate(kind, js, allowed)
    try:
        cur = worklist().get("for_date")
        if kind not in WEEKLY and cur and clean["for_date"] != cur:
            print(f"WARNING: for_date {clean['for_date']} is not the current card date {cur}; the cards will ignore it")
    except Exception:
        pass
    (agent_dir / f"{kind}.json").write_text(json.dumps(clean, indent=1))
    return clean


def publish(kind, path, push=False):
    js = json.loads(open(path).read())
    wl = worklist()
    if kind not in WEEKLY and js.get("for_date") != wl.get("for_date"):
        sys.exit(f"for_date {js.get('for_date')} != current card date {wl.get('for_date')}: new data arrived, "
                 "re-run the worklist and research again")
    if kind not in WEEKLY and wl.get("past_cutoff"):
        sys.exit(f"too late: ideas for {wl['for_date']} were bought at {wl['entry_cutoff']}; research done now can't be "
                 "logged as known beforehand. Not publishing (the overnight data is probably late; report it).")
    clean = validate(kind, js, _allowed(kind))   # same check the save job runs
    if not push:
        print(json.dumps(clean, indent=1))
        return
    b64 = base64.b64encode(json.dumps(js).encode()).decode()
    if len(b64) > 60000:
        sys.exit("payload too large: trim 'why' texts or tickers")
    r = subprocess.run(["gh", "api", "-X", "POST", f"repos/{REPO}/actions/workflows/agent.yml/dispatches", "-f", "ref=main",
                        "-f", f"inputs[kind]={kind}", "-f", f"inputs[b64]={b64}"], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("dispatch failed: " + (r.stderr or r.stdout)[:400])
    print(f"dispatched agent.yml ({kind}, {len(clean.get('stocks', {})) or 'brief'}): saved and the page rebuilt in ~4 minutes")


def status():
    """Latest Agent input run and its jobs (agents run this ~2 minutes after --push to confirm the save worked)."""
    r = subprocess.run(["gh", "api", f"repos/{REPO}/actions/workflows/agent.yml/runs?per_page=1", "--jq",
                        '.workflow_runs[0]|"\\(.id) \\(.status) \\(.conclusion) \\(.created_at)"'], capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())
    rid = (r.stdout.split() or [""])[0]
    if rid.isdigit():
        j = subprocess.run(["gh", "api", f"repos/{REPO}/actions/runs/{rid}/jobs", "--jq",
                            '.jobs[]|"  \\(.name): \\(.status) \\(.conclusion)"'], capture_output=True, text=True)
        print(j.stdout.strip())


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worklist", "schema", "publish", "save", "status"])
    p.add_argument("kind", nargs="?")
    p.add_argument("--kind", dest="kind2")
    p.add_argument("--file")
    p.add_argument("--b64")
    p.add_argument("--push", action="store_true")
    a = p.parse_args(argv)
    kind = a.kind2 or a.kind
    if a.cmd == "worklist":
        print(json.dumps(worklist(), indent=1))
    elif a.cmd == "schema":
        print(json.dumps(SCHEMA[kind], indent=1))
    elif a.cmd == "publish":
        publish(kind, a.file, a.push)
    elif a.cmd == "status":
        status()
    elif a.cmd == "save":
        clean = save(kind, json.loads(base64.b64decode(a.b64)))
        print(f"saved docs/agent/{kind}.json for {clean['for_date']}")


if __name__ == "__main__":
    sys.exit(main())
