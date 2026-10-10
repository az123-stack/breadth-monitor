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


def payload(history):
    df = history.tail(config.DASHBOARD_DAYS)
    rows = []
    for d, r in df.iterrows():
        rows.append({"date": d.strftime("%Y-%m-%d"),
                     **{c: _clean(r.get(c)) for c in metrics.METRIC_COLS}})
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
        "percentiles": metrics.percentiles(history),
        "scale": scale,
        "thresholds": {"oversold": config.T2108_OVERSOLD,
                       "overbought": config.T2108_OVERBOUGHT,
                       "strong_ratio": config.STRONG_RATIO},
        "rows": rows,
    }


def build(history):
    config.DOCS_DIR.mkdir(parents=True, exist_ok=True)
    data = payload(history)
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.read_text().replace("/*__DATA__*/null", blob)
    (config.DOCS_DIR / "index.html").write_text(html)
    (config.DOCS_DIR / "data.json").write_text(json.dumps(data, indent=1))
    history.to_csv(config.DOCS_DIR / "breadth.csv", float_format="%.4f")
    (config.DOCS_DIR / ".nojekyll").touch()
