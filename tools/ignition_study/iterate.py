"""Iterate on ignition after the cybersecurity case study: gate variants, first vs re-ignition, extension, group thrust from a washout.
Train = first half of event dates, test = second half. Outcome = group vs SPY over next 20 / 40 sessions."""
import sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/home/claude/breadth-monitor")
from breadth import metrics as M
D = pickle.load(open("frames.pkl", "rb"))
I, rel = D["I"], D["rel"]; dates = I.index
br = pd.read_csv("/home/claude/breadth-monitor/data/breadth.csv", parse_dates=["date"])
hist = br.copy(); br = br.set_index("date").reindex(dates)
tw = pd.Series(M.thrust_window(hist, list(dates)), index=dates)
r10 = br["ratio10"]
def col(s): return pd.DataFrame(np.repeat(s.to_numpy()[:, None], I.shape[1], 1), index=dates, columns=I.columns)
n_ign = D["idxhi40"].astype(int) + (D["acc"] > 0.25) + (D["br21"] >= 0.8) + (D["drk"] >= 0.30)
def ev(m, gap=20):
    m = m.fillna(False).astype(bool); return m & ~(m.shift(1).astype(float).rolling(gap, min_periods=1).max().fillna(0) > 0)
IGN = ev(n_ign == 4)
fwd = {n: rel.shift(-n) / rel - 1 for n in (20, 40)}
warm = dates[120]; mid = dates[120 + (len(dates) - 120 - 20) // 2]
def st(e, n=20, lab=""):
    out = [f"{lab:44s}"]
    b = fwd[n].loc[warm:].stack().dropna()
    for a, z in (("all", (warm, dates[-1])), ("train", (warm, mid)), ("test", (mid, dates[-1]))):
        x = fwd[n].where(e).loc[z[0]:z[1]].stack().dropna()
        if x.size < 5: out.append(f"{a} n{x.size:3d}"); continue
        t = (x.mean() - b.mean()) / (x.std() / np.sqrt(x.size))
        out.append(f"{a} n{x.size:3d} {x.mean()*100:+5.1f}% w{(x>0).mean()*100:3.0f} t{t:+.1f}")
    print(" | ".join(out))
print("split", warm.date(), mid.date(), dates[-1].date())
for n in (20, 40):
    print(f"\n--- {n} sessions ---"); b = fwd[n].loc[warm:].stack().dropna(); print(f"base {b.mean()*100:+.2f}%")
    st(IGN, n, "IGNITION (all)")
    st(IGN & col(r10 >= 1.5), n, "gate now: ratio10 >= 1.5 today")
    st(IGN & ~col(r10 >= 1.5), n, "  not strong today")
    s15 = r10.rolling(15, min_periods=1).max() >= 1.5
    st(IGN & col(s15), n, "gate: ratio10 >= 1.5 any day in last 15")
    st(IGN & ~col(s15), n, "  neither")
    st(IGN & col(tw), n, "gate: post-thrust window (25 sessions)")
    st(IGN & col(tw | (r10 >= 1.5)), n, "gate: strong today OR post-thrust")
    st(IGN & ~col(tw | (r10 >= 1.5)), n, "  neither")
    # first vs re-ignition
    prior = IGN.shift(1).astype(float).rolling(60, min_periods=1).max().fillna(0) > 0
    st(IGN & ~prior, n, "first ignition in 60 sessions")
    st(IGN & prior, n, "re-ignition (another within 60)")
    # extension: index vs 50-day SMA, run off the 120-day low
    ext = I / I.rolling(50).mean() - 1; run = I / I.rolling(120).min() - 1
    st(IGN & (ext <= 0.10), n, "ext <= 10% above 50-day")
    st(IGN & (ext > 0.10), n, "ext > 10% above 50-day")
    st(IGN & (run <= 0.40), n, "run off 120d low <= 40%")
    st(IGN & (run > 0.40), n, "run off 120d low > 40%")
    # depth before: was the group in a deep drawdown in the prior 60 sessions?
    dd = (I / I.rolling(252, min_periods=120).max() - 1).rolling(60).min()
    st(IGN & (dd <= -0.25), n, "came from a 25%+ drawdown (60d)")
    st(IGN & (dd > -0.25), n, "no deep drawdown")
    # group breadth thrust from washout
    th = ev((D["br21"] >= 0.8) & (D["br21"].rolling(10).min() <= 0.2))
    st(th, n, "GROUP THRUST (<=20% -> 80% in 10d)")
    st(th & (dd <= -0.25), n, "  + after 25%+ drawdown")
    st(th & col(tw | (r10 >= 1.5)), n, "  + market strong/post-thrust")
    st(th & (D["acc"] > 0.25), n, "  + flow > 0.25")
    # member RS and near-high
    st(IGN & (D["rsmed"] >= 70), n, "IGN + member RS median >= 70")
    st(IGN & (D["rsmed"] < 70), n, "IGN + member RS median < 70")
    st(IGN & (D["near"] >= 0.25), n, "IGN + 25%+ members within 3% of 52w hi")
    st(IGN & (D["near"] < 0.25), n, "IGN + <25% near hi")
    st(IGN & (D["rng40"] <= 0.15), n, "IGN + 40d range <= 15% (tight base)")
    st(IGN & (D["rng40"] > 0.15), n, "IGN + 40d range > 15%")
    st(IGN & (D["conf"] > 0), n, "IGN + confirmed tier same day")
