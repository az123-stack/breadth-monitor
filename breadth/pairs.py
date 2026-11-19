"""Ratio watch: RSP / SPY and MAGS / SOXX on the Breadth tab (Adam, Nov 18, 2026). Information only.

RSP / SPY  equal-weight S&P 500 vs cap-weight. Rising = the average stock beats the index (broad market);
           falling = a few megacaps carry the index.
MAGS / SOXX  the Magnificent 7 vs semiconductors. Rising = money hiding in the mega-platforms;
           falling = money in chips (the more aggressive AI trade).

Each ratio uses the real ETFs when their bars are stored (config.RATIO_ETFS are fetched like theme ETFs).
Until then, or if an ETF has gaps, it falls back to a basket built from member stocks: equal-weight S&P 500
members (data/index_members.csv) for RSP, equal-weight Mag 7 for MAGS. `src` says which one was used.

Evidence (recomputed every build): SPY next open -> 5 and 21 sessions later, split by the ratio's 20-day change
(bottom / top 20%) and by above / below its 50-day average, plus the rank correlation in each half of history.
Nothing here moves the picks (DECISIONS.md); layer `ratio_watch` in data/layers.json.
"""
import numpy as np
import pandas as pd

from . import config as C

MAG7 = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA"]
PAIRS = [
    {"key": "rsp_spy", "a": "RSP", "b": "SPY", "label": "Equal weight vs cap weight (RSP ÷ SPY)",
     "up": "average stock beating the index · broad", "dn": "megacaps carrying the index · narrow"},
    {"key": "mags_soxx", "a": "MAGS", "b": "SOXX", "label": "Mag 7 vs chips (MAGS ÷ SOXX)",
     "up": "money in the mega-platforms", "dn": "money in semiconductors"},
]
MA = 50
CHG = 20
HORIZONS = (5, 21)
MAX_DAY = 0.35      # a one-day move this big in a basket member is treated as a bad print / missed split


def _f(v, nd=2):
    if v is None or pd.isna(v) or not np.isfinite(v):
        return None
    return round(float(v), nd)


def _members():
    p = C.DATA_DIR / "index_members.csv"
    if not p.exists():
        return []
    d = pd.read_csv(p, dtype=str)
    return sorted(set(d.loc[d["index"] == "SPX", "ticker"]))


def _basket(close, tickers):
    cols = [t for t in tickers if t in close.columns]
    if len(cols) < max(3, len(tickers) // 2):
        return None
    r = close[cols].pct_change(fill_method=None)
    r = r.mask(r.abs() > MAX_DAY)
    return (1 + r.mean(axis=1).fillna(0)).cumprod()


def _leg(close, etf, basket):
    """Real ETF if it covers the whole window, else the member basket."""
    if etf in close.columns:
        s = close[etf]
        if s.notna().mean() >= 0.98:
            return s.ffill(), "etf"
    if basket is None:
        return None, None
    return _basket(close, basket), "basket"


def _bt(sig, fwd):
    df = pd.DataFrame({"s": sig, "f": fwd}).dropna()
    if len(df) < 60:
        return None
    lo, hi = df.s.quantile(0.2), df.s.quantile(0.8)
    out = {}
    for name, m in (("low", df.s <= lo), ("mid", (df.s > lo) & (df.s < hi)), ("high", df.s >= hi), ("all", df.s == df.s)):
        x = df.f[m]
        out[name] = {"n": int(len(x)), "spy": _f(100 * x.mean(), 2), "up": _f(100 * (x > 0).mean(), 0)}
    half = len(df) // 2
    out["ic"] = _f(df.s.corr(df.f, method="spearman"), 2)
    out["ic_halves"] = [_f(df.s.iloc[:half].corr(df.f.iloc[:half], method="spearman"), 2),
                        _f(df.s.iloc[half:].corr(df.f.iloc[half:], method="spearman"), 2)]
    return out


def _bt_trend(above, fwd):
    df = pd.DataFrame({"a": above, "f": fwd}).dropna()
    if len(df) < 60:
        return None
    res = {}
    for name, m in (("above", df.a > 0.5), ("below", df.a < 0.5)):
        x = df.f[m]
        res[name] = {"n": int(len(x)), "spy": _f(100 * x.mean(), 2), "up": _f(100 * (x > 0).mean(), 0)}
    return res


def build(adjusted, dates=None):
    """adjusted = split-adjusted daily bars (date, ticker, o, c, ...); dates = breadth-history dates to report on."""
    bars = adjusted[adjusted["ticker"].isin(set(MAG7) | set(_members()) | {p["a"] for p in PAIRS} | {p["b"] for p in PAIRS})]
    close = bars.pivot_table(index="date", columns="ticker", values="c").sort_index().astype(float)
    opn = bars.pivot_table(index="date", columns="ticker", values="o").sort_index().astype(float)
    if C.BENCHMARK not in close:
        return None
    spy_c, spy_o = close[C.BENCHMARK], opn[C.BENCHMARK]
    fwd = {n: spy_c.shift(-n) / spy_o.shift(-1) - 1 for n in HORIZONS}      # buy next open, hold n sessions
    baskets = {"RSP": _members(), "MAGS": MAG7}
    out = []
    for p in PAIRS:
        a, src_a = _leg(close, p["a"], baskets.get(p["a"]))
        b, src_b = _leg(close, p["b"], baskets.get(p["b"]))
        if a is None or b is None:
            continue
        ratio = (a / b).dropna()
        if len(ratio) < MA + CHG:
            continue
        ratio = 100 * ratio / ratio.iloc[0]
        ma = ratio.rolling(MA).mean()
        chg = ratio / ratio.shift(CHG) - 1
        above = (ratio > ma).astype(float).where(ma.notna())
        yr = ratio.iloc[-252:]
        last = ratio.iloc[-1]
        c20, c5 = chg.iloc[-1], ratio.iloc[-1] / ratio.iloc[-6] - 1 if len(ratio) > 6 else np.nan
        hist_chg = chg.dropna()
        state = ("up" if (last > ma.iloc[-1] and c20 > 0) else "down" if (last < ma.iloc[-1] and c20 < 0) else "mixed")
        keep = pd.DatetimeIndex(dates) if dates is not None else ratio.index
        ser = ratio.reindex(keep)
        mas = ma.reindex(keep)
        out.append({
            "key": p["key"], "label": p["label"], "a": p["a"], "b": p["b"], "up_txt": p["up"], "dn_txt": p["dn"],
            "src": {p["a"]: src_a, p["b"]: src_b},
            "date": ratio.index[-1].strftime("%Y-%m-%d"),
            "v": _f(last, 2), "ma": _f(ma.iloc[-1], 2), "above": bool(last > ma.iloc[-1]),
            "d5": _f(100 * c5, 1), "d20": _f(100 * c20, 1),
            "d20_pct": _f(100 * (hist_chg < c20).mean(), 0) if len(hist_chg) else None,
            "yr_pct": _f(100 * (last - yr.min()) / (yr.max() - yr.min()), 0) if yr.max() > yr.min() else None,
            "state": state,
            "dates": [d.strftime("%Y-%m-%d") for d in keep],
            "series": [_f(v, 2) for v in ser], "ma50": [_f(v, 2) for v in mas],
            "bt": {f"chg{n}": _bt(chg, fwd[n]) for n in HORIZONS} | {f"trend{n}": _bt_trend(above, fwd[n]) for n in HORIZONS},
        })
    return {"pairs": out, "ma": MA, "chg": CHG} if out else None
