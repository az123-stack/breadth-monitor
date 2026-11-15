"""Morning podcast (Nov 15, 2026; Adam: "turn the brief and its sub tabs into a podcast so it's easy to intake on the go" +
"make it interesting and not lame" + "try different formats each day until I tell you which I like best").

Source = the Brief: latest morning chapter of docs/story.json (Front page), docs/agent/macro_brief.json (Macro & the week
ahead) and docs/stories.json (Trade stories). The Claude scheduled task "Market Monitor · podcast" (~8:05 AM ET Mon–Fri,
after the morning story) runs `facts`, WRITES a spoken script in today's format, `check`s it and `publish --push`es it.
.github/workflows/podcast.yml turns the script into an MP3 with free Microsoft neural voices (edge-tts, one voice per
speaker), uploads it as an asset on the GitHub release `podcast` (keeps git history small) and rewrites the RSS feed
docs/podcast/feed.xml (+ episodes.json), so any podcast app can subscribe. Backup: if no episode exists by ~8:40 AM ET the
workflow's cron reads the chapter aloud (format "basic", single voice) so there is always something to listen to.

Formats rotate by trading day (FORMATS order) until Adam picks one: set FIXED_FORMAT. Episode titles name the format.

  python -m breadth.podcast facts   [--date D] [--format F]  today's format guide + the source bundle (for the agent)
  python -m breadth.podcast check   --file S.txt [--format F] validate a written script
  python -m breadth.podcast publish --file S.txt [--format F] [--date D] --push   dispatch podcast.yml with the script
  python -m breadth.podcast build   [--file S.txt] [--format F] [--date D] [--force]   script → mp3 (workflow; needs edge-tts)
  python -m breadth.podcast feed    --add /tmp/podcast/ep.json   add an episode, rewrite feed.xml, print assets to delete
  python -m breadth.podcast script  [--date D]                   print the "basic" read-aloud script (fallback)

Info only: reads what the agents already wrote, never changes picks or scores. Stdlib only except edge-tts (build).
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import gzip
import html
import json
import re
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
POD = DOCS / "podcast"
OUT = Path("/tmp/podcast")
ET = ZoneInfo("America/New_York")

REPO = "az123-stack/breadth-monitor"
SITE = "https://az123-stack.github.io/breadth-monitor"
RELEASE = "podcast"
ASSET_URL = f"https://github.com/{REPO}/releases/download/{RELEASE}/{{name}}"
KEEP = 30                 # episodes kept in the feed (older release assets are deleted)
BITRATE = 48_000          # edge-tts mp3: 24 kHz, 48 kbit/s mono → duration estimate
RATE = "+6%"

# Free Microsoft neural voices (edge-tts). Speaker tag → voice.
VOICES = {
    "MAYA": "en-US-AvaMultilingualNeural",      # two-host: host
    "JAKE": "en-US-AndrewMultilingualNeural",   # two-host: skeptical desk analyst
    "ANCHOR": "en-US-BrianMultilingualNeural",  # huddle / radio
    "NARRATOR": "en-US-AndrewMultilingualNeural",
    "DATA": "en-US-EmmaMultilingualNeural",     # narrative: the short "what the numbers say" cameo
}

FIXED_FORMAT = None       # Adam picks a favourite → e.g. "two_host"; None = rotate
ROTATION_START = dt.date(2026, 11, 16)

COMMON_RULES = """RULES FOR EVERY FORMAT
- Written for the EAR. Every line is spoken. No markdown, no bullets, no URLs, no tables, no emoji, no stage directions
  in brackets. One speaker line per paragraph, starting with the speaker tag in capitals and a colon (e.g. "MAYA: ...").
- Facts ONLY from the bundle below (chapter, macro brief, trade stories). Never invent a number, a name, a quote, a date or
  a cause. If the bundle says "no driver found", say that: it is interesting ("nobody can explain it, which itself tells you
  something").
- Say numbers the way a person would: "seven point six percent", "about ninety billion dollars", "the ten-year at five
  point one". Round where the decimal doesn't matter. Use company names the first time ("Nvidia", "Zoom"), not tickers;
  spell a ticker with spaces only when there is no common name ("C R W V"). Don't write words in ALL CAPS
  (the voice spells them letter by letter); write "mixed", not "MIXED".
- Hook in the first two lines: the single most surprising or important thing today. No "welcome back", no "buckle up",
  no "let's dive in", no "in today's episode we will", no "game-changer". Vary sentence length. Short punchy lines are good.
- Make it a SHOW: tension (what's at stake today), a point of view, and payoff (what to do or watch). Explain anything a
  smart non-quant wouldn't know in one clause.
- Cover, in whatever order the format wants: the market read and the regime call, why groups moved, the open trade stories
  (at least the two most important, by name), the next 1-3 catalysts with day and time, and Adam's trades / the list from the
  chapter if it has them.
- Say "this is information, not advice" once, near the end, in a natural way. If you discuss the Anthropic IPO story,
  mention once that Claude (the writer) is made by Anthropic.
- End with a one-line sign-off that names the date. Length: the format's word range."""

FORMATS = {
    "two_host": {
        "name": "Two-host show",
        "speakers": ["MAYA", "JAKE"],
        "words": (950, 1350),
        "guide": """FORMAT: TWO-HOST SHOW (MAYA + JAKE)
- MAYA is the host: curious, quick, keeps it moving, asks the question the listener is thinking, summarises.
- JAKE is the desk analyst: skeptical, data-first, a bit dry, pushes back with the numbers from the bundle.
- They must genuinely DISAGREE at least once on something real in the bundle (e.g. is this selling about AI or about the
  IPO? is the bounce real or a seesaw?) and settle it with evidence, or agree to disagree and say what decides it.
- Natural back-and-forth: mostly 1-3 sentence turns, interruptions are fine ("Wait, the whole basket?"). No long monologues
  (max ~70 words per turn). Light humour is welcome, never forced.
- Shape: cold open on the hook (2-4 lines) → the market read → why it moved → the trade stories → "so what do we do at
  the open?" (the list, the stops, what to avoid) → the calendar → each gives a one-line call → sign-off.""",
    },
    "huddle": {
        "name": "Desk huddle",
        "speakers": ["ANCHOR"],
        "words": (800, 1100),
        "guide": """FORMAT: DESK HUDDLE (ANCHOR = the head trader running the pre-market call)
- Tone: a sharp head trader talking to their desk at 8 AM. Direct, confident, a little intense, zero fluff. Second person
  ("you", "we"). Short sentences.
- Segments, announced out loud: "The call." (regime + how much to size, one reason) → "Ninety seconds on the tape."
  (what happened and why, the 3 biggest movers with their cause) → "Three themes." (numbered; what's working, what isn't)
  → "The stories." (each open trade story in two lines: where it stands, what would change it) → "The list." (names, triggers,
  stops ONLY as given in the chapter / stories; if none, say what kind of setup to look for and where on the dashboard) →
  "What makes us wrong." (2-3 concrete things, with times) → "One lesson." (the chapter's How markets work point in plain
  words) → sign-off.
- Each segment ends cleanly; the listener should be able to repeat the call and the list from memory.""",
    },
    "narrative": {
        "name": "Story-first",
        "speakers": ["NARRATOR", "DATA"],
        "words": (950, 1300),
        "guide": """FORMAT: STORY-FIRST NARRATIVE (like a daily news podcast)
- NARRATOR tells ONE big storyline as a story: a cold open scene or contrast ("Six weeks ago... On Friday..."), the stakes,
  the characters (companies, funds, the Fed), the turn, and the open question. Build tension; reveal the key number late.
- DATA is a short second voice (2-5 lines in the whole episode) that states the hard numbers flatly when the narrator asks
  ("What do the numbers say?"). Keep DATA lines under 40 words.
- After the main story: "Quick hits" (3-5 one-to-two-sentence items: other movers, the other trade stories, macro), then
  "What to watch" (catalysts with day and time, and the one number that tells you whether the main story is over),
  then sign-off.
- Pick the main story from the chapter's biggest driver or the most-changed trade story, not a random one.""",
    },
    "radio": {
        "name": "Radio news",
        "speakers": ["ANCHOR"],
        "words": (650, 900),
        "guide": """FORMAT: RADIO NEWS (ANCHOR, financial-radio bulletin)
- Opens with the time and three headlines in one breath ("It's eight o'clock in New York. Futures are..., the ten-year...,
  and..."). Tight, polished, authoritative; faster pace than the other formats.
- Segments: "Top story" → "Markets" (breadth, regime, what led and lagged, why) → "The trade stories" (each open story in
  one or two sentences) → "On the calendar" (with times) → "The number of the day" (one striking number from the bundle and
  why it matters) → sign-off with the date.""",
    },
}
BASIC = {"name": "Read-aloud", "speakers": ["ANCHOR"], "words": (0, 99999), "guide": ""}

# All-caps words a voice should say as a word / keep as a known acronym (others are spelled out with spaces).
SAY_AS_WORD = {"VIX", "NATO", "OPEC", "NASA", "GAAP", "SOXX", "FANG", "ASAP", "COVID", "LIVE", "WATCH", "BUY", "SELL",
               "HOLD", "NOT", "AND", "OR", "THE", "NEW", "TEAM", "MAYA", "JAKE", "ANCHOR", "NARRATOR", "DATA"}
KEEP_UPPER = {"AI", "IPO", "ETF", "CEO", "CFO", "EPS", "GDP", "CPI", "PPI", "PCE", "FOMC", "SEC", "US", "UK", "EU",
              "ADR", "ATR", "EMA", "RS", "ATH", "OK", "AM", "PM", "ET", "WTI"}


# ---------- formats ----------
def _trading_days_between(a: dt.date, b: dt.date) -> int:
    n, d = 0, a
    step = 1 if b >= a else -1
    while d != b:
        d += dt.timedelta(days=step)
        if d.weekday() < 5:
            n += step
    return n


def format_for(date: str) -> str:
    if FIXED_FORMAT:
        return FIXED_FORMAT
    keys = list(FORMATS)
    return keys[_trading_days_between(ROTATION_START, dt.date.fromisoformat(date)) % len(keys)]


def _fmt(key: str) -> dict:
    return BASIC if key == "basic" else FORMATS[key]


# ---------- text helpers ----------
def _money(m: re.Match) -> str:
    n, unit = m.group(1), (m.group(2) or "").upper()
    word = {"K": " thousand", "M": " million", "B": " billion", "T": " trillion"}.get(unit, "")
    return f"{n}{word} dollars"


def _ticker(m: re.Match) -> str:
    w = m.group(0)
    return w if (w in SAY_AS_WORD or w in KEEP_UPPER) else " ".join(w)


def ear(t: str, spell_tickers: bool = True) -> str:
    """Last-mile normalisation of a spoken line (symbols → words). Safe on agent-written scripts too."""
    t = t.replace("S&P", "S and P").replace("&", " and ")
    t = re.sub(r"\$([\d.,]+)\s?([KMBT])\b", _money, t)
    t = re.sub(r"\$([\d.,]+)", r"\1 dollars", t)
    t = re.sub(r"(?<![\w.])[−-](?=\d)", "minus ", t)
    t = re.sub(r"(?<![\w.])\+(?=\d)", "plus ", t)
    t = t.replace("%", " percent").replace("×", " times").replace("→", " to ").replace("->", " to ")
    t = t.replace("≥", "at least ").replace("≤", "at most ").replace("~", "about ").replace("–", " to ")
    t = re.sub(r"\s—\s|—", ", ", t)
    t = re.sub(r"\bvs\.?\b", "versus", t)
    t = re.sub(r"\bbps?\b", "basis points", t)
    if spell_tickers:
        t = re.sub(r"\b[A-Z]{2,5}\b", _ticker, t)
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r" +([.,;:!?])", r"\1", t).strip()


def speakable(md: str) -> str:
    """Markdown chapter text → plain sentences (used by the 'basic' fallback and for feed summaries)."""
    t = md or ""
    t = re.sub(r"\(\s*\[[^\]]+\]\([^)]+\)(?:\s*[,;]\s*\[[^\]]+\]\([^)]+\))*\s*\)", "", t)   # drop "([Src](u), …)"
    t = re.sub(r"\((?:same source|dashboard data)\)", "", t, flags=re.I)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"\*\*([^*]+?):\*\*", r"\n\1.\n", t)
    t = re.sub(r"[*_`#>]", "", t)
    t = re.sub(r"^\s*[-•]\s+", "", t, flags=re.M)
    t = re.sub(r"\(?\bn\s?=?\s?(\d+)\)?", r"(\1 cases)", t)
    t = re.sub(r"\b(\d+)(st|nd|rd|th) pct\b", r"\1\2 percentile", t)
    t = re.sub(r"\(\s*\)", "", t)
    out, para = [], []
    for ln in (ln.strip() for ln in t.splitlines()):
        if not ln:
            if para:
                out.append(ear(" ".join(para))); para = []
            continue
        para.append(ln if ln[-1] in ".!?:;," else ln + ".")
    if para:
        out.append(ear(" ".join(para)))
    return "\n\n".join(out)


def _say_date(d: dt.date) -> str:
    n = d.day
    suf = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{d:%A}, {d:%B} {n}{suf}"


def _load(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _chapter(date: str | None = None):
    chs = ((_load(DOCS / "story.json") or {}).get("chapters") or [])
    am = [c for c in chs if c.get("slot") == "am" and (not date or c.get("date") == date)]
    if am:
        return am[-1]
    return None if date else (chs[-1] if chs else None)


def _open_stories():
    return [s for s in ((_load(DOCS / "stories.json") or {}).get("stories") or []) if s.get("status") != "resolved"]


# ---------- the bundle the agent writes from ----------
def facts(date: str | None = None, fmt: str | None = None) -> str:
    ch = _chapter(date)
    if not ch:
        raise SystemExit(f"no morning chapter{' for ' + date if date else ''} in docs/story.json")
    key = fmt or format_for(ch["date"])
    f = _fmt(key)
    day = dt.date.fromisoformat(ch["date"])
    lo, hi = f["words"]
    head = [f"# Podcast · {_say_date(day)} · format `{key}` = {f['name']} · {lo}-{hi} words · speakers: {', '.join(f['speakers'])}",
            "", f["guide"], "", COMMON_RULES, "",
            "When done: python3 -m breadth.podcast check --file /tmp/pod.txt  (fix everything it lists), then",
            f"python3 -m breadth.podcast publish --file /tmp/pod.txt --date {ch['date']} --push   (ONCE).", "",
            "=" * 100, "SOURCE BUNDLE (the only facts you may use)", "=" * 100, "",
            f"## Front page · morning chapter {ch['date']}: {ch.get('title', '')}", "", ch.get("md", "")]
    mb = _load(DOCS / "agent" / "macro_brief.json") or {}
    if mb:
        head += ["", f"## Macro & the week ahead (written {mb.get('written', '?')}, risk {mb.get('risk', '?')})",
                 *(f"- {k}: {mb[k]}" for k in ("headline", "rates", "fed", "oil", "geo") if mb.get(k)),
                 "- events: " + "; ".join(f"{e.get('date')} {e.get('time', '')} {e.get('name')} ({e.get('impact', '')})"
                                          for e in (mb.get("events") or []) if str(e.get("date", "")) >= ch["date"])]
    for s in _open_stories():
        th = s.get("thesis") or {}
        head += ["", f"## Trade story: {s.get('title')} [{s.get('status')}] (id {s.get('id')})",
                 f"summary: {s.get('summary', '')}", f"changed: {s.get('changed', '')}",
                 *(f"{k}: {th[k]}" for k in ("what", "why", "how", "real", "confirm") if th.get(k)),
                 "groups long: " + ", ".join((s.get("groups") or {}).get("long") or []) +
                 " | short: " + ", ".join((s.get("groups") or {}).get("short") or []),
                 "catalysts: " + "; ".join(f"{c.get('date')} {c.get('time', '')} {c.get('name')}: {c.get('why', '')}"
                                           for c in (s.get("catalysts") or [])),
                 f"trade: {s.get('trade', '')}"]
    return "\n".join(head)


# ---------- scripts ----------
def parse(text: str) -> list[tuple[str, str]]:
    """'TAG: line' paragraphs → [(tag, line)]. Untagged paragraphs continue the previous speaker."""
    out: list[tuple[str, str]] = []
    for para in re.split(r"\n\s*\n|\n(?=[A-Z]{3,10}:)", text.strip()):
        para = " ".join(para.split())
        if not para:
            continue
        m = re.match(r"^([A-Z]{3,10}):\s*(.*)$", para)
        if m:
            out.append((m.group(1), m.group(2)))
        elif out:
            out[-1] = (out[-1][0], out[-1][1] + " " + para)
        else:
            out.append(("ANCHOR", para))
    return [(t, s) for t, s in out if s]


def check(text: str, fmt: str) -> list[str]:
    f = _fmt(fmt)
    errs = []
    lines = parse(text)
    words = sum(len(s.split()) for _, s in lines)
    lo, hi = f["words"]
    if not lo <= words <= hi:
        errs.append(f"{words} words; {f['name']} wants {lo}-{hi}")
    tags = {t for t, _ in lines}
    bad = tags - set(f["speakers"])
    if bad:
        errs.append(f"unknown speaker tags {sorted(bad)}; use {f['speakers']}")
    if fmt == "two_host" and not {"MAYA", "JAKE"} <= tags:
        errs.append("two-host show needs both MAYA and JAKE")
    if fmt == "two_host":
        long_turns = [s[:40] for t, s in lines if len(s.split()) > 90]
        if long_turns:
            errs.append(f"{len(long_turns)} turn(s) over 90 words (keep it a conversation): {long_turns[:2]}")
    if re.search(r"https?://|www\.|\]\(|\*\*|^#|^\s*[-•] ", text, flags=re.M):
        errs.append("markdown or a URL left in the script (it is read aloud)")
    if re.search(r"\[[^\]]*\]", text):
        errs.append("bracketed stage direction or citation left in")
    if "not advice" not in text.lower():
        errs.append('say "information, not advice" once')
    cliches = [c for c in ("buckle up", "dive in", "dive into", "game-changer", "game changer", "welcome back",
                           "in today's episode") if c in text.lower()]
    if cliches:
        errs.append(f"cut the clichés: {cliches}")
    return errs


def basic_script(date: str | None = None) -> str:
    ch = _chapter(date)
    if not ch:
        raise SystemExit("no chapter in docs/story.json")
    day = dt.date.fromisoformat(ch["date"])
    parts = [f"Good morning. This is the Market Monitor brief for {_say_date(day)}.",
             f"The lead story: {speakable(ch.get('title', ''))}", speakable(ch.get("md", ""))]
    mb = _load(DOCS / "agent" / "macro_brief.json") or {}
    if mb.get("headline"):
        parts.append("Macro and the week ahead. " + " ".join(speakable(mb[k]) for k in ("headline", "rates", "fed", "oil", "geo") if mb.get(k)))
    st = _open_stories()
    if st:
        parts.append("Trade stories. " + " ".join(f"{speakable(s.get('title', ''))} {speakable(s.get('summary', ''))}" for s in st))
    parts.append("That's the brief. This is information, not advice.")
    return "\n\n".join("ANCHOR: " + p.replace("\n\n", " ") for p in parts)


# ---------- publish (agent side) ----------
def publish(file: str, date: str | None, fmt: str | None, push: bool):
    text = Path(file).read_text()
    ch = _chapter(date)
    if not ch:
        sys.exit("no morning chapter for that date")
    key = fmt or format_for(ch["date"])
    errs = check(text, key)
    if errs:
        sys.exit("fix first:\n- " + "\n- ".join(errs))
    b64 = base64.b64encode(gzip.compress(text.encode())).decode()
    if not push:
        print(f"ok ({len(b64)} chars); add --push to dispatch podcast.yml")
        return
    r = subprocess.run(["gh", "api", "-X", "POST", f"repos/{REPO}/actions/workflows/podcast.yml/dispatches", "-f", "ref=main",
                        "-f", f"inputs[date]={ch['date']}", "-f", f"inputs[format]={key}", "-f", f"inputs[script_gz_b64]={b64}"],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit("dispatch failed: " + (r.stderr or r.stdout)[:400])
    print("dispatched podcast.yml: the episode appears in the feed in about 2-4 minutes")


# ---------- audio (workflow side) ----------
FALLBACK = {"MAYA": "en-US-AriaNeural", "JAKE": "en-US-GuyNeural", "ANCHOR": "en-US-ChristopherNeural",
            "NARRATOR": "en-US-GuyNeural", "DATA": "en-US-JennyNeural"}


async def _one(tag: str, text: str, spell: bool) -> bytes:
    """One spoken line → mp3 bytes. Retries, then the older (non-multilingual) voice; b'' if it still fails."""
    import asyncio
    import edge_tts
    say = ear(text, spell)
    for attempt, voice in enumerate([VOICES.get(tag, VOICES["ANCHOR"])] * 3 + [FALLBACK.get(tag, "en-US-GuyNeural")] * 2):
        try:
            buf = bytearray()
            async for chunk in edge_tts.Communicate(say, voice, rate=RATE).stream():
                if chunk["type"] == "audio":
                    buf += chunk["data"]
            if buf:
                return bytes(buf)
        except Exception as e:   # NoAudioReceived / throttling / network blips
            print(f"  retry {attempt + 1} {tag} ({type(e).__name__}): {say[:60]!r}", file=sys.stderr)
        await asyncio.sleep(2 + 3 * attempt)
    return b""


async def _synth(lines, path: Path, spell: bool):
    import asyncio
    sem = asyncio.Semaphore(4)

    async def run(tag, s):
        async with sem:
            return await _one(tag, s, spell)
    parts = await asyncio.gather(*(run(t, s) for t, s in lines))
    missing = [lines[i][1][:60] for i, b in enumerate(parts) if not b]
    if len(missing) > max(1, len(lines) // 10):
        raise SystemExit(f"TTS failed on {len(missing)} of {len(lines)} lines, e.g. {missing[:3]}")
    if missing:
        print(f"warning: skipped {len(missing)} line(s) the voice service refused: {missing}", file=sys.stderr)
    path.write_bytes(b"".join(parts))


def build(file: str | None, date: str | None, fmt: str | None, force: bool = False) -> dict:
    ch = _chapter(date)
    if not ch:
        raise SystemExit("no morning chapter for that date")
    if file:
        text = Path(file).read_text()
        key = fmt or format_for(ch["date"])
    else:
        text, key = basic_script(ch["date"]), "basic"
    ep_id = f"{ch['date']}-am"
    if not force and any(e["id"] == ep_id for e in _episodes()):
        print(json.dumps({"skip": f"episode {ep_id} already in the feed"}))
        return {}
    import asyncio
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%H%M%S")
    mp3 = OUT / f"{ep_id}-{key}-{stamp}.mp3"       # unique name: re-runs never collide with an old asset
    lines = parse(text)
    asyncio.run(_synth(lines, mp3, key == "basic"))
    size = mp3.stat().st_size
    if size < 20_000:
        raise SystemExit(f"audio too small ({size} bytes); TTS failed")
    f = _fmt(key)
    ep = {"id": ep_id, "date": ch["date"], "slot": "am", "format": key, "format_name": f["name"],
          "title": ch.get("title", "Market Monitor brief"), "name": mp3.name, "file": str(mp3),
          "url": ASSET_URL.format(name=mp3.name), "bytes": size, "seconds": round(size * 8 / BITRATE),
          "words": sum(len(s.split()) for _, s in lines),
          "summary": re.sub(r"\s+", " ", speakable(ch.get("md", ""))[:500]).strip()}
    (OUT / "ep.json").write_text(json.dumps(ep))
    print(json.dumps({k: v for k, v in ep.items() if k != "summary"}))
    return ep


# ---------- feed ----------
def _episodes() -> list:
    return (_load(POD / "episodes.json") or {}).get("episodes") or []


def add_episode(ep: dict) -> list:
    """Add/replace an episode (same id → replaced), keep the newest KEEP. Returns asset names to delete."""
    fields = ("id", "date", "slot", "format", "format_name", "title", "name", "url", "bytes", "seconds", "words", "summary")
    keep = {k: ep[k] for k in fields if k in ep}
    keep["published"] = ep.get("published") or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    old = _episodes()
    dropped = [e["name"] for e in old if e["id"] == keep["id"] and e["name"] != keep["name"]]
    eps = [e for e in old if e["id"] != keep["id"]] + [keep]
    eps.sort(key=lambda e: (e["date"], e["published"]), reverse=True)
    dropped += [e["name"] for e in eps[KEEP:]]
    eps = eps[:KEEP]
    POD.mkdir(parents=True, exist_ok=True)
    (POD / "episodes.json").write_text(json.dumps({"updated": keep["published"], "episodes": eps}, indent=1))
    (POD / "feed.xml").write_text(feed_xml(eps))
    return dropped


def _rfc822(iso: str) -> str:
    d = dt.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    return d.strftime("%a, %d %b %Y %H:%M:%S +0000")


def feed_xml(eps: list) -> str:
    e = html.escape
    items = []
    for x in eps:
        mins, secs = divmod(int(x.get("seconds", 0)), 60)
        day = dt.date.fromisoformat(x["date"])
        fmt = x.get("format_name") or "Brief"
        items.append(f"""  <item>
   <title>{e(f"{day:%a %b} {day.day} · {fmt} · {x['title']}")}</title>
   <description>{e(f"Format: {fmt}. " + x.get('summary', ''))}</description>
   <enclosure url="{e(x['url'])}" length="{int(x['bytes'])}" type="audio/mpeg"/>
   <guid isPermaLink="false">market-monitor-{e(x['name'])}</guid>
   <pubDate>{_rfc822(x['published'])}</pubDate>
   <itunes:duration>{mins}:{secs:02d}</itunes:duration>
   <itunes:explicit>false</itunes:explicit>
  </item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom">
 <channel>
  <title>Market Monitor · Morning Brief</title>
  <link>{SITE}/v3/</link>
  <atom:link href="{SITE}/podcast/feed.xml" rel="self" type="application/rss+xml"/>
  <description>The Market Monitor's Brief as a morning show each weekday: the front-page story, macro and the week ahead, and the open trade stories. Written by Claude from the dashboard. Information, not advice.</description>
  <language>en-us</language>
  <itunes:author>Market Monitor</itunes:author>
  <itunes:image href="{SITE}/podcast/cover.png"/>
  <image><url>{SITE}/podcast/cover.png</url><title>Market Monitor · Morning Brief</title><link>{SITE}/v3/</link></image>
  <itunes:category text="Business"><itunes:category text="Investing"/></itunes:category>
  <itunes:explicit>false</itunes:explicit>
  <itunes:block>Yes</itunes:block>
{chr(10).join(items)}
 </channel>
</rss>
"""


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m breadth.podcast")
    ap.add_argument("cmd", choices=["facts", "check", "publish", "build", "feed", "script"])
    ap.add_argument("--date")
    ap.add_argument("--format", choices=[*FORMATS, "basic"])
    ap.add_argument("--file")
    ap.add_argument("--add")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "facts":
        print(facts(a.date, a.format))
    elif a.cmd == "check":
        ch = _chapter(a.date)
        errs = check(Path(a.file).read_text(), a.format or format_for(ch["date"]))
        print("ok" if not errs else "fix:\n- " + "\n- ".join(errs))
        sys.exit(1 if errs else 0)
    elif a.cmd == "publish":
        publish(a.file, a.date, a.format, a.push)
    elif a.cmd == "build":
        build(a.file, a.date, a.format, a.force)
    elif a.cmd == "feed":
        for name in add_episode(json.loads(Path(a.add).read_text())):
            print(name)
    else:
        print(basic_script(a.date))


if __name__ == "__main__":
    main()
