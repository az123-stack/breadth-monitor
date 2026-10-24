"""Dip-buy check (Oct 24, 2026): uptrend liquid stocks, RS 70+. Same-day wick under the 9 / 21 EMA and close back above,
vs closed under, vs any uptrend day. Entry next open, exit close N sessions later, minus SPY. t on date averages, halves."""
import sys, os
sys.path.insert(0, "/home/claude/breadth-monitor"); os.chdir("/home/claude/breadth-monitor")
import numpy as np, pandas as pd
from breadth import store, strength, config, stairs
b = store.apply_splits(store.load_bars(), store.load_splits())
uni = set(pd.read_csv("data/universe.csv").iloc[:, 0])
w = strength.wide_all(b); cols = [t for t in w["c"].columns if t in uni or t == config.BENCHMARK]
c, h, l, o, v = (w[k][cols] for k in ("c", "h", "l", "o", "v"))
S = stairs.frames(c, h, l, v)
e9, e21 = S["e9"], S["e21"]
raw = strength.rs_raw(c); rs = (raw.where(S["liq"]).rank(axis=1, pct=True) * 99)
base = S["up"] & S["liq"] & (rs >= 70)
spy = config.BENCHMARK
res = {}
for N in (5, 10):
    fwd = c.shift(-N) / o.shift(-1) - 1
    fwd = fwd.sub(fwd[spy], axis=0).clip(-0.5, 0.5)
    ev = {"any uptrend day": base,
          "wick 9, close >= 9": base & (l < e9) & (c >= e9),
          "wick 21, close >= 21": base & (l < e21) & (c >= e21),
          "close < 9 (>= 21)": base & (c < e9) & (c >= e21),
          "close < 21": base & (c < e21),
          "reclaim 21 (under in prior 3)": base & (c >= e21) & (c.shift(1) < e21.shift(1)).rolling(3).max().astype(bool),
          "reclaim 9 (under in prior 3)": base & (c >= e9) & (c.shift(1) < e9.shift(1)).rolling(3).max().astype(bool)}
    dates = c.index[260:-N - 1]; half = dates[len(dates) // 2]
    for k, m in ev.items():
        x = fwd.where(m).loc[dates]
        per = x.mean(axis=1).dropna()
        allv = fwd.where(base).loc[dates].mean(axis=1).reindex(per.index)
        ed = per - allv
        t = ed.mean() / (ed.std() / np.sqrt(len(ed))) if k != "any uptrend day" else np.nan
        h1, h2 = ed[ed.index < half].mean(), ed[ed.index >= half].mean()
        print(f"{N:>2}d {k:32s} n {int(x.count().sum()):6d} avg vs SPY {per.mean()*100:+.2f}%  edge vs uptrend {ed.mean()*100:+.2f} t {t:+.1f}  halves {h1*100:+.2f}/{h2*100:+.2f}")

# R view: the wick gives a nearby stop. Entry next open, stop = signal-day low (wick) or 1 ADR under entry (any day),
# risk floored 0.3 ADR, exit at stop or close 10 sessions later. Vectorised per signal (sampled loop).
A = S["A"]
O, H, L, C = o.to_numpy(), h.to_numpy(), l.to_numpy(), c.to_numpy(); AA = A.to_numpy()
def rtest(mask, stopkind, N=10):
    M = mask.to_numpy(); out = []; di = []
    ii, jj = np.nonzero(M[260:-N - 1]); ii += 260
    rng = np.random.default_rng(0)
    if len(ii) > 30000:
        k = rng.choice(len(ii), 30000, replace=False); ii, jj = ii[k], jj[k]
    for i, j in zip(ii, jj):
        e = O[i + 1, j]; a = AA[i, j]
        if not (e > 0 and a > 0):
            continue
        st = L[i, j] if stopkind == "low" else e - a
        if st >= e:                       # gapped below the stop: skip
            continue
        risk = max(e - st, 0.3 * a)
        lows = L[i + 1:i + 1 + N, j]; hit = np.nonzero(lows <= st)[0]
        px = st if len(hit) else C[i + N, j]
        out.append((px - e) / risk); di.append(i)
    r = pd.Series(out, index=di); g = r.groupby(level=0).mean()
    half = len(c.index) // 2 + 130
    return len(r), r.mean(), g.mean() / (g.std() / np.sqrt(len(g))), r[r.index < half].mean(), r[r.index >= half].mean(), (r > 0).mean()
print("\nR (entry next open, exit 10 sessions or stop):")
for k, m, sk in (("any uptrend day, stop 1 ADR", base, "adr"),
                 ("wick 9 & back, stop wick low", base & (l < e9) & (c >= e9), "low"),
                 ("wick 21 & back, stop wick low", base & (l < e21) & (c >= e21), "low"),
                 ("wick 21 & back, stop 1 ADR", base & (l < e21) & (c >= e21), "adr"),
                 ("any uptrend day, stop day low", base, "low")):
    n, mr, t, h1, h2, win = rtest(m, sk)
    print(f"  {k:32s} n {n:6d} avg {mr:+.3f}R t {t:+.1f} halves {h1:+.3f}/{h2:+.3f} win {win*100:.0f}%")
