"""Leaders: a simple, transparent ranking of the strongest stocks in the theme universe.

Score 0-100 = 40% RS Rating + 25% best theme's Strength + 15% sub-theme's Strength
+ 20% closeness to the 52-week high (at the high = 100, 25%+ below = 0).
Stocks only (no ETFs), price >= $10. The page recomputes the same score in the
browser with live prices (template.html: leadersJS) - keep the two in step.
"""

WEIGHTS = {"rs": 0.40, "theme": 0.25, "sub": 0.15, "high": 0.20}
MIN_PRICE = 10.0
TOP_N = 25
SUB_DEFAULT = 50.0  # stocks without a sub-theme get a neutral sub-theme score


def high_score(off_hi):
    """0% off the high -> 100, 25% or more off -> 0."""
    if off_hi is None:
        return 0.0
    return max(0.0, min(100.0, 100.0 + off_hi * 400.0))


def score_one(s, ts, ss):
    """(score, best theme, its strength, sub-theme strength) for one stock row."""
    best_theme, best = None, None
    for th in s.get("themes") or []:
        v = ts.get(th)
        if v is not None and (best is None or v > best):
            best_theme, best = th, v
    sub = ss.get(s.get("sub"))
    sub = SUB_DEFAULT if sub is None else sub
    score = (WEIGHTS["rs"] * s["rsr"] + WEIGHTS["theme"] * (best or 0)
             + WEIGHTS["sub"] * sub + WEIGHTS["high"] * high_score(s.get("off_hi")))
    return round(score, 1), best_theme, best, sub


def eligible(s):
    return bool(s.get("is_stock")) and s.get("rsr") is not None and (s.get("price") or 0) >= MIN_PRICE


def rank(stocks, themes, subthemes, n=TOP_N):
    ts = {r["theme"]: r.get("strength") for r in themes}
    ss = {r["theme"]: r.get("strength") for r in subthemes}
    out = []
    for s in stocks:
        if not eligible(s):
            continue
        score, best_theme, best, sub = score_one(s, ts, ss)
        out.append({"t": s["t"], "score": score, "rsr": s["rsr"],
                    "theme": best_theme, "theme_str": best, "sub": s.get("sub"), "sub_str": sub,
                    "off_hi": s.get("off_hi")})
    out.sort(key=lambda r: (-r["score"], -r["rsr"], r["t"]))
    return out[:n]
