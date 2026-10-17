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


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            out = fn()
            print("ok ", name, out or "")
