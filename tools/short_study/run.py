"""Failed-pop shorts (Nov 25, 2026; Adam: "run the studies"; ROADMAP #2). Setup: liquid stock ($5+, $20M+/day) in a downtrend
(close < falling 50 SMA) pops +10% in 3 sessions; the pop FAILS when, within 3 sessions after the pop's highest close, it closes below
that day's low -> short that close. Stop = highest high since the pop began (skip if risk > 2 ADR). Exit: stop, else close after N
sessions (5 / 10). Variant 'blind' = short the close of the pop day without waiting for failure. One trade per ticker at a time.
Results in R; split by market state, the red-light flags, the 4 SPY 5%+ pullbacks, broken sub-theme, both halves."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, ".")
from breadth import store, metrics

b = store.apply_splits(store.load_bars(), store.load_splits()); b["date"] = pd.to_datetime(b["date"]); b = b.drop_duplicates(["date", "ticker"])
P = {k: b.pivot(index="date", columns="ticker", values=k).sort_index() for k in "ohlcv"}
dates, tick = P["c"].index, P["c"].columns
O, H, L, C, V = (P[k].to_numpy(float) for k in "ohlcv")
Cd = P["c"]
s50 = Cd.rolling(50).mean().to_numpy()
dv = (Cd * P["v"]).rolling(20).mean().to_numpy()
tr = np.fmax(H - L, np.fmax(abs(H - np.roll(C, 1, 0)), abs(L - np.roll(C, 1, 0))))
adr = pd.DataFrame((H / L - 1)).rolling(20).mean().to_numpy()
down = (C < s50) & (s50 < np.roll(s50, 10, 0)) 
pop3 = C / np.roll(C, 3, 0) - 1
liq = (C >= 5) & (dv >= 20e6)
sig = liq & np.roll(down, 3, 0) & (pop3 >= 0.10)      # in a downtrend BEFORE the pop
sig[:63] = False
# context
h = store.load_breadth(); h = h.set_index(pd.to_datetime(h["date"])) if "date" in h.columns else h; h.index = pd.to_datetime(h.index)
tw = pd.Series(metrics.thrust_window(h, h.index), index=h.index)
state = pd.Series(np.where(tw, "thrust", np.where((h.ratio5 >= 1.5) & (h.ratio10 >= 1.5), "strong", np.where(h.ratio10 < 1, "weak", "mixed"))), index=h.index).reindex(dates).fillna("mixed")
ev = sorted(pd.Timestamp(e["date"]) for e in metrics.events(h) if e.get("tier") == "major" and e.get("kind") in ("thrust", "followthrough"))
since = pd.Series(np.nan, index=dates)
for d in ev:
    if d in dates: i = dates.get_loc(d); since.iloc[i:i + 25] = np.arange(min(25, len(dates) - i))
r10 = h.ratio10.reindex(dates)
spy = Cd["SPY"]; spyb21 = (spy < spy.ewm(span=21, adjust=False).mean())
failing = (since >= 10) & (r10 < 1)
PB = [("2025-02-19", "2025-04-08"), ("2025-10-29", "2025-11-20"), ("2026-01-27", "2026-03-30"), ("2026-10-06", "2026-11-20")]
inpb = pd.Series("", index=dates)
for a, z in PB: inpb.loc[a:z] = a[:7]
sub = store.load_subthemes() if hasattr(store, "load_subthemes") else None
grp = {}
try:
    s = pd.read_csv("data/subthemes.csv"); grp = s.groupby("ticker").subtheme.first().to_dict()
except Exception: pass
r63 = (Cd / Cd.shift(63) - 1)
gmed = {g: r63[[t for t in m if t in r63.columns]].median(axis=1) for g, m in pd.read_csv("data/subthemes.csv").groupby("subtheme").ticker} if grp else {}

def sim(mode, hold):
    out, busy = [], np.full(len(tick), -1)
    rows, cols = np.nonzero(sig)
    for i, j in sorted(zip(rows, cols)):
        if i <= busy[j] or i + 2 >= len(dates): continue
        p0 = i - 3
        if mode == "blind":
            e = i
        else:
            k = i; e = None
            for q in range(i + 1, min(i + 4, len(dates))):   # pop may extend: track highest close
                if C[q, j] > C[k, j]: k = q
                elif C[q, j] < L[k, j]: e = q; break
            if e is None: busy[j] = i + 3; continue
        entry = C[e, j]; stop = np.nanmax(H[p0 + 1:e + 1, j]); risk = stop - entry
        a = adr[e, j] * entry
        if not (risk > 0) or not (a > 0) or risk > 2 * a: busy[j] = e; continue
        risk = max(risk, 0.3 * a)
        x = None
        for q in range(e + 1, min(e + 1 + hold, len(dates))):
            if O[q, j] >= stop: x = O[q, j]; break
            if H[q, j] >= stop: x = stop; break
        last = min(e + hold, len(dates) - 1)
        if last == e: continue
        if x is None: x = C[last, j]; q = last
        d = dates[e]; t = tick[j]; g = grp.get(t)
        gb = (gmed[g].iloc[e] < 0) if g in gmed and not np.isnan(gmed[g].iloc[e]) else None
        out.append({"date": d, "ticker": t, "R": (entry - x) / risk, "ret": entry / x - 1, "state": state.iloc[e], "weak": bool(r10.iloc[e] < 1),
                    "failing": bool(failing.iloc[e]), "spy_below21": bool(spyb21.iloc[e]), "pullback": inpb.iloc[e], "broken_group": gb,
                    "open": q == len(dates) - 1})
        busy[j] = q
    return pd.DataFrame(out)

def summ(df, by=None):
    f = lambda x: pd.Series({"n": len(x), "avg_R": round(x.R.mean(), 2), "win%": round((x.R > 0).mean() * 100), "t": round(x.R.mean() / (x.R.std() / np.sqrt(len(x))), 1) if len(x) > 2 else np.nan})
    return f(df) if by is None else df.groupby(by).apply(f)

pd.set_option("display.width", 200)
for mode in ("failed", "blind"):
    for hold in (5, 10):
        df = sim(mode, hold); df = df[~df.open]
        mid = df.date.sort_values().iloc[len(df) // 2]
        print(f"\n=== {mode} pop, hold {hold} ===  all: {summ(df).to_dict()}")
        print("halves:", summ(df[df.date < mid]).to_dict(), "|", summ(df[df.date >= mid]).to_dict())
        print(summ(df, "state").to_string())
        for k in ("weak", "failing", "spy_below21", "broken_group"): print(k, summ(df, k).to_dict("index"))
        print("pullbacks:", summ(df, "pullback").to_dict("index"))
        if mode == "failed" and hold == 5:
            df.to_csv("tools/short_study/trades.csv", index=False)
            combo = df[df.weak & df.spy_below21]
            print("weak & SPY<21EMA:", summ(combo).to_dict(), " + broken group:", summ(combo[combo.broken_group == True]).to_dict())
