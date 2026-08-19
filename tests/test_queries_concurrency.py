"""Régression : la couche SQL doit rester juste quand PLUSIEURS threads partagent une
même connexion DuckDB.

Pourquoi ce test existe : `app.py` met sa connexion en cache avec `@st.cache_resource`,
donc un seul objet connexion sert toutes les sessions Streamlit — et chaque session
s'exécute dans son propre thread. Un `DuckDBPyConnection` porte le résultat de son dernier
`execute()` : deux threads qui l'utilisent simultanément se volent leur jeu de résultats.
Le symptôme n'est pas une erreur SQL mais un DataFrame **bien formé et faux**, celui de
la requête de l'autre thread — d'où, en production uniquement, un
`KeyError: 'Transactions'` dans `analysis.calculate_kpis`.

Ce test ne passe que si `queries.py` isole chaque requête (`_cur` -> `con.cursor()`).
En local, sans concurrence, le bug est invisible : c'est tout l'intérêt de le rejouer ici.
"""
from __future__ import annotations

import os
import threading

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA = os.path.join(_REPO, "data")

pytest.importorskip("duckdb")
if not os.path.exists(os.path.join(_DATA, "sitadel.parquet")):
    pytest.skip("entrepôt Parquet absent (lancer python fetch_new_sources.py)",
                allow_module_level=True)

import queries as q  # noqa: E402  (après le skip)


def test_monthly_reste_juste_sous_concurrence():
    """Deux datasets interrogés en boucle par deux threads sur LA MÊME connexion."""
    con = q.open_warehouse(refresh=False)
    attendus = {"ventes_ancien": ["Transactions"], "sitadel": ["Permis", "MisesEnChantier"]}
    anomalies: list[str] = []

    def boucle(dataset, cols):
        for _ in range(150):
            try:
                df = q.monthly(con, dataset, cols)
            except Exception as e:                      # résultat volé -> erreur brute
                anomalies.append(f"{dataset}: {e!r}")
                return
            manquantes = [c for c in cols if c not in df.columns]
            if manquantes or df.empty:
                anomalies.append(f"{dataset}: colonnes {list(df.columns)}")
                return

    threads = [threading.Thread(target=boucle, args=(d, c)) for d, c in attendus.items()]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    con.close()

    assert not anomalies, "jeux de résultats mélangés entre threads : " + "; ".join(anomalies[:3])
