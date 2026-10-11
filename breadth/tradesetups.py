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
Coiled Leader   KQ screen 'Basing' list, RS >= 90, group >= 80; the magnet is the
                next old high above (52-week high or an older peak).

Each list is ranked by the Leaders score (breadth/leaders.py). "Setups hit"
counts how many buying angles a stock sits on at once: the four lists above,
a 2LYNCH 5+ momentum burst, and the anticipation list.
"""
import numpy as np
import pandas as pd

from . import leaders as LD

MIN_PRICE = 10.0
TOP = 5
SETUPS = [
    ("ath", "ATH Magnet", "Leader within reach of its all-time high: momentum and attention pulling it through."),
    ("pullback", "Leader Pullback", "Leader back at its 21 EMA, uptrend intact, sellers drying up: buy the dip, not the chase."),
    ("rotation", "Rotation Rookie", "A theme or sub-theme money is newly moving into; the stock hasn't run yet."),
    ("coiled", "Coiled Leader", "Top-RS name basing tight in a strong group, with old highs overhead as the magnet."),
]
RULES = {
    "ath": {"rs": 90, "grp": 80, "off": -0.03, "adr": 3.0, "ath_adr": 2.0},
    "pullback": {"rs": 85, "grp": 70, "e21": 0.03, "off_lo": -0.20, "off_hi": -0.04, "vdry": 0.9},
    "rotation": {"rs": 80, "theme_rise": 10, "theme_str": 55, "sub_rise": 15, "sub_str": 60,
                 "off_lo": -0.12, "off_hi": -0.03, "e21_hi": 0.06},
    "coiled": {"rs": 90, "grp": 80},
}


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
            "52-wk high" if abs(nxt - h52) <= h52 * 0.001 else "old high")
    if adr:
        out["ath_adr"] = round(out["ath_pct"] * 100 / adr, 1)
        out["mag_adr"] = round(out["mag_pct"] * 100 / adr, 1) if nxt else None
    return out


# ---------------------------------------------------------------------------
# Today's lists
# ---------------------------------------------------------------------------
def build(stocks, themes, subthemes, kq=None, lists=None, levels=None):
    levels = levels or {}
    ts = {r["theme"]: r.get("strength") for r in themes}
    ss = {r["theme"]: r.get("strength") for r in subthemes}
    rising = {r["theme"] for r in themes if r.get("s_r_m4") and r.get("strength") is not None
              and r["s_r_m4"] - r["s_rank"] >= RULES["rotation"]["theme_rise"] and r["strength"] >= RULES["rotation"]["theme_str"]}
    rising_sub = {r["theme"] for r in subthemes if r.get("s_r_m4") and r.get("strength") is not None
                  and r["s_r_m4"] - r["s_rank"] >= RULES["rotation"]["sub_rise"] and r["strength"] >= RULES["rotation"]["sub_str"]}
    basing = {r["t"] for r in (kq or {}).get("basing", [])}
    bursts = {r["t"] for r in (lists or {}).get("bursts", []) if (r.get("lynch") or 0) >= 5}
    antic = {r["t"] for r in (lists or {}).get("anticipation", [])}
    lead10 = {r["t"] for r in LD.rank(stocks, themes, subthemes, n=10)}

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
        R = RULES["coiled"]
        if s["t"] in basing and rs >= R["rs"] and grp >= R["grp"]:
            hit.add("coiled")
        if not hit:
            continue
        angles = set(hit) | ({"burst"} if s["t"] in bursts else set()) | ({"antic"} if s["t"] in antic else set())
        rows[s["t"]] = {
            "t": s["t"], "name": s.get("name", ""), "price": s["price"], "score": score, "rsr": rs, "rsr5": s.get("rsr5"),
            "theme": bt, "theme_str": bstr, "sub": s.get("sub"), "sub_str": sub, "grp": grp,
            "off_hi": s.get("off_hi"), "e21": e21, "e50": e50, "adr": s.get("adr"), "vdry": vdry, "tight": s.get("tight"),
            "tier": s.get("tier"), "star": bool(s.get("rs_nh")), "leader": s["t"] in lead10,
            "rising": in_rise[0] if in_rise else None, "setups": sorted(hit), "angles": sorted(angles), "hits": len(angles),
            **m,
        }
    out = []
    for key, name, desc in SETUPS:
        cand = [r for r in rows.values() if key in r["setups"]]
        cand.sort(key=lambda r: (-r["score"], -r["rsr"], r["t"]))
        out.append({"key": key, "name": name, "desc": desc, "count": len(cand), "top": [r["t"] for r in cand[:TOP]]})
    shown = {t for s_ in out for t in s_["top"]}
    return {"setups": out, "rows": {t: rows[t] for t in shown}, "rules": RULES,
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


def backtest(w_all, t_all, ratings, liquid_all, members, sub_members, focus, breadth, first=110, hold=5):
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
    C_ = RULES["coiled"]
    masks["coiled"] = base_ok & _kq_basing(w, w_all["c"]) & (rating >= C_["rs"]) & (grp >= C_["grp"])
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
    ANG = angles.to_numpy()

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

    def summarize(res, key=None):
        o = {}
        for k in ("all", "strong", "mixed", "weak"):
            rr = [r for r in res if k == "all" or regime[r[0]] == k]
            if not rr:
                o[k] = {"n": 0}
                continue
            a = np.array([r[1:5] for r in rr], dtype=float)
            o[k] = {"n": len(rr), "avg_r": round(float(np.nanmean(a[:, 0])), 3), "win": round(float(np.nanmean(a[:, 0] > 0)), 3),
                    "hit_hi": round(float(np.nanmean(a[:, 1])), 3), "hit_adr": round(float(np.nanmean(a[:, 2])), 3),
                    "ret": round(float(np.nanmean(a[:, 3])), 4)}
        return o

    out = {"from": str(dates[first].date()), "to": str(dates[N - 1 - hold].date()), "hold": hold,
           "days": {k: int((regime[first:N - hold] == k).sum()) for k in ("strong", "mixed", "weak")}, "setups": {}}
    allres = []
    for key, m in masks.items():
        r = outcomes(m)
        out["setups"][key] = summarize(r)
        allres += r
    out["base"] = summarize(outcomes(base_ok & (rating >= 80), dedupe=False, every=5))
    out["base_near"] = summarize(outcomes(base_ok & (off >= A["off"]) & (e21 > 0) & (t["adr"] >= A["adr"])))
    uniq = list({(r[0], r[6]): r for r in allres}.values())   # one trade per stock-day across lists
    out["confluence"] = {"1": summarize([r for r in uniq if r[5] <= 1]), "2+": summarize([r for r in uniq if r[5] >= 2])}
    return out
