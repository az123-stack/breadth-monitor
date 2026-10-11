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

from . import config, kq, metrics, site, store, themes
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
        try:  # names for ETFs and ADRs used in themes (a few extra calls, weekly)
            ref = client.tickers_of_type("ETF") + client.tickers_of_type("ADRC")
            store.save_ref_names(ref)
        except Exception as e:
            log.warning("could not refresh ETF/ADR names: %s", e)
        universe = {r["ticker"] for r in rows}
        log.info("universe: %d common stocks", len(universe))
    elif not config.REF_NAMES_FILE.exists():
        try:  # ETF/ADR names and exchanges (for display and TradingView export)
            store.save_ref_names(client.tickers_of_type("ETF") + client.tickers_of_type("ADRC"))
        except Exception as e:
            log.warning("could not fetch ETF/ADR names: %s", e)
    return universe


def fetch_days(client, bars, keep, days, checkpoint_every=25):
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
        bars = store.append_day(bars, d, rows, keep)
        added += 1
        log.info("[%d/%d] %s: %d bars", i, len(todo), d, len(rows))
        if added % checkpoint_every == 0:
            store.save_bars(bars)
    return bars, added


def backfill_extras(client, bars, universe, state):
    """Theme tickers outside the common-stock universe (ETFs, ADRs, SPY...)
    were not kept in older stored days. Fetch their history once, per ticker."""
    if bars.empty:
        return bars
    done = set(state.get("extras_done", []))
    missing = dict(state.get("extras_missing", {}))
    today = today_et()
    todo = []
    for t in sorted(store.theme_tickers() - universe - done):
        last_try = store.parse_date(missing.get(t))
        if last_try and (today - last_try).days < config.EXTRA_RETRY_DAYS:
            continue
        todo.append(t)
    if not todo:
        return bars
    dates = pd.DatetimeIndex(sorted(bars["date"].unique()))
    start, end = dates[0].date(), dates[-1].date()
    log.info("backfilling %d theme ticker(s) outside the stock universe", len(todo))
    new, rewrite = [], set()
    for i, t in enumerate(todo, 1):
        try:
            rows = client.daily_bars(t, start, end)
        except MassiveError as e:
            log.warning("%s: %s", t, e)
            rows = []
        rows = [r for r in rows if pd.Timestamp(r["date"]) in dates]
        if rows:
            new.extend(rows)
            rewrite.update(pd.Timestamp(r["date"]) for r in rows)
            done.add(t)
            missing.pop(t, None)
        else:
            missing[t] = today.isoformat()
        log.info("[%d/%d] %s: %d bars", i, len(todo), t, len(rows))
    if new:
        add = pd.DataFrame(new)
        add["date"] = pd.to_datetime(add["date"])
        key = add.set_index(["date", "ticker"]).index
        bars = bars[~bars.set_index(["date", "ticker"]).index.isin(key)]
        bars = pd.concat([bars, add[store.BAR_COLS]], ignore_index=True)
        store.save_bars(bars, rewrite_days=rewrite)
    state["extras_done"] = sorted(done)
    state["extras_missing"] = missing
    return bars


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


def recompute_and_publish(bars, splits, universe, state):
    adjusted = store.apply_splits(bars, splits)
    # Breadth stays on the common-stock universe; theme ETFs/ADRs are excluded.
    extras = store.theme_tickers() - set(universe)
    stocks = adjusted[~adjusted["ticker"].isin(extras)]
    fresh = metrics.compute(stocks)
    history = metrics.merge(store.load_breadth(), fresh)
    store.save_breadth(history)
    try:
        theme_data = themes.build(adjusted, store.load_themes(), universe,
                                  names=store.load_names(), subthemes_df=store.load_subthemes(),
                                  tv=store.load_tv_symbols(),
                                  missing=sorted(state.get("extras_missing", {})))
    except Exception as e:  # never let the theme tab break the breadth dashboard
        log.exception("theme build failed: %s", e)
        theme_data = None
    try:
        kq_data = kq.build(adjusted, universe, names=store.load_names(), tv=store.load_tv_symbols())
    except Exception as e:  # the KQ list is optional; never block the page
        log.exception("kq screen failed: %s", e)
        kq_data = None
    site.build(history, theme_data, kq_data)
    return history


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--backfill-days", type=int, default=0,
                   help="calendar days of history to load (free plan: up to ~730)")
    p.add_argument("--rebuild-only", action="store_true")
    p.add_argument("--extend-history", action="store_true",
                   help="refetch older days (pruned earlier) up to KEEP_TRADING_DAYS, incl. theme ETFs/ADRs")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

    state = store.load_state()
    bars = store.load_bars()

    if not args.rebuild_only:
        client = MassiveClient()
        universe = refresh_universe(client, state)
        keep = universe | store.theme_tickers()
        end = today_et()
        if args.backfill_days:
            start = end - timedelta(days=args.backfill_days)
        elif len(bars):
            start = bars["date"].max().date() + timedelta(days=1)
        else:
            log.error("no stored data yet: run once with --backfill-days")
            return 1
        bars, added = fetch_days(client, bars, keep, list(weekdays(start, end)))
        store.save_bars(bars)
        store.save_state(state)
        if args.extend_history and len(bars):
            have = len(bars["date"].unique())
            need = config.KEEP_TRADING_DAYS - have
            if need > 0:
                first = bars["date"].min().date()
                older = list(weekdays(first - timedelta(days=int(need * 1.5) + 10), first - timedelta(days=1)))
                log.info("extending history by up to %d trading days", need)
                bars, _ = fetch_days(client, bars, keep, older)
                store.save_bars(bars)
                state["extras_done"] = []      # refetch ETF/ADR history over the longer window
                store.save_state(state)
        bars = backfill_extras(client, bars, universe, state)
        if added == 0 and not args.backfill_days:
            log.info("no new trading days; rebuilding site anyway")
        splits = refresh_splits(client, bars, state)
        store.save_bars(bars)
        store.save_state(state)
    else:
        splits = store.load_splits()
        universe = store.load_universe()

    if bars.empty:
        log.error("no bars stored")
        return 1

    history = recompute_and_publish(bars, splits, universe, state)
    # Prune old bars only after the metrics they fed are safely written.
    store.prune(bars)
    last = history.iloc[-1]
    log.info("latest %s: up4=%s dn4=%s ratio5=%.2f ratio10=%.2f T2108=%.1f",
             history.index[-1].date(), last["up4"], last["dn4"],
             last["ratio5"], last["ratio10"], last["t2108"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
