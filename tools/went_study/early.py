"""Follow-up (Adam, Oct 25 2026: ACN / IT already ran when they hit the list; the buy was the flag under the 50 WEMA).
A) EARLIER event 'curl under the 50': base (20+ of 40 weeks under the 50 WEMA), 9 WEMA crossed over the 21 and the 21 rising,
   close between 1.5 weekly ATRs under and 0.5 ATR over the 50 WEMA. Does the group point still separate winners there?
B) Inside the later (fresh) setup, does buying far above the 9 WEMA do worse than buying near it?"""
import sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/home/claude/breadth-monitor")
F, w, cols = pickle.load(open("/tmp/launchF.pkl", "rb"))
W = F["W"]; c, h = W["c"], W["h"]; e9, e21, e50, atr = F["e9"], F["e21"], F["e50"], F["atr"]
liq = (c >= 5) & (F["dvol"].reindex(F["wd"])[cols] >= 10e6)
curl = liq & (F["below"] >= 20) & (e9 > e21) & (e21 > e21.shift(4)) & (c >= e50 * (1 - 1.5 * atr)) & (c <= e50 * (1 + 0.5 * atr))
flag = curl & (c > h.shift(1).rolling(4, min_periods=3).max())        # and breaking a 4-week flag
vs9 = (c / e9 - 1) / atr
days, wd = F["days"], F["wd"]; O, H, C = F["dO"].to_numpy(), F["dH"].to_numpy(), F["dC"].to_numpy()
WC, E50 = c.to_numpy(), e50.to_numpy(); spy = w["c"]["SPY"].to_numpy(); ent = days.searchsorted(wd, side="right")
P = {k: v.to_numpy() for k, v in F["pts"].items()}; V9 = vs9.to_numpy(); A = atr.to_numpy()
def collect(mask, every=26):
    M = mask.to_numpy().copy(); M[:40] = False; last = {}; rows = []
    for i in range(len(wd)):
        a = ent[i]
        if a + 130 > len(days): break
        for j in np.flatnonzero(M[i]):
            if j in last and i - last[j] < every: continue
            last[j] = i; e = O[a, j]
            if not np.isfinite(e) or e <= 0: continue
            rows.append(dict(date=wd[i], t=cols[j], g=P["group"][i, j], rs=P["rs"][i, j], rl=P["rsline"][i, j], gp=P["gap"][i, j], vs9=V9[i, j], atr=A[i, j],
                             maxg=np.nanmax(H[a:a + 130, j]) / e - 1, x13=(C[a + 65, j] / e - 1) - (spy[a + 65] / spy[a] - 1),
                             lost=bool(np.any(WC[i + 1:i + 14, j] < E50[i + 1:i + 14, j] * (1 - 1.5 * A[i, j])))))
    return pd.DataFrame(rows)
def s(x): return pd.Series(dict(n=len(x), went=(x.maxg >= .5).mean(), best=x.maxg.median(), x13=x.x13.median(), x13m=x.x13.clip(-1, 3).mean(), atr=x.atr.median()))
for nm, m in (("CURL under/at the 50", curl), ("CURL + 4-week flag break", flag)):
    X = collect(m); X["other"] = X.rs.astype(int) + X.rl.astype(int) + X.gp.astype(int)
    split = X.date.sort_values().iloc[len(X) // 2]
    print(f"\n== {nm}: {len(X)} events")
    print(X.groupby("g").apply(s).round(3))
    print(X.groupby(["g", X.other >= 2]).apply(s).round(3))
    for hh, x in (("h1", X[X.date < split]), ("h2", X[X.date >= split])):
        print(hh, "group:", s(x[x.g]).round(3).to_dict(), "| no group:", s(x[~x.g]).round(3).to_dict())
    print("ACN/IT/CTSH/CDW rows:", X[X.t.isin(["ACN", "IT", "CTSH", "CDW", "ZS"])][["t", "date", "g", "other", "maxg"]].to_string())
# B) entry location inside the fresh setup, every qualifying week (not first-only)
X = collect(F["fresh"], every=1); X["A"] = X.g & ((X.rs.astype(int) + X.rl.astype(int) + X.gp.astype(int)) >= 2)
X["loc"] = pd.cut(X.vs9, [-9, 0.5, 1.0, 1.5, 9], labels=["<=0.5 ATR over 9", "0.5-1", "1-1.5", ">1.5 ATR"])
print("\n== fresh setup, every week, by distance over the 9 WEMA (all / grade A)")
print(X.groupby("loc", observed=True).apply(s).round(3)); print(X[X.A].groupby("loc", observed=True).apply(s).round(3))
