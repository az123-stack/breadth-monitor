"""End-to-end proof that unproven layers can't move the Top 2 picks (DECISIONS.md, scorecard item 7).

Copies the repo twice, writes hostile agent files into one copy (every pick and candidate: negative news, red flags,
earnings tomorrow, high macro risk, a passed macro backtest), runs a full --rebuild-only in both, and compares the
picks, watch list, candidates and data/pick_ledger.csv. Exit code 1 if anything differs.

    python tools/check_info_only.py        # ~6 minutes (two full rebuilds)
"""
import hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def data(p):
    h = (p / "docs" / "index.html").read_text()
    i = h.index("const DATA = ") + len("const DATA = ")
    return json.JSONDecoder().raw_decode(h[i:])[0]


def main():
    tmp = Path(tempfile.mkdtemp())
    a, b = tmp / "clean", tmp / "hostile"
    ign = shutil.ignore_patterns(".git", "__pycache__")
    shutil.copytree(ROOT, a, ignore=ign); shutil.copytree(ROOT, b, ignore=ign)
    for p in (a, b):
        shutil.rmtree(p / "docs" / "agent", ignore_errors=True)
    pb = data(ROOT)["themes"]["playbook"]
    day = data(ROOT)["themes"]["date"]
    names = [x["t"] for x in pb["picks"]] + [x["t"] for x in pb.get("pick_watch", [])] + list(pb.get("pick_cands", []))
    from datetime import date, timedelta
    tomorrow = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
    ag = b / "docs" / "agent"; ag.mkdir(parents=True)
    (ag / "catalysts.json").write_text(json.dumps({"for_date": day, "written": "2000-01-01T00:00Z", "stocks": {
        t: {"why": "fraud", "direction": "negative", "quality": "strong", "earnings_date": tomorrow,
            "red_flags": ["offering", "downgrade"], "sources": ["https://x.y"], "depth": "full"} for t in names}}))
    (ag / "macro_brief.json").write_text(json.dumps({"for_date": day, "written": "2000-01-01T00:00Z", "headline": "crash",
        "risk": "high", "events": [{"date": tomorrow, "name": "CPI", "impact": "high"}], "sources": ["https://x.y"]}))
    ev = json.loads((b / "data" / "layer_evidence.json").read_text())
    if isinstance(ev.get("macro_fit"), dict):
        ev["macro_fit"]["passed"] = True
    (b / "data" / "layer_evidence.json").write_text(json.dumps(ev))
    for p in (a, b):
        r = subprocess.run([sys.executable, "-W", "ignore", "-m", "breadth.update", "--rebuild-only"], cwd=p,
                           capture_output=True, text=True)
        if r.returncode:
            print(r.stderr[-2000:]); return 1
    pa, pb_ = data(a)["themes"]["playbook"], data(b)["themes"]["playbook"]
    keys = ("picks", "pick_watch", "pick_cands")
    same = all(json.dumps(pa.get(k), sort_keys=True) == json.dumps(pb_.get(k), sort_keys=True) for k in keys)
    md5 = lambda p: hashlib.md5((p / "data" / "pick_ledger.csv").read_bytes()).hexdigest()
    same_ledger = md5(a) == md5(b)
    cards_differ = json.dumps(data(a)["themes"].get("decision")) != json.dumps(data(b)["themes"].get("decision"))
    print(f"picks/watch/candidates identical: {same} · pick_ledger.csv identical: {same_ledger} · "
          f"cards did change (sanity): {cards_differ} · picks {[x['t'] for x in pa['picks']]}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if same and same_ledger and cards_differ else 1


if __name__ == "__main__":
    sys.exit(main())
