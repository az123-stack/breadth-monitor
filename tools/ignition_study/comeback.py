"""After money leaves the market (outflow streak), where does it go when it comes back? And while it keeps leaving, what holds up?
Outflow streak day: 5-day avg of dn_share (% of $ volume in falling stocks) >= 57. Comeback day: dn_share <= 40 within 10 sessions
of a streak day (first in 10). Continuation: streak day that is itself >= 60 (first in 5). Baskets by each group's 5-session move vs
SPY into the event (sold hardest = bottom 20%, held up = top 20%) and 60-session leaders (top 20% of 60-session rel move, measured
10 sessions before the event). Outcome: group vs SPY next 5/10/20 sessions; SPY absolute."""
import pickle, numpy as np, pandas as pd
D = pickle.load(open("frames.pkl", "rb")); rel, spy = D["rel"], D["spy"]; dates = rel.index
br = pd.read_csv("/home/claude/breadth-monitor/data/breadth.csv", parse_dates=["date"]).set_index("date").reindex(dates)
ds = br["dn_share"]; ds5 = ds.rolling(5).mean()
streak = ds5 >= 57
near = streak.rolling(10, min_periods=1).max().shift(1).fillna(0) > 0
def first(m, gap):
    m = m.fillna(False); return m & ~(m.shift(1).astype(float).rolling(gap, min_periods=1).max().fillna(0) > 0)
come = first((ds <= 40) & near, 10); cont = first(streak & (ds >= 60), 5)
r5 = rel / rel.shift(5) - 1; r60 = (rel / rel.shift(60) - 1).shift(10)
fw = {n: rel.shift(-n) / rel - 1 for n in (5, 10, 20)}; sp = {n: spy.shift(-n) / spy - 1 for n in (5, 10, 20)}
def baskets(ev, lab):
    idx = [d for d in dates[ev.to_numpy()] if d >= dates[70]]
    print(f"\n=== {lab}: {len(idx)} events ===", [d.strftime('%Y-%m-%d') for d in idx])
    print("SPY next 5/10/20: " + " / ".join(f"{np.nanmean([sp[n][d] for d in idx])*100:+.1f}%" for n in (5, 10, 20)) +
          "  (all days " + " / ".join(f"{sp[n].loc[dates[70]:].mean()*100:+.1f}%" for n in (5, 10, 20)) + ")")
    rows = {k: {n: [] for n in (5, 10, 20)} for k in ("sold hardest (5d)", "held up best (5d)", "middle", "60d leaders", "60d laggards", "60d leaders sold hardest")}
    for d in idx:
        a, L = r5.loc[d].dropna(), r60.loc[d].dropna()
        lo, hi = a.quantile(0.2), a.quantile(0.8); llo, lhi = L.quantile(0.2), L.quantile(0.8)
        sets = {"sold hardest (5d)": a[a <= lo].index, "held up best (5d)": a[a >= hi].index, "middle": a[(a > lo) & (a < hi)].index,
                "60d leaders": L[L >= lhi].index, "60d laggards": L[L <= llo].index,
                "60d leaders sold hardest": [g for g in L[L >= lhi].index if g in a.index and a[g] <= a.median()]}
        for k, gs in sets.items():
            for n in (5, 10, 20):
                v = fw[n].loc[d, list(gs)].dropna()
                if len(v): rows[k][n].append(v.mean())
    for k, r in rows.items():
        print(f"  {k:26s} " + "  ".join(f"{n:2d}d {np.mean(r[n])*100:+5.1f}% (win {np.mean(np.array(r[n])>0)*100:3.0f}%, n {len(r[n])})" for n in (5, 10, 20)))
baskets(come, "COMEBACK (money returns)"); baskets(cont, "CONTINUATION (money keeps leaving)")
print("\nstreak days total", int(streak.sum()), "latest ds5", round(ds5.iloc[-1], 1), "last 5 ds", ds.iloc[-5:].round(1).tolist())
# robustness: medians, and continuation excluding the Mar-Apr 2025 crash
def quick(ev, lab, excl=False):
    idx = [d for d in dates[ev.to_numpy()] if d >= dates[70] and not (excl and pd.Timestamp("2025-03-01") <= d <= pd.Timestamp("2025-04-30"))]
    s, h, spx = [], [], []
    for d in idx:
        a = r5.loc[d].dropna(); lo, hi = a.quantile(.2), a.quantile(.8)
        s.append(fw[10].loc[d, a[a <= lo].index].mean()); h.append(fw[10].loc[d, a[a >= hi].index].mean()); spx.append(sp[10][d])
    print(f"{lab:40s} n {len(idx):2d} | 10d sold-hardest mean {np.nanmean(s)*100:+.1f}% median {np.nanmedian(s)*100:+.1f}% | held-up mean {np.nanmean(h)*100:+.1f}% median {np.nanmedian(h)*100:+.1f}% | SPY median {np.nanmedian(spx)*100:+.1f}%")
quick(come, "comeback"); quick(cont, "continuation"); quick(cont, "continuation ex Mar-Apr 2025", True)
# also simple: any day >= 70% (no streak needed)
quick(first(ds >= 70, 5), "any 70%+ day")
