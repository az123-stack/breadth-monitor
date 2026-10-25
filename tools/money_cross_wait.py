import pandas as pd, numpy as np, glob
b=pd.read_csv('data/breadth.csv',parse_dates=['date']).set_index('date')
b['m10']=b.dv_net.rolling(10).mean(); b['m20']=b.dv_net.rolling(20).mean()
bars=pd.concat([pd.read_parquet(f) for f in sorted(glob.glob('data/bars/*.parquet'))]); bars['date']=pd.to_datetime(bars.date)
O=bars.pivot(index='date',columns='ticker',values='o'); C=bars.pivot(index='date',columns='ticker',values='c'); V=bars.pivot(index='date',columns='ticker',values='v')
liq=(C>=5)&((C*V).rolling(20).mean()>=20e6)
v=b.dropna(subset=['m20']).loc[lambda d:d.index.isin(C.index)].copy()
v['below']=v.m10<v.m20; v['pct']=v.m10.rank(pct=True)
D=list(C.index); ix={d:i for i,d in enumerate(D)}
def ret(i,j):  # buy open i, sell close j
    s=C.SPY.iloc[j]/O.SPY.iloc[i]-1
    r=(C.iloc[j]/O.iloc[i]-1)[liq.iloc[i-1]].clip(-.5,.5).mean(); return s,r
rows=[]; vv=v.reset_index()
i=0
while i<len(vv):
    r=vv.iloc[i]
    if r.below and r.pct<=0.2:
        d=r.date; k=i
        while k<len(vv) and vv.iloc[k].below: k+=1
        if k>=len(vv): rows.append(dict(sig=d.date(),cross=None)); break
        c=vv.iloc[k].date; a=ix[d]+1; x=ix[c]+1
        out=dict(sig=d.date(),cross=c.date(),wait=x-a)
        if x+21<len(D):
            out['spy_now21']=ret(a,a+21)[0]; out['spy_wait']=ret(a,x-1)[0] if x-1>a else 0
            out['spy_cross21']=ret(x,x+21)[0]
            # same end date comparison: hold from now to cross+21 vs from cross to cross+21
            out['spy_now_to_end']=ret(a,x+21)[0]
            out['ew_now21'],out['ew_cross21']=ret(a,a+21)[1],ret(x,x+21)[1]
        # SPY dip below signal-day close before cross?
        out['spy_low_before_cross']=C.SPY.iloc[a:x].min()/C.SPY.iloc[a-1]-1 if x>a else 0
        rows.append(out); i=k+1
    else: i+=1
R=pd.DataFrame(rows); pd.set_option('display.width',250)
print(R.round(3).to_string())
print(R.mean(numeric_only=True).round(4))
