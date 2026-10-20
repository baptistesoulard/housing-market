"""Les affirmations CHIFFRÉES de l'accueil qui bougent, réécrites dans `index.md`.

L'accueil doit rester du HTML rendu au build : c'est, avec À propos, le seul texte du site
que lisent les robots d'aperçu de partage, qui n'exécutent aucun JavaScript. Deux de ses
affirmations dépendent pourtant des données :

* l'erreur moyenne du modèle dans le bandeau de chiffres ;
* l'horizon en deçà duquel le modèle fait moins bien qu'une prévision naïve ;
* depuis le 2026-10-04, la RÉPONSE à la question du titre (« Où en est le marché du
  logement en France ? ») : la projection des ventes, l'état du marché en une phrase et
  le dernier mois publié par les sources. La question restait sans réponse à l'écran — la
  réponse vivait sur la Synthèse, à un clic — et c'est le texte qui décide un visiteur
  arrivé d'un lien à rester. Aucune page n'avait la prévision elle-même dans son HTML.

Écrites à la main, elles ont dérivé toutes les deux : le bandeau citait l'erreur à six
mois du MILLÉSIME (5,7 % contre 5,9 %) pendant que la Synthèse annonçait sa prévision
« dans six mois » du LECTEUR (rang 9, 6,3 % contre 8,3 %) — deux « six mois » qui ne
désignaient pas le même horizon —, et « à moins de quatre mois » était resté écrit alors
que l'archive plaçait la bascule à six. Un test les attrapait, mais seulement quand
quelqu'un lançait les tests ; le job hebdomadaire, lui, publiait sans.

D'où le même sens de génération que le tableau des sources d'À propos : la chaîne Python
ÉCRIT ces deux passages entre des marqueurs, et `index.md` ainsi complété est commité par
le job hebdomadaire comme les JSON du front. La page reste 100 % statique et ne dérive
plus. Tout le reste de la page est écrit à la main et n'est jamais touché.

Le module ne dépend que de la bibliothèque standard : le test qui verrouille l'accueil
(tests/test_web_links.py) l'importe sans construire l'entrepôt.
"""
from __future__ import annotations

import os

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
INDEX = os.path.join(_REPO_ROOT, "web", "observable", "src", "index.md")

#: (début, fin) de chaque passage régénéré.
MARQUEURS = {
    "erreur": ("<!-- hm:erreur:début — régénéré par web/export/accueil.py -->",
               "<!-- hm:erreur:fin -->"),
    "bascule": ("<!-- hm:bascule — régénéré par web/export/accueil.py -->",
                "<!-- hm:bascule:fin -->"),
    "reponse": ("<!-- hm:reponse:début — régénéré par web/export/accueil.py -->",
                "<!-- hm:reponse:fin -->"),
}

#: Les passages qui sont des BLOCS (retours à la ligne autour) ; la bascule est en ligne.
_BLOCS = ("erreur", "reponse")

_LETTRES = ("zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf",
            "dix", "onze", "douze", "treize", "quatorze", "quinze", "seize", "dix-sept",
            "dix-huit")


def en_lettres(n: int) -> str:
    """Un petit nombre en toutes lettres — un chiffre au milieu d'une phrase se lit mal."""
    return _LETTRES[n] if 0 <= n < len(_LETTRES) else str(n)


def _pct(v: float) -> str:
    return f"{v:.1f} %".replace(".", ",")


def bandeau_erreur(verdict: dict | None, depuis: str | None) -> str | None:
    """L'item du bandeau : l'erreur à l'horizon du VERDICT, pas à un rang de millésime.

    C'est le même horizon que la prévision publiée sur la Synthèse et sur « Prévision &
    Scénarios » — « dans six mois » veut dire six mois pour qui lit, partout. Le chiffre
    vient de prévisions RÉTRO-SIMULÉES (recalculées après coup), et l'item le dit : la page
    « Prévisions passées » refuse d'agréger rétro-simulées et publiées, l'accueil n'a pas
    à les confondre non plus. L'erreur naïve est citée à côté : seul, le chiffre du modèle
    laisserait croire qu'il bat la référence à tous les horizons.

    None si le modèle n'a pas de verdict à cette publication : l'appelant garde alors
    l'item en place plutôt que de publier un trou.
    """
    rel = (verdict or {}).get("reliability")
    if not rel or rel.get("mape") is None or rel.get("naive_mape") is None:
        return None
    periode = f" depuis {depuis}" if depuis else ""
    return (
        "  <li>\n"
        f'    <span class="n">{_pct(rel["mape"])}</span>\n'
        # L'échéance est NOMMÉE (« pour une échéance comme avril 2027 ») : « à six mois »
        # se lisait comme l'horizon « six mois » de la page « Le modèle face au réel », qui
        # se compte depuis le dernier chiffre publié et donne un autre chiffre.
        f'    <span class="d">d\'erreur moyenne pour une échéance comme '
        f'{verdict["target_month"]} (<abbr title="recalculées après coup en tronquant les '
        f'données au mois visé">prévisions rétro-simulées</abbr>{periode}) ; '
        f"{_pct(rel['naive_mape'])} pour une prévision naïve</span>\n"
        "  </li>")


def phrase_bascule(crossover: int | None) -> str:
    """Où le modèle perd contre une prévision naïve, compté depuis le dernier chiffre publié.

    `crossover` est le premier horizon (en mois après le dernier mois de données) où le
    modèle fait mieux que la naïve — la même définition que la page « Prévisions
    passées ». L'horizon se compte ici depuis le dernier chiffre PUBLIÉ, et la phrase le
    dit : c'est l'autre convention du site, et elle doit se nommer.
    """
    if crossover is None:
        return "à aucun horizon, le modèle ne fait mieux qu'une prévision naïve"
    if crossover <= 1:
        return "le modèle fait mieux qu'une prévision naïve dès le premier mois"
    if crossover == 2:
        return ("le premier mois qui suit le dernier chiffre publié, le modèle fait moins "
                "bien qu'une prévision naïve")
    return (f"sur les {en_lettres(crossover - 1)} premiers mois qui suivent le dernier "
            "chiffre publié, le modèle fait moins bien qu'une prévision naïve")


def _milliers(v: float) -> str:
    return f"{int(round(float(v), -3)):,}".replace(",", " ")


def chiffre_projection(verdict: dict | None) -> tuple[str, str] | None:
    """La projection des ventes en UN chiffre, puis sa légende : (« −5 % », « de ventes de
    logements anciens d'ici avril 2027, dans six mois : de 951 000 à 902 000… »).

    Le chiffre est ce qu'un visiteur retient du premier écran ; il était noyé dans une
    phrase de soixante mots, en gras parmi le reste (2026-10-20). Le sens est porté par le
    signe — un vrai signe moins, pas un tiret. L'horizon se compte devant le LECTEUR
    (« dans six mois »), la convention du verdict, et la légende le nomme.
    """
    if not verdict or verdict.get("direction") not in ("hausse", "baisse", "stable"):
        return None
    mois = f"d'ici {verdict['target_month']}"
    dans = f"dans {en_lettres(int(verdict['months_ahead']))} mois"
    if verdict["direction"] == "stable":
        chiffre = "Stable"
        tete = f"pour les ventes de logements anciens {mois}"
        trajet = (f" : autour de {_milliers(verdict['predicted'])} ventes sur douze mois"
                  if verdict.get("predicted") else "")
    else:
        signe = "−" if verdict["direction"] == "baisse" else "+"
        chiffre = f"{signe}{abs(verdict['change_pct']):.0f} %".replace(".", ",")
        tete = f"de ventes de logements anciens {mois}"
        trajet = (f" : de {_milliers(verdict['from_value'])} à "
                  f"{_milliers(verdict['predicted'])} ventes sur douze mois"
                  if verdict.get("from_value") and verdict.get("predicted") else "")
    # Deux lignes à l'écran : la tête en gras sous le chiffre, la suite en dessous — qui
    # continue la phrase, d'où sa minuscule.
    return chiffre, (f'<strong>{tete}</strong> <span class="s">{dans}{trajet}, selon le '
                     "modèle du site.</span>")


def bloc_reponse(previsions: dict, synthese: dict) -> str | None:
    """La réponse sous le titre : le chiffre de la projection, l'état du marché, le
    dernier mois publié.

    None si la Synthèse n'a pas de résumé : le passage reste alors tel quel."""
    resume = (synthese or {}).get("resume")
    if not resume:
        return None
    lignes = ['<div class="hm-reponse">']
    projection = chiffre_projection((previsions or {}).get("verdict"))
    if projection:
        chiffre, legende = projection
        lignes.append(f'<p class="hm-reponse-chiffre"><span class="n">{chiffre}</span> '
                      f'<span class="l">{legende}</span></p>')
    lignes.append(f"<p>{resume}</p>")
    if synthese.get("dernier_mois"):
        lignes.append(
            f'<p class="hm-reponse-maj">Dernier mois publié par les sources : '
            f"{synthese['dernier_mois']} — elles paraissent avec quelques mois de "
            "décalage.</p>")
    lignes.append("</div>")
    return "\n".join(lignes)


def rendu(previsions: dict, archive: dict, synthese: dict | None = None) -> dict:
    """{marqueur: texte à placer entre ses bornes}, ou None pour un passage à laisser tel quel."""
    retro = ((archive or {}).get("kinds") or {}).get("retro") or {}
    premier = retro.get("first_vintage")
    return {
        "erreur": bandeau_erreur((previsions or {}).get("verdict"),
                                 premier[:4] if premier else None),
        "bascule": phrase_bascule((archive or {}).get("crossover_horizon")),
        "reponse": bloc_reponse(previsions, synthese or {}),
    }


def _bornes(src: str, cle: str, path: str):
    debut, fin = MARQUEURS[cle]
    i, j = src.find(debut), src.find(fin)
    if i < 0 or j < 0:
        raise ValueError(f"marqueurs hm:{cle} introuvables dans {path}")
    return i + len(debut), j


def ecrire(previsions: dict, archive: dict, synthese: dict | None = None,
           path: str = INDEX) -> bool:
    """Réécrit les passages entre leurs marqueurs. True si le fichier a changé.

    Même garde que les JSON du front : sans changement, aucun octet n'est touché, donc le
    rafraîchissement hebdomadaire ne produit pas de diff pour rien."""
    with open(path, encoding="utf-8") as f:
        avant = f.read()
    apres = avant
    for cle, texte in rendu(previsions, archive, synthese).items():
        if texte is None:
            print(f"[web_export] index.md : pas de valeur pour hm:{cle}, passage laissé tel quel")
            continue
        i, j = _bornes(apres, cle, path)
        # Le bandeau est un bloc (retours à la ligne autour), la bascule est en ligne.
        corps = (f"\n{texte}\n  " if cle == "erreur"
                 else f"\n{texte}\n" if cle == "reponse" else texte)
        apres = apres[:i] + corps + apres[j:]
    if apres == avant:
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(apres)
    return True


def passages_du_fichier(path: str = INDEX) -> dict:
    """Les passages actuellement dans le fichier, pour comparaison (tests)."""
    with open(path, encoding="utf-8") as f:
        src = f.read()
    out = {}
    for cle in MARQUEURS:
        i, j = _bornes(src, cle, path)
        out[cle] = src[i:j].strip("\n").rstrip() if cle in _BLOCS else src[i:j]
    return out
