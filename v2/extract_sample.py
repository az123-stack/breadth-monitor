"""Freeze a small slice of the live payload for the v2 style sample.

Run from the repo root: python3 v2/extract_sample.py
Writes v2/sample.json (only fields the v2 sample renders).
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = json.loads((ROOT / "docs/data.json").read_text())
T = D["themes"]


def num(x, nd=2):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return round(float(x), nd)


rows = D["rows"][-60:]
breadth = {
    "dates": [r["date"] for r in rows],
    "up4": [num(r.get("up4"), 0) for r in rows],
    "dn4": [num(r.get("dn4"), 0) for r in rows],
    "t2108": [num(r.get("t2108"), 1) for r in rows],
    "dn_share": [num(r.get("dn_share"), 1) for r in rows],
    "nhnl": [num(r.get("nhnl"), 0) for r in rows],
    "ratio10": [num(r.get("ratio10"), 2) for r in rows],
}

pb = T["playbook"]
playbook = {
    "state": pb["state"], "label": pb["label"], "advice": pb["advice"], "since": pb["since"],
    "rows": [{"name": r["name"], "verdict": r["verdict"], "r": num(r.get("avg_r"), 2), "n": r.get("n")}
             for r in pb["rows"]],
}

picks = []
for p in T["launch"]["picks"]:
    picks.append({
        "t": p["t"], "name": p["name"], "sub": p["sub"], "grade": p["grade"], "stage": p["stage"],
        "loc": p["loc"], "rs": p["rs"], "price": p["price"], "e9": num(p["e9"]), "e21": num(p["e21"]),
        "atr": p["atr"], "why": p["why"], "stop": p["plan"]["stop"],
    })

lc = T["lifecycle"]
groups = [{"g": r["g"], "sector": r["sector"], "stage": r["stage"], "days": r["stage_days"],
           "buy": r["buy"], "watch": r["watch"], "strength": num(r["strength"], 1), "rank": r["s_rank"],
           "tier": r.get("tier")} for r in lc["rows"]]

live = sorted(lc["live"], key=lambda x: (-int(bool(x["t3"])), -x["rs"]))[:8]
lined = [{"t": x["t"], "g": x["g"], "rs": x["rs"], "c": x["c"], "hi": x["hi"], "lo": x["lo"],
          "e9": num(x["e9"]), "e21": num(x["e21"]), "adr": num(x["adr"] * 100, 1),
          "t3": x["t3"], "earn": x["earn"]} for x in live]

ts = T["trade_setups"]
srows = ts["rows"]
setups = []
seen = set()
for s in ts["setups"]:
    for t in s.get("top", []):
        r = srows.get(t)
        if not r:
            continue
        setups.append({"t": t, "setup": s["name"], "key": s["key"], "price": r["price"], "rs": r["rsr"],
                       "group": r.get("sub") or r.get("theme"), "grp": num(r.get("grp"), 0),
                       "off_hi": num(r["off_hi"] * 100, 1), "e21": num(r["e21"] * 100, 1),
                       "adr": num(r["adr"], 1), "score": num(r["score"], 0)})
verdict = {r["name"]: r["verdict"] for r in playbook["rows"]}
for s in setups:
    s["verdict"] = verdict.get(s["setup"], "Unproven")

tick = {t for t in [p["t"] for p in picks] + [x["t"] for x in lined] + [s["t"] for s in setups]}
tv = {t: T["tv"].get(t, t) for t in tick}

trade = T["thetrade"]
story = json.loads((ROOT / "docs/story.json").read_text())["chapters"][-1]

stair_t = T["stairs"]["themes"]
stair_s = {r["g"]: r for r in T["stairs"]["rows"]}
lc_all = lc["all"]


def grow(r, kind):
    name = r["theme"]
    if kind == "theme":
        s = stair_t.get(name, {})
        stair = [s.get("status", "none"), s.get("since", 0), bool(s.get("leader"))]
        stage = None
    else:
        s = stair_s.get(name, {})
        stair = [s.get("status", "none"), s.get("since", 0), bool(s.get("leader"))]
        a = lc_all.get(name)
        stage = [a[0], a[2], a[5]] if a else None
    return {
        "n": name, "k": r["n"], "etf": r.get("etf"), "sec": r.get("group"),
        "str": num(r.get("strength"), 1), "rk": r.get("s_rank"), "mv5": r.get("s_mv5"),
        "sc": r.get("score"), "rot": r.get("rotation"), "cls": r.get("class"),
        "d1": num(r["today"] * 100, 2), "d5": num(r["d5"] * 100, 1), "d15": num(r["d15"] * 100, 1),
        "d30": num(r["d30"] * 100, 1), "d90": num(r["d90"] * 100, 1), "rs": num(r.get("rs"), 1),
        "trail": [num(x, 0) for x in (r.get("s_trail") or [])],
        "m": r["members"], "stair": stair, "stage": stage,
    }


themes = [grow(r, "theme") for r in T["themes"]]
subs = [grow(r, "sub") for r in T["subthemes"]]
want = {t for g in themes + subs for t in g["m"]}
stocks = {}
for s in T["stocks"]:
    if s["t"] in want:
        stocks[s["t"]] = [s.get("name", "")[:40], s.get("price"), num((s.get("today") or 0) * 100, 2),
                          num((s.get("d5") or 0) * 100, 1), num((s.get("d30") or 0) * 100, 1),
                          s.get("rsr"), num((s.get("off_hi") or 0) * 100, 1), num(s.get("adr"), 1),
                          num((s.get("e21") or 0) * 100, 1)]
pulse = T["pulse"]

out = {
    "themes": themes, "subs": subs, "stocks": stocks,
    "pulse": {"long": pulse["long"], "short": pulse["short"], "ll": pulse["long_label"], "sl": pulse["short_label"]},
    "asof": T["date"], "regime": D["regime"], "last": {k: num(v, 2) for k, v in D["rows"][-1].items() if k != "date"},
    "breadth": breadth, "playbook": playbook, "picks": picks, "groups": groups, "lined": lined,
    "lc_size": lc["size"], "setups": setups, "tv": tv,
    "trade": {"name": trade["name"]},
    "pick_bt": T["launch"]["pick_bt"],
    "story": {"date": story["date"], "slot": story["slot"], "title": story["title"], "md": story["md"][:3200]},
}
(ROOT / "v2/sample.json").write_text(json.dumps(out, separators=(",", ":")))
print("wrote", len(json.dumps(out)) // 1024, "KB;", len(setups), "setup rows,", len(groups), "groups")
