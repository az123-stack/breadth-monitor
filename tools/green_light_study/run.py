"""Green-light history (Nov 25, 2026; Adam: "when has the dashboard given the green light, how long did it last, what were the results").
Green = playbook state 'thrust' (25 sessions after a major breadth thrust / follow-through) or 'strong' (ratio5 and ratio10 >= 1.5).
Periods = runs of green sessions, gaps of <= 3 non-green sessions merged. Returns: close of first green day -> close of last green day,
and the 20 sessions after it ends. Equal-weight = median stock (breadth universe, $10+) from start to end."""
import sys, pandas as pd, numpy as np
sys.path.insert(0, ".")
from breadth import store, metrics

h = store.load_breadth()
h = h.set_index(pd.to_datetime(h["date"])) if "date" in h.columns else h
h.index = pd.to_datetime(h.index)
tw = metrics.thrust_window(h, h.index)
state = []
for i, (d, r) in enumerate(h.iterrows()):
    if tw[i]: state.append("thrust")
    elif r["ratio5"] >= 1.5 and r["ratio10"] >= 1.5: state.append("strong")
    elif r["ratio10"] < 1: state.append("weak")
    else: state.append("mixed")
st = pd.Series(state, index=h.index)
green = st.isin(["thrust", "strong"])
b = store.load_bars(); b["date"] = pd.to_datetime(b["date"])
c = b.drop_duplicates(["date", "ticker"]).set_index(["date", "ticker"])["c"].unstack()
etf = c[["SPY", "QQQ", "IWM", "RSP"]]
liq = c.drop(columns=["SPY", "QQQ", "IWM", "RSP"], errors="ignore")
# periods
runs, cur, gap = [], None, 0
for d, g in green.items():
    if g:
        if cur is None: cur = [d, d]
        else: cur[1] = d
        gap = 0
    elif cur is not None:
        gap += 1
        if gap > 3: runs.append(cur); cur, gap = None, 0
if cur: runs.append(cur)
dates = list(h.index)
ev = {pd.Timestamp(e["date"]): e for e in metrics.events(h) if e.get("tier") == "major" and e.get("kind") in ("thrust", "followthrough")}
rows = []
for a, z in runs:
    ia, iz = dates.index(a), dates.index(z)
    n = iz - ia + 1
    seg = st.iloc[ia:iz + 1]
    a0 = max(a, c.index[0]); z0 = c.index[c.index <= z][-1] if (c.index <= z).any() else None
    if z0 is None or z0 < a0: continue
    def ret(t, x, y):
        x, y = max(x, c.index[0]), c.index[c.index <= y][-1]
        try: return etf[t].loc[y] / etf[t].loc[x] - 1
        except KeyError: return np.nan
    spy = etf["SPY"].loc[a0:z0]
    dd = (spy / spy.cummax() - 1).min()
    s0 = liq.loc[a0]; s1 = liq.loc[z0]; ok = s0 >= 10
    med = (s1[ok] / s0[ok] - 1).median()
    after = dates[min(iz + 20, len(dates) - 1)]
    trig = [str(d.date()) for d in ev if a <= d <= z]
    rows.append({"start": a.date(), "partial": a < c.index[0], "end": z.date(), "sessions": n, "thrust_days": int((seg == "thrust").sum()),
                 "strong_days": int((seg == "strong").sum()), "triggers": ",".join(trig) or "ratio only",
                 "SPY": ret("SPY", a, z), "QQQ": ret("QQQ", a, z), "IWM": ret("IWM", a, z), "RSP": ret("RSP", a, z),
                 "median_stock": med, "SPY_maxDD": dd, "SPY_next20": ret("SPY", z, after) if iz + 1 < len(dates) else np.nan,
                 "open": z == dates[-1]})
df = pd.DataFrame(rows)
pd.set_option("display.width", 250)
fmt = df.copy()
for k in ["SPY", "QQQ", "IWM", "RSP", "median_stock", "SPY_maxDD", "SPY_next20"]: fmt[k] = (fmt[k] * 100).round(1)
print(fmt.to_string(index=False))
print("\nstate counts:", st.value_counts().to_dict(), "of", len(st), "sessions;", h.index[0].date(), "->", h.index[-1].date())
print("current:", st.iloc[-5:].to_dict())
# SPY daily return by state (next-day)
spy = etf["SPY"].reindex(h.index); fwd = spy.shift(-1) / spy - 1
print("SPY next-day avg % by state:", (fwd.groupby(st).mean() * 100).round(3).to_dict())
fwd20 = spy.shift(-20) / spy - 1
print("SPY next-20 avg % by state:", (fwd20.groupby(st).mean() * 100).round(2).to_dict(), "win", (fwd20.groupby(st).apply(lambda x: (x > 0).mean()) * 100).round(0).to_dict())
df.to_csv("tools/green_light_study/periods.csv", index=False)
