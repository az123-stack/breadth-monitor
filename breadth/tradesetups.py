"""Trade Setups: four watch lists of the trades we want in this market, top 5 each.

All lists use the theme-stock universe, common stocks only, price >= $10.
"Group" = the stronger of the stock's best theme and its sub-theme (Strength 0-100).

ATH Magnet      leader just under its all-time high, likely to tag it soon
                RS >= 90, group >= 80, within 3% of the 52-week high, above the
                21 EMA, ADR >= 3%, and (when long history is known) the all-time
                high no more than 2 ADRs away.
Leader Pullback leader back at its 21 EMA in an intact uptrend, volume drying up
                RS >= 85, group >= 70, within 3% of the 21 EMA, above the 50 EMA,
                4-20% off the high, 5-day volume <= 0.9x the 50-day.
Rotation Rookie stock in a theme or sub-theme that money is newly moving into
                theme up 10+ Strength ranks in 4 weeks (Strength >= 55) or
                sub-theme up 15+ (>= 60); RS >= 80 and not falling over 5 days,
                3-12% off the high, 0-6% above the 21 EMA (not extended).
Qullamaggie Flag KQ screen 'Basing' list (breadth/kq.py), any theme. HTF tag when the
                prior leg was +90% or more. Trade: buy the break of the 5-day high,
                stop at the entry day's low, sell half after 3 days, trail the rest
                on a close below the 10 EMA (20 EMA variant also tested).
Round Number Magnet  strong stock just under a big round number ($50, $100, $150, $200...)
                RS >= 85, above the 21 and 50 EMAs, ADR >= 2.5%, the next round level no more
                than 1.5 ADRs above the close. "Fresh" when the level is above the 52-week high
                (first test in a year). Trade: buy the open, stop 1 ADR, hold ~5 days.
Minervini VCP   trend template (above rising 150/200 SMA, 50 > 150 > 200, 30%+ off
                the 52-week low, within 15% of the high), RS >= 70, contracting
                ranges (10-day < 0.6x 20-day, 20-day < 0.8x 40-day) and volume
                drying up. Trade: buy the break of the 10-day high (pivot), stop
                under the 10-day low capped at 8%, hold until a close below the 50 SMA.

Each list is ranked by the Leaders score (breadth/leaders.py). "Setups hit"
counts how many buying angles a stock sits on at once: the four lists above,
a 2LYNCH 5+ momentum burst, and the anticipation list.
"""
import numpy as np
import pandas as pd

from . import leaders as LD

MIN_PRICE = 10.0
TOP = 5
RISK_FLOOR = 0.3     # R is measured against at least 0.3 ADR of risk (a tight low-of-day stop can be pennies)
RECENT = 30          # sessions of completed signals used for "recent results" (review flag)
SETUPS = [
    ("ath", "ATH Magnet", "Leader within reach of its all-time high: momentum and attention pulling it through."),
    ("pullback", "Leader Pullback", "Leader back at its 21 EMA, uptrend intact, sellers drying up: buy the dip, not the chase."),
    ("rotation", "Rotation Rookie", "A theme or sub-theme money is newly moving into; the stock hasn't run yet."),
    ("kq", "Qullamaggie Flag", "High-ADR top performer basing in a tight flag after a big leg (any theme). Buy the flag break, stop low of day, hold 3-5 days, trail the 10 EMA."),
    ("round", "Round Number Magnet", "Strong stock a short hop under a big round number ($50, $100, $200...): the level draws price in, and a clean break above it often runs."),
    ("vcp", "Minervini VCP", "Young Stage 2 trend tightening up with volume drying out. Buy the pivot break, stop under the last contraction (max 8%), hold while above the 50-day."),
]
RULES = {
    "ath": {"rs": 90, "grp": 80, "off": -0.03, "adr": 3.0, "ath_adr": 2.0},
    "pullback": {"rs": 85, "grp": 70, "e21": 0.03, "off_lo": -0.20, "off_hi": -0.04, "vdry": 0.9},
    "rotation": {"rs": 80, "theme_rise": 10, "theme_str": 55, "sub_rise": 15, "sub_str": 60,
                 "off_lo": -0.12, "off_hi": -0.03, "e21_hi": 0.06},
    "kq": {"htf_leg": 90},
    "round": {"rs": 85, "adr": 2.5, "dist_adr": 1.5, "min_pct": 0.002},
    "vcp": {"rs": 70, "off": -0.15, "low_up": 0.30, "r10": 0.6, "r20": 0.8, "vdry": 0.9, "stop_cap": 0.08},
}


def round_levels():
    """Big round numbers: 10, 20, 25, 30, 40, 50, 75, 100, 150, 200, 250, then every 100 to 1,000,
    every 500 to 5,000 and every 1,000 above."""
    lv = [10, 20, 25, 30, 40, 50, 75, 100, 150, 200, 250] + list(range(300, 1001, 100)) + list(range(1500, 5001, 500)) + list(range(6000, 100001, 1000))
    return np.array(sorted(set(lv)), dtype=float)


ROUND = round_levels()


def next_round(price, min_pct=0.002):
    """Smallest round level at least min_pct above the price (None past the table)."""
    i = int(np.searchsorted(ROUND, price * (1 + min_pct), side="left"))
    return float(ROUND[i]) if i < len(ROUND) else None


def is_century(level):
    return level is not None and (level % 100 == 0 or level == 50)


def _num(v, d=9.0):
    return d if v is None else v


# ---------------------------------------------------------------------------
# Magnet levels
# ---------------------------------------------------------------------------
def magnets(s, lev):
    """All-time high (and whether it's verified from long history) and the next
    overhead level at least 1% above the price."""
    price, off = s.get("price"), s.get("off_hi")
    if not price or off is None:
        return None
    h52 = price / (1 + off)
    ath, ok = h52, False
    lv = [h52]
    if lev and lev.get("ath"):
        ok = True
        ath = max(h52, lev["ath"])
        lv += [p for _, p in lev.get("peaks", [])] + [lev["ath"]]
    above = sorted(x for x in lv if x >= price * 1.01)
    nxt = above[0] if above else None
    adr = s.get("adr") or None
    out = {"ath": round(ath, 2), "ath_ok": ok, "ath_pct": round(ath / price - 1, 4),
           "mag": round(nxt, 2) if nxt else None, "mag_pct": round(nxt / price - 1, 4) if nxt else None,
           "mag_kind": None}
    if nxt:
        out["mag_kind"] = "ATH" if abs(nxt - ath) < 1e-6 * ath or nxt >= ath * 0.999 else (
            "52-wk high" if abs(nxt - h52) <= h52 * 0.001 else "prior peak")
    if adr:
        out["ath_adr"] = round(out["ath_pct"] * 100 / adr, 1)
        out["mag_adr"] = round(out["mag_pct"] * 100 / adr, 1) if nxt else None
    return out


# ---------------------------------------------------------------------------
# Today's lists
# ---------------------------------------------------------------------------
def build(stocks, themes, subthemes, kq=None, lists=None, levels=None, vcp=None):
    levels, vcp = levels or {}, vcp or {}
    ts = {r["theme"]: r.get("strength") for r in themes}
    ss = {r["theme"]: r.get("strength") for r in subthemes}
    rising = {r["theme"] for r in themes if r.get("s_r_m4") and r.get("strength") is not None
              and r["s_r_m4"] - r["s_rank"] >= RULES["rotation"]["theme_rise"] and r["strength"] >= RULES["rotation"]["theme_str"]}
    rising_sub = {r["theme"] for r in subthemes if r.get("s_r_m4") and r.get("strength") is not None
                  and r["s_r_m4"] - r["s_rank"] >= RULES["rotation"]["sub_rise"] and r["strength"] >= RULES["rotation"]["sub_str"]}
    basing = {r["t"]: r for r in (kq or {}).get("basing", [])}
    bursts = {r["t"] for r in (lists or {}).get("bursts", []) if (r.get("lynch") or 0) >= 5}
    antic = {r["t"] for r in (lists or {}).get("anticipation", [])}
    lead10 = {r["t"] for r in LD.rank(stocks, themes, subthemes, n=10)}
    nth = len(themes)
    top_th = {r["theme"] for r in themes if (r.get("s_rank") or 99) <= 2}
    bot_th = {r["theme"] for r in themes if (r.get("s_rank") or 0) >= nth - 1}
    top_sb = {r["theme"] for r in subthemes if (r.get("s_rank") or 99) <= 3}
    mkt10 = {r["t"] for r in (lists or {}).get("strongest", [])[:10]}
    eps = {r["t"] for r in (lists or {}).get("eps", [])}

    def tags_of(s, kqr):
        th = set(s.get("themes") or [])
        tg = [k for k, ok in (("lead", s.get("rs_lead")), ("star", s.get("rs_nh") and not s.get("rs_lead")),
                              ("rs99", (s.get("rsr") or 0) >= 99),
                              ("riser", (s.get("rsr5") or 0) >= 15 and (s.get("rsr") or 0) >= 60),
                              ("burst", s["t"] in bursts), ("antic", s["t"] in antic), ("mkt10", s["t"] in mkt10),
                              ("top_theme", bool(th & top_th)), ("top_sub", s.get("sub") in top_sb),
                              ("htf", bool(kqr) and (kqr.get("leg") or 0) >= 90),
                              ("ep", s["t"] in eps), ("bottom_theme", bool(th & bot_th))) if ok]
        return tg

    rows = {}
    for s in stocks:
        if not LD.eligible(s) or s["price"] < MIN_PRICE:
            continue
        score, bt, bstr, sub = LD.score_one(s, ts, ss)
        grp = max(_num(bstr, 0), _num(ss.get(s.get("sub")), 0))
        m = magnets(s, levels.get(s["t"])) or {}
        rs, off, e21, e50 = s["rsr"], _num(s.get("off_hi"), -1), s.get("e21"), s.get("e50")
        adr, vdry = _num(s.get("adr"), 0), s.get("vdry")
        hit = set()
        R = RULES["ath"]
        if (rs >= R["rs"] and grp >= R["grp"] and off >= R["off"] and _num(e21, -1) > 0 and adr >= R["adr"]
                and (not m.get("ath_ok") or _num(m.get("ath_adr"), 99) <= R["ath_adr"])):
            hit.add("ath")
        R = RULES["pullback"]
        if (rs >= R["rs"] and grp >= R["grp"] and e21 is not None and abs(e21) <= R["e21"] and _num(e50, -1) > 0
                and R["off_lo"] <= off <= R["off_hi"] and vdry is not None and vdry <= R["vdry"]):
            hit.add("pullback")
        R = RULES["rotation"]
        in_rise = [th for th in s.get("themes") or [] if th in rising] + ([s["sub"]] if s.get("sub") in rising_sub else [])
        if (in_rise and rs >= R["rs"] and _num(s.get("rsr5"), -1) >= 0 and R["off_lo"] <= off <= R["off_hi"]
                and e21 is not None and 0 <= e21 <= R["e21_hi"]):
            hit.add("rotation")
        kqr = basing.get(s["t"])
        if kqr:
            hit.add("kq")
        R = RULES["round"]
        lvl = next_round(s["price"], R["min_pct"])
        rnd = None
        if lvl and adr > 0:
            dist = lvl / s["price"] - 1
            h52 = s["price"] / (1 + off) if off > -1 else None
            rnd = {"round_lvl": lvl, "round_pct": round(dist, 4), "round_adr": round(dist * 100 / adr, 2),
                   "round_fresh": bool(h52 and lvl > h52), "round_century": is_century(lvl)}
            if (rs >= R["rs"] and _num(e21, -1) > 0 and _num(e50, -1) > 0 and adr >= R["adr"] and rnd["round_adr"] <= R["dist_adr"]):
                hit.add("round")
        vr = vcp.get(s["t"])
        if vr and rs >= RULES["vcp"]["rs"]:
            hit.add("vcp")
        if not hit:
            continue
        angles = set(hit) | ({"burst"} if s["t"] in bursts else set()) | ({"antic"} if s["t"] in antic else set())
        rows[s["t"]] = {
            "t": s["t"], "name": s.get("name", ""), "price": s["price"], "score": score, "rsr": rs, "rsr5": s.get("rsr5"),
            "theme": bt, "theme_str": bstr, "sub": s.get("sub"), "sub_str": sub, "grp": grp,
            "off_hi": s.get("off_hi"), "e21": e21, "e50": e50, "adr": s.get("adr"), "vdry": vdry, "tight": s.get("tight"), "d60": s.get("d60"),
            "tier": s.get("tier"), "star": bool(s.get("rs_nh")), "leader": s["t"] in lead10,
            "rising": in_rise[0] if in_rise else None, "setups": sorted(hit), "angles": sorted(angles), "hits": len(angles),
            "tags": tags_of(s, kqr),
            **m,
        }
        if rnd:
            rows[s["t"]].update(rnd)
        if kqr:
            rows[s["t"]].update({"kq_leg": kqr.get("leg"), "kq_rng10": kqr.get("rng10"), "kq_ext": kqr.get("ext"),
                                 "htf": (kqr.get("leg") or 0) >= RULES["kq"]["htf_leg"], "kq_pivot": kqr.get("pivot")})
        if vr:
            rows[s["t"]].update({"vcp_pivot": vr.get("pivot"), "vcp_stop": vr.get("stop"), "vcp_r10": vr.get("r10"),
                                 "vcp_r20": vr.get("r20"), "vcp_r40": vr.get("r40")})
    out = []
    for key, name, desc in SETUPS:
        cand = [r for r in rows.values() if key in r["setups"]]
        if key == "kq":      # Kristjan ranks by the base: tightest flags first, then RS
            cand.sort(key=lambda r: (_num(r.get("kq_rng10")), -r["rsr"], r["t"]))
        elif key == "vcp":   # tightest contraction first, then RS
            cand.sort(key=lambda r: (_num(r.get("vcp_r10")), -r["rsr"], r["t"]))
        elif key == "round":   # fresh tests and century marks first, then the Leaders score
            cand.sort(key=lambda r: (not r.get("round_fresh"), not r.get("round_century"), -r["score"], r["t"]))
        else:
            cand.sort(key=lambda r: (-r["score"], -r["rsr"], r["t"]))
        out.append({"key": key, "name": name, "desc": desc, "count": len(cand), "top": [r["t"] for r in cand[:TOP]]})
    shown = {t for s_ in out for t in s_["top"]}
    ondeck = [{"t": r["t"], "name": r.get("name", ""), "leg": r.get("leg"), "ext": r.get("ext"), "adr": r.get("adr"),
               "price": r.get("price")} for r in (kq or {}).get("extended", []) if (r.get("price") or 0) >= MIN_PRICE]
    return {"setups": out, "rows": {t: rows[t] for t in shown}, "rules": RULES, "kq_ondeck": ondeck[:10],
            "ath_known": sum(1 for t in shown if rows[t].get("ath_ok")), "levels_cached": len(levels)}


# ---------------------------------------------------------------------------
# Backtest (whole stored history; uses the 52-week high as the magnet)
# Each new signal (not on that list in the prior 5 sessions) is bought at the
# close with a stop 1 ADR below and sold at the close 5 sessions later.
# hit_hi = traded at or above the 52-week high within 5 sessions,
# hit_adr = rallied 1 ADR above entry within 5 sessions.
# ---------------------------------------------------------------------------
def _kq_basing(w, c_all):
    """Vectorized proxy of breadth/kq.py's 'Basing' section for every day."""
    from .kq import CFG
    h, l, c, o, v = w["h"], w["l"], w["c"], w["o"], w["v"]
    adr = ((h / l).rolling(20).mean() - 1) * 100
    dvol = (c * v).rolling(20).mean()
    pr = []
    for n in (21, 63, 126):
        r = c_all / c_all.shift(n) - 1
        pr.append(r.rank(axis=1, pct=True)[c.columns] * 100)
    top = pd.concat(pr).groupby(level=0).max().reindex(c.index)
    s10, s20, s50 = (c.rolling(n).mean() for n in (10, 20, 50))
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()]).groupby(level=0).max().reindex(c.index)
    atr = tr.rolling(14).mean()
    hh, ll = h.rolling(CFG["leg_days"]).max(), l.rolling(CFG["leg_days"]).min()
    vx = v / v.rolling(50).mean().shift(1)
    gap_ev = ((o / pc - 1) >= CFG["gap"]) & (vx >= CFG["gap_vx"])
    event = (gap_ev | (vx >= CFG["spike_vx"])).astype(float).rolling(CFG["event_days"]).max() > 0
    sign = np.sign(c - s10)
    cross = (sign.diff().fillna(0) != 0).astype(int).rolling(19).sum()
    cand = ((c >= CFG["min_price"]) & (adr >= CFG["min_adr"]) & (dvol >= CFG["min_dvol"]) & (top >= CFG["top_pct"])
            & (c > s50) & (s20 > s50) & (hh / ll - 1 >= CFG["min_leg"]) & (c / hh - 1 >= CFG["max_off"]))
    basing = (cand & ~event & ((s20 - s20.shift(10)) / atr >= CFG["flat_angle"]) & ((c - s20) / atr < CFG["extended"])
              & ((h.rolling(10).max() - l.rolling(10).min()) / atr <= CFG["loose_range"]) & (cross < CFG["chop_cross"]))
    return basing


def _group_hist(c, ema21, ema50, ratings, mem, days, spy):
    """Group Strength and rank for every day at once: a vectorized copy of
    strength.group_inputs + strength_scores (same inputs, same weights)."""
    from . import strength as S2
    mem = {g: [t for t in ts_ if t in c.columns] for g, ts_ in mem.items()}
    mem = {g: ts_ for g, ts_ in mem.items() if ts_}
    cols = sorted({t for ts_ in mem.values() for t in ts_})
    cc = c[cols]
    ok = cc.notna()
    rets = {n: cc / cc.shift(n) - 1 for n, _ in S2.STR_HORIZONS}
    spy_r = {n: spy / spy.shift(n) - 1 for n, _ in S2.STR_HORIZONS}
    a21 = (cc > ema21[cols]) & ok
    a50 = (cc > ema50[cols]) & ok
    rat = ratings.reindex(index=c.index, columns=cols).where(ok)
    rel, part, lead, nn = {}, {}, {}, {}
    for g, ts_ in mem.items():
        n_ok = ok[ts_].sum(axis=1)
        num = pd.Series(0.0, index=c.index); den = pd.Series(0.0, index=c.index)
        for n, wt in S2.STR_HORIZONS:
            med = rets[n][ts_].where(ok[ts_]).median(axis=1, skipna=True)
            good = med.notna() & spy_r[n].notna()
            num = num + (wt * (med - spy_r[n])).where(good, 0.0)
            den = den + pd.Series(np.where(good, wt, 0.0), index=c.index)
        rel[g] = (num / den.replace(0, np.nan)).where(n_ok > 0)
        part[g] = ((a21[ts_].sum(axis=1) + a50[ts_].sum(axis=1)) / (2 * n_ok.replace(0, np.nan)))
        lead[g] = rat[ts_].median(axis=1, skipna=True).where(n_ok > 0)
        nn[g] = n_ok
    rel, part, lead, nn = (pd.DataFrame(x) for x in (rel, part, lead, nn))
    present = nn > 0
    score = 0.0
    for k, wt in S2.STR_WEIGHTS.items():
        f = {"rel": rel, "part": part, "lead": lead}[k].where(present)
        score = score + wt * f.rank(axis=1, pct=True).where(present).fillna(0.5)
    score = score * 100
    kk = (nn.astype(float) / S2.SHRINK_N).clip(upper=1.0)
    strength = (50 + (score - 50) * kk).round(1).where(present)
    idx = c.index[days]
    strength = strength.loc[idx]
    return strength, strength.rank(axis=1, ascending=False, method="first")


def _per_stock(gframe, mem, cols, how="max"):
    """Days x stocks frame of the best value across each stock's groups."""
    out = pd.DataFrame(np.nan, index=gframe.index, columns=cols)
    by_t = {}
    for g, ts_ in mem.items():
        if g in gframe.columns:
            for t in ts_:
                if t in out.columns:
                    by_t.setdefault(t, []).append(g)
    for t, gs in by_t.items():
        out[t] = gframe[gs].max(axis=1) if how == "max" else gframe[gs].any(axis=1)
    return out


def vcp_mask(w, t, long_sma=200):
    """Minervini trend template + VCP contraction, vectorized (days x tickers).
    The live list uses the real 150/200-day template; the backtest uses
    long_sma=150 (100/150) because only ~1 year of bars is stored."""
    V = RULES["vcp"]
    c, h, l = w["c"], w["h"], w["l"]
    mid = 150 if long_sma == 200 else 100
    s50, sm, sl = c.rolling(50).mean(), c.rolling(mid).mean(), c.rolling(long_sma).mean()
    lo52 = l.rolling(252, min_periods=long_sma).min()
    tt = ((c > sm) & (c > sl) & (sm > sl) & (sl > sl.shift(21)) & (s50 > sm) & (c > s50)
          & (c >= (1 + V["low_up"]) * lo52) & (t["off_high"] >= V["off"]))
    rng = lambda n: h.rolling(n).max() / l.rolling(n).min() - 1
    r10, r20, r40 = rng(10), rng(20), rng(40)
    contract = (r10 < V["r10"] * r20) & (r20 < V["r20"] * r40) & (t["vdry"] <= V["vdry"])
    return tt & contract, {"r10": r10, "r20": r20, "r40": r40, "hi10": h.rolling(10).max(), "lo10": l.rolling(10).min()}


def vcp_today(w, t, focus):
    """Live VCP candidates on the latest day with pivot and stop."""
    cols = [x for x in focus if x in w["c"].columns]
    ww = {k: v[cols] for k, v in w.items()}
    tt = {k: (v[cols] if isinstance(v, pd.DataFrame) else v) for k, v in t.items()}
    m, f = vcp_mask(ww, tt, long_sma=200)
    last = m.iloc[-1].fillna(False)
    out = {}
    for tk in last[last].index:
        piv = float(f["hi10"].iloc[-1][tk])
        lo = float(f["lo10"].iloc[-1][tk])
        out[tk] = {"pivot": round(piv, 2), "stop": round(max(lo, piv * (1 - RULES["vcp"]["stop_cap"])), 2),
                   "r10": round(float(f["r10"].iloc[-1][tk]), 4), "r20": round(float(f["r20"].iloc[-1][tk]), 4),
                   "r40": round(float(f["r40"].iloc[-1][tk]), 4)}
    return out


def backtest(w_all, t_all, ratings, liquid_all, members, sub_members, focus, breadth, first=110, hold=5, signals=False):
    from . import setups as SU
    from . import strength as S2
    cols = [x for x in focus if x in w_all["c"].columns]
    w = {k: v[cols] for k, v in w_all.items()}
    t = {k: (v[cols] if isinstance(v, pd.DataFrame) else v) for k, v in t_all.items()}
    c = w["c"]
    dates = c.index
    N = len(dates)
    if N < first + hold + 5:
        return None
    spy = w_all["c"].get(S2.config.BENCHMARK)
    if spy is None:
        return None
    rating = ratings.reindex(index=dates, columns=cols)
    ema21_all = w_all["c"].ewm(span=21, adjust=False, min_periods=21).mean()
    ema50_all = t_all["ema50"]
    days = list(range(max(91, first - 25), N))
    th_s, th_r = _group_hist(w_all["c"], ema21_all, ema50_all, ratings, members, days, spy)
    sb_s, sb_r = _group_hist(w_all["c"], ema21_all, ema50_all, ratings, sub_members, days, spy)
    th_s, th_r, sb_s, sb_r = (x.reindex(dates) for x in (th_s, th_r, sb_s, sb_r))
    R = RULES["rotation"]
    th_rise = ((th_r.shift(20) - th_r) >= R["theme_rise"]) & (th_s >= R["theme_str"])
    sb_rise = ((sb_r.shift(20) - sb_r) >= R["sub_rise"]) & (sb_s >= R["sub_str"])
    best_th = _per_stock(th_s, members, cols)
    sub_str = _per_stock(sb_s, sub_members, cols)
    grp = pd.concat([best_th, sub_str]).groupby(level=0).max().reindex(dates)
    in_rise = (_per_stock(th_rise.astype(float), members, cols).fillna(0) > 0) | (_per_stock(sb_rise.astype(float), sub_members, cols).fillna(0) > 0)

    e21 = c / c.ewm(span=21, adjust=False, min_periods=21).mean() - 1
    e50 = c / t["ema50"] - 1
    off = t["off_high"]
    base_ok = liquid_all[cols] & (c >= MIN_PRICE)
    rs5 = rating - rating.shift(5)
    masks = {}
    A = RULES["ath"]
    masks["ath"] = base_ok & (rating >= A["rs"]) & (grp >= A["grp"]) & (off >= A["off"]) & (e21 > 0) & (t["adr"] >= A["adr"])
    P = RULES["pullback"]
    masks["pullback"] = (base_ok & (rating >= P["rs"]) & (grp >= P["grp"]) & (e21.abs() <= P["e21"]) & (e50 > 0)
                         & (off >= P["off_lo"]) & (off <= P["off_hi"]) & (t["vdry"] <= P["vdry"]))
    masks["rotation"] = (base_ok & in_rise & (rating >= R["rs"]) & (rs5 >= 0) & (off >= R["off_lo"]) & (off <= R["off_hi"])
                         & (e21 >= 0) & (e21 <= R["e21_hi"]))
    masks["kq"] = base_ok & _kq_basing(w, w_all["c"])
    RN = RULES["round"]
    Cv = c.to_numpy()
    with np.errstate(invalid="ignore"):
        idx = np.searchsorted(ROUND, np.nan_to_num(Cv, nan=0.0) * (1 + RN["min_pct"]), side="left")
    LVL = np.where(idx < len(ROUND), ROUND[np.minimum(idx, len(ROUND) - 1)], np.nan)
    LVL[~np.isfinite(Cv)] = np.nan
    lvl_df = pd.DataFrame(LVL, index=dates, columns=cols)
    r_adr = (lvl_df / c - 1) * 100 / t["adr"]
    masks["round"] = (base_ok & (rating >= RN["rs"]) & (e21 > 0) & (e50 > 0) & (t["adr"] >= RN["adr"]) & (r_adr <= RN["dist_adr"]))
    h52_df = w["h"].rolling(252, min_periods=60).max()
    round_fresh = lvl_df > h52_df
    round_century = (lvl_df % 100 == 0) | (lvl_df == 50)
    vm, VF = vcp_mask(w, t, long_sma=150)
    masks["vcp"] = base_ok & vm & (rating >= RULES["vcp"]["rs"])
    burst, checks, lynch, ep = SU.masks(w, t, liquid_all[cols])
    ant = SU.anticipation_mask(w, t, rating, liquid_all[cols])
    angles = sum(m.fillna(False).astype(int) for m in masks.values()) + (burst & (lynch >= 5)).fillna(False).astype(int) \
        + ant.fillna(False).astype(int)

    O, C, H, L = (w[k].to_numpy() for k in ("o", "c", "h", "l"))
    hiN = w["h"][::-1].rolling(hold, min_periods=1).max()[::-1].shift(-1).to_numpy()
    h52 = w["h"].rolling(252, min_periods=60).max().to_numpy()
    adr = t["adr"].to_numpy()
    br = breadth.reindex(dates)
    regime = np.where((br["ratio5"] >= 1.5) & (br["ratio10"] >= 1.5), "strong", np.where(br["ratio10"] < 1, "weak", "mixed"))
    from . import metrics as MT
    tw = MT.thrust_window(breadth, dates)
    ANG = angles.to_numpy()
    if True:      # per-signal features and forward outcomes: pick-rule replay, and research via signals=True
        feats = {"rs": rating, "grp": grp, "e21": e21, "e50": e50, "off": off, "adr": t["adr"], "tight": t["tight5"],
                 "vdry": t["vdry"], "d60": c / c.shift(60) - 1, "rs5": rs5}
        F = {k: v.to_numpy() for k, v in feats.items()}
        Cn = c.to_numpy()
        fwd = c.shift(-hold).to_numpy() / Cn - 1
        HI5a = w["h"].rolling(5).max().to_numpy()
        HI10a = w["h"].rolling(10).max().to_numpy()
        ADRa = t["adr"].to_numpy()

        def next_trade(key, i, j):
            """How the pick would actually be traded from the next session: flags/VCPs need
            their trigger (5-day / 10-day high) hit that day, filled at max(trigger, open);
            everything else buys the next open. Exit at the close `hold` sessions after entry.
            Returns (trigger distance in ADRs, filled, return)."""
            trig = HI5a[i, j] if key == "kq" else HI10a[i, j] if key == "vcp" else np.nan
            dist = (trig / Cn[i, j] - 1) * 100 / ADRa[i, j] if np.isfinite(trig) and ADRa[i, j] > 0 else 0.0
            k = i + 1
            if k + hold >= N:
                return dist, None, np.nan
            if np.isfinite(trig):
                tp = trig * 1.001
                if not H[k, j] >= tp:
                    return dist, False, np.nan
                e = max(tp, O[k, j])
            else:
                e = O[k, j]
            x = C[k + hold, j]
            return dist, True, (x / e - 1) if (np.isfinite(e) and e > 0 and np.isfinite(x)) else np.nan

        # conviction tags at the signal (the same lists as the TradingView export)
        nhF, leadF = S2.rs_line_flags(c, spy)
        best_th_rank = -_per_stock(-th_r, members, cols)
        best_sb_rank = -_per_stock(-sb_r, sub_members, cols)
        hh60, ll60 = w["h"].rolling(60).max(), w["l"].rolling(60).min()
        TAGF = {"lead": leadF, "star": nhF, "rs99": rating >= 99, "riser": (rs5 >= 15) & (rating >= 60),
                "burst": burst & (lynch >= 5), "antic": ant, "top_theme": best_th_rank <= 2, "top_sub": best_sb_rank <= 3,
                "htf": (hh60 / ll60 - 1) >= 0.9, "ep": ep.astype(float).rolling(5, min_periods=1).max() > 0}
        TAGA = {k: v.reindex(index=dates, columns=cols).fillna(False).astype(bool).to_numpy() for k, v in TAGF.items()
                if v is not None}
        rows = []
        for key, m in masks.items():
            mm = m.fillna(False)
            mm = (mm & ~(mm.shift(1).astype(float).rolling(5, min_periods=1).max().fillna(0) > 0)).to_numpy()
            for i, j in np.argwhere(mm):
                if i < first:
                    continue
                dist, filled, nret = next_trade(key, i, j)
                rows.append({"setup": key, "i": int(i), "date": str(dates[i].date()), "t": cols[j], "regime": str(regime[i]),
                             "thrust": bool(tw[i]), "angles": int(ANG[i, j]), "fwd": float(fwd[i, j]) if i + hold < N else np.nan,
                             "trig_adr": float(dist), "filled": filled, "fwd_next": float(nret),
                             **{k: float(F[k][i, j]) for k in F}, **{"tag_" + k: bool(v[i, j]) for k, v in TAGA.items()}})
        sig_df = pd.DataFrame(rows)

    def outcomes(mask, dedupe=True, every=1):
        m = mask.fillna(False)
        if dedupe:   # new signals only: not on the list in the prior 5 sessions
            m = m & ~(m.shift(1).astype(float).rolling(5, min_periods=1).max().fillna(0) > 0)
        m = m.to_numpy()
        if every > 1:
            m = m & (np.arange(N) % every == 0)[:, None]
        res = []
        for i, j in np.argwhere(m):
            if i < first or i + hold >= N:
                continue
            e = C[i, j]
            st = e * (1 - adr[i, j] / 100) if np.isfinite(adr[i, j]) else np.nan   # stop 1 ADR below entry
            if not (np.isfinite(e) and e > 0 and 0 < st < e):
                continue
            x = None
            for k in range(1, hold + 1):
                if L[i + k, j] <= st:
                    x = min(st, O[i + k, j]); break
            if x is None:
                x = C[i + hold, j]
            if not np.isfinite(x):
                continue
            tgt_hi = max(h52[i, j], e * 1.005) if np.isfinite(h52[i, j]) else np.nan
            res.append((i, (x - e) / (e - st), hiN[i, j] >= tgt_hi, hiN[i, j] >= e * (1 + adr[i, j] / 100),
                        C[i + hold, j] / e - 1, ANG[i, j], j))
        return res

    E10, E20 = t["ema10"].to_numpy(), t["ema20"].to_numpy()
    S50 = c.rolling(50).mean().to_numpy()
    HI5 = w["h"].rolling(5).max().to_numpy()
    HI10, LO10 = VF["hi10"].to_numpy(), VF["lo10"].to_numpy()

    def _new(mask):
        m = mask.fillna(False)
        return (m & ~(m.shift(1).astype(float).rolling(5, min_periods=1).max().fillna(0) > 0)).to_numpy()

    def _tuple(i, j, e, st, x_blend, k_entry):
        """Shared result row: R, hit 52-wk high / +1 ADR within `hold` sessions of entry, return."""
        end = min(N - 1, k_entry + hold)
        hh = np.nanmax(H[k_entry + 1:end + 1, j]) if end > k_entry else np.nan
        tgt_hi = max(h52[i, j], e * 1.005) if np.isfinite(h52[i, j]) else np.nan
        risk = max(e - st, e * adr[i, j] / 100 * RISK_FLOOR) if np.isfinite(adr[i, j]) else e - st
        return (i, (x_blend - e) / risk, hh >= tgt_hi, hh >= e * (1 + adr[i, j] / 100), x_blend / e - 1, ANG[i, j], j)

    def sim_kq(mask, trail):
        """Kristjan: buy stop above the 5-day high within 5 sessions, stop = entry-day low,
        sell half at the close 3 sessions after entry, trail the rest until a close
        below the 10 (or 20) EMA. Open trades are marked at the last close."""
        TR = E10 if trail == 10 else E20
        res = []
        for i, j in np.argwhere(_new(mask)):
            if i < first or i + 1 >= N:
                continue
            tp = HI5[i, j] * 1.001
            for k in range(i + 1, min(N, i + 6)):
                if H[k, j] < tp:
                    continue
                e = max(tp, O[k, j]); st = L[k, j]
                if not (np.isfinite(e) and 0 < st < e) or (e - st) > e * adr[i, j] / 100:
                    break      # he passes when the day's low is more than 1 ADR away
                half = None; x = None
                for q in range(k + 1, min(N, k + 41)):
                    if L[q, j] <= st:
                        x = min(st, O[q, j]); break
                    if half is None and q == k + 3:
                        half = C[q, j]
                    if q > k + 3 and C[q, j] < TR[q, j]:
                        x = C[q, j]; break
                if x is None:
                    x = C[min(N - 1, k + 40), j]
                xb = x if half is None else 0.5 * half + 0.5 * x
                if np.isfinite(xb):
                    res.append(_tuple(i, j, e, st, xb, k))
                break
        return res

    def sim_vcp(mask):
        """Minervini: buy stop above the 10-day high (pivot) within 5 sessions, stop under
        the 10-day low capped at 8%, exit on a close below the 50-day SMA (max 60 sessions)."""
        res = []
        for i, j in np.argwhere(_new(mask)):
            if i < first or i + 1 >= N:
                continue
            tp = HI10[i, j] * 1.001
            for k in range(i + 1, min(N, i + 6)):
                if H[k, j] < tp:
                    continue
                e = max(tp, O[k, j]); st = max(LO10[i, j], e * (1 - RULES["vcp"]["stop_cap"]))
                if not (np.isfinite(e) and 0 < st < e):
                    break
                x = None
                if L[k, j] <= st:
                    x = st
                for q in range(k + 1, min(N, k + 61)):
                    if x is not None:
                        break
                    if L[q, j] <= st:
                        x = min(st, O[q, j]); break
                    if C[q, j] < S50[q, j]:
                        x = C[q, j]; break
                if x is None:
                    x = C[min(N - 1, k + 60), j]
                if np.isfinite(x):
                    res.append(_tuple(i, j, e, st, x, k))
                break
        return res

    def summarize(res, key=None):
        o = {}
        for k in ("all", "strong", "mixed", "weak", "thrust"):
            rr = [r for r in res if k == "all" or (tw[r[0]] if k == "thrust" else regime[r[0]] == k)]
            if not rr:
                o[k] = {"n": 0}
                continue
            a = np.array([r[1:5] for r in rr], dtype=float)
            o[k] = {"n": len(rr), "avg_r": round(float(np.nanmean(a[:, 0])), 3), "win": round(float(np.nanmean(a[:, 0] > 0)), 3),
                    "hit_hi": round(float(np.nanmean(a[:, 1])), 3), "hit_adr": round(float(np.nanmean(a[:, 2])), 3),
                    "ret": round(float(np.nanmean(a[:, 3])), 4)}
        return o

    out = {"from": str(dates[first].date()), "to": str(dates[N - 1 - hold].date()), "hold": hold,
           "days": {**{k: int((regime[first:N - hold] == k).sum()) for k in ("strong", "mixed", "weak")},
                    "thrust": int(tw[first:N - hold].sum())}, "setups": {}}
    allres = []
    for key, m in masks.items():
        r = sim_kq(m, 10) if key == "kq" else sim_vcp(m) if key == "vcp" else outcomes(m)
        out["setups"][key] = summarize(r)
        out.setdefault("recent", {})[key] = summarize([x for x in r if x[0] >= N - hold - RECENT])["all"]
        allres += r
    out["kq_trail20"] = summarize(sim_kq(masks["kq"], 20))
    # Round Number Magnet detail: did the level get tagged / closed above, fresh vs retest, century marks vs smaller levels
    def touch(mask):
        m = _new(mask)
        o = {}
        for k in ("all", "strong", "mixed", "weak"):
            tt, cl = [], []
            for i, j in np.argwhere(m):
                if i < first or i + hold >= N or (k != "all" and regime[i] != k):
                    continue
                L_ = LVL[i, j]
                tt.append(np.nanmax(H[i + 1:i + hold + 1, j]) >= L_)
                cl.append(np.nanmax(C[i + 1:i + hold + 1, j]) >= L_)
            o[k] = {"n": len(tt), "touch": round(float(np.mean(tt)), 3) if tt else None, "close_above": round(float(np.mean(cl)), 3) if cl else None}
        return o
    rmask = masks["round"]
    uptrend = base_ok & (rating >= RN["rs"]) & (e21 > 0) & (e50 > 0) & (t["adr"] >= RN["adr"])
    out["round"] = {"fresh": summarize(outcomes(rmask & round_fresh)), "retest": summarize(outcomes(rmask & ~round_fresh)),
                    "century": summarize(outcomes(rmask & round_century)), "smaller": summarize(outcomes(rmask & ~round_century)),
                    "base": summarize(outcomes(uptrend & ~(r_adr <= RN["dist_adr"]), dedupe=False, every=5)),
                    "touch": touch(rmask), "touch_fresh": touch(rmask & round_fresh)}
    out["exits"] = {"kq": "buy above the 5-day high, stop entry-day low, half out after 3 days, rest on a close below the 10 EMA",
                    "vcp": "buy above the 10-day high, stop under the 10-day low (max 8%), exit on a close below the 50-day",
                    "other": f"buy the close, stop 1 ADR, exit after {hold} sessions"}
    out["base"] = summarize(outcomes(base_ok & (rating >= 80), dedupe=False, every=5))
    out["base_near"] = summarize(outcomes(base_ok & (off >= A["off"]) & (e21 > 0) & (t["adr"] >= A["adr"])))
    uniq = list({(r[0], r[6]): r for r in allres}.values())   # one trade per stock-day across lists
    out["confluence"] = {"1": summarize([r for r in uniq if r[5] <= 1]), "2+": summarize([r for r in uniq if r[5] >= 2])}
    try:
        out["pick_replay"] = pick_replay(sig_df, hold)
        out["tag_stats"] = tag_stats(sig_df)
    except Exception:
        out["pick_replay"] = None
    return (out, sig_df) if signals else out


def pick_key(rs, d60):
    """The top-pick rule: highest RS Rating first, then the bigger 60-day gain."""
    return (-(rs if rs == rs and rs is not None else 0), -(d60 if d60 == d60 and d60 is not None else 0))


ACTIONABLE_ADR = 1.0   # a flag/VCP trigger counts as "actionable today" within 1 ADR of the close


def pick_replay(df, hold=5, min_cands=3):
    """Replay the top-pick rule on past days, traded the way the live picks are:
    each day, among setup signals that are actionable (flag/VCP trigger within 1 ADR
    of the close; other setups always), pick the highest RS (ties: 60-day gain).
    Entry next session (open, or the trigger if it's hit that day; no fill = no trade),
    exit at the close `hold` sessions later, no stop. Benchmark: the average actionable
    candidate traded the same way."""
    if df is None or df.empty:
        return None
    df = df.drop_duplicates(["i", "t"])
    df = df[df["trig_adr"] <= ACTIONABLE_ADR]
    picks, avgs, nofill, meta = [], [], 0, []
    for i, g in df.groupby("i"):
        if len(g) < min_cands or g["filled"].isna().all():
            continue
        best = min(g.itertuples(), key=lambda r: pick_key(r.rs, r.d60))
        done = g[g["fwd_next"].notna()]
        if best.filled is False:
            nofill += 1
            continue
        if best.fwd_next != best.fwd_next or done.empty:
            continue
        picks.append(best.fwd_next); avgs.append(done["fwd_next"].mean())
        meta.append((best.setup, "thrust" if getattr(best, "thrust", False) else best.regime, best.date))
    if len(picks) < 10:
        return None
    p, a = np.array(picks), np.array(avgs)

    def grp(ix):
        v, c = p[ix], a[ix]
        return {"n": int(len(v)), "ret": round(float(v.mean()), 4), "win": round(float((v > 0).mean()), 3),
                "cand": round(float(c.mean()), 4), "beat": round(float((v > c).mean()), 3)}
    breakdown = {}
    for name, pos in (("setup", 0), ("regime", 1), ("month", 2)):
        keys = [m[pos][:7] if name == "month" else m[pos] for m in meta]
        breakdown[name] = {k: grp(np.array([q == k for q in keys])) for k in sorted(set(keys))}
    curve = np.round(np.cumsum(p - a), 4).tolist()
    rel = p - a
    t = float(rel.mean() / (rel.std(ddof=1) / np.sqrt(len(rel)))) if rel.std(ddof=1) > 0 else 0.0
    return {"days": len(p), "no_fill": nofill, "pick_ret": round(float(p.mean()), 4), "avg_ret": round(float(a.mean()), 4),
            "edge": round(float(rel.mean()), 4), "t": round(t, 2), "beat": round(float((rel > 0).mean()), 3),
            "win": round(float((p > 0).mean()), 3), "hold": hold,
            "from": str(df["date"].min()), "to": str(df["date"].max()),
            "breakdown": breakdown, "edge_curve": curve[::max(1, len(curve) // 120)]}


TAGS = {  # key: (label, kind) - kind 'plus' adds conviction, 'warn' is a caution flag
    "lead": ("RS line ahead of price ⚑", "plus"), "star": ("RS line new high ★", "plus"), "rs99": ("RS 99", "plus"),
    "riser": ("Fast riser (RS +15 in 5 days)", "plus"), "burst": ("Burst today (2LYNCH 5+)", "plus"),
    "antic": ("Anticipation coil", "plus"), "top_theme": ("Top-2 theme", "plus"), "top_sub": ("Top-3 sub-theme", "plus"),
    "htf": ("High tight flag (90%+ leg)", "plus"), "mkt10": ("Top 10 in the market", "plus"),
    "ep": ("Recent gap / news (EP)", "warn"), "bottom_theme": ("Bottom-2 theme", "warn"),
}


def tag_stats(df):
    """For each tag: setup signals WITH the tag vs WITHOUT it, traded the actionable way
    (next-session entry, 5-session hold). diff = with - without; t = Welch t-stat."""
    if df is None or df.empty:
        return None
    d = df[df["fwd_next"].notna()].drop_duplicates(["i", "t"])
    out = {"n": int(len(d)), "avg": round(float(d["fwd_next"].mean()), 4)}
    for k in TAGS:
        col = "tag_" + k
        if col not in d:
            continue
        a, b = d.loc[d[col], "fwd_next"], d.loc[~d[col], "fwd_next"]
        if len(a) < 5 or len(b) < 5:
            out[k] = {"n": int(len(a))}
            continue
        se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
        out[k] = {"n": int(len(a)), "with": round(float(a.mean()), 4), "without": round(float(b.mean()), 4),
                  "win": round(float((a > 0).mean()), 3), "diff": round(float(a.mean() - b.mean()), 4),
                  "t": round(float((a.mean() - b.mean()) / se), 2) if se > 0 else 0.0}
    return out
