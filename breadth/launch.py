"""Launch list (Adam, Oct 25 2026; card R-2026-10-25-what-made-them-go, layer `launch`, info only).

Stocks sitting where CDNA / DINO / NTRA sat before they went: out of a long base through the 50-week EMA, the 9 WEMA
over a rising 21, not yet extended. Each is scored 0-4 on the tells that separated the ones that went in the study:
  1. group  - its sub-theme is in the top third of sub-themes on 13-week return (the strongest tell, both halves)
  2. rs     - RS Rating 70+
  3. rsline - RS line (price / SPY) up 15%+ over 13 weeks
  4. gap    - a 6%+ gap-up day in the last 13 weeks (earnings / news)
Volume was tested and added nothing, so it is not scored. The group point is the gatekeeper: with it, 13-week returns beat
SPY at every score; without it even 3 other points lagged SPY (those names only "went" more because they swing harder).
Grades: A = group + 2-3 others, B = group + 0-1 others, C = no group point (or no sub-theme). Size A names smaller: they swing more.

Stages (Adam, Oct 25: "ACN / IT had already gone when they showed up; the buy was the flag under the 50"):
  curl  - the 9 WEMA has crossed over a rising 21 while price is still within 1.5 weekly ATRs under to 0.5 over the 50 WEMA
          (his yellow box: the flag before the break). Group point: 46% hit +50% vs 18% without, 13w vs SPY +5.4% vs -5.4%.
  early - 2-8 weekly closes over the 50 WEMA (the first test); later = longer over it (untested).
Names = curl + early stocks plus every Strength on Weakness row, all scored the same way. RS, RS line and gap points
mostly switch on AFTER the move starts; the group is the early clue. Each row also carries its distance over the 9 WEMA
in weekly ATRs (Grade A bought within 1 ATR of the 9 hit +50% 53-54% of the time vs 43% beyond 1.5 ATRs). The evidence is recomputed every build on the
fresh setup: entry next session's open, best high within 26 weeks, 13-week return vs SPY, lost the 50 WEMA within 13 weeks.
Never touches the picks."""
import numpy as np
import pandas as pd

CFG = {"min_price": 5.0, "min_dvol": 10e6, "run_lo": 2, "run_hi": 8, "base_wk": 40, "base_below": 20, "ext_atr": 3.0,
       "grp_top": 2 / 3, "grp_wk": 13, "grp_min": 3, "rs_min": 70, "rsl_wk": 13, "rsl_min": 0.15, "gap_days": 65, "gap_min": 0.06,
       "warm": 40, "hold": 26, "mid": 13, "went": 0.5, "gap_every": 26, "curl_lo": 1.5, "curl_hi": 0.5, "flag_wk": 4,
       "near9": 1.0, "far9": 1.5}
POINTS = [("group", "Group leading", "Its sub-theme is in the top third of sub-themes on 13-week return. The strongest tell in the study."),
          ("rs", "RS 70+", "RS Rating 70 or higher."),
          ("rsline", "RS line rising", "RS line (price ÷ SPY) up 15%+ over 13 weeks."),
          ("gap", "Gap day", "A 6%+ gap-up day in the last 13 weeks (earnings or news put it in play).")]


def _r(x, n=2):
    return None if x is None or not np.isfinite(x) else round(float(x), n)


def frames(w, cols, subthemes, bench="SPY"):
    """Weekly frames for every rule and point. All values known at each week's close."""
    from . import sow, strength
    dC, dO, dH, dL, dV = (w[k][cols] for k in ("c", "o", "h", "l", "v"))
    days = dC.index
    dvol = (dC * dV).rolling(20, min_periods=15).mean()
    raw = strength.rs_raw(dC)
    liqd = (dC >= CFG["min_price"]) & (dvol >= CFG["min_dvol"])
    rsd = (raw.where(liqd).rank(axis=1, pct=True) * 99).clip(1, 99)
    gapd = (dO / dC.shift() - 1).rolling(CFG["gap_days"], min_periods=20).max()
    W, nday = sow.weekly(w, cols)
    c, h, l = W["c"], W["h"], W["l"]
    wd = c.index
    ema = lambda x, n: x.ewm(span=n, adjust=False, min_periods=1).mean()
    e9, e21, e50 = ema(c, 9), ema(c, 21), ema(c, 50)
    pc = c.shift()
    tr = np.maximum(h - l, np.maximum((h - pc).abs(), (l - pc).abs()))
    atr = (tr / c).rolling(10, min_periods=6).mean()
    ab = (c > e50).astype(int)
    cs = ab.cumsum()
    run = cs - cs.where(ab == 0).ffill().fillna(0)
    below = (c < e50).astype(float).rolling(CFG["base_wk"], min_periods=30).sum()
    liq = (c >= CFG["min_price"]) & (dvol.reindex(wd)[cols] >= CFG["min_dvol"])
    zone = liq & (below >= CFG["base_below"]) & (e9 > e21) & (e21 > e21.shift(4)) & (c <= e50 * (1 + CFG["ext_atr"] * atr))
    fresh = zone & (run >= CFG["run_lo"]) & (run <= CFG["run_hi"])
    # the yellow box: 9 curled over a rising 21 while price still sits at / just under the 50 WEMA (before the breakout)
    curl = liq & (below >= CFG["base_below"]) & (e9 > e21) & (e21 > e21.shift(4)) & \
        (c >= e50 * (1 - CFG["curl_lo"] * atr)) & (c <= e50 * (1 + CFG["curl_hi"] * atr))
    flag = c > h.shift(1).rolling(CFG["flag_wk"], min_periods=3).max()     # closed above the last 4 weeks' high (the flag break)
    spy = w["c"][bench].groupby(days.to_period("W-FRI")).last()
    spy.index = wd
    rsl = c.div(spy, axis=0)
    rsl13 = rsl / rsl.shift(CFG["rsl_wk"]) - 1
    sub_of = dict(zip(subthemes["ticker"], subthemes["subtheme"])) if subthemes is not None and len(subthemes) else {}
    members = {}
    for t in cols:
        if t in sub_of:
            members.setdefault(sub_of[t], []).append(t)
    g = {k: (c[m] / c[m].shift(CFG["grp_wk"]) - 1).clip(-0.9, 3).mean(axis=1) for k, m in members.items() if len(m) >= CFG["grp_min"]}
    grank = pd.DataFrame(g).rank(axis=1, pct=True) if g else pd.DataFrame(index=wd)
    gr = pd.DataFrame({t: grank[sub_of[t]] for t in cols if sub_of.get(t) in grank.columns}, index=wd).reindex(columns=cols)
    rs_w = rsd.reindex(wd)
    gap_w = gapd.reindex(wd)
    pts = {"group": gr >= CFG["grp_top"], "rs": rs_w >= CFG["rs_min"], "rsline": rsl13 >= CFG["rsl_min"], "gap": gap_w >= CFG["gap_min"]}
    score = sum(p.astype(int) for p in pts.values())
    return {"W": W, "nday": nday, "wd": wd, "days": days, "e9": e9, "e21": e21, "e50": e50, "atr": atr, "run": run, "below": below,
            "zone": zone, "fresh": fresh, "curl": curl, "flag": flag, "rs": rs_w, "rsl13": rsl13, "grank": gr, "gap": gap_w, "pts": pts, "score": score,
            "sub_of": sub_of, "dO": dO, "dH": dH, "dC": dC, "dvol": dvol, "rsd": rsd}


def grade(group, score):
    return "A" if group and score >= 3 else "B" if group else "C"


def _sum(x):
    if not len(x):
        return {"n": 0}
    return {"n": int(len(x)), "went": _r(float(np.mean(x["maxg"] >= CFG["went"])), 3), "best": _r(float(np.median(x["maxg"])), 3),
            "x13": _r(float(np.nanmedian(x["x13"])), 3) if np.isfinite(x["x13"]).any() else None,
            "lost": _r(float(np.mean(x["lost"])), 3), "atr": _r(float(np.median(x["atr"])), 3)}


def evidence(F, w, bench="SPY", key="fresh"):
    """Every setup of one stage (first per stock per 26 weeks) with 26 weeks of future: outcomes by score and grade."""
    days, wd = F["days"], F["wd"]
    M = F[key].to_numpy().copy()
    M[:CFG["warm"]] = False
    O, H, C = F["dO"].to_numpy(), F["dH"].to_numpy(), F["dC"].to_numpy()
    WC, E50 = F["W"]["c"].to_numpy(), F["e50"].to_numpy()
    S, A = F["score"].to_numpy(), F["atr"].to_numpy()
    floor = CFG["curl_lo"] if key == "curl" else 0.0        # curl starts under the 50: failure = a close below the curl floor
    G = F["grank"].to_numpy()
    PG = F["pts"]["group"].to_numpy()
    spy = w["c"][bench].to_numpy()
    ent_i = days.searchsorted(wd, side="right")
    hd, md = CFG["hold"] * 5, CFG["mid"] * 5
    last = {}
    rows = []
    for i in range(len(wd)):
        a = ent_i[i]
        if a + hd > len(days):
            break
        for j in np.flatnonzero(M[i]):
            if j in last and i - last[j] < CFG["gap_every"]:
                continue
            last[j] = i
            e = O[a, j]
            if not np.isfinite(e) or e <= 0:
                continue
            mx = np.nanmax(H[a:a + hd, j]) / e - 1
            r13 = C[a + md, j] / e - 1 if a + md < len(days) else np.nan
            s13 = spy[a + md] / spy[a] - 1 if a + md < len(days) else np.nan
            lost = bool(np.any(WC[i + 1:i + 1 + CFG["mid"], j] < E50[i + 1:i + 1 + CFG["mid"], j] * (1 - floor * A[i, j])))
            rows.append((wd[i], S[i, j], np.isfinite(G[i, j]), mx, r13 - s13, lost, A[i, j], grade(bool(PG[i, j]), int(S[i, j]))))
    if not rows:
        return None
    X = pd.DataFrame(rows, columns=["date", "score", "grp", "maxg", "x13", "lost", "atr", "grade"])
    split = X["date"].sort_values().iloc[len(X) // 2]
    out = {"from": str(X["date"].min().date()), "to": str(X["date"].max().date()), "n": int(len(X)), "all": _sum(X),
           "by_score": {str(k): _sum(X[X["score"] == k]) for k in range(5)}, "grp_share": _r(float(X["grp"].mean()), 3),
           "by_grade": {k: _sum(X[X["grade"] == k]) for k in "ABC"},
           "halves": {h: {k: _sum(g[g["grade"] == k]) for k in "ABC"}
                      for h, g in (("h1", X[X["date"] < split]), ("h2", X[X["date"] >= split]))}}
    return out


def build(adjusted, universe, stocks=None, names=None, sow_payload=None, subthemes=None, evidence_on=True, ledger=False):
    from . import strength, config, store
    names = names or {}
    info = {r["t"]: r for r in (stocks or [])}
    w = strength.wide_all(adjusted)
    uni = set(universe)
    cols = [t for t in w["c"].columns if t in uni]
    if len(w["c"].index) < 250 or not cols or config.BENCHMARK not in w["c"]:
        return None
    if subthemes is None:
        subthemes = store.load_subthemes()
    F = frames(w, cols, subthemes, config.BENCHMARK)
    wi = len(F["wd"]) - 1
    di = len(F["days"]) - 1
    sow_rows = {r["t"]: r for r in ((sow_payload or {}).get("rows") or [])}
    W = F["W"]
    adr = ((w["h"][cols] / w["l"][cols]) - 1).rolling(20, min_periods=15).mean().iloc[-1] * 100
    gap_day = (F["dO"] / F["dC"].shift() - 1).iloc[-CFG["gap_days"]:]
    rows = []
    for j, t in enumerate(cols):
        fresh = bool(F["fresh"].iat[wi, j])
        curl = bool(F["curl"].iat[wi, j]) and not fresh
        s = sow_rows.get(t)
        if not fresh and not curl and not s:
            continue
        pts = {k: bool(F["pts"][k].iat[wi, j]) for k, _, _ in POINTS}
        gser = gap_day[t]
        gmax = gser.max()
        gdate = str(gser.idxmax().date()) if np.isfinite(gmax) else None
        c = W["c"].iat[wi, j]
        e50, e9, e21, atr = F["e50"].iat[wi, j], F["e9"].iat[wi, j], F["e21"].iat[wi, j], F["atr"].iat[wi, j]
        ir = info.get(t, {})
        sc = int(sum(pts.values()))
        run = int(F["run"].iat[wi, j])
        stage = "curl" if curl or run == 0 else "early" if run <= CFG["run_hi"] else "later"
        vs9 = (c / e9 - 1) / atr if atr else np.nan
        rows.append({"t": t, "grade": grade(pts["group"], sc), "stage": stage, "early": stage != "later", "curl": curl,
                     "flag": bool(F["flag"].iat[wi, j]), "vs9": _r(vs9, 2),
                     "loc": None if not np.isfinite(vs9) else "at9" if vs9 <= 0.5 else "near" if vs9 <= CFG["near9"] else "up" if vs9 <= CFG["far9"] else "far", "name": names.get(t, ir.get("name", "")), "sub": F["sub_of"].get(t), "theme": (ir.get("themes") or [None])[0],
                     "score": sc, "pts": pts, "fresh": fresh, "sow": s.get("state") if s else None,
                     "prime": bool(s.get("prime")) if s else False, "grank": _r(F["grank"].iat[wi, j], 3), "rs": _r(F["rs"].iat[wi, j], 0),
                     "rsl13": _r(F["rsl13"].iat[wi, j], 3), "gap": _r(gmax, 3), "gap_date": gdate if (gmax or 0) >= CFG["gap_min"] else None,
                     "run": int(F["run"].iat[wi, j]), "ext": _r((c / e50 - 1) / atr if atr else np.nan, 2), "atr": _r(atr * 100, 1),
                     "adr": _r(adr.get(t, np.nan), 1), "price": _r(c, 2), "e9": _r(e9, 2), "e21": _r(e21, 2), "e50": _r(e50, 2),
                     "vs50": _r(c / e50 - 1, 3), "dvol": _r(F["dvol"][t].iat[di] / 1e6, 0)})
    SO = {"curl": 0, "early": 1, "later": 2}
    rows.sort(key=lambda r: (r["grade"], SO[r["stage"]], (r["vs9"] if r["vs9"] is not None else 9) > CFG["near9"], -r["score"], -(r["grank"] or 0), -(r["rs"] or 0)))
    from . import sow
    done = bool(sow.complete_weeks(F["nday"], F["days"][-1])[-1])
    out = {"date": str(F["days"][-1].date()), "week": str(F["wd"][-1].date()), "week_done": done, "week_days": int(F["nday"].iloc[-1]),
           "cfg": CFG, "points": [{"key": k, "name": n, "desc": d} for k, n, d in POINTS], "rows": rows,
           "counts": {k: sum(1 for r in rows if r["grade"] == k) for k in "ABC"}}
    if evidence_on:
        out["evidence"] = evidence(F, w, config.BENCHMARK)
        out["evidence_curl"] = evidence(F, w, config.BENCHMARK, "curl")
        out["pick_bt"] = replay(F, w, config.BENCHMARK)
    # this week's picks (frozen into the ledger only once the week is complete)
    F["week_done"] = done
    df = ledger_load() if ledger else pd.DataFrame(columns=LCOLS)
    held = set(df.loc[df["status"].isin(["pending", "open"]), "t"]) - set(df.loc[df["week"] == out["week"], "t"])
    R = {r["t"]: r for r in rows}
    picks = []
    for p in select(F, wi, held):
        r = R.get(p["t"]) or {}
        st = "Curl, before the break" if p["stage"] == "curl" else "Just broke over the 50-week EMA"
        loc = {"at9": "at the 9-week EMA", "near": "near the 9-week EMA", "up": "1-1.5 ATRs over the 9-week EMA (wait for a nuzzle)",
               "far": "stretched over the 9-week EMA (wait for a nuzzle)"}.get(r.get("loc"), "")
        why = f"Grade {p['grade']}: {r.get('sub') or 'its group'} is top {max(1, round((1 - (r.get('grank') or 0)) * 100))}% of groups on 13 weeks" + \
              (f", plus {', '.join(nm for k, nm, _ in POINTS[1:] if (r.get('pts') or {}).get(k))}" if r.get("score", 0) > 1 else "") + \
              f". {st}{', flag break this week' if r.get('flag') else ''}; {loc}."
        plan = {"entry": "Tracked as bought at the next session's open. Better on the chart: " + ("the flag break (a weekly close over the last 4 weeks' high)"
                          if p["stage"] == "curl" and not r.get("flag") else "a nuzzle into the 9-week EMA" + (f" (${r.get('e9')})" if r.get("e9") else "")),
                "stop": (f"Weekly close under ≈ ${round(r['e50'] * stop_mult('curl', r['atr'] / 100), 2)} ({round((1 - stop_mult('curl', r['atr'] / 100)) * 100)}% under the 50-week EMA)"
                         if p["stage"] == "curl" and r.get("e50") and r.get("atr") else f"Weekly close under the 50-week EMA (${r.get('e50')})"),
                "hold": "13 weeks (the tracker scores it then); weekly swing ≈ " + (f"{r.get('atr')}%" if r.get("atr") else "–") + ", size accordingly"}
        picks.append({**{k: r.get(k) for k in ("t", "name", "sub", "grade", "score", "pts", "stage", "flag", "vs9", "loc", "rs", "rsl13", "grank",
                                               "gap", "gap_date", "price", "e9", "e21", "e50", "atr", "adr", "dvol", "sow", "prime")},
                      "why": why, "plan": plan})
    out["picks"] = picks
    out["pick_rule"] = (f"Each week: stocks in the curl or just broken out, with their group leading (grade A or B) and ${int(PICK['min_dvol'] / 1e6)}M+ a day; "
                        f"grade A first, then curl before breakout, then within {CFG['near9']} ATR of the 9-week EMA, then group rank and RS; one per sub-theme, "
                        f"weekly swing (ATR) {int(PICK['max_atr'] * 100)}% or less, skipping names already held; top {PICK['n']}. Logged at the week's close, bought the next session's open, "
                        f"sold 13 weeks later or on a weekly close through the failure line (under the 50-week EMA; curl picks min(1.5 weekly ATRs, {int(PICK['floor_cap'] * 100)}%) under it).")
    if ledger:
        try:
            if done:
                df = ledger_record(df, out["week"], picks)
            df = ledger_settle(df, F, w, config.BENCHMARK)
            df.to_csv(_lpath(), index=False)
        except Exception:
            import logging
            logging.getLogger("breadth").exception("launch ledger failed")
    out["tracker"] = ledger_summary(df)
    out["tracker"]["recorded"] = bool((df["week"] == out["week"]).any()) if len(df) else False
    return out


# ---------------------------------------------------------------------------------------------------------------------
# LAUNCH PICKS (Adam, Oct 25 2026: "switch the 2-3 recommendations to come from this, along with the performance tracking").
# Approved layer `launch` (config.APPROVED_LAYERS): passed the proof rule - Grade A minus C, 13-week return vs SPY by week:
# fresh breakouts t 3.1 (halves +15% / +19%), curl t 2.5 (+33% / +28%); pick-rule replay +9.2% vs SPY over 13 weeks
# (t 2.85, halves +14.9% / +4.4%, median +1.7%). Rule (same live and in the replay):
#   candidates = curl or fresh-breakout stocks, group point on (grade A or B), $20M+/day;
#   rank: grade A first -> curl before early -> within 1 ATR of the 9 WEMA -> group rank -> RS;
#   one per sub-theme, skip names still held (picked in the last 13 weeks); top 3 a week.
# Ledger data/launch_ledger.csv: picks freeze at the week's close (only complete weeks are recorded), entry = the next
# session's open, exit = the close 13 weeks (65 sessions) after entry or a weekly close through the failure line
# (under the 50 WEMA; for curl picks 1.5 weekly ATRs under it). Best high tracked for 26 weeks (hit +50%).
PICK = {"n": 3, "min_dvol": 20e6, "hold_wk": 13, "hold_days": 65, "best_days": 130, "floor_cap": 0.15, "max_atr": 0.15, "max_vs9": None, "one_per_sub": True}
LCOLS = ["week", "rank", "t", "grade", "stage", "sub", "name", "close", "e50", "atr", "vs9", "floor", "status", "entry_date", "entry",
         "spy_entry", "exit_date", "exit", "ret", "spy_ret", "xspy", "best", "last_date", "last", "why"]


def stop_mult(stage, atr):
    """Failure line as a multiple of the 50 WEMA: under it (breakouts), or min(1.5 weekly ATRs, 15%) under it (curl)."""
    if stage != "curl":
        return 1.0
    return 1 - min(CFG["curl_lo"] * (atr if atr is not None and np.isfinite(atr) else 0), PICK["floor_cap"])


def _rank_key(g, curl, vs9, grank, rs):
    return (g, 0 if curl else 1, 0 if (vs9 is not None and np.isfinite(vs9) and vs9 <= CFG["near9"]) else 1,
            -(grank if grank is not None and np.isfinite(grank) else 0), -(rs if rs is not None and np.isfinite(rs) else 0))


def select(F, i, held=(), n=None):
    """Top picks for week i (indices into F's columns), using only data known at that week's close."""
    n = n or PICK["n"]
    cols = list(F["W"]["c"].columns)
    c, e9, atr = F["W"]["c"].iloc[i], F["e9"].iloc[i], F["atr"].iloc[i]
    dv = F["dvol"].reindex(F["wd"]).iloc[i]
    grp, sc, gr, rs = F["pts"]["group"].iloc[i], F["score"].iloc[i], F["grank"].iloc[i], F["rs"].iloc[i]
    cu, fr = F["curl"].iloc[i], F["fresh"].iloc[i]
    held = set(held)
    cand = []
    for j, t in enumerate(cols):
        if not (bool(cu.iat[j]) or bool(fr.iat[j])) or not bool(grp.iat[j]) or t in held:
            continue
        if not (dv.iat[j] >= PICK["min_dvol"]):
            continue
        if PICK["max_atr"] and not (atr.iat[j] <= PICK["max_atr"]):
            continue
        g = grade(True, int(sc.iat[j]))
        vs9 = (c.iat[j] / e9.iat[j] - 1) / atr.iat[j] if atr.iat[j] else np.nan
        if PICK["max_vs9"] is not None and not (vs9 <= PICK["max_vs9"]):
            continue
        curl = bool(cu.iat[j]) and not bool(fr.iat[j])
        cand.append((_rank_key(g, curl, vs9, gr.iat[j], rs.iat[j]), j, g, curl, vs9))
    cand.sort(key=lambda x: x[0])
    out, subs = [], set()
    for _, j, g, curl, vs9 in cand:
        s = F["sub_of"].get(cols[j])
        if s in subs and PICK["one_per_sub"]:
            continue
        subs.add(s)
        out.append({"j": j, "t": cols[j], "grade": g, "stage": "curl" if curl else "early", "vs9": vs9})
        if len(out) == n:
            break
    return out


def replay(F, w, bench="SPY"):
    """The pick rule run on every past complete week; 13-week result vs SPY and vs the average liquid stock."""
    days, wd = F["days"], F["wd"]
    O, H, C = F["dO"].to_numpy(), F["dH"].to_numpy(), F["dC"].to_numpy()
    WC, E50, A = F["W"]["c"].to_numpy(), F["e50"].to_numpy(), F["atr"].to_numpy()
    liq = (F["W"]["c"] >= CFG["min_price"]) & (F["dvol"].reindex(wd) >= CFG["min_dvol"])
    L = liq.to_numpy()
    spy = w["c"][bench].to_numpy()
    ent = days.searchsorted(wd, side="right")
    hd, bd = PICK["hold_days"], PICK["best_days"]
    held, rows = {}, []
    cols = list(F["W"]["c"].columns)
    for i in range(CFG["warm"], len(wd)):
        a = ent[i]
        if a + hd > len(days):
            break
        hold = {cols[j] for j, k in held.items() if k > i - PICK["hold_wk"]}
        got = select(F, i, hold)
        m = L[i] & np.isfinite(C[a + hd - 1]) & np.isfinite(O[a])
        base = float(np.mean(np.clip(C[a + hd - 1, m] / O[a, m] - 1, -0.95, 5))) if m.any() else np.nan
        s13 = spy[a + hd - 1] / spy[a] - 1
        for p in got:
            j = p["j"]
            held[j] = i
            e = O[a, j]
            if not np.isfinite(e) or e <= 0:
                continue
            sm = stop_mult(p["stage"], A[i, j])
            xi, stop = a + hd - 1, False                         # same exits as the live tracker: 13 weeks, or a weekly close through the line
            for k in range(i + 1, min(i + 1 + PICK["hold_wk"], len(wd))):
                if WC[k, j] < E50[k, j] * sm:
                    xi, stop = min(days.searchsorted(wd[k]), a + hd - 1), True
                    break
            r = C[xi, j] / e - 1
            sx = spy[xi] / spy[a] - 1
            mb = L[i] & np.isfinite(C[xi]) & np.isfinite(O[a])
            bx = float(np.mean(np.clip(C[xi, mb] / O[a, mb] - 1, -0.95, 5))) if mb.any() else base
            rows.append((wd[i], p["t"], p["grade"], p["stage"], r, r - sx, r - bx, np.nanmax(H[a:min(a + bd, len(days)), j]) / e - 1,
                         a + bd <= len(days), stop, A[i, j]))
    if not rows:
        return None
    X = pd.DataFrame(rows, columns=["date", "t", "grade", "stage", "r", "xspy", "xbase", "best", "full", "stop", "atr"])
    wk = X.groupby("date").agg(xspy=("xspy", "mean"), xbase=("xbase", "mean"))
    split = wk.index[len(wk) // 2]
    tt = lambda s: _r(float(s.mean() / (s.std(ddof=1) / np.sqrt(len(s)))), 2) if len(s) > 2 and s.std(ddof=1) > 0 else None
    full = X[X["full"]]
    return {"from": str(X["date"].min().date()), "to": str(X["date"].max().date()), "n": int(len(X)), "weeks": int(len(wk)),
            "ret": _r(float(X["r"].mean()), 3), "ret_med": _r(float(X["r"].median()), 3), "xspy": _r(float(X["xspy"].mean()), 3),
            "xspy_med": _r(float(X["xspy"].median()), 3), "xbase": _r(float(X["xbase"].mean()), 3), "t": tt(wk["xspy"]), "t_base": tt(wk["xbase"]),
            "h1": _r(float(wk[wk.index < split]["xspy"].mean()), 3), "h2": _r(float(wk[wk.index >= split]["xspy"].mean()), 3),
            "beat": _r(float((X["xspy"] > 0).mean()), 3), "hit50": _r(float((full["best"] >= CFG["went"]).mean()), 3) if len(full) else None,
            "stop": _r(float(X["stop"].mean()), 3), "worst": _r(float(X["r"].min()), 3), "best": _r(float(X["r"].max()), 3)}


def _lpath():
    from . import config
    return config.DATA_DIR / "launch_ledger.csv"


def ledger_load():
    p = _lpath()
    if not p.exists():
        return pd.DataFrame(columns=LCOLS)
    df = pd.read_csv(p, dtype={"week": str, "entry_date": str, "exit_date": str, "last_date": str, "status": str, "t": str})
    for k in LCOLS:
        if k not in df.columns:
            df[k] = np.nan
    return df[LCOLS]


def ledger_record(df, week, picks):
    """Freeze a complete week's picks (never rewrites a week already recorded)."""
    if not picks or (df["week"] == week).any():
        return df
    rows = [{"week": week, "rank": k + 1, "t": p["t"], "grade": p["grade"], "stage": p["stage"], "sub": p.get("sub"), "name": p.get("name"),
             "close": p.get("price"), "e50": p.get("e50"), "atr": p.get("atr"), "vs9": p.get("vs9"),
             "floor": round(1 - stop_mult(p["stage"], (p.get("atr") or 0) / 100), 4), "status": "pending", "why": p.get("why")} for k, p in enumerate(picks)]
    return pd.concat([df, pd.DataFrame(rows, columns=LCOLS)], ignore_index=True)


def ledger_settle(df, F, w, bench="SPY"):
    """Fill entries, track open picks, close them at 13 weeks or on a weekly close through the failure line."""
    if not len(df):
        return df
    days, wd = F["days"], F["wd"]
    dO, dH, dC = w["o"], w["h"], w["c"]
    spy_o, spy_c = dO[bench], dC[bench]
    df = df.copy()
    for k, r in df.iterrows():
        if r["status"] in ("done", "stopped") or r["t"] not in dC.columns:
            continue
        wk = pd.Timestamp(r["week"])
        a = days.searchsorted(wk, side="right")
        if a >= len(days):
            continue                                            # entry session hasn't traded yet
        t = r["t"]
        e = float(dO[t].iat[a]) if np.isfinite(dO[t].iat[a]) else float(dC[t].iat[a])
        df.at[k, "entry_date"], df.at[k, "entry"], df.at[k, "spy_entry"] = str(days[a].date()), round(e, 4), round(float(spy_o.iat[a]), 4)
        end = min(a + PICK["hold_days"] - 1, len(days) - 1)
        status, xi = "open", end
        if t in F["W"]["c"].columns:                            # weekly close through the failure line (complete weeks after the pick week)
            wi0 = wd.searchsorted(wk, side="right")
            sm = stop_mult(r["stage"], float(r["atr"]) / 100 if np.isfinite(r["atr"]) else 0.0)
            for wi in range(wi0, len(wd)):
                if wd[wi] > days[end] or (wi == len(wd) - 1 and not F.get("week_done", True)):
                    break
                if F["W"]["c"][t].iat[wi] < F["e50"][t].iat[wi] * sm:
                    status, xi = "stopped", days.searchsorted(wd[wi])
                    break
        if status == "open" and a + PICK["hold_days"] - 1 <= len(days) - 1:
            status = "done"
        px = float(dC[t].iat[xi])
        df.at[k, "status"] = status
        df.at[k, "last_date"], df.at[k, "last"] = str(days[xi].date()), round(px, 4)
        df.at[k, "ret"] = round(px / e - 1, 4)
        df.at[k, "spy_ret"] = round(float(spy_c.iat[xi]) / float(spy_o.iat[a]) - 1, 4)
        df.at[k, "xspy"] = round(df.at[k, "ret"] - df.at[k, "spy_ret"], 4)
        df.at[k, "best"] = round(float(np.nanmax(dH[t].iloc[a:min(a + PICK["best_days"], len(days))])) / e - 1, 4)
        if status in ("done", "stopped"):
            df.at[k, "exit_date"], df.at[k, "exit"] = str(days[xi].date()), round(px, 4)
    return df


def ledger_summary(df):
    if not len(df):
        return {"n": 0, "rows": []}
    d = df.copy()
    closed = d[d["status"].isin(["done", "stopped"])]
    live = d[d["status"].isin(["open", "done", "stopped"])]
    f = lambda s: _r(float(s.mean()), 4) if len(s) else None
    rows = []
    for _, r in d.sort_values(["week", "rank"], ascending=[False, True]).head(80).iterrows():
        rows.append({k: (None if (isinstance(r[k], float) and not np.isfinite(r[k])) else r[k]) for k in LCOLS if k != "why"})
    return {"n": int(len(d)), "open": int((d["status"] == "open").sum()), "pending": int((d["status"] == "pending").sum()),
            "closed": int(len(closed)), "avg": f(closed["ret"]), "xspy": f(closed["xspy"]),
            "beat": _r(float((closed["xspy"] > 0).mean()), 3) if len(closed) else None,
            "stopped": int((closed["status"] == "stopped").sum()), "hit50": int((live["best"] >= CFG["went"]).sum()),
            "live_avg": f(live["ret"]), "live_xspy": f(live["xspy"]), "rows": rows}
