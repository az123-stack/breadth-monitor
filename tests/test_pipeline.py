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
    assert v == {"pullback": "Focus", "bursts": "Focus", "ath": "Selective", "kq": "Unproven", "vcp": "Unproven", "round": "Unproven", "box": "Unproven", "spring": "Unproven",
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


def test_new_highs_lows():
    n = 300
    closes = {"UP": [10 + 0.05 * i for i in range(n)], "DN": [40 - 0.05 * i for i in range(n)],
              "FLAT": [20.0 + (0.5 if i % 2 else 0) for i in range(n)]}
    vols = {t: [200000 + (i % 3) for i in range(n)] for t in closes}
    bars = make_bars(closes, vols)
    m = metrics.compute(bars)
    assert m["nh"].iloc[:251].isna().all() and m["nh"].iloc[-1] == 1 and m["nl"].iloc[-1] == 1
    assert m["near_hi"].iloc[-1] == 2 and abs(m["pct_near"].iloc[-1] - 200 / 3) < 1e-6      # UP and FLAT within 3%
    # a blank fresh value never erases a stored one (the 52-week window needs a year of bars)
    hist = m.copy()
    fresh = m.copy(); fresh.loc[fresh.index[260], "nh"] = np.nan
    merged = metrics.merge(hist, fresh)
    assert merged.loc[fresh.index[260], "nh"] == hist.loc[fresh.index[260], "nh"]
    return "ok"


def test_thrust_watch():
    from breadth import intraday
    old = config.DATA_DIR
    config.DATA_DIR = Path(__file__).resolve().parent.parent / "data"      # real index member list
    try:
        tick = [r[0] for r in intraday.load_members()["SPX"][:40]]
        n = 120
        rng = np.random.default_rng(2)
        closes = {t: list(50 * np.cumprod(1 + rng.normal(0, 0.02, n))) for t in tick}
        for t in tick[:30]:
            closes[t][-1] = closes[t][-2] * 1.06                       # a broad up-4% day at the end
        bars = make_bars(closes, {t: [200000] * n for t in tick})
        hist = metrics.compute(bars)
        w = intraday.thrust_watch(bars, hist, set(tick))
        assert w["n"] == 40 and 30 <= w["last"]["live"] <= 33          # 30 forced + any random 4% moves
        assert w["pace"] == int(np.ceil(intraday.THRUST_K * w["avg40"])) and w["close"] <= w["pace"]
        assert set(w["setup"]) >= {"met", "t2108_min"}
    finally:
        config.DATA_DIR = old
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


def test_russell_holdings():
    import tempfile, shutil, csv as _csv
    import pandas as pd
    from breadth import intraday, russell
    sample = ("\ufeffiShares Russell 2000 ETF\nFund Holdings as of,\"Oct 12, 2026\"\nInception Date,\"May 22, 2000\"\n\n"
              "Ticker,Name,Sector,Asset Class,Market Value,Weight (%),Notional Value,Quantity,Price,Location,Exchange,Currency,FX Rate,Market Currency,Accrual Date\n"
              '"AAA","A CO","Health Care","Equity","3,000.00","0.36","1,000","10","100","United States","NASDAQ","USD","1.00","USD","-"\n'
              '"MOG A","MOOG A","Industrials","Equity","1,000.00","0.31","900","9","100","United States","NYSE","USD","1.00","USD","-"\n'
              '"-","PRIVATE","Health Care","Equity","1.31","0.00","1","1","0","United States","NO MARKET (E.G. UNLISTED)","USD","1.00","USD","-"\n'
              '"RTYZ6","FUT","Cash and/or Derivatives","Futures","0","0.00","0","1","1","-","Chicago Mercantile Exchange","USD","1.00","USD","-"\n'
              '"USD","USD CASH","Cash and/or Derivatives","Cash","-44.00","-0.06","-44","-44","100","United States","-","USD","1.00","USD","-"\n')
    rows, asof = russell.parse(sample)
    assert [r["ticker"] for r in rows] == ["AAA", "MOG.A"] and asof == "2026-10-12"
    assert rows[0]["exchange"] == "NASDAQ" and rows[1]["exchange"] == "NYSE" and rows[0]["mv"] == 3000
    old = config.DATA_DIR
    real = Path(__file__).resolve().parent.parent / "data"
    with tempfile.TemporaryDirectory() as d:
        for f in ["index_members.csv", "themes.csv", "subthemes.csv"]:
            if (real / f).exists():
                shutil.copy(real / f, Path(d) / f)
        config.DATA_DIR = Path(d)
        try:
            with open(russell.path(), "w", newline="") as f:
                w = _csv.writer(f); w.writerow(["ticker", "mv", "sector", "exchange", "asof"])
                w.writerow(["AAA", 3000, "Health Care", "NASDAQ", "2026-10-12"]); w.writerow(["AAPL", 1000, "Tech", "NASDAQ", "2026-10-12"])
            flags = {r[0]: (r[1], r[2]) for r in intraday.sheet_rows()}
            assert flags["AAA"] == (2, "NASDAQ:AAA") and flags["AAPL"][0] == 1   # already listed rows keep their flag
            w0, _ = russell.weights()
            assert abs(w0["AAA"] - 75) < 1e-6
            bars = pd.DataFrame({"date": pd.to_datetime(["2026-10-12", "2026-10-13"] * 2), "ticker": ["AAA", "AAA", "AAPL", "AAPL"],
                                 "c": [10, 10, 10, 20]})
            w1, wd = russell.weights(bars)                  # AAPL doubled since the file date: 3000 vs 2000
            assert abs(w1["AAA"] - 60) < 1e-6 and wd == "2026-10-13"
            p = intraday.payload()
            assert p["members"]["R2K"][0] == ["AAA", "Health Care"] and p["r2k_asof"] == "2026-10-12" and p["r2k_stale"] == russell.STALE_DAYS
        finally:
            config.DATA_DIR = old
            intraday.set_bars(None)


def test_macrofit():
    """A stock built to fall 2% per +10bp in yields gets a real (t >= 2) rate sensitivity; noise gets none;
    the tailwind has the right sign; nothing uses data after the measured day."""
    from breadth import macrofit as MF
    rng = np.random.default_rng(7)
    n = 200
    dates = pd.bdate_range("2026-01-01", periods=n)
    spy = rng.normal(0, 0.01, n); dy = rng.normal(0, 0.05, n); oil = rng.normal(0, 0.02, n)
    rate_stock = 1.0 * spy - 0.20 * dy + rng.normal(0, 0.005, n)          # -0.2 per 1pt = -2% per 10bp
    noise = rng.normal(0, 0.02, n)
    px = lambda r: 100 * np.cumprod(1 + r)
    rows = []
    for t, r in (("SPY", spy), ("RATE", rate_stock), ("NOIS", noise)):
        rows += [{"date": d, "ticker": t, "c": v} for d, v in zip(dates, px(r))]
    bars = pd.DataFrame(rows)
    tnx = 4 + np.cumsum(dy); crude = 80 * np.cumprod(1 + oil); dxy = np.full(n, 100.0)
    mc = {k: {"rows": [[d.strftime("%Y-%m-%d"), float(v)] for d, v in zip(dates, s_)]}
          for k, s_ in (("tnx", tnx), ("crude", crude), ("dxy", dxy))}
    out = MF.build(bars, mc, ["RATE", "NOIS"])
    r, z = out["stocks"]["RATE"], out["stocks"]["NOIS"]
    assert r["t"]["tnx"] <= -2 and -2.4 < r["sens"]["tnx"] < -1.6, r
    assert not z["words"] or all("10-yr" not in w for w in z["words"])
    moved = tnx[-1] - tnx[-6]
    assert (r["tail5"] > 0) == (moved < 0)                                  # falling yields help a rate-sensitive stock
    # no look-ahead: research() at day i must equal build() on data cut at day i
    i = 150
    sig = pd.DataFrame({"date": [dates[i]], "t": ["RATE"], "fwd_next": [0.0]})
    a = MF.research(sig, bars, mc)["tail5"].iloc[0]
    cut = bars[bars["date"] <= dates[i]]
    mc_cut = {k: {"rows": [x for x in v["rows"] if x[0] <= dates[i].strftime("%Y-%m-%d")]} for k, v in mc.items()}
    b = MF.build(cut, mc_cut, ["RATE"])["stocks"]["RATE"]["tail5"]
    assert abs(a - b) < 0.02, (a, b)


def test_decision_cards(tmp_path=None):
    """Cards carry every layer; unproven layers never change the Top 2; stale agent files are ignored;
    agent JSON is validated; the log settles next-open to 5-sessions-later close."""
    import tempfile, json as _json
    from breadth import decision as DC, agentfiles as AF
    assert DC.sessions_until("2026-10-15", "2026-10-19") == 2 and DC.sessions_until("2026-10-15", "2026-10-12") == -3
    old_d, old_docs = config.DATA_DIR, config.DOCS_DIR
    with tempfile.TemporaryDirectory() as d:
        config.DATA_DIR = Path(d); config.DOCS_DIR = Path(d) / "docs"
        try:
            (config.DOCS_DIR / "agent").mkdir(parents=True)
            T = {"date": "2026-10-15",
                 "playbook": {"state": "thrust", "label": "Post-thrust",
                              "rows": [{"key": "rotation", "name": "Rotation Rookie", "verdict": "Focus", "avg_r": 0.3, "n": 400}],
                              "picks": [{"t": "AAA", "setup": "rotation", "rsr": 95, "sub": "G1", "plan": {"entry": "x"}},
                                        {"t": "BBB", "setup": "rotation", "rsr": 91, "sub": "G2"}],
                              "pick_watch": [], "pick_cands": ["AAA", "BBB", "CCC"]},
                 "trade_setups": {"rows": {"AAA": {"setups": ["rotation"], "rsr": 95, "sub": "G1", "sub_str": 90, "off_hi": -0.02, "adr": 4},
                                           "CCC": {"setups": [], "rsr": 60, "sub": "G3", "sub_str": 30}}},
                 "stocks": [], "rotation": {"flow": {"stock_group": {}, "rows": [{"g": "G3", "tier": "outflow"}]}, "ignition": {"rows": []}}}
            before = _json.dumps(T["playbook"], sort_keys=True)
            # stale catalysts (older date) must be ignored; fresh macro brief used
            (config.DOCS_DIR / "agent" / "catalysts.json").write_text(_json.dumps({"for_date": "2026-10-14", "stocks": {"AAA": {"why": "old", "direction": "positive", "quality": "strong", "sources": ["https://x.y"]}}}))
            (config.DOCS_DIR / "agent" / "macro_brief.json").write_text(_json.dumps({"for_date": "2026-10-15", "headline": "h", "risk": "high",
                "events": [{"date": "2026-10-19", "name": "CPI", "impact": "high"}], "sources": ["https://x.y"]}))
            dec = DC.build(T, None, {}, "Breadth thrust")
            assert _json.dumps(T["playbook"], sort_keys=True) == before          # information only: nothing re-ranked
            roles = [c["role"] for c in dec["cards"]]
            assert roles[:2] == ["pick1", "pick2"] and len(dec["cards"]) == 3   # de-duplicated
            a = dec["cards"][0]
            names = [l["name"] for l in a["layers"]]
            assert names == ["Market", "Group", "Setup", "Macro fit", "Calendar", "Catalyst", "Macro brief"]
            L = {l["name"]: l for l in a["layers"]}
            assert L["Catalyst"]["state"] == "unknown"                          # stale file ignored
            assert "CPI" in L["Calendar"]["text"] and L["Macro brief"]["state"] == "bad"
            assert L["Macro fit"]["proven"] is False and L["Market"]["proven"] is True
            c = {l["name"]: l for l in dec["cards"][2]["layers"]}
            assert c["Group"]["state"] == "bad" and c["Setup"]["state"] == "bad"
            # validation
            good = {"for_date": "2026-10-15", "stocks": {"aaa": {"why": "beat", "direction": "positive", "quality": "strong",
                    "earnings_date": "2026-10-20", "sources": ["https://news.example/a"]}, "BBB": {"why": "no source"}}}
            v = AF.validate("catalysts", good)
            assert list(v["stocks"]) == ["AAA"]                                # no source -> dropped
            for bad in ({"stocks": {}}, {"for_date": "2026-10-15", "stocks": {"A": {"sources": []}}}):
                try:
                    AF.validate("catalysts", bad); assert False
                except ValueError:
                    pass
            try:
                AF.validate("macro_brief", {"for_date": "2026-10-15", "headline": "h", "risk": "extreme", "sources": ["https://a.b"]}); assert False
            except ValueError:
                pass
            # log + settle: entry next open, exit 5th close after
            DC.record(dec)
            dates = pd.bdate_range("2026-10-13", periods=12)
            rows = []
            for k, dd in enumerate(dates):
                for t, base in (("AAA", 10.0), ("BBB", 20.0), ("CCC", 5.0), ("SPY", 100.0)):
                    rows.append({"date": dd, "ticker": t, "o": base + k, "c": base + k + 0.5})
            df = DC.settle(pd.DataFrame(rows))
            r = df[df["t"] == "AAA"].iloc[0]
            # card date 10-15 (k=2) -> entry open 10-16 (k=3) = 13; exit close 5 sessions after entry (k=8) = 18.5,
            # the same window as the pick ledger and the backtest
            assert r["status"] == "closed" and abs(r["entry"] - 13) < 1e-9 and abs(r["exit"] - 18.5) < 1e-9
            # malformed agent files never break the cards (each case must still give 3 full cards)
            bad_files = [[], None, "x", {"for_date": "2026-10-15", "stocks": ["AAA"]},
                         {"for_date": "2026-10-15", "stocks": {"AAA": "beat", "BBB": None}},
                         {"for_date": "2026-99-99", "stocks": {"AAA": {"why": "x"}}},
                         {"for_date": "2026-10-15", "stocks": {"AAA": {"why": "x", "red_flags": "dilution", "earnings_date": "soon"}}}]
            for bf in bad_files:
                (config.DOCS_DIR / "agent" / "catalysts.json").write_text(_json.dumps(bf))
                (config.DOCS_DIR / "agent" / "macro_brief.json").write_text(_json.dumps({"for_date": "2026-10-15", "events": "CPI", "headline": "h"}))
                dd = DC.build(T, None, {}, "x")
                assert dd and len(dd["cards"]) == 3 and all(len(c["layers"]) == 7 for c in dd["cards"]), bf
            (config.DOCS_DIR / "agent" / "catalysts.json").write_text("{not json")
            assert len(DC.build(T, None, {}, "x")["cards"]) == 3
            # a string red flag is one flag, not one per character; impossible dates are rejected
            v = AF.validate("catalysts", {"for_date": "2026-10-15", "stocks": {"AAA": {"why": "x", "red_flags": "dilution",
                            "earnings_date": "2026-02-30", "sources": "https://a.b/c"}}})
            assert v["stocks"]["AAA"]["red_flags"] == ["dilution"] and v["stocks"]["AAA"]["earnings_date"] is None
            assert v["stocks"]["AAA"]["sources"] == ["https://a.b/c"]
            for bad_date in ("2026-99-99", "2026-02-30", "soon"):
                try:
                    AF.validate("catalysts", {"for_date": bad_date, "stocks": {"AAA": {"sources": ["https://a.b"]}}}); assert False
                except ValueError:
                    pass
            v = AF.validate("catalysts", {"for_date": "2026-10-15", "stocks": {"AAA": {"why": "<!--<script>x", "sources": ["https://a.b"]}}})
            assert "<" not in v["stocks"]["AAA"]["why"]
            # holidays: Thanksgiving is not a session
            assert DC.sessions_until("2026-11-25", "2026-11-27") == 1
        finally:
            config.DATA_DIR, config.DOCS_DIR = old_d, old_docs


def test_page_blob_escaping():
    """Text containing <!-- or </script> can't break the page script: every '<' is escaped in the embedded JSON,
    and the browser's JSON/JS parser still reads back the exact text."""
    import json as _json
    from breadth import site
    data = {"themes": {"note": "<!--<script>alert(1)</script> a<b"}}
    blob = site.embed(data)
    assert "<" not in blob
    assert _json.loads(blob) == data


def test_decision_log_evidence():
    """Forward tests only compare rows where the layer was actually checked."""
    import tempfile
    from breadth import layers, decision as DC
    old = config.DATA_DIR
    with tempfile.TemporaryDirectory() as d:
        config.DATA_DIR = Path(d)
        try:
            rows = []
            for k, day in enumerate(pd.bdate_range("2026-08-03", periods=30)):
                for t, cd, fl, r in (("A", "positive", "", 0.03), ("B", "negative", "x", -0.02), ("C", None, None, 0.5)):
                    rows.append({"date": day.strftime("%Y-%m-%d"), "t": t, "cat_dir": cd, "red_flags": fl, "fwd5": r,
                                 "spy5": 0.0, "status": "closed", "support": 3, "warn": 0})
            pd.DataFrame(rows).reindex(columns=DC.LOG_COLS).to_csv(Path(d) / "decision_log.csv", index=False)
            ev = layers.study_log()
            c = ev["catalyst_positive"]
            assert c["n_good"] == 30 and c["n_bad"] == 30 and abs(c["avg_good"] - 0.03) < 1e-9   # C (unchecked, +50%) excluded
            assert ev["red_flags"]["n_good"] == 30 and ev["earnings_in_hold"]["n_good"] == 0
        finally:
            config.DATA_DIR = old


def test_box_range_and_trap():
    """A level touched 3 times over months is found when the close breaks it, and a slide 1.5+ ADR back
    inside before any bounce marks the breakout failed (the HPE case)."""
    import numpy as np
    from breadth import boxes as BX
    n = 220
    rng = np.random.default_rng(3)
    c = 50 + rng.normal(0, 0.4, n).cumsum() * 0.2
    c = np.clip(c, 44, 58)
    for p in (40, 90, 140):                       # three touches of $60
        c[p - 3:p + 4] = [57, 58.5, 59.5, 60, 59.5, 58.5, 57]
    c[200:] = np.linspace(61.5, 66, 20)             # break above, run
    h, l = c * 1.01, c * 0.99
    v = np.full(n, 1e6)
    adr = np.full(n, 2.0)
    prev10 = pd.Series(h).rolling(10).max().shift(1).to_numpy()
    ev = BX._range_breakouts(h, l, c, v, adr, 60, n - 1, prev10)
    assert ev and abs(ev[0][1]["top"] - 60.6) < 1.0 and ev[0][1]["touches"] >= 3, ev[:1]
    bi, b = ev[0]
    c2 = np.r_[c[:bi + 6], np.linspace(c[bi + 5], 55, 6)]   # fall straight back through the line
    w = BX.retest_walk(c2 * 1.01, c2 * 0.99, c2, b, bi, len(c2) - 1, 2.0)
    assert w["state"] == "failed" and w.get("bounce") is None, w


def test_washout_thrust():
    """A thrust after an 8%+ SPY pullback with T2108 <= 25 is 'deep'; a shallow one is not."""
    from breadth import washout
    n = 80
    spy = pd.Series([100.0] * 50 + list(np.linspace(100, 90, 15)) + [91.0] * 15)   # -10% pullback
    t2108 = pd.Series([50.0] * 60 + [18.0] * 10 + [40.0] * 10)
    i = 69
    pull, tlo, deep = washout._event_stats(i, spy, t2108)
    assert deep and abs(pull - (-0.10)) < 1e-9 and tlo == 18.0, (pull, tlo, deep)
    pull, tlo, deep = washout._event_stats(i, spy.clip(lower=96.0), t2108)    # only -4%
    assert not deep
    # basket: highest-beta names with RS >= 80 come first, low RS excluded
    idx = pd.bdate_range("2025-01-02", periods=n)
    rng = np.random.default_rng(0)
    m = pd.Series(rng.normal(0, 0.01, n), index=idx)
    r = pd.DataFrame({"SPY": m, "HI": 3 * m, "MID": 1.5 * m, "LOWRS": 4 * m}, index=idx)
    rs = pd.DataFrame({"SPY": 50.0, "HI": 95.0, "MID": 85.0, "LOWRS": 40.0}, index=idx)
    trad = pd.DataFrame(True, index=idx, columns=r.columns); trad["SPY"] = False
    b = washout.basket(n - 1, None, r, m, rs, trad)
    assert [t for t, _ in b] == ["HI", "MID"] and abs(b[0][1] - 3) < 1e-6, b


def test_volume_tilt():
    """Up-movers on heavier relative volume than down-movers -> positive tilt; the reverse -> negative."""
    from breadth import vtilt
    n, k = 140, 40
    rng = np.random.default_rng(1)
    rets = rng.normal(0, 0.02, (n, k))
    closes = {f"S{j}": list(50 * np.cumprod(1 + rets[:, j])) for j in range(k)}

    def vols(sign):   # last 15 days: stocks moving with `sign` trade 2x normal volume
        out = {}
        for j in range(k):
            v = [300000.0] * n
            for i in range(n - 15, n):
                if np.sign(rets[i, j]) == sign:
                    v[i] = 600000.0
            out[f"S{j}"] = v
        return out
    up = metrics.compute(make_bars(closes, vols(1)))
    dn = metrics.compute(make_bars(closes, vols(-1)))
    assert up["vtilt10"].iloc[-1] > 30 and dn["vtilt10"].iloc[-1] < -30, (up["vtilt10"].iloc[-1], dn["vtilt10"].iloc[-1])
    assert up["vtilt10"].iloc[:59].isna().all()
    # who won the close: closing at the high everywhere -> +1; falling stocks at the high count as absorbed
    hb = make_bars(closes, vols(1)); hb["h"] = hb["c"]; hb["l"] = hb["c"] * 0.97
    m = metrics.compute(hb)
    assert abs(m["clv_all"].iloc[-1] - 1) < 1e-9 and m["fade"].iloc[-1] == 0, m[["clv_all", "absorb", "fade"]].tail(2)
    assert m["absorb"].dropna().iloc[-1] == 100
    spy = make_bars({"SPY": list(np.linspace(100, 120, n))}, {"SPY": [1e6] * n})
    out = vtilt.build(dn, spy)
    assert out["tier"] == "low" and out["pct"] <= 10 and set(out["bt"]) == {"post", "other", "all"}, out


def test_nyse_calendar():
    """Holidays come from the exchange's rules (never run out) and match the published NYSE calendar."""
    from breadth import nyse
    from datetime import date as _d
    assert nyse.holidays(2025, 2025) == ["2025-01-01", "2025-01-09", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26",
                                         "2025-06-19", "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25"]
    assert nyse.holidays(2027, 2027)[-1] == "2027-12-24" and "2027-06-18" in nyse.holidays(2027, 2027)   # Sat -> Fri
    assert "2027-12-31" not in nyse.holidays(2027, 2028)          # New Year on a Saturday: no Friday holiday
    assert max(config.MARKET_HOLIDAYS) >= str(_d.today().year + 5)
    assert str(nyse.entry_cutoff("2026-10-16")) == "2026-10-19 09:30:00-04:00"        # Fri card -> Mon open
    assert str(nyse.entry_cutoff("2026-11-25")) == "2026-11-27 09:30:00-05:00"        # skips Thanksgiving


def test_decision_log_no_lookahead():
    """Rows freeze at the entry cutoff (next session's 9:30 ET open); agent data written after it is never logged."""
    import tempfile
    from datetime import datetime, timezone
    from breadth import decision as DC
    old = config.DATA_DIR
    with tempfile.TemporaryDirectory() as d:
        config.DATA_DIR = Path(d)
        try:
            lay = [{"k": "market", "state": "good"}, {"k": "catalyst", "state": "good"}, {"k": "brief", "state": "bad"}]
            def dec(why, written):
                return {"date": "2026-10-16", "written": {"catalysts": written, "macro_brief": written},
                        "cards": [{"layers": lay, "_log": {"date": "2026-10-16", "t": "AAA", "role": "pick1", "catalyst": why,
                                   "cat_dir": "positive", "brief_risk": "high", "support": 2, "warn": 1}}]}
            before = datetime(2026, 10, 19, 11, 0, tzinfo=timezone.utc)     # Mon 7:00 AM ET, before the open
            after = datetime(2026, 10, 19, 14, 0, tzinfo=timezone.utc)      # Mon 10:00 AM ET
            DC.record(dec("first", "2026-10-19T11:05Z"), now=before)
            r = DC.load_log().iloc[0]
            assert r["catalyst"] == "first" and r["support"] == 2
            DC.record(dec("second", "2026-10-19T11:20Z"), now=before)       # still before the open: replaced
            assert DC.load_log().iloc[0]["catalyst"] == "second"
            DC.record(dec("late", "2026-10-19T14:00Z"), now=after)          # after the open: frozen
            assert DC.load_log().iloc[0]["catalyst"] == "second" and len(DC.load_log()) == 1
            # first logged after the cutoff (late update): agent columns blank, agent layers not counted
            (Path(d) / "decision_log.csv").unlink()
            DC.record(dec("late", "2026-10-19T14:00Z"), now=after)
            r = DC.load_log().iloc[0]
            assert pd.isna(r["catalyst"]) and pd.isna(r["brief_risk"]) and r["support"] == 1 and r["warn"] == 0
            # agent file written after the cutoff but logged "before" (clock skew / rerun): still dropped
            (Path(d) / "decision_log.csv").unlink()
            DC.record(dec("late", "2026-10-19T14:00Z"), now=before)
            assert pd.isna(DC.load_log().iloc[0]["catalyst"])
        finally:
            config.DATA_DIR = old


def test_decision_robustness():
    """Odd agent fields can't break the cards or the page; unconfirmed earnings never count as support; a passed
    backtest still needs approval; earnings-only checks don't count as researched; evidence file errors are ignored."""
    import tempfile, json as _json
    from breadth import decision as DC, agentfiles as AF, layers
    old_d, old_docs = config.DATA_DIR, config.DOCS_DIR
    with tempfile.TemporaryDirectory() as d:
        config.DATA_DIR = Path(d); config.DOCS_DIR = Path(d) / "docs"
        try:
            ag = config.DOCS_DIR / "agent"; ag.mkdir(parents=True)
            (ag / "review.json").write_text(_json.dumps({"for_date": "2026-10-15", "summary": 123, "findings": "x"}))
            (ag / "macro_brief.json").write_text(_json.dumps({"for_date": "2026-10-15", "headline": ["a"], "risk": 5,
                "events": [{"date": "2026-10-16", "name": {"x": 1}}]}))
            (ag / "catalysts.json").write_text(_json.dumps({"for_date": "2026-10-15", "stocks": {"AAA": {"why": 7,
                "direction": "positive", "quality": "real", "sources": ["https://a.b"]}}}))
            (Path(d) / "layer_evidence.json").write_text(_json.dumps({"macro_fit": {"passed": True, "tail5": "bad"}}))
            T = {"date": "2026-10-15", "playbook": {"state": "x", "rows": [], "picks": [{"t": "AAA", "setup": "rotation"}],
                 "pick_watch": [], "pick_cands": []}, "trade_setups": {"rows": {}}, "stocks": [],
                 "rotation": {"flow": {}, "ignition": {}}}
            dd = DC.build(T, None, {"stocks": {"AAA": {"words": [], "tail5": 1.0}}}, "x")
            assert dd and dd["review"] is None                    # no usable summary = no review (round 3)
            assert dd["agents"]["brief"] is None                  # no usable risk level = no brief (round 3)
            assert dd["evidence"] == {}                                     # malformed evidence ignored
            L = {l["k"]: l for l in dd["cards"][0]["layers"]}
            assert L["calendar"]["state"] == "unknown"                      # earnings date not confirmed
            assert L["catalyst"]["text"] == "no clear catalyst found"
            # approval gate: a passed backtest alone doesn't color the macro layer
            (Path(d) / "layer_evidence.json").write_text(_json.dumps({"macro_fit": {"passed": True, "signals": 10,
                "tail5": {"t": 3}}}))
            L = {l["k"]: l for l in DC.build(T, None, {"stocks": {"AAA": {"words": [], "tail5": 1.0}}}, "x")["cards"][0]["layers"]}
            assert L["macro"]["state"] == "info" and L["macro"]["proven"] is False and "approval" in L["macro"]["text"]
            # text cleaning
            assert AF._s("w " * 400, 300).endswith("…") and len(AF._s("w " * 400, 300)) <= 300
            # earnings-only rows don't count as researched in the forward news tests
            rows = []
            for day in pd.bdate_range("2026-08-03", periods=25):
                for t, dep, cd, r in (("A", "full", "positive", 0.02), ("B", "full", "none", -0.01), ("C", "earnings_only", "none", 0.9)):
                    rows.append({"date": day.strftime("%Y-%m-%d"), "t": t, "cat_depth": dep, "cat_dir": cd, "red_flags": "",
                                 "fwd5": r, "spy5": 0.0, "status": "closed", "support": 3, "warn": 0})
            pd.DataFrame(rows).reindex(columns=DC.LOG_COLS).to_csv(Path(d) / "decision_log.csv", index=False)
            ev = layers.study_log()
            assert ev["catalyst_positive"]["n_bad"] == 25 and ev["red_flags"]["n_good"] == 50
        finally:
            config.DATA_DIR, config.DOCS_DIR = old_d, old_docs


def test_unproven_layers_cannot_reach_picks():
    """Static guarantee: the modules that choose, rank and log the Top 2 picks never read agent files, layer evidence
    or the decision cards (so no unproven layer can change them). tools/check_info_only.py tests it end to end."""
    import re as _re
    root = Path(__file__).resolve().parent.parent / "breadth"
    for mod in ("playbook.py", "ledger.py", "tradesetups.py", "leaders.py", "themes.py", "strength.py", "rotation.py"):
        src = (root / mod).read_text()
        for bad in ("docs/agent", "layer_evidence", "agentfiles", "macrofit", "decision_log", "from . import decision",
                    "import decision", '"agent"'):
            assert bad not in src, (mod, bad)
    upd = (root / "update.py").read_text()
    assert upd.index("ledger.record(") < upd.index("decision.build(")   # picks are logged before cards are built



def test_agent_tools_stdlib_only():
    """The agents' tools (worklist / schema / publish / status / save) must run with NO installed packages:
    the scheduled tasks and the agent.yml save job don't install anything first."""
    import subprocess
    root = Path(__file__).resolve().parent.parent
    code = f"import sys; sys.path.insert(0, {str(root)!r}); import breadth.agentfiles, breadth.nyse; print('ok')"
    r = subprocess.run([sys.executable, "-I", "-S", "-c", code], capture_output=True, text=True, cwd="/")
    assert r.stdout.strip() == "ok", r.stderr[-500:]



def test_round3_fixes():
    """Corrupt log -> fresh log (backup kept); exit-day earnings flagged; market-wide brief tested over dates;
    halves weigh dates equally; an unusable brief / review counts as missing."""
    import tempfile, json as _json
    from breadth import decision as DC, layers
    old_d, old_docs = config.DATA_DIR, config.DOCS_DIR
    with tempfile.TemporaryDirectory() as d:
        config.DATA_DIR = Path(d); config.DOCS_DIR = Path(d) / "docs"
        try:
            (Path(d) / "decision_log.csv").write_text("")
            assert DC.load_log().empty and (Path(d) / "decision_log.csv.bad").exists()
            ag = config.DOCS_DIR / "agent"; ag.mkdir(parents=True)
            (ag / "macro_brief.json").write_text(_json.dumps({"for_date": "2026-10-16", "headline": "h", "risk": None}))
            (ag / "review.json").write_text(_json.dumps({"for_date": "2026-10-16", "summary": None}))
            assert DC.load_agent("macro_brief", "2026-10-16") == {} and DC.load_agent("review", "2026-10-16") == {}
            # card Fri Oct 16: entry Mon 19, exit close Mon 26 = 6 sessions later -> earnings on the 26th is inside
            (ag / "catalysts.json").write_text(_json.dumps({"for_date": "2026-10-16", "stocks": {"AAA": {
                "why": "x", "direction": "positive", "quality": "real", "earnings_date": "2026-10-26", "sources": ["https://a.b"]}}}))
            T = {"date": "2026-10-16", "playbook": {"rows": [], "picks": [{"t": "AAA"}], "pick_watch": [], "pick_cands": []},
                 "trade_setups": {"rows": {}}, "stocks": [], "rotation": {"flow": {}, "ignition": {}}}
            L = {l["k"]: l for l in DC.build(T, None, {}, "x")["cards"][0]["layers"]}
            assert L["calendar"]["state"] == "bad", L["calendar"]
            # market-wide brief test: different dates, Welch over dates (the paired test would always be empty)
            rows = []
            for k, day in enumerate(pd.bdate_range("2026-06-01", periods=40)):
                risk = "low" if k % 2 else "high"
                for t in ("A", "B"):
                    rows.append({"date": day.strftime("%Y-%m-%d"), "t": t, "brief_risk": risk, "status": "closed",
                                 "fwd5": (0.02 if risk == "low" else -0.01) + (0.001 * (k % 5)), "spy5": 0.0, "support": 3, "warn": 0})
            pd.DataFrame(rows).reindex(columns=DC.LOG_COLS).to_csv(Path(d) / "decision_log.csv", index=False)
            b = layers.study_log()["brief_low_risk"]
            assert b["test"] == "welch over dates" and b["t"] and b["t"] > 2 and b["passed"] and len(b["halves"]) == 2
            # halves weigh dates equally: one date with 100 good rows can't dominate its half
            df = pd.DataFrame({"date": ["2026-01-0%d" % i for i in (1, 1, 2, 2, 3, 3, 4, 4)], "g": [1, 0] * 4,
                               "r": [0.01, 0.0] * 4})
            c = layers.compare(df, df["g"] == 1, df["g"] == 0, ret="r")
            assert c["halves"] == [0.01, 0.01] and c["dates"] == 4
        finally:
            config.DATA_DIR, config.DOCS_DIR = old_d, old_docs



def test_research_ledger():
    """Every finding card and the layer registry validate; only approved/live layers may affect picks;
    the Integrator's plan validates and loads; the digest is stdlib-only."""
    import json as _json, tempfile
    from breadth import research, agentfiles as AF, decision as DC
    saved = config.DATA_DIR
    config.DATA_DIR = config.ROOT / "data"          # the real ledger + registry (earlier tests repoint DATA_DIR)
    try:
        assert research.check() == [], research.check()
        reg = research.load_registry()
        digest = research.digest()
    finally:
        config.DATA_DIR = saved
    assert any(L["id"] == "macro_fit" and L["status"] == "info" for L in reg["layers"])
    bad = {"layers": [{"id": "x", "status": "info", "kind": "code", "affects_picks": True}]}
    assert any("only approved/live" in e for e in research.validate_registry(bad))
    meta, _ = research.parse("---\nid: R-2026-10-20-x\ntitle: t\ndate: 2026-10-20\nstatus: works\nkind: setup\n"
                             "result: r\nintegrated: no\nlayers: [a, b]\n---\nbody")
    assert meta["layers"] == ["a", "b"] and research.validate_card(meta) == []
    assert research.validate_card({**meta, "status": "great"})
    assert "Layer registry" in digest and "R-2026-10-16-macro-fit" in digest
    assert AF.validate("plan", {"for_date": "2026-10-17", "summary": "s",
                                "items": [{"title": "Q", "priority": "3"}]})["items"][0]["priority"] == 3
    plan = {"for_date": "2026-10-17", "summary": "s", "items": [{"title": "A", "verdict": "build", "priority": 2},
            {"title": "B", "verdict": "nonsense", "priority": 1, "cards": "R-x"}, "junk"],
            "new_agents": [{"name": "Earnings reaction agent", "job": "j"}, {"job": "no name"}]}
    v = AF.validate("plan", plan)
    assert [i["title"] for i in v["items"]] == ["B", "A"] and v["items"][0]["verdict"] == "watch"
    assert v["items"][0]["cards"] == ["R-x"] and len(v["new_agents"]) == 1
    try:
        AF.validate("plan", {"for_date": "2026-10-17", "summary": "s", "items": []}); assert False
    except ValueError:
        pass
    old = config.DOCS_DIR
    with tempfile.TemporaryDirectory() as d:
        config.DOCS_DIR = Path(d)
        try:
            (Path(d) / "agent").mkdir()
            (Path(d) / "agent" / "plan.json").write_text(_json.dumps({**v, "items": v["items"] + [7]}))
            p = DC.load_agent("plan", "2026-10-16", max_age=10)
            assert p["summary"] == "s" and len(p["items"]) == 2
        finally:
            config.DOCS_DIR = old


def test_finra_short_share():
    """FINRA pipe file parses (trailer dropped, zero-volume rows dropped); build() tiers the 5-day vs 120-day gap."""
    from breadth import finra
    txt = "Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market\n20261016|AAPL|600|0|1000|Q\n20261016|ZZZ|0|0|0|N\n1234\n"
    p = finra.parse(txt)
    assert list(p.ticker) == ["AAPL"] and p.short.iloc[0] == 600 and p.total.iloc[0] == 1000, p
    n = 200
    idx = pd.bdate_range("2025-01-02", periods=n)
    sr = np.r_[np.full(n - 5, 0.45), np.full(5, 0.50)]
    daily = pd.DataFrame({"sr_spx": sr, "srm_all": 0.5, "n": 2000}, index=idx)
    spy = pd.DataFrame({"date": idx, "o": np.linspace(100, 120, n), "c": np.linspace(100, 120, n)})
    out = finra.build(spy, daily)
    assert out["tier"] == "high" and out["dev"] > 4 and out["s5"] == 50.0, out


def test_strength_on_weakness():
    """Weekly screen: a stock that based around its 50-week EMA (2+ pumps), thrust, rested on the 9/21 and
    broke the box on volume fires a breakout; a nuzzle into the 9 then a close over that week's high is a pop;
    a stock that never based (straight uptrend) never qualifies; weekly bars come out of daily bars correctly."""
    from breadth import sow
    n = 110
    idx = pd.date_range("2024-10-25", periods=n, freq="W-FRI")
    base = list(20 + 2.5 * np.sin(np.arange(84) / 2.0))                      # ~60 weeks around 20: crosses the 50 WEMA
    thrust = list(np.linspace(21, 27, 8))
    rest = [26.6, 26.9, 26.5, 26.8, 27.0, 26.7, 26.9, 27.1, 26.8, 27.0, 26.7, 26.9, 27.0, 26.8]      # black box right above the rising EMAs
    a = np.array(base + thrust + rest, float)
    a = np.r_[a, np.linspace(a[-1], 27.2, n - len(a) - 1), 29.5]            # last week: break out of the box
    trend = np.linspace(10, 40, n)                                           # never under its 50 WEMA
    c = pd.DataFrame({"AAA": a, "UP": trend}, index=idx)
    h, l = c * 1.01, c * 0.99
    v = pd.DataFrame(1e6, index=idx, columns=c.columns); v.iloc[-1] = 3e6
    W = {"o": c, "h": h, "l": l, "c": c, "v": v}
    dvol = pd.DataFrame(50e6, index=idx, columns=c.columns)
    rs = pd.DataFrame(90.0, index=idx, columns=c.columns)
    F = sow.features(W, dvol, None, rs)
    assert bool(F["base"]["AAA"].iloc[-1]) and F["pumps"]["AAA"].iloc[-1] >= 2, (F["pumps"]["AAA"].iloc[-1], F["below"]["AAA"].iloc[-1])
    assert bool(F["breakout"]["AAA"].iloc[-1]), {k: bool(F[k]["AAA"].iloc[-1]) for k in ("stack", "flat50", "anchor", "tight", "brk", "volx")}
    assert not F["qual"]["UP"].any(), "a stock that never based is not this setup"
    # nuzzle week then a pop over its high
    a2 = a.copy(); a2[-2] = 26.6; a2[-1] = 28.0
    c2 = pd.DataFrame({"AAA": a2}, index=idx)
    l2 = c2 * 0.99; l2.iloc[-2] = 26.0
    l2 = c2 * 0.98; l2.iloc[-2] = 26.0                                       # a shallow, orderly dip into the 9 (not a crash)
    F2 = sow.features({"o": c2, "h": c2 * 1.02, "l": l2, "c": c2, "v": v[["AAA"]]}, dvol[["AAA"]], None, rs[["AAA"]])
    assert bool(F2["nuz"]["AAA"].iloc[-2]) and bool(F2["pop"]["AAA"].iloc[-1]), (F2["e9"]["AAA"].iloc[-2], F2["e21"]["AAA"].iloc[-2])
    # the RS floor gates it
    F3 = sow.features(W, dvol, None, rs * 0 + 50)
    assert not F3["breakout"]["AAA"].any()
    # daily -> weekly: Mon..Wed partial week keeps its own row, labelled by its last session
    days = pd.bdate_range("2026-10-05", "2026-10-14")
    dc = pd.DataFrame({"X": np.arange(len(days), dtype=float) + 1}, index=days)
    wd = {"o": dc, "h": dc + 0.5, "l": dc - 0.5, "c": dc, "v": dc * 0 + 10}
    Wk, nd = sow.weekly(wd, ["X"])
    assert list(Wk["c"].index.strftime("%Y-%m-%d")) == ["2026-10-09", "2026-10-14"] and list(nd) == [5, 3]
    assert Wk["h"]["X"].iloc[0] == 5.5 and Wk["l"]["X"].iloc[1] == 5.5 and Wk["v"]["X"].iloc[0] == 50
    assert not sow.complete_weeks(nd, days[-1])[-1]
    # PRIME POSITIONED: after the pumps it holds over the 50 WEMA, 9 over a rising 21, still close to the 50
    b = list(20 + 2.5 * np.sin(np.arange(98) / 2.0))
    hold = list(np.linspace(21.0, 22.6, 12))
    p = np.array(b + hold, float)
    cp = pd.DataFrame({"P": p, "X": p.copy()}, index=idx)
    cp.iloc[-3:, 1] = [30.0, 33.0, 36.0]                                     # same base, but the leg already ran
    spy = pd.Series(100.0, index=idx)
    Wp = {"o": cp, "h": cp * 1.02, "l": cp * 0.98, "c": cp, "v": pd.DataFrame(1e6, index=idx, columns=cp.columns)}
    Fp = sow.features(Wp, pd.DataFrame(50e6, index=idx, columns=cp.columns), None, None, spy)
    assert bool(Fp["prime"]["P"].iloc[-1]), {k: Fp[k]["P"].iloc[-1] for k in ("run", "rs_up", "flat50", "base", "e9", "e21", "e50", "atr")}
    assert not bool(Fp["prime"]["X"].iloc[-1]), "too far above the 50 WEMA: the stage-2 leg already ran"
    Fn = sow.features(Wp, pd.DataFrame(50e6, index=idx, columns=cp.columns), None, None, spy * np.r_[np.ones(n - 13), np.linspace(1, 1.6, 13)])
    assert not bool(Fn["prime"]["P"].iloc[-1]), "RS line falling (SPY doubling) is not prime"


def test_in_play_candidates():
    """Pre-market in-play list: a liquid leader gapping 8%+ with its group is a high-score EP candidate; a thin
    unknown name without steady trading is dropped; a group gapping together with breadth is listed; your pick shows."""
    from breadth import story
    T = {"date": "2026-10-20", "stocks": [
            {"t": "LEAD", "is_stock": True, "adr": 4.0, "v50": 2e6, "price": 50, "rsr": 95, "sub": "G", "off_hi": -0.05},
            {"t": "PEER", "is_stock": True, "adr": 4.0, "v50": 2e6, "price": 30, "rsr": 70, "sub": "G", "off_hi": -0.1},
            {"t": "PEER2", "is_stock": True, "adr": 4.0, "v50": 2e6, "price": 30, "rsr": 60, "sub": "G", "off_hi": -0.1},
            {"t": "MINE", "is_stock": True, "adr": 3.0, "v50": 1e6, "price": 40, "rsr": 90, "sub": "H", "off_hi": -0.02}],
         "subthemes": [{"theme": "G", "members": ["LEAD", "PEER", "PEER2"], "strength": 80, "s_rank": 3}],
         "playbook": {"picks": [{"t": "MINE", "setup_name": "Q-Flag"}], "pick_watch": []}}
    PM = {"date": "2026-10-21", "rows": {"LEAD": [55, 50, 0, "09:00", 20], "PEER": [31.5, 30, 0, "09:00", 10],
                                          "PEER2": [31, 30, 0, "09:00", 10], "MINE": [41, 40, 0, "09:00", 12], "THIN": [9, 8, 0, "07:00", 1]}}
    cat = {"for_date": "2026-10-20", "stocks": {"LEAD": {"quality": "strong", "direction": "positive", "why": "beat and raise", "earnings_date": "2026-10-20", "red_flags": []}}}
    IP = story.in_play(T, PM, cat)
    ts = [r["t"] for r in IP["stocks"]]
    assert ts[0] == "LEAD" and "THIN" not in ts, IP["stocks"]
    w = " ".join(IP["stocks"][0]["why"])
    assert "possible EP" in w and "leader RS 95" in w and "group moving" in w and "catalyst agent: strong positive" in w and "earnings 2026-10-20" in w, w
    assert IP["groups"] and IP["groups"][0]["g"] == "G", IP["groups"]
    assert [r["t"] for r in IP["mine"]] == ["MINE"]


def test_market_health():
    """Leaders = top 10% by RS as of the previous session; a base breakout on volume is counted; a loud close under
    the 20-day low is a breakdown; the 4-weeks-ago leader basket under its 50-day EMA is measured."""
    from breadth import leadership as LD
    n, m = 140, 40
    idx = pd.bdate_range("2026-01-02", periods=n)
    rng = np.random.default_rng(1)
    base = 20 * np.exp(np.cumsum(rng.normal(0, 0.003, (n, m)), axis=0))
    base[:, :4] *= np.linspace(1, 3, n)[:, None]                      # 4 clear leaders (10%)
    c = pd.DataFrame(base, index=idx, columns=[f"S{i}" for i in range(m)])
    c.iloc[-1, 10] = c.iloc[-2, 10] * 1.08                            # S10 breaks out of its flat base on volume
    c.iloc[-1, 11] = c.iloc[-2, 11] * 0.92                            # S11 breaks down on volume
    v = pd.DataFrame(1e6, index=idx, columns=c.columns); v.iloc[-1, 10:12] = 3e6
    c["SPY"] = 500.0; v["SPY"] = 1e8
    w = {"o": c, "h": c * 1.005, "l": c * 0.995, "c": c, "v": v}
    D, F = LD.frames(w, [x for x in c.columns if x != "SPY"])
    Ls = set(F["L"].iloc[-1][F["L"].iloc[-1]].index)
    assert {"S0", "S1", "S2", "S3"} <= Ls and len(Ls) <= 5, Ls          # top 10% of 40 (percentile >= 0.9)
    assert D["bo"].iloc[-1] >= 1 and D["bd"].iloc[-1] >= 1, (D["bo"].iloc[-1], D["bd"].iloc[-1])
    assert 0 <= D["basket"].iloc[-1] <= 100 and D["a50"].iloc[-1] >= 75
    import sys as _sys
    saved = {k: _sys.modules.pop(k) for k in list(_sys.modules) if k == "scipy" or k.startswith("scipy.")}
    _sys.modules["scipy"] = None                                     # GitHub Actions has no scipy: evidence must not need it
    try:
        E = LD.evidence(D, warm=20)
    finally:
        del _sys.modules["scipy"]; _sys.modules.update(saved)
    assert E["n"] > 0                                                # (no ImportError = the guard)


def test_the_trade():
    """The trade: top / bottom fifth of groups on 20 days; a seesaw (winners fall on the losers' best days) reads as
    'gives back'; the ratio state turns over after 3 closes under its 20-day average; evidence runs end to end."""
    from breadth import thetrade as TT
    n, rng = 160, np.random.default_rng(3)
    idx = pd.bdate_range("2026-01-02", periods=n)
    shock = rng.normal(0, 0.02, n)
    R = {f"G{i}": rng.normal(0, 0.01, n) for i in range(10)}
    R["G0"] = 0.004 - 0.6 * shock + rng.normal(0, 0.003, n)          # winner that moves against the loser
    R["G9"] = -0.004 + shock                                         # loser
    I = pd.DataFrame({k: np.cumprod(1 + v) for k, v in R.items()}, index=idx)
    W, L, r20 = TT._split(I, n - 1)
    assert W[0] == "G0" and L[0] == "G9" and 2 <= len(W) <= 3 and 2 <= len(L) <= 3, (W, L)
    Rr = I.pct_change()
    w, l = TT._baskets(Rr, ["G0"], ["G9"], n - 60, n)
    spy = pd.Series(0.0, index=idx)
    cr, ind, nhot, _, _ = TT._read(w, l, spy)
    assert cr < 0 and ind < 0 and nhot >= 3, (cr, ind)
    r = np.r_[np.linspace(1, 1.3, 40), [1.2, 1.15, 1.1]]
    ma = pd.Series(r).rolling(20).mean().values
    assert TT._state(r, ma)[0] == "over" and TT._state(r[:-2], ma[:-2])[0] == "fading" and TT._state(r[:40], ma[:40])[0] == "on"
    D = TT.frames(I, spy)
    E = TT.evidence(D)
    assert E and E["rows"]["all"]["w"]["n"] > 0 and set(E["rows"]) >= {"holds", "gives"}
    nm, sec = TT._side_name(["G0", "G1"], {"G0": "Software", "G1": "Consumer"}, pd.Series({"G0": 0.2, "G1": 0.05}))
    assert nm == "Software" and sec[0]["s"] == "Software"


def test_trade_stories():
    """Trade Stories: validation drops unsourced timeline items and unknown sub-themes, caps open stories, appends a dated
    history entry; the price check compares favoured vs hurt groups (or SPY) from rotation.mhist; the scorecard settles 5 later."""
    from breadth import stories as SS
    dates = [f"2026-09-{d:02d}" for d in range(1, 31)]
    up, dn = [100] * 30, [-100] * 30                                   # +1% / -1% a day
    T = {"subthemes": [{"theme": "Up"}, {"theme": "Down"}],
         "rotation": {"mhist": {"dates": dates, "spy": [0] * 30, "sub": {"Up": [[0] * 30, [0] * 30, up], "Down": [[0] * 30, [0] * 30, dn]}}}}
    s = {"id": "Test Story", "title": "t", "status": "building", "summary": "x", "thesis": {k: "x" for k in SS.THESIS},
         "timeline": [{"date": "2026-09-01", "event": "a", "url": "https://x.com"}, {"date": "2026-09-02", "event": "no link"}],
         "groups": {"long": ["Up", "Nope"], "short": ["Down"]},
         "history": [{"date": "2026-09-10", "status": "building", "long": ["Up"], "short": ["Down"]}]}
    S, probs = SS.validate({"stories": [s]}, T=T, today="2026-09-30")
    st = S["stories"][0]
    assert st["id"] == "test-story" and len(st["timeline"]) == 1 and st["groups"]["long"] == ["Up"], st
    assert any("source link" in p for p in probs) and any("unknown sub-themes" in p for p in probs)
    assert st["history"][-1]["date"] == "2026-09-30" and st["history"][-1]["status"] == "building"
    pc = SS.price_check(T, st)
    assert pc["verdict"] == "agrees" and pc["d5"] > 0.09, pc
    sc = SS.scorecard(T, st)
    assert len(sc) == 1 and sc[0]["edge"] > 0.09, sc
    only_short = SS.price_check(T, {"groups": {"long": [], "short": ["Down"]}})
    assert only_short["verdict"] == "agrees" and "SPY" in only_short["vs"]
    many = {"stories": [dict(s, id=f"s{i}") for i in range(SS.MAX_OPEN + 1)]}
    assert any("open stories" in p for p in SS.validate(many, T=T, today="2026-09-30")[1])


def test_futures_feed_parse():
    """Intraday futures: latest bar of any session vs the previous settle; the 3-2-1 crack uses gasoline + diesel."""
    from breadth import premarket as PMK
    res = {"meta": {"chartPreviousClose": 100.0, "regularMarketPrice": 101.0, "regularMarketTime": 1792675800},
           "timestamp": [1792670000, 1792675800], "indicators": {"quote": [{"close": [100.5, 102.3]}]}}
    v = PMK.parse_live(res, "2026-10-22")
    assert v[0] == 102.3 and v[1] == 100.0 and v[2]
    assert "RB=F" in PMK.FUTURES and "HO=F" in PMK.FUTURES and set(PMK.FUT_LIVE) >= {"CL=F", "RB=F", "HO=F"}
    assert PMK.parse_live({"meta": {}, "timestamp": [], "indicators": {"quote": [{}]}}, "2026-10-22") is None


def test_stair_steps():
    """A group that runs up, pulls back into its 9/21 EMAs together, then lifts: setting up -> stepping up."""
    import numpy as np
    import pandas as pd
    from breadth import stairs
    n, tick = 160, ["AAA", "BBB", "CCC", "DDD", "EEE"]
    dates = pd.bdate_range("2026-01-02", periods=n)
    rng = np.random.default_rng(1)
    base = np.concatenate([np.linspace(20, 40, 120),            # steady climb (21 > 50, 50 rising)
                           np.linspace(40, 44, 20) * 1.0,         # last push higher (stretched above the 21)
                           np.linspace(44, 41.5, 12),             # pull back into the ribbon
                           np.linspace(42.5, 47, 8)])             # lift + break the step
    c = pd.DataFrame({t: base * (1 + 0.002 * rng.standard_normal(n)) for t in tick}, index=dates)
    c["SPY"] = np.linspace(500, 520, n)
    h, l, v = c * 1.006, c * 0.994, pd.DataFrame(2e6, index=dates, columns=c.columns)   # ADR ~1.2%
    S = stairs.frames(c, h, l, v)
    G = stairs.group_frames(c, S, {"Test group": tick})
    setting, stepping, breaks, lifted = stairs.states(G)
    i_set = np.where(setting["Test group"].to_numpy())[0]
    i_step = np.where(stepping["Test group"].to_numpy())[0]
    assert len(i_set) and len(i_step), (len(i_set), len(i_step))
    assert i_set.min() >= 140 and i_step.min() > i_set.min(), (i_set.min(), i_step.min())   # sets up in the pullback, steps up after
    assert S["brk"][tick].iloc[-8:].any().all(), "every stock breaks its step in the last leg"
    ev = stairs.first(stepping)["Test group"]
    assert ev.sum() >= 1 and (ev & ~stepping["Test group"]).sum() == 0
    return f"set up day {i_set.min()}, stepping day {i_step.min()}"


def test_dip_buys():
    """Box / SoW names: a wick under the 21 EMA that closes back over is flagged; a close under is 'under'; sheet rows add them."""
    import numpy as np
    import pandas as pd
    from breadth import dips, intraday
    dates = pd.bdate_range("2026-01-02", periods=60)
    rows = []
    for t, last_low, last_close in (("WIK", 0.80, 1.0), ("UND", 0.98, 0.90), ("OK", 0.995, 1.02)):
        c = np.linspace(80, 120, 60); c[-1] = c[-2] * last_close if t != "OK" else c[-2] * 1.01
        for i, d in enumerate(dates):
            lo = c[i] * 0.99 if i < 59 else c[-2] * last_low
            rows.append({"ticker": t, "date": d, "o": c[i], "h": c[i] * 1.01, "l": min(lo, c[i]), "c": c[i], "v": 1e6})
    adj = pd.DataFrame(rows)
    td = {"boxes": {"live": [{"t": "WIK", "side": "long", "type": "retest_long", "tag": "at", "grade": "A", "rsr": 90},
                             {"t": "ZZZ", "side": "short", "type": "retest_short", "tag": "at"}]},
          "sow": {"rows": [{"t": "UND", "state": "nuzzle", "prime": False, "rsr": 80}, {"t": "OK", "state": "box", "prime": True}]}}
    p = dips.build(adj, td)
    R = {r["t"]: r for r in p["rows"]}
    assert set(R) == {"WIK", "UND", "OK"}, R.keys()          # the short box row is not a dip buy
    assert R["WIK"]["wick21"] and not R["WIK"]["under21"], R["WIK"]
    assert R["UND"]["under9"] and R["UND"]["under21"], R["UND"]
    assert not (R["OK"]["under9"] or R["OK"]["wick9"] or R["OK"]["wick21"]), R["OK"]
    assert p["rows"][0]["t"] == "WIK" and R["WIK"]["box"][0]["grade"] == "A" and R["OK"]["sow"]["prime"]
    assert all("w" in r and {"e9", "p9", "low", "under21", "strip"} <= set(r["w"]) for r in p["rows"]) and "week_done" in p
    sr = intraday.sheet_rows(["WIK"])
    assert any(r[0] == "WIK" and r[1] in (0, 3) for r in sr)
    return f"{p['n_wick']} wicked, {p['n_under']} under"


def test_launch_list():
    """Launch list: a base breakout in a leading sub-theme with a gap day grades A; the same shape alone grades C."""
    from breadth import launch, config
    old_bench, config.BENCHMARK = config.BENCHMARK, "SPY"     # an earlier test points the benchmark at a fake ticker
    days = pd.bdate_range("2025-01-02", periods=420)
    rows = []
    def put(t, c, gap_at=None):
        for i, d in enumerate(days):
            o = c[i - 1] * 1.08 if gap_at is not None and i == gap_at else c[i]
            rows.append({"ticker": t, "date": d, "o": o, "h": max(o, c[i]) * 1.03, "l": min(o, c[i]) * 0.97, "c": c[i], "v": 2e6})
    n = len(days)
    base = np.linspace(20, 18, n - 30)
    run_up = np.linspace(18, 22.5, 30)
    shape = np.concatenate([base, run_up])
    for t in ("UP", "P1", "P2"):
        put(t, shape, gap_at=n - 22)
    put("LONE", shape)
    for k in range(6):                                  # a weak group and filler stocks
        put(f"W{k}", np.linspace(30, 22, n))
    put("SPY", np.full(n, 500.0))
    adj = pd.DataFrame(rows)
    subs = pd.DataFrame({"group": "g", "subtheme": ["Hot"] * 3 + ["Cold"] * 6, "ticker": ["UP", "P1", "P2"] + [f"W{k}" for k in range(6)]})
    uni = ["UP", "P1", "P2", "LONE"] + [f"W{k}" for k in range(6)]
    try:
        p = launch.build(adj, uni, None, {}, None, subthemes=subs, evidence_on=False)
    finally:
        config.BENCHMARK = old_bench
    R = {r["t"]: r for r in p["rows"]}
    assert "UP" in R and "LONE" in R, sorted(R)
    assert R["UP"]["fresh"] and R["UP"]["early"] and R["UP"]["pts"]["group"] and R["UP"]["pts"]["gap"], R["UP"]
    assert R["UP"]["grade"] == "A", R["UP"]
    assert R["UP"]["stage"] == "early" and R["UP"]["vs9"] is not None and R["UP"]["loc"] in ("at9", "near", "up", "far"), R["UP"]
    assert not R["LONE"]["pts"]["group"] and R["LONE"]["grade"] == "C", R["LONE"]
    assert launch.grade(True, 3) == "A" and launch.grade(True, 1) == "B" and launch.grade(False, 4) == "C"
    assert p["rows"][0]["grade"] == "A"
    return f"{len(p['rows'])} rows, UP score {R['UP']['score']}"


def test_launch_picks_ledger():
    """Launch picks: the weekly pick rule picks the leading-group stock, the ledger freezes the week, fills the next open,
    and stops it on a weekly close through the failure line; rows for a week are never rewritten."""
    from breadth import launch, strength
    days = pd.bdate_range("2025-01-02", periods=440)
    n, cut = len(days), 410                     # pick at the week ending near session `cut`, then the stock collapses
    rows = []
    def put(t, c):
        for i, d in enumerate(days):
            rows.append({"ticker": t, "date": d, "o": c[i], "h": c[i] * 1.03, "l": c[i] * 0.97, "c": c[i], "v": 2e6})
    shape = np.concatenate([np.linspace(20, 18, cut - 30), np.linspace(18, 22.5, 30), np.linspace(22.5, 12, n - cut)])
    for t in ("UP", "P1", "P2"):
        put(t, shape)
    for k in range(6):
        put(f"W{k}", np.linspace(30, 22, n))
    put("SPY", np.full(n, 500.0))
    w = strength.wide_all(pd.DataFrame(rows))
    cols = ["UP", "P1", "P2"] + [f"W{k}" for k in range(6)]
    subs = pd.DataFrame({"group": "g", "subtheme": ["Hot"] * 3 + ["Cold"] * 6, "ticker": cols})
    F = launch.frames(w, cols, subs)
    F["week_done"] = True
    wi = int(F["wd"].searchsorted(days[cut - 1], side="right")) - 1
    got = launch.select(F, wi)
    assert got and got[0]["t"] in ("UP", "P1", "P2") and len(got) == 1, got     # one per sub-theme
    p = [{**got[0], "price": 22.0, "e50": float(F["e50"][got[0]["t"]].iat[wi]), "atr": 5.0}]
    df = launch.ledger_record(pd.DataFrame(columns=launch.LCOLS), str(F["wd"][wi].date()), p)
    df2 = launch.ledger_record(df, str(F["wd"][wi].date()), [{**p[0], "t": "W0"}])
    assert len(df2) == 1 and df2["t"].iat[0] == got[0]["t"]                     # a recorded week is frozen
    df = launch.ledger_settle(df, F, w)
    r = df.iloc[0]
    assert r["entry_date"] > str(F["wd"][wi].date()) and r["entry"] > 0, r
    assert r["status"] == "stopped" and r["ret"] < 0 and r["exit_date"], r           # the collapse closes it through the stop line
    s = launch.ledger_summary(df)
    assert s["closed"] == 1 and s["stopped"] == 1 and s["rows"][0]["t"] == r["t"]
    return f"{r['t']} {r['stage']} stopped {r['ret']:+.1%}"


def test_best_setups_flag_and_nuzzle():
    """Best Setups: a 40% leg into a high, then a tight flag just under it, is a high tight flag with the pivot at the high and
    the stop at the flag low; a stock pulling into its daily 9/21 EMAs after a long run is a nuzzle."""
    from breadth import launch, polished, strength
    days = pd.bdate_range("2025-01-02", periods=420)
    n = len(days)
    rows = []
    def put(t, c, rng=0.02):
        for i, d in enumerate(days):
            rows.append({"ticker": t, "date": d, "o": c[i], "h": c[i] * (1 + rng), "l": c[i] * (1 - rng), "c": c[i], "v": 3e6})
    base = np.linspace(20, 18, n - 40)
    flag = np.concatenate([base, np.linspace(18, 26, 30), 25.9 + 0.1 * np.sin(np.arange(10))])        # leg, then a tight flag
    put("FLG", flag, 0.01)
    trend = np.concatenate([np.linspace(10, 30, n - 6), [29.2, 28.6, 28.2, 28.0, 27.9, 27.9]])         # long run, now dipping
    put("NZ", trend)
    for k in range(6):
        put(f"W{k}", np.linspace(30, 22, n))
    put("SPY", np.full(n, 500.0))
    w = strength.wide_all(pd.DataFrame(rows))
    cols = ["FLG", "NZ"] + [f"W{k}" for k in range(6)]
    F = launch.frames(w, cols, pd.DataFrame({"group": "g", "subtheme": ["Hot"] * 2 + ["Cold"] * 6, "ticker": cols}))
    P = polished.frames(w, cols, F)
    i = n - 1
    assert bool(P["flag"]["FLG"].iat[i]), {k: P[k]["FLG"].iat[i] for k in ("leg", "since", "depth")}
    assert abs(P["hh"]["FLG"].iat[i] - w["h"]["FLG"].iloc[-40:].max()) < 1e-9 and P["fl_lo"]["FLG"].iat[i] < P["hh"]["FLG"].iat[i]
    assert bool(P["touch"]["NZ"].iloc[-6:].any()), "NZ never touched its 9/21 ribbon"
    ev = polished.evidence(P, w)
    assert isinstance(ev, dict)
    return f"flag pivot {P['hh']['FLG'].iat[i]:.2f}, NZ touched"


def _sheet_csv(day_mdY, rows=120, stamp10="", stamp11="", anchor=lambda t: ""):
    lines = ["ticker,index,symbol,price,closeyest,open,volume,marketcap,volumeavg,at10,at11,low",
             f"_asof,{day_mdY} 9:00:00,,,,,,,,{stamp10},{stamp11}", f"_spytime,{day_mdY} 12:00:00"]
    for k in range(rows):
        t = f"T{k}"
        lines.append(f"{t},1,{t},{10 + k},{10 + k},{10 + k},1000,,,{anchor(t)},{anchor(t)},")
    return "\n".join(lines) + "\n"


def test_theme_lifecycle():
    """Theme lifecycle: a group climbing with its members becomes ready (stage 3/4, leaders, inflow); BUY waits when breadth is
    weak and turns on when it isn't; stages for past days never change when later days are added (no look-ahead)."""
    from breadth import lifecycle as LC
    days = pd.bdate_range("2025-01-02", periods=260)
    n = len(days)
    rng = np.random.default_rng(7)
    cols, members = {}, {}
    for g, drift in (("Hot", 0.004), ("Flat", 0.0), ("Cold", -0.002), ("Mid", 0.001), ("Dull", 0.0005)):
        members[g] = []
        for k in range(4):
            t = f"{g[:2].upper()}{k}"
            r = drift + rng.normal(0, 0.008, n)
            if g == "Hot":
                r[:120] = rng.normal(0, 0.008, 120)       # forgotten first, then it goes
            cols[t] = 50 * np.cumprod(1 + r)
            members[g].append(t)
    cols["SPY"] = 400 * np.cumprod(1 + rng.normal(0.0003, 0.006, n))
    close = pd.DataFrame(cols, index=days)
    vol = pd.DataFrame(1e6, index=days, columns=close.columns) * (1 + (close.pct_change().fillna(0) > 0))   # heavier on up days
    hist = lambda r10: pd.DataFrame({"ratio5": r10, "ratio10": r10, "complete": True}, index=days)
    G = LC.group_state(close, vol, members, hist(0.8))
    assert bool(G["ready"]["Hot"].iloc[-1]) and int(G["stage"]["Hot"].iloc[-1]) in (3, 4), G["stage"]["Hot"].iloc[-5:]
    assert not bool(G["buy"]["Hot"].iloc[-1])                     # weak breadth: ready, not BUY
    G2 = LC.group_state(close, vol, members, hist(1.6))
    assert bool(G2["buy"]["Hot"].iloc[-1]) and bool(G2["act"].iloc[-1])
    assert not bool(G2["buy"]["Cold"].iloc[-1])
    Gs = LC.group_state(close.iloc[:200], vol.iloc[:200], members, hist(1.6).iloc[:200])
    assert (Gs["stage"].iloc[:200] == G2["stage"].iloc[:200]).all().all()        # no look-ahead
    assert (Gs["buy"].iloc[:200] == G2["buy"].iloc[:200]).all().all()


def test_lineup_live_and_ledger():
    """Lined-up buys: the Python alert pass matches the page's lineupState (run in Node), alerts only BUY-group names in the
    EMAs / over the trigger and never twice, nothing on hold-off days; the live ledger freezes a date, fills on the trigger,
    and stops out at the dip low."""
    import shutil, subprocess, json as _json
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from breadth import lineup, lifecycle as LC
    base = {"g": "Hot", "kind": "buy", "rs": 95, "c": 100.0, "hi": 101.0, "lo": 98.0, "e9": 99.0, "e21": 97.0, "adr": 0.03, "t3": False, "t0": False}
    xs = [dict(base, t="DIP"), dict(base, t="OVR"), dict(base, t="NEAR", e9=97.0, e21=96.0), dict(base, t="FAR", e9=80.0, e21=78.0),
          dict(base, t="RDY", kind="ready")]
    L = {"DIP": {"price": 99.2, "closeyest": 100, "open": 100, "low": 97.5}, "OVR": {"price": 101.5, "closeyest": 100, "open": 100, "low": 98.2},
         "NEAR": {"price": 99.5, "closeyest": 100, "open": 100, "low": 99.4}, "FAR": {"price": 100.5, "closeyest": 100, "open": 100, "low": 100.0},
         "RDY": {"price": 101.5, "closeyest": 100, "open": 100, "low": 98.2}}
    py = {x["t"]: lineup.state(x, L[x["t"]])["st"] for x in xs}
    assert py == {"DIP": "zone", "OVR": "over", "NEAR": "near", "FAR": None, "RDY": "over"}, py
    node = shutil.which("node")
    if node:   # the page's own function gives the same states
        src = (config.ROOT / "breadth" / "template.html").read_text()
        i = src.index("function lineupState(")
        depth, j = 0, src.index("{", i)
        while True:
            depth += src[j] == "{"; depth -= src[j] == "}"; j += 1
            if depth == 0:
                break
        js = f"""const liveActive = () => true; const LV = {_json.dumps(L)};
const liveRow = (t) => {{ const r = LV[t]; return r ? {{ ...r, chg: r.price / r.closeyest - 1 }} : null; }};
{src[i:j]}
console.log(JSON.stringify(Object.fromEntries({_json.dumps(xs)}.map(x => {{ const s = lineupState(x); return [x.t, [s.st, s.loc]]; }}))));"""
        r = subprocess.run([node, "-e", js], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-600:]
        pyl = {x["t"]: [lineup.state(x, L[x["t"]])["st"], lineup.state(x, L[x["t"]])["loc"]] for x in xs}
        assert _json.loads(r.stdout) == pyl, (r.stdout, pyl)
    locs = {x["t"]: lineup.state(x, L[x["t"]])["loc"] for x in xs}
    assert locs["DIP"] == "reclaim9" and locs["FAR"] == "above", locs                                       # wick under the 9 and back
    now = datetime(2026, 10, 27, 11, 0, tzinfo=ZoneInfo("America/New_York"))
    text = "ticker,index,symbol,price,closeyest,open,volume,marketcap,volumeavg,at10,at11,low\n_asof,x\n_spytime,10/27/2026 11:00:00\n" + \
        "\n".join(f"{t},1,{t},{r['price']},{r['closeyest']},{r['open']},1,1,1,,,{r['low']}" for t, r in L.items())
    lc = {"size": "full", "live": xs}
    doc, new = lineup.run(text, lc, {}, now)
    assert sorted((e["t"], e["state"]) for e in new) == [("DIP", "zone"), ("OVR", "over")], new          # ready / near / far: no alert
    doc2, new2 = lineup.run(text, lc, doc, now)
    assert new2 == [] and len(doc2["events"]) == 2                                                       # never twice
    _, new3 = lineup.run(text, {"size": "hold off", "live": xs}, {}, now)
    assert new3 == []                                                                                    # hold-off day: silent
    # ledger: signal on day 0 (dip-day high 101, low 98), fills day 2 at 101, stopped on day 4 under 98
    days = pd.bdate_range("2026-10-01", periods=8)
    px = {"o": [100, 100, 100.5, 101.2, 99, 97, 97, 97], "h": [101, 100.8, 101.6, 102, 99.5, 98, 98, 98],
          "l": [98, 99, 100.2, 100.5, 97.9, 96, 96, 96], "c": [100, 100.5, 101.4, 101, 98.5, 97, 97, 97]}
    w = {k: pd.DataFrame({"ZZ": v, "SPY": [400.0] * 8}, index=days) for k, v in px.items()}
    sig = [dict(base, t="ZZ", f0=True, hi=101.0, lo=98.0)]
    df = LC.ledger_record(pd.DataFrame(columns=LC.LCOLS), str(days[0].date()), sig)
    df = LC.ledger_record(df, str(days[0].date()), sig + [dict(base, t="YY", f0=True)])
    assert len(df) == 1                                                                                  # a recorded date is frozen
    df = LC.ledger_settle(df, w)
    r = df.iloc[0]
    assert r["status"] == "stopped" and r["entry_date"] == str(days[2].date()) and abs(r["entry"] - 101.0) < 1e-9 and r["R"] < 0, r.to_dict()
    tr = LC.tracker(df)
    assert tr["buy"]["closed"] == 1 and tr["buy"]["R"] < 0
    return "states match the page, alerts gated, ledger fills + stops"


def test_anchor_backup_snapshot():
    """Second-half movers backup (Oct 26 2026: the sheet's 10:00 freeze stuck on Oct 13 for two weeks): take() saves a slot
    only inside its window, once a day, only for today's session; check() flags a day with neither source."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from breadth import anchors
    ET = ZoneInfo("America/New_York")
    csv_today = _sheet_csv("10/26/2026")
    d, m = anchors.take(csv_today, datetime(2026, 10, 26, 10, 3, tzinfo=ET))
    assert "saved" in m and d["date"] == "2026-10-26" and len(d["at10"]["rows"]) == 120 and d["at10"]["rows"]["T5"] == [15.0, 1000.0], m
    d2, m2 = anchors.take(csv_today, datetime(2026, 10, 26, 10, 20, tzinfo=ET), doc=d)
    assert "already" in m2 and d2["at10"]["time"].endswith("10:03")
    d3, m3 = anchors.take(csv_today, datetime(2026, 10, 26, 10, 50, tzinfo=ET), doc=d)
    assert "outside" in m3 and "at11" not in d3
    d4, m4 = anchors.take(csv_today, datetime(2026, 10, 26, 11, 2, tzinfo=ET), doc=d)
    assert "saved" in m4 and d4["at10"] and d4["at11"]
    _, m5 = anchors.take(_sheet_csv("10/23/2026"), datetime(2026, 10, 26, 10, 3, tzinfo=ET))
    assert "not today" in m5                                                # stale sheet / holiday: never saves old prices
    d6, _ = anchors.take(csv_today, datetime(2026, 10, 27, 10, 3, tzinfo=ET), doc=d4)
    assert "at10" not in d6 or d6.get("date") != "2026-10-27"               # new day doesn't reuse yesterday's doc
    stuck = _sheet_csv("10/26/2026", stamp10="2026-10-13 20:00", stamp11="2026-10-13 20:00")
    bad = anchors.check(stuck, datetime(2026, 10, 26, 16, 25, tzinfo=ET), {})
    assert bad["ok"] is False and bad["sheet"]["at10"] is False             # the Oct 14-26 failure is caught
    good = anchors.check(stuck, datetime(2026, 10, 26, 16, 25, tzinfo=ET), d4)
    assert good["ok"] and good["backup"]["at10"] and good["backup"]["at11"]
    fresh = _sheet_csv("10/26/2026", stamp10="2026-10-26 10:01", stamp11="2026-10-26 11:01")
    assert anchors.check(fresh, datetime(2026, 10, 26, 16, 25, tzinfo=ET), {})["ok"]
    return "take / check ok"


def test_anchor_page_logic():
    """The page never uses a stale 10:00 / 11:00 snapshot, uses today's sheet freeze when it has one, and falls back to the
    GitHub backup otherwise (runs the page's own parseLiveCSV / resolveAnchors in Node)."""
    import re, shutil, subprocess, json as _json
    node = shutil.which("node")
    if not node:
        return "skipped (no node)"
    src = (config.ROOT / "breadth" / "template.html").read_text()
    def grab(name):
        i = src.index(name)
        depth, j = 0, src.index("{", i)
        while True:
            ch = src[j]
            depth += ch == "{"
            depth -= ch == "}"
            j += 1
            if depth == 0:
                return src[i:j]
    code = "\n".join([grab("function csvSplit("), src[src.index("const liveNum ="):src.index("\n", src.index("const liveNum ="))],
                      grab("function parseLiveCSV("), grab("function parseAnchor("), grab("function resolveAnchors(")])
    old = lambda t: f"{t}|5|9"                                             # undated legacy freeze from another day
    today = lambda t: f"{t}|7|9|2026-10-26"
    cases = {
        "stuck": _sheet_csv("10/26/2026", 60, "2026-10-13 20:00", "2026-10-13 20:00", old),
        "fresh": _sheet_csv("10/26/2026", 60, "2026-10-26 10:01", "2026-10-26 11:01", today),
    }
    backup = {"date": "2026-10-26", "at10": {"time": "2026-10-26 10:03", "rows": {f"T{k}": [3.0, 1] for k in range(60)}}}
    js = code + f"""
const C = {_json.dumps(cases)}, B = {_json.dumps(backup)};
const out = {{}};
for (const [k, txt] of Object.entries(C)) {{
  const a = resolveAnchors(parseLiveCSV(txt), null), b = resolveAnchors(parseLiveCSV(txt), B);
  out[k] = {{ none: [a.anchorSrc, a.anchors, a.rows.T1.at10, a.rows.T1.at11], backup: [b.anchorSrc, b.anchors, b.rows.T1.at10, b.rows.T1.at11] }};
}}
console.log(JSON.stringify(out));"""
    r = subprocess.run([node, "-e", js], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]
    o = _json.loads(r.stdout)
    st = o["stuck"]
    assert st["none"][0] == {"at10": "stale", "at11": "stale"} and st["none"][1] == {} and st["none"][2] is None, st["none"]
    assert st["backup"][0]["at10"] == "backup" and st["backup"][2]["p"] == 3 and st["backup"][0]["at11"] == "stale" and st["backup"][3] is None
    fr = o["fresh"]
    assert fr["backup"][0] == {"at10": "sheet", "at11": "sheet"} and fr["backup"][2]["p"] == 7, fr      # today's sheet freeze wins over the backup
    return "stale dropped, backup used, sheet preferred"


def test_earnings_clusters():
    """Earnings clusters: two members gapping up on heavy volume in one week make an UP cluster, one alone doesn't; the
    story fact sheet adds today's reactions from the close snapshot; reactions for past days never change with later data."""
    from breadth import earnings as EA, story as ST
    days = pd.bdate_range("2025-01-02", periods=120)
    n, rng = len(days), np.random.default_rng(3)
    W = {k: {} for k in ("o", "h", "l", "c", "v")}
    for t in ["A0", "A1", "A2", "A3", "B0", "B1", "B2", "SPY"]:
        c = 50 * np.cumprod(1 + rng.normal(0, 0.01, n))
        o = c * (1 + rng.normal(0, 0.002, n))
        v = np.full(n, 1e6)
        if t in ("A0", "A1"):                       # both report in the last week: gap up 8% on 5x volume, close up 10%
            j = n - 3 if t == "A0" else n - 2
            c[j:] *= 1.10
            o[j] = c[j - 1] * 1.08
            v[j] = 5e6
        if t == "B0":                               # a lone reaction in group B
            j = n - 2
            c[j:] *= 1.10
            o[j] = c[j - 1] * 1.08
            v[j] = 5e6
        for k, x in (("o", o), ("h", np.maximum(o, c) * 1.01), ("l", np.minimum(o, c) * 0.99), ("c", c), ("v", v)):
            W[k][t] = x
    W = {k: pd.DataFrame(v, index=days) for k, v in W.items()}
    mem = {"A": ["A0", "A1", "A2", "A3"], "B": ["B0", "B1", "B2"]}
    F = EA.frames(W)
    CL = EA.clusters(F, mem)
    assert int(CL["A"]["dir"].iloc[-1]) == 1 and int(CL["A"]["n"].iloc[-1]) == 2, CL["A"].iloc[-3:]
    assert int(CL["B"]["dir"].iloc[-1]) == 0
    F2 = EA.frames({k: v.iloc[:-2] for k, v in W.items()})            # no look-ahead
    a, b = F2["react"], F["react"].iloc[:-2]
    assert a.fillna(9).equals(b.fillna(9))
    # fact sheet: B's lone official reaction + a TODAY reaction in B1 from the snapshot -> listed; A listed UP
    T = {"earnings": {"rows": [{"g": "A", "dir": "up", "n": 2, "members": 4, "grp": 0.05, "quiet": 0.01, "next": [],
                                "reports": [{"t": "A0", "date": "2025-06-10", "dir": 1, "gap": 0.08, "move": 0.1, "rvol": 5.0, "conf": True},
                                            {"t": "A1", "date": "2025-06-11", "dir": 1, "gap": 0.08, "move": 0.1, "rvol": 5.0, "conf": False}]},
                               {"g": "B", "dir": "mixed", "n": 1, "members": 3, "grp": 0.03, "quiet": 0.0, "next": [],
                                "reports": [{"t": "B0", "date": "2025-06-11", "dir": 1, "gap": 0.08, "move": 0.1, "rvol": 5.0}]}],
                      "window": ["2025-06-06", "2025-06-12"], "spy": 0.01, "cfg": EA.CFG},
         "stocks": [{"t": "B1", "sub": "B", "v50": 1e6, "adr": 3.0}, {"t": "B2", "sub": "B", "v50": 1e6, "adr": 3.0}]}
    snap = {"B1": {"price": 55.0, "closeyest": 50.0, "open": 54.0, "volume": 4e6}, "B2": {"price": 50.2, "closeyest": 50.0, "open": 50.1, "volume": 1e6}}
    L = "\n".join(ST.earnings_lines(T, "pm", snap))
    assert "**A** · UP" in L and "**B** · UP" in L and "B1 TODAY" in L and "B2" not in L, L
    assert ST.earnings_lines({"earnings": {"rows": []}}, "am") == []
    return f"{len(L.splitlines())} fact lines"


def test_theme_upkeep_reclass():
    """Reclass check finds a misfiled stock, an unclassified leader and a dead ticker; agent proposals validate strictly
    (worklist tickers, known sub-theme names, sources) and only an explicit apply changes the theme files."""
    import json, tempfile
    from breadth import reclass as RC, agentfiles as AF
    rng = np.random.default_rng(7)
    n = 160
    fa, fb = rng.normal(0, 0.02, n), rng.normal(0, 0.02, n)          # two group factors
    closes, vols = {"SPY": list(100 * np.cumprod(1 + rng.normal(0, 0.005, n)))}, {"SPY": [5e7] * n}
    def stock(f, drift=0.0):
        return list(50 * np.cumprod(1 + f + rng.normal(0, 0.004, n) + drift))
    for k in range(4):
        closes[f"A{k}"] = stock(fa); closes[f"B{k}"] = stock(fb)
    closes["MIS"] = stock(fb)                    # filed in A, trades like B
    closes["NEW"] = stock(fa, 0.004)             # strong, in no sub-theme
    closes["DEAD"] = stock(fa)
    for t in closes:
        vols.setdefault(t, [2e6] * n)
    bars = make_bars(closes, vols)
    bars = bars[~((bars["ticker"] == "DEAD") & (bars["date"] > bars["date"].unique()[-8]))]
    subs = pd.DataFrame([{"group": "G", "subtheme": "Alpha", "ticker": t} for t in ["A0", "A1", "A2", "A3", "MIS", "DEAD"]]
                        + [{"group": "G", "subtheme": "Beta", "ticker": f"B{k}"} for k in range(4)])
    themes = pd.DataFrame(columns=["theme", "ticker", "role"])
    universe = set(closes) - {"SPY"}
    old = RC.LOG_FILE, RC.PROPOSALS, RC.SUB_FILE, RC.THEME_FILE
    old_bench, config.BENCHMARK = config.BENCHMARK, "SPY"     # an earlier test points the benchmark at a fake ticker
    tmp = Path(tempfile.mkdtemp())
    try:
        RC.LOG_FILE, RC.PROPOSALS, RC.SUB_FILE, RC.THEME_FILE = tmp / "log.csv", tmp / "p.json", tmp / "s.csv", tmp / "t.csv"
        subs.to_csv(RC.SUB_FILE, index=False)
        pd.DataFrame([{"theme": "T1", "ticker": "A0", "role": "member"}]).to_csv(RC.THEME_FILE, index=False)
        RC.CFG["rs_min"] = 50
        W = RC.build(bars, universe, subs, themes, {})
        RC.CFG["rs_min"] = 80
        poor = {r["t"]: r for r in W["poor_fit"]}
        assert "MIS" in poor and poor["MIS"]["best"][0][0] == "Beta", W["poor_fit"]
        assert not any(r["t"].startswith(("A", "B")) for r in W["poor_fit"]), W["poor_fit"]
        assert [u["t"] for u in W["unclassified"]] == ["NEW"] and W["unclassified"][0]["cand"][0][0] == "Alpha", W["unclassified"]
        assert [s["t"] for s in W["stale"]] == ["DEAD"], W["stale"]
        # validation: unknown sub-theme, off-worklist ticker and source-less moves are dropped; ids follow the order
        raw = {"for_date": "2025-08-01", "summary": "Checked 3.", "checked": 3, "moves": [
            {"t": "MIS", "action": "move", "from": "Alpha", "to": "Beta", "confidence": "high", "why": "Sells B things.", "sources": ["https://x.com/a"]},
            {"t": "NEW", "action": "add", "to": "Nowhere", "confidence": "high", "why": "?", "sources": ["https://x.com/b"]},
            {"t": "NEW", "action": "add", "to": "NEW: G / Gamma", "confidence": "medium", "why": "New niche.", "sources": ["https://x.com/c"]},
            {"t": "ZZZ", "action": "add", "to": "Beta", "confidence": "high", "why": "not on worklist", "sources": ["https://x.com/d"]},
            {"t": "DEAD", "action": "remove", "confidence": "high", "why": "Acquired.", "sources": []}]}
        clean = AF.validate("reclass", raw, {"MIS", "NEW", "DEAD"})
        got = [(m["t"], m["action"], m["to"]) for m in clean["moves"]]
        assert got == [("MIS", "move", "Beta"), ("NEW", "add", "NEW: G / Gamma")], got
        assert [m["id"] for m in clean["moves"]] == [1, 2]
        RC.PROPOSALS.write_text(json.dumps(clean))
        before = RC.SUB_FILE.read_text()
        assert RC.proposals_status()["moves"][0]["status"] == "open"
        assert RC.SUB_FILE.read_text() == before                      # proposals alone change nothing
        lines = RC.apply_moves(["1"], today=date(2025, 8, 2))
        s2 = pd.read_csv(RC.SUB_FILE)
        assert s2.loc[s2["ticker"] == "MIS", "subtheme"].tolist() == ["Beta"] and len(s2) == len(subs), (lines, s2)
        RC.reject(["2"], today=date(2025, 8, 2))
        st = {m["t"]: m["status"] for m in RC.proposals_status()["moves"]}
        assert st == {"MIS": "applied", "NEW": "rejected"}, st
        assert RC.apply_moves(["1"])[0].endswith("already decided")
        W2 = RC.build(bars, universe, pd.read_csv(RC.SUB_FILE), themes, {})   # decided tickers stay off the worklist
        assert "MIS" not in {r["t"] for r in W2["poor_fit"]} and not W2["unclassified"]
    finally:
        RC.LOG_FILE, RC.PROPOSALS, RC.SUB_FILE, RC.THEME_FILE = old
        RC.CFG["rs_min"] = 80
        config.BENCHMARK = old_bench
    return f"poor fit {poor['MIS']['own']} vs {poor['MIS']['best'][0][1]}; {len(lines)} applied"


def test_v2_page_builds():
    """v2 page: payload slims every section, a broken section is skipped (not fatal), and no text can break the script."""
    from breadth import v2site
    D = {"generated": "x", "regime": {"label": "Strong"}, "thresholds": {"oversold": 20, "overbought": 70},
         "rows": [{"date": "2025-06-10", "up4": 300.0, "dn4": 40.0, "t2108": 55.0, "dn_share": 38.0}],
         "themes": {"date": "2025-06-10", "tv": {"AAA": "NYSE:AAA"},
                    "playbook": {"state": "strong", "label": "Strong breadth", "advice": "Press </script><b>", "since": None,
                                 "rows": [{"name": "ATH Magnet", "verdict": "Focus", "avg_r": 0.2, "n": 50}]},
                    "launch": {"picks": [{"t": "AAA", "plan": {"stop": "Weekly close under $9"}}]},
                    "lifecycle": "broken"}}
    S = v2site.slim(D)
    assert S["playbook"]["state"] == "strong" and S["picks"][0]["t"] == "AAA" and "groups" not in S, S.keys()
    assert S["tv"] == {"AAA": "NYSE:AAA"}
    tmp = Path(__import__("tempfile").mkdtemp())
    old = config.DOCS_DIR
    try:
        config.DOCS_DIR = tmp
        v2site.build(D)
        h = (tmp / "v2" / "index.html").read_text()
    finally:
        config.DOCS_DIR = old
    assert h.startswith("<!doctype html>") and "/*__DATA__*/null" not in h and "</script><b>" not in h
    assert h.count("</script>") == 1
    return f"{len(h) // 1024} KB page"



def test_position_refs():
    """My positions: EOD references (close, 10/20 EMA, ADR, high/low) for liquid tickers; illiquid / cheap names left out."""
    import pandas as pd
    from breadth import positions
    d = pd.bdate_range("2026-01-01", periods=60); rows = []
    for t, b, v in [("AAA", 50, 1e6), ("CHEAP", 1, 1e6), ("THIN", 50, 100)]:
        for i, x in enumerate(d):
            c = b * (1 + .01 * i); rows.append(dict(date=x, ticker=t, c=c, h=c * 1.02, l=c * .98, v=v))
    R = positions.refs(pd.DataFrame(rows))
    assert set(R["rows"]) == {"AAA"} and R["date"] == d[-1].strftime("%Y-%m-%d") and len(R["dates"]) == 40
    c, e10, e20, adr, h, l = R["rows"]["AAA"]
    assert c > e10 > e20 and abs(adr - 4.08) < .01 and h > c > l
    return "ok"


def test_group_runners():
    """Groups running together (breadth/runners.py): running / heating / quiet, alerts once then again on +1 ADR (max 3),
    the 5-minute job emits them without breaking lined-up dedupe, and the page's runnersScan (Node) agrees with Python."""
    import shutil, subprocess, json as _json
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from breadth import runners as R, lineup
    stocks = [{"t": t, "is_stock": True, "adr": 5.0, "rsr": rs, "v50": 1e6} for t, rs in
              [("A1", 99), ("A2", 90), ("A3", 80), ("A4", 70), ("B1", 95), ("B2", 85), ("B3", 75), ("B4", 65), ("C1", 50), ("C2", 50), ("C3", 50), ("C4", 50)]]
    subs = [{"theme": "Hot", "members": ["A1", "A2", "A3", "A4"], "strength": 90}, {"theme": "Warm", "members": ["B1", "B2", "B3", "B4"]},
            {"theme": "Cold", "members": ["C1", "C2", "C3", "C4"]}]
    def row(ch, vol, op=None):
        return {"price": 20 * (1 + ch), "closeyest": 20.0, "open": op if op is not None else 20.0, "volume": vol}
    rows = {"SPY": row(0.005, 1e6), "A1": row(0.09, 2e6), "A2": row(0.08, 2e6), "A3": row(0.08, 2e6), "A4": row(0.07, 2e6, op=22.0),
            "B1": row(0.07, 5e4), "B2": row(0.07, 5e4), "B3": row(0.06, 5e4), "B4": row(0.06, 5e4),
            "C1": row(0.01, 2e6), "C2": row(-0.01, 2e6), "C3": row(0.0, 2e6), "C4": row(0.02, 2e6)}
    prof = [[0, 0], [390, 1]]
    G = {g["g"]: g for g in R.scan(rows, subs, stocks, 390, prof)}
    assert G["Hot"]["status"] == "running" and G["Hot"]["strong"] and G["Hot"]["up"] == 4, G["Hot"]           # 1.6 ADRs on 2x volume
    assert [m["t"] for m in G["Hot"]["top"]] == ["A1", "A2", "A3"]                                             # A4 fell under its open
    assert G["Warm"]["status"] == "heating" and not G["Warm"]["checks"]["vol"], G["Warm"]                     # big move, thin volume
    assert G["Cold"]["status"] is None
    e1 = R.alerts(list(G.values()), [], 60)
    assert [e["g"] for e in e1] == ["Hot"] and not e1[0]["again"]
    assert R.alerts(list(G.values()), e1, 60) == []                                                           # once
    assert R.alerts(list(G.values()), [], 5) == []                                                            # not in the first minutes
    wider = dict(G["Hot"], adrs=G["Hot"]["adrs"] + 1.05)
    e2 = R.alerts([wider], e1, 60)
    assert len(e2) == 1 and e2[0]["again"]                                                                    # widened by an ADR
    assert R.alerts([dict(wider, adrs=99)], e1 + e2 + e2, 60) == []                                          # max 3 a day
    title, body = R.text(e1[0])
    assert "Hot" in title and "4/4 up" in body
    # the 5-minute job: group events alongside lined-up events, logged once
    now = datetime(2026, 10, 28, 11, 0, tzinfo=ZoneInfo("America/New_York"))
    text = "ticker,index,symbol,price,closeyest,open,volume,marketcap,volumeavg,at10,at11,low\n_asof,x\n_spytime,10/28/2026 11:00:00\n" + \
        "\n".join(f"{t},1,{t},{r['price']},{r['closeyest']},{r['open']},{r['volume']},1,1,,,{r['open']}" for t, r in rows.items())
    D = {"themes": {"subthemes": subs, "stocks": stocks}, "intraday": {"volume_profile": prof}}
    doc, new = lineup.run(text, {"size": "full", "live": []}, {}, now, D)
    assert [e["g"] for e in new if e.get("type") == "group"] == ["Hot"] and any(g["g"] == "Hot" for g in doc["groups"])
    doc2, new2 = lineup.run(text, {"size": "full", "live": []}, doc, now, D)
    assert new2 == []
    node = shutil.which("node")
    if node:
        src = (config.ROOT / "breadth" / "template.html").read_text()
        i = src.index("const RUN_CFG")
        j = src.index("function runnersCard(")
        js = src[i:j] + f"\nconsole.log(JSON.stringify(runnersScan({_json.dumps(rows)}, {_json.dumps(subs)}, {_json.dumps(stocks)}, 150, [[0,0],[390,1]])" \
             ".map(x => [x.g, x.status, x.strong, Math.round(x.adrs * 1000), x.pace == null ? null : Math.round(x.pace * 1000), x.top.map(m => m.t)])));"
        r = subprocess.run([node, "-e", js], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-600:]
        py = [[x["g"], x["status"], x["strong"], round(x["adrs"] * 1000), None if x["pace"] is None else round(x["pace"] * 1000), [m["t"] for m in x["top"]]]
              for x in R.scan(rows, subs, stocks, 150, prof)]
        assert _json.loads(r.stdout) == py, (r.stdout, py)
    return "running / heating / quiet, alert once + widen, job + page agree"


def test_value_chain():
    """Biotech tab (breadth/valuechain.py): stages ranked by price + dollar flow, entry spots from the EMAs, missing tickers listed."""
    import json as _json, tempfile
    from breadth import valuechain as VC
    days = pd.bdate_range("2026-01-01", periods=120)
    rows = []
    def add(t, path, vol):
        for i, d in enumerate(days):
            c = path(i); rows.append(dict(date=d, ticker=t, o=c, h=c * 1.02, l=c * 0.98, c=c, v=vol(i)))
    add("SPY", lambda i: 100 + 0.05 * i, lambda i: 1e7)
    add("UP1", lambda i: 50 * 1.008 ** i, lambda i: 2e6 * (2 if i > 100 else 1))       # strong, steady trend: near its 21 EMA? no: grinding
    add("UP2", lambda i: 30 * 1.01 ** i if i < 110 else 30 * 1.01 ** 110 * 1.06 ** (i - 110), lambda i: 3e6 * (2 if i > 100 else 1))   # late surge -> extended
    add("DN1", lambda i: 80 * 0.996 ** i, lambda i: 2e6)
    add("DN2", lambda i: 60 * 0.997 ** i, lambda i: 2e6)
    add("XBI", lambda i: 90 + 0.02 * i, lambda i: 5e6)
    adj = pd.DataFrame(rows)
    cfg = {"demand": ["XBI"], "stages": [{"k": "a", "name": "Hot", "desc": "", "tickers": ["UP1", "UP2", "NOPE"]},
                                         {"k": "b", "name": "Cold", "desc": "", "tickers": ["DN1", "DN2"]}]}
    tmp = Path(tempfile.mkdtemp()) / "vc.json"; tmp.write_text(_json.dumps(cfg))
    old, old_bench, config.BENCHMARK = VC.PATH, config.BENCHMARK, "SPY"     # an earlier test points the benchmark at a fake ticker
    try:
        VC.PATH = tmp
        X = VC.build(adj, {"stocks": [{"t": "UP1", "rsr": 95, "name": "Up One"}]})
    finally:
        VC.PATH, config.BENCHMARK = old, old_bench
    st = {s["k"]: s for s in X["stages"]}
    assert X["stages"][0]["k"] == "a" and st["a"]["rank"] == 1 and st["a"]["missing"] == ["NOPE"], X["stages"]
    assert st["a"]["r20"] > 0 > st["b"]["r20"] and st["a"]["above50"] == 1 and st["b"]["above50"] == 0
    assert st["a"]["net20"] > 0 > st["b"]["net20"] and st["a"]["share_chg"] > 0 and len(st["a"]["line"]) == 61
    assert X["stocks"]["UP2"]["spot"] == "extended" and X["stocks"]["DN1"]["spot"] == "broken", {t: s["spot"] for t, s in X["stocks"].items()}
    assert X["stocks"]["UP1"]["rs"] == 95 and X["demand"][0]["t"] == "XBI"
    assert VC.spot(99.5, 99.8, 99.0, 95, 98.5, 0.03) == "pullback" and VC.spot(102, 100, 99, 95, 98.5, 0.03) == "buy"
    return f"{len(X['stocks'])} stocks, hot stage first, spots ok"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            out = fn()
            print("ok ", name, out or "")
