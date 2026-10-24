Box trades × stair steps (Oct 24, 2026; card R-2026-10-24-box-leaders).
`python tools/box_stairs/collect.py` (~80 s): every past box trade with features (boxstudy.collect + features) → /tmp/box_ev.pkl.
`python tools/box_stairs/test.py`: tags each trade with the stair-step state at its signal date (stock nuzzled/lifting/break,
★ leading group = sub-theme else theme top 30% on 60-day return, group setting/stepping) and prints R with vs without, Welch t, halves.
