"""Timelines of Cybersecurity Platforms and Identity & Security Tools: when did each indicator fire around their 2026 runs?"""
import sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/home/claude/breadth-monitor")
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400)
D = pickle.load(open("frames.pkl", "rb"))
I, rel = D["I"], D["rel"]
for g in ["Cybersecurity Platforms", "Identity & Security Tools"]:
    x = pd.DataFrame({"idx": I[g], "rel": rel[g]})
    x["rel_n"] = x.rel / x.rel.iloc[0]
    # weekly snapshot to see the shape
    w = x.loc["2025-06-01":].resample("W-FRI").last()
    w["idx%"] = (w.idx / w.idx.iloc[0] - 1) * 100; w["rel%"] = (w.rel / w.rel.iloc[0] - 1) * 100
    print("\n=====", g, D["members"][g]); print(w[["idx%", "rel%"]].round(1).T.to_string())
