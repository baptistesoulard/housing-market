"""Le tableau des sources de la page « À propos » dit vrai.

Ce tableau est le seul endroit du site où un visiteur lit, pour chaque série, QUI la
produit, où la consulter et jusqu'à quand elle est publiée. Les deux dernières
informations peuvent se périmer en silence :

  * une adresse de producteur ne bouge que rarement, mais quand elle bouge, rien ne le
    signale — un lien mort sur la page qui sert justement à établir la crédibilité du
    site est plus coûteux qu'un lien absent ;
  * une date, elle, se périme À CHAQUE publication. Elle est écrite en dur dans le
    Markdown parce que la page doit rester lisible par les robots d'aperçu de partage,
    qui n'exécutent aucun JavaScript. C'est `web/export/sources_table.py` qui la réécrit,
    et ce test vérifie que la réécriture a bien eu lieu.

Le test de fraîcheur relit les CSV versionnés plutôt que l'entrepôt Parquet : c'est la
copie de référence, et cela évite d'exiger DuckDB pour vérifier une date.
"""
import os
import re
import sys

import pytest

_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_RACINE, "web", "export"))

pd = pytest.importorskip("pandas")
import sources_table as st  # noqa: E402  (après le skip)

A_PROPOS = st.A_PROPOS
_DATA = os.path.join(_RACINE, "data")


def _page():
    with open(A_PROPOS, encoding="utf-8") as f:
        return f.read()


def _lignes():
    """Les <tr> effectivement présents entre les marqueurs."""
    return re.findall(r"<tr>.*?</tr>", st.lignes_du_fichier(A_PROPOS), re.S)


def _frames():
    """Les datasets cités par SOURCES, lus dans les CSV versionnés."""
    frames = {}
    for nom in st.DATASETS:
        chemin = os.path.join(_DATA, f"{nom}.csv")
        if not os.path.exists(chemin):
            pytest.skip(f"{chemin} absent (lancer python fetch_new_sources.py)")
        frames[nom] = pd.read_csv(chemin, parse_dates=["Date"])
    return frames


def test_le_tableau_a_bien_ete_genere():
    """Les marqueurs sont là, et une ligne par source déclarée."""
    lignes = _lignes()
    assert len(lignes) == len(st.SOURCES), (
        f"{len(st.SOURCES)} sources déclarées, {len(lignes)} lignes dans a-propos.md — "
        "relancer python web/export/web_export.py")


def test_l_entete_a_autant_de_colonnes_que_les_lignes():
    """Un <th> de moins que de <td> décale toute la lecture du tableau."""
    entete = re.search(r"<thead>.*?</thead>", _page(), re.S)
    assert entete, "en-tête du tableau des sources introuvable"
    nb_th = len(re.findall(r"<th>", entete.group(0)))
    for ligne in _lignes():
        assert len(re.findall(r"<td", ligne)) == nb_th, f"cellules manquantes : {ligne}"


def test_chaque_ligne_renvoie_a_la_page_de_son_producteur():
    """Le lien est le point de la colonne : sans lui, l'intitulé n'est qu'une affirmation."""
    liens = [re.search(r'<a href="([^"]+)"', ligne) for ligne in _lignes()]
    assert all(liens), "une ligne du tableau n'a pas de lien"
    urls = [m.group(1) for m in liens]
    assert urls == [s["url"] for s in st.SOURCES], (
        "les liens du tableau ne suivent plus SOURCES — relancer l'export")
    for url in urls:
        assert url.startswith("https://"), f"lien non chiffré : {url}"


def test_aucun_intitule_en_double():
    """Deux lignes du même nom pointant vers deux séries différentes sont illisibles."""
    mesures = [s["mesure"] for s in st.SOURCES]
    assert len(set(mesures)) == len(mesures), "intitulés en double dans SOURCES"


def test_chaque_source_pointe_vers_des_colonnes_qui_existent():
    """Une colonne renommée ferait afficher « — » sans que rien n'échoue.

    C'est le mode de panne silencieux de ce tableau : la date disparaît, la page reste
    valide, et personne ne le voit."""
    frames = _frames()
    for s in st.SOURCES:
        df = frames[s["dataset"]]
        manquantes = [c for c in s["colonnes"] if c not in df.columns]
        assert not manquantes, (
            f"« {s['mesure']} » : colonne(s) absente(s) de {s['dataset']}.csv : "
            f"{manquantes}")
        assert not pd.isna(st.dernier_point(frames, s)), (
            f"« {s['mesure']} » : aucune observation, la page afficherait « — »")


def test_les_dates_publiees_sont_celles_des_donnees():
    """Si ce test échoue, ce ne sont pas les données qu'il faut corriger : c'est le
    tableau d'a-propos.md qu'il faut régénérer, par `python web/export/web_export.py`."""
    attendu = st.render_tbody(_frames())
    assert st.lignes_du_fichier(A_PROPOS) == attendu, (
        "les dates du tableau des sources ont dérivé — relancer "
        "python web/export/web_export.py")


@pytest.mark.parametrize("freq,mois,attendu", [
    ("M", "2026-06-01", "juin 2026"),
    ("M", "2026-01-01", "janvier 2026"),
    ("T", "2026-01-01", "T1 2026"),
    ("T", "2026-04-01", "T2 2026"),
    ("T", "2026-10-01", "T4 2026"),
])
def test_libelle_de_periode(freq, mois, attendu):
    """Les séries trimestrielles sont posées sur le 1er mois du trimestre : afficher
    « avril 2026 » pour un point trimestriel laisserait croire à une donnée mensuelle."""
    assert st.libelle_periode(pd.Timestamp(mois), freq) == attendu
