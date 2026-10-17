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

CFG = {"min_price": 5.0, "min_dvol": 10e6, "min_len": 10, "max_len": 130, "max_height": 0.25,
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


def find_box(h, l, c, v, e, adr):
    """Longest qualifying box ending at bar e (inclusive). adr in %. Returns a dict or None."""
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
        if H <= 0:
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
        if gain < P["pole_min"] or gain * 100 < P["pole_adr"] * adr or plo > B * (1 - P["pole_under"]):
            continue
        pv = v[s - P["pole_days"] + j:s]
        pv = pv[np.isfinite(pv)]
        bv = np.nanmean(v[s:e + 1])
        if len(pv) < 3 or not np.nanmean(pv) > 0:
            continue
        dry = bv / np.nanmean(pv)
        if not dry <= P["dry"]:
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
        out["now"] = {"thrust": bool(tw[-1]), "regime": reg,
                      "thrust_ago": None if last_thr is None else N - 1 - last_thr}
    except Exception:
        out["now"] = {"thrust": False, "regime": None}
    out["rt"] = retest_today(H, Lo, C, V, ADR, liq, rs, h52, dates, cols, info, names)
    out["rt_cfg"] = RT
    if evidence:
        try:
            ev = retest_events(H, Lo, C, V, ADR, liq, rs, dates, w["c"][config.BENCHMARK].to_numpy(), breadth)
            first = CFG["pole_days"] + CFG["min_len"] + 2
            out["rt_study"] = retest_study(ev, dates[first + (N - first) // 2].strftime("%Y-%m-%d"))
            out["rt_study"]["from"], out["rt_study"]["to"] = dates[first].strftime("%Y-%m-%d"), dates[-1].strftime("%Y-%m-%d")
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("retest study failed: %s", e)
            out["rt_study"] = None
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
# Breakout -> retest of the box top -> bounce
# ---------------------------------------------------------------------------
RT = {"ext": 1.0, "back": 1.0, "zone": 0.5, "come": 3.0, "expire": 25, "window": 35, "fresh": 2, "fail_frac": 0.5}


def retest_walk(h, l, c, b, bi, end, adrp):
    """Walk forward from breakout bar bi to `end` (inclusive). adrp = ADR % at the breakout.
    Returns dict: state at `end` (coming / support / bounced / failed / extended / expired / waiting),
    and the bars of the high, touch and bounce."""
    T, B = b["top"], b["bot"]
    a = T * adrp / 100                       # one ADR in dollars at the top
    mid = T - RT["fail_frac"] * (T - B)
    ph, phi, touch, tlow, bounce = h[bi], bi, None, None, None
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
                touch, tlow = i, l[i]
            elif i - bi > RT["expire"]:
                return {"state": "expired", "i": i, "phi": phi, "ph": ph, "touch": None, "bounce": None}
            if touch is None:
                state = "coming" if (ph >= T + RT["ext"] * a and c[i] <= ph - RT["back"] * a and c[i] <= T + RT["come"] * a) \
                    else ("extended" if ph >= T + RT["ext"] * a else "waiting")
                continue
            state = "support"
            continue
        if bounce is None:
            tlow = min(tlow, l[i])
            if c[i] > h[i - 1] and c[i] > T:
                bounce = i
                state = "bounced"
            else:
                state = "support"
                if i - touch > RT["expire"]:
                    return {"state": "expired", "i": i, "phi": phi, "ph": ph, "touch": touch, "bounce": None}
        else:
            return {"state": "after", "i": i, "phi": phi, "ph": ph, "touch": touch, "tlow": tlow, "bounce": bounce}
    return {"state": state, "i": end, "phi": phi, "ph": ph, "touch": touch, "tlow": tlow, "bounce": bounce}


def _breakouts(h, l, c, v, adr, lo, hi, prev10):
    """[(bi, box)] first closes above a qualifying box with bi in [lo, hi]."""
    out, last_b = [], -99
    for bi in range(max(lo, 1), hi + 1):
        if not (np.isfinite(c[bi]) and np.isfinite(prev10[bi]) and c[bi] > prev10[bi]) or bi - last_b < 10:
            continue
        b = find_box(h, l, c, v, bi - 1, adr[bi - 1])
        if b and c[bi] > b["top"] >= c[bi - 1]:
            out.append((bi, b))
            last_b = bi
    return out


def retest_today(H, Lo, C, V, ADR, liq, rs, h52, dates, cols, info, names):
    N = len(dates)
    last = N - 1
    prev10 = pd.DataFrame(H).rolling(10).max().shift(1).to_numpy()
    rows = []
    for j, t in enumerate(cols):
        if not liq[-1, j]:
            continue
        h, l, c, v, adr = H[:, j], Lo[:, j], C[:, j], V[:, j], ADR[:, j]
        bos = _breakouts(h, l, c, v, adr, last - RT["window"], last, prev10[:, j])
        best = None
        for bi, b in reversed(bos):                      # most recent breakout first
            w = retest_walk(h, l, c, b, bi, last, adr[bi])
            st = w["state"]
            if st == "bounced" and last - w["bounce"] >= RT["fresh"]:
                continue
            if st in ("coming", "support", "bounced"):
                best = (bi, b, w)
                break
        if not best:
            continue
        bi, b, w = best
        T, Bt = b["top"], b["bot"]
        a = T * adr[bi] / 100
        st = w["state"]
        tag = {"coming": "coming", "support": "inside" if c[last] < T else "support", "bounced": "bounced"}[st]
        tlow = None
        if w.get("touch") is not None:
            tlow = float(np.nanmin(l[w["touch"]:last + 1]))
        bvol = v[bi] / b["bvol"] if b["bvol"] else None
        pbv = np.nanmean(v[w["phi"] + 1:last + 1]) / v[bi] if last > w["phi"] and v[bi] else None
        s = info.get(t, {})
        rows.append({
            "t": t, "name": s.get("name") or names.get(t, ""), "price": _r(c[last]), "tag": tag,
            "win": b["win"], "len": b["len"], "wks": round(b["len"] / 5, 1), "start": dates[b["s"]].strftime("%Y-%m-%d"),
            "bo_date": dates[bi].strftime("%Y-%m-%d"), "bo_ago": last - bi, "bvx": _r(bvol, 2),
            "top": _r(T), "bot": _r(Bt), "mid": _r(T - RT["fail_frac"] * (T - Bt)), "height": _r(T / Bt - 1, 4),
            "ph": _r(w["ph"]), "ext_adr": _r((w["ph"] - T) / a, 1), "pull_adr": _r((w["ph"] - c[last]) / a, 1),
            "vs_top_adr": _r((c[last] - T) / a, 1), "vs_top": _r(c[last] / T - 1, 4),
            "touch_ago": None if w.get("touch") is None else last - w["touch"],
            "bounce_ago": None if w.get("bounce") is None else last - w["bounce"],
            "tlow": _r(tlow), "stop": _r(tlow if tlow is not None else T - RT["fail_frac"] * (T - Bt)),
            "target": _r(T + (T - Bt)), "pb_vol": _r(pbv, 2), "pole": _r(b["pole"], 4), "dry": _r(b["dry"], 2),
            "adr": _r(adr[last], 1), "rsr": s.get("rsr") if s.get("rsr") is not None else _r(rs[-1, j], 0),
            "off_hi": _r(c[last] / h52[-1, j] - 1, 4) if np.isfinite(h52[-1, j]) else None,
            "dvol": _r(np.nanmean(C[-20:, j] * V[-20:, j]) / 1e6, 0),
            "theme": (s.get("themes") or [None])[0], "sub": s.get("sub"),
            "grade": "A" if (s.get("rsr") if s.get("rsr") is not None else rs[-1, j]) >= 80 and b["win"] == "w2"
            else "B" if (s.get("rsr") if s.get("rsr") is not None else rs[-1, j]) >= 80 else "C",
            "px": [_r(x) for x in c[b["s"] - 10:]], "bs": 10, "be": 10 + b["len"] - 1, "bo": 10 + (bi - b["s"]),
        })
    order = {"bounced": 0, "support": 1, "inside": 2, "coming": 3}
    rows.sort(key=lambda r: (order[r["tag"]], r["bounce_ago"] or 0, -(r["rsr"] or 0)))
    return rows


def retest_events(H, Lo, C, V, ADR, liq, rs, dates, spy, breadth=None, hold=20):
    """Every bounce off a retested box top in history, with the market and stock conditions at the bounce."""
    N, M = C.shape
    first = CFG["pole_days"] + CFG["min_len"] + 2
    prev10 = pd.DataFrame(H).rolling(10).max().shift(1).to_numpy()
    h52 = pd.DataFrame(H).rolling(252, min_periods=60).max().to_numpy()
    spy = np.asarray(spy, dtype=float)
    s50 = pd.Series(spy).rolling(50).mean().to_numpy()
    s200 = pd.Series(spy).rolling(200, min_periods=120).mean().to_numpy()
    br = breadth.reindex(dates) if breadth is not None else None
    if br is not None:
        regime = np.where((br["ratio5"] >= 1.5) & (br["ratio10"] >= 1.5), "strong", np.where(br["ratio10"] < 1, "weak", "mixed"))
        from . import metrics as MT
        tw = MT.thrust_window(breadth, dates)
        t2108 = br["t2108"].to_numpy(dtype=float)
        dn10 = br["dn_share10"].to_numpy(dtype=float) if "dn_share10" in br else np.full(N, np.nan)
        nh10 = (br["nh10"] - br["nl10"]).to_numpy(dtype=float) if "nh10" in br else np.full(N, np.nan)
    else:
        regime, tw, t2108, dn10, nh10 = np.full(N, "mixed"), np.zeros(N, bool), *(np.full(N, np.nan),) * 3
    ev = []
    for j in range(M):
        h, l, c, v, adr = H[:, j], Lo[:, j], C[:, j], V[:, j], ADR[:, j]
        if not liq[:, j].any():
            continue
        for bi, b in _breakouts(h, l, c, v, adr, first, N - 3, prev10[:, j]):
            if not liq[bi, j]:
                continue
            w = retest_walk(h, l, c, b, bi, min(N - 1, bi + 2 * RT["expire"] + 5), adr[bi])
            if w.get("bounce") is None:
                ev.append({"kind": "nobounce", "i": bi, "touch": w.get("touch") is not None, "state": w["state"]})
                continue
            i = w["bounce"]
            T, Bt = b["top"], b["bot"]
            a = T * adr[bi] / 100
            tlow = float(np.nanmin(l[w["touch"]:i + 1]))
            entry = c[i]
            risk = max(entry - tlow, 0.3 * entry * adr[i] / 100)
            o = {"kind": "bounce", "i": i, "date": dates[i].strftime("%Y-%m-%d"), "j": j}
            for k in (5, 10, 20):
                if i + k < N and np.isfinite(c[i + k]):
                    o[f"d{k}"] = float(np.clip((c[i + k] / entry - 1) - (spy[i + k] / spy[i] - 1), -0.5, 0.5))
            # trade: stop under the retest low, else exit the close `hold` sessions later; R = result / risk
            if i + 1 < N:
                end = min(N - 1, i + hold)
                xi, xp = end, c[end]
                for k in range(i + 1, end + 1):
                    if l[k] <= tlow:
                        xi, xp = k, min(tlow, h[k]) if np.isfinite(h[k]) else tlow
                        break
                if end - i >= 5 or xi < end:
                    o["R"] = float(np.clip((xp - entry) / risk, -3, 10))
                    o["stopped"] = xi < end or (xi == end and l[end] <= tlow)
                    o["tgt"] = bool(np.nanmax(h[i + 1:xi + 1]) >= T + (T - Bt)) if xi > i else False   # before the stop
            o.update({
                "regime": str(regime[i]), "thrust": bool(tw[i]),
                "spy50": bool(spy[i] > s50[i]) if np.isfinite(s50[i]) else None,
                "spy200": bool(spy[i] > s200[i]) if np.isfinite(s200[i]) else None,
                "spy50up": bool(s50[i] > s50[i - 10]) if i >= 10 and np.isfinite(s50[i - 10]) else None,
                "t2108": t2108[i], "dn10": dn10[i], "nhnl": nh10[i],
                "rs": rs[i, j], "win": b["win"], "len": b["len"], "bvx": v[bi] / b["bvol"] if b["bvol"] else np.nan,
                "inside": bool(tlow < T), "depth": (T - tlow) / a, "ext": (w["ph"] - T) / a,
                "days_touch": w["touch"] - bi, "days_bounce": i - bi,
                "pbv": np.nanmean(v[w["phi"] + 1:w["touch"] + 1]) / v[bi] if w["touch"] > w["phi"] and v[bi] else np.nan,
                "adr": adr[i], "off": c[i] / h52[i, j] - 1 if np.isfinite(h52[i, j]) else np.nan,
                "dry": b["dry"], "height_adr": b["h_adr"],
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


def retest_study(ev, split):
    """Bounce entry results by condition, each with first/second-half checks."""
    B = [e for e in ev if e["kind"] == "bounce"]
    nb = [e for e in ev if e["kind"] == "nobounce"]

    def blk(sub):
        d = {"d10": _st([e.get("d10") for e in sub]), "d20": _st([e.get("d20") for e in sub]),
             "R": _st([e.get("R") for e in sub])}
        tg = [e["tgt"] for e in sub if "tgt" in e]
        sp = [e["stopped"] for e in sub if "stopped" in e]
        if tg:
            d["tgt"], d["stop"] = round(float(np.mean(tg)), 3), round(float(np.mean(sp)), 3)
        d["h1"] = _st([e.get("d10") for e in sub if e["date"] < split]).get("ret")
        d["h2"] = _st([e.get("d10") for e in sub if e["date"] >= split]).get("ret")
        d["h1R"] = _st([e.get("R") for e in sub if e["date"] < split]).get("ret")
        d["h2R"] = _st([e.get("R") for e in sub if e["date"] >= split]).get("ret")
        return d

    def f(k, op, x):
        return [e for e in B if e.get(k) is not None and not (isinstance(e.get(k), float) and np.isnan(e[k])) and op(e[k], x)]

    import operator as o
    th = [e for e in B if e["thrust"]]
    groups = [
        ("Best combinations (research Oct 16, 2026)", [
            ("After a thrust + RS 80+", [e for e in th if np.isfinite(e["rs"]) and e["rs"] >= 80]),
            ("After a thrust + RS 80+ + 2-4 week box", [e for e in th if np.isfinite(e["rs"]) and e["rs"] >= 80 and e["win"] == "w2"]),
            ("After a thrust + 2-4 week box", [e for e in th if e["win"] == "w2"]),
            ("No thrust in the last 25 sessions", [e for e in B if not e["thrust"]]),
            ("No thrust + RS 80+", [e for e in B if not e["thrust"] and np.isfinite(e["rs"]) and e["rs"] >= 80]),
            ("Strong breadth but no thrust", [e for e in B if e["regime"] == "strong" and not e["thrust"]])]),
        ("Market", [("Strong breadth", [e for e in B if e["regime"] == "strong"]),
                    ("Mixed breadth", [e for e in B if e["regime"] == "mixed"]),
                    ("Weak breadth", [e for e in B if e["regime"] == "weak"]),
                    ("Within 25 sessions of a breadth thrust", [e for e in B if e["thrust"]]),
                    ("SPY above its 50-day, 50-day rising", [e for e in B if e["spy50"] and e["spy50up"]]),
                    ("SPY below its 50-day", [e for e in B if e["spy50"] is False]),
                    ("SPY below its 200-day", [e for e in B if e["spy200"] is False]),
                    ("T2108 under 40 (washed out)", f("t2108", o.lt, 40)),
                    ("T2108 over 70 (stretched)", f("t2108", o.gt, 70)),
                    ("New highs beating new lows (10-day)", f("nhnl", o.gt, 0)),
                    ("New lows beating new highs", f("nhnl", o.le, 0)),
                    ("Money leaving (10-day share in falling stocks ≥ 52%)", f("dn10", o.ge, 52)),
                    ("Money coming in (≤ 45%)", f("dn10", o.le, 45))]),
        ("Stock", [("RS 80+", f("rs", o.ge, 80)), ("RS 90+", f("rs", o.ge, 90)), ("RS under 60", f("rs", o.lt, 60)),
                   ("Within 5% of 52-week high", f("off", o.ge, -0.05)), ("ADR 4%+", f("adr", o.ge, 4)), ("ADR under 2.5%", f("adr", o.lt, 2.5))]),
        ("Pattern", [*[(f"{n} box", [e for e in B if e["win"] == k]) for k, n, *_ in WINDOWS],
                     ("Breakout volume 1.3×+ box avg", f("bvx", o.ge, 1.3)), ("Breakout on light volume", f("bvx", o.lt, 1.3)),
                     ("Retest held above the top", [e for e in B if not e["inside"]]),
                     ("Retest dipped back inside the box", [e for e in B if e["inside"]]),
                     ("Fast retest (touch within 5 sessions)", f("days_touch", o.le, 5)),
                     ("Slow retest (6+ sessions)", f("days_touch", o.gt, 5)),
                     ("Quiet pullback (vol ≤ 0.6× breakout day)", f("pbv", o.le, 0.6)),
                     ("Heavy pullback (vol > 0.6×)", f("pbv", o.gt, 0.6)),
                     ("Big breakout leg (2+ ADR before pulling back)", f("ext", o.ge, 2))]),
    ]
    n_bo = len(B) + len(nb)
    return {"all": blk(B), "groups": [{"name": g, "rows": [{"name": n, **blk(s)} for n, s in rows]} for g, rows in groups],
            "funnel": {"breakouts": n_bo, "touched": len(B) + sum(e["touch"] for e in nb), "bounced": len(B),
                       "failed": sum(e["state"] == "failed" for e in nb)}, "split": split}
