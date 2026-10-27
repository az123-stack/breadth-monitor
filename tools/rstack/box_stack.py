"""R stacking, first test bed (Adam, Oct 27 2026: "this trade is 0.8R, that one 0.5R, but layered together they bring 1.3R —
I want to keep making this smarter").

Uses every past Box trade (breadth/boxstudy.py: ~2 years, next-open entry, stop, 20-session exit, R floored 0.3 ADR) with its
~40 yes/no conditions (market, group, stock). Three questions, all answered on the FIRST half and checked on the SECOND half:

1. Single layers: R with the condition minus R without (what boxstudy already does).
2. Synergy: for each pair of conditions, the actual R when both are present vs the "just add them up" prediction
   (base + lift A + lift B). Pairs that beat the sum in the first half: does it hold in the second half?
3. Stacked expected R: a shrunk additive model (ridge on the condition flags, fitted on the first half) + the synergy pairs that
   held up. Out of sample: do trades the model scores highest in the second half really earn more? Compared with today's
   grade (boxstudy.expected) and with no model at all.

    python tools/rstack/box_stack.py [--types retest_long,trap_long] [--cache /tmp/box_ev.pkl]
"""
import argparse
import itertools
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from breadth import boxes as BX, boxstudy as BS, config, store, strength  # noqa: E402


def events(cache=None):
    if cache and os.path.exists(cache):
        return pickle.load(open(cache, "rb"))
    adjusted = store.apply_splits(store.load_bars(), store.load_splits())
    breadth = pd.read_csv(config.ROOT / "data" / "breadth.csv", index_col=0, parse_dates=True)
    universe = set(pd.read_csv(config.ROOT / "data" / "universe.csv").iloc[:, 0])
    w = strength.wide_all(adjusted)
    dates = w["c"].index
    cols = [t for t in w["c"].columns if t in universe]
    C, V, H, L = (w[k][cols].to_numpy() for k in ("c", "v", "h", "l"))
    dv = pd.DataFrame(C * V).rolling(50, min_periods=30).mean().to_numpy()
    liq = (C >= 5) & (dv >= 20e6)
    ADR = (pd.DataFrame(H / L).rolling(20, min_periods=15).mean().to_numpy() - 1) * 100
    raw = strength.rs_raw(w["c"][cols])
    rs = (raw.where(pd.DataFrame(liq, index=dates, columns=cols)).rank(axis=1, pct=True) * 99).clip(1, 99).to_numpy()
    spy, spyo = w["c"][config.BENCHMARK].to_numpy(), w["o"][config.BENCHMARK].to_numpy()
    sub = store.load_subthemes()
    th = store.load_themes()
    th = th[th["role"] == "member"] if "role" in th.columns else th
    sub_of, theme_of = dict(zip(sub["ticker"], sub["subtheme"])), dict(zip(th["ticker"], th["theme"]))
    grp = BS.group_frames(w["c"], sub.groupby("subtheme")["ticker"].apply(list).to_dict(), spy)
    thm = BS.group_frames(w["c"], th.groupby("theme")["ticker"].apply(list).to_dict(), spy)
    mk = BS.market_frame(dates, breadth, spy)
    ev = BS.features(BS.collect(w, cols, liq, rs, ADR, spy, spyo), w, cols, rs, ADR, spy, mk, grp, sub_of, theme_of, thm)
    first = BX.CFG["pole_days"] + BX.CFG["min_len"] + 2
    split = dates[first + (len(dates) - first) // 2].strftime("%Y-%m-%d")
    out = (ev, split)
    if cache:
        pickle.dump(out, open(cache, "wb"))
    return out


def table(ev, typ):
    conds = BS.conditions(1)          # long trades: "with the trade" conditions read as written
    rows = [e for e in ev if e["type"] == typ and not e.get("gap") and BS._ok(e.get("R"))]
    X = pd.DataFrame({n: [bool(f(e)) for e in rows] for g, n, f in conds})
    X = X.loc[:, (X.mean() > 0.03) & (X.mean() < 0.97)]          # drop flags that are almost always on or off
    y = pd.Series([e["R"] for e in rows])
    d = pd.Series([e["date"] for e in rows])
    return X, y, d, rows


def _t(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 5 or len(b) < 5:
        return None
    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return round(float((a.mean() - b.mean()) / se), 2) if se > 0 else None


def ridge(X, y, lam):
    Xm = X.to_numpy(float)
    mu = Xm.mean(0)
    Z = Xm - mu
    b = np.linalg.solve(Z.T @ Z + lam * len(y) * np.eye(Z.shape[1]), Z.T @ (y.to_numpy() - y.mean()))
    return lambda Xn: y.mean() + (Xn.to_numpy(float) - mu) @ b, pd.Series(b, index=X.columns)


def quintiles(pred, y):
    q = pd.qcut(pd.Series(pred).rank(method="first"), 5, labels=False)
    return [round(float(y[q.values == k].mean()), 3) for k in range(5)]


def analyse(ev, split, typ, min_n=40):
    X, y, d, rows = table(ev, typ)
    tr, te = (d < split).to_numpy(), (d >= split).to_numpy()
    base_tr, base_te = float(y[tr].mean()), float(y[te].mean())
    # 1. single layers (lift = with minus without), each half
    single = {}
    for c in X.columns:
        on = X[c].to_numpy()
        a, b = y[tr & on], y[tr & ~on]
        a2, b2 = y[te & on], y[te & ~on]
        if len(a) >= min_n and len(a2) >= min_n:
            single[c] = {"n1": int(len(a)), "lift1": round(float(a.mean() - b.mean()), 3), "t1": _t(a, b),
                         "n2": int(len(a2)), "lift2": round(float(a2.mean() - b2.mean()), 3), "t2": _t(a2, b2)}
    # 2. synergy: joint R vs base + liftA + liftB (first half), checked on the second half
    syn = []
    cols = list(single)
    for A, B in itertools.combinations(cols, 2):
        both1, both2 = tr & X[A].to_numpy() & X[B].to_numpy(), te & X[A].to_numpy() & X[B].to_numpy()
        if both1.sum() < min_n or both2.sum() < min_n // 2:
            continue
        add1 = base_tr + single[A]["lift1"] + single[B]["lift1"]
        add2 = base_te + single[A]["lift2"] + single[B]["lift2"]
        s1, s2 = float(y[both1].mean() - add1), float(y[both2].mean() - add2)
        syn.append({"a": A, "b": B, "n1": int(both1.sum()), "n2": int(both2.sum()), "joint1": round(float(y[both1].mean()), 3),
                    "joint2": round(float(y[both2].mean()), 3), "add1": round(add1, 3), "add2": round(add2, 3),
                    "syn1": round(s1, 3), "syn2": round(s2, 3)})
    syn.sort(key=lambda s: -s["syn1"])
    top_syn = [s for s in syn if s["syn1"] >= 0.10][:15]
    held = [s for s in top_syn if s["syn2"] > 0]
    # 3. stacked model fitted on the first half, scored on the second
    Xi = X.copy()
    for s in held[:5]:
        Xi[s["a"] + " × " + s["b"]] = X[s["a"]] & X[s["b"]]
    best = None
    for lam in (0.003, 0.01, 0.03, 0.1):
        f, coef = ridge(X[tr], y[tr], lam)
        fi, coefi = ridge(Xi[tr], y[tr], lam)
        p, pi = f(X[te]), fi(Xi[te])
        yt = y[te].to_numpy()
        ic = float(pd.Series(p).corr(pd.Series(yt), method="spearman"))
        ici = float(pd.Series(pi).corr(pd.Series(yt), method="spearman"))
        r = {"lam": lam, "ic_additive": round(ic, 3), "ic_with_synergy": round(ici, 3),
             "quintiles_additive": quintiles(p, yt), "quintiles_with_synergy": quintiles(pi, yt),
             "top_coef": coef.sort_values(ascending=False).round(3).head(6).to_dict(),
             "bottom_coef": coef.sort_values().round(3).head(4).to_dict()}
        if best is None or ic > best["ic_additive"]:
            best = r
    return {"type": typ, "n_train": int(tr.sum()), "n_test": int(te.sum()), "split": split, "base_train": round(base_tr, 3),
            "base_test": round(base_te, 3), "flags": len(X.columns),
            "single_held": sorted([dict(k=k, **v) for k, v in single.items() if v["lift1"] > 0.05 and v["lift2"] > 0.05],
                                  key=lambda r: -r["lift1"])[:12],
            "synergy_top": top_syn, "synergy_held": len(held), "synergy_tested": len(top_syn), "model": best}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--types", default="retest_long,trap_long")
    ap.add_argument("--cache", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    ev, split = events(a.cache)
    res = [analyse(ev, split, t) for t in a.types.split(",")]
    print(json.dumps(res, indent=1, default=str))
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1, default=str)
