"""Launch picks replay (Adam, Oct 25 2026: 'switch the 2-3 recommendations to come from the Launch list').
Each completed week: candidates = curl or fresh-breakout stocks, grade A/B, $20M+/day; ranked grade -> stage (curl first)
-> within 1 ATR of the 9 WEMA -> group rank -> RS; one per sub-theme; skip names picked in the last 13 weeks; top 3.
Entry next session's open; 13-week return vs SPY and vs the average liquid stock; best high in 26 weeks; failure stop.
Also: proof rule for the grade itself (A vs C, per-week averages, t, halves)."""
import sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/home/claude/breadth-monitor")
from breadth import launch
F, w, cols = pickle.load(open("/tmp/launchF.pkl", "rb"))
W = F["W"]; c = W["c"]; days, wd = F["days"], F["wd"]
e9, e50, atr = F["e9"], F["e50"], F["atr"]
liq = (c >= 5) & (F["dvol"].reindex(wd)[cols] >= 10e6)
curl = liq & (F["below"] >= 20) & (e9 > F["e21"]) & (F["e21"] > F["e21"].shift(4)) & (c >= e50 * (1 - 1.5 * atr)) & (c <= e50 * (1 + 0.5 * atr))
fresh = F["fresh"]
big = F["dvol"].reindex(wd)[cols] >= 20e6
G = F["pts"]["group"].to_numpy(); S = F["score"].to_numpy(); GR = F["grank"].to_numpy(); RS = F["rs"].to_numpy()
V9 = ((c / e9 - 1) / atr).to_numpy(); A = atr.to_numpy()
CU, FR, BG = curl.to_numpy(), fresh.to_numpy(), big.to_numpy(); L = liq.to_numpy()
O, H, C = F["dO"].to_numpy(), F["dH"].to_numpy(), F["dC"].to_numpy(); WC, E50 = c.to_numpy(), e50.to_numpy()
spy = w["c"]["SPY"].to_numpy(); ent = days.searchsorted(wd, side="right")
sub = [F["sub_of"].get(t) for t in cols]
rows, held = [], {}
for i in range(40, len(wd)):
    a = ent[i]
    if a + 65 >= len(days): break
    cand = []
    for j in np.flatnonzero((CU[i] | FR[i]) & BG[i] & G[i]):
        if held.get(j, -99) > i - 13: continue
        g = launch.grade(True, int(S[i, j]))
        cand.append(((g, 0 if CU[i, j] else 1, 0 if (V9[i, j] <= 1) else 1, -(GR[i, j] if np.isfinite(GR[i, j]) else 0), -(RS[i, j] if np.isfinite(RS[i, j]) else 0)), j, g))
    cand.sort()
    got, subs = [], set()
    for k, j, g in cand:
        if sub[j] in subs: continue
        subs.add(sub[j]); got.append((j, g))
        if len(got) == 3: break
    m = L[i] & np.isfinite(C[a + 64]) & np.isfinite(O[a])
    base = np.nanmean(np.clip(C[a + 64, m] / O[a, m] - 1, -0.95, 5))
    s13 = spy[a + 64] / spy[a] - 1
    for j, g in got:
        held[j] = i; e = O[a, j]
        if not np.isfinite(e) or e <= 0: continue
        r = C[a + 64, j] / e - 1
        mg = np.nanmax(H[a:min(a + 130, len(days)), j]) / e - 1
        floor = 1.5 if CU[i, j] else 0.0
        stop = bool(np.any(WC[i + 1:i + 14, j] < E50[i + 1:i + 14, j] * (1 - floor * A[i, j])))
        rows.append(dict(date=wd[i], t=cols[j], g=g, curl=bool(CU[i, j]), r=r, xspy=r - s13, xb=r - base, mg=mg, full26=a + 130 <= len(days), stop=stop))
P = pd.DataFrame(rows)
wk = P.groupby("date").agg(xspy=("xspy", "mean"), xb=("xb", "mean"))
def tt(x): return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 else np.nan
split = wk.index[len(wk) // 2]
print(f"PICKS replay: {len(P)} picks over {len(wk)} weeks ({P.date.min().date()} - {P.date.max().date()})")
print(f" 13w: avg return {P.r.mean():+.1%}, median {P.r.median():+.1%}; vs SPY {P.xspy.mean():+.1%} (median {P.xspy.median():+.1%}), vs avg stock {P.xb.mean():+.1%}")
print(f" by week vs SPY t {tt(wk.xspy):.2f}; vs avg stock t {tt(wk.xb):.2f}; halves vs SPY {wk[wk.index<split].xspy.mean():+.1%} / {wk[wk.index>=split].xspy.mean():+.1%}, vs stock {wk[wk.index<split].xb.mean():+.1%} / {wk[wk.index>=split].xb.mean():+.1%}")
print(f" beat SPY {(P.xspy>0).mean():.0%}; hit +50% in 26w (full window only) {(P[P.full26].mg>=.5).mean():.0%} n {P.full26.sum()}; failed (stop) within 13w {P.stop.mean():.0%}")
print(P.groupby("g")[["r","xspy","xb"]].agg(["mean","count"]).round(3))
print(P.groupby("curl")[["xspy"]].agg(["mean","count"]).round(3))
print("worst:", P.nsmallest(5, "r")[["t","date","r"]].to_string(index=False))
# proof rule for the grades themselves (first event per stock per 26 wks, per-week averages)
for key, M in (("fresh", FR), ("curl", CU)):
    last = {}; R = []
    for i in range(40, len(wd)):
        a = ent[i]
        if a + 65 >= len(days): break
        s13 = spy[a + 64] / spy[a] - 1
        for j in np.flatnonzero(M[i]):
            if j in last and i - last[j] < 26: continue
            last[j] = i; e = O[a, j]
            if not np.isfinite(e) or e <= 0: continue
            R.append(dict(date=wd[i], g=launch.grade(bool(G[i, j]), int(S[i, j])), xv=C[a + 64, j] / e - 1 - s13))
    R = pd.DataFrame(R); R["xv"] = R.xv.clip(-1, 3)
    wa = R[R.g == "A"].groupby("date").xv.mean(); wc = R[R.g == "C"].groupby("date").xv.mean()
    d = (wa - wc.reindex(wa.index)).dropna(); sp = d.index[len(d) // 2]
    wab = R[R.g != "C"].groupby("date").xv.mean(); d2 = (wab - wc.reindex(wab.index)).dropna(); sp2 = d2.index[len(d2) // 2]
    print(f"\nPROOF {key}: A minus C, 13w vs SPY by week: {d.mean():+.1%}, t {tt(d):.2f}, {len(d)} weeks, halves {d[d.index<sp].mean():+.1%} / {d[d.index>=sp].mean():+.1%}")
    print(f"        A+B minus C: {d2.mean():+.1%}, t {tt(d2):.2f}, {len(d2)} weeks, halves {d2[d2.index<sp2].mean():+.1%} / {d2[d2.index>=sp2].mean():+.1%}")
