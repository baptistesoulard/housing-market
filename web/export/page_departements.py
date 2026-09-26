"""Les 101 pages départementales (DVF + profil INSEE) : un fichier par département + un annuaire."""
from __future__ import annotations

import os

from commun import DATA_DIR, horodatage
from ecriture import ecrire_si_change
from mesures import locaux_indicateurs, percentiles

import departements                             # noqa: E402
import dvf_clean                                # noqa: E402
import queries as q                             # noqa: E402


# Régime À PART des huit JSON nationaux, et c'est délibéré.
#
# Les huit pages nationales tiennent chacune dans un fichier chargé à l'ouverture. Les
# départements, eux, sont 101 : un fichier unique les contenant tous ferait télécharger
# le pays entier à quelqu'un qui veut voir le sien. D'où un fichier PAR département,
# chargé à la demande, plus un index léger pour le sélecteur.
#
# Le format est COLONNAIRE (les dates une fois, les valeurs en tableaux nus) alors que le
# reste du site utilise des listes d'objets. Sur 48 trimestres × 3 types, répéter la clé
# « prix_m2 » 144 fois coûte plus que la donnée elle-même. Le front recompose.
#
# BUDGET : 10 Ko bruts par département, vérifié à l'écriture (voir _verifier_budget).
# Repère : la page « Marché du neuf » sert 504 Ko à chaque visite, donc la marge existe —
# ce n'est pas une raison pour la dépenser.
#
# Les fichiers sont écrits COMPACTS (sans indentation) depuis le 2026-09-26 : le plus
# gros touchait 9,95 Ko sur 10, l'indentation en pesait près de la moitié, et le bloc des
# locaux non résidentiels n'y entrait plus. Compacts, les 101 passent de 919 à ~500 Ko.

DEPARTEMENTS_DIR = os.path.join(DATA_DIR, "departements")
BUDGET_OCTETS = 10 * 1024

# Hypothèse d'emprunt du chiffre « combien de m² ». Une mensualité ronde et une durée
# usuelle : le but n'est pas de simuler un dossier mais de donner une unité de mesure
# comparable d'un département à l'autre. Affichée sur la page, jamais implicite.
MENSUALITE_REF = 1000
DUREE_REF_ANS = 20


def _colonnes(serie, cles):
    """[{date, a, b}, …] → {"dates": [...], "a": [...], "b": [...]}."""
    out = {"dates": [r["date"] for r in serie]}
    for k in cles:
        out[k] = [r.get(k) for r in serie]
    return out


def _locaux(con, code: str, terr: dict | None, ind: dict | None, rang: int | None):
    """Le bloc « locaux non résidentiels » d'un département : cumuls 12 mois (courant,
    précédent, niveau 2013-19) pour les m² autorisés et commencés, m² commencés par
    destination, repères par habitant, et les années civiles complètes.

    SIT@DEL couvre les 101 départements, y compris les quatre hors DVF : le bloc est donc
    posé AVANT le retour anticipé des départements non couverts."""
    if not terr:
        return None
    arrondi = lambda v: None if v is None else int(round(v))
    annuel = q.locaux_annuel(con, code)
    return {
        "date": terr["date"],
        "com": [arrondi(terr[f"Chantiers_Ensemble_{s}"]) for s in ("12m", "prec", "ref")],
        "aut": [arrondi(terr[f"Permis_Ensemble_{s}"]) for s in ("12m", "prec", "ref")],
        # L'ordre des destinations est celui de l'annuaire (`locaux_france.destinations`).
        "dest": [arrondi(terr[f"Chantiers_{c}_12m"]) for c in LOCAUX_DESTINATIONS],
        "ent": arrondi(terr["Chantiers_Entrepots_12m"]),
        "hab": (ind or {}).get("hab"), "p_hab": rang,
        "annuel": {"annees": [a["annee"] for a in annuel],
                   "aut": [a["Permis_Ensemble"] for a in annuel],
                   "com": [a["Chantiers_Ensemble"] for a in annuel],
                   "dest": [[a[f"Chantiers_{c}"] for a in annuel] for c in LOCAUX_DESTINATIONS]},
    }


#: Les quatre destinations, dans l'ordre des colonnes du dataset (clé → libellé du site,
#: le même que sur la page « Construction non résidentielle »).
LOCAUX_DESTINATIONS = ["Agricole", "Commerce", "Public", "Activites"]


def build_departement(con, code: str, national, locaux=None) -> dict:
    """Le JSON d'UN département. Traite franchement le cas « non couvert par DVF »."""
    couvert = code not in dvf_clean.DEPARTEMENTS_SANS_DVF
    payload = {
        "code": code,
        "nom": departements.nom(code),
        "region": departements.region(code),
        "couvert": couvert,
        "source": "DVF (DGFiP) — licence ouverte v2",
    }
    if locaux:
        payload["locaux"] = locaux
    # Le profil INSEE (recensement) est indépendant de DVF : les quatre départements hors
    # DVF le reçoivent aussi — c'est la première fois que leur page porte un chiffre.
    # None quand le recensement ne couvre pas le département (Mayotte) : la page le dit.
    profil = q.territoires_profil(con, code)
    if profil:
        # La valeur France de chaque repère est la MÊME pour les 101 fichiers : elle vit
        # dans l'annuaire (`profil_france`), pas ici — 101 copies d'une constante, c'est
        # ce qui avait amené le plus gros fichier à 150 octets du budget.
        payload["profil"] = {"millesime": profil["millesime"],
                             "items": [{k: v for k, v in it.items() if k != "fr"}
                                       for it in profil["items"]]}
    if not couvert:
        # Ces quatre départements relèvent du Livre foncier (Alsace-Moselle) ou ne sont
        # pas couverts (Mayotte). La page le DIT au lieu d'afficher des graphiques vides :
        # une absence expliquée vaut mieux qu'un blanc qui passe pour une panne.
        payload["absence"] = (
            "Le fichier DVF de la DGFiP ne couvre pas ce département. "
            "L'Alsace et la Moselle relèvent du Livre foncier, un régime de publicité "
            "foncière distinct hérité du droit local ; Mayotte n'y figure pas non plus. "
            "Il ne s'agit pas d'un trou temporaire : aucune année n'est publiée.")
        return payload

    ensemble = q.dvf_series(con, code, "Ensemble")
    if not ensemble:
        payload["couvert"] = False
        payload["absence"] = "Aucune vente retenue pour ce département après nettoyage."
        return payload

    payload["ensemble"] = _colonnes(ensemble, ["prix_m2", "prix", "ventes"])
    for label, cle in (("Maison", "maison"), ("Appartement", "appartement")):
        serie = q.dvf_series(con, code, label)
        if serie:
            # Les dates d'un type peuvent différer de celles de l'ensemble (un type sans
            # vente un trimestre n'a pas de ligne) : chaque bloc porte donc SES dates.
            payload[cle] = _colonnes(serie, ["prix_m2", "ventes"])

    payload["dernier"] = q.dvf_dernier(con, code)
    payload["evolution"] = {
        "un_an": q.dvf_evolution(con, code, 1),
        "cinq_ans": q.dvf_evolution(con, code, 5),
    }
    payload["capacite"] = q.dvf_surface_accessible(con, code, MENSUALITE_REF, DUREE_REF_ANS)
    # La référence nationale est la MÊME pour les 101 pages : la répéter dans chacune
    # coûterait 100 fois sa taille. Elle vit dans l'index, que le front charge de toute
    # façon pour son sélecteur ; on ne garde ici que le dernier point, pour le cartouche.
    payload["national_dernier"] = national[-1] if national else None
    return payload


def _verifier_budget(chemin, code):
    """Un département hors budget est une régression de performance, pas un détail."""
    taille = os.path.getsize(chemin)
    if taille > BUDGET_OCTETS:
        print(f"[web_export] ATTENTION departement {code} : {taille / 1024:.1f} Ko "
              f"> budget {BUDGET_OCTETS / 1024:.0f} Ko")
    return taille


def build_departements(con) -> int:
    """Écrit l'index + un fichier par département. Renvoie le nombre de fichiers modifiés.

    Volontairement HORS de `_BUILDERS` : le compteur « n/8 fichier(s) modifié(s) » des
    pages nationales est un signal de régression (un diff inattendu sur l'un des sept
    signale une divergence de calcul), et le noyer dans un total à 107 lui ferait perdre
    tout pouvoir d'alerte.
    """
    os.makedirs(DEPARTEMENTS_DIR, exist_ok=True)
    national = q.dvf_national_median(con)
    codes = sorted(departements.DEPARTEMENTS)

    index = {
        "generated_at": horodatage(),
        "mensualite_ref": MENSUALITE_REF,
        "duree_ref_ans": DUREE_REF_ANS,
        # La série nationale, une seule fois pour tout le site.
        "national": _colonnes(national, ["prix_m2", "ventes"]),
        "departements": [],
    }
    dispo = {d["code"]: d for d in q.dvf_departements(con)}
    # Les valeurs France du profil INSEE, une fois pour tout le site (voir build_departement).
    # Prises sur un département couvert quelconque : elles ne dépendent pas du département.
    for code in codes:
        profil = q.territoires_profil(con, code)
        if profil:
            index["profil_france"] = {"millesime": profil["millesime"],
                                      **{it["key"]: it["fr"] for it in profil["items"]}}
            break

    # Les locaux non résidentiels : une requête pour les 101, les repères par habitant et
    # leur rang calculés par les MÊMES fonctions que la carte (mesures.locaux_indicateurs,
    # mesures.percentiles) — un département doit lire ici le chiffre de sa couleur là-bas.
    vues = {r[0] for r in q._cur(con).execute(
        "SELECT view_name FROM duckdb_views() WHERE NOT internal").fetchall()}
    terr = {t["code"]: t for t in q.locaux_territoires(con)}         if "locaux_departements" in vues else {}
    pop = {c: (v or {}).get("Population")
           for c, v in q.territoires_colonnes(con, ["Population"]).items()}
    ind = locaux_indicateurs(list(terr.values()), pop)
    rangs = percentiles({c: v["hab"] for c, v in ind["par_code"].items()})
    if terr:
        from housing_data.schema import LOCAUX_DESTINATIONS as _LIBELLES
        index["locaux_france"] = {
            "date": next(iter(terr.values()))["date"], "ref_label": "2013-19",
            **ind["france"],
            # Clés du dataset → libellés du site, dans l'ordre des tableaux `dest`.
            "destinations": dict(zip(LOCAUX_DESTINATIONS, _LIBELLES)),
        }

    modifies, total = 0, 0
    for code in codes:
        payload = build_departement(
            con, code, national,
            locaux=_locaux(con, code, terr.get(code), ind["par_code"].get(code), rangs.get(code)))
        payload["generated_at"] = horodatage()
        chemin = os.path.join(DEPARTEMENTS_DIR, f"{code}.json")
        if ecrire_si_change(chemin, payload, compact=True):
            modifies += 1
        total += _verifier_budget(chemin, code)
        d = dispo.get(code)
        index["departements"].append({
            "code": code,
            "nom": payload["nom"],
            "region": payload["region"],
            "couvert": payload["couvert"],
            "prix_m2": (d or {}).get("prix_m2"),
        })

    if ecrire_si_change(os.path.join(DATA_DIR, "departements.json"), index, compact=True):
        modifies += 1
    print(f"[web_export] departements : {modifies} fichier(s) modifie(s) sur "
          f"{len(codes) + 1} | poids total {total / 1024:.0f} Ko, "
          f"moyenne {total / len(codes) / 1024:.1f} Ko")
    return modifies
