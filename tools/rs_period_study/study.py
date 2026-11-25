"""RS period study (Nov 24, 2026; Adam: "test the shorter term RS... my gut was 3 and 6 month").
Each weekly cutoff (every 5 sessions): liquid stocks ($10+, $20M+/day 50-day). Rank by return over 10/20/30/63/126 sessions and by the
dashboard RS Rating (40/20/20/20 of 63/126/189/252). Top 10% -> forward return from NEXT OPEN to close +20 / +60 sessions, minus the average
liquid stock. Also inside leading groups (sub-theme top 30% by 60-day median return). t = mean / (sd / sqrt(n cutoffs)).
"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from breadth import store
b = store.apply_splits(store.load_bars(), store.load_splits())
c = b.pivot_table(index='date', columns='ticker', values='c').sort_index()
o = b.pivot_table(index='date', columns='ticker', values='o').reindex_like(c)
dv = (c * b.pivot_table(index='date', columns='ticker', values='v').reindex_like(c)).rolling(50, min_periods=30).mean()
sub = store.load_subthemes().drop_duplicates('ticker').set_index('ticker')['subtheme']
ETF = {'SPY','QQQ','IWM','RSP','DIA','SOXX','SMH','QQQE','TQQQ'}
P = {'2wk': 10, '4wk': 20, '6wk': 30, '3mo': 63, '6mo': 126}
rows = []
for i in range(252, len(c) - 61, 5):
    px = c.iloc[i]; ok = (px >= 10) & (dv.iloc[i] >= 20e6); L = [t for t in ok[ok].index if t not in ETF]
    if len(L) < 200: continue
    ent = o.iloc[i + 1][L]
    f = {h: (c.iloc[i + h][L] / ent - 1) for h in (20, 60)}
    sc = {k: px[L] / c.iloc[i - n][L] - 1 for k, n in P.items()}
    sc['1yr RS'] = sum(w * (px[L] / c.iloc[i - n][L] - 1) for w, n in ((.4, 63), (.2, 126), (.2, 189), (.2, 252)))
    r60 = px[L] / c.iloc[i - 60][L] - 1
    g = r60.groupby(sub.reindex(L)).median(); lead = g[g >= g.quantile(.7)].index
    inlead = sub.reindex(L).isin(lead)
    for k, s in sc.items():
        s = s.dropna(); top = s[s >= s.quantile(.9)].index
        for h in (20, 60):
            fr = f[h]; base = fr.mean()
            rows.append(dict(date=c.index[i], score=k, h=h, ex=fr.reindex(top).mean() - base,
                             ex_lead=fr.reindex([t for t in top if inlead.get(t, False)]).mean() - base,
                             hit=(fr.reindex(top) > base).mean(), grp=fr[inlead.values].mean() - base))
d = pd.DataFrame(rows); d['half'] = np.where(d.date < d.date.median(), 1, 2)
print('cutoffs', d.date.nunique(), d.date.min().date(), d.date.max().date())
def t(x): x = x.dropna(); return x.mean() / (x.std() / np.sqrt(len(x))) if len(x) > 2 else np.nan
out = []
for (k, h), x in d.groupby(['score', 'h']):
    out.append(dict(score=k, h=h, top10_ex=100 * x.ex.mean(), t=t(x.ex), half1=100 * x[x.half == 1].ex.mean(), half2=100 * x[x.half == 2].ex.mean(),
                    beat_pct=100 * x.hit.mean(), lead_ex=100 * x.ex_lead.mean(), lead_t=t(x.ex_lead), lead_h1=100*x[x.half==1].ex_lead.mean(), lead_h2=100*x[x.half==2].ex_lead.mean(), group_only=100*x.grp.mean()))
O = pd.DataFrame(out).round(2)
pd.set_option('display.width', 250)
order = ['2wk', '4wk', '6wk', '3mo', '6mo', '1yr RS']
for h in (20, 60):
    print(f'\n--- next {h} sessions (top 10% minus average liquid stock, %) ---')
    print(O[O.h == h].set_index('score').loc[order].drop(columns='h').to_string())
d.to_csv('tools/rs_period_study/results.csv', index=False)
