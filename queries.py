"""Couche de calcul SQL partagée — DuckDB comme moteur unique des deux apps.

L'entrepôt `housing_data/` expose déjà les datasets en Parquet typé avec une vue SQL
DuckDB par dataset (zéro serveur). Ce module est la **porte d'entrée unique des
agrégations** pour toutes les surfaces (`app.py` Streamlit, `web/export/web_export.py`,
`report.py`) : il ouvre cette connexion et fait faire au moteur ce qui était auparavant
refait à la main en pandas — GROUP BY, cumuls glissants (fonctions de fenêtre), YoY par
LAG, z-score, capacité d'emprunt, jointures, filtrage des NULL. Définir chaque agrégation
UNE fois ici garantit que les deux apps affichent exactement les mêmes chiffres.

Ce qui reste hors de ce module (par nature) : les **modèles statistiques** (OLS de
`forecast.py`) restent en numpy — DuckDB n'est pas un moteur de régression — mais leurs
séries d'entrée sont produites ici. Les helpers de post-agrégation `analysis.calculate_kpis`
/ `momentum_metrics` / `build_market_commentary` restent réutilisés tels quels (ils
opèrent sur de petites frames déjà agrégées).

Deux formes de sortie :
  * `rows(...)`  -> list[dict] directement sérialisable (NULL SQL -> None, jamais de
    NaN, dates déjà formatées par strftime côté SQL) ;
  * `frame(...)` -> DataFrame, pour les helpers partagés avec `app.py`/`report.py`
    (`analysis.calculate_kpis` / `momentum_metrics`) qu'on réutilise tels quels.

Les cumuls glissants SQL répliquent exactement `pandas.rolling(w, min_periods=w).sum()` :
fenêtre sur les w dernières LIGNES, NULL tant qu'elle n'est pas pleine.
"""
from __future__ import annotations

import os
import sys

import pandas as pd

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import housing_data as hd            # noqa: E402
from data_manager import DataManager  # noqa: E402

DATA_DIR = os.path.join(_REPO_ROOT, "data")


# ============================ connexion ===========================================
def open_warehouse(refresh: bool = True):
    """Connexion DuckDB (une vue par dataset) sur les Parquet de `data/`.

    `refresh=True` lance d'abord `DataManager.load_or_generate_all()`, qui reconstruit
    les CSV manquants et met à jour les miroirs Parquet validés : c'est le seul moment
    où pandas voit les données brutes. Tout le reste passe par SQL. Les appelants qui ont
    déjà rafraîchi les données (l'app Streamlit via son `@st.cache_resource`) passent
    `refresh=False` pour rouvrir une connexion sur les Parquet déjà à jour.
    """
    if refresh:
        DataManager().load_or_generate_all()
    return hd.connect(DATA_DIR)


# ============================ exécution ===========================================
def rows(con, sql: str, params=(), digits: dict | None = None) -> list[dict]:
    """Exécute `sql` et renvoie des dicts JSON-ready.

    `digits` = {clé: nb_décimales} applique l'arrondi côté Python : `round()` SQL et
    `round()` Python n'ont pas la même règle de départage (moitié-vers-le-haut vs
    banquier), et l'arrondi est du formatage, pas de l'agrégation.
    """
    cur = con.execute(sql, list(params))
    cols = [d[0] for d in cur.description]
    out = []
    for rec in cur.fetchall():
        row = dict(zip(cols, rec))
        for k, v in row.items():
            if isinstance(v, float) and v != v:   # NaN éventuel -> null JSON valide
                row[k] = None
        if digits:
            for k, nd in digits.items():
                if row.get(k) is not None:
                    row[k] = round(row[k], nd)
        out.append(row)
    return out


def frame(con, sql: str, params=()) -> pd.DataFrame:
    """Résultat en DataFrame, `Date` normalisée en datetime64[ns] pour les helpers
    d'`analysis.py` (qui comparent des Timestamp et appliquent des DateOffset)."""
    df = con.execute(sql, list(params)).df()
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
    return df


def scalar(con, sql: str, params=()):
    """Première colonne de la première ligne, ou None si le résultat est vide."""
    r = con.execute(sql, list(params)).fetchone()
    return r[0] if r else None


# ============================ cumuls glissants ====================================
def _roll_exprs(cols, windows) -> str:
    """Colonnes `<col>_<w>M` = somme glissante sur w lignes, NULL si fenêtre incomplète
    (équivalent de min_periods=w). Le partitionnement éventuel vit dans `_window_clause`."""
    return ", ".join(
        f'CASE WHEN COUNT("{c}") OVER w{w} = {w} THEN SUM("{c}") OVER w{w} END AS "{c}_{w}M"'
        for c in cols for w in windows)


def _window_clause(windows, partition: str | None = None) -> str:
    part = f'PARTITION BY "{partition}" ' if partition else ""
    return "WINDOW " + ", ".join(
        f"w{w} AS ({part}ORDER BY Date ROWS BETWEEN {w - 1} PRECEDING AND CURRENT ROW)"
        for w in windows)


def _row_filter(types=None, years=None, category_col: str = "Type"):
    """Clause WHERE + paramètres communs aux agrégats : filtre de catégorie et/ou de période.

    `category_col` est la colonne qui porte la catégorie du dataset : "Type" pour
    sitadel/ventes_ancien, mais "Product" pour sales, "Serie" pour company_sales et
    "Company" pour revenue. Sans ce paramètre, seuls les deux premiers datasets étaient
    filtrables côté SQL et les autres restaient agrégés en pandas.

    `years=(min, max)` reproduit le `_filter_years` d'app.py (bornes incluses, sur
    l'ANNÉE civile), appliqué avant le GROUP BY comme le faisait le filtrage pandas.
    """
    clauses, params = [], []
    if types:
        clauses.append(f'"{category_col}" IN (' + ", ".join(["?"] * len(types)) + ")")
        params += list(types)
    if years:
        clauses.append("year(Date) BETWEEN ? AND ?")
        params += [int(years[0]), int(years[1])]
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), params


def _select_with_windows(value_cols, windows):
    """Projection + clause WINDOW, en tolérant `windows=()` (agrégat mensuel nu, sans
    cumul glissant : c'est le cas des barres de comparaison mois-par-mois d'app.py, où
    une clause WINDOW vide produirait du SQL invalide)."""
    quoted = ", ".join(f'"{c}"' for c in value_cols)
    if not windows:
        return quoted, ""
    return f"{quoted}, {_roll_exprs(value_cols, windows)}", _window_clause(windows)


def monthly(con, dataset: str, value_cols, windows=(12,), types=None,
            years=None, category_col: str = "Type") -> pd.DataFrame:
    """Série mensuelle nationale d'un dataset + ses cumuls glissants, en UN passage SQL.

    Remplace la chaîne `analysis.aggregate_* -> calculate_rolling_12m -> calculate_rolling`,
    qui recopiait le DataFrame à chaque étape. `types` filtre la colonne de catégorie côté
    SQL (aucune ligne inutile ne remonte) — `category_col` dit laquelle : "Type" par
    défaut, mais "Product" (sales), "Serie" (company_sales) ou "Company" (revenue).
    `years=(min, max)` restreint à une période, pour les vues où l'agrégat lui-même est
    borné par le slicer d'années.

    Attention : borner par `years` borne AUSSI les fenêtres glissantes. Les vues qui
    veulent un cumul 12 mois correct en début de période doivent agréger sur l'historique
    complet puis découper à l'affichage — c'est ce que fait app.py.
    """
    sums = ", ".join(f'SUM("{c}")::DOUBLE AS "{c}"' for c in value_cols)
    where, params = _row_filter(types, years, category_col)
    projection, window = _select_with_windows(value_cols, windows)
    return frame(con, f"""
        WITH mensuel AS (
            SELECT Date, {sums} FROM "{dataset}"{where} GROUP BY Date
        )
        SELECT Date, {projection}
        FROM mensuel
        {window}
        ORDER BY Date
    """, params)


def monthly_by_group(con, dataset: str, groups: dict, value_cols, windows=(12,)) -> pd.DataFrame:
    """Idem `monthly`, mais pour plusieurs regroupements de types **en une seule requête**.

    `groups` = {libellé: [types...]}. La table de correspondance est jointe au dataset,
    un même type pouvant alimenter plusieurs groupes (l'individuel pur compte aussi dans
    l'individuel total) ; les fenêtres sont partitionnées par groupe. Une passe SQL là où
    le code faisait un `aggregate + rolling` complet par groupe et par métrique.

    Renvoie un DataFrame long [Groupe, Date, <cols>, <cols>_<w>M].
    """
    pairs, params = [], []
    for label, types in groups.items():
        for t in types:
            pairs.append("(?, ?)")
            params += [label, t]
    quoted = ", ".join(f'"{c}"' for c in value_cols)
    sums = ", ".join(f'SUM(s."{c}")::DOUBLE AS "{c}"' for c in value_cols)
    return frame(con, f"""
        WITH g(Groupe, Type) AS (VALUES {", ".join(pairs)}),
        mensuel AS (
            SELECT g.Groupe, s.Date, {sums}
            FROM "{dataset}" s JOIN g ON s.Type = g.Type
            GROUP BY g.Groupe, s.Date
        )
        SELECT Groupe, Date, {quoted}, {_roll_exprs(value_cols, windows)}
        FROM mensuel
        {_window_clause(windows, "Groupe")}
        ORDER BY Groupe, Date
    """, params)


# ============================ macro ===============================================
def macro_data_columns(con) -> set:
    """Indicateurs macro effectivement renseignés (au moins une valeur non NULL).

    Remplace les gardes `col in df.columns and df[col].notna().any()` : un seul
    aller-retour SQL au lieu d'un scan pandas par colonne.
    """
    cols = [r[0] for r in con.execute('DESCRIBE "macro"').fetchall() if r[0] != "Date"]
    if not cols:
        return set()
    counts = con.execute(
        "SELECT " + ", ".join(f'COUNT("{c}")' for c in cols) + ' FROM "macro"').fetchone()
    return {c for c, n in zip(cols, counts) if n}


def macro_series(con, col: str, digits: int = 4, key: str = "value") -> list[dict]:
    """Points [{date, <key>}] d'un indicateur, NULL filtrés côté SQL."""
    return rows(con, f"""
        SELECT strftime(Date, '%Y-%m-%d') AS date, "{col}" AS "{key}"
        FROM "macro" WHERE "{col}" IS NOT NULL ORDER BY Date
    """, digits={key: digits})


def macro_frame(con, col: str, key: str = "value") -> pd.DataFrame:
    """Variante DataFrame de `macro_series` : [Date, <key>], NULL filtrés côté SQL.
    Pour les consommateurs qui tracent la série (matplotlib du rapport PDF) plutôt que
    de la sérialiser en JSON."""
    return frame(con, f"""
        SELECT Date, "{col}" AS "{key}"
        FROM "macro" WHERE "{col}" IS NOT NULL ORDER BY Date
    """)


def macro_rolling(con, dropna_col: str, roll_cols, window: int = 12,
                  keep_cols=()) -> pd.DataFrame:
    """Frame macro restreinte aux lignes où `dropna_col` est renseigné, avec un cumul
    glissant `<col>_cum{window}` par colonne de `roll_cols`.

    Réplique exactement `df.dropna(subset=[dropna_col])[col].rolling(window).sum()` :
    la fenêtre porte sur les LIGNES restantes après le filtre (pas sur des mois
    calendaires), et vaut NULL tant qu'elle n'est pas pleine. Contrairement à
    `rolling_sum()`, les lignes à cumul NULL sont CONSERVÉES et les colonnes brutes
    aussi — les vues qui superposent des barres mensuelles et une courbe cumulée ont
    besoin des deux sur le même axe temporel.
    """
    cols = list(dict.fromkeys([dropna_col, *roll_cols, *keep_cols]))
    quoted = ", ".join(f'"{c}"' for c in cols)
    rolls = ", ".join(
        f'CASE WHEN COUNT("{c}") OVER w = {window} THEN SUM("{c}") OVER w END '
        f'AS "{c}_cum{window}"' for c in roll_cols)
    return frame(con, f"""
        SELECT Date, {quoted}, {rolls}
        FROM "macro"
        WHERE "{dropna_col}" IS NOT NULL
        WINDOW w AS (ORDER BY Date ROWS BETWEEN {window - 1} PRECEDING AND CURRENT ROW)
        ORDER BY Date
    """)


def macro_last_and_year_ago(con, col: str, months: int = 12):
    """(dernière valeur, dernière valeur d'au moins `months` mois plus tôt) — la
    comparaison glissante des cartes de synthèse, faite par SQL sur deux LIMIT 1."""
    r = con.execute(f"""
        WITH s AS (SELECT Date, "{col}" AS v FROM "macro" WHERE "{col}" IS NOT NULL),
             dernier AS (SELECT Date, v FROM s ORDER BY Date DESC LIMIT 1)
        SELECT (SELECT v FROM dernier) AS last,
               (SELECT v FROM s
                 WHERE Date <= (SELECT Date FROM dernier) - INTERVAL {int(months)} MONTH
                 ORDER BY Date DESC LIMIT 1) AS prev
    """).fetchone()
    return (r[0], r[1]) if r else (None, None)


def capacity_expr(rate_expr: str, years: int) -> str:
    """Expression SQL du facteur de capacité d'emprunt (valeur actuelle d'une mensualité
    unitaire sur `years` ans) — transcription de `_borrow_capacity_factor` d'app.py."""
    n = years * 12
    i = f"(({rate_expr}) / 1200.0)"
    return f"CASE WHEN {i} > 0 THEN (1.0 - POWER(1.0 + {i}, -{n})) / {i} ELSE {float(n)} END"


def capacity_2015_base(con, years: int, rate_col: str = "Credit_Logement_Taux_Interet"):
    """Facteur de capacité moyen de 2015 (base 100 des indices d'accessibilité). Replie
    sur la première capacité disponible si 2015 n'a aucune observation (même repli que
    l'ancien code pandas)."""
    cap15 = scalar(con, f"""
        SELECT AVG({capacity_expr(rate_col, years)}) FROM "macro"
        WHERE "{rate_col}" IS NOT NULL AND year(Date) = 2015
    """)
    if cap15:
        return cap15
    return scalar(con, f"""
        SELECT {capacity_expr(rate_col, years)} FROM "macro"
        WHERE "{rate_col}" IS NOT NULL ORDER BY Date LIMIT 1
    """)


def capacity_accessibility(con, years: int, price_col: str = "Prix_Ancien_Ensemble",
                            rate_col: str = "Credit_Logement_Taux_Interet") -> pd.DataFrame:
    """DataFrame [Date, capidx, prix, access] : capacité d'emprunt indexée (base 100 =
    moyenne 2015) et indice d'accessibilité (capacité ÷ prix), pour une durée de prêt
    donnée. Traduit `_borrow_capacity_factor` (numpy vectorisé sur tout l'historique) +
    la moyenne-filtre 2015 en SQL : l'AVG() et le calcul par ligne sont faits par DuckDB.
    """
    cap15 = capacity_2015_base(con, years, rate_col)
    if not cap15:
        return pd.DataFrame(columns=["Date", "capidx", "prix", "access"])
    capidx = f"{capacity_expr(rate_col, years)} / {cap15} * 100"
    return frame(con, f"""
        SELECT Date, ({capidx}) AS capidx, "{price_col}" AS prix,
               ({capidx}) / "{price_col}" * 100 AS access
        FROM "macro"
        WHERE "{rate_col}" IS NOT NULL AND "{price_col}" IS NOT NULL
        ORDER BY Date
    """)


# ============================ transformations génériques ==========================
def series_with_lag_pct(con, col: str, lag: int = 4, digits: int = 3,
                         table: str = "macro") -> list[dict]:
    """Niveaux + variation en % vs `lag` observations valides plus tôt, sur les lignes
    non NULL de `col` — équivalent SQL de `serie.dropna().pct_change(lag) * 100`
    (le décalage porte sur des lignes déjà filtrées, pas sur des mois calendaires : pour
    une série trimestrielle avec lag=4, c'est bien un YoY)."""
    return rows(con, f"""
        WITH s AS (SELECT Date, "{col}" AS v FROM "{table}" WHERE "{col}" IS NOT NULL)
        SELECT strftime(Date, '%Y-%m-%d') AS date,
               (v - LAG(v, {lag}) OVER (ORDER BY Date))
                 / LAG(v, {lag}) OVER (ORDER BY Date) * 100 AS value
        FROM s
        QUALIFY value IS NOT NULL
        ORDER BY Date
    """, digits={"value": digits})


def rolling_sum(con, col: str, window: int = 12, table: str = "macro",
                 digits: int = 3) -> list[dict]:
    """Cumul glissant sur `window` lignes valides de `col`, NULL filtrées avant la
    fenêtre — équivalent SQL de `serie.dropna().rolling(window).sum()`."""
    return rows(con, f"""
        WITH s AS (SELECT Date, "{col}" AS v FROM "{table}" WHERE "{col}" IS NOT NULL)
        SELECT strftime(Date, '%Y-%m-%d') AS date,
               CASE WHEN COUNT(v) OVER w = {window} THEN SUM(v) OVER w END AS value
        FROM s
        WINDOW w AS (ORDER BY Date ROWS BETWEEN {window - 1} PRECEDING AND CURRENT ROW)
        QUALIFY value IS NOT NULL
        ORDER BY Date
    """, digits={"value": digits})


def macro_zscore(con, col: str, digits: int = 4) -> list[dict]:
    """Série centrée-réduite (z-score, écart-type d'échantillon comme `pandas.Series.std`)
    sur les valeurs non NULL de `col`. AVG/STDDEV_SAMP sont calculés par DuckDB en un
    seul passage plutôt que par un `.mean()`/`.std()` pandas séparé."""
    r = con.execute(f"""
        SELECT AVG("{col}"), STDDEV_SAMP("{col}") FROM "macro" WHERE "{col}" IS NOT NULL
    """).fetchone()
    mu, sd = (r or (None, None))
    if not sd:
        return []
    return rows(con, f"""
        SELECT strftime(Date, '%Y-%m-%d') AS date, (("{col}" - {mu}) / {sd}) AS value
        FROM "macro" WHERE "{col}" IS NOT NULL ORDER BY Date
    """, digits={"value": digits})
