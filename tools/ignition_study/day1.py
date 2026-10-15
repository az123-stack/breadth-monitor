import sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/home/claude/breadth-monitor")
from breadth import store, rotation as RO
D = pickle.load(open("frames.pkl", "rb")); members = D["members"]
bars = store.load_bars(); adj = store.apply_splits(bars, store.load_splits())
ticks = {t for v in members.values() for t in v} | {"SPY"}
c, h, v = RO._wide(adj, ticks); c.index = pd.to_datetime(c.index); h.index = c.index; v.index = c.index
I, rel = D["I"], D["rel"]; G = list(I.columns); dates = I.index
ret = c / c.shift(1) - 1; dv = c * v
hi10 = c.shift(1).rolling(10).max()           # close above the prior 10-day closing high = short-term breakout
hi52 = c.rolling(252, min_periods=120).max()
brk, pull, rv = {}, {}, {}
for g in G:
    t = [x for x in members[g] if x in c.columns]; n = c[t].notna().sum(axis=1).replace(0, np.nan)
    brk[g] = (c[t] > hi10[t]).sum(axis=1) / n
    off = c[t] / hi52[t] - 1
    pull[g] = ((off.shift(1) <= -0.05) & (off.shift(1) >= -0.25)).sum(axis=1) / n   # members in a 5–25% pullback the day before
    d = dv[t].sum(axis=1); rv[g] = d / d.rolling(50).mean().shift(1)
brk, pull, rv = pd.DataFrame(brk), pd.DataFrame(pull), pd.DataFrame(rv)
r1 = rel / rel.shift(1) - 1
grp_off = I / I.rolling(60).max() - 1
fwd = {n: rel.shift(-n) / rel - 1 for n in (5, 10, 20, 40)}
br = pd.read_csv("/home/claude/breadth-monitor/data/breadth.csv", parse_dates=["date"]).set_index("date").reindex(dates)
strong = (br["ratio10"] >= 1.5).to_numpy()[:, None]
warm = dates[60]
def events(m, gap=20):
    m = m.fillna(False).astype(bool); return m & ~(m.shift(1).astype(float).rolling(gap, min_periods=1).max().fillna(0) > 0)
def st(ev, n=20):
    x = fwd[n].where(ev).loc[warm:].stack().dropna(); b = fwd[n].loc[warm:].stack().dropna()
    if x.size < 5: return f"n {x.size}"
    t = (x.mean() - b.mean()) / (x.std() / np.sqrt(x.size))
    return f"n {x.size:4d} avg {x.mean()*100:+5.2f}% med {x.median()*100:+5.2f}% win {(x>0).mean()*100:3.0f}% edge {(x.mean()-b.mean())*100:+5.2f} t {t:+.1f}"
b = fwd[20].loc[warm:].stack().dropna(); print(f"BASE 20d avg {b.mean()*100:+.2f}% med {b.median()*100:+.2f}%")
# DAY 1: group beats SPY by 2%+ today, on 1.3x+ normal dollar volume, half the members break a 10-day closing high,
# group index was in a pullback (3-15% below its 60-day high yesterday) - i.e. breaking out of a flag/pullback
base = (r1 >= 0.02) & (rv >= 1.3) & (brk >= 0.5) & (grp_off.shift(1) <= -0.03) & (grp_off.shift(1) >= -0.15)
E1 = events(base.loc[warm:]).reindex(dates).fillna(False)
for n in (5, 10, 20, 40): print(f"DAY 1 {n:2d}d:", st(E1, n))
print("DAY 1 strong breadth 20d:", st(E1 & strong)); print("DAY 1 not strong 20d:   ", st(E1 & ~strong))
# variants
v2 = (r1 >= 0.02) & (rv >= 1.3) & (brk >= 0.5)
print("no pullback condition 20d:", st(events(v2.loc[warm:]).reindex(dates).fillna(False)))
v3 = base & (pull >= 0.4)
print("+40% of members in 5-25% pullbacks 20d:", st(events(v3.loc[warm:]).reindex(dates).fillna(False)))
# follow-through: Day 1 then group holds above Day-1 close over the next 3 sessions -> enter day 4
held = pd.DataFrame(False, index=dates, columns=G)
f3 = rel.shift(-3) / rel - 1
E1b = E1 & (f3 > 0)   # outcome measured from day 1 (look-ahead) just to see if follow-through matters
fwd_from3 = rel.shift(-23) / rel.shift(-3) - 1
x = fwd_from3.where(E1b).loc[warm:].stack().dropna(); y = fwd_from3.where(E1 & (f3 <= 0)).loc[warm:].stack().dropna()
print(f"DAY 1 + follow-through 3 days, then next 20d: n {x.size} avg {x.mean()*100:+.2f}% | Day 1 that faded: n {y.size} avg {y.mean()*100:+.2f}%")
# Did today's pharma qualify? latest data is Oct 13; show Large-cap Pharma last values + biggest days
g = "Large-cap Pharma"
print(g, "last Day-1 dates:", [d.strftime('%Y-%m-%d') for d in E1[g][E1[g]].index][-6:])
for d in E1[g][E1[g]].index[-6:]:
    print("  ", d.date(), {n: (round(float(fwd[n].at[d, g])*100, 1) if pd.notna(fwd[n].at[d, g]) else None) for n in (10, 20, 40)})
# how often Day-1 later becomes an ignition within 15 sessions
ign = D["idxhi40"].astype(bool) & (D["acc"] > 0.25) & (D["br21"] >= 0.8) & (D["drk"] >= 0.30)
later = ign.shift(-15).rolling(15).max() if False else ign[::-1].rolling(15, min_periods=1).max()[::-1].shift(-1)
cnt = int(E1.loc[warm:].to_numpy().sum()); conv = int((E1 & (later > 0)).loc[warm:].to_numpy().sum())
print(f"Day-1 events followed by an IGNITION within 15 sessions: {conv}/{cnt}")
