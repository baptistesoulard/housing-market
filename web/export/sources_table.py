"""Le tableau des sources de la page « À propos », régénéré depuis les données.

Pourquoi un module à part, et pourquoi générer du Markdown.

La page « À propos » doit rester du HTML rendu AU BUILD : c'est, avec l'accueil, le seul
texte du site que lisent les robots d'aperçu de partage, qui n'exécutent aucun JavaScript
(voir CLAUDE.md, « Le site public »). Or la date du dernier point de chaque série change
à chaque publication. Les deux contraintes sont inconciliables côté navigateur : un bloc
de code JS remplirait les cellules pour un visiteur et laisserait le tableau vide pour
tout robot — donc pour l'aperçu au partage et pour l'indexation.

D'où le sens de génération retenu : la chaîne Python ÉCRIT les lignes du tableau dans
`a-propos.md`, entre deux marqueurs, et le fichier ainsi complété est commité comme les
JSON du front. La page reste 100 % statique, et les dates ne dérivent pas.

Le module est séparé de `web_export.py` parce qu'il ne dépend que de pandas : le test qui
verrouille les dates peut donc l'importer sans construire l'entrepôt Parquet ni charger
DuckDB.
"""
from __future__ import annotations

import os

import pandas as pd

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
A_PROPOS = os.path.join(_REPO_ROOT, "web", "observable", "src", "a-propos.md")

# Les lignes vivent entre ces deux marqueurs, DANS le <tbody>. Tout ce qui est en dehors
# (l'en-tête, la prose, le reste de la page) est écrit à la main et n'est jamais touché.
DEBUT = "<!-- hm:sources:début — lignes régénérées par web/export/sources_table.py -->"
FIN = "<!-- hm:sources:fin -->"

_MOIS = ["janvier", "février", "mars", "avril", "mai", "juin",
         "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

# Une ligne = UNE page source et UNE périodicité.
#
# Le tableau d'origine groupait « confiance des ménages, intentions d'achat, chômage BIT »
# sur une seule ligne. Impossible d'y accrocher un lien (trois pages INSEE distinctes) ni
# une date (les deux premières sont mensuelles, le chômage BIT est trimestriel) : la ligne
# a donc été éclatée. Même raison pour les prix anciens / neufs, et pour Euribor / OAT qui
# ne viennent pas du même jeu de données BCE.
#
# `colonnes` peut en compter plusieurs quand elles partagent page ET périodicité ; la date
# retenue est alors la PLUS ANCIENNE des dernières observations, c'est-à-dire la borne
# jusqu'à laquelle la ligne est réellement complète.
#
# Les adresses sont les pages de consultation destinées à un lecteur, pas les points
# d'entrée d'API interrogés par `fetch_new_sources.py` : un visiteur qui clique doit
# tomber sur la série et sa documentation, pas sur un CSV. Elles sont recensées dans
# data_manual_input/Data source.txt, qui reste la fiche détaillée de chaque série.
SOURCES = [
    {"mesure": "Logements autorisés et commencés (SIT@DEL)",
     "url": "https://www.data.gouv.fr/datasets/logements-autorises-et-commences-nombre-"
            "et-surfaces-series-mensuelles-donnees-estimees-1",
     "producteur": "SDES", "acces": "API DiDo (data.gouv.fr)",
     "dataset": "sitadel", "colonnes": ("Permis", "MisesEnChantier"), "freq": "M"},
    {"mesure": "Commercialisation des logements neufs (ECLN)",
     "url": "https://www.data.gouv.fr/datasets/donnees-nationales-sur-la-"
            "commercialisation-des-logements-neufs",
     "producteur": "SDES", "acces": "API DiDo (data.gouv.fr)",
     "dataset": "ecln", "colonnes": ("Reservations",), "freq": "T"},
    {"mesure": "Ventes de logements anciens",
     "url": "https://www.igedd.developpement-durable.gouv.fr/"
            "prix-immobilier-evolution-a-long-terme-a1048.html",
     "producteur": "IGEDD", "acces": "Classeur publié",
     "dataset": "ventes_ancien", "colonnes": ("Transactions",), "freq": "M"},
    {"mesure": "Prix des logements anciens",
     "url": "https://www.insee.fr/fr/statistiques/serie/010567059",
     "producteur": "Notaires-INSEE", "acces": "API SDMX (BDM)",
     "dataset": "macro", "colonnes": ("Prix_Ancien_Ensemble",), "freq": "T"},
    {"mesure": "Prix des logements neufs",
     "url": "https://www.insee.fr/fr/statistiques/serie/010751595",
     "producteur": "INSEE", "acces": "API SDMX (BDM)",
     "dataset": "macro", "colonnes": ("Prix_Neuf",), "freq": "T"},
    {"mesure": "Confiance des ménages",
     "url": "https://www.insee.fr/fr/statistiques/serie/001587668",
     "producteur": "INSEE", "acces": "API SDMX (BDM)",
     "dataset": "macro", "colonnes": ("Insee_Confiance_Menages",), "freq": "M"},
    {"mesure": "Intentions d'achat de logement",
     "url": "https://www.insee.fr/fr/statistiques/serie/001616794",
     "producteur": "INSEE", "acces": "API SDMX (BDM)",
     "dataset": "macro", "colonnes": ("Intentions_Achat_Logement",), "freq": "M"},
    {"mesure": "Taux de chômage au sens du BIT",
     "url": "https://www.insee.fr/fr/statistiques/serie/001688527",
     "producteur": "INSEE", "acces": "API SDMX (BDM)",
     "dataset": "macro", "colonnes": ("Taux_Chomage_BIT",), "freq": "T"},
    {"mesure": "Activité du second œuvre (rénovation)",
     "url": "https://www.insee.fr/fr/statistiques/serie/001586954",
     "producteur": "INSEE — enquête de conjoncture", "acces": "API SDMX (BDM)",
     "dataset": "macro", "colonnes": ("Reno_Activite_Batiment", "Reno_Activite_Prevue"),
     "freq": "M"},
    {"mesure": "Taux et volume des crédits nouveaux à l'habitat",
     "url": "https://data.ecb.europa.eu/data/datasets/MIR",
     "producteur": "Banque de France / BCE", "acces": "API SDMX (MIR)",
     "dataset": "macro",
     "colonnes": ("Credit_Logement_Taux_Interet", "Production_Credits_Habitat"),
     "freq": "M"},
    {"mesure": "Demande de crédits habitat (enquête BLS)",
     "url": "https://data.ecb.europa.eu/data/datasets/BLS",
     "producteur": "BCE / Banque de France", "acces": "API SDMX (BLS)",
     "dataset": "macro",
     "colonnes": ("Demande_Credit_Realisee", "Demande_Credit_Perspectives"), "freq": "T"},
    {"mesure": "Euribor 3 mois",
     "url": "https://data.ecb.europa.eu/data/datasets/FM",
     "producteur": "BCE", "acces": "API SDMX (FM)",
     "dataset": "macro", "colonnes": ("Euribor_3M",), "freq": "M"},
    {"mesure": "OAT 10 ans",
     "url": "https://data.ecb.europa.eu/data/datasets/IRS",
     "producteur": "BCE", "acces": "API SDMX (IRS)",
     "dataset": "macro", "colonnes": ("OAT_10ans",), "freq": "M"},
]

DATASETS = sorted({s["dataset"] for s in SOURCES})


def dernier_point(frames: dict, source: dict):
    """Date de la dernière observation NON VIDE de la ligne, ou NaT.

    Sur plusieurs colonnes, on prend la plus ancienne : une ligne n'est complète que
    jusqu'à la date où sa série la moins à jour s'arrête. Annoncer la plus récente
    laisserait croire que tout est publié jusque-là."""
    df = frames.get(source["dataset"])
    if df is None or df.empty:
        return pd.NaT
    dates = []
    for col in source["colonnes"]:
        if col not in df.columns:
            continue
        valides = df.dropna(subset=[col])
        if not valides.empty:
            dates.append(pd.Timestamp(valides["Date"].max()))
    return min(dates) if dates else pd.NaT


def libelle_periode(date, freq: str) -> str:
    """« juin 2026 » pour une série mensuelle, « T2 2026 » pour une trimestrielle.

    Les séries trimestrielles sont posées sur le 1er mois du trimestre (voir
    fetch_new_sources), donc le trimestre se déduit du mois sans ambiguïté."""
    if date is None or pd.isna(date):
        return "—"
    d = pd.Timestamp(date)
    if freq == "T":
        return f"T{(d.month - 1) // 3 + 1} {d.year}"
    return f"{_MOIS[d.month - 1]} {d.year}"


def render_tbody(frames: dict) -> str:
    """Les lignes du tableau, indentées comme le reste de la page."""
    lignes = []
    for s in SOURCES:
        quand = libelle_periode(dernier_point(frames, s), s["freq"])
        lignes.append(
            f'    <tr><td><a href="{s["url"]}">{s["mesure"]}</a></td>'
            f'<td>{s["producteur"]}</td><td>{s["acces"]}</td>'
            f'<td class="hm-when">{quand}</td></tr>')
    return "\n".join(lignes)


def ecrire(frames: dict, path: str = A_PROPOS) -> bool:
    """Réécrit les lignes du tableau entre les marqueurs. True si le fichier a changé.

    Même garde que les JSON du front : sans changement de date, aucun octet n'est touché,
    donc le rafraîchissement hebdomadaire ne produit pas de diff pour rien."""
    with open(path, encoding="utf-8") as f:
        avant = f.read()
    i, j = avant.find(DEBUT), avant.find(FIN)
    if i < 0 or j < 0:
        raise ValueError(f"marqueurs hm:sources introuvables dans {path}")
    apres = avant[:i + len(DEBUT)] + "\n" + render_tbody(frames) + "\n    " + avant[j:]
    if apres == avant:
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(apres)
    return True


def lignes_du_fichier(path: str = A_PROPOS) -> str:
    """Le bloc actuellement dans le fichier, pour comparaison (tests)."""
    with open(path, encoding="utf-8") as f:
        src = f.read()
    i, j = src.find(DEBUT), src.find(FIN)
    if i < 0 or j < 0:
        raise ValueError(f"marqueurs hm:sources introuvables dans {path}")
    return src[i + len(DEBUT):j].strip("\n").rstrip()
