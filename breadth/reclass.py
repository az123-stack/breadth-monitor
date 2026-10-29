"""Theme upkeep: find tickers that may need (re)classifying in data/subthemes.csv / data/themes.csv (Adam, Oct 28 2026).

Code measures, the agent reads, Adam decides (same rule as DECISIONS.md). Each build computes a worklist into
DATA.themes.reclass; the weekly "Market Monitor · reclass agent" researches it and publishes PROPOSALS only
(docs/agent/reclass.json via `python -m breadth.agentfiles publish --kind reclass`). Nothing moves until Adam says
"apply reclass N, M" and a session runs `python -m breadth.reclass apply --ids N,M`.

The worklist has four parts:
  unclassified  liquid common stocks in no sub-theme that matter (RS 80+ or $100M+/day), with the 3 sub-themes they
                trade most like (correlation of daily returns minus SPY over 120 sessions) as a starting point
  poor_fit      sub-theme members that barely move with their own group (correlation to the group's other members)
                while another group fits clearly better
  stale         tickers in the theme files with no trading data in the last 5 sessions (delisted, renamed, acquired)
  thin          sub-themes with fewer than 3 liquid members (merge or fill)
Tickers Adam already decided on (data/reclass_log.csv) stay off the worklist for 90 days.

    python -m breadth.reclass worklist            # what the agent researches (reads docs/index.html; stdlib only)
    python -m breadth.reclass list                # numbered proposals from docs/agent/reclass.json + their status
    python -m breadth.reclass apply --ids 1,3     # apply approved proposals to the theme files and log them
    python -m breadth.reclass reject --ids 2      # log a "no" so the ticker isn't proposed again for 90 days
"""
import argparse
import csv
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUB_FILE = ROOT / "data" / "subthemes.csv"
THEME_FILE = ROOT / "data" / "themes.csv"
LOG_FILE = ROOT / "data" / "reclass_log.csv"
PROPOSALS = ROOT / "docs" / "agent" / "reclass.json"
LOG_COLS = ["date", "id", "t", "action", "from", "to", "theme_add", "status", "why"]

CFG = {"look": 120, "min_price": 5.0, "min_dv": 10e6, "rs_min": 80, "big_dv": 100e6, "n_unclass": 40, "n_poor": 30,
       "own_low": 0.25, "gap": 0.20, "best_min": 0.35, "very_low": 0.10, "stale_days": 5, "quiet_days": 90, "min_liquid": 3}


# ---------------------------------------------------------------------------
# Build (runs inside the daily update; needs pandas / numpy)
# ---------------------------------------------------------------------------
def _decided(today):
    """Tickers with a logged decision in the last CFG['quiet_days'] days."""
    out = set()
    if not LOG_FILE.exists():
        return out
    cut = (today - timedelta(days=CFG["quiet_days"])).isoformat()
    with open(LOG_FILE) as f:
        for r in csv.DictReader(f):
            if (r.get("date") or "") >= cut:
                out.add((r.get("t") or "").upper())
    return out


def build(adjusted, universe, subthemes_df, themes_df, names=None):
    import numpy as np
    import pandas as pd
    from . import config, strength

    names = names or {}
    c = adjusted.pivot(index="date", columns="ticker", values="c").sort_index().astype("float64")
    v = adjusted.pivot(index="date", columns="ticker", values="v").sort_index().astype("float64").reindex_like(c)
    last_day = c.index[-1]
    today = pd.Timestamp(last_day).date()
    L = CFG["look"]
    if config.BENCHMARK not in c.columns or len(c) < L + 2:
        return None
    ret = c.pct_change().iloc[-L:]
    ex = ret.sub(ret[config.BENCHMARK], axis=0)                  # market removed
    dv = (c * v).iloc[-50:].mean()
    px = c.iloc[-1]
    full = ret.notna().sum() >= L - 5
    raw = strength.rs_raw(c).iloc[-1]
    liquid = (px >= CFG["min_price"]) & (dv >= CFG["min_dv"]) & full
    pool = raw[liquid & raw.notna()]
    rs = pd.Series(np.nan, index=raw.index)
    if len(pool) >= 50:
        bp = np.percentile(pool.to_numpy(), np.arange(1, 100))
        rs = pd.Series(np.clip(np.searchsorted(bp, raw.to_numpy(), side="right"), 1, 99).astype(float), index=raw.index)
        rs[raw.isna()] = np.nan

    sub_of = dict(zip(subthemes_df["ticker"], subthemes_df["subtheme"]))
    grp_of = dict(zip(subthemes_df["subtheme"], subthemes_df["group"]))
    members = {}
    for t, s in sub_of.items():
        members.setdefault(s, []).append(t)

    # standardized excess returns of liquid, fully-traded stocks
    ok = [t for t in ex.columns if bool(full.get(t, False)) and t != config.BENCHMARK]
    X = ex[ok].fillna(0.0)
    Z = (X - X.mean()) / X.std(ddof=0).replace(0, np.nan)
    Z = Z.fillna(0.0)
    groups, G, S, N = [], [], [], []
    for s, ms in members.items():
        m = [t for t in ms if t in Z.columns]
        if len(m) < 2:
            continue
        groups.append(s)
        S.append(X[m].sum(axis=1).to_numpy())                     # raw sums, to rebuild "others" without the stock
        N.append(len(m))
    if not groups:
        return None
    S = np.column_stack(S)
    N = np.array(N, dtype=float)
    Gm = S / N                                                   # equal-weight group index (excess)
    Gz = (Gm - Gm.mean(0)) / np.where(Gm.std(0) == 0, np.nan, Gm.std(0))
    Gz = np.nan_to_num(Gz)
    n = len(X)
    gi = {g: k for k, g in enumerate(groups)}

    def corr_all(t):
        return (Z[t].to_numpy() @ Gz) / n

    def corr_own(t, s):
        k = gi[s]
        if N[k] < 3:
            return None
        others = (S[:, k] - X[t].to_numpy()) / (N[k] - 1)
        sd = others.std()
        if sd == 0:
            return None
        return float(((others - others.mean()) / sd) @ Z[t].to_numpy() / n)

    decided = _decided(today)
    out = {"date": today.isoformat(), "cfg": CFG, "unclassified": [], "poor_fit": [], "stale": [], "thin": []}

    # 1) unclassified liquid common stocks that matter
    for t in ok:
        if t in sub_of or t not in universe or t in decided or not bool(liquid.get(t, False)):
            continue
        r = rs.get(t)
        if not ((r is not None and r >= CFG["rs_min"]) or dv.get(t, 0) >= CFG["big_dv"]):
            continue
        cc = corr_all(t)
        top = np.argsort(-cc)[:3]
        out["unclassified"].append({"t": t, "name": names.get(t, ""), "rs": None if pd.isna(r) else int(r),
                                    "dv": round(float(dv[t]) / 1e6, 1), "price": round(float(px[t]), 2),
                                    "cand": [[groups[k], round(float(cc[k]), 2)] for k in top]})
    out["unclassified"].sort(key=lambda x: (-(x["rs"] or 0), -x["dv"]))
    out["unclassified"] = out["unclassified"][:CFG["n_unclass"]]

    # 2) members that barely trade with their own group while another group fits clearly better
    poor = []
    for t, s in sub_of.items():
        if t not in Z.columns or s not in gi or t in decided or not bool(liquid.get(t, False)):
            continue
        if t not in universe and "ETF" in s:          # baskets of ETFs (e.g. Commodity ETFs) aren't meant to trade alike
            continue
        own = corr_own(t, s)
        if own is None:
            continue
        cc = corr_all(t)
        cc[gi[s]] = -9
        k = int(np.argmax(cc))
        best = float(cc[k])
        if (own < CFG["own_low"] and best >= own + CFG["gap"] and best >= CFG["best_min"]) or own < CFG["very_low"]:
            alts = [[groups[j], round(float(cc[j]), 2)] for j in np.argsort(-cc)[:2]]
            poor.append({"t": t, "name": names.get(t, ""), "sub": s, "group": grp_of.get(s), "own": round(own, 2),
                         "best": alts, "gap": round(best - own, 2), "rs": None if pd.isna(rs.get(t)) else int(rs[t]),
                         "dv": round(float(dv[t]) / 1e6, 1)})
    poor.sort(key=lambda x: -x["gap"])
    out["poor_fit"] = poor[:CFG["n_poor"]]

    # 3) stale tickers in the theme files (no bars in the last few sessions)
    recent = set(adjusted.loc[adjusted["date"] >= c.index[-CFG["stale_days"]], "ticker"])
    where = {}
    for t, s in sub_of.items():
        where.setdefault(t, []).append("sub-theme: " + s)
    for _, r in themes_df.iterrows():
        if r.get("role") != "etf":
            where.setdefault(r["ticker"], []).append("theme: " + r["theme"])
    for t, w in sorted(where.items()):
        if t not in recent and t not in decided:
            lastseen = adjusted.loc[adjusted["ticker"] == t, "date"].max()
            out["stale"].append({"t": t, "name": names.get(t, ""), "where": w[:4],
                                 "last": None if pd.isna(lastseen) else pd.Timestamp(lastseen).date().isoformat()})

    # 4) thin sub-themes
    for s, ms in sorted(members.items()):
        nl = sum(1 for t in ms if bool(liquid.get(t, False)))
        if nl < CFG["min_liquid"]:
            out["thin"].append({"sub": s, "group": grp_of.get(s), "n": len(ms), "liquid": nl, "members": ms[:8]})

    out["counts"] = {k: len(out[k]) for k in ("unclassified", "poor_fit", "stale", "thin")}
    out["proposals"] = proposals_status()
    return out


# ---------------------------------------------------------------------------
# Proposals, apply, reject (stdlib only)
# ---------------------------------------------------------------------------
def _read_log():
    if not LOG_FILE.exists():
        return []
    with open(LOG_FILE) as f:
        return list(csv.DictReader(f))


def _append_log(rows):
    new = not LOG_FILE.exists()
    with open(LOG_FILE, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_COLS)
        if new:
            w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in LOG_COLS})


def _proposals():
    if not PROPOSALS.exists():
        return None
    return json.loads(PROPOSALS.read_text())


def proposals_status():
    """The latest agent proposals with each one's decision status (for the page)."""
    P = _proposals()
    if not P:
        return None
    done = {(r["id"], r["t"]): r["status"] for r in _read_log() if r.get("id")}
    moves = []
    for m in P.get("moves") or []:
        moves.append(dict(m, status=done.get((str(m["id"]), m["t"]), "open")))
    return {"for_date": P.get("for_date"), "written": P.get("written"), "summary": P.get("summary"), "moves": moves,
            "checked": P.get("checked") or 0}


def _read_csv(path):
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        return r.fieldnames, list(r)


def _write_csv(path, cols, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def apply_moves(ids, today=None):
    """Apply proposals by number. Returns lines describing what changed."""
    P = _proposals()
    if not P:
        sys.exit("no proposals file (docs/agent/reclass.json)")
    by_id = {str(m["id"]): m for m in P.get("moves") or []}
    done = {(r["id"], r["t"]) for r in _read_log() if r.get("id")}
    scols, subs = _read_csv(SUB_FILE)
    tcols, ths = _read_csv(THEME_FILE)
    group_of = {r["subtheme"]: r["group"] for r in subs}
    today = (today or date.today()).isoformat()
    lines, log = [], []
    for i in ids:
        m = by_id.get(str(i))
        if not m:
            lines.append(f"#{i}: no such proposal"); continue
        if (str(m["id"]), m["t"]) in done:
            lines.append(f"#{i} {m['t']}: already decided"); continue
        t, act = m["t"], m["action"]
        if act == "keep":
            log.append(dict(m, date=today, status="kept", **{"from": m.get("from") or ""})); lines.append(f"#{i} {t}: kept as is"); continue
        if act in ("add", "move"):
            to = m["to"]
            if to.startswith("NEW:"):
                grp, _, name = to[4:].partition("/")
                grp, name = grp.strip(), name.strip()
                if not grp or not name:
                    lines.append(f"#{i} {t}: new sub-theme needs 'NEW: Group / Name'"); continue
            else:
                name, grp = to, group_of.get(to)
                if not grp:
                    lines.append(f"#{i} {t}: unknown sub-theme {to}"); continue
            subs = [r for r in subs if r["ticker"].upper() != t]          # one sub-theme per stock
            subs.append({"group": grp, "subtheme": name, "ticker": t})
            group_of.setdefault(name, grp)
            lines.append(f"#{i} {t}: {act} → {grp} / {name}" + (f" (was {m.get('from')})" if m.get("from") else ""))
        elif act == "remove":
            subs = [r for r in subs if r["ticker"].upper() != t]
            ths = [r for r in ths if not (r["ticker"].upper() == t and r.get("role", "member") != "etf")]
            lines.append(f"#{i} {t}: removed from the theme files")
        elif act == "rename":
            new = (m.get("to") or "").upper().strip()
            if not new:
                lines.append(f"#{i} {t}: rename needs the new ticker in 'to'"); continue
            for r in subs + ths:
                if r["ticker"].upper() == t:
                    r["ticker"] = new
            lines.append(f"#{i} {t}: renamed to {new}")
        th = (m.get("theme_add") or "").strip()
        if th and act in ("add", "move") and not any(r["theme"] == th and r["ticker"].upper() == t for r in ths):
            ths.append({"theme": th, "ticker": t, "role": "member"})
            lines[-1] += f"; added to theme {th}"
        log.append(dict(m, date=today, status="applied", **{"from": m.get("from") or ""}))
    subs.sort(key=lambda r: (r["group"], r["subtheme"], r["ticker"]))
    _write_csv(SUB_FILE, scols, subs)
    _write_csv(THEME_FILE, tcols, ths)
    _append_log(log)
    return lines


def reject(ids, today=None):
    P = _proposals() or {}
    by_id = {str(m["id"]): m for m in P.get("moves") or []}
    today = (today or date.today()).isoformat()
    rows = [dict(by_id[str(i)], date=today, status="rejected", **{"from": by_id[str(i)].get("from") or ""})
            for i in ids if str(i) in by_id]
    _append_log(rows)
    return [f"#{r['id']} {r['t']}: rejected (not proposed again for {CFG['quiet_days']} days)" for r in rows]


def worklist():
    """What the agent researches: the build's worklist + the exact sub-theme names it may use (stdlib only)."""
    h = (ROOT / "docs" / "index.html").read_text()
    i = h.index("const DATA = ") + len("const DATA = ")
    D = json.JSONDecoder().raw_decode(h[i:])[0]
    T = D.get("themes") or {}
    W = T.get("reclass") or {}
    subs = sorted({r["subtheme"] + "  [" + r["group"] + "]" for r in _read_csv(SUB_FILE)[1]})
    themes = sorted({r["theme"] for r in _read_csv(THEME_FILE)[1]})
    return {"for_date": W.get("date"), "unclassified": W.get("unclassified", []), "poor_fit": W.get("poor_fit", []),
            "stale": W.get("stale", []), "thin": W.get("thin", []), "subthemes": subs, "themes": themes,
            "note": "Research each ticker's actual business (company site, 10-K, a reliable profile). Propose a move only when the "
                    "business clearly belongs elsewhere; correlations are hints, not proof. Use exact sub-theme names from "
                    "`subthemes` (without the [group] part), or 'NEW: Group / Name' when nothing fits and 3+ liquid peers exist. "
                    "Say keep when the current home is right. Every move needs a source URL."}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worklist", "list", "apply", "reject"])
    p.add_argument("--ids", default="")
    a = p.parse_args(argv)
    ids = [x.strip() for x in a.ids.split(",") if x.strip()]
    if a.cmd == "worklist":
        print(json.dumps(worklist(), indent=1))
    elif a.cmd == "list":
        st = proposals_status()
        if not st:
            print("no proposals yet"); return
        print(f"Proposals for {st['for_date']} ({st['checked']} tickers checked): {st['summary']}")
        for m in st["moves"]:
            print(f"#{m['id']} [{m['status']}] {m['t']} {m['action']} {m.get('from') or ''} → {m.get('to') or ''} "
                  f"({m.get('confidence')}): {m.get('why')}")
    elif a.cmd == "apply":
        for line in apply_moves(ids):
            print(line)
    elif a.cmd == "reject":
        for line in reject(ids):
            print(line)


if __name__ == "__main__":
    sys.exit(main())
