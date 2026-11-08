"""Tables for the supply-breaks study. Run after study.py: python tools/supply_study/analyze.py"""
import numpy as np
import pandas as pd

E = pd.read_parquet("/tmp/supply_study/events.parquet")
mid = E["date"].sort_values().iloc[len(E) // 2]
print("events", len(E), "| thrust-window share", round(E.thrust.mean(), 2), "| split date", mid.date())


def phases(df, horizon=63):
    f = df[df.obs >= horizon]
    q = lambda s, h: (s.notna() & (s <= h)).mean()
    return dict(n=len(f), retest10=q(f.retest, 10), retest21=q(f.retest, 21), fail21=q(f.fail, 21), fail63=q(f.fail, 63),
                clear21=q(f.clear, 21), clear63=q(f.clear, 63),
                d_retest=f.retest.median(), d_clear=f.clear.median(), d_fail=f.fail.median(),
                clear_after_retest=((f.retest.notna()) & (f.clear.notna()) & (f.clear > f.retest)).sum() / max(1, (f.retest.notna() & (f.fail.isna() | (f.fail > f.retest))).sum()))


def tt(a, b=None):
    a = a.dropna()
    if b is None:
        return round(a.mean() / (a.std(ddof=1) / np.sqrt(len(a))), 1) if len(a) > 2 else np.nan
    b = b.dropna()
    return round((a.mean() - b.mean()) / np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b)), 1) if len(a) > 2 and len(b) > 2 else np.nan


def row(df, name):
    p = phases(df)
    h1, h2 = df[df.date < mid], df[df.date >= mid]
    return dict(group=name, n=len(df), **{k: (round(v, 2) if isinstance(v, float) else v) for k, v in p.items() if k != "n"},
                R_bo=round(df.R_bo.mean(), 2), R_rt=round(df.R_rt.mean(), 2), n_rt=df.R_rt.notna().sum(), t_rt=tt(df.R_rt),
                x21=round(100 * df.x21.mean(), 1), t_x21=tt(df.x21), x63=round(100 * df.x63.mean(), 1),
                rt_h1=round(h1.R_rt.mean(), 2), rt_h2=round(h2.R_rt.mean(), 2), x21_h1=round(100 * h1.x21.mean(), 1), x21_h2=round(100 * h2.x21.mean(), 1))


cuts = {"ALL": E.index == E.index,
        "kind swing": E.kind == "swing", "kind multi-year": E.kind == "multi", "kind broken floor": E.kind == "floor",
        "depth 25-40%": E.depth < 0.40, "depth 40-60%": (E.depth >= 0.40) & (E.depth < 0.60), "depth 60%+": E.depth >= 0.60,
        "age <1y": E.age < 250, "age 1y+ (swing)": (E.age >= 250) & (E.age < 999),
        "break vol <1.5x": E.rv < 1.5, "break vol 1.5-3x": (E.rv >= 1.5) & (E.rv < 3), "break vol 3x+": E.rv >= 3,
        "gapped through": E.gap, "closed through": ~E.gap,
        "close <0.5 ADR over": E.ext < 0.5, "close 0.5-1.5 ADR over": (E.ext >= 0.5) & (E.ext < 1.5), "close 1.5+ ADR over": E.ext >= 1.5,
        "RS top 20%": E.rs >= 0.8, "RS mid": (E.rs >= 0.4) & (E.rs < 0.8), "RS bottom 40%": E.rs < 0.4,
        "group top 20% (60d)": E.g60 >= 0.8, "group bottom 50%": E.g60 < 0.5, "no sub-theme": E.g60.isna(),
        "thrust window": E.thrust, "no thrust": ~E.thrust}
T = pd.DataFrame([row(E[m], k) for k, m in cuts.items()]).set_index("group")
pd.set_option("display.width", 260); pd.set_option("display.max_columns", 40)
print(T[["n", "retest10", "retest21", "fail21", "fail63", "clear21", "clear63", "d_retest", "d_clear", "d_fail", "clear_after_retest"]].to_string())
print(T[["R_bo", "R_rt", "n_rt", "t_rt", "rt_h1", "rt_h2", "x21", "t_x21", "x21_h1", "x21_h2", "x63"]].to_string())
# combos
for name, m in {"thrust + group top 20%": E.thrust & (E.g60 >= 0.8), "thrust + RS top 20%": E.thrust & (E.rs >= 0.8),
                "RS top 20% + group top 20%": (E.rs >= 0.8) & (E.g60 >= 0.8), "vol 1.5x+ & RS top 20%": (E.rv >= 1.5) & (E.rs >= 0.8),
                "multi-year + RS top 20%": (E.kind == "multi") & (E.rs >= 0.8)}.items():
    r = row(E[m], name); print({k: r[k] for k in ("group", "n", "fail21", "clear63", "d_clear", "R_bo", "R_rt", "n_rt", "t_rt", "rt_h1", "rt_h2", "x21", "t_x21")})
# how long the work-off takes: distribution of days to clear, and what happened to names that retested
f = E[E.obs >= 63]
print("days to clear quantiles", f.clear.dropna().quantile([.25, .5, .75]).to_dict(), "| never cleared in 63:", round(f.clear.isna().mean(), 2))
rt = f[f.retest.notna() & (f.fail.isna() | (f.fail > f.retest))]
print("held the retest:", len(rt), "| then cleared within 63", round(rt.clear.notna().mean(), 2), "| failed later", round(rt.fail.notna().mean(), 2))
nort = f[f.retest.isna()]
print("never retested in 63:", len(nort), "share", round(len(nort) / len(f), 2), "| cleared", round(nort.clear.notna().mean(), 2))
# live events: breaks in the last 30 sessions
lv = E[E.d >= E.d.max() - 30].sort_values("date")
print(lv[["t", "date", "kind", "lvl", "depth", "rv", "ext", "rs", "g60", "thrust", "retest", "fail", "clear"]].tail(60).round(2).to_string(index=False))
