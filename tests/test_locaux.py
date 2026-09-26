"""Les locaux non résidentiels (SIT@DEL2) : parse, contrat de niveaux, total SQL.

Le dataset a un piège que les autres n'ont pas : deux niveaux dans une même colonne
`Type`. Les quatre destinations partitionnent l'ensemble ; les sous-destinations sont déjà
comptées dans leur destination. Ces tests verrouillent les deux faits dont dépend tout
chiffre publié : la somme des destinations EST le total du SDES, et un total ne se lit
jamais en sommant toutes les lignes.
"""
from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import data_manager as dmod                        # noqa: E402
from housing_data import schema as S               # noqa: E402

_ENTETE = '"ANNEE";"MOIS";"NAT_SERIES";"DESTINATION";"SDP_AUT";"SDP_COM"'


def _fichier(tmp_path, mois=((2026, 6), (2026, 7)), sans=None, ensemble_faux=False):
    """Un fichier au format DiDo : les neuf libellés, brut et CVS-CJO."""
    dest = {"Exploitation agricole": (800, 400), "Commerce": (600, 300),
            "Services publics": (500, 350), "Autres activites": (1400, 800)}
    sous = {"Commerce - hotels": (90, 40), "Autres activites - industrie": (400, 200),
            "Autres activites - entrepot": (650, 380), "Autres activites - bureau": (350, 220)}
    lignes = [_ENTETE]
    for an, m in mois:
        for nat in ("Brute", "CVS-CJO"):
            tot_a = sum(a for a, _ in dest.values()) + (100 if ensemble_faux else 0)
            tot_c = sum(c for _, c in dest.values())
            lignes.append(f'{an};{m};"{nat}";"Ensemble des locaux non-residentiels";{tot_a};{tot_c}')
            for lib, (a, c) in {**dest, **sous}.items():
                if lib != sans:
                    lignes.append(f'{an};{m};"{nat}";"{lib}";{a};{c}')
    chemin = tmp_path / "locaux.csv"
    chemin.write_text("\n".join(lignes), encoding="utf-8")
    return str(chemin)


def test_le_parse_garde_le_cvs_et_traduit_les_libelles(tmp_path):
    df = dmod.DataManager.build_locaux_from_manual_input(_fichier(tmp_path))
    assert set(df["Type"]) == set(S.LOCAUX_DESTINATIONS + S.LOCAUX_SOUS_DESTINATIONS)
    assert len(df) == 2 * 8                       # 2 mois x 8 libellés, CVS-CJO seulement
    assert S.validate("locaux", df) is not None
    # La somme des destinations est le total ; sommer TOUT compterait deux fois.
    juillet = df[df["Date"] == "2026-07-01"]
    assert juillet.loc[juillet["Niveau"] == "Destination", "SurfaceChantiers"].sum() == 1850
    assert juillet["SurfaceChantiers"].sum() > 1850


def test_une_destination_manquante_casse_le_parse(tmp_path):
    """Le SDES qui renomme une destination produirait sinon un total amputé, en silence."""
    with pytest.raises(ValueError, match="nomenclature"):
        dmod.DataManager.build_locaux_from_manual_input(
            _fichier(tmp_path, sans="Services publics"))


def test_un_ensemble_qui_ne_boucle_plus_casse_le_parse(tmp_path):
    with pytest.raises(ValueError, match="s'écarte"):
        dmod.DataManager.build_locaux_from_manual_input(_fichier(tmp_path, ensemble_faux=True))


def test_ensure_locaux_garde_l_ancien_derive_quand_la_source_est_illisible(tmp_path, monkeypatch):
    monkeypatch.setattr(dmod, "LOCAUX_MANUAL_CSV", _fichier(tmp_path, ensemble_faux=True))
    dm = dmod.DataManager(data_dir=str(tmp_path / "data"))
    ok, msg = dm.ensure_locaux(force_rebuild=True)
    assert not ok and "non reconstruits" in msg
    assert not os.path.exists(dm.paths["locaux"])


def test_le_vocabulaire_du_parse_est_celui_du_contrat():
    """data_manager traduit, le contrat refuse : les deux listes doivent coïncider."""
    dest = [lib for lib, niv in dmod.LOCAUX_LIBELLES.values() if niv == "Destination"]
    sous = [lib for lib, niv in dmod.LOCAUX_LIBELLES.values() if niv == "Sous-destination"]
    assert sorted(dest) == sorted(S.LOCAUX_DESTINATIONS)
    assert sorted(sous) == sorted(S.LOCAUX_SOUS_DESTINATIONS)


def test_le_builder_de_collecte_attend_les_memes_libelles():
    import fetch_new_sources as fns
    assert set(fns.LOCAUX_DESTINATIONS_SDES) == (set(dmod.LOCAUX_LIBELLES)
                                                 | {dmod.LOCAUX_ENSEMBLE_SDES})


@pytest.mark.skipif(not os.path.exists(os.path.join(_ROOT, dmod.LOCAUX_MANUAL_CSV)),
                    reason="fichier SDES des locaux absent")
def test_sur_le_vrai_fichier_le_total_sql_reproduit_l_ensemble_publie(monkeypatch):
    """Le total que publie le site (somme SQL des destinations) EST celui du SDES."""
    monkeypatch.chdir(_ROOT)
    duckdb = pytest.importorskip("duckdb")
    df = dmod.DataManager.build_locaux_from_manual_input()
    brut = pd.read_csv(dmod.LOCAUX_MANUAL_CSV, sep=";")
    ens = brut[(brut["NAT_SERIES"] == "CVS-CJO")
               & (brut["DESTINATION"] == dmod.LOCAUX_ENSEMBLE_SDES)]
    con = duckdb.connect()
    con.register("locaux", df)
    total = con.execute("SELECT SUM(SurfaceChantiers) FROM locaux "
                        "WHERE Niveau = 'Destination'").fetchone()[0]
    assert total == ens["SDP_COM"].sum()
