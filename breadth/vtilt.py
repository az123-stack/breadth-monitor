"""Volume tilt: is volume pressing into the up moves or the down moves? (Breadth tab, Oct 17, 2026)

Every share bought is also sold, so plain volume can't show imbalance. Volume tilt compares the stocks that
moved up meaningfully (> 0.5 of their own 20-day volatility) with those that moved down: median volume vs each
stock's own 50-day average on each side, log ratio, 10-day average, x100 (`metrics.vtilt10`).

Positive = up moves carry the heavier volume (buyers pressing). Negative = up moves come on lighter volume than
down moves. What a negative reading means depends on where it happens (Wyckoff's "no supply" vs "no demand"):
right after a major breadth thrust it was a healthy light-volume rally (sellers already gone); any other time it
came before weak markets (buyers tiring). The evidence is recomputed here every build from our own history.

Study (Oct 2024–Oct 2026, dashboard thrust events, 25-session window, SPY next open → 21 sessions later):
low tilt (bottom 20%) outside thrust windows SPY −3.5%, up 18% (n 33; episodes Jan–Mar 2025, Feb 2026);
low tilt after a thrust +2.5%, up 73% (n 49); high tilt (top 20%) +2.5% either way. About 4 independent
episodes per side, overlapping windows: context, not a stand-alone signal.
"""
import numpy as np
import pandas as pd

from . import config as C, metrics


def _f(v, nd=2):
    if v is None or (isinstance(v, float) and not np.isfinite(v)) or pd.isna(v):
        return None
    return round(float(v), nd)


def build(history, spy_bars):
    """history = breadth history (with vtilt10); spy_bars = SPY daily bars (date, o, c)."""
    h = history[history["complete"]] if "complete" in history else history
    s = h["vtilt10"].dropna() if "vtilt10" in h else pd.Series(dtype=float)
    if len(s) < 60:
        return None
    post = pd.Series(metrics.thrust_window(history, list(history.index), C.TILT_WINDOW),
                     index=history.index).reindex(h.index).fillna(False).astype(bool)
    lo, hi = float(s.quantile(0.2)), float(s.quantile(0.8))

    spy = spy_bars.drop_duplicates("date").set_index("date").sort_index()
    o, c = spy["o"].astype(float).reindex(h.index), spy["c"].astype(float).reindex(h.index)
    n = C.TILT_HORIZON
    fwd = c.shift(-n) / o.shift(-1) - 1          # buy next open, hold n sessions

    df = pd.DataFrame({"v": h["vtilt10"], "post": post, "fwd": fwd}).dropna(subset=["v"])
    df["tier"] = np.where(df.v <= lo, "low", np.where(df.v >= hi, "high", "mid"))
    base = df.dropna(subset=["fwd"])
    bt = {}
    for side, m in (("post", base.post), ("other", ~base.post)):
        bt[side] = {}
        for t in ("low", "mid", "high"):
            x = base[m & (base.tier == t)].fwd
            bt[side][t] = {"n": int(len(x)), "spy": _f(100 * x.mean(), 1) if len(x) else None,
                           "up": _f(100 * (x > 0).mean(), 0) if len(x) else None}
    allx = base.fwd
    bt["all"] = {"n": int(len(allx)), "spy": _f(100 * allx.mean(), 1), "up": _f(100 * (allx > 0).mean(), 0)}

    last_d = df.index[-1]
    last = df.iloc[-1]
    # sessions since the latest major thrust / follow-through (None if none in our history)
    since, thrust_date = None, None
    try:
        ev = [e for e in metrics.events(history)
              if e.get("kind") in ("thrust", "followthrough") and e.get("tier") == "major"]
        if ev:
            thrust_date = ev[-1]["date"]
            since = int(len(h.loc[pd.Timestamp(thrust_date):]) - 1)
    except Exception:
        pass
    # EXPERIMENTAL (Oct 17, 2 events): a thrust whose next 1-2 sessions put >= TILT_UNCONFIRM_SHARE% of dollar volume
    # in falling stocks is "unconfirmed" on this tile (Apr 9 2025 -> 91% next day, still worked; Oct 15 2026 -> 71%).
    # Only the tile's wording changes; the playbook's post-thrust window is untouched.
    unconfirmed, next_share = False, None
    if thrust_date is not None and "dn_share" in h:
        nxt = h.loc[pd.Timestamp(thrust_date):, "dn_share"].iloc[1:3].dropna()
        if len(nxt):
            next_share = _f(nxt.max(), 0)
            unconfirmed = bool(nxt.max() >= C.TILT_UNCONFIRM_SHARE)
    row = h.loc[last_d]
    return {
        "date": last_d.strftime("%Y-%m-%d"),
        "v": _f(last.v), "up": _f(row.get("vt_up")), "dn": _f(row.get("vt_dn")),
        "pct": int(round(100 * (s < last.v).mean())),
        "tier": last.tier, "post": bool(last.post),
        "since": since, "thrust_date": thrust_date, "unconfirmed": unconfirmed and bool(last.post),
        "next_share": next_share, "unconfirm_share": C.TILT_UNCONFIRM_SHARE,
        "lo": _f(lo), "hi": _f(hi), "window": C.TILT_WINDOW, "horizon": n,
        "bt": bt, "from": df.index[0].strftime("%Y-%m-%d"),
        "post_dates": [d.strftime("%Y-%m-%d") for d in df.index[df.post]],
    }
