# Market Monitor · to-do list

Open work, in rough priority order. Updated Oct 27, 2026 (end of session). Read this at the start of a work session; tick items off
(move them to "Done" with the date) and add new ones as Adam asks for them.

## v2 redesign (started Oct 28, 2026; Adam approved Option B: new page at /v2/ beside v1)
0. **Fill the planned v2 pages**, one main tab at a time: Groups → Lifecycle, Rotation, Timeline; Setups → Box trades, Lined-up & dips
   (live), Export lists; Market (Breadth, Money flow, Macro, Pre-market & live); Read → Trade stories, Earnings, Archive (one page per
   chapter); Lab. Then live prices (clock mode from the Google sheet / pre-market file), ticker search drawer, and the subscription-ready
   pieces Adam liked (personal watchlist layer, public track record, plain-English explainers, neutral setup names). Prototype history:
   branch `v2-prototype`.

## Theme upkeep (Oct 28)
- First reclass agent run Sat Oct 31 8:37 AM ET; Adam answers "apply reclass N" / "reject reclass N". Worklist already flags ESS (REIT in
  Batteries & Storage), CME, ISRG, stale WBD / PSKY / ATKR / BZH.

## Next up (Adam: "next week")
1. **Trade warehouse + stacked R** (Adam, Oct 27: "this trade is 0.8R, that one 0.5R, but layered together 1.3R — keep making this
   smarter"). Card R-2026-10-27-r-stacking says how: (a) one table of every setup's past trades on the same yardstick (box, spring,
   lined-up dips, Best Setups nuzzles / flags, Launch picks) with the same layer columns; (b) expected R = setup base + PROVEN layer
   lifts only, shrunk by sample size; combinations count only if proposed first and confirmed in both halves (searched-for synergy
   mostly evaporated); (c) show the stack on each live Launch pick / lined-up buy and log it forward; (d) the Saturday Integrator
   re-runs it and proposes combinations to test. Start: `tools/rstack/box_stack.py`.
2. **"My positions" card** (Adam, Oct 27, to-do): Adam's own real trades with his exit rules live — sell part after 3–5 days, trail
   the 10 / 20 EMA, stop alerts. Ask how he wants to enter positions (paste, a Google Sheet tab, or the page itself).

## New data layers (Adam, Oct 27: "add order flow, and abnormal option volume in either direction")
3. **Order flow.** What we already have is end-of-day and indirect: FINRA off-exchange short share ("Hidden buying", Breadth tab,
   info), who won the close, volume tilt, dollar flow. Next: (a) per-STOCK order-flow reads, not just the market — FINRA short
   share per ticker is already stored in `data/finra/` (start here, free): unusual dark-pool buying/selling in a stock vs its own
   normal, tested on our setups (Launch picks, lined-up dips, box longs) like any layer; (b) block trades / dark-pool prints and
   intraday buy/sell imbalance need a paid feed (e.g. a Massive plan with trades/quotes, Unusual Whales, Cheddar Flow, FlowAlgo) —
   price it and check what's reachable from GitHub Actions before building.
4. **Abnormal option volume, both directions** (bullish call sweeps AND bearish put buying). Needs an options feed: check the Massive
   options add-on first (same API key), else a flow service. Measure per stock: today's call / put volume vs its own 20-day
   normal, call/put ratio change, big out-of-the-money short-dated buying, open-interest change next day. Then the usual test:
   does abnormal call (or put) volume ahead of a setup change its R, both halves, before anything shows as more than "info".
   Show it as tags on Launch picks / lined-up buys and a "Unusual options" list on the Read-out.

## When data allows
5. **Longer price history** (Massive Starter ~$29 for one month, reaches 5 years; Adam will buy it later, not now). Then re-test
   everything stuck at "only ~1 year testable": Strength on Weakness, Launch list stages, weekly dips, R stacking.
6. **Finish the 15-minute bar download** (`.github/workflows/orb_study.yml`, branch `orb-data`; stopped at ~700 of ~1,040 tickers,
   A–PBR) and re-test the top late mover (card R-2026-10-27-late-mover) on all stocks, plus: only when the theme is in BUY, only in
   strong breadth, and as an entry for names already on the Launch / Lined-up lists.
7. **Earnings clusters** (card R-2026-10-27-earnings-clusters): after this earnings season, test "UP cluster + group in BUY" for the
   not-yet-reported members, and whether writer-confirmed clusters (the reports really agreed) beat price-only ones.

## Review dates (just watch)
8. **Live track records** — Lined-up buys (`data/lineup_ledger.csv`) and Launch picks (`data/launch_ledger.csv`): first honest read
   around late November (lined-up needs ~30+ closed trades; Launch picks hold 13 weeks).
9. **Agent layers** (catalyst, macro brief, calendar): first real read of the forward log in late November (Integrator).
10. **Retired from the page Oct 27** (old Top 2 swing picks, Decision Cards, pick scoreboard): Python still logs them quietly. Around
   December decide whether to delete that code for good (it costs build time) — the macro brief stays (Read-out card).

## Housekeeping
11. **Build time** ~5½ minutes per rebuild: profile it (`python -m cProfile -m breadth.update --rebuild-only`) and speed up the slowest
   parts (box study ~85 s, SoW ~40 s, market health ~40 s are known).
12. **Headless check of the Intraday tab** hangs in Claude's sandbox (it waits on the blocked live feeds; the live page is fine).
    Make the tab render without network so it can be checked before pushing.
13. **Integrator plan (Oct 24) items still open**: market filters on setups (volume tilt, hidden buying), "the trade" as pick
    context, in-vogue groups as long confluence, a position-ideas list. Its #1 (Top 2 stop rule) is moot now the Top 2 is retired.

## Done (recent)
- Oct 27, 2026: Lined-up buys moved to Best Setups (live); tab refresh bug fixed; cleanup; earnings clusters (card + story
  section); headline picks = Launch picks + Lined-up buys; ★ leading group in box grades + playbook; top late mover watch line;
  "Macro & the week ahead" card; two scheduled tasks moved to the cheaper model; R-stacking study; theme-breadth play dropped.
