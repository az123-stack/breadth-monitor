"""Supply-break SHORT (Adam Nov 7, 2026: "flag where price broke a big overhead supply pivot ... short it; entry = crossing back down below
the pivot line, stop above the local high"). Uses /tmp/supply_study/events.parquet from study.py.
Trigger within 21 sessions of the break: A = first close back below the level; B = first close 0.5 ADR below it.
Entry = next open (no look-ahead; also reported: at the trigger close). Stop = highest high from the break to the trigger day (+0.1 ADR),
risk floored at 0.3 ADR. Exit: stop, or close after 5 / 10 / 20 sessions. Reports win rate, average R, odds of reaching 1R / 2R before the stop.
Run from the repo root: python tools/supply_study/short.py
"""
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from breadth import store

E = pd.read_parquet("/tmp/supply_study/events.parquet")
b = store.apply_splits(store.load_bars(), store.load_splits()); b["date"] = pd.to_datetime(b["date"])
P = {k: b.pivot(index="date", columns="ticker", values=k).sort_index() for k in "ohlc"}
n = len(P["c"])
mid = E["date"].sort_values().iloc[len(E) // 2]
rows = []
for r in E.itertuples():
    o, h, l, c = (P[k][r.t].to_numpy() for k in "ohlc")
    a, L = r.adr, r.lvl
    for trig, line in (("A close under", L), ("B 0.5 ADR under", L * (1 - 0.5 * r.adr))):
        k = next((i for i in range(r.d + 1, min(n, r.d + 22)) if c[i] < line), None)
        if k is None:
            rows.append(dict(t=r.t, date=r.date, trig=trig, fired=False, g60=r.g60, thrust=r.thrust, rv=r.rv, kind=r.kind, gap=r.gap, ext=r.ext, rs=r.rs))
            continue
        hi = np.nanmax(h[r.d:k + 1]); stop = hi * (1 + 0.1 * a)
        for when, e_px, e0 in (("next open", o[k + 1] if k + 1 < n else np.nan, k + 1), ("trigger close", c[k], k + 1)):
            if np.isnan(e_px) or e0 >= n:
                continue
            risk = max(stop - e_px, 0.3 * a * e_px)
            st = e_px + risk
            out = {}; hit1 = hit2 = False; stopped = None
            for i in range(e0, min(n, e0 + 20)):
                if when == "next open" and i == e0 and o[i] >= st:
                    stopped = i; break
                lo_r = (e_px - l[i]) / risk
                if h[i] >= st:     # assume the stop hits before a same-day new low (conservative)
                    stopped = i; break
                hit1 |= lo_r >= 1; hit2 |= lo_r >= 2
                for m in (5, 10, 20):
                    if i - e0 + 1 == m:
                        out[m] = (e_px - c[i]) / risk
            for m in (5, 10, 20):
                if m not in out:
                    out[m] = -1.0 if stopped is not None and stopped - e0 < m else np.nan
            rows.append(dict(t=r.t, date=r.date, trig=trig, fired=True, when=when, days=k - r.d, risk_adr=risk / e_px / a,
                             R5=out[5], R10=out[10], R20=out[20], hit1=hit1, hit2=hit2, stopped=stopped is not None,
                             g60=r.g60, thrust=r.thrust, rv=r.rv, kind=r.kind, gap=r.gap, ext=r.ext, rs=r.rs))
S = pd.DataFrame(rows)
S.to_parquet("/tmp/supply_study/short.parquet")
tt = lambda x: round(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))), 1) if len(x) > 2 else np.nan
for trig in S.trig.unique():
    f = S[S.trig == trig]
    print(f"\n== {trig}: fired {f.fired.mean():.0%} of {len(f[f.when.isna() | (f.when == 'next open')])} breaks (within 21 sessions)")
    for when in ("next open", "trigger close"):
        g = f[f.fired & (f.when == when)]
        print(f"  entry {when}: n {len(g)}  win20 {(g.R20 > 0).mean():.0%}  R5 {g.R5.mean():+.2f}  R10 {g.R10.mean():+.2f}  R20 {g.R20.mean():+.2f} (t {tt(g.R20.dropna())})"
              f"  reach 1R {g.hit1.mean():.0%}  2R {g.hit2.mean():.0%}  stopped {g.stopped.mean():.0%}  risk {g.risk_adr.median():.1f} ADR  days to trigger {g.days.median():.0f}")
    g = f[f.fired & (f.when == "next open")]
    cuts = {"top-20% group": g.g60 >= 0.8, "group 50-80%": (g.g60 >= 0.5) & (g.g60 < 0.8), "bottom-half group": g.g60 < 0.5,
            "not in themes": g.g60.isna(), "thrust window": g.thrust, "no thrust": ~g.thrust,
            "break vol 3x+": g.rv >= 3, "break vol <1.5x": g.rv < 1.5, "gapped through": g.gap, "multi-year": g.kind == "multi",
            "broken floor": g.kind == "floor", "RS top 20%": g.rs >= 0.8, "RS bottom 40%": g.rs < 0.4,
            "trigger in 1-3 days": g.days <= 3, "trigger in 4-10": (g.days > 3) & (g.days <= 10), "trigger 11-21": g.days > 10,
            "no thrust & bottom-half grp": ~g.thrust & (g.g60 < 0.5), "no thrust & not in themes": ~g.thrust & g.g60.isna()}
    for k, m in cuts.items():
        x = g[m]; h1, h2 = x[x.date < mid], x[x.date >= mid]
        print(f"    {k:28} n {len(x):4}  win {(x.R20 > 0).mean():.0%}  R20 {x.R20.mean():+.2f} (t {tt(x.R20.dropna())})  halves {h1.R20.mean():+.2f} / {h2.R20.mean():+.2f}  1R {x.hit1.mean():.0%}")
