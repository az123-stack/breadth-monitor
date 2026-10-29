import numpy as np, pandas as pd
P = "/tmp/pivot_study/"
ev = pd.read_parquet(P + "ev_out.parquet"); F = pd.read_pickle(P + "frames.pkl")
O, H, L, C, V, dv50, v50 = F["O"], F["H"], F["L"], F["C"], F["V"], F["dv50"], F["v50"]
n = len(C); Ov, Hv, Cv = O.to_numpy(), H.to_numpy(), C.to_numpy()
run21 = (C / C.shift(21) - 1).to_numpy(); rvol = (V / v50).to_numpy()
hi20 = H.rolling(20).max().shift(1).to_numpy()
trad = ((C >= 5) & (dv50 >= 20e6)).to_numpy()
evset = set(zip(ev.d, ev.j))
def fwd(d, j, k): return Cv[d + k, j] / Ov[d + 1, j] - 1 if d + k < n and Ov[d + 1, j] > 0 else np.nan
def bucket(r, v):
    rb = 0 if r < .2 else 1 if r < .5 else 2
    vb = 0 if v < 1 else 1 if v <= 2 else 2
    return rb, vb
# matched control: same date, same run-up bucket and same volume bucket, ALSO making a 20-day high (a rally day), not a pivot event
out = []
for r in ev.itertuples():
    d = r.d
    if d + 21 >= n: continue
    rb, vb = bucket(r.run21, r.rvol)
    js = [j for j in np.flatnonzero(trad[d] & (Hv[d] > hi20[d])) if (d, j) not in evset and np.isfinite(run21[d, j]) and np.isfinite(rvol[d, j]) and bucket(run21[d, j], rvol[d, j]) == (rb, vb)]
    if not js: continue
    for k in (5, 21):
        c = np.nanmean([fwd(d, j, k) for j in js])
        out.append(dict(d=d, k=k, rb=rb, vb=vb, ev=getattr(r, f"f{k}"), ctrl=c, depth=r.depth, kind=r.kind, nctrl=len(js), t=r.t))
M = pd.DataFrame(out); M["diff"] = M.ev - M.ctrl
def rep(m, label):
    x = m.groupby("d")["diff"].mean().dropna()
    if len(x) < 8: return print(f"{label:42} n/a ({len(x)} dates)")
    t = x.mean() / (x.std(ddof=1) / np.sqrt(len(x))); h = len(x) // 2
    print(f"{label:42} pivot {m.ev.mean()*100:+6.2f}% (median {m.ev.median()*100:+5.2f}%)  matched {m.ctrl.mean()*100:+6.2f}%  diff {x.mean()*100:+6.2f}%  t {t:5.2f}  halves {x.iloc[:h].mean()*100:+5.2f}/{x.iloc[h:].mean()*100:+5.2f}  events {len(m)} dates {len(x)}")
for k in (5, 21):
    print(f"\n==== {k}-day, vs matched rally days (same date, same run-up and volume bucket, no pivot) ====")
    m = M[M.k == k]
    rep(m, "ALL")
    for rb, nm in enumerate(["run-up <20%", "run-up 20-50%", "run-up >50%"]): rep(m[m.rb == rb], nm)
    for vb, nm in enumerate(["volume <1x", "volume 1-2x", "volume >2x"]): rep(m[m.vb == vb], nm)
    rep(m[m.depth > .6], "round trip >60%"); rep(m[m.depth.between(.4, .6)], "round trip 40-60%"); rep(m[m.depth < .4], "round trip 25-40%")
    rep(m[m.kind == "floor"], "old floor (broken support)"); rep(m[m.kind == "peak"], "old peak")
    rep(m[(m.rb >= 1) & (m.vb == 2)], "run-up 20%+ AND volume >2x")
M.to_parquet(P + "matched.parquet")
