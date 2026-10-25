"""One pick per sub-theme vs the top 3 regardless of group (Adam, Oct 25 2026). Same replay and exits as the tracker.
Also the risk side: how spread out each week's 3 picks were (average pairwise correlation of their weekly returns
over the hold) and the worst weeks."""
import sys, pickle, json, numpy as np, pandas as pd
sys.path.insert(0, "/home/claude/breadth-monitor")
from breadth import launch, store
F, w, cols = pickle.load(open("/tmp/launchF.pkl", "rb"))
F = launch.frames(w, cols, store.load_subthemes())
days, wd = F["days"], F["wd"]; O, C = F["dO"].to_numpy(), F["dC"].to_numpy()
WC, E50, A = F["W"]["c"].to_numpy(), F["e50"].to_numpy(), F["atr"].to_numpy(); spy = w["c"]["SPY"].to_numpy()
ent = days.searchsorted(wd, side="right"); hd = 65
def run(one):
    launch.PICK["one_per_sub"] = one
    held, rows = {}, []
    for i in range(40, len(wd)):
        if ent[i] + hd > len(days): break
        hold = {cols[j] for j, k in held.items() if k > i - 13}
        got = launch.select(F, i, hold)
        a = ent[i]; xs = []; subs = []; paths = []
        for p in got:
            j = p["j"]; held[j] = i; e = O[a, j]
            if not np.isfinite(e) or e <= 0: continue
            sm = launch.stop_mult(p["stage"], A[i, j]); xi = a + hd - 1
            for k in range(i + 1, min(i + 14, len(wd))):
                if WC[k, j] < E50[k, j] * sm: xi = min(days.searchsorted(wd[k]), a + hd - 1); break
            xs.append(C[xi, j] / e - 1 - (spy[xi] / spy[a] - 1)); subs.append(F["sub_of"].get(p["t"]))
            paths.append(pd.Series(C[a:a + hd, j]).pct_change().values[1:])
        if not xs: continue
        cc = np.corrcoef(np.array(paths)) if len(paths) > 1 else np.array([[1]])
        corr = np.nanmean(cc[np.triu_indices(len(paths), 1)]) if len(paths) > 1 else np.nan
        rows.append(dict(date=wd[i], wk=np.mean(xs), n=len(xs), same=len(subs) - len(set(subs)), corr=corr, picks=xs))
    W = pd.DataFrame(rows); sp = W.date.iloc[len(W) // 2]
    allp = np.concatenate(W.picks.values)
    tt = W.wk.mean() / (W.wk.std(ddof=1) / np.sqrt(len(W)))
    return dict(weeks=len(W), mean=W.wk.mean(), med_pick=np.median(allp), t=tt, h1=W[W.date < sp].wk.mean(), h2=W[W.date >= sp].wk.mean(),
                beat=(allp > 0).mean(), weekly_sd=W.wk.std(), worst_week=W.wk.min(), worst5=W.wk.nsmallest(5).mean(), corr=W["corr"].mean(),
                weeks_with_dupes=int((W.same > 0).sum())), W
a, Wa = run(True); b, Wb = run(False)
for nm, r in (("one per sub-theme (now)", a), ("top 3 any group", b)):
    print(nm, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
d = (Wb.set_index("date").wk - Wa.set_index("date").wk).dropna()
print("same-group minus one-per-group by week: %+.3f, t %.2f, weeks differ %d" % (d.mean(), d.mean() / (d.std(ddof=1) / np.sqrt(len(d))), int((d != 0).sum())))
launch.PICK["one_per_sub"] = True
