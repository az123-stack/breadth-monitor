"""Build wide price frames + find every rally into / break through a major old pivot. Saves events.parquet."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, ".")
from breadth import store
b = store.apply_splits(store.load_bars(), store.load_splits())
b["date"] = pd.to_datetime(b["date"])
uni = pd.read_csv("data/universe.csv")
th = pd.read_csv("data/themes.csv")
etf = set(th.loc[th.get("role", "") == "etf", "ticker"]) if "role" in th.columns else set()
bad = uni["name"].fillna("").str.contains(r"\bETF\b|\bFund\b|\bTrust\b|ProShares|Direxion|iShares|SPDR|2X|3X|Leveraged|Bull|Bear", case=False, regex=True)
stocks = set(uni.loc[~bad, "ticker"]) - etf
W = {k: b.pivot(index="date", columns="ticker", values=k).sort_index() for k in "ohlcv"}
O, H, L, C, V = (W[k] for k in "ohlcv")
spy = C["SPY"]
cols = [t for t in C.columns if t in stocks]
O, H, L, C, V = (x[cols] for x in (O, H, L, C, V))
dv50 = (C * V).rolling(50, min_periods=40).mean()
v50 = V.rolling(50, min_periods=40).mean().shift(1)
adr = (H / L - 1).rolling(20, min_periods=15).mean()
dates = C.index; n = len(dates)
PROM = 30        # swing point = highest high (lowest low) within +-30 sessions
MIN_AGE = 60     # pivot at least 60 sessions old at the touch
DROP = 0.25      # after the pivot, price traded 25%+ below it (it's a big, old level with trapped holders)
rows = []
Hv, Lv, Cv, Ov, Vv = H.to_numpy(), L.to_numpy(), C.to_numpy(), O.to_numpy(), V.to_numpy()
for j, t in enumerate(cols):
    h, l, c = Hv[:, j], Lv[:, j], Cv[:, j]
    if np.isnan(c).sum() > n * 0.3:
        continue
    hs = pd.Series(h); ls = pd.Series(l)
    rmax = hs.rolling(2 * PROM + 1, center=True, min_periods=PROM + 1).max().to_numpy()
    rmin = ls.rolling(2 * PROM + 1, center=True, min_periods=PROM + 1).min().to_numpy()
    piv = [(i, h[i], "peak") for i in range(PROM, n - PROM) if h[i] == rmax[i] and not np.isnan(h[i])]
    piv += [(i, l[i], "floor") for i in range(PROM, n - PROM) if l[i] == rmin[i] and not np.isnan(l[i])]
    for (pi, lvl, kind) in piv:
        # for a floor, it only becomes overhead resistance once price breaks well below it
        after = l[pi + 1:]
        if np.all(np.isnan(after)):
            continue
        # find the low point after the pivot that is DROP below the level
        below = np.flatnonzero(after <= lvl * (1 - DROP))
        if not len(below):
            continue
        k0 = pi + 1 + below[0]
        # track the trough from k0, then first day the high comes back within 1% of the level, with 10 prior closes under 97%
        for d in range(k0 + 1, n - 1):
            if np.isnan(h[d]) or d - pi < MIN_AGE:
                continue
            if h[d] >= lvl * 0.99:
                prior = c[max(0, d - 10):d]
                if len(prior) == 10 and np.all(prior < lvl * 0.97):
                    trough = np.nanmin(l[pi + 1:d])
                    rows.append(dict(t=t, d=d, date=dates[d], lvl=lvl, kind=kind, age=d - pi, depth=1 - trough / lvl,
                                     run21=c[d] / c[d - 21] - 1 if d >= 21 else np.nan))
                break   # first return only
ev = pd.DataFrame(rows)
print("raw events", len(ev))
# keep the most important level when a stock touches several on one day (the highest / oldest)
ev = ev.sort_values(["t", "d", "age"], ascending=[True, True, False]).drop_duplicates(["t", "d"])
# one event per stock per 20 sessions (overlapping windows = one event)
keep, last = [], {}
for r in ev.sort_values(["t", "d"]).itertuples():
    if r.t in last and r.d - last[r.t] < 20:
        continue
    keep.append(r.Index); last[r.t] = r.d
ev = ev.loc[keep]
i = ev["d"].to_numpy(); jx = [cols.index(t) for t in ev["t"]]
ev["c"] = Cv[i, jx]; ev["dv50"] = dv50.to_numpy()[i, jx]; ev["rvol"] = Vv[i, jx] / v50.to_numpy()[i, jx]
ev["adr"] = adr.to_numpy()[i, jx]; ev["closed_above"] = Cv[i, jx] > ev["lvl"].to_numpy()
ev = ev[(ev["c"] >= 5) & (ev["dv50"] >= 20e6)]
print("tradeable events", len(ev), "stocks", ev.t.nunique(), "dates", ev.date.nunique())
ev.to_parquet("/tmp/pivot_study/events.parquet")
pd.to_pickle(dict(O=O, H=H, L=L, C=C, V=V, spy=spy, dv50=dv50, v50=v50, adr=adr), "/tmp/pivot_study/frames.pkl")
