"""Market Monitor v2 page (Oct 28 2026; Adam approved "Option B": a new page beside the old one, same data).

Every build, `site.build` hands the finished payload to `build(data)`, which slims it to what the v2 views use and writes
docs/v2/index.html (served at /breadth-monitor/v2/). The v1 page at docs/index.html is unchanged. Each section is built
on its own: one failing section leaves its page showing "appears after the next data run", never a broken page.

Views (6 main tabs with sub-tabs): Today · Market · Groups (Themes, Lifecycle, Lighting up, Stair steps, Rotation, Timeline)
· Setups (All setups, Launch list, Box trades, Lined-up & dips, Strength on weakness, Record volume, Export lists) · Read · Lab.
Pages not built yet list what moves there from v1.
"""
import json
import logging
import math
from pathlib import Path

from . import config

log = logging.getLogger(__name__)
TEMPLATE = Path(__file__).with_name("v2_template.html")


def num(x, nd=2):
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return round(x, nd)


def _pct(x, nd=1):
    v = num(x, 6)
    return None if v is None else round(v * 100, nd)


def _today(D, T):
    pb = T["playbook"]
    rows = D["rows"]
    out = {
        "asof": T.get("date") or rows[-1]["date"],
        "last": {k: num(v, 2) for k, v in rows[-1].items() if k != "date"},
        "breadth": {k: [num(r.get(k), 2) for r in rows[-60:]] for k in ("up4", "dn4", "t2108", "dn_share", "nhnl", "ratio10")},
        "thresholds": D.get("thresholds") or {},
        "playbook": {"state": pb["state"], "label": pb["label"], "advice": pb["advice"], "since": pb.get("since"),
                     "rows": [{"name": r["name"], "verdict": r["verdict"], "r": num(r.get("avg_r"), 2), "n": r.get("n")}
                              for r in pb.get("rows") or []]},
    }
    return out


def _picks(T):
    out = []
    for p in (T.get("launch") or {}).get("picks") or []:
        plan = p.get("plan") or {}
        out.append({"t": p["t"], "name": p.get("name") or "", "sub": p.get("sub") or "", "grade": p.get("grade"),
                    "stage": p.get("stage"), "loc": p.get("loc"), "rs": p.get("rs"), "price": p.get("price"),
                    "atr": p.get("atr"), "why": p.get("why") or "", "stop": plan.get("stop") or ""})
    return out


def _lifecycle(T):
    lc = T["lifecycle"]
    groups = [{"g": r["g"], "sector": r.get("sector"), "stage": r.get("stage"), "days": r.get("stage_days"),
               "buy": bool(r.get("buy")), "watch": bool(r.get("watch")), "strength": num(r.get("strength"), 1),
               "rank": r.get("s_rank"), "tier": r.get("tier")} for r in lc.get("rows") or []]
    live = sorted(lc.get("live") or [], key=lambda x: (-int(bool(x.get("t3"))), -(x.get("rs") or 0)))[:8]
    lined = [{"t": x["t"], "g": x.get("g"), "rs": x.get("rs"), "c": x.get("c"), "hi": x.get("hi"), "lo": x.get("lo"),
              "e9": num(x.get("e9")), "e21": num(x.get("e21")), "adr": _pct(x.get("adr")), "t3": bool(x.get("t3")),
              "earn": x.get("earn")} for x in live]
    return {"groups": groups, "lined": lined, "lc_size": lc.get("size"), "lc_all": lc.get("all") or {}}


def _setups(T, verdicts):
    ts = T["trade_setups"]
    srows = ts["rows"]
    out = []
    for s in ts["setups"]:
        for t in s.get("top", []):
            r = srows.get(t)
            if not r:
                continue
            out.append({"t": t, "setup": s["name"], "key": s["key"], "price": r.get("price"), "rs": r.get("rsr"),
                        "group": r.get("sub") or r.get("theme"), "grp": num(r.get("grp"), 0),
                        "off_hi": _pct(r.get("off_hi")), "e21": _pct(r.get("e21")), "adr": num(r.get("adr"), 1),
                        "score": num(r.get("score"), 0), "verdict": verdicts.get(s["name"], "Unproven")})
    return out


def _groups(T, lc_all):
    stair_t = (T.get("stairs") or {}).get("themes") or {}
    stair_s = {r["g"]: r for r in (T.get("stairs") or {}).get("rows") or []}

    def grow(r, kind):
        name = r["theme"]
        s = (stair_t if kind == "theme" else stair_s).get(name) or {}
        a = lc_all.get(name) if kind == "sub" else None
        return {"n": name, "k": r.get("n"), "etf": r.get("etf"), "sec": r.get("group"),
                "str": num(r.get("strength"), 1), "rk": r.get("s_rank"), "mv5": r.get("s_mv5"), "sc": r.get("score"),
                "rot": r.get("rotation"), "cls": r.get("class"),
                "d1": _pct(r.get("today"), 2), "d5": _pct(r.get("d5")), "d15": _pct(r.get("d15")), "d30": _pct(r.get("d30")),
                "d90": _pct(r.get("d90")), "rs": num(r.get("rs"), 1),
                "trail": [num(x, 0) for x in (r.get("s_trail") or [])], "m": r.get("members") or [],
                "stair": [s.get("status", "none"), s.get("since", 0), bool(s.get("leader"))],
                "stage": [a[0], a[2], a[5]] if a else None}
    themes = [grow(r, "theme") for r in T["themes"]]
    subs = [grow(r, "sub") for r in T["subthemes"]]
    want = {t for g in themes + subs for t in g["m"]}
    stocks = {}
    for s in T.get("stocks") or []:
        if s["t"] in want:
            stocks[s["t"]] = [(s.get("name") or "")[:40], s.get("price"), _pct(s.get("today"), 2), _pct(s.get("d5")),
                              _pct(s.get("d30")), s.get("rsr"), _pct(s.get("off_hi")), num(s.get("adr"), 1), _pct(s.get("e21"))]
    return {"themes": themes, "subs": subs, "stocks": stocks}


def _lighting(T):
    ig = T["rotation"]["ignition"]
    bt = ig.get("bt") or {}
    d1 = ig.get("day1") or {}
    return {
        "act": ig.get("act"), "ratio10": ig.get("ratio10"), "peak15": ig.get("peak15"), "labels": ig.get("labels") or {},
        "bt": {k: bt[k] for k in ("all", "strong", "other", "base", "lead_strong", "lead_other") if k in bt},
        "rows": [{"g": r["g"], "sec": r.get("sector"), "status": r.get("status"), "ago": r.get("ago"), "since": num(r.get("since"), 4),
                  "met": r.get("met") or {}, "n": r.get("n_met"), "br": num(r.get("breadth"), 2), "flow": num(r.get("flow"), 2),
                  "drk": num(r.get("drk"), 2), "r20": num(r.get("r20"), 4), "str": num(r.get("strength"), 1), "rk": r.get("s_rank"),
                  "lead": (r.get("lead") or {}).get("ok", False), "drivers": [d.get("label") for d in r.get("drivers") or []],
                  "stocks": [[s["t"], s.get("rsr"), _pct(s.get("off_hi"))] for s in (r.get("stocks") or [])[:4]]}
                 for r in ig.get("rows") or []],
        "day1": [{"g": r["g"], "sec": r.get("sector"), "ago": r.get("ago"), "r1": _pct(r.get("r1"), 2), "rv": r.get("rv"),
                  "brk": num(r.get("brk"), 2), "d3": _pct(r.get("d3"), 2), "since": _pct(r.get("since"), 2),
                  "str": num(r.get("strength"), 1), "stocks": [[s["t"], s.get("rsr")] for s in (r.get("stocks") or [])[:4]]}
                 for r in d1.get("rows") or []],
        "d1bt": {k: d1.get("bt", {})[k] for k in ("all", "held", "faded") if k in d1.get("bt", {})},
    }


def _stairs(T, lc_all):
    X = T["stairs"]
    return {"date": X.get("date"), "n_step": X.get("n_stepping"), "n_set": X.get("n_setting"),
            "rows": [{"g": r["g"], "th": r.get("theme"), "status": r.get("status"), "since": r.get("since"), "lead": bool(r.get("leader")),
                      "n": r.get("n"), "nuz5": num(r.get("nuz5"), 2), "lifted": num(r.get("lifted"), 2),
                      "rel5": _pct(r.get("rel5")), "rel20": _pct(r.get("rel20")),
                      "h_nuz": [num(x, 2) for x in r.get("h_nuz") or []], "h_lift": [num(x, 2) for x in r.get("h_lift") or []],
                      "h_st": r.get("h_st") or [], "stage": (lc_all.get(r["g"]) or [None])[0],
                      "m": [[m["t"], m.get("state"), num(m.get("d9"), 2), num(m.get("d21"), 2), m.get("rsr"), m.get("price"),
                             _pct(m.get("to_step")), m.get("adr")] for m in r.get("members") or []]}
                     for r in X.get("rows") or []]}


def _launch(T):
    L = T["launch"]
    tr = L.get("tracker") or {}
    return {"picks_bt": L.get("pick_bt") or {}, "counts": L.get("counts") or {},
            "tracker": {k: tr.get(k) for k in ("n", "open", "closed", "live_avg", "live_xspy")},
            "trk": [{k: r.get(k) for k in ("week", "rank", "t", "grade", "stage", "sub", "entry", "last", "ret", "xspy", "best", "status")}
                    for r in tr.get("rows") or []],
            "rows": [{"t": r["t"], "name": (r.get("name") or "")[:40], "grade": r.get("grade"), "stage": r.get("stage"),
                      "loc": r.get("loc"), "vs9": num(r.get("vs9"), 2), "flag": bool(r.get("flag")), "sub": r.get("sub"),
                      "pts": r.get("pts") or {}, "rs": r.get("rs"), "price": r.get("price"), "atr": r.get("atr"),
                      "dvol": r.get("dvol"), "prime": bool(r.get("prime"))} for r in L.get("rows") or []]}


def _sow(T):
    sw = T["sow"]
    return {"week": sw.get("week"), "week_done": sw.get("week_done"), "states": sw.get("states") or [],
            "rows": [{"t": r["t"], "name": (r.get("name") or "")[:40], "state": r.get("state"), "ago": r.get("ago"),
                      "price": r.get("price"), "vs9": _pct(r.get("vs9")), "vs21": _pct(r.get("vs21")), "atr": r.get("atr"),
                      "trig": r.get("trig"), "stop": r.get("stop"), "risk": _pct(r.get("risk")), "rs": r.get("rsr"),
                      "sub": r.get("sub") or r.get("theme"), "prime": bool(r.get("prime")), "pnew": bool(r.get("prime_new")),
                      "rslhi": bool(r.get("rsl_hi")), "adr": r.get("adr"),
                      "wk": [num(x, 2) for x in (r.get("wk") or [])[-26:]], "w9": [num(x, 2) for x in (r.get("w9") or [])[-26:]],
                      "w21": [num(x, 2) for x in (r.get("w21") or [])[-26:]]} for r in sw.get("rows") or []]}


def _hve(T):
    hv = T["hve"]
    ev = hv.get("evidence") or {}
    return {"ev": {k: ev[k] for k in ("hold", "from", "to", "up", "base", "up_rs85", "down") if k in ev},
            "rows": [{k: r.get(k) for k in ("t", "name", "date", "dow", "ago", "x50", "vs_prev", "chg", "gap", "loc", "lo", "hi",
                                            "close", "since", "dollars", "rsr", "ever", "liq", "profile", "sub", "theme", "adr", "short")}
                     for r in hv.get("rows") or []]}


def _story():
    f = config.DOCS_DIR / "story.json"
    try:
        ch = [c for c in json.loads(f.read_text()).get("chapters") or [] if c.get("slot") != "data"]
        c = ch[-1]
        return {"date": c["date"], "slot": c.get("slot"), "title": c.get("title") or "", "md": c.get("md") or ""}
    except Exception:
        return None


def slim(D):
    """The v2 payload. Sections that fail are left out (the page shows them as not available yet)."""
    T = D.get("themes") or {}
    out = {"generated": D.get("generated"), "regime": D.get("regime")}

    def put(name, fn, *a):
        try:
            v = fn(*a)
            if isinstance(v, dict) and name is None:
                out.update(v)
            else:
                out[name] = v
        except Exception as e:  # one section never takes the page down
            log.warning("v2 section %s skipped: %s", name or fn.__name__, e)

    put(None, _today, D, T)
    put("picks", _picks, T)
    lc = {}
    try:
        lc = _lifecycle(T)
        out.update({k: lc[k] for k in ("groups", "lined", "lc_size")})
    except Exception as e:
        log.warning("v2 section lifecycle skipped: %s", e)
    lc_all = lc.get("lc_all") or {}
    verdicts = {r["name"]: r["verdict"] for r in (out.get("playbook") or {}).get("rows") or []}
    put("setups", _setups, T, verdicts)
    put(None, _groups, T, lc_all)
    put("lighting", _lighting, T)
    put("stairs", _stairs, T, lc_all)
    put("launch", _launch, T)
    put("sow", _sow, T)
    put("hve", _hve, T)
    put("story", _story)
    try:
        tt = T.get("thetrade") or {}
        out["trade"] = {"name": tt.get("name"), "state": tt.get("state"), "above": tt.get("above"), "below": tt.get("below")}
    except Exception:
        pass
    want = {p["t"] for p in out.get("picks") or []} | {x["t"] for x in out.get("lined") or []} | {s["t"] for s in out.get("setups") or []}
    for k in ("launch", "sow", "hve"):
        want |= {r["t"] for r in (out.get(k) or {}).get("rows") or []}
    want |= {t for g in (out.get("themes") or []) + (out.get("subs") or []) for t in g["m"]}
    want |= {m[0] for r in (out.get("stairs") or {}).get("rows") or [] for m in r["m"]}
    tv = T.get("tv") or {}
    out["tv"] = {t: tv[t] for t in want if t in tv}
    return out


def build(data):
    if not TEMPLATE.exists():
        return
    S = slim(data)
    blob = json.dumps(S, separators=(",", ":")).replace("<", "\\u003c")
    html = TEMPLATE.read_text().replace("/*__DATA__*/null", blob)
    out = config.DOCS_DIR / "v2"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(html)
