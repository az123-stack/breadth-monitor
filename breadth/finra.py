"""FINRA daily short sale volume -> a free, daily "who was buying" read (Oct 17, 2026; research first, not on the page yet).

FINRA publishes, for every stock and every trading day (since Aug 2018, posted by ~6 PM ET, free, no key):
    https://cdn.finra.org/equity/regsho/daily/CNMSshvolYYYYMMDD.txt
    Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market
covering trades reported OFF exchange (dark pools, wholesalers / retail internalizers). "Short volume" there is mostly
market makers selling short to fill customer BUY orders, so a high short share tends to mean buyers were lifting offers
(SqueezeMetrics' DIX is built from this). Claude's sandbox can't reach cdn.finra.org; GitHub Actions can (finra.yml).

Stored per ticker (liquid universe stocks + SPY/QQQ/IWM, compact) in data/finra/YYYY-MM.parquet so any measure can be
rebuilt later; `aggregate()` writes the daily market measures to data/finra_daily.csv:
    sr_all   dollar-weighted short share of off-exchange volume, liquid universe ($3+, 100k avg vol, $5M+/day)
    sr_spx   same for S&P 500 members (closest to SqueezeMetrics' DIX)       sr_ndx  Nasdaq-100 members
    srm_all  median stock's short share (equal weight)
    offx_all off-exchange volume / consolidated volume (how much traded away from the exchanges)
    sr_SPY / sr_QQQ / sr_IWM   the ETFs themselves (ETF short volume is mostly hedging/creation noise)
"""
import argparse
import io
import logging
import time
import urllib.error
import urllib.request

import numpy as np
import pandas as pd

from . import config, store

log = logging.getLogger(__name__)
URL = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{:%Y%m%d}.txt"
DIR = config.DATA_DIR / "finra"
DAILY = config.DATA_DIR / "finra_daily.csv"
ETFS = ("SPY", "QQQ", "IWM")
UA = "Mozilla/5.0 (breadth-monitor)"


def parse(text):
    """FINRA pipe file -> DataFrame(ticker, short, total). Header-driven; the trailer line (record count) is dropped."""
    df = pd.read_csv(io.StringIO(text), sep="|", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    df = df[pd.to_numeric(df.get("ShortVolume"), errors="coerce").notna()]
    out = pd.DataFrame({"ticker": df["Symbol"].str.strip(),
                        "short": pd.to_numeric(df["ShortVolume"]).astype("float64"),
                        "total": pd.to_numeric(df["TotalVolume"]).astype("float64")})
    out = out[out.total > 0]
    return out.groupby("ticker", as_index=False)[["short", "total"]].sum()


def fetch(day, tries=3):
    """Text of one day's file, or None (404 = holiday / not posted yet)."""
    req = urllib.request.Request(URL.format(pd.Timestamp(day)), headers={"User-Agent": UA})
    for k in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return None
            log.warning("FINRA %s HTTP %s", day, e.code)
        except Exception as e:  # network hiccup
            log.warning("FINRA %s: %s", day, e)
        time.sleep(2 * (k + 1))
    return None


def _liquid(bars):
    """(date, ticker) pairs we keep: universe-style liquid stocks + the ETFs; plus close price for weighting."""
    c = bars.pivot(index="date", columns="ticker", values="c").sort_index().astype(float)
    v = bars.pivot(index="date", columns="ticker", values="v").reindex(c.index).astype(float)
    av = v.rolling(20, min_periods=15).mean()
    ok = (c >= config.MIN_PRICE) & (av >= config.MIN_AVG_VOLUME) & (c * av >= config.TILT_MIN_DOLLARS)
    for t in ETFS:
        if t in ok:
            ok[t] = c[t].notna()
    return c, v, ok


def load():
    files = sorted(DIR.glob("*.parquet")) if DIR.exists() else []
    if not files:
        return pd.DataFrame(columns=["date", "ticker", "short", "total"])
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    return df


def save(df):
    DIR.mkdir(parents=True, exist_ok=True)
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    for m, g in df.groupby(df["date"].dt.strftime("%Y-%m")):
        g = g.sort_values(["date", "ticker"]).reset_index(drop=True)
        g["short"], g["total"] = g["short"].astype("int64"), g["total"].astype("int64")
        g.to_parquet(DIR / f"{m}.parquet", index=False)


def update(recent=None, bars=None):
    """Download every trading day in our bars (or the last `recent`) that isn't stored yet."""
    bars = store.apply_splits(store.load_bars(), store.load_splits()) if bars is None else bars
    c, v, ok = _liquid(bars)
    have = load()
    done = set(have["date"].dt.normalize()) if len(have) else set()
    days = [d for d in c.index if d not in done]
    if recent:
        days = [d for d in days if d >= c.index[-min(recent, len(c.index))]]
    new = []
    for i, d in enumerate(days):
        txt = fetch(d)
        if txt is None:
            log.info("FINRA %s: not available", d.date())
            continue
        f = parse(txt)
        keep = ok.loc[d]
        f = f[f.ticker.isin(keep.index[keep.values])]
        f.insert(0, "date", d)
        new.append(f)
        if i % 25 == 0:
            log.info("FINRA %s: %d tickers (%d/%d)", d.date(), len(f), i + 1, len(days))
        if len(new) % 50 == 0:      # keep progress if a later download fails
            have = _merge_save(have, new[-50:])
    rest = len(new) % 50
    if rest:
        _merge_save(have, new[-rest:])
    log.info("FINRA: %d new days", len(new))
    return len(new)


def _merge_save(have, chunk):
    months = {pd.Timestamp(n["date"].iloc[0]).strftime("%Y-%m") for n in chunk}
    allf = pd.concat([x for x in [have] + chunk if len(x)], ignore_index=True)
    allf["date"] = pd.to_datetime(allf["date"])
    allf = allf.drop_duplicates(["date", "ticker"], keep="last")
    save(allf[allf["date"].dt.strftime("%Y-%m").isin(months)])
    return allf


def aggregate(bars=None, fin=None):
    """Daily market measures from the stored per-ticker files -> data/finra_daily.csv (returns the frame)."""
    bars = store.apply_splits(store.load_bars(), store.load_splits()) if bars is None else bars
    fin = load() if fin is None else fin
    if not len(fin):
        return pd.DataFrame()
    c, v, ok = _liquid(bars)
    sh = fin.pivot(index="date", columns="ticker", values="short").reindex(columns=c.columns)
    tot = fin.pivot(index="date", columns="ticker", values="total").reindex(columns=c.columns)
    c, v, ok = c.reindex(sh.index), v.reindex(sh.index), ok.reindex(sh.index).fillna(False)
    try:
        mem = pd.read_csv(config.DATA_DIR / "index_members.csv")
        spx, ndx = set(mem[mem["index"] == "SPX"].ticker), set(mem[mem["index"] == "NDX"].ticker)
    except Exception:
        spx, ndx = set(), set()
    stocks = ok.copy()
    for t in ETFS:
        if t in stocks:
            stocks[t] = False
    valid = stocks & sh.notna() & (tot > 0)

    def dw(mask):
        m = valid & mask
        return (sh * c).where(m).sum(axis=1) / (tot * c).where(m).sum(axis=1).replace(0, np.nan)
    allm = pd.DataFrame(True, index=valid.index, columns=valid.columns)
    out = pd.DataFrame(index=sh.index)
    out["sr_all"] = dw(allm)
    out["sr_spx"] = dw(pd.DataFrame({t: t in spx for t in valid.columns}, index=valid.index))
    out["sr_ndx"] = dw(pd.DataFrame({t: t in ndx for t in valid.columns}, index=valid.index))
    out["srm_all"] = (sh / tot).where(valid).median(axis=1)
    out["offx_all"] = tot.where(valid).sum(axis=1) / v.where(valid).sum(axis=1).replace(0, np.nan)
    out["n"] = valid.sum(axis=1)
    for t in ETFS:
        out["sr_" + t] = (sh[t] / tot[t]) if t in sh else np.nan
    out.index.name = "date"
    out = out.round(4)
    out.to_csv(DAILY)
    return out


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--recent", type=int, default=0, help="only the last N trading days in our bars (0 = all missing)")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    bars = store.apply_splits(store.load_bars(), store.load_splits())
    update(a.recent or None, bars)
    out = aggregate(bars)
    if len(out):
        log.info("FINRA daily: %d days, last %s sr_all %.3f", len(out), out.index[-1].date(), out["sr_all"].iloc[-1])


if __name__ == "__main__":
    main()
