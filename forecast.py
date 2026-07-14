"""
Prospective module: turn the app's real leading indicators into a small, transparent
"nowcast → forecast" of existing-home transactions, plus a scenario engine.

Two-stage econometrics (plain OLS via numpy — no extra dependency):
  Stage 1  credit rate  ~ OAT 10y + Euribor 3M               (scenario lever on financing)
  Stage 2  transactions ~ credit rate(lag) + purchase-intentions(lag) + unemployment(lag)

Everything is fit on the app's REAL national series (macro.csv + IGEDD dvf.csv). The
transactions target is the 12-month rolling sum (the published "ventes sur un an").
A train/test split (fit ≤2021, predict 2022→) provides an honest out-of-sample backtest.
"""
import numpy as np
import pandas as pd

# Stage-2 predictor columns and the sign we expect (for display / sanity only).
TX_PREDICTORS = ["Credit_Logement_Taux_Interet", "Intentions_Achat_Logement", "Taux_Chomage_BIT"]


def ols(X, y):
    """Ordinary least squares with intercept. X:(n,k), y:(n,). Returns (beta[k+1], r2,
    rmse, pred) where beta[0] is the intercept."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    X1 = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
    pred = X1 @ beta
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    rmse = float(np.sqrt(ss_res / len(y))) if len(y) else float("nan")
    return beta, r2, rmse, pred


def build_target(df_dvf):
    """12-month rolling sum of national existing-home transactions (IGEDD), indexed by
    Date. Reproduces the published 'ventes sur un an' series."""
    tx = df_dvf.groupby("Date")["Transactions"].sum().sort_index()
    return tx.rolling(12).sum().rename("tx12")


def _macro_indexed(df_macro):
    """Date-indexed macro with unemployment interpolated to monthly (it is quarterly)."""
    m = df_macro.set_index("Date").sort_index().copy()
    if "Taux_Chomage_BIT" in m:
        m["Taux_Chomage_BIT"] = m["Taux_Chomage_BIT"].interpolate(limit_direction="both")
    return m


def fit_rate_model(df_macro):
    """Stage 1: credit rate ~ OAT + Euribor. Returns dict with beta, r2, rmse and an
    aligned frame [Date, obs, fit]."""
    m = _macro_indexed(df_macro)
    d = m.dropna(subset=["Credit_Logement_Taux_Interet", "OAT_10ans", "Euribor_3M"])
    beta, r2, rmse, pred = ols(d[["OAT_10ans", "Euribor_3M"]].values,
                               d["Credit_Logement_Taux_Interet"].values)
    frame = pd.DataFrame({"Date": d.index, "obs": d["Credit_Logement_Taux_Interet"].values, "fit": pred})
    return {"beta": beta, "r2": r2, "rmse": rmse, "frame": frame}


def predict_rate(beta, oat, euribor):
    """Scenario credit rate from Stage-1 coefficients."""
    return float(beta[0] + beta[1] * oat + beta[2] * euribor)


def _design(m, tx12, kr, ki, kc):
    """Aligned design matrix for Stage 2 with the given lead-lags (months)."""
    X = pd.DataFrame({
        "rate": m["Credit_Logement_Taux_Interet"].shift(kr),
        "intent": m["Intentions_Achat_Logement"].shift(ki),
        "chom": m["Taux_Chomage_BIT"].shift(kc),
    })
    return X.join(tx12).dropna()


def search_tx_lags(df_macro, tx12, kr_range=range(0, 13), ki_range=range(0, 19, 2),
                   kc_range=range(0, 13, 2), min_obs=60):
    """Grid-search the predictor lead-lags that maximise in-sample R² for Stage 2."""
    m = _macro_indexed(df_macro)
    best = None
    for kr in kr_range:
        for ki in ki_range:
            for kc in kc_range:
                d = _design(m, tx12, kr, ki, kc)
                if len(d) < min_obs:
                    continue
                _, r2, _, _ = ols(d[["rate", "intent", "chom"]].values, d["tx12"].values)
                if best is None or r2 > best[0]:
                    best = (r2, kr, ki, kc)
    if best is None:
        return {"kr": 9, "ki": 4, "kc": 0}
    return {"kr": best[1], "ki": best[2], "kc": best[3]}


def fit_tx_model(df_macro, tx12, kr, ki, kc, split="2021-12-01"):
    """Stage 2 fit on the full sample + an out-of-sample backtest (train ≤ split).
    Returns beta, r2, rmse, an aligned [Date, obs, fit] frame, and backtest metrics."""
    m = _macro_indexed(df_macro)
    d = _design(m, tx12, kr, ki, kc)
    beta, r2, rmse, pred = ols(d[["rate", "intent", "chom"]].values, d["tx12"].values)
    frame = pd.DataFrame({"Date": d.index, "obs": d["tx12"].values, "fit": pred})

    train = d[d.index <= split]
    test = d[d.index > split]
    bt = {"split": split, "n_test": len(test)}
    if len(train) >= 40 and len(test) >= 6:
        bbeta, _, _, _ = ols(train[["rate", "intent", "chom"]].values, train["tx12"].values)
        tp = bbeta[0] + test[["rate", "intent", "chom"]].values @ bbeta[1:]
        err = test["tx12"].values - tp
        bt["rmse"] = float(np.sqrt((err ** 2).mean()))
        bt["mape"] = float(np.abs(err / test["tx12"].values).mean() * 100)
        bt["frame"] = pd.DataFrame({"Date": test.index, "obs": test["tx12"].values, "pred": tp})
        bt["train_beta"] = bbeta
    return {"beta": beta, "r2": r2, "rmse": rmse, "frame": frame,
            "lags": {"kr": kr, "ki": ki, "kc": kc}, "backtest": bt}


def predict_tx(beta, rate, intent, chom):
    """Scenario transactions (12-month) from Stage-2 coefficients."""
    return float(beta[0] + beta[1] * rate + beta[2] * intent + beta[3] * chom)


def scenario(rate_beta, tx_beta, base, scen):
    """Delta-anchored scenario, robust to the models' level biases (e.g. Stage 1 currently
    over-predicts the rate because banks hold it below what the OAT implies). We apply the
    estimated SENSITIVITIES to the *changes* vs the current actual baseline.

    base : {oat, euribor, intent, chom, rate_now, tx_now} — current actual values.
    scen : {oat, euribor, intent, chom} — scenario values.
    Returns {rate, d_rate, tx, d_tx}: implied credit rate and 12-month transactions.
    """
    d_rate = (rate_beta[1] * (scen["oat"] - base["oat"])
              + rate_beta[2] * (scen["euribor"] - base["euribor"]))
    rate_scen = base["rate_now"] + d_rate
    d_tx = (tx_beta[1] * d_rate
            + tx_beta[2] * (scen["intent"] - base["intent"])
            + tx_beta[3] * (scen["chom"] - base["chom"]))
    return {"rate": rate_scen, "d_rate": d_rate, "tx": base["tx_now"] + d_tx, "d_tx": d_tx}


def fit_tx_to_ca(df_revenue, tx12, company, lag_q=2):
    """Elasticity of a company's quarterly revenue to the transactions run-rate, at
    `lag_q` quarters. Returns dict with beta, r2, lag_q, n or None if too few points."""
    r = (df_revenue[df_revenue["Company"] == company]
         .set_index("Date")["CA_MEUR"].sort_index())
    txq = tx12.resample("QS").mean()
    d = pd.DataFrame({"ca": r}).join(txq.shift(lag_q).rename("tx")).dropna()
    if len(d) < 8:
        return None
    beta, r2, _, _ = ols(d["tx"].values.reshape(-1, 1), d["ca"].values)
    return {"beta": beta, "r2": r2, "lag_q": lag_q, "n": len(d)}


def best_tx_to_ca(df_revenue, tx12, company, lags=range(0, 7)):
    """Pick the transactions→revenue lag (quarters) with the highest R²."""
    best = None
    for lg in lags:
        fit = fit_tx_to_ca(df_revenue, tx12, company, lag_q=lg)
        if fit and (best is None or fit["r2"] > best["r2"]):
            best = fit
    return best
