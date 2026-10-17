"""Macro fit layer: how each stock reacts to rates, oil and the dollar, and whether recent macro moves help or hurt it.

For every stock we regress its daily return on SPY's return plus three macro moves over the last WINDOW sessions
(only data up to the day measured, so the same numbers can be rebuilt for any past date):

    r_stock = a + b_mkt*r_SPY + b_tnx*d(10-yr yield, pts) + b_oil*r_WTI + b_usd*r_DXY

Controlling for SPY isolates the macro part (a stock that falls when yields rise only because the whole market
does gets no rate sensitivity). A sensitivity counts as "real" only when its t-stat is >= T_MIN; the others are
shown as "no clear link".

Tailwind = the return those real sensitivities imply from the macro moves of the last N sessions, in % of the stock.
Positive = rates / oil / dollar have recently moved in the stock's favour. It is information on the cards; it does
not change any ranking unless its backtest (research()) passes and Adam approves (see DECISIONS.md).
"""
import numpy as np
import pandas as pd

WINDOW = 120         # sessions of history per regression
MIN_OBS = 80
T_MIN = 2.0          # |t| needed before a sensitivity counts
FACTORS = ("tnx", "oil", "usd")
LABEL = {"tnx": "10-yr yield", "oil": "oil", "usd": "dollar"}
UNIT = {"tnx": 0.10, "oil": 0.01, "usd": 0.01}       # shown per +10bp yield, +1% oil, +1% dollar


def factor_frame(macro_cache, dates):
    """Daily macro moves aligned to our bar dates: tnx = change in yield (percentage points),
    oil / usd = % return. Days the macro market was shut are filled forward (move 0)."""
    def ser(key):
        rows = (macro_cache.get(key) or {}).get("rows") or []
        if not rows:
            return None
        s = pd.Series({pd.Timestamp(d): float(v) for d, v in rows}).sort_index()
        return s.reindex(s.index.union(dates)).ffill().reindex(dates)
    lv = {"tnx": ser("tnx"), "oil": ser("crude"), "usd": ser("dxy")}
    if any(v is None for v in lv.values()):
        return None, None
    levels = pd.DataFrame(lv)
    moves = pd.DataFrame({"tnx": levels["tnx"].diff(), "oil": levels["oil"].pct_change(fill_method=None),
                          "usd": levels["usd"].pct_change(fill_method=None)})
    return moves, levels


def _ols(y, X):
    """OLS with t-stats. y (n,), X (n,k) incl. constant. Returns (beta, t) or (None, None)."""
    ok = np.isfinite(y) & np.isfinite(X).all(axis=1)
    y, X = y[ok], X[ok]
    n, k = X.shape
    if n < MIN_OBS:
        return None, None
    XtX_inv = np.linalg.pinv(X.T @ X)
    b = XtX_inv @ X.T @ y
    resid = y - X @ b
    s2 = resid @ resid / max(n - k, 1)
    se = np.sqrt(np.clip(np.diag(XtX_inv) * s2, 1e-18, None))
    return b, b / se


def fit_at(ret, spy_ret, moves, i, window=WINDOW):
    """Sensitivities for one stock as of row i (inclusive). ret / spy_ret: 1-D arrays; moves: (N,3) array."""
    lo = max(0, i - window + 1)
    X = np.column_stack([np.ones(i + 1 - lo), spy_ret[lo:i + 1], moves[lo:i + 1]])
    b, t = _ols(ret[lo:i + 1], X)
    if b is None:
        return None
    return {"mkt": b[1], **{f: b[2 + k] for k, f in enumerate(FACTORS)},
            **{f"t_{f}": t[2 + k] for k, f in enumerate(FACTORS)}}


def tailwind(fit, moves, i, n=5):
    """% stock return implied by the last n sessions' macro moves, using only sensitivities with |t| >= T_MIN."""
    if fit is None or i < n:
        return None
    m = np.nansum(moves[i - n + 1:i + 1], axis=0)
    tot = 0.0
    for k, f in enumerate(FACTORS):
        if abs(fit[f"t_{f}"]) >= T_MIN:
            tot += fit[f] * m[k]
    return tot * 100


def words(fit):
    """Plain-English sensitivities, real ones only."""
    if fit is None:
        return []
    out = []
    for f in FACTORS:
        if abs(fit[f"t_{f}"]) < T_MIN:
            continue
        eff = fit[f] * UNIT[f] * 100
        step = "+10bp" if f == "tnx" else "+1%"
        out.append(f"{step} {LABEL[f]} → {eff:+.1f}%")
    return out


def build(adjusted, macro_cache, tickers, bench="SPY"):
    """Macro fit for each ticker as of the last bar: sensitivities, words, 5- and 20-session tailwind,
    plus the macro moves themselves (for the card / banner). Never raises; returns {} without macro data."""
    try:
        c = adjusted.pivot_table(index="date", columns="ticker", values="c").sort_index()
        dates = c.index
        moves_df, levels = factor_frame(macro_cache, dates)
        if moves_df is None or bench not in c.columns:
            return {}
        R = c.pct_change(fill_method=None)
        spy = R[bench].to_numpy()
        M = moves_df.to_numpy()
        i = len(dates) - 1
        out = {}
        for t in tickers:
            if t not in R.columns:
                continue
            fit = fit_at(R[t].to_numpy(), spy, M, i)
            if fit is None:
                continue
            out[t] = {"words": words(fit),
                      "tail5": None if (v := tailwind(fit, M, i, 5)) is None else round(v, 2),
                      "tail20": None if (v := tailwind(fit, M, i, 20)) is None else round(v, 2),
                      "sens": {f: round(fit[f] * UNIT[f] * 100, 2) for f in FACTORS},
                      "t": {f: round(fit[f"t_{f}"], 1) for f in FACTORS}}
        last = levels.iloc[-1]
        ctx = {"date": dates[-1].strftime("%Y-%m-%d"),
               "tnx": round(float(last["tnx"]), 3), "oil": round(float(last["oil"]), 2), "usd": round(float(last["usd"]), 2),
               "tnx_d5": round(float(levels["tnx"].iloc[-1] - levels["tnx"].iloc[-6]) * 100, 1),     # bp
               "oil_d5": round(float(levels["oil"].iloc[-1] / levels["oil"].iloc[-6] - 1) * 100, 1),
               "usd_d5": round(float(levels["usd"].iloc[-1] / levels["usd"].iloc[-6] - 1) * 100, 1)}
        return {"stocks": out, "ctx": ctx}
    except Exception:            # optional layer: never block the build
        import logging
        logging.getLogger(__name__).exception("macro fit failed")
        return {}


def research(signals, adjusted, macro_cache, bench="SPY", n_list=(5, 20)):
    """Per-signal tailwind as of each signal date (no look-ahead). signals: frame with columns date, t, fwd_next.
    Returns the frame with tail5 / tail20 columns added (NaN where history is too short)."""
    c = adjusted.pivot_table(index="date", columns="ticker", values="c").sort_index()
    dates = c.index
    moves_df, _ = factor_frame(macro_cache, dates)
    R = c.pct_change(fill_method=None)
    spy = R[bench].to_numpy()
    M = moves_df.to_numpy()
    pos = {d: k for k, d in enumerate(dates)}
    cols = {f"tail{n}": [] for n in n_list}
    cache = {}
    for d, t in zip(pd.to_datetime(signals["date"]), signals["t"]):
        i = pos.get(d)
        fit = None
        if i is not None and t in R.columns:
            key = (t, i)
            fit = cache.get(key)
            if fit is None:
                fit = cache[key] = fit_at(R[t].to_numpy(), spy, M, i)
        for n in n_list:
            v = tailwind(fit, M, i, n) if fit is not None else None
            cols[f"tail{n}"].append(np.nan if v is None else v)
    out = signals.copy()
    for k, v in cols.items():
        out[k] = v
    return out
