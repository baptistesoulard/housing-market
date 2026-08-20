"""Les renvois de la page Synthèse pointent vers des pages qui existent.

Ces liens sont construits dans le NAVIGATEUR (`synthese.md` lit `blocks[].links` de
synthese.json et fabrique l'href), donc la validation de liens d'Observable Framework,
qui ne regarde que le Markdown, ne les voit pas. Renommer un chemin dans
`site.config.js` sans toucher `web_export.py` ne casserait donc rien au build : le site se
construirait sans avertissement, et le clic donnerait un 404 en production.

C'est ce trou-là que ferme ce test — il compare les chemins des deux côtés.
"""
import json
import pathlib
import re

WEB = pathlib.Path(__file__).resolve().parent.parent / "web" / "observable"
# La navigation vit dans site.config.js — observablehq.config.js ne porte que le rendu.
CONFIG = WEB / "site.config.js"
SYNTHESE = WEB / "src" / "data" / "synthese.json"
ARCHIVE = WEB / "src" / "data" / "archive.json"
INDEX = WEB / "src" / "index.md"


def _declared_paths():
    """Les chemins de la barre latérale, lus dans le tableau NAV de la config."""
    nav = re.search(r"const NAV = \[(.*?)\n\];", CONFIG.read_text(encoding="utf-8"), re.S)
    assert nav, "tableau NAV introuvable dans site.config.js"
    return set(re.findall(r'path:\s*"([^"]+)"', nav.group(1)))


def test_shortcut_paths_exist():
    blocks = json.loads(SYNTHESE.read_text(encoding="utf-8"))["blocks"]
    declared = _declared_paths()
    used = {link["path"] for b in blocks for link in b["links"]}
    assert used, "aucun renvoi dans synthese.json"
    assert used <= declared, f"chemins inconnus : {sorted(used - declared)}"


def test_shortcut_labels_match_the_sidebar():
    """Le libellé du renvoi est celui de l'onglet : deux noms pour une même page
    obligeraient le lecteur à faire le rapprochement lui-même."""
    src = CONFIG.read_text(encoding="utf-8")
    nav = re.search(r"const NAV = \[(.*?)\n\];", src, re.S).group(1)
    names = dict(zip(re.findall(r'path:\s*"([^"]+)"', nav),
                     re.findall(r'name:\s*"([^"]+)"', nav)))
    blocks = json.loads(SYNTHESE.read_text(encoding="utf-8"))["blocks"]
    for b in blocks:
        for link in b["links"]:
            assert link["label"] == names[link["path"]], (
                f"{link['path']} : « {link['label']} » côté Synthèse, "
                f"« {names[link['path']]} » côté barre latérale")


# --- La bande de chiffres de l'accueil ------------------------------------------------
# Ces quatre nombres sont écrits en DUR dans index.md, et c'est délibéré : ils doivent
# être lus par les robots d'aperçu de partage, qui n'exécutent pas de JavaScript (voir le
# commentaire de la page). Trois d'entre eux sont des constantes de fait — profondeur
# d'historique, nombre de producteurs, cadence du rafraîchissement. Le quatrième, lui,
# est recalculé à chaque publication de données : sans garde, il dérive en silence et
# l'accueil finit par annoncer une performance que la page « Prévisions passées »
# contredit deux clics plus loin.
_ERREUR_6M = "Erreur moyenne à 6 mois"


def _chiffres_de_l_accueil():
    """Les couples (nombre, légende) de la bande <ul class="hm-stats"> de l'accueil."""
    src = INDEX.read_text(encoding="utf-8")
    bande = re.search(r'<ul class="hm-stats">(.*?)</ul>', src, re.S)
    assert bande, "bande de chiffres introuvable dans index.md"
    couples = re.findall(
        r'<span class="n">(.*?)</span>\s*<span class="d">(.*?)</span>',
        bande.group(1), re.S)
    assert len(couples) == 4, f"4 chiffres attendus dans la bande, {len(couples)} trouvés"
    return [(n.strip(), " ".join(d.split())) for n, d in couples]


def _kpi_archive(label):
    kpis = json.loads(ARCHIVE.read_text(encoding="utf-8"))["kpis"]
    trouve = [k for k in kpis if k["label"] == label]
    assert trouve, f"KPI « {label} » absent d'archive.json"
    return trouve[0]


def test_l_erreur_annoncee_sur_l_accueil_est_celle_de_l_archive():
    """L'accueil et la page « Prévisions passées » doivent citer le MÊME chiffre.

    Si ce test échoue, ce n'est pas archive.json qu'il faut corriger : c'est la valeur
    codée dans la bande de chiffres de web/observable/src/index.md qu'il faut reporter.
    """
    kpi = _kpi_archive(_ERREUR_6M)
    modele = next(n for n, d in _chiffres_de_l_accueil() if "erreur moyenne à 6 mois" in d)
    assert modele == kpi["value"], (
        f"l'accueil annonce {modele} d'erreur à 6 mois, l'archive {kpi['value']} — "
        "reporter la valeur dans la bande de chiffres d'index.md")


def test_l_accueil_cite_aussi_la_reference_naive():
    """Le chiffre du modèle ne se publie jamais seul.

    Isolé, il laisse croire que le modèle bat la référence naïve à tous les horizons,
    alors qu'il lui est INFÉRIEUR en deçà de quatre mois (voir « Prévisions passées »).
    La légende doit donc porter l'erreur naïve, et la même que l'archive.
    """
    kpi = _kpi_archive(_ERREUR_6M)
    naif = re.search(r"([\d,]+\s*%)", " ".join(kpi["subs"]))
    assert naif, f"erreur naïve absente des sous-titres du KPI « {_ERREUR_6M} »"
    legende = next(d for n, d in _chiffres_de_l_accueil() if "erreur moyenne à 6 mois" in d)
    assert naif.group(1) in legende, (
        f"l'accueil doit citer l'erreur naïve ({naif.group(1)}) à côté de celle du "
        f"modèle ; légende actuelle : « {legende} »")
