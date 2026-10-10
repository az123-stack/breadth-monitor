"""Local storage: daily bars (rolling window), breadth history, small state file."""
import json
from datetime import date

import pandas as pd

from . import config

BAR_COLS = ["date", "ticker", "o", "h", "l", "c", "v"]


def _day_file(day):
    return config.BARS_DIR / f"{pd.Timestamp(day).strftime('%Y-%m-%d')}.parquet"


def load_bars():
    """All stored days as one long DataFrame (raw, unadjusted prices)."""
    files = sorted(config.BARS_DIR.glob("*.parquet")) if config.BARS_DIR.exists() else []
    if not files:
        return pd.DataFrame(columns=BAR_COLS)
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    return df


def save_bars(df, rewrite_days=()):
    """Write one file per trading day, only for days not already on disk.

    Existing files are only rewritten for `rewrite_days` (when newly added
    theme tickers were backfilled into them); splits are applied in memory.
    """
    config.BARS_DIR.mkdir(parents=True, exist_ok=True)
    for day, g in df.groupby("date"):
        f = _day_file(day)
        if f.exists() and pd.Timestamp(day) not in rewrite_days:
            continue
        g = g.sort_values("ticker").reset_index(drop=True)[BAR_COLS].copy()
        for col in ["o", "h", "l", "c"]:
            g[col] = g[col].astype("float32")
        g["v"] = g["v"].astype("float64")
        g.to_parquet(f, index=False, compression="zstd")


def append_day(bars, day, rows, keep):
    """Add one day's grouped bars, keeping only tickers in `keep`
    (the common-stock universe plus theme tickers such as ETFs and ADRs)."""
    if not rows:
        return bars
    new = pd.DataFrame(rows)
    new = new[new["ticker"].isin(keep)]
    new.insert(0, "date", pd.Timestamp(day))
    bars = bars[bars["date"] != pd.Timestamp(day)]
    return pd.concat([bars, new[BAR_COLS]], ignore_index=True) if len(bars) else new[BAR_COLS]


def apply_splits(bars, splits):
    """Back-adjust bars dated before each split's execution date (in memory).

    Stored bars stay raw (unadjusted); adjustment happens every run at compute
    time, so the order in which days and splits arrive never matters.
    A 2-for-1 split (split_from=1, split_to=2) halves earlier prices and
    doubles earlier volume. Splits dated after the newest bar are ignored
    until that day arrives.
    """
    if bars.empty or splits is None or len(splits) == 0:
        return bars
    last = bars["date"].max()
    sp = splits[(splits["execution_date"] <= last) &
                (splits["ticker"].isin(bars["ticker"].unique()))]
    if sp.empty:
        return bars
    bars = bars.copy()
    for s in sp.itertuples():
        factor = s.split_from / s.split_to
        mask = (bars["ticker"] == s.ticker) & (bars["date"] < s.execution_date)
        if mask.any():
            bars.loc[mask, ["o", "h", "l", "c"]] *= factor
            bars.loc[mask, "v"] /= factor
    return bars


def load_splits():
    if not config.SPLITS_FILE.exists():
        return pd.DataFrame(columns=["ticker", "execution_date", "split_from", "split_to"])
    return pd.read_csv(config.SPLITS_FILE, parse_dates=["execution_date"])


def save_splits(existing, new_rows):
    new = pd.DataFrame(new_rows, columns=["ticker", "execution_date", "split_from", "split_to"])
    if len(new):
        new["execution_date"] = pd.to_datetime(new["execution_date"])
    df = pd.concat([existing, new], ignore_index=True) if len(existing) else new
    df = df.drop_duplicates(["ticker", "execution_date"], keep="last")
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.sort_values(["execution_date", "ticker"]).to_csv(
        config.SPLITS_FILE, index=False, date_format="%Y-%m-%d")
    return df


def prune(bars, keep=config.KEEP_TRADING_DAYS):
    """Keep the newest `keep` trading days, in memory and on disk."""
    dates = sorted(bars["date"].unique())
    if len(dates) <= keep:
        return bars
    cutoff = dates[-keep]
    for f in config.BARS_DIR.glob("*.parquet"):
        if pd.Timestamp(f.stem) < cutoff:
            f.unlink()
    return bars[bars["date"] >= cutoff]


def load_breadth():
    if not config.BREADTH_FILE.exists():
        return pd.DataFrame()
    return pd.read_csv(config.BREADTH_FILE, parse_dates=["date"]).set_index("date")


def save_breadth(df):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.sort_index().to_csv(config.BREADTH_FILE, float_format="%.4f")


def load_universe():
    if not config.UNIVERSE_FILE.exists():
        return set()
    return set(pd.read_csv(config.UNIVERSE_FILE)["ticker"])


def save_universe(rows):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).sort_values("ticker").to_csv(config.UNIVERSE_FILE, index=False)


def load_state():
    if config.STATE_FILE.exists():
        return json.loads(config.STATE_FILE.read_text())
    return {}


def save_state(state):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


def parse_date(s):
    return date.fromisoformat(s) if s else None


def load_themes():
    """data/themes.csv -> DataFrame(theme, ticker, role). Empty if missing."""
    if not config.THEMES_FILE.exists():
        return pd.DataFrame(columns=["theme", "ticker", "role"])
    t = pd.read_csv(config.THEMES_FILE, dtype=str).fillna("")
    t["ticker"] = t["ticker"].str.strip().str.upper()
    t["theme"] = t["theme"].str.strip()
    t["role"] = t["role"].str.strip().str.lower().replace("", "member")
    return t[t["ticker"] != ""].drop_duplicates(["theme", "ticker", "role"])


def theme_tickers():
    t = load_themes()
    return set(t["ticker"]) | {config.BENCHMARK}


def load_names():
    names = {}
    for f in (config.UNIVERSE_FILE, config.REF_NAMES_FILE):
        if f.exists():
            d = pd.read_csv(f, dtype=str).fillna("")
            names.update(dict(zip(d["ticker"], d["name"])))
    import re
    junk = re.compile(r"[\s,]+(Class [A-Z]\s+)?(Common|Ordinary|American Depositary|Depositary)\b.*$|\s+Common$", re.I)
    return {k: junk.sub("", v).strip() for k, v in names.items()}


def save_ref_names(rows):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).drop_duplicates("ticker").sort_values("ticker").to_csv(config.REF_NAMES_FILE, index=False)
