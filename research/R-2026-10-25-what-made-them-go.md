---
id: R-2026-10-25-what-made-them-go
title: "Base breakouts riding the 9 WEMA: what separated the ones that went"
date: 2026-10-25
status: mixed
kind: stock
horizon: 13 and 26 weeks
sample: 1,142 events Aug 2025 – Apr 2026 (26 weeks of future each); 441 with a sub-theme
result: base rate 22% made +50% within 26w, median 13w vs SPY −4.5%, 65% lost the 50 WEMA within 13w. Group (sub-theme top third on 13w) 13w vs SPY +5.9% vs −4.0% bottom third, lost-50 50% vs 67% (vol-adjusted IC +0.16, both halves). Volume trend / up-down volume / biggest volume week: no edge (IC −0.1 to 0). Score (sub-theme top third + RS 70+ + RS line +15% in 13w + a 6%+ gap day in 13w) 3–4 of 4: 53% went, 13w vs SPY +4.5–6.5%, lost-50 36–43% (n 91) vs 0 of 4: 11%, −6.0%, 73% (n 179)
halves: score ≥ 3 went 49% / 57% vs others 22% / 17%; group IC 0.16 / 0.25 (vol-adjusted)
layers: [sow, launch]
integrated: yes
source: tools/went_study/collect.py + test.py + test2.py (Adam, Oct 25 2026: CDNA / DINO / NTRA weekly charts, "find the tells")
---
**Idea.** Adam has ~50 names sitting where CDNA, DINO and NTRA sat before they went parabolic (out of a long base through the
weekly 50 EMA, riding the 9 WEMA). Volume didn't look like the tell. Which features separated the ones that went?

**How it was tested.** Weekly bars from daily (split-adjusted). Event = liquid ($5+, $10M+/day), 20+ of the prior 40 weekly
closes under the 50 WEMA, now 2–8 weekly closes in a row above it, 9 WEMA over a rising 21, close within 3 weekly ATRs of the 50;
first event per stock per 26 weeks. Entry next session's open. Outcomes: best high within 26 weeks (raw and in weekly ATRs),
13-week return vs SPY, lost the 50 WEMA on a weekly close within 13 weeks. Features known at the event week's close. Terciles,
rank IC, halves split by date, plus within-ADR checks.

**Result.** Most of these fail. Raw "went +50%" is dominated by volatility (ADR top third 39% vs 6%), gap days, deep bases, low
price and RS, but almost all of that vanishes once the move is measured in the stock's own ATRs or vs SPY: volatile stocks simply
swing further both ways. What survived: the stock's GROUP already leading (sub-theme top third on 13-week return) in both
halves on every yardstick, strongest in mid/high-ADR names. RS rating and the RS line mainly cut failures (lost the 50 WEMA 49%
vs 77% for RS top vs bottom third) rather than predicting the parabolic run. Volume (10 vs 26-week trend, up vs down weeks, biggest
week) added nothing. Stacked score (group top third + RS 70+ + RS line up 15%+ over 13 weeks + a 6%+ gap day in 13 weeks): 3–4 of
4 → 53% went, 2.4× the base rate, both halves. CDNA fired Nov 28 2025 at $17.69 (RS 52, diagnostics group top 11%, score 2):
only +36% within 26 weeks, the run came ~7 months later; DINO Aug 1 2025 $42.89 (refiners top 16%) +37% in 26 weeks, ran after.

**Caveats.** ~9 months of event dates in one mostly-bull stretch, survivors only, overlapping, 61% of events have no sub-theme
(the group feature only covers listed groups), score thresholds picked from the terciles (not tuned out of sample). The score
also selects more volatile names (median weekly ATR 10–15% vs 5%): size smaller.

**Grades (built Oct 25 as the Launch list tab, `breadth/launch.py`).** Splitting by the group point: with the sub-theme in its
top third, 13-week returns beat SPY at every score (0 other points +0% median, 1 +9%, 2 +9%, 3 +4%); without it even 3 of 3 other
points lagged SPY (−5%, hit +50% 38% only through volatility). A = group + 2–3 others: 76 setups, hit +50% 57%, 13w vs SPY +5.6%,
lost the 50 WEMA 41% (halves 55% / 58% hit); B = group + 0–1: 96, 33%, +3.1%, 62%; C: 970, 18%, −5.1%, 67%.
Oct 23, 2026 Grade A early (2–8 weeks over the 50): ACN, CTSH, IT, CDW (IT services), DNA, NTSK, RPD, ZS, PTC, CART, DHR, FDS, CME,
SPOT, ULTA; 80 more Grade A later in the move.

**Follow-up: earlier entry (Adam: ACN / IT had already gone when the list flagged them; the buy was the flag under the 50).**
`tools/went_study/early.py`. "Curl" = base + 9 WEMA over a rising 21 + close within 1.5 weekly ATRs under to 0.5 over the 50 WEMA
(1,076 events). Group point again decides it: group 46% hit +50%, 13w vs SPY +5.4% vs 18% / −5.4% without (halves 53/38% vs 20/17%);
group + 2 other points 58%, +11%; WITHOUT the group, RS / RS line / gap points made it worse (−12% vs SPY). Adding a 4-week flag break:
small (31 with group), halves 62% / 17% → shown as a tag only. ACN's RS was 8–14 in August while IT Services was already top 30%:
the group is the early clue, the other points switch on after the move starts. Entry location inside Grade A breakouts: within 1 ATR of
the 9 WEMA 53–54% hit +50% vs 43% beyond 1.5 ATRs (mild). Built: `curl` stage (default view) + "where to buy" (ATRs over the 9).
Oct 23 curl with group: AI, SBET, BMNR (A); HUBS, ADSK, TRMB (flag breaks), SNPS, DUOL, GEHC (B).

**How it could be used.** Rank Adam's SoW / prime list by the 4-point score with group strength first; treat RS line as a
failure filter, not a timing signal; stop using volume to choose. Needs a longer history (Massive Starter) to confirm.
