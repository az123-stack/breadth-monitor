"""Pick scoreboard: logs each morning's top picks and scores them 5 sessions later.

data/pick_ledger.csv, one row per pick:
  date, rank, t, setup, rsr, price (signal-day close), stop_pct (stop distance as a
  fraction of price), cands (all candidates the rule chose from, ';'-joined),
  then, once 5 sessions have passed: exit_date, ret (5-session close-to-close),
  stop_hit (low touched the stop within the 5 sessions), cand_ret (average 5-session
  return of all candidates that day - the benchmark the pick has to beat).
Returns are measured from the signal-day close for every setup, so picks are
comparable with each other and with the replay in trade_bt.pick_replay.
"""
import numpy as np
import pandas as pd

from . import config

HOLD = 5
COLS = ["date", "rank", "t", "setup", "rsr", "price", "stop_pct", "cands", "exit_date", "ret", "stop_hit", "cand_ret"]


def _path():
    return config.DATA_DIR / "pick_ledger.csv"


def load():
    p = _path()
    if not p.exists():
        return pd.DataFrame(columns=COLS)
    return pd.read_csv(p, dtype={"date": str, "exit_date": str, "cands": str})


def record(day, picks, cands):
    """Write today's picks (replacing any earlier rows for the same date)."""
    df = load()
    rows = [{"date": day, "rank": i + 1, "t": c["t"], "setup": c["setup"], "rsr": c.get("rsr"), "price": c.get("price"),
             "stop_pct": round((c.get("risk10k") or 0) / 10000, 4), "cands": ";".join(cands)} for i, c in enumerate(picks)]
    df = pd.concat([df[df["date"] != day], pd.DataFrame(rows, columns=COLS)], ignore_index=True)
    df = df.sort_values(["date", "rank"])
    df.to_csv(_path(), index=False)
    return df


def settle(adjusted, df=None):
    """Fill outcomes for picks whose 5 sessions have passed."""
    df = load() if df is None else df
    if df.empty:
        return df
    need = df["ret"].isna() if "ret" in df else pd.Series(True, index=df.index)
    if not need.any():
        return df
    for col in ("exit_date", "stop_hit"):
        df[col] = df[col].astype(object)
    for col in ("ret", "cand_ret"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    tick = set(df.loc[need, "t"])
    for cs in df.loc[need, "cands"].dropna():
        tick |= set(str(cs).split(";"))
    sub = adjusted[adjusted["ticker"].isin(tick)]
    c = sub.pivot(index="date", columns="ticker", values="c").sort_index()
    lo = sub.pivot(index="date", columns="ticker", values="l").sort_index().reindex_like(c)
    pos = {d.strftime("%Y-%m-%d"): i for i, d in enumerate(c.index)}

    def fwd(t, i):
        if t not in c.columns or i + HOLD >= len(c.index):
            return np.nan
        a, b = c[t].iloc[i], c[t].iloc[i + HOLD]
        return b / a - 1 if a and a == a and b == b else np.nan

    for k in df.index[need]:
        i = pos.get(df.at[k, "date"])
        if i is None or i + HOLD >= len(c.index):
            continue
        t = df.at[k, "t"]
        r = fwd(t, i)
        if r != r:
            continue
        df.at[k, "ret"] = round(r, 4)
        df.at[k, "exit_date"] = c.index[i + HOLD].strftime("%Y-%m-%d")
        st = float(df.at[k, "price"]) * (1 - float(df.at[k, "stop_pct"] or 0))
        df.at[k, "stop_hit"] = bool(t in lo.columns and lo[t].iloc[i + 1:i + HOLD + 1].min() <= st)
        cr = [fwd(x, i) for x in str(df.at[k, "cands"]).split(";") if x]
        cr = [x for x in cr if x == x]
        df.at[k, "cand_ret"] = round(float(np.mean(cr)), 4) if cr else np.nan
    df.to_csv(_path(), index=False)
    return df


def summary(adjusted=None, df=None):
    df = load() if df is None else df
    if df.empty:
        return {"n": 0, "closed": [], "open": []}
    closed = df[df["ret"].notna()]
    open_ = df[df["ret"].isna()]
    last = {}
    if adjusted is not None and len(open_):
        latest = adjusted[adjusted["date"] == adjusted["date"].max()].set_index("ticker")["c"]
        last = {t: float(latest[t]) for t in set(open_["t"]) if t in latest.index}

    def rec(r, now=None):
        o = {k: (None if (isinstance(v, float) and v != v) else v) for k, v in r.items() if k != "cands"}
        if now is not None and r.get("price"):
            o["now_ret"] = round(now / float(r["price"]) - 1, 4)
        return o

    out = {"n": int(len(closed)), "open": [rec(r, last.get(r["t"])) for r in open_.to_dict("records")][-6:],
           "closed": [rec(r) for r in closed.to_dict("records")][-30:][::-1]}
    if len(closed):
        rel = (closed["ret"] - closed["cand_ret"]).dropna()
        out.update({"avg_ret": round(float(closed["ret"].mean()), 4), "win": round(float((closed["ret"] > 0).mean()), 3),
                    "avg_cand": round(float(closed["cand_ret"].mean()), 4) if closed["cand_ret"].notna().any() else None,
                    "beat": round(float((rel > 0).mean()), 3) if len(rel) else None,
                    "pnl10k": round(float(closed["ret"].sum() * 10000)),
                    "stops": round(float(closed["stop_hit"].astype(str).str.lower().eq("true").mean()), 3)})
    return out
