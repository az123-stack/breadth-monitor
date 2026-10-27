# Trade Stories · writing guide

Adam is a Qullamaggie-style swing trader. Trade Stories are the running storylines moving the market: news, earnings, macro
and policy pulled into one cohesive case file per story, with how to trade it while it develops. He reads them to
UNDERSTAND the market, because understanding is what gives him the confidence to hold a trade. Plain words, no jargon
without a one-clause explanation.

## The job (once a day, after the close)
1. `python3 -m breadth.stories facts` → open stories, their price check (does price agree with the story?), scorecard,
   stocks in their groups, catalysts due or just past, THE TRADE, and the exact sub-theme names.
2. Read today's chapter (docs/story.json, latest pm) for today's researched why. Research more with WebSearch where a story
   moved or a catalyst happened (earnings results, data, policy). Never invent a fact, number, date or link.
   Earnings clusters: the chapter's **What earnings said:** section (from the fact sheet's EARNINGS CLUSTERS block) names
   groups where several companies reported the same thing this week. Add each confirmed cluster as ONE timeline item on the
   story it belongs to ("Earnings: AMT, CCI, SBAC all raised guidance on carrier spending", source = one of the reports,
   reaction = the group's move); start a new story only when 3+ companies in a group say the same thing and no story covers it.
3. Copy docs/stories.json to /tmp/stories.json and EDIT it:
   - Update each open story that moved: add today's timeline items (with sources and the price reaction), rewrite the parts of
     the thesis that changed, set `changed` (one sentence: what changed today, or "" if nothing), update status, catalysts
     (move any that happened into the timeline with the result) and `trade`.
   - Start a new story only when a real, sourced narrative is driving several groups (or a big group) for more than a day.
   - Resolve a story when it has played out or price has disagreed for 5+ sessions (status "resolved", say how it ended in
     `changed`). Merge stories that turned out to be the same thing. Max 6 open.
4. `python3 -m breadth.stories check --file /tmp/stories.json` (fix every warning), then
   `python3 -m breadth.stories publish --file /tmp/stories.json --push` ONCE.

## Status
- **building**: the story is gaining force: new sourced events and price agrees (long groups beating the short side).
- **peaking**: still true but crowded or extended: price agrees on 20 days but wobbles on 5 (seesaw), or everyone is talking
  about it, or the big confirming catalyst is just ahead.
- **fading**: price check "disagrees"/"turning" for several sessions, or the key catalyst came out against it.
- **resolved**: over. Keep it with a one-line ending.
Let the price check lead: if the story says one thing and price says another for 5+ sessions, price wins.

## Fields (JSON, one object per story in "stories")
- `id` (slug, never change it), `title` (under 60 chars, names the cause, e.g. "AI spending gets repriced"), `status`,
  `started` (YYYY-MM-DD the story began), `summary` (one sentence a trader can repeat), `changed` (today's change).
- `thesis`: `what` (what is happening, with the numbers from the fact sheet), `why` (the 1–3 real drivers, inline
  [source](url) links), `how` (the mechanism: who sells, who buys, why the money lands where it does), `real` (real
  buying or a seesaw, and what the price check says), `confirm` (what would prove it / what would break it, with dates).
  2–4 sentences each, markdown allowed (**bold**, [links](url)).
- `timeline`: [{date, event, source (site name), url, reaction (price move that day, from the chapters/fact sheet)}].
  Keep the important beats only (8–15 per story); never remove sourced history except to trim duplicates.
- `groups`: {long: [sub-themes the story favours], short: [sub-themes it hurts]} using EXACT names from the fact sheet.
  These drive the price check and scorecard, so pick groups the story really moves (3–8 each; short may be empty).
- `tickers`: {long: [...], short: [...], watch: [...]} the names that best express it (RS leaders in the long groups from the
  fact sheet; the counter-trade names in `watch`).
- `catalysts`: [{date, time, name, why}] upcoming events that confirm or break it (earnings, data, Fed, OPEC, policy).
- `trade`: how to trade it NOW, 3–5 bullets in markdown: the expression (which groups/stocks, using the dashboard's setups
  and "don't chase" flags), entry style (pullback / flag / breakout, never chase extended days), the stop logic, what to do
  into the next catalyst (size down, hold, take partials), and the counter-trade trigger. Information, not orders.
- `related`: ids of stories it feeds or depends on (e.g. oil → rates → AI spending).

## Style
Plain English, specific numbers, dates and sources. Say "no clear driver found" rather than guess. Don't repeat the daily
chapter; write the arc. A good story reads like a briefing note from a sharp macro trader to a swing trader.
