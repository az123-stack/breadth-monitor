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
    try:
        out["picks"] = picks(theme_data, out)
    except Exception as e:
        import logging
        logging.getLogger("breadth").exception("picks failed: %s", e)
        out["picks"] = []
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


# ---------------------------------------------------------------------------
# Today's top 2 trades
# ---------------------------------------------------------------------------
def trigger_of(key, r):
    """(trigger price, distance in ADRs) for breakout setups; (None, 0) for buy-next-open setups."""
    trig = r.get("kq_pivot") if key == "kq" else r.get("vcp_pivot") if key == "vcp" else None
    if not trig or not r.get("price") or not r.get("adr"):
        return None, 0.0
    return trig, (trig / r["price"] - 1) * 100 / r["adr"]


def picks(theme_data, pb, n=2):
    """Today's top trades, actionable today. Rule (it did best in a day-by-day replay of our
    own history - trade_bt.pick_replay - and is simple enough not to be curve-fit): take the
    top 5 of every Focus setup for today's market (Selective too if fewer than n are
    actionable), keep the ones you can act on today (flag/VCP trigger within 1 ADR of the
    close; other setups buy the next open), pick the highest RS Rating, ties on the 60-day
    gain, one pick per sub-theme. Candidates not actionable yet go to pb["pick_watch"]."""
    from .tradesetups import pick_key, ACTIONABLE_ADR
    X = theme_data.get("trade_setups") or {}
    verdict = {r["key"]: r for r in pb["rows"]}
    for allowed in (("Focus",), ("Focus", "Selective")):
        cands, watch = [], []
        for S in X.get("setups", []):
            v = verdict.get(S["key"])
            if not v or v["verdict"] not in allowed:
                continue
            for t in S["top"]:
                r = X["rows"][t]
                trig, dist = trigger_of(S["key"], r)
                c = {"t": t, "setup": S["key"], "setup_name": S["name"], "verdict": v["verdict"], "avg_r": v["avg_r"],
                     "row": r, "trigger": trig, "trig_adr": round(dist, 2)}
                (cands if dist <= ACTIONABLE_ADR else watch).append(c)
        if len({c["t"] for c in cands}) >= n:
            break
    cands.sort(key=lambda c: pick_key(c["row"]["rsr"], c["row"].get("d60")))
    watch.sort(key=lambda c: pick_key(c["row"]["rsr"], c["row"].get("d60")))
    pb["pick_cands"] = sorted({c["t"] for c in cands})
    pb["pick_watch"] = [{"t": c["t"], "setup_name": c["setup_name"], "rsr": c["row"]["rsr"], "trigger": c["trigger"],
                         "dist_pct": round((c["trigger"] / c["row"]["price"] - 1), 4), "trig_adr": c["trig_adr"]}
                        for c in watch][:5]
    out, seen_t, seen_g = [], set(), set()
    for c in cands:
        g = c["row"].get("sub") or c["row"].get("theme")
        if c["t"] in seen_t or g in seen_g:
            continue
        seen_t.add(c["t"]); seen_g.add(g)
        r = c.pop("row")
        c.update({"rsr": r["rsr"], "d60": r.get("d60"), "name": r.get("name", ""), "sub": g, "price": r.get("price"),
                  "adr": r.get("adr"), "tags": r.get("tags") or [], "vcp_stop": r.get("vcp_stop") if c["setup"] == "vcp" else None,
                  "entry_type": "trigger" if c["trigger"] else "open",
                  "plan": plan(c["setup"], r), "why": why(c, pb, r), "risk10k": risk10k(c["setup"], r)})
        out.append(c)
        if len(out) == n:
            break
    return out


def risk10k(key, r):
    """Dollars lost on a $10k position if the stop is hit (1 ADR, or the VCP stop)."""
    if key == "vcp" and r.get("vcp_pivot") and r.get("vcp_stop"):
        return round(10000 * (1 - r["vcp_stop"] / r["vcp_pivot"]))
    return round(100 * (r.get("adr") or 0) * 1)   # 1 ADR as a % of $10k


def _p(x):
    return f"${x:,.2f}"


def plan(key, r):
    price, adr = r["price"], (r.get("adr") or 0) / 100
    stop1 = price * (1 - adr)
    tgt = f"{_p(r['mag'])} ({r['mag_kind'] if r.get('ath_ok') or r.get('mag_kind') != 'ATH' else '52-wk high'}, {r['mag_pct'] * 100:+.1f}%)" if r.get("mag") else "no overhead level: trail it"
    if key == "ath":
        return {"entry": f"Buy at the open (last close {_p(price)}) as it presses the high", "stop": "1 ADR below your fill" + f" (~{_p(stop1)})",
                "target": f"Through the all-time high {_p(r['ath'])} ({r['ath_pct'] * 100:+.1f}%); hold ~5 days"}
    if key == "pullback":
        e21 = price / (1 + r["e21"]) if r.get("e21") is not None else None
        return {"entry": f"Buy at the open, near the 21 EMA{f' (~{_p(e21)})' if e21 else ''}", "stop": "1 ADR below your fill" + f" (~{_p(stop1)})",
                "target": tgt}
    if key == "rotation":
        return {"entry": f"Buy at the open (last close {_p(price)})", "stop": "1 ADR below your fill" + f" (~{_p(stop1)})", "target": tgt}
    if key == "kq":
        return {"entry": (f"Buy the break of the flag above {_p(r['kq_pivot'])} ({(r['kq_pivot'] / price - 1) * 100:+.1f}% from here)"
                          if r.get("kq_pivot") else "Buy the flag break"),
                "stop": "Low of the entry day (pass if it's more than 1 ADR away)",
                "target": f"Sell half after 3–5 days, trail the rest on the 10 EMA; next level {tgt}"}
    if key == "vcp":
        return {"entry": (f"Buy the pivot break above {_p(r['vcp_pivot'])} ({(r['vcp_pivot'] / price - 1) * 100:+.1f}% from here)"
                          if r.get("vcp_pivot") else "Buy the pivot break"),
                "stop": f"{_p(r['vcp_stop'])}" if r.get("vcp_stop") else "Under the last contraction (max 8%)",
                "target": "Hold while above the 50-day; " + tgt}
    return {}


def why(c, pb, r):
    bits = [f"Highest RS among today's {c['verdict'].lower()} setups: RS {int(r['rsr'])}" + (" ★" if r.get("star") else "")
            + (f", {r['d60'] * 100:+.0f}% in 60 days" if r.get("d60") is not None else "")]
    bits.append(f"{c['setup_name']} is {c['verdict'].lower()} in {pb['label'].lower()} ({c['avg_r']:+.2f}R a trade)")
    if r.get("htf"):
        bits.append(f"high tight flag (+{int(r['kq_leg'])}% leg)")
    if r.get("grp"):
        bits.append(f"group Strength {round(r['grp'])}")
    return "; ".join(bits) + "."
