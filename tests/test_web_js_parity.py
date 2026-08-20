"""Parité entre la régression JS du front et son équivalent Python.

Les ventes société importées ne quittent jamais le navigateur (décision produit : voir
`web/observable/src/donnees.md`). Leur élasticité est donc calculée en JavaScript, par
`bestLagFit` dans `web/observable/src/components/api.js` — alors que la même question, sur
les mêmes données, est répondue en Python par `forecast.best_tx_to_monthly`.

Deux implémentations du même estimateur, c'est exactement la situation qui produit deux
chiffres différents et une discussion sans arbitre. Ce test l'empêche : sur des données
identiques, les deux doivent retenir le MÊME décalage et le même R².

Il se skippe si Node n'est pas installé — la CI Python n'en a pas besoin pour le reste.
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
