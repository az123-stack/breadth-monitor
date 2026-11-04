# Market Monitor · to-do list

Open work, in rough priority order. Updated Oct 27, 2026 (end of session). Read this at the start of a work session; tick items off
(move them to "Done" with the date) and add new ones as Adam asks for them.

## v2 redesign (started Oct 28, 2026; Adam approved Option B: new page at /v2/ beside v1)
0. Oct 29: Adam preferred v1's content over v2 ("organization was the biggest flaw"). v1 reorganized instead (10 tabs, merged Setups,
   jump bar, fold-up cards, search drawer, My positions, theme toggle). v2 (/v2/) still builds; retire it (drop `v2site.build` from
   `site.build`, delete docs/v2) once Adam confirms he's happy with the new v1 layout. Open: phone alerts for positions (needs a private
   ntfy topic; repo is public so positions can't be committed).

## Theme upkeep (Oct 28)
- First reclass agent run Sat Oct 31 8:37 AM ET; Adam answers "apply reclass N" / "reject reclass N". Worklist already flags ESS (REIT in
  Batteries & Storage), CME, ISRG, stale WBD / PSKY / ATKR / BZH.

## Wednesday Nov 4, 2026 (Adam: "when my usage resets")
- [x] **RS formula check: sheet vs dashboard.** DONE Nov 4 → card R-2026-11-04-rs-sheet-vs-dashboard: keep our RS (the names only the sheet finds did worse); neither has a proven edge this year. Adam's "Trading Dashboard v12" sheet uses
  `=IFERROR(ROUND((googlefinance(A4,"price")/INDEX(googlefinance(A4,"price",TODAY()-90,TODAY()-63,1),2,2)-1)*100,2),"")`
  = raw % change from the first close ~90 calendar days ago (≈ 62 sessions) to now, one period, not ranked.
  Ours = RS Rating 1–99: 63/126/189/252-session returns weighted 40/20/20/20, percentile vs liquid stocks.
  Adam: "it definitely comes up with different stocks, I just don't know which is better." Plan: rebuild the sheet's number from our bars,
  compare the top lists (overlap, who each one finds), and backtest both (top 10% / 20% by each → next 20 / 60 sessions vs SPY and vs the
  average liquid stock, halves, by breadth regime; also the 3-month-only and blended versions, and the short RS periods rs2w/rs4w/rs6w).
  Answer which to keep (or offer it as another "RS period" chip), file a research card.
- [x] **"Golden eggs" that never show up** DONE Nov 4: deals / pinned stocks (10-session ADR < 0.8% or aimon exclude) out of strongest / Leaders / Oracle; v3 Stocks → Strongest (breadth/unseen.py, every RS 90+ name + "on no list" + "new this week"); reclass worklist keeps every $100M+/day unfiled name. (Adam, Nov 1: "NTRA is super strong and not even in our universe … these can't get missed").
  Checked Nov 1: NTRA IS in the data (Genomics & Diagnostics, RS 97, +99% 180D, +56% 60D, ~5% off its high, $580M/day) but no list
  surfaces it: Oracle shows the top 15 only (NTRA #20 on 60D, #74 on 180D); Leaders "Any theme" (`lists.strongest`, top 40) is crowded by
  pinned deal stocks (HZO #2 with a 0.29% ADR, sitting "at the high") so NTRA misses it; no setup fired. Fixes to build: (1) drop deal /
  pinned stocks (ADR < ~0.8% or aimon.json exclude) from every leader list; (2) a "Strongest stocks" view (RS 90+, liquid, near highs,
  sortable, one table, every name, not a top-N) on the v3 Stocks tab; (3) a weekly "new leaders you haven't seen" alert = names that just
  entered RS 95+ / Oracle top 20 on 60D or 180D and aren't on any list; (4) widen the reclass worklist (busy names like TW, $100M+/day,
  regardless of RS) so unfiled stocks get a sub-theme.

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
