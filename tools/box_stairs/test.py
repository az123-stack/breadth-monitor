import sys, os, pickle
sys.path.insert(0, "/home/claude/breadth-monitor"); os.chdir("/home/claude/breadth-monitor")
import numpy as np, pandas as pd
from breadth import store, strength, stairs
ev = pickle.load(open("/tmp/box_ev.pkl", "rb"))
b = store.apply_splits(store.load_bars(), store.load_splits())
w = strength.wide_all(b); c, h, l, v = w["c"], w["h"], w["l"], w["v"]; dates = c.index
S = stairs.frames(c, h, l, v)
sub = store.load_subthemes(); th = store.load_themes(); th = th[th["role"] != "etf"]
sub_of = dict(zip(sub["ticker"], sub["subtheme"])); theme_of = dict(zip(th["ticker"], th["theme"]))
G = stairs.group_frames(c, S, sub.groupby("subtheme")["ticker"].apply(list).to_dict())
TG = stairs.group_frames(c, S, th.groupby("theme")["ticker"].apply(list).to_dict())
gs = {}
for nm, X in (("sub", G), ("th", TG)):
    st_, sp_, _, _ = stairs.states(X)
    gs[nm] = {"set": st_, "step": sp_, "lead": (X["idx"] / X["idx"].shift(60)).rank(axis=1, pct=True) >= 0.7}
def gv(nm, key, g, i):
    F = gs[nm][key]
    return bool(F[g].iat[i]) if g in F.columns else None
rows = []
for e in ev:
    if e.get("gap") or e.get("R") is None or not np.isfinite(e["R"]): continue
    i, t = e["i"], e["t"]
    if t not in c.columns: continue
    g = sub_of.get(t); tt = theme_of.get(t)
    def grp(key):
        a = gv("sub", key, g, i) if g else None
        return a if a is not None else (gv("th", key, tt, i) if tt else None)
    lead, gset, gstep = grp("lead"), grp("set"), grp("step")
    rows.append({"type": e["type"], "date": dates[i], "R": e["R"], "R5": e.get("R5"), "x21": e.get("x21"), "state": e["state"],
                 "own_nuz": bool(S["nuz5"][t].iat[i]), "own_lift": bool(S["lift3"][t].iat[i]), "own_brk": bool(S["brk3"][t].iat[i]),
                 "lead": lead, "gact": None if gset is None else bool(gset or gstep), "has_grp": lead is not None})
D = pd.DataFrame(rows); D["own_nl"] = D.own_nuz | D.own_lift
split = D.date.sort_values().iloc[len(D) // 2]
D.to_pickle("/tmp/box_stair_rows.pkl")
def welch(a, b):
    a, b = a.dropna(), b.dropna()
    if len(a) < 10 or len(b) < 10: return np.nan
    return (a.mean() - b.mean()) / np.sqrt(a.var() / len(a) + b.var() / len(b))
conds = {"own nuzzled/lifting": lambda d: d.own_nl, "own step break": lambda d: d.own_brk,
         "★ leading group": lambda d: d.lead.fillna(False).astype(bool), "group setting/stepping": lambda d: d.gact.fillna(False).astype(bool),
         "★ group setting/stepping": lambda d: d.lead.fillna(False).astype(bool) & d.gact.fillna(False).astype(bool),
         "★ group + own nuzzled/lifting": lambda d: d.lead.fillna(False).astype(bool) & d.own_nl,
         "★ group setting/stepping + own nuz/lift": lambda d: d.lead.fillna(False).astype(bool) & d.gact.fillna(False).astype(bool) & d.own_nl}
for typ in ("retest_long", "trap_long", "far_long", "retest_short", "trap_short"):
    d = D[D.type == typ]
    print(f"\n{typ}: n {len(d)}  all R {d.R.mean():+.2f}  R5 {d.R5.mean():+.2f}")
    for nm, f in conds.items():
        m = f(d); a, r = d[m], d[~m]
        if len(a) < 15: print(f"  {nm:40s} n {len(a)}"); continue
        h1 = a[a.date < split].R.mean() - r[r.date < split].R.mean(); h2 = a[a.date >= split].R.mean() - r[r.date >= split].R.mean()
        print(f"  {nm:40s} n {len(a):5d}  R {a.R.mean():+.2f} vs {r.R.mean():+.2f}  edge {a.R.mean()-r.R.mean():+.2f} t {welch(a.R, r.R):+.1f}  halves {h1:+.2f}/{h2:+.2f}"
              f"  | R5 edge {a.R5.mean()-r.R5.mean():+.2f} t {welch(a.R5, r.R5):+.1f}  | post-thrust n {int((a.state!='none').sum())} R {a[a.state!='none'].R.mean():+.2f}")
