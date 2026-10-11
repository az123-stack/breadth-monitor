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
    out["pick_weights"] = PICK_W
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
SHRINK_N = 30   # edge is shrunk toward 0 by n / (n + 30) so a hot small sample can't dominate
PICK_W = {"edge": 0.30, "prob": 0.20, "stock": 0.20, "room": 0.20, "confluence": 0.10}


def _clip(x, lo, hi):
    return max(lo, min(hi, x))


def picks(theme_data, pb, n=2):
    """Best n trades today across the Trade Setups lists. Score 0-100:
      edge        30%  the setup's backtested avg R in today's market state, shrunk by sample
                       size n/(n+30) (-0.2R -> 0, +0.8R -> 100)
      probability 20%  how often that setup rallied 1 ADR within 5 sessions in this state
      stock       20%  RS Rating (and group Strength where the setup uses it)
      room        20%  pullback/rotation: distance to the next overhead level in ADRs (0.5 or less =
                       cramped, 2+ = open); flag/VCP: how close the trigger is (0.5 ADR = ready, 2+ = far)
      confluence  10%  extra buying angles the stock is on (2+ setups, burst, coil)
    Only Focus/Selective setups are eligible; one pick per sub-theme."""
    X, B = theme_data.get("trade_setups") or {}, theme_data.get("trade_bt") or {}
    state = pb["state"]
    verdict = {r["key"]: r for r in pb["rows"]}
    cands = []
    for S in X.get("setups", []):
        v = verdict.get(S["key"])
        if not v or v["verdict"] not in ("Focus", "Selective"):
            continue
        st = ((B.get("setups") or {}).get(S["key"]) or {}).get(state) or {}
        for t in S["top"]:
            r = X["rows"][t]
            nn = v["n"] or 0
            shrunk = (v["avg_r"] or 0) * nn / (nn + SHRINK_N)       # small samples count for less
            edge = _clip((shrunk + 0.2) / 1.0, 0, 1)
            prob = _clip(st.get("hit_adr") or 0, 0, 1)
            stock = r["rsr"] / 99 if S["key"] in ("kq", "vcp") else 0.6 * r["rsr"] / 99 + 0.4 * (r.get("grp") or 0) / 100
            room_adr = r.get("mag_adr")
            trig = r.get("kq_pivot") if S["key"] == "kq" else r.get("vcp_pivot") if S["key"] == "vcp" else None
            if trig and r.get("adr"):
                # breakout setups: how reachable the trigger is (0.5 ADR or less = ready, 2+ ADRs = not this week)
                room = _clip((2.0 - (trig / r["price"] - 1) * 100 / r["adr"]) / 1.5, 0, 1)
            elif S["key"] in ("ath", "kq", "vcp"):
                room = 1.0                     # the level is the trigger, not a ceiling
            elif room_adr is None:
                room = 1.0                     # nothing overhead
            else:
                room = _clip((room_adr - 0.5) / 1.5, 0, 1)
            conf = _clip((r.get("hits", 1) - 1) / 2, 0, 1)
            score = 100 * (PICK_W["edge"] * edge + PICK_W["prob"] * prob + PICK_W["stock"] * stock
                           + PICK_W["room"] * room + PICK_W["confluence"] * conf)
            cands.append({"t": t, "setup": S["key"], "setup_name": S["name"], "score": round(score, 1),
                          "parts": {"edge": round(edge * 100), "prob": round(prob * 100), "stock": round(stock * 100),
                                    "room": round(room * 100), "confluence": round(conf * 100)},
                          "row": r, "verdict": v["verdict"], "avg_r": v["avg_r"], "hit_adr": st.get("hit_adr"), "n": st.get("n")})
    cands.sort(key=lambda c: -c["score"])
    out, seen_t, seen_g, seen_s = [], set(), set(), set()
    for strict in (True, False):       # first pass: a different setup and group for each pick
        for c in cands:
            if len(out) == n:
                break
            if c["t"] in seen_t:
                continue
            g = c["row"].get("sub") or c["row"].get("theme")
            if strict and (g in seen_g or c["setup"] in seen_s):
                continue
            seen_t.add(c["t"]); seen_g.add(g); seen_s.add(c["setup"])
            _finish(c, pb)
            out.append(c)
    out.sort(key=lambda c: -c["score"])
    return out


def _finish(c, pb):
    if True:
        c["plan"] = plan(c["setup"], c["row"])
        c["why"] = why(c, pb)
        c["name"] = c["row"].get("name", "")
        c["sub"] = c["row"].get("sub") or c["row"].get("theme")
        c["price"] = c["row"].get("price")
        c.pop("row")


def _p(x):
    return f"${x:,.2f}"


def plan(key, r):
    price, adr = r["price"], (r.get("adr") or 0) / 100
    stop1 = price * (1 - adr)
    tgt = f"{_p(r['mag'])} ({r['mag_kind'] if r.get('ath_ok') or r.get('mag_kind') != 'ATH' else '52-wk high'}, {r['mag_pct'] * 100:+.1f}%)" if r.get("mag") else "no overhead level: trail it"
    if key == "ath":
        return {"entry": f"Buy strength near {_p(price)} as it presses the high", "stop": f"{_p(stop1)} (1 ADR)",
                "target": f"Through the all-time high {_p(r['ath'])} ({r['ath_pct'] * 100:+.1f}%); hold ~5 days"}
    if key == "pullback":
        e21 = price / (1 + r["e21"]) if r.get("e21") is not None else None
        return {"entry": f"Buy the bounce off the 21 EMA{f' (~{_p(e21)})' if e21 else ''}", "stop": f"{_p(stop1)} (1 ADR) or a close under the 21 EMA",
                "target": tgt}
    if key == "rotation":
        return {"entry": f"Buy near {_p(price)} or on a burst day", "stop": f"{_p(stop1)} (1 ADR)", "target": tgt}
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


def why(c, pb):
    r = c["row"]
    bits = [f"{c['setup_name']} is {c['verdict'].lower()} in {pb['label'].lower()} ({c['avg_r']:+.2f}R a trade"
            + (f", +1 ADR within 5 days {round(c['hit_adr'] * 100)}% of the time" if c.get("hit_adr") is not None else "") + ")"]
    bits.append(f"RS {int(r['rsr'])}" + (" ★" if r.get("star") else "") + (f", group Strength {round(r['grp'])}" if r.get("grp") else ""))
    if r.get("htf"):
        bits.append(f"high tight flag (+{int(r['kq_leg'])}% leg)")
    if r.get("hits", 1) > 1:
        bits.append(f"on {r['hits']} buying angles")
    if r.get("mag_adr") is not None and c["setup"] in ("pullback", "rotation"):
        bits.append(f"{r['mag_adr']} ADR of room to {_p(r['mag'])}")
    return "; ".join(bits) + "."
