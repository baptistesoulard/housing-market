"""Couche 2 bis — composition du moteur de calcul, **sans HTTP**.

Ce module n'importe ni Flask ni Streamlit : c'est l'invariant central du patron « API
HTTP locale ». Il se teste et s'exécute serveur éteint (`python -c "from api import
engine; print(engine.rate_model())"`), et `api/routes.py` ne fait que le traduire en JSON.

Il n'y a **aucune logique métier ici** non plus : les calculs vivent dans `queries.py`
(agrégations SQL) et `forecast.py` (OLS, backtest, scénarios). Ce module ne fait que trois
choses qu'aucun des deux ne doit porter :

1. tenir la connexion DuckDB et les frames pandas d'entrée, ouvertes une fois ;
2. mémoriser l'ajustement des modèles, coûteux (recherche en grille des décalages), pour
   qu'un déplacement de curseur ne le relance pas ;
3. convertir les sorties (Timestamp, numpy.float64, DataFrame) en types JSON-sérialisables,
   **avec un format de date figé** — voir `_iso`.

Concurrence : un serveur HTTP sert plusieurs requêtes en parallèle, chacune dans son
thread. Les agrégations passent par `queries.py`, qui isole déjà chaque `execute()` dans
son propre curseur (`queries._cur`) — ne jamais contourner cette règle ici. L'état ajouté
par ce module (le cache des modèles) est protégé par un verrou : sans lui, deux requêtes
simultanées lanceraient deux recherches en grille identiques.
"""
from __future__ import annotations

import threading

import numpy as np
import pandas as pd

import forecast as fc
import queries as q
from data_manager import DataManager

# Fenêtre d'entraînement du backtest — même valeur que `app.py:_FORECAST_SPLIT`. Les deux
# surfaces doivent afficher les mêmes chiffres, donc la constante est partagée par copie
# explicite plutôt que par import croisé (l'API ne doit pas dépendre de l'app Streamlit).
FORECAST_SPLIT = "2021-12-01"

# Grilles de décalage exposées au curseur du front. Bornes identiques à celles de l'onglet
# Streamlit « Vérifier les décalages retenus », pour que les deux donnent le même R².
LAG_GRIDS = {
    "rate": ("kr", "Credit_Logement_Taux_Interet", range(0, 13)),
    "intentions": ("ki", "Intentions_Achat_Logement", range(0, 19)),
    "unemployment": ("kc", "Taux_Chomage_BIT", range(0, 13)),
}

_REQUIRED_MACRO = {"OAT_10ans", "Euribor_3M", "Credit_Logement_Taux_Interet",
                   "Intentions_Achat_Logement", "Taux_Chomage_BIT"}

_lock = threading.Lock()
_state: dict = {}


class EngineUnavailable(RuntimeError):
    """Les séries d'entrée ne permettent pas de calibrer le modèle (macro incomplète)."""


# ------------------------------------------------------------------ sérialisation
def _iso(ts) -> str:
    """Date en `YYYY-MM-DD`, **toujours**.

    Le format des clés de date est figé ici et vérifié par `tests/test_api_contract.py`.
    C'est le piège que le patron signale nommément : une requête qui réussit et renvoie
    zéro ligne parce qu'un côté écrit `2025-03` et l'autre `2025-03-01`.
    """
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def _num(v):
    """numpy.float64 → float, NaN → None (JSON n'a pas de NaN)."""
    if v is None:
        return None
    f = float(v)
    return None if np.isnan(f) else f


def _series(frame: pd.DataFrame, date_col: str, cols: dict[str, str]) -> list[dict]:
    """DataFrame → [{date, <clés>}], dates ISO et valeurs JSON-propres."""
    out = []
    for _, r in frame.iterrows():
        row = {"date": _iso(r[date_col])}
        row.update({out_key: _num(r[src]) for out_key, src in cols.items()})
        out.append(row)
    return out


# ------------------------------------------------------------------ état partagé
def _load():
    """Connexion + frames + modèles ajustés, calculés une seule fois."""
    with _lock:
        if _state:
            return _state
        con = q.open_warehouse()
        frames = DataManager().read_frames()
        macro = frames[2]
        tx12 = q.transactions_run_rate(con)

        if tx12.dropna().empty or not _REQUIRED_MACRO.issubset(set(macro.columns)):
            raise EngineUnavailable(
                "Séries macro incomplètes — le modèle ne peut pas être calibré. "
                f"Colonnes manquantes : {sorted(_REQUIRED_MACRO - set(macro.columns))}")

        rate = fc.fit_rate_model(macro)
        lags = fc.search_tx_lags(macro, tx12, split=FORECAST_SPLIT)
        tx = fc.fit_tx_model(macro, tx12, split=FORECAST_SPLIT, **lags)

        _state.update(con=con, macro=macro, tx12=tx12,
                      rate=rate, lags=lags, tx=tx)
        return _state


def reset():
    """Vide l'état (tests, ou données rafraîchies sous le serveur)."""
    with _lock:
        _state.clear()


def _band():
    """La bande calibrée, ou None si l'archive n'a pas encore été étalonnée.

    Import tardif : `forecast_archive` n'est pas une dépendance du moteur de calcul, et
    l'absence de la table ne doit jamais empêcher une projection — elle retombe alors sur
    la bande de largeur constante.
    """
    try:
        import forecast_archive as fa
        return fa.read_band()
    except Exception:                                   # noqa: BLE001
        return None


# ------------------------------------------------------------------ questions métier
def health() -> dict:
    """L'API répond-elle, et sur quelles données ?"""
    try:
        s = _load()
        obs = s["tx"]["frame"]
        return {
            "status": "ok",
            "datasets": sorted(DataManager().dataset_sources().items()),
            "transactions_last_month": _iso(obs["Date"].iloc[-1]),
            "macro_last_month": _iso(pd.to_datetime(s["macro"]["Date"]).max()),
            "forecast_split": FORECAST_SPLIT,
        }
    except EngineUnavailable as e:
        return {"status": "degraded", "detail": str(e)}


def rate_model() -> dict:
    """Étage 1 : le taux de crédit expliqué par l'OAT 10 ans et l'Euribor 3 mois."""
    s = _load()
    rm = s["rate"]
    b = [float(x) for x in rm["beta"]]
    # `lag` : le délai de répercussion des taux de marché sur le barème des banques, et
    # `projected` : les mois à venir que les taux de marché DÉJÀ publiés déterminent, sans
    # aucune hypothèse. Voir `forecast.rate_path`.
    path = fc.rate_path(s["macro"], rm["beta"], rm["lag"])
    return {
        "r2": _num(rm["r2"]),
        "rmse": _num(rm["rmse"]),
        "lag": int(rm["lag"]),
        # Un seul coefficient de marché depuis le retrait de l'Euribor : `marche` reste
        # exposé sous ce nom, le front et les tests le lisant ainsi, mais il ne somme plus
        # rien — il EST le coefficient de l'OAT, et se lit donc tel quel.
        "coefficients": {"intercept": b[0], "oat": b[1], "marche": b[1]},
        # `rate` = la valeur publiée, recalée sur le dernier taux observé ; `modelled` = la
        # sortie brute du même modèle, qui prolonge la courbe d'ajustement sans rupture.
        "projected": [{"date": _iso(r.Date), "rate": _num(r.taux),
                       "modelled": _num(r.modelled), "source": _iso(r.source)}
                      for r in path.itertuples()],
        "series": _series(rm["frame"], "Date", {"observed": "obs", "modelled": "fit"}),
    }


def transactions_model() -> dict:
    """Étage 2 : les ventes anciennes (cumul 12 mois) et le backtest hors échantillon."""
    s = _load()
    tm, bt = s["tx"], s["tx"]["backtest"]
    b = [float(x) for x in tm["beta"]]
    return {
        "r2": _num(tm["r2"]),
        "rmse": _num(tm["rmse"]),
        "lags": {k: int(v) for k, v in s["lags"].items()},
        "coefficients": {"intercept": b[0], "rate": b[1], "intentions": b[2],
                         "unemployment": b[3]},
        "backtest": {
            "split": bt["split"],
            "n_test": int(bt["n_test"]),
            "mape": _num(bt.get("mape")),
            "rmse": _num(bt.get("rmse")),
            "series": (_series(bt["frame"], "Date", {"observed": "obs", "predicted": "pred"})
                       if "frame" in bt else []),
        },
        "series": _series(tm["frame"], "Date", {"observed": "obs", "fitted": "fit"}),
    }


def projection(horizon: int = 18) -> dict:
    """Projection à horizon : les décalages déjà observés fixent les mois à venir."""
    s = _load()
    bt = s["tx"]["backtest"]
    sigma = float(bt["rmse"]) if "rmse" in bt else float(s["tx"]["rmse"])
    # Recalage sur le dernier point observé, et bande calibrée sur les erreurs passées :
    # les deux viennent de `forecast_archive`, qui est le juge du modèle. La projection
    # publiée est donc corrigée par sa propre feuille de match, ce qui est le seul emploi
    # honnête d'une archive de prévisions.
    path = fc.forecast_path(s["macro"], s["tx12"], s["lags"], s["tx"]["beta"], sigma,
                            horizon=horizon, anchor=fc.anchor_of(s["tx"], s["tx12"]),
                            band=_band())
    if path is None or path.empty:
        return {"available": False, "reason": "lags_too_short", "series": []}
    rows = _series(path, "Date", {"predicted": "pred", "lo": "lo", "hi": "hi"})
    for row, assured in zip(rows, path["assured"]):
        row["assured"] = bool(assured)
    last_obs = _num(s["tx12"].dropna().iloc[-1])
    end = _num(path["pred"].iloc[-1])
    return {
        "available": True,
        "horizon_months": len(path),
        "assured_months": int(path["assured"].sum()),
        "sigma": sigma,
        "last_observed": last_obs,
        "end_value": end,
        "end_change_pct": (end / last_obs - 1) * 100 if last_obs else None,
        "series": rows,
    }


def lag_sensitivity(predictor: str) -> dict:
    """Sensibilité du modèle au décalage d'UN prédicteur, les deux autres figés.

    Renvoie la courbe R² **entière** plutôt qu'un point : le front peut alors déplacer son
    curseur sans un aller-retour réseau par cran, ce qui est le seul moyen d'avoir un
    curseur fluide sur une API distante.
    """
    if predictor not in LAG_GRIDS:
        raise KeyError(predictor)
    s = _load()
    key, macro_col, grid = LAG_GRIDS[predictor]
    retained = int(s["lags"][key])

    curve = []
    for lag in grid:
        trial = dict(s["lags"])
        trial[key] = int(lag)
        fit = fc.fit_tx_model(s["macro"], s["tx12"], split=FORECAST_SPLIT, **trial)
        curve.append({"lag": int(lag), "r2": _num(fit["r2"])})

    pred_frame = s["macro"][["Date", macro_col]].dropna(subset=[macro_col]).copy()
    pred_frame["Date"] = pd.to_datetime(pred_frame["Date"])
    return {
        "predictor": predictor,
        "macro_column": macro_col,
        "retained_lag": retained,
        "retained_r2": _num(s["tx"]["r2"]),
        "curve": curve,
        "predictor_series": _series(pred_frame, "Date", {"value": macro_col}),
        "transactions_series": _series(s["tx"]["frame"], "Date", {"value": "obs"}),
    }


def scenario_baseline() -> dict:
    """Valeurs actuelles réelles servant d'ancrage aux scénarios."""
    s = _load()
    mi = s["macro"].set_index("Date").sort_index()
    intent = mi["Intentions_Achat_Logement"].dropna()
    mu, sd = float(intent.mean()), float(intent.std())
    last = float(intent.iloc[-1])
    return {
        "oat": _num(mi["OAT_10ans"].dropna().iloc[-1]),
        "euribor": _num(mi["Euribor_3M"].dropna().iloc[-1]),
        "rate_now": _num(mi["Credit_Logement_Taux_Interet"].dropna().iloc[-1]),
        "intentions": last,
        "intentions_mean": mu,
        "intentions_std": sd,
        "intentions_z": (last - mu) / sd if sd > 0 else 0.0,
        "unemployment": _num(mi["Taux_Chomage_BIT"].dropna().iloc[-1]),
        "tx_now": _num(s["tx12"].dropna().iloc[-1]),
    }


def run_scenario(oat=None, euribor=None, unemployment=None, intentions_z=None) -> dict:
    """Effet à terme d'un jeu d'hypothèses macro sur les transactions.

    Approche en écart, ancrée sur les valeurs actuelles réelles : les sensibilités
    estimées sont appliquées aux VARIATIONS, pas aux niveaux (le modèle de taux
    sur-prédit le niveau courant, cf. `forecast.scenario`).
    """
    s = _load()
    base = scenario_baseline()
    z = base["intentions_z"] if intentions_z is None else float(intentions_z)
    # `euribor` reste accepté pour ne pas casser les appelants, mais n'entre plus dans le
    # calcul du taux : voir `forecast.RATE_DRIVER`.
    scen = {
        "oat": base["oat"] if oat is None else float(oat),
        "euribor": base["euribor"] if euribor is None else float(euribor),
        "chom": base["unemployment"] if unemployment is None else float(unemployment),
        "intent": base["intentions_mean"] + z * base["intentions_std"],
    }
    res = fc.scenario(s["rate"]["beta"], s["tx"]["beta"],
                      {"oat": base["oat"], "euribor": base["euribor"],
                       "intent": base["intentions"], "chom": base["unemployment"],
                       "rate_now": base["rate_now"], "tx_now": base["tx_now"]},
                      scen)
    tx0 = base["tx_now"]
    return {
        "baseline": base,
        "assumptions": {"oat": scen["oat"], "euribor": scen["euribor"],
                        "unemployment": scen["chom"], "intentions_z": z,
                        "intentions": scen["intent"]},
        "rate": _num(res["rate"]),
        "rate_change": _num(res["d_rate"]),
        "transactions": _num(res["tx"]),
        "transactions_change": _num(res["d_tx"]),
        "transactions_change_pct": (res["d_tx"] / tx0 * 100) if tx0 else None,
    }


def transactions_run_rate() -> dict:
    """La série pilote elle-même : ventes anciennes en cumul 12 mois (IGEDD).

    Exposée parce que le front calcule EN LOCAL l'élasticité vers les ventes société
    importées — celles-ci ne quittent jamais le navigateur, donc leur régression ne peut
    pas se faire ici (voir `web/README.md`, « ventes société »).
    """
    s = _load()
    ser = s["tx12"].dropna()
    return {"series": [{"date": _iso(d), "value": _num(v)} for d, v in ser.items()]}


def permits_run_rate(housing_type: str, metric: str = "Permis") -> dict:
    """Permis (ou mises en chantier) en cumul 12 mois, pour un type de logement.

    Même cadence que la série de transactions, pour que les deux drivers amont soient
    comparés à armes égales côté front.
    """
    if metric not in ("Permis", "MisesEnChantier"):
        raise ValueError(metric)
    s = _load()
    df = q.monthly(s["con"], "sitadel", [metric], windows=(12,), types=[housing_type])
    col = f"{metric}_12M"
    df = df.dropna(subset=[col])
    return {
        "housing_type": housing_type,
        "metric": metric,
        "series": _series(df, "Date", {"value": col}),
    }


def housing_types() -> dict:
    """Les types de logement disponibles, pour peupler le sélecteur du front."""
    s = _load()
    rows = q.rows(s["con"], 'SELECT DISTINCT Type FROM sitadel ORDER BY Type')
    return {"types": [r["Type"] for r in rows]}
