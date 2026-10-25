"""How many Launch picks to hold at once (Adam, Oct 25 2026: 'three every day might be too many').
Weekly steps; a position stays open until its stop (weekly close through the line) or 13 weeks. Each week, fill free slots
from the ranked pick list (one per sub-theme, skip held). Compare caps on open positions and new picks per week."""
import sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/home/claude/breadth-monitor")
from breadth import launch, store
F, w, cols = pickle.load(open("/tmp/launchF.pkl", "rb"))
F = launch.frames(w, cols, store.load_subthemes())
days, wd = F["days"], F["wd"]; O, C = F["dO"].to_numpy(), F["dC"].to_numpy()
WC, E50, A = F["W"]["c"].to_numpy(), F["e50"].to_numpy(), F["atr"].to_numpy(); spy = w["c"]["SPY"].to_numpy()
ent = days.searchsorted(wd, side="right"); hd = 65
last_i = max(i for i in range(len(wd)) if ent[i] + hd <= len(days))
def exit_of(i, j, stage):
    a = ent[i]; sm = launch.stop_mult(stage, A[i, j])
    for k in range(i + 1, min(i + 14, len(wd))):
        if WC[k, j] < E50[k, j] * sm: return k, min(days.searchsorted(wd[k]), a + hd - 1)
    return i + 13, a + hd - 1
def sim(cap, per_week):
    open_, trades, occ = {}, [], []
    for i in range(40, last_i + 1):
        open_ = {j: v for j, v in open_.items() if v["xw"] > i}          # closed on or before this week's close
        occ.append(len(open_))
        free = min(cap - len(open_), per_week)
        if free <= 0: continue
        for p in launch.select(F, i, {cols[j] for j in open_}, n=free):
            j = p["j"]; a = ent[i]; e = O[a, j]
            if not np.isfinite(e) or e <= 0: continue
            xw, xi = exit_of(i, j, p["stage"])
            r = C[xi, j] / e - 1; open_[j] = {"xw": xw}
            trades.append(dict(date=wd[i], r=r, x=r - (spy[xi] / spy[a] - 1), days=xi - a + 1))
    T = pd.DataFrame(trades); sp = T.date.iloc[len(T) // 2]
    wk = T.groupby("date").x.mean(); tt = wk.mean() / (wk.std(ddof=1) / np.sqrt(len(wk)))
    return dict(trades=len(T), new_per_wk=round(len(T) / (last_i - 39), 2), avg_open=round(np.mean(occ), 1), max_open=int(np.max(occ)),
                vs_spy=round(T.x.mean(), 3), median=round(T.x.median(), 3), beat=round((T.x > 0).mean(), 2), t=round(tt, 2),
                h1=round(T[T.date < sp].x.mean(), 3), h2=round(T[T.date >= sp].x.mean(), 3), hold_wks=round(T.days.mean() / 5, 1))
for cap, pw in ((99, 3), (12, 3), (8, 3), (6, 3), (6, 1), (4, 1), (3, 1), (99, 1)):
    print(f"max open {cap if cap < 99 else 'none':>4}, new per week {pw}:", sim(cap, pw))
