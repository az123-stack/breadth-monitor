import pandas as pd, numpy as np, glob
b=pd.read_csv('data/breadth.csv',parse_dates=['date']).set_index('date')
b['m10']=b.dv_net.rolling(10).mean(); b['m20']=b.dv_net.rolling(20).mean()
bars=pd.concat([pd.read_parquet(f) for f in sorted(glob.glob('data/bars/*.parquet'))]); bars['date']=pd.to_datetime(bars.date)
O=bars.pivot(index='date',columns='ticker',values='o'); C=bars.pivot(index='date',columns='ticker',values='c'); V=bars.pivot(index='date',columns='ticker',values='v')
dv=(C*V).rolling(20).mean()
liq=(C>=5)&(dv>=20e6)
b=b.loc[b.index.isin(C.index)]
dates=C.index
def fwd(h):
    out={}
    for i,d in enumerate(dates[:-1]):
        if i+h>=len(dates): break
        o=O.iloc[i+1]; c=C.iloc[i+h]; spy=c['SPY']/o['SPY']-1
        r=(c/o-1)[liq.iloc[i]].clip(-.5,.5)
        out[d]=(spy, r.mean())
    return pd.DataFrame(out,index=['spy','ew']).T
res={h:fwd(h) for h in (5,10,21)}
b['below']=b.m10<b.m20
b['cross_up']=(~b.below)&(b.below.shift(1).fillna(False))
b['cross_dn']=(b.below)&(~b.below.shift(1).fillna(True))
v=b.dropna(subset=['m20'])
print('days',len(v),'below',v.below.sum(),'cross ups',v.cross_up.sum(), 'first',v.index[0].date())
half=v.index[len(v)//2]
for h,R in res.items():
    j=v.join(R,how='inner')
    def s(m,lab):
        x=j[m]; print(f' {h}d {lab:14s} n{len(x):4d} SPY {x.spy.mean()*100:+.2f}% up {(x.spy>0).mean()*100:3.0f}%  EW {x.ew.mean()*100:+.2f}%  | 1st {x[x.index<half].spy.mean()*100:+.2f} 2nd {x[x.index>=half].spy.mean()*100:+.2f}')
    s(j.below,'10<20'); s(~j.below,'10>20'); s(j.cross_up,'cross up day'); s(j.index.isin(j.index),'all')
# streaks
v=v.copy(); v['grp']=(v.below!=v.below.shift()).cumsum()
st=v.groupby('grp').agg(start=('below',lambda x:x.index[0].date()),end=('below',lambda x:x.index[-1].date()),below=('below','first'),n=('below','size'))
print(st[st.below].to_string())
print(v[['dv_net','m10','m20','dn_share10','ratio10','t2108']].tail(8).round(1).to_string())
print('---- depth of outflow')
v['pct']=v.m10.rank(pct=True)
print('current m10 pct', round(v.pct.iloc[-1]*100), 'gap m10-m20 pct', round((v.m10-v.m20).rank(pct=True).iloc[-1]*100))
for h,R in res.items():
    j=v.join(R,how='inner')
    for lab,m in [('m10 bottom 20%',j.pct<=.2),('m10 top 20%',j.pct>=.8),('dn_share10>=53',j.dn_share10>=53),('below & bottom20',j.below&(j.pct<=.2))]:
        x=j[m]; print(f' {h}d {lab:18s} n{len(x):4d} SPY {x.spy.mean()*100:+.2f}% up {(x.spy>0).mean()*100:3.0f}% EW {x.ew.mean()*100:+.2f}% | 1st {x[x.index<half].spy.mean()*100:+.2f} 2nd {x[x.index>=half].spy.mean()*100:+.2f}')
