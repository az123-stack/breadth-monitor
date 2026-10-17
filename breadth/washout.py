"""Washout thrust: which breadth thrusts came out of a deep washout, and the
high-beta leaders list that paid after them.

Research (Oct 16, 2026, ~2 years of bars): after a thrust that followed an SPY
pullback of 8%+ with T2108 at 25 or below (Apr 9 2025, Mar 31 2026), the 30
stocks with RS >= 80 and the highest 60-day beta to SPY made +26% and +33% in
the next 21 sessions (all stocks +9% / +8%). After the five shallow thrusts the
same list made -26% to +9%. Hidden "hub" groups did not lead the rebound, and
plain RS lagged in thrust windows (momentum-crash pattern), so the edge is
sensitivity to the market, gated on the depth of the washout. Two events:
information only, not a proven rule.
"""
import numpy as np
import pandas as pd

from . import config as C, metrics, strength


def _event_stats(i, spy, t2108):
    hi = spy.iloc[max(0, i - 59):i + 1].max()
    lo = spy.iloc[max(0, i - 14):i + 1].min()
    pull = float(lo / hi - 1) if hi and np.isfinite(hi) else None
    tlo = t2108.iloc[max(0, i - 9):i + 1].min()
    tlo = None if pd.isna(tlo) else float(tlo)
    deep = pull is not None and tlo is not None and pull <= -C.WASHOUT_PULLBACK and tlo <= C.WASHOUT_T2108
    return pull, tlo, bool(deep)


def basket(i, w, r, spyr, rs, tradeable):
    """RS >= WASHOUT_MIN_RS, top WASHOUT_TOP by 60-day beta to SPY, as of row i."""
    if i < 60:
        return []
    R = r.iloc[i - 59:i + 1]
    m = spyr.iloc[i - 59:i + 1]
    ok = tradeable.iloc[i] & (R.notna().sum() >= 57) & (rs.iloc[i] >= C.WASHOUT_MIN_RS)
    cols = ok[ok].index
    if not len(cols):
        return []
    X = R[cols].fillna(0.0)
    mc = (m - m.mean()).fillna(0.0)
    beta = (X - X.mean()).mul(mc, axis=0).sum() / float((mc ** 2).sum())
    return list(beta.sort_values(ascending=False).head(C.WASHOUT_TOP).items())


def build(adjusted, history, universe, names=None, w=None):
    names = names or {}
    w = w or strength.wide_all(adjusted)
    c, o, v = w["c"], w["o"], w["v"]
    if C.BENCHMARK not in c.columns:
        return None
    dates = c.index
    spy = c[C.BENCHMARK]
    h = history[history["complete"]] if "complete" in history.columns else history
    t2108 = h["t2108"].reindex(dates)
    uni = pd.Series(c.columns.isin(list(universe)), index=c.columns)
    r = (c / c.shift(1) - 1).clip(-0.6, 1.5)
    spyr = r[C.BENCHMARK]
    adv50 = (c * v).rolling(50, min_periods=40).mean()
    tradeable = (c >= 5) & (adv50 >= C.WASHOUT_MIN_DVOL) & uni
    liquid = (c >= C.MIN_PRICE) & (v.rolling(20, min_periods=15).mean() >= C.MIN_AVG_VOLUME) & uni
    pos = {d: k for k, d in enumerate(dates)}

    evs = [e for e in metrics.events(history) if e["kind"] == "thrust"]
    rows_i = sorted({pos[pd.Timestamp(e["date"])] for e in evs if pd.Timestamp(e["date"]) in pos})
    last = len(dates) - 1
    need = [i for i in rows_i if i >= 60] + [last]
    rs_df, _, _ = strength.rs_ratings(c, liquid, sorted(set(need)))
    rs_full = pd.DataFrame(np.nan, index=dates, columns=c.columns)
    rs_full.loc[rs_df.index] = rs_df.values

    events = []
    for i in rows_i:
        pull, tlo, deep = _event_stats(i, spy, t2108)
        ev = {"date": dates[i].strftime("%Y-%m-%d"), "pullback": None if pull is None else round(pull, 4),
              "t2108_low": None if tlo is None else round(tlo, 1), "deep": deep, "sessions": last - i}
        picks = basket(i, w, r, spyr, rs_full, tradeable) if i >= 60 else []
        if picks and i + 1 <= last:
            j = min(i + C.WASHOUT_WINDOW, last)
            tk = [t for t, _ in picks]
            ent = o.iloc[i + 1][tk]
            ret = (c.iloc[j][tk] / ent - 1)
            allt = tradeable.iloc[i]
            all_ret = (c.iloc[j][allt[allt].index] / o.iloc[i + 1][allt[allt].index] - 1).replace([np.inf, -np.inf], np.nan)
            ev.update({"held": j - i, "done": j - i >= C.WASHOUT_WINDOW,
                       "basket": round(float(ret.mean()), 4), "basket_med": round(float(ret.median()), 4),
                       "all": round(float(all_ret.mean()), 4),
                       "spy": round(float(c[C.BENCHMARK].iloc[j] / o[C.BENCHMARK].iloc[i + 1] - 1), 4),
                       "picks": [{"t": t, "name": names.get(t, ""), "beta": round(float(b), 2),
                                  "rs": None if pd.isna(rs_full.at[dates[i], t]) else int(rs_full.at[dates[i], t]),
                                  "ret": None if pd.isna(ret[t]) else round(float(ret[t]), 4)} for t, b in picks]})
        events.append(ev)

    cur = events[-1] if events and events[-1]["sessions"] < C.WASHOUT_WINDOW else None
    state = "none" if cur is None else ("washout" if cur["deep"] else "shallow")
    pull_now, tlo_now, _ = _event_stats(last, spy, t2108)
    # today's would-be list (for the watch view): who is most market-sensitive among strong stocks right now
    now = basket(last, w, r, spyr, rs_full, tradeable)
    done = [e for e in events if e.get("done")]
    return {"date": dates[last].strftime("%Y-%m-%d"), "state": state, "current": cur,
            "rules": {"pullback": C.WASHOUT_PULLBACK, "t2108": C.WASHOUT_T2108, "window": C.WASHOUT_WINDOW,
                      "min_rs": C.WASHOUT_MIN_RS, "top": C.WASHOUT_TOP, "dvol": C.WASHOUT_MIN_DVOL},
            "now": {"pullback": None if pull_now is None else round(pull_now, 4), "t2108_low": None if tlo_now is None else round(tlo_now, 1),
                    "list": [{"t": t, "name": names.get(t, ""), "beta": round(float(b), 2),
                              "rs": None if pd.isna(rs_full.at[dates[last], t]) else int(rs_full.at[dates[last], t])} for t, b in now[:15]]},
            "events": [{k: e[k] for k in e if k != "picks"} for e in events],
            "deep_n": sum(e["deep"] for e in done), "shallow_n": sum(not e["deep"] for e in done)}
