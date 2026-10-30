# How to write a Market Monitor story chapter

You are writing the next chapter of a running market narrative for Adam, a swing trader who trades like Kristjan Kullamägi
(breakouts, high tight flags, episodic pivots, leaders in leading groups) and waits for breadth thrusts before pressing.
The chapter appears at the top of the Read-out tab of his dashboard. It must pull every part of the market together into a
story he can absorb in two minutes, and it must CONTINUE the story from the previous chapters (they are in the fact sheet).

## Ground rules
- Use only numbers in the fact sheet for market data. Never invent a figure, ticker, or event.
- THE WHY IS THE POINT. Adam wants to know *why* money is moving, not just where. For every group on the fact sheet's
  "WHY research list" (and anything else central to the story), run WebSearch (several short queries: the group name plus
  its biggest tickers, "stocks today", "earnings", the date) and find the actual driver: earnings/guidance (with the key
  number, e.g. "medical cost ratio 88.4% vs 89.9%"), policy/regulation, macro (rates, oil, dollar), deals, analyst moves,
  sector news. Use search snippets; WebFetch a page only when a snippet is too thin. Then classify each move:
  **catalyst** (its own news), **rotation/shelter** (no news; defensive money hiding), **sympathy** (moving with a
  peer's news), or **unexplained** (say so plainly; never guess a reason). Say whether price confirms the news
  (Day 1 / ignition / follow-through from the fact sheet) and whether the catalyst is likely to repeat.
- Every news claim needs a source: inline markdown link `[short source name](https://...)` right after the claim.
  Only link URLs you actually got from WebSearch / WebFetch results.
- Plain English, short sentences, no jargon without a gloss. Present tense for today, past tense for history.
- Lead with what changed since the last chapter: did the scenario play out, flip, or stall? Name it ("Scenario A held for a
  fourth day", "The money came back, and it went to …").
- Evidence lines (historical tendencies) are context, never promises. Say "has tended to", "historically", give n when small.
- Name groups and stocks specifically. Every "trade" line should point at concrete groups/stocks from the fact sheet
  (ignitions, Day 1s, leaders, held-up / sold-hardest baskets, picks). No position sizing advice beyond "small / normal / press".
- 400–650 words (am chapter: up to 750 with the In play section). Markdown: short paragraphs, **bold** lead-ins, "- " bullets. No headings deeper than "**Bold:**" lead-ins.

## Structure (keep these lead-ins so chapters read the same every day)
**Where we are:** 2–4 sentences: the story so far + today's update (money in/out, how much, where it went, breadth, indexes).
**In play today:** (am chapter only, right after "Where we are") where the extra edge is today, so Adam knows where to focus.
  See "In play (morning chapter)" below. 3–6 bullets, best edge first, then one "Skip:" line.
**Why it's moving:** 3–6 bullets, one per key group: the driver in one line with the key number, its type (catalyst /
  rotation / sympathy / unexplained), and the source link. Lead with the groups that matter most to the story and the trades.
**What earnings said:** (only when the fact sheet has an EARNINGS CLUSTERS block; see "What earnings said" below) 1–4
  bullets, one per group where several companies reported the same thing this week.
**AI monetizers:** (only when the fact sheet's AI MONETIZERS block lists CHANGES) one bullet per name ADDED or REMOVED: what the
  market just said about its AI money (the report, the key AI number, the reaction) with a source. Adam watches this list: it is the
  set of companies Wall Street believes are actually making money from AI. If a candidate on that block is clearly AI-driven, say so
  in one line ("worth adding: X, because ...") so Claude can add it to the pool.
**What it means:** 2–3 sentences tying it together (rotation vs leaving, leadership, thrust setup, regime), using the why.
**Scenario A — money keeps leaving:** signs to watch (concrete thresholds from the scenario engine) and what to trade / avoid.
**Scenario B — money comes back:** signs to watch, and WHERE it is likely to go and how to trade each case (snapback in the
  sold-hardest 60-day leaders vs rotation into what held up), citing the evidence lines.
**Leaderboard:** 2–3 bullets: strongest sub-themes and what moved in/out of the top 10, best stocks, notable changes.
**Your trades:** 1–3 bullets on picks / open trades (trigger, stop proximity) in the context of the story.
**Next tell:** 1–3 specific things to watch next session (a follow-through day, a level, a group).
**How markets work:** one short teaching point (3–5 sentences) drawn from what is happening right now, so Adam builds
  pattern recognition. Name the pattern (e.g. "when tech stalls, money parks in health care"), explain the mechanism
  (who is buying/selling and why: earnings that don't depend on the economy, fund mandates that must stay invested,
  rate sensitivity, short covering, sector rotation through the cycle), say when it usually holds and when it breaks,
  and how a swing trader uses it. Tie it to the dashboard's own evidence when there is some (comeback study, ignition,
  Day-1 follow-through, record-volume warnings) and mark general market knowledge as such. Pick a new pattern each time:
  check the previous chapters in the fact sheet and don't repeat one unless today adds something new.

## Slots
- am (written 7:52 AM ET, posted ~8:00): official close of the last session + pre-market. Frame today's open against the story.
- data (written 8:44 AM ET, only on days with an 8:30 AM release): the data card. See "Data days" below.
- pm (written 4:50 PM ET): today's close from Google prices (estimates; official numbers land overnight). Say how today moved the story.

## In play (morning chapter)
The fact sheet's "IN PLAY candidates" block lists what code measured before the open: stocks gapping 4%+ (and 1.5+ ADRs) on
steady pre-market trading, with the reasons stacked (possible EP, leader RS 85+, its group gapping with it, on Adam's lists,
earnings, catalyst-agent read) and warnings (red flags, record-volume up day, gap into overhead supply); sub-themes gapping 1%+
with breadth (60%+ of members the same way), fresh ignitions / Day 1s, top-10 groups; and Adam's own names moving pre-market.
Your job is the WHY and the judgment:
1. WebSearch "stocks moving premarket today <date>", "earnings before the open <date>" and "after hours earnings <yesterday>"
   to catch reports and news the code can't see, then WebSearch each candidate you consider using ("<TICKER> stock premarket",
   "<TICKER> earnings"). Find the hard reason: earnings beat/raise with the key number, guidance, FDA, contract, M&A, upgrade,
   sector news, or a peer's news (sympathy). A gap with no news you can find is "no clear catalyst": say so.
2. Pick 3–6 with the MOST edge. Edge = a real catalyst AND something structural: leader (RS 85+) in a strong / igniting group,
   an EP (8%+ gap on real news, ideally a first gap out of a base), a whole group gapping together (the money is going there),
   or one of Adam's setups reaching its trigger. Prefer liquid names. Long-side first; a big gap-down in a leader or a whole
   group gapping down is in play as a "stay away / exit" note, not a short idea.
3. Each bullet: **TICKER or group** — gap and the one-line why with a source link — the edge (why it can keep going) — the plan in
   one clause for a Qullamaggie-style trader (e.g. "opening-range high after the first 5–30 min, stop the day's low; skip if it
   gives back half the gap" for EPs; "wait for the first pullback to hold the gap" for extended names; "your trigger $X" for picks).
4. End with one **Skip:** line: big movers with no catalyst, news that caps the upside (a cash takeover), red flags, gaps into
   overhead supply (30%+ below the high), record-volume climaxes. Never invent a catalyst; never present a candidate as a
   guaranteed trade. The pre-market gap is a snapshot (written ~7:50 AM ET); say gaps can change by the open.

## Data days (morning chapter)
Before writing the am chapter, WebSearch today's US economic calendar ("economic calendar today <date>", "CPI release date
<month year>", "Fed speakers today", "FOMC <month year>"). Count only MARKET-MOVING items: CPI, PPI, core PCE / personal income,
nonfarm payrolls, retail sales, GDP, ISM manufacturing / services, JOLTS, FOMC decision days (2:00 PM statement, 2:30 press
conference), FOMC minutes, Fed Chair testimony or major speeches, Treasury refunding, a government shutdown / debt-ceiling deadline.
Skip routine items (weekly jobless claims unless a big surprise is expected, regional Fed surveys, small auctions, minor speakers).
- If there are any: open the chapter with one line, before "Where we are": **Data today:** e.g. "8:30 AM CPI (September),
  10:00 AM consumer sentiment. This chapter is written before the release; the data card at ~8:45 covers the reaction." Add
  one sentence on why it matters for the story (rate-cut odds, growth vs defensives, small caps). Then pass the events to publish
  with `--events-file events.json`, a JSON list like
  `[{"time": "8:30 AM", "name": "CPI (September)", "why": "first inflation read since the selloff; hot = pressure on growth"}]`
  (time as "H:MM AM/PM" ET, name short, why one short clause). The Read-out tab shows them in a banner at the top.
- If there are none: no line, no events file.

## Data card (slot data, 8:44 AM ET)
Run `python3 -m breadth.story facts --slot data`. It lists today's events (from the morning chapter) and the pre-market reaction:
latest snapshot vs last close and vs the last snapshot before 8:30. Only write a card if an 8:30 AM release came out today;
otherwise stop. 120–250 words, these lead-ins:
**The numbers:** each release: actual vs consensus vs prior (headline and core where relevant), with a source link from WebSearch.
  Say hot / cool / in line in plain words.
**How the market took it:** futures, 10y yield / note futures, dollar, and the rate-sensitive ETFs, using only the fact sheet's
  moves since before 8:30. Say if the reaction is big or small (S&P futures moves under ~0.3% are small).
**What it means today:** 2–3 sentences: rate-cut odds direction (only if a source says so), which kinds of stocks it helps or
  hurts (growth / small caps / banks / homebuilders vs defensives), and how it fits the story's current scenario.
**Watch at the open:** 1–2 bullets: concrete things to check in the first 30 minutes (does the futures move hold, group or level).
Title under 60 characters, e.g. "CPI runs hot; yields jump, Nasdaq futures slip". Publish with
`python3 -m breadth.story publish --slot data --title "..." --branch <same as this morning's chapter> --file card.md --push`.

## Branch
Pass --branch with the scenario engine's branch (A / B / W / none) unless the facts clearly contradict it; if you override, say why in the text.

## The trade (every chapter)
The fact sheet's "THE TRADE" block names the market's main rotation (winning vs losing groups over 20 sessions), its
state (on / cooling / fading / over), and whether the winners hold up when the losers bounce (real buying) or give it back
(a seesaw). Mention it in one line inside **Where we are** ("The trade: Software + Consumer over AI Infrastructure, day 12,
still on, but a seesaw"). Say plainly when its state changes since the last chapter. Use only the fact sheet's numbers.

Then write a **The trade, explained:** section (place it right after **What it means**). Adam wants to UNDERSTAND the trade,
not just see which groups lead: it is what gives him the confidence to hold. It is shown on its own at the top of the Read-out
("The trade" card), so it must stand alone. 5 bullets, each starting with its bold label, plain words, 120–220 words total:
- **What's happening:** one sentence: money moving from <losing side> to <winning side>, how long, how big (fact sheet).
- **Why:** the 1–3 real drivers behind the whole rotation (not just today), each with a source link from your research
  (earnings/guidance, rates, oil, credit, policy). If you can't find a driver, say "no clear driver found" — never invent one.
- **How it works:** the mechanism in plain words: who is selling and why, why the money lands where it does (e.g. funds cut
  crowded AI-capex winners and buy earnings that don't depend on AI spending; falling yields help rate-sensitive groups).
- **Real or seesaw:** the fact sheet's read in plain words and what history says it usually means next.
- **What confirms it / what breaks it:** specific upcoming events with dates (earnings, data, Fed) that would prove or
  disprove the "why", plus the code's kill switch (3 closes under the 20-day average) and the comeback trigger.

## What earnings said (earnings season)
Adam wants to know when several companies in ONE group say the same thing in the same week: that is a statement about the
theme, not about one stock (e.g. three tower REITs all raising guidance on carrier spending; two chip-equipment makers both
guiding China sales down). The fact sheet's EARNINGS CLUSTERS block lists the groups where 2+ members had an earnings-style
day (big gap on heavy volume) in the last 5 sessions (pm: plus today), the direction, the group's move, and how the members
that did NOT report moved (the market treating it as a read-through).
1. For each cluster (UP / DOWN first, mixed only if it matters to the story), WebSearch each reporter ("<TICKER> earnings
   <month year>", "<TICKER> guidance") and confirm it was earnings. If one wasn't (deal, FDA, downgrade), drop it from the
   cluster; a cluster needs 2+ real reports.
2. Find the COMMON message, with the key number and a source link per company: demand (orders, backlog, bookings), pricing,
   margins, guidance raised/cut, a named driver (AI capex, China, the consumer, rates, oil). Say whether the reports AGREE
   (a theme) or only moved the same way for different reasons (not a theme: say so).
3. Bullet per real cluster: "**<Group>:** <A>, <B> (and <C>) all <common message> (<key numbers with links>). Read-through:
   the members that haven't reported <moved +x% / didn't move> → <the market is / isn't treating it as a group story>.
   Next up: <ticker date> (from the fact sheet's 'reporting next')."
4. Use it: a theme confirmed by its own earnings belongs in **Why it's moving**, **The trade, explained** (Why / What
   confirms it) and the Trade Stories (after-close task: add each confirmed cluster as a sourced timeline item to the story
   it belongs to, or start a story when 3+ companies in a group say the same thing and nothing covers it).
Evidence line from the fact sheet, in plain words: after UP clusters the not-yet-reported members drifted up vs other groups
over the next 20 sessions (not proven yet); DOWN clusters did NOT keep spreading (bad news in a group tended to be priced in
fast). Never call it a buy signal.

## Trade Stories
The Trade Stories tab (docs/stories.json) holds the running storylines. In the morning chapter, if a story's catalyst lands
today or overnight news moved one, say so in one line ("Trade story: AI spending repriced: Microsoft reports tonight").
The after-the-close task updates the stories themselves (stories_guide.md) AFTER publishing the chapter.
