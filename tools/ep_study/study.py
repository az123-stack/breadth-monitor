"""Episodic pivots by market state, longs AND shorts (Nov 25, 2026; Adam: "I thought episodic pivots were the best to trade in bad markets,
longs or shorting after a couple days"). Card R-2026-11-25-ep-by-market.
EP day d: gap >= +8% (long) or <= -8% (short) from the prior close, volume >= 3x the 50-day average, $5+, $20M+ traded that day, not an ETF.
Entries (stop on the far side of the EP day's range, risk floored 0.3 ADR, capped 2 ADR):
  next_open        enter at the open of d+1
  break_d1_3       long: buy-stop over the EP-day high within d+1..d+3; short: sell-stop under the EP-day low
  after_2_days     wait 2 sessions; long if the EP-day low held, buy over the 2-day high in d+3..d+5;
                   short if the EP-day high held (failed bounce), sell under the 2-day low in d+3..d+5
Exits: 5 sessions at the close, or trail (first close through the 10 EMA, max 30). Market state = Today's playbook rule at the prior close.
"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from breadth import store, metrics
b = store.apply_splits(store.load_bars(), store.load_splits())
P = {k: b.pivot_table(index='date', columns='ticker', values=k).sort_index() for k in 'ohlcv'}
O, H, L, C, V = (P[k] for k in 'ohlcv'); dates = C.index
ETF = set(pd.read_csv('data/universe.csv').query('type != "CS"').ticker) if 'type' in pd.read_csv('data/universe.csv', nrows=1).columns else set()
h = store.load_breadth(); idx = pd.to_datetime(h.index); tw = metrics.thrust_window(h, h.index)
st = pd.Series(np.where(tw, 'thrust', np.where((h.ratio5 >= 1.5) & (h.ratio10 >= 1.5), 'strong', np.where(h.ratio10 < 1, 'weak', 'mixed'))), index=idx).shift(1)
v50 = V.rolling(50, min_periods=30).mean().shift(1)
adr = ((H - L) / C).rolling(20, min_periods=10).mean().shift(1) * C.shift(1)
gap = O / C.shift(1) - 1
ep = (V >= 3 * v50) & (C.shift(1) >= 5) & (C * V >= 20e6)
rows = []
def run(t, side, i0, entry, stop, a, o, hh, ll, c, e10):
    risk = abs(entry - stop); risk = min(max(risk, 0.3 * a), 2 * a); stop = entry - risk if side == 1 else entry + risk
    out = {}
    for mode in ('d5', 'trail'):
        ex = None
        for k in range(i0, min(i0 + (5 if mode == 'd5' else 30), len(c))):
            if k > i0 and ((side == 1 and o[k] <= stop) or (side == -1 and o[k] >= stop)): ex = o[k]; break
            if (side == 1 and ll[k] <= stop) or (side == -1 and hh[k] >= stop): ex = stop; break
            if mode == 'd5' and k == i0 + 4: ex = c[k]; break
            if mode == 'trail' and k > i0 and ((side == 1 and c[k] < e10[k]) or (side == -1 and c[k] > e10[k])): ex = c[k]; break
        if ex is None: ex = c[min(i0 + (4 if mode == 'd5' else 29), len(c) - 1)]
        out[mode] = side * (ex - entry) / risk
    return out
for t in C.columns:
    if t in ETF or t == 'SPY': continue
    g, e = gap[t].to_numpy(), ep[t].to_numpy()
    cand = np.where(e & ((g >= 0.08) & (g <= 0.6) | (g <= -0.08) & (g >= -0.6)))[0]
    if not len(cand): continue
    o, hh, ll, c, a = O[t].to_numpy(), H[t].to_numpy(), L[t].to_numpy(), C[t].to_numpy(), adr[t].to_numpy()
    e10 = pd.Series(c).ewm(span=10, adjust=False).mean().to_numpy()
    for d in cand:
        if d + 8 >= len(c) or not np.isfinite(a[d]) or a[d] <= 0: continue
        side = 1 if g[d] > 0 else -1
        rng = hh[d] - ll[d]
        base = dict(t=t, date=dates[d], side='long' if side == 1 else 'short', state=st.get(dates[d]),
                    clv=(c[d] - ll[d]) / rng if rng > 0 else 0.5, px=c[d], dv50=(v50[t].iloc[d] or 0) * c[d - 1],
                    r60=c[d - 1] / c[d - 61] - 1 if d > 61 else np.nan, gapsz=abs(g[d]))
        rows.append({**base, 'entry': 'next_open', **run(t, side, d + 1, o[d + 1], ll[d] if side == 1 else hh[d], a[d], o, hh, ll, c, e10)})
        lvl = hh[d] if side == 1 else ll[d]
        for k in range(d + 1, d + 4):
            if (side == 1 and hh[k] > lvl) or (side == -1 and ll[k] < lvl):
                en = max(o[k], lvl) if side == 1 else min(o[k], lvl)
                rows.append({**base, 'entry': 'break_d1_3', **run(t, side, k, en, ll[d] if side == 1 else hh[d], a[d], o, hh, ll, c, e10)}); break
        held = (ll[d + 1:d + 3].min() > ll[d]) if side == 1 else (hh[d + 1:d + 3].max() < hh[d])
        if held:
            lvl2 = hh[d + 1:d + 3].max() if side == 1 else ll[d + 1:d + 3].min()
            stop2 = ll[d + 1:d + 3].min() if side == 1 else hh[d + 1:d + 3].max()
            for k in range(d + 3, d + 6):
                if (side == 1 and hh[k] > lvl2) or (side == -1 and ll[k] < lvl2):
                    en = max(o[k], lvl2) if side == 1 else min(o[k], lvl2)
                    rows.append({**base, 'entry': 'after_2_days', **run(t, side, k, en, stop2, a[d], o, hh, ll, c, e10)}); break
df = pd.DataFrame(rows).dropna(subset=['state'])
df['half'] = np.where(df.date < df.date.median(), 1, 2)
def tt(x, col):
    m = x.groupby('date')[col].mean(); return m.mean() / (m.std() / np.sqrt(len(m))) if len(m) > 2 else np.nan
pd.set_option('display.width', 250)
out = df.groupby(['side', 'entry', 'state']).apply(lambda x: pd.Series({'n': len(x), 'R5': x.d5.mean(), 't5': tt(x, 'd5'), 'win5': (x.d5 > 0).mean(),
      'Rtrail': x.trail.mean(), 'h1_5': x[x.half == 1].d5.mean(), 'h2_5': x[x.half == 2].d5.mean()})).round(2)
print(df.date.min().date(), df.date.max().date(), len(df)); print(out.to_string())
df.to_csv('/tmp/ep_trades.csv', index=False)
