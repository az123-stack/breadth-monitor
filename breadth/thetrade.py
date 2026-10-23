"""The trade: the market's main rotation, named every night (Oct 22, 2026; Adam: "how do we handle the trade in play?").

What it does
  - Ranks every sub-theme (4+ stocks, equal-weight index, same as rotation.py) on its 20-session move. The top fifth is
    the WINNING basket, the bottom fifth the LOSING basket. The trade = "winners over losers", named by the sectors that
    dominate each side (e.g. Software over Semiconductors).
  - Scoreboard: ratio of the two baskets (today's members held fixed) vs its 20-day average → state on / cooling /
    fading / over, sessions running, 20-day spread.
  - Is it real or a seesaw? Over the last 60 sessions: correlation of the two baskets' daily moves, and how the winners
    did (vs SPY) on the losers' best 15% of days. "Holds up" = winners kept pace when the losers bounced; "gives back" =
    the money just sloshes back and forth.
  - How to play it: strong stocks (RS 80+, $10+) in the winning groups, flagged "don't chase" when more than 2 ADRs
    above the 21-day EMA, with any Trade Setups / picks they're on. Counter-trade watch: still-strong stocks (RS 85+) in
    the losing groups, the comeback trigger (share of dollar volume in falling stocks ≤ 40%, story.py's B rule).

Evidence (`evidence`, recomputed each build; every day from day 80; baskets chosen with data up to that day; next 10
sessions of each basket vs the average group; independent samples every 10 sessions; halves). First run Oct 22, 2026
(Feb 2025–Oct 2026, 420 days): winners +0.9% vs avg group (t 1.5, halves +1.0/+0.9); when winners HOLD UP +1.1%
(t 2.0, halves +1.3/+1.1); when they GIVE BACK (47 days, ~8 episodes) winners −1.3%, losers +1.9% (n 5 independent,
not significant) — the snapback side won in 6 of 8 episodes. Information only; never touches the picks.
"""
import numpy as np
import pandas as pd

from . import rotation, store

CFG = dict(q=0.2, look=20, win=60, hot=0.85, hold=10, warm=80, chart=90, ma=20,
           chase_adr=2.0, play_rs=80, play_px=10, counter_rs=85, max_plays=10, max_counter=8,
           seesaw_corr=0.3, together_corr=0.5, comeback=40.0)


def _members():
    sd = store.load_subthemes()
    return sd.groupby("subtheme")["ticker"].apply(list).to_dict(), sd.groupby("subtheme")["group"].first().to_dict()


def _split(I, d, q=CFG["q"], look=CFG["look"]):
    r = I.iloc[d] / I.iloc[d - look] - 1
    r = r.dropna()
    p = r.rank(pct=True)
    return list(r[p >= 1 - q].sort_values(ascending=False).index), list(r[p <= q].sort_values().index), r


def _baskets(R, W, L, a, b):
    return R[W].iloc[a:b].mean(axis=1).fillna(0.0), R[L].iloc[a:b].mean(axis=1).fillna(0.0)


def _read(w, l, spy, hot=CFG["hot"]):
    """Correlation and 'does the winning basket hold up on the losers' best days' (vs SPY)."""
    cr = float(w.corr(l)) if len(w) > 5 else None
    h = l >= l.quantile(hot)
    ind = float((w[h] - spy.reindex(w.index)[h]).mean()) if h.sum() >= 3 else None
    return cr, ind, int(h.sum()), float(w[h].mean()) if h.sum() else None, float(l[h].mean()) if h.sum() else None


def frames(I, spy_ret):
    """Every day: spread, corr, hold-up read, and the next-10 result of each basket vs the average group."""
    R = I.pct_change()
    P, rows = CFG, []
    for d in range(P["warm"], len(I)):
        W, L, _ = _split(I, d)
        if len(W) < 2 or len(L) < 2:
            continue
        w, l = _baskets(R, W, L, d - P["win"] + 1, d + 1)
        cr, ind, _, _, _ = _read(w, l, spy_ret)
        sp = float((1 + w.iloc[-P["look"]:]).prod() - (1 + l.iloc[-P["look"]:]).prod())
        wf = lf = np.nan
        if d + P["hold"] < len(I):
            f = I.iloc[d + P["hold"]] / I.iloc[d] - 1
            wf, lf = float(f[W].mean() - f.mean()), float(f[L].mean() - f.mean())
        rows.append(dict(date=I.index[d], spread=sp, cr=cr, ind=ind, wf=wf, lf=lf))
    if not rows:
        return pd.DataFrame(columns=["spread", "cr", "ind", "wf", "lf"])
    return pd.DataFrame(rows).set_index("date")


def _stat(x, hold, half):
    x = x.dropna()
    s = x.iloc[::hold]
    out = {"days": int(len(x)), "n": int(len(s)), "mean": round(float(s.mean()), 4) if len(s) else None}
    out["t"] = round(float(s.mean() / s.std() * np.sqrt(len(s))), 2) if len(s) >= 3 and s.std() > 0 else None
    out["h1"] = round(float(x[x.index < half].mean()), 4) if (x.index < half).any() else None
    out["h2"] = round(float(x[x.index >= half].mean()), 4) if (x.index >= half).any() else None
    return out


def _episodes(mask, D):
    out, g = [], (mask != mask.shift()).cumsum()
    for _, v in D[mask].groupby(g[mask]):
        if len(v) < 2:
            continue
        out.append({"start": str(v.index[0].date()), "end": str(v.index[-1].date()), "days": int(len(v)),
                    "w": None if v.wf.isna().all() else round(float(v.wf.mean()), 4),
                    "l": None if v.lf.isna().all() else round(float(v.lf.mean()), 4)})
    return out


def evidence(D):
    hold, X = CFG["hold"], D.dropna(subset=["wf"])
    if len(X) < 40:
        return None
    half = X.index[len(X) // 2]
    conds = {"all": X.spread > -9, "holds": X.ind >= 0, "gives": X.ind < 0,
             "seesaw": X.cr < CFG["seesaw_corr"], "together": X.cr >= CFG["together_corr"]}
    rows = {k: {"w": _stat(X.wf[m], hold, half), "l": _stat(X.lf[m], hold, half)} for k, m in conds.items()}
    gives = _episodes(D.ind < 0, D)
    done = [e for e in gives if e["w"] is not None]
    return {"from": str(X.index[0].date()), "to": str(X.index[-1].date()), "n": int(len(X)), "hold": hold,
            "rows": rows, "gives_eps": gives[-10:],
            "gives_snap": [sum(1 for e in done if e["l"] > e["w"]), len(done)]}


def _state(r, ma):
    below = 0
    for a, b in zip(r[::-1], ma[::-1]):
        if np.isnan(b) or a >= b:
            break
        below += 1
    above = 0
    for a, b in zip(r[::-1], ma[::-1]):
        if np.isnan(b) or a < b:
            break
        above += 1
    if below >= 3:
        return "over", above, below
    if below >= 1:
        return "fading", above, below
    if r[-1] < max(r[-5:]) * 0.98:
        return "cooling", above, below
    return "on", above, below


def _side_name(groups, sector, r20, sign=1):
    """Name a side by the sectors carrying the most of its 20-day move (a close second joins with '&')."""
    w, n = {}, {}
    for g in groups:
        k = sector.get(g, "Other")
        w[k] = w.get(k, 0.0) + sign * float(r20[g])
        n[k] = n.get(k, 0) + 1
    top = sorted(w.items(), key=lambda kv: -kv[1])
    if not top:
        return "–", []
    name = top[0][0] + (f" + {top[1][0]}" if len(top) > 1 and top[1][1] >= 0.7 * top[0][1] else "")
    return name, [{"s": k, "n": n[k], "move": round(v, 4)} for k, v in top[:4]]


def _spread(rows, per_sub, cap):
    out, seen = [], {}
    for r in rows:
        if seen.get(r["sub"], 0) >= per_sub:
            continue
        seen[r["sub"]] = seen.get(r["sub"], 0) + 1
        out.append(r)
        if len(out) >= cap:
            break
    return out


def build(adjusted, theme_data, history=None):
    T = theme_data or {}
    mem, sector = _members()
    tick = sorted({t for v in mem.values() for t in v} | {"SPY"})
    close, _, _ = rotation._wide(adjusted, tick)
    if "SPY" not in close.columns or len(close) < CFG["warm"] + 20:
        return None
    F = rotation.group_frames(close, mem)
    I = F["idx"]
    R = I.pct_change()
    spy = close["SPY"].pct_change()
    d = len(I) - 1
    W, L, r20 = _split(I, d)
    a = max(1, d - CFG["chart"] - CFG["ma"] + 1)
    w, l = _baskets(R, W, L, a, d + 1)
    ratio = ((1 + w).cumprod() / (1 + l).cumprod())
    ma = ratio.rolling(CFG["ma"]).mean()
    rr, mm = ratio.values, ma.values
    state, above, below = _state(rr, mm)
    w60, l60 = w.iloc[-CFG["win"]:], l.iloc[-CFG["win"]:]
    cr, ind, nhot, w_hot, l_hot = _read(w60, l60, spy)
    sp20 = float((1 + w.iloc[-20:]).prod() - (1 + l.iloc[-20:]).prod())
    wname, wsec = _side_name(W, sector, r20)
    lname, lsec = _side_name(L, sector, r20, -1)
    subs = {r["theme"]: r for r in T.get("subthemes") or []}
    grp = lambda g: {"g": g, "sector": sector.get(g), "r20": round(float(r20[g]), 4),
                     "r5": round(float(I[g].iloc[-1] / I[g].iloc[-6] - 1), 4),
                     "strength": (subs.get(g) or {}).get("strength"), "s_rank": (subs.get(g) or {}).get("s_rank")}
    # how to play it / counter-trade
    on = {}
    for s in ((T.get("trade_setups") or {}).get("setups") or []):
        for t in s.get("top") or []:
            on.setdefault(t, []).append(s["name"])
    for i, p in enumerate((T.get("playbook") or {}).get("picks") or []):
        on.setdefault(p["t"], []).insert(0, f"Top pick #{i + 1}")
    Wset, Lset = set(W), set(L)

    def row(s):
        adr = s.get("adr") or 0
        ext = (s.get("e21") or 0) / (adr / 100) if adr else None
        return {"t": s["t"], "name": s.get("name"), "sub": s.get("sub"), "price": s.get("price"), "rsr": s.get("rsr"),
                "off_hi": s.get("off_hi"), "d5": s.get("d5"), "d20": s.get("d20"), "e21": s.get("e21"), "adr": adr,
                "ext": None if ext is None else round(ext, 2), "chase": ext is not None and ext > CFG["chase_adr"],
                "reclaim": (s.get("e21") or -1) >= 0, "on": on.get(s["t"], [])}
    st = [s for s in T.get("stocks") or [] if s.get("is_stock", True) and (s.get("price") or 0) >= CFG["play_px"]]
    rank = {g: i for i, g in enumerate(W)}
    cand = sorted([row(s) for s in st if s.get("sub") in Wset and (s.get("rsr") or 0) >= CFG["play_rs"]],
                  key=lambda r: (-len(r["on"]), -(r["rsr"] or 0), rank.get(r["sub"], 99)))
    plays = _spread([r for r in cand if not r["chase"]], 2, CFG["max_plays"])
    stretched = _spread([r for r in cand if r["chase"]], 2, 6)
    counter = _spread(sorted([row(s) for s in st if s.get("sub") in Lset and (s.get("rsr") or 0) >= CFG["counter_rs"]],
                             key=lambda r: (not r["reclaim"], -(r["rsr"] or 0))), 2, CFG["max_counter"])
    ds = None
    if history is not None and len(history) and "dn_share" in history.columns:
        v = history["dn_share"].dropna()
        ds = round(float(v.iloc[-1]), 1) if len(v) else None
    try:
        D = frames(I, spy)
        ev = evidence(D)
        hist = D.iloc[-CFG["chart"]:]
        hist = {"dates": [str(x.date()) for x in hist.index], "cr": [None if pd.isna(x) else round(float(x), 3) for x in hist.cr],
                "ind": [None if pd.isna(x) else round(float(x) * 100, 2) for x in hist.ind]}
    except Exception:          # evidence is optional; the card still names the trade
        ev, hist = None, None
    dates = [str(x.date()) for x in ratio.index[-CFG["chart"]:]]
    return {
        "date": str(I.index[-1].date()), "name": f"{wname} over {lname}", "win_sector": wname, "lose_sector": lname,
        "win_sectors": wsec, "lose_sectors": lsec,
        "winners": [grp(g) for g in W], "losers": [grp(g) for g in L],
        "state": state, "above": above, "below": below, "spread20": round(sp20, 4),
        "ratio": {"dates": dates, "r": [round(float(x), 4) for x in rr[-CFG["chart"]:]],
                  "ma": [None if np.isnan(x) else round(float(x), 4) for x in mm[-CFG["chart"]:]]},
        "corr": None if cr is None else round(cr, 3), "ind": None if ind is None else round(ind, 4),
        "hot_n": nhot, "w_hot": None if w_hot is None else round(w_hot, 4), "l_hot": None if l_hot is None else round(l_hot, 4),
        "plays": plays, "stretched": stretched, "counter": counter, "dn_share": ds, "comeback": ds is not None and ds <= CFG["comeback"],
        "members": {g: [t for t in mem.get(g, []) if t in close.columns] for g in W + L},
        "evidence": ev, "hist": hist, "cfg": {k: CFG[k] for k in ("q", "look", "win", "hot", "hold", "chase_adr", "comeback")},
    }
