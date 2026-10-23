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
- `facts --slot data` / `publish --slot data` (Oct 16): the 8:44 AM ET "data card" on days with an 8:30 release: market reaction from
  the pre-market snapshots (latest vs the last one before 8:30, read from the commit history of docs/premarket.json) plus today's
  scheduled events. The morning chapter stores the day's market-moving events (`--events-b64`, a JSON list of {time, name, why}) on
  its chapter; the Read-out tab shows them in a banner and the data card on top of the story.
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
SLOT_ORDER = {"am": 0, "data": 1, "pm": 2}


def _pm_before(cut="08:30", day=None):
    """The last pre-market snapshot committed before `cut` ET today, from the commit history of docs/premarket.json (gh REST)."""
    day = day or datetime.now(ET).date().isoformat()
    try:
        r = subprocess.run(["gh", "api", f"repos/{REPO}/commits?path=docs/premarket.json&per_page=40", "--jq",
                            '.[]|"\\(.sha) \\(.commit.message)"'], capture_output=True, text=True, timeout=60)
        for line in r.stdout.splitlines():   # newest first; messages read "Pre-market HH:MM ET"
            sha, _, msg = line.partition(" ")
            hm = msg.replace("Pre-market", "").replace("ET", "").strip()[:5]
            if len(hm) == 5 and hm < cut:
                raw = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github.raw", f"repos/{REPO}/contents/docs/premarket.json?ref={sha}"],
                                     capture_output=True, text=True, timeout=60).stdout
                J = json.loads(raw)
                return J if J.get("date") == day else None
    except Exception:
        return None
    return None


def today_events(S=None):
    """Today's market-moving events saved on today's morning chapter (or the data card)."""
    try:
        S = S or json.loads(STORY.read_text())
    except Exception:
        return []
    day = datetime.now(ET).date().isoformat()
    for c in sorted(S.get("chapters", []), key=lambda c: SLOT_ORDER.get(c["slot"], 3)):
        if c["date"] == day and c.get("events"):
            return c["events"]
    return []


def facts_data():
    out = []
    P = lambda s="": out.append(s)
    now = datetime.now(ET)
    P(f"# Fact sheet · DATA · generated {now:%Y-%m-%d %H:%M} ET")
    ev = today_events()
    P("\n## Today's market-moving events (from the morning chapter)")
    P("\n".join(f"- {e.get('time', '')} {e.get('name', '')}: {e.get('why', '')}" for e in ev) if ev else "(none saved: check the calendar yourself)")
    try:
        NOW = json.loads((config.DOCS_DIR / "premarket.json").read_text())
    except Exception:
        NOW = None
    if not NOW or NOW.get("date") != now.date().isoformat():
        P("\n(No pre-market snapshot for today yet.)")
        return "\n".join(out)
    B = _pm_before("08:30", now.date().isoformat())
    P(f"\n## Market reaction (Yahoo pre-market; latest {NOW.get('asof', '')[11:16]} ET" + (f" vs before the release {B.get('asof', '')[11:16]} ET)" if B else "; no pre-8:30 snapshot found)"))
    F, FB = NOW.get("futures", {}), (B or {}).get("futures", {})
    for k, lab in NOW.get("futures_labels", {}).items():
        f, b = F.get(k), FB.get(k)
        if not (f and f[0] and f[1]):
            continue
        if k == "^TNX":
            P(f"- {lab}: {f[0]:.2f}% ({(f[0] - f[1]) * 100:+.0f} bp vs last close" + (f", {(f[0] - b[0]) * 100:+.0f} bp since before 8:30)" if b and b[0] else ")"))
        else:
            P(f"- {lab}: {pct(f[0] / f[1] - 1, 2)} vs last close" + (f", {pct(f[0] / b[0] - 1, 2)} since before 8:30" if b and b[0] else ""))
    R, RB = NOW.get("rows", {}), (B or {}).get("rows", {})
    etfs = ["SPY", "QQQ", "IWM", "RSP", "TLT", "XLF", "KRE", "XHB", "XLK", "SMH", "XLY", "XLU", "XLV", "XLE", "GLD", "UUP"]
    ln = []
    for t in etfs:
        r, b = R.get(t), RB.get(t)
        if r and r[0] and r[1]:
            ln.append(f"{t} {pct(r[0] / r[1] - 1, 2)}" + (f" ({pct(r[0] / b[0] - 1, 2)} since)" if b and b[0] else ""))
    if ln:
        P("- ETFs pre-market vs last close (since before 8:30): " + ", ".join(ln))
    P("\nRate-sensitive tells: 10y note futures (ZN) UP = yields DOWN; the dollar index; IWM, KRE, XHB (small caps, regional banks, homebuilders)"
      " react most to rates; QQQ / SMH for long-duration growth.")
    return "\n".join(out)


def facts(slot):
    if slot == "data":
        return facts_data()
    D = load_data()
    T, rows = D["themes"], D["rows"]
    last = rows[-1]
    out = []
    P = lambda s="": out.append(s)
    now = datetime.now(ET)
    P(f"# Fact sheet · {slot.upper()} · generated {now:%Y-%m-%d %H:%M} ET")
    P(f"Official data through {T['date']} (Massive). Regime: {D['regime'].get('label')} — {D['regime'].get('advice')}")
    X = T.get("thetrade") or {}
    if X.get("winners"):
        pc = lambda v: "–" if v is None else f"{v * 100:+.1f}%"
        P(f"\n## THE TRADE (open with one line on it): {X['name']} · state {X.get('state')} · {X.get('above', 0)} sessions above"
          f" its 20-day avg · 20-day spread {pc(X.get('spread20'))}")
        P(f"- Winners: " + ", ".join(f"{g['g']} {pc(g['r20'])}" for g in X["winners"][:5]))
        P(f"- Losers: " + ", ".join(f"{g['g']} {pc(g['r20'])}" for g in X["losers"][:5]))
        ind = X.get("ind")
        P(f"- Real or seesaw: correlation {X.get('corr')}; on the losers' best days winners did {pc(X.get('w_hot'))}"
          f" ({pc(ind)} vs SPY) → {'HOLDS UP on its own' if ind is not None and ind >= 0 else 'GIVES BACK (seesaw)'}")
        ev = (X.get("evidence") or {})
        if ev.get("gives_snap"):
            g = ev["gives_snap"]
            P(f"- Evidence: in past 'gives back' stretches the losing side won the next 10 sessions in {g[0]} of {g[1]} episodes;"
              f" when winners hold up they beat the average group by {pc(((ev.get('rows') or {}).get('holds') or {}).get('w', {}).get('mean'))}.")
        P(f"- Plays (not stretched): " + ", ".join(f"{r['t']} ({r['sub']}, RS {r['rsr']})" for r in (X.get('plays') or [])[:6]))
        if X.get("stretched"):
            P("- Don't chase (> 2 ADRs over the 21 EMA): " + ", ".join(r["t"] for r in X["stretched"]))
        P(f"- Counter-trade watch (RS 85+ in losing groups): " + ", ".join(f"{r['t']}{' (back over 21 EMA)' if r['reclaim'] else ''}" for r in (X.get('counter') or [])[:6])
          + f" · comeback trigger {'MET' if X.get('comeback') else 'not met'} (last share in falling stocks {X.get('dn_share')}%)")
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
    explain = []   # (group, reason) for the "why" research
    if sub_today:
        srt2 = sorted(sub_today.items(), key=lambda kv: kv[1][1])
        explain += [(g, f"net $ inflow today {pct(v[0])}") for g, v in srt2[::-1][:3]] + [(g, f"net $ outflow today {pct(v[0])}") for g, v in srt2[:3]]
    elif B:
        explain += [(r["theme"], f"held up best over 5 sessions ({pct(r['vs_d5'])} vs SPY)") for r in B["held"][:3]]
        explain += [(r["theme"], f"sold hardest over 5 sessions ({pct(r['vs_d5'])} vs SPY)") for r in B["sold"][:3]]
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
                explain += [(n, f"gapping {pct(v)} pre-market") for v, n in g[::-1][:3]] + [(n, f"gapping {pct(v)} pre-market") for v, n in g[:3]]
                P("- Gapping up most: " + ", ".join(f"{n} {pct(v)}" for v, n in g[::-1][:5]))
                P("- Gapping down most: " + ", ".join(f"{n} {pct(v)}" for v, n in g[:5]))
            big = sorted(((R[t][0] / R[t][1] - 1, t) for t in R if R[t][0] and R[t][1] and (R[t][4] or 0) >= 6 and R[t][0] >= 5), reverse=True)
            P("- Biggest steady gappers up: " + ", ".join(f"{t} {pct(v, 0)}" for v, t in big[:8] if v >= 0.04))
            P("- Biggest steady gappers down: " + ", ".join(f"{t} {pct(v, 0)}" for v, t in big[::-1][:8] if v <= -0.04))
            try:
                cat = json.loads((config.DOCS_DIR / "agent" / "catalysts.json").read_text())
            except Exception:
                cat = None
            IP = in_play(T, PM, cat)
            P("\n## IN PLAY candidates (for the **In play today:** section; code measured these, YOU find the why)")
            P("Stocks (score = number of independent reasons; warnings subtract):")
            for r in IP["stocks"]:
                P(f"- {r['t']} {pct(r['gap'])} pre-market, ${r['price']}, RS {f"{r['rsr']:.0f}" if r['rsr'] is not None else '–'}, {r['sub'] or 'no sub-theme'} · "
                  f"score {r['score']:g}: {'; '.join(r['why'])}" + (f" · WARN: {'; '.join(r['warn'])}" if r["warn"] else ""))
            if not IP["stocks"]:
                P("- (no stock is gapping 4%+ on steady pre-market trading)")
            P("Groups moving together pre-market:")
            for r in IP["groups"]:
                P(f"- {r['g']}: {'; '.join(r['why'])} · names {', '.join(r['names'])}")
            if not IP["groups"]:
                P("- (no sub-theme is gapping 1%+ with breadth)")
            P("Your names in pre-market (picks, setups, Strength on Weakness): " + (", ".join(f"{r['t']} {pct(r['gap'])}" for r in IP["mine"]) or "none moving"))
        else:
            P(f"\n(No pre-market snapshot for {today} yet.)")
    # groups whose moves the chapter should explain: the writer searches the news for each
    for r in (X.get("rows", []) if X else []):
        if r["status"] == "ignition" and r.get("ago", 9) <= 1:
            explain.append((r["g"], "fresh ignition"))
    for r in ((X.get("day1") or {}).get("rows", []) if X else []):
        if r.get("ago", 9) <= 1:
            explain.append((r["g"], "fresh Day 1"))
    stocks_by = {}
    for s_ in T.get("stocks", []):
        if s_.get("is_stock") and s_.get("sub"):
            stocks_by.setdefault(s_["sub"], []).append(s_)
    seen, lines = set(), []
    for g, why in explain:
        if g in seen:
            continue
        seen.add(g)
        top = sorted(stocks_by.get(g, []), key=lambda x: -(x.get("rsr") or 0))[:4]
        lines.append(f"- {g} ({why}): biggest names {', '.join(x['t'] for x in top) or '–'}")
    if lines:
        P("\n## WHY research list: search the news for what is driving each of these (earnings, guidance, policy, macro, deals) and confirm with the price action above")
        out.extend(lines[:12])
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


# ---------------------------------------------------------------- in play (morning chapter)
INPLAY = {"gap": 0.04, "gap_adr": 1.5, "ep": 0.08, "min_px": 5.0, "min_dv": 20e6, "bars": 6, "grp_gap": 0.01, "grp_up": 0.6, "n": 12}


def in_play(T, PM, cat=None):
    """Candidates for "In play today" from the pre-market snapshot + the dashboard's own lists. Code measures, the writer
    explains: each candidate carries the measurable reasons; the morning chapter searches the news for the WHY.
    Returns {"stocks": [...], "groups": [...], "mine": [...]} sorted by score (count of independent reasons)."""
    I = INPLAY
    R = (PM or {}).get("rows", {}) or {}
    stocks = {x["t"]: x for x in T.get("stocks", []) if x.get("is_stock")}
    gap = lambda t: (R[t][0] / R[t][1] - 1) if t in R and R[t][0] and R[t][1] else None
    steady = lambda t: t in R and (R[t][4] or 0) >= I["bars"]
    cat = cat if (cat or {}).get("for_date") == T.get("date") else {}
    C = (cat or {}).get("stocks", {}) or {}
    PB = T.get("playbook") or {}
    mine = {}
    for i, c in enumerate(PB.get("picks", [])):
        mine.setdefault(c["t"], []).append(f"Top pick #{i + 1} ({c.get('setup_name')})")
    for c in PB.get("pick_watch", []):
        mine.setdefault(c["t"], []).append(f"pick watch ({c.get('setup_name')}, trigger {c.get('trigger')})")
    for S in (T.get("trade_setups") or {}).get("setups", []):
        for t in S.get("top", []):
            mine.setdefault(t, []).append(S["name"])
    SW = T.get("sow") or {}
    for r in SW.get("rows", []):
        if r.get("prime") or r.get("state") in ("breakout", "pop", "nuzzle"):
            mine.setdefault(r["t"], []).append("SoW " + ("⭐ Prime" if r.get("prime") else r["state"]))
    hve = {r["t"] for r in (T.get("hve") or {}).get("rows", []) if (r.get("chg") or 0) > 0}
    # group gaps
    grp = {}
    for g in T.get("subthemes", []):
        cs = [gap(t) for t in g.get("members", []) if t in stocks and gap(t) is not None]
        if len(cs) >= 3:
            grp[g["theme"]] = (sum(cs) / len(cs), sum(c > 0 for c in cs) / len(cs), len(cs), g.get("strength"), g.get("s_rank"))
    X = (T.get("rotation") or {}).get("ignition") or {}
    fresh = {r["g"]: "ignition" for r in X.get("rows", []) if r.get("status") == "ignition" and r.get("ago", 9) <= 5}
    fresh.update({r["g"]: "Day 1" for r in (X.get("day1") or {}).get("rows", []) if r.get("ago", 9) <= 3})
    groups = []
    for g, (a, up, n, st, rk) in grp.items():
        why = []
        if a >= I["grp_gap"] and up >= I["grp_up"]:
            why.append(f"gapping {pct(a)} with {up:.0%} of {n} members up")
        elif a <= -I["grp_gap"] and up <= 1 - I["grp_up"]:
            why.append(f"gapping {pct(a)} with {1 - up:.0%} of {n} members down")
        if not why:
            continue
        if g in fresh:
            why.append(f"fresh {fresh[g]}")
        if rk and rk <= 10:
            why.append(f"top-10 group (#{rk}, Strength {st})")
        lead = sorted((stocks[t] for t in next((x.get("members", []) for x in T.get("subthemes", []) if x["theme"] == g), []) if t in stocks),
                      key=lambda x: -(x.get("rsr") or 0))[:4]
        groups.append({"g": g, "gap": round(a, 4), "breadth": round(up, 2), "n": n, "score": len(why), "why": why,
                       "names": [f"{x['t']} {pct(gap(x['t']))}" for x in lead if gap(x["t"]) is not None]})
    groups.sort(key=lambda r: (-r["score"], -abs(r["gap"])))
    out = []
    for t in R:
        s = stocks.get(t)
        g = gap(t)
        if g is None or not steady(t) or R[t][0] < I["min_px"]:
            continue
        adr = (s or {}).get("adr")
        g_adr = g / (adr / 100) if adr else None
        big = abs(g) >= I["gap"] and (g_adr is None or abs(g_adr) >= I["gap_adr"])
        c = C.get(t) or {}
        earn = c.get("earnings_date")
        if not big and t not in mine:
            continue
        if not big and abs(g) < 0.02:           # one of your names, but not moving yet
            continue
        dv = (s or {}).get("v50", 0) * (s or {}).get("price", 0) if s else None
        if dv is not None and dv < I["min_dv"] and t not in mine:
            continue
        why, warn = [], []
        if big:
            why.append(f"gap {pct(g)}" + (f" ({g_adr:+.1f} ADR)" if g_adr is not None else ""))
        if g >= I["ep"] and (dv or 0) >= I["min_dv"]:
            why.append("possible EP (8%+ gap, liquid): needs a real catalyst")
        if s and (s.get("rsr") or 0) >= 85:
            why.append(f"leader RS {s['rsr']:.0f}")
        sub = (s or {}).get("sub")
        if sub in grp and grp[sub][0] * g > 0 and abs(grp[sub][0]) >= I["grp_gap"]:
            why.append(f"group moving with it ({sub} {pct(grp[sub][0])})")
        if t in mine:
            why.append("on your lists: " + "; ".join(dict.fromkeys(mine[t]))[:120])
        if earn and earn <= (PM or {}).get("date", "9999") and earn >= T.get("date", ""):
            why.append(f"earnings {earn}")
        if c.get("quality") in ("strong", "real") and c.get("direction") in ("positive", "negative"):
            why.append(f"catalyst agent: {c['quality']} {c['direction']} — {str(c.get('why', ''))[:120]}")
        for f in c.get("red_flags") or []:
            warn.append(f"red flag: {f}")
        if t in hve:
            warn.append("record-volume up day in the last 5 sessions (has tended to lag SPY)")
        if s and (s.get("off_hi") or 0) <= -0.3 and g > 0:
            warn.append("30%+ below its 52-wk high (gap into overhead supply)")
        out.append({"t": t, "gap": round(g, 4), "g_adr": None if g_adr is None else round(g_adr, 1), "rsr": (s or {}).get("rsr"),
                    "sub": sub, "price": R[t][0], "score": len(why) - 0.5 * len(warn), "why": why, "warn": warn, "mine": t in mine})
    out.sort(key=lambda r: (-r["score"], -abs(r["gap"])))
    up = [r for r in out if r["gap"] > 0][:I["n"]]
    dn = [r for r in out if r["gap"] < 0][:max(4, I["n"] // 3)]
    mine_rows = [{"t": t, "why": list(dict.fromkeys(v))[:2], "gap": gap(t)} for t, v in mine.items() if gap(t) is not None]
    mine_rows.sort(key=lambda r: -abs(r["gap"]))
    return {"stocks": up + dn, "groups": groups[:8], "mine": mine_rows[:10]}


# ---------------------------------------------------------------- publish / snapshot
def publish(slot, title, branch, md, date=None, push=False, events=None):
    date = date or datetime.now(ET).date().isoformat()
    try:
        S = json.loads(STORY.read_text())
    except Exception:
        S = {"chapters": []}
    S["chapters"] = [c for c in S["chapters"] if not (c["date"] == date and c["slot"] == slot)]
    ch = {"date": date, "slot": slot, "title": title.strip(), "branch": branch, "md": md.strip(),
          "written": datetime.now(ET).strftime("%Y-%m-%dT%H:%M")}
    if events:
        ch["events"] = [{k: str(e.get(k, "")).strip() for k in ("time", "name", "why")} for e in events if e.get("name")]
    S["chapters"].append(ch)
    S["chapters"] = sorted(S["chapters"], key=lambda c: (c["date"], SLOT_ORDER.get(c["slot"], 3)))[-80:]
    text = json.dumps(S, indent=1, ensure_ascii=False)
    STORY.write_text(text)
    if push:   # Claude sessions can't write repo files through the API, but they can dispatch workflows: story.yml saves it
        r = subprocess.run(["gh", "api", "-X", "POST", f"repos/{REPO}/actions/workflows/story.yml/dispatches", "-f", "ref=main",
                            "-f", f"inputs[slot]={slot}", "-f", f"inputs[date]={date}", "-f", f"inputs[branch]={branch}",
                            "-f", f"inputs[title]={title.strip()}", "-f", f"inputs[md_b64]={base64.b64encode(md.strip().encode()).decode()}",
                            "-f", f"inputs[events_b64]={base64.b64encode(json.dumps(ch.get('events', [])).encode()).decode()}"],
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
    f = sub.add_parser("facts"); f.add_argument("--slot", choices=["am", "pm", "data"], required=True)
    p = sub.add_parser("publish"); p.add_argument("--slot", choices=["am", "pm", "data"], required=True); p.add_argument("--title", required=True)
    p.add_argument("--branch", choices=["A", "B", "W", "none"], required=True); p.add_argument("--file"); p.add_argument("--md-b64")
    p.add_argument("--date"); p.add_argument("--push", action="store_true")
    p.add_argument("--events-file", help="JSON list of today's market-moving events [{time, name, why}]"); p.add_argument("--events-b64")
    sub.add_parser("snapshot")
    sub.add_parser("guide")
    a = ap.parse_args()
    if a.cmd == "facts":
        print(facts(a.slot))
    elif a.cmd == "publish":
        md = base64.b64decode(a.md_b64).decode() if a.md_b64 else open(a.file).read()
        ev = json.loads(base64.b64decode(a.events_b64).decode() or "[]") if a.events_b64 else json.load(open(a.events_file)) if a.events_file else None
        publish(a.slot, a.title, a.branch, md, a.date, a.push, ev)
        print("chapter saved")
    elif a.cmd == "snapshot":
        snapshot()
    else:
        print(GUIDE.read_text())
