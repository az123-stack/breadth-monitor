"""Do the Launch picks beat a random pick from the same eligible pool? (Adam, Oct 25 2026)
Each past week: eligible = every stock passing the pick filters (curl/fresh, group point, $20M+/day, weekly ATR <= 15%).
Same exits as the tracker (13 weeks or a weekly close through the stop line). Compare picks #1/#2/#3 vs the pool average."""
import sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/home/claude/breadth-monitor")
from breadth import launch, store
F, w, cols = pickle.load(open("/tmp/launchF.pkl", "rb"))
F = launch.frames(w, cols, store.load_subthemes())
days, wd = F["days"], F["wd"]; O, C = F["dO"].to_numpy(), F["dC"].to_numpy()
WC, E50, A = F["W"]["c"].to_numpy(), F["e50"].to_numpy(), F["atr"].to_numpy(); spy = w["c"]["SPY"].to_numpy()
ent = days.searchsorted(wd, side="right"); hd = 65
def res(i, j, stage):
    a = ent[i]; e = O[a, j]
    if not np.isfinite(e) or e <= 0: return None
    sm = launch.stop_mult(stage, A[i, j]); xi = a + hd - 1
    for k in range(i + 1, min(i + 14, len(wd))):
        if WC[k, j] < E50[k, j] * sm: xi = min(days.searchsorted(wd[k]), a + hd - 1); break
    return C[xi, j] / e - 1 - (spy[xi] / spy[a] - 1)
rows = []
for i in range(40, len(wd)):
    if ent[i] + hd > len(days): break
    pool = launch.select(F, i, n=999)          # everything eligible, already in rank order (one per sub-theme)
    for k, p in enumerate(pool):
        r = res(i, p["j"], p["stage"])
        if r is not None: rows.append(dict(date=wd[i], rank=k + 1, n=len(pool), x=min(r, 3)))
X = pd.DataFrame(rows); X["top3"] = X["rank"] <= 3
wk = X.groupby("date").apply(lambda g: pd.Series({"top3": g[g.top3].x.mean(), "pool": g.x.mean(), "rest": g[~g.top3].x.mean() if (~g.top3).any() else np.nan, "n": len(g)}))
d = (wk.top3 - wk.pool).dropna(); d2 = (wk.top3 - wk.rest).dropna(); sp = d.index[len(d) // 2]
tt = lambda s: s.mean() / (s.std(ddof=1) / np.sqrt(len(s)))
print(f"weeks {len(wk)}, pool size median {wk.n.median():.0f} (one per sub-theme)")
print(f"top 3 vs SPY {wk.top3.mean():+.1%}, whole pool {wk.pool.mean():+.1%}, the rest (#4+) {wk.rest.mean():+.1%}")
print(f"top3 minus pool {d.mean():+.1%} t {tt(d):.2f} halves {d[d.index<sp].mean():+.1%} / {d[d.index>=sp].mean():+.1%}")
print(f"top3 minus rest {d2.mean():+.1%} t {tt(d2):.2f}")
print(X.groupby(X["rank"].clip(upper=6)).x.agg(["mean", "median", "count"]).round(3))
