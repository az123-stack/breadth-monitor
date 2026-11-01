"""Special group pullbacks (Nov 1, 2026, Adam).

Idea: a sub-theme that is already top-tier on Theme Strength AND jumped a lot in
the last 5 sessions is "doing something special". Its leaders are usually
extended on that day. Does waiting for a pullback to the 8 / 21 EMA in the next
10 sessions beat (a) buying at the signal and (b) the same pullback in ordinary
or strong-but-not-accelerating groups?

Run from the repo root:  python tools/special_pullback/study.py
"""
import json
import numpy as np
import pandas as pd

from breadth import store, strength as S2, config

SPECIAL_STR, SPECIAL_JUMP = 85.0, 15.0
WAIT = 10          # sessions after the signal to wait for a pullback
GAP = 10           # first fire per group after this many quiet sessions
HOLD = (5, 20)
RS_MIN = 85

bars = store.apply_splits(store.load_bars(), store.load_splits())
w = S2.wide_all(bars)
c, h, l, o, v = w["c"], w["h"], w["l"], w["o"], w["v"]
dates = c.index
N = len(dates)
uni = set(store.load_universe())
uni_mask = pd.Series(c.columns.isin(list(uni)), index=c.columns)
liquid = (c >= config.MIN_PRICE) & (v.rolling(20, min_periods=15).mean() >= config.MIN_AVG_VOLUME) & uni_mask
tradeable = (c >= 5) & ((c * v).rolling(50, min_periods=30).mean() >= 20e6) & uni_mask
ratings, _, _ = S2.rs_ratings(c, liquid, list(range(63, N)))
ratings = ratings.reindex(index=dates)
ema8 = c.ewm(span=8, adjust=False, min_periods=8).mean()
ema21 = c.ewm(span=21, adjust=False, min_periods=21).mean()
ema50 = c.ewm(span=50, adjust=False, min_periods=50).mean()
adr = ((h / l - 1).rolling(20, min_periods=15).mean())          # fraction
spy = c["SPY"]

sub = store.load_subthemes()
members = {}
for r in sub.itertuples():
    members.setdefault(r.subtheme, []).append(r.ticker)

rows = list(range(91, N))
inp = S2.group_inputs_many(c, ema21, ema50, ratings, members, rows, spy)
STR = pd.DataFrame({dates[i]: S2.strength_scores(df) for i, df in inp.items()}).T.reindex(dates)

# market context
br = pd.read_csv(config.DATA_DIR / "breadth.csv", parse_dates=["date"]).set_index("date").reindex(dates)
thr = [pd.Timestamp(e["date"]) for e in json.load(open("docs/data.json"))["events"] if e["kind"] == "thrust"]
pos = {d: k for k, d in enumerate(dates)}
post_thrust = np.zeros(N, bool)
for d in thr:
    if d in pos:
        post_thrust[pos[d]:pos[d] + 26] = True

C, H, L, O = (x.to_numpy(float) for x in (c, h, l, o))
E8, E21, A = ema8.to_numpy(float), ema21.to_numpy(float), adr.to_numpy(float)
TR = tradeable.to_numpy(bool)
RT = ratings.to_numpy(float)
col = {t: k for k, t in enumerate(c.columns)}

# all-stock baseline return from open i to close i+n (mean of tradeable)
def base_ret(i, n):
    j = i + n - 1
    if j >= N:
        return np.nan
    m = TR[i - 1]
    r = C[j, m] / O[i, m] - 1
    r = r[np.isfinite(r)]
    return float(np.clip(r, -0.9, 3).mean()) if len(r) else np.nan

BASE = {n: {i: base_ret(i, n) for i in range(92, N)} for n in HOLD}


def trade(k, e):
    """Buy open e; returns dict of returns and R (stop 1 ADR under entry, 20 sessions)."""
    out = {}
    if e >= N:
        return None
    ent = O[e, k]
    a = A[e - 1, k]
    if not (np.isfinite(ent) and np.isfinite(a) and a > 0):
        return None
    for n in HOLD:
        j = e + n - 1
        out[f"x{n}"] = (C[j, k] / ent - 1 - BASE[n][e]) if j < N else np.nan
        out[f"r{n}"] = (C[j, k] / ent - 1) if j < N else np.nan
    j_end = min(e + 19, N - 1)
    if e + 19 >= N:
        out["R"] = np.nan
    else:
        stop = ent * (1 - a)
        hit = np.where(L[e:j_end + 1, k] <= stop)[0]
        out["R"] = -1.0 if len(hit) else min((C[j_end, k] / ent - 1) / a, 10)
    return out


def classify(g, i):
    s = STR.at[dates[i], g] if g in STR.columns else np.nan
    s5 = STR.at[dates[i - 5], g] if g in STR.columns else np.nan
    if not (np.isfinite(s) and np.isfinite(s5)):
        return None
    if s >= SPECIAL_STR and s - s5 >= SPECIAL_JUMP:
        return "special"
    if s >= SPECIAL_STR and s - s5 < 5:
        return "strong_steady"
    if 50 <= s < 75:
        return "ordinary"
    return None


recs = []
last_fire = {}
for i in range(97, N - 1):
    for g, tick in members.items():
        cls = classify(g, i)
        if cls is None:
            continue
        key = (g, cls)
        if key in last_fire and i - last_fire[key] < GAP:
            continue
        last_fire[key] = i
        for t in tick:
            k = col.get(t)
            if k is None or not TR[i, k] or not (RT[i, k] >= RS_MIN):
                continue
            base = dict(group=g, cls=cls, t=t, sig=dates[i], post=post_thrust[i],
                        ratio10=br["ratio10"].iloc[i], spy50=bool(C[i, col["SPY"]] > ema50.iloc[i]["SPY"]),
                        ext21=(C[i, k] / E21[i, k] - 1) / A[i, k])
            ch = trade(k, i + 1)
            if ch:
                recs.append({**base, "kind": "chase", "entry": dates[i + 1] if i + 1 < N else None, **ch})
            # pullback: first session in i+1..i+WAIT whose low comes within 0.25 ADR of the EMA,
            # and the close holds (no more than 0.5 ADR under it)
            for ema_name, E in (("pb8", E8), ("pb21", E21)):
                for j in range(i + 1, min(i + WAIT + 1, N - 1)):
                    a = A[j, k] * C[j, k]
                    if not np.isfinite(a):
                        break
                    if L[j, k] <= E[j, k] + 0.25 * a:
                        if C[j, k] >= E[j, k] - 0.5 * a:
                            tr = trade(k, j + 1)
                            if tr:
                                recs.append({**base, "kind": ema_name, "entry": dates[j + 1], "wait": j - i, **tr})
                        else:
                            recs.append({**base, "kind": ema_name + "_broke", "entry": None})
                        break

df = pd.DataFrame(recs)
df.to_csv("tools/special_pullback/trades.csv", index=False)
STR.to_csv("tools/special_pullback/strength_hist.csv")
print("dates", dates[97].date(), "->", dates[-1].date(), " signals by class:")
print(df[df.kind == "chase"].groupby("cls").agg(stocks=("t", "size"), groups=("group", "nunique"), dates=("sig", "nunique")))
