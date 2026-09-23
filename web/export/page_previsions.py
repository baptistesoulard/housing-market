"""Page « Prévision & Scénarios » — l'export statique de ce que `api.engine` calcule.

Le modèle n'est PAS réajusté ici : `api.engine` porte l'unique implémentation, et ce
module ne fait qu'assembler ses sorties, le verdict partagé (`verdict.py`) et les repères
datés (`reperes.py`).
"""
from __future__ import annotations

import pandas as pd

from commun import iso_mois
from reperes import BENCHMARK_FNAIM, BENCHMARK_TAUX, REFUTATIONS
from verdict import HORIZON_MIN, blocs_horizon, fiabilite_regime, partage

from api import engine                          # noqa: E402  (moteur de prévision, sans Flask)


def _benchmark(projection: dict) -> dict | None:
    """Le repère externe, aligné sur le mois où il est comparable — décembre, et lui seul.

    Renvoie None si le mois cible n'est plus dans la projection : un repère qu'on ne peut
    plus confronter n'a rien à faire sur un graphique.
    """
    cible = pd.Timestamp(BENCHMARK_FNAIM["mois_cible"])
    point = next((p for p in projection.get("series", [])
                  if pd.Timestamp(p["date"]) == cible), None)
    if point is None:
        return None
    milieu = (BENCHMARK_FNAIM["lo"] + BENCHMARK_FNAIM["hi"]) / 2
    return {
        **{k: v for k, v in BENCHMARK_FNAIM.items() if k != "mois_cible"},
        "date": iso_mois(cible),
        "notre_prevision": int(round(point["predicted"])),
        "dans_la_fourchette": bool(BENCHMARK_FNAIM["lo"] <= point["predicted"]
                                   <= BENCHMARK_FNAIM["hi"]),
        "ecart_au_milieu_pct": round((point["predicted"] / milieu - 1) * 100, 1),
    }


def build_previsions(con, frames: dict) -> dict:
    """Page « Prévision & Scénarios » — export statique de ce que l'API HTTP calculerait.

    Réutilise `api.engine` TEL QUEL plutôt que de rejouer l'ajustement des modèles ici :
    ce module n'importe pas Flask et s'exécute déjà serveur éteint (voir son en-tête),
    exactement l'invariant qui permet de l'appeler depuis un script d'export. Ça garantit
    que le site statique et une instance de l'API future affichent EXACTEMENT les mêmes
    chiffres — une seule implémentation du modèle, pas deux qui pourraient diverger.

    `engine.reset()` vide l'état mis en cache (connexion, modèles ajustés) avant de
    commencer : sans lui, un import antérieur d'`api.engine` dans le même process (pas le
    cas ici, mais explicite) servirait un ajustement d'une exécution précédente.
    Volontairement, ce builder ouvre SA PROPRE connexion DuckDB via `engine._load()`
    plutôt que de réutiliser `con`/`frames` : `load_or_generate_all()` est déjà rejoué une
    seconde fois par ce chemin, mtime-aware donc bon marché quand rien n'a changé — le
    prix à payer pour ne pas dupliquer l'assemblage (rate/tx/projection/scénarios/lags)
    que `api.engine` porte déjà.

    Chaque courbe de sensibilité (une par prédicteur) est pré-calculée ici : le curseur
    du front n'a donc plus de requête réseau à faire à chaque changement de prédicteur,
    seulement une lecture dans le JSON déjà chargé — mieux que ce que l'API elle-même
    offrait (un aller-retour par changement de prédicteur, aucun par déplacement du
    curseur puisque la courbe entière arrivait déjà d'un coup).
    """
    engine.reset()
    try:
        payload = {
            "available": True,
            "health": engine.health(),
            "rate": engine.rate_model(),
            "transactions": engine.transactions_model(),
            "projection": engine.projection(),
            "lag_sensitivity": {p: engine.lag_sensitivity(p) for p in engine.LAG_GRIDS},
            "scenario_baseline": engine.scenario_baseline(),
        }
    except engine.EngineUnavailable as e:
        payload = {"available": False, "reason": str(e)}
    if payload["available"]:
        payload["verdict"] = partage(con)
        payload["benchmark"] = _benchmark(payload["projection"])
    if payload["available"]:
        _hb = blocs_horizon(con)
        payload["horizon_blocks"] = _hb["blocks"]
        payload["crossover_horizon"] = _hb["crossover"]
        # Au MÊME horizon que le verdict : ce bloc est un avertissement sur le chiffre
        # de tête, pas une statistique indépendante. Deux horizons différents
        # feraient dire à l'un ce que l'autre ne dit pas.
        _v = payload.get("verdict") or {}
        payload["regime"] = fiabilite_regime(con, _v.get("horizon", HORIZON_MIN))
    payload["refutations"] = REFUTATIONS
    payload["benchmark_taux"] = BENCHMARK_TAUX
    engine.reset()  # ne laisse pas la connexion ouverte pour le reste du script
    return payload
