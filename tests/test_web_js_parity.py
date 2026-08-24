"""Parité entre les calculs JS du front et leurs équivalents Python.

Deux fonctions du front dupliquent délibérément un calcul Python plutôt que d'appeler un
serveur pour huit multiplications, et chacune est un risque de divergence silencieuse :

- Les ventes société importées ne quittent jamais le navigateur (décision produit : voir
  `web/observable/src/donnees.md`). Leur élasticité est calculée en JavaScript, par
  `bestLagFit` dans `web/observable/src/components/api.js` — la même question, sur les
  mêmes données, est répondue en Python par `forecast.best_tx_to_monthly`.
- Le panneau de scénarios de `previsions.md` applique en JS, via `computeScenario`, la
  même formule fermée que `forecast.scenario` — sur les coefficients EXPORTÉS
  (previsions.json), pas recalculés : un aller-retour réseau pour huit multiplications
  n'aurait aucun sens une fois le modèle publié.

Deux implémentations du même calcul, c'est exactement la situation qui produit deux
chiffres différents et une discussion sans arbitre. Ces tests l'empêchent : sur des
données identiques, les deux doivent produire le MÊME résultat.

Ils se skippent si Node n'est pas installé — la CI Python n'en a pas besoin pour le reste.
"""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile

import numpy as np
import pandas as pd
import pytest

import forecast as fc

NODE = shutil.which("node")
API_JS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web",
                                      "observable", "src", "components", "api.js"))

pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js absent")


def _run_js(driver_rows, sales_rows):
    """Appelle `bestLagFit` du front sur les mêmes données, via Node."""
    script = f"""
import {{bestLagFit, ols1, shiftMonths}} from {json.dumps(pathlib.Path(API_JS).as_uri())};
const driver = {json.dumps(driver_rows)};
const sales = {json.dumps(sales_rows)};
const fit = bestLagFit(driver, sales);
process.stdout.write(JSON.stringify({{
  fit,
  shiftCheck: shiftMonths([{{date: "2024-11-01", value: 1}}], 3)[0].date,
  olsCheck: ols1([1,2,3,4,5,6,7,8,9,10], [3,5,7,9,11,13,15,17,19,21])
}}));
"""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "probe.mjs")
        with open(p, "w", encoding="utf-8") as f:
            f.write(script)
        # encoding="utf-8" : voir la note de tests/test_web_seo.py — sans lui, la sortie
        # de Node est decodee en cp1252 sous Windows et stdout revient a None.
        out = subprocess.run([NODE, p], capture_output=True, text=True,
                             encoding="utf-8", timeout=120)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def _synthetic_case(lag_months=7, n=90, seed=3):
    """Un driver mensuel et des ventes qui en dérivent avec un décalage connu."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2016-01-01", periods=n, freq="MS")
    driver = pd.Series(np.cumsum(rng.normal(0, 1, n)) + 100.0, index=dates)
    sales_idx = dates[lag_months:]
    sales_val = driver.values[:n - lag_months] * 2.5 + 40 + rng.normal(0, 0.4, n - lag_months)
    driver_rows = [{"date": d.strftime("%Y-%m-%d"), "value": float(v)}
                   for d, v in driver.items()]
    sales_rows = [{"date": d.strftime("%Y-%m-%d"), "value": float(v)}
                  for d, v in zip(sales_idx, sales_val)]
    sales_df = pd.DataFrame({"Date": sales_idx, "Sales": sales_val})
    return driver, driver_rows, sales_df, sales_rows


def test_js_helpers_behave_as_specified():
    """Décalage de dates et régression simple : les briques de base, isolément."""
    _, driver_rows, _, sales_rows = _synthetic_case()
    got = _run_js(driver_rows, sales_rows)
    # Novembre + 3 mois = février de l'année SUIVANTE (piège classique du passage d'année).
    assert got["shiftCheck"] == "2025-02-01"
    # y = 2x + 1 exactement : pente 2, ordonnée 1, R² = 1.
    o = got["olsCheck"]
    assert o["b"] == pytest.approx(2.0, abs=1e-9)
    assert o["a"] == pytest.approx(1.0, abs=1e-9)
    assert o["r2"] == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize("lag_months", [0, 4, 7, 12])
def test_best_lag_matches_python(lag_months):
    """Même décalage retenu et même R² que `forecast.best_tx_to_monthly`."""
    driver, driver_rows, sales_df, sales_rows = _synthetic_case(lag_months=lag_months)
    py = fc.best_tx_to_monthly(sales_df, driver, value_col="Sales")
    js = _run_js(driver_rows, sales_rows)["fit"]

    assert py is not None and js is not None
    assert js["lag"] == py["lag_m"] == lag_months, (
        f"JS retient {js['lag']} mois, Python {py['lag_m']}, injecté {lag_months}")
    assert js["r2"] == pytest.approx(py["r2"], abs=1e-9)
    assert js["n"] == py["n"]
    assert js["b"] == pytest.approx(py["beta"][1], rel=1e-9)


def test_best_lag_matches_python_on_real_transactions():
    """Même contrôle, mais sur la VRAIE série de transactions (bruit et trous réels)."""
    q = pytest.importorskip("queries")
    try:
        con = q.open_warehouse()
        tx12 = q.transactions_run_rate(con).dropna()
    except Exception as e:                                        # pragma: no cover
        pytest.skip(f"entrepôt indisponible : {e}")
    if tx12.empty:
        pytest.skip("série de transactions vide")

    rng = np.random.default_rng(11)
    lag = 6
    shifted = tx12.iloc[:-lag] if lag else tx12
    sales_idx = tx12.index[lag:]
    sales_val = shifted.values * 0.004 * (1 + rng.normal(0, 0.03, len(shifted)))

    sales_df = pd.DataFrame({"Date": sales_idx, "Sales": sales_val})
    py = fc.best_tx_to_monthly(sales_df, tx12, value_col="Sales")
    js = _run_js(
        [{"date": d.strftime("%Y-%m-%d"), "value": float(v)} for d, v in tx12.items()],
        [{"date": d.strftime("%Y-%m-%d"), "value": float(v)}
         for d, v in zip(sales_idx, sales_val)])["fit"]

    assert js["lag"] == py["lag_m"]
    assert js["r2"] == pytest.approx(py["r2"], abs=1e-9)


def _run_js_scenario(rate_coef, tx_coef, base, scen):
    """Appelle `computeScenario` du front sur les mêmes hypothèses, via Node."""
    script = f"""
import {{computeScenario}} from {json.dumps(pathlib.Path(API_JS).as_uri())};
process.stdout.write(JSON.stringify(computeScenario(
  {json.dumps(rate_coef)}, {json.dumps(tx_coef)}, {json.dumps(base)}, {json.dumps(scen)})));
"""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "probe.mjs")
        with open(p, "w", encoding="utf-8") as f:
            f.write(script)
        out = subprocess.run([NODE, p], capture_output=True, text=True,
                             encoding="utf-8", timeout=120)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


# L'Euribor a disparu des hypothèses : l'étage 1 ne régresse plus que sur l'OAT (voir
# `forecast.RATE_DRIVER`). Le cas « +1 pt d'Euribor seul » n'a donc plus d'objet — il
# testait un levier qui n'existe plus.
@pytest.mark.parametrize("oat,chom,z", [
    (3.85, 8.3, 0.0),      # scénario = baseline : aucun changement
    (4.85, 8.3, 0.0),      # +1 pt d'OAT seul
    (2.85, 8.3, 0.0),      # -1 pt d'OAT seul
    (3.85, 9.3, 0.0),      # +1 pt de chômage seul
    (3.35, 7.3, 1.5),      # les trois leviers ensemble
])
def test_scenario_matches_python(oat, chom, z):
    """`computeScenario` (JS) et `forecast.scenario` (Python) sur les mêmes hypothèses."""
    rate_beta = [1.22, 0.742]
    tx_beta = [2_671_810.7, -91_616.5, 13_006.8, -50_424.8]
    rate_coef = {"intercept": rate_beta[0], "oat": rate_beta[1]}
    tx_coef = {"intercept": tx_beta[0], "rate": tx_beta[1],
               "intentions": tx_beta[2], "unemployment": tx_beta[3]}

    intentions_mean, intentions_std, intentions_now = -83.14, 2.64, -82.0
    base_intent = intentions_now  # la baseline Python ancre "intent" sur la valeur RÉELLE
    scen_intent = intentions_mean + z * intentions_std

    py_base = {"oat": 3.85, "intent": base_intent, "chom": 8.3,
               "rate_now": 3.16, "tx_now": 954_000.0}
    py_scen = {"oat": oat, "intent": scen_intent, "chom": chom}
    py = fc.scenario(rate_beta, tx_beta, py_base, py_scen)

    js_base = {"oat": 3.85, "rate_now": 3.16, "tx_now": 954_000.0,
               "intentions": intentions_now, "intentions_mean": intentions_mean,
               "intentions_std": intentions_std, "unemployment": 8.3}
    js_scen = {"oat": oat, "chom": chom, "intentZ": z}
    js = _run_js_scenario(rate_coef, tx_coef, js_base, js_scen)

    assert js["rate"] == pytest.approx(py["rate"], rel=1e-9)
    assert js["rate_change"] == pytest.approx(py["d_rate"], rel=1e-9)
    assert js["transactions"] == pytest.approx(py["tx"], rel=1e-9)
    assert js["transactions_change"] == pytest.approx(py["d_tx"], rel=1e-9)
