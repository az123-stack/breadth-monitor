"""Polished setups study (Adam, Oct 25 2026): inside leading sub-themes (top third on 13-week return, as of the PRIOR week),
do (a) late-stage leaders nuzzling into their EMAs and (b) high tight flags near the pivot beat the same setups outside them?
Daily bars, split-adjusted. Entry next session (nuzzle: open; flag: buy-stop at the pivot within 5 sessions). Outcome: 20-session
return vs SPY and R (nuzzle: stop 1 ADR under entry; flag: stop at the flag low, exit on a close under the 10 EMA after day 3 or 20 days)."""
import sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/home/claude/breadth-monitor")
from breadth import store, strength, launch
b = store.apply_splits(store.load_bars(), store.load_splits())
uni = set(pd.read_csv("data/universe.csv").iloc[:, 0]); w = strength.wide_all(b)
cols = [t for t in w["c"].columns if t in uni]
F = launch.frames(w, cols, store.load_subthemes())
c, o, h, l, v = (w[k][cols] for k in ("c", "o", "h", "l", "v")); days = c.index
adr = ((h / l) - 1).rolling(20, min_periods=15).mean()
dvol = (c * v).rolling(20, min_periods=15).mean()
e9, e10, e21, e50 = (c.ewm(span=n, adjust=False, min_periods=n).mean() for n in (9, 10, 21, 50))
liq = (c >= 5) & (dvol >= 20e6)
# group state known on each day = last COMPLETED week's rank (shift 1 week, then forward-fill to days)
gr = F["grank"].shift(1).reindex(days, method="ffill")
lead = gr >= 2 / 3; nogrp = gr.isna()
wk_run = F["run"].reindex(days, method="ffill"); wk_stack = ((F["e9"] > F["e21"]) & (F["e21"] > F["e50"])).reindex(days, method="ffill")
rs = F["rsd"]
went = (wk_run > 8) & wk_stack                                                     # already moved: 9+ weeks over the 50 WEMA, weekly stack
up = (e21 > e50) & (e50 > e50.shift(10))
ribbon_hi = np.maximum(e9, e21)
nuz = liq & went & up & (rs >= 70) & (l <= ribbon_hi + 0.25 * adr * c) & (c >= e21 - 0.5 * adr * c) & (c <= e9 + 1.0 * adr * c)
nuz = nuz & ~nuz.shift(1, fill_value=False).rolling(5, min_periods=1).max().astype(bool)   # first touch in 5 sessions
# high tight flag: 30%+ leg into a high within the last 3-15 sessions, flag depth <= 25% and <= 3 ADR, last 5 days tight, close within 1 ADR of the high
hh = h.rolling(15, min_periods=3).max(); since = h.rolling(15, min_periods=3).apply(lambda x: len(x) - 1 - np.argmax(x), raw=True)
base_lo = l.shift(15).rolling(40, min_periods=20).min()
leg = hh / base_lo - 1
fl_lo = l.rolling(15, min_periods=3).min()  # NOTE: superseded in breadth/polished.py (flag low = since the high)
depth = 1 - fl_lo / hh
tight5 = (h.rolling(5).max() / l.rolling(5).min() - 1) <= 2.0 * adr
flag = liq & (leg >= 0.30) & (since >= 3) & (since <= 15) & (depth <= 0.25) & (depth <= 3 * adr) & tight5 & (c >= hh * (1 - adr)) & (c > e21) & (rs >= 70)
flag = flag & ~flag.shift(1, fill_value=False).rolling(10, min_periods=1).max().astype(bool)
spy = w["c"]["SPY"]; spyo = w["o"]["SPY"]
C, O, H, L, E10, A = (x.to_numpy() for x in (c, o, h, l, e10, adr)); HH, FL = hh.to_numpy(), fl_lo.to_numpy()
S, SO = spy.to_numpy(), spyo.to_numpy(); n = len(days)
def outcome(mask, kind):
    rows = []; M = mask.to_numpy(); LD, NG = lead.to_numpy(), nogrp.to_numpy()
    for i in range(60, n - 21):
        for j in np.flatnonzero(M[i]):
            a = i + 1
            if kind == "nuz":
                e = O[a, j]; stop = e * (1 - A[i, j]); ent = a
            else:
                piv = HH[i, j]; ent = None
                for k in range(a, min(a + 5, n - 20)):
                    if H[k, j] >= piv: ent = k; e = max(O[k, j], piv); break
                if ent is None: continue
                stop = FL[i, j]
            if not (np.isfinite(e) and e > stop > 0): continue
            risk = max(e - stop, 0.3 * A[i, j] * e)
            ex = min(ent + 19, n - 1); px = C[ex, j]
            for k in range(ent, min(ent + 20, n)):
                if L[k, j] <= stop: px = min(O[k, j], stop) if k > ent else stop; ex = k; break
                if kind == "flag" and k >= ent + 3 and C[k, j] < E10[k, j]: px = C[k, j]; ex = k; break
            r = px / e - 1; sx = S[ex] / SO[ent] - 1
            rows.append(dict(date=days[i], t=cols[j], grp="lead" if LD[i, j] else "none" if NG[i, j] else "other", R=(px - e) / risk, ret=r, xs=r - sx))
    return pd.DataFrame(rows)
for kind, m in (("nuz", nuz), ("flag", flag)):
    X = outcome(m, kind); split = X.date.sort_values().iloc[len(X) // 2]
    print(f"\n== {kind}: {len(X)} trades {X.date.min().date()} - {X.date.max().date()}")
    g = X.groupby("grp").agg(n=("R", "size"), R=("R", "mean"), win=("R", lambda s: (s > 0).mean()), xs=("xs", "mean"), xs_med=("xs", "median"))
    print(g.round(3))
    for hlf, x in (("h1", X[X.date < split]), ("h2", X[X.date >= split])):
        print(hlf, x.groupby("grp").R.mean().round(3).to_dict(), "n", x.groupby("grp").size().to_dict())
    d = X[X.grp == "lead"].groupby("date").R.mean() - X[X.grp != "lead"].groupby("date").R.mean()
    d = d.dropna(); print("lead minus rest by date: %+.3fR t %.2f (%d dates)" % (d.mean(), d.mean() / (d.std() / np.sqrt(len(d))), len(d)))
    X.to_pickle(f"/tmp/polished_{kind}.pkl")
