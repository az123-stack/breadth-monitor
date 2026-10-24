"""ORB x sub-theme study (Adam, Oct 24, 2026).

Idea: before the opening range breaks, rank sub-themes by "up the most + most breadth" (and the reverse).
If SPY / QQQ breaks its 15- or 30-minute opening range UP, buy the best stock in the top 2 sub-themes;
if it breaks DOWN, short the worst stock in the bottom 2 sub-themes.

    python -m tools.orb_study.study --bars orb15.parquet [--out results.json]

Data: 15-minute regular-session bars (tools/orb_study/download.py) + stored daily bars for liquidity / ADR,
data/breadth.csv for regimes, data/subthemes.csv for groups.

Rules (no look-ahead):
- Liquid = close >= $5 and 50-day avg $ volume >= $20M, as of the prior session (daily bars).
- Sub-theme needs 3+ liquid members with data. Score = rank(avg move) + rank(% of members up), across groups.
  Ranking "prior": yesterday's close vs the day before. Ranking "or": today's price at the end of the opening
  range vs yesterday's close (gap + first 15/30 min). Best stock = biggest move in that group, worst = smallest.
- Trigger: first 15-min bar AFTER the opening range that closes above the index's OR high (up) / below its OR low (down).
  Enter each stock at that same bar's close. One trade direction per day; no break = no trade.
- Stop: the stock's own opening-range low (long) / high (short); risk floored at 0.3 ADR (dashboard convention).
- Exits: "close" = stop or day's close · "2R" = stop, 2R target, else close (same bar: stop first) · "5d" = stop
  (intraday, then daily lows/highs) or the close 4 sessions after entry day.
- Costs: 0.10% round trip.
- Baselines on the same day, trigger and exits: "any" = average of every liquid sub-theme stock in the trade
  direction; "basket" = average of all liquid members of the 2 chosen groups; "anywhere" = best / worst
  liquid stock regardless of group (same ranking measure).
Unit = date (average of the day's trades). Edge = strategy minus "any" on the same dates, paired t, both halves.
"""
import argparse
import json
import math

import numpy as np
import pandas as pd

from breadth import boxes as BX
from breadth import store

COST = 0.001
NB = 26              # 15-minute bars in a regular session
SIDE = {1: "long (index broke up)", -1: "short (index broke down)"}


def load(bars_path):
    import glob
    import os
    if os.path.isdir(bars_path):
        df = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(os.path.join(bars_path, "*.parquet")))], ignore_index=True)
    else:
        df = pd.read_parquet(bars_path)
    df["date"] = pd.to_datetime(df["date"])
    df = df[(df.m % 15 == 0) & (df.m < NB * 15)]
    dates = sorted(df.date.unique())
    tks = sorted(df.ticker.unique())
    di = {d: i for i, d in enumerate(dates)}
    ti = {t: i for i, t in enumerate(tks)}
    A = {k: np.full((len(dates), NB, len(tks)), np.nan) for k in "ohlcv"}
    r, b, c = df.date.map(di).to_numpy(), (df.m // 15).to_numpy(), df.ticker.map(ti).to_numpy()
    for k in "ohlcv":
        A[k][r, b, c] = df[k].to_numpy(float)
    return pd.DatetimeIndex(dates), tks, A


def daily_context(dates, tks):
    b = store.apply_splits(store.load_bars(), store.load_splits())
    b = b[b.ticker.isin(set(tks))]
    piv = {k: b.pivot_table(index="date", columns="ticker", values=k) for k in ("c", "v", "h", "l")}
    allds = piv["c"].index
    c, v, h, l = (piv[k].reindex(columns=tks) for k in ("c", "v", "h", "l"))
    dv50 = (c * v).rolling(50, min_periods=40).mean()
    adr = ((h / l) - 1).rolling(20, min_periods=15).mean()
    # values known before day d = previous daily row
    prev = lambda x: x.shift(1).reindex(dates).to_numpy()
    liquid = (prev(c) >= 5) & (prev(dv50) >= 20e6)
    br = pd.read_csv("data/breadth.csv", parse_dates=["date"]).set_index("date")
    mk = BX.market_arrays(br, allds)
    reg = pd.Series(mk["regime"], index=allds).shift(1).reindex(dates).fillna("mixed").to_numpy()
    since = pd.Series(mk["since"], index=allds).shift(1).reindex(dates).to_numpy()
    spy = c.get("SPY") if "SPY" in c else None
    if spy is None:
        spyc = b[b.ticker == "SPY"].set_index("date")["c"]
    else:
        spyc = spy
    spy50 = (spyc > spyc.rolling(50).mean()).shift(1).reindex(dates).fillna(False).to_numpy()
    return liquid, prev(adr), reg, since, spy50


def groups(tks):
    st = pd.read_csv("data/subthemes.csv")
    ti = {t: i for i, t in enumerate(tks)}
    out = {}
    for g, s in st.groupby("subtheme"):
        idx = np.array(sorted({ti[t] for t in s.ticker if t in ti and t not in ("SPY", "QQQ")}), int)
        if len(idx) >= 3:
            out[g] = idx
    return out


def rank_groups(r, ok, G, rv=None, use_vol=False):
    """r = per-stock move, ok = usable mask, rv = per-stock relative volume. Returns list of
    (group, score, members, group rel. volume) sorted best first. use_vol adds rank(group rel. volume) to the
    score for the top end and is direction-agnostic (heavy volume counts for both the best and the worst groups):
    score_up = rank(avg) + rank(%up) + rank(rvol); score_dn = rank(avg) + rank(%up) - rank(rvol)."""
    rows = []
    for g, idx in G.items():
        m = idx[ok[idx]]
        if len(m) < 3:
            continue
        x = np.clip(r[m], -0.5, 0.5)
        gv = np.nanmedian(rv[m]) if rv is not None and np.isfinite(rv[m]).any() else np.nan
        rows.append((g, x.mean(), (x > 0).mean(), m, gv))
    if len(rows) < 6:
        return [], []
    avg = pd.Series([x[1] for x in rows]).rank(pct=True).to_numpy()
    up = pd.Series([x[2] for x in rows]).rank(pct=True).to_numpy()
    vol = pd.Series([x[4] for x in rows]).rank(pct=True).fillna(0.5).to_numpy()
    tie = 1e-9 * np.array([x[1] for x in rows])     # tie-break on avg move
    base = avg + up + tie
    sc_up = base + (vol if use_vol else 0)
    sc_dn = base - (vol if use_vol else 0)
    up_order, dn_order = np.argsort(-sc_up), np.argsort(sc_dn)
    pack = lambda o: [(rows[i][0], 0.0, rows[i][3], rows[i][4]) for i in o]
    return pack(up_order), pack(dn_order)


def trades(A, dayC, dayL, dayH, d, j, k, s, dd, adr):
    """Vectorized over stock indices s. Returns dict exit -> (R array, ret array); NaN where no trade."""
    O, H, L, C = A["o"][d], A["h"][d], A["l"][d], A["c"][d]
    e = C[j, s]
    stop = np.nanmin(L[:k, s], axis=0) if dd > 0 else np.nanmax(H[:k, s], axis=0)
    floor = 0.3 * np.nan_to_num(adr[s], nan=0.03) * e
    risk = np.maximum(dd * (e - stop), floor)
    stop = e - dd * risk
    out = {}
    for name in ("close", "2R", "5d"):
        tgt = e + dd * 2 * risk if name == "2R" else None
        px = np.full(len(s), np.nan)
        done = np.zeros(len(s), bool)
        for bi in range(j + 1, NB):
            o, hh, ll = O[bi, s], H[bi, s], L[bi, s]
            hit = ~done & np.isfinite(ll) & ((ll <= stop) if dd > 0 else (hh >= stop))
            px[hit] = np.where(dd > 0, np.minimum(o, stop), np.maximum(o, stop))[hit]
            done |= hit
            if tgt is not None:
                th = ~done & np.isfinite(hh) & ((hh >= tgt) if dd > 0 else (ll <= tgt))
                px[th] = np.where(dd > 0, np.maximum(o, tgt), np.minimum(o, tgt))[th]
                done |= th
        if name == "5d":
            last = min(d + 4, len(dayC) - 1)
            if last < d + 4:
                out[name] = (np.full(len(s), np.nan), np.full(len(s), np.nan))
                continue
            for dx in range(d + 1, last + 1):
                o = A["o"][dx][0, s]
                o = np.where(np.isfinite(o), o, dayC[dx - 1, s])
                hit = ~done & np.isfinite(dayL[dx, s]) & ((dayL[dx, s] <= stop) if dd > 0 else (dayH[dx, s] >= stop))
                px[hit] = np.where(dd > 0, np.minimum(o, stop), np.maximum(o, stop))[hit]
                done |= hit
            px[~done] = dayC[last, s][~done]
        else:
            px[~done] = dayC[d, s][~done]
        ret = dd * (px / e - 1) - COST
        R = ret * e / risk
        with np.errstate(all="ignore"):
            bad = ~np.isfinite(e) | ~np.isfinite(px) | (px / e > 2) | (px / e < 0.5)   # bad prints / unadjusted splits
        R[bad], ret[bad] = np.nan, np.nan
        out[name] = (R, ret)
    return out


def run(bars_path):
    dates, tks, A = load(bars_path)
    nd = len(dates)
    with np.errstate(all="ignore"):
        last = np.where(np.isfinite(A["c"]), np.arange(NB)[None, :, None], -1).max(axis=1)
        dayC = np.take_along_axis(A["c"], np.maximum(last, 0)[:, None, :], axis=1)[:, 0, :]
        dayC[last < 0] = np.nan
        dayL, dayH = np.nanmin(A["l"], axis=1), np.nanmax(A["h"], axis=1)
    liquid, adr, reg, since, spy50 = daily_context(dates, tks)
    G = groups(tks)
    ti = {t: i for i, t in enumerate(tks)}
    # Relative volume per stock, known at decision time.
    # prior: yesterday's total volume / its average over the 20 sessions before it.
    # or (k bars): volume in today's first k bars / average volume in the first k bars over the prior 20 sessions.
    with np.errstate(all="ignore"):
        V = np.where(np.isfinite(A["v"]), A["v"], 0.0)
        dayV = np.where(last >= 0, V.sum(axis=1), np.nan)
        dv = pd.DataFrame(dayV)
        avgV = dv.shift(1).rolling(20, min_periods=15).mean().to_numpy()   # avg of the 20 sessions before each day
        rv_prior = np.full_like(dayV, np.nan)
        rv_prior[1:] = (dayV / avgV)[:-1]                                   # yesterday's rel. volume, used on day d
        rv_or = {}
        for k in (1, 2):
            ov = pd.DataFrame(V[:, :k, :].sum(axis=1))
            ov[ov == 0] = np.nan
            rv_or[k] = (ov / ov.shift(1).rolling(20, min_periods=15).mean()).to_numpy()
    rows = []
    for d in range(2, nd):
        for idx_name in ("SPY", "QQQ"):
            x = ti.get(idx_name)
            if x is None:
                continue
            for k in (1, 2):
                Hh, Ll, Cc = A["h"][d, :, x], A["l"][d, :, x], A["c"][d, :, x]
                if not np.isfinite(Hh[:k]).all():
                    continue
                orh, orl = Hh[:k].max(), Ll[:k].min()
                j, dd = None, 0
                for bi in range(k, NB):
                    if Cc[bi] > orh:
                        j, dd = bi, 1
                        break
                    if Cc[bi] < orl:
                        j, dd = bi, -1
                        break
                base = {"date": dates[d], "idx": idx_name, "orb": 15 * k, "regime": reg[d],
                        "post": bool(np.isfinite(since[d]) and since[d] <= 25), "spy50": bool(spy50[d])}
                if j is None:
                    rows.append({**base, "dir": 0})
                    continue
                ok = liquid[d] & np.isfinite(A["c"][d, j]) & np.isfinite(dayC[d - 1])
                ok[[ti[t] for t in ("SPY", "QQQ") if t in ti]] = False
                allm = np.unique(np.concatenate(list(G.values())))
                anym = allm[ok[allm]]
                if len(anym) < 50:
                    continue
                anyres = trades(A, dayC, dayL, dayH, d, j, k, anym, dd, adr[d])
                for rk in ("prior", "or", "prior+vol", "or+vol"):
                    base_rk, use_vol = rk.split("+")[0], rk.endswith("+vol")
                    with np.errstate(all="ignore"):
                        r = dayC[d - 1] / dayC[d - 2] - 1 if base_rk == "prior" else A["c"][d, k - 1] / dayC[d - 1] - 1
                    okr = ok & np.isfinite(r)
                    rv = rv_prior[d] if base_rk == "prior" else rv_or[k][d]
                    best_first, worst_first = rank_groups(r, okr, G, rv, use_vol)
                    if not best_first:
                        continue
                    chosen = best_first[:2] if dd > 0 else worst_first[:2]
                    allrv = [x[3] for x in best_first]
                    picks, used = [], set()
                    for g, sc, m, _ in chosen:
                        cand = m[np.argsort(-dd * r[m])]
                        cand = [c for c in cand if c not in used]
                        if cand:
                            picks.append(cand[0])
                            used.add(cand[0])
                    basket = np.unique(np.concatenate([m for _, _, m, _ in chosen]))
                    am = anym[np.isfinite(r[anym])]
                    anywhere = am[np.argsort(-dd * r[am])][:2]
                    res = {"pick": trades(A, dayC, dayL, dayH, d, j, k, np.array(picks), dd, adr[d]),
                           "basket": trades(A, dayC, dayL, dayH, d, j, k, basket, dd, adr[d]),
                           "anywhere": trades(A, dayC, dayL, dayH, d, j, k, anywhere, dd, adr[d])}
                    pk = np.array(picks, int)
                    with np.errstate(all="ignore"):
                        own = (np.nanmax(A["h"][d, :k, pk], axis=0) if dd > 0 else np.nanmin(A["l"][d, :k, pk], axis=0)) if len(pk) else np.array([])
                        gap = (A["o"][d, 0, pk] / dayC[d - 1, pk] - 1) if len(pk) else np.array([])
                    row = {**base, "dir": dd, "rank": rk, "bar": j,
                           # extra context for splits: is the stock itself past its own opening range at entry?
                           # how big was its gap in the trade direction? did both SPY and QQQ break the same way?
                           "aligned": float(np.mean(dd * (A["c"][d, j, pk] - own) > 0)) if len(pk) else np.nan,
                           "gap_dir": float(np.nanmean(dd * gap)) if len(pk) else np.nan,
                           "both_idx": both_break(A, d, k, ti, dd, j),
                           "groups": " | ".join(g for g, _, _, _ in chosen), "names": " ".join(tks[p] for p in picks),
                           # chosen groups' relative volume and its percentile among all groups that day
                           "grp_rvol": float(np.nanmean([x[3] for x in chosen])),
                           "grp_rvol_pct": float(np.nanmean([pd.Series(allrv).rank(pct=True).iloc[[x[0] for x in best_first].index(c[0])]
                                                              for c in chosen]))}
                    for ex in ("close", "2R", "5d"):
                        for nm, rr in (("pick", res["pick"]), ("basket", res["basket"]), ("anywhere", res["anywhere"]), ("any", anyres)):
                            R, ret = rr[ex]
                            row[f"{nm}_{ex}_R"] = np.nanmean(R) if np.isfinite(R).any() else np.nan
                            row[f"{nm}_{ex}_ret"] = np.nanmean(ret) if np.isfinite(ret).any() else np.nan
                    rows.append(row)
    return pd.DataFrame(rows)


def both_break(A, d, k, ti, dd, j):
    """True when SPY and QQQ have both closed beyond their opening range in direction dd by bar j."""
    ok = []
    for nm in ("SPY", "QQQ"):
        x = ti.get(nm)
        if x is None:
            return False
        H, L, C = A["h"][d, :, x], A["l"][d, :, x], A["c"][d, :, x]
        lvl = H[:k].max() if dd > 0 else L[:k].min()
        ok.append(bool(np.any(dd * (C[k:j + 1] - lvl) > 0)))
    return all(ok)


def splits(df, ex="close"):
    """Extra cuts on the plain rankings: stock past its own OR at entry, early vs late break, gap size, both indexes."""
    t = df[(df.dir != 0) & df["rank"].isin(["prior", "or"])].copy()
    t["early"] = t.bar <= t.orb // 15 + 1                       # broke on the first bar after the range
    t["gap_big"] = t.gap_dir >= 0.02
    cuts = {"own ORB aligned": t.aligned >= 1, "own ORB not aligned": t.aligned < 1, "early break": t.early,
            "late break": ~t.early, "gapped 2%+ our way": t.gap_big, "small/against gap": ~t.gap_big,
            "SPY+QQQ both": t.both_idx.astype(bool), "only one index": ~t.both_idx.astype(bool)}
    out = []
    for (ix, orb, rk, side), g in t.groupby(["idx", "orb", "rank", "dir"]):
        for lab, m in cuts.items():
            s = g[m.loc[g.index]]
            p, a = s[f"pick_{ex}_R"], s[f"any_{ex}_R"]
            out.append({"idx": ix, "orb": orb, "rank": rk, "side": SIDE[side], "cut": lab, "n": int(p.notna().sum()),
                        "pick_R": p.mean(), "edge_R": (p - a).mean(), "edge_t": tstat(p - a)})
    return pd.DataFrame(out)


def tstat(x):
    x = pd.Series(x).dropna()
    if len(x) < 3 or x.std() == 0:
        return np.nan
    return x.mean() / (x.std() / math.sqrt(len(x)))


def summarize(df):
    out = []
    t = df[df.dir != 0]
    mid = t.date.sort_values().iloc[len(t) // 2] if len(t) else None
    for (ix, orb, rk), g in t.groupby(["idx", "orb", "rank"]):
        for side in (1, -1, 0):
            s = g if side == 0 else g[g.dir == side]
            for ex in ("close", "2R", "5d"):
                p, a = s[f"pick_{ex}_R"], s[f"any_{ex}_R"]
                e = p - a
                h1, h2 = s.date < mid, s.date >= mid
                rec = {"idx": ix, "orb": orb, "rank": rk, "side": {1: "long", -1: "short", 0: "both"}[side], "exit": ex,
                       "n": int(p.notna().sum()), "pick_R": p.mean(), "pick_ret%": 100 * s[f"pick_{ex}_ret"].mean(),
                       "win%": 100 * (p > 0).mean(), "t": tstat(p), "basket_R": s[f"basket_{ex}_R"].mean(),
                       "anywhere_R": s[f"anywhere_{ex}_R"].mean(), "any_R": a.mean(), "edge_R": e.mean(), "edge_t": tstat(e),
                       "edge_h1": e[h1].mean(), "edge_h2": e[h2].mean(), "pick_h1": p[h1].mean(), "pick_h2": p[h2].mean()}
                out.append(rec)
    return pd.DataFrame(out)


def by_state(df, idx="SPY", orb=30, rank="or", ex="close"):
    t = df[(df.dir != 0) & (df.idx == idx) & (df.orb == orb) & (df["rank"] == rank)]
    out = []
    for lab, m in (("all", t.index == t.index), ("strong", t.regime == "strong"), ("mixed", t.regime == "mixed"),
                   ("weak", t.regime == "weak"), ("post-thrust", t.post), ("SPY>50d", t.spy50), ("SPY<50d", ~t.spy50)):
        for side in (1, -1):
            s = t[m & (t.dir == side)]
            p, a = s[f"pick_{ex}_R"], s[f"any_{ex}_R"]
            out.append({"state": lab, "side": SIDE[side], "n": int(p.notna().sum()), "pick_R": p.mean(), "any_R": a.mean(),
                        "edge_R": (p - a).mean(), "edge_t": tstat(p - a)})
    return pd.DataFrame(out)


def vol_split(df, ex="close"):
    """For the plain rankings: did the chosen groups' relative volume (percentile among groups that day) matter?
    high = top third of groups by rel. volume, low = bottom third. Edge = pick minus 'any' on the same days."""
    t = df[(df.dir != 0) & df["rank"].isin(["prior", "or"])]
    out = []
    for (ix, orb, rk, side), g in t.groupby(["idx", "orb", "rank", "dir"]):
        for lab, m in (("high rvol", g.grp_rvol_pct >= 2 / 3), ("mid", (g.grp_rvol_pct > 1 / 3) & (g.grp_rvol_pct < 2 / 3)),
                       ("low rvol", g.grp_rvol_pct <= 1 / 3)):
            s = g[m]
            p, a = s[f"pick_{ex}_R"], s[f"any_{ex}_R"]
            out.append({"idx": ix, "orb": orb, "rank": rk, "side": SIDE[side], "group vol": lab, "n": int(p.notna().sum()),
                        "pick_R": p.mean(), "edge_R": (p - a).mean(), "edge_t": tstat(p - a)})
    return pd.DataFrame(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", default="orb15.parquet")
    ap.add_argument("--out", default="orb_rows.parquet")
    a = ap.parse_args()
    df = run(a.bars)
    df.to_parquet(a.out, index=False)
    pd.set_option("display.width", 250, "display.max_columns", 40, "display.max_rows", 200)
    print(summarize(df).round(3).to_string())
    print(vol_split(df).round(3).to_string())
    print(splits(df).round(3).to_string())


if __name__ == "__main__":
    main()
