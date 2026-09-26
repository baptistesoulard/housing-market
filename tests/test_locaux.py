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


# --- Les locaux PAR DÉPARTEMENT : réduction, contrôle régional, fenêtres SQL -----------

def _brut_dep(lignes):
    """Fichier départemental DiDo fabriqué : [(annee, mois, dep, {libellé: (aut, com)})]."""
    import fetch_new_sources as fns
    out = []
    for an, mois, dep, vals in lignes:
        for lib in fns.LOCAUX_CLES_SDES:
            aut, com = vals.get(lib, (0, 0))
            out.append({"ANNEE": str(an), "MOIS": str(mois), "DEPARTEMENT_CODE": dep,
                        "DEPARTEMENT_LIBELLE": dep, "DESTINATION": lib,
                        "SDP_AUT": str(aut), "SDP_COM": str(com)})
    return pd.DataFrame(out)


def _brut_reg(dep):
    """Le fichier régional COHÉRENT avec `dep` : somme par région, en « Brute »."""
    import departements
    d = dep.copy()
    for c in ("SDP_AUT", "SDP_COM"):
        d[c] = d[c].astype(int)
    d["REGION"] = d["DEPARTEMENT_CODE"].map(departements.region)
    r = d.groupby(["ANNEE", "MOIS", "REGION", "DESTINATION"], as_index=False)[
        ["SDP_AUT", "SDP_COM"]].sum()
    r["NAT_SERIES"] = "Brute"
    return r.astype(str)


_E = "Ensemble des locaux non-residentiels"


def test_la_reduction_departementale_donne_une_grille_complete_et_garde_les_negatifs():
    import fetch_new_sources as fns
    dep = _brut_dep([(2026, 6, "44", {_E: (1000, 500), "Autres activites - entrepot": (400, 200)}),
                     (2026, 6, "49", {_E: (-433, 0)}),
                     (2026, 7, "44", {_E: (800, 300)})])          # 49 absent en juillet
    out = fns.reduire_locaux_departements(dep, _brut_reg(dep))
    assert len(out) == 4                                          # 2 mois × 2 départements
    juillet_49 = out[(out["Date"] == "2026-07-01") & (out["Department"] == "49")]
    assert juillet_49["Chantiers_Ensemble"].item() == 0           # trou → zéro, pas de ligne manquante
    assert out.loc[out["Department"] == "49", "Permis_Ensemble"].min() == -433
    assert out.loc[(out["Department"] == "44") & (out["Date"] == "2026-06-01"),
                   "Chantiers_Entrepots"].item() == 200
    assert S.validate("locaux_departements", out) is not None


def test_une_region_qui_ne_boucle_plus_arrete_la_collecte():
    """La région publiée doit être la somme exacte de ses départements : un écart dit
    qu'un département manque ou que la table département → région est périmée."""
    import fetch_new_sources as fns
    dep = _brut_dep([(2026, 7, "44", {_E: (1000, 500)}), (2026, 7, "49", {_E: (100, 50)})])
    reg = _brut_reg(dep)
    reg.loc[reg["DESTINATION"] == _E, "SDP_COM"] = "551"
    with pytest.raises(ValueError, match="région publiée"):
        fns.reduire_locaux_departements(dep, reg)


def test_un_departement_inconnu_arrete_la_collecte():
    import fetch_new_sources as fns
    dep = _brut_dep([(2026, 7, "99", {})])
    with pytest.raises(ValueError, match="inconnus"):
        fns.reduire_locaux_departements(dep, _brut_reg(_brut_dep([(2026, 7, "44", {})])))


def test_les_cles_du_fichier_reduit_sont_celles_du_contrat():
    import fetch_new_sources as fns
    assert list(fns.LOCAUX_CLES_SDES.values()) == S.LOCAUX_CLES
    assert set(fns.LOCAUX_CLES_SDES) == set(fns.LOCAUX_DESTINATIONS_SDES)


_DEP_CSV = os.path.join(_ROOT, dmod.LOCAUX_DEP_CSV)
_NAT_CSV = os.path.join(_ROOT, dmod.LOCAUX_MANUAL_CSV)


@pytest.mark.skipif(not (os.path.exists(_DEP_CSV) and os.path.exists(_NAT_CSV)),
                    reason="fichiers SDES des locaux absents")
def test_sur_les_vrais_fichiers_les_departements_redonnent_le_national():
    """Au m² près, chaque mois : la somme des 101 départements EST le national brut."""
    dep = pd.read_csv(_DEP_CSV, dtype={"Department": str})
    nat = pd.read_csv(_NAT_CSV, sep=";")
    nat = nat[(nat["NAT_SERIES"] == "Brute") & (nat["DESTINATION"] == _E)].copy()
    nat["Date"] = pd.to_datetime(nat["ANNEE"].astype(str) + "-"
                                 + nat["MOIS"].astype(str).str.zfill(2) + "-01")
    somme = dep.groupby(pd.to_datetime(dep["Date"]))[["Permis_Ensemble", "Chantiers_Ensemble"]].sum()
    n = nat.set_index("Date").sort_index()
    commun = somme.index.intersection(n.index)
    assert len(commun) > 100
    assert (somme.loc[commun, "Chantiers_Ensemble"] == n.loc[commun, "SDP_COM"]).all()
    assert (somme.loc[commun, "Permis_Ensemble"] == n.loc[commun, "SDP_AUT"]).all()


def _con_departements(df):
    """Une vraie TABLE, pas un DataFrame enregistré : les requêtes passent par un curseur
    isolé (queries._cur, la règle de concurrence), qui ne voit pas les objets propres à
    la connexion — un `register()` y est invisible."""
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.register("_grille", df)
    con.execute("CREATE TABLE locaux_departements AS SELECT * FROM _grille")
    return con


def _grille(valeurs, departements_=("44", "49", "75")):
    """Grille mensuelle 2013-01 → 2026-07 ; `valeurs(dep, i)` donne Chantiers_Ensemble."""
    dates = pd.date_range("2013-01-01", "2026-07-01", freq="MS")
    lignes = []
    for i, d in enumerate(dates):
        for dep in departements_:
            ligne = {"Date": d, "Department": dep}
            for c in S.LOCAUX_CLES:
                ligne[f"Permis_{c}"] = 0
                ligne[f"Chantiers_{c}"] = 0
            ligne["Chantiers_Ensemble"] = valeurs(dep, i)
            ligne["Permis_Ensemble"] = 2 * valeurs(dep, i)
            lignes.append(ligne)
    return pd.DataFrame(lignes)


def test_la_reference_sql_a_la_definition_de_la_page_nationale():
    """`queries.locaux_territoires` et `analysis.level_context` doivent dire le MÊME
    « écart à 2013-19 » : sinon deux chiffres différents pour une même série s'affichent
    sur la même page (−16,4 % contre −15,5 %, vu en préparant la section régionale)."""
    import numpy as np
    import analysis as ana
    import queries as q

    rng = np.random.default_rng(3)
    brut = {dep: rng.integers(0, 50_000, size=163) for dep in ("44", "49", "75")}
    df = _grille(lambda dep, i: int(brut[dep][i]))
    res = {r["code"]: r for r in q.locaux_territoires(_con_departements(df))}
    for dep in ("44", "75"):
        serie = df[df["Department"] == dep][["Date", "Chantiers_Ensemble"]]
        ctx = ana.level_context(serie, "Chantiers_Ensemble", ref=("2013", "2019"))
        r = res[dep]
        assert r["Chantiers_Ensemble_12m"] == pytest.approx(ctx["level"])
        assert (r["Chantiers_Ensemble_12m"] / r["Chantiers_Ensemble_ref"] - 1) * 100 \
            == pytest.approx(ctx["gap_pct"], abs=0.05)
        assert r["Chantiers_Ensemble_prec"] == pytest.approx(
            serie["Chantiers_Ensemble"].iloc[-24:-12].sum())


def test_une_region_est_la_somme_de_ses_departements_en_sql():
    import queries as q
    df = _grille(lambda dep, i: {"44": 10, "49": 5, "75": 7}[dep])
    reg = {r["code"]: r for r in q.locaux_territoires(_con_departements(df), "region")}
    assert reg["Pays de la Loire"]["Chantiers_Ensemble_12m"] == 12 * (10 + 5)
    assert reg["Île-de-France"]["Chantiers_Ensemble_12m"] == 12 * 7
    assert len(reg) == 2                              # seules les régions présentes


def test_l_annee_en_cours_n_est_pas_une_annee():
    import queries as q
    df = _grille(lambda dep, i: 1)
    annees = [a["annee"] for a in q.locaux_annuel(_con_departements(df), "44")]
    assert annees[0] == 2013 and annees[-1] == 2025          # 2026 : sept mois seulement
