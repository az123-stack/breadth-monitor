"""Turning-point leaders (Nov 4, 2026; Adam: "at the April low and a couple of other big turning points the next leaders set up near
their highs and all broke out together (DELL, HPE …). I think this might be another one of those moments; who's setting up similarly?").

Turning points = the dashboard's major breadth thrusts (metrics events, kind "thrust", tier "major"); deep = washout card's rule
(SPY 8%+ under its 60-day high and T2108 ≤ 25). Signal at the thrust-day close (no look-ahead: only bars up to that close), buy next open.
Universe: $5+, 50-day avg $20M+/day, 60+ sessions of history. Reference high = highest high over up to 252 sessions (Apr 2025 has only
~110 sessions behind it, so its "52-week" high is the high since Nov 2024).

Rules tested at each thrust (and, as the yardstick, on every 5th ordinary session):
  near10 / near15   close within 10% / 15% of the high
  held              off-high smaller than half of SPY's own drawdown from its high (held up while the market fell)
  rshi              RS line (close ÷ SPY) within 3% of its own high
  setup             near15 + RS line within 5% of its high + 10-session range ≤ 3 ADRs (tight, "setting up")
  setup_grp         setup + 2 or more other setup names in the same sub-theme ("setting up together")
  beta30            the washout card's basket: RS ≥ 80, top 30 by 60-day beta (for comparison)
Outcomes: next open → close 21 / 63 sessions later minus the equal-weight average liquid stock; share that closed above the high within
15 sessions ("broke out together"); share that doubled the market in 63 sessions.
Run: PYTHONPATH=. python3 tools/turn_leaders/study.py [--now]
"""
import sys

import numpy as np
import pandas as pd

from breadth import store, strength

bars = store.apply_splits(store.load_bars(), store.load_splits())
W = strength.wide_all(bars)
c, h, l, o, v = W["c"], W["h"], W["l"], W["o"], W["v"]
spy = c["SPY"]
dv = (c * v).rolling(50, min_periods=30).mean()
n_hist = c.notna().cumsum()
liquid = (c >= 5) & (dv >= 20e6) & (n_hist >= 60)
hi = h.rolling(252, min_periods=60).max()
off = c / hi - 1
rsl = c.div(spy, axis=0)
rs_off = rsl / rsl.rolling(252, min_periods=60).max() - 1
rng = (h / l - 1)
adr = rng.rolling(20, min_periods=15).mean()
r10 = (h.rolling(10).max() / l.rolling(10).min() - 1) / adr
spy_off = spy / h["SPY"].rolling(252, min_periods=60).max() - 1
ret = c.pct_change(fill_method=None)
beta60 = ret.rolling(60, min_periods=50).cov(ret["SPY"]).div(ret["SPY"].rolling(60, min_periods=50).var(), axis=0)
raw = strength.rs_raw(c)
sub_of = dict(zip(store.load_subthemes()["ticker"], store.load_subthemes()["subtheme"]))
idx = c.index
N = len(idx)


def rs_rank(i, names):
    return raw.iloc[i][names].rank(pct=True) * 99


def sets(i):
    L = liquid.iloc[i]
    names = L[L].index.difference(["SPY"])
    so = float(spy_off.iloc[i])
    o_ = off.iloc[i][names]
    S = {}
    S["near10"] = set(o_[o_ >= -0.10].index)
    S["near15"] = set(o_[o_ >= -0.15].index)
    S["held"] = set(o_[o_ >= so / 2].index) if so < -0.03 else set()
    S["rshi"] = set(names[(rs_off.iloc[i][names] >= -0.03).values])
    tight = r10.iloc[i][names] <= 3
    S["setup"] = set(names[((o_ >= -0.15) & (rs_off.iloc[i][names] >= -0.05) & tight).values])
    cnt = pd.Series([sub_of.get(t) for t in S["setup"]]).value_counts()
    S["setup_grp"] = {t for t in S["setup"] if sub_of.get(t) and cnt.get(sub_of[t], 0) >= 3}
    rk = rs_rank(i, names)
    b = beta60.iloc[i][names][rk >= 80].dropna().sort_values(ascending=False)
    S["beta30"] = set(b.index[:30])
    return names, S


def outcome(i, names, sel):
    if not sel or i + 1 >= N:
        return None
    e = o.iloc[i + 1]
    out = {"n": len(sel)}
    for k in (21, 63):
        j = i + k
        if j >= N:
            out[f"x{k}"] = np.nan
            continue
        f = (c.iloc[j][names] / e[names] - 1).clip(-0.9, 5)
        out[f"x{k}"] = float(f[list(sel)].mean() - f.mean())
        out[f"w{k}"] = float((f[list(sel)] > f.mean()).mean())
    j = min(i + 15, N - 1)
    brk = (c.iloc[i + 1:j + 1][list(sel)] > hi.iloc[i][list(sel)]).any()
    out["brk15"] = float(brk.mean())
    return out


def thrusts():
    import json
    d = json.load(open("docs/data.json"))
    ev = [e for e in d.get("events", []) if e.get("kind") == "thrust" and e.get("tier") == "major"]
    wo = {e["date"]: e for e in (d["themes"].get("washout") or {}).get("events", [])}
    return [(e["date"], bool(wo.get(e["date"], {}).get("deep"))) for e in ev]


def main():
    RULES = ["near10", "near15", "held", "rshi", "setup", "setup_grp", "beta30"]
    rows = []
    T = thrusts()
    tset = set()
    for dstr, deep in T:
        i = idx.get_indexer([pd.Timestamp(dstr)])[0]
        if i < 0:
            continue
        tset.update(range(i - 5, i + 26))
        names, S = sets(i)
        for r in RULES:
            out = outcome(i, names, S[r])
            if out:
                rows.append({"date": dstr, "deep": deep, "kind": "thrust", "rule": r, **out,
                             "names": ",".join(sorted(S[r], key=lambda t: -float(c[t].iloc[min(i + 63, N - 1)] / o[t].iloc[i + 1])))[:400]})
    for i in range(80, N - 21, 5):
        if i in tset:
            continue
        names, S = sets(i)
        for r in RULES:
            out = outcome(i, names, S[r])
            if out:
                rows.append({"date": idx[i].strftime("%Y-%m-%d"), "deep": False, "kind": "other", "rule": r, **out})
    D = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    th = D[D.kind == "thrust"]
    print("=== at each thrust: excess vs the average liquid stock (21 / 63 sessions), share at a new high within 15 ===")
    for dstr, deep in T:
        X = th[th.date == dstr].set_index("rule")
        if not len(X):
            continue
        so = float(spy_off.iloc[idx.get_indexer([pd.Timestamp(dstr)])[0]])
        print(f"\n{dstr} {'DEEP' if deep else 'shallow'} (SPY {so:+.1%} off its high)")
        print((X[["n", "x21", "x63", "w21", "brk15"]] * [1, 100, 100, 100, 100]).round(1).to_string())
    print("\n=== averages ===")
    g = D.groupby(["kind", "rule"]).agg(n=("n", "mean"), x21=("x21", "mean"), x63=("x63", "mean"), w21=("w21", "mean"), brk15=("brk15", "mean"), k=("x21", "size"))
    print((g * [1, 100, 100, 100, 100, 1]).round(1).to_string())
    dd = th[th.deep]
    print("\ndeep thrusts only:")
    print((dd.groupby("rule")[["x21", "x63", "w21", "brk15"]].mean() * 100).round(1).to_string())
    sh = th[~th.deep]
    print("\nshallow thrusts only:")
    print((sh.groupby("rule")[["x21", "x63", "w21", "brk15"]].mean() * 100).round(1).to_string())
    oth = D[D.kind == "other"]
    print("\nordinary days, halves (x21):")
    mid = sorted(oth.date.unique())[len(oth.date.unique()) // 2]
    print((oth.assign(half=np.where(oth.date < mid, "1st", "2nd")).groupby(["rule", "half"])["x21"].mean().unstack() * 100).round(2).to_string())
    for dstr, deep in T:
        X = th[(th.date == dstr) & (th.rule == "setup")]
        if len(X):
            print(dstr, "setup names (best 63d first):", X.iloc[0]["names"][:300])
    D.drop(columns=["names"], errors="ignore").to_csv("/tmp/turn_leaders_rows.csv", index=False)


def now():
    i = N - 1
    names, S = sets(i)
    print(f"as of {idx[i]:%Y-%m-%d}: SPY {float(spy_off.iloc[i]):+.1%} off its high")
    rk = rs_rank(i, names)
    rows = []
    for t in S["setup"]:
        rows.append({"t": t, "sub": sub_of.get(t, ""), "rs": round(float(rk[t])), "off": round(float(off.iloc[i][t]) * 100, 1),
                     "rs_off": round(float(rs_off.iloc[i][t]) * 100, 1), "r10_adr": round(float(r10.iloc[i][t]), 1),
                     "adr": round(float(adr.iloc[i][t]) * 100, 1), "dv": round(float(dv.iloc[i][t]) / 1e6), "grp": t in S["setup_grp"],
                     "d20": round(float(c[t].iloc[i] / c[t].iloc[i - 20] - 1) * 100, 1)})
    R = pd.DataFrame(rows).sort_values(["grp", "rs"], ascending=[False, False])
    print(R.to_string(index=False))
    R.to_csv("/tmp/turn_leaders_now.csv", index=False)
    print("\nsub-themes with 3+ setting up:", pd.Series([sub_of.get(t) for t in S["setup_grp"]]).value_counts().to_dict())


if __name__ == "__main__":
    now() if "--now" in sys.argv else main()
