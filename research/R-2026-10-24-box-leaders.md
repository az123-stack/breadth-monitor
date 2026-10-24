---
id: R-2026-10-24-box-leaders
title: "Box trades in leading groups: does ★ / setting up / nuzzled add to the box edge?"
date: 2026-10-24
status: works
kind: setup
horizon: 20 sessions (box study exit), 5 sessions
sample: Jan 2025 – Oct 2026 box trades, next-open entry: 3,784 retest bounces, 2,978 springs, 1,654 ceiling breaks, 5,221 retest shorts, 1,782 failed-breakout shorts
result: retest bounce in a ★ leading group (sub-theme else theme top 30% on 60-day) +0.23R vs −0.02R (edge +0.25R, t 3.2, halves +0.27/+0.25; post-thrust +0.56R); still +0.29R vs −0.02R outside the existing sub-theme-top-20%-60d badge (t 2.7); stock's own nuzzle/lift adds nothing inside ★ groups (+0.24 vs +0.22R); group setting/stepping adds nothing (halves disagree); springs ★ +0.22R vs +0.04R (t 1.7, 2nd half only); shorts in ★ groups much worse (retest −0.28R t −3.5, failed breakout −0.23R t −3.4)
halves: retest ★ +0.27 / +0.25; ★ outside top-20% badge +0.33 / +0.28; shorts ★ −0.33 / −0.24
layers: [stairs, box_favorites]
integrated: partly
source: tools/box_stairs/ (Adam, Oct 24 2026: "couple this with our box setups" → "your favorite of these trades")
---
**Idea.** Adam liked the stair-step names ("leading names in great setups") and asked to couple them with the box trades, then for a
"favorites" list. Before ranking anything, test whether the stair-step tags actually lift box-trade results.

**How it was tested.** `boxstudy.collect` + `features` (the same events the Box trades research uses: signal close, buy next open, stop
per trade type, 20-session exit, R floored 0.3 ADR). Each trade tagged at its signal date with: the stock's own state (nuzzled within 5
sessions, lifting within 3, step break within 3), its group (sub-theme, else theme) ★ leading = top 30% of groups on 60-day return,
and the group setting up / stepping up together (stairs.states). R with vs without each tag, Welch t, split halves at the median date.
Overlap check: ★ vs the box study's existing "sub-theme top 20% on 60-day return" confluence.

**Result.** Retest bounce: ★ leading group +0.23R vs −0.02R (t 3.2, halves +0.27 / +0.25, R5 +0.07); right after a thrust +0.56R.
It is not just the existing badge: among trades WITHOUT the sub-theme-top-20% badge, ★ (theme fallback, top 30%) +0.29R vs −0.02R
(t 2.7, halves +0.33 / +0.28). The stock's own nuzzle/lift: +0.10R overall (t 1.6; R5 t 2.1) but nothing once the group is ★ (+0.24 vs
+0.22R). Group setting/stepping: +0.05R, halves +0.22 / −0.14 (no). Springs: ★ +0.22R vs +0.04R (t 1.7, halves +0.01 / +0.39: unproven).
Ceiling breaks: stock step break +0.16R (t 1.8), group setting/stepping +0.17R (t 1.6): leads only. Shorts: every ★ cut made them worse
(retest rejection −0.28R, t −3.5; failed breakout −0.23R, t −3.4) — same message as "in vogue": leaders' boxes get bought.

**Caveats.** ~2 years, mostly a bull market, survivors only, today's theme lists, no costs; ★ and the existing group badges overlap
heavily (502 of 825 ★ retests also carry the top-20% badge).

**How it's used.** Built (info only): Box trades card "★ My favorites right now" (template.html `isBoxFav` / `boxFavRank`): long box
trades actionable now (retest go/at, spring failed), grade A–B, ★ leading group, reward:risk from the last close ≥ 1.5 and "at the line"
within 1.5 ADR (chase guards, judgment, not tested); ranked acting-now first, then graded expectation, then own nuzzle/lift, then RS; top 5
+ "★ Favorites" filter chip. NOT yet a box confluence: adding ★ to boxstudy.conditions would change grades and the Box Retest playbook
order (which feeds the Top 2 picks), so it needs Adam's approval per DECISIONS.md. It passes the proven rule (t ≥ 2, n ≥ 30, both halves).
