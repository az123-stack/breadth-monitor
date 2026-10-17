"""Evidence for each decision layer -> data/layer_evidence.json (read by the Decision Cards and the weekly Reviewer).

Two kinds of evidence:
  * macro_fit: backtest on every past Trade Setups signal (tradesetups.backtest signals=True, actionable 5-session
    result `fwd_next`), with the macro tailwind measured as of each signal date (macrofit.research, no look-ahead).
  * log: forward results from data/decision_log.csv (every layer of every carded idea, settled 5 sessions later).
    This is the only way to test the agent layers (catalyst, calendar, macro brief), which can't be rebuilt for the past.

Promotion rule (DECISIONS.md): a layer "passes" only if the good-vs-bad difference has t >= 2 (dates as the unit, so
one busy day can't dominate) and the same sign in both halves of the sample. Passing does not change rankings by
itself; Adam approves any change.

    python -m breadth.layers macro [--signals FILE]   # recompute macro-fit evidence (~3 min: replays the backtest)
    python -m breadth.layers log                       # recompute decision-log evidence (seconds)
    python -m breadth.layers report                    # print both, plain text (for the Reviewer)
"""
import argparse
import json
import pickle
import sys
from datetime import date

import numpy as np
import pandas as pd

from . import config

T_PASS = 2.0
MIN_DATES = 20


def load():
    try:
        return json.loads((config.DATA_DIR / "layer_evidence.json").read_text())
    except Exception:
        return {}


def save(ev):
    (config.DATA_DIR / "layer_evidence.json").write_text(json.dumps(ev, indent=1, default=float))


def compare(df, good, bad, ret="fwd_next", date_col="date"):
    """Good vs bad group: averages, date-paired t, both halves. good / bad: boolean masks."""
    df = df.assign(_d=pd.to_datetime(df[date_col]))
    a, b = df[good], df[bad]
    out = {"n_good": int(len(a)), "n_bad": int(len(b)),
           "avg_good": None if a.empty else round(float(a[ret].mean()), 5),
           "avg_bad": None if b.empty else round(float(b[ret].mean()), 5)}
    ga, gb = a.groupby("_d")[ret].mean(), b.groupby("_d")[ret].mean()
    j = pd.concat([ga, gb], axis=1, keys=["a", "b"]).dropna()
    d = j["a"] - j["b"]
    out["dates"] = int(len(d))
    out["diff"] = None if (a.empty or b.empty) else round(out["avg_good"] - out["avg_bad"], 5)
    out["t"] = round(float(d.mean() / d.std() * np.sqrt(len(d))), 2) if len(d) >= 3 and d.std() > 0 else None
    mid = df["_d"].sort_values().iloc[len(df) // 2] if len(df) else None
    halves = []
    for part in (df["_d"] < mid, df["_d"] >= mid) if mid is not None else ():
        pa, pb = df[good & part], df[bad & part]
        halves.append(None if pa.empty or pb.empty else round(float(pa[ret].mean() - pb[ret].mean()), 5))
    out["halves"] = halves
    out["passed"] = bool(out["t"] is not None and out["t"] >= T_PASS and out["dates"] >= MIN_DATES
                         and len(halves) == 2 and all(h is not None and h > 0 for h in halves))
    return out


# ---------------------------------------------------------------- macro fit (backtest)
def capture_signals():
    """Replay the Trade Setups backtest in memory and return its per-signal frame (no files written)."""
    from . import store, update, tradesetups as TS, site
    box = {}
    orig, orig_build = TS.backtest, site.build

    def wrapped(*a, **k):
        res, sig = orig(*a, **{**k, "signals": True})
        box["sig"] = sig
        return res
    TS.backtest = wrapped
    site.build = lambda *a, **k: None                       # don't rewrite the page
    import breadth.ledger as LG, breadth.decision as DC, breadth.metrics as MT
    saved = (LG.record, LG.settle, DC.record, DC.settle, store.save_breadth)
    LG.record = LG.settle = DC.record = DC.settle = store.save_breadth = lambda *a, **k: None
    try:
        bars = store.load_bars()
        update.recompute_and_publish(bars, store.load_splits(), store.load_universe(), store.load_state())
    finally:
        TS.backtest, site.build = orig, orig_build
        LG.record, LG.settle, DC.record, DC.settle, store.save_breadth = saved
    return box.get("sig")


def study_macro(signals=None):
    from . import store, macro, macrofit
    if signals is None:
        signals = capture_signals()
    adj = store.apply_splits(store.load_bars(), store.load_splits())
    r = macrofit.research(signals, adj, macro.load())
    r = r[r["filled"].astype(bool) & r["fwd_next"].notna()]
    res = {"asof": date.today().isoformat(), "signals": int(len(r)),
           "from": str(pd.to_datetime(r["date"]).min().date()), "to": str(pd.to_datetime(r["date"]).max().date()),
           "rule": "tailwind = macro moves of the last 5 sessions imply > +0.25% for the stock (real sensitivities only); "
                   "headwind < -0.25%; result = actionable 5-session return of each Trade Setups signal"}
    for n in (5, 20):
        col = f"tail{n}"
        res[col] = compare(r, r[col] > 0.25, r[col] < -0.25)
    res["passed"] = bool(res["tail5"]["passed"])
    by = {}
    for s, g in r.groupby("setup"):
        x = compare(g, g["tail5"] > 0.25, g["tail5"] < -0.25)
        by[s] = {k: x[k] for k in ("n_good", "n_bad", "diff", "t")}
    res["by_setup"] = by
    return res


# ---------------------------------------------------------------- decision log (forward)
def study_log():
    from . import decision
    df = decision.load_log()
    df = df[df["status"] == "closed"].copy()
    out = {"asof": date.today().isoformat(), "closed": int(len(df)),
           "dates": int(df["date"].nunique()) if len(df) else 0}
    if df.empty:
        out["note"] = "no settled rows yet"
        return out
    df["ex"] = df["fwd5"].astype(float) - df["spy5"].astype(float)
    tests = {
        "catalyst_positive": (df["cat_dir"] == "positive", df["cat_dir"].isin(["negative", "none"])),
        "red_flags": (df["red_flags"].fillna("") == "", df["red_flags"].fillna("") != ""),
        "earnings_in_hold": (~df["earn_days"].between(0, decision.HOLD), df["earn_days"].between(0, decision.HOLD)),
        "brief_low_risk": (df["brief_risk"] == "low", df["brief_risk"] == "high"),
        "macro_tailwind": (df["tail5"].astype(float) > 0.25, df["tail5"].astype(float) < -0.25),
        "more_support": (df["support"].astype(float) >= 4, df["support"].astype(float) <= 2),
        "no_warnings": (df["warn"].astype(float) == 0, df["warn"].astype(float) >= 2),
    }
    for k, (g, b) in tests.items():
        out[k] = compare(df, g.fillna(False), b.fillna(False), ret="ex")
    return out


def report(ev=None):
    ev = ev or load()
    lines = []
    m = ev.get("macro_fit")
    if m:
        t5 = m["tail5"]
        lines.append(f"Macro fit (backtest {m['from']}..{m['to']}, {m['signals']} signals): tailwind {t5['avg_good']:+.2%} "
                     f"(n {t5['n_good']}) vs headwind {t5['avg_bad']:+.2%} (n {t5['n_bad']}), t {t5['t']}, halves {t5['halves']} "
                     f"-> {'PASSED' if m['passed'] else 'not proven (information only)'}")
    lg = ev.get("log")
    if lg:
        lines.append(f"Decision log: {lg.get('closed', 0)} settled rows over {lg.get('dates', 0)} dates")
        for k, v in lg.items():
            if isinstance(v, dict) and "t" in v:
                lines.append(f"  {k}: good {v['avg_good']} (n {v['n_good']}) vs bad {v['avg_bad']} (n {v['n_bad']}), "
                             f"t {v['t']}, halves {v['halves']} -> {'PASSED' if v['passed'] else 'not proven'}")
    return "\n".join(lines) or "no evidence yet"


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["macro", "log", "report"])
    p.add_argument("--signals")
    a = p.parse_args(argv)
    ev = load()
    if a.cmd == "macro":
        sig = pickle.load(open(a.signals, "rb")) if a.signals else None
        ev["macro_fit"] = study_macro(sig)
        save(ev)
    elif a.cmd == "log":
        ev["log"] = study_log()
        save(ev)
    print(report(ev))


if __name__ == "__main__":
    sys.exit(main())
