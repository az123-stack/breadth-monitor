"""Russell 2000 members and weights, from an IWM holdings file Adam downloads from iShares.

iShares and Vanguard block scripted downloads from GitHub's servers (tested Oct 13, 2026), so the
member list comes from the "Detailed Holdings" CSV on the iShares IWM page, imported with
    python -m breadth.russell path/to/IWM_holdings.csv
into data/russell2000.csv (ticker, mv, sector, exchange, asof). Weights are refreshed every build
from our own closes (market value on the file date x price change since), so only membership goes
stale. The Intraday tab shows a re-upload caution once the file is STALE_DAYS old.
"""
import csv
import io
import logging
import re
import sys
from datetime import datetime

from . import config

log = logging.getLogger(__name__)

STALE_DAYS = 45        # caution on the Intraday tab
OLD_DAYS = 75          # red caution
# iShares exchange name -> Google Finance prefix (bare tickers can resolve to the wrong listing)
EXCHANGE = {"nasdaq": "NASDAQ", "nyse": "NYSE", "new york stock exchange inc.": "NYSE", "nyse arca": "NYSEARCA",
            "nyse mkt llc": "NYSEAMERICAN", "cboe bzx formerly known as bats": "BATS"}


def path():
    return config.DATA_DIR / "russell2000.csv"


def _num(v):
    try:
        return float(str(v).replace(",", "").replace("%", ""))
    except (TypeError, ValueError):
        return None


def parse(text):
    """Holdings CSV -> (rows, asof 'YYYY-MM-DD'). Listed equity rows with a positive market value."""
    lines = text.lstrip("\ufeff").splitlines()
    asof = None
    for ln in lines[:12]:
        m = re.search(r"as of,\"?([A-Za-z]{3} \d{1,2}, \d{4})", ln)
        if m:
            asof = datetime.strptime(m.group(1), "%b %d, %Y").date().isoformat()
    start = next((i for i, ln in enumerate(lines) if ln.startswith("Ticker,")), None)
    if start is None:
        raise ValueError("this doesn't look like an iShares holdings file (no 'Ticker,' header)")
    out = []
    for r in csv.DictReader(io.StringIO("\n".join(lines[start:]))):
        t = (r.get("Ticker") or "").strip().upper()
        if not t or t == "-" or (r.get("Asset Class") or "").strip() != "Equity":
            continue
        ex = (r.get("Exchange") or "").strip().lower()
        if ex.startswith("no market"):
            continue
        mv = _num(r.get("Market Value")) or 0.0
        if mv <= 0:
            continue
        out.append({"ticker": t.replace(" ", "."), "mv": mv, "sector": (r.get("Sector") or "Other").strip(),
                    "exchange": EXCHANGE.get(ex, "")})
    return out, asof


def import_file(src):
    with open(src, encoding="utf-8-sig") as f:
        rows, asof = parse(f.read())
    if len(rows) < 1000:
        raise ValueError(f"only {len(rows)} holdings found: is this the IWM file?")
    with open(path(), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "mv", "sector", "exchange", "asof"])
        for x in rows:
            w.writerow([x["ticker"], round(x["mv"], 2), x["sector"], x["exchange"], asof or ""])
    log.info("Russell 2000: %d holdings (as of %s)", len(rows), asof)
    return len(rows), asof


def load():
    """[{ticker, mv, sector, exchange}], asof — empty if never imported."""
    if not path().exists():
        return [], None
    with open(path()) as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["mv"] = float(r["mv"])
    return rows, (rows[0].get("asof") or None) if rows else None


def weights(adjusted=None):
    """{ticker: weight %}: file market value x (latest close / close on the file date), normalised.
    Names without bars keep their file value."""
    rows, asof = load()
    if not rows:
        return {}, None
    mv = {r["ticker"]: r["mv"] for r in rows}
    last_date = None
    if adjusted is not None and asof and len(adjusted):
        import pandas as pd
        sub = adjusted[adjusted["ticker"].isin(mv)]
        if len(sub):
            c = sub.pivot_table(index="date", columns="ticker", values="c").sort_index().ffill()
            base = c[c.index <= pd.Timestamp(asof)]
            if len(base):
                ratio = (c.iloc[-1] / base.iloc[-1]).dropna()
                ratio = ratio[(ratio > 0.2) & (ratio < 5)]          # ignore bad prints
                for t, x in ratio.items():
                    mv[t] *= float(x)
                last_date = c.index[-1].strftime("%Y-%m-%d")
    tot = sum(mv.values())
    return {t: round(v / tot * 100, 5) for t, v in mv.items()}, last_date


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if len(sys.argv) != 2:
        sys.exit("usage: python -m breadth.russell path/to/IWM_holdings.csv")
    n, d = import_file(sys.argv[1])
    print(f"imported {n} Russell 2000 holdings as of {d}")
