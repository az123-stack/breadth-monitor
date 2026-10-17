# Research ledger

One finding card per piece of research (`R-YYYY-MM-DD-short-name.md`). Every research chat ends by filing one —
including research that failed (a "doesnt" card stops us re-testing the same thing). The weekly Integrator agent reads
the cards with the layer registry (`data/layers.json`) and proposes how to use them; nothing changes without Adam's OK.

- New card: `python -m breadth.research new --id R-2026-10-20-my-idea --title "My idea"` then fill it in.
- Check: `python -m breadth.research check` (also run by the tests).
- What the Integrator reads: `python -m breadth.research digest`.

Front matter: id, title, date, status (works / doesnt / mixed / untested / process), kind, horizon, sample, result
(one line with the numbers), halves, layers (registry ids), integrated (yes / partly / no / rejected), source.
