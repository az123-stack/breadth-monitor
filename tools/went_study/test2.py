import os, pandas as pd, numpy as np
D = pd.read_pickle(os.environ.get("IN", "/tmp/went_ev.pkl"))
F = D[D.fwd_weeks >= 26].copy()
F["gain_atr"] = F.maxg / F.atr            # best high in weekly ATRs: removes the "volatile stocks move more" effect
F["went_v"] = F.gain_atr >= F.gain_atr.quantile(0.8)
split = F.date.sort_values().iloc[len(F)//2]
feats = ["rs","rsl13","rsl_ema","rsl_hi","vr","udv","vmax","gapmax","adr","price","dvol","off_hi","depth","run","ext","tight4","slope50","gsub13","peers","spy13"]
pd.set_option("display.width", 250)
def table(y, label):
    out=[]
    for f in feats:
        x = F[list(dict.fromkeys([f, y, "date", "lost50", "x13"]))].dropna()
        h1, h2 = x[x.date < split], x[x.date >= split]
        q = x[f].quantile([1/3, 2/3])
        hi, lo = (x[x[f]==1], x[x[f]==0]) if f=="rsl_hi" else (x[x[f]>=q.iloc[1]], x[x[f]<=q.iloc[0]])
        out.append(dict(f=f, ic=x[f].rank().corr(x[y].rank()), ic1=h1[f].rank().corr(h1[y].rank()), ic2=h2[f].rank().corr(h2[y].rank()),
                        top3_x13=hi.x13.median(), bot3_x13=lo.x13.median(), top3_lost50=hi.lost50.mean(), bot3_lost50=lo.lost50.mean()))
    print(f"\n== vs {label}"); print(pd.DataFrame(out).sort_values("ic", key=abs, ascending=False).round(3).to_string(index=False))
table("gain_atr", "best 26w high in weekly ATRs (volatility-adjusted)")
table("x13", "13-week return vs SPY")
# within-ADR check for the group + RS features
F["adr_t"] = pd.qcut(F.adr, 3, labels=["lowADR","midADR","hiADR"])
for f in ["gsub13","rs","rsl13","gapmax","depth","off_hi"]:
    print(f, {str(k): round(g[f].rank().corr(g.gain_atr.rank()),2) for k, g in F.groupby("adr_t", observed=True)})
# simple stacked score
x = F.dropna(subset=["gsub13"]).copy()
x["score"] = (x.gsub13 >= 0.67).astype(int) + (x.rs >= 70).astype(int) + (x.rsl13 >= 0.15).astype(int) + (x.gapmax >= 0.06).astype(int)
print("\nin a sub-theme: score -> n, went(+50%) rate, median best high, median x13, lost 50 WEMA")
print(x.groupby("score").agg(n=("t","size"), went=("maxg", lambda s:(s>=.5).mean()), best=("maxg","median"), x13=("x13","median"), lost=("lost50","mean"), atr=("atr","median")).round(3))
for h, g in ((1, x[x.date < split]), (2, x[x.date >= split])):
    print("half", h, g.groupby(g.score >= 3).agg(n=("t","size"), went=("maxg", lambda s:(s>=.5).mean()), x13=("x13","median")).round(3).to_dict())
print("all events lost-50 rate", round(F.lost50.mean(),2), " in a sub-theme:", round(F.gsub13.notna().mean(),2))
