---
id: R-2026-11-07-librarian
title: Librarian: weekly Project brief rewritten from the repo, proposed for approval (the "sleep cycle")
date: 2026-11-07
status: process         # works | doesnt | mixed | untested | process
kind: process           # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: weekly
sample: first draft Nov 7, 2026 (58 cards, 42 layers, 11 pinned rules)
result: first brief 1,947 words vs ~5,000 in the old Project context doc, which had missed every card after Oct 28 and still described retired pieces (Top 2 as headline, 79 themes / 119 groups); all 58 cards named, layer statuses checked against the registry
halves: n/a (process)
layers: []              # ids from data/layers.json this is evidence for (empty = new idea)
integrated: yes         # yes | partly | no | rejected
source: chat Nov 7, 2026 (Adam's "sleep cycle agent" idea); breadth/librarian.py; research/PINNED.md
---
**Idea.** Adam proposed a weekly "sleep cycle" agent: pull the week's chats, score items by recency and frequency, prune and
merge, and push the result into the Claude Project as the new baseline.

**What changed from the proposal (and why).**
- Source = the repo, not chats. Decisions already land in finding cards, DECISIONS.md, the layer registry and ROADMAP; chats mix
  Adam's decisions with Claude's suggestions, and mining them risks turning a suggestion into a rule. Claude's own memory already
  handles chat-level preferences.
- No frequency decay for rules. The most important rules are said once (only approved layers move picks; never ask for the API key;
  no look-ahead). They live in research/PINNED.md and are copied word for word every week; the check fails a draft that edits one.
- Propose, don't inject. Same rule as every other agent: the Librarian publishes a draft (docs/agent/brief.json) and a change list;
  nothing changes until Adam says "approve brief". Then a session runs `librarian approve` (research/BRIEF.md) and replaces the
  Project doc.

**Checks in code.** 5 required sections in order; every pinned rule verbatim; ≤ 3,000 words; `layer_id (status)` must match
data/layers.json; every R- id must exist; every card filed on/after the approved brief's draft date must be named; no
secret-looking strings; the draft can't claim to be approved. Tested in `test_librarian_brief` (each failure case caught).

**First run (Nov 7).** Draft written in the build session from `librarian pack`: 1,947 words, all 58 cards, 11 pinned rules, 42 layers.

**Caveats.** A clean check doesn't prove the summary is right; Adam's read is the real gate. Watch for drift over ~4 runs.

**How it could be used.** Every Market Dashboard chat starts from a current, short brief instead of a month-old one.
