import numpy as np, pandas as pd
P = "/tmp/pivot_study/"
ev = pd.read_parquet(P + "events.parquet"); F = pd.read_pickle(P + "frames.pkl")
O, H, L, C, spy, dv50, adr = F["O"], F["H"], F["L"], F["C"], F["spy"], F["dv50"], F["adr"]
n = len(C); cols = list(C.columns); Ov, Hv, Lv, Cv = O.to_numpy(), H.to_numpy(), L.to_numpy(), C.to_numpy()
spy50 = spy.ewm(span=50, adjust=False).mean()
def fwd(d, j, k):
    if d + k >= n: return np.nan
    e = Ov[d + 1, j]; return Cv[d + k, j] / e - 1 if e > 0 else np.nan
def spyf(d, k): return spy.iat[d + k] / spy.iat[d + 1] - 1 if d + k < n else np.nan   # SPY close-to-close approx
def path(d, j, lvl, k=10):
    cc = Cv[d:d + k + 1, j]; ll = Lv[d + 1:d + k + 1, j]
    if len(cc) < k + 1: return None, np.nan
    ab = np.flatnonzero(cc > lvl)
    if not len(ab): st = "reject"
    else:
        st = "popfail" if np.any(cc[ab[0] + 1:] < lvl) else "hold"
    dd = (np.nanmin(ll) / Cv[d, j] - 1)
    return st, dd
ev["j"] = [cols.index(t) for t in ev.t]
for k in (5, 21, 63):
    ev[f"f{k}"] = [fwd(d, j, k) for d, j in zip(ev.d, ev.j)]
    ev[f"s{k}"] = [spyf(d, k) for d in ev.d]
pp = [path(d, j, l) for d, j, l in zip(ev.d, ev.j, ev.lvl)]
ev["path"] = [p[0] for p in pp]; ev["dd10"] = [p[1] for p in pp]; ev["dd10_adr"] = ev.dd10 / ev.adr
ev["spy_up"] = [spy.iat[d] > spy50.iat[d] for d in ev.d]
# ---- control: same-date stocks making a 20-day high while within 3% of their own 2-year high (no overhead supply) ----
hi20 = H.rolling(20).max().shift(1); allhi = H.cummax().shift(1)
ctrl_mask = (H > hi20) & (C >= allhi * 0.97) & (C >= 5) & (dv50 >= 20e6) & (np.arange(n)[:, None] >= 250)
cm = ctrl_mask.to_numpy()
crow = []
for d in sorted(ev.d.unique()):
    js = np.flatnonzero(cm[d])
    for j in js:
        lvl = hi20.iat[d, j]
        st, dd = path(d, j, lvl)
        crow.append(dict(d=d, j=j, f5=fwd(d, j, 5), f21=fwd(d, j, 21), f63=fwd(d, j, 63), path=st, dd10=dd, adr=adr.iat[d, j]))
ct = pd.DataFrame(crow); ct["dd10_adr"] = ct.dd10 / ct.adr
# ---- market: all tradeable stocks same date ----
trad = ((C >= 5) & (dv50 >= 20e6)).to_numpy()
def mkt(d, k):
    if d + k >= n: return np.nan
    js = np.flatnonzero(trad[d]); r = Cv[d + k, js] / Ov[d + 1, js] - 1
    return np.nanmean(r)
for k in (5, 21, 63):
    ev[f"m{k}"] = [mkt(d, k) for d in ev.d]
ev.to_parquet(P + "ev_out.parquet"); ct.to_parquet(P + "ct_out.parquet")

def paired(a, b, k, label):
    """per-date mean of events minus per-date mean of controls (dates with both)."""
    A = a.groupby("d")[f"f{k}"].mean(); B = b.groupby("d")[f"f{k}"].mean()
    x = (A - B).dropna()
    if len(x) < 5: return f"{label:38} n/a"
    t = x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
    h = len(x) // 2; h1, h2 = x.iloc[:h].mean(), x.iloc[h:].mean()
    return f"{label:38} ev {A.reindex(x.index).mean()*100:+6.2f}%  ctrl {B.reindex(x.index).mean()*100:+6.2f}%  diff {x.mean()*100:+6.2f}%  t {t:5.2f}  halves {h1*100:+5.2f}/{h2*100:+5.2f}  dates {len(x)}"
print(f"EVENTS {len(ev)} · {ev.t.nunique()} stocks · {ev.date.nunique()} dates · {ev.date.min().date()} to {ev.date.max().date()}")
print("\n== 10-session path after touching the pivot ==")
print("pivot :", ev.path.value_counts(normalize=True).round(3).to_dict(), " median low in 10d", round(ev.dd10.median()*100,1), "% =", round(ev.dd10_adr.median(),2), "ADR")
print("ctrl  :", ct.path.value_counts(normalize=True).round(3).to_dict(), " median low in 10d", round(ct.dd10.median()*100,1), "% =", round(ct.dd10_adr.median(),2), "ADR")
print("\n== forward returns from next open: pivot touch vs clear-skies 20-day-high breakouts, same dates ==")
for k in (5, 21, 63): print(paired(ev, ct, k, f"{k}d all"))
print("\n== vs average tradeable stock, same dates ==")
for k in (5, 21, 63):
    x = (ev.groupby("d")[f"f{k}"].mean() - ev.groupby("d")[f"m{k}"].mean()).dropna()
    t = x.mean() / (x.std(ddof=1) / np.sqrt(len(x))); h = len(x)//2
    print(f"{k}d  ev-mkt {x.mean()*100:+.2f}%  t {t:.2f}  halves {x.iloc[:h].mean()*100:+.2f}/{x.iloc[h:].mean()*100:+.2f}  dates {len(x)}")
print("\n== splits (pivot touch minus clear-skies control, 21d) ==")
splits = {
 "touch-day volume <1x": ev.rvol < 1, "touch-day volume 1-2x": ev.rvol.between(1, 2), "touch-day volume >2x": ev.rvol > 2,
 "run-up 21d <20%": ev.run21 < .2, "run-up 21d 20-50%": ev.run21.between(.2, .5), "run-up 21d >50%": ev.run21 > .5,
 "round trip 25-40%": ev.depth < .4, "round trip 40-60%": ev.depth.between(.4, .6), "round trip >60%": ev.depth > .6,
 "pivot age 60-120": ev.age < 120, "pivot age 120-250": ev.age.between(120, 250), "pivot age >250": ev.age > 250,
 "old peak": ev.kind == "peak", "old floor (broken support)": ev.kind == "floor",
 "closed ABOVE level on touch day": ev.closed_above, "closed below on touch day": ~ev.closed_above,
 "SPY above 50 EMA": ev.spy_up, "SPY below 50 EMA": ~ev.spy_up}
for nm, m in splits.items():
    s = ev[m]
    print(paired(s, ct, 21, f"{nm} (n {len(s)})"), "| reject/popfail/hold", s.path.value_counts(normalize=True).reindex(["reject","popfail","hold"]).round(2).tolist())
print("\n== 5d splits by path is look-ahead, so instead: touch-day close above vs below, 5d ==")
for nm in ["closed ABOVE level on touch day", "closed below on touch day", "touch-day volume >2x", "run-up 21d >50%"]:
    print(paired(ev[splits[nm]], ct, 5, nm))
