"""La comparaison des modèles de la page « Le modèle face au réel ».

Une section qui compare le modèle publié à d'autres méthodes doit les juger EXACTEMENT
comme lui : mêmes millésimes `retro`, même réalisé rejoint à la lecture, mêmes plages
d'horizon. Ces tests le vérifient sur des données fabriquées, sans entrepôt ni réseau.
"""
import os
import sys

import pandas as pd
import pytest

_RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_RACINE, "web", "export"))
sys.path.insert(0, _RACINE)

import page_archive as pa  # noqa: E402

_V = pd.Timestamp("2020-01-01")


def _archive(kind="retro"):
    rows = []
    for h in range(1, 19):
        rows.append({"run_date": "2020-01-01", "kind": kind, "data_vintage": "2020-01-01",
                     "target_month": (_V + pd.DateOffset(months=h)).strftime("%Y-%m-%d"),
                     "horizon": h, "predicted": 110.0, "lo": 90.0, "hi": 130.0,
                     "assured": False, "naive": 120.0})
    return pd.DataFrame(rows)


def _instantane(tmp_path, timestral=100.0, hw=100.0):
    rows = []
    for m, val in (("holt_winters", hw), ("timestral", timestral)):
        for h in range(1, 19):
            rows.append({"methode": m, "data_vintage": "2020-01-01",
                         "target_month": (_V + pd.DateOffset(months=h)).strftime("%Y-%m-%d"),
                         "horizon": h, "predicted": val, "mesure_le": "2026-10-17"})
    chemin = tmp_path / "comparaison.csv"
    pd.DataFrame(rows).to_csv(chemin, index=False)
    return str(chemin)


def _realise(jusqua=18, valeur=100.0):
    idx = pd.date_range(_V + pd.DateOffset(months=1), periods=jusqua, freq="MS")
    return pd.Series(valeur, index=idx)


def test_sans_instantane_la_section_disparait(tmp_path):
    assert pa._comparaison_modeles(_archive(), _realise(), str(tmp_path / "absent.csv")) is None


def test_la_combinaison_est_la_moyenne_du_modele_et_de_timestral(tmp_path):
    c = pa._comparaison_modeles(_archive(), _realise(), _instantane(tmp_path, timestral=100.0))
    point = c["courbe"][0]
    assert point["combinaison"] == (point["modele"] + point["timestral"]) / 2 == 105


def test_les_erreurs_et_l_erreur_evitee_par_plage(tmp_path):
    c = pa._comparaison_modeles(_archive(), _realise(), _instantane(tmp_path))
    par = {m["cle"]: {b["bloc"]: b for b in m["blocs"]} for m in c["methodes"]}
    assert [m["cle"] for m in c["methodes"]] == ["naive", "modele", "holt_winters",
                                                 "timestral", "combinaison"]
    assert par["naive"]["1-3"]["mape"] == 20.0          # 120 contre un réalisé de 100
    assert par["modele"]["7-12"]["mape"] == 10.0
    assert par["modele"]["7-12"]["skill_pct"] == 50.0   # moitié de l'erreur naïve évitée
    assert par["timestral"]["13-18"]["mape"] == 0.0


def test_seuls_les_mois_realises_sont_juges(tmp_path):
    c = pa._comparaison_modeles(_archive(), _realise(jusqua=8), _instantane(tmp_path))
    blocs = [b["bloc"] for b in c["methodes"][0]["blocs"]]
    assert blocs == ["1-3", "4-6", "7-12"]             # rien d'échu au-delà du 8e mois


def test_les_lignes_publiees_ne_sont_jamais_melangees(tmp_path):
    """L'instantané est une rétro-simulation : il ne se compare qu'aux lignes `retro`."""
    assert pa._comparaison_modeles(_archive(kind="archive"), _realise(),
                                   _instantane(tmp_path)) is None


@pytest.mark.parametrize("timestral, passe", [(100.0, True), (110.0, False)])
def test_le_statut_suit_le_seuil_d_entree(tmp_path, timestral, passe):
    c = pa._comparaison_modeles(_archive(), _realise(), _instantane(tmp_path, timestral))
    assert c["statut"].startswith("La prévision publiée reste celle du modèle")
    assert ("fait mieux en rétro-simulation" in c["statut"]) is passe
