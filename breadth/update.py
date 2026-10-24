"""Entry point: fetch missing days, recompute breadth, rebuild the dashboard.

    python -m breadth.update                    # daily incremental run
    python -m breadth.update --backfill-days 730  # first-time history load
    python -m breadth.update --rebuild-only     # recompute + site, no API calls
    python -m breadth.update --wait-until 01:00 # evening run: wait (checking every 15 min) for today's bars
"""
import argparse
import logging
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from . import config, intraday, kq, metrics, site, store, themes
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


PUBLISH_LOG = config.DATA_DIR / "massive_publish.csv"   # every "is today's data out yet?" check


def log_check(day, result, n=0):
    import csv
    new = not PUBLISH_LOG.exists()
    with open(PUBLISH_LOG, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["checked_at_et", "day", "result", "bars"])
        w.writerow([datetime.now(ET).strftime("%Y-%m-%d %H:%M"), day.isoformat(), result, n])


def wait_for_day(client, day, until, every_min=15):
    """Ask Massive for `day`'s grouped bars every `every_min` minutes until they appear or `until`
    (an ET datetime) passes. Each check is logged to data/massive_publish.csv so we learn when the
    free plan publishes. Returns True once the day is out."""
    import time
    while True:
        try:
            rows = client.grouped_daily(day)
            result, n = ("published", len(rows)) if len(rows) >= 1000 else ("empty" if not rows else "partial", len(rows))
        except MassiveError as e:
            result, n = ("403 not on plan yet" if "403" in str(e) else "error: " + str(e)[:80]), 0
        log_check(day, result, n)
        log.info("%s check for %s: %s (%d bars)", datetime.now(ET).strftime("%H:%M ET"), day, result, n)
        if result == "published":
            return True
        nxt = datetime.now(ET) + timedelta(minutes=every_min)
        if nxt > until:
            log.info("stopped waiting at %s; the morning run will pick %s up", datetime.now(ET).strftime("%H:%M ET"), day)
            return False
        time.sleep(every_min * 60)


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
    fresh = metrics.compute(stocks, bench=adjusted[adjusted["ticker"] == config.BENCHMARK])
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
    macro_data = None
    try:
        from . import macro
        macro_data = macro.build(adjusted)
    except Exception as e:  # optional strip; never block the page
        log.exception("macro strip failed: %s", e)
    if theme_data:
        try:
            from . import levels as LV, tradesetups as TS
            theme_data["trade_setups"] = TS.build(theme_data["stocks"], theme_data["themes"], theme_data["subthemes"],
                                                  kq_data, theme_data.get("lists"), LV.load(),
                                                  vcp=theme_data.get("vcp_live"))
        except Exception as e:  # optional panel; never block the page
            log.exception("trade setups failed: %s", e)
        try:   # Box breakout retests, long + short (Edwards & Magee rectangle / Darvas box), with research
            from . import boxes
            theme_data["boxes"] = boxes.build(adjusted, universe, theme_data.get("stocks"), store.load_names(), history)
            boxes.attach(theme_data)          # long retest joins the Trade Setups so the playbook ranks it
        except Exception as e:  # optional panel; never block the page
            log.exception("box scan failed: %s", e)
        try:   # Market health: leaders acting + breakouts working (Adam, Oct 22 2026; info only)
            from . import leadership
            theme_data["leadership"] = leadership.build(adjusted, universe, theme_data.get("stocks"), store.load_names())
        except Exception as e:  # optional panel; never block the page
            log.exception("market health failed: %s", e)
        try:   # Strength on Weakness: weekly position trades out of a stage-1 base (Adam, Oct 21 2026; info only)
            from . import sow
            theme_data["sow"] = sow.build(adjusted, universe, theme_data.get("stocks"), store.load_names())
        except Exception as e:  # optional panel; never block the page
            log.exception("strength-on-weakness scan failed: %s", e)
        try:   # Stair steps: stocks / sub-themes nuzzling into the 9-21 EMAs and stepping up together (Adam, Oct 24 2026; info only)
            from . import stairs
            theme_data["stairs"] = stairs.build(adjusted, theme_data.get("stocks"), store.load_names(), store.load_subthemes())
        except Exception as e:  # optional panel; never block the page
            log.exception("stair steps failed: %s", e)
        try:   # Dip buys: Box + SoW names under / wicking under their 9-21 EMAs (Adam, Oct 24 2026; info only)
            from . import dips
            theme_data["dips"] = dips.build(adjusted, theme_data, store.load_names())
        except Exception as e:  # optional panel; never block the page
            log.exception("dip buys failed: %s", e)
        try:
            from . import playbook
            theme_data["playbook"] = playbook.build(theme_data, history)
        except Exception as e:
            log.exception("playbook failed: %s", e)
        intraday.set_bars(adjusted)      # Russell 2000 weights follow prices since the holdings file date
        try:
            theme_data["thrust_watch"] = intraday.thrust_watch(adjusted, history, universe)
        except Exception as e:  # optional panel; never block the page
            log.exception("thrust watch failed: %s", e)
        try:   # washout thrust flag + high-beta leaders list (connector study, Oct 2026)
            from . import washout
            theme_data["washout"] = washout.build(adjusted, history, universe, names=store.load_names())
        except Exception as e:  # optional panel; never block the page
            log.exception("washout thrust failed: %s", e)
        try:   # volume tilt: up moves on heavier or lighter volume than down moves (imbalance study, Oct 2026)
            from . import vtilt
            theme_data["vtilt"] = vtilt.build(history, adjusted[adjusted["ticker"] == config.BENCHMARK])
        except Exception as e:  # optional panel; never block the page
            log.exception("volume tilt failed: %s", e)
        try:   # FINRA off-exchange short share (free daily; experimental "hidden buying" read, Oct 17 study)
            from . import finra
            if config.LEVELS_ENABLED:
                finra.update(recent=7, bars=adjusted)
                finra.aggregate(bars=adjusted)
            theme_data["dix"] = finra.build(adjusted[adjusted["ticker"] == config.BENCHMARK])
        except Exception as e:  # optional panel; never block the page
            log.exception("FINRA short share failed: %s", e)
        try:
            from . import rotation
            theme_data["rotation"] = rotation.build(adjusted, theme_data, kq_data, macro_data, history)
        except Exception as e:  # optional panel; never block the page
            log.exception("rotation ideas failed: %s", e)
        try:   # top picks: re-rank with group / money-flow context now that rotation + ignition exist
            from . import playbook
            playbook.rerank(theme_data, history)
        except Exception as e:
            log.exception("pick re-rank failed: %s", e)
        try:   # The trade: the market's main rotation (winning vs losing groups), info only (Oct 22)
            from . import thetrade
            theme_data["thetrade"] = thetrade.build(adjusted, theme_data, history)
        except Exception as e:  # optional panel; never block the page
            log.exception("the trade failed: %s", e)
        try:
            from . import ledger
            pb = theme_data.get("playbook") or {}
            if pb.get("picks"):
                ledger.record(theme_data["date"], pb["picks"], pb.get("pick_cands") or [])
            ledger.settle(adjusted)
            theme_data["scoreboard"] = ledger.summary(adjusted, history=history)
        except Exception as e:
            log.exception("pick scoreboard failed: %s", e)
        try:   # Decision Cards: every layer per trade idea (information only; see DECISIONS.md) + daily layer log
            from . import decision, macrofit, macro as MAC
            cands = [t for t, _ in decision.candidates(theme_data)]
            mfit = macrofit.build(adjusted, MAC.load(), cands)
            dec = decision.build(theme_data, history, mfit, metrics.classify(history).get("label"))
            if dec:
                theme_data["decision"] = decision.strip_private(dec)     # the page gets the cards even if logging fails
                try:
                    decision.record(dec)
                except Exception as e:
                    log.exception("decision log record failed: %s", e)
        except Exception as e:
            log.exception("decision cards failed: %s", e)
        try:   # settle earlier ideas and refresh forward evidence even if today's cards failed
            from . import decision, layers
            decision.settle(adjusted)
            ev = layers.load(); ev["log"] = layers.study_log(); layers.save(ev)
            if theme_data.get("decision"):
                theme_data["decision"]["evidence"] = decision.load_evidence()   # cleaned, never raw
        except Exception as e:
            log.exception("decision log settle failed: %s", e)
        try:
            from . import review
            theme_data["setup_review"] = review.evaluate(theme_data, history)
        except Exception as e:
            log.exception("setup review failed: %s", e)
    site.build(history, theme_data, kq_data, macro_data)
    try:
        from . import dips
        intraday.write_sheet_csv(dips.tickers((theme_data or {}).get("dips")))
    except Exception as e:  # never block the page on this
        log.warning("live sheet ticker list skipped: %s", e)
    return history


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--backfill-days", type=int, default=0,
                   help="calendar days of history to load (free plan: up to ~730)")
    p.add_argument("--rebuild-only", action="store_true")
    p.add_argument("--wait-until", default="",
                   help="HH:MM ET (after midnight = next day): on a weekday evening, wait for today's bars until then")
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
        # Waiting mode: the free plan unlocks a session only after midnight ET (403 before that; measured Oct 13:
        # 403 every 15 min until 23:58, published at 00:13). After 4 PM wait for today; otherwise for the last weekday.
        now = datetime.now(ET)
        target = end if now.hour >= 16 else max(weekdays(end - timedelta(days=7), end - timedelta(days=1)))
        have = len(bars) and bars["date"].max().date() >= target
        if args.wait_until and target.weekday() < 5 and not have:
            hh, mm = map(int, args.wait_until.split(":"))
            until = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if until <= now:
                until += timedelta(days=1)
            wait_for_day(client, target, until)
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
        try:   # old highs for the Trade Setups magnets (cached; only new tickers are fetched)
            from . import levels as LV
            if config.LEVELS_ENABLED:
                LV.refresh(store.theme_tickers() & set(universe))
        except Exception as e:
            log.warning("levels refresh skipped: %s", e)
        try:   # record-volume candidates: confirm "highest ever" from Yahoo's full daily history
            from . import hve
            if config.LEVELS_ENABLED:
                hve.refresh_ever(hve.candidates(store.apply_splits(bars, splits), universe, store.theme_tickers()))
        except Exception as e:
            log.warning("record volume history skipped: %s", e)
        try:   # macro drivers strip (Yahoo futures; cached, ETF fallback)
            from . import macro
            if config.LEVELS_ENABLED:
                macro.refresh()
        except Exception as e:
            log.warning("macro refresh skipped: %s", e)
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
