"""Stair steps: stocks and sub-themes pulling into their 9/21 EMAs and stepping up together (Adam, Oct 24, 2026).

Adam noticed Cybersecurity Platforms (ZS, NTSK, CHKP, CRWD...) breaking out of their latest stair step on
Oct 22-23, 2026 and wanted to see it across sessions: (a) stocks nuzzled into their EMAs, (b) stocks breaking the
top of their last short-term step, (c) whole groups positioned together.

Stock states (daily bars, last close; ADR = 20-day average high/low range):
- uptrend   21 EMA above the 50 EMA and the 50 EMA rising over 10 sessions
- nuzzle    uptrend + closed 2+ ADRs above the 21 EMA within 20 sessions (it stepped up first) + today's low reached
            into the 9/21 ribbon (low <= upper ribbon + 0.5 ADR), close no more than 1.5 ADR under the 21 EMA and no
            more than 1 ADR above the ribbon
- lifting   nuzzled in the 5 sessions before today, today closes above the 9 EMA and above yesterday's high
- step break close above the highest high of the prior 15 sessions after a nuzzle within those 15 sessions
            (first such close in 5 sessions)
Group (sub-theme, 4+ liquid members $5+ and $10M+/day):
- setting up together   50%+ of members nuzzled within the last 5 sessions and 50%+ in an uptrend
- stepping up together  40%+ of members lifted or broke a step in the last 3 sessions, after 40%+ were nuzzled
                        3 sessions earlier
Evidence (Oct 24, 2026 study, card R-2026-10-24-stair-steps; recomputed each build): on their own neither state
beat the average group (median below it). Inside groups already in the top 30% on 60-day return, setting up added
about +2% over 20 sessions vs other leading groups (t ~1.9, both halves positive); stepping up about +1.7% (t ~2.0);
pure step breaks with no pullback first lagged. Information only.
"""
import numpy as np
import pandas as pd

CFG = {"min_price": 5.0, "min_dvol": 10e6, "min_members": 4, "stretch_adr": 2.0, "ribbon_adr": 0.5,
       "under21_adr": 1.5, "above_adr": 1.0, "nuz_days": 5, "step_days": 15, "recent": 3,
       "setting": 0.5, "stepping": 0.4, "set_before": 0.4, "leader_pct": 0.7, "ext_adr": 2.0,
       "hist": 15, "first_gap": 10, "fwd": (10, 20), "warm": 80}


def frames(c, h, l, v):
    """Per-stock boolean frames + helper levels. All inputs: DataFrames date x ticker (split-adjusted)."""
    C = CFG
    e9 = c.ewm(span=9, adjust=False, min_periods=9).mean()
    e21 = c.ewm(span=21, adjust=False, min_periods=21).mean()
    e50 = c.ewm(span=50, adjust=False, min_periods=50).mean()
    adr = (h / l - 1).rolling(20, min_periods=15).mean()
    A = adr * c
    dv = (c * v).rolling(50, min_periods=40).mean()
    liq = (c >= C["min_price"]) & (dv >= C["min_dvol"])
    zone_hi = np.maximum(e9, e21)
    up = (e21 > e50) & (e50 > e50.shift(10))
    stretched = ((c - e21) / A).rolling(20, min_periods=10).max() >= C["stretch_adr"]
    nuz = up & stretched & (l <= zone_hi + C["ribbon_adr"] * A) & (c >= e21 - C["under21_adr"] * A) & (c <= zone_hi + C["above_adr"] * A)
    roll = lambda X, n: X.astype(float).rolling(n, min_periods=1).max().astype(bool)
    nuz5 = roll(nuz, C["nuz_days"])
    lift = roll(nuz, C["nuz_days"]).shift(1, fill_value=False) & (c > e9) & (c > h.shift(1)) & up
    step = h.shift(1).rolling(C["step_days"], min_periods=10).max()
    brk_raw = (c > step) & up & roll(nuz, C["step_days"]).shift(1, fill_value=False)
    brk = brk_raw & ~roll(brk_raw, 5).shift(1, fill_value=False)
    return {"e9": e9, "e21": e21, "e50": e50, "A": A, "adr": adr, "liq": liq, "up": up, "nuz": nuz, "nuz5": nuz5,
            "lift": lift, "brk": brk, "step": step, "lift3": roll(lift, C["recent"]), "brk3": roll(brk, C["recent"])}


def group_frames(c, S, members):
    """Shares of liquid members in each state, per sub-theme; equal-weight group index. Returns dict of frames."""
    ret = c.pct_change(fill_method=None).clip(-0.5, 0.5)
    out = {k: {} for k in ("n", "up", "nuz", "nuz5", "lift3", "brk3", "idx")}
    for g, m in members.items():
        m = [t for t in m if t in c.columns]
        if len(m) < CFG["min_members"]:
            continue
        L = S["liq"][m]
        n = L.sum(axis=1)
        nn = n.where(n >= CFG["min_members"])
        out["n"][g] = n
        for k in ("up", "nuz", "nuz5", "lift3", "brk3"):
            out[k][g] = (S[k][m] & L).sum(axis=1) / nn
        out["idx"][g] = (1 + ret[m].where(L).mean(axis=1).fillna(0)).cumprod()
    return {k: pd.DataFrame(v) for k, v in out.items()}


def states(G):
    C = CFG
    lifted = (G["lift3"] + G["brk3"]).clip(upper=1)
    setting = (G["nuz5"] >= C["setting"]) & (G["up"] >= 0.5)
    stepping = (lifted >= C["stepping"]) & (G["nuz5"].shift(C["recent"]) >= C["set_before"])
    breaks = (G["brk3"] >= C["stepping"]) & (G["nuz5"].shift(C["recent"]) >= C["set_before"])
    return setting.fillna(False), stepping.fillna(False), breaks.fillna(False), lifted


def first(X, gap=None):
    gap = gap or CFG["first_gap"]
    return X & ~X.astype(float).rolling(gap, min_periods=1).max().shift(1).fillna(0).astype(bool)


def evidence(G, spy, setting, stepping, breaks):
    """Group vs SPY over the next 10/20 sessions (from the next close) on the first day of each state, against the
    average group and against the average top-30% (60-day) group on the same dates. Date-paired t, halves."""
    idx = G["idx"]
    dates = idx.index
    if len(dates) < CFG["warm"] + 40:
        return None
    ok = dates[CFG["warm"]:]
    mid = ok[len(ok) // 2]
    r60 = (idx / idx.shift(60)).rank(axis=1, pct=True)
    top = (r60 >= CFG["leader_pct"]).loc[ok]
    out = {"from": ok[0].strftime("%Y-%m-%d"), "to": dates[-1].strftime("%Y-%m-%d")}

    def stat(S, F, base):
        ev = F.where(S).stack().dropna()
        if len(ev) < 10:
            return {"n": int(len(ev))}
        ex = ev - base.reindex(ev.index.get_level_values(0)).to_numpy()
        dm = ex.groupby(level=0).mean()
        sd = dm.std()
        t = float(dm.mean() / (sd / np.sqrt(len(dm)))) if len(dm) > 2 and sd > 0 else None
        r = lambda x: None if x is None or not np.isfinite(x) else round(float(x), 4)
        return {"n": int(len(ev)), "dates": int(len(dm)), "ret": r(ev.mean()), "ex": r(ex.mean()), "med": r(ex.median()),
                "win": r((ex > 0).mean()), "t": None if t is None else round(t, 2),
                "h1": r(dm[dm.index < mid].mean()), "h2": r(dm[dm.index >= mid].mean())}

    for hz in CFG["fwd"]:
        F = ((idx.shift(-hz - 1) / idx.shift(-1) - 1).sub(spy.shift(-hz - 1) / spy.shift(-1) - 1, axis=0)).loc[ok]
        base, tbase = F.mean(axis=1), F.where(top).mean(axis=1)
        o = {}
        for k, X in (("setting", setting), ("stepping", stepping), ("breaks", breaks)):
            E = first(X).loc[ok]
            o[k] = {"all": stat(E, F, base), "leaders": stat(E & top, F, tbase)}
        o["leaders_vs_avg"] = round(float((tbase - base).mean()), 4) if tbase.notna().any() else None
        out[f"d{hz}"] = o
    return out


def build(adjusted, stocks=None, names=None, subthemes=None, with_evidence=True):
    """Payload for DATA.themes.stairs."""
    from . import config, store, strength
    names = names or {}
    info = {r["t"]: r for r in (stocks or [])}
    st = subthemes if subthemes is not None else store.load_subthemes() if hasattr(store, "load_subthemes") else pd.read_csv("data/subthemes.csv")
    w = strength.wide_all(adjusted)
    c, h, l, v = w["c"], w["h"], w["l"], w["v"]
    if len(c.index) < 120:
        return None
    members = {g: list(dict.fromkeys(s.ticker)) for g, s in st.groupby("subtheme")}
    parent = {g: s["group"].iloc[0] for g, s in st.groupby("subtheme")} if "group" in st.columns else {}
    S = frames(c, h, l, v)
    G = group_frames(c, S, members)
    if G["idx"].empty:
        return None
    setting, stepping, breaks, lifted = states(G)
    dates = c.index
    d = dates[-1]
    bench = config.BENCHMARK
    spy = c[bench] if bench in c.columns else None
    idx = G["idx"]
    r60 = (idx / idx.shift(60)).rank(axis=1, pct=True)
    rel5 = (idx / idx.shift(5) - 1).sub((spy / spy.shift(5) - 1) if spy is not None else 0, axis=0)
    rel20 = (idx / idx.shift(20) - 1).sub((spy / spy.shift(20) - 1) if spy is not None else 0, axis=0)
    rnd = lambda x, k=2: None if x is None or not np.isfinite(x) else round(float(x), k)
    H = CFG["hist"]

    def since(X, g):
        s = X[g].to_numpy()[::-1]
        n = 0
        for x in s:
            if not x:
                break
            n += 1
        return n

    def stock_state(t):
        if not bool(S["up"].at[d, t]):
            return "down"
        if bool(S["brk3"].at[d, t]):
            return "break"
        if bool(S["lift3"].at[d, t]):
            return "lift"
        if bool(S["nuz5"].at[d, t]):
            return "nuzzle"
        a = S["A"].at[d, t]
        if np.isfinite(a) and a > 0 and (c.at[d, t] - S["e21"].at[d, t]) / a > CFG["ext_adr"]:
            return "extended"
        return "riding"

    rows = []
    for g in idx.columns:
        n = G["n"].at[d, g]
        if not np.isfinite(n) or n < CFG["min_members"]:
            continue
        status = "stepping" if stepping.at[d, g] else "setting" if setting.at[d, g] else "none"
        mem = []
        for t in members[g]:
            if t not in c.columns or not bool(S["liq"].at[d, t]):
                continue
            a = S["A"].at[d, t]
            cl = c.at[d, t]
            ago = None
            for k in ("brk", "lift"):
                col = S[k][t].to_numpy()[-CFG["recent"]:]
                if col.any():
                    j = int(np.where(col)[0][-1])
                    ago = CFG["recent"] - 1 - j if ago is None else min(ago, CFG["recent"] - 1 - j)
            stp = S["step"].at[d, t]
            mem.append({"t": t, "name": names.get(t, ""), "state": stock_state(t), "ago": ago,
                        "d9": rnd((cl - S["e9"].at[d, t]) / a) if a else None, "d21": rnd((cl - S["e21"].at[d, t]) / a) if a else None,
                        "e9": rnd(S["e9"].at[d, t]), "e21": rnd(S["e21"].at[d, t]), "step": rnd(stp),
                        "to_step": rnd(stp / cl - 1, 4) if np.isfinite(stp) and cl else None, "adr": rnd(S["adr"].at[d, t] * 100, 1),
                        "rsr": (info.get(t) or {}).get("rsr"), "price": rnd(cl)})
        order = {"break": 0, "lift": 1, "nuzzle": 2, "riding": 3, "extended": 4, "down": 5}
        mem.sort(key=lambda r: (order[r["state"]], -(r["rsr"] or 0)))
        lead = bool((r60.at[d, g] or 0) >= CFG["leader_pct"])
        active = [m for m in mem if m["state"] in ("break", "lift", "nuzzle")]
        if status == "none" and not lead:          # keep the page light: only the names worth seeing
            mem = active
        rows.append({"g": g, "theme": parent.get(g, ""), "status": status, "n": int(n),
                     "since": since(stepping, g) if status == "stepping" else since(setting, g) if status == "setting" else 0,
                     "fresh": bool(first(stepping)[g].iat[-1] or first(setting)[g].iat[-1]),
                     "up": rnd(G["up"].at[d, g]), "nuz": rnd(G["nuz"].at[d, g]), "nuz5": rnd(G["nuz5"].at[d, g]),
                     "lifted": rnd(lifted.at[d, g]), "brk3": rnd(G["brk3"].at[d, g]),
                     "r60": rnd(r60.at[d, g]), "leader": lead,
                     "rel5": rnd(rel5.at[d, g], 4), "rel20": rnd(rel20.at[d, g], 4),
                     # last H sessions: share nuzzled (5d) and share lifted/broke (3d), for the across-sessions strip
                     "h_nuz": [rnd(x) for x in G["nuz5"][g].iloc[-H:]], "h_lift": [rnd(x) for x in lifted[g].iloc[-H:]],
                     "h_st": ["S" if a_ else "E" if b_ else "" for a_, b_ in zip(stepping[g].iloc[-H:], setting[g].iloc[-H:])],
                     "members": mem})
    pri = {"stepping": 0, "setting": 1, "none": 2}
    rows.sort(key=lambda r: (pri[r["status"]], not r["leader"], -(r["lifted"] or 0) - (r["nuz5"] or 0)))
    ev = None
    if with_evidence and spy is not None:
        try:
            ev = evidence(G, spy, setting, stepping, breaks)
        except Exception:  # evidence is optional
            ev = None
    return {"date": d.strftime("%Y-%m-%d"), "dates": [x.strftime("%Y-%m-%d") for x in dates[-H:]], "cfg": CFG,
            "n_stepping": sum(r["status"] == "stepping" for r in rows), "n_setting": sum(r["status"] == "setting" for r in rows),
            "rows": rows, "evidence": ev}
