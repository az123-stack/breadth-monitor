"""Scenario study (Nov 21, 2026; Adam: "scenario plan: if large caps come back what happens, if large and small both move up...").
Setups: every session where SPY is down 5%+ over 20 sessions (pullback like Nov 2026). Look 20 sessions ahead and sort what happened into
  A both up, big caps lead (SPY>RSP) · B both up, broad leads (RSP>=SPY) · C SPY up, RSP down (narrow) · D SPY down (more selling).
For each scenario: what won over the next 20 sessions among baskets measured AT THE SIGNAL DATE (no look-ahead):
  leaders = RS top 10% liquid · beta = top 10% 60d beta · held = top 10% by 20d return into the signal (held up best)
  defensive = staples/utilities/healthcare sub-themes · megacaps · semis (SOXX) · all liquid median.
Independent episodes = first signal date after 20 sessions with no signal.
"""
import sys; sys.path.insert(0, '.')
import warnings; warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from breadth import store
b = store.apply_splits(store.load_bars(), store.load_splits())
c = b.pivot_table(index='date', columns='ticker', values='c').sort_index()
dv = (b.c * b.v).groupby([b.date, b.ticker]).sum().unstack().reindex(c.index)
sub = store.load_subthemes()
DEF = sub[sub.group.str.contains('Staples|Utilit|Health', case=False, na=False)].ticker.unique()
MEGA = ['NVDA', 'AVGO', 'MSFT', 'GOOGL', 'META', 'AMZN', 'AAPL', 'TSLA']
ret = c.pct_change()
spy = c['SPY']; H = 20
rows = []
TH = float(sys.argv[1]) if len(sys.argv) > 1 else -0.05
for i in range(65, len(c) - H):
    if spy.iloc[i] / spy.iloc[i - 20] - 1 > TH: continue
    px = c.iloc[i]; liq = (dv.iloc[i-20:i+1].mean() >= 20e6) & (px >= 5)
    liq = liq.drop([x for x in ['SPY','RSP','QQQ','IWM','SOXX','QQQE','DIA'] if x in liq.index], errors='ignore')
    L = liq[liq].index
    fwd = c.iloc[i + H][L] / px[L] - 1
    r = px/c.iloc[i-63]-1  # 3-month RS (bar history too short for the 12-month RS Rating before late 2025)
    r = r[L].dropna(); lead = r[r >= r.quantile(.9)].index
    w = ret.iloc[i-59:i+1]; m = w['SPY']; beta = (w[L].apply(lambda s: s.cov(m)) / m.var()).dropna()
    hb = beta[beta >= beta.quantile(.9)].index
    r20 = (px[L] / c.iloc[i-20][L] - 1).dropna(); held = r20[r20 >= r20.quantile(.9)].index
    sp = spy.iloc[i+H]/spy.iloc[i]-1; rs = c['RSP'].iloc[i+H]/c['RSP'].iloc[i]-1
    scen = 'D more selling' if sp < 0 else ('C narrow: SPY up, RSP down' if rs < 0 else ('A both up, big caps lead' if sp > rs else 'B both up, broad leads'))
    f = lambda t: float(fwd.reindex(t).dropna().mean()) if len(fwd.reindex(t).dropna()) else np.nan
    rows.append(dict(date=c.index[i].date(), scen=scen, spy=sp, rsp=rs, all=float(fwd.median()), leaders=f(lead), beta=f(hb), held=f(held),
                     defensive=f(DEF), mega=f(MEGA), semis=c['SOXX'].iloc[i+H]/c['SOXX'].iloc[i]-1 if 'SOXX' in c else np.nan))
d = pd.DataFrame(rows)
d['episode'] = (pd.to_datetime(d.date).diff().dt.days.fillna(99) > 30).cumsum()
print('signal days', len(d), 'episodes', d.episode.nunique())
print(d.groupby('episode').agg(start=('date','min'), end=('date','max'), days=('date','size'), main=('scen', lambda s: s.mode()[0])).to_string())
cols = ['spy','rsp','all','leaders','beta','held','defensive','mega','semis']
g = d.groupby('scen'); out = (100*g[cols].mean()).round(1); out.insert(0,'days',g.size()); out.insert(1,'episodes',g.episode.nunique())
print(out.to_string())
print('\nall pullback days:', (100*d[cols].mean()).round(1).to_dict())
d.to_csv('tools/scenario_study/results.csv', index=False)
