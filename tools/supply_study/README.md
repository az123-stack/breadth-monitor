# Supply breaks study (R-2026-11-07-supply-breaks)
Run from the repo root: `python tools/supply_study/study.py` (~1 min, writes /tmp/supply_study/events.parquet), then
`python tools/supply_study/analyze.py` (tables + the last 30 sessions' live breaks).
