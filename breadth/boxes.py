"""Box breakouts (Edwards & Magee "rectangle", Darvas box): a daily scan with a box-length filter.

The pattern (Loew's, Nov 1936 - Jan 1937, Technical Analysis of Stock Trends):
  1. a sharp advance (the "pole") lifts the stock into a new trading range,
  2. it then trades sideways between a flat top and a flat bottom for weeks, touching
     both edges more than once, while volume dries up (quieter than during the advance),
  3. it closes above the top of the box, ideally on expanding volume. The classic
     "measured move" target is the box height added to the top.

Rules (all on split-adjusted daily bars, common-stock universe, $5+, $10M+ a day):
  box      longest stretch of 10-130 sessions whose high-low range is no taller than
           BOX_ADR[window] ADRs (20-day ADR at the end of the box) and 25%;
           2+ separate touches of the top and of the bottom (within 20% of the height);
           flat: the best-fit line through the closes moves less than half the height.
  pole     in the 40 sessions before the box the stock rose 15%+ (and 4+ ADRs) from its
           low to the box top, and that low sits 5%+ under the box bottom.
  dry-up   average volume inside the box <= 0.9x the average volume of the pole.
Windows: 2-4 weeks (10-20 sessions), 4-8 weeks (21-40), 2-3 months (41-65), 3-6 months (66-130).

Status today: breakout today (first close above the top), recent breakout (1-5 sessions
ago and still above the top), near the top (inside, within 1 ADR), in the box.

THE TRADE (Adam, Oct 16 2026): breakout -> sharp pullback to the old box top (now support) -> bounce.
`retest_walk` follows every breakout of the last RT["window"] sessions and tags it:
  coming back  the post-breakout high reached 1+ ADR above the top, price has since dropped 1+ ADR
               off that high and is now within 3 ADRs of the top, not touched yet
  at support   a low came within 0.5 ADR of the top (or below it), no bounce yet; "back inside"
               when the close is under the top. Dead if it closes under the box middle.
  bounced      first close above the prior day's high AND above the box top after the touch,
               in the last 2 sessions. Stop = lowest low since the touch.
`retest_events` + `retest_study` test the bounce entry (buy the bounce close) by market type.

Backtest (`evidence`): every first close above a qualifying box over our ~2 years vs a
baseline of every first close at a new 20-day high (same liquidity), next 5/10/20
sessions vs SPY, target hit rate and failure rate (close back below the box bottom
within 20 sessions), by window and breadth regime.
"""
import numpy as np
import pandas as pd

CFG = {"min_price": 5.0, "min_dvol": 10e6, "min_len": 10, "max_len": 130, "max_height": 0.25, "min_height": 0.03, "min_h_adr": 1.0,
       "touch": 0.20, "min_touch": 2, "touch_gap": 3, "flat": 0.5,
       "pole_days": 40, "pole_min": 0.15, "pole_adr": 4.0, "pole_under": 0.05, "dry": 0.9,
       "break_vol": 1.3, "recent": 5, "near_adr": 1.0, "hold": 20}
WINDOWS = [("w2", "2-4 weeks", 10, 20, 3.0), ("w4", "4-8 weeks", 21, 40, 4.0),
           ("m2", "2-3 months", 41, 65, 5.0), ("m3", "3-6 months", 66, 130, 6.0)]
_LIM = np.zeros(CFG["max_len"] + 1)
_WIN = np.empty(CFG["max_len"] + 1, dtype=object)
for _k, _n, _a, _b, _x in WINDOWS:
    _LIM[_a:_b + 1] = _x
    _WIN[_a:_b + 1] = _k


def _touches(x, gap):
    """Number of separate touches: runs of True bars split by `gap`+ bars without one."""
    idx = np.flatnonzero(x)
    if not len(idx):
        return 0
    return 1 + int(np.sum(np.diff(idx) > gap))


def find_box(h, l, c, v, e, adr, strict=True):
    """Longest qualifying box ending at bar e (inclusive). adr in %. Returns a dict or None.
    strict=False skips the advance and dry-up rules (used for the short side, where the box can
    sit after a decline or at a top)."""
    P = CFG
    if not np.isfinite(adr) or adr <= 0:
        return None
    first = e - P["max_len"] + 1
    lo_start = P["pole_days"] + 1
    if e - P["min_len"] + 1 < lo_start:
        return None
    a = max(first, lo_start)
    hh, ll = h[a:e + 1][::-1], l[a:e + 1][::-1]          # bar e first, going back
    top = np.maximum.accumulate(hh)
    bot = np.minimum.accumulate(ll)
    L = np.arange(1, len(hh) + 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        hgt = top / bot - 1
    lim = np.minimum(_LIM[np.minimum(L, P["max_len"])] * adr / 100, P["max_height"])
    ok = (L >= P["min_len"]) & (hgt <= lim) & np.isfinite(hgt)
    for k in np.flatnonzero(ok)[::-1]:                    # longest first
        n = int(L[k])
        s = e - n + 1
        T, B = float(top[k]), float(bot[k])
        H = T - B
        if H <= 0 or T / B - 1 < max(P["min_height"], P["min_h_adr"] * adr / 100):   # pinned / buyout "boxes"
            continue
        hs, ls, cs = h[s:e + 1], l[s:e + 1], c[s:e + 1]
        if _touches(hs >= T - P["touch"] * H, P["touch_gap"]) < P["min_touch"]:
            continue
        if _touches(ls <= B + P["touch"] * H, P["touch_gap"]) < P["min_touch"]:
            continue
        slope = np.polyfit(np.arange(n), cs, 1)[0] if n > 2 else 0.0
        if abs(slope * n) > P["flat"] * H:
            continue
        pl = l[s - P["pole_days"]:s]
        if not np.isfinite(pl).all():
            continue
        j = int(np.argmin(pl))
        plo = float(pl[j])
        if not np.isfinite(plo) or plo <= 0:
            continue
        gain = T / plo - 1
        if strict and (gain < P["pole_min"] or gain * 100 < P["pole_adr"] * adr or plo > B * (1 - P["pole_under"])):
            continue
        pv = v[s - P["pole_days"] + j:s]
        pv = pv[np.isfinite(pv)]
        bv = np.nanmean(v[s:e + 1])
        if len(pv) < 3 or not np.nanmean(pv) > 0:
            if strict:
                continue
            pv = v[s - P["pole_days"]:s]
            pv = pv[np.isfinite(pv)]
            if not len(pv) or not np.nanmean(pv) > 0:
                continue
        dry = bv / np.nanmean(pv)
        if strict and not dry <= P["dry"]:
            continue
        third = max(n // 3, 1)
        return {"s": s, "e": e, "len": n, "win": _WIN[n], "top": T, "bot": B, "height": T / B - 1,
                "h_adr": (T / B - 1) * 100 / adr, "pole": gain, "pole_days": s - (s - P["pole_days"] + j),
                "dry": dry, "fade": np.nanmean(v[e - third + 1:e + 1]) / np.nanmean(v[s:s + third]),
                "bvol": bv, "pole_vol": float(np.nanmax(pv))}
    return None


def _adr(h, l):
    """20-day ADR % series (mean high/low - 1)."""
    return (pd.Series(h / l).rolling(20, min_periods=15).mean().to_numpy() - 1) * 100


def _r(x, n=2):
    return None if x is None or not np.isfinite(x) else round(float(x), n)


def _status(h, l, c, v, adr, N):
    """Today's row for one stock, or None."""
    last = N - 1
    # breakouts: the box ended the session before the first close above its top
    for ago in range(0, CFG["recent"] + 1):
        bi = last - ago
        if bi < 1:
            break
        if not np.isfinite(c[bi]) or not np.isfinite(c[bi - 1]):
            continue
        b = find_box(h, l, c, v, bi - 1, adr[bi - 1])
        if not b or not (c[bi] > b["top"] >= c[bi - 1]):
            continue
        if ago and c[last] < b["top"]:
            return None          # broke out and fell back into the box: not a setup anymore
        b.update(state="today" if ago == 0 else "recent", ago=ago, bvx=v[bi] / b["bvol"] if b["bvol"] else None,
                 bchg=c[bi] / c[bi - 1] - 1)
        return b
    b = find_box(h, l, c, v, last, adr[last])
    if not b:
        return None
    near = (b["top"] - c[last]) / c[last] * 100 / adr[last] <= CFG["near_adr"]
    b.update(state="near" if near else "inside", ago=None, bvx=None, bchg=None)
    return b


def _liquid(c, v):
    dv = pd.DataFrame(c * v).rolling(20, min_periods=15).mean().to_numpy()
    return (c >= CFG["min_price"]) & (dv >= CFG["min_dvol"])


def build(adjusted, universe, stocks=None, names=None, breadth=None, evidence=True):
    """Payload for DATA.themes.boxes: today's rows + backtest evidence."""
    from . import config, strength
    names = names or {}
    info = {r["t"]: r for r in (stocks or [])}
    w = strength.wide_all(adjusted)
    cols = [t for t in w["c"].columns if t in set(universe)]
    H, Lo, C, V = (w[k][cols].to_numpy() for k in ("h", "l", "c", "v"))
    dates = w["c"].index
    N = len(dates)
    if N < 60:
        return None
    liq = _liquid(C, V)
    ADR = (pd.DataFrame(H / Lo).rolling(20, min_periods=15).mean().to_numpy() - 1) * 100
    raw = strength.rs_raw(w["c"][cols])
    rs = (raw.where(pd.DataFrame(liq, index=dates, columns=cols)).rank(axis=1, pct=True) * 99).clip(1, 99).to_numpy()
    h52 = pd.DataFrame(H).rolling(252, min_periods=60).max().to_numpy()

    rows = []
    for j, t in enumerate(cols):
        if not liq[-1, j]:
            continue
        b = _status(H[:, j], Lo[:, j], C[:, j], V[:, j], ADR[:, j], N)
        if not b:
            continue
        price = C[-1, j]
        s = info.get(t, {})
        rows.append({
            "t": t, "name": s.get("name") or names.get(t, ""), "price": _r(price), "state": b["state"], "ago": b["ago"],
            "win": b["win"], "len": b["len"], "wks": round(b["len"] / 5, 1), "start": dates[b["s"]].strftime("%Y-%m-%d"),
            "top": _r(b["top"]), "bot": _r(b["bot"]), "height": _r(b["height"], 4), "h_adr": _r(b["h_adr"], 1),
            "pole": _r(b["pole"], 4), "dry": _r(b["dry"], 2), "fade": _r(b["fade"], 2),
            "bvx": _r(b["bvx"], 2), "bchg": _r(b["bchg"], 4),
            "vs_top": _r(price / b["top"] - 1, 4), "target": _r(b["top"] + (b["top"] - b["bot"])),
            "tgt_pct": _r((b["top"] + (b["top"] - b["bot"])) / price - 1, 4), "stop": _r(b["bot"]),
            "adr": _r(ADR[-1, j], 1), "rsr": s.get("rsr") if s.get("rsr") is not None else _r(rs[-1, j], 0),
            "off_hi": _r(price / h52[-1, j] - 1, 4) if np.isfinite(h52[-1, j]) else None,
            "dvol": _r(np.nanmean(C[-20:, j] * V[-20:, j]) / 1e6, 0),
            "theme": (s.get("themes") or [None])[0], "sub": s.get("sub"), "tier": s.get("tier"),
            # mini chart: closes from the start of the advance window to today; box = px[bs:be+1]
            "px": [_r(x) for x in C[b["s"] - CFG["pole_days"]:, j]], "bs": CFG["pole_days"], "be": CFG["pole_days"] + b["len"] - 1,
        })
    order = {"today": 0, "recent": 1, "near": 2, "inside": 3}
    rows.sort(key=lambda r: (order[r["state"]], r["ago"] or 0, -(r["rsr"] or 0)))
    out = {"date": dates[-1].strftime("%Y-%m-%d"), "rows": rows, "cfg": CFG,
           "windows": [{"key": k, "name": n, "lo": a, "hi": b, "adr": x} for k, n, a, b, x in WINDOWS],
           "counts": {k: sum(r["state"] == k for r in rows) for k in order}}
    try:
        from . import metrics as MT
        tw = MT.thrust_window(breadth, dates) if breadth is not None else np.zeros(N, bool)
        br = breadth.reindex(dates).iloc[-1] if breadth is not None else None
        reg = None if br is None else ("strong" if br["ratio5"] >= 1.5 and br["ratio10"] >= 1.5 else "weak" if br["ratio10"] < 1 else "mixed")
        last_thr = int(np.flatnonzero(tw)[-1]) if tw.any() else None
        since = market_arrays(breadth, dates)["since"][-1]
        out["now"] = {"thrust": bool(tw[-1]), "regime": reg, "since": None if not np.isfinite(since) else int(since)}
    except Exception:
        out["now"] = {"thrust": False, "regime": None}
    out["rt"] = retest_today(H, Lo, C, V, ADR, liq, rs, h52, dates, cols, info, names, "long")
    out["rt_short"] = retest_today(H, Lo, C, V, ADR, liq, rs, h52, dates, cols, info, names, "short")
    out["rt_cfg"] = RT
    if evidence:
        first = CFG["pole_days"] + CFG["min_len"] + 2
        split = dates[first + (N - first) // 2].strftime("%Y-%m-%d")
        spy = w["c"][config.BENCHMARK].to_numpy()
        for side, key in (("long", "rt_study"), ("short", "rt_study_short")):
            try:
                ev = retest_events(H, Lo, C, V, ADR, liq, rs, dates, spy, breadth, side=side)
                out[key] = retest_study(ev, split, side)
                out[key]["from"], out[key]["to"] = dates[first].strftime("%Y-%m-%d"), dates[-1].strftime("%Y-%m-%d")
            except Exception as e:
                import logging
                logging.getLogger(__name__).exception("retest study (%s) failed: %s", side, e)
                out[key] = None
        try:
            out["evidence"] = backtest(H, Lo, C, V, ADR, liq, rs, dates, w["c"].get(config.BENCHMARK), breadth)
        except Exception as e:   # evidence is optional
            import logging
            logging.getLogger(__name__).exception("box backtest failed: %s", e)
            out["evidence"] = None
    return out


def backtest(H, Lo, C, V, ADR, liq, rs, dates, spy, breadth=None, hold=None):
    hold = hold or CFG["hold"]
    N, M = C.shape
    first = CFG["pole_days"] + CFG["min_len"] + 2
    spy = spy.to_numpy(dtype=float) if spy is not None else np.ones(N)
    if breadth is not None and {"ratio5", "ratio10"} <= set(breadth.columns):
        br = breadth.reindex(dates)
        regime = np.where((br["ratio5"] >= 1.5) & (br["ratio10"] >= 1.5), "strong",
                          np.where(br["ratio10"] < 1, "weak", "mixed"))
    else:
        regime = np.full(N, "mixed")
    prev20 = pd.DataFrame(H).rolling(20).max().shift(1).to_numpy()
    sig, base = [], []

    def fwd(i, j, entry, top=None, bot=None):
        o = {}
        for k in (5, 10, 20):
            if i + k < N and np.isfinite(C[i + k, j]):
                o[k] = (C[i + k, j] / entry - 1) - (spy[i + k] / spy[i] - 1)
        if top is not None and i + hold < N:
            hi = np.nanmax(H[i + 1:i + hold + 1, j])
            o["tgt"] = bool(hi >= top + (top - bot))
            o["fail"] = bool(np.nanmin(C[i + 1:i + hold + 1, j]) < bot)
        return o

    for j in range(M):
        h, l, c, v, adr = H[:, j], Lo[:, j], C[:, j], V[:, j], ADR[:, j]
        cand = np.flatnonzero(liq[:, j] & (c > prev20[:, j]) & np.r_[False, c[:-1] <= prev20[1:, j]])
        last_b = -99
        for i in cand:
            if i < first or i + 5 >= N:
                continue
            base.append((i, regime[i], fwd(i, j, c[i])))
            if i - last_b < 10:
                continue
            b = find_box(h, l, c, v, i - 1, adr[i - 1])
            if not b or not (c[i] > b["top"] >= c[i - 1]):
                continue
            last_b = i
            o = fwd(i, j, c[i], b["top"], b["bot"])
            sig.append((i, regime[i], o, b["win"], (v[i] / b["bvol"]) if b["bvol"] else 0, rs[i, j]))

    def stat(items, k=10):
        x = np.array([s[2][k] for s in items if k in s[2]])
        if len(x) < 5:
            return {"n": int(len(x))}
        x = np.clip(x, -0.5, 0.5)
        out = {"n": int(len(x)), "ret": round(float(x.mean()), 4), "median": round(float(np.median(x)), 4),
               "win": round(float((x > 0).mean()), 3), "t": round(float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))), 2)
               if x.std(ddof=1) > 0 else None}
        return out

    def block(items):
        d = {f"d{k}": stat(items, k) for k in (5, 10, 20)}
        tg = [s[2]["tgt"] for s in items if "tgt" in s[2]]
        fl = [s[2]["fail"] for s in items if "fail" in s[2]]
        if tg:
            d["tgt"] = round(float(np.mean(tg)), 3)
            d["fail"] = round(float(np.mean(fl)), 3)
        return d

    half = dates[first + (N - first) // 2]
    ev = {"from": dates[first].strftime("%Y-%m-%d"), "to": dates[-1].strftime("%Y-%m-%d"), "hold": hold,
          "split": half.strftime("%Y-%m-%d"),
          "all": block(sig), "base": {f"d{k}": stat(base, k) for k in (5, 10, 20)},
          "vol": block([s for s in sig if s[4] >= CFG["break_vol"]]),
          "novol": block([s for s in sig if s[4] < CFG["break_vol"]]),
          "rs80": block([s for s in sig if np.isfinite(s[5]) and s[5] >= 80]),
          "h1": block([s for s in sig if dates[s[0]] < half]), "h2": block([s for s in sig if dates[s[0]] >= half]),
          "win": {k: block([s for s in sig if s[3] == k]) for k, *_ in WINDOWS},
          "regime": {r: block([s for s in sig if s[1] == r]) for r in ("strong", "mixed", "weak")},
          "base_regime": {r: {f"d{k}": stat([b for b in base if b[1] == r], k) for k in (10, 20)} for r in ("strong", "mixed", "weak")}}
    return ev


# ---------------------------------------------------------------------------
# Retests, both directions
#   LONG : breakout above the top  -> pullback to the old top (support)        -> bounce
#   SHORT: breakdown below the bottom -> rally back to the old bottom (resistance) -> rejection
# The short side runs the same code on reciprocal prices (1/low, 1/high, 1/close): a breakdown in
# price is a breakout in 1/price. Outcomes are always measured on real prices.
# ---------------------------------------------------------------------------
RT = {"ext": 1.0, "back": 1.0, "zone": 0.5, "come": 3.0, "expire": 25, "window": 35, "fresh": 2, "fail_frac": 0.5,
      "rs_long": 80, "rs_short": 30}


def _space(H, Lo, C, side):
    if side == "long":
        return H, Lo, C
    with np.errstate(divide="ignore", invalid="ignore"):
        return 1 / Lo, 1 / H, 1 / C


def retest_walk(h, l, c, b, bi, end, adrp):
    """Walk forward from breakout bar bi to `end` (inclusive), in breakout space. adrp = ADR % at the breakout.
    State at `end`: coming / support / bounced / failed / extended / expired / waiting / after."""
    T, B = b["top"], b["bot"]
    a = T * adrp / 100
    mid = T - RT["fail_frac"] * (T - B)
    ph, phi, touch, bounce = h[bi], bi, None, None
    state = "waiting"
    for i in range(bi + 1, end + 1):
        if not np.isfinite(c[i]):
            continue
        if c[i] < mid:
            return {"state": "failed", "i": i, "phi": phi, "ph": ph, "touch": touch, "bounce": bounce}
        if touch is None:
            if h[i] > ph:
                ph, phi = h[i], i
            if ph >= T + RT["ext"] * a and l[i] <= T + RT["zone"] * a:
                touch = i
                state = "support"
                continue
            if i - bi > RT["expire"]:
                return {"state": "expired", "i": i, "phi": phi, "ph": ph, "touch": None, "bounce": None}
            state = "coming" if (ph >= T + RT["ext"] * a and c[i] <= ph - RT["back"] * a and c[i] <= T + RT["come"] * a) \
                else ("extended" if ph >= T + RT["ext"] * a else "waiting")
            continue
        if bounce is None:
            if c[i] > h[i - 1] and c[i] > T:
                bounce = i
                state = "bounced"
            elif i - touch > RT["expire"]:
                return {"state": "expired", "i": i, "phi": phi, "ph": ph, "touch": touch, "bounce": None}
            else:
                state = "support"
        else:
            return {"state": "after", "i": i, "phi": phi, "ph": ph, "touch": touch, "bounce": bounce}
    return {"state": state, "i": end, "phi": phi, "ph": ph, "touch": touch, "bounce": bounce}


def _breakouts(h, l, c, v, adr, lo, hi, prev10, strict=True):
    """[(bi, box)] first closes above a qualifying box with bi in [lo, hi] (breakout space)."""
    out, last_b = [], -99
    for bi in range(max(lo, 1), hi + 1):
        if not (np.isfinite(c[bi]) and np.isfinite(prev10[bi]) and c[bi] > prev10[bi]) or bi - last_b < 10:
            continue
        b = find_box(h, l, c, v, bi - 1, adr[bi - 1], strict=strict)
        if b and c[bi] > b["top"] >= c[bi - 1]:
            out.append((bi, b))
            last_b = bi
    return out


def _real_box(b, side):
    """(top, bottom, level, far) in real prices; level = the line being retested."""
    if side == "long":
        return b["top"], b["bot"], b["top"], b["bot"]
    top, bot = 1 / b["bot"], 1 / b["top"]
    return top, bot, bot, top


def retest_today(H, Lo, C, V, ADR, liq, rs, h52, dates, cols, info, names, side="long"):
    N = len(dates)
    last = N - 1
    d = 1 if side == "long" else -1
    SH, SL, SC = _space(H, Lo, C, side)
    prev10 = pd.DataFrame(SH).rolling(10).max().shift(1).to_numpy()
    TAG = {"coming": "coming", "support": "at", "bounced": "go"}
    rows = []
    for j, t in enumerate(cols):
        if not liq[-1, j]:
            continue
        h, l, c, v, adr = SH[:, j], SL[:, j], SC[:, j], V[:, j], ADR[:, j]
        best = None
        for bi, b in reversed(_breakouts(h, l, c, v, adr, last - RT["window"], last, prev10[:, j], strict=(side == "long"))):
            w = retest_walk(h, l, c, b, bi, last, adr[bi])
            if w["state"] == "bounced" and last - w["bounce"] >= RT["fresh"]:
                continue
            if w["state"] in TAG:
                best = (bi, b, w)
                break
        if not best:
            continue
        bi, b, w = best
        top, bot, lvl, far = _real_box(b, side)
        rc, rh, rl = C[:, j], H[:, j], Lo[:, j]
        price = rc[last]
        a = lvl * adr[bi] / 100
        ext = w["ph"] if side == "long" else 1 / w["ph"]      # furthest point past the line since the break
        tag = TAG[w["state"]]
        if tag == "at" and d * (price - lvl) < 0:
            tag = "inside"
        stop = None
        if w.get("touch") is not None:
            stop = float(np.nanmin(rl[w["touch"]:last + 1])) if side == "long" else float(np.nanmax(rh[w["touch"]:last + 1]))
        midp = (top + bot) / 2
        target = top + (top - bot) if side == "long" else bot - (top - bot)
        s = info.get(t, {})
        rsv = s.get("rsr") if s.get("rsr") is not None else _r(rs[-1, j], 0)
        rsv = rsv if rsv is not None else 50
        good = rsv >= RT["rs_long"] if side == "long" else rsv <= RT["rs_short"]
        rows.append({
            "t": t, "name": s.get("name") or names.get(t, ""), "price": _r(price), "side": side, "tag": tag,
            "win": b["win"], "len": b["len"], "wks": round(b["len"] / 5, 1), "start": dates[b["s"]].strftime("%Y-%m-%d"),
            "bo_date": dates[bi].strftime("%Y-%m-%d"), "bo_ago": last - bi,
            "bvx": _r(v[bi] / b["bvol"], 2) if b["bvol"] else None,
            "top": _r(top), "bot": _r(bot), "lvl": _r(lvl), "mid": _r(midp), "height": _r(top / bot - 1, 4),
            "ph": _r(ext), "ext_adr": _r(d * (ext - lvl) / a, 1), "vs_lvl_adr": _r(d * (price - lvl) / a, 1),
            "vs_lvl": _r(d * (price / lvl - 1), 4),
            "touch_ago": None if w.get("touch") is None else last - w["touch"],
            "bounce_ago": None if w.get("bounce") is None else last - w["bounce"],
            "stop": _r(stop if stop is not None else midp), "stop_kind": "retest" if stop is not None else "box middle",
            "target": _r(target), "tgt_pct": _r(target / price - 1, 4),
            "adr": _r(adr[last], 1), "rsr": rsv,
            "off_hi": _r(price / h52[-1, j] - 1, 4) if np.isfinite(h52[-1, j]) else None,
            "dvol": _r(np.nanmean(C[-20:, j] * V[-20:, j]) / 1e6, 0),
            "theme": (s.get("themes") or [None])[0], "sub": s.get("sub"), "d60": s.get("d60"),
            "grade": ("A" if b["win"] == "w2" else "B") if good else "C",
            "px": [_r(x) for x in rc[b["s"] - 10:]], "bs": 10, "be": 10 + b["len"] - 1, "bo": 10 + (bi - b["s"]),
        })
    order = {"go": 0, "at": 1, "inside": 2, "coming": 3}
    rows.sort(key=lambda r: (order[r["tag"]], r["grade"], r["bounce_ago"] or 0, -d * (r["rsr"] or 0)))
    return rows


def market_arrays(breadth, dates):
    N = len(dates)
    if breadth is None:
        z = np.full(N, np.nan)
        return {"regime": np.full(N, "mixed"), "tw": np.zeros(N, bool), "since": z, "t2108": z, "dn10": z, "nhnl": z}
    br = breadth.reindex(dates)
    regime = np.where((br["ratio5"] >= 1.5) & (br["ratio10"] >= 1.5), "strong", np.where(br["ratio10"] < 1, "weak", "mixed"))
    from . import metrics as MT
    tw = MT.thrust_window(breadth, dates)
    # sessions since the latest major thrust / follow-through
    starts = np.zeros(N, bool)
    pos = {dd: i for i, dd in enumerate(dates)}
    try:
        for e in MT.events(breadth):
            if e.get("kind") in ("thrust", "followthrough") and e.get("tier") == "major":
                i = pos.get(pd.Timestamp(e["date"]))
                if i is not None:
                    starts[i] = True
    except Exception:
        pass
    since, last = np.full(N, np.nan), None
    for i in range(N):
        if starts[i]:
            last = i
        if last is not None:
            since[i] = i - last
    col = lambda k: br[k].to_numpy(dtype=float) if k in br else np.full(N, np.nan)
    return {"regime": regime, "tw": tw, "since": since, "t2108": col("t2108"), "dn10": col("dn_share10"),
            "nhnl": (col("nh10") - col("nl10"))}


def retest_events(H, Lo, C, V, ADR, liq, rs, dates, spy, breadth=None, side="long", hold=20):
    """Every bounce (long) / rejection (short) off a retested box edge in history, with conditions."""
    N, M = C.shape
    d = 1 if side == "long" else -1
    first = CFG["pole_days"] + CFG["min_len"] + 2
    SH, SL, SC = _space(H, Lo, C, side)
    prev10 = pd.DataFrame(SH).rolling(10).max().shift(1).to_numpy()
    h52 = pd.DataFrame(H).rolling(252, min_periods=60).max().to_numpy()
    spy = np.asarray(spy, dtype=float)
    s50 = pd.Series(spy).rolling(50).mean().to_numpy()
    s200 = pd.Series(spy).rolling(200, min_periods=120).mean().to_numpy()
    mk = market_arrays(breadth, dates)
    ev = []

    def trade(i, entry, stop, risk, end, j):
        rh, rl, rc = H[:, j], Lo[:, j], C[:, j]
        xi, xp = end, rc[end]
        for k in range(i + 1, end + 1):
            if (rl[k] <= stop) if d > 0 else (rh[k] >= stop):
                xi, xp = k, stop
                break
        return float(np.clip(d * (xp - entry) / risk, -3, 10)), xi

    for j in range(M):
        if not liq[:, j].any():
            continue
        h, l, c, v, adr = SH[:, j], SL[:, j], SC[:, j], V[:, j], ADR[:, j]
        rh, rl, rc = H[:, j], Lo[:, j], C[:, j]
        for bi, b in _breakouts(h, l, c, v, adr, first, N - 3, prev10[:, j], strict=(side == "long")):
            if not liq[bi, j]:
                continue
            w = retest_walk(h, l, c, b, bi, min(N - 1, bi + 2 * RT["expire"] + 5), adr[bi])
            if w.get("bounce") is None:
                ev.append({"kind": "nobounce", "i": bi, "touch": w.get("touch") is not None, "state": w["state"]})
                continue
            i = w["bounce"]
            top, bot, lvl, far = _real_box(b, side)
            entry = rc[i]
            stop = float(np.nanmin(rl[w["touch"]:i + 1])) if d > 0 else float(np.nanmax(rh[w["touch"]:i + 1]))
            risk = max(d * (entry - stop), 0.3 * entry * adr[i] / 100)
            o = {"kind": "bounce", "i": i, "date": dates[i].strftime("%Y-%m-%d"), "j": j}
            for k in (5, 10, 20):
                if i + k < N and np.isfinite(rc[i + k]):
                    o[f"d{k}"] = float(np.clip(d * ((rc[i + k] / entry - 1) - (spy[i + k] / spy[i] - 1)), -0.5, 0.5))
            if i + 5 < N:
                o["R5"], _ = trade(i, entry, stop, risk, i + 5, j)
            if i + 5 < N:
                midp = (top + bot) / 2       # wider stop variant: the middle of the box
                rk = max(d * (entry - midp), 0.3 * entry * adr[i] / 100)
                o["Rm"], _ = trade(i, entry, midp, rk, min(N - 1, i + hold), j)
                end = min(N - 1, i + hold)
                o["R"], xi = trade(i, entry, stop, risk, end, j)
                target = top + (top - bot) if d > 0 else bot - (top - bot)
                seg = rh[i + 1:xi + 1] if d > 0 else rl[i + 1:xi + 1]
                o["tgt"] = bool(len(seg) and ((np.nanmax(seg) >= target) if d > 0 else (np.nanmin(seg) <= target)))
                o["stopped"] = xi < end
            s0 = b["s"]
            prior = rc[s0 - 1] / rc[s0 - 41] - 1 if s0 >= 41 and np.isfinite(rc[s0 - 41]) else np.nan
            o.update({
                "regime": str(mk["regime"][i]), "thrust": bool(mk["tw"][i]), "since": mk["since"][i],
                "state": "thrust" if mk["tw"][i] else str(mk["regime"][i]),
                "spy50": bool(spy[i] > s50[i]) if np.isfinite(s50[i]) else None,
                "spy200": bool(spy[i] > s200[i]) if np.isfinite(s200[i]) else None,
                "spy50up": bool(s50[i] > s50[i - 10]) if i >= 10 and np.isfinite(s50[i - 10]) else None,
                "t2108": mk["t2108"][i], "dn10": mk["dn10"][i], "nhnl": mk["nhnl"][i],
                "rs": rs[i, j], "win": b["win"], "len": b["len"], "bvx": v[bi] / b["bvol"] if b["bvol"] else np.nan,
                "inside": bool(d * (stop - lvl) < 0), "ext": (w["ph"] - b["top"]) / (b["top"] * adr[bi] / 100),
                "days_touch": w["touch"] - bi, "pbv": np.nanmean(v[w["phi"] + 1:w["touch"] + 1]) / v[bi] if w["touch"] > w["phi"] and v[bi] else np.nan,
                "adr": adr[i], "off": rc[i] / h52[i, j] - 1 if np.isfinite(h52[i, j]) else np.nan,
                "prior": prior,
            })
            ev.append(o)
    return ev


def _st(x):
    x = np.asarray([v for v in x if v is not None and np.isfinite(v)], dtype=float)
    if len(x) < 8:
        return {"n": int(len(x))}
    sd = x.std(ddof=1)
    return {"n": int(len(x)), "ret": round(float(x.mean()), 4), "median": round(float(np.median(x)), 4),
            "win": round(float((x > 0).mean()), 3), "t": round(float(x.mean() / (sd / np.sqrt(len(x)))), 2) if sd > 0 else None}


def retest_study(ev, split, side="long"):
    """Results by condition (R over 20 sessions with the retest stop; R5 = 5-session version), with halves."""
    B = [e for e in ev if e["kind"] == "bounce"]
    nb = [e for e in ev if e["kind"] == "nobounce"]
    ok = lambda v: v is not None and not (isinstance(v, float) and np.isnan(v))

    def blk(sub):
        d = {"d10": _st([e.get("d10") for e in sub]), "R": _st([e.get("R") for e in sub]), "R5": _st([e.get("R5") for e in sub]),
             "Rm": _st([e.get("Rm") for e in sub])}
        tg = [e["tgt"] for e in sub if "tgt" in e]
        if tg:
            d["tgt"], d["stop"] = round(float(np.mean(tg)), 3), round(float(np.mean([e["stopped"] for e in sub if "stopped" in e])), 3)
        d["h1R"] = _st([e.get("R") for e in sub if e["date"] < split]).get("ret")
        d["h2R"] = _st([e.get("R") for e in sub if e["date"] >= split]).get("ret")
        return d

    def f(k, test):
        return [e for e in B if ok(e.get(k)) and test(e[k])]

    rsk, rsn = ("rs", RT["rs_long"]) if side == "long" else ("rs", RT["rs_short"])
    good = (lambda x: x >= rsn) if side == "long" else (lambda x: x <= rsn)
    rsname = f"RS {rsn}+" if side == "long" else f"RS {rsn} or lower"
    th = [e for e in B if e["thrust"]]
    gs = [e for e in B if ok(e["rs"]) and good(e["rs"])]
    groups = [
        ("Best combinations" if side == "long" else "Key combinations", [
            (f"After a thrust + {rsname}", [e for e in th if e in gs]),
            (f"After a thrust + {rsname} + 2-4 week box", [e for e in th if e in gs and e["win"] == "w2"]),
            ("After a thrust + 2-4 week box", [e for e in th if e["win"] == "w2"]),
            ("No thrust in the last 25 sessions", [e for e in B if not e["thrust"]]),
            (f"No thrust + {rsname}", [e for e in B if not e["thrust"] and e in gs]),
            ("Strong breadth but no thrust", [e for e in B if e["regime"] == "strong" and not e["thrust"]]),
            ("Weak breadth, no thrust", [e for e in B if e["regime"] == "weak" and not e["thrust"]])]),
        ("Market", [("Strong breadth", [e for e in B if e["regime"] == "strong"]),
                    ("Mixed breadth", [e for e in B if e["regime"] == "mixed"]),
                    ("Weak breadth", [e for e in B if e["regime"] == "weak"]),
                    ("Within 25 sessions of a breadth thrust", th),
                    ("Thrust day to 5 sessions after", f("since", lambda x: 0 <= x <= 5)),
                    ("6-25 sessions after a thrust", f("since", lambda x: 6 <= x <= 25)),
                    ("SPY above its 50-day, 50-day rising", [e for e in B if e["spy50"] and e["spy50up"]]),
                    ("SPY below its 50-day", [e for e in B if e["spy50"] is False]),
                    ("SPY below its 200-day", [e for e in B if e["spy200"] is False]),
                    ("T2108 under 40 (washed out)", f("t2108", lambda x: x < 40)),
                    ("T2108 over 70 (stretched)", f("t2108", lambda x: x > 70)),
                    ("New highs beating new lows (10-day)", f("nhnl", lambda x: x > 0)),
                    ("New lows beating new highs", f("nhnl", lambda x: x <= 0)),
                    ("Money leaving (10-day share in falling stocks ≥ 52%)", f("dn10", lambda x: x >= 52)),
                    ("Money coming in (≤ 45%)", f("dn10", lambda x: x <= 45))]),
        ("Stock", [("RS 80+", f("rs", lambda x: x >= 80)), ("RS 90+", f("rs", lambda x: x >= 90)),
                   ("RS 30 or lower", f("rs", lambda x: x <= 30)), ("RS 31-79", f("rs", lambda x: 30 < x < 80)),
                   ("Within 5% of 52-week high", f("off", lambda x: x >= -0.05)), ("30%+ below 52-week high", f("off", lambda x: x <= -0.30)),
                   ("ADR 4%+", f("adr", lambda x: x >= 4)), ("ADR under 2.5%", f("adr", lambda x: x < 2.5))]),
        ("Pattern", [*[(f"{n} box", [e for e in B if e["win"] == k]) for k, n, *_ in WINDOWS],
                     ("Box after a 10%+ advance", f("prior", lambda x: x >= 0.10)),
                     ("Box after a 10%+ decline", f("prior", lambda x: x <= -0.10)),
                     ("Break on volume 1.3×+ box avg", f("bvx", lambda x: x >= 1.3)), ("Break on light volume", f("bvx", lambda x: x < 1.3)),
                     ("Retest stayed outside the box", [e for e in B if not e["inside"]]),
                     ("Retest went back inside the box", [e for e in B if e["inside"]]),
                     ("Fast retest (within 5 sessions)", f("days_touch", lambda x: x <= 5)),
                     ("Slow retest (6+ sessions)", f("days_touch", lambda x: x > 5)),
                     ("Quiet retest (vol ≤ 0.6× break day)", f("pbv", lambda x: x <= 0.6)),
                     ("Heavy retest (vol > 0.6×)", f("pbv", lambda x: x > 0.6))]),
    ]
    by_state = {}
    for k in ("all", "thrust", "strong", "mixed", "weak"):
        sub = B if k == "all" else [e for e in B if e["state"] == k]
        r5 = [e["R5"] for e in sub if ok(e.get("R5"))]
        by_state[k] = {"n": len(r5), "avg_r": round(float(np.mean(r5)), 3) if r5 else None,
                       "win": round(float(np.mean(np.array(r5) > 0)), 3) if r5 else None}
        sg = [e["R5"] for e in sub if ok(e.get("R5")) and e in gs]
        by_state[k + "_rs"] = {"n": len(sg), "avg_r": round(float(np.mean(sg)), 3) if sg else None,
                               "win": round(float(np.mean(np.array(sg) > 0)), 3) if sg else None}
    return {"side": side, "all": blk(B), "groups": [{"name": g, "rows": [{"name": n, **blk(s)} for n, s in rows]} for g, rows in groups],
            "funnel": {"breakouts": len(B) + len(nb), "touched": len(B) + sum(e["touch"] for e in nb), "bounced": len(B),
                       "failed": sum(e["state"] == "failed" for e in nb)}, "split": split, "by_state": by_state}


# ---------------------------------------------------------------------------
# Playbook hook: the long retest joins the Trade Setups as "Box Retest"
# ---------------------------------------------------------------------------
BOX_SETUP = ("box", "Box Retest", "Broke out of a flat box, snapped back to the old top and just bounced off it (RS 80+). "
             "Buy, stop under the retest low, target = box height above the top. Paid best in the weeks after a breadth thrust.")


def attach(theme_data, top=5):
    """Add today's fresh RS 80+ bounces (theme universe) to trade_setups as setup 'box' so the playbook can rank it."""
    from . import leaders as LD
    X, Bx = theme_data.get("trade_setups"), theme_data.get("boxes")
    if not X or not Bx:
        return
    stocks = {s["t"]: s for s in theme_data.get("stocks") or []}
    ts = {r["theme"]: r.get("strength") for r in theme_data.get("themes") or []}
    ss = {r["theme"]: r.get("strength") for r in theme_data.get("subthemes") or []}
    cand = [r for r in Bx.get("rt") or [] if r["tag"] == "go" and (r["rsr"] or 0) >= RT["rs_long"] and r["t"] in stocks]
    cand.sort(key=lambda r: (r["grade"], r["bounce_ago"] or 0, -(r["rsr"] or 0)))
    keys = []
    for r in cand:
        s = stocks[r["t"]]
        row = X["rows"].get(r["t"])
        if row is None:
            if not LD.eligible(s):
                continue
            score, bt, bstr, sub = LD.score_one(s, ts, ss)
            row = {"t": s["t"], "name": s.get("name", ""), "price": s["price"], "score": score, "rsr": s["rsr"], "rsr5": s.get("rsr5"),
                   "theme": bt, "theme_str": bstr, "sub": s.get("sub"), "sub_str": sub,
                   "grp": max(bstr or 0, ss.get(s.get("sub")) or 0), "off_hi": s.get("off_hi"), "e21": s.get("e21"), "e50": s.get("e50"),
                   "adr": s.get("adr"), "vdry": s.get("vdry"), "tight": s.get("tight"), "d60": s.get("d60"), "tier": s.get("tier"),
                   "star": bool(s.get("rs_nh")), "leader": False, "rising": None, "setups": [], "angles": [], "hits": 0, "tags": []}
            X["rows"][r["t"]] = row
        row["setups"] = sorted(set(row.get("setups", [])) | {"box"})
        row["angles"] = sorted(set(row.get("angles", [])) | {"box"})
        row["hits"] = len(row["angles"])
        row.update({"box_stop": r["stop"], "box_lvl": r["lvl"], "box_target": r["target"], "box_grade": r["grade"],
                    "box_wks": r["wks"], "box_bounce_ago": r["bounce_ago"]})
        keys.append(r["t"])
    X["setups"] = [S for S in X["setups"] if S["key"] != "box"] + [
        {"key": BOX_SETUP[0], "name": BOX_SETUP[1], "desc": BOX_SETUP[2], "count": len(keys), "top": keys[:top]}]
