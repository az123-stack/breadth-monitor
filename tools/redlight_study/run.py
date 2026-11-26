"""Red light for longs (Nov 25, 2026; Adam: "run the studies"; ROADMAP #1). Each warning is a daily on/off flag known at that close.
Scored on what longs did NEXT: SPY next 10 sessions and a momentum-long proxy (median next-5 return of leaders = $10+, $20M+/day,
top 10% 63-day return, close above 21 EMA). Also: 'only long when the flag is off' vs always long (SPY), and the lead before each
5%+ pullback's trough plus how much of the fall it sidestepped."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, ".")
from breadth import store, macro, metrics

b = store.apply_splits(store.load_bars(), store.load_splits()); b["date"] = pd.to_datetime(b["date"])
b = b.drop_duplicates(["date", "ticker"])
C = b.pivot(index="date", columns="ticker", values="c").sort_index()
V = b.pivot(index="date", columns="ticker", values="v").reindex(C.index)
spy = C["SPY"]; dates = C.index
h = store.load_breadth(); h = h.set_index(pd.to_datetime(h["date"])) if "date" in h.columns else h; h.index = pd.to_datetime(h.index)
h = h.reindex(dates)
mc = macro.load()
ser = lambda k: pd.Series({pd.Timestamp(d): float(v) for d, v in (mc.get(k) or {}).get("rows", []) if v is not None}).sort_index().reindex(dates).ffill()
vix, credit = ser("vix"), ser("hyg") / ser("iei")
# leaders
e21 = C.ewm(span=21, adjust=False).mean()
dv = (C * V).rolling(20).mean()
r63 = C / C.shift(63) - 1
liq = (C >= 10) & (dv >= 20e6)
rk = r63.where(liq).rank(axis=1, pct=True)
lead = rk >= 0.9
f5 = C.shift(-5) / C - 1
long_proxy = f5.where(lead & (C > e21)).median(axis=1)
lead_below = ((C < e21) & lead).sum(axis=1).astype(float) / lead.sum(axis=1).astype(float).replace(0, np.nan)
# thrust day-10 tell: inside a thrust window, 10+ sessions after the latest major signal, ratio10 < 1
ev = sorted(pd.Timestamp(e["date"]) for e in metrics.events(h.dropna(subset=["ratio10"])) if e.get("tier") == "major" and e.get("kind") in ("thrust", "followthrough"))
since = pd.Series(np.nan, index=dates)
for d in ev:
    if d in dates:
        i = dates.get_loc(d); since.iloc[i:i + 25] = np.arange(min(25, len(dates) - i))
spy_e21, spy_s50 = spy.ewm(span=21, adjust=False).mean(), spy.rolling(50).mean()
dn10 = (h["dn_share"] >= 1000 / 11)
F = {
    "ratio10 < 1 (weak breadth)": h["ratio10"] < 1,
    "ratio5 < 0.5": h["ratio5"] < 0.5,
    "10:1 down day in last 5": dn10.rolling(5, min_periods=1).max().astype(bool),
    "new lows > new highs": h["nl"] > h["nh"],
    "SPY below 21 EMA": spy < spy_e21,
    "SPY below 50 SMA": spy < spy_s50,
    "VIX > 22": vix > 22,
    "VIX up 20%+ in 5 days": vix / vix.shift(5) - 1 >= 0.2,
    "credit below 20-day avg": credit < credit.rolling(20).mean(),
    "half of leaders below 21 EMA": lead_below >= 0.5,
    "thrust failing (day 10+, ratio10 < 1)": (since >= 10) & (h["ratio10"] < 1),
    "2 of: weak breadth / SPY<21EMA / leaders<21EMA": ((h["ratio10"] < 1).astype(int) + (spy < spy_e21).astype(int) + (lead_below >= 0.5).astype(int)) >= 2,
}
f10 = spy.shift(-10) / spy - 1
d1 = spy.shift(-1) / spy - 1
valid = dates[(dates >= dates[63]) & (dates <= dates[-6])]
rows = []
for name, f in F.items():
    f = f.reindex(dates).fillna(False).astype(bool)
    on, off = f.loc[valid], ~f.loc[valid]
    onset = f & ~f.shift(1, fill_value=False)
    eq_off = (1 + d1.loc[valid].where(off, 0)).prod() - 1      # long SPY only when flag off (cash when on)
    eq = (1 + d1.loc[valid].where(off, 0)).cumprod(); mdd = (eq / eq.cummax() - 1).min()
    rows.append({"warning": name, "maxDD %": round(mdd * 100, 1), "days on %": round(on.mean() * 100), "times fired": int(onset.loc[valid].sum()),
                 "SPY next10 on": round(f10.loc[valid][on].mean() * 100, 2), "SPY next10 off": round(f10.loc[valid][off].mean() * 100, 2),
                 "leader next5 on": round(long_proxy.loc[valid][on].mean() * 100, 2), "leader next5 off": round(long_proxy.loc[valid][off].mean() * 100, 2),
                 "SPY long-when-off %": round(eq_off * 100, 1)})
R = pd.DataFrame(rows)
bh = (1 + d1.loc[valid]).prod() - 1
_e = (1 + d1.loc[valid]).cumprod(); print("SPY buy & hold maxDD", round(((_e / _e.cummax()) - 1).min() * 100, 1))
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 20)
print(f"valid {valid[0].date()} -> {valid[-1].date()}, {len(valid)} sessions; SPY buy & hold {bh*100:.1f}%; leader next5 avg {long_proxy.loc[valid].mean()*100:.2f}%")
print(R.to_string(index=False))
# pullbacks: first fire after the peak, lead vs trough, share of the fall sidestepped
PB = [("2025-02-19", "2025-04-08"), ("2025-10-29", "2025-11-20"), ("2026-01-27", "2026-03-30"), ("2026-10-06", "2026-11-20")]
print("\nFirst fire after each peak (sessions after peak / SPY % already lost / % of the peak-to-trough fall avoided if you'd stepped out):")
for name, f in F.items():
    f = f.reindex(dates).fillna(False).astype(bool); out = []
    for a, z in PB:
        a, z = pd.Timestamp(a), pd.Timestamp(z)
        w = f.loc[a:z]; hit = w[w].index
        if len(hit) == 0: out.append("never"); continue
        d = hit[0]; lost = spy[d] / spy[a] - 1; tot = spy[z] / spy[a] - 1
        out.append(f"+{dates.get_loc(d) - dates.get_loc(a)}d {lost*100:+.1f}% ({(1 - lost / tot) * 100:.0f}% avoided)")
    print(f"  {name:48s} " + " | ".join(out))
R.to_csv("tools/redlight_study/results.csv", index=False)
