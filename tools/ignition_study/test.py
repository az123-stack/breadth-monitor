import pickle, pandas as pd, numpy as np
D = pickle.load(open("frames.pkl","rb"))
rel = D["rel"]; G = rel.columns
fwd = {n: rel.shift(-n) / rel - 1 for n in (10, 20, 40)}
dates = rel.index
br21 = D["br21"]; br_min10 = br21.rolling(10).min()
S = {
 "base breakout (40d high)": D["idxhi40"].astype(bool),
 "dollar flow > +0.25": D["acc"] > 0.25,
 "breadth 80%+ above 21EMA": br21 >= 0.8,
 "breadth thrust (≤20% → 80%+ in 10d)": (br21 >= 0.8) & (br_min10 <= 0.2),
 "RS rank jump (+30 pts in 10d)": D["drk"] >= 0.30,
 "rel. strength 60d high": D["relhi60"].astype(bool),
 "rotation graph: leading": (D["rrgx"] > 100) & (D["rrgy"] > 100),
 "confirmed inflow tier": D["conf"] > 0,
}
S["IGNITION: base breakout + flow + breadth + RS jump"] = S["base breakout (40d high)"] & S["dollar flow > +0.25"] & S["breadth 80%+ above 21EMA"] & S["RS rank jump (+30 pts in 10d)"]
S["IGNITION + rotation leading"] = S["IGNITION: base breakout + flow + breadth + RS jump"] & S["rotation graph: leading"]
S["EARLY: breadth thrust + rotation leading"] = S["breadth thrust (≤20% → 80%+ in 10d)"] & S["rotation graph: leading"]
first = 260  # need 252d for some inputs? use after warmup ~ day 60 for most; start where all exist
def events(mask, gap=20):
    m = mask.fillna(False).astype(bool)
    prior = m.shift(1).astype(float).rolling(gap, min_periods=1).max().fillna(0) > 0
    return m & ~prior
def summarize(ev, lo=None, hi=None):
    out = {}
    e = ev.copy()
    if lo is not None: e = e.loc[lo:hi]
    for n, f in fwd.items():
        v = f.reindex(e.index).where(e).stack().dropna()
        out[f"n"] = int(v.size) if n == 10 else out.get("n")
        out[f"rel{n}"] = round(v.mean()*100, 2) if v.size else None
        out[f"win{n}"] = round((v > 0).mean()*100) if v.size else None
    return out
warm = dates[60]
base = {}
for n, f in fwd.items():
    v = f.loc[warm:].stack(); base[f"rel{n}"] = round(v.mean()*100, 2); base[f"win{n}"] = round((v > 0).mean()*100)
print("BASE (any group, any day):", base)
rows = []
for k, m in S.items():
    ev = events(m.loc[warm:])
    r = summarize(ev); h1 = summarize(ev, dates[60], dates[280]); h2 = summarize(ev, dates[281], dates[-1])
    rows.append([k, r["n"], r["rel10"], r["win10"], r["rel20"], r["win20"], r["rel40"], r["win40"], h1["rel20"], h1["n"], h2["rel20"], h2["n"]])
df = pd.DataFrame(rows, columns=["signal","n","rel10%","win10","rel20%","win20","rel40%","win40","1st half rel20","n1","2nd half rel20","n2"])
pd.set_option("display.width", 250); print(df.to_string(index=False))
# Refiners hit dates for each
g = "Refiners"
for k, m in S.items():
    ev = events(m.loc[warm:])[g]; print(f"{k[:52]:52} ", [d.strftime('%Y-%m-%d') for d in ev[ev].index][-5:])
