"""Supply breaks study (R-2026-11-07-supply-breaks; Adam Nov 7, 2026: "we need a system for figuring out what happens when a stock
takes out significant overhead supply and how quickly it works that off").

Event = first CLOSE above a significant old level after 20+ closes under it:
  swing  = a +-30-session swing high in our bars, 60+ sessions old, that price later traded 25%+ under (trapped holders)
  floor  = a +-30-session swing low that later broke 25%+ (old support turned supply)
  multi  = a monthly peak / ATH from data/levels.json (Yahoo, back to the 2000s) that the stock traded 25%+ under in our bars
$5+, $20M+/day 50-day $ volume, stocks only. Highest level per stock per day; one event per stock per 20 sessions.
Phases after the break (L = level, a = ADR as a fraction):
  retest  = first low within 0.25 ADR above L (or below it)        fail = first close under L x (1 - 0.5a)
  clear   = first close >= L x (1 + 2a) with no fail before it ("worked off": left the level behind)
Trades (no look-ahead: entries at the next open): breakout buy next open after the break; retest buy next open after the first retest
that closed above the fail line. Stop L x (1 - 0.5a) (risk floored at 0.3 ADR), exit after 20 sessions. Excess returns vs same-date stocks
making an ordinary 60-day closing high in the same $ volume bucket. Writes /tmp/supply_study/events.parquet and prints the tables.
Run from the repo root: python tools/supply_study/study.py
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from breadth import store, metrics

OUT = "/tmp/supply_study"; os.makedirs(OUT, exist_ok=True)
PROM, MIN_AGE, DROP, UNDER = 30, 60, 0.25, 20
b = store.apply_splits(store.load_bars(), store.load_splits()); b["date"] = pd.to_datetime(b["date"])
uni = pd.read_csv("data/universe.csv")
bad = uni["name"].fillna("").str.contains(r"\bETF\b|\bFund\b|\bTrust\b|ProShares|Direxion|iShares|SPDR|2X|3X|Leveraged|Bull|Bear", case=False, regex=True)
stocks = set(uni.loc[~bad, "ticker"])
W = {k: b.pivot(index="date", columns="ticker", values=k).sort_index() for k in "ohlcv"}
cols = [t for t in W["c"].columns if t in stocks]
O, H, L, C, V = (W[k][cols] for k in "ohlcv")
spy = W["c"]["SPY"]
dates = C.index; n = len(dates)
dv50 = (C * V).rolling(50, min_periods=40).mean()
rv = V / V.rolling(50, min_periods=40).mean().shift(1)
adr = (H / L - 1).rolling(20, min_periods=15).mean()
r126 = C / C.shift(126) - 1
liq = (C >= 5) & (dv50 >= 20e6)
rs = r126.where(liq).rank(axis=1, pct=True)           # RS proxy: 6-month return percentile among liquid stocks
# sub-theme 60-day return percentile (today's lists = mild hindsight)
sub = pd.read_csv("data/subthemes.csv")
ret60 = C / C.shift(60) - 1
g60 = pd.DataFrame({g: ret60[[t for t in m if t in ret60.columns]].mean(axis=1) for g, m in sub.groupby("subtheme")["ticker"]
                    if len([t for t in m if t in ret60.columns]) >= 3})
g60p = g60.rank(axis=1, pct=True)
tsub = sub.drop_duplicates("ticker").set_index("ticker")["subtheme"].to_dict()
hist = pd.read_csv("docs/breadth.csv", parse_dates=["date"]).set_index("date") if "date" in pd.read_csv("docs/breadth.csv", nrows=1).columns else pd.read_csv("docs/breadth.csv", index_col=0, parse_dates=True)
tw = pd.Series(metrics.thrust_window(hist, list(dates)), index=dates)
levels = json.load(open("data/levels.json"))
first = dates[0]

rows = []
Hv, Lv, Cv, Ov = H.to_numpy(), L.to_numpy(), C.to_numpy(), O.to_numpy()
for j, t in enumerate(cols):
    h, l, c = Hv[:, j], Lv[:, j], Cv[:, j]
    if np.isnan(c).sum() > n * 0.3:
        continue
    cand = []    # (level, kind, start index from which the level counts as supply, pivot date)
    hs, ls = pd.Series(h), pd.Series(l)
    rmax = hs.rolling(2 * PROM + 1, center=True, min_periods=PROM + 1).max().to_numpy()
    rmin = ls.rolling(2 * PROM + 1, center=True, min_periods=PROM + 1).min().to_numpy()
    for i in range(PROM, n - PROM):
        for lvl, kind in ((h[i], "swing"), (l[i], "floor")):
            if np.isnan(lvl) or (kind == "swing" and lvl != rmax[i]) or (kind == "floor" and lvl != rmin[i]):
                continue
            below = np.flatnonzero(l[i + 1:] <= lvl * (1 - DROP))
            if len(below):
                cand.append((lvl, kind, i + 1 + below[0], i))
    lv = levels.get(t) or {}
    for d, p in (lv.get("peaks") or []) + ([[lv.get("ath_d"), lv.get("ath")]] if lv.get("ath") else []):
        if p and d and pd.Timestamp(d + "-01") < first:
            below = np.flatnonzero(l <= p * (1 - DROP))
            if len(below):
                cand.append((float(p), "multi", below[0], -1))
    for lvl, kind, k0, pi in cand:
        for d in range(max(k0 + 1, UNDER), n):
            if np.isnan(c[d]) or (pi >= 0 and d - pi < MIN_AGE):
                continue
            if c[d] > lvl:
                prior = c[d - UNDER:d]
                if np.all(prior[~np.isnan(prior)] <= lvl) and (~np.isnan(prior)).sum() >= UNDER - 2:
                    rows.append(dict(t=t, j=j, d=d, lvl=lvl, kind=kind, age=(d - pi) if pi >= 0 else 999,
                                     depth=1 - np.nanmin(l[(pi + 1 if pi >= 0 else 0):d]) / lvl))
                break   # first break only
ev = pd.DataFrame(rows)
ev = ev.sort_values(["t", "d", "lvl"], ascending=[True, True, False]).drop_duplicates(["t", "d"])
keep, last = [], {}
for r in ev.sort_values(["t", "d"]).itertuples():
    if r.d - last.get(r.t, -99) >= 20:
        keep.append(r.Index); last[r.t] = r.d
ev = ev.loc[keep].reset_index(drop=True)
print("breaks before liquidity filter", len(ev))

out = []
for r in ev.itertuples():
    d, j, Lv0 = r.d, r.j, r.lvl
    if not liq.iat[d, j] or np.isnan(adr.iat[d, j]):
        continue
    a = adr.iat[d, j]; fail_ln = Lv0 * (1 - 0.5 * a); clear_ln = Lv0 * (1 + 2 * a)
    c, h, l, o = Cv[:, j], Hv[:, j], Lv[:, j], Ov[:, j]
    end = min(n - 1, d + 63)
    retest = fail = clear = None
    for k in range(d + 1, end + 1):
        if np.isnan(c[k]):
            continue
        if retest is None and l[k] <= Lv0 * (1 + 0.25 * a):
            retest = k
        if fail is None and c[k] < fail_ln:
            fail = k
        if clear is None and fail is None and c[k] >= clear_ln:
            clear = k
    obs = end - d
    def trade(e):   # buy open of e, stop fail line (risk floor 0.3 ADR), exit close e+19
        if e is None or e >= n or np.isnan(o[e]):
            return np.nan
        risk = max(o[e] - fail_ln, 0.3 * a * o[e])
        stop = o[e] - risk
        for k in range(e, min(n - 1, e + 19) + 1):
            if l[k] <= stop:
                return (min(o[k], stop) - o[e]) / risk
        k = min(n - 1, e + 19)
        return (c[k] - o[e]) / risk if k - e >= 19 else np.nan
    ret_e = None
    if retest is not None and (fail is None or fail > retest) and c[retest] >= fail_ln:
        ret_e = retest + 1
    fw = lambda m: (c[d + m] / o[d + 1] - 1) if d + m < n and d + 1 < n else np.nan
    g = tsub.get(r.t)
    out.append(dict(t=r.t, date=dates[d], d=d, lvl=Lv0, kind=r.kind, age=r.age, depth=r.depth, adr=a, rv=rv.iat[d, j],
                    gap=o[d] > Lv0, ext=(c[d] / Lv0 - 1) / a, rs=rs.iat[d, j], thrust=bool(tw.iat[d]),
                    g60=(g60p[g].iat[d] if g in g60p.columns else np.nan), sub=g, obs=obs,
                    retest=None if retest is None else retest - d, fail=None if fail is None else fail - d,
                    clear=None if clear is None else clear - d, R_bo=trade(d + 1), R_rt=trade(ret_e),
                    r5=fw(5), r21=fw(21), r63=fw(63)))
E = pd.DataFrame(out)
# matched control: same date, ordinary 60-day closing high (no supply break), same $ volume bucket
hi60 = C >= C.rolling(60, min_periods=50).max()
bk = pd.DataFrame(np.digitize(np.log10(dv50.fillna(1).to_numpy()), [7.5, 8, 8.5, 9]), index=dates, columns=cols)
fwd = {m: (C.shift(-m) / O.shift(-1) - 1) for m in (5, 21, 63)}
ctl = {}
for d in E["d"].unique():
    m = (hi60.iloc[d] & liq.iloc[d]).to_numpy()
    for bb in range(5):
        sel = m & (bk.iloc[d].to_numpy() == bb)
        ctl[(d, bb)] = {k: np.nanmean(fwd[k].iloc[d].to_numpy()[sel]) if sel.sum() >= 5 else np.nan for k in fwd}
E["bk"] = [bk.iat[d, cols.index(t)] for d, t in zip(E["d"], E["t"])]
for m in (5, 21, 63):
    E[f"x{m}"] = E[f"r{m}"] - [ctl[(d, bb)][m] for d, bb in zip(E["d"], E["bk"])]
E.to_parquet(f"{OUT}/events.parquet")
print("events", len(E), "dates", E["date"].min().date(), "->", E["date"].max().date(), "|", E["kind"].value_counts().to_dict())
