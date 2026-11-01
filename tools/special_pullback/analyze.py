import pandas as pd, numpy as np
df = pd.read_csv("tools/special_pullback/trades.csv", parse_dates=["sig", "entry"])
d = df[df.kind.isin(["chase", "pb8", "pb21"])].dropna(subset=["R"])
mid = d.sig.sort_values().iloc[len(d)//2]

def summ(x):
    pdm = x.groupby("sig")[["x5", "x20", "R"]].mean()   # per signal date
    t = lambda s: s.mean() / (s.std(ddof=1) / np.sqrt(len(s))) if len(s) > 2 else np.nan
    h1 = x[x.sig < mid].R.mean(); h2 = x[x.sig >= mid].R.mean()
    return pd.Series(dict(n=len(x), dates=len(pdm), x5=x.x5.mean()*100, x20=x.x20.mean()*100,
                          med20=x.x20.median()*100, win=(x.R > 0).mean()*100, R=x.R.mean(),
                          tR_dates=t(pdm.R), R_h1=h1, R_h2=h2, worst20=x.r20.min()*100))
pd.set_option("display.width", 200); pd.set_option("display.float_format", lambda v: f"{v:.2f}")
print("ALL"); print(d.groupby(["cls", "kind"]).apply(summ))
print("\nPOST-THRUST (25 sessions)"); print(d[d.post].groupby(["cls", "kind"]).apply(summ))
print("\nNOT POST-THRUST"); print(d[~d.post].groupby(["cls", "kind"]).apply(summ))
# how often does a pullback come at all?
s = df[df.cls == "special"]
nsig = len(s[s.kind == "chase"])
for k in ["pb8", "pb21"]:
    got = (s.kind == k).sum(); broke = (s.kind == k + "_broke").sum()
    print(f"special {k}: clean pullback {got/nsig:.0%}, broke through {broke/nsig:.0%}, none in 10 sessions {1-(got+broke)/nsig:.0%}")

print("\nR / win columns")
for name, sel in (("ALL", d), ("POST", d[d.post]), ("NOT POST", d[~d.post])):
    g = sel.groupby(["cls", "kind"]).apply(summ)[["n", "win", "R", "tR_dates", "R_h1", "R_h2", "x20", "med20"]]
    print(name); print(g)
# paired: same signal stock, pullback minus chase (only stocks that got the pullback)
ch = d[d.kind == "chase"].set_index(["cls", "group", "t", "sig"])
for k in ("pb8", "pb21"):
    pb = d[d.kind == k].set_index(["cls", "group", "t", "sig"])
    j = pb[["R", "x20"]].join(ch[["R", "x20"]], rsuffix="_ch", how="inner")
    j["dR"] = j.R - j.R_ch; j["dx"] = j.x20 - j.x20_ch
    j = j.reset_index(); j["post"] = j.sig.isin(d[d.post].sig)
    for (cls, post), x in j.groupby(["cls", "post"]):
        pdm = x.groupby("sig").dR.mean()
        t = pdm.mean() / (pdm.std(ddof=1) / np.sqrt(len(pdm)))
        h = x[x.sig < mid].dR.mean(), x[x.sig >= mid].dR.mean()
        print(f"{k} minus chase | {cls:13} post={post!s:5} n {len(x):4} dates {len(pdm):3} dR {x.dR.mean():+.2f} (t {t:+.1f}, halves {h[0]:+.2f}/{h[1]:+.2f}) d20 {x.dx.mean()*100:+.1f}pts")
