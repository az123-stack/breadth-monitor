"""Trade warehouse · step 1 (plan: tools/warehouse/PLAN.md v3.1). One row per pullback episode of a leader, with the daily-dip (D)
and weekly-dip (W) entries traded under identical rules, the three policies, and the variables measured at the final leg high.
Run: PYTHONPATH=. python3 tools/warehouse/build.py  → data/warehouse/episodes.parquet (+ trades.parquet)
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from breadth import config, emaprob, metrics, store, strength  # noqa: E402

OUT = ROOT / "data" / "warehouse"
START = pd.Timestamp("2025-09-05")
BUFFER = 85
EP_MAX, TRIG, HOLD = 40, 3, 40


def wide():
    bars = store.apply_splits(store.load_bars(), store.load_splits())
    return strength.wide_all(bars), bars


def weekly_atr(h, l, c):
    """Mean of the last 10 weekly true ranges, completed weeks only, as % of that week's close; mapped onto each day."""
    wk = c.index.to_period("W-FRI")
    wh, wl, wc = h.groupby(wk).max(), l.groupby(wk).min(), c.groupby(wk).last()
    tr = pd.concat([wh - wl, (wh - wc.shift(1)).abs(), (wl - wc.shift(1)).abs()]).groupby(level=0).max()
    atr = (tr / wc).rolling(10, min_periods=10).mean().shift(1)   # shift: only weeks completed before the current one
    return atr.reindex(wk).set_axis(c.index)


def supply_levels(t, month_S, leglow_date, monthly, h_daily, s_idx, leglow_idx, dates):
    """Known supply above, as of the episode start: monthly pivots (all 6 neighbours complete before month_S) and ATH from months
    before the current leg, plus daily swing highs (10 either side, complete before S) before the leg low. Returns [(level, source, age_yrs)]."""
    out = []
    rec = monthly.get(t)
    if rec:
        m = [x for x in rec["m"] if x[0] < leglow_date.strftime("%Y-%m")]   # months before the current leg
        mon = [x[0] for x in m]
        his = [x[1] for x in m]
        cut = (month_S - 1)
        for i in range(len(m)):
            pm = pd.Period(mon[i], "M")
            if pm + 3 > cut or i < 3 or i + 3 >= len(m):
                continue
            if his[i] > max(his[i - 3:i]) and his[i] > max(his[i + 1:i + 4]):
                out.append((his[i], "monthly", (month_S - pm).n / 12))
        if his:
            j = int(np.argmax(his))
            out.append((his[j], "ath", (month_S - pd.Period(mon[j], "M")).n / 12))
    hd = h_daily
    for k in range(10, leglow_idx - 10):
        if k + 10 >= s_idx:
            break
        v = hd[k]
        if np.isfinite(v) and v > np.nanmax(hd[k - 10:k]) and v > np.nanmax(hd[k + 1:k + 11]):
            out.append((float(v), "daily", (dates[s_idx] - dates[k]).days / 365.25))
    return out


def trade(k, end, o, h, l, c, e10, adr, n):
    """Trigger / fill / stop / exits for a dip on bar k (plan rules). Returns dict or None (no fill)."""
    a = adr[k]
    if not np.isfinite(a) or a <= 0:
        return None
    for j in range(k + 1, min(k + TRIG, end, n - 1) + 1):
        if h[j] >= h[k]:
            fill = max(o[j], h[k])
            stop0 = max(l[k], fill * (1 - a))
            risk = max(fill - stop0, 0.3 * a * fill)
            res = {"fill_i": j, "fill": fill, "risk": risk, "stop0": stop0}
            # --- primary: Adam's management ---
            if l[j] <= stop0:
                res.update(R=(stop0 - fill) / risk, stopped=True, exit_i=j, sameday=True)
            else:
                stop, half, R, stopped, ex = stop0, None, None, False, None
                for t in range(j + 1, min(j + HOLD, n - 1) + 1):
                    px = None
                    if o[t] <= stop:
                        px = o[t]
                    elif l[t] <= stop:
                        px = stop
                    if px is not None:
                        R = ((half if half is not None else 0) + (px - fill) * (0.5 if half is not None else 1.0)) / risk
                        stopped, ex = half is None, t
                        break
                    if t == j + 4 and half is None:
                        half = 0.5 * (c[t] - fill)
                        stop = max(stop, fill)            # break-even on the rest
                    elif half is not None and c[t] < e10[t]:
                        R, ex = (half + 0.5 * (c[t] - fill)) / risk, t
                        break
                if R is None:
                    t = min(j + HOLD, n - 1)
                    if t < j + HOLD:
                        res["censored"] = True
                    R = ((half if half is not None else 0) + (c[t] - fill) * (0.5 if half is not None else 1.0)) / risk
                    ex = t
                res.update(R=R, stopped=stopped, exit_i=ex, sameday=False)
            # --- secondary: fixed 20 sessions or stop ---
            R20 = None
            if l[j] <= stop0:
                R20 = (stop0 - fill) / risk
            else:
                for t in range(j + 1, min(j + 19, n - 1) + 1):
                    if o[t] <= stop0:
                        R20 = (o[t] - fill) / risk
                        break
                    if l[t] <= stop0:
                        R20 = (stop0 - fill) / risk
                        break
                if R20 is None:
                    R20 = (c[min(j + 19, n - 1)] - fill) / risk
            res["R"] = float(min(res["R"], 10))
            res["R20"] = float(min(R20, 10))
            return res
    return None


def spy_groups(spy):
    """Independent SPY pullbacks: 3%+ close drawdown from a 20-session closing high, merged within 10 sessions.
    Each = [start (the 20-day high date) , end (recovery to that high, or last day)]."""
    c = spy.to_numpy()
    n = len(c)
    raw = []
    i = 20
    while i < n:
        hi_i = i - 20 + int(np.argmax(c[i - 20:i + 1]))
        if c[i] <= 0.97 * c[hi_i]:
            hi = c[hi_i]
            j = i
            while j < n and c[j] < hi:
                j += 1
            raw.append([hi_i, min(j, n - 1)])
            i = j + 1
        else:
            i += 1
    merged = []
    for s, e in raw:
        if merged and s - merged[-1][1] <= 10:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged


def main():
    W, bars = wide()
    c, o, h, l, v = W["c"], W["o"], W["h"], W["l"], W["v"]
    dates = c.index
    n = len(dates)
    uni = set(store.load_universe())
    inuni = pd.DataFrame(np.broadcast_to(c.columns.isin(list(uni)), c.shape), index=c.index, columns=c.columns)
    liquid_all = (c >= config.MIN_PRICE) & (v.rolling(20, min_periods=15).mean() >= config.MIN_AVG_VOLUME) & inuni
    print("RS ratings…", flush=True)
    rs, _, _ = strength.rs_ratings(c, liquid_all, range(n))
    rs = rs.reindex(index=dates, columns=c.columns)
    subs = store.load_subthemes()
    sub_of = dict(zip(subs["ticker"], subs["subtheme"]))
    focus = sorted((set(subs["ticker"]) | set(store.load_themes()["ticker"])) & set(c.columns))
    monthly = {}
    mp = OUT / "monthly.json"
    if mp.exists():
        monthly = json.loads(mp.read_text())
    print(f"{len(focus)} theme tickers, monthly levels for {len(monthly)}", flush=True)
    # spot check monthly vs our daily highs
    bad = set()
    for t in focus:
        rec = monthly.get(t)
        if not rec:
            continue
        dm = h[t].groupby(dates.to_period("M")).max().dropna()
        mm = {x[0]: x[1] for x in rec["m"]}
        for p, val in dm.items():
            ym = str(p)
            if ym in mm and ym != dates[-1].strftime("%Y-%m") and val > 0 and abs(mm[ym] / val - 1) > 0.02:
                bad.add(t)
                break
    spy = c[config.BENCHMARK]
    groups = spy_groups(spy)
    br = store.load_breadth().reindex(dates)
    strong = ((br["ratio5"] >= 1.5) & (br["ratio10"] >= 1.5)).fillna(False).to_numpy()
    thr = metrics.thrust_window(store.load_breadth(), list(dates))
    i0 = int(np.searchsorted(dates, START))
    iend = n - 1 - BUFFER
    eps, nrm = [], 0
    for t in focus:
        C, O, H, L = (x[t].to_numpy(dtype=float) for x in (c, o, h, l))
        if np.isnan(C[i0:]).all():
            continue
        adr = ((h[t] / l[t]) - 1).rolling(20, min_periods=15).mean().to_numpy()
        dv = (c[t] * v[t]).rolling(20, min_periods=15).mean().to_numpy()
        e9, e10, e21, e50 = (c[t].ewm(span=k, adjust=False, min_periods=k).mean().to_numpy() for k in (9, 10, 21, 50))
        w9 = emaprob.weekly_ema(c[t], 9)[0].to_numpy()
        w21 = emaprob.weekly_ema(c[t], 21)[0].to_numpy()
        watr = weekly_atr(h[t], l[t], c[t]).to_numpy()
        RS = rs[t].to_numpy()
        hi20 = c[t].rolling(20, min_periods=20).max().to_numpy()
        i = max(i0, 60)
        while i <= n - 1:
            if not (i <= iend and np.isfinite(C[i]) and np.isfinite(hi20[i]) and C[i] >= hi20[i]):
                i += 1
                continue
            S, lh, first, firstkind = i, C[i], None, None
            D = Wk = None
            j = i + 1
            end = None
            while j <= n - 1:
                if not np.isfinite(C[j]):
                    j += 1
                    continue
                if first is None and C[j] > lh:
                    S, lh = j, C[j]
                    j += 1
                    if S > iend:
                        break
                    continue
                a = adr[S]
                pulled = np.nanmin(C[S + 1:j + 1]) <= lh * (1 - a) if np.isfinite(a) else False
                rib_d, rib_w = max(e9[j], e21[j]), max(w9[j], w21[j])
                isD = pulled and L[j] <= rib_d + 0.25 * adr[j] * C[j] and C[j] >= e21[j] - 0.5 * adr[j] * C[j] and C[j] <= e9[j] + adr[j] * C[j]
                isW = pulled and L[j] <= rib_w + 0.25 * adr[j] * C[j] and C[j] >= w21[j] - 0.5 * adr[j] * C[j] and C[j] <= w9[j] + adr[j] * C[j]
                if first is None and (isD or isW):
                    first = j
                    firstkind = "both" if (isD and isW) else ("D" if isD else "W")
                    if isD:
                        D = j
                    if isW:
                        Wk = j
                elif first is not None and Wk is None and isW:
                    Wk = j
                # episode end
                if first is not None and j > first and C[j] > lh:
                    end = j
                    break
                if np.isfinite(watr[j]) and C[j] < w21[j] - watr[j] * C[j]:
                    end = j
                    break
                if j - S >= EP_MAX:
                    end = j
                    break
                j += 1
            if end is None:
                end = min(j, n - 1)
            if S > iend or S < i0:
                i = end + 1
                continue
            # leader filter at the FINAL S
            ok = (C[S] >= 10 and dv[S] >= 20e6 and np.isfinite(RS[S]) and RS[S] >= 80 and e21[S] > e50[S] and e50[S] > e50[S - 10]
                  and w9[S] > w21[S])
            if not ok:
                i = end + 1
                continue
            if first is None:
                nrm += 0
            # variables at S
            low_i = S - 60 + int(np.nanargmin(C[S - 60:S + 1]))
            ext = (C[S] - w21[S]) / (watr[S] * C[S]) if np.isfinite(watr[S]) and watr[S] > 0 else np.nan
            lv = [] if t in bad else supply_levels(t, dates[S].to_period("M"), dates[low_i], monthly, H, S, low_i, dates)
            band = max(0.02, adr[S] if np.isfinite(adr[S]) else 0.02)
            hit = any(-band <= C[S] / L_ - 1 <= 0.03 for L_, _, _ in lv)
            above = [L_ / C[S] - 1 for L_, _, _ in lv if L_ > C[S]]
            room = min(above) if above else np.inf
            src = sorted({s for L_, s, _ in lv if -band <= C[S] / L_ - 1 <= 0.03})
            g = next((gi for gi, (gs, ge) in enumerate(groups) if gs <= S <= ge), -1)
            row = {"t": t, "sub": sub_of.get(t, ""), "S": dates[S], "lh": C[S], "rs": RS[S], "adr": adr[S], "ext": ext,
                   "hit_supply": bool(hit), "supply_src": ",".join(src), "room": room, "n_levels": len(lv), "bad_levels": t in bad,
                   "has_monthly": t in monthly, "run": C[S] / np.nanmin(C[S - 60:S + 1]) - 1, "strong": bool(strong[S]),
                   "thrust": bool(thr[S]), "mkt_group": g, "first_kind": firstkind, "end": dates[end]}
            tD = trade(D, end, O, H, L, C, e10, adr, n) if D is not None else None
            tW = trade(Wk, end, O, H, L, C, e10, adr, n) if Wk is not None else None
            # W after a D stop (P_DW): the next W bar after D's exit, inside the episode
            tW2 = None
            if tD is not None and tD.get("stopped"):
                k2 = next((k for k in range(tD["exit_i"] + 1, end + 1)
                           if np.isfinite(C[k]) and L[k] <= max(w9[k], w21[k]) + 0.25 * adr[k] * C[k] and C[k] >= w21[k] - 0.5 * adr[k] * C[k]
                           and C[k] <= w9[k] + adr[k] * C[k]), None)
                if Wk is not None and Wk > tD["exit_i"]:
                    k2 = Wk
                tW2 = trade(k2, end, O, H, L, C, e10, adr, n) if k2 is not None else None
            spyR = lambda tr: (spy.iat[tr["exit_i"]] / spy.iat[tr["fill_i"]] - 1) if tr else None
            for nm, tr in (("D", tD), ("W", tW), ("W2", tW2)):
                row[nm + "_bar"] = {"D": D, "W": Wk, "W2": None}.get(nm)
                row[nm + "_fill"] = tr is not None
                row[nm + "_R"] = tr["R"] if tr else 0.0
                row[nm + "_R20"] = tr["R20"] if tr else 0.0
                row[nm + "_stopped"] = bool(tr and tr.get("stopped"))
                row[nm + "_sameday"] = bool(tr and tr.get("sameday"))
                row[nm + "_censored"] = bool(tr and tr.get("censored"))
                row[nm + "_risk"] = tr["risk"] / tr["fill"] if tr else np.nan
                row[nm + "_xs"] = ((C[tr["exit_i"]] / tr["fill"] - 1) - spyR(tr)) if tr else np.nan
                row[nm + "_fill_date"] = dates[tr["fill_i"]] if tr else pd.NaT
            row["P_D"] = row["D_R"]
            row["P_W"] = row["W_R"]
            if row["D_fill"]:
                row["P_DW"] = row["D_R"] + (row["W2_R"] if row["D_stopped"] else 0.0)
                row["P_DW_units"] = 1 + (1 if (row["D_stopped"] and row["W2_fill"]) else 0)
            else:
                row["P_DW"], row["P_DW_units"] = row["W_R"], (1 if row["W_fill"] else 0)
            eps.append(row)
            i = end + 1
    E = pd.DataFrame(eps)
    OUT.mkdir(parents=True, exist_ok=True)
    E.to_parquet(OUT / "episodes.parquet")
    json.dump({"groups": [[str(dates[a].date()), str(dates[b].date())] for a, b in groups], "bad_levels": sorted(bad),
               "n_monthly": len(monthly)}, open(OUT / "meta.json", "w"), indent=1)
    print(f"{len(E)} episodes, {E['first_kind'].notna().sum()} with a dip; monthly-level mismatches dropped: {len(bad)}")


if __name__ == "__main__":
    main()
