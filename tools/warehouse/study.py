"""Step-1 study (PLAN.md v3.1): power gate first (no outcomes), then H1, robustness, exploratory tables.
Run: PYTHONPATH=. python3 tools/warehouse/study.py [--gate-only]"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
E = pd.read_parquet(ROOT / "data" / "warehouse" / "episodes.parquet")
META = json.load(open(ROOT / "data" / "warehouse" / "meta.json"))
rng = np.random.default_rng(7)

E["wk"] = E["S"].dt.to_period("W-FRI").astype(str)
E["mo"] = E["S"].dt.to_period("M")
mid = E["S"].sort_values().iloc[len(E) // 2]
E["half"] = np.where(E["S"] < mid, 1, 2)
first = E[E["half"] == 1]
cut = first["ext"].quantile(2 / 3)
E["ext_top"] = E["ext"] >= cut
E["cell"] = E["hit_supply"] & E["ext_top"]
E["informative"] = E["D_fill"] | E["W_fill"]
E["mgroup"] = E["mkt_group"].where(E["mkt_group"] >= 0, -1)
E["diff"] = E["P_W"] - E["P_D"]


def gate():
    print(f"episodes {len(E)} · starts {E.S.min():%Y-%m-%d} → {E.S.max():%Y-%m-%d} · split at {mid:%Y-%m-%d} · ext top-third cut {cut:.2f} weekly ATRs")
    print("SPY 3%+ pullback groups:", META["groups"])
    print(f"monthly levels: {META['n_monthly']} tickers, mismatches dropped {len(META['bad_levels'])}; episodes with monthly data {E.has_monthly.mean():.0%}")
    print("first dip kind:", E.first_kind.value_counts(dropna=False).to_dict())
    print("hit_supply:", int(E.hit_supply.sum()), "· ext top third:", int(E.ext_top.sum()), "· cell:", int(E.cell.sum()))
    c = E[E.cell]
    inf = c[c.informative]
    print(f"cell informative episodes {len(inf)} (half 1 {int((inf.half == 1).sum())}, half 2 {int((inf.half == 2).sum())}); "
          f"market groups {sorted(inf.mgroup.unique().tolist())} (−1 = no SPY pullback)")
    ok = len(inf) >= 40 and (inf.half == 1).sum() >= 15 and (inf.half == 2).sum() >= 15 and inf.mgroup.nunique() >= 4
    print("POWER GATE:", "MET" if ok else "NOT MET → H1 inconclusive")
    return ok


def ct(x, cl):
    """cluster-robust t of the mean of x, clusters cl"""
    d = pd.DataFrame({"x": x, "c": cl})
    g = d.groupby("c")["x"].sum()
    n, G = len(d), len(g)
    m = d["x"].mean()
    r = d.groupby("c").apply(lambda z: (z["x"] - m).sum())
    var = (G / (G - 1)) * (r ** 2).sum() / n ** 2 if G > 1 else np.nan
    return m, (m / np.sqrt(var) if var and var > 0 else np.nan)


def effect(D):
    a, b = D[D.cell], D[~D.cell]
    return a["diff"].mean() - b["diff"].mean()


def eff_t(D):
    """cluster t of the difference-in-differences via per-episode contrast scaled by group sizes"""
    a, b = D[D.cell], D[~D.cell]
    x = np.where(D.cell, D["diff"] / len(a), -D["diff"] / len(b)) * len(D)
    return ct(x, D["wk"])[1]


def boot(D, B=2000):
    mos = sorted(D["mo"].unique())
    k = len(mos)
    out = []
    by = {m: D[D.mo == m] for m in mos}
    for _ in range(B):
        parts = []
        while sum(len(p) for p in parts) < len(D):
            s = rng.integers(0, max(1, k - 2))
            parts += [by[m] for m in mos[s:s + 3]]
        X = pd.concat(parts)
        if X.cell.any() and (~X.cell).any():
            out.append(effect(X))
    return np.percentile(out, [2.5, 97.5])


def perm(D, R=10000):
    obs = effect(D)
    cnt = 0
    grp = D["mgroup"].to_numpy()
    cell = D["cell"].to_numpy()
    diff = D["diff"].to_numpy()
    for _ in range(R):
        c2 = cell.copy()
        for g in np.unique(grp):
            ix = np.flatnonzero(grp == g)
            c2[ix] = rng.permutation(c2[ix])
        if c2.any() and (~c2).any() and diff[c2].mean() - diff[~c2].mean() >= obs:
            cnt += 1
    return (cnt + 1) / (R + 1)


def h1():
    D = E
    eff, t = effect(D), eff_t(D)
    cin, tin = ct(D[D.cell]["diff"], D[D.cell]["wk"])
    lo, hi = boot(D)
    p = perm(D)
    halves = {h: (effect(D[D.half == h]), D[(D.half == h) & D.cell]["diff"].mean()) for h in (1, 2)}
    gs = D[D.cell].groupby("mgroup")["diff"].mean()
    gshare = (gs > 0).mean()
    print(f"\nH1 effect {eff:+.3f}R (cluster t {t:.2f}) · in-cell P_W−P_D {cin:+.3f}R (t {tin:.2f}) · bootstrap 95% [{lo:+.3f}, {hi:+.3f}] · perm p {p:.4f}")
    print("halves (effect, in-cell diff):", {k: (round(a, 3), round(b, 3)) for k, (a, b) in halves.items()})
    print("in-cell diff by market group:", gs.round(3).to_dict(), f"share > 0: {gshare:.0%}")
    rob = {
        "starts ≥ 2025-11-07": D[D.S >= "2025-11-07"],
        "no post-thrust": D[~D.thrust],
        "no top 1% R": D[(D[["D_R", "W_R"]].max(axis=1) < D[["D_R", "W_R"]].max(axis=1).quantile(0.99))],
        "strong breadth": D[D.strong], "not strong": D[~D.strong],
    }
    for s in D["sub"].value_counts().index[:3]:
        rob[f"without {s}"] = D[D["sub"] != s]
    fails = 0
    print("robustness (effect, keeps sign & ≥ half size?):")
    for k, X in rob.items():
        if not X.cell.any() or not (~X.cell).any():
            print(f"  {k}: no cell episodes"); fails += 1; continue
        e = effect(X)
        good = e > 0 and e >= eff / 2
        fails += not good
        print(f"  {k}: {e:+.3f} {'ok' if good else 'FAIL'}")
    Dx = D.assign(diff=D["W_xs"].fillna(0) - D["D_xs"].fillna(0))
    ex = effect(Dx)
    print(f"  excess vs SPY instead of R: {ex:+.4f} {'ok' if ex > 0 else 'FAIL'}"); fails += ex <= 0
    halves_ok = all(a > 0 and b > 0 for a, b in halves.values())
    proven = eff >= 0.15 and t >= 2 and p < 0.05 and lo > 0 and cin > 0 and tin >= 1.5 and halves_ok and gshare >= 2 / 3 and fails == 0
    core = eff >= 0.15 and t >= 2 and p < 0.05 and lo > 0 and cin > 0 and tin >= 1.5 and halves_ok
    if proven:
        lab = "proven"
    elif core and (fails + (gshare < 2 / 3)) == 1:
        lab = "info / promising"
    elif eff <= 0 or hi < 0.15:
        lab = "doesn't work"
    else:
        lab = "not shown"
    print("LABEL:", lab, f"(robustness failures {fails})")
    return lab


def exploratory():
    print("\n--- exploratory (no 'proven' claims) ---")
    def pol(X):
        r = {}
        for k in ("P_D", "P_W", "P_DW"):
            r[k] = round(X[k].mean(), 3)
        r["traded D/W"] = (round(X.D_fill.mean(), 2), round(X.W_fill.mean(), 2))
        r["R/trade D/W"] = (round(X.loc[X.D_fill, "D_R"].mean(), 3), round(X.loc[X.W_fill, "W_R"].mean(), 3))
        r["P_DW per unit"] = round(X["P_DW"].sum() / max(X["P_DW_units"].sum(), 1), 3)
        r["n"] = len(X)
        return r
    print("all:", pol(E))
    for nm, m in (("hit supply", E.hit_supply), ("no supply hit", ~E.hit_supply), ("ext top third", E.ext_top), ("ext rest", ~E.ext_top),
                  ("CELL", E.cell), ("strong breadth", E.strong), ("post-thrust", E.thrust), ("half 1", E.half == 1), ("half 2", E.half == 2)):
        print(f"{nm}:", pol(E[m]))
    r = E.room.replace(np.inf, 9)
    for nm, m in (("room < 5%", r < 0.05), ("room 5–15%", (r >= 0.05) & (r < 0.15)), ("room ≥ 15% / none", r >= 0.15)):
        print(f"{nm}:", pol(E[m]))
    print("secondary exit (20 sessions) P_D / P_W:", round(E.D_R20.mean(), 3), round(E.W_R20.mean(), 3))
    print("W's R after D was stopped (conditional):", round(E.loc[E.D_stopped & E.W2_fill, "W2_R"].mean(), 3), int((E.D_stopped & E.W2_fill).sum()))
    print("same-day stop-outs D/W:", int(E.D_sameday.sum()), int(E.W_sameday.sum()), "· censored:", int(E.D_censored.sum() + E.W_censored.sum()))


if __name__ == "__main__":
    ok = gate()
    if "--gate-only" in sys.argv:
        sys.exit()
    if ok:
        h1()
    else:
        print("H1: inconclusive (gate not met) — reporting the overall policy comparison only")
    exploratory()
