"""RS formula check (Nov 4, 2026; Adam: "the formula in my Trading Dashboard v12 sheet comes up with different stocks than our RS,
which is better?"). Sheet = price now ÷ first close on/after TODAY()-90 calendar days − 1 (≈ 62 sessions, one period, not ranked).
Dashboard RS Rating = 63/126/189/252-session returns weighted 40/20/20/20, percentile vs liquid stocks.

Each test date (every 5 sessions with 252 sessions behind it), liquid stocks ($5+, $20M+/day 50-day avg): pick the top 10% / top 20% by
each score; next 20 and 60 sessions return vs the average liquid stock (equal weight). Also short periods (21 / 42 sessions), a
blend, and the "both agree" overlap. Prints a table; run: PYTHONPATH=. python3 tools/rs_compare/study.py
"""
import numpy as np
import pandas as pd

from breadth import store, strength

bars = store.apply_splits(store.load_bars(), store.load_splits())
uni = set(store.load_universe())
bars = bars[bars["ticker"].isin(uni)]
W = strength.wide_all(bars)
c, v = W["c"], W["v"]
dv = (c * v).rolling(50, min_periods=30).mean()
liquid = (c >= 5) & (dv >= 20e6)
dates = c.index

raw_rs = strength.rs_raw(c)
need = c.notna() & c.shift(252).notna()
scores = {
    "dashboard RS (40/20/20/20)": raw_rs.where(need),
    "sheet: ~62-session % change": (c / c.shift(62) - 1).where(need),
    "63-session only": (c / c.shift(63) - 1).where(need),
    "42-session": (c / c.shift(42) - 1).where(need),
    "21-session": (c / c.shift(21) - 1).where(need),
    "blend 50/50 (RS pct + sheet pct)": None,
}
F20, F60 = c.shift(-20) / c - 1, c.shift(-60) / c - 1

rows = []
test = [i for i in range(252, len(dates) - 20) if (i - 252) % 5 == 0]
half = test[len(test) // 2]
for i in test:
    L = liquid.iloc[i] & need.iloc[i]
    names = L[L].index
    if len(names) < 200:
        continue
    ranks = {}
    for k, s in scores.items():
        if s is not None:
            ranks[k] = s.iloc[i][names].rank(pct=True)
    ranks["blend 50/50 (RS pct + sheet pct)"] = (ranks["dashboard RS (40/20/20/20)"] + ranks["sheet: ~62-session % change"]) / 2
    for hz, F in (("20", F20), ("60", F60)):
        if i + int(hz) >= len(dates):
            continue
        f = F.iloc[i][names].clip(-0.9, 3)
        base = f.mean()
        for k, r in ranks.items():
            for cut in (0.9, 0.8):
                sel = r[r >= cut].index
                rows.append({"i": i, "date": dates[i], "hz": hz, "score": k, "top": f"top {int(round((1 - cut) * 100))}%",
                             "ex": f[sel].mean() - base, "hit": (f[sel] > base).mean(), "n": len(sel)})
        # both agree vs only one
        a = set(ranks["dashboard RS (40/20/20/20)"][ranks["dashboard RS (40/20/20/20)"] >= 0.9].index)
        b = set(ranks["sheet: ~62-session % change"][ranks["sheet: ~62-session % change"] >= 0.9].index)
        for k, sel in (("top 10% on BOTH", a & b), ("dashboard RS only (not sheet)", a - b), ("sheet only (not dashboard RS)", b - a)):
            if sel:
                rows.append({"i": i, "date": dates[i], "hz": hz, "score": k, "top": "top 10%", "ex": f[list(sel)].mean() - base,
                             "hit": (f[list(sel)] > base).mean(), "n": len(sel)})
        if hz == "20":
            rows.append({"i": i, "date": dates[i], "hz": "ovl", "score": "overlap", "top": "top 10%", "ex": len(a & b) / max(len(a), 1), "hit": np.nan, "n": len(a)})

D = pd.DataFrame(rows)
D["half"] = np.where(D["i"] < half, "1st", "2nd")
print(f"test dates {D['date'].min():%Y-%m-%d} .. {D['date'].max():%Y-%m-%d}, every 5 sessions, split at {dates[half]:%Y-%m-%d}")
print("top-10% overlap, dashboard RS vs sheet:", round(D[D.hz == "ovl"]["ex"].mean() * 100), "% of names shared")
for hz in ("20", "60"):
    X = D[D.hz == hz]
    g = X.groupby(["top", "score"]).agg(ex=("ex", "mean"), sd=("ex", "std"), k=("ex", "size"), hit=("hit", "mean"), n=("n", "mean"))
    # overlapping windows: effective sample ≈ k × 5 / horizon
    g["t~"] = g["ex"] / (g["sd"] / np.sqrt(g["k"] * 5 / int(hz)))
    h = X.groupby(["top", "score", "half"])["ex"].mean().unstack()
    g = g.join(h)
    print(f"\n=== next {hz} sessions, excess vs the average liquid stock ===")
    print((g[["ex", "1st", "2nd", "hit", "t~", "n"]].assign(ex=lambda d: d.ex * 100, **{"1st": lambda d: d["1st"] * 100, "2nd": lambda d: d["2nd"] * 100, "hit": lambda d: d.hit * 100})).round(2).to_string())
D.to_csv("/tmp/rs_compare_rows.csv", index=False)
