"""EMA test odds (Oct 29, 2026; Adam: "time spent above the 9 and/or 21 EMAs ... when it comes near them or goes under them, when the
probability is high enough it results in an entry. Same thing on the short side.")

A "test" = a liquid stock ($5+, $20M+/day) that closed on the right side of its 9 or 21 EMA for 3+ sessions comes back to it: the low
gets within 0.25 ADR of the EMA (or through it). Shorts mirror it: a stock living under the EMA rallies up into it. First test in 5
sessions per stock and EMA; a 9-EMA test that also reaches the 21 counts as a 21 test.

Every test is traded like the other dip cards: buy the break of the test-day high within 3 sessions (fill = max(open, trigger)), stop
the test-day low (max 1 ADR under the entry, risk floored at 0.3 ADR); WIN = +2R before the stop within 20 sessions (2:1 breaks even at
33%); also R after 20 sessions (capped 10R) and Adam's exit (first close under the 10 EMA). Shorts mirror.

First pass (Oct 29): a logistic model on ~17 features (time above, share of closes above, depth, run-up, tests, slope, RS, market,
group, thrust) had NO out-of-sample skill (AUC 0.50 long / 0.49 short), so the page doesn't show a model "probability". What did hold
up in both halves was coupling: time above + leading group + post-thrust window. So the odds are an honest lookup table of tiers
(`tier`, mirrored in the page as `emaTier`), recomputed every build with win rate, avg R and halves.

  A  post-thrust window + leading group (sub-theme top 30% on 60 days) + 15+ sessions on the right side of the EMA
  B  post-thrust window + leading group
  C  leading group + (15+ sessions on the right side OR the test held 0.5+ ADR above the EMA)
  D  leading group, short run, deep test
  E  not in a leading group
Shorts use the same tiers with "leading group" = the weakest 30% of sub-themes and time BELOW the EMA.
"""
import numpy as np
import pandas as pd

from . import config

CFG = dict(min_price=5.0, min_dvol=20e6, touch=0.25, space=5, trig_days=3, hold=20, target=2.0, floor=0.3, warm=60, lead=0.7,
           run=15, held=0.5, near=1.5, min_streak=3, n_live=120, recent=3)
TIERS = ["A", "B", "C", "D", "E"]
TIER_LABEL = {"A": "Post-thrust + leading group + 15+ sessions on the right side",
              "B": "Post-thrust + leading group",
              "C": "Leading group + 15+ sessions, or held 0.5+ ADR off the EMA",
              "D": "Leading group, short run and a deep test",
              "E": "Not in a leading group"}


def _r(x, n=3):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, n) if np.isfinite(x) else None


def tier(lead, thr, streak, depth):
    """The odds tier of one test (the page has the same rule in `emaTier`)."""
    if not lead:
        return "E"
    if thr and streak >= CFG["run"]:
        return "A"
    if thr:
        return "B"
    if streak >= CFG["run"] or depth >= CFG["held"]:
        return "C"
    return "D"


def _streak(b):
    s = b.cumsum()
    return s - s.where(~b).ffill().fillna(0)


def frames(adjusted, subthemes=None, history=None, bench=None):
    bench = bench or config.BENCHMARK
    piv = lambda k: adjusted.pivot_table(index="date", columns="ticker", values=k).sort_index()
    c = piv("c").astype("float64")
    if bench not in c.columns:
        return None
    o, h, l, v = (piv(k).reindex_like(c).astype("float64") for k in ("o", "h", "l", "v"))
    adr = ((h / l) - 1).rolling(20, min_periods=15).mean()
    dvol = (c * v).rolling(20, min_periods=15).mean()
    e9, e10, e21 = (c.ewm(span=n, adjust=False, min_periods=n).mean() for n in (9, 10, 21))
    liq = (c >= CFG["min_price"]) & (dvol >= CFG["min_dvol"])
    grp = pd.DataFrame(np.nan, index=c.index, columns=c.columns)   # sub-theme 60-day median return, ranked across sub-themes
    sub_of = {}
    if subthemes is not None and len(subthemes):
        r60 = c / c.shift(60) - 1
        med = {}
        for sname, d in subthemes.groupby("subtheme"):
            m = [t for t in d["ticker"] if t in c.columns]
            if len(m) >= 3:
                med[sname] = r60[m].median(axis=1)
        if med:
            G = pd.DataFrame(med).rank(axis=1, pct=True)
            for t, sname in zip(subthemes["ticker"], subthemes["subtheme"]):
                if t in grp.columns and sname in G.columns:
                    grp[t] = G[sname].to_numpy()
                    sub_of[t] = sname
    thr = np.zeros(len(c), dtype=bool)
    if history is not None:
        try:
            from . import metrics
            thr = metrics.thrust_window(history, list(c.index))
        except Exception:
            pass
    return dict(c=c, o=o, h=h, l=l, adr=adr, dvol=dvol, e9=e9, e10=e10, e21=e21, liq=liq, grp=grp, sub_of=sub_of,
                thr=pd.Series(thr, index=c.index))


def _tests(F, side):
    """Per EMA: first-test mask, the streak BEFORE the test day, and the test-day depth (ADRs, + = still on the right side)."""
    c, h, l, adr = F["c"], F["h"], F["l"], F["adr"]
    out = {}
    for k, e in (("9", F["e9"]), ("21", F["e21"])):
        right = (c > e) if side > 0 else (c < e)
        streak = _streak(right)
        before = streak.shift(1)
        reach = (l <= e + CFG["touch"] * adr * c) if side > 0 else (h >= e - CFG["touch"] * adr * c)
        test = F["liq"] & right.shift(1, fill_value=False) & reach & (before >= CFG["min_streak"])
        if k == "9":
            test = test & ((l > F["e21"] + CFG["touch"] * adr * c) if side > 0 else (h < F["e21"] - CFG["touch"] * adr * c))
        first = test & ~test.shift(1, fill_value=False).rolling(CFG["space"], min_periods=1).max().astype(bool)
        out[k] = dict(first=first, before=before, streak=streak, depth=side * (c - e) / (adr * c))
    return out


def _trade(F, i, j, side):
    """(win2R, R20 capped, R Adam's exit) of a test on day i, or None if never triggered."""
    c, o, h, l, adr, e10 = F["_np"]
    n = c.shape[0]
    H, D = CFG["hold"], CFG["trig_days"]
    a = adr[i, j]
    if i + D + H >= n or not (np.isfinite(a) and a > 0):
        return None
    trig, other = (h[i, j], l[i, j]) if side > 0 else (l[i, j], h[i, j])
    for k in range(i + 1, i + 1 + D):
        if (side > 0 and h[k, j] >= trig) or (side < 0 and l[k, j] <= trig):
            en = max(o[k, j], trig) if side > 0 else min(o[k, j], trig)
            st = max(other, en * (1 - a)) if side > 0 else min(other, en * (1 + a))
            risk = max(side * (en - st), CFG["floor"] * a * en)
            tgt = en + side * CFG["target"] * risk
            stop_hit = lambda m: (l[m, j] <= st) if side > 0 else (h[m, j] >= st)
            win = 0
            for m in range(k, k + H):
                if stop_hit(m):
                    break
                if (h[m, j] >= tgt) if side > 0 else (l[m, j] <= tgt):
                    win = 1
                    break
            ex = next((st for m in range(k, k + H) if stop_hit(m)), c[k + H - 1, j])
            exk = None
            for m in range(k, k + H):
                if stop_hit(m):
                    exk = st; break
                if m > k and ((c[m, j] < e10[m, j]) if side > 0 else (c[m, j] > e10[m, j])):
                    exk = c[m, j]; break
            exk = c[k + H - 1, j] if exk is None else exk
            return win, min(side * (ex - en) / risk, 10), min(side * (exk - en) / risk, 10)
    return None


def _tab(x):
    return {"n": int(len(x)), "win": _r(x["win"].mean()), "R": _r(x["R"].mean()), "Rk": _r(x["Rk"].mean())} if len(x) else {"n": 0}


def study(F, side, P):
    rows = []
    thr = F["thr"].to_numpy()
    grp = F["grp"].to_numpy()
    for k in ("9", "21"):
        D = P[k]
        ii, jj = np.nonzero(D["first"].to_numpy())
        bef, dep = D["before"].to_numpy(), D["depth"].to_numpy()
        for i, j in zip(ii, jj):
            if i < CFG["warm"]:
                continue
            res = _trade(F, i, j, side)
            if res is None:
                continue
            g = grp[i, j]
            lead = bool(np.isfinite(g) and ((g >= CFG["lead"]) if side > 0 else (g <= 1 - CFG["lead"])))
            rows.append((i, k, bef[i, j], dep[i, j], lead, bool(thr[i]), *res))
    X = pd.DataFrame(rows, columns=["i", "ema", "streak", "depth", "lead", "thr", "win", "R", "Rk"])
    if len(X) < 100:
        return None
    X["tier"] = [tier(a, b, s, d) for a, b, s, d in zip(X["lead"], X["thr"], X["streak"], X["depth"])]
    dates = F["c"].index
    split = int(np.median(X["i"]))
    half = X["i"] < split
    def tab2(m):
        x = X[m]
        return {**_tab(x), "h1": _r(x[half[m]]["R"].mean()), "h2": _r(x[~half[m]]["R"].mean()),
                "w1": _r(x[half[m]]["win"].mean()), "w2": _r(x[~half[m]]["win"].mean())}
    tiers = []
    for t in TIERS:
        o = tab2(X["tier"] == t)
        o["entry"] = bool(o["n"] >= 100 and (o.get("h1") or -1) > 0 and (o.get("h2") or -1) > 0 and (o.get("win") or 0) >= 0.30)
        tiers.append({"tier": t, "label": TIER_LABEL[t], **o})
    def bucket(col, edges, labels):
        return [{"label": lab, **tab2((X[col] >= a) & (X[col] < b))} for (a, b), lab in zip(zip(edges[:-1], edges[1:]), labels)]
    return {"n": int(len(X)), "from": str(dates[int(X["i"].min())].date()), "to": str(dates[int(X["i"].max())].date()),
            "split": str(dates[split].date()), "all": tab2(X["i"] >= 0), "tiers": tiers,
            "by_streak": bucket("streak", [3, 6, 11, 21, 41, 1e9], ["3–5 sessions", "6–10", "11–20", "21–40", "41+"]),
            "by_depth": bucket("depth", [-9, -0.5, 0, 0.5, 1, 9], ["closed 0.5+ ADR through", "closed just through",
                                                                  "held, close within 0.5 ADR", "held 0.5–1 ADR off", "held 1+ ADR off (wick only)"]),
            "by_ema": [{"label": "9 EMA test", **tab2(X["ema"] == "9")}, {"label": "21 EMA test", **tab2(X["ema"] == "21")}]}


def live(F, side, P, theme_data=None):
    """Candidates for the page: leading-group stocks (weak-group for shorts) on the right side of the 9 or 21 EMA, within 1.5 ADR of
    it, with the numbers the browser needs to score a live test; plus tests in the last 3 sessions not yet triggered."""
    T = theme_data or {}
    stocks = {s["t"]: s for s in (T.get("stocks") or [])}
    i = len(F["c"]) - 1
    c, h, l, adr = (F[k].iloc[i] for k in ("c", "h", "l", "adr"))
    g = F["grp"].iloc[i]
    lead = (g >= CFG["lead"]) if side > 0 else (g <= 1 - CFG["lead"])
    thr = bool(F["thr"].iat[i])
    rows = {}
    for k, e in (("21", F["e21"].iloc[i]), ("9", F["e9"].iloc[i])):
        D = P[k]
        dist = side * (c - e) / (adr * c)
        ok = F["liq"].iloc[i] & lead.fillna(False) & (dist > 0) & (dist <= CFG["near"]) & (D["streak"].iloc[i] >= CFG["min_streak"] - 1)
        for t in ok[ok].index:
            if t in rows or t == config.BENCHMARK:
                continue
            rows[t] = {"t": t, "ema": k, "streak": int(D["streak"][t].iat[i]), "dist": _r(dist[t], 2)}
    # recent tests (official), not yet triggered
    recent = {}
    for k in ("21", "9"):
        D = P[k]
        for back in range(CFG["recent"]):
            ii = i - back
            m = D["first"].iloc[ii]
            for t in m[m].index:
                if t in recent or t == config.BENCHMARK:
                    continue
                trig = F["h"][t].iat[ii] if side > 0 else F["l"][t].iat[ii]
                later = F["h"][t].iloc[ii + 1:i + 1] if side > 0 else F["l"][t].iloc[ii + 1:i + 1]
                if len(later) and ((later >= trig).any() if side > 0 else (later <= trig).any()):
                    continue   # already triggered
                gg = F["grp"][t].iat[ii]
                ld = bool(np.isfinite(gg) and ((gg >= CFG["lead"]) if side > 0 else (gg <= 1 - CFG["lead"])))
                st, dp = D["before"][t].iat[ii], D["depth"][t].iat[ii]
                tr = tier(ld, bool(F["thr"].iat[ii]), st, dp)
                if tr == "E":
                    continue
                a = F["adr"][t].iat[ii]
                other = F["l"][t].iat[ii] if side > 0 else F["h"][t].iat[ii]
                stop = max(other, trig * (1 - a)) if side > 0 else min(other, trig * (1 + a))
                recent[t] = {"t": t, "ema": k, "ago": back, "date": str(F["c"].index[ii].date()), "streak": int(st), "depth": _r(dp, 2),
                             "tier": tr, "trig": _r(trig, 2), "stop": _r(stop, 2)}
    out = []
    for t, r in list(rows.items()) + [(t, None) for t in recent if t not in rows]:
        s = stocks.get(t) or {}
        j = F["c"].columns.get_loc(t)
        base = {"t": t, "name": (s.get("name") or "")[:40], "sub": s.get("sub") or F["sub_of"].get(t, ""), "rsr": s.get("rsr"),
                "grp": _r(F["grp"].iat[i, j], 2), "c": _r(F["c"].iat[i, j], 2), "hi": _r(F["h"].iat[i, j], 2), "lo": _r(F["l"].iat[i, j], 2),
                "e9": _r(F["e9"].iat[i, j], 3), "e21": _r(F["e21"].iat[i, j], 3), "adr": _r(F["adr"].iat[i, j], 4),
                "s9": int(P["9"]["streak"].iat[i, j]), "s21": int(P["21"]["streak"].iat[i, j]),
                "dvol": _r(F["dvol"].iat[i, j] / 1e6, 1)}
        if r:
            base.update({"near_ema": r["ema"], "dist": r["dist"]})
        if t in recent:
            base["test"] = recent[t]
        out.append(base)
    out.sort(key=lambda r: (0 if r.get("test") else 1, r.get("dist") if r.get("dist") is not None else 9))
    return out[:CFG["n_live"]], thr


def build(adjusted, theme_data=None, history=None, subthemes=None):
    if subthemes is None:
        try:
            from . import store
            subthemes = store.load_subthemes()
        except Exception:
            subthemes = None
    F = frames(adjusted, subthemes, history)
    if F is None:
        return None
    F["_np"] = tuple(F[k].to_numpy() for k in ("c", "o", "h", "l", "adr", "e10"))
    out = {"date": str(F["c"].index[-1].date()), "cfg": {k: CFG[k] for k in ("touch", "lead", "run", "held", "near", "target", "hold",
                                                                            "min_streak", "min_price", "min_dvol")},
           "tier_label": TIER_LABEL}
    for name, side in (("long", 1), ("short", -1)):
        P = _tests(F, side)
        ev = study(F, side, P)
        if ev is None:
            continue
        rows, thr = live(F, side, P, theme_data)
        out[name] = {"evidence": ev, "rows": rows, "thr": thr}
    return out


if __name__ == "__main__":
    from . import store
    b = store.load_bars()
    a = store.apply_splits(b, store.load_splits())
    try:
        hist = store.load_breadth()
    except Exception:
        hist = None
    X = build(a, None, hist)
    for side in ("long", "short"):
        E = X[side]["evidence"]
        print("==", side, E["from"], E["to"], "n", E["n"], "split", E["split"], "all", E["all"])
        for t in E["tiers"]:
            print("  ", t)
        for k in ("by_streak", "by_depth", "by_ema"):
            print("  ", k, [(b["label"], b["n"], b["win"], b["R"], b["h1"], b["h2"]) for b in E[k]])
        print("  live", len(X[side]["rows"]), "thr", X[side]["thr"], [(r["t"], r.get("test", {}).get("tier")) for r in X[side]["rows"][:12]])
