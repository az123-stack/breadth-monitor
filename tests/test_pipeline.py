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
    config.LEVELS_ENABLED = False
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
    assert update.main(["--backfill-days", str(int(config.KEEP_TRADING_DAYS * 1.5))]) == 0
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



def test_kq_screen():
    from breadth import kq
    n = 140
    dates = pd.bdate_range("2026-01-01", periods=n)
    rows = []
    def add(t, closes, vol=2_000_000, spread=0.035, gap_at=None):
        for i, d in enumerate(dates):
            c = closes[i]
            o = c * (1.12 if gap_at is not None and i == gap_at else 1.0)
            v = vol * (10 if gap_at is not None and i == gap_at else 1)
            rows.append({"date": d, "ticker": t, "o": o, "h": c * (1 + spread), "l": c * (1 - spread), "c": c, "v": v})
    # LEAD: flat, then a steep leg up, then a tight pause near the rising 20-day
    lead = [10.0] * 70 + list(np.linspace(10, 30, 60)) + [30.0, 30.3, 30.1, 30.4, 30.2, 30.5, 30.3, 30.6, 30.4, 30.5]
    add("LEAD", lead)
    # GAP: same shape but a 10x-volume gap 5 days ago -> not this setup
    add("GAP", lead, gap_at=n - 5)
    # DULL: drifts, never a top performer -> not a candidate
    add("DULL", list(np.linspace(10, 11, n)))
    # filler so the performance percentile means something
    for k in range(40):
        add(f"F{k}", list(np.linspace(10, 10 + k * 0.05, n)))
    df = pd.DataFrame(rows)
    out = kq.build(df, set(df["ticker"]), tv={"LEAD": "NASDAQ:LEAD"})
    secs = {r["t"]: s for s in ("basing", "extended", "reject") for r in out[s]}
    assert "DULL" not in secs
    assert secs.get("GAP") == "reject", secs
    assert secs.get("LEAD") in ("basing", "extended"), secs
    assert out["tv"].get("LEAD") == "NASDAQ:LEAD"
    return {k: v for k, v in secs.items()}


def test_leaders():
    from breadth import leaders as LD
    themes = [{"theme": "A", "strength": 90.0}, {"theme": "B", "strength": 20.0}]
    subs = [{"theme": "SA", "strength": 80.0}]
    st = lambda t, rsr, th, sub, off, price=50, stock=True: {"t": t, "rsr": rsr, "themes": th, "sub": sub, "off_hi": off, "price": price, "is_stock": stock}
    stocks = [st("HI", 95, ["B", "A"], "SA", 0.0), st("LO", 95, ["B"], None, -0.30),
              st("ETF", 99, ["A"], "SA", 0.0, stock=False), st("PENNY", 99, ["A"], "SA", 0.0, price=5)]
    r = LD.rank(stocks, themes, subs)
    assert [x["t"] for x in r] == ["HI", "LO"]
    assert r[0]["theme"] == "A" and r[0]["score"] == round(0.4 * 95 + 0.25 * 90 + 0.15 * 80 + 0.2 * 100, 1)
    assert r[1]["sub_str"] == 50.0 and LD.high_score(-0.30) == 0.0 and LD.high_score(-0.10) == 60.0


def test_trade_setups():
    from breadth import levels as LV, tradesetups as TS
    # monthly peaks: pivot highs and the all-time high
    rows = [("2021-01", 50), ("2021-02", 80), ("2021-03", 100), ("2021-04", 70), ("2021-05", 60), ("2021-06", 55),
            ("2021-07", 40), ("2022-01", 30), ("2022-02", 75), ("2022-03", 35), ("2022-04", 30), ("2022-05", 20)]
    lv = LV.peaks_from_monthly(rows)
    assert lv["ath"] == 100 and ["2021-03", 100] in lv["peaks"] and ["2022-02", 75] in lv["peaks"]
    # Yahoo chart JSON parses into the same structure
    js = {"chart": {"result": [{"timestamp": [1609459200, 1612137600], "indicators": {"quote": [{"high": [10.0, 12.5]}]}}]}}
    assert LV.parse_chart(js)["ath"] == 12.5
    themes = [{"theme": "Hot", "strength": 95.0, "s_rank": 1, "s_r_m4": 2},
              {"theme": "Rising", "strength": 70.0, "s_rank": 10, "s_r_m4": 30}]
    subs = [{"theme": "HotSub", "strength": 90.0, "s_rank": 1, "s_r_m4": 1}]
    base = {"is_stock": True, "name": "", "tier": "B", "rs_nh": False, "tight": 1.5, "rsr5": 2}
    stocks = [
        {**base, "t": "ATHX", "price": 100.0, "rsr": 97, "themes": ["Hot"], "sub": "HotSub", "off_hi": -0.01, "e21": 0.05, "e50": 0.1, "adr": 4.0, "vdry": 1.0},
        {**base, "t": "FAR", "price": 100.0, "rsr": 97, "themes": ["Hot"], "sub": "HotSub", "off_hi": -0.01, "e21": 0.05, "e50": 0.1, "adr": 4.0, "vdry": 1.0},
        {**base, "t": "PB", "price": 50.0, "rsr": 90, "themes": ["Hot"], "sub": None, "off_hi": -0.10, "e21": 0.01, "e50": 0.05, "adr": 4.0, "vdry": 0.8},
        {**base, "t": "ROT", "price": 30.0, "rsr": 85, "themes": ["Rising"], "sub": None, "off_hi": -0.06, "e21": 0.03, "e50": 0.05, "adr": 3.0, "vdry": 1.0},
        {**base, "t": "COIL", "price": 40.0, "rsr": 95, "themes": ["Hot"], "sub": None, "off_hi": -0.12, "e21": 0.05, "e50": 0.2, "adr": 6.0, "vdry": 1.0},
        {**base, "t": "CHEAP", "price": 8.0, "rsr": 99, "themes": ["Hot"], "sub": "HotSub", "off_hi": -0.01, "e21": 0.05, "e50": 0.1, "adr": 4.0, "vdry": 1.0},
    ]
    levels = {"FAR": {"ath": 150.0, "peaks": [["2021-03", 150.0]]}, "COIL": {"ath": 90.0, "peaks": [["2021-03", 90.0], ["2022-02", 50.0]]}}
    out = TS.build(stocks, themes, subs, kq={"basing": [{"t": "COIL", "leg": 120, "rng10": 2.0, "pivot": 41.0}],
                                             "extended": [{"t": "RUN", "price": 50, "leg": 200, "ext": 2.5}]},
                   lists={"bursts": [{"t": "PB", "lynch": 5}]}, levels=levels, vcp={"ROT": {"pivot": 31, "stop": 29, "r10": 0.05}})
    top = {s["key"]: s["top"] for s in out["setups"]}
    assert top["ath"] == ["ATHX"], top          # FAR's real ATH is 50% away; CHEAP is under $10
    assert top["pullback"] == ["PB"] and top["rotation"] == ["ROT"] and top["kq"] == ["COIL"] and top["vcp"] == ["ROT"], top
    assert out["rows"]["COIL"]["htf"] and out["kq_ondeck"][0]["t"] == "RUN" and out["rows"]["ROT"]["hits"] == 2
    assert "htf" in out["rows"]["COIL"]["tags"] and "burst" in out["rows"]["PB"]["tags"]
    df = pd.DataFrame({"i": range(40), "t": ["X"] * 40, "fwd_next": [0.05] * 20 + [-0.01] * 20,
                       "tag_rs99": [True] * 20 + [False] * 20, "tag_ep": [False] * 40})
    ts = TS.tag_stats(df)
    assert ts["rs99"]["diff"] == 0.06 and ts["rs99"]["n"] == 20 and ts["ep"]["n"] == 0
    r = out["rows"]
    assert r["PB"]["hits"] == 2 and "burst" in r["PB"]["angles"]
    assert r["COIL"]["mag"] == round(40 / 0.88, 2) and r["COIL"]["mag_kind"] == "52-wk high"
    assert r["ATHX"]["ath_ok"] is False


def test_setup_review(tmp_path=None):
    import json, tempfile
    from datetime import date
    from pathlib import Path
    from breadth import config, review
    old = config.DATA_DIR
    config.DATA_DIR = Path(tmp_path or tempfile.mkdtemp())
    try:
        (config.DATA_DIR / "setups_review.json").write_text(json.dumps(
            {"date": "2026-10-11", "regime": "mixed", "top_themes": ["A", "B", "C", "D", "E"]}))
        br = pd.DataFrame({"ratio5": [1.0, 0.8, 0.7, 0.6], "ratio10": [1.1, 0.9, 0.9, 0.8]})
        setups = [{"key": "ath", "name": "ATH Magnet", "count": 0}, {"key": "pullback", "name": "Leader Pullback", "count": 4}]
        td = {"date": "2026-10-14", "themes": [{"theme": x, "strength": 90 - i} for i, x in enumerate("AXYZE")],
              "trade_setups": {"setups": setups},
              "trade_bt": {"setups": {"ath": {"weak": {"n": 20, "avg_r": -0.2}}}, "recent": {"pullback": {"n": 12, "avg_r": -0.3}}}}
        for d in ("2026-10-12", "2026-10-13"):
            review.record_counts(d, setups)
        out = review.evaluate(td, br, today=date(2026, 10, 14))
        kinds = {r["kind"] for r in out["reasons"]}
        assert out["flag"] and kinds == {"regime", "dry", "slump", "leaders"}, out["reasons"]
        # calm market, same leaders, recent review -> no flag
        br2 = pd.DataFrame({"ratio5": [1.1] * 3, "ratio10": [1.1] * 3})
        td2 = {**td, "themes": [{"theme": x, "strength": 90 - i} for i, x in enumerate("ABCDE")],
               "trade_setups": {"setups": [{"key": "ath", "name": "ATH Magnet", "count": 5}]}, "trade_bt": None}
        assert not review.evaluate(td2, br2, today=date(2026, 10, 15))["flag"]
    finally:
        config.DATA_DIR = old


def test_playbook():
    from breadth import playbook as PB
    st = lambda r, n=30: {"mixed": {"n": n, "avg_r": r, "win": 0.5}, "thrust": {"n": n, "avg_r": -r, "win": 0.5}, "all": {"n": n, "avg_r": r}}
    td = {"trade_bt": {"setups": {"ath": st(0.05), "pullback": st(0.30), "rotation": st(-0.10), "kq": st(0.40, n=5)},
                       "recent": {"pullback": {"n": 12, "avg_r": -0.2}}, "base": {"mixed": {"n": 99, "avg_r": 0.1}}, "days": {"thrust": 25}},
          "setup_stats": {"bursts": st(0.20), "anticipation": st(-0.05), "eps": st(-0.30)},
          "trade_setups": {"setups": [{"key": "ath", "count": 3}, {"key": "pullback", "count": 0}]},
          "lists": {"bursts": [{"lynch": 5}, {"lynch": 3}], "counts": {"anticipation": 2, "eps": 1}}}
    rows = PB.rank(td, "mixed")
    v = {r["key"]: r["verdict"] for r in rows}
    assert [r["key"] for r in rows][:3] == ["pullback", "bursts", "ath"], rows
    assert v == {"pullback": "Focus", "bursts": "Focus", "ath": "Selective", "kq": "Unproven", "vcp": "Unproven",
                 "rotation": "Avoid", "anticipation": "Avoid", "eps": "Avoid"}
    p = next(r for r in rows if r["key"] == "pullback")
    assert "cooling lately" in p["why"] and "none qualify today" in p["why"]
    assert next(r for r in rows if r["key"] == "bursts")["today"] == 1
    assert PB.rank(td, "thrust")[0]["key"] == "eps"   # signs flip in the thrust bucket of this fixture


def test_picks():
    from breadth import playbook as PB, ledger, config
    import tempfile
    from pathlib import Path
    pb = {"state": "mixed", "label": "Mixed breadth", "rows": [
        {"key": "ath", "verdict": "Selective", "avg_r": 0.1, "n": 100},
        {"key": "rotation", "verdict": "Focus", "avg_r": 0.3, "n": 100},
        {"key": "pullback", "verdict": "Focus", "avg_r": 0.2, "n": 100},
        {"key": "kq", "verdict": "Focus", "avg_r": 0.5, "n": 100}]}
    row = lambda t, sub, rs, d60=0.1, **k: {"t": t, "name": t, "price": 100.0, "adr": 4.0, "rsr": rs, "grp": 90, "sub": sub,
                                            "d60": d60, "hits": 1, "mag": 110.0, "mag_pct": 0.1, "mag_adr": 2.5, "mag_kind": "ATH",
                                            "ath": 101.0, "ath_pct": 0.01, "ath_ok": True, "e21": 0.02, **k}
    td = {"trade_setups": {"setups": [{"key": "ath", "name": "ATH Magnet", "top": ["A1"]},
                                      {"key": "rotation", "name": "Rotation Rookie", "top": ["R1", "R2"]},
                                      {"key": "pullback", "name": "Leader Pullback", "top": ["P1"]},
                                      {"key": "kq", "name": "Qullamaggie Flag", "top": ["K1", "K2"]}],
                           "rows": {"A1": row("A1", "S1", 99), "R1": row("R1", "S2", 95, 0.2), "R2": row("R2", "S2", 95, 0.5),
                                    "P1": row("P1", "S3", 90), "K1": row("K1", "S9", 99, kq_pivot=110.0, kq_leg=120),
                                    "K2": row("K2", "S10", 98, kq_pivot=102.0, kq_leg=95)}}}
    out = PB.picks(td, pb)
    # K1's trigger is 2.5 ADRs away -> watch list; K2 (trigger 0.5 ADR) is actionable and has the top RS;
    # Selective A1 is skipped while 2+ Focus picks are actionable; RS ties go to the bigger 60-day gain
    assert [c["t"] for c in out] == ["K2", "R2"], [c["t"] for c in out]
    assert out[0]["entry_type"] == "trigger" and out[1]["entry_type"] == "open"
    assert [w["t"] for w in pb["pick_watch"]] == ["K1"] and "K1" not in pb["pick_cands"]
    old = config.DATA_DIR
    config.DATA_DIR = Path(tempfile.mkdtemp())
    try:
        dates = pd.bdate_range("2026-01-05", periods=8)
        def bar(t, k):
            c = 110.0 if (t == "R2" and k >= 5) else 100.0
            h = 103.0 if (t == "K2" and k == 1) else 101.0
            return {"o": 100.0, "h": h, "l": 99.5, "c": c}
        bars = pd.DataFrame([{"date": d, "ticker": t, **bar(t, k)} for k, d in enumerate(dates) for t in ("R2", "P1", "R1", "K2")])
        ledger.record("2026-01-05", out, pb["pick_cands"])
        df = ledger.settle(bars)
        r = df[df.t == "R2"].iloc[0]
        assert r["status"] == "closed" and abs(r["ret"] - 0.10) < 1e-9 and r["entry"] == 100.0
        k2 = df[df.t == "K2"].iloc[0]
        assert k2["status"] == "closed" and abs(k2["entry"] - 102.102) < 1e-6   # filled at the trigger
        # a trigger that never trades means no fill
        ledger.record("2026-01-06", [{**out[0], "trigger": 150.0}], ["K2"])
        df = ledger.settle(bars)
        assert df[df.date == "2026-01-06"].iloc[0]["status"] == "no fill"
        sm = ledger.summary(bars)
        assert sm["n"] == 2 and sm["no_fill"] == 1
        card = sm["card"]   # scorecard: by setup / breadth state, results in R
        assert card["all"]["n"] == 2 and set(card["by_setup"]) == {"kq", "rotation"}
        assert card["by_setup"]["rotation"]["avg_r"] > 0 and "unknown" in card["by_regime"]
    finally:
        config.DATA_DIR = old

def test_strength_fast_matches():
    """The vectorized group strength must give exactly the per-day numbers."""
    from breadth import strength as S2
    rng = np.random.default_rng(3)
    dates = pd.bdate_range("2025-01-01", periods=140)
    cols = [f"T{k}" for k in range(30)] + ["SPY"]
    close = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0, 0.02, (140, 31)), axis=0)), index=dates, columns=cols)
    close.iloc[100:, 3] = np.nan                       # a delisted name
    close.iloc[:50, 7] = np.nan                        # a late listing
    ema21 = close.ewm(span=21, adjust=False, min_periods=21).mean()
    ema50 = close.ewm(span=50, adjust=False, min_periods=50).mean()
    ratings = pd.DataFrame(rng.integers(1, 99, (140, 31)).astype(float), index=dates, columns=cols)
    mem = {"A": cols[:6], "B": cols[5:14], "C": ["T3", "T7", "ZZZ"], "D": cols[14:30]}
    rows = list(range(95, 140))
    fast = S2.group_inputs_many(close, ema21, ema50, ratings, mem, rows, close["SPY"])
    spy = close["SPY"]
    for i in rows:
        sr = {n: float(spy.iloc[i] / spy.iloc[i - n] - 1) for n, _ in S2.STR_HORIZONS if i - n >= 0}
        a = S2.group_inputs(close, ema21, ema50, ratings.loc[dates[i]], mem, i, sr).astype(float)
        b = fast[i].astype(float).loc[a.index, a.columns]
        assert np.allclose(a.values, b.values, equal_nan=True, atol=0, rtol=0), i
        assert (S2.strength_scores(a) == S2.strength_scores(b)).all()
    return f"{len(rows)} days"


def test_macro_strip():
    from breadth import macro
    def chart(vals, start="2026-09-01"):
        ds = pd.bdate_range(start, periods=len(vals))
        ts = [int(pd.Timestamp(d).tz_localize("America/New_York").timestamp()) for d in ds]
        return {"chart": {"result": [{"meta": {"gmtoffset": -14400}, "timestamp": ts,
                                      "indicators": {"quote": [{"close": vals}]}}]}}
    rows = macro.parse_chart(chart([70.0, None, 72.0, 75.0]))
    assert [r[0] for r in rows] == ["2026-09-01", "2026-09-03", "2026-09-04"] and rows[-1][1] == 75.0
    n = 30
    cl = macro.parse_chart(chart([80.0] * (n - 1) + [88.0]))
    rb = macro.parse_chart(chart([2.5] * n)); ho = macro.parse_chart(chart([3.0] * n))
    tnx = macro.parse_chart(chart([4.0] * (n - 1) + [4.25]))
    cache = {"crude": {"rows": cl}, "gasoline": {"rows": rb}, "diesel": {"rows": ho}, "tnx": {"rows": tnx}}
    last = pd.Timestamp(cl[-1][0])
    bars = pd.DataFrame([{"date": d, "ticker": t, "c": 50.0 + k} for k, d in enumerate(pd.bdate_range(end=last, periods=n))
                         for t in ("GLD", "AAPL")])
    out = {m["key"]: m for m in macro.build(bars, cache)}
    assert out["crude"]["src"] == "futures" and abs(out["crude"]["d1"] - 0.10) < 1e-9
    # 3-2-1 crack: (2*2.5*42 + 3.0*42 - 3*88) / 3 = 24.0 on the last day
    assert abs(out["crack"]["last"] - 24.0) < 1e-9 and out["crack"]["src"] == "derived"
    assert abs(out["tnx"]["d1"] - 0.25) < 1e-9                 # yields change in points, shown as bp
    assert out["gold"]["src"] == "ETF GLD"                       # no futures cached -> ETF fallback
    assert "natgas" not in out                                    # no futures, no ETF in bars -> skipped
    stale = macro.build(bars.assign(date=bars["date"] + pd.Timedelta(days=30)), cache)
    assert "crude" not in {m["key"] for m in stale}               # stale futures and no USO -> dropped
    return f"{len(out)} tiles"


def test_rotation_ideas():
    from breadth import rotation
    rng = np.random.default_rng(5)
    dates = pd.bdate_range("2025-01-01", periods=160)
    groups = {"Up": [f"U{k}" for k in range(4)], "Down": [f"D{k}" for k in range(4)],
              **{f"N{g}": [f"N{g}{k}" for k in range(4)] for g in range(6)}}
    drift = {"Up": 0.006, "Down": -0.004}
    rows = []
    for g, tick in groups.items():
        for t in tick:
            p = 50 * np.exp(np.cumsum(rng.normal(drift.get(g, 0.0), 0.01, len(dates))))
            rows += [{"date": d, "ticker": t, "o": v, "h": v * 1.01, "l": v * 0.99, "c": v, "v": 1e6} for d, v in zip(dates, p)]
    rows += [{"date": d, "ticker": "SPY", "o": 100.0, "h": 101.0, "l": 99.0, "c": 100.0 + k * 0.01, "v": 1e6} for k, d in enumerate(dates)]
    bars = pd.DataFrame(rows)
    last = bars[bars.date == dates[-1]].set_index("ticker")["c"]
    stocks = [{"t": t, "name": t, "sub": g, "price": float(last[t]), "adr": 4.0, "e21": 0.02 + 0.01 * k, "rsr": 90,
               "off_hi": -0.02} for g, tick in groups.items() for k, t in enumerate(tick)]
    td = {"subthemes": [{"theme": g, "group": "Test", "members": tick, "strength": 50, "s_rank": 1} for g, tick in groups.items()],
          "stocks": stocks, "playbook": {"state": "mixed"}}
    out = rotation.build(bars, td)
    names = [i["group"] for i in out["ideas"]]
    assert names[0] == "Up" and "Down" not in names, names       # strongest relative move first
    idea = out["ideas"][0]
    assert idea["stocks"][0]["t"] == "U0" and idea["stocks"][0]["zone"] == "near 21 EMA"   # least stretched first
    p0 = idea["stocks"][0]
    assert p0["trigger"] >= p0["price"] and abs(p0["stop"] - p0["trigger"] * 0.96) < 0.02
    assert "Down" in [a["group"] for a in out["avoid"]]
    assert out["bt"]["lead"]["all"]["n"] > 0 and out["state_key"] == "mixed"
    fl = {r["g"]: r for r in out["flow"]["rows"]}                  # money flow tiers
    assert fl["Up"]["tier"] in ("confirmed", "steady") and fl["Down"]["tier"] == "outflow", (fl["Up"]["tier"], fl["Down"]["tier"])
    assert fl["Up"]["x"] > 100 and fl["Down"]["x"] < 100 and len(fl["Up"]["tail"]) == out["flow"]["tail_days"]
    assert out["flow"]["stock_group"]["U0"] == "Up" and "confirmed" in out["flow"]["evidence"]
    json_ok = __import__("json").dumps(out)
    return f"{len(out['ideas'])} idea, {len(out['avoid'])} avoid"


def test_record_volume():
    from breadth import hve
    dates = pd.bdate_range("2025-01-01", periods=300)
    rows = []
    for k, d in enumerate(dates):
        for t, base in (("REC", 1e6), ("FLAT", 1e6), ("SPY", 5e7)):
            v = base * (1 + 0.1 * np.sin(k))
            if t == "REC" and k == 297:
                v = 9e6                                   # record 2 sessions before the end
            if t == "REC" and k == 298:
                v = 9.5e6                                 # and again the next day
            c = 30.0 + (3.0 if t == "REC" and k >= 297 else 0.0)
            rows.append({"date": d, "ticker": t, "o": c, "h": c * 1.02, "l": c * 0.98, "c": c, "v": v})
    adj = pd.DataFrame(rows)
    assert hve.candidates(adj, {"REC", "FLAT"}) == ["REC"]
    from breadth import strength as S2
    out = hve.screen(S2.wide_all(adj), None, {"REC", "FLAT"}, {"REC": "Record Co"}, cache={})
    assert out["count"] == 1 and len(out["rows"]) == 1
    r = out["rows"][0]
    assert r["t"] == "REC" and r["date"] == dates[298].strftime("%Y-%m-%d") and r["ago"] == 1 and r["also"]
    assert r["ever"] is None and r["dow"] == dates[298].strftime("%a")
    js = {"chart": {"result": [{"meta": {"gmtoffset": 0}, "timestamp": [1262390400, 1262476800, 1700000000],
                                "indicators": {"quote": [{"volume": [5e6, 2e7, 1e6]}]}}]}}
    months = hve.parse_months(js)
    assert months["2010-01"][0] == 20000000
    cache = {"REC": {"months": months, "first": "2010-01-02"}}
    assert hve.ever_check(cache, "REC", "2025-01-01", 9.5e6) == ("not ever", "2010-01-03")
    assert hve.ever_check(cache, "REC", "2025-01-01", 3e7)[0] == "ever"
    assert "profile" in r
    base = {"chg": 0.05, "gap": 0.01, "x50": 5, "vs_prev": 1.2}
    assert hve.profile({**base, "gap": 0.12}, 30e6, 4, -0.05, 0.1) == "spike"
    assert hve.profile(base, 30e6, 4, -0.05, 0.1) == "pullback"
    assert hve.profile(base, 3e6, 4, -0.05, 0.1) == "other" and hve.profile({**base, "chg": -0.02}, 30e6, 4, -0.05, 0.1) == "down"
    cc = np.array([10, 15, 14, 13, 12.5, 12.0]); hh = cc * 1.02; ll = cc * 0.98
    assert hve.short_status(cc, hh, ll, 1, 2)["state"] == "wait"
    st = hve.short_status(cc, hh, ll, 1, 5)              # day 4 closes below the record-day low (14.7)
    assert st["state"] == "triggered" and st["entry"] == 12.5 and st["stop"] == round(15 * 1.02, 2)
    return "ok"


def test_intraday_sheet_rows():
    from breadth import intraday
    old = config.DATA_DIR
    config.DATA_DIR = Path(__file__).resolve().parent.parent / "data"   # the real member list
    try:
        _check_sheet_rows(intraday)
    finally:
        config.DATA_DIR = old


def _check_sheet_rows(intraday):
    rows = intraday.sheet_rows()
    keys = [r[0] for r in rows]
    assert len(keys) == len(set(keys))
    assert keys[:len(intraday.PULSE)] == list(intraday.PULSE)
    flags = {r[0]: r[1] for r in rows}
    assert flags.get("AAPL") == 1 and flags.get("GOOG") == 0 and flags.get("SPY") == 0
    assert all(k in flags for k in intraday.SECTOR_ETFS)
    p = intraday.payload()
    assert len(p["members"]["SPX"]) > 490 and len(p["members"]["NDX"]) > 95


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            out = fn()
            print("ok ", name, out or "")
