"""KQ watchlist: a daily screen for Kristjan Kullamägi's basic breakout setup.

Candidates (all must hold, on split-adjusted daily bars):
  price >= $3, 20-day ADR >= 5%, 20-day average dollar volume >= $20M,
  top 5% of stocks over 1, 3 or 6 months (wider than
  Kristjan's 1-2% so near-misses show up; the chart grade is still strict), close above the 50-day SMA,
  20-day SMA above the 50-day, a prior leg of +30% or more inside the last
  60 sessions, and no more than 25% off that leg's high.

Each candidate lands in ONE section, checked in this order:
  1. Not this setup / failing a rule
     - news or event bar: a 10%+ gap on 3x+ volume, or any 8x+ volume day,
       in the last 15 sessions (gap-and-go / episodic pivot, not a base)
     - rule 3, flat MAs: the 20-day SMA rose less than 0.9 ATR over 10 days
  2. Extended - wait for a handle: close 1.5+ ATR above the 20-day SMA
  3. Not this setup / failing a rule (continued)
     - rule 5, loose: 10-day range over 3.5 ATR, or 4+ closes crossing the
       10-day SMA in 20 sessions (chop)
  4. Basing - watch for the trigger: everything left, tightest first

These are screen proxies for chart rules, calibrated by hand on the Oct 9,
2026 candidates. A name on the list still needs a full chart grade.
"""
import numpy as np
import pandas as pd

CFG = {
    "min_price": 3.0, "min_adr": 5.0, "min_dvol": 20e6, "top_pct": 95.0,
    "min_leg": 0.30, "leg_days": 60, "max_off": -0.25,
    "gap": 0.10, "gap_vx": 3.0, "spike_vx": 8.0, "event_days": 15,
    "flat_angle": 0.9, "extended": 1.5, "loose_range": 3.5, "chop_cross": 4,
}
MIN_BARS = 127   # need ~6 months for the performance filter


def _r(v, n=2):
    return None if v is None or not np.isfinite(v) else round(float(v), n)


def _features(g):
    c, h, l, o, v = (g[k].to_numpy(dtype=float) for k in ("c", "h", "l", "o", "v"))
    pc = np.r_[np.nan, c[:-1]]
    tr = np.fmax(h - l, np.fmax(np.abs(h - pc), np.abs(l - pc)))
    atr = np.nanmean(tr[-14:])
    if not np.isfinite(atr) or atr <= 0 or c[-1] <= 0:
        return None
    cs = pd.Series(c)
    s10, s20, s50 = (cs.rolling(n).mean().to_numpy() for n in (10, 20, 50))
    vol50 = pd.Series(v).rolling(50).mean().shift(1).to_numpy()
    k = CFG["leg_days"]
    hi_i = int(np.argmax(h[-k:]))
    leg_lo = np.min(l[-k:][:hi_i + 1])
    leg_hi = h[-k:][hi_i]
    ev = CFG["event_days"]
    gaps = (o[1:] / c[:-1] - 1)[-ev:]
    vx = (v / vol50)[-ev:]
    vx_gap = vx[-len(gaps):]
    cross = int(np.sum(np.diff(np.sign(c[-20:] - s10[-20:])) != 0))
    return {
        "price": c[-1],
        "adr": (np.mean(h[-20:] / l[-20:]) - 1) * 100,
        "atr": atr / c[-1] * 100,
        "dvol": np.mean(c[-20:] * v[-20:]),
        "r1": c[-1] / c[-22] - 1, "r3": c[-1] / c[-64] - 1, "r6": c[-1] / c[-127] - 1,
        "s20": s20[-1], "s50": s50[-1],
        "leg": leg_hi / leg_lo - 1, "off": c[-1] / leg_hi - 1,
        "angle": (s20[-1] - s20[-11]) / atr,
        "ext": (c[-1] - s20[-1]) / atr,
        "rng10": (h[-10:].max() - l[-10:].min()) / atr,
        "cross": cross,
        "gap_ev": bool(np.any((gaps >= CFG["gap"]) & (vx_gap >= CFG["gap_vx"]))),
        "spike": bool(np.nanmax(vx) >= CFG["spike_vx"]) if np.isfinite(vx).any() else False,
        "day": c[-1] / c[-2] - 1,
        "pivot": float(np.max(h[-5:])),
    }


def _n(x):
    s = f"{x:.1f}"
    return "0.0" if s == "-0.0" else s


def classify(f):
    """Section and reason for one candidate's features."""
    if f["gap_ev"] or f["spike"]:
        why = "10%+ gap on heavy volume" if f["gap_ev"] else "8x+ volume day"
        return "reject", f"Not this setup: {why} in last 15 days (news/event, check catalyst)"
    if f["angle"] < CFG["flat_angle"]:
        return "reject", f"Rule 3: 20-day MA flat ({_n(f['angle'])} ATR rise in 10 days)"
    if f["ext"] >= CFG["extended"]:
        return "extended", f"{_n(f['ext'])} ATR above the 20-day: wait for a handle"
    if f["rng10"] > CFG["loose_range"] or f["cross"] >= CFG["chop_cross"]:
        what = f"10-day range {_n(f['rng10'])} ATR" if f["rng10"] > CFG["loose_range"] else f"{f['cross']} crosses of the 10-day"
        return "reject", f"Rule 5: loose/choppy base ({what})"
    return "basing", f"10-day range {_n(f['rng10'])} ATR, {_n(f['ext'])} ATR above the 20-day"


def build(adjusted, universe, names=None, tv=None):
    """Screen the common-stock universe on the latest day. Returns the payload dict."""
    names, tv = names or {}, tv or {}
    if adjusted.empty:
        return None
    last = adjusted["date"].max()
    df = adjusted[adjusted["ticker"].isin(universe)].sort_values(["ticker", "date"])
    feats = {}
    for t, g in df.groupby("ticker", sort=False):
        if len(g) < MIN_BARS or g["date"].iloc[-1] != last or g["c"].iloc[-1] < CFG["min_price"]:
            continue
        f = _features(g)
        if f:
            feats[t] = f
    if not feats:
        return None
    F = pd.DataFrame.from_dict(feats, orient="index")
    for k in ("r1", "r3", "r6"):
        F[k + "p"] = F[k].rank(pct=True) * 100
    F["top"] = F[["r1p", "r3p", "r6p"]].max(axis=1)
    cand = F[(F.adr >= CFG["min_adr"]) & (F.dvol >= CFG["min_dvol"]) & (F.top >= CFG["top_pct"])
             & (F.price > F.s50) & (F.s20 > F.s50) & (F.leg >= CFG["min_leg"]) & (F.off >= CFG["max_off"])]
    out = {"basing": [], "extended": [], "reject": []}
    for t, f in cand.iterrows():
        sec, why = classify(f)
        out[sec].append({"t": t, "name": names.get(t, ""), "price": _r(f.price), "adr": _r(f.adr, 1),
                         "atr": _r(f.atr, 1), "dvol": _r(f.dvol / 1e6, 0), "top": _r(f.top, 1),
                         "leg": _r(f.leg * 100, 0), "off": _r(f.off * 100, 1), "ext": _r(f.ext, 1),
                         "rng10": _r(f.rng10, 1), "angle": _r(f.angle, 1), "day": _r(f.day * 100, 1), "why": why,
                         "pivot": _r(f.pivot)})
    out["basing"].sort(key=lambda r: r["rng10"])
    out["extended"].sort(key=lambda r: r["ext"])
    out["reject"].sort(key=lambda r: r["why"])
    every = [r["t"] for s in out.values() for r in s]
    return {"date": last.strftime("%Y-%m-%d"), "cfg": CFG, "screened": len(F), "candidates": len(cand),
            **out, "tv": {t: tv[t] for t in every if t in tv}}
