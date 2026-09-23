"""Les 101 pages départementales (DVF + profil INSEE) : un fichier par département + un annuaire."""
from __future__ import annotations

import os

from commun import DATA_DIR, horodatage
from ecriture import ecrire_si_change

import departements                             # noqa: E402
import dvf_clean                                # noqa: E402
import queries as q                             # noqa: E402


# Régime À PART des sept JSON nationaux, et c'est délibéré.
#
# Les sept pages nationales tiennent chacune dans un fichier chargé à l'ouverture. Les
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


def build_departement(con, code: str, national) -> dict:
    """Le JSON d'UN département. Traite franchement le cas « non couvert par DVF »."""
    couvert = code not in dvf_clean.DEPARTEMENTS_SANS_DVF
    payload = {
        "code": code,
        "nom": departements.nom(code),
        "region": departements.region(code),
        "couvert": couvert,
        "source": "DVF (DGFiP) — licence ouverte v2",
    }
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

    Volontairement HORS de `_BUILDERS` : le compteur « n/7 fichier(s) modifié(s) » des
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

    modifies, total = 0, 0
    for code in codes:
        payload = build_departement(con, code, national)
        payload["generated_at"] = horodatage()
        chemin = os.path.join(DEPARTEMENTS_DIR, f"{code}.json")
        if ecrire_si_change(chemin, payload):
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

    if ecrire_si_change(os.path.join(DATA_DIR, "departements.json"), index):
        modifies += 1
    print(f"[web_export] departements : {modifies} fichier(s) modifie(s) sur "
          f"{len(codes) + 1} | poids total {total / 1024:.0f} Ko, "
          f"moyenne {total / len(codes) / 1024:.1f} Ko")
    return modifies
