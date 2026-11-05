"""Raw monthly bars (full history, split-adjusted) from Yahoo for the warehouse's point-in-time overhead-supply variable.
Runs in GitHub Actions (Claude's sandbox can't reach Yahoo): `python tools/warehouse/monthly.py` → data/warehouse/monthly.json
{ticker: {"asof", "m": [[YYYY-MM, high, low, close], ...]}}. Resumable: skips tickers fetched in the last 30 days."""
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from breadth import store  # noqa: E402

OUT = ROOT / "data" / "warehouse" / "monthly.json"
URL = "https://query1.finance.yahoo.com/v8/finance/chart/{t}"


def tickers():
    s = set(store.load_subthemes()["ticker"]) | set(store.load_themes()["ticker"])
    return sorted(t for t in s if isinstance(t, str) and t)


def fetch(t, sess):
    r = sess.get(URL.format(t=t.replace(".", "-")), params={"range": "max", "interval": "1mo"},
                 headers={"User-Agent": "Mozilla/5.0 (breadth-monitor)"}, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(str(r.status_code))
    res = ((r.json().get("chart") or {}).get("result") or [None])[0]
    if not res:
        return None
    ts = res.get("timestamp") or []
    q = ((res.get("indicators") or {}).get("quote") or [{}])[0]
    out = []
    for i, t0 in enumerate(ts):
        h, l, c = q.get("high", [None])[i], q.get("low", [None])[i], q.get("close", [None])[i]
        if h is None or c is None:
            continue
        out.append([datetime.fromtimestamp(t0, timezone.utc).strftime("%Y-%m"), round(h, 4), round(l, 4) if l is not None else None, round(c, 4)])
    return out


def main(budget_s=3000):
    data = json.loads(OUT.read_text()) if OUT.exists() else {}
    sess, t0, done, fails = requests.Session(), time.time(), 0, 0
    today = date.today()
    for t in tickers():
        rec = data.get(t)
        if rec and (today - date.fromisoformat(rec["asof"])).days < 30:
            continue
        if time.time() - t0 > budget_s:
            break
        try:
            m = fetch(t, sess)
            if m:
                data[t] = {"asof": today.isoformat(), "m": m}
            done += 1
            fails = 0
        except Exception as e:
            fails += 1
            print("fail", t, e)
            if fails >= 15:
                print("too many failures in a row; stopping")
                break
            time.sleep(2)
        time.sleep(0.4)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")))
    print(f"fetched {done}, total {len(data)} of {len(tickers())}")


if __name__ == "__main__":
    main()
