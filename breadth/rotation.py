"""Rotation trade ideas: which sub-themes money is rotating into, the evidence, and how to trade them.

Tested on our own history (Oct 2024 onward, sub-themes with 4+ stocks, equal-weight group index vs SPY,
next 10 sessions, one signal per group per 10 sessions):
  - A fresh cross of the group/SPY line above its 20-day average had NO edge on its own.
  - "Leading & accelerating" = group/SPY line above a rising 20-day average, within 3% of its 60-day high,
    and a top-20% 20-day relative move: +0.9% vs the average group (t 2.8); +1.8% in strong breadth
    (t 3.75, 60% win), about +0.3% (not reliable) in mixed or weak breadth.
  - Groups near their 60-day relative low and falling lagged (-0.4%, t -2.1): the avoid list.
  - Picking the member closest to its 60-day high LAGGED its own group; the member closest above its
    21 EMA did a little better than the group (not significant). So ideas lead with the group and rank
    stocks by how little they're stretched above the 21 EMA.
The numbers are recomputed every build (`bt`), so the page always shows the current evidence.
Caveat: sub-theme lists were built from today's strong names (survivorship), which flatters all groups
equally; edges are measured against the average group, which cancels most of it.
"""
import numpy as np
import pandas as pd

MIN_MEMBERS = 4
MA = 20          # relative line average
HI_DAYS = 60     # relative high lookback
NEAR_HI = 0.97   # within 3% of the 60-day relative high
TOP_PCT = 0.8    # top 20% of groups on 20-day relative move
HOLD = 10        # sessions, for the evidence table
SPACING = 10     # one signal per group per this many sessions
MAX_IDEAS = 6
TWIN_CORR = 0.8  # a leading group this correlated with a chosen one is shown under it, not as a new idea
MAX_STOCKS = 5


def _wide(adjusted, tickers):
    sub = adjusted[adjusted["ticker"].isin(tickers)]
    piv = lambda k: sub.pivot_table(index="date", columns="ticker", values=k).sort_index()
    c = piv("c")
    return c, piv("h").reindex_like(c), piv("v").reindex_like(c)


def group_frames(close, members, bench="SPY"):
    """Equal-weight group indexes and the relative-strength state of every group on every day."""
    ret = (close / close.shift(1) - 1).clip(-0.6, 3.0)
    idx = {}
    for g, tick in members.items():
        t = [x for x in tick if x in close.columns]
        if len(t) < MIN_MEMBERS:
            continue
        idx[g] = (1 + ret[t].mean(axis=1, skipna=True).fillna(0.0)).cumprod()
    I = pd.DataFrame(idx)
    rel = I.div(close[bench], axis=0)
    ma = rel.rolling(MA).mean()
    above = rel > ma
    rising = ma > ma.shift(5)
    near_hi = rel >= rel.rolling(HI_DAYS).max() * NEAR_HI
    r20 = rel / rel.shift(20) - 1
    top = r20.rank(axis=1, pct=True) >= TOP_PCT
    lead = above & rising & near_hi & top
    weak = (rel <= rel.rolling(HI_DAYS).min() * 1.03) & ~rising
    cross = above & ~above.shift(1, fill_value=False)
    return {"idx": I, "rel": rel, "ma": ma, "lead": lead, "trend": above & rising & near_hi,
            "weak": weak, "cross": cross, "r20": r20, "top": top}


def _regimes(history, dates):
    out = pd.Series("mixed", index=dates)
    if history is None or not len(history):
        return out
    h = history[history["complete"]] if "complete" in history.columns else history
    r = pd.Series("mixed", index=h.index)
    r[(h["ratio5"] >= 1.5) & (h["ratio10"] >= 1.5)] = "strong"
    r[h["ratio10"] < 1] = "weak"
    return r.reindex(dates).ffill().fillna("mixed")


def evidence(F, regimes, hold=HOLD):
    """Next-`hold`-session relative return of signal groups vs the average group, by breadth regime."""
    rel = F["rel"]
    n = len(rel)
    fwd = rel.shift(-hold) / rel - 1
    valid = np.zeros(rel.shape, dtype=bool)
    valid[HI_DAYS + MA:n - hold] = True
    FV = fwd.to_numpy()
    reg = regimes.reindex(rel.index).to_numpy()

    def spaced(mask):
        m = mask.to_numpy() & valid
        for j in range(m.shape[1]):
            last = -10 ** 6
            for i in np.flatnonzero(m[:, j]):
                if i - last < SPACING:
                    m[i, j] = False
                else:
                    last = i
        return m

    out = {"hold": hold, "from": str(rel.index[HI_DAYS + MA].date()) if n > HI_DAYS + MA else None,
           "to": str(rel.index[max(0, n - hold - 1)].date()), "groups": int(rel.shape[1])}
    for key, mask in (("lead", F["lead"]), ("cross", F["cross"]), ("weak", F["weak"])):
        m = spaced(mask)
        o = {}
        for rk in ("all", "strong", "mixed", "weak"):
            sel = np.ones(n, dtype=bool) if rk == "all" else (reg == rk)
            a = FV[m & sel[:, None]]
            b = FV[valid & sel[:, None]]
            a, b = a[~np.isnan(a)], b[~np.isnan(b)]
            if len(a) < 10 or len(b) < 10:
                o[rk] = {"n": int(len(a))}
                continue
            d = a.mean() - b.mean()
            se = a.std(ddof=1) / np.sqrt(len(a))
            o[rk] = {"n": int(len(a)), "ret": round(float(a.mean()), 4), "base": round(float(b.mean()), 4),
                     "edge": round(float(d), 4), "t": round(float(d / se), 2) if se > 0 else 0.0,
                     "win": round(float((a > 0).mean()), 3), "base_win": round(float((b > 0).mean()), 3)}
        out[key] = o
    return out


def _streak(col):
    v = col.to_numpy()
    k = 0
    for x in v[::-1]:
        if not x:
            break
        k += 1
    return k


def _corr_partner(I, g, groups, n=120):
    r = (I / I.shift(1) - 1).iloc[-n:]
    best, bc = None, 0.6
    for h in groups:
        if h == g:
            continue
        c = r[g].corr(r[h])
        if c == c and c > bc:
            best, bc = h, c
    return best, bc


def stock_plan(s, hi5):
    """Plan for one stock: zone vs the 21 EMA in ADRs, buy-above trigger, 1-ADR stop."""
    adr = (s.get("adr") or 0) / 100
    e21 = s.get("e21")
    ext = (e21 / adr) if (adr and e21 is not None) else None
    zone = None if ext is None else "near 21 EMA" if ext <= 1.0 else "fair" if ext <= 2.5 else "extended"
    price = s.get("price")
    trig = hi5 if hi5 and price and hi5 >= price else price
    stop = trig * (1 - adr) if trig and adr else None
    return {"t": s["t"], "name": s.get("name", ""), "price": price, "rsr": s.get("rsr"), "adr": s.get("adr"),
            "e21": e21, "ext": round(ext, 2) if ext is not None else None, "zone": zone,
            "off_hi": s.get("off_hi"), "d20": s.get("d20"),
            "trigger": round(float(trig), 2) if trig else None, "stop": round(float(stop), 2) if stop else None,
            "risk": round(adr, 4) if adr else None, "star": bool(s.get("rs_nh")), "lead": bool(s.get("rs_lead"))}



# ---------------------------------------------------------------------------
# Money flow: Relative Rotation Graph + volume accumulation, with confidence tiers
# ---------------------------------------------------------------------------
TIERS = [  # key, label, plain meaning
    ("confirmed", "Confirmed inflow", "Money has been flowing in and it's still accelerating, or it's been leading for weeks with buying volume behind it."),
    ("steady", "Steady inflow", "Leading SPY on most days for three weeks; volume isn't confirming it as strongly."),
    ("new", "New this week", "Just moved into the Leading corner. Early: on its own this hasn't shown an edge yet."),
    ("fading", "Fading", "Still ahead of SPY but losing momentum: money is starting to slow."),
    ("bouncing", "Bouncing", "Was lagging and is improving. These bounces have tended to fail."),
    ("outflow", "Outflow", "Lagging SPY and losing momentum, or volume shows selling: money leaving."),
    ("neutral", "No clear flow", ""),
]
SUSTAIN = (10, 15)    # in the Leading quadrant on at least 10 of the last 15 sessions
ACC_MIN = 0.15        # 10-day up-volume minus down-volume, as a share of dollar volume
TAIL = 15             # sessions of tail on the graph


def flow_frames(close, vol, members, F):
    rel = F["rel"]
    x = (100 * rel / rel.rolling(50).mean()).ewm(span=5, adjust=False).mean()   # trend vs SPY (RS-Ratio)
    y = 100 * x / x.shift(10)                                                  # momentum of that trend (RS-Momentum)
    dv = close * vol
    sg = np.sign(close / close.shift(1) - 1)
    acc, part = {}, {}
    for g in rel.columns:
        t = [q for q in members[g] if q in close.columns]
        acc[g] = (dv[t] * sg[t]).sum(axis=1).rolling(10).sum() / dv[t].sum(axis=1).rolling(10).sum()
        d = dv[t].sum(axis=1)
        part[g] = d.rolling(10).mean() / d.rolling(50).mean()
    acc, part = pd.DataFrame(acc), pd.DataFrame(part)
    lead = (x > 100) & (y > 100)
    sust = lead.rolling(SUSTAIN[1]).sum() >= SUSTAIN[0]
    new = lead & ~lead.shift(5, fill_value=False).astype(bool)
    accp = acc > ACC_MIN
    conf = F["lead"] | (sust & accp)
    steady = sust & ~conf
    newt = new & ~sust & ~conf
    fading = (x > 100) & (y < 100) & ~conf & ~steady
    outflow = (((x < 100) & (y < 100)) | ((x < 100) & (acc < -ACC_MIN))) & ~conf & ~steady & ~newt
    bouncing = (x < 100) & (y > 100) & ~newt & ~outflow & ~conf & ~steady
    tiers = {"confirmed": conf, "steady": steady, "new": newt, "fading": fading, "bouncing": bouncing, "outflow": outflow}
    return {"x": x, "y": y, "acc": acc, "part": part, "lead": lead, "tiers": tiers}


def flow_safe(*a):
    try:
        return flow_build(*a)
    except Exception as e:  # never lose the ideas card over the flow panel
        import logging
        logging.getLogger("breadth").exception("money flow failed: %s", e)
        return None


def tier_of(FL, g, i=-1):
    for k, _, _ in TIERS[:-1]:
        if bool(FL["tiers"][k][g].iloc[i]):
            return k
    return "neutral"


def flow_evidence(F, FL, regimes):
    out = {}
    for k, _, _ in TIERS[:-1]:
        e = evidence({"rel": F["rel"], "lead": FL["tiers"][k], "cross": FL["tiers"][k], "weak": FL["tiers"][k]}, regimes)
        out[k] = e["lead"]
    e = evidence({"rel": F["rel"], "lead": F["lead"], "cross": F["lead"], "weak": F["lead"]}, regimes)
    out["_meta"] = {k: e[k] for k in ("hold", "from", "to", "groups")}
    return out


def flow_build(close, vol, members, F, regimes, subs, stocks):
    FL = flow_frames(close, vol, members, F)
    x, y, acc, part, rel = FL["x"], FL["y"], FL["acc"], FL["part"], F["rel"]
    groups = list(rel.columns)
    rows = []
    for g in groups:
        if x[g].iloc[-1] != x[g].iloc[-1] or y[g].iloc[-1] != y[g].iloc[-1]:
            continue
        r = subs.get(g, {})
        tail = [[round(float(x[g].iloc[i]), 2), round(float(y[g].iloc[i]), 2)] for i in range(-TAIL, 0)
                if x[g].iloc[i] == x[g].iloc[i] and y[g].iloc[i] == y[g].iloc[i]]
        r5 = rel[g].iloc[-1] / rel[g].iloc[-6] - 1
        r20 = rel[g].iloc[-1] / rel[g].iloc[-21] - 1
        rows.append({"g": g, "sector": r.get("group", ""), "tier": tier_of(FL, g), "x": tail[-1][0], "y": tail[-1][1], "tail": tail,
                     "lead15": int(FL["lead"][g].iloc[-SUSTAIN[1]:].sum()), "acc": round(float(acc[g].iloc[-1]), 3),
                     "part": round(float(part[g].iloc[-1]), 2) if part[g].iloc[-1] == part[g].iloc[-1] else None,
                     "r5": round(float(r5), 4), "r20": round(float(r20), 4), "strength": r.get("strength"), "s_rank": r.get("s_rank"),
                     "tier5": tier_of(FL, g, -6), "n": len([t for t in members[g] if t in close.columns])})
    order = {k: i for i, (k, _, _) in enumerate(TIERS)}
    rows.sort(key=lambda r: (order[r["tier"]], r["r20"] if r["tier"] in ("outflow", "fading") else -r["r20"]))
    stock_tier = {}
    for g in groups:
        for t in members[g]:
            stock_tier[t] = g
    return {"rows": rows, "tiers": [{"k": k, "label": l, "desc": d} for k, l, d in TIERS],
            "evidence": flow_evidence(F, FL, regimes), "tail_days": TAIL,
            "dates": [close.index[-TAIL].strftime("%Y-%m-%d"), close.index[-1].strftime("%Y-%m-%d")],
            "stock_group": {t: g for t, g in stock_tier.items() if t in (stocks or {})}}


def build(adjusted, theme_data, kq_data=None, macro_data=None, history=None, sub_members=None):
    T = theme_data or {}
    subs = {r["theme"]: r for r in T.get("subthemes") or []}
    if sub_members is None:
        sub_members = {g: r.get("members") or [] for g, r in subs.items()}
    tick = sorted({t for v in sub_members.values() for t in v} | {"SPY"})
    close, high, vol = _wide(adjusted, tick)
    if "SPY" not in close.columns or len(close) < HI_DAYS + MA + 5:
        return None
    F = group_frames(close, sub_members)
    I, rel, ma = F["idx"], F["rel"], F["ma"]
    dates = rel.index
    regimes = _regimes(history, dates)
    ev = evidence(F, regimes)
    last = len(dates) - 1
    state = ((T.get("playbook") or {}).get("state")) or regimes.iloc[-1]
    st_key = "strong" if state in ("strong", "thrust") else state
    stocks = {s["t"]: s for s in T.get("stocks") or []}
    hi5 = high.iloc[-5:].max()
    in_setups = {}
    for s in ((T.get("trade_setups") or {}).get("setups") or []):
        for t in s.get("top") or []:
            in_setups.setdefault(t, []).append(s["name"])
    for r in (kq_data or {}).get("basing", []):
        in_setups.setdefault(r["t"], []).append("KQ basing")
    drives = {}
    for m in macro_data or []:
        for g in m.get("drives") or []:
            drives.setdefault(g, []).append(m)
    groups = list(rel.columns)
    r20 = F["r20"].iloc[-1]
    rank20 = r20.rank(ascending=False)

    def why_group(g):
        r = subs.get(g, {})
        rl, m_ = rel[g], ma[g]
        hi60 = rl.iloc[-HI_DAYS:].max()
        bits = [
            {"k": "rs", "ok": True, "txt": f"Beating SPY by {r20[g] * 100:+.1f}% over 20 sessions, #{int(rank20[g])} of {len(groups)} groups"},
            {"k": "trend", "ok": True, "txt": "Its line vs SPY is above a rising 20-day average and "
             + ("at its 60-day high" if rl.iloc[-1] / hi60 - 1 >= -0.005 else f"{abs(rl.iloc[-1] / hi60 - 1) * 100:.1f}% below its 60-day high")},
        ]
        sh = r.get("s_hist") or []
        if len(sh) > 20 and sh[-1] is not None and sh[-21] is not None:
            bits.append({"k": "strength", "ok": bool(sh[-1] >= sh[-21]), "txt": f"Theme Strength {sh[-1]:.0f} (#{r.get('s_rank', '–')}), {sh[-1] - sh[-21]:+.0f} over 20 sessions"})
        mem = [stocks[t] for t in sub_members.get(g, []) if t in stocks and stocks[t].get("e21") is not None]
        if mem:
            p = float(np.mean([m_["e21"] > 0 for m_ in mem]))
            bits.append({"k": "breadth", "ok": bool(p >= 0.6), "txt": f"{round(p * 100)}% of its {len(mem)} stocks above their 21 EMA"})
        partner, pc = _corr_partner(I, g, groups)
        if partner:
            pr = (I[g].iloc[-1] / I[g].iloc[-21]) / (I[partner].iloc[-1] / I[partner].iloc[-21]) - 1
            bits.append({"k": "cousin", "ok": bool(pr > 0), "pair": partner,
                         "txt": f"{'Beating' if pr > 0 else 'Lagging'} its closest cousin {partner} by {abs(pr) * 100:.1f}% over 20 sessions (correlation {pc:.2f})"})
        for m in drives.get(g, []):
            d30 = m.get("d30")
            if d30 is None:
                continue
            up = bool(d30 > 0)
            val = f"{d30 * 100:+.0f} bp" if m.get("unit") == "pct" else f"{d30 * 100:+.1f}%"
            bits.append({"k": "macro", "ok": up, "txt": f"{m['label']} {val} over the last month ({'tailwind' if up else 'headwind'})"})
        return bits

    def spark(g, n=60):
        a, b = rel[g].iloc[-n:], ma[g].iloc[-n:]
        base = a.iloc[0]
        return {"rel": [round(float(v / base * 100), 2) for v in a], "ma": [None if v != v else round(float(v / base * 100), 2) for v in b]}

    ideas = []
    lead_now = [g for g in groups if bool(F["lead"][g].iloc[-1])]
    lead_now.sort(key=lambda g: -r20[g])
    chosen, also = [], {}
    for g in lead_now:                     # a near-twin (corr >= 0.8) of a chosen group joins it instead
        partner, pc = _corr_partner(I, g, chosen) if chosen else (None, 0)
        if partner and pc >= TWIN_CORR:
            also.setdefault(partner, []).append(g)
        elif len(chosen) < MAX_IDEAS:
            chosen.append(g)
    for g in chosen:
        mem = [stocks[t] for t in dict.fromkeys(t for h in [g] + also.get(g, []) for t in sub_members.get(h, [])) if t in stocks]
        cands = [s for s in mem if (s.get("price") or 0) >= 10 and (s.get("adr") or 0) >= 3
                 and (s.get("e21") or -1) > 0 and (s.get("rsr") or 0) >= 70]
        plans = [stock_plan(s, float(hi5[s["t"]]) if s["t"] in hi5.index and hi5[s["t"]] == hi5[s["t"]] else None) for s in cands]
        for p in plans:
            p["setups"] = in_setups.get(p["t"], [])
            p["sub"] = stocks[p["t"]].get("sub")
        plans.sort(key=lambda p: (p["ext"] if p["ext"] is not None else 9, -(p["rsr"] or 0)))
        r = subs.get(g, {})
        ideas.append({"group": g, "sector": r.get("group", ""), "strength": r.get("strength"), "s_rank": r.get("s_rank"),
                      "n": len(sub_members.get(g, [])), "days": _streak(F["lead"][g]), "r20": round(float(r20[g]), 4),
                      "why": why_group(g), "stocks": plans[:MAX_STOCKS], "skipped": len(mem) - len(cands),
                      "also": also.get(g, []),
                      "spark": spark(g)})

    def brief(g):
        r = subs.get(g, {})
        return {"group": g, "sector": r.get("group", ""), "strength": r.get("strength"), "s_rank": r.get("s_rank"),
                "r20": round(float(r20[g]), 4), "days": _streak(F["weak"][g] if g in F["weak"] else F["cross"][g])}

    avoid = sorted([g for g in groups if bool(F["weak"][g].iloc[-1])], key=lambda g: r20[g])[:8]
    turning = sorted([g for g in groups if bool(F["cross"][g].iloc[-5:].any()) and bool((rel[g] > ma[g]).iloc[-1])
                      and g not in lead_now], key=lambda g: -r20[g])[:8]
    return {"date": dates[last].strftime("%Y-%m-%d"), "state": state, "state_key": st_key,
            "ideas": ideas, "lead_count": len(lead_now),
            "more": [g for g in lead_now if g not in chosen and not any(g in v for v in also.values())], "avoid": [brief(g) for g in avoid],
            "turning": [{**brief(g), "days": int(len(F["cross"][g]) - 1 - np.flatnonzero(F["cross"][g].to_numpy())[-1])} for g in turning],
            "bt": ev, "spark_dates": [d.strftime("%Y-%m-%d") for d in dates[-60:]],
            "flow": flow_safe(close, vol, sub_members, F, regimes, subs, stocks)}
