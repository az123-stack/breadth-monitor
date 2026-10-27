"""Theme lifecycle: which stage every sub-theme is in, when to WATCH it, when a BUY is on, and which tickers to buy
(Adam, Oct 27 2026: "trigger a watch for a buy on a theme, activate a buy on a theme, and recommend which tickers to buy").
Built from the "Anatomy of a Blossomed Theme" synthesis (Cybersecurity, Refiners, Enterprise SaaS + the group studies).
Card R-2026-10-27-theme-lifecycle, layer `lifecycle`, info only: it never re-ranks the picks.

Stages (daily, per sub-theme with 4+ stocks; only data up to that day):
  0 forgotten  - bottom fifth of groups on 60-day return vs SPY.
  1 first push - RS-rank (20-day relative return percentile) up 30+ points in 10 sessions from the bottom half on 60 days,
                 or 3 of the 4 ignition checks met; not yet ignited.
  2 ignition   - a group ignition (rotation.ignition_frames) in the last 10 sessions.
  3 build      - top 40% on 60 days, index within 15% of its 60-day high, and in an inflow tier or a rising relative trend on
                 12+ of the last 20 sessions.
  4 blossom    - top 20% on 60 days, index within 3% of its 60-day high, and an ignition in the last 40 sessions or the
                 confirmed money-flow tier.
  5 fade       - was top 20% on 60 days in the last 40 sessions, now in the fading/outflow tier with under half the members above
                 the 21 EMA.
WATCH = stage 1 or 2 WITH leaders present (look for curls and early names, starter size at most). Tested Oct 27: stage 1-2
        without leaders lagged (-0.6% vs avg group over 20 sessions, t -2.5) and only 30% turned BUY within 30 sessions;
        with leaders ~0 edge but 53% turned BUY (ignition + leaders 68%). WATCH means "line up the names", not "buy".
BUY   = stage 3 or 4 + leaders present (median member RS 70+ or 25%+ near a 52-week high) + money-flow tier confirmed or steady,
        and breadth not weak. Full size when the 10-day ratio hit 1.5 in the last 15 sessions ("Act"), else half size.
Tickers: members $10+, $20M+/day, RS 70+, ranked by entry: pullback into the 9/21 EMA ribbon (buy over the day's high, stop the
day's low, at most 1 ADR), high tight flag (pivot, stop flag low), Launch-list curl; leaders more than 2 ADRs over the 21 EMA are
"wait for a pullback". Evidence is recomputed every build (`evidence`).
"""
import numpy as np
import pandas as pd

from . import rotation as R

CFG = {"min_members": 4, "fwd": 20, "fwd2": 40, "space": 20, "warm": 120,
       "forgot": 0.2, "push_from": 0.5, "push_drk": 0.30, "ign_recent": 10, "ign_back": 40,
       "build_rk": 0.6, "build_off": -0.15, "build_days": 12, "bloom_rk": 0.8, "bloom_off": -0.03,
       "fade_was": 0.8, "fade_br": 0.5, "min_price": 10.0, "min_dvol": 20e6, "rs_min": 70,
       "touch": 0.25, "hold21": 0.5, "max9": 1.0, "fresh": 3, "ext": 2.0, "picks": 4, "new_days": 3}
STAGES = [(0, "forgotten", "Forgotten"), (1, "push", "First push"), (2, "ignition", "Ignition"), (3, "build", "Quiet build"),
          (4, "blossom", "Blossom"), (5, "fade", "Fading")]
NAME = {k: n for _, k, n in STAGES}
NUM = {k: i for i, k, _ in STAGES}
BY_NUM = {i: n for i, _, n in STAGES}


def _r(x, n=2):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, n) if np.isfinite(x) else None


def _wide(adjusted, tickers):
    sub = adjusted[adjusted["ticker"].isin(tickers)]
    piv = lambda k: sub.pivot_table(index="date", columns="ticker", values=k).sort_index()
    c = piv("c")
    return {k: (c if k == "c" else piv(k).reindex_like(c)) for k in ("c", "o", "h", "l", "v")}


def group_state(close, vol, members, history):
    """Daily stage / watch / buy frames for every sub-theme."""
    F = R.group_frames(close, members)
    FL = R.flow_frames(close, vol, members, F)
    X = R.ignition_frames(close, members, F, FL)
    rel, I = F["rel"], F["idx"]
    dates, cols = rel.index, rel.columns
    rk60 = (rel / rel.shift(60) - 1).rank(axis=1, pct=True)
    off60 = I / I.rolling(60).max() - 1
    T = FL["tiers"]
    inflow = T["confirmed"] | T["steady"]
    ev = X["events"].astype(float)
    ign10 = ev.rolling(CFG["ign_recent"], min_periods=1).max() > 0
    ign40 = ev.rolling(CFG["ign_back"], min_periods=1).max() > 0
    nmet = sum(X["C"][k].astype(int) for k in X["C"])
    build_cnt = (inflow | F["trend"]).astype(int).rolling(20, min_periods=1).sum()
    was_top = rk60.rolling(40, min_periods=1).max() >= CFG["fade_was"]
    S = {
        "blossom": (rk60 >= CFG["bloom_rk"]) & (off60 >= CFG["bloom_off"]) & (ign40 | T["confirmed"]),
        "fade": was_top & (T["fading"] | T["outflow"]) & (X["br"] < CFG["fade_br"]),
        "build": (rk60 >= CFG["build_rk"]) & (off60 >= CFG["build_off"]) & (build_cnt >= CFG["build_days"]),
        "ignition": ign10,
        "push": ((X["drk"] >= CFG["push_drk"]) & (rk60.shift(10) < CFG["push_from"])) | (nmet >= 3),
        "forgotten": rk60 <= CFG["forgot"],
    }
    stage = pd.DataFrame(-1, index=dates, columns=cols)
    for k in ("forgotten", "push", "ignition", "build", "fade", "blossom"):   # later wins = higher priority
        stage = stage.mask(S[k].fillna(False).astype(bool), NUM[k])
    h = history[history["complete"]] if history is not None and len(history) and "complete" in history.columns else history
    r10 = h["ratio10"].reindex(dates).ffill() if h is not None and len(h) else pd.Series(np.nan, index=dates)
    act = (r10.rolling(R.IGN["gate_days"], min_periods=1).max() >= R.IGN["strong_ratio"])
    weak = r10 < 1
    regime = R._regimes(history, dates)
    lead = X["lead"]
    ready = stage.isin([3, 4]) & lead & inflow
    buy = ready & ~weak.to_numpy()[:, None]
    watch = stage.isin([1, 2]) & lead & ~ready     # without leaders a first push converted 30% and lagged (-0.8%, t -2.7)
    return {"F": F, "FL": FL, "X": X, "rk60": rk60, "off60": off60, "stage": stage, "buy": buy, "ready": ready, "watch": watch,
            "act": act, "weak": weak, "regime": regime, "r10": r10, "lead": lead, "inflow": inflow}


def _spaced(mask, gap):
    m = mask.copy()
    for j in range(m.shape[1]):
        last = -10 ** 6
        for i in np.flatnonzero(m[:, j]):
            if i - last < gap:
                m[i, j] = False
            else:
                last = i
    return m


def _stat(fx, mask, dates, half):
    """fx = forward excess (vs the average group that date) as an array; mask = signal cells."""
    a = fx[mask]
    a = a[np.isfinite(a)]
    if a.size < 8:
        return {"n": int(a.size)}
    rows, cols = np.nonzero(mask & np.isfinite(fx))
    per = pd.Series(fx[rows, cols], index=dates[rows]).groupby(level=0).mean()
    t = per.mean() / (per.std(ddof=1) / np.sqrt(len(per))) if len(per) > 2 and per.std(ddof=1) > 0 else None
    h1 = per[per.index < half].mean() if (per.index < half).any() else None
    h2 = per[per.index >= half].mean() if (per.index >= half).any() else None
    return {"n": int(a.size), "dates": int(len(per)), "xs": _r(a.mean(), 4), "med": _r(np.median(a), 4),
            "win": _r((a > 0).mean(), 3), "t": _r(t, 2), "h1": _r(h1, 4), "h2": _r(h2, 4)}


def group_evidence(G):
    rel, dates = G["F"]["rel"], G["F"]["rel"].index
    n = len(dates)
    valid = np.zeros(rel.shape, dtype=bool)
    valid[CFG["warm"]:] = True
    half = dates[CFG["warm"] + (n - CFG["warm"]) // 2]
    out = {"from": str(dates[min(CFG["warm"], n - 1)].date()), "to": str(dates[-1].date()), "groups": int(rel.shape[1])}
    reg = G["regime"].to_numpy()
    act = G["act"].to_numpy()
    for fwd in (CFG["fwd"], CFG["fwd2"]):
        f = (rel.shift(-fwd) / rel - 1)
        fx = f.sub(f.mean(axis=1), axis=0).to_numpy()
        res = {}
        for k, num in [(k, NUM[k]) for _, k, _ in STAGES]:
            res[k] = _stat(fx, _spaced((G["stage"].to_numpy() == num) & valid, CFG["space"]), dates, half)
        for k, M in (("watch", G["watch"]), ("buy", G["buy"])):
            m = M.to_numpy() & valid
            first = m & ~np.vstack([np.zeros((1, m.shape[1]), bool), m[:-1]])
            res[k] = _stat(fx, _spaced(m, CFG["space"]), dates, half)
            res[k + "_first"] = _stat(fx, _spaced(first, CFG["space"]), dates, half)
            res[k + "_act"] = _stat(fx, _spaced(m & act[:, None], CFG["space"]), dates, half)
            res[k + "_noact"] = _stat(fx, _spaced(m & ~act[:, None], CFG["space"]), dates, half)
            for rk in ("strong", "mixed", "weak"):
                res[f"{k}_{rk}"] = _stat(fx, _spaced(m & (reg == rk)[:, None], CFG["space"]), dates, half)
        # the same setup in weak breadth (why BUY waits for breadth)
        res["ready_weak"] = _stat(fx, _spaced(G["ready"].to_numpy() & valid & G["weak"].to_numpy()[:, None], CFG["space"]), dates, half)
        # buy-like groups WITHOUT leaders or inflow (what the extra conditions add)
        st34 = G["stage"].isin([3, 4]).to_numpy() & valid & ~G["weak"].to_numpy()[:, None]
        res["stage34_not_buy"] = _stat(fx, _spaced(st34 & ~G["buy"].to_numpy(), CFG["space"]), dates, half)
        out[f"d{fwd}"] = res
    # how often a fresh WATCH turns into a BUY (ready) within 30 sessions
    wm = G["watch"].to_numpy() & valid
    wf = _spaced(wm & ~np.vstack([np.zeros((1, wm.shape[1]), bool), wm[:-1]]), CFG["space"])
    rd = G["ready"].to_numpy()
    hits = tot = 0
    for i, j in np.argwhere(wf):
        if i + 30 >= n:
            continue
        tot += 1
        hits += bool(rd[i + 1:i + 31, j].any())
    out["watch_to_buy"] = {"n": tot, "rate": _r(hits / tot, 3) if tot else None, "within": 30}
    return out


def stock_frames(w, close_cols):
    c, o, h, l, v = (w[k][close_cols] for k in ("c", "o", "h", "l", "v"))
    adr = ((h / l) - 1).rolling(20, min_periods=15).mean()
    dvol = (c * v).rolling(20, min_periods=15).mean()
    e9, e21, e50 = (c.ewm(span=n, adjust=False, min_periods=n).mean() for n in (9, 21, 50))
    rs = (c / c.shift(63) - 1).rank(axis=1, pct=True) * 99
    up = (e21 > e50) & (e50 > e50.shift(10))
    liq = (c >= CFG["min_price"]) & (dvol >= CFG["min_dvol"])
    rib = np.maximum(e9, e21)
    base = liq & up & (rs >= CFG["rs_min"])
    touch = base & (l <= rib + CFG["touch"] * adr * c) & (c >= e21 - CFG["hold21"] * adr * c) & (c <= e9 + CFG["max9"] * adr * c)
    return {"c": c, "o": o, "h": h, "l": l, "adr": adr, "dvol": dvol, "e9": e9, "e21": e21, "e50": e50, "rs": rs,
            "touch": touch, "base": base, "liq": liq}


def stock_evidence(P, G, members, bench_c, bench_o):
    """Pullback entries (low into the 9/21 ribbon) by the stock's group state that day: next open -> close 20 sessions later,
    stop 1 ADR under the entry (R), and % vs SPY."""
    days = P["c"].index
    n = len(days)
    stG = {}
    for g, mem in members.items():
        if g not in G["stage"].columns:
            continue
        for t in mem:
            stG.setdefault(t, []).append(g)
    buy, watch = G["buy"].reindex(days), G["watch"].reindex(days)
    first = P["touch"] & ~P["touch"].shift(1, fill_value=False).rolling(5, min_periods=1).max().astype(bool)
    H = CFG["fwd"]
    rows = []
    for t in P["c"].columns:
        gs = stG.get(t)
        if not gs:
            continue
        ix = np.flatnonzero(first[t].to_numpy())
        for i in ix:
            if i < CFG["warm"] or i + H >= n:
                continue
            e = P["o"][t].iat[i + 1]
            a = P["adr"][t].iat[i]
            if not (np.isfinite(e) and e > 0 and np.isfinite(a) and a > 0):
                continue
            stop = e * (1 - a)
            lows = P["l"][t].iloc[i + 1:i + 1 + H].to_numpy()
            ex = P["c"][t].iat[i + H]
            hit = np.flatnonzero(lows <= stop)
            ret = -a if len(hit) else ex / e - 1
            spy = bench_c.iat[i + H] / bench_o.iat[i + 1] - 1
            b = any(bool(buy[g].iat[i]) for g in gs)
            wv = any(bool(watch[g].iat[i]) for g in gs)
            # live rule: buy the break of the touch-day high within 3 sessions, stop the touch-day low (max 1 ADR)
            hi_i, lo_i = P["h"][t].iat[i], P["l"][t].iat[i]
            Rt = None
            for j in range(i + 1, min(i + 4, n - H)):
                if P["h"][t].iat[j] >= hi_i:
                    en = max(P["o"][t].iat[j], hi_i)
                    st = max(lo_i, en * (1 - a))
                    risk = max(en - st, 0.3 * a * en)
                    lw = P["l"][t].iloc[j:j + H].to_numpy()
                    hit2 = np.flatnonzero(lw <= st)
                    Rt = (st - en) / risk if len(hit2) else (P["c"][t].iat[j + H - 1] - en) / risk
                    break
            rows.append((days[i], "buy" if b else "watch" if wv else "other", ret / a, ex / e - 1 - spy, Rt))
    X = pd.DataFrame(rows, columns=["date", "grp", "R", "xs", "Rt"])
    if not len(X):
        return None
    split = X["date"].sort_values().iloc[len(X) // 2]
    out = {"from": str(X["date"].min().date()), "to": str(X["date"].max().date()), "hold": H}
    for g in ("buy", "watch", "other"):
        x = X[X["grp"] == g]
        out[g] = {"n": int(len(x)), "R": _r(x["R"].mean(), 3), "win": _r((x["R"] > 0).mean(), 3), "xs": _r(x["xs"].mean(), 4),
                  "h1": _r(x[x["date"] < split]["R"].mean(), 3), "h2": _r(x[x["date"] >= split]["R"].mean(), 3)}
    d = (X[X["grp"] == "buy"].groupby("date")["R"].mean() - X[X["grp"] != "buy"].groupby("date")["R"].mean()).dropna()
    out["edge"] = _r(d.mean(), 3)
    out["t"] = _r(d.mean() / (d.std(ddof=1) / np.sqrt(len(d))), 2) if len(d) > 2 and d.std(ddof=1) > 0 else None
    out["proven"] = bool(out["t"] is not None and out["t"] >= 2 and (out["buy"]["h1"] or 0) > 0 and (out["buy"]["h2"] or 0) > 0)
    Y = X.dropna(subset=["Rt"])           # the intraday rule the live card uses (trigger over the touch-day high)
    tr = {"filled": _r(len(Y) / len(X), 3) if len(X) else None}
    for g in ("buy", "watch", "other"):
        y = Y[Y["grp"] == g]
        tr[g] = {"n": int(len(y)), "R": _r(y["Rt"].mean(), 3), "win": _r((y["Rt"] > 0).mean(), 3),
                 "h1": _r(y[y["date"] < split]["Rt"].mean(), 3), "h2": _r(y[y["date"] >= split]["Rt"].mean(), 3)}
    d2 = (Y[Y["grp"] == "buy"].groupby("date")["Rt"].mean() - Y[Y["grp"] != "buy"].groupby("date")["Rt"].mean()).dropna()
    tr["edge"] = _r(d2.mean(), 3)
    tr["t"] = _r(d2.mean() / (d2.std(ddof=1) / np.sqrt(len(d2))), 2) if len(d2) > 2 and d2.std(ddof=1) > 0 else None
    out["trigger"] = tr
    return out


def _run(col):
    v = col.to_numpy()
    k = 0
    for x in v[::-1]:
        if x != v[-1]:
            break
        k += 1
    return k


def picks(g, members, P, stocks, extra):
    """Tickers to buy in a group today, best entry first, plus leaders to wait on."""
    i = len(P["c"].index) - 1
    out, wait = [], []
    for t in members.get(g, []):
        if t not in P["c"].columns or not (stocks.get(t) or {}).get("is_stock"):
            continue
        s = stocks.get(t) or {}
        c, a = P["c"][t].iat[i], P["adr"][t].iat[i]
        if not (np.isfinite(c) and np.isfinite(a) and a > 0) or not bool(P["liq"][t].iat[i]):
            continue
        rs = s.get("rsr")
        if rs is None or rs < CFG["rs_min"]:
            continue
        e9, e21 = P["e9"][t].iat[i], P["e21"][t].iat[i]
        vs21 = (c / e21 - 1) / a if np.isfinite(e21) else None
        tch = P["touch"][t].iloc[i - CFG["fresh"] + 1:i + 1]
        rib = max(e9, e21)
        row = {"t": t, "rs": _r(rs, 0), "price": _r(c, 2), "adr": _r(a * 100, 1), "vs21": _r(vs21, 2),
               "off_hi": s.get("off_hi"), "e21": _r(e21, 2), "dvol": _r(P["dvol"][t].iat[i] / 1e6, 0)}
        fl = extra["flags"].get(t)
        cu = extra["curl"].get(t)
        hi, lo = P["h"][t].iat[i], P["l"][t].iat[i]
        if bool(tch.any()) and bool(P["base"][t].iat[i]) and c <= rib * (1 + CFG["max9"] * a) and c >= e21 * (1 - CFG["hold21"] * a):
            stop = max(lo, hi * (1 - a)) if bool(tch.iat[-1]) else max(min(P["l"][t].iloc[i - CFG["fresh"] + 1:i + 1].min(), e21 * (1 - CFG["hold21"] * a)), hi * (1 - a))
            row.update({"entry": "pullback", "trigger": _r(hi, 2), "stop": _r(stop, 2),
                        "plan": "Pulled back into the 9/21 EMAs: buy over today's high, stop under the low (max 1 ADR)",
                        "days": int(CFG["fresh"] - 1 - np.argmax(tch.to_numpy()[::-1]))})
        elif vs21 is not None and vs21 > CFG["ext"] and not fl:
            row.update({"entry": "extended", "plan": f"{vs21:.1f} ADRs over the 21 EMA: wait for a pullback to the 9/21 EMAs"})
            wait.append(row)
            continue
        elif fl:
            row.update({"entry": "flag", "trigger": fl.get("pivot"), "stop": fl.get("stop"),
                        "plan": "High tight flag: buy the break of the pivot, stop at the flag low"})
        elif cu:
            row.update({"entry": "curl", "trigger": None, "stop": None,
                        "plan": "Launch-list curl under the 50-week EMA: buy the weekly flag break (see the Launch list)"})
        elif vs21 is not None and vs21 > CFG["ext"]:
            row.update({"entry": "extended", "plan": f"{vs21:.1f} ADRs over the 21 EMA: wait for a pullback to the 9/21 EMAs"})
            wait.append(row)
            continue
        elif c > rib and c <= rib * (1 + CFG["max9"] * a):
            row.update({"entry": "near", "trigger": None, "stop": None, "plan": "Within 1 ADR above the 9/21 EMAs: alert at the 9 EMA"})
        else:
            continue
        out.append(row)
    order = {"pullback": 0, "flag": 1, "curl": 2, "near": 3}
    out.sort(key=lambda r: (order[r["entry"]], -(r["rs"] or 0)))
    wait.sort(key=lambda r: -(r["rs"] or 0))
    return out[:CFG["picks"]], wait[:3]


def build(adjusted, theme_data, history, evidence_on=True):
    from . import config
    T = theme_data or {}
    subs = {r["theme"]: r for r in T.get("subthemes") or []}
    members = {g: r.get("members") or [] for g, r in subs.items()}
    tick = sorted({t for v in members.values() for t in v} | {config.BENCHMARK})
    w = _wide(adjusted, tick)
    close, vol = w["c"], w["v"]
    if config.BENCHMARK not in close.columns or len(close) < CFG["warm"] + 30:
        return None
    G = group_state(close, vol, members, history)
    stocks = {s["t"]: s for s in T.get("stocks") or []}
    cols = [t for t in close.columns if t != config.BENCHMARK]
    P = stock_frames(w, cols)
    earn = {}
    try:   # earnings dates the catalyst agent found (docs/agent/catalysts.json); a report inside the hold is a coin flip
        import json, pathlib
        cj = json.loads((pathlib.Path(__file__).resolve().parent.parent / "docs" / "agent" / "catalysts.json").read_text())
        earn = {t: v.get("earnings_date") for t, v in (cj.get("stocks") or {}).items() if v.get("earnings_date")}
    except Exception:
        pass
    pol = T.get("polished") or {}
    extra = {"flags": {r["t"]: r for r in pol.get("flags") or []},
             "curl": {r["t"]: r for r in ((T.get("launch") or {}).get("rows") or []) if r.get("stage") in ("curl", "early") and r.get("grade") in ("A", "B")}}
    dates = G["stage"].index
    i = len(dates) - 1
    rows = []
    for g in G["stage"].columns:
        st = int(G["stage"][g].iat[i])
        buy, watch, ready = bool(G["buy"][g].iat[i]), bool(G["watch"][g].iat[i]), bool(G["ready"][g].iat[i])
        if st < 0 and not (ready or watch):
            continue
        b_run = _run(G["ready"][g]) if ready else 0
        w_run = _run(G["watch"][g]) if watch else 0
        prev = int(G["stage"][g].iat[i - 5]) if i >= 5 else -1
        X, FL = G["X"], G["FL"]
        r = subs.get(g, {})
        why = []
        rk = G["rk60"][g].iat[i]
        if np.isfinite(rk):
            why.append(f"60-day return vs SPY: top {max(1, round((1 - rk) * 100))}% of groups")
        why.append(f"Index {G['off60'][g].iat[i] * 100:+.0f}% from its 60-day high")
        why.append(f"{X['br'][g].iat[i] * 100:.0f}% of members above the 21 EMA")
        why.append(f"Money flow tier: {R.tier_of(FL, g)}")
        why.append("Leaders present" if bool(G["lead"][g].iat[i]) else "No leaders yet")
        ev = X["events"][g].to_numpy()
        if ev.any():
            ago = int(i - np.flatnonzero(ev)[-1])
            if ago <= 60:
                why.append(f"Ignition {ago} session{'s' if ago != 1 else ''} ago")
        row = {"g": g, "sector": r.get("group", ""), "stage": BY_NUM.get(st, "Neutral"),
               "stage_n": st, "stage_days": _run(G["stage"][g]), "prev": prev, "buy": buy, "ready": ready, "watch": watch,
               "hot": watch and st == 2,
               "new": (ready and b_run <= CFG["new_days"]) or (watch and w_run <= CFG["new_days"]), "on_days": b_run or w_run,
               "strength": r.get("strength"), "s_rank": r.get("s_rank"), "tier": R.tier_of(FL, g),
               "lead": bool(G["lead"][g].iat[i]), "rk60": _r(rk, 3), "off60": _r(G["off60"][g].iat[i], 3),
               "br": _r(X["br"][g].iat[i], 2), "why": why}
        if ready or watch:
            row["picks"], row["wait"] = picks(g, members, P, stocks, extra)
            for p_ in row["picks"] + row["wait"]:
                if earn.get(p_["t"]):
                    p_["earn"] = earn[p_["t"]]
        rows.append(row)
    act = bool(G["act"].iat[i])
    weak = bool(G["weak"].iat[i]) if G["weak"].iat[i] == G["weak"].iat[i] else False
    size = "full" if act else ("hold off" if weak else "half")
    # Live "lined up" list for the Intraday tab: every liquid RS 70+ uptrend member of a ready / watch group, with what the
    # browser needs to test today's dip into the 9/21 EMAs from Google prices (lifecycleLive in template.html).
    live, rank = {}, {"buy": 0, "ready": 1, "watch": 2}
    for r in rows:
        kind = ("buy" if r["buy"] else "ready") if r["ready"] else None   # WATCH-group dips lost (-0.16R): not listed
        if not kind:
            continue
        for t in members.get(r["g"], []):
            if t not in P["c"].columns or not (stocks.get(t) or {}).get("is_stock") or not bool(P["base"][t].iat[i]):
                continue
            rs = (stocks.get(t) or {}).get("rsr")
            if rs is None or rs < CFG["rs_min"] or (t in live and rank[live[t]["kind"]] <= rank[kind]):
                continue
            a = P["adr"][t].iat[i]
            live[t] = {"t": t, "g": r["g"], "kind": kind, "lead": r["lead"], "stage": r["stage"], "rs": _r(rs, 0),
                       "c": _r(P["c"][t].iat[i], 4), "hi": _r(P["h"][t].iat[i], 4), "lo": _r(P["l"][t].iat[i], 4),
                       "e9": _r(P["e9"][t].iat[i], 4), "e21": _r(P["e21"][t].iat[i], 4), "adr": _r(a, 4),
                       "t3": bool(P["touch"][t].iloc[i - CFG["fresh"] + 1:i + 1].any()), "t0": bool(P["touch"][t].iat[i]),
                       "earn": earn.get(t)}
    rows.sort(key=lambda r: (not r["ready"], not r["watch"], not r["new"], -(r["strength"] or 0)))
    counts = {k: int((G["stage"].iloc[i] == NUM[k]).sum()) for _, k, _ in STAGES}
    alerts = [{"g": r["g"], "kind": ("buy" if r["buy"] else "ready") if r["ready"] else "watch", "days": r["on_days"], "stage": r["stage"]}
              for r in rows if r["new"]]
    out = {"date": dates[i].strftime("%Y-%m-%d"), "cfg": CFG, "stages": [{"n": n, "k": k, "name": nm} for n, k, nm in STAGES],
           "rows": rows, "counts": counts, "alerts": alerts, "act": act, "weak": weak, "size": size,
           "ratio10": _r(G["r10"].iat[i], 2), "regime": str(G["regime"].iat[i]),
           "live": sorted(live.values(), key=lambda x: (rank[x["kind"]], -(x["rs"] or 0)))}
    if evidence_on:
        out["evidence"] = group_evidence(G)
        try:
            out["stock_evidence"] = stock_evidence(P, G, members, close[config.BENCHMARK], w["o"][config.BENCHMARK])
        except Exception as e:  # never lose the card over the stock study
            import logging
            logging.getLogger("breadth").exception("lifecycle stock evidence failed: %s", e)
    return out


def build_safe(*a, **k):
    try:
        return build(*a, **k)
    except Exception as e:  # optional panel; never block the page
        import logging
        logging.getLogger("breadth").exception("theme lifecycle failed: %s", e)
        return None
