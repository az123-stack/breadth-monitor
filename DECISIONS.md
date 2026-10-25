# Trade decision architecture (agreed Oct 16, 2026)

Goal: every trade decision uses everything available (breadth, groups, setups, macro, calendar, news),
without letting unproven inputs move the score.

## Principle
**Code measures, agents read, and only proven layers move the score.**

| # | Layer | Made by | Backtestable? | Starts as |
|---|---|---|---|---|
| 1 | Market: breadth regime, thrust window, money flow | code (`metrics`, `playbook`) | yes | score (already) |
| 2 | Group: Strength, rotation tier, ignition | code (`strength`, `rotation`) | yes | score (already) |
| 3 | Setup: RS, setup type, leaders | code (`tradesetups`, `leaders`) | yes | score (already) |
| 4 | Macro fit: rate / oil / dollar sensitivity × recent macro move | code (`macrofit`) | yes | **info until its backtest passes** |
| 5 | Calendar: earnings dates, CPI / jobs / FOMC | code + Macro agent file | partly | **gate / flag** |
| 6 | Catalyst: why it's moving, real catalyst or not, red flags | Catalyst agent | only forward (ledger) | **flag** |
| 7 | Macro brief: Fed, rates, oil, geopolitics, event risk | Macro agent | only forward (ledger) | **flag / banner** |
| 8 | Review: which layers separate winners from losers | Reviewer agent (weekly) | reads the ledger | proposals only |

Decision engine (`decision.py`): builds one **Decision Card** per pick / top candidate with every layer,
and appends every layer's value to `data/decision_log.csv` each morning. Agent layers become testable once
the log has ~2–3 months of settled rows; the Reviewer then proposes promotion (needs both-halves evidence).

## Approved layers
- **launch** (Oct 25, 2026, Adam): the headline picks now come from the Launch list (`breadth/launch.py`, top 3 a week, weekly position
  trades, 13-week hold, logged in `data/launch_ledger.csv`). Passed: grade A minus C t 3.1 / 2.5 (both halves positive); pick-rule replay
  +9.7% vs SPY over 13 weeks, t 3.66, halves +11.4% / +8.7%. The old 5-day swing Top 2 (playbook + pick_ledger + decision cards) still runs
  and logs unchanged, shown below the Launch picks as "Swing picks (old rule)". Agent layers still cannot move either.

## Rules that keep it honest
- No layer re-ranks the live Top 2 picks until (a) it passes a backtest in both halves of the history
  (t ≥ 2 overall, same sign in each half) and (b) Adam approves.
- Agent output is data written to `docs/*.json`; the page and pipeline work unchanged if a file is missing or stale.
- No look-ahead: every backtested feature uses data up to the signal date only.
- Agents never trade, never change code or weights; they write files and proposals.

## Scorecard (definition of done) — graded by an independent reviewer, not the builder
1. Layers 1–4 computed in code with tests; layer 4 backtested on past setup signals, both halves reported.
2. Calendar layer: earnings within the hold period and macro event days flagged on every card.
3. Decision Cards on the page for the Top 2 picks and top candidates, showing every layer in plain words.
4. `data/decision_log.csv` records every layer for every carded candidate, every day, and is settled with outcomes.
5. Catalyst and Macro agents scheduled, writing structured JSON with sources; page shows their flags; fail-safe.
6. Weekly Reviewer scheduled: reads the log, reports per-layer evidence, proposes changes, applies nothing.
7. Unproven layers do not change live pick ranking (verified by test).
8. Existing + new tests pass; `--rebuild-only` works offline; page checked in a headless browser.
9. Costs and run times documented; CLAUDE.md and the project context updated.
10. No look-ahead in the forward log: nothing learned after an idea's entry (next session's open) is logged for it.

## Research → dashboard loop (the Integrator, Oct 17, 2026)
- **Research ledger** `research/R-*.md`: one finding card per study (works / doesnt / mixed / untested / process), with
  the numbers, both halves, the registry layers it is evidence for, and whether it is integrated. Every research chat
  ends by filing one — failed ideas too, so they aren't re-tested. 24 cards backfilled Oct 17.
- **Layer registry** `data/layers.json`: every input on the ladder idea → tested → info → proven → approved → live
  (retired); only approved/live layers may affect the picks (validated by `python -m breadth.research check` and tests).
- **Integrator** (Claude scheduled task, Saturday 10:07 AM ET, after the Reviewer): reads the digest
  (`python -m breadth.research digest`), the review, the evidence and last week's plan; proposes where each finding plugs
  in, the test that proves it, the result that kills it, effort, priority, new agents (job description) and retirements →
  `docs/agent/plan.json` → "🧠 Integrator plan" on the Decision Cards + push notification. **Proposes only.**
- Building: Adam says "build #N" in the project; a Claude session builds it with tests, `tools/check_info_only.py` and an
  independent grader, updates the card (integrated) and the registry (status), and creates any approved new agent.

## How it runs (built Oct 16–17, 2026)
| When (ET) | What | Writes |
|---|---|---|
| ~12:25 AM Tue–Sat | Daily update (existing): official data, all layers in code, cards for the new date, settles 5-session-old log rows, forward evidence (`layers.study_log`) | `docs/index.html`, `data/decision_log.csv`, `data/layer_evidence.json` |
| 7:02 AM Mon–Fri | **Macro agent** (Claude scheduled task) → `agentfiles publish --kind macro_brief --push` | `docs/agent/macro_brief.json` + rebuild |
| 7:12 AM Mon–Fri | **Catalyst agent** → every carded ticker: the first 15 get full research (why it's moving, direction for a long swing, quality, red flags), the rest an earnings-date check; all with sources. Waits up to 30 min if the overnight data is late | `docs/agent/catalysts.json` + rebuild |
| 10:07 AM Sat | **Integrator** → research cards + registry + evidence → ranked plan, new-agent proposals (applies nothing) | `docs/agent/plan.json` + rebuild; push notification |
| 9:07 AM Sat | **Weekly Reviewer** → refreshes macro backtest + log evidence, writes a plain-English review with proposals (applies nothing) | `docs/agent/review.json` + evidence + rebuild; push notification |

`.github/workflows/agent.yml`: job `save` (validate + commit the JSON; never queued, so it can't be cancelled; fails red if
it can't push) then job `rebuild` (own queue `agent-rebuild`, so it can never cancel a waiting daily update; waits for any
running daily update, rebuilds on the latest `main`, and starts over if `main` moved before its push). Agents confirm the
save with `python -m breadth.agentfiles status`. Staleness: catalysts count only for their exact card date; the macro brief
for up to 4 days; the review 10. Malformed or wrongly-shaped agent files are ignored field by field (never break the cards);
every "<" in the embedded page data is escaped, so agent text can't break the page.
If agent input lands while a daily update runs, the daily update's last step rebuilds again on the newest main.

## Costs and run times
- GitHub Actions: free (public repo). agent.yml ≈ 4–5 min per run (2 a weekday) + ≈ 9 min weekly (evidence refresh).
- Claude scheduled tasks: 2 runs each weekday (macro ≈ 3–6 min, ~8 searches; catalysts ≈ 6–12 min, ~20–40 searches) and
  1 weekly (≈ 10 min). These count toward Adam's Claude plan usage like any session.
- Daily build: cards + log add ~2 s; the 2-year macro history adds ~10 s to the Yahoo fetch.

## Evidence so far
- Macro fit (backtest, 6,258 Trade Setups signals Mar 2025–Oct 2026, actionable 5-session result): 5-day macro tailwind
  +0.25% vs headwind +2.00% (t −1.52; both halves negative: −2.2%, −1.4%). **Not proven → information only.** If anything,
  a recent macro headwind came before better results (mean reversion), but not significantly. 20-day version: no difference.
- Grading round 1 (independent reviewer, Oct 17): 72% (0 fail, 9 partial). All 10 defects fixed the same night:
  per-field agent-file cleaning, per-card isolation, settle window = pick ledger (+5 sessions after entry), page-data
  escaping, red push failures, own rebuild queue, real-date validation, "not checked" excluded from forward tests,
  earnings check for every card, NYSE holidays in session counts, sources shown on cards.
- Grading round 2 (fresh independent reviewer, Oct 17): 82% (0 fail). 12 defects, all fixed:
  **no look-ahead in the forward log** — rows freeze at the entry cutoff (9:30 ET on the next session, `nyse.entry_cutoff`);
  agent files written after it are never logged and their layers don't count; `publish` refuses research after the cutoff;
  the Oct 15 agent columns (researched Oct 17) were blanked. Every agent text field type-checked; decision card wrapped
  so it can't take down the tab; malformed evidence ignored; unconfirmed earnings = unknown (not support); a passed
  backtest still needs `config.APPROVED_LAYERS`; earnings-only checks excluded from news tests (`cat_depth`); daily
  update rebuilds again if agent input arrived during it; NYSE holidays computed by rule (`breadth/nyse.py`);
  clean truncation; `tools/check_info_only.py` (two full rebuilds, hostile agent files) proves picks and pick_ledger.csv
  are byte-identical. Tests: 31.
- Grading round 3 (Oct 17): 72% — critical: `nyse.py` imported dateutil, which the agent save job doesn't install (no
  agent output could be saved; caught before any scheduled run). Fixed: stdlib-only (test runs the agent tools with no
  packages), live save verified; plus corrupt-log recovery, cleaned evidence on the page, hold window through the exit
  day (`EXIT_SESSIONS` = 6 sessions after the card date), market-wide brief tested over dates (Welch), halves weigh dates
  equally, unusable brief/review = missing.
- Agent layers: forward log started Oct 15, 2026 (Oct 15 rows have no agent data; first full agent day: Oct 16 cards,
  researched Mon Oct 19 before the open). Earliest meaningful test ≈ 60+ settled ideas over 20+ dates (~5–6 weeks).
