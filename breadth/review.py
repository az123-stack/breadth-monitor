"""Review flag for the Trade Setups: tells you when the market has moved away
from what the current setups were chosen for, so they get revisited.

The setups were last reviewed against a baseline saved in data/setups_review.json
(date, breadth regime, top themes). Each daily build checks:
  regime    breadth regime has been different from the baseline for 3+ sessions
            (and says how each setup has traded in the new regime)
  dry       a setup has had 0 qualifying stocks for 3+ sessions in a row
  slumping  a setup's last 30 sessions of completed signals average <= -0.15R (n >= 10)
  leaders   3 or more of the top 5 themes by Strength have changed since the review
  stale     30+ days since the last review
  thrust    a major Breadth thrust / Follow-through fired in the last 3 sessions
            (same morning, with the post-thrust playbook in the reason)
Mark a review done (after rewriting setups with Claude):
    python -m breadth.review --mark-reviewed
"""
import argparse
import json
from datetime import date

import pandas as pd

from . import config

REGIME_DAYS = 3
DRY_DAYS = 3
SLUMP_R, SLUMP_N = -0.15, 10
LEADER_CHANGES = 3
STALE_DAYS = 30
NAMES = {"round": "Round Number Magnet", "ath": "ATH Magnet", "pullback": "Leader Pullback", "rotation": "Rotation Rookie", "kq": "Qullamaggie Flag", "vcp": "Minervini VCP", "box": "Box Retest"}
REG = {"strong": "Strong", "mixed": "Mixed", "weak": "Weak"}


def _base_path():
    return config.DATA_DIR / "setups_review.json"


def _counts_path():
    return config.DATA_DIR / "setup_counts.csv"


def regime_of(row):
    if row["ratio5"] >= 1.5 and row["ratio10"] >= 1.5:
        return "strong"
    return "weak" if row["ratio10"] < 1 else "mixed"


def load_baseline():
    p = _base_path()
    try:
        return json.loads(p.read_text()) if p.exists() else None
    except Exception:
        return None


def top_themes(themes, n=5):
    rows = sorted((r for r in themes if r.get("strength") is not None), key=lambda r: -r["strength"])
    return [r["theme"] for r in rows[:n]]


def record_counts(day, setups):
    """Append (or replace) today's qualifier counts; returns the full history."""
    p = _counts_path()
    df = pd.read_csv(p, dtype={"date": str}) if p.exists() else pd.DataFrame(columns=["date"])
    row = {"date": day, **{s["key"]: s["count"] for s in setups}}
    df = pd.concat([df[df["date"] != day], pd.DataFrame([row])]).sort_values("date")
    df.to_csv(p, index=False)
    return df


def evaluate(theme_data, breadth, today=None):
    X, B = theme_data.get("trade_setups"), theme_data.get("trade_bt")
    if not X:
        return None
    base = load_baseline()
    day = theme_data["date"]
    counts = record_counts(day, X["setups"])
    reasons = []
    try:
        from . import playbook
        th = playbook.thrust_today(breadth)
        if th and (not base or th["date"] > base.get("data_date", "")):
            pb = theme_data.get("playbook") or {}
            ranks = pb.get("rows") if pb.get("state") == "thrust" else pb.get("if_thrust")
            top = [f"{r['name']} ({r['avg_r']:+.2f}R)" for r in (ranks or []) if r["verdict"] in ("Focus", "Selective")][:3]
            avoid = [r["name"] for r in (ranks or []) if r["verdict"] == "Avoid"]
            reasons.append({"kind": "thrust", "text": f"{th['label']} on {th['date']}. Switch to the post-thrust playbook: "
                            + (", ".join(top) if top else "press the leaders")
                            + (f"; pause {', '.join(avoid)}" if avoid else "") + "."})
    except Exception:
        pass
    regs = [regime_of(r) for _, r in breadth.tail(REGIME_DAYS).iterrows()] if len(breadth) else []
    now = regs[-1] if regs else None
    if base and regs and len(set(regs)) == 1 and now != base.get("regime"):
        perf = ""
        if B:
            parts = []
            for k, nm in NAMES.items():
                o = (B["setups"].get(k) or {}).get(now) or {}
                if o.get("n"):
                    parts.append(f"{nm} {o['avg_r']:+.2f}R")
            perf = f" In {REG[now].lower()} breadth so far: " + ", ".join(parts) + "." if parts else ""
        reasons.append({"kind": "regime", "text": f"Breadth has been {REG[now]} for {REGIME_DAYS}+ sessions; the setups were chosen in "
                                                  f"{REG.get(base.get('regime'), base.get('regime'))} breadth.{perf}"})
    for s in X["setups"]:
        k = s["key"]
        if k in counts.columns:
            last = counts[k].tail(DRY_DAYS)
            if len(last) == DRY_DAYS and (last.fillna(0) == 0).all():
                reasons.append({"kind": "dry", "text": f"{s['name']} has had no qualifying stocks for {DRY_DAYS} sessions."})
        rec = (B or {}).get("recent", {}).get(k) or {}
        if rec.get("n", 0) >= SLUMP_N and rec.get("avg_r") is not None and rec["avg_r"] <= SLUMP_R:
            reasons.append({"kind": "slump", "text": f"{s['name']} is slumping: {rec['avg_r']:+.2f}R a trade over its last {rec['n']} signals."})
    tops = top_themes(theme_data.get("themes", []))
    if base and base.get("top_themes"):
        new = [t for t in tops if t not in base["top_themes"]]
        if len(new) >= LEADER_CHANGES:
            reasons.append({"kind": "leaders", "text": f"Leadership has rotated: {len(new)} of the top 5 themes are new since the review ("
                                                       + ", ".join(new) + ")."})
    today = today or date.today()
    days = None
    if base and base.get("date"):
        days = (today - date.fromisoformat(base["date"])).days
        if days >= STALE_DAYS:
            reasons.append({"kind": "stale", "text": f"It's been {days} days since the setups were reviewed."})
    if not base:
        reasons.append({"kind": "stale", "text": "The setups have never been reviewed against a baseline."})
    return {"flag": bool(reasons), "reasons": reasons, "regime_now": now, "top_themes": tops,
            "baseline": base, "days_since": days,
            "checks": {"regime_days": REGIME_DAYS, "dry_days": DRY_DAYS, "slump_r": SLUMP_R, "stale_days": STALE_DAYS}}


def mark_reviewed(note=""):
    """Save today's market as the baseline the setups were reviewed against."""
    from . import store
    br = store.load_breadth()
    d = json.loads((config.DOCS_DIR / "data.json").read_text())
    base = {"date": date.today().isoformat(), "data_date": d["themes"]["date"], "regime": regime_of(br.iloc[-1]),
            "top_themes": top_themes(d["themes"]["themes"]),
            "setups": [s["key"] for s in d["themes"]["trade_setups"]["setups"]], "note": note}
    _base_path().write_text(json.dumps(base, indent=1))
    return base


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mark-reviewed", action="store_true")
    p.add_argument("--note", default="")
    a = p.parse_args()
    if a.mark_reviewed:
        print(json.dumps(mark_reviewed(a.note), indent=1))
