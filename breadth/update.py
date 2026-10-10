"""Entry point: fetch missing days, recompute breadth, rebuild the dashboard.

    python -m breadth.update                    # daily incremental run
    python -m breadth.update --backfill-days 730  # first-time history load
    python -m breadth.update --rebuild-only     # recompute + site, no API calls
"""
import argparse
import logging
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from . import config, metrics, site, store
from .massive import MassiveClient, MassiveError

log = logging.getLogger("breadth")
ET = ZoneInfo("America/New_York")


def today_et():
    return datetime.now(ET).date()


def weekdays(start, end):
    d = start
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def refresh_universe(client, state, force=False):
    last = store.parse_date(state.get("universe_refreshed"))
    universe = store.load_universe()
    if force or not universe or not last or (today_et() - last).days >= config.UNIVERSE_REFRESH_DAYS:
        log.info("refreshing common-stock universe")
        rows = client.common_stocks()
        if len(rows) < 1000:
            raise MassiveError(f"universe looks too small ({len(rows)} tickers), not saving")
        store.save_universe(rows)
        state["universe_refreshed"] = today_et().isoformat()
        universe = {r["ticker"] for r in rows}
        log.info("universe: %d common stocks", len(universe))
    return universe


def fetch_days(client, bars, universe, days, checkpoint_every=25):
    have = set(pd.to_datetime(bars["date"]).dt.date) if len(bars) else set()
    todo = [d for d in days if d not in have]
    log.info("%d day(s) to fetch", len(todo))
    added = 0
    for i, d in enumerate(todo, 1):
        try:
            rows = client.grouped_daily(d)
        except MassiveError as e:
            if "403" in str(e):   # beyond the plan's history window
                log.warning("%s not available on this plan, skipping", d)
                continue
            raise
        if not rows:
            log.info("%s: no data (holiday or not published yet)", d)
            continue
        bars = store.append_day(bars, d, rows, universe)
        added += 1
        log.info("[%d/%d] %s: %d bars", i, len(todo), d, len(rows))
        if added % checkpoint_every == 0:
            store.save_bars(bars)
    return bars, added


def refresh_splits(client, bars, state):
    splits = store.load_splits()
    if bars.empty:
        return splits
    earliest = bars["date"].min().date()
    covered = store.parse_date(state.get("splits_covered_from"))
    if covered is None or earliest < covered:
        start = earliest
    else:  # re-check the last month to pick up late-published records
        start = today_et() - timedelta(days=30)
    try:
        rows = client.splits_since(start)
    except Exception as e:  # non-fatal: metrics still compute, splits just aren't adjusted
        log.warning("could not fetch splits (%s); continuing without new split data", e)
        return splits
    splits = store.save_splits(splits, rows)
    state["splits_covered_from"] = min(earliest, covered or earliest).isoformat()
    log.info("splits on file: %d", len(splits))
    return splits


def recompute_and_publish(bars, splits):
    adjusted = store.apply_splits(bars, splits)
    fresh = metrics.compute(adjusted)
    history = metrics.merge(store.load_breadth(), fresh)
    store.save_breadth(history)
    site.build(history)
    return history


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--backfill-days", type=int, default=0,
                   help="calendar days of history to load (free plan: up to ~730)")
    p.add_argument("--rebuild-only", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

    state = store.load_state()
    bars = store.load_bars()

    if not args.rebuild_only:
        client = MassiveClient()
        universe = refresh_universe(client, state)
        end = today_et()
        if args.backfill_days:
            start = end - timedelta(days=args.backfill_days)
        elif len(bars):
            start = bars["date"].max().date() + timedelta(days=1)
        else:
            log.error("no stored data yet: run once with --backfill-days")
            return 1
        bars, added = fetch_days(client, bars, universe, list(weekdays(start, end)))
        if added == 0 and not args.backfill_days:
            log.info("no new trading days; rebuilding site anyway")
        splits = refresh_splits(client, bars, state)
        store.save_bars(bars)
        store.save_state(state)
    else:
        splits = store.load_splits()

    if bars.empty:
        log.error("no bars stored")
        return 1

    history = recompute_and_publish(bars, splits)
    # Prune old bars only after the metrics they fed are safely written.
    store.prune(bars)
    last = history.iloc[-1]
    log.info("latest %s: up4=%s dn4=%s ratio5=%.2f ratio10=%.2f T2108=%.1f",
             history.index[-1].date(), last["up4"], last["dn4"],
             last["ratio5"], last["ratio10"], last["t2108"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
