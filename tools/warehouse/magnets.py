"""Trade scorecard step 2 · liquidity magnets (plan: tools/warehouse/PLAN2.md v9.1, graded 86%).

Stages (each writes into data/warehouse/magnets/):
  python -m tools.warehouse.magnets build    --data DIR   Yahoo parts → validation.json + fills.parquet (outcomes stored, not read)
  python -m tools.warehouse.magnets power                 power table from non-outcome columns + simulated label power
  python -m tools.warehouse.magnets test                  H2a / H2b / stopped short / exploratory → results_magnets.txt
DIR = a checkout of branch `warehouse-data` (daily/*.parquet, meta/*.json).
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from breadth import config, emaprob, metrics, store, strength  # noqa: E402
from tools.warehouse.build import EP_MAX, TRIG, spy_groups, trade, weekly_atr  # noqa: E402,F401

OUT = ROOT / "data" / "warehouse" / "magnets"
C_START, C_END = pd.Timestamp("2015-03-02"), pd.Timestamp("2025-09-05")      # C: S ≥ C_START, fill + 40 < C_END
D_START, D_END = pd.Timestamp("2025-09-05"), pd.Timestamp("2026-06-26")
ERAS = [("e1", "2015-03-01", "2018-12-31"), ("e2", "2019-01-01", "2021-12-31"), ("e3", "2022-01-01", "2025-08-31")]
SPLIT_R = [2, 0.5, 3, 1 / 3, 1.5, 4, 0.25]
HOLD = 40


# --------------------------------------------------------------------------------------------------------------- data
def load(data):
    data = Path(data)
    parts = sorted((data / "daily").glob("part_*.parquet"))
    B = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
    B = B.drop_duplicates(["t", "date"], keep="last")
    meta = {}
    for p in sorted((data / "meta").glob("part_*.json")):
        meta.update(json.loads(p.read_text()))
    W = {k: B.pivot(index="date", columns="t", values=k).sort_index().astype("float64") for k in ("o", "h", "l", "c", "v")}
    idx = W["c"].index
    for k in W:
        W[k] = W[k].reindex(idx)
    return W, meta


def screen(o, h, l, c):
    """v4 bad-bar screen: a spike high (> 1.25 × max(o, c)) not confirmed next session (next high < 0.9 × it) → max(o, c); lows mirrored.
    Used only for level-forming bars and ADR / RS inputs (v9.1 rule 2); outcome bars stay raw."""
    top, bot = np.maximum(o, c), np.minimum(o, c)
    hs = h.where(~((h > 1.25 * top) & (h.shift(-1) < 0.9 * h)), top)
    ls = l.where(~((l < bot / 1.25) & (l.shift(-1) > l / 0.9)), bot)
    n = int(((h > 1.25 * top) & (h.shift(-1) < 0.9 * h)).sum().sum() + ((l < bot / 1.25) & (l.shift(-1) > l / 0.9)).sum().sum())
    return hs, ls, n


def bad_years(c, meta):
    """v6 rule 3: ticker-years with an unreversed split-ratio jump (not near a Yahoo split event)."""
    r = c / c.shift(1)
    out = {}
    for t in c.columns:
        s = r[t].dropna()
        hit = np.zeros(len(s), dtype=bool)
        for q in SPLIT_R:
            hit |= (np.abs(s.to_numpy() / q - 1) <= 0.03)
        if not hit.any():
            continue
        sp = {pd.Timestamp(x[0]) for x in (meta.get(t, {}).get("splits") or [])}
        cs = c[t]
        for d in s.index[hit]:
            if any(abs((d - x).days) <= 3 for x in sp):
                continue
            i = cs.index.get_loc(d)
            prev = cs.iloc[i - 1]
            later = cs.iloc[i + 1:i + 6]
            # reversed = price back within 15% of the pre-jump close inside 5 sessions
            if len(later) and (np.abs(later / prev - 1) <= 0.15).any():
                continue
            out.setdefault(t, set()).add(d.year)
    return out


def month_bars(meta, t):
    """Yahoo's monthly series ends with an extra row stamped with the latest trade date (the current month so far, duplicating the
    YYYY-MM-01 row); only true month bars (dated the 1st) are kept, so v9.1's 25–35-day spacing test sees the real series."""
    return [x for x in (meta.get(t, {}).get("monthly") or []) if str(x[0]).endswith("-01")]


def monthly_ok(t, meta, daily_first):
    """v9.1 rule 1: complete monthly history = first bar within 1 month of firstTradeDate and every gap 25–35 days.
    v7 rule 4 (weak recycling screen): daily first month vs monthly first month (only when the daily series starts after 2014-01),
    and month-end closes within 2% on overlapping months — checked in build()."""
    m = month_bars(meta, t)
    ft = meta.get(t, {}).get("first")
    if len(m) < 2 or ft is None:
        return False, "no monthly"
    d0 = pd.Timestamp(m[0][0])
    f0 = pd.Timestamp(int(ft), unit="s")
    if abs((d0.to_period("M") - f0.to_period("M")).n) > 1:
        return False, "starts late"
    ds = np.diff(pd.to_datetime([x[0] for x in m]).values).astype("timedelta64[D]").astype(int)
    if (ds < 25).any() or (ds > 35).any():
        return False, "not monthly"
    if daily_first is not None and daily_first > pd.Timestamp("2014-01-10"):
        if abs((daily_first.to_period("M") - d0.to_period("M")).n) > 1:
            return False, "recycled?"
    return True, ""


# ------------------------------------------------------------------------------------------------------------- levels
def levels_at_S(S, low_i, dates, Hs, Cd, mon, first_daily_m, band):
    """Frozen level set at S (v8 rule 1 + v4 age cap / untraded + v8 rule 2 seam).
    mon = [(Period month, high, close)] monthly.json bars for months BEFORE the first daily month; months from the first daily month on
    are rebuilt from screened daily highs / daily closes. Returns list of (level, source, level_date or Period)."""
    low_m = dates[low_i].to_period("M")
    # monthly series: pre-daily months from monthly.json + daily-built months, all ending before the leg-low month
    dm = pd.Series(Hs[:low_i], index=dates[:low_i])
    dmh = dm.groupby(dates[:low_i].to_period("M")).max()
    dmc = pd.Series(Cd[:low_i], index=dates[:low_i]).groupby(dates[:low_i].to_period("M")).last()
    months, highs = [], []
    for p, hi, _ in mon:
        if p < first_daily_m and p < low_m:
            months.append(p)
            highs.append(hi)
    for p, hi in dmh.items():
        if p < low_m and np.isfinite(hi):
            months.append(p)
            highs.append(float(hi))
    lv = []
    for i in range(3, len(months) - 3):
        if highs[i] > max(highs[i - 3:i]) and highs[i] > max(highs[i + 1:i + 4]):
            lv.append((highs[i], "monthly", months[i]))
    # ATH = max of those months and of daily highs from the leg-low month start to the bar before the leg low
    k0 = int(np.searchsorted(dates, low_m.start_time))
    tail = Hs[k0:low_i]
    cand = [(h, "ath", p) for p, h in zip(months, highs)]
    if len(tail) and np.isfinite(tail).any():
        j = k0 + int(np.nanargmax(tail))
        cand.append((float(Hs[j]), "ath", dates[j]))
    if cand:
        lv.append(max(cand, key=lambda x: x[0]))
    # daily swing highs ±10, complete before the leg low, ≤ 504 sessions old at S
    for k in range(max(10, S - 504), low_i - 10):
        v = Hs[k]
        if np.isfinite(v) and v > np.nanmax(Hs[k - 10:k]) and v > np.nanmax(Hs[k + 1:k + 11]):
            lv.append((float(v), "daily", dates[k]))
    # untraded: no close after the level through the leg low above level × (1 + band)
    pre_c = {p: cl for p, _, cl in mon if p < first_daily_m}
    keep = []
    for L, src, when in lv:
        if isinstance(when, pd.Period):
            closes = [cl for p, cl in pre_c.items() if p > when]
            d0 = int(np.searchsorted(dates, (when + 1).start_time))
        else:
            closes = []
            d0 = int(np.searchsorted(dates, when)) + 1
        mx = max([x for x in closes if x is not None] + [np.nanmax(Cd[d0:low_i + 1]) if low_i + 1 > d0 else -np.inf])
        if not (mx > L * (1 + band)):
            keep.append((L, src, when))
    return keep


# -------------------------------------------------------------------------------------------------------------- build
def build(data):
    t0 = time.time()
    W, meta = load(data)
    o, h, l, c, v = W["o"], W["h"], W["l"], W["c"], W["v"]
    dates = c.index
    n = len(dates)
    print(f"{c.shape[1]} tickers × {n} sessions ({dates[0]:%Y-%m-%d} → {dates[-1]:%Y-%m-%d})", flush=True)
    hs, ls, n_bad = screen(o, h, l, c)
    V = {"bad_bars_screened": n_bad}
    # equity mask: universe tickers; others must be Yahoo EQUITY and not in our bars as non-universe (ETF / ADR)
    uni = set(store.load_universe())
    ours = set(store.load_bars()["ticker"].unique())
    eq = [t for t in c.columns if t in uni or (t not in ours and (meta.get(t, {}).get("type") == "EQUITY"))]
    eqm = pd.DataFrame(np.broadcast_to(c.columns.isin(eq), c.shape), index=dates, columns=c.columns)
    liquid_all = (c >= config.MIN_PRICE) & (v.rolling(20, min_periods=15).mean() >= config.MIN_AVG_VOLUME) & eqm
    nliq = liquid_all.sum(axis=1)
    keep_d = nliq >= 500
    V["liquid_median_by_year"] = {str(y): int(s.median()) for y, s in nliq.groupby(dates.year)}
    print("RS…", flush=True)
    rs, _, _ = strength.rs_ratings(c, liquid_all, range(n))
    rs = rs.reindex(index=dates, columns=c.columns)
    rs[~keep_d] = np.nan
    # breadth (metrics.compute rules on the equity set) + validation vs our stored breadth
    prev_c, prev_v = c.shift(1), v.shift(1)
    chg = c / prev_c - 1
    vol_ok = (v > prev_v) & (v >= config.MIN_VOLUME) & eqm
    pok = c >= config.MIN_PRICE
    up4 = ((chg >= config.PCT_MOVE) & vol_ok & pok).sum(axis=1)
    dn4 = ((chg <= -config.PCT_MOVE) & vol_ok & pok).sum(axis=1)
    r5 = up4.rolling(5).sum() / dn4.rolling(5).sum().clip(lower=1)
    r10 = up4.rolling(10).sum() / dn4.rolling(10).sum().clip(lower=1)
    strong = (r5 >= 1.5) & (r10 >= 1.5)
    br = store.load_breadth()
    ov = br.index.intersection(dates)
    ours_strong = (br.loc[ov, "ratio5"] >= 1.5) & (br.loc[ov, "ratio10"] >= 1.5)
    agree = float((ours_strong == strong.reindex(ov)).mean()) if len(ov) else np.nan
    share_ov = float(strong.reindex(ov).mean()) if len(ov) else np.nan
    era_share = {e: float(strong[(dates >= a) & (dates <= b)].mean()) for e, a, b in ERAS}
    era_liq = {e: float(nliq[(dates >= a) & (dates <= b)].median()) for e, a, b in ERAS}
    spy = c["SPY"]
    spy50 = spy > spy.rolling(50).mean()
    use_spy = (not np.isfinite(agree)) or agree < 0.9 or any(np.isfinite(s) and not (0.5 * share_ov <= s <= 2 * share_ov)
                                                              for s in era_share.values()) \
        or any(np.isfinite(x) and x < 1000 for x in era_liq.values())
    state = spy50 if use_spy else strong
    V.update(breadth_agree=agree, strong_share_overlap=share_ov, strong_share_era=era_share, liquid_median_era=era_liq,
             state="spy50" if use_spy else "breadth strong")
    # validation: Yahoo vs Massive closes on the overlap, RS rank correlation
    mb = strength.wide_all(store.apply_splits(store.load_bars(), store.load_splits()))
    mc = mb["c"]
    common = [t for t in mc.columns if t in c.columns]
    od = mc.index.intersection(dates)
    yc, mcc = c.loc[od, common], mc.loc[od, common]
    rel = (yc / mcc - 1).abs()
    good = (rel <= 0.005) | (yc.isna() & mcc.isna())
    frac = good.where(mcc.notna() & yc.notna()).mean()
    drop_massive = set(frac[frac < 0.99].index)
    V["yahoo_vs_massive"] = {"tickers": len(common), "dropped": len(drop_massive), "sample": sorted(drop_massive)[:40]}
    print("RS validation…", flush=True)
    uni_m = pd.DataFrame(np.broadcast_to(mc.columns.isin(list(uni)), mc.shape), index=mc.index, columns=mc.columns)
    liq_m = (mc >= config.MIN_PRICE) & (mb["v"].rolling(20, min_periods=15).mean() >= config.MIN_AVG_VOLUME) & uni_m
    rows = list(range(260, len(mc.index), 10))
    rsm, _, _ = strength.rs_ratings(mc, liq_m, rows)
    cors = []
    for d in rsm.index:
        if d in rs.index:
            a, b = rsm.loc[d, common], rs.loc[d, common]
            ok = a.notna() & b.notna()
            if ok.sum() > 200:
                cors.append(a[ok].rank().corr(b[ok].rank()))
    V["rs_rank_corr"] = {"median": float(np.median(cors)) if cors else None, "n_dates": len(cors)}
    # RS from monthly closes 2016–2019 (reported)
    try:
        mcl = {}
        for t in common:
            m = meta.get(t, {}).get("monthly") or []
            if m:
                mcl[t] = pd.Series({pd.Timestamp(x[0]): x[3] for x in m})
        MC = pd.DataFrame(mcl).sort_index()
        mr = 0.4 * MC.pct_change(3) + 0.2 * MC.pct_change(6) + 0.2 * MC.pct_change(9) + 0.2 * MC.pct_change(12)
        cc = []
        for d in MC.index[(MC.index >= "2016-01-01") & (MC.index <= "2019-12-31")]:
            k = int(np.searchsorted(dates, d)) - 1
            if 0 <= k < n:
                a, b = mr.loc[d].rank(), rs.iloc[k][MC.columns].rank()
                ok = a.notna() & b.notna()
                if ok.sum() > 200:
                    cc.append(a[ok].corr(b[ok]))
        V["rs_vs_monthly_2016_2019"] = float(np.median(cc)) if cc else None
    except Exception as e:  # reported only
        V["rs_vs_monthly_2016_2019"] = f"error {e}"
    OUT.mkdir(parents=True, exist_ok=True)
    rc = V["rs_rank_corr"]["median"]
    if rc is None or rc < 0.9:
        V["STOP"] = "RS rank correlation below 0.9 → no H2 run (v4)"
        json.dump(V, open(OUT / "validation.json", "w"), indent=1, default=str)
        print(json.dumps(V, indent=1, default=str))
        return
    groups = spy_groups(spy)
    try:
        thr_hist = metrics.compute(pd.concat([
            c[eq].stack().rename("c"), v[eq].stack().rename("v"), h[eq].stack().rename("h"), l[eq].stack().rename("l")],
            axis=1).reset_index().rename(columns={"t": "ticker"}), bench=None)
        thr = metrics.thrust_window(thr_hist, list(dates))
    except Exception as e:
        print("thrust windows unavailable:", e)
        thr = np.zeros(n, dtype=bool)
    # liquidity floor: 20-day avg $ volume in the top 30% of that day's liquid set
    dv20 = (c * v).rolling(20, min_periods=15).mean()
    dvcut = dv20.where(liquid_all).quantile(0.7, axis=1)
    V["usd20m_share_overlap"] = float((dv20.where(liquid_all) >= 20e6).sum(axis=1).reindex(ov).mean() / nliq.reindex(ov).mean())
    badyr = bad_years(c, meta)
    V["split_screen_ticker_years"] = sum(len(x) for x in badyr.values())
    subs = store.load_subthemes()
    sub_of = dict(zip(subs["ticker"], subs["subtheme"]))
    im = pd.read_csv(ROOT / "data" / "index_members.csv")
    sector = dict(zip(im["ticker"], im["sector"]))
    r2 = pd.read_csv(ROOT / "data" / "russell2000.csv")
    sector.update({k: s for k, s in zip(r2["ticker"], r2["sector"]) if k not in sector})
    in_index = set(im["ticker"])
    i15 = int(np.searchsorted(dates, C_START))
    top15 = set(dv20.iloc[i15].where(liquid_all.iloc[i15]).dropna().sort_values(ascending=False).index[:500])
    cE = int(np.searchsorted(dates, C_END))
    dS, dE = int(np.searchsorted(dates, D_START)), int(np.searchsorted(dates, D_END, side="right")) - 1
    era_of = lambda d: next((e for e, a, b in ERAS if pd.Timestamp(a) <= d <= pd.Timestamp(b)), "")
    mono = {"ok": 0, "no monthly": 0, "starts late": 0, "not monthly": 0, "recycled?": 0, "close mismatch": 0}
    fills = []
    epi = 0
    print(f"setup done {time.time() - t0:.0f}s; episodes…", flush=True)
    for ti, t in enumerate(eq):
        C, O, H, L = (x[t].to_numpy(dtype=float) for x in (c, o, h, l))
        Hs = hs[t].to_numpy(dtype=float)
        if np.isfinite(C).sum() < 300:
            continue
        first_bar = int(np.argmax(np.isfinite(C)))
        dfirst = dates[first_bar]
        ok_m, why = monthly_ok(t, meta, dfirst)
        m_raw = month_bars(meta, t)
        mon = [(pd.Period(x[0][:7], "M"), x[1], x[3]) for x in m_raw if x[1] is not None]
        if ok_m:
            # month-end closes within 2% on overlapping months (weak recycling screen)
            me = pd.Series(C, index=dates).groupby(dates.to_period("M")).last().dropna()
            mm = {p: cl for p, _, cl in mon}
            diffs = [abs(mm[p] / me[p] - 1) for p in me.index[:-1] if p in mm and mm[p] and me[p] > 0]
            if diffs and max(diffs) > 0.02:
                ok_m, why = False, "close mismatch"
        mono["ok" if ok_m else why] += 1
        first_daily_m = dfirst.to_period("M")
        mon_hi = max([x[1] for x in mon] + [np.nanmax(Hs)]) if mon else np.nanmax(Hs)
        adr = ((hs[t] / ls[t]) - 1).rolling(20, min_periods=15).mean().to_numpy()
        e9, e10, e21, e50 = (c[t].ewm(span=k, adjust=False, min_periods=k).mean().to_numpy() for k in (9, 10, 21, 50))
        w9 = emaprob.weekly_ema(c[t], 9)[0].to_numpy()
        w21 = emaprob.weekly_ema(c[t], 21)[0].to_numpy()
        watr = weekly_atr(h[t], l[t], c[t]).to_numpy()
        RS, DV, CUT, ST = rs[t].to_numpy(), dv20[t].to_numpy(), dvcut.to_numpy(), state.to_numpy()
        LQ = liquid_all[t].to_numpy()
        hi20 = c[t].rolling(20, min_periods=20).max().to_numpy()
        i = max(first_bar + 252, 60)
        while i <= n - 1:
            if not (np.isfinite(C[i]) and np.isfinite(hi20[i]) and C[i] >= hi20[i]):
                i += 1
                continue
            S, lh, first = i, C[i], None
            D = Wk = None
            j, end = i + 1, None
            while j <= n - 1:
                if not np.isfinite(C[j]):
                    j += 1
                    continue
                if first is None and C[j] > lh:
                    S, lh = j, C[j]
                    j += 1
                    continue
                a = adr[S]
                pulled = np.nanmin(C[S + 1:j + 1]) <= lh * (1 - a) if np.isfinite(a) else False
                rib_d, rib_w = max(e9[j], e21[j]), max(w9[j], w21[j])
                isD = pulled and L[j] <= rib_d + 0.25 * adr[j] * C[j] and C[j] >= e21[j] - 0.5 * adr[j] * C[j] and C[j] <= e9[j] + adr[j] * C[j]
                isW = pulled and L[j] <= rib_w + 0.25 * adr[j] * C[j] and C[j] >= w21[j] - 0.5 * adr[j] * C[j] and C[j] <= w9[j] + adr[j] * C[j]
                if first is None and (isD or isW):
                    first = j
                    D = j if isD else None
                    Wk = j if isW else None
                elif first is not None and Wk is None and isW:
                    Wk = j
                if first is not None and j > first and C[j] > lh:
                    end = j
                    break
                if np.isfinite(watr[j]) and C[j] < w21[j] - watr[j] * C[j]:
                    end = j
                    break
                if j - S >= EP_MAX:
                    end = j
                    break
                j += 1
            if end is None:
                end = min(j, n - 1)
            dS_ = dates[S]
            sset = "C" if dS_ >= C_START and S < cE else ("D" if dS <= S <= dE else None)
            ok = (sset is not None and S - first_bar >= 252 and LQ[S] and C[S] >= 10 and np.isfinite(DV[S]) and np.isfinite(CUT[S])
                  and DV[S] >= CUT[S] and np.isfinite(RS[S]) and RS[S] >= 80 and e21[S] > e50[S] and e50[S] > e50[S - 10]
                  and w9[S] > w21[S] and dS_.year not in badyr.get(t, set()) and t not in drop_massive)
            if not ok or first is None:
                i = end + 1
                continue
            epi += 1
            low_i = S - 60 + int(np.nanargmin(C[S - 60:S + 1]))
            band = max(0.02, adr[S] if np.isfinite(adr[S]) else 0.02)
            complete = ok_m
            if complete:
                lv = levels_at_S(S, low_i, dates, Hs, C, mon, first_daily_m, band)
            else:
                lv = None
                if lh * (1 + band) > mon_hi:     # above every high ever recorded → open sky is certain
                    lv = []
            ext = (C[S] - w21[S]) / (watr[S] * C[S]) if np.isfinite(watr[S]) and watr[S] > 0 else np.nan
            hitlv = [L_ for L_, _, _ in (lv or []) if -band <= C[S] / L_ - 1 <= 0.03]
            legmax = np.nanmax(H[low_i:S + 1])
            touched = any(legmax >= L_ * 0.995 for L_ in hitlv)
            ss_lv = min([L_ for L_ in hitlv if L_ > lh], default=np.nan)
            ath = max([L_ for L_, s_, _ in (lv or []) if s_ == "ath"], default=np.nan)
            seen = set()
            for kind, k in (("D", D), ("W", Wk)):
                if k is None or k in seen:
                    continue
                seen.add(k)
                tr = trade(k, end, O, H, L, C, e10, adr, n)
                if tr is None:
                    continue
                f = tr["fill_i"]
                if sset == "C" and f + HOLD >= cE:
                    continue
                if sset == "D" and f + HOLD > n - 1:
                    continue
                fill, a = tr["fill"], adr[f - 1]
                if not np.isfinite(a) or a <= 0:
                    continue
                if lv is None:
                    cls = "excluded"
                    lv_up = np.nan
                elif hitlv:
                    cls = "stalled"
                    lv_up = np.nan
                else:
                    above = [L_ for L_, _, _ in lv if L_ > max(fill, lh * (1 + band))]
                    lv_up = min(above) if above else np.inf
                    du = (lv_up - fill) / (fill * a)
                    cls = ("open" if not above else "too_close" if du < 1.5 else "approach" if du <= 6 else "far")
                d_up = (lv_up - fill) / (fill * a) if np.isfinite(lv_up) else (np.inf if lv_up == np.inf else np.nan)
                hh = H[f:f + 21]
                mfe = lambda kk: (np.nanmax(H[f:f + kk + 1]) / fill - 1) / a
                mfe20s = (np.nanmax(Hs[f:f + 21]) / fill - 1) / a
                tag_day = None
                if np.isfinite(lv_up) and cls not in ("stalled", "excluded"):
                    w = np.flatnonzero(hh >= lv_up)
                    tag_day = int(w[0]) if len(w) else None
                spy_ret = spy.iat[tr["exit_i"]] / spy.iat[f] - 1
                fd = dates[f]
                fills.append({
                    "set": sset, "ep": epi, "t": t, "S": dS_, "kind": kind, "fill_date": fd, "class": cls,
                    "stall": ("touched" if touched else "short") if cls == "stalled" else "",
                    "lv_up": lv_up, "d_up": d_up, "d_lh": (lh - fill) / (fill * a),
                    "d_ss": (ss_lv - fill) / (fill * a) if cls == "stalled" and not touched and np.isfinite(ss_lv) else np.nan,
                    "mfe5": mfe(5), "mfe10": mfe(10), "mfe20": mfe(20), "mfe20_scr": mfe20s,
                    "tag_day": tag_day, "exit_off": tr["exit_i"] - f,
                    "R": tr["R"], "R20": tr["R20"], "stopped": bool(tr.get("stopped")),
                    "xs": (C[tr["exit_i"]] / fill - 1) - spy_ret,
                    "adr": a, "state": bool(ST[f - 1]), "rs": RS[f - 1], "ext": ext, "dd_ath": lh / ath - 1 if np.isfinite(ath) else 0.0,
                    "age": (fd - (pd.Timestamp(m_raw[0][0]) if m_raw else dfirst)).days * 252 / 365.25,
                    "complete": complete, "thrust": bool(thr[f - 1]),
                    "month": str(fd.to_period("M")), "year": fd.year, "era": era_of(fd),
                    "mgroup": next((gi for gi, (gs, ge) in enumerate(groups) if gs <= f <= ge), -1),
                    "grp": sub_of.get(t) or ("sector:" + str(sector.get(t, "unknown"))),
                    "in_index": t in in_index, "top15": t in top15,
                    "n_levels": len(lv or []), "src": ",".join(sorted({s_ for L_, s_, _ in (lv or []) if np.isfinite(lv_up) and L_ == lv_up})),
                })
            i = end + 1
        if ti % 300 == 0:
            print(f"  {ti}/{len(eq)} tickers · {len(fills)} fills · {time.time() - t0:.0f}s", flush=True)
    F = pd.DataFrame(fills)
    V["monthly_completeness"] = mono
    V["fills"] = int(len(F))
    V["episodes"] = int(epi)
    F.to_parquet(OUT / "fills.parquet", index=False)
    json.dump(V, open(OUT / "validation.json", "w"), indent=1, default=str)
    print(json.dumps(V, indent=1, default=str))
    print(f"done {time.time() - t0:.0f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["build", "power", "test"])
    ap.add_argument("--data")
    a = ap.parse_args()
    if a.stage == "build":
        build(a.data)
    else:
        from tools.warehouse import magnets_stats as MS
        getattr(MS, a.stage)()
