"""10:00 / 11:00 ET price snapshots for the Second-half movers card (backup to the sheet's at10 / at11 columns).

Why (Oct 26, 2026): the sheet's freeze formulas only reset when the sheet happened to recalculate on a weekday before
10:00 ET. It didn't from Oct 14 on, so the snapshot stayed stuck on Oct 13 and the card showed nothing for two weeks.
The sheet formulas are now date-stamped (they refreeze every weekday on their own), and this module keeps an
independent copy taken by GitHub Actions, so the card works if either source fails.

    python -m breadth.anchors take [--slot at10|at11] [--force]   # read the published sheet, save docs/anchors.json
    python -m breadth.anchors check                              # after the close: did today get a snapshot? exit 1 if not

docs/anchors.json = {"date": "YYYY-MM-DD", "at10": {"time": "YYYY-MM-DD HH:MM", "rows": {TICKER: [price, volume]}}, "at11": {...},
                     "health": {...}}. The page reads it from GitHub Pages and uses it when the sheet's snapshot isn't from today.
Slots: at10 is taken between 10:00 and 10:45 ET, at11 between 11:00 and 11:45 (later than that the move is no longer
"since 10:00"). Only on the day the sheet's prices are from (holidays / stale sheet are skipped).
"""
import argparse
import json
import sys
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from . import config
from .story import read_csv_rows

ET = ZoneInfo("America/New_York")
PATH = config.ROOT / "docs" / "anchors.json"
SLOTS = {"at10": (10 * 60, 10 * 60 + 45), "at11": (11 * 60, 11 * 60 + 45)}
MIN_ROWS = 100


def fetch_csv():
    url = config.LIVE_CSV_URL + ("&" if "?" in config.LIVE_CSV_URL else "?") + "cb=" + str(int(datetime.now().timestamp()))
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def load():
    try:
        return json.loads(PATH.read_text())
    except Exception:
        return {}


def slot_for(now):
    m = now.hour * 60 + now.minute
    for k, (a, b) in SLOTS.items():
        if a <= m < b:
            return k
    return None


def take(text, now, slot=None, force=False, doc=None):
    """Add a slot to the snapshot doc from the sheet CSV text. Returns (doc, message). Pure: no file or network I/O."""
    doc = dict(doc or {})
    rows, date = read_csv_rows(text)
    today = now.strftime("%Y-%m-%d")
    if now.weekday() >= 5:
        return doc, "weekend: nothing to do"
    if date != today:
        return doc, f"sheet prices are from {date}, not today ({today}): market closed or sheet stale, skipped"
    slot = slot or slot_for(now)
    if not slot:
        return doc, f"{now:%H:%M} ET is outside the 10:00-10:45 / 11:00-11:45 windows: skipped"
    if doc.get("date") != today:
        doc = {"date": today}
    if doc.get(slot) and not force:
        return doc, f"{slot} already taken today at {doc[slot]['time']}"
    snap = {t: [r["price"], r.get("volume")] for t, r in rows.items()
            if r.get("price") is not None and r["price"] > 0}
    if len(snap) < MIN_ROWS:
        return doc, f"only {len(snap)} priced rows in the sheet: skipped"
    doc[slot] = {"time": now.strftime("%Y-%m-%d %H:%M"), "rows": snap}
    return doc, f"{slot} saved: {len(snap)} prices at {now:%H:%M} ET"


def sheet_stamps(text):
    """The sheet's own freeze stamps (row _asof, columns at10 / at11)."""
    import csv, io
    cols, out = None, {}
    for f in csv.reader(io.StringIO(text)):
        if not f:
            continue
        if f[0] == "ticker":
            cols = [c.strip().lower() for c in f]
        elif f[0] == "_asof" and cols:
            out = {c: f[i] for i, c in enumerate(cols) if c in SLOTS and i < len(f) and f[i] not in ("", "0")}
            break
    return out


def check(text, now, doc):
    """After the close: which source has a snapshot for today? ok = at least one source covers each slot."""
    rows, date = read_csv_rows(text)
    today = now.strftime("%Y-%m-%d")
    if now.weekday() >= 5 or date != today:
        return {"date": today, "ok": True, "note": "no session today"}
    st = sheet_stamps(text)
    res = {"date": today, "checked": now.strftime("%H:%M"), "sheet": {}, "backup": {}}
    ok = True
    for s in SLOTS:
        sh = st.get(s, "")
        res["sheet"][s] = sh[:10] == today
        res["backup"][s] = (doc.get("date") == today and bool(doc.get(s)))
        ok = ok and (res["sheet"][s] or res["backup"][s])
    res["ok"] = ok
    res["sheet_stamp"] = st
    return res


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("take")
    t.add_argument("--slot", choices=list(SLOTS))
    t.add_argument("--force", action="store_true")
    sub.add_parser("check")
    a = ap.parse_args()
    now = datetime.now(ET)
    text = fetch_csv()
    doc = load()
    if a.cmd == "take":
        doc, msg = take(text, now, a.slot, a.force, doc)
        print(msg)
        if "saved" in msg:
            PATH.write_text(json.dumps(doc, separators=(",", ":")))
    else:
        res = check(text, now, doc)
        doc["health"] = res
        PATH.write_text(json.dumps(doc, separators=(",", ":")))
        print(json.dumps(res))
        if not res["ok"]:
            sys.exit("No 10:00 / 11:00 snapshot today from the sheet or the backup: the Second-half movers card had nothing "
                     "to compare against. Check the sheet's at10/at11 formulas and the anchors workflow.")


if __name__ == "__main__":
    main()
