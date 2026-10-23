"""Trade Stories (Oct 22, 2026; Adam: "a tab where you put together news and earnings narratives into a cohesive story and
recommend how to trade the developing story").

Running storylines (max 6 open), each a case file that is UPDATED, not rewritten: status, thesis (what / why / how it works /
real or seesaw / what confirms or breaks it), dated timeline with sources, the groups and stocks it trades through, upcoming
catalysts, how to trade it, related stories and a status history. Stored in docs/stories.json, written once a day by the
"after the close" Claude task (see stories_guide.md), saved by .github/workflows/stories.yml.

Code measures, the agent writes: `price_check` ties every story to its sub-themes (rotation.mhist equal-weight returns) and
says whether price agrees; `scorecard` settles each day's call (long groups minus short groups, or minus SPY, next 5 sessions).
The page (`renderStories`) recomputes both from DATA so they're always current. Information only; never touches the picks.
Stdlib only (runs in the scheduled task without installs).
"""
import argparse
import base64
import gzip
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta

from . import config
from .story import ET, REPO, load_data, pct

STORIES = config.DOCS_DIR / "stories.json"
GUIDE = config.ROOT / "breadth" / "stories_guide.md"
STATUSES = ("building", "peaking", "fading", "resolved")
THESIS = ("what", "why", "how", "real", "confirm")
MAX_OPEN = 6
KEEP_RESOLVED = 20
HOLD = 5
CHASE = " (don't chase: > 2 ADRs over the 21 EMA)"


def load():
    try:
        return json.loads(STORIES.read_text())
    except Exception:
        return {"updated": None, "stories": []}


# ---------------------------------------------------------------- price check (mirrors storyPrice / storyScore in the page)
def _mh(T):
    M = (T.get("rotation") or {}).get("mhist") or {}
    return M.get("dates") or [], M.get("sub") or {}, M.get("spy") or []


def _basket(sub, groups, i0, i1):
    """Equal-weight average of the groups' compounded return over sessions (i0, i1] (indexes into mhist dates)."""
    vals = []
    for g in groups:
        r = (sub.get(g) or [None, None, None])[2]
        if not r or i1 >= len(r) or i0 < -1:
            continue
        p = 1.0
        for x in r[i0 + 1:i1 + 1]:
            p *= 1 + (x or 0) / 1e4
        vals.append(p - 1)
    return sum(vals) / len(vals) if vals else None


def _spy(spy, i0, i1):
    p = 1.0
    for x in spy[i0 + 1:i1 + 1]:
        p *= 1 + (x or 0) / 1e4
    return p - 1


def price_check(T, s):
    dates, sub, spy = _mh(T)
    if len(dates) < 25:
        return None
    L, S = (s.get("groups") or {}).get("long") or [], (s.get("groups") or {}).get("short") or []
    L, S = [g for g in L if g in sub], [g for g in S if g in sub]
    if not L and not S:
        return None
    n = len(dates) - 1
    out = {}
    for k, w in (("d1", 1), ("d5", 5), ("d20", 20)):
        lo = _basket(sub, L, n - w, n) if L else _spy(spy, n - w, n)
        sh = _basket(sub, S, n - w, n) if S else _spy(spy, n - w, n)
        out[k] = None if lo is None or sh is None else round(lo - sh, 4)
        out[k + "_long"] = None if lo is None else round(lo, 4)
        out[k + "_short"] = None if sh is None else round(sh, 4)
    a, b = out["d5"], out["d20"]
    out["vs"] = ("losing groups" if L else "SPY (story = these groups lag)") if S else "SPY"
    out["verdict"] = ("unknown" if a is None or b is None else "agrees" if a > 0 and b > 0 else
                      "wobbling" if b > 0 >= a else "turning" if a > 0 >= b else "disagrees")
    return out


def scorecard(T, s):
    """Each history day: the story's call (long minus short groups, or minus SPY) over the next HOLD sessions."""
    dates, sub, spy = _mh(T)
    idx = {d: i for i, d in enumerate(dates)}
    rows = []
    for h in s.get("history") or []:
        i = idx.get(h.get("date"))
        if i is None or i + HOLD >= len(dates) or h.get("status") == "resolved":
            continue
        L = [g for g in h.get("long") or [] if g in sub]
        S = [g for g in h.get("short") or [] if g in sub]
        if not L and not S:
            continue
        lo = _basket(sub, L, i, i + HOLD) if L else _spy(spy, i, i + HOLD)
        sh = _basket(sub, S, i, i + HOLD) if S else _spy(spy, i, i + HOLD)
        if lo is None or sh is None:
            continue
        rows.append({"date": h["date"], "status": h.get("status"), "edge": round(lo - sh, 4)})
    return rows


def stocks_for(T, groups, n=8):
    on = {}
    for st in ((T.get("trade_setups") or {}).get("setups") or []):
        for t in st.get("top") or []:
            on.setdefault(t, []).append(st["name"])
    for i, p in enumerate((T.get("playbook") or {}).get("picks") or []):
        on.setdefault(p["t"], []).insert(0, f"Top pick #{i + 1}")
    out = []
    for s in T.get("stocks") or []:
        if s.get("sub") not in groups or (s.get("rsr") or 0) < 80 or (s.get("price") or 0) < 10:
            continue
        adr = s.get("adr") or 0
        ext = (s.get("e21") or 0) / (adr / 100) if adr else None
        out.append({"t": s["t"], "sub": s.get("sub"), "rsr": s.get("rsr"), "ext": None if ext is None else round(ext, 1),
                    "chase": ext is not None and ext > 2, "on": on.get(s["t"], [])})
    out.sort(key=lambda r: (r["chase"], -len(r["on"]), -(r["rsr"] or 0)))
    return out[:n]


# ---------------------------------------------------------------- validate / publish
def _slug(x):
    return re.sub(r"[^a-z0-9]+", "-", str(x).lower()).strip("-")[:40]


def validate(S, T=None, today=None):
    """Returns (cleaned, problems). Problems that drop data are listed; the caller decides whether they're fatal."""
    T = T if T is not None else load_data()["themes"]
    today = today or datetime.now(ET).date().isoformat()
    names = {r["theme"] for r in T.get("subthemes") or []}
    probs, out, seen = [], [], set()
    for s in (S.get("stories") or []):
        sid = _slug(s.get("id") or s.get("title") or "")
        if not sid or sid in seen:
            probs.append(f"story without a unique id: {s.get('title')!r}")
            continue
        seen.add(sid)
        st = str(s.get("status", "")).lower()
        if st not in STATUSES:
            probs.append(f"{sid}: status must be one of {STATUSES}")
            continue
        th = s.get("thesis") or {}
        miss = [k for k in THESIS if not str(th.get(k, "")).strip()]
        if miss and st != "resolved":
            probs.append(f"{sid}: thesis missing {miss}")
            continue
        tl = []
        for e in s.get("timeline") or []:
            u = str(e.get("url", ""))
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(e.get("date", ""))) or not str(e.get("event", "")).strip():
                probs.append(f"{sid}: timeline item needs date + event: {e}")
                continue
            if not u.startswith("http"):
                probs.append(f"{sid}: timeline item without a source link dropped: {e.get('event')!r}")
                continue
            tl.append({k: str(e.get(k, "")).strip() for k in ("date", "event", "url", "source", "reaction")})
        if not tl and st != "resolved":
            probs.append(f"{sid}: needs at least one sourced timeline item")
            continue
        g = s.get("groups") or {}
        groups = {}
        for side in ("long", "short"):
            keep = [x for x in g.get(side) or [] if x in names]
            bad = [x for x in g.get(side) or [] if x not in names]
            if bad:
                probs.append(f"{sid}: unknown sub-themes dropped ({side}): {bad}")
            groups[side] = keep
        cats = [{k: str(c.get(k, "")).strip() for k in ("date", "time", "name", "why")} for c in s.get("catalysts") or []
                if re.match(r"^\d{4}-\d{2}-\d{2}$", str(c.get("date", "")))]
        hist = [h for h in s.get("history") or [] if h.get("date")]
        if not hist or hist[-1]["date"] != today:
            hist.append({"date": today})
        hist[-1].update({"status": st, "long": groups["long"], "short": groups["short"],
                         "note": str(s.get("changed", "")).strip()[:300]})
        out.append({"id": sid, "title": str(s.get("title", "")).strip()[:90], "status": st,
                    "started": str(s.get("started") or today), "updated": today,
                    "summary": str(s.get("summary", "")).strip()[:300], "changed": str(s.get("changed", "")).strip()[:400],
                    "thesis": {k: str(th.get(k, "")).strip() for k in THESIS}, "timeline": sorted(tl, key=lambda e: e["date"]),
                    "groups": groups, "tickers": {k: [str(t).upper() for t in (s.get("tickers") or {}).get(k) or []][:12]
                                                  for k in ("long", "short", "watch")},
                    "catalysts": sorted(cats, key=lambda c: c["date"]), "trade": str(s.get("trade", "")).strip(),
                    "related": [_slug(x) for x in s.get("related") or []], "history": hist[-120:],
                    **({"resolved": s.get("resolved") or today} if st == "resolved" else {})})
    opened = [s for s in out if s["status"] != "resolved"]
    if len(opened) > MAX_OPEN:
        probs.append(f"{len(opened)} open stories: keep at most {MAX_OPEN} (resolve or merge the weakest)")
    closed = sorted([s for s in out if s["status"] == "resolved"], key=lambda s: s.get("resolved", ""))[-KEEP_RESOLVED:]
    # open stories keep the writer's order: the most important story first
    return {"updated": datetime.now(ET).strftime("%Y-%m-%dT%H:%M"), "stories": opened + closed}, probs


def save(S):
    STORIES.write_text(json.dumps(S, indent=1, ensure_ascii=False))


def publish(path, push=False, strict=True):
    S, probs = validate(json.load(open(path)))
    for p in probs:
        print("WARN", p)
    fatal = [p for p in probs if "open stories" in p]
    if fatal and strict:
        sys.exit("refused: " + "; ".join(fatal))
    save(S)
    print(f"ok: {sum(s['status'] != 'resolved' for s in S['stories'])} open, "
          f"{sum(s['status'] == 'resolved' for s in S['stories'])} resolved")
    if push:
        b = base64.b64encode(gzip.compress(json.dumps(S, ensure_ascii=False).encode())).decode()
        r = subprocess.run(["gh", "api", "-X", "POST", f"repos/{REPO}/actions/workflows/stories.yml/dispatches", "-f", "ref=main",
                            "-f", f"inputs[gz_b64]={b}"], capture_output=True, text=True)
        if r.returncode:
            sys.exit("dispatch failed: " + (r.stderr or r.stdout)[:400])
        print("dispatched stories.yml: committed by GitHub Actions in about a minute")


def save_b64(b):
    S = json.loads(gzip.decompress(base64.b64decode(b)).decode())
    S2, probs = validate(S, today=(S.get("updated") or "")[:10] or None)
    save(S if not probs else S2)
    print("saved", len(S2["stories"]), "stories", "; ".join(probs)[:500])


# ---------------------------------------------------------------- fact sheet for the writer
def facts():
    D = load_data()
    T = D["themes"]
    S = load()
    now = datetime.now(ET)
    out = []
    P = out.append
    P(f"# Trade Stories fact sheet · generated {now:%Y-%m-%d %H:%M} ET · official data through {T['date']}")
    P("Rules: max 6 open stories; update, don't rewrite; every timeline item needs a source URL; groups must be exact sub-theme "
      "names from the list at the bottom. Edit a copy of docs/stories.json (start from it).")
    X = T.get("thetrade") or {}
    if X.get("name"):
        P(f"\n## THE TRADE (code): {X['name']} · {X.get('state')} · {X.get('above')} sessions · corr {X.get('corr')} · "
          f"{'holds up' if (X.get('ind') or 0) >= 0 else 'gives back (seesaw)'}")
        P("Winners: " + ", ".join(g["g"] for g in X.get("winners", [])[:8]))
        P("Losers: " + ", ".join(g["g"] for g in X.get("losers", [])[:8]))
    try:
        ch = json.loads((config.DOCS_DIR / "story.json").read_text()).get("chapters", [])[-3:]
        P("\n## Latest chapters (read them for today's why): " + " | ".join(f"{c['date']} {c['slot']}: {c['title']}" for c in ch))
    except Exception:
        pass
    open_s = [s for s in S.get("stories", []) if s.get("status") != "resolved"]
    P(f"\n## Open stories ({len(open_s)})")
    soon = (now.date() + timedelta(days=10)).isoformat()
    for s in open_s:
        pc = price_check(T, s) or {}
        sc = scorecard(T, s)
        P(f"\n### {s['id']} · {s['title']} · {s['status']} since {s['started']} · last updated {s.get('updated')}")
        P(f"- Summary: {s.get('summary')}")
        P(f"- Price check (long groups vs {pc.get('vs', '–')}): today {pct(pc.get('d1'))}, 5 days {pct(pc.get('d5'))}, "
          f"20 days {pct(pc.get('d20'))} → {pc.get('verdict', 'unknown').upper()}")
        if sc:
            hits = sum(r["edge"] > 0 for r in sc)
            P(f"- Scorecard: {hits} of {len(sc)} settled days right (next {HOLD} sessions), avg {pct(sum(r['edge'] for r in sc) / len(sc))}")
        st = stocks_for(T, set(s["groups"].get("long") or []))
        if st:
            P("- Stocks in the long groups (RS 80+): " + ", ".join(
                f"{r['t']} RS {r['rsr']:.0f}{CHASE if r['chase'] else ''}{' [' + '; '.join(r['on']) + ']' if r['on'] else ''}" for r in st))
        cs = [c for c in s.get("catalysts", []) if now.date().isoformat() <= c["date"] <= soon]
        if cs:
            P("- Catalysts in the next 10 days: " + "; ".join(f"{c['date']} {c['time']} {c['name']}" for c in cs))
        past = [c for c in s.get("catalysts", []) if c["date"] < now.date().isoformat()]
        if past:
            P("- Catalysts that have now HAPPENED (research the result, add it to the timeline, drop it from catalysts): "
              + "; ".join(f"{c['date']} {c['name']}" for c in past))
    P("\n## Sub-theme names (use exactly), by sector")
    by = {}
    for r in T.get("subthemes") or []:
        if (r.get("n") or 0) >= 3:
            by.setdefault(r.get("group") or "Other", []).append(r["theme"])
    for k in sorted(by):
        P(f"- {k}: " + ", ".join(sorted(by[k])))
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("facts")
    sub.add_parser("guide")
    p = sub.add_parser("publish"); p.add_argument("--file", required=True); p.add_argument("--push", action="store_true")
    v = sub.add_parser("check"); v.add_argument("--file", required=True)
    s = sub.add_parser("save"); s.add_argument("--gz-b64", required=True)
    a = ap.parse_args()
    if a.cmd == "facts":
        print(facts())
    elif a.cmd == "guide":
        print(GUIDE.read_text())
    elif a.cmd == "check":
        S, probs = validate(json.load(open(a.file)))
        print("\n".join(probs) or "ok", f"\n{len(S['stories'])} stories")
    elif a.cmd == "publish":
        publish(a.file, a.push)
    elif a.cmd == "save":
        save_b64(a.gz_b64)
