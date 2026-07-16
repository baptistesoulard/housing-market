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
