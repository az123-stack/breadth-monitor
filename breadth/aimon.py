"""AI Monetizers, kept honest by the market (Oct 29, 2026; Adam: "a lot of these are not monetizing AI ... they're trying but it's
not coming in yet" after NOW −27%, GOOGL −12%, AMZN −5% on their Oct 29 reports, while BOX is rewarded).

data/aimon.json `pool` = companies with a documented AI product line that brings in revenue (one-line note + source each). Code
decides who is IN the theme "AI & ROBOTICS - AI Monetizers" from the market's verdict on each name's LAST big reaction day
(earnings-style: gap ≥ max(3%, 1 ADR) on 2.5×+ the 50-day volume, `earnings.frames`) within the last `win` sessions:
  IN   = up on the day, or 3 sessions later still above the pre-reaction close
  OUT  = down on the day and (fewer than 3 sessions since, or still under the pre-reaction close 3 sessions later)
  no reaction in the window → keeps its previous status (`status` in aimon.json)
`apply()` rewrites the theme's rows in data/themes.csv, records the status, and appends every change to data/aimon_log.csv; the
story fact sheet (`story.aimon_lines`) flags additions / removals of the last 2 sessions so the chapter says so.
`candidates()` = stocks OUTSIDE the pool in software / internet / AI groups that the market just rewarded (same rule, day ≥ +1
ADR and held 3 sessions) → the writer / Claude checks whether AI drove it before adding them to the pool.
"""
import json

import numpy as np
import pandas as pd

from . import config, store

THEME = "AI & ROBOTICS - AI Monetizers"
FILE = config.DATA_DIR / "aimon.json"
LOG = config.DATA_DIR / "aimon_log.csv"
CFG = dict(win=70, hold=3, px=5.0, cand_groups=("Software", "AI Infrastructure"),
           cand_subs=("Hyperscalers", "AI Applications & Platforms", "Data & Observability", "Cybersecurity Platforms",
                      "Identity & Security Tools", "Cloud Communications", "Business Services & Data", "Digital Advertising",
                      "Internet & Digital Ads", "Defense Tech & Electronics"))


def load():
    try:
        return json.loads(FILE.read_text())
    except Exception:
        return {"pool": {}, "status": {}}


def _frames(adjusted, tickers):
    from . import earnings as E
    W = E._wide(adjusted, sorted(tickers))
    return E.frames(W)


def verdicts(F, tickers, win=CFG["win"], hold=CFG["hold"]):
    """Ticker -> last big reaction in the window: {date, gap, day, hold3, since, status in/out, pending} (None if none)."""
    R, c, mv, gp = F["react"], F["c"], F["move"], F["gap"]
    n = len(c)
    out = {}
    for t in tickers:
        if t not in R.columns:
            continue
        r = R[t].iloc[-win:].dropna()
        if not len(r):
            out[t] = None
            continue
        d = r.index[-1]
        i = c.index.get_loc(d)
        pc = c[t].iloc[i - 1]
        day = float(mv[t].iloc[i])
        h3 = float(c[t].iloc[i + hold] / pc - 1) if i + hold < n else None
        since = float(c[t].iloc[-1] / pc - 1)
        keep = day > 0 or (h3 is not None and h3 > 0)
        out[t] = {"date": str(d.date()), "gap": round(float(gp[t].iloc[i]), 4), "day": round(day, 4),
                  "hold3": None if h3 is None else round(h3, 4), "since": round(since, 4), "in": bool(keep),
                  "pending": h3 is None}
    return out


def why(v):
    if not v:
        return "no big reaction lately"
    pc = lambda x: f"{x * 100:+.1f}%"
    s = f"{v['date']}: gap {pc(v['gap'])}, day {pc(v['day'])}"
    s += f", 3 sessions later {pc(v['hold3'])}" if v["hold3"] is not None else " (3-session check pending)"
    return s


def candidates(F, pool, subthemes, stocks=None, hold=CFG["hold"]):
    """Rewarded reactions (day ≥ +1 ADR and held 3 sessions) outside the pool, in software / internet / AI groups."""
    sd = subthemes if subthemes is not None else store.load_subthemes()
    ok = sd if CFG.get("cand_all", True) else sd[sd["group"].isin(CFG["cand_groups"]) | sd["subtheme"].isin(CFG["cand_subs"])]
    sub_of = dict(zip(ok["ticker"], ok["subtheme"]))
    L = load()
    skip = set(pool) | set(L.get("exclude") or {}) | set(L.get("not_ai") or {})
    V = verdicts(F, [t for t in sub_of if t not in skip])
    rs = {s["t"]: s.get("rsr") for s in (stocks or [])}
    out = []
    for t, v in V.items():
        if not v or v["pending"] or v["hold3"] is None or v["hold3"] <= 0:
            continue
        a = F["adr"][t].loc[pd.Timestamp(v["date"])]
        if not (np.isfinite(a) and v["day"] >= a) or F["c"][t].iloc[-1] < CFG["px"]:
            continue
        d = F["c"].index.get_loc(pd.Timestamp(v["date"]))
        tail = F["c"][t].iloc[d + 1:]
        pinned = bool(v["day"] >= 0.15 and len(tail) >= 3 and (tail.max() / tail.min() - 1) <= 0.02)   # deal stocks stop moving
        out.append({"t": t, "sub": sub_of[t], "rsr": rs.get(t), **v, "why": why(v) + (" · PINNED since: possible takeover" if pinned else ""),
                    "pinned": pinned})
    out.sort(key=lambda r: -r["since"])
    return out


SCORE_W = dict(share=0.4, growth=0.4, usd=0.2)   # AI exposure (share of revenue), AI growth, AI $ size


def scorecard(pool, status=None):
    """Rank pool names on disclosed AI numbers (pool[t]["ai"] = {usd $B a year, share of revenue, growth y/y, basis, asof, src}).
    Each component = percentile among names that disclose it; missing components are left out and the weights renormalised;
    no growth figure or no size figure → no score ("not enough disclosed"). Size uses log($)."""
    rows = []
    for t, p in pool.items():
        a = p.get("ai") or {}
        rows.append({"t": t, "usd": a.get("usd"), "share": a.get("share"), "growth": a.get("growth"), "basis": a.get("basis", ""),
                     "asof": a.get("asof", ""), "src": a.get("src") or p.get("source", ""), "note": p.get("note", ""),
                     "in": bool((status or {}).get(t, {}).get("in", True)), "why": (status or {}).get(t, {}).get("why", "")})
    def pct(k, f=lambda x: x):
        v = sorted(f(r[k]) for r in rows if r[k] is not None)
        for r in rows:
            r["p_" + k] = None if r[k] is None else (sum(x <= f(r[k]) for x in v) - 0.5) / len(v) * 100
    pct("share"); pct("growth"); pct("usd", lambda x: np.log(max(x, 1e-3)))
    for r in rows:
        parts = [(SCORE_W[k], r["p_" + k]) for k in SCORE_W if r["p_" + k] is not None]
        r["n"] = len(parts)
        ok = r["p_growth"] is not None and (r["p_share"] is not None or r["p_usd"] is not None)   # needs growth AND a size
        r["score"] = round(sum(w * x for w, x in parts) / sum(w for w, _ in parts)) if ok else None
        r["tier"] = (None if r["score"] is None else "leader" if r["score"] >= 60 else "contender" if r["score"] >= 45 else "early")
    rows.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0), -(r["p_growth"] or 0)))
    for i, r in enumerate(rows):
        r["rank"] = i + 1 if r["score"] is not None else None
    return rows


def apply(adjusted, theme_data=None, write=True, today=None):
    """Recompute who is IN, rewrite the theme rows in data/themes.csv and log changes. Returns the payload for the page/story."""
    P = load()
    pool = P.get("pool") or {}
    if not pool:
        return None
    F = _frames(adjusted, set(pool) | set(store.load_subthemes()["ticker"]))
    V = verdicts(F, list(pool))
    prev = P.get("status") or {}
    status, changes = {}, []
    date = today or str(F["c"].index[-1].date())
    manual = P.get("manual") or {}     # {t: {in, date, why}}: a hand call that holds until a newer big reaction
    for t in pool:
        v = V.get(t)
        m = manual.get(t)
        if m and (not v or v["date"] <= m.get("date", "")):
            v = None
            now = bool(m.get("in"))
        else:
            now = v["in"] if v else bool(prev.get(t, {}).get("in", True))
        status[t] = {"in": now, "why": (m.get("why") if m and v is None else why(v)), **({k: v[k] for k in ("date", "day", "hold3", "since", "pending")} if v else {})}
        was = prev.get(t, {}).get("in")
        if was is not None and was != now:
            changes.append({"date": date, "t": t, "action": "add" if now else "remove", "why": why(v), "note": pool[t].get("note", "")})
    stocks = (theme_data or {}).get("stocks") or []
    cands = candidates(F, pool, None, stocks)
    if write:
        T = pd.read_csv(config.THEMES_FILE, dtype=str).fillna("")
        T = T[T["theme"] != THEME]
        members = [t for t in pool if status[t]["in"]]
        T = pd.concat([T, pd.DataFrame({"theme": THEME, "ticker": members, "role": "member"})])
        T.to_csv(config.THEMES_FILE, index=False)
        P["status"] = status
        P["updated"] = date
        FILE.write_text(json.dumps(P, indent=1, ensure_ascii=False) + "\n")
        if changes:
            old = pd.read_csv(LOG, dtype=str) if LOG.exists() else pd.DataFrame()
            pd.concat([old, pd.DataFrame(changes)]).to_csv(LOG, index=False)
    log = pd.read_csv(LOG, dtype=str).fillna("").to_dict("records") if LOG.exists() else []
    return {"date": date, "theme": THEME, "score": scorecard(pool, status), "weights": SCORE_W, "members": [t for t in pool if status[t]["in"]],
            "out": [t for t in pool if not status[t]["in"]], "status": status,
            "notes": {t: pool[t].get("note", "") for t in pool}, "changes": changes, "log": log[-30:], "candidates": cands[:15]}


if __name__ == "__main__":
    b = store.load_bars()
    X = apply(store.apply_splits(b, store.load_splits()), write=False)
    print("IN:", " ".join(X["members"]))
    print("OUT:", " ".join(f"{t} ({X['status'][t]['why']})" for t in X["out"]))
    print("AI scorecard:")
    for r in X["score"]:
        f = lambda v, m=100: "–" if v is None else f"{v * m:.0f}"
        print(f"  {r['rank'] or '-':>3} {r['t']:6} score {r['score'] if r['score'] is not None else '–':>3} ({r['tier']}) $ {r['usd'] or '–'}B "
              f"share {f(r['share'])}% growth {f(r['growth'])}% {'IN' if r['in'] else 'out'}  {r['basis'][:60]}")
    print("candidates:")
    for c in X["candidates"]:
        print(f"  {c['t']:6} {c['sub'][:28]:28} RS {c['rsr']}  {c['why']}  since {c['since'] * 100:+.0f}%")
