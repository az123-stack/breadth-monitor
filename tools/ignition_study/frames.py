"""Build daily per-sub-theme indicator frames from stored bars (cached to frames.pkl)."""
import sys, os, json, pickle
sys.path.insert(0, "/home/claude/breadth-monitor")
import numpy as np, pandas as pd
from breadth import store, rotation as RO
OUT = os.path.join(os.path.dirname(__file__), "frames.pkl")
bars = store.load_bars(); adj = store.apply_splits(bars, store.load_splits())
subs = pd.read_csv("/home/claude/breadth-monitor/data/subthemes.csv")
members = subs.groupby("subtheme")["ticker"].apply(list).to_dict()
universe = set(store.load_universe())
ticks = set(subs.ticker) | {"SPY"}
c, h, v = RO._wide(adj, ticks)
l = adj[adj.ticker.isin(ticks)].pivot_table(index="date", columns="ticker", values="l").reindex_like(c)
c.index = pd.to_datetime(c.index); h.index = c.index; v.index = c.index; l.index = c.index
F = RO.group_frames(c, members); FL = RO.flow_frames(c, v, members, F)
I, rel = F["idx"], F["rel"]
G = list(I.columns)
ema21 = c.ewm(span=21, adjust=False, min_periods=21).mean(); sma50 = c.rolling(50).mean()
hi20 = h.rolling(20).max(); hi252 = h.rolling(252, min_periods=200).max()
r63 = c / c.shift(63) - 1
# RS proxy: each stock's 63-day return percentile among liquid universe stocks we have (theme stocks here)
rs63 = r63.rank(axis=1, pct=True) * 99
br21, br50, nh20, near, rsmed, up4 = {}, {}, {}, {}, {}, {}
ret = c / c.shift(1) - 1
for g in G:
    t = [x for x in members[g] if x in c.columns]
    n = c[t].notna().sum(axis=1).replace(0, np.nan)
    br21[g] = (c[t] > ema21[t]).sum(axis=1) / n
    br50[g] = (c[t] > sma50[t]).sum(axis=1) / n
    nh20[g] = (h[t] >= hi20[t]).sum(axis=1) / n
    near[g] = (c[t] >= 0.97 * hi252[t]).sum(axis=1) / n
    rsmed[g] = rs63[t].median(axis=1)
    up4[g] = (ret[t] >= 0.04).sum(axis=1) / n
D = {k: pd.DataFrame(x) for k, x in dict(br21=br21, br50=br50, nh20=nh20, near=near, rsmed=rsmed, up4=up4).items()}
r20 = rel / rel.shift(20) - 1; rk20 = r20.rank(axis=1, pct=True)
r5 = rel / rel.shift(5) - 1; rk5 = r5.rank(axis=1, pct=True)
D.update(I=I, rel=rel, r20=r20, rk20=rk20, rk5=rk5, drk=rk20 - rk20.shift(10),
         relhi60=rel >= rel.rolling(60).max(), relma50=rel > rel.rolling(50).mean(),
         idxhi40=I >= I.rolling(40).max(), rng40=I.rolling(40).max() / I.rolling(40).min() - 1,
         acc=FL["acc"], part=FL["part"], rrgx=FL["x"], rrgy=FL["y"], lead=F["lead"].astype(float),
         conf=FL["tiers"]["confirmed"].astype(float))
D["spy"] = c["SPY"]; D["members"] = members
# macro: crack spread
m = json.load(open("/home/claude/breadth-monitor/data/macro.json"))
s = {k: pd.Series({pd.Timestamp(d): x for d, x in m[k]["rows"]}) for k in ("gasoline", "diesel", "crude")}
cr = ((2 * s["gasoline"] * 42 + s["diesel"] * 42 - 3 * s["crude"]) / 3).dropna()
D["crack"] = cr
pickle.dump(D, open(OUT, "wb"))
print("groups", len(G), "days", len(I), I.index[0].date(), I.index[-1].date())
