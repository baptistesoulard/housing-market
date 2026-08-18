"""Chargement du thème partagé + génération de sa projection JavaScript.

`web/theme.json` est la source unique de vérité des couleurs du front. Ce module la lit
pour le Python (les métadonnées de séries sérialisées dans les JSON portent une couleur)
et régénère `web/observable/src/components/theme.js`, la même palette sous forme de module
ESM que les pages Observable importent — plus aucun littéral hexadécimal dupliqué entre
Python, le CSS et les pages.

Le troisième consommateur, `observablehq.config.js`, lit `theme.json` directement en Node
(fs) pour émettre les variables CSS `--hm-*`.
"""
from __future__ import annotations

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_WEB_DIR = os.path.abspath(os.path.join(_HERE, ".."))

THEME_PATH = os.path.join(_WEB_DIR, "theme.json")
THEME_JS_PATH = os.path.join(_WEB_DIR, "observable", "src", "components", "theme.js")


def load() -> dict:
    """Le thème complet, tel qu'écrit dans theme.json."""
    with open(THEME_PATH, encoding="utf-8") as f:
        return json.load(f)


THEME = load()

# Rampe catégorielle des graphiques (ordre fixe — voir la note `_doc` de theme.json).
SERIES = THEME["series"]
BRAND = THEME["brand"]
STATUS = THEME["status"]
UI = THEME["ui"]

# Alias lisibles pour les builders (les slots, pas les jetons de marque).
S_BRICK = SERIES["brick"]
S_BLUE = SERIES["blue"]
S_GREEN = SERIES["green"]
S_VIOLET = SERIES["violet"]
S_GOLD = SERIES["gold"]


def write_theme_js(path: str = THEME_JS_PATH) -> str:
    """(Re)génère le module ESM lu par les pages Observable. Renvoie le chemin écrit."""
    payload = {k: v for k, v in THEME.items() if not k.startswith("_")}
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    js = (
        "// GÉNÉRÉ par web/export/theme.py — NE PAS ÉDITER À LA MAIN.\n"
        "// Source de vérité : web/theme.json  ·  régénérer : python web/export/web_export.py\n"
        f"export const THEME = {body};\n\n"
        "export const {brand, series, status, delta, ui} = THEME;\n"
        "\n// Rampe catégorielle dans son ordre d'assignation (jamais cyclée).\n"
        "export const SERIES_ORDER = [series.brick, series.blue, series.green,"
        " series.violet, series.gold];\n"
    )
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(js)
    return path
