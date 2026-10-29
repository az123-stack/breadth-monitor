"""Every sub-theme x day over ~2 years: the runner checks at the close + forward returns. Saves gd.parquet."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, ".")
from breadth import store
b = store.apply_splits(store.load_bars(), store.load_splits()); b["date"] = pd.to_datetime(b["date"])
W = {k: b.pivot(index="date", columns="ticker", values=k).sort_index() for k in "ohlcv"}
O, H, L, C, V = (W[k] for k in "ohlcv")
D = json.load(open("docs/data.json")); T = D["themes"]
isstock = {s["t"] for s in T["stocks"] if s.get("is_stock")}
subs = {g["theme"]: [t for t in g["members"] if t in isstock and t in C.columns] for g in T["subthemes"]}
prev = C.shift(1); chg = C / prev - 1
adr = (H / L - 1).rolling(20, min_periods=15).mean().shift(1)
dv = C * V; dv50 = dv.rolling(50, min_periods=40).mean().shift(1)
ok = (prev >= 3) & (dv50 >= 10e6) & chg.abs().le(0.6)
spy = C["SPY"] / C["SPY"].shift(1) - 1
n = len(C); dates = C.index
rows = []
for g, mem in subs.items():
    if len(mem) < 4: continue
    c = chg[mem]; a = adr[mem]; m = ok[mem]
    cnt = m.sum(1); up = ((c > 0) & m).sum(1)
    avg = c.where(m).mean(1); adrs = (c / a).where(m).mean(1)
    pace = dv[mem].where(m).sum(1) / dv50[mem].where(m).sum(1)
    # forward: equal-weight group, buy next open, hold k sessions (close), vs SPY same
    eo = O[mem].shift(-1)
    for k in (1, 5, 10):
        rows_k = (C[mem].shift(-k) / eo - 1).where(m).mean(1)
        if k == 1: f1 = rows_k
        elif k == 5: f5 = rows_k
        else: f10 = rows_k
    # same-day after the signal: close-to-close next day (no entry at open) for continuation
    nxt = (C[mem].shift(-1) / C[mem] - 1).where(m).mean(1)
    df = pd.DataFrame({"date": dates, "g": g, "n": cnt.values, "up": up.values, "avg": avg.values, "adrs": adrs.values,
                       "pace": pace.values, "rel": (avg - spy).values, "f1": f1.values, "f5": f5.values, "f10": f10.values, "nxt": nxt.values})
    rows.append(df)
gd = pd.concat(rows); gd = gd[gd.n >= 4].dropna(subset=["adrs", "pace"])
gd = gd[gd.date >= dates[60]]
spyf = pd.DataFrame({"date": dates, "s1": (C["SPY"].shift(-1) / O["SPY"].shift(-1) - 1).values,
                     "s5": (C["SPY"].shift(-5) / O["SPY"].shift(-1) - 1).values, "s10": (C["SPY"].shift(-10) / O["SPY"].shift(-1) - 1).values})
gd = gd.merge(spyf, on="date")
gd["upsh"] = gd.up / gd.n
gd.to_parquet("/tmp/gd.parquet")
print(len(gd), "group-days", gd.g.nunique(), "groups", gd.date.nunique(), "days")
q = gd[["adrs", "pace", "avg", "upsh"]].quantile([.5, .9, .95, .98, .99]).round(2); print(q)
x = gd[(gd.date == "2026-10-28")].sort_values("adrs", ascending=False).head(8)
print(x[["g", "n", "up", "avg", "adrs", "pace"]].round(2).to_string())
