"""EMA touch odds (Oct 29, 2026; Adam: "pick a time frame like 1 month; if the % of time spent over the 9/21 is like 80% and it's
going into the 9/21 right now it's likely going to bounce ... 80/90% over 30 days and it's about to make its first touch ... then
measure the second touch". Same thing on the short side.)

For every liquid stock ($5+, $20M+/day) and each EMA (9, 21):
  time above = share of the last 30 closes above that EMA (below, for shorts)
  touch      = the low comes within 0.25 ADR of the EMA (or through it) after closing above it the day before; a new touch needs 3+
               sessions since the last; a 9 touch that also reaches the 21 counts as a 21 touch
  touch #    = 1 + touches of that EMA in the 30 sessions before (1st, 2nd, 3rd+)
What happened next (first to happen within 10 sessions):
  BOUNCE = a close above the touch-day high + 0.5 ADR;  FAIL = a close more than 0.5 ADR through the EMA;  else chop
and the trade: buy the break of the touch-day high within 3 sessions, stop the touch-day low (max 1 ADR, risk floored at 0.3 ADR),
win = +2R first within 20 sessions; R after 20 sessions (capped 10R) and Adam's exit (first close under the 10 EMA).
Couplings: leading group (sub-theme top 30% on 60-day return; bottom 30% for shorts), post-thrust window.

The tables are re-run every build; the page (`emaTouchCard`) looks up today's names in them (`touchLabel` / `band` are the same
rules as the page's `etBand` / `etTouch`).
"""
import numpy as np
import pandas as pd

from . import config

CFG = dict(min_price=5.0, min_dvol=20e6, touch=0.25, space=3, win=30, look=10, bounce=0.5, fail=0.5, trig_days=3, hold=20,
           target=2.0, floor=0.3, warm=260, lead=0.7, hi=0.8, near=1.5, n_live=150)
BANDS = [(-0.01, 0.5, "<50%"), (0.5, 0.7, "50–70%"), (0.7, 0.8, "70–80%"), (0.8, 0.9, "80–90%"), (0.9, 1.01, "90%+")]
TOUCHES = ["1st", "2nd", "3rd+"]


def _r(x, n=3):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, n) if np.isfinite(x) else None


def band(p):
    for a, b, lab in BANDS:
        if a < p <= b or (a == -0.01 and p <= b):
            return lab
    return BANDS[-1][2]


def touch_label(prior):
    return TOUCHES[min(int(prior), 2)]


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


def _touches(F, side):
    """Per EMA: spaced touch mask, share of the prior 30 closes on the right side, touches in the prior 30 sessions."""
    c, h, l, adr = F["c"], F["h"], F["l"], F["adr"]
    out = {}
    for k in ("9", "21"):
        e = F["e" + k]
        right = (c > e) if side > 0 else (c < e)
        reach = (l <= e + CFG["touch"] * adr * c) if side > 0 else (h >= e - CFG["touch"] * adr * c)
        if k == "9":
            reach = reach & ((l > F["e21"] + CFG["touch"] * adr * c) if side > 0 else (h < F["e21"] - CFG["touch"] * adr * c))
        t = F["liq"] & right.shift(1, fill_value=False) & reach
        sp = t & ~t.shift(1, fill_value=False).rolling(CFG["space"], min_periods=1).max().astype(bool)
        pct_now = right.astype(float).rolling(CFG["win"], min_periods=CFG["win"]).mean()     # incl. today
        cnt_now = sp.astype(float).rolling(CFG["win"], min_periods=1).sum()
        out[k] = dict(sp=sp, right=right, pct=pct_now.shift(1), prior=cnt_now.shift(1).fillna(0), pct_now=pct_now, cnt_now=cnt_now,
                      depth=side * (c - e) / (adr * c))
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


def _outcome(F, i, j, side, e):
    c, h, l, adr = F["_np"][0], F["_np"][2], F["_np"][3], F["_np"][4]
    a = adr[i, j]
    for m in range(i + 1, min(i + 1 + CFG["look"], c.shape[0])):
        if side > 0:
            if c[m, j] > h[i, j] + CFG["bounce"] * a * c[i, j]:
                return "bounce"
            if c[m, j] < e[m, j] - CFG["fail"] * a * c[m, j]:
                return "fail"
        else:
            if c[m, j] < l[i, j] - CFG["bounce"] * a * c[i, j]:
                return "bounce"
            if c[m, j] > e[m, j] + CFG["fail"] * a * c[m, j]:
                return "fail"
    return "chop"


def _events(F, side, P):
    rows = []
    n = len(F["c"])
    grp, thr = F["grp"].to_numpy(), F["thr"].to_numpy()
    for k in ("9", "21"):
        D = P[k]
        e = F["e" + k].to_numpy()
        pct, prior, dep = D["pct"].to_numpy(), D["prior"].to_numpy(), D["depth"].to_numpy()
        ii, jj = np.nonzero(D["sp"].to_numpy())
        for i, j in zip(ii, jj):
            if i < CFG["warm"] or i + CFG["trig_days"] + CFG["hold"] >= n or not np.isfinite(pct[i, j]):
                continue
            a = F["_np"][4][i, j]
            if not (np.isfinite(a) and a > 0):
                continue
            tr = _trade(F, i, j, side)
            g = grp[i, j]
            rows.append((k, i, pct[i, j], int(prior[i, j]), _outcome(F, i, j, side, e), *(tr or (np.nan, np.nan, np.nan)),
                         bool(np.isfinite(g) and ((g >= CFG["lead"]) if side > 0 else (g <= 1 - CFG["lead"]))), bool(thr[i]), dep[i, j]))
    X = pd.DataFrame(rows, columns=["ema", "i", "pct", "prior", "res", "win", "R", "Rk", "lead", "thr", "depth"])
    X["band"] = [band(p) for p in X["pct"]]
    X["touch"] = [touch_label(p) for p in X["prior"]]
    return X


def _stat(x, half):
    if not len(x):
        return {"n": 0}
    t = x.dropna(subset=["win"])
    h1, h2 = x[half[x.index]], x[~half[x.index]]
    return {"n": int(len(x)), "bounce": _r((x["res"] == "bounce").mean()), "fail": _r((x["res"] == "fail").mean()),
            "traded": int(len(t)), "win": _r(t["win"].mean()), "R": _r(t["R"].mean()), "Rk": _r(t["Rk"].mean()),
            "b1": _r((h1["res"] == "bounce").mean()), "b2": _r((h2["res"] == "bounce").mean()),
            "R1": _r(h1["R"].mean()), "R2": _r(h2["R"].mean())}


def study(F, side, P):
    X = _events(F, side, P)
    if len(X) < 200:
        return None
    dates = F["c"].index
    split = int(X["i"].median())
    half = X["i"] < split
    out = {"n": int(len(X)), "from": str(dates[int(X["i"].min())].date()), "to": str(dates[int(X["i"].max())].date()),
           "split": str(dates[split].date()), "ema": {}}
    for k in ("21", "9"):
        Y = X[X["ema"] == k]
        cell = {b: {t: _stat(Y[(Y["band"] == b) & (Y["touch"] == t)], half) for t in TOUCHES} for _, _, b in BANDS}
        rowall = {b: _stat(Y[Y["band"] == b], half) for _, _, b in BANDS}
        hi = Y[Y["pct"] >= CFG["hi"]]
        coupled = {t: {"all": _stat(hi[hi["touch"] == t], half), "lead": _stat(hi[(hi["touch"] == t) & hi["lead"]], half),
                       "lead_thr": _stat(hi[(hi["touch"] == t) & hi["lead"] & hi["thr"]], half),
                       "held": _stat(hi[(hi["touch"] == t) & (hi["depth"] >= 0)], half)} for t in TOUCHES}
        out["ema"][k] = {"all": _stat(Y, half), "cell": cell, "band": rowall, "coupled": coupled}
    return out


def live(F, side, P, theme_data=None):
    """Names on the right side of the 9 or 21 EMA with 70%+ of the last 30 closes there, touching at the last close or within 1.5 ADR
    of the EMA; with what the page needs to score a live touch."""
    T = theme_data or {}
    stocks = {s["t"]: s for s in (T.get("stocks") or [])}
    i = len(F["c"]) - 1
    out = {}
    for k in ("21", "9"):
        D = P[k]
        e = F["e" + k].iloc[i]
        c, a = F["c"].iloc[i], F["adr"].iloc[i]
        dist = side * (c - e) / (a * c)
        touched = D["sp"].iloc[i]
        pct_prior, prior = D["pct"].iloc[i], D["prior"].iloc[i]          # for a touch TODAY (at the last close)
        pct_now, cnt_now = D["pct_now"].iloc[i], D["cnt_now"].iloc[i]    # for a touch NEXT session
        ok_t = F["liq"].iloc[i] & touched & (pct_prior >= 0.7)
        ok_n = F["liq"].iloc[i] & ~touched & (dist > 0) & (dist <= CFG["near"]) & (pct_now >= 0.7)
        for t in list(ok_t[ok_t].index) + list(ok_n[ok_n].index):
            if t == config.BENCHMARK or (t in out and out[t].get("state") == "touched"):
                continue
            tch = bool(touched.get(t, False))
            r = {"ema": k, "state": "touched" if tch else "near", "pct": _r(pct_prior[t] if tch else pct_now[t], 3),
                 "touch": touch_label(prior[t] if tch else cnt_now[t]), "dist": _r(dist[t], 2), "depth": _r(D["depth"][t].iat[i], 2)}
            if t not in out or (tch and out[t].get("state") != "touched"):
                out[t] = r
    rows = []
    for t, r in out.items():
        j = F["c"].columns.get_loc(t)
        s = stocks.get(t) or {}
        g = F["grp"].iat[i, j]
        lead = bool(np.isfinite(g) and ((g >= CFG["lead"]) if side > 0 else (g <= 1 - CFG["lead"])))
        a = F["adr"].iat[i, j]
        hi, lo = F["h"].iat[i, j], F["l"].iat[i, j]
        trig, stop = (hi, max(lo, hi * (1 - a))) if side > 0 else (lo, min(hi, lo * (1 + a)))
        rows.append({"t": t, "name": (s.get("name") or "")[:40], "sub": s.get("sub") or F["sub_of"].get(t, ""), "rsr": s.get("rsr"),
                     "lead": lead, "grp": _r(g, 2), **r, "c": _r(F["c"].iat[i, j], 2), "hi": _r(hi, 2), "lo": _r(lo, 2),
                     "e9": _r(F["e9"].iat[i, j], 3), "e21": _r(F["e21"].iat[i, j], 3), "adr": _r(a, 4),
                     "trig": _r(trig, 2) if r["state"] == "touched" else None, "stop": _r(stop, 2) if r["state"] == "touched" else None,
                     "dvol": _r(F["dvol"].iat[i, j] / 1e6, 1)})
    rows.sort(key=lambda r: (r["state"] != "touched", -(r["pct"] or 0), r["dist"] if r["dist"] is not None else 9))
    return rows[:CFG["n_live"]]


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
    out = {"date": str(F["c"].index[-1].date()), "cfg": {k: CFG[k] for k in ("touch", "win", "look", "bounce", "fail", "hi", "lead", "near",
                                                                            "target", "hold", "min_price", "min_dvol")},
           "bands": [b for _, _, b in BANDS], "touches": TOUCHES, "thr": bool(F["thr"].iat[-1])}
    for name, side in (("long", 1), ("short", -1)):
        P = _touches(F, side)
        ev = study(F, side, P)
        if ev is None:
            continue
        out[name] = {"evidence": ev, "rows": live(F, side, P, theme_data)}
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
    f = lambda o: f"n {o.get('n')} bounce {o.get('bounce')} fail {o.get('fail')} win {o.get('win')} R {o.get('R')} b {o.get('b1')}/{o.get('b2')} R {o.get('R1')}/{o.get('R2')}"
    for side in ("long", "short"):
        if side not in X:
            continue
        E = X[side]["evidence"]
        print("=====", side, E["from"], E["to"], E["n"])
        for k, V in E["ema"].items():
            print(" EMA", k, "all:", f(V["all"]))
            for bnd in X["bands"]:
                print("   ", bnd, "|", " | ".join(t + " " + f(V["cell"][bnd][t]) for t in TOUCHES[:2]))
            for t in TOUCHES:
                print("   80%+", t, {kk: (v.get("n"), v.get("bounce"), v.get("R"), v.get("R1"), v.get("R2")) for kk, v in V["coupled"][t].items()})
        print(" live", len(X[side]["rows"]), [(r["t"], r["ema"], r["state"], r["touch"], r["pct"]) for r in X[side]["rows"][:8]])
