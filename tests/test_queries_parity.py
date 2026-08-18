"""Tests de PARITÉ : la couche SQL (`queries.py`, DuckDB) donne EXACTEMENT les mêmes
chiffres que l'ancienne voie pandas (`analysis.py` + les calculs inline d'`app.py`),
sur les données RÉELLES de `data/*.parquet`.

C'est le filet de sécurité de la migration « DuckDB = moteur de calcul unique » : tant
que ces tests sont verts, remplacer un appel pandas par son équivalent SQL ne peut pas
faire diverger les chiffres affichés par Streamlit, le web ou le rapport PDF.

Ignoré proprement (skip) si l'entrepôt Parquet n'est pas présent ou si duckdb manque.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import pytest

import analysis as ana

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA = os.path.join(_REPO, "data")

pytest.importorskip("duckdb")
if not os.path.exists(os.path.join(_DATA, "sitadel.parquet")):
    pytest.skip("entrepôt Parquet absent (lancer python fetch_new_sources.py)",
                allow_module_level=True)

import queries as q  # noqa: E402  (après le skip)


@pytest.fixture(scope="module")
def con():
    c = q.open_warehouse(refresh=False)
    yield c
    c.close()


def _same(a, b, tol=1e-9, name=""):
    """Égalité numérique avec motif de NaN identique (comparaison float robuste)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    assert a.shape == b.shape, f"{name}: shapes {a.shape} != {b.shape}"
    assert np.array_equal(np.isnan(a), np.isnan(b)), f"{name}: motif de NaN différent"
    m = ~np.isnan(a)
    assert np.allclose(a[m], b[m], atol=tol, rtol=0), \
        f"{name}: maxdiff={np.nanmax(np.abs(a - b)):.6g}"


def _borrow_capacity_factor(rate_pct, years):
    """Réplique `_borrow_capacity_factor` d'app.py (référence pandas/numpy)."""
    i = np.asarray(rate_pct, dtype=float) / 100.0 / 12.0
    n = years * 12
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(i > 0, (1.0 - (1.0 + i) ** (-n)) / i, float(n))


# ------------------------------------------------------------------ cumuls glissants
@pytest.mark.parametrize("dataset,cols", [
    ("sitadel", ["Permis", "MisesEnChantier"]),
    ("ventes_ancien", ["Transactions"]),
])
def test_monthly_matches_pandas_rolling(con, dataset, cols):
    sql = q.monthly(con, dataset, cols, windows=(12, 6)).sort_values("Date").reset_index(drop=True)

    df = pd.read_parquet(os.path.join(_DATA, f"{dataset}.parquet"))
    agg = (ana.aggregate_sitadel(df) if dataset == "sitadel"
           else ana.aggregate_ventes_ancien(df))
    roll = ana.calculate_rolling_12m(agg, cols)
    roll = ana.calculate_rolling(roll, cols, 6).sort_values("Date").reset_index(drop=True)

    assert len(sql) == len(roll)
    for c in cols:
        for suffix in ["", "_12M", "_6M"]:
            _same(sql[c + suffix], roll[c + suffix], name=f"{dataset}.{c}{suffix}")


def test_monthly_by_group_matches_per_group_pandas(con):
    groups = {
        "pur": ana.SITADEL_INDIVIDUEL_PUR,
        "total": ana.SITADEL_INDIVIDUEL,
        "collectif": ana.SITADEL_COLLECTIF,
    }
    sql = q.monthly_by_group(con, "sitadel", groups, ["MisesEnChantier"], windows=(12,))
    df = pd.read_parquet(os.path.join(_DATA, "sitadel.parquet"))
    for label, types in groups.items():
        agg = ana.aggregate_sitadel(df, types)
        roll = ana.calculate_rolling_12m(agg, ["MisesEnChantier"]).sort_values("Date").reset_index(drop=True)
        sub = sql[sql["Groupe"] == label].sort_values("Date").reset_index(drop=True)
        _same(sub["MisesEnChantier"], roll["MisesEnChantier"], name=f"grp {label}")
        _same(sub["MisesEnChantier_12M"], roll["MisesEnChantier_12M"], name=f"grp {label} 12M")


def test_monthly_type_filter_matches_pandas(con):
    types = ana.SITADEL_INDIVIDUEL_PUR
    sql = q.monthly(con, "sitadel", ["Permis"], windows=(12,), types=types).sort_values("Date").reset_index(drop=True)
    df = pd.read_parquet(os.path.join(_DATA, "sitadel.parquet"))
    roll = ana.calculate_rolling_12m(ana.aggregate_sitadel(df, types), ["Permis"]).sort_values("Date").reset_index(drop=True)
    _same(sql["Permis"], roll["Permis"], name="pur Permis")
    _same(sql["Permis_12M"], roll["Permis_12M"], name="pur Permis_12M")


# ------------------------------------------------------------------ macro & transforms
def test_macro_series_matches_dropna(con):
    col = "Insee_Confiance_Menages"
    sql = q.macro_series(con, col, digits=6)
    m = pd.read_parquet(os.path.join(_DATA, "macro.parquet")).dropna(subset=[col]).sort_values("Date")
    _same([r["value"] for r in sql], m[col].values, tol=1e-4, name="macro_series")


def test_series_with_lag_pct_matches_pct_change(con):
    col = "Prix_Ancien_Ensemble"
    sql = q.series_with_lag_pct(con, col, lag=4, digits=8)
    m = pd.read_parquet(os.path.join(_DATA, "macro.parquet")).dropna(subset=[col]).sort_values("Date")
    yoy = (m[col].pct_change(4) * 100).dropna()
    _same([r["value"] for r in sql], yoy.values, tol=1e-4, name="lag_pct")


def test_rolling_sum_matches_pandas(con):
    col = "Production_Credits_Habitat"
    sql = q.rolling_sum(con, col, window=12, digits=8)
    m = pd.read_parquet(os.path.join(_DATA, "macro.parquet")).dropna(subset=[col]).sort_values("Date")
    roll = m[col].rolling(12).sum().dropna()
    _same([r["value"] for r in sql], roll.values, tol=1e-3, name="rolling_sum")


def test_macro_zscore_matches_pandas(con):
    col = "Intentions_Achat_Logement"
    sql = q.macro_zscore(con, col, digits=8)
    m = pd.read_parquet(os.path.join(_DATA, "macro.parquet")).dropna(subset=[col]).sort_values("Date")
    z = (m[col] - m[col].mean()) / m[col].std()
    _same([r["value"] for r in sql], z.values, tol=1e-4, name="zscore")


@pytest.mark.parametrize("years", [25, 20])
def test_capacity_accessibility_matches_pandas(con, years):
    sql = q.capacity_accessibility(con, years).sort_values("Date").reset_index(drop=True)
    m = pd.read_parquet(os.path.join(_DATA, "macro.parquet"))
    full = m.dropna(subset=["Credit_Logement_Taux_Interet"]).copy()
    cap15 = _borrow_capacity_factor(
        full.loc[full["Date"].dt.year == 2015, "Credit_Logement_Taux_Interet"], years).mean()
    acc = m.dropna(subset=["Credit_Logement_Taux_Interet", "Prix_Ancien_Ensemble"]).copy()
    acc["capidx"] = _borrow_capacity_factor(acc["Credit_Logement_Taux_Interet"], years) / cap15 * 100
    acc["access"] = acc["capidx"] / acc["Prix_Ancien_Ensemble"] * 100
    acc = acc.sort_values("Date").reset_index(drop=True)
    _same(sql["capidx"], acc["capidx"], tol=1e-6, name="capidx")
    _same(sql["access"], acc["access"], tol=1e-6, name="access")
