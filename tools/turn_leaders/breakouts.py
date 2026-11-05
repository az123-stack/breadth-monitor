"""Part 2: do fresh 52-week-high breakouts right after a turning point (the DELL / HPE "broke out together" moment) beat breakouts
at other times, and does breaking out with group peers matter?

Fresh breakout = close above the highest high of up to 252 prior sessions (min 60) with no such close in the prior 20 sessions; liquid
($5+, $20M+/day). Post-thrust = within 1–15 sessions after a major thrust (signal close → buy next open). Together = 2+ other members of
the same sub-theme also broke out fresh within the 5 sessions up to that day. Outcome = next open → close 21 / 63 sessions later minus the
average liquid stock over the same window. Halves split at the median event date.
Run: PYTHONPATH=. python3 tools/turn_leaders/breakouts.py [--now]
"""
import json
import sys

import numpy as np
import pandas as pd

from breadth import store, strength

bars = store.apply_splits(store.load_bars(), store.load_splits())
W = strength.wide_all(bars)
c, h, o, v = W["c"], W["h"], W["o"], W["v"]
dv = (c * v).rolling(50, min_periods=30).mean()
liquid = (c >= 5) & (dv >= 20e6) & (c.notna().cumsum() >= 60)
prior_hi = h.shift(1).rolling(252, min_periods=60).max()
brk = (c > prior_hi) & liquid
fresh = brk & ~brk.shift(1).rolling(20, min_periods=1).max().fillna(0).astype(bool)
raw = strength.rs_raw(c)
sub = store.load_subthemes()
sub_of = dict(zip(sub["ticker"], sub["subtheme"]))
idx = c.index
N = len(idx)
d = json.load(open("docs/data.json"))
wo = {e["date"]: e for e in (d["themes"].get("washout") or {}).get("events", [])}
TH = [(idx.get_indexer([pd.Timestamp(e["date"])])[0], bool(wo.get(e["date"], {}).get("deep")), e["date"])
      for e in d.get("events", []) if e.get("kind") == "thrust" and e.get("tier") == "major"]


def ctx(i):
    for ti, deep, ds in TH:
        if 1 <= i - ti <= 15:
            return ("post_deep" if deep else "post_shallow"), ds, i - ti
    return "other", None, None


# group peers breaking out within the last 5 sessions
F = fresh.astype(int)
recent5 = F.rolling(5, min_periods=1).sum() > 0
grp_cols = {}
for t in c.columns:
    g = sub_of.get(t)
    if g:
        grp_cols.setdefault(g, []).append(t)


def main():
    rows = []
    mean_fwd = {}
    for i in range(80, N - 21):
        L = liquid.iloc[i]
        names = L[L].index
        tick = fresh.iloc[i]
        hits = tick[tick].index
        if not len(hits):
            continue
        e = o.iloc[i + 1] if i + 1 < N else None
        base = {}
        for k in (21, 63):
            j = i + k
            if j < N:
                f = (c.iloc[j][names] / e[names] - 1).clip(-0.9, 5)
                base[k] = (f, f.mean())
        kind, ds, ago = ctx(i)
        rk = raw.iloc[i][names].rank(pct=True) * 99
        for t in hits:
            if t not in names:
                continue
            g = sub_of.get(t)
            peers = sum(1 for x in grp_cols.get(g, []) if x != t and bool(recent5.iloc[i].get(x, False))) if g else 0
            r = {"date": idx[i], "t": t, "kind": kind, "thrust": ds, "ago": ago, "peers": peers, "rs": float(rk.get(t, np.nan)),
                 "together": peers >= 2}
            for k, (f, m) in base.items():
                r[f"x{k}"] = float(f.get(t, np.nan) - m)
            rows.append(r)
    D = pd.DataFrame(rows)
    D["half"] = np.where(D["date"] < D["date"].quantile(0.5), "1st", "2nd")
    pd.set_option("display.width", 200)
    def tab(X, by):
        g = X.groupby(by).agg(n=("x21", "size"), x21=("x21", "mean"), x63=("x63", "mean"), win21=("x21", lambda s: (s > 0).mean()))
        g["t21"] = X.groupby(by)["x21"].apply(lambda s: s.mean() / (s.std() / np.sqrt(len(s))) if len(s) > 2 else np.nan)
        return g.assign(x21=g.x21 * 100, x63=g.x63 * 100, win21=g.win21 * 100).round(2)
    print(f"{len(D)} fresh breakouts, {D.date.min():%Y-%m-%d} .. {D.date.max():%Y-%m-%d}")
    print("\n== by context ==\n", tab(D, "kind").to_string())
    print("\n== by context × together (2+ group peers broke out in 5 sessions) ==\n", tab(D, ["kind", "together"]).to_string())
    print("\n== RS 80+ only ==\n", tab(D[D.rs >= 80], ["kind", "together"]).to_string())
    print("\n== halves (all contexts) ==\n", tab(D, ["kind", "half"]).to_string())
    P = D[D.kind != "other"]
    print("\n== per thrust ==\n", tab(P, ["thrust", "together"]).to_string())
    print("\n== days after the thrust ==\n", tab(P.assign(w=pd.cut(P.ago, [0, 5, 10, 15])), "w").to_string())
    for ds in sorted(P.thrust.unique()):
        X = P[(P.thrust == ds) & P.together].sort_values("x63", ascending=False)
        print(ds, "together breakouts, best 63d:", ", ".join(f"{r.t}({r.x63*100:+.0f})" for r in X.head(12).itertuples()))
    D.to_csv("/tmp/turn_breakouts.csv", index=False)


def now(days=15):
    i = N - 1
    out = []
    for k in range(days):
        j = i - k
        tick = fresh.iloc[j]
        for t in tick[tick].index:
            g = sub_of.get(t)
            peers = [x for x in grp_cols.get(g, []) if x != t and bool(recent5.iloc[j].get(x, False))] if g else []
            out.append({"date": f"{idx[j]:%m-%d}", "t": t, "sub": g or "", "peers": len(peers), "with": ",".join(peers[:6]),
                        "since%": round(float(c[t].iloc[i] / c[t].iloc[j] - 1) * 100, 1),
                        "vs_hi%": round(float(c[t].iloc[i] / h[t].iloc[:i + 1].tail(252).max() - 1) * 100, 1)})
    R = pd.DataFrame(out).drop_duplicates("t")
    print(R.sort_values(["peers", "date"], ascending=[False, False]).to_string(index=False))
    R.to_csv("/tmp/turn_breakouts_now.csv", index=False)


if __name__ == "__main__":
    now() if "--now" in sys.argv else main()
