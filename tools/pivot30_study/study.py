"""15-min and 30-min pivot entries vs daily entries on the same pullback setups (Nov 26, 2026; Adam, @1ChartMaster: "a shakeout into a
30-min pivot on tight risk right before a stock goes on an insane run"). Card R-2026-11-26-intraday-pivot.

Data: 15-minute regular-session bars, branch orb-data (~700 liquid sub-theme stocks A-PBR, Oct 2024 - Oct 2026); 30-min bars = pairs.
Daily context from the main bars (splits applied): stock $10+, $20M+/day, prior close > 50 EMA, 21 EMA > 50 EMA, top 30% on 63-day
return (liquid set) at the prior close. Flags: leading group (sub-theme top 30% on 60d median), RS fire (RS line new 63-day high 1-3x in
the prior 20 sessions), breadth state at the prior close.
Setup day i: the day's low undercuts the level. Levels: 'pdl' = prior day's low; 'e21' = prior day's 21 EMA (both from daily bars).
Entries (all on the same setup days):
  D_touch : buy at the level (open if it opens below), stop 1 ADR under entry                   (the current daily-touch style)
  D_close : buy at the day's close if it closed back above the level, stop = day low (risk floor 0.3 ADR)
  P15/P30 : after the undercut, the first 15/30-min bar that CLOSES back above the level = pivot bar; buy the break of its high in a later
            bar the same day (fill = max(bar open, pivot high)); stop = day's low so far (floor 0.1 ADR). No trigger -> no trade.
Exits: (5d) close of day i+4; (trail) first daily close under the 10 EMA, max 30 sessions. Same-day stop checked on bars after entry.
One setup per ticker per level per 5 sessions. Reported: trigger rate, R/trade, win %, R per setup day (misses count 0), % return/trade,
and "equal risk" = R x (risk / 1 ADR) compare via R per setup day. Date = unit for t; halves at the median date.
"""
import sys, glob, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from breadth import store, metrics

IN = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/orbdata'
b = store.apply_splits(store.load_bars(), store.load_splits())
P = {k: b.pivot_table(index='date', columns='ticker', values=k).sort_index() for k in 'ohlcv'}
C, H, L, O, V = P['c'], P['h'], P['l'], P['o'], P['v']
dates = C.index; N = len(dates); di = {d: i for i, d in enumerate(dates)}
spy = C['SPY']
dv = (C * V).rolling(50, min_periods=30).mean()
ETF = {'SPY', 'QQQ', 'IWM', 'SMH', 'SOXX', 'TQQQ', 'SOXL', 'GLD', 'SLV', 'IBIT', 'TLT', 'XLE', 'XLK', 'XLF', 'ARKK', 'KRE', 'XBI'}
liq = (dv >= 20e6) & (C >= 10); liq.loc[:, [t for t in C.columns if t in ETF]] = False
E10 = C.ewm(span=10, adjust=False, min_periods=10).mean(); E21 = C.ewm(span=21, adjust=False, min_periods=21).mean()
E50 = C.ewm(span=50, adjust=False, min_periods=50).mean()
ADR = ((H - L) / C).rolling(20, min_periods=10).mean() * C
r63 = C / C.shift(63) - 1
top30 = r63.where(liq).rank(axis=1, pct=True) >= 0.7
RS = C.div(spy, axis=0); fire = RS >= RS.rolling(63, min_periods=63).max() * 0.999
fires20 = fire.astype(float).rolling(20).sum()
sub = store.load_subthemes().drop_duplicates('ticker').set_index('ticker')['subtheme']
r60 = C / C.shift(60) - 1
lead = {}
for i in range(60, N):
    m = liq.iloc[i].to_numpy()
    g = r60.iloc[i][m].groupby(sub.reindex(r60.columns[m]).to_numpy()).median().dropna()
    lead[i] = set(g[g >= g.quantile(.7)].index)
hist = pd.read_csv('data/breadth.csv', parse_dates=['date']).set_index('date').reindex(dates)
tw = metrics.thrust_window(hist, dates)
state = pd.Series(np.where(tw, 'thrust', np.where((hist.ratio5 >= 1.5) & (hist.ratio10 >= 1.5), 'strong',
                  np.where(hist.ratio10 < 1, 'weak', 'mixed'))), index=dates)

intr = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(IN + '/part_*.parquet'))])
intr = intr[intr.m < 390]
last_intr = intr.date.max()

def daily_after(t, i, entry, stop, mode):
    """Walk daily bars from i+1 (day i handled intraday). Returns exit price."""
    o, l, c, e10 = O[t].to_numpy(), L[t].to_numpy(), C[t].to_numpy(), E10[t].to_numpy()
    end = i + (4 if mode == '5d' else 29)
    if mode == 'trail' and c[i] < e10[i]: return c[i]
    for k in range(i + 1, min(end + 1, N)):
        if o[k] <= stop: return o[k]
        if l[k] <= stop: return stop
        if mode == 'trail' and c[k] < e10[k]: return c[k]
    return c[min(end, N - 1)]

def run(entry, stop, adr, t, i, bars_after=None):
    """bars_after: intraday (h,l,c) arrays after the entry bar on day i; None = daily entry at/after the close."""
    risk = entry - stop
    if risk <= 0: return None
    out = {'risk_adr': risk / adr, 'entry': entry}
    stopped_today = False
    if bars_after is not None:
        lo = bars_after
        if len(lo) and np.nanmin(lo) <= stop: stopped_today = True
    for mode in ('5d', 'trail'):
        ex = stop if stopped_today else daily_after(t, i, entry, stop, mode)
        out['R_' + mode] = (ex - entry) / risk
        out['pct_' + mode] = ex / entry - 1
    return out

rows = []
for t, g in intr.groupby('ticker'):
    if t not in C.columns or t in ETF: continue
    g = g.sort_values(['date', 'm'])
    byday = {d: x for d, x in g.groupby('date')}
    lq, e21, e50, adr = liq[t].to_numpy(), E21[t].to_numpy(), E50[t].to_numpy(), ADR[t].to_numpy()
    c, l, o, h = C[t].to_numpy(), L[t].to_numpy(), O[t].to_numpy(), H[t].to_numpy()
    tp, fr = top30[t].to_numpy(), fires20[t].to_numpy()
    last = {'pdl': -99, 'e21': -99}
    for i in range(70, N - 5):
        d = dates[i]
        if d > last_intr: break
        p = i - 1
        if not (lq[p] and c[p] > e50[p] and e21[p] > e50[p] and tp[p]) or np.isnan(adr[p]): continue
        x = byday.get(d)
        if x is None or len(x) < 20: continue
        A = adr[p]
        for lv_name, lvl in (('pdl', l[p]), ('e21', e21[p])):
            if i - last[lv_name] < 5 or not (l[i] < lvl) or o[i] < lvl - 2 * A: continue
            last[lv_name] = i
            base = dict(t=t, date=d, level=lv_name, state=state.iloc[p], lead=sub.get(t) in lead.get(p, ()),
                        rsfire=1 <= fr[p] <= 3, gap_below=o[i] < lvl)
            # D_touch
            en = min(o[i], lvl); r = run(en, en - A, A, t, i, bars_after=np.array([l[i]]) if True else None)
            # same-day stop for D_touch: if the day's low reached entry - 1 ADR after entry (approx: day low)
            rows.append({**base, 'entry_type': 'D_touch', 'trig': True, **(r or {})})
            # D_close
            if c[i] > lvl:
                st = min(l[i], c[i] - 0.3 * A); r = run(c[i], st, A, t, i, None)
                rows.append({**base, 'entry_type': 'D_close', 'trig': r is not None, **(r or {})})
            else:
                rows.append({**base, 'entry_type': 'D_close', 'trig': False})
            # intraday pivots
            bh, bl, bc, bo = (x[k].to_numpy() for k in 'hlco')
            for size in (15, 30):
                if size == 30:
                    n2 = len(bh) // 2
                    hh = np.maximum(bh[0:2 * n2:2], bh[1:2 * n2:2]); ll = np.minimum(bl[0:2 * n2:2], bl[1:2 * n2:2])
                    cc = bc[1:2 * n2:2]; oo = bo[0:2 * n2:2]
                else:
                    hh, ll, cc, oo = bh, bl, bc, bo
                res = None; undercut = False; piv = None; lowsofar = np.inf
                for k in range(len(hh)):
                    if piv is not None and hh[k] > piv:
                        en = max(oo[k], piv); st = min(lowsofar, en - 0.1 * A)
                        # entry bar: stopped if it closes under the stop
                        after = ll[k + 1:]
                        if cc[k] <= st: after = np.array([st])
                        res = run(en, st, A, t, i, bars_after=after); res = res and {**res, 'bar': k}
                        # hybrid: same pivot entry, but the daily-style 1 ADR stop (pivot as confirmation, not as a tight stop)
                        hres = run(en, en - A, A, t, i, bars_after=ll[k + 1:] if cc[k] > en - A else np.array([en - A]))
                        rows.append({**base, 'entry_type': f'H{size}', 'trig': hres is not None, **(hres or {}), 'bar': k}); break
                    lowsofar = min(lowsofar, ll[k])
                    if ll[k] < lvl: undercut = True
                    if undercut and piv is None and cc[k] > lvl: piv = hh[k]
                    elif piv is not None and cc[k] < lvl: piv = None   # lost the level again: wait for a new reclaim bar
                rows.append({**base, 'entry_type': f'P{size}', 'trig': res is not None, **(res or {})})
                if res is None: rows.append({**base, 'entry_type': f'H{size}', 'trig': False})

d = pd.DataFrame(rows)
d['half'] = np.where(d.date < d.date.median(), 1, 2)
d.to_csv('tools/pivot30_study/trades.csv', index=False)

def tdate(s, dts):
    m = s.groupby(dts).mean().dropna()
    return m.mean() / (m.std() / np.sqrt(len(m))) if len(m) > 2 and m.std() > 0 else np.nan

def summ(g):
    tr = g[g.trig]
    out = {'setups': len(g), 'trig%': 100 * g.trig.mean(), 'risk_adr': tr.risk_adr.median(),
           'R5': tr.R_5d.mean(), 'win5%': 100 * (tr.R_5d > 0).mean(), 'Rtrail': tr.R_trail.mean(), 'win_tr%': 100 * (tr.R_trail > 0).mean(),
           't_trail': tdate(tr.R_trail, tr.date), 'pct_trail': 100 * tr.pct_trail.mean()}
    # R per setup day (misses = 0), and equal-risk R scaled to a 1-ADR stop doesn't change R; R per setup measures the miss cost
    per = g.R_trail.where(g.trig, 0.0)
    out['R/setup'] = per.mean(); out['h1'] = per[g.half == 1].mean(); out['h2'] = per[g.half == 2].mean()
    return pd.Series(out)

pd.set_option('display.width', 250)
print('setup-level rows', len(d) // 6, '| dates', d.date.min().date(), d.date.max().date(), '| tickers', d.t.nunique())
order = ['D_touch', 'D_close', 'P30', 'P15', 'H30', 'H15']
for lv in ('pdl', 'e21'):
    s = d[d.level == lv]
    print(f'\n===== level {lv}: all setups')
    print(s.groupby('entry_type').apply(summ).reindex(order).round(2).to_string())
    print(f'-- leading group')
    print(s[s.lead].groupby('entry_type').apply(summ).reindex(order).round(2).to_string())
    print(f'-- leading group + RS fire 1-3')
    print(s[s.lead & s.rsfire].groupby('entry_type').apply(summ).reindex(order).round(2).to_string())
    print('-- by state (R/setup, Rtrail, trig%)')
    print(s.groupby(['state', 'entry_type']).apply(summ)[['setups', 'trig%', 'Rtrail', 'R/setup']].unstack('entry_type').round(2).to_string())

# paired per setup: pivot vs daily touch on the same setups (date-paired on R per setup)
def paired(s, a, bname):
    pa = s[s.entry_type == a].set_index(['t', 'date', 'level']); pb = s[s.entry_type == bname].set_index(['t', 'date', 'level'])
    j = pd.DataFrame({'a': pa.R_trail.where(pa.trig, 0.0), 'b': pb.R_trail.where(pb.trig, 0.0)}).dropna()
    dd = (j.a - j.b).groupby(level='date').mean()
    mid = dd.index.sort_values()[len(dd) // 2]
    return dict(n=len(j), dates=len(dd), diff=round(dd.mean(), 3), t=round(dd.mean() / dd.std() * np.sqrt(len(dd)), 2),
                h1=round(dd[dd.index < mid].mean(), 3), h2=round(dd[dd.index >= mid].mean(), 3))
for lv in ('pdl', 'e21'):
    s = d[d.level == lv]
    for a in ('P30', 'P15', 'H30', 'H15', 'D_close'):
        print(f'paired {lv} {a} vs D_touch (R/setup, trail):', paired(s, a, 'D_touch'), '| leading:', paired(s[s.lead], a, 'D_touch'))
