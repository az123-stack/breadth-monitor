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
KINDS = ("catalysts", "macro_brief", "review")
MAX_TICKERS = 15
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL = re.compile(r"^https?://\S+$")

SCHEMA = {
    "catalysts": {
        "for_date": "YYYY-MM-DD — copy `for_date` from the worklist",
        "stocks": {"TICKER": {
            "why": "one or two plain sentences: what is actually driving the stock now (or 'no clear catalyst found')",
            "direction": "positive | negative | mixed | none",
            "quality": "strong (fresh hard news: earnings beat/raise, FDA, contract, M&A) | real (genuine but older or softer) | weak (rumour, sympathy only) | none | unknown",
            "earnings_date": "YYYY-MM-DD of the NEXT earnings report if found, else null",
            "red_flags": ["short list: offering/dilution, downgrade, lawsuit, guidance cut, short report, insider selling... [] if none"],
            "sources": ["https://... at least one URL you actually used"]}},
    },
    "review": {
        "for_date": "YYYY-MM-DD — the latest official date (worklist for_date)",
        "summary": "2-4 plain sentences for Adam: what the evidence says this week",
        "findings": ["one line each: a layer and what its evidence shows (numbers from `python -m breadth.layers report`)"],
        "proposals": ["one line each: a concrete change to consider, and the evidence; or 'no changes yet: not enough data'"],
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
    stocks = [{"t": c["t"], "role": c["role"], "name": c.get("name"), "setup": c.get("setup_name") or c.get("setup"),
               "price": c.get("price")} for c in cards[:MAX_TICKERS]]
    return {"for_date": dec.get("date"), "tickers": stocks,
            "note": "for_date is the last official close; research news up to now. Keep the order: picks first."}


def _s(v, n=400):
    return re.sub(r"\s+", " ", str(v)).strip()[:n] if v is not None else None


def _urls(v):
    return [u for u in (v or []) if isinstance(u, str) and URL.match(u.strip())][:6]


def validate(kind, js, allowed=None):
    """Return a clean dict or raise ValueError."""
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind}")
    if not isinstance(js, dict) or not DATE.match(str(js.get("for_date", ""))):
        raise ValueError("for_date (YYYY-MM-DD) missing")
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
                        "earnings_date": ed if isinstance(ed, str) and DATE.match(ed) else None,
                        "red_flags": [_s(x, 120) for x in (c.get("red_flags") or []) if _s(x)][:4],
                        "sources": src}
        if not clean:
            raise ValueError("no valid tickers (each needs a source URL)")
        out["stocks"] = clean
    elif kind == "review":
        out["summary"] = _s(js.get("summary"), 700)
        out["findings"] = [_s(x, 240) for x in (js.get("findings") or []) if _s(x)][:10]
        out["proposals"] = [_s(x, 240) for x in (js.get("proposals") or []) if _s(x)][:6]
        if not out["summary"]:
            raise ValueError("summary is required")
    else:
        r = str(js.get("risk", "")).lower()
        if r not in ("low", "medium", "high"):
            raise ValueError("risk must be low, medium or high")
        out.update({"headline": _s(js.get("headline"), 240), "risk": r,
                    **{k: _s(js.get(k), 300) for k in ("rates", "fed", "oil", "geo")}})
        ev = []
        for e in js.get("events") or []:
            if isinstance(e, dict) and DATE.match(str(e.get("date", ""))) and _s(e.get("name")):
                imp = str(e.get("impact", "")).lower()
                ev.append({"date": e["date"], "time": _s(e.get("time"), 20), "name": _s(e.get("name"), 80),
                           "impact": imp if imp in ("high", "medium") else "medium"})
        out["events"] = sorted(ev, key=lambda e: e["date"])[:12]
        out["sources"] = _urls(js.get("sources"))
        if not out["headline"] or not out["sources"]:
            raise ValueError("headline and at least one source URL are required")
    return out


def save(kind, js):
    agent_dir = config.DOCS_DIR / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    allowed = None
    try:
        allowed = {x["t"] for x in worklist()["tickers"]} or None
    except Exception:
        pass
    clean = validate(kind, js, allowed)
    (agent_dir / f"{kind}.json").write_text(json.dumps(clean, indent=1))
    return clean


def publish(kind, path, push=False):
    js = json.loads(open(path).read())
    clean = validate(kind, js)                    # fail fast before dispatching
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


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worklist", "schema", "publish", "save"])
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
    elif a.cmd == "save":
        clean = save(kind, json.loads(base64.b64decode(a.b64)))
        print(f"saved docs/agent/{kind}.json for {clean['for_date']}")


if __name__ == "__main__":
    sys.exit(main())
