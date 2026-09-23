"""La rédaction de la Synthèse, testée sur des FAITS FABRIQUÉS — sans entrepôt ni données.

C'est ce que la séparation `faits()` / `rediger()` de `web/export/page_synthese.py` rend
possible : `rediger()` ne lit aucune donnée, donc on peut lui présenter les cas qui ne se
produisent pas d'eux-mêmes dans la série du moment (un écart qui change de signe, un
modèle non calibrable, une variation qui s'arrondit à zéro) et vérifier ce qu'il en écrit.

Les règles verrouillées ici sont des règles de SENS, qu'aucun test sur les JSON publiés ne
peut attraper tant que la donnée courante ne les met pas à l'épreuve.
"""
import pathlib
import re
import sys

import pandas as pd

RACINE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "web" / "export"))
sys.path.insert(0, str(RACINE))

import commun                                                           # noqa: E402
import page_synthese as ps                                              # noqa: E402


def _kpi(courant, annuel):
    return {"current_val": courant // 12, "current_12m": courant, "yoy_12m_pct": annuel,
            "yoy_monthly_pct": 0.0, "trend": "Stable"}


def _head(v, annuel=False):
    if annuel:
        return {"value": v, "key": "roll12_yoy", "window": "sur 12 mois vs les 12 précédents"}
    return {"value": v, "key": "last3_seq", "window": "sur 3 mois vs les 3 précédents"}


def _niveau(ecart, rang):
    return {"level": 0.0, "gap_pct": ecart, "rank_pct": rang, "below": ecart < 0,
            "ref_label": "2010-19", "since_year": 2000}


def _faits(**maj):
    """Un jeu de faits complet et plausible ; chaque test ne change que ce qu'il éprouve."""
    f = {
        "kpi": {"permis": _kpi(370_673, 5.8), "mises": _kpi(296_131, 17.9),
                "tx": _kpi(956_000, 4.3)},
        "momentum": {"permis": _head(-3.6), "mises": _head(-0.5), "tx": _head(4.3, True)},
        "pilier_neuf": {"status": "flat", "kind": "amont_repli", "amont": "down",
                        "aval": "flat", "word": "amont en repli"},
        "plateau_tx": {"months": 7, "since": pd.Timestamp("2025-12-01"), "level": 956_000},
        "niveau": {"permis": _niveau(-18.0, 9.0), "mises": _niveau(-23.0, 10.0),
                   "tx": _niveau(17.0, 74.0)},
        "individuel_pur": {"seq": 8.3, "annuel": 22.8},
        "stock": {"encours": 124_027.0, "mois": 22.0, "moy_mois": 15.0, "ecart_pct": 53.0,
                  "seq": 1.6, "since": 2017, "status": "down"},
        "transformation": {"now": 79.9, "moy": 85.3, "implied": 316_000.0,
                           "ecart": 20_000.0, "ref_label": "2010-19"},
        "ecln": {"dernier": 16_112.0, "seq": -4.8, "tendance": -4.3},
        "taux": {"now": 3.18, "sur_un_an": 0.2},
        "bls": -12.0,
        "accessibilite": {"now": 73.0, "sur_un_an": -1.4},
        "verdict": {"direction": "baisse", "change_pct": -7.8, "target_month": "mars 2027",
                    "predicted": 882_000, "lo": 798_000, "hi": 959_000,
                    "reliability": {"direction": 0.75, "n": 203}},
        "tx12_dernier": 956_000.0,
        "renovation": {"now": -14.0, "delta": -2.0},
        "prochain_jalon": {"date": "2026-12-01", "libelle": "Citizens Energy Package"},
        "fraicheur": {"sitadel": pd.Timestamp("2026-07-01"),
                      "igedd": pd.Timestamp("2026-07-01"),
                      "ecln": pd.Timestamp("2026-04-01")},
        "graphique": {},
    }
    f.update(maj)
    return f


def _carte(texte, titre):
    return next(c for b in texte["blocks"] for c in b["cards"] if c["title"] == titre)


def _tout_le_texte(texte):
    morceaux = list(texte["takeaways"]) + list(texte["freshness"])
    for b in texte["blocks"]:
        morceaux.append(b["title"])
        for c in b["cards"]:
            morceaux += [c.get("value", ""), c.get("sub", ""), c.get("level", "")]
    morceaux += [p["word"] for p in texte["pillars"]]
    return "\n".join(morceaux)


_TR = "Taux de transformation permis → chantiers"


def test_un_manque_se_dit_comme_un_manque():
    """Le signe arithmétique et le signe RESSENTI pointent dans le même sens.

    Quand le taux de transformation est dégradé, les permis auraient dû donner PLUS de
    chantiers qu'il n'y en a : c'est un manque, et la phrase doit le dire comme tel. La
    première version écrivait « soit 28 000 de plus qu'aujourd'hui » — exact, et lu comme
    une bonne nouvelle.
    """
    ligne = _carte(ps.rediger(_faits()), _TR)["level"]
    assert "manquent à l'appel" in ligne and "au lieu de" in ligne
    assert "de plus" not in ligne


def test_un_surplus_ne_se_dit_pas_comme_un_manque():
    """Contre-épreuve : sans elle, le test précédent passerait même si la phrase disait
    « manquent à l'appel » quel que soit le signe."""
    tr = {"now": 90.0, "moy": 85.3, "implied": 280_000.0, "ecart": -16_000.0,
          "ref_label": "2010-19"}
    ligne = _carte(ps.rediger(_faits(transformation=tr)), _TR)["level"]
    assert "manquent à l'appel" not in ligne
    assert "de plus" in ligne


def test_le_contrefactuel_est_arrondi_au_millier():
    """Précision réelle d'un écart dérivé d'un taux dont l'écart-type vaut ~5 points."""
    tr = {"now": 79.9, "moy": 85.3, "implied": 316_000.0, "ecart": 19_734.0,
          "ref_label": "2010-19"}
    ligne = _carte(ps.rediger(_faits(transformation=tr)), _TR)["level"]
    assert "environ 20 000" in ligne and "19 734" not in ligne


def test_la_page_tient_sans_modele():
    """Modèle non calibrable : le bloc « Où va le marché » retombe sur la cible BPCE au
    lieu de rester vide, et aucune puce n'invente de projection."""
    texte = ps.rediger(_faits(verdict=None))
    bloc = texte["blocks"][-1]
    assert bloc["cards"], "le bloc de perspective ne doit jamais être vide"
    assert "BPCE" in bloc["title"]
    assert "projetées" not in texte["takeaways"][-1]


def test_une_serie_absente_donne_un_tiret_pas_une_erreur():
    texte = ps.rediger(_faits(taux=None, bls=None, accessibilite=None, stock=None,
                              ecln=None, renovation=None, prochain_jalon=None))
    assert _carte(texte, "Taux de crédit habitat (toutes durées)")["value"] == "—"
    assert _carte(texte, "Demande de crédit (banques)")["value"] == "—"
    assert "None" not in _tout_le_texte(texte)


# --- Typographie des variations ----------------------------------------------------------
# La Synthèse publiait « -3,6% » et « 17 % » dans la même puce, et « sur un an : -0,0 pt »
# sur la carte d'accessibilité. Les deux règles vivent dans commun._variation ; ces tests
# les éprouvent sur la page entière, là où un nouveau format écrit à la main les
# contournerait.
def test_une_variation_nulle_n_a_pas_de_signe():
    assert commun.pct(-0.03) == "0,0 %" and commun.pct(0.04) == "0,0 %"
    assert commun.pt(-0.049) == "0,0 pt"
    texte = ps.rediger(_faits(accessibilite={"now": 73.0, "sur_un_an": -0.03},
                              taux={"now": 3.18, "sur_un_an": 0.02}))
    assert not re.search(r"[+\-−]0,0\b", _tout_le_texte(texte))


def test_le_signe_pourcent_est_toujours_precede_d_une_espace():
    assert commun.pct(4.26) == "+4,3 %" and commun.pct(-3.6) == "-3,6 %"
    texte = _tout_le_texte(ps.rediger(_faits()))
    colles = re.findall(r"\d%", texte)
    assert not colles, f"« % » collé au nombre : {colles}"
