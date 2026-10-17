"""Box research engine (Oct 17, 2026): every box event in our ~2 years, tagged with market / group / stock /
pattern conditions, so we can see where each trade works.

Six trades, each found on tight boxes (boxes.find_box) and wide ranges (boxes._range_breakouts):
  retest_long   break above the top -> pull back to it -> bounce                       LONG
  retest_short  break below the bottom -> rally back to it -> rejection                 SHORT
  trap_short    break above the top -> fails, closes back inside past the fail line     SHORT  (HPE, Oct 2026)
  far_short     ...after that failure, closes below the box bottom within 40 sessions   SHORT  (HPE "through the floor")
  trap_long     break below the bottom -> fails, closes back inside                      LONG   (spring / bear trap)
  far_long      ...after that failure, closes above the box top within 40 sessions      LONG
Fail line: tight box = its middle; wide range = 1.5 ADR back inside the line.

Trade (per the backtest skill): signal at the close, ENTER AT THE NEXT OPEN (skip if it gaps through the stop),
stop = retest extreme (retests) / 0.5 ADR past the line (traps) / 5-session extreme (far-side breaks), else exit
the close 20 sessions after entry. R = result / risk (risk floored at 0.3 ADR). Also 21- and 63-session return
vs SPY from the entry open, direction-adjusted. Halves split at the middle date. One event per stock, side and
trade within 10 sessions.
"""
import numpy as np
import pandas as pd

from . import boxes as BX

HOLD = 20
FAR_DAYS = 40
TYPES = [("retest_long", "Retest bounce (long)", 1), ("retest_short", "Retest rejection (short)", -1),
         ("trap_short", "Failed breakout (short)", -1), ("far_short", "Through the floor after a failed breakout (short)", -1),
         ("trap_long", "Failed breakdown (long)", 1), ("far_long", "Through the ceiling after a failed breakdown (long)", 1)]


# ----------------------------------------------------------------------------- group / market features
def group_frames(c, members, spy):
    """Per group (dict name -> tickers): rank of 20/60-day return among groups (0-1), above its 50-day, share of
    members above their 21 EMA. Returns dict of DataFrames indexed by date, columns = groups."""
    ret = c.pct_change(fill_method=None).clip(-0.5, 0.5)
    ema21 = c.ewm(span=21, adjust=False, min_periods=21).mean()
    above = (c > ema21).where(c.notna() & ema21.notna())
    idx, br = {}, {}
    for g, tick in members.items():
        tk = [t for t in tick if t in c.columns]
        if len(tk) < 4:
            continue
        idx[g] = (1 + ret[tk].mean(axis=1).fillna(0)).cumprod()
        br[g] = above[tk].mean(axis=1)
    if not idx:
        return None
    I = pd.DataFrame(idx)
    return {"r20": (I / I.shift(20) - 1).rank(axis=1, pct=True), "r60": (I / I.shift(60) - 1).rank(axis=1, pct=True),
            "a50": (I > I.rolling(50).mean()).astype(float).where(I.rolling(50).mean().notna()),
            "br": pd.DataFrame(br)}


def market_frame(dates, breadth, spy):
    mk = BX.market_arrays(breadth, dates)
    s = pd.Series(spy, index=dates)
    return {"state": np.where(mk["since"] <= 5, "thr05", np.where(mk["tw"], "thr625", "none")),
            "regime": mk["regime"], "spy50": (s > s.rolling(50).mean()).to_numpy(),
            "spy200": (s > s.rolling(200, min_periods=120).mean()).to_numpy(),
            "t2108": mk["t2108"], "dn10": mk["dn10"], "nhnl": mk["nhnl"]}


# ----------------------------------------------------------------------------- events
def _trade(O, H, L, C, i, dd, stop, adr, n):
    """Enter next open; returns dict or None. dd = +1 long / -1 short; stop in real price."""
    e_i = i + 1
    if e_i >= n or not np.isfinite(O[e_i]) or not np.isfinite(stop):
        return None
    e = O[e_i]
    if dd * (e - stop) <= 0:
        return {"gap": True}
    risk = max(dd * (e - stop), 0.003 * adr * e)
    end = min(n - 1, e_i + HOLD - 1)
    xi, xp = end, C[end]
    for k in range(e_i, end + 1):
        if (L[k] <= stop) if dd > 0 else (H[k] >= stop):
            xi, xp = k, (min(stop, O[k]) if dd > 0 else max(stop, O[k])) if k > e_i else stop
            break
    done = end - e_i >= HOLD - 1 or xi < end
    o = {"gap": False, "e": e, "stop": stop, "risk": risk / e}
    if done:
        o["R"] = float(np.clip(dd * (xp - e) / risk, -3, 10))
        o["stopped"] = xi < end
        e5 = min(n - 1, e_i + 4)
        x5 = xp if xi <= e5 and xi < end else C[e5]
        o["R5"] = float(np.clip(dd * (x5 - e) / risk, -3, 10))
    return o


def collect(w, cols, liq, rs, ADR, spy, spyo, lo=None):
    """All events for the given columns. Returns a list of dicts (no features yet)."""
    O_all, H_all, L_all, C_all, V_all = (w[k][cols].to_numpy() for k in ("o", "h", "l", "c", "v"))
    N = len(w["c"].index)
    first = BX.CFG["pole_days"] + BX.CFG["min_len"] + 2
    lo = lo or first
    ev = []
    for j, t in enumerate(cols):
        if not liq[:, j].any():
            continue
        O, H, L, C, V, adr = O_all[:, j], H_all[:, j], L_all[:, j], C_all[:, j], V_all[:, j], ADR[:, j]
        for side, d in (("long", 1), ("short", -1)):
            h, l, c = BX._space(H, L, C, side)
            prev10 = pd.Series(h).rolling(10).max().shift(1).to_numpy()
            bos = [(bi, b, "tight") for bi, b in BX._breakouts(h, l, c, V, adr, lo, N - 2, prev10, strict=(side == "long"))]
            bos += [(bi, b, "range") for bi, b in BX._range_breakouts(h, l, c, V, adr, lo, N - 2, prev10)]
            bos.sort(key=lambda x: x[0])
            last = {}
            for bi, b, kind in bos:
                if not liq[bi, j]:
                    continue
                w_ = BX.retest_walk(h, l, c, b, bi, min(N - 1, bi + 2 * BX.RT["expire"] + 5), adr[bi])
                top, bot, lvl, far = BX._real_box(b, side)
                T = b["top"]
                a = adr[bi]
                base = {"j": j, "t": t, "side": side, "kind": kind, "bi": bi, "win": b["win"], "len": b["len"],
                        "touches": b.get("touches"), "lvl": lvl, "far": far, "h_adr": b["h_adr"],
                        "bvx": V[bi] / b["bvol"] if b["bvol"] else np.nan, "ext": (w_["ph"] - T) / (T * a / 100)}

                def add(typ, i, dd, stop, extra=None):
                    if i is None or i >= N - 1 or not liq[i, j] or i - last.get(typ, -99) < 10:
                        return
                    tr = _trade(O, H, L, C, i, dd, stop, ADR[i, j], N)
                    if tr is None:
                        return
                    last[typ] = i
                    e_i = i + 1
                    o = {**base, "type": typ, "i": i, "dd": dd, **tr, **(extra or {})}
                    for k in (21, 63):
                        x = e_i + k - 1
                        if x < N and np.isfinite(C[x]) and np.isfinite(spy[x]) and not tr["gap"]:
                            o[f"x{k}"] = float(np.clip(dd * ((C[x] / tr["e"] - 1) - (spy[x] / spyo[e_i] - 1)), -0.6, 0.6))
                    ev.append(o)

                # retest bounce / rejection
                if w_.get("bounce") is not None:
                    i = w_["bounce"]
                    st = float(np.nanmin(L[w_["touch"]:i + 1])) if d > 0 else float(np.nanmax(H[w_["touch"]:i + 1]))
                    add("retest_" + side, i, d, st, {"days_touch": w_["touch"] - bi, "inside": bool(d * (st - lvl) < 0)})
                # failed break -> trap, then far side
                if w_["state"] == "failed" and w_.get("bounce") is None and w_["i"] - bi <= FAR_DAYS:
                    f = w_["i"]
                    trap = "trap_" + ("short" if side == "long" else "long")
                    st_b = T * (1 + 0.5 * a / 100)                    # breakout space: back over the line
                    st = st_b if side == "long" else 1 / st_b
                    add(trap, f, -d, st, {"days_fail": f - bi})
                    Bb = b["bot"]
                    for k in range(f + 1, min(N - 1, f + FAR_DAYS) + 1):
                        if c[k] > T:                                  # reclaimed the line: thesis gone
                            break
                        if c[k] < Bb <= c[k - 1]:
                            hi5 = np.nanmax(h[k - 4:k + 1])
                            st = hi5 if side == "long" else 1 / hi5
                            add("far_" + ("short" if side == "long" else "long"), k, -d, st, {"days_fail": f - bi, "days_far": k - f})
                            break
    return ev


def features(ev, w, cols, rs, ADR, spy, mk, grp, sub_of, theme_of, thm):
    c = w["c"][cols]
    C, V = c.to_numpy(), w["v"][cols].to_numpy()
    rl = c.div(pd.Series(spy, index=c.index), axis=0)
    rl_hi = (rl >= 0.97 * rl.rolling(252, min_periods=120).max()).to_numpy()
    rl_lo = (rl <= 1.03 * rl.rolling(252, min_periods=120).min()).to_numpy()
    s200 = (c > c.rolling(200, min_periods=150).mean()).to_numpy()
    s50 = c.rolling(50).mean()
    s50up = (s50 > s50.shift(10)).to_numpy()
    v50 = pd.DataFrame(V).rolling(50, min_periods=30).mean().shift(1).to_numpy()
    h52 = w["h"][cols].rolling(252, min_periods=60).max().to_numpy()
    r = c.pct_change(fill_method=None)
    sr = pd.Series(spy, index=c.index).pct_change()
    beta = (r.rolling(60).cov(sr) / sr.rolling(60).var()).to_numpy()
    bq = pd.DataFrame(beta).rank(axis=1, pct=True).to_numpy()
    di = {d: k for k, d in enumerate(c.index)}
    for e in ev:
        i, j = e["i"], e["j"]
        e["date"] = c.index[i].strftime("%Y-%m-%d")
        for k in ("state", "regime", "spy50", "spy200", "t2108", "dn10", "nhnl"):
            e[k] = mk[k][i]
        e["rs"] = rs[i, j]
        e["rl_hi"], e["rl_lo"] = bool(rl_hi[i, j]), bool(rl_lo[i, j])
        e["a200"], e["s50up"] = bool(s200[i, j]), bool(s50up[i, j])
        e["vx"] = V[i, j] / v50[i, j] if v50[i, j] else np.nan
        e["off"] = C[i, j] / h52[i, j] - 1 if np.isfinite(h52[i, j]) else np.nan
        e["adr"] = ADR[i, j]
        e["betaq"] = bq[i, j]
        for name, G, of in (("g", grp, sub_of), ("th", thm, theme_of)):
            g = of.get(e["t"])
            if G is None or g is None or g not in G["r20"].columns:
                e[name] = None
                continue
            e[name] = g
            e[name + "_r20"] = G["r20"].iat[i, G["r20"].columns.get_loc(g)]
            e[name + "_r60"] = G["r60"].iat[i, G["r60"].columns.get_loc(g)]
            e[name + "_a50"] = G["a50"].iat[i, G["a50"].columns.get_loc(g)]
            e[name + "_br"] = G["br"].iat[i, G["br"].columns.get_loc(g)]
    # siblings: same group, same trade, within the prior 10 sessions (incl. the same day)
    by = {}
    for e in ev:
        if e.get("g"):
            by.setdefault((e["g"], e["type"]), []).append(e["i"])
    for e in ev:
        ii = by.get((e.get("g"), e["type"]), []) if e.get("g") else []
        e["sib"] = sum(1 for x in ii if 0 <= e["i"] - x <= 10) - 1
    return ev


# ----------------------------------------------------------------------------- conditions + stats
def _ok(v):
    return v is not None and not (isinstance(v, float) and np.isnan(v))


def conditions(dd):
    """(group, name, test) — `dd` = trade direction, so 'with the trade' conditions read naturally."""
    up = dd > 0
    f = lambda k, fn: (lambda e: _ok(e.get(k)) and bool(fn(e[k])))
    return [
        ("Market", "Thrust day to 5 sessions after", lambda e: e["state"] == "thr05"),
        ("Market", "6-25 sessions after a thrust", lambda e: e["state"] == "thr625"),
        ("Market", "No thrust in 25 sessions", lambda e: e["state"] == "none"),
        ("Market", "Strong breadth", lambda e: e["regime"] == "strong"),
        ("Market", "Mixed breadth", lambda e: e["regime"] == "mixed"),
        ("Market", "Weak breadth", lambda e: e["regime"] == "weak"),
        ("Market", "SPY above its 50-day", f("spy50", lambda x: x)),
        ("Market", "SPY below its 50-day", f("spy50", lambda x: not x)),
        ("Market", "SPY below its 200-day", f("spy200", lambda x: not x)),
        ("Market", "Money leaving (10-day share in falling ≥ 52%)", f("dn10", lambda x: x >= 52)),
        ("Market", "New lows beating new highs", f("nhnl", lambda x: x <= 0)),
        ("Theme / group", "Sub-theme top 20% on 20-day return", f("g_r20", lambda x: x >= 0.8)),
        ("Theme / group", "Sub-theme bottom 20% on 20-day return", f("g_r20", lambda x: x <= 0.2)),
        ("Theme / group", "Sub-theme top 20% on 60-day return", f("g_r60", lambda x: x >= 0.8)),
        ("Theme / group", "Sub-theme bottom 20% on 60-day return", f("g_r60", lambda x: x <= 0.2)),
        ("Theme / group", "Sub-theme above its 50-day", f("g_a50", lambda x: x == 1)),
        ("Theme / group", "Sub-theme below its 50-day", f("g_a50", lambda x: x == 0)),
        ("Theme / group", "Sub-theme breadth 70%+ above 21 EMA", f("g_br", lambda x: x >= 0.7)),
        ("Theme / group", "Sub-theme breadth 30% or less above 21 EMA", f("g_br", lambda x: x <= 0.3)),
        ("Theme / group", "Theme top 20% on 20-day return", f("th_r20", lambda x: x >= 0.8)),
        ("Theme / group", "Theme bottom 20% on 20-day return", f("th_r20", lambda x: x <= 0.2)),
        ("Theme / group", "A sibling did the same trade in the last 10 sessions", f("sib", lambda x: x >= 1)),
        ("Theme / group", "Not in any sub-theme", lambda e: not e.get("g")),
        ("Stock", "RS 80+", f("rs", lambda x: x >= 80)),
        ("Stock", "RS 30 or lower", f("rs", lambda x: x <= 30)),
        ("Stock", "RS line within 3% of its 1-year high", f("rl_hi", lambda x: x)),
        ("Stock", "RS line within 3% of its 1-year low", f("rl_lo", lambda x: x)),
        ("Stock", "Above its 200-day", f("a200", lambda x: x)),
        ("Stock", "Below its 200-day", f("a200", lambda x: not x)),
        ("Stock", "50-day rising", f("s50up", lambda x: x)),
        ("Stock", "50-day falling", f("s50up", lambda x: not x)),
        ("Stock", "Signal-day volume 1.5×+ average", f("vx", lambda x: x >= 1.5)),
        ("Stock", "Within 10% of 52-week high", f("off", lambda x: x >= -0.10)),
        ("Stock", "30%+ below 52-week high", f("off", lambda x: x <= -0.30)),
        ("Stock", "High beta (top 25%)", f("betaq", lambda x: x >= 0.75)),
        ("Stock", "ADR 4%+", f("adr", lambda x: x >= 4)),
        ("Pattern", "Tight box", lambda e: e["kind"] == "tight"),
        ("Pattern", "Wide range (multi-touch level)", lambda e: e["kind"] == "range"),
        ("Pattern", "2-4 week tight box", lambda e: e["win"] == "w2"),
        ("Pattern", "Break on volume 1.3×+ box avg", f("bvx", lambda x: x >= 1.3)),
        ("Pattern", "Ran 2+ ADR past the line first", f("ext", lambda x: x >= 2)),
        ("Pattern", "Retest dipped back inside", f("inside", lambda x: x)),
        ("Pattern", "Failure within 5 sessions of the break", f("days_fail", lambda x: x <= 5)),
        ("Pattern", "Failure 6+ sessions after the break", f("days_fail", lambda x: x > 5)),
    ]


def stats(sub, split):
    R = np.array([e["R"] for e in sub if _ok(e.get("R"))])
    out = {"n": int(len(R)), "dates": len({e["date"] for e in sub if _ok(e.get("R"))})}
    if len(R) >= 8:
        sd = R.std(ddof=1)
        out.update({"R": round(float(R.mean()), 3), "win": round(float((R > 0).mean()), 3),
                    "t": round(float(R.mean() / (sd / np.sqrt(len(R)))), 2) if sd > 0 else None})
        for k, cond in (("h1", lambda e: e["date"] < split), ("h2", lambda e: e["date"] >= split)):
            x = [e["R"] for e in sub if _ok(e.get("R")) and cond(e)]
            out[k] = round(float(np.mean(x)), 3) if len(x) >= 5 else None
    for k in ("x21", "x63"):
        x = np.array([e[k] for e in sub if _ok(e.get(k))])
        if len(x) >= 8:
            out[k] = round(float(x.mean()), 4)
            out[k + "_med"] = round(float(np.median(x)), 4)
            if k == "x21":
                out["worst21"] = round(float(x.min()), 3)
    return out


def edge_vs_rest(s, rest, split):
    """Avg R with the condition minus without it, Welch t, and the same difference in each half."""
    a = np.array([e["R"] for e in s if _ok(e.get("R"))])
    b = np.array([e["R"] for e in rest if _ok(e.get("R"))])
    if len(a) < 8 or len(b) < 8:
        return {}
    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    out = {"edge": round(float(a.mean() - b.mean()), 3), "edge_t": round(float((a.mean() - b.mean()) / se), 2) if se > 0 else None}
    for k, cond in (("e1", lambda e: e["date"] < split), ("e2", lambda e: e["date"] >= split)):
        x = [e["R"] for e in s if _ok(e.get("R")) and cond(e)]
        y = [e["R"] for e in rest if _ok(e.get("R")) and cond(e)]
        out[k] = round(float(np.mean(x) - np.mean(y)), 3) if len(x) >= 5 and len(y) >= 5 else None
    return out


def proven(st, min_n=30):
    """+1 helps / -1 hurts / 0: the condition beats (or trails) the same trade without it — Welch t >= 2 on 30+ trades,
    and the difference has the same sign in both halves of the data."""
    if st.get("n", 0) < min_n or st.get("edge_t") is None or st.get("e1") is None or st.get("e2") is None:
        return 0
    if st["edge_t"] >= 2 and st["e1"] > 0 and st["e2"] > 0:
        return 1
    if st["edge_t"] <= -2 and st["e1"] < 0 and st["e2"] < 0:
        return -1
    return 0


def study(ev, split):
    out = {}
    for typ, name, dd in TYPES:
        sub = [e for e in ev if e["type"] == typ and not e.get("gap")]
        if not sub:
            continue
        base = stats(sub, split)
        conds = conditions(dd)
        rows = []
        for grp_, nm, fn in conds:
            s, rest = [], []
            for e in sub:
                (s if fn(e) else rest).append(e)
            st = stats(s, split)
            st.update(edge_vs_rest(s, rest, split))
            rows.append({"group": grp_, "name": nm, **st})
        # pairs: exploratory, must hold in both halves, ranked by t
        pairs = []
        for a in range(len(conds)):
            for b in range(a + 1, len(conds)):
                if conds[a][0] == conds[b][0] == "Market":
                    continue
                s = [e for e in sub if conds[a][2](e) and conds[b][2](e)]
                if len(s) < 40:
                    continue
                st = stats(s, split)
                if st.get("t") and st["t"] >= 2.5 and (st.get("h1") or 0) > 0 and (st.get("h2") or 0) > 0 and st["dates"] >= 15:
                    pairs.append({"name": conds[a][1] + " + " + conds[b][1], **st})
        pairs.sort(key=lambda r: -r["t"])
        out[typ] = {"name": name, "dd": dd, "all": base, "gaps": sum(1 for e in ev if e["type"] == typ and e.get("gap")),
                    "rows": rows, "pairs": pairs[:10],
                    "kinds": {k: stats([e for e in sub if e["kind"] == k], split) for k in ("tight", "range")}}
    return out


# ----------------------------------------------------------------------------- episodes (independent thrusts)
def episodes(ev, breadth, typ):
    """Average R per thrust episode for signals in the first 5 sessions after a thrust (independent events)."""
    from . import metrics as MT
    thr = sorted({e["date"] for e in MT.events(breadth) if e.get("kind") in ("thrust", "followthrough") and e.get("tier") == "major"})
    out = {}
    for e in ev:
        if e["type"] != typ or e.get("state") != "thr05" or not _ok(e.get("R")):
            continue
        ep = max([d for d in thr if d <= e["date"]], default=None)
        if ep:
            out.setdefault(ep, []).append(e["R"])
    # merge a follow-through into the thrust it follows (within 10 sessions ~ 14 days)
    rows, last = [], None
    for d in sorted(out):
        if last and (pd.Timestamp(d) - pd.Timestamp(last["date"])).days <= 14:
            last["r"] += out[d]
            continue
        last = {"date": d, "r": list(out[d])}
        rows.append(last)
    return [{"date": r["date"], "n": len(r["r"]), "R": round(float(np.mean(r["r"])), 3)} for r in rows]


# ----------------------------------------------------------------------------- live tags
TAGS = {"retest_long": ["go", "at", "inside", "coming"], "retest_short": ["go", "at", "inside", "coming"],
        "trap_short": ["failed", "far", "falling"], "trap_long": ["failed", "far", "falling"]}
GROUP_OK = ("Sub-theme above its 50-day", "Sub-theme top 20% on 20-day return", "Theme top 20% on 20-day return")


def live(w, cols, liq, rs, ADR, h52, dates, info, names, window=60):
    """Today's rows: retests (both sides, tight + wide), and failed breaks (trap -> through the far side)."""
    O_all, H_all, L_all, C_all, V_all = (w[k][cols].to_numpy() for k in ("o", "h", "l", "c", "v"))
    N = len(dates)
    last = N - 1
    rows = []
    for j, t in enumerate(cols):
        if not liq[-1, j]:
            continue
        H, L, C, V, adr = H_all[:, j], L_all[:, j], C_all[:, j], V_all[:, j], ADR[:, j]
        for side, d in (("long", 1), ("short", -1)):
            h, l, c = BX._space(H, L, C, side)
            prev10 = pd.Series(h).rolling(10).max().shift(1).to_numpy()
            bos = [(bi, b, "tight") for bi, b in BX._breakouts(h, l, c, V, adr, last - window, last, prev10, strict=(side == "long"))]
            bos += [(bi, b, "range") for bi, b in BX._range_breakouts(h, l, c, V, adr, last - window, last, prev10)]
            best = None
            for bi, b, kind in sorted(bos, key=lambda x: -x[0]):          # most recent break first
                w_ = BX.retest_walk(h, l, c, b, bi, last, adr[bi])
                st = w_["state"]
                T, Bb = b["top"], b["bot"]
                if st in ("coming", "support", "bounced") and not (st == "bounced" and last - w_["bounce"] >= BX.RT["fresh"]):
                    tag = {"coming": "coming", "support": "at", "bounced": "go"}[st]
                    if tag == "at" and c[last] < T:
                        tag = "inside"
                    best = (bi, b, kind, w_, "retest_" + side, tag, None)
                    break
                if st == "failed" and w_.get("bounce") is None and w_["i"] - bi <= FAR_DAYS:
                    f = w_["i"]
                    if np.nanmax(c[f:last + 1]) > T:                       # reclaimed the line: no trap anymore
                        continue
                    far_i = next((k for k in range(f + 1, last + 1) if c[k] < Bb <= c[k - 1]), None)
                    if far_i is not None and last - far_i >= BX.RT["fresh"]:
                        continue                                           # far-side break is old news
                    if far_i is None and last - f > FAR_DAYS:
                        continue
                    tag = "far" if far_i is not None else ("failed" if last - f < BX.RT["fresh"] else "falling")
                    best = (bi, b, kind, w_, "trap_" + ("short" if side == "long" else "long"), tag, (f, far_i))
                    break
            if not best:
                continue
            bi, b, kind, w_, typ, tag, fx = best
            top, bot, lvl, farp = BX._real_box(b, side)
            price = C[last]
            a = lvl * adr[bi] / 100
            dd = d if typ.startswith("retest") else -d
            if typ.startswith("retest"):
                stop = (float(np.nanmin(L[w_["touch"]:last + 1])) if d > 0 else float(np.nanmax(H[w_["touch"]:last + 1]))) \
                    if w_.get("touch") is not None else None
                target = top + (top - bot) if d > 0 else bot - (top - bot)
            else:
                if tag == "far":
                    k5 = np.nanmax(h[last - 4:last + 1])
                    stop = k5 if side == "long" else 1 / k5
                    target = (bot - (top - bot)) if side == "long" else (top + (top - bot))
                else:
                    sb = b["top"] * (1 + 0.5 * adr[bi] / 100)
                    stop = sb if side == "long" else 1 / sb
                    target = farp
            s = info.get(t, {})
            ext = w_["ph"] if side == "long" else 1 / w_["ph"]
            rows.append({
                "t": t, "name": s.get("name") or names.get(t, ""), "price": BX._r(price), "type": typ, "side": "long" if dd > 0 else "short",
                "tag": tag, "kind": kind, "win": b["win"], "len": b["len"], "wks": round(b["len"] / 5, 1), "touches": b.get("touches"),
                "start": dates[b["s"]].strftime("%Y-%m-%d"), "bo_date": dates[bi].strftime("%Y-%m-%d"), "bo_ago": last - bi,
                "bvx": BX._r(V[bi] / b["bvol"], 2) if b["bvol"] else None,
                "top": BX._r(top), "bot": BX._r(bot), "lvl": BX._r(lvl), "farp": BX._r(farp), "height": BX._r(top / bot - 1, 4),
                "ph": BX._r(ext), "ext_adr": BX._r(d * (ext - lvl) / a, 1), "vs_lvl_adr": BX._r(d * (price - lvl) / a, 1), "vs_lvl": BX._r(d * (price / lvl - 1), 4),
                "touch_ago": None if w_.get("touch") is None else last - w_["touch"],
                "bounce_ago": None if w_.get("bounce") is None else last - w_["bounce"],
                "fail_ago": None if not fx else last - fx[0], "far_ago": None if not fx or fx[1] is None else last - fx[1],
                "stop": BX._r(stop) if stop is not None else None, "target": BX._r(target), "tgt_pct": BX._r(target / price - 1, 4),
                "adr": BX._r(ADR[last, j], 1), "rsr": s.get("rsr") if s.get("rsr") is not None else BX._r(rs[-1, j], 0),
                "off_hi": BX._r(price / h52[-1, j] - 1, 4) if np.isfinite(h52[-1, j]) else None,
                "theme": (s.get("themes") or [None])[0], "sub": s.get("sub"),
                "px": [BX._r(x) for x in C[max(0, b["s"] - 10):]], "bs": min(10, b["s"]), "be": min(10, b["s"]) + b["len"] - 1,
                "bo": min(10, b["s"]) + (bi - b["s"]),
                # for confluence features (same names as the research events)
                "_j": j, "_ev": {"j": j, "t": t, "i": last, "type": typ, "kind": kind, "win": b["win"],
                                 "bvx": V[bi] / b["bvol"] if b["bvol"] else np.nan, "ext": (w_["ph"] - b["top"]) / (b["top"] * adr[bi] / 100),
                                 "inside": bool(tag == "inside"), "days_fail": (fx[0] - bi) if fx else None},
            })
    return rows


def confluence(rows, R, w, cols, rs, ADR, spy, mk, grp, sub_of, theme_of, thm):
    """Tag each live row with the proven confluences of its trade (helps / hurts) and grade it."""
    evs = features([r["_ev"] for r in rows], w, cols, rs, ADR, spy, mk, grp, sub_of, theme_of, thm)
    for r, e in zip(rows, evs):
        X = (R or {}).get(r["type"]) or {}
        prov = {x["name"]: proven(x) for x in X.get("rows", [])}
        dd = 1 if r["side"] == "long" else -1
        flags = []
        for g, nm, fn in conditions(dd):
            if g == "Market" or not prov.get(nm):
                continue
            if fn(e):
                flags.append({"name": nm, "eff": prov[nm]})
        sc = sum(f["eff"] for f in flags)
        r["conf"], r["score"] = flags, sc
        r["grade"] = "A" if sc >= 2 else "B" if sc == 1 else "C"
        r["group_ok"] = any(fn(e) for g, nm, fn in conditions(dd) if nm in GROUP_OK)
        r["g_r20"] = BX._r(e.get("g_r20"), 2) if _ok(e.get("g_r20")) else None
        r["th_r20"] = BX._r(e.get("th_r20"), 2) if _ok(e.get("th_r20")) else None
        r["g_br"] = BX._r(e.get("g_br"), 2) if _ok(e.get("g_br")) else None
        r.pop("_ev", None); r.pop("_j", None)
    return rows


def playbook_states(ev):
    """Box Retest (long, with group confluence) by playbook state, 5-session R (same yardstick as other setups)."""
    conds = {nm: fn for g, nm, fn in conditions(1)}
    sub = [e for e in ev if e["type"] == "retest_long" and _ok(e.get("R5")) and any(conds[n](e) for n in GROUP_OK)]
    out = {}
    for k in ("all", "thrust", "strong", "mixed", "weak"):
        s = sub if k == "all" else [e for e in sub if (e["state"] != "none" if k == "thrust" else e["state"] == "none" and e["regime"] == k)]
        x = np.array([e["R5"] for e in s])
        out[k] = {"n": int(len(x)), "avg_r": round(float(x.mean()), 3) if len(x) else None, "win": round(float((x > 0).mean()), 3) if len(x) else None}
    s20 = [e["R"] for e in sub if e["state"] != "none" and _ok(e.get("R"))]
    out["thrust_R20"] = {"n": len(s20), "avg_r": round(float(np.mean(s20)), 3) if s20 else None}
    return out


def run(adjusted, universe, stocks, names, breadth):
    """Everything for the dashboard: today's tags with confluence, and the research."""
    from . import config, strength, store
    w = strength.wide_all(adjusted)
    dates = w["c"].index
    cols = [t for t in w["c"].columns if t in set(universe)]
    C, V, H, L = (w[k][cols].to_numpy() for k in ("c", "v", "h", "l"))
    dv = pd.DataFrame(C * V).rolling(50, min_periods=30).mean().to_numpy()
    liq = (C >= 5) & (dv >= 20e6)
    ADR = (pd.DataFrame(H / L).rolling(20, min_periods=15).mean().to_numpy() - 1) * 100
    raw = strength.rs_raw(w["c"][cols])
    rs = (raw.where(pd.DataFrame(liq, index=dates, columns=cols)).rank(axis=1, pct=True) * 99).clip(1, 99).to_numpy()
    spy, spyo = w["c"][config.BENCHMARK].to_numpy(), w["o"][config.BENCHMARK].to_numpy()
    h52 = pd.DataFrame(H).rolling(252, min_periods=60).max().to_numpy()
    sub = store.load_subthemes()
    th = store.load_themes()
    th = th[th["role"] == "member"] if "role" in th.columns else th
    sub_of, theme_of = dict(zip(sub["ticker"], sub["subtheme"])), dict(zip(th["ticker"], th["theme"]))
    grp = group_frames(w["c"], sub.groupby("subtheme")["ticker"].apply(list).to_dict(), spy)
    thm = group_frames(w["c"], th.groupby("theme")["ticker"].apply(list).to_dict(), spy)
    mk = market_frame(dates, breadth, spy)
    ev = features(collect(w, cols, liq, rs, ADR, spy, spyo), w, cols, rs, ADR, spy, mk, grp, sub_of, theme_of, thm)
    first = BX.CFG["pole_days"] + BX.CFG["min_len"] + 2
    split = dates[first + (len(dates) - first) // 2].strftime("%Y-%m-%d")
    R = study(ev, split)
    for typ in R:
        R[typ]["episodes"] = episodes(ev, breadth, typ) if breadth is not None else []
    info = {s["t"]: s for s in stocks or []}
    rows = confluence(live(w, cols, liq, rs, ADR, h52, dates, info, names or {}), R, w, cols, rs, ADR, spy, mk, grp, sub_of, theme_of, thm)
    order = {"go": 0, "failed": 0, "far": 0, "at": 1, "inside": 2, "falling": 2, "coming": 3}
    rows.sort(key=lambda r: (order.get(r["tag"], 9), -r["score"], -(r["rsr"] or 0) * (1 if r["side"] == "long" else -1)))
    now = {"state": str(mk["state"][-1]), "regime": str(mk["regime"][-1])}
    return {"live": rows, "study": R, "split": split, "now_state": now, "pb": playbook_states(ev),
            "from": dates[first].strftime("%Y-%m-%d"), "to": dates[-1].strftime("%Y-%m-%d"),
            "baseline": baseline(w, cols, liq, spy, spyo, first)}


def baseline(w, cols, liq, spy, spyo, first):
    """Any liquid stock, every 5th session: 21-day return vs SPY from the next open (long; shorts = minus this)."""
    O, C = w["o"][cols].to_numpy(), w["c"][cols].to_numpy()
    xs = []
    for i in range(first, len(C) - 22, 5):
        e, x = O[i + 1], C[i + 21]
        m = liq[i] & np.isfinite(e) & np.isfinite(x) & (e > 0)
        xs.append(np.clip((x[m] / e[m] - 1) - (spy[i + 21] / spyo[i + 1] - 1), -0.6, 0.6))
    x = np.concatenate(xs) if xs else np.array([])
    return {"x21": round(float(x.mean()), 4) if len(x) else None, "x21_med": round(float(np.median(x)), 4) if len(x) else None}
