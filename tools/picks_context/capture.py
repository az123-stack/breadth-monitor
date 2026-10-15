"""Capture every past Trade Setups signal (with features and the actionable 5-session result) by running a normal
--rebuild-only with tradesetups.backtest wrapped to return its per-signal frame. Writes signals.pkl here."""
import os, pickle, sys, runpy
sys.path.insert(0, "/home/claude/breadth-monitor")
from breadth import tradesetups as TS
orig = TS.backtest
def wrapped(*a, **k):
    out, sig = orig(*a, **{**k, "signals": True})
    pickle.dump(sig, open(os.path.join(os.path.dirname(__file__), "signals.pkl"), "wb"))
    return out
TS.backtest = wrapped
sys.argv = ["update", "--rebuild-only"]
runpy.run_module("breadth.update", run_name="__main__")
