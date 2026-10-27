"""Lined-up buys, live (Adam, Oct 27 2026: phone notifications when a stock is ready).

Every few minutes during the session (.github/workflows/lineup.yml) this reads the published Google Sheet (price, open, low) and
the last build's `DATA.themes.lifecycle.live` list (docs/data.json), finds the same states as the Intraday card (`lineupState` in
template.html, mirrored here and tested), and writes docs/lineup_live.json:
  {date, time, gate: buy | half | hold, rows: [...current states...], events: [{time, t, g, state, price, trigger, stop}, ...]}
Events are the first time today a name reaches "zone" (in the 9/21 EMAs, set the buy-stop) or "over" (price over yesterday's high =
triggered). Only names whose group is in BUY count when breadth isn't weak; on a hold-off day nothing alerts (the card still shows
them). The Claude scheduled task "Market Monitor · lined-up alerts" reads the events and sends the phone notification.
Optional instant push: if the repo secret NTFY_TOPIC is set, each new event is also posted to https://ntfy.sh/<topic>.

    python -m breadth.lineup live            # one pass (network: the sheet CSV)
    python -m breadth.lineup events --since 15   # print events from the last 15 minutes (what the alert task reads)
"""
import csv
import io
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import config

ET = ZoneInfo("America/New_York")
OUT = config.ROOT / "docs" / "lineup_live.json"
DATA = config.ROOT / "docs" / "data.json"
PRECISE = ("reclaim21", "reclaim9", "on21", "on9", "between")   # price on the line, not above it (OKTA, Oct 27)
LOC_TEXT = {"reclaim21": "reclaimed the 21", "reclaim9": "reclaimed the 9", "on21": "on the 21 EMA", "on9": "on the 9 EMA",
            "between": "between the 9 and 21"}


def read_rows(text):
    """Sheet CSV -> ({TICKER: {price, closeyest, open, low}}, sheet date 'YYYY-MM-DD')."""
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
            if i < len(f) and c in ("price", "closeyest", "open", "low"):
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


def state(x, L):
    """Python twin of lineupState (template.html). x = a lifecycle.live row, L = the sheet row (or None = last close)."""
    a = x.get("adr") or 0
    live = bool(L and (L.get("price") or 0) > 0)
    if live:
        p = L["price"]
        lo = L.get("low")
        low = min(lo, p) if lo and lo > 0 else (min(L["open"], p) if L.get("open") else p)
    else:
        p, low = x["c"], x["lo"]
    x9 = x["e9"] + (p - x["e9"]) * 0.2 if live else x["e9"]
    x21 = x["e21"] + (p - x["e21"]) * 2 / 22 if live else x["e21"]
    rib = max(x9, x21)
    touch_now = low <= rib + 0.25 * a * p and p >= x21 - 0.5 * a * p
    trig = x["hi"]
    zone = bool((touch_now or x.get("t3")) and p >= x21 - 0.5 * a * p and p <= x9 + a * p and (trig / p - 1) <= 1.5 * a)
    over = zone and live and p > trig
    near = (not zone) and p > rib and p <= rib * (1 + a)
    stop = max(low if touch_now else x["lo"], trig * (1 - a))
    st = "over" if over else "zone" if zone else "near" if near else None
    d9 = (p - x9) / (a * p) if a else 0.0
    d21 = (p - x21) / (a * p) if a else 0.0
    loc = ("reclaim21" if low < x21 and p >= x21 and d21 <= 0.5 else "reclaim9" if low < x9 and p >= x9 and d9 <= 0.5 else "on21" if abs(d21) <= 0.3
           else "on9" if abs(d9) <= 0.3 else "under21" if p < x21 else "between" if p < x9 else "above")
    return {"t": x["t"], "g": x["g"], "kind": x["kind"], "st": st, "live": live, "price": round(p, 2), "trigger": round(trig, 2),
            "stop": round(stop, 2), "x9": round(x9, 2), "x21": round(x21, 2), "rs": x.get("rs"), "earn": x.get("earn"),
            "loc": loc, "precise": loc in PRECISE, "d9": round(d9, 2), "d21": round(d21, 2)}


def run(text, lc, doc, now):
    """One pass. Pure: returns (new doc, new events). doc = yesterday's / earlier today's docs/lineup_live.json."""
    rows, sdate = read_rows(text)
    today = now.strftime("%Y-%m-%d")
    doc = dict(doc or {})
    if doc.get("date") != today:
        doc = {"date": today, "events": []}
    if sdate != today:
        doc.update({"time": now.strftime("%H:%M"), "note": f"sheet prices are from {sdate}, not today: no session"})
        return doc, []
    size = (lc or {}).get("size")
    gate = "hold" if size == "hold off" else "half" if size == "half" else "buy"
    cur = [state(x, rows.get(x["t"])) for x in (lc or {}).get("live") or []]
    cur = [c for c in cur if c["st"]]
    seen = {(e["t"], e["state"]) for e in doc.get("events") or []}
    new = []
    for c in cur:
        if c["st"] not in ("zone", "over") or c["kind"] != "buy" or gate == "hold" or not c["live"]:
            continue
        if c["st"] == "zone" and not c["precise"]:     # bounced well above the EMAs: no alert until it's on the line
            continue
        if (c["t"], c["st"]) in seen:
            continue
        new.append({"time": now.strftime("%H:%M"), "t": c["t"], "g": c["g"], "state": c["st"], "price": c["price"],
                    "trigger": c["trigger"], "stop": c["stop"], "rs": c["rs"], "earn": c["earn"], "where": LOC_TEXT.get(c["loc"], f"{c['d9']:+.1f} ADR from the 9")})
    doc.update({"time": now.strftime("%H:%M"), "gate": gate, "ratio10": (lc or {}).get("ratio10"), "built": (lc or {}).get("date"),
                "rows": cur, "events": (doc.get("events") or []) + new})
    doc.pop("note", None)
    return doc, new


def _ntfy(events):
    topic = os.environ.get("NTFY_TOPIC")
    if not topic or not events:
        return
    for e in events:
        title = f"{e['t']} {'BUY: over yesterday high' if e['state'] == 'over' else e.get('where') or 'in its 9/21 EMAs'}"
        body = f"{e['g']} · ${e['price']} · buy over ${e['trigger']}, stop ${e['stop']}"
        try:
            req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode(), headers={"Title": title, "Tags": "chart_with_upwards_trend"})
            urllib.request.urlopen(req, timeout=20).read()
        except Exception as ex:   # an alert failure never stops the loop
            print("ntfy failed:", ex)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["live", "events"])
    ap.add_argument("--since", type=int, default=15, help="minutes (events)")
    a = ap.parse_args(argv)
    now = datetime.now(ET)
    if a.cmd == "events":
        doc = json.loads(OUT.read_text()) if OUT.exists() else {}
        if doc.get("date") != now.strftime("%Y-%m-%d"):
            print(json.dumps({"date": doc.get("date"), "events": [], "note": "no events today"}))
            return
        cut = (now - timedelta(minutes=a.since)).strftime("%H:%M")
        print(json.dumps({"date": doc["date"], "time": doc.get("time"), "gate": doc.get("gate"),
                          "events": [e for e in doc.get("events") or [] if e["time"] >= cut]}, indent=1))
        return
    from .anchors import fetch_csv
    lc = (json.loads(DATA.read_text()).get("themes") or {}).get("lifecycle") or {}
    doc = json.loads(OUT.read_text()) if OUT.exists() else {}
    doc, new = run(fetch_csv(), lc, doc, now)
    OUT.write_text(json.dumps(doc, separators=(",", ":")))
    _ntfy(new)
    print(f"{doc.get('time')} gate {doc.get('gate')} · {len(doc.get('rows') or [])} names in or near the EMAs · {len(new)} new alerts"
          + (": " + ", ".join(f"{e['t']} {e['state']}" for e in new) if new else ""))


if __name__ == "__main__":
    main(sys.argv[1:])
