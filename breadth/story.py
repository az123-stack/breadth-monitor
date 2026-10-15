"""The market story: a running narrative across sessions, written by Claude twice a day.

Pieces:
- `scenario(...)`: the same rules the Read-out tab's story tracker uses in the browser (`storyState` in template.html): is money still
  leaving (A), coming back (B), or paused (waiting)? Built on the share of dollar volume in falling stocks (breadth.csv `dn_share`,
  percent) plus, for today, a live share computed from Google prices.
- `facts --slot am|pm`: a plain-text fact sheet for the chapter writer. am = official close (docs/data.json) + Yahoo pre-market
  (docs/premarket.json); pm = Google closing prices saved by the "Close snapshot" workflow (data/close_snapshot.csv).
- `publish`: appends a chapter to docs/story.json (the page fetches it from GitHub Pages). With --push it dispatches
  .github/workflows/story.yml with the chapter as inputs and that workflow commits it (Claude sessions may not write repo files
  through the contents API, but they can dispatch workflows).
- `snapshot`: fetches the live Google Sheet CSV into data/close_snapshot.csv (run by .github/workflows/close.yml after the close).

Comeback study (Oct 15, 2026; tools/ignition_study/comeback.py; Feb 2025–Oct 2026, small samples):
- Heavy-selling day inside an outflow streak (n 18): SPY median +1.7% over the next 10 sessions; the sub-themes sold hardest over the
  prior 5 sessions beat SPY by +4.3% (median +3.2%, 78% win) vs +0.5% for those that held up best; "60-day leaders sold hardest" +3.7%.
  Excluding the Mar–Apr 2025 crash: +3.9% / median +2.5%. Any 70%+ day (n 24): sold hardest +1.9%, held up +1.0%.
- First clean comeback day (<= 40% in falling stocks within 10 sessions of a streak, n 9): SPY median −1.2% next 10; held-up groups
  +1.7% vs SPY, middle +1.5%, sold hardest −0.1%; 60-day leaders +3.1% over 20 sessions.
  Read: the snapback in what was sold tends to start around the heavy-selling days themselves; once a calm "money is back" day prints,
  that bounce has usually run and the durable leaders are the groups that held up and the 60-day leaders.
Stdlib only, so it runs anywhere (scheduled Claude sessions, GitHub Actions) without installing packages.
"""
import argparse
import base64
import csv
import io
import json
import subprocess
import sys
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from . import config

ET = ZoneInfo("America/New_York")
REPO = "az123-stack/breadth-monitor"
STORY = config.DOCS_DIR / "story.json"
SNAP = config.DATA_DIR / "close_snapshot.csv"
GUIDE = config.ROOT / "breadth" / "story_guide.md"
RULES = {"leave": 60, "come": 40, "streak5": 55, "lookback": 10, "basket": 0.2}
FINDINGS = {
    "heavy_day": "After heavy-selling days inside an outflow streak (n 18, Feb 2025–Oct 2026), SPY rose a median +1.7% over the next "
                 "10 sessions, and the sub-themes sold hardest that week beat SPY by +4.3% (median +3.2%, 78% of the time) vs +0.5% for "
                 "the groups that held up. The snapback usually starts in what was sold.",
    "comeback": "Once a calm 'money is back' day prints (40% or less in falling stocks, n 9), the snapback has usually run: SPY median "
                "−1.2% over the next 10 sessions, the groups that held up +1.7% vs SPY, the sold-hardest groups about flat; 60-day "
                "leaders +3.1% over 20 sessions. Follow what held up, not the bounce.",
}


def pct(v, d=1):
    return "–" if v is None else f"{v * 100:+.{d}f}%"


def scenario(shares, live=None):
    """shares: daily % of dollar volume in falling stocks (percent, oldest first). live: today's share (percent) or None."""
    s = [x for x in shares if x is not None]
    if live is not None:
        s = s + [live]
    if not s:
        return {"branch": "none", "label": "No data", "latest": None}
    last, R = s[-1], RULES
    prior = s[:-1]
    def episode_at(i):   # outflow streak around day i: 5-day avg >= 55 or 2+ of the last 5 days >= 60
        w = s[max(0, i - 4): i + 1]
        return (sum(w) / len(w) >= R["streak5"]) or sum(1 for x in w if x >= R["leave"]) >= 2
    recent_ep = any(episode_at(i) for i in range(max(0, len(s) - 1 - R["lookback"]), len(s) - 1))
    streak = 0
    for x in reversed(s):
        if x >= R["leave"] - 5:
            streak += 1
        else:
            break
    left5 = sum(1 for x in s[-5:] if x >= R["leave"])
    if last >= R["leave"]:
        b, lab = "A", "Money is still leaving"
    elif last <= R["come"] and (recent_ep or episode_at(len(s) - 1)):
        b, lab = "B", "Money is coming back"
    elif recent_ep or episode_at(len(s) - 1):
        b, lab = "W", "Selling paused: waiting for the market to pick a side"
    else:
        b, lab = "none", "No outflow story right now"
    return {"branch": b, "label": lab, "latest": round(last, 1), "avg5": round(sum(s[-5:]) / len(s[-5:]), 1), "left5": left5,
            "streak": streak, "recent_episode": bool(recent_ep), "series": [round(x, 1) for x in s[-10:]]}


# ---------------------------------------------------------------- inputs
def load_data():
    return json.loads((config.DOCS_DIR / "data.json").read_text())


def baskets(T):
    """Sold hardest / held up best over the last 5 sessions (bottom / top 20% of sub-themes by 5-day move vs SPY) and the
    60-day-leader proxy (top 20% Strength 10 sessions ago)."""
    subs = [r for r in T.get("subthemes", []) if r.get("vs_d5") is not None and r.get("n", 0) >= 3]
    if not subs:
        return {}
    v = sorted(r["vs_d5"] for r in subs)
    k = max(1, int(len(v) * RULES["basket"]))
    lo, hi, med = v[k - 1], v[-k], v[len(v) // 2]
    past = sorted((r["s_hist"][-11] for r in subs if r.get("s_hist") and len(r["s_hist"]) >= 11), reverse=True)
    cut = past[max(0, int(len(past) * RULES["basket"]) - 1)] if past else 999
    lead = [r for r in subs if r.get("s_hist") and len(r["s_hist"]) >= 11 and r["s_hist"][-11] >= cut]
    return {"sold": sorted([r for r in subs if r["vs_d5"] <= lo], key=lambda r: r["vs_d5"]),
            "held": sorted([r for r in subs if r["vs_d5"] >= hi], key=lambda r: -r["vs_d5"]),
            "lead_sold": sorted([r for r in lead if r["vs_d5"] <= med], key=lambda r: r["vs_d5"]), "lead": lead}


def read_csv_rows(text):
    rows, cols, spytime = {}, None, None
    for f in csv.reader(io.StringIO(text)):
        if not f or not f[0]:
            continue
        k = f[0].strip()
        if k == "ticker":
            cols = [c.strip().lower() for c in f]
            continue
        if k == "_spytime":
            spytime = f[1] if len(f) > 1 else None
            continue
        if k.startswith("_") or not cols:
            continue
        r = {}
        for i, c in enumerate(cols[1:], 1):
            if i < len(f) and c in ("price", "closeyest", "open", "volume", "marketcap", "volumeavg"):
                try:
                    r[c] = float(str(f[i]).replace(",", "").replace("$", ""))
                except ValueError:
                    r[c] = None
        rows[k.upper()] = r
    date = None
    if spytime:
        import re
        m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", spytime)
        if m:
            date = f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return rows, date


def chg(r):
    if not r or not r.get("price") or not r.get("closeyest"):
        return None
    c = r["price"] / r["closeyest"] - 1
    return c if abs(c) <= 0.6 else None


# ---------------------------------------------------------------- fact sheet
def facts(slot):
    D = load_data()
    T, rows = D["themes"], D["rows"]
    last = rows[-1]
    out = []
    P = lambda s="": out.append(s)
    now = datetime.now(ET)
    P(f"# Fact sheet · {slot.upper()} · generated {now:%Y-%m-%d %H:%M} ET")
    P(f"Official data through {T['date']} (Massive). Regime: {D['regime'].get('label')} — {D['regime'].get('advice')}")
    PB = T.get("playbook", {})
    P(f"Playbook state: {PB.get('label')}. Focus: {', '.join(r['name'] for r in PB.get('rows', []) if r['verdict'] == 'Focus') or 'none'}. "
      f"Avoid: {', '.join(r['name'] for r in PB.get('rows', []) if r['verdict'] == 'Avoid') or 'none'}.")
    P("\n## Money in / out, last 10 official sessions (% of $ volume in falling stocks; net $B)")
    for r in rows[-10:]:
        P(f"- {r['date']}: {r.get('dn_share')}% falling, net {r.get('dv_net')}B, up4 {r.get('up4')} / dn4 {r.get('dn4')}, highs {r.get('nh')} / lows {r.get('nl')}")
    P(f"10-day avg share {last.get('dn_share10')}%, 5-day net {last.get('dv_net5')}B, T2108 {last.get('t2108')}, ratio5 {last.get('ratio5')}, ratio10 {last.get('ratio10')}")
    W = T.get("thrust_watch", {})
    if W.get("setup"):
        P(f"Thrust setup (washout in last 10 sessions): {'YES' if W['setup'].get('met') else 'no'}. Thrust pace on the live list: {W.get('pace')} up 4%+.")
    shares = [r.get("dn_share") for r in rows[-40:]]
    live_share, snap_rows, snap_date = None, None, None
    if slot == "pm" and SNAP.exists():
        snap_rows, snap_date = read_csv_rows(SNAP.read_text())
        up = dn = n = 0
        mU = mD = 0.0
        for t in W.get("tickers", []):
            r = snap_rows.get(t)
            c = chg(r)
            if c is None:
                continue
            if r["price"] >= 3:
                n += 1
                up += c >= 0.04
                dn += c <= -0.04
            v = (r.get("volume") or 0) * r["price"]
            if c > 0:
                mU += v
            elif c < 0:
                mD += v
        if mU + mD > 0 and snap_date and snap_date > T["date"]:
            live_share = mD / (mU + mD) * 100
            P(f"\n## Today ({snap_date}) from Google closing prices (snapshot file)")
            P(f"- {live_share:.0f}% of dollar volume in falling stocks on the {n}-stock live list (net {(mU - mD) / 1e9:+.0f}B); "
              f"{up} up 4%+ vs {dn} down 4%+ ({up / W['avg40']:.1f}x the 40-day avg; thrust pace = {W.get('k')}x)" if W.get("avg40") else "")
            for k, lab in [("SPY", "S&P 500"), ("QQQ", "Nasdaq-100"), ("IWM", "Russell 2000"), ("RSP", "Equal weight"), ("^VIX", "VIX"),
                           ("TLT", "Treasuries"), ("GLD", "Gold"), ("UUP", "Dollar"), ("USO", "Oil")]:
                c = chg(snap_rows.get(k))
                if c is not None:
                    P(f"- {lab} ({k}) {pct(c, 2)}")
        else:
            P(f"\n(Close snapshot is for {snap_date}; not newer than the official data, so no live today section.)")
    sc = scenario(shares, live_share)
    P(f"\n## Scenario engine: branch {sc['branch']} — {sc['label']}")
    P(f"Latest share {sc['latest']}%, 5-day avg {sc.get('avg5')}%, days >= 60% in last 5: {sc.get('left5')}, streak of heavy days: {sc.get('streak')}, "
      f"outflow episode in last 10 sessions: {sc.get('recent_episode')}. Series: {sc.get('series')}")
    P(f"Rules: A = latest >= {RULES['leave']}%; B = latest <= {RULES['come']}% after an outflow episode; W = paused after an episode.")
    P(f"Evidence A: {FINDINGS['heavy_day']}")
    P(f"Evidence B: {FINDINGS['comeback']}")
    # baskets
    B = baskets(T)
    sub_today = {}
    if snap_rows and live_share is not None:
        stocks = {s["t"]: s for s in T.get("stocks", [])}
        for g in T.get("subthemes", []):
            cs = [(chg(snap_rows.get(t)), snap_rows.get(t)) for t in g.get("members", []) if stocks.get(t, {}).get("is_stock")]
            cs = [(c, r) for c, r in cs if c is not None]
            if len(cs) >= 3:
                sub_today[g["theme"]] = (sum(c for c, _ in cs) / len(cs), sum((1 if c > 0 else -1 if c < 0 else 0) * (r.get("volume") or 0) * r["price"] for c, r in cs))
    def bl(rs):
        out_ = []
        for r in rs:
            t = sub_today.get(r["theme"])
            out_.append(f"{r['theme']} (5d vs SPY {pct(r['vs_d5'])}{', today ' + pct(t[0]) if t else ''})")
        return "; ".join(out_)
    if B:
        P("\n## Baskets (as of the last official close)")
        P(f"- Sold hardest (5 sessions; {len(B['sold'])} groups, 10 worst shown): {bl(B['sold'][:10])}")
        P(f"- Held up best (5 sessions; {len(B['held'])} groups, 10 best shown): {bl(B['held'][:10])}")
        P(f"- 60-day leaders sold hardest this week (snapback candidates): {bl(B['lead_sold'])}")
        if sub_today:
            avg = lambda rs: (lambda v: sum(v) / len(v) if v else None)([sub_today[r["theme"]][0] for r in rs if r["theme"] in sub_today])
            a1, a2 = avg(B["sold"]), avg(B["held"])
            P(f"- TODAY: sold-hardest basket {pct(a1)} vs held-up basket {pct(a2)} → "
              + ("snapback in what was sold" if a1 is not None and a2 is not None and a1 - a2 > 0.01 else
                 "money staying in what held up" if a1 is not None and a2 is not None and a2 - a1 > 0.01 else "no clear preference"))
            srt = sorted(sub_today.items(), key=lambda kv: kv[1][1])
            P(f"- Biggest net $ inflow today: {', '.join(f'{g} {pct(v[0])}' for g, v in srt[::-1][:6])}")
            P(f"- Biggest net $ outflow today: {', '.join(f'{g} {pct(v[0])}' for g, v in srt[:6])}")
            P(f"- Sub-themes up today: {sum(1 for v in sub_today.values() if v[0] > 0)} of {len(sub_today)}")
    # leaderboard
    subs = sorted([r for r in T.get("subthemes", []) if r.get("s_rank")], key=lambda r: r["s_rank"])
    P("\n## Leaderboard (official Strength)")
    for r in subs[:10]:
        h = r.get("s_hist") or []
        was = None
        if len(h) >= 6:
            prev = sorted((x.get("s_hist") or [0] * 6)[-6] for x in subs if len(x.get("s_hist") or []) >= 6)[::-1]
            was = prev.index(h[-6]) + 1 if h[-6] in prev else None
        P(f"- #{r['s_rank']} {r['theme']} Strength {r.get('strength')} (5 sessions ago #{was}), last session {pct(r.get('today'))}, 5d vs SPY {pct(r.get('vs_d5'))}, 1m vs SPY {pct(r.get('vs_d30'))}")
    L = T.get("leaders", [])[:8]
    P("Top stocks (Leaders score): " + ", ".join(f"{s['t']} (RS {s['rsr']}, {s.get('sub') or s.get('theme')})" for s in L))
    mk = (T.get("lists") or {}).get("strongest", [])[:6]
    P("Strongest anywhere: " + ", ".join(f"{s['t']} (RS {s['rsr']}, {s.get('sub') or 'no theme'}, last close {pct(s.get('chg'))})" for s in mk))
    # group signals
    X = (T.get("rotation") or {}).get("ignition") or {}
    if X:
        P(f"\n## Group signals (official close; Act gate {'ON' if X.get('act') else 'off'}: 10-day ratio peak in 15 sessions {X.get('peak15')})")
        for r in X.get("rows", []):
            if r["status"] == "ignition":
                P(f"- IGNITION {r['g']} {r['ago']} sessions ago, since {pct(r.get('since'))} vs SPY, leaders {'yes' if (r.get('lead') or {}).get('ok') else 'no'}, top stocks {', '.join(s['t'] for s in r.get('stocks', [])[:3])}")
        for r in (X.get("day1") or {}).get("rows", []):
            P(f"- DAY 1 {r['g']} on {r['date']} ({r['ago']} sessions ago): day-3 result {pct(r.get('d3'))}, since {pct(r.get('since'))}")
        w = [r for r in X.get("rows", []) if r["status"] == "warming"][:6]
        if w:
            P("- Warming up: " + ", ".join(f"{r['g']} {r['n_met']}/4{' (leaders)' if (r.get('lead') or {}).get('ok') else ''}" for r in w))
    # trades
    P("\n## Your plan / trades")
    for i, c in enumerate(PB.get("picks", [])):
        now_px = chg(snap_rows.get(c["t"])) if snap_rows else None
        P(f"- Pick #{i + 1} {c['t']} ({c['setup_name']}, {c.get('sub')}): trigger {c.get('trigger')}, entry {c.get('entry_type')}, close {c.get('price')}" + (f", today {pct(now_px)}" if now_px is not None else ""))
    for o in (T.get("scoreboard") or {}).get("open", []):
        if o.get("status") == "open" and o.get("entry"):
            P(f"- Open trade {o['t']} picked {o['date']}, entry {o['entry']}, stop ~{round(o['entry'] * (1 - (o.get('stop_pct') or 0)), 2)}, return so far {pct(o.get('now_ret'))}")
    # pre-market
    if slot == "am":
        try:
            PM = json.loads((config.DOCS_DIR / "premarket.json").read_text())
        except Exception:
            PM = None
        today = now.date().isoformat()
        if PM and PM.get("date") == today:
            F = PM.get("futures", {})
            P(f"\n## Pre-market ({PM.get('asof')} ET, Yahoo)")
            for k, lab in PM.get("futures_labels", {}).items():
                f = F.get(k)
                if f and f[0] and f[1]:
                    P(f"- {lab}: {pct(f[0] / f[1] - 1, 2)}" if k != "^TNX" else f"- {lab}: {f[0]:.2f}% ({(f[0] - f[1]) * 100:+.0f} bp)")
            R = PM.get("rows", {})
            g = []
            stocks = {s["t"]: s for s in T.get("stocks", [])}
            for grp in T.get("subthemes", []):
                cs = [R[t][0] / R[t][1] - 1 for t in grp.get("members", []) if t in R and R[t][0] and R[t][1] and stocks.get(t, {}).get("is_stock")]
                if len(cs) >= 3:
                    g.append((sum(cs) / len(cs), grp["theme"]))
            g.sort()
            if g:
                P("- Gapping up most: " + ", ".join(f"{n} {pct(v)}" for v, n in g[::-1][:5]))
                P("- Gapping down most: " + ", ".join(f"{n} {pct(v)}" for v, n in g[:5]))
            big = sorted(((R[t][0] / R[t][1] - 1, t) for t in R if R[t][0] and R[t][1] and (R[t][4] or 0) >= 6 and R[t][0] >= 5), reverse=True)
            P("- Biggest steady gappers up: " + ", ".join(f"{t} {pct(v, 0)}" for v, t in big[:8] if v >= 0.04))
            P("- Biggest steady gappers down: " + ", ".join(f"{t} {pct(v, 0)}" for v, t in big[::-1][:8] if v <= -0.04))
        else:
            P(f"\n(No pre-market snapshot for {today} yet.)")
    # previous chapters
    try:
        S = json.loads(STORY.read_text())
    except Exception:
        S = {"chapters": []}
    P("\n## Previous chapters (newest first)")
    for c in S.get("chapters", [])[-6:][::-1]:
        P(f"### {c['date']} {c['slot']} · branch {c.get('branch')} · {c.get('title')}\n{c.get('md', '')[:1500]}")
    if not S.get("chapters"):
        P("(none yet: this is the first chapter)")
    return "\n".join(x for x in out if x is not None)


# ---------------------------------------------------------------- publish / snapshot
def publish(slot, title, branch, md, date=None, push=False):
    date = date or datetime.now(ET).date().isoformat()
    try:
        S = json.loads(STORY.read_text())
    except Exception:
        S = {"chapters": []}
    S["chapters"] = [c for c in S["chapters"] if not (c["date"] == date and c["slot"] == slot)]
    S["chapters"].append({"date": date, "slot": slot, "title": title.strip(), "branch": branch, "md": md.strip(),
                          "written": datetime.now(ET).strftime("%Y-%m-%dT%H:%M")})
    S["chapters"] = sorted(S["chapters"], key=lambda c: (c["date"], c["slot"] == "pm"))[-80:]
    text = json.dumps(S, indent=1, ensure_ascii=False)
    STORY.write_text(text)
    if push:   # Claude sessions can't write repo files through the API, but they can dispatch workflows: story.yml saves it
        r = subprocess.run(["gh", "api", "-X", "POST", f"repos/{REPO}/actions/workflows/story.yml/dispatches", "-f", "ref=main",
                            "-f", f"inputs[slot]={slot}", "-f", f"inputs[date]={date}", "-f", f"inputs[branch]={branch}",
                            "-f", f"inputs[title]={title.strip()}", "-f", f"inputs[md_b64]={base64.b64encode(md.strip().encode()).decode()}"],
                           capture_output=True, text=True)
        if r.returncode:
            sys.exit("dispatch failed: " + (r.stderr or r.stdout)[:400])
        print("dispatched story.yml: the chapter is committed by GitHub Actions in about a minute")
    return S


def snapshot():
    with urllib.request.urlopen(config.LIVE_CSV_URL + ("&" if "?" in config.LIVE_CSV_URL else "?") + "cb=" + str(int(datetime.now().timestamp())), timeout=60) as r:
        text = r.read().decode("utf-8", "replace")
    rows, date = read_csv_rows(text)
    if len(rows) < 100:
        sys.exit(f"snapshot too small ({len(rows)} rows)")
    SNAP.write_text(text)
    print(f"close snapshot: {len(rows)} rows, session {date}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("facts"); f.add_argument("--slot", choices=["am", "pm"], required=True)
    p = sub.add_parser("publish"); p.add_argument("--slot", choices=["am", "pm"], required=True); p.add_argument("--title", required=True)
    p.add_argument("--branch", choices=["A", "B", "W", "none"], required=True); p.add_argument("--file"); p.add_argument("--md-b64")
    p.add_argument("--date"); p.add_argument("--push", action="store_true")
    sub.add_parser("snapshot")
    sub.add_parser("guide")
    a = ap.parse_args()
    if a.cmd == "facts":
        print(facts(a.slot))
    elif a.cmd == "publish":
        md = base64.b64decode(a.md_b64).decode() if a.md_b64 else open(a.file).read()
        publish(a.slot, a.title, a.branch, md, a.date, a.push)
        print("chapter saved")
    elif a.cmd == "snapshot":
        snapshot()
    else:
        print(GUIDE.read_text())
