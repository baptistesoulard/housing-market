"""Page « Carte des départements » : les 101 départements côte à côte, en DESCRIPTION.

Ce que la page montre, et ce qu'elle s'interdit :

* une mesure par carte, OBSERVÉE et datée — prix, évolutions, ventes, profil INSEE —,
  chacune avec son rang parmi les départements renseignés et sa valeur de référence ;
* aucun score, aucun classement de « gagnants » : la porte du module Territoires a été
  manquée (docs/mesure-territoires-2026-09-20.md), c'est-à-dire qu'aucun croisement de ces
  mesures n'a su dire où les prix iraient. La page le montre au lieu de le taire : la
  section « retournement » trace la relation âge du parc → prix sur les deux fenêtres de
  la mesure, et la pente s'y inverse.

Le fond de carte n'est PAS produit ici : il est construit une fois par
`web/export/fond_de_carte.py` et versionné (les limites des départements ne bougent pas).
Ce module n'écrit que les valeurs, colonnaires par indicateur pour tenir le poids bas.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from commun import horodatage, mois_annee
from page_departements import DUREE_REF_ANS, MENSUALITE_REF

import departements                             # noqa: E402
import dvf_clean                                # noqa: E402
import queries as q                             # noqa: E402

#: Les deux fenêtres de la mesure Territoires, FIGÉES comme la mesure elle-même : le
#: recensement dont on part, puis les deux années de prix comparées (voir
#: mesure_territoires.FENETRES). Ce sont les mêmes départements, les mêmes calculs, sur
#: les données du jour — le graphique ne réinterprète rien.
FENETRES_RETOURNEMENT = [
    {"millesime": 2012, "debut": 2014, "fin": 2019},
    {"millesime": 2017, "debut": 2019, "fin": 2025},
]

#: Le catalogue des mesures cartographiables. `echelle` : « sequentielle » pour une
#: grandeur (une teinte, du clair au foncé), « divergente » pour un écart de part et
#: d'autre d'un pivot (deux teintes, gris au pivot). `ref` dit ce que vaut la référence
#: affichée — la France quand un ratio national existe, sinon le département médian, et
#: la page le nomme. Aucune mesure n'est « meilleure » vers le haut : les couleurs ne
#: portent pas de jugement, seulement une intensité ou un sens.
INDICATEURS = [
    # --- Prix et marché (DVF) -----------------------------------------------------------
    {"key": "prix_m2", "groupe": "Prix et ventes", "label": "Prix médian au m²",
     "unite": "euro", "echelle": "sequentielle", "source": "DVF (DGFiP)"},
    {"key": "evol_1an", "groupe": "Prix et ventes", "label": "Évolution du prix au m² sur un an",
     "unite": "pct_signe", "echelle": "divergente", "source": "DVF (DGFiP)"},
    {"key": "evol_5ans", "groupe": "Prix et ventes",
     "label": "Évolution du prix au m² sur cinq ans",
     "unite": "pct_signe", "echelle": "divergente", "source": "DVF (DGFiP)"},
    {"key": "m2_accessibles", "groupe": "Prix et ventes",
     "label": f"m² achetés avec {MENSUALITE_REF:,} € par mois sur {DUREE_REF_ANS} ans".replace(",", " "),
     "unite": "m2", "echelle": "sequentielle",
     "source": "DVF (DGFiP) et taux de crédit (Banque de France)"},
    {"key": "ventes_hab", "groupe": "Prix et ventes",
     "label": "Ventes sur un an, pour 1 000 habitants",
     "unite": "decimal", "echelle": "sequentielle", "source": "DVF (DGFiP) et recensement (INSEE)"},
    {"key": "evol_ventes", "groupe": "Prix et ventes",
     "label": "Évolution des ventes sur un an",
     "unite": "pct_signe", "echelle": "divergente", "source": "DVF (DGFiP)"},
    # --- Habitants (recensement INSEE, mêmes libellés que les pages départementales) ------
    {"key": "part_rp_65", "groupe": "Habitants et logements",
     "label": "Résidences principales détenues par un ménage de 65 ans ou plus",
     "unite": "pct", "echelle": "sequentielle", "source": "recensement (INSEE)"},
    {"key": "part_65", "groupe": "Habitants et logements", "label": "Habitants de 65 ans et plus",
     "unite": "pct", "echelle": "sequentielle", "source": "recensement (INSEE)"},
    {"key": "part_maisons", "groupe": "Habitants et logements",
     "label": "Part de maisons parmi les résidences principales",
     "unite": "pct", "echelle": "sequentielle", "source": "recensement (INSEE)"},
    {"key": "taux_vacance", "groupe": "Habitants et logements", "label": "Logements vacants",
     "unite": "pct", "echelle": "sequentielle", "source": "recensement (INSEE)"},
    {"key": "taux_arrivee", "groupe": "Habitants et logements",
     "label": "Habitants arrivés d'un autre département dans l'année",
     "unite": "pct", "echelle": "sequentielle", "source": "recensement (INSEE)"},
    {"key": "solde_migratoire", "groupe": "Habitants et logements",
     "label": "Solde migratoire apparent, par an",
     "unite": "pct_signe", "echelle": "divergente", "source": "recensement et état civil (INSEE)",
     "note": ("arrivées moins départs, rapportés à la population, entre deux recensements "
              "— il mesure autant la pénurie de logements que l'attrait : Paris y est "
              "dernier")},
    {"key": "niveau_vie", "groupe": "Habitants et logements", "label": "Niveau de vie médian",
     "unite": "euro_an", "echelle": "sequentielle", "source": "Filosofi (INSEE)"},
]
_PROFIL = {"part_rp_65", "part_65", "part_maisons", "taux_vacance", "taux_arrivee",
           "solde_migratoire", "niveau_vie"}


def _percentiles(valeurs: dict) -> dict:
    """Part des AUTRES départements renseignés strictement en dessous (0-100).

    Même définition que `queries.territoires_profil` (percent_rank) : un rang « plus haut
    que 81 % des autres » doit vouloir dire la même chose sur la carte et sur la page du
    département."""
    presents = {k: v for k, v in valeurs.items() if v is not None}
    n = len(presents)
    tri = sorted(presents.values())
    out = {}
    for k, v in presents.items():
        dessous = sum(1 for w in tri if w < v)
        out[k] = int(round(100 * dessous / (n - 1))) if n > 1 else None
    return out


def _mediane(valeurs):
    xs = [v for v in valeurs if v is not None]
    return float(np.median(xs)) if xs else None


def _spearman(x, y):
    """ρ de Spearman, rangs moyens en cas d'égalité — la définition de la mesure."""
    return float(np.corrcoef(pd.Series(x).rank(), pd.Series(y).rank())[0, 1])


def _libelle_trimestre(date_iso):
    if not date_iso:
        return None
    y, m = int(date_iso[:4]), int(date_iso[5:7])
    return f"T{(m - 1) // 3 + 1} {y}"


def build_carte(con, frames: dict) -> dict:
    codes = sorted(departements.DEPARTEMENTS)
    couverts = {c: c not in dvf_clean.DEPARTEMENTS_SANS_DVF for c in codes}
    dernier = {d["code"]: d for d in q.dvf_departements(con)}
    ventes = {r["code"]: r for r in q.dvf_ventes_annuelles(con)}
    pop = q.territoires_colonnes(con, ["Population"])

    val = {ind["key"]: {} for ind in INDICATEURS}
    france = {}
    millesime = None
    for c in codes:
        d = dernier.get(c)
        if couverts[c] and d:
            val["prix_m2"][c] = d["prix_m2"]
            val["evol_1an"][c] = q.dvf_evolution(con, c, 1)
            val["evol_5ans"][c] = q.dvf_evolution(con, c, 5)
            cap = q.dvf_surface_accessible(con, c, MENSUALITE_REF, DUREE_REF_ANS)
            val["m2_accessibles"][c] = cap["m2_aujourdhui"] if cap else None
            v = ventes.get(c) or {}
            habitants = (pop.get(c) or {}).get("Population")
            val["ventes_hab"][c] = (round(1000 * v["ventes"] / habitants, 2)
                                    if v.get("ventes") and habitants else None)
            val["evol_ventes"][c] = (round((v["ventes"] / v["ventes_prec"] - 1) * 100, 1)
                                     if v.get("ventes") and v.get("ventes_prec") else None)
        profil = q.territoires_profil(con, c)
        if profil:
            millesime = profil["millesime"]
            for it in profil["items"]:
                val[it["key"]][c] = it["v"]
                france.setdefault(it["key"], it["fr"])

    # Référence des mesures DVF : le département MÉDIAN, jamais une moyenne que
    # l'Île-de-France écraserait (même convention que `queries.dvf_national_median`).
    for ind in INDICATEURS:
        if ind["key"] not in _PROFIL:
            med = _mediane(val[ind["key"]].get(c) for c in codes)
            france[ind["key"]] = round(med, 2) if med is not None else None

    # Les références du profil sont des ratios France quand le recensement le permet, le
    # département médian sinon — exactement comme sur les pages départementales.
    ref_mediane = {"solde_migratoire", "niveau_vie"}
    date_dvf = max((d["date"] for d in dernier.values()), default=None)
    periode_dvf = _libelle_trimestre(date_dvf)
    indicateurs = []
    for ind in INDICATEURS:
        k = ind["key"]
        profil = k in _PROFIL
        if profil:
            periode = f"recensement {millesime}" if millesime else None
            if k == "niveau_vie" and millesime:
                periode = f"Filosofi {millesime}"
        elif k in ("evol_1an", "evol_5ans"):
            recul = "un an" if k == "evol_1an" else "cinq ans"
            periode = (f"{periode_dvf}, comparé au même trimestre {recul} plus tôt"
                       if periode_dvf else None)
        elif k in ("ventes_hab", "evol_ventes"):
            periode = (f"quatre trimestres jusqu'au {periode_dvf}"
                       + (" contre les quatre précédents" if k == "evol_ventes" else ""))
        elif k == "m2_accessibles":
            periode = f"prix du {periode_dvf}, taux de crédit du dernier mois publié"
        else:
            periode = periode_dvf
        indicateurs.append({
            **ind, "periode": periode, "ref": france.get(k),
            "ref_libelle": ("département médian" if (not profil or k in ref_mediane)
                            else "France"),
            "n": sum(1 for c in codes if val[k].get(c) is not None)})

    lignes = []
    pcts = {k: _percentiles({c: val[k].get(c) for c in codes}) for k in val}
    for c in codes:
        lignes.append({
            "code": c, "nom": departements.nom(c), "couvert": couverts[c],
            "v": [val[ind["key"]].get(c) for ind in INDICATEURS],
            "p": [pcts[ind["key"]].get(c) for ind in INDICATEURS]})

    fenetres = []
    for f in FENETRES_RETOURNEMENT:
        pts = q.territoires_retournement(con, f["millesime"], f["debut"], f["fin"])
        if len(pts) < 10:
            continue
        rho = _spearman(np.array([p["x"] for p in pts]), np.array([p["y"] for p in pts]))
        fenetres.append({**f, "n": len(pts), "rho": round(rho, 2),
                         "points": [{"code": p["code"], "nom": departements.nom(p["code"]),
                                     "x": p["x"], "y": p["y"]} for p in pts]})

    return {
        "generated_at": horodatage(),
        "periode_dvf": periode_dvf,
        "date_dvf": date_dvf,
        "date_dvf_libelle": mois_annee(date_dvf) if date_dvf else None,
        "millesime_rp": millesime,
        "indicateurs": indicateurs,
        "departements": lignes,
        "retournement": {
            "x_label": "Indice d'âge du parc (part de propriétaires × part des 65 ans et plus)",
            "y_label": "Croissance du prix au m², en écart au département médian (points)",
            "fenetres": fenetres,
        },
    }
