"""Market health: how the leaders are acting + are breakouts working (Adam, Oct 22 2026).

LEADERS = the top 10% of liquid stocks ($5+, $10M+/day) by RS Rating, taken as of the PREVIOUS session (no look-ahead).
  up10 / dn10   share of leader-days in the last 10 sessions that closed at a 20-day high / 20-day low (%)
  net           up10 - dn10
  a21 / a50     % of leaders above their 21 / 50-day EMA
  off           median leader's distance from its 63-day high
  basket        the leaders of 20 sessions ago: % now below their 50-day EMA (did the cracked leaders recover?)
BREAKOUTS across the whole liquid universe: a close beyond the prior 20-day high (low) out of a base (prior 20-day range
  <= 6 ADRs) on 1.3x the 50-day average volume. `bo` / `bd` daily counts, `ratio10` = breakouts / (breakouts + breakdowns)
  over 10 sessions. WORKING = breakouts from 5-25 sessions ago (outcome known): % still closing above their breakout level
  and their average return from the next open.

Evidence (recomputed every build from our ~2 years): each gauge split into fifths vs the next 20 sessions of the average
non-leader stock. Full window (Feb 2025-Sep 2026, 410 days): every gauge's rank correlation within about +-0.2, halves
disagree -> no forward edge either way. First cut (Nov 2025-Sep 2026, ~220 days): leaders NOT a leading indicator:
leader breakouts weakest -> rest +3.9% next 20 vs +0.6% when strongest; leader breakdowns heaviest -> +3.4%; same-week
correlation 0.67, one week later 0.26, reversing after 2-4 weeks. No bear market in the window: the classic "leaders crack
before a top" can't be tested yet. Information only; nothing here moves the picks.
"""
import numpy as np
import pandas as pd

CFG = {"min_price": 5.0, "min_dvol": 10e6, "lead_pct": 0.90, "win": 10, "hi": 20, "base_adr": 6.0, "vol_x": 1.3,
       "work_from": 5, "work_to": 25, "basket_ago": 20, "fwd": 20, "hist": 130, "list_n": 15,
       "warn_basket": 0.50, "watch_basket": 0.30, "work_good": 0.55, "work_bad": 0.40}


def _r(x, n=3):
    return None if x is None or not np.isfinite(x) else round(float(x), n)


def frames(w, cols, bench="SPY"):
    """Daily gauge history (DataFrame indexed by date) + the per-stock frames the live lists need."""
    from . import strength
    P = CFG
    c, h, l, v, o = (w[k][cols] for k in ("c", "h", "l", "v", "o"))
    dv = (c * v).rolling(20, min_periods=15).mean()
    liq = (c >= P["min_price"]) & (dv >= P["min_dvol"])
    rs = strength.rs_raw(c).where(liq).rank(axis=1, pct=True)
    L = (rs.shift(1) >= P["lead_pct"]) & liq
    R = (rs.shift(1) < P["lead_pct"]) & liq
    hi = h.shift().rolling(P["hi"], min_periods=15).max()
    lo = l.shift().rolling(P["hi"], min_periods=15).min()
    adr = (h / l).rolling(20, min_periods=15).mean() - 1
    base = (hi / lo - 1) <= P["base_adr"] * adr
    v50 = v.shift().rolling(50, min_periods=30).mean()
    loud = v >= P["vol_x"] * v50
    up, dn = c > hi, c < lo
    e21 = c.ewm(span=21, adjust=False).mean()
    e50 = c.ewm(span=50, adjust=False).mean()
    D = pd.DataFrame(index=c.index)
    nL = L.sum(axis=1).rolling(P["win"]).sum()
    D["up10"] = (up & L).sum(axis=1).rolling(P["win"]).sum() / nL * 100
    D["dn10"] = (dn & L).sum(axis=1).rolling(P["win"]).sum() / nL * 100
    D["net"] = D["up10"] - D["dn10"]
    D["a21"] = (c > e21).where(L).mean(axis=1) * 100
    D["a50"] = (c > e50).where(L).mean(axis=1) * 100
    D["off"] = (c / h.rolling(63, min_periods=40).max() - 1).where(L).median(axis=1)
    Lb = L.shift(P["basket_ago"]).fillna(False).astype(bool)
    D["basket"] = (c < e50).where(Lb & liq).mean(axis=1) * 100
    bo = liq & base & up & loud
    bd = liq & base & dn & loud
    D["bo"] = bo.sum(axis=1)
    D["bd"] = bd.sum(axis=1)
    s_bo, s_bd = D["bo"].rolling(P["win"]).sum(), D["bd"].rolling(P["win"]).sum()
    D["ratio10"] = s_bo / (s_bo + s_bd).replace(0, np.nan)
    # breakouts working: for each day d, breakouts from d-25 .. d-5 sessions; above their level at d? return since next open?
    lvl = hi.where(bo)
    ent = o.shift(-1).where(bo)
    C = c.to_numpy()
    LV, EN = lvl.to_numpy(), ent.to_numpy()
    n = len(c.index)
    work, wret, wn = np.full(n, np.nan), np.full(n, np.nan), np.zeros(n)
    for i in range(P["work_to"], n):
        a, b = i - P["work_to"], i - P["work_from"] + 1
        lv, en = LV[a:b], EN[a:b]
        m = np.isfinite(lv) & np.isfinite(en)
        if m.sum() < 10:
            continue
        cc = np.broadcast_to(C[i], lv.shape)[m]
        ok = np.isfinite(cc)
        work[i] = np.mean(cc[ok] > lv[m][ok])
        wret[i] = np.mean(np.clip(cc[ok] / en[m][ok] - 1, -0.9, 3))
        wn[i] = ok.sum()
    D["work"], D["wret"], D["wn"] = work * 100, wret, wn
    # forward outcome for the evidence: average non-leader stock, next 20 sessions (only known for older dates)
    D["rest_fwd"] = (c.shift(-P["fwd"]) / c - 1).where(R).clip(-0.9, 3).mean(axis=1)
    if bench in w["c"]:
        s = w["c"][bench]
        D["spy_fwd"] = s.shift(-P["fwd"]) / s - 1
    return D, {"c": c, "h": h, "l": l, "v": v, "v50": v50, "liq": liq, "rs": rs, "L": L, "hi": hi, "lo": lo,
               "e21": e21, "e50": e50, "up": up, "dn": dn, "loud": loud}


def evidence(D, warm=70):
    """Each gauge in fifths vs the next 20 sessions of the average non-leader stock (and SPY). Per-day, both halves."""
    X = D.iloc[warm:].dropna(subset=["rest_fwd"])
    out = {"from": X.index[0].strftime("%Y-%m-%d") if len(X) else None, "to": X.index[-1].strftime("%Y-%m-%d") if len(X) else None,
           "n": int(len(X)), "fwd": CFG["fwd"], "rows": {}}
    for k in ("net", "dn10", "a50", "basket", "ratio10", "work"):
        x = X[[k, "rest_fwd", "spy_fwd"]].dropna() if "spy_fwd" in X else X[[k, "rest_fwd"]].dropna()
        if len(x) < 60:
            continue
        q = pd.qcut(x[k].rank(method="first"), 5, labels=False)
        h = len(x) // 2
        ic = lambda z: _r(z[k].rank().corr(z["rest_fwd"].rank()), 2)   # Spearman without scipy (not installed in CI)
        out["rows"][k] = {"q": [_r(x[k][q == i].mean(), 1) for i in range(5)],
                          "rest": [_r(x["rest_fwd"][q == i].mean(), 4) for i in range(5)],
                          "spy": [_r(x["spy_fwd"][q == i].mean(), 4) for i in range(5)] if "spy_fwd" in x else None,
                          "ic": ic(x), "h1": ic(x.iloc[:h]), "h2": ic(x.iloc[h:]), "n": int(len(x)),
                          "edges": [_r(float(x[k].quantile(p)), 3) for p in (0.2, 0.4, 0.6, 0.8)]}
    out["all_rest"] = _r(X["rest_fwd"].mean(), 4)
    return out


def _verdict(now):
    P = CFG
    lead, brk = [], []
    if now["net"] is not None:
        if now["net"] >= 5:
            lead = ["good", "Leaders breaking out"]
        elif now["net"] <= -5:
            lead = ["bad", "Leaders cracking"]
        else:
            lead = ["mid", "Leaders stalling"]
    if now["basket"] is not None and now["basket"] >= P["warn_basket"] * 100:
        lead = ["bad", "Leaders not recovering"]
    w = now.get("work")
    if w is not None:
        brk = ["good", "Breakouts working"] if w >= P["work_good"] * 100 and (now.get("wret") or 0) > 0 else \
              ["bad", "Breakouts failing"] if w <= P["work_bad"] * 100 else ["mid", "Breakouts mixed"]
    return lead, brk


def build(adjusted, universe, stocks=None, names=None):
    from . import config, strength
    names = names or {}
    info = {s["t"]: s for s in (stocks or [])}
    w = strength.wide_all(adjusted)
    uni = set(universe)
    cols = [t for t in w["c"].columns if t in uni]
    if len(w["c"].index) < 80 or not cols:
        return None
    D, F = frames(w, cols, config.BENCHMARK)
    last = D.iloc[-1]
    P = CFG
    g = lambda k: None if not np.isfinite(last.get(k, np.nan)) else float(last[k])
    now = {k: _r(g(k), 3 if k in ("off", "wret", "ratio10") else 1) for k in ("up10", "dn10", "net", "a21", "a50", "off", "basket", "ratio10", "work", "wret")}
    now.update({"bo": int(last["bo"]), "bd": int(last["bd"]), "wn": int(last["wn"]), "n_lead": int(F["L"].iloc[-1].sum())})
    for k in ("net", "basket", "work", "a50"):                       # 10 sessions ago, for "is it getting better or worse"
        x = D[k].iloc[-11] if len(D) > 11 else np.nan
        now[k + "_10"] = _r(float(x), 1) if np.isfinite(x) else None
    lead, brk = _verdict(now)
    # live lists: leaders (as of 5 sessions ago, so a crack doesn't drop them from the list) cracking / breaking out
    c, liq, rs = F["c"], F["liq"], F["rs"]
    Lnow = (rs.iloc[-6] >= P["lead_pct"]) & liq.iloc[-1]
    rows = []
    for t in Lnow[Lnow].index:
        cl = c[t]
        lo5 = bool(F["dn"][t].iloc[-5:].any())
        u50 = cl.iloc[-1] < F["e50"][t].iloc[-1]
        x50 = u50 and (cl.iloc[-6:-1] >= F["e50"][t].iloc[-6:-1]).any()
        hi5 = bool(F["up"][t].iloc[-5:].any())
        v1 = float(F["v"][t].iloc[-1] / F["v50"][t].iloc[-1]) if F["v50"][t].iloc[-1] else None
        state = "crack" if (lo5 or x50) else "under50" if u50 else "breakout" if hi5 else "holding"
        s = info.get(t, {})
        rows.append({"t": t, "name": s.get("name") or names.get(t, ""), "state": state, "rsr": _r(rs[t].iloc[-1] * 99, 0),
                     "price": _r(cl.iloc[-1], 2), "d5": _r(cl.iloc[-1] / cl.iloc[-6] - 1, 4), "vs50": _r(cl.iloc[-1] / F["e50"][t].iloc[-1] - 1, 4),
                     "off": _r(cl.iloc[-1] / F["h"][t].iloc[-63:].max() - 1, 4), "vx": _r(v1, 2),
                     "loud": bool(F["loud"][t].iloc[-5:][(F["dn"][t] | (cl < F["e50"][t])).iloc[-5:]].any()),
                     "sub": s.get("sub"), "theme": (s.get("themes") or [None])[0]})
    order = {"crack": 0, "under50": 1, "breakout": 2, "holding": 3}
    rows.sort(key=lambda r: (order[r["state"]], -(r["rsr"] or 0)))
    H = D.iloc[-P["hist"]:]
    hist = {"dates": [d.strftime("%Y-%m-%d") for d in H.index]}
    for k in ("net", "up10", "dn10", "a50", "basket", "bo", "bd", "ratio10", "work"):
        hist[k] = [_r(float(x), 3 if k == "ratio10" else 1) if np.isfinite(x) else None for x in H[k]]
    return {"date": c.index[-1].strftime("%Y-%m-%d"), "now": now, "lead": lead, "brk": brk, "hist": hist,
            "rows": rows, "counts": {k: sum(r["state"] == k for r in rows) for k in order}, "cfg": P, "evidence": evidence(D)}
