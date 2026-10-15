"""Replay a simple top-2-per-day pick rule on past actionable signals: current (highest RS, ties on 60-day gain, one per
sub-theme) vs context-ranked (score = +1 group ignited in 20d with leaders, +1 group sold hardest during an outflow episode,
-1 group held up best during an outflow episode; then RS). Halves reported."""
import pickle, numpy as np, pandas as pd
S = pickle.load(open("tools/picks_context/joined.pkl", "rb"))
S = S[S.trig_adr <= 1.0].copy()
ep = S["mkt outflow episode (5d>=55)"]
S["ctx"] = S["grp ignited + leaders"].astype(int) + (S["grp sold hardest (bottom 20% 5d)"] & ep).astype(int) - (S["grp held up (top 20% 5d)"] & ep).astype(int)
S["ctx2"] = S["grp ignited + leaders"].astype(int)
def pick(df, keys):
    out = []
    for d, g in df.sort_values(keys, ascending=False).groupby("d", sort=False):
        seen, n = set(), 0
        for _, r in g.iterrows():
            if r.g in seen: continue
            seen.add(r.g); out.append(r); n += 1
            if n == 2: break
    return pd.DataFrame(out)
mid = S.d.sort_values().iloc[len(S) // 2]
for lab, keys in [("current: RS, d60", ["rs", "d60"]), ("context: ctx, RS, d60", ["ctx", "rs", "d60"]), ("ignition only: ctx2, RS", ["ctx2", "rs", "d60"])]:
    P = pick(S, keys)
    a, b = P[P.d < mid].fwd_next, P[P.d >= mid].fwd_next
    print(f"{lab:28s} n {len(P)} avg {P.fwd_next.mean()*100:+.2f}% med {P.fwd_next.median()*100:+.2f}% win {(P.fwd_next>0).mean()*100:.0f}% | halves {a.mean()*100:+.2f}% / {b.mean()*100:+.2f}% | weak {P[P.regime=='weak'].fwd_next.mean()*100:+.2f}% (n {(P.regime=='weak').sum()})")
print("all actionable avg", round(S.fwd_next.mean()*100, 2))
