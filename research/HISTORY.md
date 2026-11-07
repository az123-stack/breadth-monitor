# Early findings (Feb–Oct 2026), moved out of CLAUDE.md Nov 7, 2026

Most of these are also finding cards in research/. Kept here word for word.

## Findings so far (Feb–Oct 2026 history)
- Theme Strength ranks far more stable than Score /8 (rank corr 0.96 vs 0.79); neither predicts
  10-day theme returns, so weights were not tuned to the data.
- Setups pay only in strong breadth (bursts +0.16R, anticipation +0.18R; bursts −0.09R in weak);
  EPs without a catalyst check lose in every regime.
- Trade Setups (Mar–Oct 2026, mixed breadth): Rotation +0.29R, Pullback +0.22R, ATH Magnet +0.12R (tags the high 81%
  vs 76% for any near-high stock), Coiled +0.12R; RS 80+ baseline +0.10R. Confluence (2+ angles) ≈ same R as 1 angle.
- Round Number Magnet first backtest (Oct 14, 2026, ~Mar–Oct 2026): all +0.12R (n 1,859) vs the same strong stocks not near a level
  +0.11R → the level alone adds little. Edge sits in fresh levels in good tape: after a thrust +0.30R all / +0.42R fresh vs base +0.20R;
  strong breadth fresh +0.36R vs base +0.22R; mixed fresh +0.07R vs base +0.17R; weak −0.01R (base −0.10R). Century marks ($50/$100/$200…)
  +0.01R vs smaller levels +0.18R (centuries act more like resistance). Level traded within 5 sessions 57% (closed above 42%); fresh 50% / 36%.
- Group ignition study (Oct 14, 2026; `tools/ignition_study/`; 101 sub-themes, Jan 2025–Oct 2026, event = first day in 20, outcome =
  group vs SPY). Refiners' run (Jun 18 low → +100% by Oct 13 vs SPY +4%) fired in order: crack spread +14% (20d) Jun 24 → group breadth
  0% → 89% above 21 EMA by Jun 29 → RRG leading Jun 30 → dollar flow +0.43, RS-rank +45 pts/10d and 40-day base breakout Jul 6
  (index +16% off the low) → rel 60-day high + confirmed tier Jul 8–9 (+23%). IGNITION = group index at 40-day high + 10-day dollar flow
  > +0.25 + 80%+ of members above 21 EMA + RS-rank (20d rel return pct) up 30+ pts in 10 sessions: all groups 20d +2.9% vs base +1.4%
  (median +1.3% vs +0.3%, t 1.9; 40d +5.0% vs +3.4%, win 57% vs 47%), both halves similar. In strong breadth (10-day ratio ≥ 1.5)
  +4.0% (edge +2.6 pts, t 2.4); otherwise no edge (−0.25). Market money net in vs out (dn_share10) made no difference. Macro driver up
  8%+ in 20d +5.5% (n 16) vs +3.6% (n 52) — small sample. Singles: dollar flow alone, RS jump alone, RRG leading alone ≈ base or worse;
  base breakout +2.5%, rel 60d high +2.7%. Refiners IGNITION dates: May 12 2025 (+27% 40d), Aug 29 2025 (+11.5%), Feb 11 2026 (+20%),
  May 4 2026 (−3%, false start), Jul 6 2026 (+37%), Sep 2 2026 (+9% 20d). Built Oct 14: `rotation.ignition_build` →
  `DATA.themes.rotation.ignition` → "Group ignition" card (Rotation tab, under the money card): gate Act (10-day ratio ≥ 1.5) / Watch only,
  evidence recomputed each build (all / strong / other vs base, next 20 sessions), 🔥 Ignition (fired in last 5 sessions, rel since),
  Warming up (3 of 4 checks, or group breadth thrust in 10 days + RRG leading), checks as of last close, breadth, flow, RS-rank Δ, 20d vs
  SPY, macro drivers (d30, up = +8% or yield up), Strength, top 4 stocks by RS with Trade Setups tags; recent ignitions (60 sessions).
  Live (Oct 14): `ignition.live[g]` (members, idx, hi39, rel20, rk10, f9/d9 signed/total $ vol of the last 9 sessions, brmin9, thrust9,
  rrg, ign20, ago) + `ignition.spy`; `liveIgnition()` in the browser finishes today's checks from Google prices + `refs` ema21 when
  `liveActive()` (sheet session newer than our bars). Verified Oct 13 (copy with that day's bars removed, Oct 13 bars as "live"): 14/15
  flagged groups identical status + checks, breadth/flow/RS-rank within ~0.02; the miss was RRG-only warming (RRG stays last close).
- "Day 1" group breakout study (Oct 14, 2026, `tools/ignition_study/day1.py`, prompted by large-cap pharma breaking out of 2-month
  bear flags on Oct 14 while scoring 0/4 on ignition: index 2.7% below its 40-day high, 10-day flow −0.01, breadth 67%, RS-rank +9).
  DAY 1 = group beats SPY by 2%+ on 1.3×+ normal $ volume, half its members close above their prior 10-day closing high, group 3–15%
  below its 60-day high the day before. Alone: no edge (20d +1.3% vs base +1.4%, n 264); strong breadth +2.7% (t 1.0), otherwise −0.4%.
  Follow-through decides it: Day 1 still above its close 3 sessions later → next 20 sessions +3.4% (n 132); faded → −0.7% (n 129).
  39% of Day-1 events (106/272) became an IGNITION within 15 sessions. Built Oct 14: `rotation.DAY1` rules, `ignition.day1` = {rows (Day 1 in last 6
  sessions: rel_d1, r1, rv, brk, d3 = rel 3 sessions later, since), bt (all/strong/other/held/faded), live (per group hi10 per stock,
  dv50, off, d1_20)} → "Day 1 · watch for follow-through" section of the Group ignition card (between Ignition and Warming up);
  browser `liveDay1` (with `ignLiveGroups`, shared with `liveIgnition`) adds today's Day 1s from Google prices (dollar volume paced by
  `volPace` while open), rolls follow-through forward, and lists "almost a Day 1" groups one rule short (Oct 14: Large-cap Pharma 1.16×).
- Cybersecurity case study + ignition iteration (Oct 14, 2026; `tools/ignition_study/cyber.py`, `cyber2.py`, `iterate*.py`; train/test
  halves split Dec 26, 2025). Cybersecurity Platforms and Identity & Security Tools both bottomed Apr 10, 2026 (rel −45% / −56% vs
  Jun 2025) and ran +131% / +166%. Sequence: group breadth thrust from a washout Apr 21/22 (+16–23% off the low; Identity already
  3 of 4 = warming) → flow > 0.25 Apr 24 → IGNITION May 7 for both (+29–30% off the low; next 40 sessions +28% / +55% vs SPY) →
  re-ignitions Jul 2–6, Aug 13, Sep 17, Oct 9 as they kept making highs. No Day 1 at the start (V-bottoms, > 15% below the 60-day high).
  The same-day gate said "watch" on May 7 (10-day ratio 1.40) although ratio hit 2.95 on Apr 17. Across all groups: leaders present
  (members' median 63-day RS pct ≥ 70 or 25%+ within 3% of a 52-wk high) +4.7% 20d / +8.1% 40d vs +2.0% / +3.0% without (base
  +1.9% / +3.9%), both halves; leaders + strong today +5.8%, leaders + strong only within 15 sessions +4.0% (40d +9.8%), no leaders +
  not strong −0.5%. Not useful: group breadth thrust alone (+1.4%, ≈ base), tight 40-day base (worse, +0.6%), coming from a 25%+
  drawdown (test half ≈ 0). Re-ignitions ≈ first ignitions at 40d. Identity's May 7 ignition had NO leaders (RS med 36) and still ran:
  grades are odds, not vetoes. Built: `IGN.gate_days` 15 (Act = ratio10 ≥ 1.5 any of the last 15 sessions, `ignition.peak15`),
  `ignition_frames` → `rsmed`, `near`, `lead`; rows/live/day1 rows carry `lead {ok, rsmed, near}`; bt adds lead / nolead /
  lead_strong / lead_other / c, day1 bt adds lead / nolead / held_lead / held_nolead; card shows Grade A (leaders + strong window) /
  B / C on ignitions, "★ has leaders" / "no leaders yet" on every row, Leaders column in recent ignitions.
- Record-volume "tells" study (Oct 12, 2026; 2,048 events Oct 2025–Sep 2026, no index/expiry days; 10-session return vs
  SPY, clipped ±50%; tells found on the first 60% by date, checked on the last 40%): all events −4.9% train / −7.7% test.
  Consistent AVOID tells (both halves): gap up 10%+ or up 20%+ (−15 to −18%), volume > 20× avg or > 2.2× old record,
  ADR > 10%, avg $ volume < $5M, down 20%+ over 60 days, 30%+ below the 52-wk high, breakout to a new 20-day high,
  2+ ADR above the 21 EMA. RS did NOT help: RS 95+ +0.7% train → −13% test; the decision tree's only positive leaf
  (RS > 95.5, liquid) +9.5% → −2.6% test. Cleaned set (avg $ vol ≥ $25M, ADR ≤ 10, × avg ≤ 20, gap < 10%, day < +20%,
  ≥ −30% off high, 60-day > −20%) ≈ flat vs SPY. Only candidate: cleaned + 3–10% below the 52-wk high: +1.9% (t 2.7,
  59% beat, n 130; train +2.1% t 2.7, test +1.35% t 1.0; fades by 20 sessions) vs −0.2% / 47% for ANY liquid stock 3–10%
  off its high. Promising, not proven; re-test as more data arrives.
  Retracement follow-up (same events, up days): buying a hold of the record day's 50% / 61.8% / low, or of the 38.2 / 50 / 61.8%
  retracement of the 20-session leg into the record day (touch within 20 sessions, close above), at the hold-day close or on a
  "pop back" (close above the hold day's high within 3 days), with or without a stop 0.5 ADR under the level: negative in both
  halves for all events (−1% to −9% vs SPY); cleaned set slightly positive in train (+0.3 to +2%), negative in test. No edge.
  By market type (first level touched per event, hold-day close): all events negative in every breadth regime and SPY trend
  (strong −6.1% t −4.4, mixed −6.8% t −6.6, weak −2.4% t −2.6; SPY uptrend −6.1% t −8.0, downtrend −3.0%); worst in strong/mixed
  and SPY uptrends. Cleaned set ≈ 0 in all; strong breadth + deeper leg retracements (38.2/61.8%) +2–3% but n 22–31, and strong
  train +1.8% → test −3.2% (n 13). Strong-breadth sample too small to trust.
  SHORT after the pop (up-day records, entries from day 3; cover on close > stop, close > 10 EMA, or 10 sessions; no borrow
  costs): A "turn" = close below record-day low (stop = post-pop peak); B = close below prior 3-day low while below record close
  (stop = 4-day high); C bear flag = ≥ 2 ADR drop then 3–7 day flag ≤ 1.5 ADR, close below flag low (stop = flag high).
  Spike profile (gap ≥ 10% or day ≥ +20% or × avg > 20 or > 2.2× old record) A: +8.1% train / +6.9% test (57% win), but the
  edge is in thin names (< $5M avg $ vol: +10% mean, worst −164%, 8% of trades lose > 30%, median stop 71% away → +0.04R);
  mid $5–25M A +8.8% / B +0.14R; liquid $25M+ ≈ 0 (A +0.3%, B −1.2% test, C −2%). Non-spike: no edge. Bear flag weakest.
- Limits: survivorship bias in backfill, small strong-regime sample, no costs, no intraday H/L/volume.

