"""
Business-logic invariants for the analysis / forecast / data layers.

Pure-Python, runnable standalone (`python tests/test_logic.py`) and pytest-compatible.
Covers the highest-value invariants the app relies on: the IGEDD monthly reconstruction,
the momentum / KPI helpers, the OLS + scenario arithmetic and the forward forecast path.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import analysis as ana
import forecast as fc
import simulation as sim
from data_manager import (DataManager, IGEDD_ANCIEN_XLS, IGEDD_ANCIEN_SHEET,
                          IGEDD_ANCIEN_DATE_COL, IGEDD_ANCIEN_VALUE_COL)


# --- IGEDD reconstruction --------------------------------------------------------------

def test_igedd_reconstruction_reproduces_published_cumulative():
    """The reconstructed monthly flows, summed over a trailing 12-month window, must
    reproduce the published 12-month cumulative (in counts) to within integer-rounding
    drift (each monthly flow is rounded once, so a 12-term window drifts by at most ~±6)."""
    if not os.path.exists(IGEDD_ANCIEN_XLS):
        print("SKIP igedd (source .xls absent)")
        return
    df = DataManager.build_ventes_ancien_from_igedd()
    assert list(df["Type"].unique()) == ["Ancien"]
    assert df["Date"].is_monotonic_increasing and df["Date"].is_unique
    assert (df["Transactions"] >= 0).all()

    roll = df.set_index("Date")["Transactions"].astype(float).rolling(12).sum()

    # Rebuild the published cumulative C the same way the loader reads it.
    raw = pd.read_excel(IGEDD_ANCIEN_XLS, sheet_name=IGEDD_ANCIEN_SHEET, header=None)
    s = raw.iloc[:, [IGEDD_ANCIEN_DATE_COL, IGEDD_ANCIEN_VALUE_COL]].copy()
    s.columns = ["date", "val"]
    s["date"] = pd.to_datetime(s["date"], errors="coerce")
    s["val"] = pd.to_numeric(s["val"].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    s = s.dropna(subset=["date", "val"]).sort_values("date")
    s = s[s["date"] >= "2001-01-01"]
    C = pd.Series((s["val"].to_numpy() * 1000.0),
                  index=s["date"].dt.to_period("M").dt.to_timestamp())

    common = roll.dropna().index.intersection(C.index)
    diff = (roll.reindex(common) - C.reindex(common)).abs()
    assert diff.max() <= 12, f"IGEDD rolling-12m drifts by {diff.max():.0f} vs published cumulative"


# --- momentum & KPIs -------------------------------------------------------------------

def _monthly(values, start="2019-01-01"):
    idx = pd.date_range(start, periods=len(values), freq="MS")
    return pd.DataFrame({"Date": idx, "V": values})


def test_momentum_last3_yoy():
    # 27 months; last 3 = [100,100,100]=300, same 3 months a year earlier index 12-14.
    vals = list(range(1, 13)) + [10, 10, 10] + list(range(16, 28))  # len 27
    df = _monthly(vals)
    # last 3 months are indices 24,25,26 -> values 25,26,27 = 78; prev year 12,13,14 -> 10,10,10=30
    m = ana.momentum_metrics(df, "V")
    assert m["last3_yoy"] == round((78 - 30) / 30 * 100, 1)


def test_calculate_kpis_yoy_on_rolling():
    # Constant +1000/month; 12m rolling is flat once warmed. Use a step to get a known YoY.
    vals = [1000] * 24 + [1100] * 12  # 36 months
    df = ana.calculate_rolling_12m(_monthly(vals), ["V"])
    k = ana.calculate_kpis(df, "V")
    assert k["current_12m"] == 13200  # last 12 months = 12*1100
    assert k["yoy_12m_pct"] > 0


# --- OLS + scenario --------------------------------------------------------------------

def test_ols_recovers_known_line():
    x = np.arange(50.0)
    y = 2.0 + 3.0 * x
    beta, r2, rmse, _ = fc.ols(x.reshape(-1, 1), y)
    assert abs(beta[0] - 2.0) < 1e-6 and abs(beta[1] - 3.0) < 1e-6
    assert r2 > 0.999999 and rmse < 1e-6


def test_scenario_is_delta_anchored():
    # rate = 1 + 0.5*OAT + 0.5*Euribor ; tx = 0 + (-100)*rate + 10*intent + (-50)*chom
    rate_beta = np.array([1.0, 0.5, 0.5])
    tx_beta = np.array([0.0, -100.0, 10.0, -50.0])
    base = {"oat": 3.0, "euribor": 2.0, "intent": 0.0, "chom": 7.0,
            "rate_now": 3.4, "tx_now": 900_000}
    scen = {"oat": 4.0, "euribor": 2.0, "intent": 0.0, "chom": 7.0}  # +1pt OAT only
    out = fc.scenario(rate_beta, tx_beta, base, scen)
    assert abs(out["d_rate"] - 0.5) < 1e-9           # +1pt OAT * 0.5
    assert abs(out["rate"] - (3.4 + 0.5)) < 1e-9     # anchored on the actual current rate
    assert abs(out["d_tx"] - (-100.0 * 0.5)) < 1e-9  # rate change propagated to tx
    assert abs(out["tx"] - (900_000 - 50.0)) < 1e-9


# --- forward forecast path -------------------------------------------------------------

def test_forecast_path_uses_observed_lags_and_bounds_horizon():
    # 40 monthly macro rows; predictors fully observed. tx observed only up to month 30, so
    # the model can project ahead using already-observed lagged predictors.
    idx = pd.date_range("2020-01-01", periods=40, freq="MS")
    macro = pd.DataFrame({
        "Date": idx,
        "Credit_Logement_Taux_Interet": np.linspace(1.0, 4.0, 40),
        "Intentions_Achat_Logement": np.linspace(-1.0, 1.0, 40),
        "Taux_Chomage_BIT": np.linspace(8.0, 7.0, 40),
    })
    tx12 = pd.Series(np.linspace(800_000, 950_000, 31), index=idx[:31], name="tx12")
    lags = {"kr": 6, "ki": 4, "kc": 2}
    beta = np.array([500_000.0, -10_000.0, 50_000.0, -20_000.0])
    path = fc.forecast_path(macro, tx12, lags, beta, sigma=5_000.0, horizon=18)
    assert path is not None and not path.empty
    # Full horizon (carry-forward beyond predictor availability): 18 months past last obs.
    assert len(path) == 18
    assert path["Date"].max() == tx12.index.max() + pd.DateOffset(months=18)
    # Assumption-free part is bounded by the smallest predictor reach (chom: last date + 2).
    assured = path[path["assured"]]
    assert not assured.empty
    assert assured["Date"].max() <= idx[-1] + pd.DateOffset(months=2)
    assert (path["hi"] > path["pred"]).all() and (path["lo"] < path["pred"]).all()
    # Predictions match the closed-form model on the first projected month (all observed).
    t0 = path["Date"].iloc[0]
    m = macro.set_index("Date")
    exp = (beta[0]
           + beta[1] * m["Credit_Logement_Taux_Interet"].loc[t0 - pd.DateOffset(months=6)]
           + beta[2] * m["Intentions_Achat_Logement"].loc[t0 - pd.DateOffset(months=4)]
           + beta[3] * m["Taux_Chomage_BIT"].loc[t0 - pd.DateOffset(months=2)])
    assert bool(path["assured"].iloc[0]) is True
    assert abs(path["pred"].iloc[0] - exp) < 1e-6


def test_propagate_to_series_drives_sales_from_tx_path():
    """The company-sales forecast = a + b·tx12(t − lag_m), driven by observed tx then the
    forecast path, out to tx_path end + lag_m."""
    obs_idx = pd.date_range("2020-01-01", periods=24, freq="MS")   # ...2021-12
    tx12_obs = pd.Series(np.linspace(800_000, 900_000, 24), index=obs_idx, name="tx12")
    path_idx = pd.date_range("2022-01-01", periods=6, freq="MS")   # ...2022-06
    tx_path = pd.DataFrame({"Date": path_idx, "pred": np.linspace(905_000, 930_000, 6),
                            "lo": 0, "hi": 0, "assured": True})
    fit = {"beta": [1_000.0, 0.01], "lag_m": 3, "r2": 0.9, "n": 20}
    sales_df = pd.DataFrame({"Date": obs_idx, "Sales": np.linspace(100, 200, 24)})
    out = fc.propagate_to_series(fit, tx12_obs, tx_path, sales_df, "Sales", sigma_tx=1_000.0)
    assert not out.empty
    # Horizon: last sales month (2021-12) +1 .. tx_path end (2022-06) + lag_m(3) = 2022-09.
    assert out["Date"].max() == pd.Timestamp("2022-09-01")
    # First projected month 2022-01 uses tx at 2021-10 (observed).
    drv = tx12_obs.loc[pd.Timestamp("2021-10-01")]
    assert abs(out["pred"].iloc[0] - (1_000.0 + 0.01 * drv)) < 1e-6
    # Band = |b|·z·sigma (z≈1.2816).
    assert abs((out["hi"].iloc[0] - out["pred"].iloc[0]) - 0.01 * 1.2816 * 1_000.0) < 1e-6


def test_search_tx_lags_split_avoids_leakage():
    """With a train/test split, the lag search must use the TRAIN window only. Build a
    series whose intentions lead transactions by 6 months IN TRAIN, but by 2 months (more
    strongly) IN TEST. Full-sample search is pulled toward 2; split search must return 6."""
    n = 240
    idx = pd.date_range("2005-01-01", periods=n, freq="MS")
    rng = np.random.default_rng(0)
    intent = rng.normal(0, 1, n)
    split = "2015-12-01"
    split_i = int((pd.DatetimeIndex(idx) <= split).sum())
    tx = np.empty(n)
    for t in range(n):
        if t < split_i:
            tx[t] = 100_000 + 5_000 * (intent[t - 6] if t >= 6 else 0.0)      # train: lag 6
        else:
            tx[t] = 100_000 + 20_000 * (intent[t - 2] if t >= 2 else 0.0)     # test: lag 2, strong
    macro = pd.DataFrame({
        "Date": idx,
        "Credit_Logement_Taux_Interet": np.full(n, 2.0),   # flat -> irrelevant predictor
        "Intentions_Achat_Logement": intent,
        "Taux_Chomage_BIT": np.full(n, 8.0),               # flat -> irrelevant predictor
    })
    tx12 = pd.Series(tx, index=idx, name="tx12")
    full = fc.search_tx_lags(macro, tx12)                       # may lock onto lag 2 (leak)
    train = fc.search_tx_lags(macro, tx12, split=split)         # must see only the train lag
    assert train["ki"] == 6, f"split search leaked (ki={train['ki']})"
    assert full["ki"] != train["ki"] or full["ki"] == 2         # sanity: full is pulled to test


def test_two_factor_recovers_renovation_driver():
    """sales = a + b_tx·tx(t-3) + b_reno·reno(t-6): the two-factor fit must recover both
    lags and beat a transactions-only fit."""
    idx = pd.date_range("2015-01-01", periods=96, freq="MS")
    rng = np.random.default_rng(3)
    tx = pd.Series(np.linspace(800_000, 950_000, 96) + rng.normal(0, 3_000, 96), index=idx)
    reno = pd.Series(rng.normal(50, 8, 96), index=idx)
    sales_vals = np.full(96, np.nan)
    for t in range(96):
        if t >= 6:
            sales_vals[t] = 100.0 + 0.0005 * tx.iloc[t - 3] + 3.0 * reno.iloc[t - 6]
    sdf = pd.DataFrame({"Date": idx, "Sales": sales_vals}).dropna()
    tf = fc.fit_sales_two_factor(sdf, tx, reno, "Sales")
    assert tf is not None
    assert tf["tx_lag"] == 3 and tf["reno_lag"] == 6
    assert tf["r2"] > 0.98
    single = fc.best_tx_to_monthly(sdf, tx, "Sales")
    assert tf["r2"] >= single["r2"]  # adding renovation cannot hurt in-sample fit


def test_composite_optimizer_reports_out_of_sample():
    """The composite optimizer must return a held-out test correlation, and on pure noise
    the (overfit) train r should exceed the honest test r."""
    idx = pd.date_range("2010-01-01", periods=120, freq="MS")
    rng = np.random.default_rng(1)
    c1 = pd.DataFrame({"Date": idx, "Permis": rng.normal(500, 50, 120)})
    c2 = pd.DataFrame({"Date": idx, "Conf": rng.normal(100, 5, 120)})
    c3 = pd.DataFrame({"Date": idx, "Rate": rng.normal(2, 0.3, 120)})
    sales = pd.DataFrame({"Date": idx, "Sales_Units": rng.normal(1000, 100, 120)})
    res = sim.optimize_composite_parameters(c1, "Permis", c2, "Conf", c3, "Rate",
                                            sales, "Sales_Units")
    assert "test_correlation" in res and res["test_correlation"] is not None
    assert res["max_correlation"] > res["test_correlation"]  # overfit unmasked on noise


# --- Derived-cache invalidation & source resilience -------------------------------------

def test_sitadel_macro_cache_is_invalidated_by_a_newer_source():
    """data/sitadel.csv and data/macro.csv must be rebuilt when any manual-input source is
    newer, like every other derived dataset. They used to be built once and never
    invalidated, so the weekly refresh silently left the app serving frozen CSVs.

    Fully hermetic: the source list is stubbed onto a temp directory, so the test never
    reads or re-stamps a real file in data_manual_input/.
    """
    import tempfile
    import data_manager as dmod
    with tempfile.TemporaryDirectory() as tmp:
        sit = os.path.join(tmp, "sitadel.csv")
        mac = os.path.join(tmp, "macro.csv")
        assert dmod.sitadel_macro_is_stale(sit, mac), "missing caches must count as stale"

        src = os.path.join(tmp, "source.csv")
        for p in (src, sit, mac):
            open(p, "w").write("Date\n2020-01-01\n")

        real_sources = dmod._sitadel_macro_sources
        dmod._sitadel_macro_sources = lambda: [src]
        try:
            # Caches strictly newer than the source -> fresh, no rebuild.
            os.utime(src, (1_000_000, 1_000_000))
            for p in (sit, mac):
                os.utime(p, (2_000_000, 2_000_000))
            assert not dmod.sitadel_macro_is_stale(sit, mac)

            # Source refreshed after the caches -> stale, rebuild.
            os.utime(src, (3_000_000, 3_000_000))
            assert dmod.sitadel_macro_is_stale(sit, mac)
        finally:
            dmod._sitadel_macro_sources = real_sources


def test_macro_optional_column_missing_degrades_to_nan():
    """An OPTIONAL series whose column disappears upstream must leave that column NaN, not
    raise. These CSVs are refreshed weekly from public APIs, so a rename must not take the
    whole app down at startup."""
    import tempfile
    import data_manager as dmod
    idx = pd.date_range("2020-01-01", periods=24, freq="MS")
    with tempfile.TemporaryDirectory() as tmp:
        req = [(os.path.join(tmp, "r.csv"), "Insee_Confiance_Menages"),
               (os.path.join(tmp, "r2.csv"), "Credit_Logement_Taux_Interet")]
        for path, col in req:
            pd.DataFrame({"Date": idx, col: np.arange(24.0)}).to_csv(path, index=False)
        # Present file, but the requested column is gone.
        drifted = os.path.join(tmp, "drift.csv")
        pd.DataFrame({"Date": idx, "SomethingElse": 1.0}).to_csv(drifted, index=False)
        opt = [(drifted, "Euribor_3M"), (os.path.join(tmp, "absent.csv"), "OAT_10ans")]

        orig_req, orig_opt = dmod._MACRO_REQUIRED, dmod._MACRO_OPTIONAL
        dmod._MACRO_REQUIRED, dmod._MACRO_OPTIONAL = req, opt
        try:
            out = dmod.build_macro_from_files(idx)          # must not raise
        finally:
            dmod._MACRO_REQUIRED, dmod._MACRO_OPTIONAL = orig_req, orig_opt
    assert out["Euribor_3M"].isna().all(), "drifted column must degrade to NaN"
    assert out["OAT_10ans"].isna().all(), "absent file must still degrade to NaN"
    assert out["Insee_Confiance_Menages"].notna().any(), "required series must survive"


def test_search_tx_lags_scores_every_candidate_on_one_window():
    """Every candidate's R² must be computed on the SAME months. Otherwise a longer lag is
    scored on a smaller sample and the comparison that picks the winner is not like-for-like.

    Spies on the OLS calls search_tx_lags makes and asserts they all saw one sample size.
    """
    idx = pd.date_range("2005-01-01", periods=240, freq="MS")
    rng = np.random.default_rng(3)
    macro = pd.DataFrame({
        "Date": idx,
        "Credit_Logement_Taux_Interet": rng.normal(2, 0.3, 240),
        "Intentions_Achat_Logement": rng.normal(0, 1, 240),
        "Taux_Chomage_BIT": rng.normal(8, 0.5, 240),
    })
    tx12 = pd.Series(rng.normal(9e5, 5e4, 240), index=idx, name="tx12")

    seen = []
    real_ols = fc.ols
    fc.ols = lambda X, y: (seen.append(len(y)), real_ols(X, y))[1]
    try:
        lags = fc.search_tx_lags(macro, tx12, split="2021-12-01")
    finally:
        fc.ols = real_ols

    assert len(seen) > 100, "the grid should have scored many candidates"
    assert len(set(seen)) == 1, f"candidates scored on differing sample sizes: {sorted(set(seen))}"
    assert set(lags) and {"kr", "ki", "kc"} == set(lags)

    # The shared window must also respect the train/test split.
    m = fc._macro_indexed(macro)
    common = fc._grid_common_index(m, tx12, range(0, 13), range(0, 19, 2),
                                   range(0, 13, 2), split="2021-12-01")
    assert len(common) == seen[0]
    assert common.max() <= pd.Timestamp("2021-12-01")


def test_optional_fallback_frames_match_the_real_datasets():
    """The empty frame returned when an optional dataset is missing must carry exactly the
    columns the real CSV has. The ECLN schema used to be spelled out three times; it now
    lives in one constant, and this pins it to the actual file so the two cannot drift."""
    import tempfile
    import data_manager as dmod
    for key, columns, real in (("revenue", dmod.REVENUE_COLUMNS, "data/revenue.csv"),
                               ("ecln", dmod.ECLN_COLUMNS, "data/ecln.csv")):
        with tempfile.TemporaryDirectory() as tmp:
            empty = dmod.DataManager(data_dir=tmp)._read_optional(key, columns)
        assert empty.empty and list(empty.columns) == columns
        if os.path.exists(real):
            assert list(pd.read_csv(real).columns) == columns, f"{key}: schéma désaligné"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"FAIL {fn.__name__}: {e.__class__.__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)


# --- Base 100 (convention INSEE) -------------------------------------------------------

def _serie_annuelle(annees, valeurs_par_an):
    """Une frame mensuelle {Date, V} couvrant `annees` en entier."""
    lignes = []
    for an in annees:
        for mois in range(1, 13):
            lignes.append({"Date": pd.Timestamp(an, mois, 1), "V": valeurs_par_an[an]})
    return pd.DataFrame(lignes)


def test_base_100_est_la_moyenne_de_l_annee_de_reference():
    """La base est la moyenne des DOUZE mois, pas le premier point de l'année."""
    df = pd.DataFrame({"Date": pd.date_range("2015-01-01", periods=12, freq="MS"),
                       "V": list(range(1, 13))})
    assert ana.base_100(df, ["V"])["V"] == 6.5          # moyenne de 1..12


def test_base_100_indexe_bien_a_100_sur_l_annee_de_reference():
    """Le contrôle qui compte : la série divisée par sa base fait 100 en moyenne en 2015."""
    df = _serie_annuelle([2015, 2016], {2015: 200.0, 2016: 260.0})
    base = ana.base_100(df, ["V"])["V"]
    indice = df.assign(idx=df["V"] / base * 100.0)
    en_2015 = indice[indice["Date"].dt.year == 2015]["idx"]
    assert abs(en_2015.mean() - 100.0) < 1e-9
    assert abs(indice[indice["Date"].dt.year == 2016]["idx"].iloc[0] - 130.0) < 1e-9


def test_base_100_refuse_une_annee_de_reference_incomplete():
    """Onze mois ne font pas une moyenne annuelle : la saisonnalité du mois manquant
    passerait dans le dénominateur de toute la série. Mieux vaut ne pas indexer."""
    df = pd.DataFrame({"Date": pd.date_range("2015-01-01", periods=11, freq="MS"),
                       "V": [10.0] * 11})
    assert ana.base_100(df, ["V"])["V"] is None


def test_base_100_refuse_une_colonne_absente_ou_vide():
    df = pd.DataFrame({"Date": pd.date_range("2015-01-01", periods=12, freq="MS"),
                       "V": [np.nan] * 12})
    base = ana.base_100(df, ["V", "Inconnue"])
    assert base["V"] is None and base["Inconnue"] is None


def test_base_100_ne_divise_jamais_par_zero():
    """Une moyenne nulle est une base inutilisable, pas une base valide."""
    df = pd.DataFrame({"Date": pd.date_range("2015-01-01", periods=12, freq="MS"),
                       "V": [0.0] * 12})
    assert ana.base_100(df, ["V"])["V"] is None


def test_base_100_ignore_les_autres_annees():
    """Le slicer de période ne doit jamais pouvoir déplacer la base."""
    df = _serie_annuelle([2014, 2015, 2016], {2014: 50.0, 2015: 100.0, 2016: 400.0})
    assert ana.base_100(df, ["V"])["V"] == 100.0
