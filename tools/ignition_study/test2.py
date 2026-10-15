import pickle, json, pandas as pd, numpy as np, sys
sys.path.insert(0, "/home/claude/breadth-monitor")
from breadth import macro as MC
D = pickle.load(open("frames.pkl","rb"))
rel = D["rel"]; dates = rel.index; warm = dates[60]
fwd = {n: rel.shift(-n) / rel - 1 for n in (10, 20, 40)}
br = pd.read_csv("/home/claude/breadth-monitor/data/breadth.csv", parse_dates=["date"]).set_index("date").reindex(dates)
def events(mask, gap=20):
    m = mask.fillna(False).astype(bool); prior = m.shift(1).astype(float).rolling(gap, min_periods=1).max().fillna(0) > 0
    return m & ~prior
def st(ev, n=20):
    v = fwd[n].where(ev).stack().dropna()
    if v.size < 5: return f"n {v.size}"
    b = fwd[n].loc[warm:].stack().dropna()
    t = (v.mean() - b.mean()) / (v.std() / np.sqrt(v.size))
    return f"n {v.size:4d}  avg {v.mean()*100:+5.2f}%  median {v.median()*100:+5.2f}%  win {(v>0).mean()*100:3.0f}%  edge vs base {(v.mean()-b.mean())*100:+5.2f} pts  t {t:+.1f}"
ign = D["idxhi40"].astype(bool) & (D["acc"] > 0.25) & (D["br21"] >= 0.8) & (D["drk"] >= 0.30)
rrg = (D["rrgx"] > 100) & (D["rrgy"] > 100)
b = fwd[20].loc[warm:].stack().dropna(); print(f"BASE 20d: avg {b.mean()*100:+.2f}% median {b.median()*100:+.2f}% win {(b>0).mean()*100:.0f}%")
E1 = events(ign.loc[warm:])
for n in (10, 20, 40): print(f"IGNITION {n}d:", st(E1, n))
print("rel 60d high 20d:", st(events(D["relhi60"].astype(bool).loc[warm:])))
print("base breakout 20d:", st(events(D["idxhi40"].astype(bool).loc[warm:])))
# market money context at the signal (breadth tab metrics, whole market)
inflow = (br["dn_share10"] <= 47).values[:, None]; outflow = (br["dn_share10"] > 47).values[:, None]
E1c = E1.reindex(dates).fillna(False)
print("\nIGNITION when market money 10d is net IN (selling share ≤ 47%):", st(E1c & inflow))
print("IGNITION when market money 10d is net OUT (> 47%):              ", st(E1c & outflow))
lead = (br["ratio10"] >= 1.5).values[:, None]
print("IGNITION in strong breadth (10-day ratio ≥ 1.5):", st(E1c & lead))
print("IGNITION otherwise:                              ", st(E1c & ~lead))
# macro driver confirmation for groups that have one
m = json.load(open("/home/claude/breadth-monitor/data/macro.json"))
ser = {k: pd.Series({pd.Timestamp(d): x for d, x in m[k]["rows"]}) for k in m if "rows" in m[k]}
if all(k in ser for k in ("gasoline","diesel","crude")): ser["crack"] = (2*ser["gasoline"]*42 + ser["diesel"]*42 - 3*ser["crude"]) / 3
drv = pd.DataFrame(False, index=dates, columns=rel.columns); has = pd.Series(False, index=rel.columns)
for key, sym, label, unit, etf, groups in MC.SERIES:
    s = ser.get(key)
    if s is None: continue
    s = s.reindex(dates).ffill(); up = (s / s.shift(20) - 1) >= (0.0 if key == "tnx" else 0.08)
    for g in groups:
        if g in drv.columns: drv[g] = drv[g] | up; has[g] = True
gd = [g for g in rel.columns if has[g]]
print(f"\nGroups with a macro driver: {len(gd)}  (macro history covers {ser['crude'].index[0].date()} →)")
E2 = E1c[gd]; dv = drv[gd]
print("IGNITION, driver group, driver up 8%+ in 20d:", st(E2 & dv))
print("IGNITION, driver group, driver NOT up:       ", st(E2 & ~dv))
# refiners ignition outcomes
g = "Refiners"; ev = E1c[g]
for d in ev[ev].index:
    print(g, d.date(), {n: round(float(fwd[n].at[d, g])*100, 1) if pd.notna(fwd[n].at[d, g]) else None for n in (10, 20, 40)})
