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
              "e9": num(x.get("e9")), "e21": num(x.get("e21")), "adr": _pct(x.get("adr")), "a": x.get("adr"), "t3": bool(x.get("t3")),
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
                              _pct(s.get("d30")), s.get("rsr"), _pct(s.get("off_hi")), num(s.get("adr"), 1), _pct(s.get("e21")),
                              s.get("sub") or ""]
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


STATE_ROW = {"thr05": "Thrust day to 5 sessions after", "thr625": "6-25 sessions after a thrust", "none": "No thrust in 25 sessions"}
BOX_LONG = {"retest_long": "Retest bounce", "trap_long": "Spring (failed breakdown)"}


def _stair_lookup(T):
    S = T.get("stairs") or {}
    subs = {r["g"]: r for r in S.get("rows") or []}
    themes = S.get("themes") or {}
    own = S.get("stocks") or {}
    stk = {s["t"]: s for s in T.get("stocks") or []}

    def group(t, sub=None, theme=None):
        k = stk.get(t) or {}
        sub = sub or k.get("sub")
        theme = theme or (k.get("themes") or [None])[0]
        return subs.get(sub) or themes.get(theme) or None
    return group, own


def _boxes(T):
    X = T["boxes"]
    group, own = _stair_lookup(T)
    now = (X.get("now_state") or {}).get("state")
    tiles = []
    for typ, name in BOX_LONG.items():
        rows = (X.get("study") or {}).get(typ, {}).get("rows") or []
        r = next((x for x in rows if x.get("name") == STATE_ROW.get(now)), None)
        if r and r.get("n", 0) >= 30 and r.get("R") is not None:
            v = "Favored" if r["R"] >= 0.15 and r.get("t", 0) >= 2 and r.get("h1", 0) > 0 and r.get("h2", 0) > 0 else \
                "Fights the tape" if r["R"] < 0 and r.get("t", 0) <= -2 else "No clear edge"
        else:
            v = "Not enough history"
        tiles.append({"type": typ, "name": name, "verdict": v, "R": num((r or {}).get("R"), 2), "win": num((r or {}).get("win"), 3),
                      "n": (r or {}).get("n"), "state": STATE_ROW.get(now)})
    out = []
    for r in X.get("live") or []:
        if r.get("type") not in BOX_LONG:
            continue
        g = group(r["t"], r.get("sub"), r.get("theme")) or {}
        o = own.get(r["t"])
        p, st, tg = r.get("price"), r.get("stop"), r.get("target")
        rr = (tg - p) / (p - st) if p and st is not None and tg is not None and st < p else None
        act = (r["type"] == "retest_long" and r.get("tag") in ("go", "at")) or (r["type"] == "trap_long" and r.get("tag") == "failed")
        fav = bool(act and r.get("grade") in ("A", "B") and rr is not None and rr >= 1.5 and g.get("leader")
                   and not (r.get("tag") == "at" and not ((r.get("vs_lvl_adr") if r.get("vs_lvl_adr") is not None else 9) <= 1.5)))
        out.append({"t": r["t"], "name": (r.get("name") or "")[:40], "price": p, "type": r["type"], "tag": r.get("tag"),
                    "kind": r.get("kind"), "wks": r.get("wks"), "lvl": r.get("lvl"), "top": r.get("top"), "bot": r.get("bot"),
                    "stop": st, "target": tg, "rr": num(rr, 2), "grade": r.get("grade"), "exp": num(r.get("exp"), 2),
                    "win": num(r.get("exp_win"), 3), "en": r.get("exp_n"), "vs": r.get("vs_lvl_adr"), "adr": r.get("adr"),
                    "rs": r.get("rsr"), "sub": r.get("sub") or r.get("theme"), "fav": fav, "glead": bool(g.get("leader")),
                    "gst": g.get("status") or "none", "own": o[0] if o else None,
                    "px": [num(x, 2) for x in (r.get("px") or [])[-80:]]})
    idx = []
    for t, s in (X.get("idx_status") or {}).items():
        r = next((x for x in X.get("idx") or [] if x["t"] == t), None)
        idx.append({"t": t, "type": (s or {}).get("type"), "tag": (s or {}).get("tag"), "lvl": (r or {}).get("lvl"),
                    "farp": (r or {}).get("farp"), "price": (r or {}).get("price")})
    return {"date": X.get("date"), "state": STATE_ROW.get(now), "tiles": tiles, "rows": out, "idx": idx,
            "from": X.get("from"), "to": X.get("to")}


def _lineup(T):
    from . import lineup
    lc = T["lifecycle"]
    rows = []
    for x in lc.get("live") or []:
        try:
            s = lineup.state(x, None)
        except Exception:
            continue
        rows.append({"t": x["t"], "g": x.get("g"), "kind": x.get("kind"), "stage": x.get("stage"), "lead": bool(x.get("lead")),
                     "rs": x.get("rs"), "price": s["price"], "trigger": s["trigger"], "stop": s["stop"], "st": s["st"],
                     "loc": s["loc"], "precise": s["precise"], "d9": s["d9"], "d21": s["d21"], "earn": x.get("earn"),
                     "adr": _pct(x.get("adr")),
                     # raw inputs so the page can redo the state on live prices (same math as lineup.state)
                     "c": x.get("c"), "hi": x.get("hi"), "lo": x.get("lo"), "e9": x.get("e9"), "e21": x.get("e21"),
                     "a": x.get("adr"), "t3": bool(x.get("t3"))})
    tr = lc.get("tracker") or {}
    se = (lc.get("stock_evidence") or {}).get("trigger") or {}
    P = T.get("polished") or {}
    nz = [{"t": r["t"], "sub": r.get("sub"), "price": r.get("price"), "rs": r.get("rs"), "state": r.get("state"),
           "ago": r.get("days_since"), "e9": r.get("e9"), "e21": r.get("e21"), "stop": r.get("stop"), "adr": r.get("adr"),
           "lead": (r.get("grank") or 0) >= 2 / 3} for r in P.get("nuzzle") or []]
    fl = [{"t": r["t"], "sub": r.get("sub"), "price": r.get("price"), "rs": r.get("rs"), "pivot": r.get("pivot"),
           "to": r.get("to_pivot"), "stop": r.get("stop"), "risk": _pct(r.get("risk")), "leg": _pct(r.get("leg"), 0),
           "depth": _pct(r.get("depth")), "days": r.get("days"), "lead": (r.get("grank") or 0) >= 2 / 3} for r in P.get("flags") or []]
    D = T.get("dips") or {}
    dips = [{"t": r["t"], "sub": r.get("sub") or r.get("theme"), "price": r.get("price"), "low": r.get("low"), "e9": num(r.get("e9")),
             "e21": num(r.get("e21")), "adr": r.get("adr"), "rs": r.get("rsr"), "up": bool(r.get("up")),
             "f": [k for k in ("wick9", "wick21", "reclaim9", "reclaim21", "under9", "under21") if r.get(k)],
             "strip": r.get("strip") or []} for r in D.get("rows") or []]
    ev = P.get("evidence") or {}
    return {"size": lc.get("size"), "weak": lc.get("weak"), "act": lc.get("act"), "ratio10": lc.get("ratio10"),
            "rows": rows, "tracker": {k: tr.get(k) for k in ("since", "sessions", "buy", "ready", "all")},
            "trk": (tr.get("rows") or [])[:40],
            "ev": {k: se.get(k) for k in ("buy", "watch", "other", "edge", "t", "filled")},
            "nuzzle": nz, "flags": fl, "dips": dips,
            "pev": {k: {kk: (ev.get(k) or {}).get(kk) for kk in ("lead", "other", "none", "edge", "t", "proven")} for k in ("nuzzle", "flag")}}


def _lifepage(T):
    lc = T["lifecycle"]
    ev = lc.get("evidence") or {}
    keep = ("forgotten", "push", "ignition", "build", "blossom", "fade", "watch", "buy", "buy_act", "buy_noact", "buy_weak")
    return {"size": lc.get("size"), "weak": lc.get("weak"), "act": lc.get("act"), "ratio10": lc.get("ratio10"), "regime": lc.get("regime"),
            "alerts": lc.get("alerts") or [], "all": lc.get("all") or {},
            "rows": [{"g": r["g"], "sec": r.get("sector"), "stage": r.get("stage"), "days": r.get("stage_days"), "buy": bool(r.get("buy")),
                      "ready": bool(r.get("ready")), "watch": bool(r.get("watch")), "hot": bool(r.get("hot")), "new": bool(r.get("new")),
                      "str": num(r.get("strength"), 1), "rk": r.get("s_rank"), "tier": r.get("tier"), "lead": bool(r.get("lead")),
                      "br": num(r.get("br"), 2), "why": r.get("why") or [],
                      "picks": [{k: p.get(k) for k in ("t", "rs", "price", "entry", "trigger", "stop", "plan", "earn", "vs21")} for p in r.get("picks") or []],
                      "wait": [{k: p.get(k) for k in ("t", "rs", "price", "plan", "earn", "vs21")} for p in r.get("wait") or []]}
                     for r in lc.get("rows") or []],
            "ev": {k: ev.get("d20", {}).get(k) for k in keep}, "ev40": {k: ev.get("d40", {}).get(k) for k in ("buy", "blossom")},
            "w2b": ev.get("watch_to_buy"), "from": ev.get("from"), "to": ev.get("to")}


def _market(D, T):
    keys = ("up4", "dn4", "ratio5", "ratio10", "up25q", "dn25q", "up25m", "dn25m", "t2108", "nh", "nl", "dn_share", "dv_net", "dv_up", "dv_dn", "up4_avg40")
    rows = [{"d": r["date"], **{k: num(r.get(k), 2) for k in keys}} for r in D["rows"][-120:]]
    out = {"rows": rows, "events": (D.get("events") or [])[-12:], "regime": D.get("regime"), "pct": D.get("percentiles") or {}}
    tt = T.get("thetrade") or {}
    if tt:
        ra = tt.get("ratio") or {}
        out["trade"] = {"name": tt.get("name"), "state": tt.get("state"), "above": tt.get("above"), "below": tt.get("below"),
                        "corr": tt.get("corr"), "ind": tt.get("ind"), "comeback": tt.get("comeback"), "dn_share": tt.get("dn_share"),
                        "winners": [{k: w.get(k) for k in ("g", "sector", "r20", "r5", "strength")} for w in (tt.get("winners") or [])[:8]],
                        "losers": [{k: w.get(k) for k in ("g", "sector", "r20", "r5", "strength")} for w in (tt.get("losers") or [])[:8]],
                        "plays": [{k: w.get(k) for k in ("t", "sub", "price", "rsr", "d20", "ext", "chase", "on")} for w in (tt.get("plays") or [])[:10]],
                        "counter": [{k: w.get(k) for k in ("t", "sub", "price", "rsr", "d20", "off_hi")} for w in (tt.get("counter") or [])[:8]],
                        "ratio": {"d": (ra.get("dates") or [])[-90:], "r": [num(x, 4) for x in (ra.get("r") or [])[-90:]],
                                  "ma": [num(x, 4) for x in (ra.get("ma") or [])[-90:]]}}
    mac = []
    for m in D.get("macro") or []:
        mac.append({k: m.get(k) for k in ("key", "label", "unit", "src", "date", "last", "d1", "d5", "d30", "d90", "pos", "drives")}
                   | {"spark": [num(x, 4) for x in (m.get("spark") or [])[-90:]]})
    out["macro"] = mac
    return out


def _rotation(T):
    R = T["rotation"]
    F = R.get("flow") or {}
    MH = R.get("mhist") or {}

    def wins(series):
        out = {}
        for g, (net, vol, bp) in (series or {}).items():
            row = {}
            for w in (5, 15, 30, 90):
                row[w] = [int(sum(net[-w:])), int(sum(vol[-w:])), round(sum(bp[-w:]) / 100, 2)]
            out[g] = row
        return out
    spy = MH.get("spy") or []
    return {
        "state": R.get("state"), "lead_count": R.get("lead_count"), "more": R.get("more") or [],
        "ideas": [{"g": i["group"], "sector": i.get("sector"), "strength": i.get("strength"), "rk": i.get("s_rank"), "days": i.get("days"),
                   "r20": _pct(i.get("r20")), "why": [w.get("txt") for w in i.get("why") or []], "also": i.get("also") or [],
                   "spark": [num(x, 2) for x in ((i.get("spark") or {}).get("rel") or [])],
                   "stocks": [{k: s.get(k) for k in ("t", "price", "rsr", "zone", "ext", "trigger", "stop")} for s in (i.get("stocks") or [])[:6]]}
                  for i in R.get("ideas") or []],
        "avoid": [{"g": a["group"], "sector": a.get("sector"), "r20": _pct(a.get("r20")), "strength": a.get("strength"), "days": a.get("days")} for a in R.get("avoid") or []],
        "turning": [{"g": a["group"], "sector": a.get("sector"), "r20": _pct(a.get("r20")), "strength": a.get("strength"), "days": a.get("days")} for a in R.get("turning") or []],
        "bt": R.get("bt") or {},
        "flow": [{"g": r["g"], "sector": r.get("sector"), "tier": r.get("tier"), "x": r.get("x"), "y": r.get("y"),
                  "tail": r.get("tail") or [], "r20": _pct(r.get("r20")), "r5": _pct(r.get("r5")), "strength": r.get("strength")} for r in F.get("rows") or []],
        "tiers": F.get("tiers") or [], "fev": F.get("evidence") or {},
        "win": wins(MH.get("sub")), "spy": {w: round(sum(spy[-w:]) / 100, 2) for w in (5, 15, 30, 90)},
    }


def _timeline(T):
    d = T.get("timeline_dates") or []
    pack = lambda rows: [{"n": r["theme"], "sec": r.get("group"), "h": [None if x is None else int(round(x)) for x in (r.get("s_hist") or [])]}
                         for r in rows if r.get("s_hist")]
    return {"dates": d, "subs": pack(T.get("subthemes") or []), "themes": pack(T.get("themes") or [])}


def _earnings(T):
    E = T["earnings"]
    return {"window": E.get("window"), "spy": E.get("spy"), "evidence": E.get("evidence") or {},
            "rows": [{"g": r["g"], "sector": r.get("sector"), "dir": r.get("dir"), "n": r.get("n"), "members": r.get("members"),
                      "grp": _pct(r.get("grp")), "quiet": _pct(r.get("quiet")), "next": r.get("next") or [],
                      "reports": [{k: x.get(k) for k in ("t", "date", "dir", "gap", "move", "rvol", "since", "conf", "rs")} for x in r.get("reports") or []]}
                     for r in E.get("rows") or []]}


def _chapters():
    try:
        ch = json.loads((config.DOCS_DIR / "story.json").read_text()).get("chapters") or []
    except Exception:
        return []
    return [{"date": c["date"], "slot": c.get("slot"), "title": c.get("title") or "", "branch": c.get("branch"), "md": c.get("md") or ""}
            for c in ch if c.get("slot") != "data"][-30:]


def _stories():
    try:
        return json.loads((config.DOCS_DIR / "stories.json").read_text())
    except Exception:
        return None


def _cards():
    import re
    out = []
    for f in sorted((config.ROOT / "research").glob("R-*.md")) if hasattr(config, "ROOT") else sorted((Path(__file__).resolve().parents[1] / "research").glob("R-*.md")):
        txt = f.read_text()
        m = re.match(r"---\n(.*?)\n---\n(.*)", txt, re.S)
        if not m:
            continue
        meta = {}
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = re.sub(r"\s+#.*$", "", v).strip()
        body = m.group(2).strip()
        out.append({"id": meta.get("id") or f.stem, "title": meta.get("title"), "date": meta.get("date"), "status": meta.get("status"),
                    "kind": meta.get("kind"), "result": meta.get("result"), "integrated": meta.get("integrated"),
                    "layers": [x.strip() for x in (meta.get("layers") or "").strip("[]").split(",") if x.strip()],
                    "idea": body.split("\n\n")[0][:600]})
    return sorted(out, key=lambda c: c["date"] or "", reverse=True)


def _registry():
    f = Path(__file__).resolve().parents[1] / "data" / "layers.json"
    try:
        L = json.loads(f.read_text())
    except Exception:
        return None
    return [{k: x.get(k) for k in ("id", "name", "kind", "status", "where", "what", "affects_picks", "evidence")} for x in L.get("layers") or []]


def _lab(D, T):
    last = D["rows"][-1]
    W = T.get("washout") or {}
    cur = W.get("current") or {}
    V = T.get("vtilt") or {}
    X = T.get("dix") or {}
    L = T.get("leadership") or {}
    P = T.get("pulse") or {}
    return {
        "washout": {"state": W.get("state"), "date": cur.get("date"), "pullback": _pct(cur.get("pullback")), "t2108": cur.get("t2108_low"),
                    "sessions": cur.get("sessions"), "basket": _pct(cur.get("basket")), "all": _pct(cur.get("all")),
                    "picks": [p.get("t") for p in (cur.get("picks") or [])[:12]], "deep_n": W.get("deep_n"), "shallow_n": W.get("shallow_n")},
        "tilt": {k: V.get(k) for k in ("v", "pct", "tier", "post", "since", "unconfirmed")},
        "dix": {k: X.get(k) for k in ("s5", "norm", "dev", "dev_pct", "tier", "m5_pct")},
        "close": {"clv": num(last.get("clv_all"), 2), "absorb": num(last.get("absorb"), 1), "fade": num(last.get("fade"), 1)},
        "health": {"lead": L.get("lead"), "brk": L.get("brk"), "now": {k: (L.get("now") or {}).get(k) for k in ("net", "basket", "work", "bo", "bd")}},
        "pulse": {"long": P.get("long"), "short": P.get("short"), "ll": P.get("long_label"), "sl": P.get("short_label")},
        "registry": _registry(), "cards": _cards(),
    }


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
    put("boxes", _boxes, T)
    put("lineup", _lineup, T)
    put("life", _lifepage, T)
    put("market", _market, D, T)
    put("rotation", _rotation, T)
    put("timeline", _timeline, T)
    put("earnings", _earnings, T)
    put("chapters", _chapters)
    put("stories", _stories)
    put("lab", _lab, D, T)
    put("story", _story)
    try:
        I = D.get("intraday") or {}
        out["live"] = {"url": D.get("live_url"), "pulse": I.get("pulse") or {}, "etfs": I.get("sector_etfs") or {},
                       "vp": I.get("volume_profile") or []}
    except Exception:
        pass
    try:
        tt = T.get("thetrade") or {}
        out["trade"] = {"name": tt.get("name"), "state": tt.get("state"), "above": tt.get("above"), "below": tt.get("below")}
    except Exception:
        pass
    want = {p["t"] for p in out.get("picks") or []} | {x["t"] for x in out.get("lined") or []} | {s["t"] for s in out.get("setups") or []}
    for k in ("launch", "sow", "hve", "boxes", "lineup"):
        want |= {r["t"] for r in (out.get(k) or {}).get("rows") or []}
    for k in ("nuzzle", "flags", "dips"):
        want |= {r["t"] for r in (out.get("lineup") or {}).get(k) or []}
    for r in (out.get("life") or {}).get("rows") or []:
        want |= {p["t"] for p in r["picks"] + r["wait"]}
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
