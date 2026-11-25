"""RS fire -> pullback to the EMAs (Nov 24, 2026; Adam: "when the x-timeframe RS fires one or a couple times and then pulls back to the
EMAs, buy the touch or the undercut and rally"). Card R-2026-11-24-rs-fire-pullback.

RS fire (period X = 20 / 63 / 126 / 252 sessions): the stock's RS line (close / SPY close) makes a new X-session high.
Setup on day t: 1-3 fire days ("once or a couple times") in the 20 sessions before t (none in the last 2), close above the 50 EMA at the
last fire, first EMA contact since that fire. Stocks $10+, $20M+/day 50-day avg, no ETFs.
Entries:
  touch21 / touch9 : low reaches yesterday's 21 / 9 EMA -> buy at the EMA (or the open if it opens below), stop 1 ADR under the entry
  undercut         : low goes 0.3+ ADR under the 21 EMA, then within 3 sessions a close back above the 21 EMA and above the prior high
                     -> buy next open, stop = lowest low since the undercut (risk floored 0.3 ADR, capped 2 ADR)
Exits: (a) 5 sessions at the close; (b) trail: first close under the 10 EMA, max 30 sessions. Stop checked each day (gap -> open).
Baseline: the same entries on stocks with NO RS fire (63-session) in the last 60 sessions but above the 50 EMA.
Stats per entry type: n, mean R, win %, t on per-date means, halves; leading groups = sub-theme top 30% by 60-day median return.
"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from breadth import store
b = store.apply_splits(store.load_bars(), store.load_splits())
P = {k: b.pivot_table(index='date', columns='ticker', values=k).sort_index() for k in 'ohlcv'}
C = P['c']; dates = C.index
spy = C['SPY'].to_numpy()
dv = (C * P['v']).rolling(50, min_periods=30).mean()
ETF = {'SPY','QQQ','IWM','RSP','DIA','SOXX','SMH','QQQE','TQQQ','SQQQ','SPXL','SOXL','TLT','GLD','SLV','USO','UNG','XLE','XLK','XLF','XLV','XLU','XLP','XLI','XLB','XLY','XLC','XLRE','KRE','XBI','IBB','ARKK','EEM','EFA','FXI','KWEB','IBIT','BITO','HYG','LQD','UUP'}
sub = store.load_subthemes().drop_duplicates('ticker').set_index('ticker')['subtheme']
r60 = C / C.shift(60) - 1
ok_t = [t for t in C.columns if t not in ETF and (dv[t] >= 20e6).sum() > 100]
# leading groups by date
lead = {}
for i in range(60, len(dates)):
    g = r60.iloc[i][ok_t].groupby(sub.reindex(ok_t)).median().dropna()
    lead[i] = set(g[g >= g.quantile(.7)].index)
ema = lambda a, n: pd.Series(a).ewm(span=n, adjust=False, min_periods=n).mean().to_numpy()

def trade(o, h, l, c, e10, i0, entry, stop, adr):
    risk = max(entry - stop, 0.3 * adr); risk = min(risk, 2 * adr); stop = entry - risk
    res = {}
    for mode in ('d5', 'trail'):
        ex = None
        for k in range(i0, min(i0 + (5 if mode == 'd5' else 30), len(c))):
            if k > i0 and o[k] <= stop: ex = o[k]; break
            if l[k] <= stop: ex = stop; break
            if mode == 'd5' and k == i0 + 4: ex = c[k]; break
            if mode == 'trail' and k > i0 and c[k] < e10[k]: ex = c[k]; break
        if ex is None: ex = c[min(i0 + (4 if mode == 'd5' else 29), len(c) - 1)]
        res[mode] = (ex - entry) / risk
    return res

rows = []
for t in ok_t:
    o, h, l, c = (P[k][t].to_numpy() for k in 'ohlc')
    if np.isnan(c).mean() > 0.5: continue
    liq = (dv[t].to_numpy() >= 20e6) & (c >= 10)
    rs = c / spy
    e9, e10, e21, e50 = ema(c, 9), ema(c, 10), ema(c, 21), ema(c, 50)
    adr = pd.Series((h - l) / c).rolling(20, min_periods=10).mean().to_numpy() * c
    fires = {X: np.r_[np.zeros(X), [rs[i] >= np.nanmax(rs[i - X + 1:i + 1]) for i in range(X, len(c))]].astype(bool) for X in (20, 63, 126, 252)}
    f63_60 = pd.Series(fires[63]).rolling(60, min_periods=1).sum().to_numpy()
    used = {}
    for i in range(60, len(c) - 6):
        if not liq[i] or np.isnan(e21[i - 1]) or np.isnan(adr[i]): continue
        for X, f in fires.items():
            win = f[i - 20:i]
            n = int(win.sum())
            nofire_base = X == 63 and f63_60[i - 1] == 0 and c[i - 1] > e50[i - 1]
            if not ((1 <= n and not f[i - 2:i].any()) or nofire_base): continue
            grp = 'base' if (nofire_base and n == 0) else ('1-3' if n <= 3 else '4+')
            if grp != 'base':
                lf = i - 20 + int(np.where(win)[0][-1])
                if c[lf] < e50[lf] or (l[lf + 1:i] <= e21[lf:i - 1]).any(): continue   # first 21 EMA contact since the last fire
            key = (X if grp != 'base' else 'base', grp)
            if used.get(key, -99) > i - 10: continue
            ld = sub.get(t) in lead.get(i, ())
            base = dict(t=t, date=dates[i], X=X if grp != 'base' else 'none', fires=grp, lead=ld)
            hit = False
            for nm, e in (('touch21', e21[i - 1]), ('touch9', e9[i - 1])):
                if l[i] <= e and h[i] >= e * 0.97:
                    entry = min(o[i], e) if o[i] > 0 else e
                    r = trade(o, h, l, c, e10, i, entry, entry - adr[i], adr[i]); rows.append({**base, 'entry': nm, **r}); hit = True
            if l[i] <= e21[i - 1] - 0.3 * adr[i]:
                for j in range(i, min(i + 3, len(c) - 7)):
                    if c[j] > e21[j] and c[j] > h[j - 1]:
                        r = trade(o, h, l, c, e10, j + 1, o[j + 1], np.nanmin(l[i:j + 1]), adr[i]); rows.append({**base, 'entry': 'undercut', **r}); hit = True; break
            if hit: used[key] = i
d = pd.DataFrame(rows)
d['half'] = np.where(d.date < d.date.median(), 1, 2)
def tstat(x):
    m = x.groupby(d.loc[x.index, 'date']).mean()
    return m.mean() / (m.std() / np.sqrt(len(m))) if len(m) > 2 else np.nan
def summ(g):
    return pd.Series({'n': len(g), 'R5': g.d5.mean(), 't5': tstat(g.d5), 'win5%': 100 * (g.d5 > 0).mean(), 'Rtrail': g.trail.mean(), 'ttrail': tstat(g.trail),
                      'h1': g[g.half == 1].trail.mean(), 'h2': g[g.half == 2].trail.mean()})
pd.set_option('display.width', 250)
print(d.date.min().date(), d.date.max().date(), len(d))
print(d.groupby(['entry', 'X', 'fires']).apply(summ).round(2).to_string())
print('\nleading groups only:')
print(d[d.lead].groupby(['entry', 'X', 'fires']).apply(summ).round(2).to_string())
d.to_csv('tools/rs_fire_pullback/trades.csv', index=False)
