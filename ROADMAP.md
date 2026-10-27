# Market Monitor · to-do list

Open work, in rough priority order. Updated Oct 27, 2026 (end of session). Read this at the start of a work session; tick items off
(move them to "Done" with the date) and add new ones as Adam asks for them.

## Next up (Adam: "next week")
1. **Trade warehouse + stacked R** (Adam, Oct 27: "this trade is 0.8R, that one 0.5R, but layered together 1.3R — keep making this
   smarter"). Card R-2026-10-27-r-stacking says how: (a) one table of every setup's past trades on the same yardstick (box, spring,
   lined-up dips, Best Setups nuzzles / flags, Launch picks) with the same layer columns; (b) expected R = setup base + PROVEN layer
   lifts only, shrunk by sample size; combinations count only if proposed first and confirmed in both halves (searched-for synergy
   mostly evaporated); (c) show the stack on each live Launch pick / lined-up buy and log it forward; (d) the Saturday Integrator
   re-runs it and proposes combinations to test. Start: `tools/rstack/box_stack.py`.
2. **"My positions" card** (Adam, Oct 27, to-do): Adam's own real trades with his exit rules live — sell part after 3–5 days, trail
   the 10 / 20 EMA, stop alerts. Ask how he wants to enter positions (paste, a Google Sheet tab, or the page itself).

## When data allows
3. **Longer price history** (Massive Starter ~$29 for one month, reaches 5 years; Adam will buy it later, not now). Then re-test
   everything stuck at "only ~1 year testable": Strength on Weakness, Launch list stages, weekly dips, R stacking.
4. **Finish the 15-minute bar download** (`.github/workflows/orb_study.yml`, branch `orb-data`; stopped at ~700 of ~1,040 tickers,
   A–PBR) and re-test the top late mover (card R-2026-10-27-late-mover) on all stocks, plus: only when the theme is in BUY, only in
   strong breadth, and as an entry for names already on the Launch / Lined-up lists.
5. **Earnings clusters** (card R-2026-10-27-earnings-clusters): after this earnings season, test "UP cluster + group in BUY" for the
   not-yet-reported members, and whether writer-confirmed clusters (the reports really agreed) beat price-only ones.

## Review dates (just watch)
6. **Live track records** — Lined-up buys (`data/lineup_ledger.csv`) and Launch picks (`data/launch_ledger.csv`): first honest read
   around late November (lined-up needs ~30+ closed trades; Launch picks hold 13 weeks).
7. **Agent layers** (catalyst, macro brief, calendar): first real read of the forward log in late November (Integrator).
8. **Retired from the page Oct 27** (old Top 2 swing picks, Decision Cards, pick scoreboard): Python still logs them quietly. Around
   December decide whether to delete that code for good (it costs build time) — the macro brief stays (Read-out card).

## Housekeeping
9. **Build time** ~5½ minutes per rebuild: profile it (`python -m cProfile -m breadth.update --rebuild-only`) and speed up the slowest
   parts (box study ~85 s, SoW ~40 s, market health ~40 s are known).
10. **Headless check of the Intraday tab** hangs in Claude's sandbox (it waits on the blocked live feeds; the live page is fine).
    Make the tab render without network so it can be checked before pushing.
11. **Integrator plan (Oct 24) items still open**: market filters on setups (volume tilt, hidden buying), "the trade" as pick
    context, in-vogue groups as long confluence, a position-ideas list. Its #1 (Top 2 stop rule) is moot now the Top 2 is retired.

## Done (recent)
- Oct 27, 2026: Lined-up buys moved to Best Setups (live); tab refresh bug fixed; cleanup; earnings clusters (card + story
  section); headline picks = Launch picks + Lined-up buys; ★ leading group in box grades + playbook; top late mover watch line;
  "Macro & the week ahead" card; two scheduled tasks moved to the cheaper model; R-stacking study; theme-breadth play dropped.
