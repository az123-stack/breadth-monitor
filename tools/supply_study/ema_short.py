"""Short the rally into falling EMAs (Adam Nov 8, 2026, about a trader's 'mean reversion back into supply' plan: "we're in a falling
market, so like momentum bursts up from on top of EMAs, this would be down from below EMAs").

Setup (stock, $5+, $20M+/day): downtrend = close < EMA21 < EMA50, both EMAs lower than 5 sessions ago, stock 10%+ under its 60-day high.
Signal day: the high reaches the 21 EMA (or 50 EMA variant) from below (within 0.25 ADR) and the close is back under it, red on the day
(close < open). Entry next open; stop 0.1 ADR above the signal-day high (risk floor 0.3 ADR); exits: 5 / 10 / 20 sessions, a 2R target,
or a trail (cover on a close above the 9 EMA, Kristjan's long rule flipped). One signal per stock per 10 sessions.
Cuts: market (SPY under its falling 50-day = "falling market"), group (sub-theme 60-day percentile), RS (6-month percentile), thrust window.
Run from the repo root: python tools/supply_study/ema_short.py
"""
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from breadth import store, metrics

b = store.apply_splits(store.load_bars(), store.load_splits()); b["date"] = pd.to_datetime(b["date"])
uni = pd.read_csv("data/universe.csv")
bad = uni["name"].fillna("").str.contains(r"\bETF\b|\bFund\b|\bTrust\b|ProShares|Direxion|iShares|SPDR|2X|3X|Leveraged|Bull|Bear", case=False, regex=True)
stocks = set(uni.loc[~bad, "ticker"])
W = {k: b.pivot(index="date", columns="ticker", values=k).sort_index() for k in "ohlcv"}
cols = [t for t in W["c"].columns if t in stocks]
O, H, L, C, V = (W[k][cols] for k in "ohlcv")
dates = C.index; n = len(dates)
e9, e21, e50 = (C.ewm(span=k, adjust=False, min_periods=k).mean() for k in (9, 21, 50))
adr = (H / L - 1).rolling(20, min_periods=15).mean()
dv50 = (C * V).rolling(50, min_periods=40).mean()
liq = (C >= 5) & (dv50 >= 20e6)
rs = (C / C.shift(126) - 1).where(liq).rank(axis=1, pct=True)
hi60 = H.rolling(60, min_periods=40).max()
spy = W["c"]["SPY"]; s50 = spy.rolling(50).mean()
falling_mkt = (spy < s50) & (s50 < s50.shift(5))
sub = pd.read_csv("data/subthemes.csv"); ret60 = C / C.shift(60) - 1
g60 = pd.DataFrame({g: ret60[[t for t in m if t in ret60.columns]].mean(axis=1) for g, m in sub.groupby("subtheme")["ticker"]
                    if len([t for t in m if t in ret60.columns]) >= 3}).rank(axis=1, pct=True)
tsub = sub.drop_duplicates("ticker").set_index("ticker")["subtheme"].to_dict()
hist = pd.read_csv("docs/breadth.csv", parse_dates=["date"]).set_index("date")
tw = pd.Series(metrics.thrust_window(hist, list(dates)), index=dates)

down = (C < e21) & (e21 < e50) & (e21 < e21.shift(5)) & (e50 < e50.shift(5)) & (C <= hi60 * 0.9) & liq
rows = []
Ov, Hv, Lv, Cv, E9 = O.to_numpy(), H.to_numpy(), L.to_numpy(), C.to_numpy(), e9.to_numpy()
for lvl_name, EM in (("21 EMA", e21), ("50 EMA", e50)):
    sig = down & (H >= EM - 0.25 * adr * C) & (C < EM) & (C < O)
    if lvl_name == "50 EMA":
        sig = down & (H >= EM - 0.25 * adr * C) & (C < EM) & (C < O) & (H > e21)
    S = sig.to_numpy(); A = adr.to_numpy()
    for j in range(len(cols)):
        last = -99
        for d in np.flatnonzero(S[:, j]):
            if d - last < 10 or d + 1 >= n:
                continue
            last = d
            a = A[d, j]; e = Ov[d + 1, j]
            if np.isnan(e) or np.isnan(a):
                continue
            stop = Hv[d, j] * (1 + 0.1 * a); risk = max(stop - e, 0.3 * a * e); st = e + risk
            res = {}; hit2 = False; trail = None; stopped = None
            for i in range(d + 1, min(n, d + 21)):
                if (i == d + 1 and Ov[i, j] >= st) or Hv[i, j] >= st:
                    stopped = i; break
                if (e - Lv[i, j]) / risk >= 2:
                    hit2 = True
                if trail is None and i > d + 1 and Cv[i, j] > E9[i, j]:
                    trail = (e - Cv[i, j]) / risk
                for m in (5, 10, 20):
                    if i - d == m:
                        res[m] = (e - Cv[i, j]) / risk
            for m in (5, 10, 20):
                if m not in res:
                    res[m] = -1.0 if stopped is not None and stopped - d <= m else np.nan
            if trail is None:
                trail = -1.0 if stopped is not None else res[20]
            tgt = 2.0 if hit2 and (stopped is None or True) else res[20]
            # 2R target: if 2R touched before the stop -> +2, else stop -1 / 20-day close
            rows.append(dict(level=lvl_name, t=cols[j], date=dates[d], R5=res[5], R10=res[10], R20=res[20], trail=trail,
                             tgt2=2.0 if hit2 else (-1.0 if stopped is not None else res[20]), stopped=stopped is not None,
                             mkt=bool(falling_mkt.iat[d]), thrust=bool(tw.iat[d]), rs=rs.iat[d, j],
                             g60=g60[tsub[cols[j]]].iat[d] if tsub.get(cols[j]) in g60.columns else np.nan))
R = pd.DataFrame(rows); R.to_parquet("/tmp/supply_study/ema_short.parquet")
mid = R.date.sort_values().iloc[len(R) // 2]
tt = lambda x: round(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))), 1) if len(x.dropna()) > 2 else np.nan
for lv in R.level.unique():
    f = R[R.level == lv]
    print(f"\n== short the rally into a falling {lv}: {len(f)} trades, {f.date.nunique()} dates")
    cuts = {"ALL": f.index == f.index, "falling market (SPY < falling 50d)": f.mkt, "market not falling": ~f.mkt,
            "thrust window": f.thrust, "falling mkt & no thrust": f.mkt & ~f.thrust,
            "RS bottom 30%": f.rs <= 0.3, "RS top 30% (fallen leader)": f.rs >= 0.7,
            "group bottom 30%": f.g60 <= 0.3, "group top 50%": f.g60 >= 0.5, "not in themes": f.g60.isna(),
            "falling mkt & RS bottom 30%": f.mkt & (f.rs <= 0.3), "falling mkt & group bottom 30%": f.mkt & (f.g60 <= 0.3),
            "falling mkt & not in themes": f.mkt & f.g60.isna()}
    for k, m in cuts.items():
        x = f[m]; h1, h2 = x[x.date < mid], x[x.date >= mid]
        if len(x) < 30:
            continue
        print(f"  {k:36} n {len(x):5} d {x.date.nunique():3}  win20 {(x.R20 > 0).mean():.0%}  R5 {x.R5.mean():+.2f}  R20 {x.R20.mean():+.2f} (t {tt(x.R20.dropna())})"
              f"  trail9 {x.trail.mean():+.2f} (t {tt(x.trail.dropna())})  2R-tgt {x.tgt2.mean():+.2f}  halves R20 {h1.R20.mean():+.2f}/{h2.R20.mean():+.2f} trail {h1.trail.mean():+.2f}/{h2.trail.mean():+.2f}")
print("\nfalling-market days in sample:", int(falling_mkt.sum()), "of", n)
