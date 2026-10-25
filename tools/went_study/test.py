import sys, os, pandas as pd, numpy as np
D = pd.read_pickle(os.environ.get("IN", "/tmp/went_ev.pkl"))
print("CDNA/DINO/NTRA events:\n", D[D.t.isin(["CDNA","DINO","NTRA"])][["t","date","ent","maxg","r13","rs","rsl13","vr","gsub13","peers"]].round(2).to_string())
F = D[D.fwd_weeks >= 26].copy()
F["went"] = F.maxg >= 0.5
print(f"\nevents with 26 weeks of future: {len(F)}  ({F.date.min().date()} - {F.date.max().date()}); went (+50% high within 26w): {F.went.mean():.0%}")
print("median 26w best high", f"{F.maxg.median():.0%}", " 13w return vs SPY", f"{F.x13.median():+.1%}")
split = F.date.sort_values().iloc[len(F)//2]
feats = ["rs","rsl13","rsl_ema","rsl_hi","vr","udv","vmax","gapmax","adr","atr","dvol","price","off_hi","depth","run","ext","tight4","slope50","gsub13","peers","spy13"]
out = []
for f in feats:
    x = F[[f,"went","maxg","x13","date"]].dropna()
    if f == "rsl_hi":
        hi, lo = x[x[f] == 1], x[x[f] == 0]
    else:
        q = x[f].quantile([1/3, 2/3]); hi, lo = x[x[f] >= q.iloc[1]], x[x[f] <= q.iloc[0]]
    ic = x[f].rank().corr(x.maxg.rank())
    h1 = x[x.date < split]; h2 = x[x.date >= split]
    ic1, ic2 = h1[f].rank().corr(h1.maxg.rank()), h2[f].rank().corr(h2.maxg.rank())
    out.append(dict(f=f, n=len(x), ic=ic, ic1=ic1, ic2=ic2, went_hi=hi.went.mean(), went_lo=lo.went.mean(),
                    x13_hi=hi.x13.median(), x13_lo=lo.x13.median(), med_went=x[x.went][f].median(), med_not=x[~x.went][f].median()))
O = pd.DataFrame(out).sort_values("ic", key=abs, ascending=False)
pd.set_option("display.width", 250)
print(O.round(3).to_string(index=False))
print("\nTop 25 that went (26w best high):")
print(F.sort_values("maxg", ascending=False).head(25)[["t","date","ent","maxg","r13","sub","rs","rsl13","vr","adr","gapmax","gsub13","peers"]].round(2).to_string(index=False))
