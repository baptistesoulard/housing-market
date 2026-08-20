"""Les renvois de la page Synthèse pointent vers des pages qui existent.

Ces liens sont construits dans le NAVIGATEUR (`index.md` lit `blocks[].links` de
synthese.json et fabrique l'href), donc la validation de liens d'Observable Framework,
qui ne regarde que le Markdown, ne les voit pas. Renommer un chemin dans
`observablehq.config.js` sans toucher `web_export.py` ne casserait donc rien au build :
le site se construirait sans avertissement, et le clic donnerait un 404 en production.

C'est ce trou-là que ferme ce test — il compare les chemins des deux côtés.
"""
import json
import pathlib
import re

WEB = pathlib.Path(__file__).resolve().parent.parent / "web" / "observable"
CONFIG = WEB / "observablehq.config.js"
SYNTHESE = WEB / "src" / "data" / "synthese.json"


def _declared_paths():
    """Les chemins de la barre latérale, lus dans le tableau NAV de la config."""
    nav = re.search(r"const NAV = \[(.*?)\n\];", CONFIG.read_text(encoding="utf-8"), re.S)
    assert nav, "tableau NAV introuvable dans observablehq.config.js"
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
