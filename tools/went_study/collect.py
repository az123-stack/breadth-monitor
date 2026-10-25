"""'What made the ones that went?' (Adam, Oct 25 2026; CDNA / DINO / NTRA charts).
Event = the highlighted area: a liquid stock that spent most of the prior 40 weeks under its 50-week EMA, has now closed
above it 2-8 weeks in a row, 9 WEMA over a rising 21 WEMA, not yet extended (<= 3 weekly ATRs over the 50). First such week
per stock per 26 weeks. Entry = next session's open. Outcome: best high within 26 weeks, return at 13 weeks.
Features are all known at the event week's close."""
import sys, os
sys.path.insert(0, "/home/claude/breadth-monitor"); os.chdir("/home/claude/breadth-monitor")
import numpy as np, pandas as pd
from breadth import store, strength, config, sow

b = store.apply_splits(store.load_bars(), store.load_splits())
w = strength.wide_all(b)
uni = set(pd.read_csv("data/universe.csv").iloc[:, 0])
cols = [t for t in w["c"].columns if t in uni]
days = w["c"].index
dC, dO, dH, dL, dV = (w[k][cols] for k in ("c", "o", "h", "l", "v"))
dvol = (dC * dV).rolling(20, min_periods=15).mean()
adr = ((dH / dL) - 1).rolling(20, min_periods=15).mean() * 100
gap = (dO / dC.shift() - 1)
raw = strength.rs_raw(dC)
liqd = (dC >= 5) & (dvol >= 10e6)
rsd = (raw.where(liqd).rank(axis=1, pct=True) * 99).clip(1, 99)
W, nday = sow.weekly(w, cols)
c, h, l, v = W["c"], W["h"], W["l"], W["v"]
wd = c.index
ema = lambda x, n: x.ewm(span=n, adjust=False, min_periods=1).mean()
e9, e21, e50 = ema(c, 9), ema(c, 21), ema(c, 50)
pc = c.shift()
tr = np.maximum(h - l, np.maximum((h - pc).abs(), (l - pc).abs()))
atr = (tr / c).rolling(10, min_periods=6).mean()
ab = (c > e50).astype(int); cs = ab.cumsum(); run = cs - cs.where(ab == 0).ffill().fillna(0)
below40 = (c < e50).astype(float).rolling(40, min_periods=30).sum().shift(run.clip(upper=8).max().astype(int) * 0)  # placeholder
below40 = (c < e50).astype(float).rolling(40, min_periods=30).sum()
liq = (c >= 5) & (dvol.reindex(wd)[cols] >= 10e6)
spy_d = w["c"][config.BENCHMARK]
spy = spy_d.groupby(days.to_period("W-FRI")).last(); spy.index = wd
rsl = c.div(spy, axis=0)
ev_mask = liq & (run >= 2) & (run <= 8) & (below40 >= 20) & (e9 > e21) & (e21 > e21.shift(4)) & (c <= e50 * (1 + 3 * atr))
ev_mask.iloc[:40] = False

sub = store.load_subthemes(); sub_of = dict(zip(sub["ticker"], sub["subtheme"]))
th = store.load_themes(); th = th[th["role"] == "member"]; theme_of = dict(zip(th["ticker"], th["theme"]))
# group 13-week return rank (equal-weight members, weekly closes)
grp_members = sub.groupby("subtheme")["ticker"].apply(lambda s: [t for t in s if t in c.columns]).to_dict()
g13 = pd.DataFrame({g: (c[m] / c[m].shift(13) - 1).clip(-0.9, 3).mean(axis=1) for g, m in grp_members.items() if len(m) >= 3})
g13r = g13.rank(axis=1, pct=True)
ent_i = days.searchsorted(wd, side="right")
rows, last = [], {}
M = ev_mask.to_numpy()
for i in range(len(wd)):
    if ent_i[i] >= len(days):
        continue
    for j in np.flatnonzero(M[i]):
        t = cols[j]
        if t in last and i - last[t] < 26:
            continue
        last[t] = i
        a = ent_i[i]
        ent = dO[t].iat[a]
        if not np.isfinite(ent) or ent <= 0:
            continue
        nfw = len(days) - a
        e26 = min(a + 130, len(days))
        fwdH = dH[t].iloc[a:e26].max() / ent - 1
        r13 = dC[t].iat[a + 64] / ent - 1 if a + 64 < len(days) else np.nan
        s13 = spy_d.iat[a + 64] / spy_d.iat[a] - 1 if a + 64 < len(days) else np.nan
        # did it lose the 50 WEMA (weekly close) within 13 weeks?
        lost = bool((c[t].iloc[i + 1:i + 14] < e50[t].iloc[i + 1:i + 14]).any())
        di = days.searchsorted(wd[i], side="right") - 1          # event week's last session
        d13 = max(0, di - 64)
        prior_hi = dH[t].iloc[:di + 1].max()
        lo40 = l[t].iloc[max(0, i - 40):i + 1].min()
        hi_before = dH[t].iloc[:max(1, days.searchsorted(wd[max(0, i - 40)]))].max()
        rs_hist = rsl[t].iloc[max(0, i - 52):i + 1]
        updn = v[t].iloc[i - 9:i + 1]; ch = (c[t] - pc[t]).iloc[i - 9:i + 1]
        vbase = v[t].iloc[max(0, i - 36):i - 10].mean()
        g = sub_of.get(t)
        peers = grp_members.get(g, [])
        pe = [p for p in peers if p != t and p in ev_mask.columns]
        peer_ev = float(ev_mask[pe].iloc[max(0, i - 8):i + 1].any().mean()) if len(pe) >= 2 else np.nan
        rows.append(dict(
            t=t, date=wd[i], ent=ent, fwd_weeks=nfw / 5, maxg=fwdH, r13=r13, x13=r13 - s13 if np.isfinite(r13) else np.nan, lost50=lost,
            sub=g, theme=theme_of.get(t),
            rs=rsd[t].iat[di], rsl13=rsl[t].iat[i] / rsl[t].iat[i - 13] - 1, rsl_hi=float(rsl[t].iat[i] >= rs_hist.max() * 0.98),
            rsl_ema=rsl[t].iat[i] / ema(rsl[t].iloc[:i + 1], 21).iat[-1] - 1,
            vr=v[t].iloc[i - 9:i + 1].mean() / vbase if vbase > 0 else np.nan,
            udv=updn[ch > 0].sum() / max(updn[ch <= 0].sum(), 1),
            vmax=v[t].iloc[i - 12:i + 1].max() / vbase if vbase > 0 else np.nan,
            gapmax=gap[t].iloc[d13:di + 1].max(), adr=adr[t].iat[di], dvol=np.log10(dvol[t].iat[di]), price=dC[t].iat[di],
            off_hi=dC[t].iat[di] / prior_hi - 1, depth=lo40 / hi_before - 1 if hi_before > 0 else np.nan,
            run=run[t].iat[i], ext=(c[t].iat[i] / e50[t].iat[i] - 1) / atr[t].iat[i], tight4=(h[t].iloc[i - 3:i + 1].max() / l[t].iloc[i - 3:i + 1].min() - 1) / atr[t].iat[i],
            slope50=e50[t].iat[i] / e50[t].iat[i - 13] - 1, atr=atr[t].iat[i],
            gsub13=g13r[g].iat[i] if g in g13r.columns else np.nan, peers=peer_ev,
            spy13=spy.iat[i] / spy.iat[i - 13] - 1))
D = pd.DataFrame(rows)
D.to_pickle(os.environ.get("OUT", "/tmp/went_ev.pkl"))
print(len(D), D.date.min().date(), D.date.max().date())
