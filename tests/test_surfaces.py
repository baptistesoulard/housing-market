"""Les m² de logements : décomposition volume / mix / taille, mise en forme, rédaction.

La section « En m² » de la page du neuf publie une décomposition qui doit (1) s'additionner
EXACTEMENT au recul total, (2) attribuer chaque écart à la bonne cause — c'est tout son
intérêt, l'explication intuitive (« les logements rétrécissent ») étant la mauvaise — et
(3) se dire dans le sens de la donnée. Tout est vérifié ici sur des cas fabriqués, dont on
connaît la réponse à la main.
"""
from __future__ import annotations

import pathlib
import sys

import pandas as pd
import pytest

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "web" / "export"))
sys.path.insert(0, str(RACINE))

import commun                                                           # noqa: E402
from mesures import decomposition_surface                               # noqa: E402


def _flux(ref, recent):
    """Frame mensuelle par type : `ref` pour 2010-2019, `recent` pour les 12 mois suivants.

    Chaque argument est {type: (logements par mois, m² par logement)}."""
    lignes = []
    for date in pd.date_range("2010-01-01", "2019-12-01", freq="MS"):
        for t, (n, s) in ref.items():
            lignes.append({"Date": date, "Type": t, "N": n, "M": n * s})
    for date in pd.date_range("2020-01-01", "2020-12-01", freq="MS"):
        for t, (n, s) in recent.items():
            lignes.append({"Date": date, "Type": t, "N": n, "M": n * s})
    return pd.DataFrame(lignes)


def _decomp(ref, recent):
    return decomposition_surface(_flux(ref, recent), "N", "M")


def test_les_trois_effets_s_additionnent_au_total():
    d = _decomp({"Maison": (100, 120), "Collectif": (100, 60)},
                {"Maison": (50, 110), "Collectif": (120, 58)})
    assert d["volume"] + d["mix"] + d["taille"] == pytest.approx(d["total"])


def test_un_recul_de_volume_pur_n_a_ni_mix_ni_taille():
    d = _decomp({"Maison": (100, 120), "Collectif": (100, 60)},
                {"Maison": (80, 120), "Collectif": (80, 60)})
    assert d["volume"] == pytest.approx(-20)
    assert d["mix"] == pytest.approx(0) and d["taille"] == pytest.approx(0)
    assert d["total"] == pytest.approx(-20)


def test_un_mix_qui_bascule_vers_le_petit_se_lit_en_mix_et_non_en_taille():
    """Le cas du marché actuel, réduit à l'os : autant de logements, chaque type garde sa
    taille, mais les maisons cèdent la place au collectif. La surface moyenne baisse —
    et la cause publiée doit être le MIX, pas la taille."""
    d = _decomp({"Maison": (100, 120), "Collectif": (100, 60)},
                {"Maison": (50, 120), "Collectif": (150, 60)})
    assert d["volume"] == pytest.approx(0)
    assert d["taille"] == pytest.approx(0)
    assert d["mix"] == pytest.approx(d["total"]) and d["mix"] < 0
    assert d["surface_moyenne"]["recent"] < d["surface_moyenne"]["ref"]


def test_des_logements_qui_retrecissent_se_lisent_en_taille():
    d = _decomp({"Maison": (100, 120), "Collectif": (100, 60)},
                {"Maison": (100, 108), "Collectif": (100, 54)})
    assert d["volume"] == pytest.approx(0) and d["mix"] == pytest.approx(0)
    assert d["taille"] == pytest.approx(-10)


def test_la_periode_de_reference_est_une_moyenne_annuelle():
    """Dix ans de référence, douze mois récents : sans la division par le nombre
    d'années, un marché IDENTIQUE afficherait un recul de 90 %."""
    stable = {"Maison": (100, 120), "Collectif": (100, 60)}
    d = _decomp(stable, stable)
    assert d["total"] == pytest.approx(0)


@pytest.mark.parametrize("v, attendu", [
    (22_563_274, "22,6 M m²"), (1_000_000, "1,0 M m²"), (514_400, "514 000 m²"),
    (41_600, "42 000 m²"), (None, "—")])
def test_surface_a_la_francaise(v, attendu):
    assert commun.surface(v) == attendu


def test_la_phrase_de_decomposition_suit_le_sens_de_la_donnee():
    """« recule de -30,7 % » est une double négation : le total se dit sans signe, porté
    par le verbe, et le verbe change quand la surface progresse. La glose sur la maison
    individuelle n'est dite que si la donnée la porte."""
    from page_marches import _phrase_decomposition

    def phrase(total, volume, mix, taille, part_ref=33.0, part_recent=25.0):
        d = {"total": total, "volume": volume, "mix": mix, "taille": taille,
             "ref_label": "2010-19",
             "types": [{"type": "Maison Individuelle Pure", "part_ref": part_ref,
                        "part_recent": part_recent, "m2_ref": 121.0},
                       {"type": "Logement en Résidence", "part_ref": 7.0,
                        "part_recent": 15.0, "m2_ref": 47.0}]}
        return _phrase_decomposition(d, "surface mise en chantier")

    recul = phrase(-30.7, -22.8, -5.3, -2.6)
    assert "recule de 30,7 %" in recul and "de -" not in recul
    assert "maison individuelle pure" in recul
    hausse = phrase(12.0, 10.0, 1.5, 0.5, part_ref=25.0, part_recent=30.0)
    assert "progresse de 12,0 %" in hausse
    assert "maison individuelle" not in hausse
