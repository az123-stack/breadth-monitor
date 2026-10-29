import numpy as np, pandas as pd
P = "/tmp/pivot_study/"
ev = pd.read_parquet(P + "ev_out.parquet"); F = pd.read_pickle(P + "frames.pkl")
O, H, L, C, V, dv50, v50, adr = F["O"], F["H"], F["L"], F["C"], F["V"], F["dv50"], F["v50"], F["adr"]
n = len(C); Ov, Hv, Lv, Cv = O.to_numpy(), H.to_numpy(), L.to_numpy(), C.to_numpy(); A = adr.to_numpy()
run21 = (C / C.shift(21) - 1).to_numpy(); rvol = (V / v50).to_numpy()
hi20 = H.rolling(20).max().shift(1).to_numpy(); trad = ((C >= 5) & (dv50 >= 20e6)).to_numpy()
evset = set(zip(ev.d, ev.j))
def bucket(r, v): return (0 if r < .2 else 1 if r < .5 else 2, 0 if v < 1 else 1 if v <= 2 else 2)
def sell(d, j, k=5):   # sells off = within 5 sessions the low reaches 2 ADRs under the touch-day close; also 5-day close-to-close
    if d + k >= n or not np.isfinite(A[d, j]) or A[d, j] <= 0: return np.nan, np.nan
    lo = np.nanmin(Lv[d + 1:d + k + 1, j]); return float(lo <= Cv[d, j] * (1 - 2 * A[d, j])), Cv[d + k, j] / Cv[d, j] - 1
rows = []
for r in ev.itertuples():
    d, j = r.d, r.j
    if d + 6 >= n: continue
    s, c5 = sell(d, j)
    b = bucket(r.run21, r.rvol)
    js = [k for k in np.flatnonzero(trad[d] & (Hv[d] > hi20[d])) if (d, k) not in evset and np.isfinite(run21[d, k]) and np.isfinite(rvol[d, k]) and bucket(run21[d, k], rvol[d, k]) == b]
    if not js: continue
    cs = np.array([sell(d, k) for k in js], dtype=float)
    rows.append(dict(d=d, ev_sell=s, ctrl_sell=np.nanmean(cs[:, 0]), ev_c5=c5, ctrl_c5=np.nanmean(cs[:, 1]), rb=b[0], vb=b[1], kind=r.kind))
S = pd.DataFrame(rows)
def rep(m, label):
    x = (m.groupby("d").ev_sell.mean() - m.groupby("d").ctrl_sell.mean()).dropna()
    t = x.mean() / (x.std(ddof=1) / np.sqrt(len(x))); h = len(x) // 2
    print(f"{label:30} sell-off 2+ ADRs within 5d: pivot {m.ev_sell.mean()*100:4.1f}%  matched rally {m.ctrl_sell.mean()*100:4.1f}%  diff {x.mean()*100:+5.1f} pts  t {t:5.2f}  halves {x.iloc[:h].mean()*100:+4.1f}/{x.iloc[h:].mean()*100:+4.1f}  dates {len(x)}")
print("== 'touch it and sell off': chance of a 2-ADR drop from the touch-day close within 5 sessions ==")
rep(S, "ALL")
for rb, nm in enumerate(["run-up <20%", "run-up 20-50%", "run-up >50%"]): rep(S[S.rb == rb], nm)
for vb, nm in enumerate(["volume <1x", "volume 1-2x", "volume >2x"]): rep(S[S.vb == vb], nm)
rep(S[S.kind == "floor"], "old floor"); rep(S[S.kind == "peak"], "old peak")

# ---- 'pop through and then sell off': first close above the level (within 10 sessions of the touch) vs matched 20-day-high breakouts
print("\n== 'pop through then sell off': from the first close above the old level ==")
rows = []
for r in ev.itertuples():
    d0, j, lvl = r.d, r.j, r.lvl
    cc = Cv[d0:d0 + 11, j]; ab = np.flatnonzero(cc > lvl)
    if not len(ab): continue
    d = d0 + ab[0]
    if d + 21 >= n: continue
    back = float(np.any(Cv[d + 1:d + 11, j] < lvl))                  # closed back under the level within 10 sessions
    f21 = Cv[d + 21, j] / Ov[d + 1, j] - 1
    b = bucket(run21[d, j], rvol[d, j]) if np.isfinite(run21[d, j]) and np.isfinite(rvol[d, j]) else None
    if b is None: continue
    js = [k for k in np.flatnonzero(trad[d] & (Cv[d] > hi20[d])) if (d, k) not in evset and np.isfinite(run21[d, k]) and np.isfinite(rvol[d, k]) and bucket(run21[d, k], rvol[d, k]) == b]
    if not js: continue
    cb = np.nanmean([float(np.any(Cv[d + 1:d + 11, k] < hi20[d, k])) for k in js])
    cf = np.nanmean([Cv[d + 21, k] / Ov[d + 1, k] - 1 for k in js])
    rows.append(dict(d=d, back=back, cback=cb, f21=f21, cf21=cf, rb=b[0], vb=b[1], kind=r.kind))
B = pd.DataFrame(rows)
def rep2(m, label):
    x = (m.groupby("d").f21.mean() - m.groupby("d").cf21.mean()).dropna(); t = x.mean() / (x.std(ddof=1) / np.sqrt(len(x))); h = len(x) // 2
    y = (m.groupby("d").back.mean() - m.groupby("d").cback.mean()).dropna(); ty = y.mean() / (y.std(ddof=1) / np.sqrt(len(y)))
    print(f"{label:16} n {len(m):4}  fell back under in 10d: pivot {m.back.mean()*100:4.1f}% vs breakout {m.cback.mean()*100:4.1f}% (t {ty:5.2f})  | 21d: pivot {m.f21.mean()*100:+5.2f}% vs {m.cf21.mean()*100:+5.2f}%  diff {x.mean()*100:+5.2f}% t {t:5.2f} halves {x.iloc[:h].mean()*100:+5.2f}/{x.iloc[h:].mean()*100:+5.2f}")
rep2(B, "ALL pops")
for vb, nm in enumerate(["volume <1x", "volume 1-2x", "volume >2x"]): rep2(B[B.vb == vb], nm)
for rb, nm in enumerate(["run-up <20%", "run-up 20-50%", "run-up >50%"]): rep2(B[B.rb == rb], nm)
rep2(B[B.kind == "floor"], "old floor"); rep2(B[B.kind == "peak"], "old peak")
