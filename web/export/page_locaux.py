"""Page « Construction non résidentielle » — les locaux que le logement ne dit pas.

Bureaux, entrepôts, commerces, bâtiments agricoles, équipements publics : les surfaces de
locaux mises en chantier pèsent à peu près autant que celles des logements neufs, et le
site n'en disait rien. Pour un fabricant de matériaux, c'est la moitié du marché de la
construction neuve, et une moitié qui ne suit pas le cycle du logement.

Tout ici est en m² de surface de plancher : pour un local, il n'y a pas d'autre unité (un
« nombre de locaux » additionnerait un kiosque et une plateforme logistique).

Quatre choix de lecture, chacun mesuré (voir data_manager.build_locaux_from_manual_input
et le journal 05) :

* **cumul 12 mois comparé aux 12 précédents**, pas le séquentiel à 3 mois des pages
  logement : les m² commencés varient de 19 % d'un mois à l'autre, le séquentiel y vaut
  ±12,5 points — du bruit en carte de tête (ana.RAW_TWELVE_MONTHS) ;
* **niveau rapporté à 2013-2019**, pas à 2010-2019 : la série démarre en 2013. Chaque
  ligne de niveau nomme sa période, comme le taux de transformation le fait déjà ;
* **un total se lit sur les DESTINATIONS**, jamais en sommant toutes les lignes : les
  sous-destinations (hôtels, industrie, entrepôts, bureaux) sont déjà comptées dans la
  leur (voir housing_data.schema.LOCAUX) ;
* **aucun taux de transformation** des autorisations en chantiers, contrairement au
  neuf : les m² commencés ne font qu'environ deux tiers des m² autorisés, et ces données ne
  permettent pas de séparer les projets abandonnés des déclarations d'ouverture de
  chantier jamais remontées. Un ratio dont on ne sait pas ce qu'il mesure ne se publie pas.

Les locaux sont en DATE DE PRISE EN COMPTE, les logements en date réelle estimée : la
comparaison des deux se fait en cumul 12 mois, où le décalage compte le moins, et la page
le dit à chaque endroit où elle les met côte à côte.
"""
from __future__ import annotations

import pandas as pd

from commun import (COLOR_BLUE, COLOR_BRICK, COLOR_GREEN, COLOR_SUNFLOWER, COLOR_TEXT,
                    derniere_date, horodatage, iso_mois, ligne_niveau, mois_annee, pct, pt,
                    surface)
from page_marches import _yoy_kpi

import analysis as ana                          # noqa: E402
import queries as q                             # noqa: E402
from housing_data.schema import LOCAUX_DESTINATIONS, LOCAUX_SOUS_DESTINATIONS  # noqa: E402

#: Période de référence du NIVEAU. La série commence en janvier 2013 : la décennie
#: 2010-19 des pages logement n'existe pas ici, et 2013-19 en est la partie disponible —
#: même esprit (un marché ordinaire, avant le Covid et le choc de taux), fenêtre plus
#: courte, et nommée à chaque affichage.
REF_LOCAUX = ("2013", "2019")

#: Les deux mesures, dans l'ordre d'affichage : les chantiers d'abord (l'activité qui
#: consomme les matériaux), les autorisations ensuite (le signal le plus frais).
MESURES = {"SurfaceChantiers": "commencées", "SurfacePermis": "autorisées"}

#: Une couleur par destination — la palette du site en a cinq, il en faut quatre.
COULEURS = {
    "Industrie, entrepôts et bureaux": COLOR_BLUE,
    "Exploitation agricole ou forestière": COLOR_GREEN,
    "Commerce et services": COLOR_BRICK,
    "Équipements publics": COLOR_TEXT,
    "Entrepôts": COLOR_BLUE,
    "Industrie": COLOR_SUNFLOWER,
    "Bureaux": COLOR_TEXT,
    "Hôtels": COLOR_BRICK,
}
#: La destination qui contient chaque sous-destination (pour le dire, pas pour sommer).
PARENT = {"Hôtels": "Commerce et services", "Industrie": "Industrie, entrepôts et bureaux",
          "Entrepôts": "Industrie, entrepôts et bureaux",
          "Bureaux": "Industrie, entrepôts et bureaux"}


def _arr(col):
    return [None if pd.isna(v) else round(float(v), 1) for v in col]


def _ligne(roll, col, total12=None):
    """Une ligne du tableau par destination : cumul 12 mois, tendance, niveau, part."""
    s = roll.dropna(subset=[col])
    if len(s) < 24:
        return None
    mom = ana.momentum_metrics(s, col)
    lvl = ana.level_context(s, col, ref=REF_LOCAUX)
    v12 = float(s[f"{col}_12M"].iloc[-1])
    return {"val12": v12, "val12_txt": surface(v12),
            "yoy": mom["roll12_yoy"], "yoy_txt": pct(mom["roll12_yoy"]),
            "ecart_ref": lvl["gap_pct"] if lvl else None,
            "ecart_ref_txt": pct(lvl["gap_pct"]) if lvl else "—",
            "niveau": ligne_niveau(lvl),
            "part": round(v12 / total12 * 100, 1) if total12 else None}


def build_locaux(con, frames: dict) -> dict:
    cols = list(MESURES)
    total = q.monthly(con, "locaux", cols, (12,), types=LOCAUX_DESTINATIONS)
    if total.empty or total["SurfaceChantiers"].dropna().empty:
        return {"generated_at": horodatage(), "available": False}
    mois = mois_annee(derniere_date(total, "SurfaceChantiers"))

    # --- Cartes de tête : régime 12 mois, niveau 2013-19 --------------------------------
    kpis = [_yoy_kpi(ana.calculate_kpis(total, col), ana.momentum_metrics(total, col),
                     f"Surfaces de locaux {lib} (cumul 12 mois)", mois,
                     regime=ana.RAW_TWELVE_MONTHS,
                     level=ana.level_context(total, col, ref=REF_LOCAUX), fmt=surface)
            for col, lib in MESURES.items()]

    # --- Toute la construction neuve en m² : logements et locaux, côte à côte ------------
    # Cumuls 12 mois seulement : c'est là que l'écart entre les deux conventions de date
    # (réelle estimée pour les logements, prise en compte pour les locaux) pèse le moins.
    logts = q.monthly(con, "sitadel", cols, (12,)).set_index("Date")
    loc = total.set_index("Date")
    construction, part = {}, {}
    for col in cols:
        both = pd.DataFrame({"Logements": logts[f"{col}_12M"],
                             "Locaux non résidentiels": loc[f"{col}_12M"]}).dropna()
        construction[col] = [{"date": iso_mois(d), "series": nom, "value": round(v / 1e6, 3)}
                             for d, r in both.iterrows() for nom, v in r.items()]
        if both.empty:
            continue
        dernier = both.iloc[-1]
        ref = both.loc[REF_LOCAUX[0]:REF_LOCAUX[1]]
        # Part moyenne sur la période de référence, en rapport de SOMMES (et non en
        # moyenne de parts mensuelles, qui surpondérerait les mois creux).
        part_ref = (ref["Locaux non résidentiels"].sum()
                    / ref.sum(axis=1).sum() * 100) if not ref.empty else None
        p = float(dernier["Locaux non résidentiels"] / dernier.sum() * 100)
        part[col] = {"part": round(p, 1), "part_ref": round(part_ref, 1) if part_ref else None,
                     "logements": surface(dernier["Logements"]),
                     "locaux": surface(dernier["Locaux non résidentiels"]),
                     "ecart_txt": pt(p - part_ref) if part_ref else "—"}
    pc = part.get("SurfaceChantiers")
    if pc:
        kpis.append({
            "label": "Part des locaux dans la surface neuve commencée",
            "value": f"{pc['part']:.0f} %",
            "delta": f"{pc['ecart_txt']} vs {REF_LOCAUX[0]}-{REF_LOCAUX[1][-2:]}",
            "subs": [f"locaux {pc['locaux']} · logements {pc['logements']} (cumuls 12 mois)",
                     f"{pc['part_ref']:.0f} % en moyenne {REF_LOCAUX[0]}-{REF_LOCAUX[1][-2:]}"
                     .replace(".", ",")]})

    # --- Par destination et sous-destination : séries et tableau -----------------------
    tous = LOCAUX_DESTINATIONS + LOCAUX_SOUS_DESTINATIONS
    bg = q.monthly_by_group(con, "locaux", {t: [t] for t in tous}, cols, (12,))
    axe = list(total["Date"])
    series, tableau = [], []
    for t in tous:
        g = bg[bg["Groupe"] == t].sort_values("Date")
        gi = g.set_index("Date").reindex(axe)
        niveau = "Destination" if t in LOCAUX_DESTINATIONS else "Sous-destination"
        entree = {"type": t, "niveau": niveau, "parent": PARENT.get(t),
                  "color": COULEURS[t]}
        for col in cols:
            series.append({"type": t, "mesure": col, "raw": _arr(gi[col]),
                           "roll12": _arr(gi[f"{col}_12M"])})
            entree[col] = _ligne(g, col, total12=float(total[f"{col}_12M"].dropna().iloc[-1]))
        tableau.append(entree)
    tableau.append({"type": "Ensemble des locaux", "niveau": "Ensemble", "parent": None,
                    "color": None,
                    **{col: _ligne(total, col, total12=float(total[f"{col}_12M"].dropna().iloc[-1]))
                       for col in cols}})

    return {
        "generated_at": horodatage(),
        "available": True,
        "how_to_read": (
            "Toutes les valeurs sont des surfaces de plancher, en m², cumulées sur 12 mois "
            "glissants. La tendance compare les 12 derniers mois aux 12 précédents : d'un "
            "mois à l'autre, ces séries sont trop bruitées pour qu'un rythme sur trois mois "
            "veuille dire quelque chose, même corrigées des variations saisonnières. Le "
            "niveau se lit par rapport à la moyenne 2013-2019, la série commençant en 2013. "
            "Les quatre destinations s'additionnent au total ; les sous-destinations "
            "(hôtels, industrie, entrepôts, bureaux) sont un zoom à l'intérieur de la leur. "
            "Les m² commencés sont datés du jour où l'administration enregistre la "
            "déclaration, pas du premier coup de pelle : ils arrivent avec retard, et les "
            "m² autorisés sont le signal le plus frais."),
        "last_month": mois,
        "ref_label": f"{REF_LOCAUX[0]}-{REF_LOCAUX[1][-2:]}",
        "mesures": [{"key": k, "label": v} for k, v in MESURES.items()],
        "kpis": kpis,
        "construction": {"rows": construction, "part": part,
                         "meta": [{"name": "Logements", "color": COLOR_TEXT},
                                  {"name": "Locaux non résidentiels", "color": COLOR_BLUE}]},
        "par_type": {"dates": [iso_mois(d) for d in axe], "series": series},
        "tableau": tableau,
        "source": "SDES — SIT@DEL2, locaux non résidentiels (CVS-CJO, date de prise en compte)",
    }
