import sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/home/claude/breadth-monitor")
from breadth import store, rotation as RO
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400)
D = pickle.load(open("frames.pkl", "rb")); members = D["members"]
bars = store.load_bars(); adj = store.apply_splits(bars, store.load_splits())
ticks = {t for v in members.values() for t in v} | {"SPY"}
c, h, v = RO._wide(adj, ticks); c.index = pd.to_datetime(c.index); v.index = c.index
I, rel = D["I"], D["rel"]; dv = c * v; hi10 = c.shift(1).rolling(10).max()
br = pd.read_csv("/home/claude/breadth-monitor/data/breadth.csv", parse_dates=["date"]).set_index("date").reindex(I.index)
def ev(m, gap=20):
    m = m.fillna(False).astype(bool); return m & ~(m.shift(1).astype(float).rolling(gap, min_periods=1).max().fillna(0) > 0)
for g in ["Cybersecurity Platforms", "Identity & Security Tools"]:
    t = [x for x in members[g] if x in c.columns]; n = c[t].notna().sum(axis=1).replace(0, np.nan)
    brk = (c[t] > hi10[t]).sum(axis=1) / n; d = dv[t].sum(axis=1); rv = d / d.rolling(50).mean().shift(1)
    r1 = rel[g] / rel[g].shift(1) - 1; off = I[g] / I[g].rolling(60).max() - 1
    X = pd.DataFrame({"idx": I[g], "rel": rel[g], "base": D["idxhi40"][g], "flow": D["acc"][g], "br21": D["br21"][g], "drk": D["drk"][g],
        "rk20": D["rk20"][g], "relhi60": D["relhi60"][g], "lead": D["lead"][g], "conf": D["conf"][g], "near": D["near"][g], "rsmed": D["rsmed"][g],
        "nh20": D["nh20"][g], "up4": D["up4"][g], "rng40": D["rng40"][g], "rrgx": D["rrgx"][g], "rrgy": D["rrgy"][g], "r1": r1, "rv": rv, "brk": brk, "off": off,
        "ratio10": br["ratio10"]})
    X["n_ign"] = X.base.astype(int) + (X.flow > 0.25) + (X.br21 >= 0.8) + (X.drk >= 0.30)
    X["IGN"] = ev(X.n_ign == 4); X["D1"] = ev((r1 >= .02) & (rv >= 1.3) & (brk >= .5) & (off.shift(1) <= -.03) & (off.shift(1) >= -.15))
    X["thrust"] = ev((X.br21 >= 0.8) & (X.br21.rolling(10).min() <= 0.2))
    X["f40"] = rel[g].shift(-40) / rel[g] - 1; X["f20"] = rel[g].shift(-20) / rel[g] - 1
    X["idx_pct_from_low"] = X.idx / X.idx.loc["2026-03-15":"2026-04-30"].min() - 1
    Y = X.loc["2026-03-20":]
    print("\n=====", g, "low", X.idx.loc["2026-03-15":"2026-04-30"].idxmin().date())
    cols = ["idx_pct_from_low", "rel", "n_ign", "base", "flow", "br21", "drk", "rk20", "relhi60", "lead", "conf", "near", "rsmed", "r1", "rv", "brk", "off", "IGN", "D1", "thrust", "ratio10", "f20", "f40"]
    show = Y[(Y.IGN) | (Y.D1) | (Y.thrust) | (Y.n_ign >= 3) | (Y.index.isin(Y.resample("W-FRI").last().index))]
    print(show[cols].round(2).to_string())
    pickle.dump(X, open(f"cy_{g[:5]}.pkl", "wb"))
