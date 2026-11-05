"""Statistics for the liquidity-magnet study (PLAN2.md v9.1). `power()` uses only non-outcome columns, plus open-sky / far outcomes
for the correlation and simulation inputs the plan allows; `test()` opens the approaching / stopped-short outcomes.
Deviations from the plan text are printed in the output (search "DEVIATION")."""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "warehouse" / "magnets"
SEED = 7
LOG = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.append(s)


def load():
    F = pd.read_parquet(OUT / "fills.parquet")
    F["fid"] = np.arange(len(F))
    F["aget"] = ""
    for e, g in F.groupby("era"):
        F.loc[g.index, "aget"] = pd.qcut(g["age"].rank(method="first"), 3, labels=["a1", "a2", "a3"]).astype(str)
    F["cell"] = F["month"] + "|" + F["state"].astype(str) + "|" + F["kind"]
    F["mcell"] = F["cell"] + "|" + F["aget"]
    return F


# ------------------------------------------------------------------------------------------------ cluster-robust means
def _cv(x, g):
    d = pd.DataFrame({"x": x - x.mean(), "g": g})
    s = d.groupby("g")["x"].sum()
    G = len(s)
    return (G / (G - 1)) * (s ** 2).sum() / len(x) ** 2 if G > 1 else np.nan


def cmean(x, month, ticker):
    """mean and two-way (month × ticker) cluster-robust t (Cameron–Gelbach–Miller); falls back to month alone if the variance < 0."""
    x = np.asarray(x, float)
    m = x.mean()
    v = _cv(x, month) + _cv(x, ticker) - _cv(x, pd.Series(month).astype(str).values + "|" + pd.Series(ticker).astype(str).values)
    if not (v > 0):
        v = _cv(x, month)
    return m, (m / np.sqrt(v) if v > 0 else np.nan)


# ------------------------------------------------------------------------------------------------------------ matching
def match(T, B, dcol="d_up"):
    """v5/v6 matching: same month × state × kind × age tercile, |Δ d_lh| ≤ 0.5 ADR (widen to 1.0 if < 3), ≥ 3 matches, each baseline fill
    used ≤ 5 times, targets in random order (seed 7), candidates by |Δ d_lh| then date then ticker. Returns {target fid: [baseline fids]}."""
    rng = np.random.default_rng(SEED)
    pool = {k: g.sort_values(["fill_date", "t"]) for k, g in B.groupby("mcell")}
    uses = {}
    out = {}
    order = rng.permutation(T.index.to_numpy())
    for ix in order:
        r = T.loc[ix]
        g = pool.get(r["mcell"])
        if g is None or len(g) < 3:
            continue
        dd = (g["d_lh"] - r["d_lh"]).abs()
        for wdt in (0.5, 1.0):
            cand = g[dd <= wdt].assign(_d=dd[dd <= wdt]).sort_values(["_d", "fill_date", "t"], kind="stable")
            cand = cand[[uses.get(f, 0) < 5 for f in cand["fid"]]]
            if len(cand) >= 3:
                break
        if len(cand) < 3:
            continue
        ids = cand["fid"].tolist()
        for f in ids:
            uses[f] = uses.get(f, 0) + 1
        out[int(r["fid"])] = ids
    return out, uses


def matched_effect(F, M, d_of, tag_of_target=None, mfe="mfe20", shift=0.0):
    """per-target diff = tag(target) − mean(tag of matches at the target's d)."""
    mf = F.set_index("fid")[mfe]
    rows = []
    for tf, ids in M.items():
        d = d_of[tf] + shift
        tt = (mf[tf] >= d) if tag_of_target is None else tag_of_target[tf]
        base = float(np.mean(mf.loc[ids].to_numpy() >= d))
        rows.append((tf, float(tt) - base))
    return pd.DataFrame(rows, columns=["fid", "diff"])


# -------------------------------------------------------------------------------------------------------------- model
def model_ame(F, T, B, dcol, seeds=50):
    """GLM binomial: tag20 ~ approach + B-spline(d; knots 10/50/90th pct of target d) + d_lh + rs + adr + ext + kind + age + month FE.
    Baseline fills take the d of a random target in their cell (fallback month × kind, then month). AME of approach, two-way clusters."""
    import statsmodels.api as sm
    from patsy import dmatrix
    td = T[dcol].to_numpy()
    kn = tuple(np.percentile(td, [10, 50, 90]))
    by_cell = {k: g[dcol].to_numpy() for k, g in T.groupby("cell")}
    T["mk"] = T["month"] + "|" + T["kind"]
    by_mk = {k: g[dcol].to_numpy() for k, g in T.groupby("mk")}
    by_m = {k: g[dcol].to_numpy() for k, g in T.groupby("month")}
    ames, ses, drops = [], [], 0
    for s in range(seeds):
        rng = np.random.default_rng(SEED + s)
        bd = []
        for _, r in B.iterrows():
            arr = by_cell.get(r["cell"])
            if arr is None:
                arr = by_mk.get(r["month"] + "|" + r["kind"])
            if arr is None:
                arr = by_m.get(r["month"])
            bd.append(rng.choice(arr) if arr is not None else np.nan)
        Bx = B.assign(d=bd).dropna(subset=["d"])
        drops = len(B) - len(Bx)
        X = pd.concat([T.assign(d=T[dcol], ap=1), Bx.assign(ap=0)], ignore_index=True)
        X["y"] = (X["mfe20"] >= X["d"]).astype(float)
        X = X.dropna(subset=["ext", "rs", "adr"])
        sp = dmatrix(f"bs(d, knots={kn}, degree=3) - 1", X, return_type="dataframe")
        fe = pd.get_dummies(X["month"], drop_first=True, dtype=float)
        Z = pd.concat([X[["ap", "d_lh", "rs", "adr", "ext", "age"]].astype(float), (X["kind"] == "W").astype(float).rename("kW"),
                       sp.reset_index(drop=True), fe.reset_index(drop=True)], axis=1)
        Z = sm.add_constant(Z, has_constant="add")
        Z = Z.loc[:, Z.std() > 0].assign(const=1.0)
        mod = sm.GLM(X["y"].to_numpy(), Z, family=sm.families.Binomial())
        g2 = np.column_stack([pd.factorize(X["month"])[0], pd.factorize(X["t"])[0]])
        try:
            res = mod.fit(cov_type="cluster", cov_kwds={"groups": g2})
        except Exception:
            res = mod.fit(cov_type="cluster", cov_kwds={"groups": g2[:, 0]})
        Z1, Z0 = Z.copy(), Z.copy()
        Z1["ap"], Z0["ap"] = 1.0, 0.0
        p1, p0 = res.predict(Z1), res.predict(Z0)
        ame = float(np.mean(p1 - p0))
        # delta-method SE of the AME via the ap coefficient's SE scaled by mean density
        dens = float(np.mean(p0 * (1 - p0)))
        se = float(res.bse["ap"] * dens) if "ap" in res.bse else np.nan
        ames.append(ame)
        ses.append(se)
    a, se = float(np.mean(ames)), float(np.mean(ses))
    return {"ame_pts": 100 * a, "t": a / se if se > 0 else np.nan, "dropped_baseline": drops, "seeds": seeds}


# -------------------------------------------------------------------------------------------------------------- power
def icc(x, g):
    d = pd.DataFrame({"x": x, "g": g}).dropna()
    gm = d.groupby("g")["x"].transform("mean")
    vb = d.groupby("g")["x"].mean().var()
    vw = (d["x"] - gm).var()
    return max(0.0, vb / (vb + vw)) if vb + vw > 0 else 0.0


def power(sims=500):
    t0 = time.time()
    F = load()
    V = json.load(open(OUT / "validation.json"))
    C = F[F["set"] == "C"]
    say("=== VALIDATION (before outcomes) ===")
    for k in ("yahoo_vs_massive", "rs_rank_corr", "rs_vs_monthly_2016_2019", "breadth_agree", "strong_share_overlap",
              "strong_share_era", "liquid_median_era", "state", "usd20m_share_overlap", "split_screen_ticker_years",
              "monthly_completeness", "bad_bars_screened", "episodes", "fills"):
        say(f"{k}: {V.get(k)}")
    say("\n=== CLASS MIX (fills) ===")
    say(pd.crosstab([F["set"], F["era"]], F["class"]).to_string())
    say("stalled split:", F[F["class"] == "stalled"].groupby(["set", "stall"]).size().to_dict())
    say("class by listing-age tercile (C):\n" + pd.crosstab(C["aget"], C["class"]).to_string())
    say("excluded vs kept by era (C):", C.assign(ex=C["class"] == "excluded").groupby("era")["ex"].mean().round(3).to_dict())
    say("d_up of approaching (C) quantiles:", C.loc[C["class"] == "approach", "d_up"].quantile([.1, .25, .5, .75, .9]).round(2).to_dict())
    say("d_lh by class (C) median:", C.groupby("class")["d_lh"].median().round(2).to_dict())
    A = C[C["class"] == "approach"]
    res = {}
    for nm, bcls in (("A open sky", "open"), ("B far", "far")):
        Bc = C[C["class"] == bcls]
        M, uses = match(A, Bc)
        nT = len(M)
        eff_n = len({f for ids in M.values() for f in ids})
        capped = sum(1 for v in uses.values() if v >= 5)
        say(f"\n[{nm}] approaching {len(A)} · matched {nT} (dropped {len(A) - nT}) · distinct baseline fills {eff_n}, at cap {capped}")
        Am = A[A["fid"].isin(M)]
        say("  matched per era:", Am.groupby("era").size().to_dict(), "· per year:", Am.groupby("year").size().to_dict())
        res[nm] = (M, Bc)
    # design effect from open-sky outcomes only
    O = C[C["class"] == "open"]
    q = O["mfe20"].rank(pct=True)
    rho_m, rho_t = icc(q, O["month"]), icc(q, O["t"])
    mbar = A.groupby("month").size().mean()
    tbar = A.groupby("t").size().mean()
    deff = 1 + (mbar - 1) * rho_m + (tbar - 1) * rho_t
    MA = res["A open sky"][0]
    pbar = float(np.mean(O["mfe20"].to_numpy()[:, None] >= A["d_up"].median()))
    n_eff = len(MA) / deff
    mde_tag = 100 * (2 + norm.ppf(0.8)) * np.sqrt(2 * pbar * (1 - pbar) / max(n_eff, 1))
    rR = O["R"]
    rho_mR, rho_tR = icc(rR, O["month"]), icc(rR, O["t"])
    deffR = 1 + (mbar - 1) * rho_mR + (tbar - 1) * rho_tR
    sdR = C[C["class"].isin(["approach", "open", "far", "stalled", "too_close"])]["R"].std()
    nA, nO = len(A), len(O)
    mde_R = (2 + norm.ppf(0.8)) * sdR * np.sqrt(deffR * (1 / max(nA, 1) + 1 / max(nO, 1)))
    say(f"\nρ month {rho_m:.3f}, ρ ticker {rho_t:.3f}, fills/month {mbar:.1f}, fills/ticker {tbar:.1f} → design effect {deff:.2f}; "
        f"tag rate at median d {pbar:.2f}; MDE tag (t ≥ 2, 80%) {mde_tag:.1f} pts (gate ≤ 6)")
    say(f"R: ρ month {rho_mR:.3f}, ρ ticker {rho_tR:.3f}, deff {deffR:.2f}, SD {sdR:.2f}, approaching {nA}, open {nO} → MDE {mde_R:.3f}R (gate ≤ 0.15)")
    gates = {
        "H2a_counts": len(MA) >= 300 and len(res["B far"][0]) >= 300 and all(
            (A[A["fid"].isin(MA)]["era"] == e).sum() >= 60 for e in ("e1", "e2", "e3")),
        "H2a_mde": mde_tag <= 6,
        "H2b_counts": nA >= 300 and nO >= 300 and all((A["era"] == e).sum() >= 60 for e in ("e1", "e2", "e3")),
        "H2b_mde": mde_R <= 0.15,
    }
    say("gates:", gates)
    # simulated label power
    sim = simulate(C, res, rho_m, rho_t, sims)
    say(f"simulated pass rate (+6 pts true): H2a {sim['H2a']:.0%} · near bucket {sim['near']:.0%} · stopped short {sim['ss']:.0%}; "
        f"H2b-1 (+0.15R true) {sim['H2b']:.0%}  (cap: < 50% → inconclusive)")
    say("DEVIATION: the simulation applies the matched-effect, era, era-3, year, subset and dose rules; the model fit, permutation and"
        " jackknife are not re-run inside each simulation (cost) — the matched t ≥ 2 rule stands in for them.")
    P = {"gates": gates, "mde_tag": mde_tag, "mde_R": mde_R, "deff": deff, "deffR": deffR, "sim": sim,
         "rho": [rho_m, rho_t, rho_mR, rho_tR]}
    json.dump(P, open(OUT / "power.json", "w"), indent=1, default=float)
    (OUT / "power.txt").write_text("\n".join(LOG))
    say(f"power done {time.time() - t0:.0f}s")


def label_tag(diff, month, ticker, era, year, top15, d, need_near=False):
    m, t = cmean(diff, month, ticker)
    if not (m >= 0.05 and t >= 2):
        return False
    s = np.sign(m)
    D = pd.DataFrame({"x": diff, "era": era, "year": year, "top": top15, "d": d})
    em = D.groupby("era")["x"].mean()
    if len(em) < 3 or (np.sign(em) != s).any() or em.get("e3", 0) < 0.5 * m:
        return False
    yc = D.groupby("year")["x"].agg(["mean", "size"])
    yc = yc[yc["size"] >= 30]
    if len(yc) < 5 or (np.sign(yc["mean"]) == s).mean() < 2 / 3:
        return False
    if D.loc[D["top"], "x"].mean() < 0.03:
        return False
    return True


def simulate(C, res, rho_m, rho_t, sims):
    """Gaussian copula: latent u = Φ(month shock + ticker shock + noise) with the open-sky ICCs; each fill's simulated mfe20 = quantile u
    of its class's empirical mfe20 in its cell (open sky for baseline A, far for B; fallback month × kind → era); approaching tags get
    +6 pts on the probability scale."""
    rng = np.random.default_rng(SEED)
    sm2 = rho_m / max(1e-6, 1 - rho_m - rho_t)
    st2 = rho_t / max(1e-6, 1 - rho_m - rho_t)
    A = C[C["class"] == "approach"]
    months = C["month"].unique()
    tick = C["t"].unique()

    def dist(cls):
        X = C[C["class"] == cls]
        return ({k: np.sort(g["mfe20"].to_numpy()) for k, g in X.groupby("cell")},
                {k: np.sort(g["mfe20"].to_numpy()) for k, g in X.groupby(X["month"] + "|" + X["kind"])},
                {k: np.sort(g["mfe20"].to_numpy()) for k, g in X.groupby("era")})

    Dopen, Dfar = dist("open"), dist("far")

    def arr_for(r, Dd):
        for key, dd in ((r["cell"], Dd[0]), (r["month"] + "|" + r["kind"], Dd[1]), (r["era"], Dd[2])):
            a = dd.get(key)
            if a is not None and len(a) >= 5:
                return a
        return None

    pass_a = pass_near = pass_ss = pass_b = 0
    Ad = A.set_index("fid")
    Cf = C.set_index("fid")
    for s in range(sims):
        zm = dict(zip(months, rng.normal(0, np.sqrt(sm2), len(months))))
        zt = dict(zip(tick, rng.normal(0, np.sqrt(st2), len(tick))))
        ok_both = True
        diffs_A = None
        for nm, Dd in (("A open sky", Dopen), ("B far", Dfar)):
            M, Bc = res[nm]
            u_cache = {}

            def u_of(fid):
                if fid not in u_cache:
                    r = Cf.loc[fid]
                    u_cache[fid] = norm.cdf(zm[r["month"]] + zt[r["t"]] + rng.normal())
                return u_cache[fid]
            rows = []
            for tf, ids in M.items():
                r = Ad.loc[tf]
                d = r["d_up"]
                a = arr_for(r, Dd)
                if a is None:
                    continue
                p = float(np.mean(a >= d))
                tag = u_of(tf) >= 1 - min(1.0, p + 0.06)
                bvals = []
                for f in ids:
                    rb = Cf.loc[f]
                    ab = arr_for(rb, Dd)
                    if ab is None:
                        continue
                    bvals.append(np.quantile(ab, u_of(f)) >= d)
                if bvals:
                    rows.append((tf, float(tag) - float(np.mean(bvals)), r["month"], r["t"], r["era"], r["year"], r["top15"], d))
            X = pd.DataFrame(rows, columns=["fid", "x", "month", "t", "era", "year", "top", "d"])
            ok = len(X) > 30 and label_tag(X["x"].to_numpy(), X["month"], X["t"], X["era"], X["year"], X["top"].to_numpy(), X["d"])
            ok_both &= ok
            if nm == "A open sky":
                diffs_A = X
        if ok_both:
            pass_a += 1
            near = diffs_A[(diffs_A["d"] >= 1.5) & (diffs_A["d"] <= 3)]
            m, t = cmean(near["x"].to_numpy(), near["month"], near["t"]) if len(near) > 10 else (0, 0)
            pass_near += m >= 0.05 and t >= 2
        if s >= 200:      # the R and stopped-short sims are cheaper to estimate on 200 draws
            continue
        # H2b-1: whole-month resampling of open-sky R, +0.15R to approaching
        O = C[C["class"] == "open"]
        omon = {k: g["R"].to_numpy() for k, g in O.groupby("month")}
        keys = list(omon)
        Xb = C[C["class"].isin(["approach", "open"])][["class", "month", "t", "era", "year", "top15"]].copy()
        donor = dict(zip(keys, rng.choice(keys, len(keys))))
        Rs = np.array([rng.choice(omon[donor.get(m, m)]) if donor.get(m, m) in omon else np.nan for m in Xb["month"]])
        Rs = Rs + np.where(Xb["class"] == "approach", 0.15, 0.0)
        Xb["R"] = Rs
        Xb = Xb.dropna(subset=["R"])
        ap = Xb[Xb["class"] == "approach"]
        op = Xb[Xb["class"] == "open"]
        x = np.where(Xb["class"] == "approach", Xb["R"] / len(ap), -Xb["R"] / len(op)) * len(Xb)
        m, t = cmean(x, Xb["month"].to_numpy(), Xb["t"].to_numpy())
        em = Xb.assign(s=np.where(Xb["class"] == "approach", 1, -1)).groupby(["era", "class"])["R"].mean().unstack()
        eras_ok = len(em) == 3 and ((em["approach"] - em["open"]) > 0).all()
        top = Xb[Xb["top15"]]
        sub_ok = top.loc[top["class"] == "approach", "R"].mean() - top.loc[top["class"] == "open", "R"].mean() >= 0.10
        pass_b += bool(m >= 0.15 and t >= 2 and eras_ok and sub_ok and ap["R"].mean() > 0)
    nb = min(sims, 200)
    # stopped short: same copula logic against open sky only (secondary; estimated from the open-sky A rule on the ss rows)
    ss = C[(C["class"] == "stalled") & (C["stall"] == "short") & C["d_ss"].notna()]
    pass_ss = float("nan") if len(ss) < 30 else None
    if pass_ss is None:
        Mss, _ = match(ss.assign(d_up=ss["d_ss"]), C[C["class"] == "open"])
        hits = 0
        for s in range(nb):
            zm = dict(zip(months, rng.normal(0, np.sqrt(sm2), len(months))))
            zt = dict(zip(tick, rng.normal(0, np.sqrt(st2), len(tick))))
            rows = []
            Sd = ss.set_index("fid")
            for tf, ids in Mss.items():
                r = Sd.loc[tf]
                a = arr_for(r, Dopen)
                if a is None:
                    continue
                p = float(np.mean(a >= r["d_ss"]))
                u = norm.cdf(zm[r["month"]] + zt[r["t"]] + rng.normal())
                tag = u >= 1 - min(1.0, p + 0.06)
                b = [np.quantile(arr_for(Cf.loc[f], Dopen), norm.cdf(zm[Cf.loc[f, "month"]] + zt[Cf.loc[f, "t"]] + rng.normal())) >= r["d_ss"]
                     for f in ids if arr_for(Cf.loc[f], Dopen) is not None]
                if b:
                    rows.append((float(tag) - np.mean(b), r["month"], r["t"]))
            if len(rows) > 10:
                X = pd.DataFrame(rows, columns=["x", "month", "t"])
                m, t = cmean(X["x"].to_numpy(), X["month"], X["t"])
                hits += m >= 0.05 and t >= 2
        pass_ss = hits / nb
    return {"H2a": pass_a / sims, "near": pass_near / sims, "H2b": pass_b / nb, "ss": pass_ss}


# --------------------------------------------------------------------------------------------------------------- test
def test():
    raise SystemExit("test() is written after the power table is reviewed (outcomes stay closed until then).")
