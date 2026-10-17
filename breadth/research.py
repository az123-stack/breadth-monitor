"""Research ledger + layer registry: the dashboard's memory of what it has learned and what it is made of.

* `research/*.md` — one FINDING CARD per piece of research (a study, a backtest, a replay lesson). Every research chat
  ends by filing one (`python -m breadth.research new ...` writes the skeleton). Front matter between `---` lines,
  `key: value`, lists as `[a, b]`; then free text (idea, method, caveats, integration notes).
* `data/layers.json` — the LAYER REGISTRY: every input the dashboard uses or has tried, with its status on the ladder
  idea -> tested -> info -> proven -> approved -> live (or retired), the cards that are its evidence, and who owns it.

The weekly Integrator agent reads both (plus data/layer_evidence.json and DECISIONS.md) and proposes how to use new
findings. Stdlib only, so scheduled agents can run it without installing anything.

    python -m breadth.research check          # validate every card + the registry (also run by the tests)
    python -m breadth.research digest         # what the Integrator reads: new/unintegrated cards, registry, evidence
    python -m breadth.research new --id R-2026-10-20-name --title "..."   # card skeleton to fill in
"""
import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from . import config

STATUS = ("works", "doesnt", "mixed", "untested", "process")
KINDS = ("market", "group", "setup", "stock", "exit", "sizing", "macro", "news", "data", "process")
INTEGRATED = ("yes", "partly", "no", "rejected")
LADDER = ("idea", "tested", "info", "proven", "approved", "live", "retired")
REQUIRED = ("id", "title", "date", "status", "kind", "result", "integrated")
ID = re.compile(r"^R-\d{4}-\d{2}-\d{2}-[a-z0-9-]+$")


def research_dir():
    return config.ROOT / "research"


def registry_path():
    return config.DATA_DIR / "layers.json"


def _val(v):
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        return [x.strip() for x in v[1:-1].split(",") if x.strip()]
    return v


def parse(text):
    """Card text -> (front matter dict, body). Raises ValueError on a malformed card."""
    if not text.startswith("---"):
        raise ValueError("card must start with a --- front matter block")
    parts = text.split("\n---", 1)
    if len(parts) != 2:
        raise ValueError("front matter not closed with ---")
    meta = {}
    for line in parts[0].splitlines()[1:]:
        line = line.split("  #", 1)[0].rstrip()
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"bad front matter line: {line!r}")
        k, v = line.split(":", 1)
        meta[k.strip()] = _val(v)
    return meta, parts[1].lstrip("-\n")


def validate_card(meta, registry_ids=()):
    errs = []
    for k in REQUIRED:
        if not meta.get(k):
            errs.append(f"missing {k}")
    if meta.get("id") and not ID.match(meta["id"]):
        errs.append("id must look like R-YYYY-MM-DD-short-name")
    try:
        date.fromisoformat(str(meta.get("date")))
    except ValueError:
        errs.append("date must be YYYY-MM-DD")
    if meta.get("status") not in STATUS:
        errs.append(f"status must be one of {STATUS}")
    if meta.get("kind") not in KINDS:
        errs.append(f"kind must be one of {KINDS}")
    if meta.get("integrated") not in INTEGRATED:
        errs.append(f"integrated must be one of {INTEGRATED}")
    layers = meta.get("layers") or []
    if isinstance(layers, str):
        layers = [layers]
    for l in layers:
        if registry_ids and l not in registry_ids:
            errs.append(f"layer {l!r} not in data/layers.json")
    return errs


def load_cards():
    out = []
    d = research_dir()
    if not d.exists():
        return out
    for p in sorted(d.glob("R-*.md")):
        meta, body = parse(p.read_text())
        meta["_file"] = p.name
        meta["_body"] = body.strip()
        out.append(meta)
    return out


def load_registry():
    try:
        js = json.loads(registry_path().read_text())
    except Exception:
        return {"layers": []}
    return js if isinstance(js, dict) and isinstance(js.get("layers"), list) else {"layers": []}


def validate_registry(reg, card_ids=()):
    errs, seen = [], set()
    for L in reg.get("layers", []):
        i = L.get("id")
        if not i or not re.match(r"^[a-z0-9_]+$", str(i)):
            errs.append(f"bad layer id {i!r}")
        if i in seen:
            errs.append(f"duplicate layer id {i}")
        seen.add(i)
        if L.get("status") not in LADDER:
            errs.append(f"{i}: status must be one of {LADDER}")
        if L.get("kind") not in ("code", "agent"):
            errs.append(f"{i}: kind must be code or agent")
        if L.get("affects_picks") and L.get("status") not in ("approved", "live"):
            errs.append(f"{i}: only approved/live layers may affect the picks")
        for c in L.get("evidence") or []:
            if card_ids and c not in card_ids:
                errs.append(f"{i}: evidence card {c} not found in research/")
    return errs


def check():
    reg = load_registry()
    reg_ids = {L.get("id") for L in reg["layers"]}
    errs, ids = [], set()
    try:
        cards = load_cards()
    except ValueError as e:
        return [str(e)]
    for c in cards:
        for e in validate_card(c, reg_ids):
            errs.append(f"{c['_file']}: {e}")
        if c.get("id") in ids:
            errs.append(f"{c['_file']}: duplicate id")
        if c.get("id") and c["_file"] != c["id"] + ".md":
            errs.append(f"{c['_file']}: file name must be <id>.md")
        ids.add(c.get("id"))
    errs += validate_registry(reg, ids)
    return errs


def digest(full=False):
    """Plain-text bundle for the Integrator: cards not yet fully integrated (in full), the registry, the evidence."""
    cards = load_cards()
    reg = load_registry()
    try:
        ev = json.loads((config.DATA_DIR / "layer_evidence.json").read_text())
    except Exception:
        ev = {}
    lines = [f"# Research digest ({date.today().isoformat()}): {len(cards)} cards, {len(reg['layers'])} layers", ""]
    lines.append("## Layer registry (what the dashboard is made of)")
    for L in reg["layers"]:
        lines.append(f"- {L['id']} [{L['status']}, {L['kind']}, owner {L.get('owner', '?')}] {L.get('name', '')}: "
                     f"{L.get('what', '')} | evidence: {', '.join(L.get('evidence') or []) or 'none'}")
    lines += ["", "## Cards not fully integrated (read these closely)"]
    for c in cards:
        if c["integrated"] in ("no", "partly") or full:
            lines += [f"### {c['id']} — {c['title']} ({c['date']}, {c['status']}, {c['kind']}, integrated: {c['integrated']})",
                      f"Result: {c['result']}", f"Layers: {c.get('layers') or 'none'}", c["_body"], ""]
    lines += ["## Integrated or rejected cards (one line each)"]
    for c in cards:
        if c["integrated"] in ("yes", "rejected") and not full:
            lines.append(f"- {c['id']} ({c['status']}, {c['integrated']}): {c['title']} — {c['result']}")
    lines += ["", "## Layer evidence (data/layer_evidence.json)", json.dumps(ev, indent=1, default=str)[:6000]]
    return "\n".join(lines)


SKELETON = """---
id: {id}
title: {title}
date: {date}
status: untested        # works | doesnt | mixed | untested | process
kind: setup             # market | group | setup | stock | exit | sizing | macro | news | data | process
horizon: 5 sessions
sample: (dates, number of signals / events)
result: (one line with the numbers: edge, t, win rate)
halves: (first half / second half)
layers: []              # ids from data/layers.json this is evidence for (empty = new idea)
integrated: no          # yes | partly | no | rejected
source: (chat / script / commit)
---
**Idea.** What we thought might help, in plain words.

**How it was tested.** Data, entry/exit, no-look-ahead check.

**Result.** Numbers, both halves, by market state.

**Caveats.** Sample size, survivorship, overlap with existing layers.

**How it could be used.** Where it would plug in (setup filter, card flag, exit rule, sizing, new agent...).
"""


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["check", "digest", "new"])
    p.add_argument("--id")
    p.add_argument("--title", default="")
    p.add_argument("--full", action="store_true")
    a = p.parse_args(argv)
    if a.cmd == "check":
        errs = check()
        print("\n".join(errs) if errs else f"ok: {len(load_cards())} cards, {len(load_registry()['layers'])} layers")
        return 1 if errs else 0
    if a.cmd == "digest":
        print(digest(a.full))
        return 0
    if not a.id or not ID.match(a.id):
        sys.exit("--id like R-2026-10-20-short-name is required")
    f = research_dir() / f"{a.id}.md"
    if f.exists():
        sys.exit(f"{f} exists")
    research_dir().mkdir(exist_ok=True)
    f.write_text(SKELETON.format(id=a.id, title=a.title or a.id, date=a.id[2:12]))
    print(f"wrote {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
