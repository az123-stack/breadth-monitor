"""Theme rotation engine, following the formulas from the user's
"Trading Dashboard v12" Google Sheet, computed from stored daily bars.

Per ticker: Today/3D/5D/15D/20D/30D returns, RS (~3-month % change),
5D Score, LT Score, distance from 8/21/50 EMAs, setup score (/10).
Per theme: averages over its member stocks, score /8 (6 signals + ST and LT
breadth points), class, rotation stage, breadth labels, vs-SPY, rank history.
Market pulse: long and short scores (/10) from the theme table.
"""
import numpy as np
import pandas as pd

from . import config

RS_DAYS = 63           # ~90 calendar days, as in the sheet's RS formula
# Return horizons in trading days. Short ones feed the scores; long ones are
# shown for context (they fill in once enough history is stored).
HORIZONS = {"today": 1, "d3": 3, "d5": 5, "d15": 15, "d20": 20, "d30": 30, "d60": 60, "d90": 90, "d180": 180}
SHOW = ["today", "d5", "d15", "d30", "d60", "d90", "d180"]
HISTORY_DAYS = 30      # days of theme scores/ranks kept for movement + trails


# ---------------------------------------------------------------------------
# Per-ticker metrics (wide matrices: rows = dates, cols = tickers)
# ---------------------------------------------------------------------------
def ticker_frames(adjusted, tickers):
    b = adjusted[adjusted["ticker"].isin(tickers)]
    close = b.pivot(index="date", columns="ticker", values="c").sort_index().astype("float64")
    close = close.ffill(limit=3)  # bridge the odd missing print
    r = lambda n: close / close.shift(n) - 1
    f = {"close": close, "rs": (close / close.shift(RS_DAYS) - 1) * 100}
    for k, n in HORIZONS.items():
        f[k] = r(n)
    # Sheet: 5D Score = (Today*2 + 1D*1 + 3D*1 + 5D*2)/6 ; 1D == Today here.
    f["st"] = (f["today"] * 3 + f["d3"] + f["d5"] * 2) / 6
    # Sheet: LT Score = (1D + 3D + 5D*2 + 15D*2 + 20D*2 + 30D*3)/11
    f["lt"] = (f["today"] + f["d3"] + f["d5"] * 2 + f["d15"] * 2 + f["d20"] * 2 + f["d30"] * 3) / 11
    for n in (8, 21, 50):
        ema = close.ewm(span=n, adjust=False, min_periods=n).mean()
        f[f"ema{n}"] = ema
        f[f"e{n}"] = close / ema - 1
    return f


def setup_score(theme_score, s):
    """Sheet's Setup Score (/10). `s` is a dict/Series of one ticker's metrics."""
    def ok(v):
        return v is not None and not pd.isna(v)
    pts = 0
    pts += 2 if theme_score >= 7 else 1 if theme_score >= 4 else 0
    if ok(s["d15"]) and ok(s["d30"]) and s["d15"] > 0 and s["d30"] > 0:
        pts += 2 if (ok(s["rs"]) and s["rs"] > 0 and ok(s["lt"]) and s["lt"] > 0.02) else 1
    near = lambda v: ok(v) and -0.03 <= v <= 0.01
    if near(s["e8"]) or near(s["e21"]):
        pts += 2
    if ok(s["today"]) and s["today"] > 0:
        pts += 1
    if ok(s["d5"]) and ok(s["d15"]) and ok(s["d30"]) and s["d5"] < 0.02 and s["d15"] > 0.05 and s["d30"] > 0.05:
        pts += 1
    if ok(s["rs"]) and s["rs"] > 0:
        pts += 1
    if (ok(s["d5"]) and ok(s["today"]) and abs(s["d5"]) < 0.02 and abs(s["today"]) < 0.03
            and s["d15"] > 0.05 and s["d30"] > 0.05):
        pts += 1  # coiling
    return pts


def tier(pts):
    return "A" if pts >= 8 else "B" if pts >= 5 else "C"


# ---------------------------------------------------------------------------
# Theme table for one date
# ---------------------------------------------------------------------------
# Rotation stage (rewritten Oct 30, 2026; Adam: "energy/oil was showing Early but it's been climbing all year"). The sheet's
# version only looked at today/5/15/30 days, so any up day in a year-long leader read "Early". Now the stage is judged by how
# long and how far the group has run (90 and 180 days) and whether its 5/15-day momentum still holds; today's move is ignored.
# Descriptive label only (feeds the Market pulse counts); not a backtested layer.
ROT_RULES = {"est_d90": 0.10, "est_d180": 0.20, "late_d90": 0.30, "late_d180": 0.40, "early_d30": 0.05, "mid_d30": 0.03}


def rotation(today, d5, d15, d30, d90=0.0, d180=0.0):
    R = ROT_RULES
    established = d90 >= R["est_d90"] or d180 >= R["est_d180"]       # it has already been running for months
    if established and ((d5 < 0 and d15 < 0) or d30 < 0):
        return "Late / Cooling"                                         # an old run losing momentum
    if not established and d30 > R["early_d30"] and d15 > 0:
        return "Early Rotation"                                         # a young move out of a quiet or falling stretch
    if established and (d90 >= R["late_d90"] or d180 >= R["late_d180"]) and d30 > 0:
        return "Late / Extended"                                        # still rising, but it has run a long way already
    if established and d30 > R["mid_d30"]:
        return "Mid Rotation"
    return "Neutral"


def breadth_label(x):
    return "Wide" if x >= 0.7 else "Moderate" if x >= 0.4 else "Narrow"


def theme_table(f, i, members):
    """Scores for every theme at row index i of the frames."""
    rows = []
    for theme, tick in members.items():
        tick = [t for t in tick if t in f["close"].columns]
        if not tick:
            continue
        v = {k: f[k].iloc[i][tick] for k in SHOW + ["rs", "lt"]}
        valid = v["today"].notna()
        if not valid.any():
            continue
        avg = {k: float(v[k][valid].mean()) if v[k][valid].notna().any() else np.nan for k in v}
        n = int(valid.sum())
        st_b = float(((v["today"] > 0) & (v["d5"] > 0))[valid].sum() / n)
        lt_b = float(((v["d15"] > 0) & (v["d30"] > 0))[valid].sum() / n)
        sig = sum(int(avg[k] > 0) for k in ("today", "d5", "d15", "d30", "rs", "lt") if not pd.isna(avg[k]))
        score = sig + int(st_b >= 0.5) + int(lt_b >= 0.6)
        rows.append({
            "theme": theme, "n": n, "score": score,
            "class": "STRONG" if score >= 7 else "WATCHLIST" if score >= 4 else "WEAK",
            "rotation": rotation(*(0 if pd.isna(avg[k]) else avg[k] for k in ("today", "d5", "d15", "d30", "d90", "d180"))),
            **{k: avg[k] for k in SHOW}, "rs": avg["rs"], "lt": avg["lt"], "st_b": st_b, "lt_b": lt_b,
            "st_label": breadth_label(st_b), "lt_label": breadth_label(lt_b),
        })
    t = pd.DataFrame(rows)
    if t.empty:
        return t
    t = t.sort_values(["score", "rs"], ascending=[False, False]).reset_index(drop=True)
    t["rank"] = np.arange(1, len(t) + 1)
    return t


# ---------------------------------------------------------------------------
# Market pulse (sheet's Market Pulse long/short scores)
# ---------------------------------------------------------------------------
def pulse(t):
    N = max(len(t), 1)
    strong = int((t["score"] >= 7).sum()); weak = int((t["score"] <= 2).sum())
    green = float((t["today"] > 0).sum() / N); red = float((t["today"] < 0).sum() / N)
    mid = int(t["rotation"].eq("Mid Rotation").sum()); cool = int(t["rotation"].eq("Late / Cooling").sum())
    st_wide = float(t["st_label"].eq("Wide").sum() / N); st_narrow = float(t["st_label"].eq("Narrow").sum() / N)
    lt_wide = float(t["lt_label"].eq("Wide").sum() / N); neg_rs = int((t["rs"] < 0).sum())
    tiers = lambda x, a, b, c: 3 if x >= a else 2 if x >= b else 1 if x >= c else 0
    two = lambda x, a, b: 2 if x >= a else 1 if x >= b else 0

    long_c = [
        ("Strong themes (7+/8)", f"{strong} of {N}", tiers(strong / N, .25, .15, .08), 3,
         "Wide leadership — high conviction to trade long" if strong / N >= .25 else
         "Some leaders — be selective" if strong / N >= .08 else "Few leaders — sit on hands"),
        ("Themes green today", f"{green:.0%} of themes", two(green, .55, .35), 2,
         "Majority green — good day to trade long" if green >= .55 else
         "Mixed — selective only" if green >= .35 else "Mostly red — avoid longs"),
        ("Mid-rotation themes", f"{mid} themes", 2 if mid >= 5 else 1 if mid >= 3 else 0, 2,
         "Strong rotation — multiple themes accelerating" if mid >= 5 else
         "Rotation present — follow the leaders" if mid >= 3 else "Little rotation — wait"),
        ("Short-term breadth wide", f"{st_wide:.0%} of themes", two(st_wide, .35, .15), 2,
         "Broad participation — confirms the move" if st_wide >= .35 else "Narrow breadth — thin leadership"),
        ("Long-term breadth wide", f"{lt_wide:.0%} of themes", 1 if lt_wide >= .4 else 0, 1,
         "Strong structural base — trend has legs" if lt_wide >= .4 else "LT breadth thin — reversal risk"),
    ]
    short_c = [
        ("Weak themes (0–2/8)", f"{weak} of {N}", tiers(weak / N, .25, .15, .08), 3,
         "Many weak themes — strong short environment" if weak / N >= .25 else
         "Some weakness — selective shorts" if weak / N >= .08 else "Few weak themes — not ideal short day"),
        ("Themes red today", f"{red:.0%} of themes", two(red, .55, .35), 2,
         "Majority red — good day to work the short side" if red >= .55 else
         "Mixed — selective shorts only" if red >= .35 else "Mostly green — poor short day"),
        ("Late / cooling themes", f"{cool} themes", 2 if cool >= 5 else 1 if cool >= 3 else 0, 2,
         "Multiple themes rolling over — short side has fuel" if cool >= 5 else
         "Some themes cooling — watch for failed bounces" if cool >= 3 else "Little deterioration — shorts premature"),
        ("Short-term breadth narrow", f"{st_narrow:.0%} of themes", two(st_narrow, .35, .15), 2,
         "Breadth collapsing — distribution underway" if st_narrow >= .35 else "Breadth still holding — shorts need patience"),
        ("Themes with negative RS", f"{neg_rs} of {N}", 1 if neg_rs / N >= .4 else 0, 1,
         "Relative strength deteriorating broadly — structural shorts" if neg_rs / N >= .4 else
         "RS mostly positive still — be patient with shorts"),
    ]
    L = sum(c[2] for c in long_c); S = sum(c[2] for c in short_c)
    long_label = ("GO — strong broad setup" if L >= 8 else "LEAN LONG — stay selective" if L >= 6 else
                  "SELECTIVE — A-tier setups only" if L >= 4 else "CAUTION — weak breadth, reduce size" if L >= 2 else
                  "SIT OUT — no edge today")
    short_label = ("SHORT SIDE LIVE — strong short setup" if S >= 8 else "LEAN SHORT — selective shorts only" if S >= 6 else
                   "SOME SHORT SETUPS — weak themes present" if S >= 4 else "MOSTLY NEUTRAL — monitor for deterioration" if S >= 2 else
                   "NO SHORT EDGE — market too strong to short")
    comp = lambda cs: [{"name": a, "value": b, "pts": c, "max": d, "note": e} for a, b, c, d, e in cs]
    return {"long": L, "short": S, "long_label": long_label, "short_label": short_label,
            "long_parts": comp(long_c), "short_parts": comp(short_c)}


# ---------------------------------------------------------------------------
# Build everything for the dashboard
# ---------------------------------------------------------------------------
def _r(v, nd=4):
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return None
    return round(float(v), nd)


def etfs_flat(etfs):
    return {e for lst in etfs.values() for e in lst}


def _tv_map(tv, tickers):
    tv = tv or {}
    return {t: tv[t] for t in dict.fromkeys(tickers) if t in tv}


def build(adjusted, themes_df, universe, names=None, missing=(), subthemes_df=None, tv=None):
    if themes_df is None or themes_df.empty or adjusted.empty:
        return None
    names = names or {}
    members, etfs = {}, {}
    for theme, g in themes_df.groupby("theme", sort=False):
        m = list(dict.fromkeys(g.loc[g["role"] == "member", "ticker"]))
        e = list(dict.fromkeys(g.loc[g["role"] == "etf", "ticker"]))
        members[theme] = m or e          # ETF-only themes (e.g. Gold) score their ETFs
        etfs[theme] = e
    all_t = set(themes_df["ticker"]) | {config.BENCHMARK}
    if subthemes_df is not None and not subthemes_df.empty:
        all_t |= set(subthemes_df["ticker"])
    f = ticker_frames(adjusted, all_t)
    dates = f["close"].index
    if len(dates) < RS_DAYS + 2:
        return None
    last = len(dates) - 1
    first_hist = max(RS_DAYS, last - HISTORY_DAYS + 1)

    bench = config.BENCHMARK if config.BENCHMARK in f["close"].columns else None
    bret = {k: (float(f[k].iloc[last][bench]) if bench and not pd.isna(f[k].iloc[last][bench]) else None)
            for k in SHOW}

    def ranked(members_map, etfs_map, extra=None):
        """Score + rank every group for each recent day; rows for the latest day."""
        tables = {}
        for i in range(first_hist, last + 1):
            t = theme_table(f, i, members_map)
            if not t.empty:
                tables[i] = t
        hist_idx = sorted(tables)
        now = tables[last]
        rank_at = {i: dict(zip(tables[i]["theme"], tables[i]["rank"])) for i in hist_idx}
        score_hist = {i: dict(zip(tables[i]["theme"], tables[i]["score"])) for i in hist_idx}
        ago = lambda n: rank_at.get(last - n, {})
        r1, r3, r4, r5, r10 = ago(1), ago(3), ago(4), ago(5), ago(10)
        rows = []
        for row in now.to_dict("records"):
            th = row["theme"]
            etf = next((e for e in etfs_map.get(th, []) if e in f["close"].columns
                        and not pd.isna(f["d5"].iloc[last].get(e))), None)
            delta = lambda prev: int(prev[th] - row["rank"]) if prev.get(th) is not None else None
            rows.append({
                "theme": th, "rank": int(row["rank"]), "score": int(row["score"]), "class": row["class"],
                "rotation": row["rotation"], "n": int(row["n"]),
                **{k: _r(row[k]) for k in SHOW},
                "rs": _r(row["rs"], 2), "lt": _r(row["lt"]), "st_b": _r(row["st_b"], 3), "lt_b": _r(row["lt_b"], 3),
                "st_label": row["st_label"], "lt_label": row["lt_label"],
                **{f"vs_{k}": (_r(row[k] - bret[k]) if bret[k] is not None and not pd.isna(row[k]) else None)
                   for k in ("d5", "d30", "d90")},
                "mv1": delta(r1), "mv3": delta(r3), "mv5": delta(r5), "mv10": delta(r10), "r_m4": r4.get(th),
                "etf": etf, **{f"etf_{k}": (_r(f[k].iloc[last][etf]) if etf else None) for k in ("d5", "d30")},
                "trail": [None if score_hist[i].get(th) is None else int(score_hist[i][th]) for i in hist_idx],
                "members": [t for t in members_map[th] if t in f["close"].columns],
                **(extra(th) if extra else {}),
            })
        return rows, now, tables, hist_idx

    theme_rows, now, tables, hist_idx = ranked(members, etfs)
    score_of = dict(zip(now["theme"], now["score"]))

    # sub-themes: one peer group per stock (data/subthemes.csv)
    sub_rows, sub_of, group_of = [], {}, {}
    if subthemes_df is not None and not subthemes_df.empty:
        sub_members = {}
        for r in subthemes_df.itertuples():
            sub_members.setdefault(r.subtheme, []).append(r.ticker)
            sub_of[r.ticker] = r.subtheme
            group_of[r.subtheme] = r.group
        # a sub-theme's "themes" = the themes its stocks belong to
        th_of = {}
        for th, tick in members.items():
            for t in tick:
                th_of.setdefault(t, set()).add(th)
        extra = lambda st: {"group": group_of.get(st, ""),
                            "parents": sorted({x for t in sub_members[st] for x in th_of.get(t, ())})}
        sub_rows, _, _, _ = ranked(sub_members, {}, extra)
    sub_score = {r["theme"]: r["score"] for r in sub_rows}

    # stocks: unique members, scored with their strongest theme
    stock_themes = {}
    for th, tick in members.items():
        for t in tick:
            stock_themes.setdefault(t, []).append(th)
    for t in sub_of:            # sub-theme-only stocks (e.g. WMT, COST, AAPL): listed with no theme
        stock_themes.setdefault(t, [])
    cols = f["close"].columns
    def rs_rank(i):
        s = f["rs"].iloc[i][[t for t in stock_themes if t in cols]].dropna().sort_values(ascending=False)
        return {t: k + 1 for k, t in enumerate(s.index)}
    rk_now, rk5, rk10, rk4 = rs_rank(last), rs_rank(last - 5), rs_rank(last - 10), rs_rank(last - 4)
    stocks = []
    for t, ths in stock_themes.items():
        if t not in cols or pd.isna(f["today"].iloc[last][t]):
            continue
        s = {k: f[k].iloc[last][t] for k in list(HORIZONS) + ["rs", "st", "lt", "e8", "e21", "e50"]}
        ths_sorted = sorted(ths, key=lambda x: -score_of.get(x, -1))
        best = score_of.get(ths_sorted[0], 0) if ths_sorted else 0
        pts = setup_score(best, s)
        sub = sub_of.get(t)
        stocks.append({
            "t": t, "name": names.get(t, ""), "themes": ths_sorted, "tscore": int(best),
            "sub": sub, "group": group_of.get(sub, "") if sub else "", "sscore": sub_score.get(sub),
            "setup": pts, "tier": tier(pts), "price": _r(f["close"].iloc[last][t], 2),
            **{k: _r(v, 2 if k == "rs" else 4) for k, v in s.items()},
            "rk": rk_now.get(t), "rk5": int(rk5[t] - rk_now[t]) if t in rk5 and t in rk_now else None,
            "rk10": int(rk10[t] - rk_now[t]) if t in rk10 and t in rk_now else None,
            "rk_m4": rk4.get(t),
            "is_stock": t in universe,
        })
    stocks.sort(key=lambda r: (-r["setup"], -(r["rs"] or -1e9)))

    # Live layer: for a new session N, an N-day return = live / close[last+1-N] - 1
    offs = {"c1": 0, "c3": 2, "c5": 4, "c15": 14, "c20": 19, "c30": 29, "c63": RS_DAYS - 1,
            "c60": 59, "c90": 89, "c180": 179, "c126": 125, "c189": 188, "c252": 251, "c10": 9}
    refs = {}
    for t in cols:
        if pd.isna(f["close"].iloc[last][t]):
            continue
        refs[t] = [_r(f["close"].iloc[last - o][t], 4) if last - o >= 0 else None for o in offs.values()] + \
                  [_r(f[f"ema{n}"].iloc[last][t], 4) for n in (8, 21, 50)]
    # ---- version-2 measures: RS Rating, Theme Strength, tightness, setup lists ----
    v2 = None
    try:
        from . import strength as S2
        sub_mem = {}
        if subthemes_df is not None and not subthemes_df.empty:
            for r_ in subthemes_df.itertuples():
                sub_mem.setdefault(r_.subtheme, []).append(r_.ticker)
        v2 = S2.build_v2(adjusted, universe, members, sub_mem, names, set(cols))
        for rows_, key in ((theme_rows, "themes"), (sub_rows, "subthemes")):
            for r_ in rows_:
                r_.update(v2[key].get(r_["theme"], {}))
        for s_ in stocks:
            s_.update(v2["tickers"].get(s_["t"], {}))
        tag = {}
        for s_ in stocks:
            tag[s_["t"]] = {"sub": s_.get("sub"), "theme": s_["themes"][0] if s_["themes"] else None}
        for lst in v2["lists"].values():
            if isinstance(lst, list):
                for r_ in lst:
                    r_.update(tag.get(r_["t"], {}))
    except Exception as e:  # keep the v1 dashboard working whatever happens
        import logging
        logging.getLogger("breadth").exception("v2 measures failed: %s", e)
    leaders = []
    try:
        from . import leaders as LD
        leaders = LD.rank(stocks, theme_rows, sub_rows)
    except Exception as e:  # never break the page over the leaders panel
        import logging
        logging.getLogger("breadth").exception("leaders failed: %s", e)
    pulse_hist = [{"date": dates[i].strftime("%Y-%m-%d"), **{k: v for k, v in pulse(tables[i]).items() if k in ("long", "short")}}
                  for i in hist_idx]
    return {
        "date": dates[last].strftime("%Y-%m-%d"),
        "trail_dates": [dates[i].strftime("%Y-%m-%d") for i in hist_idx],
        "pulse": pulse(now), "pulse_hist": pulse_hist,
        "bench": {"ticker": bench, **{k: _r(v) for k, v in bret.items()}},
        "themes": theme_rows, "subthemes": sub_rows, "stocks": stocks, "horizons": SHOW,
        "refs": refs, "ref_keys": list(offs) + ["ema8", "ema21", "ema50"],
        "hve": v2.get("hve") if v2 else None,
        "timeline_dates": v2.get("timeline_dates") if v2 else None, "px_dates": v2.get("px_dates") if v2 else None,
        "rs_bp": v2["rs_bp"] if v2 else [], "rs_short_bp": v2.get("rs_short_bp") if v2 else {}, "lists": v2["lists"] if v2 else None,
        "leaders": leaders, "trade_bt": v2.get("trade_bt") if v2 else None, "vcp_live": v2.get("vcp") if v2 else None,
        "setup_stats": v2.get("setup_stats") if v2 else None, "regime_now": v2.get("regime_now") if v2 else None,
        "str_weights": {"rel": 0.5, "part": 0.25, "lead": 0.25},
        "str_horizons": [[5, 0.15], [15, 0.20], [30, 0.25], [60, 0.20], [90, 0.20]],
        "theme_etfs": {th: e for th, e in etfs.items()},
        "missing": [m for m in missing if m in all_t],
        "counts": {"themes": len(theme_rows), "subthemes": len(sub_rows), "stocks": len(stocks)},
        "tv": _tv_map(tv, [s_["t"] for s_ in stocks] + list(etfs_flat(etfs)) + [config.BENCHMARK, "QQQ", "IWM"]
                      + ([r_["t"] for lst in (v2 or {}).get("lists", {}).values() if isinstance(lst, list) for r_ in lst])
                      + [r_["t"] for r_ in (((v2 or {}).get("hve") or {}).get("rows") or [])]),
    }
