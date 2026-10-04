"""Ce qui a changé d'une publication à l'autre — le journal daté de l'accueil et du flux RSS.

Un baromètre se lit à intervalles réguliers ; encore faut-il que le lecteur qui revient
voie ce qui a bougé depuis sa dernière visite, sans avoir à le reconstituer. Ce module
compare les payloads qui viennent d'être calculés à ceux qui sont sur le disque (la
publication précédente, telle que commitée) et en tire des lignes datées :

* une source publie un nouveau mois ;
* la projection des ventes change d'horizon, de sens ou d'ampleur (au point près) ;
* une pastille de la Synthèse change de couleur.

Le journal (`changements.json`) est lu par l'accueil (section « Revenir ») et par
`scripts/postbuild.mjs`, qui en écrit le flux RSS (`/flux.xml`). Il ne s'écrit que s'il
y a quelque chose à dire : une semaine sans nouveauté ne produit ni ligne ni diff.

Hors du compteur « n/9 » de web_export.py, comme les pages départementales : ce n'est pas
le calcul d'une page mais l'historique de leurs différences.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

#: Nombre d'entrées datées conservées (une par publication qui a changé quelque chose).
GARDER = 30

_PASTILLE = {"up": "🟢", "flat": "🟠", "down": "🔴"}


def _fraicheur(synth: dict | None) -> dict:
    """{ce que la source compte: dernier point publié}, depuis « libellé : valeur »."""
    out = {}
    for ligne in (synth or {}).get("freshness") or []:
        libelle, _, valeur = ligne.partition(" : ")
        out[libelle] = valeur
    return out


def _mouvement(v: dict) -> str:
    ampleur = f"{abs(v['change_pct']):.0f} %".replace(".", ",")
    return {"hausse": f"en hausse d'environ {ampleur}",
            "baisse": f"en recul d'environ {ampleur}",
            "stable": "à peu près stables"}.get(v.get("direction"), "sans direction nette")


def _cle_verdict(v: dict | None):
    if not v:
        return None
    return (v.get("target_month"), v.get("direction"), round(v.get("change_pct") or 0))


def _phrase_verdict(v: dict) -> str:
    return (f"ventes de logements anciens projetées {_mouvement(v)} d'ici "
            f"{v['target_month']}")


def evenements(avant_synth: dict | None, apres_synth: dict,
               avant_prev: dict | None, apres_prev: dict) -> list[str]:
    """Les lignes à publier pour cette publication — vide si rien n'a bougé.

    Sans publication précédente (premier passage), une ligne d'état tient lieu de point
    de départ : elle dit ce qui est en vigueur, pas ce qui a changé, et le dit."""
    v_apres = (apres_prev or {}).get("verdict")
    if avant_synth is None:
        etat = "Ouverture de ce journal. Derniers mois publiés — " + " · ".join(
            f"{k} : {v}" for k, v in _fraicheur(apres_synth).items()) + "."
        lignes = [etat]
        if v_apres:
            lignes.append(f"Prévision en vigueur : {_phrase_verdict(v_apres)}.")
        return lignes

    lignes = []
    avant_f, apres_f = _fraicheur(avant_synth), _fraicheur(apres_synth)
    for libelle, valeur in apres_f.items():
        if libelle in avant_f and avant_f[libelle] != valeur:
            lignes.append(f"Nouvelles données — {libelle} : {valeur}.")

    v_avant = (avant_prev or {}).get("verdict")
    if v_apres and _cle_verdict(v_apres) != _cle_verdict(v_avant):
        phrase = f"Prévision mise à jour : {_phrase_verdict(v_apres)}"
        if v_avant:
            phrase += f" (contre {_mouvement(v_avant)} d'ici {v_avant['target_month']} jusqu'ici)"
        lignes.append(phrase + ".")

    avant_p = {p["key"]: p for p in (avant_synth.get("pillars") or [])}
    for p in apres_synth.get("pillars") or []:
        a = avant_p.get(p["key"])
        if a and a.get("status") != p.get("status"):
            lignes.append(f"{p['label']} : {p['word']} "
                          f"({_PASTILLE.get(a['status'], '⚪')} → {_PASTILLE.get(p['status'], '⚪')}).")
    return lignes


def lire(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def ajouter(journal: dict | None, lignes: list[str], jour: str) -> dict:
    """Le journal avec les lignes du jour en tête (fusionnées si le jour existe déjà)."""
    entrees = list((journal or {}).get("entrees") or [])
    if lignes:
        if entrees and entrees[0]["date"] == jour:
            deja = entrees[0]["items"]
            entrees[0] = {"date": jour, "items": deja + [l for l in lignes if l not in deja]}
        else:
            entrees.insert(0, {"date": jour, "items": lignes})
    return {"entrees": entrees[:GARDER]}


def aujourd_hui() -> str:
    return datetime.now(timezone.utc).date().isoformat()
