"""Best Setups tab (Adam, Oct 25 2026: "a new tab for the polished trade setups... the early tickers in the top groups, the
leaders that already went but nuzzling into the EMAs or close to it, and those about to break a high tight flag").
Card R-2026-10-25-polished-setups, layer `polished`, info only (the headline picks stay the Launch picks).

Leading group = the stock's sub-theme is in the top third of sub-themes on 13-week return (launch.frames `grank`), as of
the PRIOR completed week in the backtest (no look-ahead) and the latest week live.
  early   - the Launch list curl / early names with the group point (built in the browser from DATA.themes.launch rows).
  nuzzle  - already went (9+ weekly closes over the 50 WEMA, weekly 9 > 21 > 50), daily uptrend (21 > 50 EMA, 50 rising),
            RS 70+, $20M+/day, and today's low came into the daily 9/21 EMA ribbon (within 0.25 ADR) while the close holds
            the 21 (no more than 0.5 ADR under) and isn't stretched (within 1 ADR of the 9). "close" = same stock, no touch
            yet, close within 1 ADR above the ribbon (untested).
            Test (Jan 2025 - Sep 2026, next open, stop 1 ADR, 20 sessions): leading +0.19R (n 2,201) vs other sub-themes +0.05R
            vs no sub-theme -0.13R; leading minus rest +0.19R, t 2.57, halves +0.23 / +0.15.
  flag    - high tight flag: a 30%+ leg into a high 3-15 sessions ago, flag no deeper than 25% and 3 ADR, last 5 sessions within
            2 ADR, close within 1 ADR of the high, above the 21 EMA, RS 70+, $20M+/day. Buy-stop at the high (pivot) within 5
            sessions, stop at the flag low, exit on a close under the 10 EMA after day 3 or 20 sessions.
            Flag low = lowest low SINCE the high (Oct 25 fix; the first cut used the whole 15-day window, which reached back into
            the leg). Test: leading +0.12R (n 754) vs other sub-themes +0.02R vs no sub-theme -0.13R; leading minus rest +0.26R,
            t 2.96, but leading halves +0.29 / -0.04 -> fails the both-halves rule: shown as unproven.
"""
import numpy as np
import pandas as pd

CFG = {"min_price": 5.0, "min_dvol": 20e6, "lead": 2 / 3, "went_wk": 8, "rs_min": 70, "touch": 0.25, "hold21": 0.5, "max9": 1.0,
       "close_adr": 1.0, "leg": 0.30, "flag_min": 3, "flag_max": 15, "depth": 0.25, "depth_adr": 3.0, "tight": 2.0, "near": 1.0,
       "base_back": 40, "fresh": 5, "flag_fresh": 10, "hold": 20}


def _r(x, n=2):
    return None if x is None or not np.isfinite(x) else round(float(x), n)


def frames(w, cols, F):
    """Daily frames for the nuzzle and flag rules. F = launch.frames output (weekly group rank, run, EMAs, RS)."""
    c, o, h, l, v = (w[k][cols] for k in ("c", "o", "h", "l", "v"))
    days = c.index
    adr = ((h / l) - 1).rolling(20, min_periods=15).mean()
    dvol = (c * v).rolling(20, min_periods=15).mean()
    e9, e10, e21, e50 = (c.ewm(span=n, adjust=False, min_periods=n).mean() for n in (9, 10, 21, 50))
    liq = (c >= CFG["min_price"]) & (dvol >= CFG["min_dvol"])
    gr_bt = F["grank"].shift(1).reindex(days, method="ffill")          # backtest: last COMPLETED week
    gr_live = F["grank"].reindex(days, method="ffill")                 # live: this week as it stands
    run = F["run"].reindex(days, method="ffill")
    stack = ((F["e9"] > F["e21"]) & (F["e21"] > F["e50"])).reindex(days, method="ffill").fillna(False).astype(bool)
    rs = F["rsd"].reindex(columns=cols)
    went = (run > CFG["went_wk"]) & stack
    up = (e21 > e50) & (e50 > e50.shift(10))
    rib_hi, rib_lo = np.maximum(e9, e21), np.minimum(e9, e21)
    base = liq & went & up & (rs >= CFG["rs_min"])
    touch = base & (l <= rib_hi + CFG["touch"] * adr * c) & (c >= e21 - CFG["hold21"] * adr * c) & (c <= e9 + CFG["max9"] * adr * c)
    first = touch & ~touch.shift(1, fill_value=False).rolling(CFG["fresh"], min_periods=1).max().astype(bool)
    close = base & ~touch & (c > rib_hi) & (c <= rib_hi + CFG["close_adr"] * adr * c)
    H = h.to_numpy()
    win = CFG["flag_max"]
    hh = h.rolling(win, min_periods=CFG["flag_min"]).max()
    pad = np.vstack([np.full((win - 1, H.shape[1]), -np.inf), np.nan_to_num(H, nan=-np.inf)])
    sw = np.lib.stride_tricks.sliding_window_view(pad, win, axis=0)          # (days, cols, win)
    am = np.argmax(sw, axis=2)
    since = pd.DataFrame(win - 1 - am, index=days, columns=cols)
    base_lo = l.shift(win).rolling(CFG["base_back"], min_periods=20).min()
    leg = hh / base_lo - 1
    padl = np.vstack([np.full((win - 1, H.shape[1]), np.inf), np.nan_to_num(l.to_numpy(), nan=np.inf)])
    swl = np.lib.stride_tricks.sliding_window_view(padl, win, axis=0)
    swl = np.where(np.arange(win)[None, None, :] >= am[:, :, None], swl, np.inf)   # the flag = from the high onward
    fl_lo = pd.DataFrame(swl.min(axis=2), index=days, columns=cols).replace(np.inf, np.nan)
    depth = 1 - fl_lo / hh
    tight = (h.rolling(5).max() / l.rolling(5).min() - 1) <= CFG["tight"] * adr
    flag = liq & (leg >= CFG["leg"]) & (since >= CFG["flag_min"]) & (since <= CFG["flag_max"]) & (depth <= CFG["depth"]) & \
        (depth <= CFG["depth_adr"] * adr) & tight & (c >= hh * (1 - CFG["near"] * adr)) & (c > e21) & (rs >= CFG["rs_min"])
    flag_first = flag & ~flag.shift(1, fill_value=False).rolling(CFG["flag_fresh"], min_periods=1).max().astype(bool)
    return {"c": c, "o": o, "h": h, "l": l, "days": days, "adr": adr, "dvol": dvol, "e9": e9, "e10": e10, "e21": e21, "e50": e50,
            "gr_bt": gr_bt, "gr_live": gr_live, "run": run, "rs": rs, "touch": touch, "first": first, "close": close, "flag": flag,
            "flag_first": flag_first, "hh": hh, "since": since, "leg": leg, "fl_lo": fl_lo, "depth": depth}


def _trades(P, mask, kind, spy, spyo):
    days = P["days"]
    C, O, H, L, E10, A = (P[k].to_numpy() for k in ("c", "o", "h", "l", "e10", "adr"))
    HH, FL, G = P["hh"].to_numpy(), P["fl_lo"].to_numpy(), P["gr_bt"].to_numpy()
    S, SO = spy.to_numpy(), spyo.to_numpy()
    M = mask.to_numpy()
    n, hold = len(days), CFG["hold"]
    rows = []
    for i in range(60, n - hold - 1):
        for j in np.flatnonzero(M[i]):
            a = i + 1
            if kind == "nuzzle":
                e, ent = O[a, j], a
                stop = e * (1 - A[i, j])
            else:
                piv, ent = HH[i, j], None
                for k in range(a, min(a + 5, n - hold)):
                    if H[k, j] >= piv:
                        ent, e = k, max(O[k, j], piv)
                        break
                if ent is None:
                    continue
                stop = FL[i, j]
            if not (np.isfinite(e) and e > stop > 0):
                continue
            risk = max(e - stop, 0.3 * A[i, j] * e)
            ex, px = min(ent + hold - 1, n - 1), None
            for k in range(ent, min(ent + hold, n)):
                if L[k, j] <= stop:
                    px, ex = (min(O[k, j], stop) if k > ent else stop), k
                    break
                if kind == "flag" and k >= ent + 3 and C[k, j] < E10[k, j]:
                    px, ex = C[k, j], k
                    break
            if px is None:
                px = C[ex, j]
            g = G[i, j]
            rows.append((days[i], "lead" if g >= CFG["lead"] else "none" if not np.isfinite(g) else "other", (px - e) / risk,
                         px / e - 1 - (S[ex] / SO[ent] - 1)))
    return pd.DataFrame(rows, columns=["date", "grp", "R", "xs"])


def evidence(P, w, bench="SPY"):
    out = {}
    for kind, m in (("nuzzle", P["first"]), ("flag", P["flag_first"])):
        X = _trades(P, m, kind, w["c"][bench], w["o"][bench])
        if not len(X):
            continue
        split = X["date"].sort_values().iloc[len(X) // 2]
        e = {"from": str(X["date"].min().date()), "to": str(X["date"].max().date())}
        for g in ("lead", "other", "none"):
            x = X[X["grp"] == g]
            e[g] = {"n": int(len(x)), "R": _r(x["R"].mean(), 3), "win": _r((x["R"] > 0).mean(), 3), "xs": _r(x["xs"].mean(), 4),
                    "h1": _r(x[x["date"] < split]["R"].mean(), 3), "h2": _r(x[x["date"] >= split]["R"].mean(), 3)}
        d = (X[X["grp"] == "lead"].groupby("date")["R"].mean() - X[X["grp"] != "lead"].groupby("date")["R"].mean()).dropna()
        e["edge"] = _r(d.mean(), 3)
        e["t"] = _r(d.mean() / (d.std(ddof=1) / np.sqrt(len(d))), 2) if len(d) > 2 and d.std(ddof=1) > 0 else None
        e["proven"] = bool(e["t"] is not None and e["t"] >= 2 and (e["lead"]["h1"] or 0) > 0 and (e["lead"]["h2"] or 0) > 0)
        out[kind] = e
    return out


def build(adjusted, universe, stocks=None, names=None, launch_F=None, subthemes=None, evidence_on=True):
    from . import strength, config, store, launch
    names = names or {}
    info = {r["t"]: r for r in (stocks or [])}
    w = strength.wide_all(adjusted)
    uni = set(universe)
    cols = [t for t in w["c"].columns if t in uni]
    if len(w["c"].index) < 250 or not cols or config.BENCHMARK not in w["c"]:
        return None
    if subthemes is None:
        subthemes = store.load_subthemes()
    F = launch_F if launch_F is not None else launch.frames(w, cols, subthemes, config.BENCHMARK)
    P = frames(w, cols, F)
    i = len(P["days"]) - 1
    sub_of = F["sub_of"]
    lead_now = P["gr_live"].iloc[i]
    # leading groups strip
    wi = len(F["wd"]) - 1
    c_w = F["W"]["c"]
    mem = {}
    for t in cols:
        if t in sub_of:
            mem.setdefault(sub_of[t], []).append(t)
    groups = []
    for g, m in mem.items():
        if len(m) < launch.CFG["grp_min"] or not np.isfinite(F["grank"][m[0]].iat[wi]):
            continue
        rk = float(F["grank"][m[0]].iat[wi])
        if rk < CFG["lead"]:
            continue
        r13 = float((c_w[m].iloc[wi] / c_w[m].iloc[wi - 13] - 1).clip(-0.9, 3).mean())
        groups.append({"sub": g, "rank": _r(rk, 3), "r13": _r(r13, 3), "n": len(m)})
    groups.sort(key=lambda x: -(x["r13"] or 0))
    lead_set = {g["sub"] for g in groups}

    def base_row(t, j):
        ir = info.get(t, {})
        a = P["adr"][t].iat[i]
        c = P["c"][t].iat[i]
        return {"t": t, "name": names.get(t, ir.get("name", "")), "sub": sub_of.get(t), "theme": (ir.get("themes") or [None])[0],
                "price": _r(c, 2), "adr": _r(a * 100, 1), "rs": _r(P["rs"][t].iat[i], 0), "grank": _r(lead_now.iat[j], 3),
                "e9": _r(P["e9"][t].iat[i], 2), "e21": _r(P["e21"][t].iat[i], 2), "e50": _r(P["e50"][t].iat[i], 2),
                "vs21": _r((c / P["e21"][t].iat[i] - 1) / a, 2) if a else None, "dvol": _r(P["dvol"][t].iat[i] / 1e6, 0),
                "wk_run": int(P["run"][t].iat[i]) if np.isfinite(P["run"][t].iat[i]) else None}
    nuz, flags = [], []
    T5 = P["touch"].iloc[i - CFG["fresh"] + 1:i + 1]
    for j, t in enumerate(cols):
        if sub_of.get(t) not in lead_set:
            continue
        tch, cls = bool(P["touch"][t].iat[i]), bool(P["close"][t].iat[i])
        recent = bool(T5[t].any())
        if tch or cls or recent:
            r = base_row(t, j)
            a, c = P["adr"][t].iat[i], P["c"][t].iat[i]
            r.update({"state": "nuzzle" if tch else "close" if cls else "touched",
                      "days_since": int(CFG["fresh"] - 1 - np.argmax(T5[t].to_numpy()[::-1])) if recent and not tch else 0,
                      "low": _r(P["l"][t].iat[i], 2), "stop": _r(c * (1 - a), 2)})
            if r["state"] == "touched" and not (c <= max(P["e9"][t].iat[i], P["e21"][t].iat[i]) * (1 + CFG["close_adr"] * a) and c >= P["e21"][t].iat[i] * (1 - CFG["hold21"] * a)):
                pass
            else:
                nuz.append(r)
        if bool(P["flag"][t].iat[i]):
            r = base_row(t, j)
            a, c, piv = P["adr"][t].iat[i], P["c"][t].iat[i], P["hh"][t].iat[i]
            r.update({"pivot": _r(piv, 2), "to_pivot": _r((piv / c - 1) / a, 2) if a else None, "stop": _r(P["fl_lo"][t].iat[i], 2),
                      "risk": _r(1 - P["fl_lo"][t].iat[i] / piv, 3), "leg": _r(P["leg"][t].iat[i], 3), "depth": _r(P["depth"][t].iat[i], 3),
                      "days": int(P["since"][t].iat[i]), "new": bool(P["flag_first"][t].iat[i])})
            flags.append(r)
    SO = {"nuzzle": 0, "touched": 1, "close": 2}
    nuz.sort(key=lambda r: (SO[r["state"]], -(r["grank"] or 0), -(r["rs"] or 0)))
    flags.sort(key=lambda r: (r["to_pivot"] if r["to_pivot"] is not None else 9, -(r["grank"] or 0)))
    out = {"date": str(P["days"][i].date()), "cfg": CFG, "groups": groups, "nuzzle": nuz, "flags": flags}
    if evidence_on:
        out["evidence"] = evidence(P, w, config.BENCHMARK)
    return out
