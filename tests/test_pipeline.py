"""Offline tests: hand-checked metrics, split handling, and a full mocked run.

    python -m pytest tests -q      (or: python tests/test_pipeline.py)
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from breadth import config, metrics, store  # noqa: E402


def make_bars(closes, vols):
    """closes/vols: dict ticker -> list (one value per trading day)."""
    n = len(next(iter(closes.values())))
    dates = pd.bdate_range("2025-01-02", periods=n)
    rows = []
    for t in closes:
        for i, d in enumerate(dates):
            c = closes[t][i]
            rows.append({"date": d, "ticker": t, "o": c, "h": c, "l": c, "c": c, "v": vols[t][i]})
    return pd.DataFrame(rows)


def test_four_percent_rules():
    n = 70
    base = [10.0] * n
    vol = [200_000] * n
    closes = {"UP": base.copy(), "UPLOWVOL": base.copy(), "DOWN": base.copy(), "CHEAP": [2.0] * n}
    vols = {k: vol.copy() for k in closes}
    # Last day: UP +5% on higher volume -> counts
    closes["UP"][-1] = 10.5; vols["UP"][-1] = 300_000
    # +5% but volume lower than prior day -> does not count
    closes["UPLOWVOL"][-1] = 10.5; vols["UPLOWVOL"][-1] = 150_000
    # -6% on higher volume -> breakdown
    closes["DOWN"][-1] = 9.4; vols["DOWN"][-1] = 400_000
    # under $3 -> ignored
    closes["CHEAP"][-1] = 2.2; vols["CHEAP"][-1] = 900_000
    m = metrics.compute(make_bars(closes, vols))
    last = m.iloc[-1]
    assert last["up4"] == 1, last["up4"]
    assert last["dn4"] == 1, last["dn4"]
    assert m["complete"].iloc[-1]


def test_quarter_and_t2108():
    n = 70
    rising = list(np.linspace(10, 14, n))       # +40% over the window, above its MA
    falling = list(np.linspace(20, 12, n))      # -40%, below its MA
    flat = [10.0] * n                            # exactly at MA -> not above
    closes = {"R": rising, "F": falling, "Z": flat}
    vols = {k: [500_000] * n for k in closes}
    m = metrics.compute(make_bars(closes, vols))
    last = m.iloc[-1]
    # 65 days back: R from ~10.29 to 14 (+36%), F from ~19.42 to 12 (-38%)
    assert last["up25q"] == 1 and last["dn25q"] == 1
    assert abs(last["t2108"] - 100 / 3) < 0.01, last["t2108"]


def test_ratio():
    n = 70
    closes, vols = {}, {}
    # 3 tickers alternately pop 5% then fall back, creating up and down days
    for k in range(3):
        c, v = [], []
        for i in range(n):
            c.append(10.5 if (i + k) % 6 == 0 else 10.0)
            v.append(200_000 + i * 1000)       # rising volume so vol_ok holds
        closes[f"T{k}"], vols[f"T{k}"] = c, v
    m = metrics.compute(make_bars(closes, vols))
    up5 = m["up4"].iloc[-5:].sum(); dn5 = m["dn4"].iloc[-5:].sum()
    assert abs(m["ratio5"].iloc[-1] - up5 / max(dn5, 1)) < 1e-9


def test_split_adjustment():
    n = 70
    c = [100.0] * 60 + [50.0] * 10          # 2-for-1 split on day 61, no real move
    v = [200_000] * 60 + [400_000] * 10
    bars = make_bars({"S": c}, {"S": v})
    raw = metrics.compute(bars)
    assert raw["dn4"].sum() == 1             # fake -50% "breakdown" before adjustment
    ex = sorted(bars["date"].unique())[60]
    splits = pd.DataFrame([{"ticker": "S", "execution_date": pd.Timestamp(ex),
                            "split_from": 1.0, "split_to": 2.0}])
    adj = metrics.compute(store.apply_splits(bars, splits))
    assert adj["dn4"].sum() == 0
    # A split dated after the last bar must be ignored
    future = splits.assign(execution_date=pd.Timestamp("2030-01-01"))
    assert store.apply_splits(bars, future)["c"].equals(bars["c"])


class FakeClient:
    """Mimics MassiveClient with a reproducible random-walk market."""
    def __init__(self, n_tickers=400, seed=7):
        self.rng = np.random.default_rng(seed)
        self.tickers = [f"T{i:04d}" for i in range(n_tickers)] + ["SPYETF"]
        self.price = dict(zip(self.tickers, self.rng.uniform(5, 80, len(self.tickers))))
        self.cache = {}
        self.calls = 0

    def common_stocks(self):
        self.calls += 1
        return [{"ticker": t, "name": t, "exchange": "XNAS"} for t in self.tickers if t != "SPYETF"] * 3

    def grouped_daily(self, d):
        self.calls += 1
        if d in self.cache:
            return self.cache[d]
        if d == date(2025, 12, 25):
            return []                        # holiday
        # regime drift: rally, then selloff, then chop
        k = d.toordinal() % 200
        drift = 0.004 if k < 70 else (-0.006 if k < 110 else 0.0)
        rows = []
        for t in self.tickers:
            r = self.rng.normal(drift, 0.03)
            self.price[t] *= 1 + r
            v = float(self.rng.lognormal(12.5, 0.6)) * (1 + 8 * abs(r))
            c = self.price[t]
            rows.append({"ticker": t, "o": c, "h": c * 1.01, "l": c * 0.99, "c": c, "v": v})
        self.cache[d] = rows
        return rows

    def splits_since(self, start):
        self.calls += 1
        return []

    def tickers_of_type(self, kind):
        self.calls += 1
        return [{"ticker": "SPYETF", "name": "Fake ETF", "type": "ETF"}] if kind == "ETF" else []

    def daily_bars(self, ticker, start, end):
        """Per-ticker history: replay cached grouped days for that ticker."""
        self.calls += 1
        out = []
        for d, rows in sorted(self.cache.items()):
            if start <= d <= end:
                out += [{"date": d, **r} for r in rows if r["ticker"] == ticker]
        return out


def test_end_to_end(tmp_path=None):
    import tempfile
    from breadth import update

    tmp = Path(tmp_path or tempfile.mkdtemp())
    for name in ["DATA_DIR", "DOCS_DIR"]:
        setattr(config, name, tmp / name.lower())
    config.BARS_DIR = config.DATA_DIR / "bars"
    config.BREADTH_FILE = config.DATA_DIR / "breadth.csv"
    config.UNIVERSE_FILE = config.DATA_DIR / "universe.csv"
    config.SPLITS_FILE = config.DATA_DIR / "splits.csv"
    config.STATE_FILE = config.DATA_DIR / "state.json"
    config.THEMES_FILE = config.DATA_DIR / "themes.csv"
    config.SUBTHEMES_FILE = config.DATA_DIR / "subthemes.csv"
    config.REF_NAMES_FILE = config.DATA_DIR / "ref_names.csv"
    config.BENCHMARK = "NOTRADED"
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)

    fake = FakeClient()
    update.MassiveClient = lambda: fake
    real_today = update.today_et

    update.today_et = lambda: date(2026, 3, 31)
    assert update.main(["--backfill-days", "400"]) == 0
    # Add themes after the backfill: the ETF must be backfilled per ticker.
    rows = ["theme,ticker,role", "Alpha,SPYETF,etf"] + [f"Alpha,T{i:04d},member" for i in range(10)] \
        + [f"Beta,T{i:04d},member" for i in range(10, 25)]
    config.THEMES_FILE.write_text("\n".join(rows) + "\n")
    config.SUBTHEMES_FILE.write_text("group,subtheme,ticker\n" + "".join(
        f"G,{'Sub A' if i < 12 else 'Sub B'},T{i:04d}\n" for i in range(25)))
    config.BENCHMARK = "SPYETF"
    hist1 = store.load_breadth()
    assert hist1["complete"].sum() > 150
    assert len(store.load_bars()["date"].unique()) == config.KEEP_TRADING_DAYS
    assert set(store.load_universe()) == set(fake.tickers) - {"SPYETF"}
    assert "SPYETF" not in set(store.load_bars()["ticker"])   # not a theme ticker yet

    # Incremental: three more days, one already-known day is not refetched
    update.today_et = lambda: date(2026, 4, 3)
    calls_before = fake.calls
    assert update.main([]) == 0
    hist2 = store.load_breadth()
    assert hist2.index.max() == pd.Timestamp("2026-04-03")
    assert len(hist2) == len(hist1) + 3
    assert fake.calls - calls_before == 5      # 3 days + 1 ETF backfill + splits
    bars_now = store.load_bars()
    etf_days = bars_now[bars_now["ticker"] == "SPYETF"]["date"].nunique()
    assert etf_days == bars_now["date"].nunique(), (etf_days, bars_now["date"].nunique())
    import json
    data = json.loads((config.DOCS_DIR / "data.json").read_text())
    T = data["themes"]
    assert T and T["counts"]["themes"] == 2 and T["counts"]["stocks"] == 25
    assert all(0 <= r["score"] <= 8 for r in T["themes"])
    assert T["counts"]["subthemes"] == 2 and all(s_["sub"] in ("Sub A", "Sub B") for s_ in T["stocks"])
    assert set(T["horizons"]) >= {"d60", "d90", "d180"}
    assert all(0 <= s_["setup"] <= 10 for s_ in T["stocks"])
    assert T["bench"]["ticker"] == "SPYETF" and T["themes"][0]["etf"] in (None, "SPYETF")
    assert 0 <= T["pulse"]["long"] <= 10 and 0 <= T["pulse"]["short"] <= 10
    # Breadth must not include the ETF
    assert hist2["universe"].max() <= 400
    # History before the bar window is untouched
    early = hist1.index[:50]
    pd.testing.assert_frame_equal(hist1.loc[early], hist2.loc[early], check_freq=False)

    html = (config.DOCS_DIR / "index.html").read_text()
    assert "/*__DATA__*/null" not in html and '"regime"' in html
    update.today_et = real_today
    return tmp



def test_v2_measures():
    from breadth import strength as S2
    # RS Rating: breakpoints map raw scores onto 1-99
    raw = pd.Series(np.linspace(-1, 1, 1001))
    bp = S2.breakpoints(raw, pd.Series(True, index=raw.index))
    r = S2.rate(np.array([-2.0, 0.0, 2.0, np.nan]), bp)
    assert r[0] == 1 and r[2] == 99 and 45 <= r[1] <= 55 and np.isnan(r[3])
    # Strength: small groups are pulled toward 50
    inp = pd.DataFrame({"rel": [0.10, -0.10, 0.20], "part": [0.9, 0.1, 0.95], "lead": [90, 10, 95], "n": [10, 10, 1]},
                       index=["big_strong", "big_weak", "tiny_strong"])
    sc = S2.strength_scores(inp)
    assert sc["big_strong"] > sc["big_weak"]
    assert abs(sc["tiny_strong"] - 50) < abs(sc["big_strong"] - 50)
    assert ((sc >= 0) & (sc <= 100)).all()


def test_setup_masks():
    from breadth import strength as S2, setups as SU
    n, tick = 80, ["A", "B"]
    dates = pd.bdate_range("2026-01-01", periods=n)
    c = pd.DataFrame({"A": np.linspace(10, 14, n), "B": [10.0] * n}, index=dates)
    c.iloc[-1, 0] = c.iloc[-2, 0] * 1.06            # A: +6% burst on the last day
    w = {"c": c, "o": c * 0.995, "h": c * 1.01, "l": c * 0.99,
         "v": pd.DataFrame(500_000.0, index=dates, columns=tick)}
    w["v"].iloc[-1, 0] = 900_000                      # on rising volume
    w["h"].iloc[-1, 0] = c.iloc[-1, 0] * 1.002        # closes near the high
    t = S2.tightness(w)
    liquid = pd.DataFrame(True, index=dates, columns=tick)
    burst, checks, lynch, ep = SU.masks(w, t, liquid)
    assert bool(burst.iloc[-1]["A"]) and not bool(burst.iloc[-1]["B"])
    assert bool(checks["H"].iloc[-1]["A"])


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            out = fn()
            print("ok ", name, out or "")
