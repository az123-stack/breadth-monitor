"""IPO supply study (Nov 15, 2026; Adam: "is this downturn just freeing up funds for the Anthropic IPO?").

Question: before a mega IPO prices, do the stocks most like it and the crowded winners lag SPY,
and do they bounce once the deal is priced?  Card R-2026-11-15-ipo-supply.

Baskets (equal weight, returns vs SPY, split-adjusted closes):
  ai_hw    the 7 AI-hardware sub-themes of the "AI spending gets repriced" story
  space    Launch & Space Systems + Satellite Connectivity & Imaging
  megacap  NVDA AVGO MSFT GOOGL META AMZN TSM ORCL
  winners  top 50 liquid stocks ($10+, $20M+/day) by 63-day return at the window start (crowded longs)
Windows: pre = public filing close -> pricing-day close (15 sessions for the small IPOs);
         post = pricing-day close -> +5 / +10 / +20 sessions.
Placebo: the same baskets over every rolling window of the same length (all dates), so each event
gets a percentile vs ordinary times.
Run: python tools/ipo_study/study.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from breadth import store  # noqa: E402

AI_HW = ["Semicap Equipment", "Optical Components & Transceivers", "AI Servers & Integrators",
         "Custom Silicon & Networking Chips", "Neoclouds & GPU Hosting", "Data Center Power & Cooling",
         "Memory & Storage Media"]
SPACE = ["Launch & Space Systems", "Satellite Connectivity & Imaging"]
MEGA = ["NVDA", "AVGO", "MSFT", "GOOGL", "META", "AMZN", "TSM", "ORCL"]

# (name, size $B, public filing date or None, pricing date)
EVENTS = [
    ("CoreWeave", 1.5, None, "2025-03-27"),
    ("Circle", 1.1, None, "2025-06-04"),
    ("Figma", 1.2, None, "2025-07-30"),
    ("Klarna", 1.4, None, "2025-09-09"),
    ("SpaceX", 75.0, "2026-05-20", "2026-06-11"),
    ("Anthropic*", 64.4, "2026-10-26", "2026-11-18"),   # * not priced yet: pre-window runs to the last bar
]


def load():
    bars = store.apply_splits(store.load_bars(), store.load_splits())
    close = bars.pivot_table(index="date", columns="ticker", values="c").sort_index()
    dv = (bars["c"] * bars["v"]).groupby([bars["date"], bars["ticker"]]).sum().unstack()
    return close, dv.reindex(close.index)


def basket_rel(close, tickers, i0, i1):
    """Equal-weight return of tickers from row i0 to i1 minus SPY's, in %."""
    t = [x for x in tickers if x in close.columns]
    a, b = close.iloc[i0][t], close.iloc[i1][t]
    ok = a.notna() & b.notna() & (a > 0)
    if ok.sum() == 0:
        return np.nan, 0
    r = (b[ok] / a[ok] - 1).mean()
    spy = close["SPY"].iloc[i1] / close["SPY"].iloc[i0] - 1
    return 100 * (r - spy), int(ok.sum())


def winners_at(close, dv, i0, n=50):
    if i0 < 63:
        return []
    px = close.iloc[i0]
    liq = dv.iloc[max(0, i0 - 20):i0 + 1].mean()
    r63 = px / close.iloc[i0 - 63] - 1
    ok = (px >= 10) & (liq >= 20e6) & r63.notna()
    ok = ok.drop(labels=[c for c in ["SPY", "QQQ", "IWM", "DIA"] if c in ok.index], errors="ignore")
    return r63[ok[ok].index].nlargest(n).index.tolist()


def main():
    close, dv = load()
    sub = store.load_subthemes()
    hw = sub[sub["subtheme"].isin(AI_HW)]["ticker"].tolist()
    sp = sub[sub["subtheme"].isin(SPACE)]["ticker"].tolist()
    dates = close.index
    last = len(dates) - 1

    def idx(d):
        return int(dates.searchsorted(pd.Timestamp(d), side="right") - 1)

    def baskets(i0):
        return {"ai_hw": hw, "space": sp, "megacap": MEGA, "winners": winners_at(close, dv, i0)}

    # placebo distribution per window length L for every basket
    cache = {}

    def placebo(name, L):
        key = (name, L)
        if key not in cache:
            vals = []
            for i0 in range(63, last - L + 1, 3):
                v, _ = basket_rel(close, baskets(i0)[name], i0, i0 + L)
                vals.append(v)
            cache[key] = np.array([v for v in vals if np.isfinite(v)])
        return cache[key]

    rows = []
    for name, size, filed, priced in EVENTS:
        ip = min(idx(priced), last)
        i0 = idx(filed) if filed else ip - 15
        L = ip - i0
        b = baskets(i0)
        row = {"event": name, "size_$B": size, "pre_from": str(dates[i0].date()), "pre_to": str(dates[ip].date()),
               "pre_sessions": L}
        for k, tick in b.items():
            v, n = basket_rel(close, tick, i0, ip)
            pl = placebo(k, L)
            row[f"pre_{k}"] = round(v, 1)
            row[f"pre_{k}_pct"] = int(round(100 * (pl < v).mean())) if len(pl) else None
        bp = baskets(ip)
        for h in (5, 10, 20):
            for k in ("ai_hw", "space", "megacap", "winners"):
                if ip + h <= last and not name.endswith("*"):
                    v, _ = basket_rel(close, bp[k], ip, ip + h)
                    row[f"post{h}_{k}"] = round(v, 1)
                else:
                    row[f"post{h}_{k}"] = None
        rows.append(row)
    df = pd.DataFrame(rows).set_index("event")
    pd.set_option("display.width", 250)
    pre = [c for c in df.columns if c.startswith("pre_") and not c.endswith(("from", "to", "sessions"))]
    print("PRE-WINDOW (basket minus SPY, %; _pct = percentile vs every same-length window, low = unusually weak)")
    print(df[["size_$B", "pre_from", "pre_to", "pre_sessions"] + pre].to_string())
    print("\nPOST-PRICING (basket minus SPY, %, from pricing-day close)")
    print(df[[c for c in df.columns if c.startswith("post")]].to_string())
    for L in (15,):
        for k in ("ai_hw", "space", "megacap", "winners"):
            pl = placebo(k, L)
            print(f"placebo {k} {L}d: median {np.median(pl):+.1f}%, 10th pct {np.percentile(pl, 10):+.1f}%")
    out = Path(__file__).with_name("results.csv")
    df.to_csv(out)
    # SpaceX daily path for the story (space + winners vs SPY, rebased at filing)
    i0, ip = idx("2026-05-20"), idx("2026-06-11")
    w = winners_at(close, dv, i0)
    path = []
    for i in range(i0, min(ip + 21, last) + 1):
        path.append((str(dates[i].date()), round(basket_rel(close, sp, i0, i)[0], 1),
                     round(basket_rel(close, w, i0, i)[0], 1), round(basket_rel(close, hw, i0, i)[0], 1)))
    print("\nSpaceX path (date, space, winners, ai_hw vs SPY since May 20):")
    for p in path[::3]:
        print(p)
    # Anthropic path so far
    i0 = idx("2026-10-26")
    w = winners_at(close, dv, i0)
    print("\nAnthropic path (date, ai_hw, megacap, winners vs SPY since Oct 26):")
    for i in range(i0, last + 1):
        print(str(dates[i].date()), round(basket_rel(close, hw, i0, i)[0], 1),
              round(basket_rel(close, MEGA, i0, i)[0], 1), round(basket_rel(close, w, i0, i)[0], 1))
    # the IPO comps rallied on the filing? space from confidential filing (Apr 1) to public filing
    print("\nspace Apr 1 -> May 20:", basket_rel(close, sp, idx("2026-04-01"), idx("2026-05-20")))
    print("winners count Oct 26:", len(w), w[:15])


if __name__ == "__main__":
    main()
