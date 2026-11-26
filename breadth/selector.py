"""What to trade today (Nov 24, 2026; Adam: "figure out a way to tell me what type of setup I should be trading in any given market condition,
starting tomorrow, and add that to the trade brief"). v3 Brief → "What to trade" (first sub-tab). Info only, layer `setup_selector`.

1. Market state = Today's playbook state (post-thrust 25 sessions / strong / mixed / weak breadth). If the post-thrust window is on but the
   Post-thrust board's follow-through check reads "fading" (SPY and RSP under the thrust-day close and net 4% movers negative), the thrust
   is treated as failed and the plain breadth regime is used instead - the Oct 15 and Nov 4 thrusts both failed that way.
2. Setup menu = playbook.rank() for that state (each setup's backtested R in that state: Focus >= +0.15R, Selective >= 0, Avoid < 0,
   Unproven < 15 trades) plus the newer setups with their own state evidence: Fresh RS → 21 EMA (R-2026-11-24-rs-fire-pullback) and the
   Post-thrust board (only while a thrust holds).
4. Red light (Nov 25, 2026; R-2026-11-25-red-light): weak breadth (ratio10 < 1) and HYG/IEI credit below its 20-day average each roughly
   halved SPY's worst drawdown without costing return. Both on = red (half size, no new index longs), one = amber, none = clear. VIX > 22 is
   shown as "fear high, watch for a bottom" (it came near the lows, not before them).
3. Size = confluence lights on the Post-thrust board: 0-2 green small / starters, 3-4 normal, 5-6 full. Weak breadth caps it at small.
"""
from __future__ import annotations

from . import playbook, rsfire

V3 = {  # where each setup lives in v3
    "rotation": "Stocks → Setups → Trade setups", "pullback": "Stocks → Setups → Trade setups", "ath": "Stocks → Setups → Trade setups",
    "round": "Stocks → Setups → Trade setups", "kq": "Stocks → Setups → Trade setups", "vcp": "Stocks → Setups → Trade setups",
    "box": "Stocks → Setups → Trade setups", "spring": "Stocks → Setups → Trade setups", "bursts": "Stocks → Setups → Leaders & bursts",
    "anticipation": "Stocks → Setups → Leaders & bursts", "eps": "Stocks → Setups → Episodic pivots",
    "rsfire": "Stocks → Setups → Fresh RS → 21 EMA", "thrustboard": "Stocks → Setups → Post-thrust board",
}
SIZE = [(5, "Full size", "5-6 confluence lights green: the rally is confirmed on every front."),
        (3, "Normal size", "3-4 lights green: trade the Focus setups at normal size."),
        (0, "Small / starters only", "0-2 lights green: watchlist and small starter positions; wait for confirmation.")]


def _verdict(r, n):
    if r is None or n < playbook.MIN_N:
        return "Unproven"
    return "Focus" if r >= playbook.FOCUS_R else ("Selective" if r >= 0 else "Avoid")


def redlight(history, cache=None):
    """Red-light line. Each check: ok True = warning ON. Never raises."""
    out = {"checks": [], "on": 0, "level": "clear", "vix": None}
    try:
        from . import macro, thrustboard
        cache = cache if cache is not None else macro.load()
        r10 = float(history.iloc[-1]["ratio10"])
        out["checks"].append({"k": "breadth", "label": "Weak breadth (10-day ratio under 1)", "on": r10 < 1, "detail": f"10-day ratio {r10:.2f}"})
        h, i = thrustboard._macro_series(cache, "hyg"), thrustboard._macro_series(cache, "iei")
        if h is not None and i is not None:
            cr = (h / i).dropna()
            if len(cr) > 20:
                avg = cr.iloc[-20:].mean()
                out["checks"].append({"k": "credit", "label": "Credit (HYG/IEI) below its 20-day average", "on": bool(cr.iloc[-1] < avg),
                                      "detail": f"{cr.iloc[-1]:.4f} vs 20-day avg {avg:.4f} ({cr.index[-1].date()})"})
        v = thrustboard._macro_series(cache, "vix")
        if v is not None and len(v):
            out["vix"] = {"level": round(float(v.iloc[-1]), 1), "high": bool(v.iloc[-1] > 22), "date": str(v.index[-1].date())}
        n = sum(1 for c in out["checks"] if c["on"])
        out["on"] = n
        out["level"] = "red" if n >= 2 else ("amber" if n == 1 else "clear")
    except Exception:
        out["level"] = "unknown"
    return out


def build(theme_data, history):
    T = theme_data or {}
    pstate, since = playbook.state_of(history)
    tb = T.get("thrustboard") or {}
    ft = (tb.get("ft") or {}).get("verdict")
    state, note = pstate, None
    if pstate == "thrust" and ft == "fading":
        r = history.iloc[-1]
        state = "strong" if (r["ratio5"] >= 1.5 and r["ratio10"] >= 1.5) else ("weak" if r["ratio10"] < 1 else "mixed")
        note = (f"The {tb.get('thrust_date') or 'last'} thrust is failing (SPY and RSP under the thrust-day close, more stocks falling 4% "
                f"than rising): treated as {playbook.STATE[state][0].lower()}, not post-thrust.")
    rows = playbook.rank(T, state)
    rs = T.get("rsfire") or {}
    a, w, n = rsfire.STATS["touch"].get(state, (None, None, 0))
    live = sum(1 for x in rs.get("rows") or [] if x["st"] in ("zone", "undercut", "reclaimed"))
    rows.append({"key": "rsfire", "name": "Fresh RS → 21 EMA (leading groups)", "verdict": _verdict(a, n), "avg_r": a, "n": n, "win": w,
                 "today": live, "why": (f"{a:+.2f}R a trade, {round(w * 100)}% win over {n} trades in {playbook.STATE[state][0].lower()} "
                                        f"(touch of the 21 EMA after 1-3 RS-line highs); {live or 'none'} set up today." if a is not None else "")})
    if state == "thrust":
        rows.append({"key": "thrustboard", "name": "Post-thrust board leaders", "verdict": "Unproven", "avg_r": None, "n": 0, "win": None,
                     "today": sum(len(g.get("stocks") or []) for g in tb.get("groups") or []),
                     "why": "Leading groups since the thrust × buyable RS 80+ stocks; ranking not backtested yet."})
    order = {"Focus": 0, "Selective": 1, "Unproven": 2, "Avoid": 3}
    rows.sort(key=lambda x: (order[x["verdict"]], -(x["avg_r"] if x["avg_r"] is not None else -9)))
    for x in rows:
        x["v3"] = V3.get(x["key"], "Stocks → Setups")
    lights = tb.get("lights") or []
    green = sum(1 for l in lights if l.get("ok"))
    size = next(s for s in SIZE if green >= s[0])
    if state == "weak" and size[0] > 0:
        size = SIZE[-1]
    rl = redlight(history)
    focus = [x["name"] for x in rows if x["verdict"] == "Focus"]
    headline = {
        "thrust": "Post-thrust: press the Focus setups in the leading groups.",
        "strong": "Strong breadth: leaders and pullbacks pay - trade the Focus list.",
        "mixed": "Mixed breadth: be picky - one or two Focus setups, smaller size.",
        "weak": "Weak breadth: most setups lose - sit on your hands or trade tiny; build the watchlist for the next thrust.",
    }[state]
    return {"date": str(history.index[-1])[:10], "state": state, "label": playbook.STATE[state][0], "advice": playbook.STATE[state][1],
            "headline": headline, "note": note, "since": since if state == "thrust" else None, "rows": rows, "focus": focus,
            "redlight": rl, "green": green, "lights": len(lights), "size": size[1], "size_why": size[2],
            "if_thrust": [{"name": x["name"], "verdict": x["verdict"], "avg_r": x["avg_r"], "n": x["n"]} for x in playbook.rank(T, "thrust")[:5]]
            if state != "thrust" else None}
