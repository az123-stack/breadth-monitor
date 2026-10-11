"""Evaluate v2 measures against the sheet's v1 measures on stored history.

    python tools/evaluate.py [--fwd 10]

Reports, for themes and sub-themes:
  - rank stability (day-to-day and 5-day rank correlation, median |5-day rank move|)
  - information coefficient: Spearman correlation between today's rank and the
    group's next-N-day median return minus SPY (higher = rankings that persist)
for stocks:
  - RS Rating vs 3-month % IC on forward returns across the liquid universe
and for setup lists: forward returns and +8% hit rates vs the universe base rate.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from breadth import config, store, strength as S, themes as TH, setups as SU  # noqa: E402


def spearman(a, b):
    m = a.notna() & b.notna()
    if m.sum() < 8:
        return np.nan
    return float(a[m].rank().corr(b[m].rank()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fwd", type=int, default=10)
    args = ap.parse_args()
    F = args.fwd

    adj = store.apply_splits(store.load_bars(), store.load_splits())
    universe = store.load_universe()
    w = S.wide_all(adj)
    close = w["c"]
    dates = close.index
    N = len(dates)
    print(f"{N} trading days, {close.shape[1]} tickers, {dates[0].date()} -> {dates[-1].date()}")
    spy = close[config.BENCHMARK] if config.BENCHMARK in close.columns else None
    liquid = (close >= config.MIN_PRICE) & (w["v"].rolling(20, min_periods=15).mean() >= config.MIN_AVG_VOLUME)
    liquid = liquid & pd.Series(close.columns.isin(list(universe)), index=close.columns)

    days = list(range(S.RS_W[0][0], N))
    ratings, bps, raw = S.rs_ratings(close, liquid, days)
    ema21 = close.ewm(span=21, adjust=False, min_periods=21).mean()
    ema50 = close.ewm(span=50, adjust=False, min_periods=50).mean()

    th = store.load_themes()
    members = {g: list(dict.fromkeys(d.loc[d.role == "member", "ticker"])) or list(d.ticker)
               for g, d in th.groupby("theme")}
    sub = store.load_subthemes()
    sub_members = {g: list(d.ticker) for g, d in sub.groupby("subtheme")}
    tf = TH.ticker_frames(adj, set(th.ticker) | set(sub.ticker) | {config.BENCHMARK})

    first = max(90, S.RS_W[0][0]) + 1
    test_days = list(range(first, N - F))
    print(f"strength evaluated on {len(test_days)} days ({dates[test_days[0]].date()} -> {dates[test_days[-1]].date()}), forward {F}d")

    def group_fwd(mem, i):
        out = {}
        if spy is None:
            return pd.Series(dtype=float)
        sr = spy.iloc[i + F] / spy.iloc[i] - 1
        for g, tick in mem.items():
            tick = [t for t in tick if t in close.columns]
            r = (close.iloc[i + F][tick] / close.iloc[i][tick] - 1).dropna()
            if len(r):
                out[g] = float(r.median()) - sr
        return pd.Series(out)

    for label, mem in (("THEMES", members), ("SUB-THEMES", sub_members)):
        new_rank, old_rank, ic_new, ic_old = {}, {}, [], []
        for i in range(first, N):
            spy_ret = {n: float(spy.iloc[i] / spy.iloc[i - n] - 1) for n, _ in S.STR_HORIZONS} if spy is not None else {}
            inp = S.group_inputs(close, ema21, ema50, ratings.loc[dates[i]] if dates[i] in ratings.index else None, mem, i, spy_ret)
            sc = S.strength_scores(inp)
            new_rank[i] = sc.rank(ascending=False)
            ot = TH.theme_table(tf, i, mem)
            old_rank[i] = pd.Series(ot["rank"].values, index=ot["theme"]) if len(ot) else pd.Series(dtype=float)
            if i < N - F:
                fwd = group_fwd(mem, i)
                ic_new.append(spearman(-new_rank[i], fwd))
                ic_old.append(spearman(-old_rank[i], fwd))

        def stab(rk, lag):
            cs = [spearman(rk[i], rk[i - lag]) for i in rk if i - lag in rk]
            return np.nanmean(cs)

        def med_move(rk, lag=5):
            mv = []
            for i in rk:
                if i - lag in rk:
                    a, b = rk[i].align(rk[i - lag], join="inner")
                    mv.extend((a - b).abs().tolist())
            return float(np.nanmedian(mv)) if mv else np.nan

        print(f"\n== {label} ({len(mem)} groups)")
        print(f"{'':28}{'v2 Strength':>14}{'v1 Score/8':>14}")
        print(f"{'rank corr day-to-day':28}{stab(new_rank, 1):>14.2f}{stab(old_rank, 1):>14.2f}")
        print(f"{'rank corr vs 5 days ago':28}{stab(new_rank, 5):>14.2f}{stab(old_rank, 5):>14.2f}")
        print(f"{'median |rank move| 5d':28}{med_move(new_rank):>14.1f}{med_move(old_rank):>14.1f}")
        print(f"{'IC vs fwd ' + str(F) + 'd rel return':28}{np.nanmean(ic_new):>14.3f}{np.nanmean(ic_old):>14.3f}")
        print(f"{'IC > 0 share of days':28}{np.mean(np.array(ic_new) > 0):>14.0%}{np.mean(np.array(ic_old) > 0):>14.0%}")

    # ---- stocks: RS Rating vs 3-month % ----
    fwd20 = close.shift(-20) / close - 1
    ic_r, ic_3m = [], []
    for i in days:
        if i >= N - 20:
            break
        m = liquid.iloc[i]
        f = fwd20.iloc[i][m]
        ic_r.append(spearman(ratings.loc[dates[i]][m], f))
        ic_3m.append(spearman((close.iloc[i] / close.iloc[i - 63] - 1)[m], f))
    print(f"\n== STOCKS (liquid universe) fwd 20d IC: RS Rating {np.nanmean(ic_r):.3f} | 3-month % {np.nanmean(ic_3m):.3f}"
          f"  over {len(ic_r)} days")

    # ---- setup lists ----
    t = S.tightness(w)
    res = SU.evaluate_lists(w, t, ratings, liquid, dates, first, F)
    print("\n== SETUP LISTS: avg forward return, % reaching +8% intraday within the window, vs liquid-universe base")
    for name, r in res.items():
        print(f"{name:26} n={r['n']:5d}  fwd{F}d {r['fwd']:+.2%}  hit+8% {r['hit']:.0%}   | base fwd {r['base_fwd']:+.2%} hit {r['base_hit']:.0%}")


if __name__ == "__main__":
    main()
