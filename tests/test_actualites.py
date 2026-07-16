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
