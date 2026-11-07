"""In Play scoring study (Nov 7, 2026; Adam: "score the in play so it's sorted with the best at the top").
Question: among stocks In Play (the inplay.py rules, last 5 sessions), which traits pick the ones that do best over the next
10 sessions? Entry = next open after the signal date, exit = close 10 sessions later, measured vs SPY (same dates) and vs the
average in-play stock that day (date-demeaned). Each trait: mean with vs without, t over dates (date-paired), both halves.
Traits were chosen BEFORE looking, from earlier cards (group strength, RS, near highs, direction, freshness, and the
record-volume "avoid" tells: spike gap/day, > 20x volume, ADR > 10%, 2+ ADRs over the 21 EMA, 30%+ off the high).
Run: python tools/inplay_study/score.py   (uses data/bars; ~2 min)"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from breadth import store, strength, config
from breadth.inplay import frames, CFG

b = store.apply_splits(store.load_bars(), store.load_splits())
uni = store.load_universe()
tick = sorted(set(b["ticker"].unique()) & uni)
sub = b[b["ticker"].isin(tick + ["SPY"])]
piv = lambda k: sub.pivot_table(index="date", columns="ticker", values=k).sort_index()
c = piv("c"); W = {k: piv(k).reindex_like(c) for k in ("o", "h", "l", "v")}; W["c"] = c
spy_o, spy_c = W["o"]["SPY"], c["SPY"]
c = c[tick]; W = {k: v[tick] for k, v in W.items()}
F = frames(W)
dv20 = (c * W["v"]).rolling(20, min_periods=10).mean()
liq = (c >= CFG["px"]) & (dv20 >= CFG["dvol"])
ev = (F["news"] | F["brk"] | F["base"] | F["bdn"] | F["rng"]).astype(float)
inplay = (ev.rolling(CFG["win"], min_periods=1).max() > 0) & liq
# ago of the latest event, direction of the 5-session move
last_ev = ev.where(ev > 0).ffill(limit=CFG["win"] - 1)
d5 = c / c.shift(CFG["win"]) - 1
# RS percentile among liquid stocks
lq = (c >= config.MIN_PRICE) & (W["v"].rolling(20, min_periods=15).mean() >= config.MIN_AVG_VOLUME)
rsp = strength.rs_raw(c).where(lq).rank(axis=1, pct=True)
# sub-theme top third on 63-session equal-weight return (today's lists: mild hindsight)
sd = store.load_subthemes(); sub_of = dict(zip(sd["ticker"], sd["subtheme"]))
r1 = c.pct_change().clip(-0.5, 1.0)
grp_rank = pd.DataFrame(index=c.index, columns=c.columns, dtype=float)
groups = {}
for t, g in sub_of.items():
    if t in c.columns: groups.setdefault(g, []).append(t)
gidx = pd.DataFrame({g: (1 + r1[m].mean(axis=1)).cumprod() for g, m in groups.items() if len(m) >= 3})
g63 = (gidx / gidx.shift(63) - 1).rank(axis=1, pct=True)
for g, m in groups.items():
    if g in g63.columns:
        for t in m: grp_rank[t] = g63[g]
hi52 = W["h"].rolling(252, min_periods=120).max()
off = c / hi52 - 1
ema21 = c.ewm(span=21, adjust=False).mean()
ext = (c - ema21) / (c * F["adr"])
spike = ((F["gap"] >= 0.10) | (F["move"] >= 0.20) | (F["rv"] > 20)).astype(float).rolling(CFG["win"], min_periods=1).max() > 0
fwd = c.shift(-10) / W["o"].shift(-1) - 1
spy_f = spy_c.shift(-10) / spy_o.shift(-1) - 1
traits = {
    "up (5-day move > 0)": d5 > 0,
    "RS top 30%": rsp >= 0.7,
    "group top third (63d)": grp_rank >= 2 / 3,
    "within 15% of 52-wk high": off >= -0.15,
    "event today": ev > 0,
    "AVOID spike (gap 10%+/day +20%/vol 20x)": spike,
    "AVOID ADR > 10%": F["adr"] > 0.10,
    "AVOID 2+ ADRs over 21 EMA": ext > 2,
    "AVOID 30%+ off the high": off < -0.30,
}
rows = []
dates = c.index[260:-11]
for dt in dates:
    m = inplay.loc[dt].fillna(False)
    if m.sum() < 10: continue
    f = fwd.loc[dt][m]; ok = f.notna()
    if ok.sum() < 10: continue
    rows.append(pd.DataFrame({"date": dt, "t": f.index[ok], "fwd": f[ok].values, "xspy": (f[ok] - spy_f.loc[dt]).values,
                              **{k: v.loc[dt][m][ok].fillna(False).astype(bool).values for k, v in traits.items()}}))
D = pd.concat(rows, ignore_index=True)
D["dm"] = D["fwd"] - D.groupby("date")["fwd"].transform("mean")
half = D["date"] < D["date"].iloc[len(D) // 2] if len(D) else None
dts = sorted(D["date"].unique()); mid = dts[len(dts) // 2]
print(f"in-play stock-days: {len(D):,} on {len(dts)} dates ({str(dts[0])[:10]} to {str(dts[-1])[:10]}); all vs SPY 10d {D.xspy.mean()*100:+.2f}%")
def edge(sel):
    g = D.assign(s=sel).groupby(["date", "s"])["fwd"].mean().unstack().dropna()
    if len(g) < 20 or True not in g or False not in g: return None
    e = (g[True] - g[False]); t = e.mean() / (e.std() / np.sqrt(len(e)))
    h1, h2 = e[e.index < mid].mean(), e[e.index >= mid].mean()
    return e.mean(), t, h1, h2, sel.mean()
for k in traits:
    r = edge(D[k])
    if r: print(f"{k:42s} share {r[4]*100:4.0f}%  edge {r[0]*100:+.2f} pts  t {r[1]:+.1f}  halves {r[2]*100:+.2f} / {r[3]*100:+.2f}")
# composite: +1 per helpful trait, -1 per avoid tell (pre-registered, equal weights)
good = [k for k in traits if not k.startswith("AVOID")]; bad = [k for k in traits if k.startswith("AVOID")]
D["score"] = D[good].sum(axis=1) - D[bad].sum(axis=1)
D["q"] = D.groupby("date")["score"].rank(pct=True, method="first")
for lo, hi, name in [(0.8, 1.01, "top fifth"), (0, 0.2, "bottom fifth")]:
    s = D[(D.q > lo) & (D.q <= hi)]
    print(f"composite {name}: vs SPY {s.xspy.mean()*100:+.2f}%  vs avg in-play {s.dm.mean()*100:+.2f} pts  win {(s.fwd>0).mean()*100:.0f}%  n {len(s):,}")
e = D.assign(top=D.q > 0.8, bot=D.q <= 0.2)
g = e.groupby("date").apply(lambda x: x[x.top].fwd.mean() - x[x.bot].fwd.mean()).dropna()
print(f"top minus bottom fifth: {g.mean()*100:+.2f} pts  t {g.mean()/(g.std()/np.sqrt(len(g))):+.1f}  halves {g[g.index<mid].mean()*100:+.2f} / {g[g.index>=mid].mean()*100:+.2f}")
# Second composite = only the traits with the same sign in both halves above (chosen after looking: treat as a lead, forward-test it)
KEEP = ["group top third (63d)", "within 15% of 52-wk high"]
DROP = ["AVOID spike (gap 10%+/day +20%/vol 20x)", "AVOID ADR > 10%", "AVOID 30%+ off the high"]
D["score2"] = D[KEEP].sum(axis=1) - D[DROP].sum(axis=1)
print("\nscore2 (both-halves traits only): value  share  vs SPY 10d  vs avg in-play  win")
for v, s in D.groupby("score2"):
    print(f"  {v:+d}  {len(s)/len(D)*100:4.0f}%  {s.xspy.mean()*100:+6.2f}%  {s.dm.mean()*100:+6.2f} pts  {(s.fwd>0).mean()*100:3.0f}%")
D["q2"] = D.groupby("date")["score2"].rank(pct=True, method="average")
g = D.groupby("date").apply(lambda x: x[x.score2 >= 2].fwd.mean() - x[x.score2 <= -1].fwd.mean()).dropna()
print(f"score2 >= 2 minus <= -1: {g.mean()*100:+.2f} pts  t {g.mean()/(g.std()/np.sqrt(len(g))):+.1f} (overlapping 10-day windows: t overstated ~3x)  halves {g[g.index<mid].mean()*100:+.2f} / {g[g.index>=mid].mean()*100:+.2f}")
# non-overlapping check: every 10th date only
nd = dts[::10]; gn = g[g.index.isin(nd)]
print(f"non-overlapping dates ({len(gn)}): {gn.mean()*100:+.2f} pts  t {gn.mean()/(gn.std()/np.sqrt(len(gn))):+.1f}")
