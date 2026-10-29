"""Groups running together, live (Adam, Oct 28 2026: "an alert when a sub-theme is running hard together, like AI drug
discovery today — worth day trading").

Pure functions shared by the 5-minute alert job (breadth/lineup.py → docs/lineup_live.json + ntfy) and mirrored on the page
(`runnersNow` in template.html, tested against this file in Node). A sub-theme is RUNNING when, from the live Google Sheet:
  - at least CFG.min_n liquid members have a live price,
  - CFG.up_share+ of them are up on the day,
  - their average move is CFG.adr_avg+ ADRs (each stock's move ÷ its own 20-day ADR) and CFG.rel+ better than SPY,
  - their dollar volume is running CFG.pace+ × normal for the time of day (paced with the intraday volume profile).
"Strong" = 1.5+ ADRs on 1.5x volume (best follow-through). "Heating up" = 3 of 4 checks with most members up and the average
at least 80% of the bar (shown on the page, no alert). Names to trade = members above today's
open (holding their gains) and up 0.75+ ADR, best RS first.
"""

# Thresholds from the daily backtest (card R-2026-10-29-group-runs, ~2 years, 115 sub-themes): runs of 1.25+ ADRs on 1.2x volume
# beat the average group next day open->close +0.34% (t 2.25) and over 5 days +0.90% (t 2.47); "strong" runs (1.5+ ADRs on
# 1.5x volume, ~2.7 a week) +0.62% (t 2.64) and +1.47% (t 2.58), both halves positive.
CFG = {"min_n": 4, "up_share": 0.75, "adr_avg": 1.25, "rel": 0.03, "pace": 1.2, "strong_adr": 1.5, "strong_pace": 1.5,
       "min_mins": 15, "top": 3, "min_price": 3.0, "min_dvol": 10e6, "again_adr": 1.0, "max_alerts": 3}


def vol_pace(mins, profile):
    """Share of a normal day's volume done after `mins` minutes of the session (twin of volPace)."""
    P = profile or [[0, 0], [390, 1]]
    if mins is None or mins <= 0:
        return None
    if mins >= 390:
        return 1.0
    for i in range(1, len(P)):
        if mins <= P[i][0]:
            a, x = P[i - 1]
            b, y = P[i]
            return x + (y - x) * (mins - a) / (b - a)
    return 1.0


def _chg(r):
    if not r or not r.get("price") or not r.get("closeyest"):
        return None
    c = r["price"] / r["closeyest"] - 1
    return c if abs(c) <= 0.6 else None


def scan(rows, subthemes, stocks, mins, profile, cfg=None):
    """rows = {TICKER: {price, closeyest, open, volume}} from the sheet; subthemes = DATA.themes.subthemes; stocks =
    DATA.themes.stocks. Returns every sub-theme with enough live members, sorted running first, with its checks."""
    C = dict(CFG, **(cfg or {}))
    S = {s["t"]: s for s in stocks or []}
    pace = vol_pace(mins, profile)
    spy = _chg(rows.get("SPY")) or 0.0
    out = []
    for g in subthemes or []:
        mem = []
        for t in g.get("members") or []:
            s, r = S.get(t), rows.get(t)
            ch = _chg(r)
            if not s or not s.get("is_stock") or ch is None or not s.get("adr"):
                continue
            px = r["price"]
            if px < C["min_price"] or (s.get("v50") or 0) * px < C["min_dvol"]:
                continue
            a = s["adr"] / 100.0
            mem.append({"t": t, "chg": ch, "adrs": ch / a, "rs": s.get("rsr"), "px": px, "open": r.get("open"),
                        "dv": px * (r.get("volume") or 0), "nv": px * (s.get("v50") or 0)})
        if len(mem) < C["min_n"]:
            continue
        n = len(mem)
        up = sum(1 for m in mem if m["chg"] > 0)
        avg = sum(m["chg"] for m in mem) / n
        adrs = sum(m["adrs"] for m in mem) / n
        nv = sum(m["nv"] for m in mem)
        vp = (sum(m["dv"] for m in mem) / (nv * pace)) if nv and pace else None
        checks = {"up": up / n >= C["up_share"], "adr": adrs >= C["adr_avg"], "rel": avg - spy >= C["rel"],
                  "vol": vp is not None and vp >= C["pace"]}
        passed = sum(checks.values())
        status = "running" if passed == 4 else "heating" if passed == 3 and checks["up"] and (checks["adr"] or adrs >= 0.8 * C["adr_avg"]) else None
        strong = status == "running" and adrs >= C["strong_adr"] and vp >= C["strong_pace"]
        hold = [m for m in mem if m["adrs"] >= 0.75 and (not m["open"] or m["px"] >= m["open"])]
        hold.sort(key=lambda m: -(m["rs"] or 0))
        out.append({"g": g.get("theme"), "n": n, "up": up, "avg": round(avg, 4), "adrs": round(adrs, 2), "rel": round(avg - spy, 4),
                    "pace": None if vp is None else round(vp, 2), "checks": checks, "status": status, "strong": bool(strong), "strength": g.get("strength"),
                    "top": [{"t": m["t"], "chg": round(m["chg"], 4), "adrs": round(m["adrs"], 2), "rs": m["rs"]} for m in hold[:C["top"]]],
                    "movers": [m["t"] for m in sorted(mem, key=lambda m: -m["chg"])[:6]]})
    rank = {"running": 0, "heating": 1, None: 2}
    out.sort(key=lambda x: (rank[x["status"]], -x["adrs"]))
    return out


def alerts(groups, prior, mins, cfg=None):
    """New alert events: the first time today a group is RUNNING, then again each time its average move grows by
    CFG.again_adr more ADRs (max CFG.max_alerts per group per day). prior = today's earlier group events."""
    C = dict(CFG, **(cfg or {}))
    if mins is None or mins < C["min_mins"]:
        return []
    last = {}
    for e in prior or []:
        last.setdefault(e["g"], []).append(e)
    new = []
    for x in groups:
        if x["status"] != "running":
            continue
        p = last.get(x["g"]) or []
        if len(p) >= C["max_alerts"] or (p and x["adrs"] < p[-1]["adrs"] + C["again_adr"]):
            continue
        new.append({"type": "group", "g": x["g"], "again": bool(p), "strong": x["strong"], "n": x["n"], "up": x["up"], "avg": x["avg"], "adrs": x["adrs"],
                    "rel": x["rel"], "pace": x["pace"], "top": x["top"], "strength": x["strength"]})
    return new


def text(e):
    """(title, body) for a phone notification."""
    top = ", ".join(f"{m['t']} {m['chg'] * 100:+.1f}% (RS {m['rs'] if m['rs'] is not None else '–'})" for m in e["top"]) or "none holding over the open"
    title = f"{'Still running' if e['again'] else 'Group running'}{' (strong)' if e.get('strong') else ''}: {e['g']}"
    body = (f"{e['up']}/{e['n']} up · avg {e['avg'] * 100:+.1f}% ({e['adrs']:.1f} ADRs) · {e['rel'] * 100:+.1f} pts vs SPY · "
            f"volume {e['pace']:.1f}x normal pace · holding: {top}")
    return title, body
