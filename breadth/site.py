"""Builds docs/index.html (served by GitHub Pages) with the data embedded,
so the page is a single self-contained file that also opens locally."""
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from . import config, metrics

TEMPLATE = Path(__file__).with_name("template.html")


def _clean(v):
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if hasattr(v, "item"):
        v = v.item()
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
    return round(v, 2) if isinstance(v, float) else v


def payload(history, theme_data=None, kq_data=None, macro_data=None):
    full = history.copy()
    # Short averages for the "breakout trend" chart, computed over the full
    # history so the visible window is never blank at its start.
    full["up4_avg20"] = full["up4"].rolling(20).mean()
    full["dn4_avg20"] = full["dn4"].rolling(20).mean()
    extra = ["up4_avg20", "dn4_avg20"]
    # Chart window: every fully computed day (capped), so you can scroll back.
    comp_idx = full.index[full["complete"]]
    df = full.loc[comp_idx].tail(config.DASHBOARD_DAYS) if len(comp_idx) else full.tail(120)
    rows = []
    for d, r in df.iterrows():
        rows.append({"date": d.strftime("%Y-%m-%d"),
                     **{c: _clean(r.get(c)) for c in metrics.METRIC_COLS + extra}})
    # Percentile thresholds from full history for cell shading.
    comp = history[history["complete"]]
    scale = {}
    for c in metrics.METRIC_COLS:
        s = comp[c].dropna()
        if len(s) >= 10:
            scale[c] = [_clean(float(s.quantile(q))) for q in (0.1, 0.5, 0.9)]
    return {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "history_days": int(history["complete"].sum()),
        "regime": metrics.classify(history),
        "events": metrics.events(history),
        "percentiles": metrics.percentiles(history),
        "scale": scale,
        "thresholds": {"oversold": config.T2108_OVERSOLD,
                       "overbought": config.T2108_OVERBOUGHT,
                       "strong_ratio": config.STRONG_RATIO},
        "rows": rows,
        "themes": theme_data,
        "kq": kq_data,
        "repo": config.REPO_URL,
        "live_url": config.LIVE_CSV_URL,
        "pos_url": config.POSITIONS_CSV_URL, "pos_edit": config.POSITIONS_EDIT_URL,
        "intraday": _intraday(),
        "macro": macro_data,
    }


def _intraday():
    try:
        from . import intraday
        return intraday.payload()
    except Exception:
        return None


def embed(data):
    """JSON for the inline <script>: every "<" becomes \\u003c (JSON only has "<" inside strings, so this is exact),
    so no text (e.g. from an agent) containing "<!--" or "</script" can break out of the script block."""
    return json.dumps(data, separators=(",", ":")).replace("<", "\\u003c")


def build(history, theme_data=None, kq_data=None, macro_data=None):
    config.DOCS_DIR.mkdir(parents=True, exist_ok=True)
    data = payload(history, theme_data, kq_data, macro_data)
    blob = embed(data)
    html = TEMPLATE.read_text().replace("/*__DATA__*/null", blob)
    (config.DOCS_DIR / "index.html").write_text(html)
    (config.DOCS_DIR / "data.json").write_text(json.dumps(data, separators=(",", ":")))
    history.to_csv(config.DOCS_DIR / "breadth.csv", float_format="%.4f")
    (config.DOCS_DIR / ".nojekyll").touch()
    try:   # v2 page at /v2/ from the same payload (Oct 28 2026); never blocks the v1 page
        from . import v2site
        v2site.build(data)
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("v2 page failed: %s", e)
