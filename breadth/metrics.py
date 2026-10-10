"""Breadth metrics in the style of Stockbee's Market Monitor, plus a regime label.

Everything is computed from a wide close/volume matrix (rows = trading days,
columns = tickers), so every metric is a vectorised count.
"""
import numpy as np
import pandas as pd

from . import config as C

METRIC_COLS = [
    "up4", "dn4", "ratio5", "ratio10", "up4_avg40",
    "up25q", "dn25q", "up25m", "dn25m", "up50m", "dn50m",
    "up13_34", "dn13_34", "t2108", "universe",
]
LOOKBACK_NEEDED = C.QUARTER_DAYS + 1   # rows needed before every metric is valid


def wide(bars):
    close = bars.pivot(index="date", columns="ticker", values="c").sort_index()
    vol = bars.pivot(index="date", columns="ticker", values="v").reindex(close.index)
    return close.astype("float64"), vol.astype("float64")


def compute(bars):
    """Return a DataFrame indexed by date with METRIC_COLS plus `complete`
    (True once the full lookback is available for that row)."""
    close, vol = wide(bars)
    prev_c, prev_v = close.shift(1), vol.shift(1)
    chg = close / prev_c - 1

    price_ok = close >= C.MIN_PRICE
    # 4% days: Stockbee's definition requires volume above the prior day too.
    vol_ok = (vol > prev_v) & (vol >= C.MIN_VOLUME)
    up4 = ((chg >= C.PCT_MOVE) & vol_ok & price_ok).sum(axis=1)
    dn4 = ((chg <= -C.PCT_MOVE) & vol_ok & price_ok).sum(axis=1)

    # Liquid universe for the slower metrics.
    avg_vol = vol.rolling(20, min_periods=15).mean()
    liquid = price_ok & (avg_vol >= C.MIN_AVG_VOLUME)

    def count_moves(days, pct):
        r = close / close.shift(days) - 1
        return (((r >= pct) & liquid).sum(axis=1),
                ((r <= -pct) & liquid).sum(axis=1))

    up25q, dn25q = count_moves(C.QUARTER_DAYS, C.QUARTER_PCT)
    up25m, dn25m = count_moves(C.MONTH_DAYS, C.MONTH_PCT)
    up50m, dn50m = count_moves(C.MONTH_DAYS, C.MONTH_BIG_PCT)
    up13, dn13 = count_moves(C.D34_DAYS, C.D34_PCT)

    sma = close.rolling(C.MA_DAYS, min_periods=C.MA_DAYS).mean()
    has_ma = liquid & sma.notna()
    above = (close > sma) & has_ma
    t2108 = 100 * above.sum(axis=1) / has_ma.sum(axis=1).replace(0, np.nan)

    # Sum first, then divide; floor the denominator at 1 to avoid infinities.
    ratio5 = up4.rolling(5).sum() / dn4.rolling(5).sum().clip(lower=1)
    ratio10 = up4.rolling(10).sum() / dn4.rolling(10).sum().clip(lower=1)

    out = pd.DataFrame({
        "up4": up4, "dn4": dn4, "ratio5": ratio5, "ratio10": ratio10,
        "up4_avg40": up4.rolling(C.AVG_WINDOW).mean(),
        "up25q": up25q, "dn25q": dn25q, "up25m": up25m, "dn25m": dn25m,
        "up50m": up50m, "dn50m": dn50m, "up13_34": up13, "dn13_34": dn13,
        "t2108": t2108, "universe": liquid.sum(axis=1),
    })
    out.index.name = "date"
    out["complete"] = np.arange(len(out)) >= LOOKBACK_NEEDED
    # Blank out metrics whose own lookback isn't filled yet.
    n = np.arange(len(out))
    for col, need in [("up25q", C.QUARTER_DAYS), ("dn25q", C.QUARTER_DAYS),
                      ("up25m", C.MONTH_DAYS), ("dn25m", C.MONTH_DAYS),
                      ("up50m", C.MONTH_DAYS), ("dn50m", C.MONTH_DAYS),
                      ("up13_34", C.D34_DAYS), ("dn13_34", C.D34_DAYS),
                      ("t2108", C.MA_DAYS + 20), ("up4", 1), ("dn4", 1)]:
        out.loc[n < need, col] = np.nan
    return out


def merge(history, fresh):
    """Fold freshly computed rows into stored history.

    Complete rows always win (they reflect the latest split adjustments).
    Incomplete rows only fill dates the history doesn't have yet.
    """
    fresh = fresh.copy()
    keep = fresh[fresh["complete"]] if len(history) else fresh
    if len(history):
        new_dates = fresh.index.difference(history.index)
        keep = pd.concat([keep, fresh.loc[new_dates.difference(keep.index)]])
        history = history.drop(index=keep.index.intersection(history.index))
        merged = pd.concat([history, keep])
    else:
        merged = keep
    merged = merged.sort_index()
    merged["complete"] = merged["complete"].astype(bool)
    return merged


# ---------------------------------------------------------------------------
# Regime
# ---------------------------------------------------------------------------
REGIMES = {
    "washed_out": ("Washed out", "bear",
                   "Extremely weak breadth often marks bounce zones. Favor bottom "
                   "bounces/reversals on strong names; keep size modest until a thrust."),
    "thrust": ("Breadth thrust", "bull",
               "Unusually broad 4% buying. Start pressing momentum bursts on the "
               "strongest names; watch for follow-through over the next days."),
    "extended": ("Overextended", "warn",
                 "Short-term breadth is stretched. Pullbacks are likely; reduce "
                 "aggression, take profits into strength, avoid late breakouts."),
    "strong": ("Strong uptrend", "bull",
               "Sustained positive breadth. Press momentum bursts, anticipation "
               "and continuation setups with normal-to-full size."),
    "deteriorating": ("Deteriorating", "bear",
                      "Breadth is rolling over. Most breakouts fail here; stand aside "
                      "or trade only the very best setups (e.g. EPs) small."),
    "choppy": ("Choppy / mixed", "neutral",
               "No clear breadth edge. Be highly selective, size down, and wait "
               "for a breadth thrust before getting aggressive."),
}


def _pct_rank(series, value):
    s = series.dropna()
    if len(s) < C.MIN_HISTORY_FOR_PCTILES or pd.isna(value):
        return None
    return float((s <= value).mean())


def classify(history):
    """Label the latest row of `history`. Returns dict with key, label, tone,
    advice and the reasons that triggered it."""
    df = history[history["complete"]] if history["complete"].any() else history
    row = df.iloc[-1]
    hist = df.iloc[:-1]
    reasons = []

    r10_rank = _pct_rank(hist["ratio10"], row["ratio10"])
    r5_rank = _pct_rank(hist["ratio5"], row["ratio5"])
    up4_rank = _pct_rank(hist["up4"], row["up4"])
    t = row["t2108"]
    t_5ago = df["t2108"].iloc[-6] if len(df) >= 6 else np.nan

    def done(key):
        label, tone, advice = REGIMES[key]
        return {"key": key, "label": label, "tone": tone, "advice": advice,
                "reasons": reasons, "date": str(df.index[-1].date())}

    # 1. Washed out
    if pd.notna(t) and t <= C.T2108_OVERSOLD:
        reasons.append(f"T2108 {t:.0f} at or below {C.T2108_OVERSOLD}")
    if r10_rank is not None and r10_rank <= C.EXTREME_LOW_PCTILE:
        reasons.append(f"10-day ratio {row['ratio10']:.2f} in bottom "
                       f"{C.EXTREME_LOW_PCTILE:.0%} of history")
    if reasons:
        return done("washed_out")

    # 2. Breadth thrust
    avg = row["up4_avg40"]
    if (pd.notna(avg) and avg > 0 and row["up4"] >= C.THRUST_MULT * avg
            and (up4_rank is None or up4_rank >= C.THRUST_PCTILE)):
        reasons.append(f"{row['up4']:.0f} stocks up 4%+ vs 40-day avg {avg:.0f}")
        return done("thrust")

    # 3. Overextended
    if pd.notna(t) and t >= C.T2108_OVERBOUGHT:
        reasons.append(f"T2108 {t:.0f} at or above {C.T2108_OVERBOUGHT}")
    if r5_rank is not None and r5_rank >= C.EXTREME_HIGH_PCTILE:
        reasons.append(f"5-day ratio {row['ratio5']:.2f} in top "
                       f"{1 - C.EXTREME_HIGH_PCTILE:.0%} of history")
    if reasons:
        return done("extended")

    # 4. Strong
    if row["ratio5"] >= C.STRONG_RATIO and row["ratio10"] >= C.STRONG_RATIO and (pd.isna(t) or t >= 50):
        reasons.append(f"5-day ratio {row['ratio5']:.2f} and 10-day ratio "
                       f"{row['ratio10']:.2f} both at or above {C.STRONG_RATIO}")
        return done("strong")

    # 5. Deteriorating
    if row["ratio10"] < 1 and row["ratio5"] < row["ratio10"] and pd.notna(t_5ago) and t < t_5ago:
        reasons.append(f"10-day ratio {row['ratio10']:.2f} below 1, 5-day weaker, "
                       f"T2108 down from {t_5ago:.0f} to {t:.0f} in 5 days")
        return done("deteriorating")

    reasons.append(f"5-day ratio {row['ratio5']:.2f}, 10-day {row['ratio10']:.2f}, "
                   f"T2108 {t:.0f}: no extreme or trend")
    return done("choppy")


def percentiles(history, cols=("up4", "dn4", "ratio5", "ratio10", "t2108", "up25q", "dn25q")):
    """Where the latest value sits in your own history (0-100), for calibration."""
    df = history[history["complete"]]
    if len(df) < 2:
        return {}
    out = {}
    for c in cols:
        r = _pct_rank(df[c].iloc[:-1], df[c].iloc[-1])
        out[c] = None if r is None else round(100 * r)
    return out
