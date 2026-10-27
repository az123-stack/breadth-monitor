"""Top late mover study (Adam, Oct 27 2026: "top stock pick after the morning window sounds great").

Question: once the opening rush settles, does the strongest stock since 10:00 ET keep going?
    python tools/late_mover/study.py --bars <folder with the orb-data branch parquet parts>

Data: 15-minute regular-session bars (orb-data branch, ~700 liquid sub-theme stocks + SPY, Oct 2024 - Oct 2026) and the stored
daily bars for everything known BEFORE the day (ADR, 50-day $ volume, RS Rating, sub-theme 13-week rank, 20-day intraday volume norm).

Rules (no look-ahead):
- Anchor = price at 10:00 ET (close of the 9:45 bar). Decision at D = 11:00 or 12:00 ET (close of the bar ending then).
- Candidates: $5+, 50-day avg $ volume >= $20M (prior session), up >= 1% since 10:00 AND beating SPY since 10:00.
- Volume since vs normal = volume 10:00 -> D / the stock's average volume over the same window on the prior 20 sessions.
- Score = move since 10:00 in ADRs. Filters tested: RS 80+, group (sub-theme top third on 13-week equal-weight return), rv >= 1.5.
- Entry = open of the next bar after D. Stop = the day's low up to D. R risk floored at 0.3 ADR. Exits:
  "close" = stop (bar lows) or today's close; "next" = stop intraday, else tomorrow's close (daily low checked);
  "5d" = stop (intraday, then daily lows) or the close 4 sessions after entry day. Costs 0.10% round trip.
Units: per day, the #1 pick vs the average candidate and vs the average liquid stock (same entry/exit), paired by date; t and halves.
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from breadth import store, strength  # noqa: E402

COST = 0.001
ANCHOR_M = 15            # bar starting 9:45 -> close = 10:00
DEC = {"11:00": 75, "12:00": 135}   # bar starting 10:45 / 11:45 -> close = 11:00 / 12:00


def daily_context(tickers):
    b = store.apply_splits(store.load_bars(), store.load_splits())
    w = strength.wide_all(b)
    c, h, l, v = w["c"], w["h"], w["l"], w["v"]
    adr = (((h / l) - 1).rolling(20, min_periods=15).mean()).shift()           # known before the day
    dvol = (c * v).rolling(50, min_periods=30).mean().shift()
    raw = strength.rs_raw(c)
    liq = (c.shift() >= 5) & (dvol >= 20e6)
    rs = (raw.where(liq).rank(axis=1, pct=True) * 99).shift()
    sd = store.load_subthemes()
    mem = sd.groupby("subtheme")["ticker"].apply(list).to_dict()
    ret = (c / c.shift() - 1).clip(-0.6, 3)
    idx = pd.DataFrame({g: (1 + ret[[x for x in t if x in c.columns]].mean(axis=1).fillna(0)).cumprod()
                        for g, t in mem.items() if len([x for x in t if x in c.columns]) >= 3})
    grank = (idx / idx.shift(65) - 1).rank(axis=1, pct=True).shift()
    sub_of = sd.drop_duplicates("ticker").set_index("ticker")["subtheme"].to_dict()
    lmin1 = l.shift(-1)                                                      # tomorrow's low
    lmin5 = l[::-1].rolling(5, min_periods=1).min()[::-1].shift(-1)          # lowest low of the next 5 sessions
    return {"c": c, "l": l, "adr": adr, "liq": liq, "rs": rs, "grank": grank, "sub_of": sub_of,
            "c1": c.shift(-1), "c5": c.shift(-5), "lmin1": lmin1, "lmin5": lmin5}


def run(bars_dir):
    B = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(os.path.join(bars_dir, "part_*.parquet")))])
    B["date"] = pd.to_datetime(B["date"])
    D = daily_context(B["ticker"].unique())
    days = sorted(B["date"].unique())
    piv = {k: B.pivot_table(index=["date", "m"], columns="ticker", values=k) for k in ("o", "h", "l", "c", "v")}
    # per-day matrices: rows = 15-min slot index 0..25
    out = {d: [] for d in DEC}
    vol_hist = {d: [] for d in DEC}          # rolling 20-session intraday volume norms
    dcl = D["c"]
    for di, day in enumerate(days):
        try:
            O, H, L, C, V = (piv[k].xs(day, level="date") for k in ("o", "h", "l", "c", "v"))
        except KeyError:
            continue
        if ANCHOR_M not in C.index or "SPY" not in C.columns:
            continue
        cday = pd.Timestamp(day)
        if cday not in dcl.index:
            continue
        di_d = dcl.index.get_loc(cday)
        for dk, dm in DEC.items():
            if dm not in C.index:
                continue
            win = (V.index > ANCHOR_M) & (V.index <= dm)
            vsince = V[win].sum()
            hist = vol_hist[dk]
            norm = pd.concat(hist[-20:], axis=1).mean(axis=1) if len(hist) >= 10 else None
            hist.append(vsince)
            a = C.loc[ANCHOR_M]
            p = C.loc[dm]
            since = p / a - 1
            spy = since.get("SPY", np.nan)
            low_so_far = L[L.index <= dm].min()
            nxt = [m for m in C.index if m > dm]
            if not nxt or not np.isfinite(spy):
                continue
            entry = O.loc[nxt[0]]
            rest_low = L[L.index > dm].min()
            close = C.iloc[-1]
            adr = D["adr"].iloc[di_d]
            liq = D["liq"].iloc[di_d]
            rs = D["rs"].iloc[di_d]
            gr = D["grank"].iloc[di_d]
            tick = [t for t in C.columns if t != "SPY" and bool(liq.get(t, False)) and np.isfinite(entry.get(t, np.nan))
                    and np.isfinite(adr.get(t, np.nan)) and adr.get(t) > 0]
            if len(tick) < 50:
                continue
            tk = pd.Index(tick)
            e, lo = entry[tk], low_so_far[tk]
            A = adr[tk]
            risk = np.maximum(e - lo, 0.3 * A * e)
            stop = e - risk
            hit0 = rest_low[tk] <= stop
            cost = COST * e / risk
            Rc = np.where(hit0, -risk, close[tk] - e) / risk - cost
            def fwd(cl, lm):
                cl, lm = D[cl].iloc[di_d].reindex(tk), D[lm].iloc[di_d].reindex(tk)
                r = np.where(hit0 | (lm <= stop), -risk, cl - e)
                return pd.Series(r, index=tk).where(cl.notna()) / risk - cost
            subs = pd.Series([D["sub_of"].get(t) for t in tk], index=tk)
            df = pd.DataFrame({"t": tk, "since": since[tk].values, "rel": (since[tk] - spy).values, "adrx": (since[tk] / A).values,
                               "rv": ((vsince[tk] / norm.reindex(tk)).values if norm is not None else np.nan),
                               "rs": rs.reindex(tk).values, "grp": subs.map(lambda g: gr.get(g, np.nan) if g else np.nan).values,
                               "Rc": Rc.values, "Rn": fwd("c1", "lmin1").values, "R5": fwd("c5", "lmin5").values})
            df["date"] = cday
            out[dk].append(df)
    return {k: pd.concat(v, ignore_index=True) for k, v in out.items() if v}


def _t(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return round(float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))), 2) if len(x) > 3 and x.std(ddof=1) > 0 else None


def evaluate(df, mask_name, mask):
    """Per day: #1 by adrx among candidates passing `mask` vs avg candidate (same mask) and vs avg liquid stock."""
    res = {}
    cand = df[(df["since"] >= 0.01) & (df["rel"] > 0) & mask]
    for col in ("Rc", "Rn", "R5"):
        top = cand.sort_values("adrx", ascending=False).groupby("date").head(1).set_index("date")[col]
        avgc = cand.groupby("date")[col].mean()
        allr = df.groupby("date")[col].mean()
        j = top.index
        e1, e2 = (top - avgc.reindex(j)).dropna(), (top - allr.reindex(j)).dropna()
        h = len(e1) // 2
        res[col] = {"n_days": int(top.notna().sum()), "pick": round(float(top.mean()), 3), "avg_cand": round(float(avgc.reindex(j).mean()), 3),
                    "all": round(float(allr.reindex(j).mean()), 3), "edge_vs_cand": round(float(e1.mean()), 3), "t_cand": _t(e1),
                    "halves_cand": [round(float(e1.iloc[:h].mean()), 3), round(float(e1.iloc[h:].mean()), 3)],
                    "edge_vs_all": round(float(e2.mean()), 3), "t_all": _t(e2), "win": round(float((top > 0).mean()), 2)}
    return {mask_name: res}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    R = run(a.bars)
    report = {}
    for dk, df in R.items():
        rep = {}
        T = pd.Series(True, index=df.index)
        rep.update(evaluate(df, "any", T))
        rep.update(evaluate(df, "rs80", df["rs"] >= 80))
        rep.update(evaluate(df, "group", df["grp"] >= 2 / 3))
        rep.update(evaluate(df, "rv1.5", df["rv"] >= 1.5))
        rep.update(evaluate(df, "rs80+group", (df["rs"] >= 80) & (df["grp"] >= 2 / 3)))
        rep.update(evaluate(df, "rs80+group+rv", (df["rs"] >= 80) & (df["grp"] >= 2 / 3) & (df["rv"] >= 1.5)))
        report[dk] = rep
        df.to_parquet(f"/tmp/late_{dk.replace(':', '')}.parquet")
    print(json.dumps(report, indent=1))
    if a.out:
        json.dump(report, open(a.out, "w"), indent=1)
