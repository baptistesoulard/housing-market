"""La page « Carte des départements » : fond de carte, données, tableau statique.

La carte est dessinée dans le navigateur, donc aucun test Python ne peut en compter les
départements coloriés (voir CLAUDE.md, « Rien ne teste le RENDU »). Ce qui PEUT casser en
silence, et que ces tests attrapent :

* un fond de carte qui perd ou gagne un département — la carte afficherait un trou ou
  une collectivité que ni DVF ni le site ne couvrent, sans erreur ;
* un JSON dont les valeurs ne suivent plus le catalogue des mesures — la carte
  colorierait une mesure avec les chiffres d'une autre ;
* une projection qui diverge entre le constructeur du fond (qui pré-tourne les encarts
  POUR elle) et la page (qui la déclare) — les encarts pencheraient à nouveau ;
* le tableau statique, seul texte chiffré de la page pour un robot, qui ne serait plus
  écrit par le post-traitement du build.
"""
import json
import math
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

RACINE = pathlib.Path(__file__).resolve().parent.parent
WEB = RACINE / "web" / "observable"
DATA = WEB / "src" / "data"
GEO = DATA / "departements-geo.json"
CARTE = DATA / "carte.json"
NODE = shutil.which("node")

sys.path.insert(0, str(RACINE / "web" / "export"))
sys.path.insert(0, str(RACINE))

import departements                                                     # noqa: E402
import dvf_clean                                                        # noqa: E402
import fond_de_carte                                                    # noqa: E402

pytestmark = pytest.mark.skipif(not (GEO.exists() and CARTE.exists()),
                                reason="fond de carte ou carte.json absent")


def _json(p):
    return json.loads(p.read_text(encoding="utf-8"))


# --- Le fond de carte -----------------------------------------------------------------
def test_le_fond_porte_exactement_les_101_departements():
    """Ni trou, ni collectivité d'outre-mer (Nouvelle-Calédonie, Polynésie…) que la
    source porte aussi mais que le site ne couvre pas."""
    geo = _json(GEO)
    normaux = [f["properties"]["code"] for f in geo["features"]
               if not f["properties"].get("zoom")]
    assert sorted(normaux) == sorted(departements.DEPARTEMENTS)
    assert len(set(normaux)) == len(normaux), "département en double dans le fond"


def test_seuls_paris_et_la_petite_couronne_sont_agrandis():
    geo = _json(GEO)
    zoom = sorted(f["properties"]["code"] for f in geo["features"] if f["properties"].get("zoom"))
    assert zoom == sorted(fond_de_carte.ZOOM_IDF)


def test_chaque_encart_a_son_cadre():
    geo = _json(GEO)
    codes = {c["properties"]["code"] for c in geo["cadres"]}
    assert codes == set(fond_de_carte.ENCARTS) | {"idf"}


def test_le_fond_reste_leger():
    """Chargé à chaque ouverture de la page : au-delà, c'est la simplification qui a sauté."""
    assert GEO.stat().st_size < 250 * 1024, f"{GEO.stat().st_size / 1024:.0f} Ko"


def test_la_projection_est_la_meme_des_deux_cotes():
    """Le fond pré-tourne ses encarts pour UNE projection ; la page doit déclarer celle-là.

    Sans cet accord, les cadres de l'outre-mer penchent à nouveau (près de 8° mesurés
    avant correction), et rien ne le signale ailleurs qu'à l'œil."""
    hm = (WEB / "src" / "components" / "hm.js").read_text(encoding="utf-8")
    m = re.search(r'type:\s*"conic-conformal",\s*parallels:\s*\[([\d.]+),\s*([\d.]+)\],\s*'
                  r'rotate:\s*\[(-?[\d.]+),', hm)
    assert m, "projection de carteDepartements introuvable dans hm.js"
    assert (float(m.group(1)), float(m.group(2))) == fond_de_carte.PROJ_PARALLELES
    assert -float(m.group(3)) == fond_de_carte.PROJ_MERIDIEN


def test_le_redressement_compense_bien_la_convergence():
    """Contre-épreuve du redressement : un cadre posé au méridien central ne tourne pas,
    un cadre à l'ouest tourne dans le sens qui annule la convergence (antihoraire)."""
    centre = (fond_de_carte.PROJ_MERIDIEN, 46.0)
    carre = {"type": "Polygon", "coordinates": [[[3.0, 46.5], [3.5, 46.5]]]}
    assert fond_de_carte._redresser(carre, centre)["coordinates"] == [[[3.0, 46.5], [3.5, 46.5]]]
    ouest = (-7.6, 46.0)
    bord = {"type": "Polygon", "coordinates": [[[-7.6, 46.5], [-7.1, 46.5]]]}
    (a, b), = [r for r in fond_de_carte._redresser(bord, ouest)["coordinates"]]
    pente = math.degrees(math.atan2(b[1] - a[1], (b[0] - a[0]) * math.cos(math.radians(46))))
    attendu = fond_de_carte._cone() * (fond_de_carte.PROJ_MERIDIEN - ouest[0])
    assert pente > 0 and abs(pente - attendu) < 0.5, (pente, attendu)


# --- Les données de la page -----------------------------------------------------------
def test_carte_json_couvre_les_101_departements_et_suit_son_catalogue():
    carte = _json(CARTE)
    codes = [d["code"] for d in carte["departements"]]
    assert sorted(codes) == sorted(departements.DEPARTEMENTS)
    n = len(carte["indicateurs"])
    for d in carte["departements"]:
        assert len(d["v"]) == n and len(d["p"]) == n, d["code"]
    for m in carte["indicateurs"]:
        assert m["echelle"] in ("sequentielle", "divergente"), m["key"]
        assert m["periode"] and m["source"] and m["ref_libelle"], m["key"]


def test_les_departements_hors_dvf_n_ont_aucune_mesure_dvf():
    """Hachurés sur la carte, « hors DVF » dans le tableau — jamais un zéro."""
    carte = _json(CARTE)
    dvf = [i for i, m in enumerate(carte["indicateurs"]) if "DVF" in m["source"]]
    for d in carte["departements"]:
        if d["code"] in dvf_clean.DEPARTEMENTS_SANS_DVF:
            assert not d["couvert"]
            assert all(d["v"][i] is None for i in dvf), d["code"]


def test_les_rangs_sont_des_centiles():
    carte = _json(CARTE)
    for d in carte["departements"]:
        for v, p in zip(d["v"], d["p"]):
            assert (v is None) == (p is None), d["code"]
            assert p is None or 0 <= p <= 100, d["code"]


def test_aucun_nan_dans_le_json():
    """`json.dumps` écrit NaN par défaut, et JSON.parse lève dessus : toute la page tomberait."""
    assert "NaN" not in CARTE.read_text(encoding="utf-8")


def test_le_retournement_porte_ses_deux_periodes():
    """Les deux fenêtres de la mesure Territoires, sur les départements couverts par DVF."""
    fenetres = _json(CARTE)["retournement"]["fenetres"]
    assert [(f["debut"], f["fin"]) for f in fenetres] == [(2014, 2019), (2019, 2025)]
    for f in fenetres:
        assert f["n"] >= 90 and len(f["points"]) == f["n"]
        assert -1 <= f["rho"] <= 1


# --- Le tableau statique (post-traitement du build) ------------------------------------
_CARTE_HTML = ('<!DOCTYPE html>\n<html>\n<head>\n<meta charset="utf-8">\n<title>x</title>\n'
               '</head>\n<body><main id="observablehq-main">\n<h1>Carte</h1>\n'
               '<details class="hm-howto"><summary>Afficher</summary>\n'
               '<!-- hm:tableau-departements — écrit par scripts/postbuild.mjs à chaque build -->'
               '<!-- hm:tableau-departements:fin -->\n</details></main></body>\n</html>\n')


@pytest.mark.skipif(NODE is None, reason="Node.js absent")
def test_postbuild_ecrit_le_tableau_des_departements_une_seule_fois(tmp_path):
    """Écrit à chaque build depuis carte.json, REMPLACÉ au build suivant — jamais empilé.
    C'est le seul texte chiffré de la page qu'un robot lise, et le maillage interne qui
    relie la carte aux 101 pages départementales."""
    page = tmp_path / "carte.html"
    page.write_text(_CARTE_HTML, encoding="utf-8")
    for _ in range(2):
        out = subprocess.run([NODE, str(WEB / "scripts" / "postbuild.mjs"), str(tmp_path)],
                             capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert out.returncode == 0, out.stderr
    html = page.read_text(encoding="utf-8")
    assert html.count("<table") == 1, "tableau empilé ou absent"
    liens = re.findall(r'<a href="/departement/([0-9AB]{2,3})">', html)
    assert sorted(liens) == sorted(departements.DEPARTEMENTS)
    carte = _json(CARTE)
    i = [m["key"] for m in carte["indicateurs"]].index("prix_m2")
    paris = next(d for d in carte["departements"] if d["code"] == "75")
    prix = f"{round(paris['v'][i]):,}".replace(",", " ")
    # Node écrit les milliers avec une espace fine insécable (fr-FR) : on la ramène à une
    # espace ordinaire pour comparer.
    normalise = html.replace(" ", " ").replace(" ", " ")
    assert f"75 — Paris</a></td><td>{prix} €" in normalise
    for code in dvf_clean.DEPARTEMENTS_SANS_DVF:
        ligne = re.search(rf'departement/{code}">.*?</tr>', html)
        assert ligne and "hors DVF" in ligne.group(0), code
