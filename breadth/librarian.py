"""The Librarian: a weekly "sleep cycle" that rewrites the Claude Project brief from the repo, for Adam to approve.

Why: the Project's context doc (what every Market Dashboard chat starts from) goes stale while CLAUDE.md, the research
cards and data/layers.json stay current. The Librarian agent (Claude scheduled task, Saturday after the Integrator)
reads a source pack built here, drafts a compact brief, and PROPOSES it. Nothing changes until Adam says
"approve brief"; a session then runs `approve` and copies research/BRIEF.md into the Project doc.

    python -m breadth.librarian pack                 # source pack for the agent (stdout, markdown)
    python -m breadth.librarian check --file F.md    # validate a draft brief (markdown) without publishing
    python -m breadth.librarian diff                 # proposed draft (docs/agent/brief.json) vs approved research/BRIEF.md
    python -m breadth.librarian approve              # (only when Adam says so) draft -> research/BRIEF.md

Rules the code enforces (so a bad week can't quietly rewrite how every chat thinks):
  * every pinned rule in research/PINNED.md appears word for word (pinned rules never decay);
  * required sections, a word cap, no secrets, every R-card id named exists;
  * every card filed since the last approved brief is mentioned (nothing new gets silently dropped);
  * a layer written as `layer_id (status)` must carry its real status from data/layers.json;
  * "approved" is only ever written by `approve`, never by the agent.
Standard library only (the agent save job imports it).
"""
import argparse
import difflib
import json
import re
import sys
from datetime import date

from . import config, research

PINNED = "PINNED.md"
APPROVED = "BRIEF.md"
WORD_CAP = 3000
SECTIONS = ("## Rules that never fade", "## How it runs", "## What's live", "## Findings", "## Open threads")
SECRET = re.compile(r"(sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|"
                    r"MASSIVE_API_KEY\s*[=:]\s*\S{8,}|apiKey=[A-Za-z0-9]{12,})")
CARD = re.compile(r"\bR-\d{4}-\d{2}-\d{2}-[a-z0-9-]+\b")
LAYER_STATUS = re.compile(r"`?([a-z0-9_]+)`?\s*\((idea|tested|info|proven|approved|live|retired)\)")
HEADER = re.compile(r"^<!-- approved: (\d{4}-\d{2}-\d{2}) draft: (\d{4}-\d{2}-\d{2}) -->")
SKIP_CLAUDE = ("Code map", "Findings so far")   # the code map is summarised below; findings come from the cards


def _rdir():
    return research.research_dir()


def pinned_rules():
    p = _rdir() / PINNED
    if not p.exists():
        return []
    return [ln[2:].strip() for ln in p.read_text().splitlines() if ln.startswith("- ") and ln[2:].strip()]


def approved():
    """(approved date, draft date, brief text) of research/BRIEF.md, or (None, None, '')."""
    p = _rdir() / APPROVED
    if not p.exists():
        return None, None, ""
    txt = p.read_text()
    m = HEADER.match(txt)
    body = txt.split("\n", 1)[1] if m else txt
    return (m.group(1), m.group(2), body.lstrip("\n")) if m else (None, None, body)


def draft_path():
    return config.DOCS_DIR / "agent" / "brief.json"


def draft():
    try:
        return json.loads(draft_path().read_text())
    except Exception:
        return None


def _claude_sections():
    p = config.ROOT / "CLAUDE.md"
    if not p.exists():
        return ""
    out, keep, name = [], True, ""
    for ln in p.read_text().splitlines():
        if ln.startswith("## "):
            name = ln[3:]
            keep = not any(name.startswith(s) for s in SKIP_CLAUDE)
            out.append(ln)
            if name.startswith("Code map"):
                out.append("(module list only: first line of each entry; read CLAUDE.md for detail)")
            continue
        if keep:
            out.append(ln)
        elif name.startswith("Code map") and ln.startswith("- "):
            out.append(ln[:160] + ("…" if len(ln) > 160 else ""))
    return "\n".join(out)


def _roadmap_open():
    p = config.ROOT / "ROADMAP.md"
    if not p.exists():
        return ""
    out, done = [], False
    for ln in p.read_text().splitlines():
        if ln.startswith("## "):
            done = ln[3:].strip().lower().startswith("done")
        if done or "[x]" in ln:
            continue
        out.append(ln[:240] + ("…" if len(ln) > 240 else ""))
    return "\n".join(out)


def _nest(text):
    """Demote a sub-document's headings so the pack's own numbered sections stay the top level."""
    return "\n".join("##" + ln if ln.startswith("#") else ln for ln in (text or "").splitlines())


def pack():
    """Everything the Librarian may use, in one markdown bundle. The repo is the only source: no chats."""
    _, ap_date, ap_text = approved()       # baseline = the approved brief's DRAFT date (its content cut-off)
    cards = research.load_cards()
    reg = research.load_registry()
    L = [f"# Librarian source pack ({date.today().isoformat()})",
         f"Last approved brief (content as of): {ap_date or 'none yet (first run: compare against nothing; write it fresh)'}",
         f"Cards: {len(cards)} · layers: {len(reg['layers'])} · word cap for the brief: {WORD_CAP}", "",
         "## 1. Pinned rules (copy every one into '## Rules that never fade' WORD FOR WORD, in this order)"]
    L += [f"- {r}" for r in pinned_rules()]
    L += ["", "## 2. Layer registry (status is authoritative; write a layer as `id (status)`)"]
    for x in reg["layers"]:
        L.append(f"- {x['id']} ({x['status']}) [{x.get('kind')}] {x.get('name', '')} | evidence: "
                 f"{', '.join(x.get('evidence') or []) or 'none'}")
    L += ["", "## 3. Finding cards (NEW = filed after the last approved brief: each must be mentioned by id)"]
    for c in cards:
        new = "NEW " if not ap_date or str(c["date"]) >= ap_date else ""
        L.append(f"- {new}{c['id']} [{c['status']}, integrated {c['integrated']}] {c['title']} — {c['result']}")
    L += ["", "## 4. Open to-do (ROADMAP.md, done items removed)", _nest(_roadmap_open())]
    pl = config.DOCS_DIR / "agent" / "plan.json"
    if pl.exists():
        try:
            P = json.loads(pl.read_text())
            L += ["", f"## 5. Latest Integrator plan ({P.get('for_date')})", P.get("summary", "")]
            L += [f"- #{it.get('priority')} {it.get('title')} [{it.get('verdict')}]" for it in P.get("items", [])]
        except Exception:
            pass
    L += ["", "## 6. DECISIONS.md", _nest((config.ROOT / "DECISIONS.md").read_text()) if (config.ROOT / "DECISIONS.md").exists() else ""]
    L += ["", "## 7. CLAUDE.md (everything but the findings; code map shortened)", _nest(_claude_sections())]
    L += ["", "## 8. Current approved brief", _nest(ap_text) or "(none yet)"]
    return "\n".join(L)


def check_brief(text):
    """Return (errors, warnings) for a draft brief in markdown."""
    errs, warns = [], []
    if not isinstance(text, str) or not text.strip():
        return ["brief is empty"], warns
    if HEADER.match(text):
        errs.append("the draft must not carry an 'approved' header (only `approve` writes it)")
    words = len(text.split())
    if words > WORD_CAP:
        errs.append(f"brief is {words} words; cap is {WORD_CAP} (merge, shorten, point to cards instead)")
    pos = -1
    for s in SECTIONS:
        i = text.find("\n" + s)
        if i < 0 and not text.startswith(s):
            errs.append(f"missing section '{s}'")
        elif i < pos:
            errs.append(f"section '{s}' out of order (expected {', '.join(SECTIONS)})")
        pos = max(pos, i)
    for r in pinned_rules():
        if r not in text:
            errs.append(f"pinned rule missing or edited: {r[:80]}…")
    if SECRET.search(text):
        errs.append("brief contains something that looks like a secret key; remove it")
    cards = {c["id"]: c for c in research.load_cards()}
    named = set(CARD.findall(text))
    for cid in sorted(named - set(cards)):
        errs.append(f"card {cid} does not exist in research/")
    ap_date = approved()[1]
    for cid, c in cards.items():
        if (not ap_date or str(c["date"]) >= ap_date) and cid not in named:
            (warns if not ap_date else errs).append(f"new card {cid} not mentioned")
    reg = {x["id"]: x["status"] for x in research.load_registry()["layers"]}
    for lid, st in LAYER_STATUS.findall(text):
        if lid in reg and reg[lid] != st:
            errs.append(f"layer {lid} written as ({st}) but data/layers.json says ({reg[lid]})")
    return errs, warns


def validate(js):
    """The 'brief' agent kind: {for_date, summary, brief, changes}. Returns the clean dict or raises ValueError."""
    if not isinstance(js, dict):
        raise ValueError("brief JSON must be an object")
    text = js.get("brief")
    errs, warns = check_brief(text)
    if errs:
        raise ValueError("brief failed checks:\n  " + "\n  ".join(errs))
    summary = str(js.get("summary") or "").strip()[:800]
    if not summary:
        raise ValueError("summary is required")
    K = ("added", "updated", "merged", "retired", "moved")
    changes = []
    for c in (js.get("changes") or [])[:40]:
        if not isinstance(c, dict):
            continue
        k = str(c.get("change") or "").lower()
        what = str(c.get("what") or "").strip()[:300]
        src = str(c.get("source") or "").strip()[:120]
        if k in K and what and src:
            changes.append({"change": k, "what": what, "source": src})
    return {"summary": summary, "brief": text.strip() + "\n", "changes": changes, "words": len(text.split()),
            "warnings": warns[:20]}


def diff(limit=400):
    d = draft()
    if not d:
        return "no draft (docs/agent/brief.json) yet"
    _, _, cur = approved()
    lines = list(difflib.unified_diff(cur.splitlines(), d["brief"].splitlines(), "approved BRIEF.md",
                                      f"draft {d.get('for_date')}", lineterm="", n=0))
    add = sum(1 for x in lines if x.startswith("+") and not x.startswith("+++"))
    rem = sum(1 for x in lines if x.startswith("-") and not x.startswith("---"))
    head = f"draft {d.get('for_date')}: {d.get('words')} words · +{add} / -{rem} lines vs the approved brief"
    return "\n".join([head] + lines[:limit] + ([f"… {len(lines) - limit} more lines"] if len(lines) > limit else []))


def approve():
    d = draft()
    if not d:
        sys.exit("no draft to approve (docs/agent/brief.json missing)")
    errs, _ = check_brief(d["brief"])
    if errs:
        sys.exit("draft no longer passes the checks (pinned rules or cards changed since it was written):\n  " + "\n  ".join(errs))
    p = _rdir() / APPROVED
    p.write_text(f"<!-- approved: {date.today().isoformat()} draft: {d['for_date']} -->\n" + d["brief"])
    return p


def main(argv=None):
    a = argparse.ArgumentParser()
    a.add_argument("cmd", choices=["pack", "check", "diff", "approve"])
    a.add_argument("--file")
    o = a.parse_args(argv)
    if o.cmd == "pack":
        print(pack())
    elif o.cmd == "check":
        errs, warns = check_brief(open(o.file).read())
        for w in warns:
            print("warning:", w)
        if errs:
            print("FAILED:\n  " + "\n  ".join(errs))
            return 1
        print(f"OK ({len(open(o.file).read().split())} words)")
    elif o.cmd == "diff":
        print(diff())
    elif o.cmd == "approve":
        print(f"approved -> {approve()}  (now copy it into the Project doc)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
