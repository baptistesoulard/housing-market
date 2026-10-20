"""Pages « Crédit & conjoncture » et « Actualités & Aides ».

Deux pages de contexte : la première publie les séries macro-financières telles quelles
(aucun jugement), la seconde met en forme la veille curatée d'`actualites.py`.
"""
from __future__ import annotations

import pandas as pd

from commun import (COLOR_BLUE, COLOR_BRICK, COLOR_GREEN, COLOR_TEXT, horodatage, jalons_a_venir,
                    jour_mois_annee, mois_annee)

import actualites as actu                       # noqa: E402
import queries as q                             # noqa: E402


def build_macro(con, frames: dict) -> dict:
    macro_cols = q.macro_data_columns(con)

    def series(col):
        return q.macro_series(con, col, digits=4)

    # Taux : format long des 3 séries togglables.
    rate_defs = [("Credit_Logement_Taux_Interet", "Taux Crédit Habitat (toutes durées)", COLOR_TEXT),
                 ("Euribor_3M", "Euribor 3 mois", COLOR_BLUE),
                 ("OAT_10ans", "OAT 10 ans", COLOR_GREEN)]
    rate_rows, rate_meta = [], []
    for col, name, color in rate_defs:
        if col in macro_cols:
            rate_meta.append({"name": name, "color": color})
            for r in series(col):
                rate_rows.append({"date": r["date"], "series": name, "value": r["value"]})

    # Intentions d'achat : centrées-réduites (z-score, SQL).
    intentions = q.macro_zscore(con, "Intentions_Achat_Logement", digits=4) \
        if "Intentions_Achat_Logement" in macro_cols else []

    # Volume de crédits (mensuel stacked + cumul 12m), conditionnel.
    credit = None
    if "Production_Credits_Habitat" in macro_cols:
        has_split = "Production_Credits_Pure" in macro_cols
        monthly = []
        if has_split:
            monthly = q.rows(con, """
                SELECT strftime(Date, '%Y-%m-%d') AS date,
                       Production_Credits_Pure AS pure, Production_Credits_Renego AS renego
                FROM macro WHERE Production_Credits_Pure IS NOT NULL ORDER BY Date""")
        # Cumuls 12m calculés sur les lignes où Habitat est renseigné (même axe qu'avant) :
        # `pure` reste NULL tant que sa fenêtre de 12 n'est pas pleine (min_periods=12).
        pure_expr = (", CASE WHEN COUNT(Production_Credits_Pure) OVER w = 12 "
                     "THEN SUM(Production_Credits_Pure) OVER w END AS pure") if has_split else ""
        cum = q.rows(con, f"""
            WITH s AS (SELECT * FROM macro WHERE Production_Credits_Habitat IS NOT NULL)
            SELECT strftime(Date, '%Y-%m-%d') AS date,
                   CASE WHEN COUNT(Production_Credits_Habitat) OVER w = 12
                        THEN SUM(Production_Credits_Habitat) OVER w END AS total{pure_expr}
            FROM s
            WINDOW w AS (ORDER BY Date ROWS BETWEEN 11 PRECEDING AND CURRENT ROW)
            QUALIFY total IS NOT NULL
            ORDER BY Date""")
        credit = {"has_split": has_split, "monthly": monthly, "cum": cum}

    # Demande de crédits (BLS), conditionnel.
    bls = None
    if "Demande_Credit_Perspectives" in macro_cols:
        rows = []
        for col, name in (("Demande_Credit_Realisee", "Réalisé (3 derniers mois)"),
                          ("Demande_Credit_Perspectives", "Perspectives (3 prochains mois)")):
            if col in macro_cols:
                for r in series(col):
                    rows.append({"date": r["date"], "series": name, "value": r["value"]})
        bls = {"rows": rows,
               "meta": [{"name": "Réalisé (3 derniers mois)", "color": "#9AA5B1"},
                        {"name": "Perspectives (3 prochains mois)", "color": COLOR_BRICK, "dash": None}]}

    # Rénovation, conditionnel.
    reno_defs = [("Reno_Activite_Batiment", "Activité passée — second œuvre", COLOR_BRICK),
                 ("Reno_Activite_Prevue", "Activité prévue — second œuvre", COLOR_GREEN)]
    reno = [{"title": name, "color": color, "rows": series(col)}
            for col, name, color in reno_defs if col in macro_cols]

    return {
        "generated_at": horodatage(),
        "title": "🏦 Contexte Macroéconomique et Financement",
        "caption": ("Indicateurs de contexte macroéconomique et de conditions de financement : confiance "
                    "des ménages (INSEE), taux du crédit habitat (BdF/BCE), Euribor 3 mois et OAT 10 ans "
                    "(BCE), intentions d'achat de logement et taux de chômage BIT (INSEE)."),
        "how_to_read": (
            "Ces indicateurs expliquent le marché plus qu'ils ne le décrivent, et la plupart le "
            "précèdent.\n\n"
            "Les soldes d'opinion (confiance, intentions d'achat, rénovation, demande de crédits) "
            "se lisent en écart à leur repère — le zéro ou la moyenne de longue période — et non "
            "en niveau absolu : c'est leur mouvement qui informe.\n\n"
            "La demande de crédits (enquête BLS) paraît avant les chiffres de ventes. Testée "
            "comme indicateur avancé, elle n'a pourtant pas amélioré la prévision du site : la "
            "mesure est publiée sur la page Méthode de la prévision.\n\n"
            "Dans les volumes de crédit, les renégociations sont isolées : elles ne déclenchent "
            "ni vente ni chantier."),
        "confidence": series("Insee_Confiance_Menages"),
        "rates": {"rows": rate_rows, "meta": rate_meta},
        "intentions": intentions,
        "chomage": series("Taux_Chomage_BIT"),
        "credit": credit,
        "bls": bls,
        "renovation": reno,
    }


def build_actualites(con, frames: dict) -> dict:
    items_all = actu.items_sorted()
    L = "FR"

    def item_dict(it):
        echs = [(d, lbl) for d, lbl, typ in it.get("jalons", []) if typ == "echeance"]
        return {
            "id": it["id"], "categorie": it["categorie"], "statut": it["statut"],
            "court": it["court"][L], "titre": it["titre"][L], "resume": it["resume"][L],
            "montant": it["montant"][L] if it.get("montant") else None,
            "horizon": it["horizon"][L], "impacts": it["impacts"],
            "impact_detail": it["impact_detail"][L],
            "echeance": ({"date": jour_mois_annee(echs[0][0]),
                          "label": echs[0][1][L]} if echs else None),
            "jalons": [{"date": pd.Timestamp(d).strftime("%Y-%m-%d"), "label": lbl[L], "type": typ}
                       for d, lbl, typ in it.get("jalons", [])],
            "sources": [{"label": lbl, "url": url} for lbl, url in it["sources"]],
        }

    items = [item_dict(it) for it in items_all]
    n_vigueur = sum(1 for it in items_all if it["statut"] == "vigueur")
    next_jalons = jalons_a_venir(items_all)
    kpis = [
        {"label": "Dispositifs suivis", "value": str(len(items_all))},
        {"label": "En vigueur", "value": str(n_vigueur)},
        {"label": actu.CHIFFRE_CLE["label"], "value": actu.CHIFFRE_CLE["value"],
         "subs": [actu.CHIFFRE_CLE["sub"]]},
    ]
    if next_jalons:
        nd, nit, nlbl = next_jalons[0]
        kpis.append({"label": "Prochaine échéance", "value": mois_annee(nd),
                     "subs": [f"{nit['court']['FR']} — {nlbl}"]})

    return {
        "generated_at": horodatage(),
        "title": "📰 Actualités — aides & plans de relance logement",
        "caption": ("Veille sur les grands dispositifs publics français et européens qui soutiennent (ou "
                    "freinent) le marché du logement, avec pour chaque mesure : statut, jalons, montants et "
                    "impact potentiel sur les trois piliers du modèle (neuf, ancien, rénovation)."),
        "how_to_read": (
            "Chaque mesure est notée de ⬇⬇ (frein fort) à ⬆⬆ (soutien fort) sur le neuf, "
            "l'ancien et la rénovation, selon le sens et l'intensité de l'effet attendu : c'est "
            "une appréciation d'auteur, révisable, pas un résultat calculé.\n\n"
            "Le statut distingue ce qui est en vigueur de ce qui est seulement adopté ou en "
            "discussion : seules les mesures en vigueur agissent déjà sur les chiffres des autres "
            "pages."),
        "maj": actu.MAJ,
        "maj_fr": jour_mois_annee(actu.MAJ),
        "kpis": kpis,
        "items": items,
        "impact_labels": actu.IMPACT_LABELS[L],
        "pilier_labels": actu.PILIERS[L],
        "statut_labels": actu.STATUTS[L],
        "category_labels": actu.CATEGORIES[L],
        "jalon_types": {k: {"label": v[L], "symbol": v["symbol"]} for k, v in actu.JALON_TYPES.items()},
    }
