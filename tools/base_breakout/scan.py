"""Big-base breakout scan (Nov 27, 2026; Adam's Unity weekly chart: multi-year box $20-49 since 2022, now pushing through the top).
Ceiling = highest close in the bar history (~2 years) EXCLUDING the last 20 sessions. Tested = 3+ distinct months whose high came
within 8% of the ceiling. Now = close within -8%..+15% of the ceiling, 150-day SMA rising (stage 2), $10+, $20M+/day.
Tag 'dead leader' when the Yahoo all-time high (data/levels.json) is 1.5x+ the close: a former leader basing for years, like Unity."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, ".")
from breadth import store
b = store.apply_splits(store.load_bars(), store.load_splits()); b["date"] = pd.to_datetime(b["date"]); b = b.drop_duplicates(["date", "ticker"])
lv = json.load(open("data/levels.json"))
try:
    import re
    s = open("docs/index.html").read(); D = json.loads(re.search(r'const DATA\s*=\s*(\{.*?\});\s*\n', s, re.S).group(1))
    meta = {x["t"]: x for x in D["themes"]["stocks"]}
except Exception: meta = {}
out = []
for t, g in b.groupby("ticker"):
    g = g.sort_values("date")
    if len(g) < 300: continue
    c, h, v = g.c.to_numpy(), g.h.to_numpy(), g.v.to_numpy()
    if c[-1] < 10 or np.mean(c[-20:] * v[-20:]) < 20e6: continue
    top = c[:-20].max(); lo = c[:-20].min()
    m = g.iloc[:-20].assign(mo=g.date.dt.to_period("M")).groupby("mo").h.max()
    touches = int((m >= top * 0.92).sum())
    pos = c[-1] / top - 1
    s150 = pd.Series(c).rolling(150).mean().to_numpy()
    if touches < 3 or not (-0.08 <= pos <= 0.15) or not (s150[-1] > s150[-21]): continue
    depth = top / lo  # how deep the box is
    ath = (lv.get(t) or {}).get("ath")
    mt = meta.get(t, {})
    out.append({"t": t, "price": round(c[-1], 2), "vs_top%": round(pos * 100, 1), "top": round(top, 2), "box_low": round(lo, 2), "depth_x": round(depth, 2),
                "touch_months": touches, "ath": ath, "dead_leader": bool(ath and ath >= 1.5 * c[-1]), "rs": mt.get("rsr"), "rs4w": mt.get("rs4w"),
                "sub": mt.get("sub"), "d60%": round((c[-1] / c[-61] - 1) * 100, 1), "vol_x": round(v[-5:].mean() / v[-50:].mean(), 2)})
df = pd.DataFrame(out).sort_values(["dead_leader", "rs"], ascending=[False, False])
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
print(f"{len(df)} names; data through {b.date.max().date()}")
print(df.to_string(index=False))
df.to_csv("tools/base_breakout/latest.csv", index=False)
