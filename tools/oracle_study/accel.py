"""Accelerating sub-themes study (Oct 31, 2026; Adam on Oracle: catch runners like Cloud Communications early —
the relative line vs SPY speeding up on 60 and 15 sessions, like Defense IT / IT Services on Oct 30).

Sub-theme = equal-weight index (mean daily return of members, clipped like oracle.py). rel = index / SPY.
Pace over N sessions = (rel_t / rel_{t-N} - 1) / N. Signal variants on every date; outcome = group return over the next
20 / 40 / 60 sessions (from the next close) minus the average group's. Unit = dates (every 5th, so windows overlap less)."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, ".")
from breadth import store

bars = store.apply_splits(store.load_bars(), store.load_splits())
C = bars.pivot_table(index="date", columns="ticker", values="c").sort_index()
V = bars.pivot_table(index="date", columns="ticker", values="v").sort_index().reindex_like(C)
dv = (C * V).rolling(50, min_periods=20).mean()
sub = store.load_subthemes()
col = "subtheme" if "subtheme" in sub.columns else sub.columns[1]
R = C.pct_change(fill_method=None).clip(-0.5, 1.0)
liq = (C >= 5) & (dv >= 10e6)
idx = {}
for g, d in sub.groupby(col):
    m = [t for t in d["ticker"] if t in C.columns]
    if len(m) < 3: continue
    r = R[m].where(liq[m].shift(1))           # members liquid as of the prior day (no look-ahead)
    ok = r.notna().sum(axis=1) >= 3
    idx[g] = (1 + r.mean(axis=1).where(ok).fillna(0)).cumprod()
I = pd.DataFrame(idx)
spy = C["SPY"]
rel = I.div(spy, axis=0)
def pace(n): return (rel / rel.shift(n) - 1) / n
p15, p60, p180 = pace(15), pace(60), pace(180)
s15, s60, s180 = rel / rel.shift(15) - 1, rel / rel.shift(60) - 1, rel / rel.shift(180) - 1
hi60 = rel >= rel.rolling(60).max() * 0.97          # rel line within 3% of its 60-session high
sig = {
  "accel (15 pace > 60 pace > 180 pace, 15/60 > 0)": (s15 > 0) & (s60 > 0) & (p15 > p60) & (p60 > p180),
  "accel + rel near 60d high": (s15 > 0) & (s60 > 0) & (p15 > p60) & (p60 > p180) & hi60,
  "accel + 60d vs SPY >= +10%": (s15 > 0) & (s60 >= 0.10) & (p15 > p60) & (p60 > p180),
  "accel early (180d vs SPY < +25%)": (s15 > 0) & (s60 >= 0.10) & (p15 > p60) & (p60 > p180) & (s180 < 0.25),
  "accel running (180d vs SPY >= +25%)": (s15 > 0) & (s60 >= 0.10) & (p15 > p60) & (p60 > p180) & (s180 >= 0.25),
  "just 60d vs SPY top 20%": s60.rank(axis=1, pct=True) >= 0.8,
  "just 15d vs SPY top 20%": s15.rank(axis=1, pct=True) >= 0.8,
}
dates = rel.index
out = {}
for H in (20, 40, 60):
    fwd = I.shift(-H) / I - 1
    ex = fwd.sub(fwd.mean(axis=1), axis=0)          # vs the average group
    out[H] = ex
use = [d for k, d in enumerate(dates) if k >= 180 and k % 5 == 0]
print(f"{len(I.columns)} sub-themes, dates {dates[180].date()} → {dates[-1].date()}")
for name, S in sig.items():
    row = [name[:44].ljust(44)]
    for H in (20, 40, 60):
        vals = []
        for d in use:
            k = dates.get_loc(d)
            if k + H >= len(dates): continue
            m = S.loc[d].fillna(False)
            if m.sum() == 0: continue
            vals.append((d, out[H].loc[d][m].mean(), m.sum()))
        if not vals: row.append("–"); continue
        v = np.array([x[1] for x in vals]); h = len(v) // 2
        t = v.mean() / (v.std(ddof=1) / np.sqrt(len(v))) if len(v) > 2 else np.nan
        row.append(f"{H}d {v.mean()*100:+.1f}% t{t:.1f} n{len(v)} [{v[:h].mean()*100:+.1f}/{v[h:].mean()*100:+.1f}] ~{np.mean([x[2] for x in vals]):.0f}g")
    print(" | ".join(row))
# when did Cloud Communications / Defense IT / IT Services first fire (accel + 60d >= 10%)?
S = sig["accel + 60d vs SPY >= +10%"]
for g in [c for c in I.columns if any(k in c for k in ("Cloud Comm", "Defense IT", "IT Services"))]:
    on = S[g][S[g].fillna(False)].index
    first = [d.date() for k, d in enumerate(on) if k == 0 or (on[k] - on[k-1]).days > 30]
    print(g, "fires:", len(on), "days; episode starts", first[-6:])
    print("   rel line:", {str(d.date()): round(float(rel[g].loc[d] / rel[g].iloc[0]), 2) for d in rel.index[::40]})
print("today:", list(S.iloc[-1][S.iloc[-1].fillna(False)].index))

# ---- does acceleration add anything beyond plain 60-day relative strength? date-paired, same dates ----
print("\nControl: groups up 10%+ vs SPY over 60 sessions — accelerating vs not (date-paired difference)")
A = (s15 > 0) & (p15 > p60) & (p60 > p180)
base = s60 >= 0.10
for H in (20, 40, 60):
    dif = []
    for d in use:
        k = dates.get_loc(d)
        if k + H >= len(dates): continue
        a = (base.loc[d] & A.loc[d]).fillna(False); b = (base.loc[d] & ~A.loc[d]).fillna(False)
        if a.sum() and b.sum(): dif.append(out[H].loc[d][a].mean() - out[H].loc[d][b].mean())
    v = np.array(dif); h = len(v) // 2
    print(f"  {H}d accel minus not {v.mean()*100:+.1f} pts t{v.mean()/(v.std(ddof=1)/np.sqrt(len(v))):.1f} n{len(v)} halves {v[:h].mean()*100:+.1f}/{v[h:].mean()*100:+.1f}")
top = s60.rank(axis=1, pct=True) >= 0.8
print("Control 2: inside the 60-day top 20%: accelerating vs not")
for H in (20, 40, 60):
    dif = []
    for d in use:
        k = dates.get_loc(d)
        if k + H >= len(dates): continue
        a = (top.loc[d] & A.loc[d]).fillna(False); b = (top.loc[d] & ~A.loc[d]).fillna(False)
        if a.sum() and b.sum(): dif.append(out[H].loc[d][a].mean() - out[H].loc[d][b].mean())
    v = np.array(dif); h = len(v) // 2
    print(f"  {H}d accel minus not {v.mean()*100:+.1f} pts t{v.mean()/(v.std(ddof=1)/np.sqrt(len(v))):.1f} n{len(v)} halves {v[:h].mean()*100:+.1f}/{v[h:].mean()*100:+.1f}")
# independent episodes: count group runs of the main signal (gap > 30 days = new episode) and their 60d outcome
S = sig["accel + 60d vs SPY >= +10%"]; ep = []
for g in S.columns:
    on = S[g][S[g].fillna(False)].index
    for k, d in enumerate(on):
        if k == 0 or (on[k] - on[k-1]).days > 30:
            j = dates.get_loc(d)
            if j + 60 < len(dates): ep.append((g, d.date(), out[60].loc[d][g]))
e = np.array([x[2] for x in ep]); print(f"\nEpisodes (first day per group, 30-day gap): n {len(e)}, 60d vs avg group mean {e.mean()*100:+.1f}%, median {np.median(e)*100:+.1f}%, beat {np.mean(e>0)*100:.0f}%, worst {e.min()*100:+.0f}%")
for x in sorted(ep, key=lambda x: -x[2])[:5]: print("  best", x[0], x[1], f"{x[2]*100:+.0f}%")
for x in sorted(ep, key=lambda x: x[2])[:3]: print("  worst", x[0], x[1], f"{x[2]*100:+.0f}%")
