"""Daily setup lists in the Stockbee / Qullamaggie style, from stored OHLCV.

Momentum burst (Stockbee 4% breakout, qualified with a 2LYNCH-style checklist):
  close >= +4%, volume above the prior day and >= 100k, price >= $3, then
  2  not up two days in a row before the breakout
  L  orderly prior trend: above a rising 20-day EMA, which is above the 50-day
  Y  young: no more than one other 4% burst in the prior 20 sessions
  N  narrow range or down day the day before
  C  consolidation: 5-day range <= 2.5 ADRs and volume not expanding before
  H  closes in the top 30% of the day's range
Anticipation (tight, quiet coil in a leader, before the breakout):
  RS Rating >= 85, within 10% of the 52-week high, above a rising 50-day EMA,
  ADR >= 4%, 5-day range <= 1.5 ADRs, and an NR7, inside day or volume dry-up (<= 0.7).
Episodic pivot: gap up 8-60% on >= 3x average volume that holds >= +5% at the close,
  price >= $5 and >= $20M average dollar volume.
"""
import numpy as np
import pandas as pd

ANT = {"rs_min": 85, "off_high": -0.10, "adr_min": 4.0, "tight_max": 1.5, "vdry_max": 0.7}


def masks(w, t, liquid):
    c, v = w["c"], w["v"]
    chg = t["chg"]
    burst = (chg >= 0.04) & (v > v.shift(1)) & (v >= 100_000) & (c >= 3) & liquid
    two = ~((chg.shift(1) > 0) & (chg.shift(2) > 0))
    L = (c.shift(1) > t["ema20"].shift(1)) & (t["ema20"].shift(1) > t["ema20"].shift(6)) & (t["ema20"].shift(1) > t["ema50"].shift(1))
    Y = burst.shift(1).rolling(20, min_periods=1).sum() <= 1
    rng = (w["h"] / w["l"] - 1) * 100
    N = (rng.shift(1) < t["adr"].shift(1)) | (chg.shift(1) < 0)
    C = (t["tight5"].shift(1) <= 2.5) & (t["vdry"].shift(1) <= 1.0)
    H = t["range_pos"] >= 0.7
    checks = {"2": two, "L": L, "Y": Y, "N": N, "C": C, "H": H}
    lynch = sum(m.astype(int) for m in checks.values())
    # quality: $5+, $20M+ average dollar volume, gap <= 60% (skips pumps/reverse-split noise)
    ep = ((t["gap"] >= 0.08) & (t["gap"] <= 0.6) & (v >= 3 * t["vol50"]) & (chg >= 0.05) & (c >= 5)
          & (c * t["vol50"] >= 20e6) & liquid)
    return burst, checks, lynch, ep


def anticipation_mask(w, t, rating, liquid):
    c = w["c"]
    e50 = t["ema50"]
    trigger = t["nr7"] | t["inside"] | (t["vdry"] <= ANT["vdry_max"])
    m = (liquid & (rating >= ANT["rs_min"]) & (t["off_high"] >= ANT["off_high"]) & (c > e50) & (e50 > e50.shift(10))
         & (t["adr"] >= ANT["adr_min"]) & (t["tight5"] <= ANT["tight_max"]) & trigger)
    return m


def evaluate_lists(w, t, ratings, liquid, dates, first, F):
    """Forward performance of each list vs the liquid universe (for tools/evaluate.py)."""
    c, h = w["c"], w["h"]
    rating = ratings.reindex(index=c.index, columns=c.columns)
    burst, checks, lynch, ep = masks(w, t, liquid)
    ant = anticipation_mask(w, t, rating, liquid)
    fwd = c.shift(-F) / c - 1
    hi = h[::-1].rolling(F, min_periods=1).max()[::-1].shift(-1)   # max high over next F days
    hit = (hi / c - 1) >= 0.08
    lists = {
        "Momentum bursts (all)": burst,
        "Momentum bursts 2LYNCH>=5": burst & (lynch >= 5),
        "Anticipation": ant,
        "Episodic pivots": ep,
    }
    rows = slice(first, len(dates) - F)
    base = liquid.iloc[rows]
    out = {}
    for name, m in lists.items():
        mm = m.iloc[rows].fillna(False).astype(bool)
        out[name] = {"n": int(mm.values.sum()),
                     "fwd": float(np.nanmean(fwd.iloc[rows].values[mm.values])) if mm.values.any() else np.nan,
                     "hit": float(np.nanmean(hit.iloc[rows].values[mm.values])) if mm.values.any() else np.nan,
                     "base_fwd": float(np.nanmean(fwd.iloc[rows].values[base.values])),
                     "base_hit": float(np.nanmean(hit.iloc[rows].values[base.values]))}
    return out


# ---------------------------------------------------------------------------
# Trade simulation (how these setups are actually traded) and regime stats
# ---------------------------------------------------------------------------
def _sim_close(mask, O, C, H, L, hold, first):
    """Enter at the signal day's close, stop at that day's low, exit at the close
    `hold` days later unless stopped (gap through the stop fills at the open)."""
    N = C.shape[0]
    out = []
    for i, j in np.argwhere(mask):
        if i < first or i + hold >= N:
            continue
        e, st = C[i, j], L[i, j]
        if not (e > 0 and 0 < st < e):
            continue
        x = None
        for k in range(1, hold + 1):
            if L[i + k, j] <= st:
                x = min(st, O[i + k, j]); break
        if x is None:
            x = C[i + hold, j]
        if np.isfinite(x):
            out.append((i, (x - e) / (e - st)))
    return out


def _sim_trigger(mask, O, C, H, L, hi5, lo5, hold, first, window=5):
    """Buy stop just above the 5-day high within `window` days; stop at the
    5-day low; exit `hold` days after entry."""
    N = C.shape[0]
    out = []
    for i, j in np.argwhere(mask):
        if i < first or i + window + hold >= N:
            continue
        tp, st = hi5[i, j] * 1.001, lo5[i, j]
        for k in range(1, window + 1):
            if H[i + k, j] >= tp:
                e = max(tp, O[i + k, j])
                if not st < e:
                    break
                x = st if L[i + k, j] <= st else None
                if x is None:
                    for q in range(1, hold + 1):
                        if L[i + k + q, j] <= st:
                            x = min(st, O[i + k + q, j]); break
                    if x is None:
                        x = C[i + k + hold, j]
                out.append((i, (x - e) / (e - st)))
                break
    return out


def regime_stats(w, t, rating, liquid, breadth, first=100, hold=3):
    """Average R per trade and win rate for each list, split by the breadth
    regime on the signal day: strong (5- and 10-day ratios >= 1.5), weak
    (10-day ratio < 1), mixed otherwise."""
    O, C, H, L = (w[k].to_numpy() for k in ("o", "c", "h", "l"))
    burst, checks, lynch, ep = masks(w, t, liquid)
    ant = anticipation_mask(w, t, rating, liquid)
    hi5 = w["h"].rolling(5).max().to_numpy(); lo5 = w["l"].rolling(5).min().to_numpy()
    br = breadth.reindex(w["c"].index)
    regime = np.where((br["ratio5"] >= 1.5) & (br["ratio10"] >= 1.5), "strong",
                      np.where(br["ratio10"] < 1, "weak", "mixed"))
    trades = {
        "bursts": _sim_close((burst & (lynch >= 5)).fillna(False).to_numpy(), O, C, H, L, hold, first),
        "anticipation": _sim_trigger(ant.fillna(False).to_numpy(), O, C, H, L, hi5, lo5, hold, first),
        "eps": _sim_close(ep.fillna(False).to_numpy(), O, C, H, L, 5, first),
    }
    from . import metrics as MT
    tw = MT.thrust_window(breadth, w["c"].index)
    out = {"days": {**{k: int((regime[first:] == k).sum()) for k in ("strong", "mixed", "weak")}, "thrust": int(tw[first:].sum())},
           "from": str(w["c"].index[first].date()), "to": str(w["c"].index[-1].date())}
    for name, tr in trades.items():
        out[name] = {}
        for k in ("all", "strong", "mixed", "weak", "thrust"):
            r = np.array([x for i, x in tr if k == "all" or (tw[i] if k == "thrust" else regime[i] == k)])
            out[name][k] = {"n": int(len(r)), "avg_r": round(float(r.mean()), 3) if len(r) else None,
                            "win": round(float((r > 0).mean()), 3) if len(r) else None}
    return out
