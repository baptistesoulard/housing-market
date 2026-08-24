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


def test_monthly_without_windows_matches_bare_aggregate(con):
    """`windows=()` = agrégat mensuel nu, sans cumul glissant. C'est ce que consomment les
    barres de comparaison mois-par-mois d'app.py et les métriques de momentum : une clause
    WINDOW vide produirait du SQL invalide, ce chemin doit donc rester couvert."""
    types = ana.SITADEL_INDIVIDUEL_PUR
    sql = q.monthly(con, "sitadel", ["Permis", "MisesEnChantier"], windows=(),
                    types=types).sort_values("Date").reset_index(drop=True)
    df = pd.read_parquet(os.path.join(_DATA, "sitadel.parquet"))
    agg = ana.aggregate_sitadel(df, types).sort_values("Date").reset_index(drop=True)

    assert list(sql.columns) == ["Date", "Permis", "MisesEnChantier"]   # aucune colonne _NM
    assert sql["Date"].tolist() == agg["Date"].tolist()
    for c in ["Permis", "MisesEnChantier"]:
        _same(sql[c], agg[c], name=f"nu {c}")


@pytest.mark.parametrize("years", [(2015, 2020), (2019, 2019)])
def test_monthly_years_filter_matches_pandas_slicer(con, years):
    """`years=` reproduit le `_filter_years` d'app.py (bornes incluses, sur l'année civile),
    appliqué avant le GROUP BY comme le faisait le filtrage pandas en amont de l'agrégat."""
    sql = q.monthly(con, "ventes_ancien", ["Transactions"], windows=(),
                    years=years).sort_values("Date").reset_index(drop=True)
    df = pd.read_parquet(os.path.join(_DATA, "ventes_ancien.parquet"))
    filtre = df[(df["Date"].dt.year >= years[0]) & (df["Date"].dt.year <= years[1])]
    agg = ana.aggregate_ventes_ancien(filtre).sort_values("Date").reset_index(drop=True)

    assert sql["Date"].tolist() == agg["Date"].tolist(), f"bornes {years}"
    _same(sql["Transactions"], agg["Transactions"], name=f"années {years}")


def test_years_filter_and_type_filter_combine(con):
    """Les deux filtres se cumulent dans la même clause WHERE — combinaison utilisée par
    l'onglet « Marché du neuf » (segmentation par type + slicer d'années)."""
    types, years = ana.SITADEL_COLLECTIF, (2018, 2022)
    sql = q.monthly(con, "sitadel", ["Permis"], windows=(), types=types,
                    years=years).sort_values("Date").reset_index(drop=True)
    df = pd.read_parquet(os.path.join(_DATA, "sitadel.parquet"))
    filtre = df[(df["Date"].dt.year >= years[0]) & (df["Date"].dt.year <= years[1])]
    agg = ana.aggregate_sitadel(filtre, types).sort_values("Date").reset_index(drop=True)

    assert sql["Date"].tolist() == agg["Date"].tolist()
    _same(sql["Permis"], agg["Permis"], name="collectif 2018-2022")


@pytest.mark.parametrize("dataset,col,category_col", [
    ("sales", "Sales_Units", "Product"),
    ("company_sales", "Sales", "Serie"),
])
def test_category_col_filters_non_type_datasets(con, dataset, col, category_col):
    """Deux datasets portent leur catégorie dans une colonne autre que `Type`. Sans
    `category_col` ils restaient agrégés en pandas dans les onglets interactifs."""
    path = os.path.join(_DATA, f"{dataset}.parquet")
    if not os.path.exists(path):
        pytest.skip(f"{dataset} absent (dataset optionnel)")
    df = pd.read_parquet(path)
    if df.empty:
        pytest.skip(f"{dataset} vide")
    valeur = sorted(df[category_col].dropna().unique())[0]

    sql = q.monthly(con, dataset, [col], windows=(), types=[valeur],
                    category_col=category_col).sort_values("Date").reset_index(drop=True)
    ref = (df[df[category_col] == valeur].groupby("Date")[col].sum().reset_index()
           .sort_values("Date").reset_index(drop=True))
    assert sql["Date"].tolist() == ref["Date"].tolist(), f"{dataset}/{valeur}"
    _same(sql[col], ref[col], name=f"{dataset}[{category_col}={valeur}]")


def test_macro_rolling_matches_dropna_then_rolling(con):
    """`macro_rolling` réplique `df.dropna(subset=[c]).rolling(w).sum()` en CONSERVANT les
    lignes à cumul NULL et les colonnes brutes — les vues qui superposent barres mensuelles
    et courbe cumulée ont besoin des deux sur le même axe."""
    base = "Production_Credits_Habitat"
    autre = "Production_Credits_Pure"
    df = pd.read_parquet(os.path.join(_DATA, "macro.parquet"))
    if base not in df.columns or not df[base].notna().any():
        pytest.skip("série de crédits absente")
    roll = [base] + ([autre] if autre in df.columns and df[autre].notna().any() else [])

    sql = q.macro_rolling(con, base, roll, window=12)
    ref = df.dropna(subset=[base]).copy()
    assert len(sql) == len(ref)                       # aucune ligne perdue
    for c in roll:
        ref[f"{c}_ref"] = ref[c].rolling(12).sum()
        _same(sql[f"{c}_cum12"], ref[f"{c}_ref"], name=f"cum12 {c}")
        _same(sql[c], ref[c], name=f"brut {c}")       # colonne brute conservée


def test_transactions_run_rate_matches_forecast_build_target(con):
    """La série pilote de la prévision. C'était le dernier chiffre AFFICHÉ défini deux
    fois : `Transactions_12M` en SQL dans l'onglet Ancien, et le même cumul recalculé en
    pandas pour alimenter les modèles. La forme compte autant que les valeurs — les
    modèles font `.shift()`, `.resample("QS")` et des jointures sur l'index."""
    import forecast as fc

    sql = q.transactions_run_rate(con)
    ref = fc.build_target(pd.read_parquet(os.path.join(_DATA, "ventes_ancien.parquet")))

    assert sql.name == ref.name == "tx12"
    assert sql.index.equals(ref.index)                  # même index, même dtype
    assert str(sql.index.dtype) == "datetime64[ns]"
    _same(sql.values, ref.values, name="tx12")


def test_macro_frame_matches_macro_series(con):
    """`macro_frame` (consommé par les graphiques du rapport PDF) et `macro_series`
    (consommé par l'export JSON) doivent décrire exactement la même série."""
    col = "OAT_10ans"
    fr = q.macro_frame(con, col)
    rw = q.macro_series(con, col, digits=12)
    assert len(fr) == len(rw)
    _same(fr["value"], [r["value"] for r in rw], name="macro_frame vs macro_series")
    df = pd.read_parquet(os.path.join(_DATA, "macro.parquet")).dropna(subset=[col])
    _same(fr["value"], df[col].values, name="macro_frame vs pandas dropna")


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
