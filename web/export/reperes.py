"""Tout ce que l'export publie et que RIEN ne régénère : repères saisis à la main, mesures datées.

Ces constantes ne sont pas des oublis de l'automate : ce sont soit des relevés externes
(FNAIM, Observatoire Crédit Logement, BPCE), soit des résultats sur la MÉTHODE obtenus par
des backtests de plusieurs centaines de millésimes, trop coûteux pour être rejoués chaque
semaine et qui ne bougent pas d'une semaine à l'autre. Elles vieillissent donc, et c'est
pourquoi chacune porte sa date de relevé ou de mesure — des tests échouent quand l'une
d'elles devient périmée.

Les réunir dans un seul fichier rend visible, d'un coup d'œil, la part du site qui se
maintient à la main. Le reste de l'export est recalculé depuis les données à chaque
publication. (La veille des aides, `actualites.py`, relève du même régime et a sa propre
garde de fraîcheur.)
"""
from __future__ import annotations


# Cible BPCE 2026 : repli du bloc « Où va le marché » de la Synthèse quand le modèle n'est
# pas calibrable.
BPCE_TX_ANCIEN_2026 = 890_000


#: Repère externe : la seule prévision CHIFFRÉE de volumes publiée en France.
#:
#: Personne ne prévoit ce que ce site prévoit. Les Notaires disposent pourtant du meilleur
#: indicateur avancé qui soit — les avant-contrats, trois mois d'avance sur l'acte — mais
#: ne s'en servent que pour projeter les PRIX. La FNAIM, elle, publie une fourchette de
#: volumes pour l'année en cours. C'est notre unique point de contrôle externe.
#:
#: SAISI À LA MAIN, deux à quatre fois par an. D'où `releve_le` : sans date de relevé, ce
#: chiffre vieillirait en silence sur un graphique qui, lui, se rafraîchit toutes les
#: semaines — le mode de panne exact que le tableau des sources d'À propos évite déjà.
#: `tests/test_web_links.py` échoue si l'année visée est révolue.
BENCHMARK_FNAIM = {
    "source": "FNAIM",
    "url": "https://www.fnaim.fr/4361-marche-du-logement-la-reprise-sous-conditions.htm",
    "annee": 2026,
    "mois_cible": "2026-12-01",
    "lo": 900_000,
    "hi": 920_000,
    "releve_le": "2026-01-01",
    "note": ("Prévision annuelle publiée par la FNAIM. Son chiffre est un TOTAL d'année ; "
             "le nôtre un cumul sur douze mois glissants — les deux ne coïncident qu'en "
             "décembre. Les périmètres diffèrent aussi d'environ 0,6 % : à fin février "
             "2026, les Notaires comptaient 958 000 ventes là où notre série IGEDD en "
             "voit 952 000 en mars."),
}


#: Date de la mesure qui a écarté le modèle « permis → mises en chantier » (voir
#: `_transformation`). Stockée plutôt que recalculée : c'est un résultat sur la MÉTHODE,
#: pas une métrique vivante, et rejouer un backtest à origine glissante de 197 millésimes
#: à chaque export ajouterait des minutes au job hebdomadaire pour un chiffre qui ne bouge
#: pas d'une semaine à l'autre. Le protocole est dans CLAUDE.md.
NEUF_GATE = {
    "mesure_le": "2026-08-24",
    "millesimes": 197,
    "mape": 9.15,
    "naive_mape": 7.30,
    "skill": -0.252,
    "direction": 0.52,
}


#: Les hypothèses plausibles TESTÉES ET ÉCARTÉES, publiées sur la page de prévision.
#:
#: Un site qui ne montre que ce qui a marché laisse croire que tout ce qu'on essaie marche.
#: Ces idées avaient toutes l'air bonnes — plusieurs étaient inscrites au plan, une a été
#: affirmée pendant des semaines avant d'être vérifiée. (Pas de décompte dans la prose :
#: « trois » était déjà faux d'une entrée quand la cinquième est arrivée — le mode de panne
#: des « huit épisodes ».) Les publier avec leur chiffre est le pendant naturel de la page
#: « Prévisions passées » :
#: là on montre où le modèle se trompe, ici on montre ce qu'on a renoncé à lui ajouter.
#:
#: STOCKÉES ET DATÉES, jamais recalculées : ce sont des résultats sur la MÉTHODE, pas des
#: métriques vivantes. Chaque mesure a coûté un backtest à origine glissante de plusieurs
#: centaines de millésimes ; les rejouer à chaque export ajouterait des dizaines de minutes
#: au job hebdomadaire pour des chiffres qui ne bougent pas. Le protocole de chacune est
#: dans CLAUDE.md.
#:
#: Le seuil d'entrée du modèle, rappelé sur la page : au moins 5 % d'erreur évitée hors
#: échantillon sur au moins 3 des 4 plages d'horizon (1-3, 4-6, 7-12 et 13-18 mois).
REFUTATIONS = [
    {
        "titre": "Basculer vers la prévision naïve quand les taux sont calmes",
        "idee": ("Ce modèle n'a qu'un moteur, le coût du crédit, et sa performance en "
                 "dépend : mesuré sur 209 millésimes, il évite 47 % de l'erreur naïve "
                 "quand les taux bougent fort et en perd 7 % quand ils sont stables. "
                 "Puisqu'on sait reconnaître le régime, autant mélanger les deux "
                 "prévisions en donnant plus de poids à la naïve quand les taux dorment."),
        "mesure": "−1,8 % d'erreur ÉVITÉE au-delà de 6 mois — la zone où le modèle sert",
        "lecon": ("Le mélange progressif franchit bien 3 plages d'horizon sur 4, mais "
                  "uniquement sur 1 à 6 mois : la zone où le site dit déjà de s'en tenir "
                  "au dernier chiffre connu. Au-delà de six mois, là où l'on consulte "
                  "vraiment le modèle, il fait 1,8 % de MOINS bien — et sa dégradation "
                  "s'aggrave avec le temps : +7 % sur les millésimes 2013-16, −6 % sur "
                  "2017-20, −23 % sur 2021-25. Une relation qui s'inverse ainsi n'en est "
                  "pas une. La variante à seuil franc, elle, effondre en plus le sens du "
                  "marché annoncé, de 73 % à 46 % : en régime calme elle recopie la "
                  "naïve, donc n'annonce plus aucun sens. Ce que la mesure justifie n'est "
                  "pas de corriger la prévision, c'est de DIRE dans quel régime elle est "
                  "publiée — ce que fait désormais l'encart en tête de page."),
        "mesure_le": "2026-08-29",
    },
    {
        "titre": "Ajouter ce que les banques disent de la demande de crédit",
        "idee": ("Chaque trimestre, les banques déclarent à la Banque de France si la "
                 "demande de prêts au logement monte ou baisse. Cette enquête paraît AVANT "
                 "les chiffres de transactions : elle devrait donc les annoncer."),
        "mesure": "+3,7 % d'erreur évitée — 1 plage d'horizon sur 4",
        "lecon": ("Sur les seules années 2022-2024, elle faisait gagner 14 %. Mais ces "
                  "années-là sont le choc de taux, c'est-à-dire précisément l'épisode où la "
                  "demande de crédit s'effondre puis rebondit le plus fort. Sur huit "
                  "épisodes de marché, l'apport fond. Et surtout, le recalage de la "
                  "prévision sur le dernier chiffre connu captait déjà une bonne part du "
                  "même signal : les deux corrections se disputaient la même information."),
        "mesure_le": "2026-08-24",
    },
    {
        "titre": "Utiliser les anticipations de taux du marché",
        "idee": ("Au-delà de leur dernière valeur connue, les indicateurs sont maintenus à "
                 "plat dans la projection. Pour les taux, cette hypothèse a un substitut "
                 "coté : la courbe des taux dit quel niveau le marché attend dans six mois, "
                 "dans un an, dans deux ans. Remplacer « rien ne bouge » par « ce que le "
                 "marché anticipe » semblait un gain acquis."),
        "mesure": "0 plage d'horizon sur 4 — et légèrement PIRE que le report à plat",
        "lecon": ("Sur les mois réellement concernés, le report à plat se trompe de 7,18 % "
                  "et les anticipations de marché de 7,20 %. C'est un résultat connu de la "
                  "littérature sur les taux : les taux à terme prédisent mal les taux "
                  "futurs, et une marche aléatoire est très difficile à battre. Ce qui "
                  "ressemblait à la faiblesse la plus évidente du modèle est en réalité son "
                  "hypothèse la plus raisonnable."),
        "mesure_le": "2026-08-24",
    },
    {
        "titre": "Prévoir les chantiers à partir des permis de construire",
        "idee": ("Une autorisation d'urbanisme précède forcément l'ouverture du chantier. "
                 "Les permis devraient donc donner plusieurs mois d'avance sur les mises en "
                 "chantier — l'indicateur rêvé pour qui fournit le bâtiment."),
        "mesure": "0 plage d'horizon sur 4 — 25 % d'erreur en PLUS qu'une simple persistance",
        "lecon": ("Le lien entre les deux séries est maximal à décalage NUL et faiblit "
                  "ensuite, mois après mois : les permis ne devancent rien. Les deux "
                  "séries sont corrigées des variations saisonnières et remontent par la "
                  "même voie administrative, si bien que le délai de déclaration pèse plus "
                  "que le délai de construction. Le décalage réel existe projet par projet ; "
                  "la moyenne nationale l'efface."),
        "page": {"href": "/neuf", "libelle": "Voir la mesure sur Marché du neuf"},
        "mesure_le": "2026-08-24",
    },
    {
        # Protocole, seuils et rapport : docs/plan-territoires.md §3 et
        # docs/mesure-territoires-2026-09-20.md ; script : mesure_territoires.py.
        "titre": "Classer les départements entre « France héritée » et « France désirée »",
        "idee": ("Le transfert de patrimoine des quinze prochaines années ne ferait ni "
                 "monter ni baisser l'immobilier : il creuserait l'écart entre les "
                 "départements âgés et propriétaires, où les logements vont être hérités "
                 "puis vendus, et ceux qui attirent des habitants, où l'argent de ces "
                 "ventes irait s'investir. Deux axes observés — la part des résidences "
                 "principales détenues par un ménage de 65 ans ou plus, et l'attractivité "
                 "migratoire — devraient donc séparer les marchés qui montent de ceux qui "
                 "baissent."),
        "mesure": ("Le lien change de SIGNE d'un cycle à l'autre : +0,57 sur 2014-2019, "
                   "−0,06 sur 2019-2025"),
        "lecon": ("Sur 2014-2019, les départements âgés et propriétaires ont bien vu leurs "
                  "prix progresser moins que les autres — mais entièrement parce qu'ils "
                  "étaient déjà les moins chers, à une époque où les métropoles chères "
                  "décrochaient du reste du pays : à niveau de prix donné, l'axe "
                  "n'expliquait plus rien (corrélation partielle +0,03). Sur 2019-2025, "
                  "c'est l'inverse qui s'est produit : ces mêmes départements ont vu leurs "
                  "prix (+0,46) et leurs ventes (+0,44) progresser PLUS que les jeunes "
                  "métropoles — Covid, littoral, puis une correction qui a d'abord frappé "
                  "les grandes villes. Une relation qui change de signe avec le cycle dit "
                  "dans quel cycle on est, pas où en sera le marché dans quinze ans. Au "
                  "passage, le solde migratoire net s'est révélé mesurer la pénurie de "
                  "logements et non l'attrait : il classe Paris dernier des cent "
                  "départements. Les indicateurs eux-mêmes restent publiés, en "
                  "description, sur chaque page départementale — sans carte des gagnants "
                  "et des perdants."),
        "mesure_le": "2026-09-20",
    },
]


#: Repère analyste pour le TAUX DE CRÉDIT. Plus solide que le repère FNAIM des volumes :
#: l'Observatoire Crédit Logement/CSA est le PRODUCTEUR de la série que ce site modélise,
#: donc sa prévision porte exactement sur la même grandeur — aucun écart de périmètre à
#: expliquer, contrairement aux 0,6 % qui séparent les volumes Notaires de la série IGEDD.
#:
#: Le calendrier, en revanche, ne se recouvre PAS : notre projection sans hypothèse s'arrête
#: à l'horizon du délai de répercussion (~7 mois), la leur porte sur fin 2027. Les deux se
#: complètent, elles ne se comparent pas au même mois — et la page doit le dire.
#:
#: Saisi à la main, donc daté et testé comme BENCHMARK_FNAIM.
BENCHMARK_TAUX = {
    "source": "Observatoire Crédit Logement / CSA",
    "url": "https://lobservatoire.creditlogement.fr/",
    "horizon": "fin 2027",
    # Date exploitable, pour que le graphique puisse POSER le repère au bon endroit plutôt
    # que de le laisser en note. Décembre 2027 : « fin 2027 » au sens de leur publication.
    "date": "2027-12-01",
    "valeur": 3.95,
    "releve_le": "2026-08-24",
    "note": ("L'Observatoire produit la série même que ce site modélise : sa prévision "
             "porte donc exactement sur la même grandeur. Elle vise fin 2027, au-delà de "
             "l'horizon que nos seuls taux de marché publiés permettent de déterminer — "
             "les deux se complètent plutôt qu'elles ne se comparent."),
}
