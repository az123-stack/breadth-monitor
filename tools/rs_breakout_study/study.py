"""RS line new highs ("blue dots") as a breakout filter, a divergence warning and a hold/tighten rule.
Nov 26, 2026 (Adam, from an @1ChartMaster SNDK chart: "notice when it stopped printing RS dots" - dots printed all the way up, stopped
before the final price high, then -73%). Card R-2026-11-26-rs-dots-breakouts.

RS line = close / SPY close. RS dot (period X = 63 or 126) = RS line at a new X-session high.
Universe: stocks $10+, $20M+/day 50-day average dollar volume, ETFs out. Signals use data through day i; buy at the open of i+1.

Part A - breakout entry filter. Breakout day i: close above the highest high of the prior 20 sessions, close > 50 EMA, 21 EMA > 50 EMA,
  first breakout for the stock in 10 sessions. Groups: RS dot in the last 5 sessions incl. i ("confirmed"), RS dot 6-20 sessions ago,
  no RS dot in 20 sessions ("unconfirmed"); also "RS led" = dot in i-10..i-1 while the close was 3%+ under its X-session high.
  Outcomes: excess return vs the average liquid stock (same entry open -> close) at 5 / 21 / 63 sessions; trade R: stop = breakout-day
  low (risk floored 0.3 ADR, capped 2 ADR), exit first close under the 10 EMA, max 63 sessions.
Part B - divergence (the SNDK pattern). Close at a new 126-session closing high: RS dot (126) within 5 sessions ("confirmed high") vs no
  RS dot in 20 sessions ("divergent high"). Outcomes: 21/63-session excess, worst drawdown next 63 sessions, share falling 25%+.
Part C - stop adding / tighten. (1) holders: stocks above the 50 EMA with an RS dot in the last 60 sessions, sampled every 5 sessions,
  bucketed by sessions since the last dot (0-5, 6-14, 15-30, 31-60); also split by RS Rating >= 80 (the lagging 1-year rating).
  (2) exits on Part A trades: 10 EMA trail always vs "wide while dots print": trail on the 21 EMA until 15 sessions pass without a dot,
  then the 10 EMA. Paired per trade.
Stats: date is the unit (per-date means), t, halves split at the median date; regimes = breadth state at the signal close, SPY vs 50-day,
leading group (sub-theme top 30% on 60-day median return).
"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from breadth import store, strength, metrics

b = store.apply_splits(store.load_bars(), store.load_splits())
W = strength.wide_all(b)
O, H, L, C, V = W['o'], W['h'], W['l'], W['c'], W['v']
dates = C.index; N = len(dates)
spy = C['SPY']
ETF = {'SPY','QQQ','IWM','RSP','DIA','SOXX','SMH','QQQE','TQQQ','SQQQ','SPXL','SOXL','TLT','GLD','SLV','USO','UNG','XLE','XLK','XLF','XLV',
       'XLU','XLP','XLI','XLB','XLY','XLC','XLRE','KRE','XBI','IBB','ARKK','EEM','EFA','FXI','KWEB','IBIT','BITO','HYG','LQD','UUP','MAGS'}
dv = (C * V).rolling(50, min_periods=30).mean()
liq = (dv >= 20e6) & (C >= 10)
liq.loc[:, [t for t in C.columns if t in ETF]] = False
E10 = C.ewm(span=10, adjust=False, min_periods=10).mean()
E21 = C.ewm(span=21, adjust=False, min_periods=21).mean()
E50 = C.ewm(span=50, adjust=False, min_periods=50).mean()
ADR = ((H - L) / C).rolling(20, min_periods=10).mean() * C
RS = C.div(spy, axis=0)
DOT = {X: RS >= RS.rolling(X, min_periods=X).max() * 0.999 for X in (63, 126)}
since = {}
for X, D in DOT.items():   # sessions since the last dot (0 = today), NaN if none yet
    idx = pd.DataFrame(np.where(D.to_numpy(), np.arange(N)[:, None], np.nan), index=dates, columns=C.columns).ffill()
    since[X] = pd.DataFrame(np.arange(N)[:, None] - idx.to_numpy(), index=dates, columns=C.columns)

# average liquid stock, entry open(i+1) -> close(i+h)
def univ_ret(h):
    r = C.shift(-h) / O.shift(-1) - 1
    return r.where(liq).clip(-0.9, 3).mean(axis=1)
U = {h: univ_ret(h) for h in (5, 21, 63)}

# regimes
hist = pd.read_csv('data/breadth.csv', parse_dates=['date']).set_index('date').reindex(dates)
tw = metrics.thrust_window(hist, dates)
state = np.where(tw, 'thrust', np.where((hist.ratio5 >= 1.5) & (hist.ratio10 >= 1.5), 'strong', np.where(hist.ratio10 < 1, 'weak', 'mixed')))
state = pd.Series(state, index=dates)
spy50 = spy > spy.rolling(50).mean()
sub = store.load_subthemes().drop_duplicates('ticker').set_index('ticker')['subtheme']
r60 = C / C.shift(60) - 1
lead = {}
for i in range(60, N):
    g = r60.iloc[i][liq.iloc[i]].groupby(sub.reindex(r60.columns[liq.iloc[i].to_numpy()])).median().dropna()
    lead[i] = set(g[g >= g.quantile(.7)].index)
ratings, _, _ = strength.rs_ratings(C, liq, range(N))

def trail_exit(t, i0, stop, mode):
    """Walk from entry day i0 (bought at open). mode '10' or 'dots'. Returns exit price."""
    o, l, c = O[t].to_numpy(), L[t].to_numpy(), C[t].to_numpy()
    e10, e21, s = E10[t].to_numpy(), E21[t].to_numpy(), since[126][t].to_numpy()
    for k in range(i0, min(i0 + 63, N)):
        if k > i0 and o[k] <= stop: return o[k]
        if l[k] <= stop: return stop
        if k == i0: continue
        if mode == '10' or not (s[k] <= 15): line = e10[k]
        else: line = e21[k]
        if c[k] < line: return c[k]
    return c[min(i0 + 62, N - 1)]

rowsA, rowsB, rowsC = [], [], []
hh20 = H.rolling(20).max().shift(1)
c126hi = C.rolling(126, min_periods=126).max()
low3 = {}
for t in C.columns:
    if t in ETF or liq[t].sum() < 60: continue
    c, o, l = C[t].to_numpy(), O[t].to_numpy(), L[t].to_numpy()
    lq, e21, e50, adr, h20 = liq[t].to_numpy(), E21[t].to_numpy(), E50[t].to_numpy(), ADR[t].to_numpy(), hh20[t].to_numpy()
    s63, s126 = since[63][t].to_numpy(), since[126][t].to_numpy()
    hi126, rt = c126hi[t].to_numpy(), ratings[t].to_numpy()
    cmax63 = C[t].rolling(63, min_periods=63).max().to_numpy(); cmax126 = hi126
    lastA = lastB = -99
    for i in range(130, N - 6):
        if not lq[i] or np.isnan(e50[i]): continue
        common = dict(t=t, date=dates[i], state=state.iloc[i], spy50=bool(spy50.iloc[i]), lead=sub.get(t) in lead.get(i, ()), rating=rt[i])
        def fwd(h):
            j = i + h
            if j >= N or np.isnan(c[j]) or np.isnan(o[i + 1]): return np.nan, np.nan
            r = c[j] / o[i + 1] - 1
            return r, r - U[h].iloc[i]
        # ---- A: breakouts
        if c[i] > h20[i] and c[i] > e50[i] and e21[i] > e50[i] and i - lastA >= 10:
            lastA = i
            row = dict(common)
            for X, s in ((63, s63), (126, s126)):
                v = s[i]
                row[f'g{X}'] = 'confirmed 0-5' if v <= 5 else ('dot 6-20' if v <= 20 else 'unconfirmed')
                # RS led: a dot in i-10..i-1 while price was 3%+ under its own X high
                cm = cmax63 if X == 63 else cmax126
                led = False
                for k in range(i - 10, i):
                    if (DOT[X][t].iat[k]) and c[k] < 0.97 * cm[k]: led = True; break
                row[f'led{X}'] = led
            for h in (5, 21, 63):
                row[f'r{h}'], row[f'x{h}'] = fwd(h)
            if i + 1 < N and not np.isnan(o[i + 1]) and not np.isnan(adr[i]):
                risk = min(max(o[i + 1] - l[i], 0.3 * adr[i]), 2 * adr[i]); stop = o[i + 1] - risk
                for m in ('10', 'dots'):
                    row[f'R_{m}'] = (trail_exit(t, i + 1, stop, m) - o[i + 1]) / risk
            rowsA.append(row)
        # ---- B: new 126-session closing high, confirmed vs divergent
        if c[i] >= hi126[i] * 0.999 and i - lastB >= 10 and (s126[i] <= 5 or not (s126[i] <= 20)):
            lastB = i
            row = dict(common, grp='confirmed' if s126[i] <= 5 else 'divergent')
            for h in (21, 63):
                row[f'r{h}'], row[f'x{h}'] = fwd(h)
            j2 = min(i + 63, N - 1)
            row['dd63'] = np.nanmin(l[i + 1:j2 + 1]) / c[i] - 1 if j2 > i else np.nan
            rowsB.append(row)
        # ---- C: holders, every 5 sessions
        if i % 5 == 0 and c[i] > e50[i] and s126[i] <= 60:
            v = s126[i]
            row = dict(common, bucket='0-5' if v <= 5 else '6-14' if v <= 14 else '15-30' if v <= 30 else '31-60')
            for h in (21, 63):
                row[f'r{h}'], row[f'x{h}'] = fwd(h)
            j2 = min(i + 21, N - 1)
            row['dd21'] = np.nanmin(l[i + 1:j2 + 1]) / c[i] - 1 if j2 > i else np.nan
            rowsC.append(row)

A, B, Cc = pd.DataFrame(rowsA), pd.DataFrame(rowsB), pd.DataFrame(rowsC)
for d in (A, B, Cc):
    d['half'] = np.where(d.date < d.date.median(), 1, 2)

def tdate(x, dts):
    m = x.groupby(dts).mean().dropna()
    return m.mean() / (m.std() / np.sqrt(len(m))) if len(m) > 2 and m.std() > 0 else np.nan

def summ(g, cols):
    out = {'n': len(g), 'dates': g.date.nunique()}
    for c in cols:
        out[c] = g[c].mean()
        out['t_' + c] = tdate(g[c], g.date)
        out[c + '_h1'] = g[g.half == 1][c].mean(); out[c + '_h2'] = g[g.half == 2][c].mean()
    return pd.Series(out)

pd.set_option('display.width', 260); pd.set_option('display.max_columns', 40)
print('bars', dates[0].date(), dates[-1].date(), '| A', len(A), 'B', len(B), 'C', len(Cc))
for X in (63, 126):
    print(f'\n=== A breakouts by RS dot ({X}) — excess vs avg stock, R with 10 EMA trail')
    print(A.groupby(f'g{X}').apply(summ, cols=['x5', 'x21', 'x63', 'R_10']).round(3).to_string())
    print(f'-- RS led ({X})'); print(A.groupby(f'led{X}').apply(summ, cols=['x5', 'x21', 'R_10']).round(3).to_string())
print('\n-- A (126) leading groups only'); print(A[A.lead].groupby('g126').apply(summ, cols=['x21', 'R_10']).round(3).to_string())
print('\n-- A (126) by state'); print(A.groupby(['state', 'g126']).apply(summ, cols=['x21', 'R_10']).round(3)[['n', 'x21', 't_x21', 'R_10', 't_R_10']].to_string())
print('\n-- A (126) by SPY vs 50d'); print(A.groupby(['spy50', 'g126']).apply(summ, cols=['x21', 'R_10']).round(3)[['n', 'x21', 't_x21', 'R_10', 't_R_10']].to_string())
# paired date diff confirmed vs unconfirmed
def paired(df, col, a, b, key):
    ga = df[df[key] == a].groupby('date')[col].mean(); gb = df[df[key] == b].groupby('date')[col].mean()
    j = pd.concat([ga, gb], axis=1, keys=['a', 'b']).dropna(); d = j.a - j.b
    mid = d.index.sort_values()[len(d) // 2]
    return dict(dates=len(d), diff=round(d.mean(), 4), t=round(d.mean() / d.std() * np.sqrt(len(d)), 2), h1=round(d[d.index < mid].mean(), 4), h2=round(d[d.index >= mid].mean(), 4))
print('\npaired A confirmed vs unconfirmed (126):', {c: paired(A, c, 'confirmed 0-5', 'unconfirmed', 'g126') for c in ('x21', 'R_10')})
print('paired A confirmed vs unconfirmed (63):', {c: paired(A, c, 'confirmed 0-5', 'unconfirmed', 'g63') for c in ('x21', 'R_10')})

print('\n=== B new 126-session highs: confirmed vs divergent')
B['fell25'] = B.dd63 <= -0.25
print(B.groupby('grp').apply(summ, cols=['x21', 'x63', 'dd63', 'fell25']).round(3).to_string())
print('paired B:', {c: paired(B, c, 'confirmed', 'divergent', 'grp') for c in ('x21', 'x63', 'dd63')})

print('\n=== C holders by sessions since last RS dot (126)')
print(Cc.groupby('bucket').apply(summ, cols=['x21', 'x63', 'dd21']).round(3).to_string())
print('-- RS Rating >= 80 only'); print(Cc[Cc.rating >= 80].groupby('bucket').apply(summ, cols=['x21', 'x63']).round(3)[['n', 'x21', 't_x21', 'x21_h1', 'x21_h2', 'x63', 't_x63']].to_string())
print('paired C 0-5 vs 15-30:', paired(Cc, 'x21', '0-5', '15-30', 'bucket'), ' 0-5 vs 31-60:', paired(Cc, 'x21', '0-5', '31-60', 'bucket'))

print('\n=== C2 exits on breakout trades: wide while dots print vs 10 EMA always (R)')
A['dR'] = A.R_dots - A.R_10
print(A.groupby('g126').apply(summ, cols=['R_10', 'R_dots', 'dR']).round(3)[['n', 'R_10', 'R_dots', 'dR', 't_dR', 'dR_h1', 'dR_h2']].to_string())
print('all:', summ(A, ['dR']).round(3).to_dict())
for nm, d in (('A', A), ('B', B), ('C', Cc)):
    d.to_csv(f'tools/rs_breakout_study/{nm}.csv', index=False)
