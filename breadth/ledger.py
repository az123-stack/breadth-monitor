"""Pick scoreboard: logs each morning's top picks and scores them the way they'd be traded.

data/pick_ledger.csv, one row per pick. Picks are made from the prior close (the
dashboard updates before the open), so the trade starts the next session:
  entry   'open' setups (ATH Magnet, Pullback, Rotation) buy that session's open;
          'trigger' setups (Qullamaggie Flag, VCP) buy only if that session trades
          through the trigger, filled at max(trigger, open) - otherwise 'no fill'.
  stop    1 ADR below the fill (open setups), the entry day's low (flag), or the
          VCP stop; if a later low touches it, exit at the stop (or the open if it
          gaps through).
  exit    the close 5 sessions after entry.
  ret         result with the stop; ret_nostop  same entry, held 5 sessions.
  cand_ret    the average candidate that day bought at the same next open and held
              5 sessions - the benchmark for ret_nostop (did the rule pick better
              than picking at random from the same list?).
"""
import numpy as np
import pandas as pd

from . import config

HOLD = 5
COLS = ["date", "rank", "t", "setup", "rsr", "price", "entry_type", "trigger", "stop_pct", "vcp_stop", "cands",
        "status", "entry", "exit_date", "ret", "ret_nostop", "stop_hit", "cand_ret"]


def _path():
    return config.DATA_DIR / "pick_ledger.csv"


def load():
    p = _path()
    if not p.exists():
        return pd.DataFrame(columns=COLS)
    df = pd.read_csv(p, dtype={"date": str, "exit_date": str, "cands": str, "status": str, "entry_type": str})
    for c in COLS:
        if c not in df.columns:
            df[c] = np.nan
    return df[COLS]


def record(day, picks, cands):
    """Write today's picks (replacing earlier rows for the same date)."""
    df = load()
    rows = [{"date": day, "rank": i + 1, "t": c["t"], "setup": c["setup"], "rsr": c.get("rsr"), "price": c.get("price"),
             "entry_type": c.get("entry_type", "open"), "trigger": c.get("trigger"),
             "stop_pct": round((c.get("adr") or 0) / 100, 4), "vcp_stop": c.get("vcp_stop"),
             "cands": ";".join(cands), "status": "pending"} for i, c in enumerate(picks)]
    df = pd.concat([df[df["date"] != day], pd.DataFrame(rows, columns=COLS)], ignore_index=True)
    df = df.sort_values(["date", "rank"])
    df.to_csv(_path(), index=False)
    return df


def _wide(adjusted, tickers):
    sub = adjusted[adjusted["ticker"].isin(tickers)]
    piv = lambda k: sub.pivot(index="date", columns="ticker", values=k).sort_index()
    c = piv("c")
    return {k: (c if k == "c" else piv(k).reindex_like(c)) for k in ("o", "h", "l", "c")}


def settle(adjusted, df=None):
    """Fill in entries and outcomes as sessions pass."""
    df = load() if df is None else df
    if df.empty:
        return df
    todo = ~df["status"].isin(["closed", "no fill"])
    if not todo.any():
        return df
    for col in ("exit_date", "stop_hit", "status", "entry_type"):
        df[col] = df[col].astype(object)
    for col in ("ret", "ret_nostop", "cand_ret", "entry", "trigger", "vcp_stop", "stop_pct", "price"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    tick = set(df.loc[todo, "t"])
    for cs in df.loc[todo, "cands"].dropna():
        tick |= set(str(cs).split(";"))
    W = _wide(adjusted, tick)
    O, H, L, C = W["o"], W["h"], W["l"], W["c"]
    idx = C.index
    pos = {d.strftime("%Y-%m-%d"): i for i, d in enumerate(idx)}
    n = len(idx)
    for k in df.index[todo]:
        i = pos.get(df.at[k, "date"])
        t = df.at[k, "t"]
        if i is None or t not in C.columns or i + 1 >= n:
            continue
        e_i = i + 1
        trig = df.at[k, "trigger"]
        if df.at[k, "entry_type"] == "trigger" and trig == trig and trig:
            tp = trig * 1.001
            if not H[t].iloc[e_i] >= tp:
                df.at[k, "status"] = "no fill"
                continue
            e = max(tp, O[t].iloc[e_i])
        else:
            e = O[t].iloc[e_i]
        if not (e == e and e > 0):
            continue
        df.at[k, "entry"] = round(float(e), 4)
        if df.at[k, "setup"] == "kq":
            stop = float(L[t].iloc[e_i])
        elif df.at[k, "setup"] == "vcp" and df.at[k, "vcp_stop"] == df.at[k, "vcp_stop"]:
            stop = float(df.at[k, "vcp_stop"])
        else:
            stop = e * (1 - float(df.at[k, "stop_pct"] or 0))
        if e_i + HOLD >= n:
            df.at[k, "status"] = "open"
            continue
        x, hit = None, False
        for q in range(e_i + 1, e_i + HOLD + 1):
            if L[t].iloc[q] <= stop:
                x, hit = min(stop, O[t].iloc[q]), True
                break
        close5 = C[t].iloc[e_i + HOLD]
        x = close5 if x is None else x
        df.at[k, "ret"] = round(float(x / e - 1), 4)
        df.at[k, "ret_nostop"] = round(float(close5 / e - 1), 4)
        df.at[k, "stop_hit"] = hit
        df.at[k, "exit_date"] = idx[e_i + HOLD].strftime("%Y-%m-%d")
        df.at[k, "status"] = "closed"
        cr = []
        for x_ in str(df.at[k, "cands"]).split(";"):
            if x_ in C.columns:
                a, b = O[x_].iloc[e_i], C[x_].iloc[e_i + HOLD]
                if a == a and b == b and a > 0:
                    cr.append(b / a - 1)
        df.at[k, "cand_ret"] = round(float(np.mean(cr)), 4) if cr else np.nan
    df.to_csv(_path(), index=False)
    return df


def summary(adjusted=None, df=None):
    df = load() if df is None else df
    if df.empty:
        return {"n": 0, "closed": [], "open": [], "no_fill": 0}
    closed = df[df["status"] == "closed"].copy()
    live = df[df["status"].isin(["pending", "open"])]
    nofill = df[df["status"] == "no fill"]
    last = {}
    if adjusted is not None and len(live):
        latest = adjusted[adjusted["date"] == adjusted["date"].max()].set_index("ticker")["c"]
        last = {t: float(latest[t]) for t in set(live["t"]) if t in latest.index}

    def rec(r):
        o = {k: (None if (isinstance(v, float) and v != v) else v) for k, v in r.items() if k != "cands"}
        if o.get("status") == "open" and o.get("entry") and r["t"] in last:
            o["now_ret"] = round(last[r["t"]] / float(o["entry"]) - 1, 4)
        return o

    out = {"n": int(len(closed)), "no_fill": int(len(nofill)),
           "open": [rec(r) for r in live.to_dict("records")][-6:],
           "closed": [rec(r) for r in pd.concat([closed, nofill]).sort_values("date").to_dict("records")][-30:][::-1]}
    if len(closed):
        for c in ("ret", "ret_nostop", "cand_ret"):
            closed[c] = pd.to_numeric(closed[c], errors="coerce")
        rel = (closed["ret_nostop"] - closed["cand_ret"]).dropna()
        out.update({"avg_ret": round(float(closed["ret"].mean()), 4), "win": round(float((closed["ret"] > 0).mean()), 3),
                    "avg_nostop": round(float(closed["ret_nostop"].mean()), 4),
                    "avg_cand": round(float(closed["cand_ret"].mean()), 4) if closed["cand_ret"].notna().any() else None,
                    "beat": round(float((rel > 0).mean()), 3) if len(rel) else None,
                    "pnl10k": round(float(closed["ret"].sum() * 10000)),
                    "stops": round(float(closed["stop_hit"].astype(str).str.lower().eq("true").mean()), 3)})
    return out
