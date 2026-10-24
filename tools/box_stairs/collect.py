import sys, os, pickle
sys.path.insert(0, "/home/claude/breadth-monitor"); os.chdir("/home/claude/breadth-monitor")
import numpy as np, pandas as pd
from breadth import store, strength, config, stairs, boxstudy as BS, boxes as BX
b = store.apply_splits(store.load_bars(), store.load_splits())
uni = set(pd.read_csv("data/universe.csv").iloc[:, 0])
br = pd.read_csv("data/breadth.csv", parse_dates=["date"]).set_index("date")
w = strength.wide_all(b); dates = w["c"].index
cols = [t for t in w["c"].columns if t in uni]
C, V, H, L = (w[k][cols].to_numpy() for k in ("c", "v", "h", "l"))
dv = pd.DataFrame(C * V).rolling(50, min_periods=30).mean().to_numpy(); liq = (C >= 5) & (dv >= 20e6)
ADR = (pd.DataFrame(H / L).rolling(20, min_periods=15).mean().to_numpy() - 1) * 100
raw = strength.rs_raw(w["c"][cols]); rs = (raw.where(pd.DataFrame(liq, index=dates, columns=cols)).rank(axis=1, pct=True) * 99).clip(1, 99).to_numpy()
spy, spyo = w["c"][config.BENCHMARK].to_numpy(), w["o"][config.BENCHMARK].to_numpy()
sub = store.load_subthemes(); th = store.load_themes(); th = th[th["role"] == "member"]
sub_of, theme_of = dict(zip(sub["ticker"], sub["subtheme"])), dict(zip(th["ticker"], th["theme"]))
grp = BS.group_frames(w["c"], sub.groupby("subtheme")["ticker"].apply(list).to_dict(), spy)
thm = BS.group_frames(w["c"], th.groupby("theme")["ticker"].apply(list).to_dict(), spy)
mk = BS.market_frame(dates, br, spy)
ev = BS.features(BS.collect(w, cols, liq, rs, ADR, spy, spyo), w, cols, rs, ADR, spy, mk, grp, sub_of, theme_of, thm)
pickle.dump(ev, open(os.environ.get("OUT", "/tmp/box_ev.pkl"), "wb"))
print(len(ev), list(ev[0].keys()))
