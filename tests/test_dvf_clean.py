"""Le nettoyage DVF, éprouvé sur les cas tordus qui font les chiffres faux.

Chaque test correspond à une façon précise de se tromper, pas à une ligne de code à
couvrir. Les données sont fabriquées : on veut connaître la bonne réponse à l'avance,
ce qu'un extrait réel ne permet pas.

Repères mesurés sur les données réelles 2025 (voir l'en-tête de `dvf_clean`), qui donnent
l'ordre de grandeur de ce que ces tests protègent :

* un `valeur_fonciere / surface` ligne à ligne surestime la médiane de **+14 %** (Lozère)
  et **+5,4 %** (Paris) ;
* 66 % des mutations à un logement embarquent une dépendance ou du terrain.
"""
import pandas as pd
import pytest

import dvf_clean as dv


def geo(rows):
    """Construit un extrait au format géolocalisé Etalab à partir de tuples courts."""
    cols = ["id_mutation", "date_mutation", "nature_mutation", "valeur_fonciere",
            "code_departement", "type_local", "surface_reelle_bati"]
    return dv.from_geo_dvf(pd.DataFrame(rows, columns=cols))


def _vente(mut, valeur, type_local, surface, date="2024-02-15", dep="12",
           nature="Vente"):
    return (mut, date, nature, valeur, dep, type_local, surface)


# ------------------------------------------------------------------ le piège central
def test_une_mutation_multi_lots_ne_compte_quune_fois():
    """La valeur foncière est le prix TOTAL, répété sur chaque ligne de la mutation.

    Ici : un appartement de 50 m² vendu 200 000 € avec sa cave et son garage. Trois
    lignes portent 200 000 €. Le bon prix est 4 000 €/m² — pas 12 000 (somme des lignes),
    pas 3 lignes retenues.
    """
    d = geo([
        _vente("M1", 200000, "Appartement", 50),
        _vente("M1", 200000, "Dépendance", 0),
        _vente("M1", 200000, "Dépendance", 0),
    ])
    out = dv.clean(d)
    assert len(out) == 1, "une mutation = une vente, quel que soit le nombre de lots"
    assert out["prix_m2"].iloc[0] == pytest.approx(4000.0)
    assert out["valeur_fonciere"].iloc[0] == 200000


def test_les_dependances_sont_tolerees_et_gonflent_le_prix_au_m2():
    """Décision assumée : la maison + garage EST une vente normale, on la garde.

    Le test fige la conséquence — le prix au m² inclut l'annexe — pour qu'un futur
    changement de politique soit un choix explicite et pas un effet de bord.
    """
    d = geo([
        _vente("M1", 300000, "Maison", 100),          # maison seule -> 3000 €/m²
        _vente("M2", 300000, "Maison", 100),          # même prix, mais avec garage…
        _vente("M2", 300000, "Dépendance", 0),
    ])
    out = dv.clean(d)
    assert len(out) == 2, "la mutation avec dépendance doit être CONSERVÉE"
    assert set(out["prix_m2"]) == {3000.0}


def test_mutation_a_deux_logements_ecartee():
    """Deux appartements pour un seul prix : aucune clé de répartition, donc on sort."""
    d = geo([
        _vente("M1", 400000, "Appartement", 50),
        _vente("M1", 400000, "Appartement", 50),
    ])
    assert dv.clean(d).empty


def test_mutation_sans_logement_ecartee():
    """Un garage seul, un terrain, un local commercial : pas de logement, pas de prix."""
    d = geo([
        _vente("M1", 20000, "Dépendance", 0),
        _vente("M2", 90000, "Local industriel. commercial ou assimilé", 200),
        _vente("M3", 50000, None, 0),
    ])
    assert dv.clean(d).empty


@pytest.mark.parametrize("nature", [
    "Vente en l'état futur d'achèvement", "Echange", "Adjudication",
    "Vente terrain à bâtir",
])
def test_seules_les_vraies_ventes_sont_retenues(nature):
    """La VEFA surtout : son prix n'est pas comparable à celui d'un bien existant."""
    d = geo([_vente("M1", 300000, "Appartement", 60, nature=nature)])
    assert dv.clean(d).empty
    assert len(dv.clean(geo([_vente("M2", 300000, "Appartement", 60)]))) == 1


def test_surface_nulle_ou_prix_nul_ecartes():
    """Une division par zéro ne doit pas produire un prix infini mais une exclusion."""
    d = geo([
        _vente("M1", 300000, "Appartement", 0),
        _vente("M2", 0, "Appartement", 60),
        _vente("M3", 300000, "Appartement", 60),
    ])
    out = dv.clean(d)
    assert list(out["mutation"]) == ["M3"]


# ------------------------------------------------------------------ valeurs aberrantes
def test_les_bornes_coupent_par_departement_et_par_annee():
    """Un plafond national serait absurde : le 99ᵉ percentile parisien est à 25 730 €/m².

    On fabrique deux départements aux niveaux de prix incomparables. Chacun doit être
    borné chez lui : la vente parisienne à 20 000 €/m² est ordinaire à Paris et doit
    survivre, alors qu'un même prix en Lozère serait une aberration.
    """
    rows = []
    # Paris : une distribution ÉTALÉE de 6 000 à 20 000 €/m², comme le vrai marché. Une
    # centaine de valeurs identiques rendrait tous les percentiles égaux et le test faux.
    for i in range(200):
        ppm = 6000 + i * 70                                # 6 000 → 19 930
        rows.append(_vente(f"P{i}", ppm * 60, "Appartement", 60, dep="75"))
    for i in range(200):                                   # Lozère : 900 → 2 890
        ppm = 900 + i * 10
        rows.append(_vente(f"L{i}", ppm * 100, "Maison", 100, dep="48"))
    rows.append(_vente("L_absurde", 20000 * 100, "Maison", 100, dep="48"))

    out = dv.clean(geo(rows))
    gardees = set(out["mutation"])
    assert "L_absurde" not in gardees, "20 000 €/m² en Lozère doit sauter"
    # Le MÊME prix au m² survit à Paris, où il est ordinaire : c'est tout l'objet de
    # bornes locales plutôt que nationales.
    assert out[out["departement"] == "75"]["prix_m2"].max() > 15000
    assert out[out["departement"] == "48"]["prix_m2"].max() < 3000


def test_bornes_desactivables_sans_effet_sur_la_mediane():
    """La médiane est robuste : c'est ce qui rend le choix des bornes peu risqué.

    Vérifie la propriété sur laquelle repose la décision documentée (écart mesuré de
    +0,03 % à Paris entre avec et sans bornes).
    """
    rows = [_vente(f"M{i}", (1000 + i) * 50, "Appartement", 50) for i in range(200)]
    rows.append(_vente("EXTREME", 900000 * 50, "Appartement", 50))
    avec = dv.clean(geo(rows))["prix_m2"].median()
    sans = dv.clean(geo(rows), q_low=0, q_high=1)["prix_m2"].median()
    assert avec == pytest.approx(sans, rel=0.01)


# ------------------------------------------------------------------ agrégation
def test_agregation_trimestrielle_par_type():
    """« Ensemble » est la médiane du marché entier, pas la moyenne des deux médianes."""
    rows = [
        _vente("A1", 100000, "Appartement", 50, date="2024-01-10"),   # 2000 €/m²
        _vente("A2", 120000, "Appartement", 50, date="2024-02-10"),   # 2400
        _vente("M1", 300000, "Maison", 100, date="2024-03-10"),       # 3000
        _vente("M2", 400000, "Maison", 100, date="2024-05-10"),       # T2
    ]
    # Bornes neutralisées : ce test porte sur l'agrégation, pas sur l'écrêtage (quatre
    # ventes, tout percentile mordrait dans les données et brouillerait la lecture).
    agg = dv.aggregate(dv.clean(geo(rows), q_low=0, q_high=1))
    t1 = agg[(agg["Date"] == pd.Timestamp("2024-01-01"))]
    ens = t1[t1["Type"] == "Ensemble"].iloc[0]
    assert ens["NbVentes"] == 3
    assert ens["PrixM2Median"] == 2400, "médiane des trois ventes réunies"
    assert t1[t1["Type"] == "Maison"].iloc[0]["PrixM2Median"] == 3000
    assert t1[t1["Type"] == "Appartement"].iloc[0]["NbVentes"] == 2
    # Le trimestre est bien daté à son premier jour.
    assert set(agg["Date"]) == {pd.Timestamp("2024-01-01"), pd.Timestamp("2024-04-01")}


def test_entree_vide_ne_casse_pas():
    vide = pd.DataFrame(columns=["id_mutation", "date_mutation", "nature_mutation",
                                 "valeur_fonciere", "code_departement", "type_local",
                                 "surface_reelle_bati"])
    assert dv.clean(dv.from_geo_dvf(vide)).empty
    assert dv.aggregate(dv.clean(dv.from_geo_dvf(vide))).empty


# ------------------------------------------------------------------ format brut DGFiP
def test_lecture_du_format_brut_pipe():
    """Dates JJ/MM/AAAA, virgule décimale, en-têtes espacés : le brut DGFiP tel quel."""
    brut = pd.DataFrame({
        "No disposition": ["000001", "000001"],
        "Date mutation": ["03/01/2018", "03/01/2018"],
        "Nature mutation": ["Vente", "Vente"],
        "Valeur fonciere": ["109000,00", "109000,00"],
        "Code departement": ["1", "1"],
        "Code commune": ["01053", "01053"],
        "Type local": ["Maison", "Dépendance"],
        "Surface reelle bati": ["100", "0"],
    })
    canon = dv.from_raw_dgfip(brut)
    assert canon["date"].iloc[0] == pd.Timestamp("2018-01-03")
    assert canon["valeur_fonciere"].iloc[0] == 109000.0
    assert canon["departement"].iloc[0] == "01", "le code département doit être sur 2 chiffres"
    assert canon["mutation"].nunique() == 1, "les deux lignes sont la MÊME mutation"
    out = dv.clean(canon)
    assert len(out) == 1 and out["prix_m2"].iloc[0] == pytest.approx(1090.0)


def test_lecture_du_consolide_iso():
    """Le CSV consolidé du miroir : mêmes champs, dates ISO et point décimal."""
    cons = pd.DataFrame({
        "numero_disposition": ["000001"],
        "date_mutation": ["2014-01-07"],
        "nature_mutation": ["Vente"],
        "valeur_fonciere": ["167500"],
        "code_departement": ["30"],
        "code_commune": ["30221"],
        "type_local": ["Maison"],
        "surface_reelle_bati": ["100"],
    })
    canon = dv.from_raw_dgfip(cons)
    assert canon["date"].iloc[0] == pd.Timestamp("2014-01-07")
    assert canon["valeur_fonciere"].iloc[0] == 167500.0


def test_les_deux_formats_donnent_le_meme_resultat():
    """Le raccord des deux sources ne doit pas créer de marche dans la série.

    Même vente décrite dans les deux formats : le prix au m² doit être identique. C'est
    la version fabriquée du contrôle mené sur les données réelles (+0,15 % d'écart de
    médiane au maximum, voir l'en-tête du module).
    """
    g = geo([
        _vente("2024-02-15|000001|12001|300000", 300000, "Maison", 100, dep="12"),
        _vente("2024-02-15|000001|12001|300000", 300000, "Dépendance", 0, dep="12"),
    ])
    b = dv.from_raw_dgfip(pd.DataFrame({
        "No disposition": ["000001", "000001"],
        "Date mutation": ["15/02/2024", "15/02/2024"],
        "Nature mutation": ["Vente", "Vente"],
        "Valeur fonciere": ["300000", "300000"],
        "Code departement": ["12", "12"],
        "Code commune": ["12001", "12001"],
        "Type local": ["Maison", "Dépendance"],
        "Surface reelle bati": ["100", "0"],
    }))
    og, ob = dv.clean(g), dv.clean(b)
    assert len(og) == len(ob) == 1
    assert og["prix_m2"].iloc[0] == ob["prix_m2"].iloc[0] == 3000.0


def test_liste_des_departements_sans_dvf():
    """Verrouille la liste : elle pilote le message affiché sur 4 pages du site."""
    assert dv.DEPARTEMENTS_SANS_DVF == ("57", "67", "68", "976")
