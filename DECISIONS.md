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

## How it runs (built Oct 16–17, 2026)
| When (ET) | What | Writes |
|---|---|---|
| ~12:25 AM Tue–Sat | Daily update (existing): official data, all layers in code, cards for the new date, settles 5-session-old log rows, forward evidence (`layers.study_log`) | `docs/index.html`, `data/decision_log.csv`, `data/layer_evidence.json` |
| 7:02 AM Mon–Fri | **Macro agent** (Claude scheduled task) → `agentfiles publish --kind macro_brief --push` | `docs/agent/macro_brief.json` + rebuild |
| 7:12 AM Mon–Fri | **Catalyst agent** → up to 15 carded tickers: why it's moving, direction, quality, next earnings date, red flags, sources | `docs/agent/catalysts.json` + rebuild |
| 9:07 AM Sat | **Weekly Reviewer** → refreshes macro backtest + log evidence, writes a plain-English review with proposals (applies nothing) | `docs/agent/review.json` + evidence + rebuild; push notification |

`.github/workflows/agent.yml`: job `save` (validate + commit the JSON; never queued, so it can't be cancelled) then job
`rebuild` (queued behind the daily update in group `breadth-update`; checks out `main`, so a cancelled pending rebuild is
harmless). Staleness: catalysts count only for their exact card date; the macro brief for up to 4 days; the review 10.

## Costs and run times
- GitHub Actions: free (public repo). agent.yml ≈ 4–5 min per run (2 a weekday) + ≈ 9 min weekly (evidence refresh).
- Claude scheduled tasks: 2 runs each weekday (macro ≈ 3–6 min, ~8 searches; catalysts ≈ 6–12 min, ~20–40 searches) and
  1 weekly (≈ 10 min). These count toward Adam's Claude plan usage like any session.
- Daily build: cards + log add ~2 s; the 2-year macro history adds ~10 s to the Yahoo fetch.

## Evidence so far
- Macro fit (backtest, 6,258 Trade Setups signals Mar 2025–Oct 2026, actionable 5-session result): 5-day macro tailwind
  +0.25% vs headwind +2.00% (t −1.52; both halves negative: −2.2%, −1.4%). **Not proven → information only.** If anything,
  a recent macro headwind came before better results (mean reversion), but not significantly. 20-day version: no difference.
- Agent layers: forward log started Oct 15, 2026. Earliest meaningful test ≈ 60+ settled ideas over 20+ dates (~5–6 weeks).
