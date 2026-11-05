"""Pop watch (Nov 4, 2026; Adam: "sub-themes pop and then I forget about them because they're not exploding anymore, but that's exactly
when I need to be grabbing them. Homebuilders popped today, I'd love to grab one on the pullback, but I'll forget" + "basically had relative
strength but then pulled back").

The dashboard remembers every sub-theme POP for POP_DAYS sessions and tracks it while it pulls back:
  pop day   = the same rule as the live Runners alert (runners.CFG), on the official close: 4+ liquid members ($3+, $10M+/day),
              75%+ up, average move ≥ 1.25 of their own ADRs, group beats SPY by 3+ pts, dollar volume ≥ 1.2× its 50-day average
              (+ any group the live Runners alert logged as running today, data/runner_log.csv, so today's pop is kept before the
              nightly data arrives)
  state     = running (within half an ADR of its post-pop high) / pulling back (off the post-pop high, still above the pop-day
              open) / gave it back (closed under the pop-day open: the pop failed) ; rel = group vs SPY since the pop day's close
  names     = liquid RS 70+ uptrend members (lifecycle.stock_frames "base"), with the same fields as the Lined-up buys rows so the page
              tags them live (into the 9/21 ribbon / near / over yesterday's high)
Evidence (`study`): first 9/21 ribbon dips 3–25 sessions after a pop, bought on the break of the dip-day high within 3 sessions (stop the
dip low ≤ 1 ADR, 20 sessions) = the Lined-up buys trigger rule, vs the same dips by stocks whose group had no pop in 25 sessions.
"""
import csv
import logging

import numpy as np
import pandas as pd

from . import config
from .lifecycle import _r, _wide, stock_frames
from .runners import CFG as RUN

POP_DAYS = 25
CFG = {"min_n": RUN["min_n"], "up_share": RUN["up_share"], "adr_avg": RUN["adr_avg"], "rel": RUN["rel"], "pace": RUN["pace"],
       "min_price": RUN["min_price"], "min_dvol": RUN["min_dvol"], "space": 10, "dip_from": 3, "dip_to": POP_DAYS, "hold": 20}
log = logging.getLogger("breadth")


def pops(w, members):
    """DataFrame (dates × groups) of pop days, plus each group's equal-weight index (price) and avg ADR."""
    c, o, h, l, v = (w[k] for k in ("c", "o", "h", "l", "v"))
    ret = c.pct_change(fill_method=None)
    adr = ((h / l) - 1).rolling(20, min_periods=15).mean().shift(1)
    dv = (c * v)
    dv50 = dv.rolling(50, min_periods=30).mean().shift(1)
    liq = (c.shift(1) >= CFG["min_price"]) & (dv50 >= CFG["min_dvol"])
    spy = ret[config.BENCHMARK]
    P, IDX, A = {}, {}, {}
    for g, mem in members.items():
        m = [t for t in mem if t in c.columns]
        if len(m) < CFG["min_n"]:
            continue
        L = liq[m]
        n = L.sum(axis=1)
        r = ret[m].where(L)
        up = (r > 0).sum(axis=1) / n.replace(0, np.nan)
        mv = (r / adr[m]).where(L).mean(axis=1)
        avg = r.mean(axis=1)
        pace = dv[m].where(L).sum(axis=1) / dv50[m].where(L).sum(axis=1)
        P[g] = (n >= CFG["min_n"]) & (up >= CFG["up_share"]) & (mv >= CFG["adr_avg"]) & (avg - spy >= CFG["rel"]) & (pace >= CFG["pace"])
        IDX[g] = (1 + ret[m].clip(-0.5, 1).mean(axis=1).fillna(0)).cumprod()
        A[g] = adr[m].where(L).mean(axis=1)
    return pd.DataFrame(P).fillna(False), pd.DataFrame(IDX), pd.DataFrame(A)


def _first(mask, gap):
    out = mask.copy() & False
    for g in mask.columns:
        last = -10 ** 9
        col = mask[g].to_numpy()
        for i in np.flatnonzero(col):
            if i - last > gap:
                out.iat[i, out.columns.get_loc(g)] = True
            last = i
    return out


def study(P, POP, members, IDX=None, spy=None):
    """Lined-up trigger rule on first ribbon dips: after a pop (3–25 sessions) vs groups without a pop in 25 sessions."""
    days = P["c"].index
    n = len(days)
    first = P["touch"] & ~P["touch"].shift(1, fill_value=False).rolling(5, min_periods=1).max().astype(bool)
    F = _first(POP, CFG["space"])
    since, popk = {}, {}             # sessions since the group's last pop (first-of-run), and that pop's index

    for g in F.columns:
        s = np.full(n, 10 ** 6)
        pk = np.full(n, -1)
        last = None
        for i, x in enumerate(F[g].to_numpy()):
            if x:
                last = i
            if last is not None:
                s[i] = i - last
                pk[i] = last
        since[g], popk[g] = s, pk
    grp = {}
    for g, mem in members.items():
        for t in mem:
            grp.setdefault(t, g)
    H = CFG["hold"]
    rows = []
    for t in P["c"].columns:
        g = grp.get(t)
        if g not in since:
            continue
        for i in np.flatnonzero(first[t].to_numpy()):
            if i < 120 or i + H + 3 >= n:
                continue
            a = P["adr"][t].iat[i]
            hi_i, lo_i = P["h"][t].iat[i], P["l"][t].iat[i]
            if not (np.isfinite(a) and a > 0):
                continue
            Rt = None
            for j in range(i + 1, i + 4):
                if P["h"][t].iat[j] >= hi_i:
                    en = max(P["o"][t].iat[j], hi_i)
                    st = max(lo_i, en * (1 - a))
                    risk = max(en - st, 0.3 * a * en)
                    lw = P["l"][t].iloc[j:j + H].to_numpy()
                    Rt = (st - en) / risk if len(np.flatnonzero(lw <= st)) else (P["c"][t].iat[j + H - 1] - en) / risk
                    break
            if Rt is None:
                continue
            s = since[g][i]
            k = "after_pop" if CFG["dip_from"] <= s <= CFG["dip_to"] else "no_pop" if s > CFG["dip_to"] else "too_soon"
            held = None
            if k == "after_pop" and IDX is not None and g in IDX.columns:
                q = popk[g][i]
                held = bool((IDX[g].iat[i] / IDX[g].iat[q]) / (spy.iat[i] / spy.iat[q]) - 1 >= 0)
            rows.append((days[i], t, g, k, min(Rt, 10), held))
    X = pd.DataFrame(rows, columns=["date", "t", "g", "k", "R", "held"])
    if not len(X):
        return None
    split = X["date"].sort_values().iloc[len(X) // 2]
    out = {"from": str(X["date"].min().date()), "to": str(X["date"].max().date()), "pops": int(F.to_numpy().sum())}
    X["k2"] = None
    X.loc[(X["k"] == "after_pop") & (X["held"] == True), "k2"] = "held_rs"
    X.loc[(X["k"] == "after_pop") & (X["held"] == False), "k2"] = "lost_rs"
    for k in ("after_pop", "no_pop", "too_soon", "held_rs", "lost_rs"):
        x = X[(X["k"] == k) | (X["k2"] == k)]
        out[k] = {"n": int(len(x)), "R": _r(x["R"].mean(), 3), "win": _r((x["R"] > 0).mean(), 3),
                  "h1": _r(x[x["date"] < split]["R"].mean(), 3), "h2": _r(x[x["date"] >= split]["R"].mean(), 3)}
    d = (X[X["k"] == "after_pop"].groupby("date")["R"].mean() - X[X["k"] == "no_pop"].groupby("date")["R"].mean()).dropna()
    out["edge"] = _r(d.mean(), 3)
    out["t"] = _r(d.mean() / (d.std(ddof=1) / np.sqrt(len(d))), 2) if len(d) > 2 and d.std(ddof=1) > 0 else None
    d2 = (X[X["k2"] == "held_rs"].groupby("date")["R"].mean() - X[X["k"] == "no_pop"].groupby("date")["R"].mean()).dropna()
    out["edge_held"] = _r(d2.mean(), 3)
    out["t_held"] = _r(d2.mean() / (d2.std(ddof=1) / np.sqrt(len(d2))), 2) if len(d2) > 2 and d2.std(ddof=1) > 0 else None
    out["proven"] = bool(out["t"] is not None and out["t"] >= 2 and (out["after_pop"]["h1"] or 0) > (out["no_pop"]["h1"] or 0)
                         and (out["after_pop"]["h2"] or 0) > (out["no_pop"]["h2"] or 0))
    return out


def live_pops(today_str):
    """Groups the live Runners alert logged as running on `today_str` (data/runner_log.csv)."""
    p = config.DATA_DIR / "runner_log.csv"
    out = {}
    try:
        with open(p) as f:
            for r in csv.DictReader(f):
                if r.get("date") == today_str:
                    out[r["group"]] = r
    except FileNotFoundError:
        pass
    return out


def build(adjusted, theme_data, evidence_on=True):
    T = theme_data or {}
    members = {g["theme"]: list(g.get("members") or []) for g in T.get("subthemes") or []}
    tick = sorted({t for m in members.values() for t in m} | {config.BENCHMARK})
    w = _wide(adjusted, tick)
    POP, IDX, A = pops(w, members)
    P = stock_frames(w, [t for t in w["c"].columns])
    days = w["c"].index
    i = len(days) - 1
    stocks = {s["t"]: s for s in T.get("stocks") or []}
    strength = {g["theme"]: g.get("strength") for g in T.get("subthemes") or []}
    c, o = w["c"], w["o"]
    spy = c[config.BENCHMARK]
    rows = []
    for g in POP.columns:
        hits = np.flatnonzero(POP[g].to_numpy()[max(0, i - POP_DAYS + 1):i + 1])
        if not len(hits):
            continue
        k = max(0, i - POP_DAYS + 1) + int(hits[-1])          # most recent pop day
        firstk = max(0, i - POP_DAYS + 1) + int(hits[0])
        ix = IDX[g]
        pop_open = ix.iat[k - 1] * (1 + (np.nanmean([o[t].iat[k] / c[t].iat[k - 1] - 1 for t in members[g] if t in c.columns
                                                       and np.isfinite(o[t].iat[k]) and np.isfinite(c[t].iat[k - 1])]) or 0))
        peak = float(ix.iloc[k:i + 1].max())
        ago_peak = i - (k + int(np.argmax(ix.iloc[k:i + 1].to_numpy())))
        last = float(ix.iat[i])
        adr_g = float(A[g].iat[i]) if np.isfinite(A[g].iat[i]) else None
        off_pk = last / peak - 1
        rel = (last / ix.iat[k]) / (spy.iat[i] / spy.iat[k]) - 1                      # vs SPY since the pop-day close
        rel0 = (last / ix.iat[k - 1]) / (spy.iat[i] / spy.iat[k - 1]) - 1              # vs SPY incl. the pop day
        near_pk = adr_g is not None and off_pk >= -0.5 * adr_g          # within half a day's range of the post-pop high
        state = "gave_back" if last < pop_open else "running" if near_pk else "pulling_back"
        names = []
        for t in members[g]:
            if t not in P["c"].columns or not bool(P["base"][t].iat[i]):
                continue
            s = stocks.get(t) or {}
            if s.get("deal") or (s.get("is_stock") is False and s.get("name")):
                continue
            rs = s.get("rsr")
            a = P["adr"][t].iat[i]
            names.append({"t": t, "g": g, "rs": _r(rs, 0), "c": _r(P["c"][t].iat[i], 4), "hi": _r(P["h"][t].iat[i], 4),
                          "lo": _r(P["l"][t].iat[i], 4), "e9": _r(P["e9"][t].iat[i], 4), "e21": _r(P["e21"][t].iat[i], 4),
                          "adr": _r(a, 4), "t3": bool(P["touch"][t].iloc[i - 2:i + 1].any()), "t0": bool(P["touch"][t].iat[i]),
                          "pop_r": _r(c[t].iat[k] / c[t].iat[k - 1] - 1, 4), "since": _r(c[t].iat[i] / c[t].iat[k] - 1, 4)})
        names.sort(key=lambda x: (not x["t3"], -(x["rs"] or 0)))
        rows.append({"g": g, "pop": days[k].strftime("%Y-%m-%d"), "first": days[firstk].strftime("%Y-%m-%d"), "ago": i - k,
                     "pops": int(len(hits)), "pop_r": _r(ix.iat[k] / ix.iat[k - 1] - 1, 4), "state": state,
                     "off_pk": _r(off_pk, 4), "off_adr": _r(off_pk / adr_g, 2) if adr_g else None, "rel": _r(rel, 4), "rel0": _r(rel0, 4),
                     "strength": _r(strength.get(g), 1), "n": len(members[g]), "names": names,
                     "line": [_r(x, 4) for x in (ix.iloc[max(0, k - 5):i + 1] / ix.iat[k - 1]).to_numpy()], "line_k": min(5, k)})
    today = days[i].strftime("%Y-%m-%d")
    live = live_pops(pd.Timestamp.now(tz="America/New_York").strftime("%Y-%m-%d"))
    seen = {r["g"] for r in rows}
    fresh = []
    for g, r in live.items():
        if g not in members or (g in seen and next(x for x in rows if x["g"] == g)["pop"] >= r["date"]):
            continue
        fresh.append({"g": g, "date": r["date"], "avg": _r(r.get("avg"), 4), "adrs": _r(r.get("adrs"), 2), "top": r.get("top", "")})
    rows.sort(key=lambda r: ({"pulling_back": 0, "running": 1, "gave_back": 2}[r["state"]], -(r["rel"] or 0)))
    out = {"date": today, "cfg": CFG, "days": POP_DAYS, "rows": rows, "live_today": fresh}
    if evidence_on:
        try:
            out["evidence"] = study(P, POP, members, IDX, spy)
        except Exception as e:
            log.exception("pop watch evidence failed: %s", e)
    return out
