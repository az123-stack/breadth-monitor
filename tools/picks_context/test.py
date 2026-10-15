"""Does group / money-flow context improve Trade Setups signals? Each past signal (actionable 5-session result, fwd_next) is
tagged with its sub-theme's state on the signal date. with vs without, Welch t; also inside weak breadth and outflow episodes."""
import pickle, sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/claude/breadth-monitor")
S = pickle.load(open("tools/picks_context/signals.pkl", "rb"))
S = S[S.fwd_next.notna()].drop_duplicates(["i", "t", "setup"]).copy()
D = pickle.load(open("tools/ignition_study/frames.pkl", "rb"))
subs = pd.read_csv("data/subthemes.csv"); g_of = dict(zip(subs.ticker, subs.subtheme))
I, rel = D["I"], D["rel"]; dates = I.index
n_ign = D["idxhi40"].astype(int) + (D["acc"] > 0.25) + (D["br21"] >= 0.8) + (D["drk"] >= 0.30)
def ev(m, gap=20):
    m = m.fillna(False).astype(bool); return m & ~(m.shift(1).astype(float).rolling(gap, min_periods=1).max().fillna(0) > 0)
ign = ev(n_ign == 4); ign20 = ign.astype(float).rolling(20, min_periods=1).max() > 0
lead = (D["rsmed"] >= 70) | (D["near"] >= 0.25)
r5 = rel / rel.shift(5) - 1; q = r5.rank(axis=1, pct=True)
br = pd.read_csv("data/breadth.csv", parse_dates=["date"]).set_index("date").reindex(dates)
ds, ds5 = br["dn_share"], br["dn_share"].rolling(5).mean()
outflow_tier = (D["rrgx"] < 100) & (D["acc"] < -0.15)
ctx = {"grp ignited (20d)": ign20, "grp ignited + leaders": ign20 & lead, "grp has leaders": lead, "grp warming 3+/4": n_ign >= 3,
       "grp confirmed tier": D["conf"] > 0, "grp leading&accel": D["lead"] > 0, "grp flow > +0.25": D["acc"] > 0.25,
       "grp outflow tier": outflow_tier, "grp held up (top 20% 5d)": q >= 0.8, "grp sold hardest (bottom 20% 5d)": q <= 0.2,
       "grp breadth >= 80%": D["br21"] >= 0.8}
S["d"] = pd.to_datetime(S.date); S["g"] = S.t.map(g_of)
S = S[S.g.isin(I.columns) & S.d.isin(dates)]
for k, f in ctx.items():
    S[k] = [bool(f.at[d, g]) if pd.notna(f.at[d, g]) else False for d, g in zip(S.d, S.g)]
S["mkt heavy-out day (>=60%)"] = S.d.map(ds) >= 60
S["mkt outflow episode (5d>=55)"] = S.d.map(ds5) >= 55
S["mkt calm in (<=40%)"] = S.d.map(ds) <= 40
def rep(df, lab):
    print(f"\n=== {lab}: n {len(df)}, avg {df.fwd_next.mean()*100:+.2f}% ===")
    for k in list(ctx) + ["mkt heavy-out day (>=60%)", "mkt outflow episode (5d>=55)", "mkt calm in (<=40%)"]:
        a, b = df.loc[df[k], "fwd_next"], df.loc[~df[k], "fwd_next"]
        if len(a) < 15 or len(b) < 15: print(f"  {k:36s} n {len(a)}"); continue
        se = np.sqrt(a.var() / len(a) + b.var() / len(b)); t = (a.mean() - b.mean()) / se
        # halves
        mid = df.d.sort_values().iloc[len(df) // 2]
        h = [df[(df.d < mid) & df[k]].fwd_next.mean() - df[(df.d < mid) & ~df[k]].fwd_next.mean(), df[(df.d >= mid) & df[k]].fwd_next.mean() - df[(df.d >= mid) & ~df[k]].fwd_next.mean()]
        print(f"  {k:36s} n {len(a):5d} with {a.mean()*100:+5.2f}% vs {b.mean()*100:+5.2f}%  diff {(a.mean()-b.mean())*100:+5.2f} t {t:+5.1f} | halves {h[0]*100:+.2f} / {h[1]*100:+.2f} | win {(a>0).mean()*100:.0f}%")
rep(S, "ALL setups")
rep(S[S.regime == "weak"], "WEAK breadth")
rep(S[S["mkt outflow episode (5d>=55)"]], "During outflow episodes")
# picks proxy: actionable only
rep(S[S.trig_adr <= 1.0], "ACTIONABLE (pick pool)")
pickle.dump(S, open("tools/picks_context/joined.pkl", "wb"))
