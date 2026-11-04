"""Strongest stocks + "new leaders you haven't seen" (Nov 4, 2026).

Adam, Nov 1: "NTRA is super strong and not even in our universe ... these can't get missed." NTRA was in the data (RS 97, +99%
over 180 days, $580M a day) but no list showed it: the Oracle shows a top 15, the strongest list was cut at 40 and crowded by pinned
buyout stocks, and no setup fired. This module tags every strong stock with the lists it IS on, so the page can show one uncapped
"Strongest stocks" table and flag the ones on no list ("unseen"), with "new" = became a leader in the last 5 sessions.

Leader = liquid stock ($10+, $20M+/day, not a deal) with RS 90+ (lists.strong_all) or in the Oracle top 20 on 60 or 180 sessions.
New = RS crossed 95 in the last 5 sessions, or entered the Oracle top 20 (60D / 180D) in the last 5 sessions.
Descriptive only: nothing here is a buy signal or changes a pick.
"""

LIST_KEYS = {   # payload section -> label shown in the "On" column (the trade / pick lists Adam reads, not the big reference tables)
    "trade_setups": "Trade setups", "boxes": "Box trades", "sow": "Strength on Weakness", "launch": "Launch list",
    "polished": "Best setups", "dips": "Dip buys", "lifecycle": "Theme lifecycle picks", "leaders": "Leaders",
}
LIST_PARTS = {"bursts": "Momentum bursts", "anticipation": "Anticipation", "eps": "Episodic pivots", "strongest": "Strongest (top 40)"}
RS_NEW = 95
ORACLE_TOP = 20
ORACLE_SHOWN = 15


def _walk(v, tick, out):
    if isinstance(v, dict):
        for k, x in v.items():
            if k in ("t", "tk", "ticker") and isinstance(x, str) and x in tick:
                out.add(x)
            else:
                _walk(x, tick, out)
    elif isinstance(v, list):
        for x in v:
            if isinstance(x, str) and x in tick:
                out.add(x)
            else:
                _walk(x, tick, out)


def on_lists(T, tick):
    """{ticker: [list labels]} for the pick / setup lists in the payload."""
    found = {}
    def add(label, names):
        for t in names:
            found.setdefault(t, []).append(label)
    L = T.get("lists") or {}
    for k, label in LIST_PARTS.items():
        s = set()
        _walk((L.get(k) or [])[:40] if k == "strongest" else L.get(k), tick, s)
        add(label, s)
    for k, label in LIST_KEYS.items():
        s = set()
        _walk(T.get(k), tick, s)
        add(label, s)
    O = T.get("oracle") or {}
    shown = set()
    for k in ("d180", "d60", "d30", "d15", "d5"):
        shown.update((O.get("cohorts") or {}).get(k, [])[:ORACLE_SHOWN])
    add("Oracle top 15", shown & tick)
    return found


def build(T):
    stocks = {s["t"]: s for s in T.get("stocks") or []}
    strong = (T.get("lists") or {}).get("strong_all") or []
    O = T.get("oracle") or {}
    rall, prev = O.get("rall") or {}, O.get("prev20") or {}
    rows = {r["t"]: dict(r) for r in strong}
    rows_o = O.get("rows") or {}
    for key in ("d60", "d180"):
        for i, t in enumerate((rall.get(key) or [])[:ORACLE_TOP]):
            if t not in rows:
                s = stocks.get(t) or {}
                ro = rows_o.get(t) or {}
                rows[t] = {"t": t, "name": s.get("name") or ro.get("name", ""), "price": s.get("price"), "rsr": s.get("rsr"),
                           "adr": s.get("adr"), "off_hi": s.get("off_hi")}
    tick = set(stocks) | set(rows)
    lists = on_lists(T, tick)
    out = []
    for t, r in rows.items():
        s = stocks.get(t) or {}
        if s.get("deal"):
            continue
        ro = rows_o.get(t) or {}
        why, new = [], []
        rs = r.get("rsr") if r.get("rsr") is not None else s.get("rsr")
        if rs is not None and rs >= RS_NEW:
            why.append(f"RS {int(rs)}")
            d5 = s.get("rsr5")
            if d5 is not None and rs - d5 < RS_NEW:
                new.append(f"RS crossed {RS_NEW} this week")
        for key, lab in (("d60", "60D"), ("d180", "180D")):
            top = (rall.get(key) or [])[:ORACLE_TOP]
            if t in top:
                why.append(f"Oracle #{top.index(t) + 1} on {lab}")
                if prev.get(key) is not None and t not in prev[key]:
                    new.append(f"entered the Oracle top {ORACLE_TOP} on {lab} this week")
        r6 = ro.get("r") or []
        out.append({"t": t, "name": r.get("name") or s.get("name", ""), "sub": s.get("sub") or "", "price": r.get("price") or s.get("price"),
                    "rsr": rs, "rsr5": s.get("rsr5"), "adr": r.get("adr") if r.get("adr") is not None else s.get("adr"),
                    "off_hi": r.get("off_hi") if r.get("off_hi") is not None else s.get("off_hi"),
                    "dvol": r.get("dvol"), "d5": r.get("d5"), "d20": r.get("d20"), "d60": r.get("d60"),
                    "r180": r6[0] if len(r6) > 0 else None, "e50": r.get("e50"), "star": r.get("star"),
                    "why": why, "new": new, "on": sorted(set(lists.get(t, [])))})
    out.sort(key=lambda x: (-(x["rsr"] or 0), x["off_hi"] if x["off_hi"] is not None else -1))
    unseen = [x["t"] for x in out if not x["on"] and (x["why"])]
    return {"date": T.get("date"), "rows": out, "unseen": unseen, "new_unseen": [x["t"] for x in out if not x["on"] and x["new"]],
            "rules": {"rs_new": RS_NEW, "oracle_top": ORACLE_TOP, "lists": list(LIST_PARTS.values()) + list(LIST_KEYS.values()) + ["Oracle top 15"]}}
