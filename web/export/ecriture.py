"""Le point d'écriture UNIQUE des JSON du front : arrondi, garde de contenu, horodatage exclu.

Tout fichier publié passe par `ecrire_si_change` — les sept JSON nationaux, l'annuaire et
les 101 départements. Aucun appelant n'a donc à penser à l'arrondi ni à la garde.
"""
from __future__ import annotations

import json
import os


def sans_horodatage(payload):
    """Le payload privé de son horodatage — la partie qui décide s'il a vraiment changé."""
    return {k: v for k, v in payload.items() if k != "generated_at"}


#: Précision d'écriture des flottants, en CHIFFRES SIGNIFICATIFS (et non en décimales).
#:
#: Le payload mêle des comptes de ventes (~9,5 × 10⁵) et des coefficients (~10⁻³) : un
#: nombre de décimales fixe écraserait les seconds ou laisserait les premiers bruités.
#:
#: Pourquoi 9 plutôt que 12 ou 15 : la dérive à absorber vit au 16ᵉ chiffre, donc n'importe
#: quelle troncature la couvre. Ce qui départage, c'est le risque qu'une valeur tombe
#: exactement sur une frontière d'arrondi et bascule quand même d'une machine à l'autre —
#: il vaut environ 10^(N−17) par valeur. À 12 chiffres c'est ~10⁻⁵, soit une occurrence
#: attendue sur les ~25 000 flottants publiés ; à 9 chiffres c'est ~10⁻⁸, donc jamais.
#: Et 9 chiffres restent très au-delà de tout besoin d'affichage : 935 815,187 ventes.
PRECISION_JSON = 9


def arrondir_flottants(o):
    """Arrondit tout flottant du payload à `PRECISION_JSON` chiffres significatifs.

    POURQUOI. Le job hebdomadaire (runner Linux) et un export lancé en local écrivaient
    des valeurs qui diffèrent d'un ULP — `935815.186488427` contre `935815.1864884269` —
    parce que l'algèbre linéaire de numpy n'est pas compilée de la même façon des deux
    côtés. Ce n'est pas un problème de mise en forme : ce sont deux doubles distincts.

    Sans arrondi, les deux environnements se repoussent `previsions.json` indéfiniment,
    chacun reformatant les décimales de l'autre — 814 lignes de diff pour zéro
    information. Et surtout le compteur « n/7 fichier(s) modifié(s) » perd son POUVOIR
    D'ALERTE, qui est sa seule raison d'être : un fichier qui bouge à chaque exécution ne
    signale plus rien quand il bouge pour de bon.

    Les booléens sont des entiers en Python et les entiers sont exacts : ni les uns ni les
    autres ne passent par ici. `numpy.float64` hérite de `float`, donc il est couvert.
    """
    if isinstance(o, bool) or isinstance(o, int):
        return o
    if isinstance(o, float):
        if o != o or o in (float("inf"), float("-inf")):
            return o                     # NaN / inf : pas notre sujet, laissés visibles
        return float(f"%.{PRECISION_JSON}g" % o)
    if isinstance(o, dict):
        return {k: arrondir_flottants(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [arrondir_flottants(v) for v in o]
    return o


def ecrire_si_change(path, payload):
    """Écrit le JSON uniquement si son contenu a réellement changé, `generated_at` exclu
    de la comparaison.

    `generated_at` étant l'horloge murale, une écriture inconditionnelle produirait un
    diff sur les 5 fichiers à CHAQUE passage, y compris quand aucune donnée n'a bougé —
    le refresh hebdomadaire committerait donc du bruit toutes les semaines. Même
    garde-fou que _write_if_changed dans fetch_new_sources.py, avec la même conséquence
    utile : « Généré le » affiché par le front date de la dernière évolution réelle des
    données, pas de la dernière exécution du script. Renvoie True si le fichier a été
    (ré)écrit."""
    # Arrondi AVANT sérialisation, et donc avant la comparaison : les deux côtés sont
    # alors traités à la même précision (voir `arrondir_flottants`). Point de passage
    # unique — les 7 JSON nationaux, l'annuaire et les 101 fichiers départementaux
    # passent tous par ici, donc aucun appelant n'a à y penser.
    payload = arrondir_flottants(payload)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                old = json.load(f)
        except (OSError, json.JSONDecodeError):
            old = None                      # illisible / tronqué -> on réécrit
        if old is not None:
            # Comparer le payload APRÈS un aller-retour JSON : la sérialisation convertit
            # les clés non-str en str (impact_labels est indexé par des int), si bien que
            # l'objet Python et sa relecture ne sont jamais égaux tels quels — sans cela
            # actualites.json serait réécrit à chaque passage.
            if sans_horodatage(old) == sans_horodatage(json.loads(text)):
                return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return True
