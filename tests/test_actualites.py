"""Cohérence du contenu éditorial de l'onglet « Actualités & Aides » (actualites.py).

Garde-fous de structure : chaque item de NEWS_ITEMS doit rester rendable par app.py
(clés présentes, bilingue FR/EN, impacts dans l'échelle, dates parseables, jalons typés).
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import actualites as actu  # noqa: E402

LANGS = ("FR", "EN")


def test_maj_is_a_date():
    assert pd.Timestamp(actu.MAJ) is not pd.NaT


@pytest.mark.parametrize("item", actu.NEWS_ITEMS, ids=lambda it: it["id"])
def test_item_structure(item):
    assert item["categorie"] in actu.CATEGORIES["FR"]
    assert item["statut"] in actu.STATUTS["FR"]
    assert pd.Timestamp(item["date"]) is not pd.NaT
    # Textes bilingues obligatoires
    for key in ("court", "titre", "resume", "impact_detail", "horizon"):
        assert set(item[key]) == set(LANGS), f"{item['id']}.{key} doit être FR+EN"
    if item.get("montant") is not None:
        assert set(item["montant"]) == set(LANGS)
    # Impacts : les 3 piliers, valeurs dans l'échelle des libellés
    assert set(item["impacts"]) == {"neuf", "ancien", "renovation"}
    for v in item["impacts"].values():
        assert v in actu.IMPACT_LABELS["FR"]
    # Jalons : (date parseable, libellé bilingue, type connu)
    assert item["jalons"], f"{item['id']} doit avoir au moins un jalon"
    for d, label, typ in item["jalons"]:
        assert pd.Timestamp(d) is not pd.NaT
        assert set(label) == set(LANGS)
        assert typ in actu.JALON_TYPES
    # Sources : au moins une, en (libellé, url http)
    assert item["sources"]
    for lbl, url in item["sources"]:
        assert lbl and url.startswith("http")


def test_ids_unique():
    ids = [it["id"] for it in actu.NEWS_ITEMS]
    assert len(ids) == len(set(ids))


def test_items_sorted_desc():
    dates = [it["date"] for it in actu.items_sorted()]
    assert dates == sorted(dates, reverse=True)


@pytest.mark.parametrize("lang", LANGS)
def test_frames_build(lang):
    items = actu.items_sorted()
    jf = actu.jalons_frame(items, lang)
    assert not jf.empty
    assert {"Dispositif", "Date", "Jalon", "Type", "Categorie"} <= set(jf.columns)
    mx = actu.impact_matrix(items, lang)
    assert len(mx) == len(items)
    # Une colonne par pilier
    for col in actu.PILIERS[lang].values():
        assert col in mx.columns


# --- Fraîcheur de la veille -----------------------------------------------------------
# CLAUDE.md range NEWS_ITEMS + MAJ dans la colonne « à maintenir à la main », et note que
# cette ligne « vieillit » sans aucune garde. Ces deux tests SONT cette garde. Ils échouent
# par le seul passage du temps, ce qui est inhabituel et assumé : c'est exactement le mode
# de panne qu'on veut attraper, et aucune autre mécanique ne peut le signaler.

#: Au-delà, la veille n'est plus une veille. Le seuil est large exprès — il attrape
#: l'abandon, pas le retard de quelques semaines.
MAJ_MAX_JOURS = 120


def test_la_veille_n_est_pas_perimee():
    age = (pd.Timestamp.today().normalize() - pd.Timestamp(actu.MAJ)).days
    assert age <= MAJ_MAX_JOURS, (
        f"la veille date du {actu.MAJ}, soit {age} jours : relire NEWS_ITEMS "
        f"(statuts, jalons, montants) puis remonter MAJ. La page AFFICHE cette date, "
        f"donc un lecteur la voit vieillir avant nous.")


def test_il_reste_une_echeance_a_venir():
    """Sinon la carte « Prochaine échéance aides » disparaît des DEUX surfaces, en silence.

    Depuis que le filtre se compare au jour courant et non à `MAJ` (web_export
    `_jalons_a_venir`, app.py `_AUJOURDHUI`), une veille dont tous les jalons sont passés
    ne produit plus de carte du tout — pas d'erreur, pas de trou visible, juste un bloc
    qui a une carte de moins. C'est le prix de la correction, et voici sa contrepartie."""
    aujourdhui = pd.Timestamp.today().normalize().strftime("%Y-%m-%d")
    a_venir = [d for it in actu.NEWS_ITEMS
               for d, _lbl, _typ in it.get("jalons", []) if d > aujourdhui]
    assert a_venir, (
        "plus aucun jalon dans le futur : la carte « Prochaine échéance aides » ne "
        "s'affichera plus. Ajouter les échéances connues des dispositifs suivis.")
