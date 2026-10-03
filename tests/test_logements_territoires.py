"""Les logements autorisés et commencés PAR DÉPARTEMENT (SIT@DEL2, bruts).

La déclinaison locale de la série nationale `sitadel`, jumelle des locaux par département
(tests/test_locaux.py). Ce qui est verrouillé ici : les deux contrôles qui arrêtent la
collecte plutôt que de publier un fichier faux (individuel + collectif = total publié ;
somme des départements = région publiée), la grille complète dont dépendent les cumuls
SQL, et la définition du niveau de référence — la même que les pages nationales.
"""
from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_EXPORT = os.path.join(_ROOT, "web", "export")
if _EXPORT not in sys.path:
    sys.path.insert(0, _EXPORT)

import data_manager as dmod                        # noqa: E402
from housing_data import schema as S               # noqa: E402

_MESURES = ("LOG_AUT", "LOG_COM", "SDP_AUT", "SDP_COM")


def _brut_dep(lignes, total_faux=False):
    """Fichier départemental DiDo fabriqué : [(annee, mois, dep, (ind…), (coll…))], chaque
    tuple portant les quatre mesures dans l'ordre de _MESURES. « Tous Logements » est
    leur somme, sauf si `total_faux`."""
    out = []
    for an, mois, dep, ind, coll in lignes:
        tous = tuple(a + b + (1 if total_faux else 0) for a, b in zip(ind, coll))
        for typ, vals in (("Individuel", ind), ("Collectif et Residence", coll),
                          ("Tous Logements", tous)):
            out.append({"ANNEE": str(an), "MOIS": f"{mois:02d}", "DEPARTEMENT_CODE": dep,
                        "DEPARTEMENT_LIBELLE": dep, "TYPE_LGT": typ,
                        **{m: str(v) for m, v in zip(_MESURES, vals)}})
    return pd.DataFrame(out)


def _brut_reg(dep):
    """Le fichier régional COHÉRENT avec `dep` : somme par région, en « Brute »."""
    import departements
    d = dep.copy()
    for c in _MESURES:
        d[c] = d[c].astype(int)
    d["REGION"] = d["DEPARTEMENT_CODE"].map(departements.region)
    r = d.groupby(["ANNEE", "MOIS", "REGION", "TYPE_LGT"], as_index=False)[list(_MESURES)].sum()
    r["NAT_SERIES"] = "Brute"
    return r.astype(str)


def test_la_reduction_donne_une_grille_complete_au_format_du_contrat():
    import fetch_new_sources as fns
    dep = _brut_dep([(2026, 6, "44", (100, 80, 12000, 9000), (50, 40, 3000, -200)),
                     (2026, 6, "49", (10, 8, 1200, 900), (0, 0, 0, 0)),
                     (2026, 7, "44", (90, 70, 11000, 8000), (40, 30, 2500, 2000))])  # 49 absent
    out = fns.reduire_logements_departements(dep, _brut_reg(dep))
    assert len(out) == 4                                            # 2 mois × 2 départements
    juillet_49 = out[(out["Date"] == "2026-07-01") & (out["Department"] == "49")]
    assert juillet_49["Chantiers_Individuel"].item() == 0           # trou → zéro
    l44 = out[(out["Date"] == "2026-06-01") & (out["Department"] == "44")].iloc[0]
    assert (l44["Permis_Individuel"], l44["Chantiers_Collectif"]) == (100, 40)
    assert l44["SurfaceChantiers_Collectif"] == -200                # annulation gardée
    assert S.validate("logements_departements", out) is not None


def test_un_total_qui_ne_vaut_plus_la_somme_des_types_arrete_la_collecte():
    """Ne stocker que deux types n'est permis que parce qu'ils partitionnent le total."""
    import fetch_new_sources as fns
    dep = _brut_dep([(2026, 7, "44", (10, 5, 900, 400), (3, 2, 200, 100))], total_faux=True)
    with pytest.raises(ValueError, match="Tous Logements"):
        fns.reduire_logements_departements(dep, _brut_reg(dep))


def test_une_region_qui_ne_boucle_plus_arrete_la_collecte():
    import fetch_new_sources as fns
    dep = _brut_dep([(2026, 7, "44", (10, 5, 900, 400), (3, 2, 200, 100)),
                     (2026, 7, "49", (1, 1, 90, 40), (0, 0, 0, 0))])
    reg = _brut_reg(dep)
    reg.loc[reg["TYPE_LGT"] == "Individuel", "LOG_COM"] = "7"
    with pytest.raises(ValueError, match="région publiée"):
        fns.reduire_logements_departements(dep, reg)


def test_un_departement_inconnu_arrete_la_collecte():
    import fetch_new_sources as fns
    dep = _brut_dep([(2026, 7, "99", (1, 1, 1, 1), (1, 1, 1, 1))])
    with pytest.raises(ValueError, match="inconnus"):
        fns.reduire_logements_departements(dep, _brut_reg(_brut_dep(
            [(2026, 7, "44", (1, 1, 1, 1), (1, 1, 1, 1))])))


def test_les_colonnes_du_fichier_reduit_sont_celles_du_contrat():
    import fetch_new_sources as fns
    assert list(fns.LOGEMENTS_TYPES_SDES.values()) == S.LOGEMENTS_TYPES
    assert list(fns.LOGEMENTS_MESURES_SDES.values()) == S.LOGEMENTS_MESURES


_DEP_CSV = os.path.join(_ROOT, dmod.LOGEMENTS_DEP_CSV)
_NAT_CSV = os.path.join(_ROOT, "data_manual_input", "Donnees-mensuelles-nationales-Logements.csv")


@pytest.mark.skipif(not (os.path.exists(_DEP_CSV) and os.path.exists(_NAT_CSV)),
                    reason="fichiers SDES des logements absents")
def test_sur_les_vrais_fichiers_les_departements_redonnent_le_national():
    """Au logement près, chaque mois : la somme des départements EST le national brut des
    mises en chantier. Les permis peuvent s'en écarter de quelques unités — Mayotte, absente
    du fichier départemental. Les deux fichiers doivent venir du même millésime (le job
    hebdomadaire les collecte ensemble) : sinon les révisions récentes les séparent."""
    dep = pd.read_csv(_DEP_CSV, dtype={"Department": str})
    nat = pd.read_csv(_NAT_CSV, sep=";")
    nat = nat[(nat["NAT_SERIES"] == "Brute") & (nat["TYPE_LGT"] == "Tous Logements")].copy()
    nat["Date"] = pd.to_datetime(nat["ANNEE"].astype(str) + "-"
                                 + nat["MOIS"].astype(str).str.zfill(2) + "-01")
    if nat["Date"].max() != pd.Timestamp(dep["Date"].max()):
        pytest.skip("fichiers national et départemental de millésimes différents")
    d = dep.assign(Date=pd.to_datetime(dep["Date"])).groupby("Date").sum(numeric_only=True)
    n = nat.set_index("Date").sort_index()
    commun = d.index.intersection(n.index)
    assert len(commun) > 300
    com = d.loc[commun, "Chantiers_Individuel"] + d.loc[commun, "Chantiers_Collectif"]
    aut = d.loc[commun, "Permis_Individuel"] + d.loc[commun, "Permis_Collectif"]
    assert (com == n.loc[commun, "LOG_COM"]).all()
    assert (aut - n.loc[commun, "LOG_AUT"]).abs().max() <= 50


def _con(df):
    """Une vraie TABLE (les requêtes passent par un curseur isolé, qui ne voit pas un
    DataFrame enregistré sur la connexion)."""
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.register("_grille", df)
    con.execute("CREATE TABLE logements_departements AS SELECT * FROM _grille")
    return con


def _grille(ind, coll=lambda dep, i: 0, departements_=("44", "49", "75")):
    """Grille mensuelle 2008-01 → 2026-07 ; `ind`/`coll(dep, i)` donnent les chantiers."""
    dates = pd.date_range("2008-01-01", "2026-07-01", freq="MS")
    lignes = []
    for i, d in enumerate(dates):
        for dep in departements_:
            ligne = {"Date": d, "Department": dep}
            for c in S.LOGEMENTS_MESURES:
                for t in S.LOGEMENTS_TYPES:
                    ligne[f"{c}_{t}"] = 0
            ligne["Chantiers_Individuel"] = ind(dep, i)
            ligne["Chantiers_Collectif"] = coll(dep, i)
            ligne["Permis_Individuel"] = 2 * ind(dep, i)
            lignes.append(ligne)
    return pd.DataFrame(lignes)


def test_la_reference_sql_a_la_definition_des_pages_nationales():
    """Même « écart à 2010-19 » que `analysis.level_context`, appliqué au total."""
    import numpy as np
    import analysis as ana
    import queries as q

    rng = np.random.default_rng(7)
    a = {dep: rng.integers(0, 900, size=223) for dep in ("44", "49", "75")}
    b = {dep: rng.integers(0, 600, size=223) for dep in ("44", "49", "75")}
    df = _grille(lambda dep, i: int(a[dep][i]), lambda dep, i: int(b[dep][i]))
    res = {r["code"]: r for r in q.logements_territoires(_con(df))}
    for dep in ("44", "75"):
        s = df[df["Department"] == dep].assign(
            Total=lambda x: x["Chantiers_Individuel"] + x["Chantiers_Collectif"])
        ctx = ana.level_context(s[["Date", "Total"]], "Total")
        r = res[dep]
        tot = r["Chantiers_Individuel_12m"] + r["Chantiers_Collectif_12m"]
        ref = r["Chantiers_Individuel_ref"] + r["Chantiers_Collectif_ref"]
        assert tot == pytest.approx(ctx["level"])
        assert (tot / ref - 1) * 100 == pytest.approx(ctx["gap_pct"], abs=0.05)


def test_une_region_est_la_somme_de_ses_departements_en_sql():
    import queries as q
    df = _grille(lambda dep, i: {"44": 10, "49": 5, "75": 7}[dep])
    reg = {r["code"]: r for r in q.logements_territoires(_con(df), "region")}
    assert reg["Pays de la Loire"]["Chantiers_Individuel_12m"] == 12 * (10 + 5)
    assert reg["Île-de-France"]["Permis_Individuel_12m"] == 2 * 12 * 7


def test_l_annee_en_cours_n_est_pas_une_annee():
    import queries as q
    annees = q.logements_annuel(_con(_grille(lambda dep, i: 1, lambda dep, i: 2)), "44")
    assert annees[0]["annee"] == 2008 and annees[-1]["annee"] == 2025
    assert (annees[0]["ind"], annees[0]["coll"], annees[0]["aut"]) == (12, 24, 24)


def test_les_reperes_france_sont_des_rapports_de_sommes():
    """Un petit département ne doit pas peser autant que le Nord dans la référence."""
    from mesures import logements_indicateurs
    terr = [{"code": "48", "Chantiers_Individuel_12m": 90, "Chantiers_Collectif_12m": 10,
             "Chantiers_Individuel_ref": 100, "Chantiers_Collectif_ref": 25},
            {"code": "59", "Chantiers_Individuel_12m": 2000, "Chantiers_Collectif_12m": 6000,
             "Chantiers_Individuel_ref": 3000, "Chantiers_Collectif_ref": 7000}]
    out = logements_indicateurs(terr, {"48": 76_000, "59": 2_600_000})
    assert out["par_code"]["48"] == {"hab": 1.32, "ecart": -20.0, "ind": 90.0}
    assert out["france"]["hab"] == round(1000 * 8100 / 2_676_000, 2)
    assert out["france"]["ind"] == round(100 * 2090 / 8100, 1)
    assert out["france"]["ecart"] == round((8100 / 10125 - 1) * 100, 1)
