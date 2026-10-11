"""Today's playbook: which kind of setup to take right now, ranked, and why.

The market state is "thrust" for THRUST_WINDOW sessions after a major Breadth
thrust / Follow-through signal, otherwise the breadth regime (strong / mixed /
weak, same rule as the setup stats). Every setup type - the four Trade Setups
plus the Setups-tab lists (momentum bursts, anticipation, EPs) - is ranked by
its backtested average R in that state:
    Focus      >= +0.15R a trade (n >= MIN_N)
    Selective  >= 0R
    Avoid      below 0R
    Unproven   fewer than MIN_N trades in this state
The reason line also reports the last 30 sessions (Trade Setups only) and how
many names qualify today. The same table for the thrust state is shown as
"if a thrust comes" so the switch is ready before it happens.
"""
from . import metrics

MIN_N = 15
FOCUS_R = 0.15
STATE = {
    "thrust": ("Post-thrust", "Press. The weeks after a breadth thrust have been the best time to trade: size up on the top-ranked setups."),
    "strong": ("Strong breadth", "Setups pay in strong breadth: trade normal size and press the leaders."),
    "mixed": ("Mixed breadth", "No breadth edge: be selective, size down, and stick to the top one or two setups."),
    "weak": ("Weak breadth", "Most setups lose in weak breadth: trade small or stand aside and wait for a thrust."),
}
TYPES = [  # key, name, source, where to find the names
    ("rotation", "Rotation Rookie", "trade", "Trade Setups"),
    ("pullback", "Leader Pullback", "trade", "Trade Setups"),
    ("ath", "ATH Magnet", "trade", "Trade Setups"),
    ("kq", "Qullamaggie Flag", "trade", "Trade Setups"),
    ("vcp", "Minervini VCP", "trade", "Trade Setups"),
    ("bursts", "Momentum bursts (2LYNCH 5+)", "lists", "Setups tab"),
    ("anticipation", "Anticipation coils", "lists", "Setups tab"),
    ("eps", "Episodic pivots", "lists", "Setups tab"),
]


def state_of(history):
    """('thrust', sessions since) or (regime, None)."""
    if history is None or not len(history):
        return "mixed", None
    tw = metrics.thrust_window(history, history.index)
    if tw[-1]:
        # sessions since the latest major thrust/follow-through
        k = 0
        for v in tw[::-1]:
            if not v:
                break
            k += 1
        return "thrust", k - 1
    r = history.iloc[-1]
    if r["ratio5"] >= 1.5 and r["ratio10"] >= 1.5:
        return "strong", None
    return ("weak" if r["ratio10"] < 1 else "mixed"), None


def rank(theme_data, state):
    B, S = theme_data.get("trade_bt") or {}, theme_data.get("setup_stats") or {}
    X = theme_data.get("trade_setups") or {}
    L = theme_data.get("lists") or {}
    counts = {s["key"]: s["count"] for s in X.get("setups", [])}
    lc = L.get("counts") or {}
    today = {**counts, "bursts": sum(1 for r in L.get("bursts", []) if (r.get("lynch") or 0) >= 5),
             "anticipation": lc.get("anticipation"), "eps": lc.get("eps")}
    label = STATE[state][0].lower()
    rows = []
    for key, name, src, where in TYPES:
        st = ((B.get("setups") or {}).get(key) if src == "trade" else S.get(key)) or {}
        o = st.get(state) or {}
        allo = st.get("all") or {}
        rec = (B.get("recent") or {}).get(key) if src == "trade" else None
        n, r = o.get("n") or 0, o.get("avg_r")
        if n < MIN_N or r is None:
            verdict = "Unproven"
        elif r >= FOCUS_R:
            verdict = "Focus"
        elif r >= 0:
            verdict = "Selective"
        else:
            verdict = "Avoid"
        bits = []
        if n and r is not None:
            bits.append(f"{r:+.2f}R a trade, {round((o.get('win') or 0) * 100)}% win over {n} trades in {label}")
        else:
            bits.append(f"no trades yet in {label}")
        if verdict == "Unproven" and allo.get("n"):
            bits.append(f"all days {allo['avg_r']:+.2f}R (n {allo['n']})")
        if rec and rec.get("n"):
            cool = " — cooling lately" if r is not None and r > 0 and rec["avg_r"] < 0 else (
                " — improving lately" if r is not None and r < 0 and rec["avg_r"] > 0.1 else "")
            bits.append(f"last 30 sessions {rec['avg_r']:+.2f}R (n {rec['n']}){cool}")
        t = today.get(key)
        bits.append("none qualify today" if not t else f"{t} qualify today")
        rows.append({"key": key, "name": name, "where": where, "verdict": verdict, "avg_r": r, "n": n,
                     "win": o.get("win"), "today": t, "why": "; ".join(bits) + "."})
    order = {"Focus": 0, "Selective": 1, "Unproven": 2, "Avoid": 3}
    rows.sort(key=lambda x: (order[x["verdict"]], -(x["avg_r"] if x["avg_r"] is not None else -9)))
    for i, x in enumerate(rows):
        x["rank"] = i + 1
    return rows


def build(theme_data, history):
    state, since = state_of(history)
    rows = rank(theme_data, state)
    base = ((theme_data.get("trade_bt") or {}).get("base") or {}).get(state) or {}
    out = {"state": state, "label": STATE[state][0], "advice": STATE[state][1], "since": since, "rows": rows,
           "baseline": base, "thrust_days": (theme_data.get("trade_bt") or {}).get("days", {}).get("thrust")}
    if state != "thrust":
        out["if_thrust"] = rank(theme_data, "thrust")
    return out


def thrust_today(history, recent=3):
    """The latest major thrust / follow-through if it fired in the last `recent` sessions."""
    try:
        ev = [e for e in metrics.events(history) if e.get("kind") in ("thrust", "followthrough") and e.get("tier") == "major"]
    except Exception:
        return None
    if not ev:
        return None
    last = ev[-1]
    tail = [d.strftime("%Y-%m-%d") for d in history.index[-recent:]]
    return last if last["date"] in tail else None
