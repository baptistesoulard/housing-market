# Le modèle de prévision et l'archive des prévisions

> **Journal daté — ne pas réécrire.** Ce fichier est l'ancien contenu de `CLAUDE.md`,
> déplacé tel quel le 2026-09-23. Chaque paragraphe reflète l'état du dépôt À SA DATE :
> les chiffres, les noms de fichiers (`app.py`, `web_export.py` d'un seul tenant…) et les
> décomptes ont pu changer depuis. L'état courant et les règles en vigueur sont dans
> `CLAUDE.md` ; ce journal garde le POURQUOI et les mesures. On y ajoute des entrées
> datées, on ne corrige pas les anciennes.

## L'archive des prévisions — ce qui ne doit jamais bouger

Choix produit du 2026-08-20 : le projet vise un **média d'analyse à audience large** plutôt
qu'un outil de travail à maille fine. La crédibilité devient donc la fonctionnalité
principale, et `forecast_archive.py` en est le pivot — une prévision publiée sans historique
n'est qu'une opinion.

**Deux natures de lignes, jamais agrégées ensemble.** La colonne `kind` sépare `archive`
(prévision réellement publiée ce jour-là, enregistrée par le job hebdomadaire avant que la
suite ne soit connue) et `retro` (recalculée après coup en tronquant les données au
millésime visé). La première prouve une promesse tenue, la seconde seulement que la méthode
tenait. `web_export.build_archive` ventile TOUT par `kind`, compteurs compris ; produire un
« notre erreur moyenne » unique serait une tromperie.

**Ce qui est publié ne se réécrit pas.** `main()` rejoue la rétro-simulation en entier à
chaque `--backfill` (elle est déterministe) mais ne touche jamais aux lignes `archive`.
Ne pas inverser cette asymétrie.

**Le réalisé n'est PAS stocké.** Il est rejoint à la lecture (`evaluate`), depuis la série
courante. La source révise ses chiffres : une valeur réalisée figée à l'enregistrement
ferait comparer une prévision à un réalisé périmé. La référence naïve, elle, EST stockée —
c'est le dernier cumul 12 mois observé au moment de la prévision, information qui n'existe
plus une fois la série révisée.

**La référence naïve n'est pas décorative.** Sur les données réelles, le modèle est *moins
bon* qu'elle aux horizons courts et évite une bonne part de son erreur au-delà. Publier un
MAPE unique masquerait le premier fait. La page montre la zone où le modèle perd — c'est le
propos, pas un aveu.

**La fenêtre du backtest est 2009, pas 2022, et ce n'est pas un détail de mesure.**
`BACKFILL_START = "2009-01-01"`. La fenêtre courte d'origine (2022-07) ne couvre qu'UN
épisode — le choc de taux de 2022-2024 — c'est-à-dire précisément celui qu'un modèle piloté
par les taux réussit le mieux : il y évite 49 % de l'erreur naïve et annonce le bon sens
neuf fois sur dix. Mesuré sur 2009-2026 (210 millésimes, **sept** épisodes), l'écart évité
tombe à 18 % et le taux de bon sens à 74 % — et surtout la performance devient très
DISPERSÉE d'un épisode à l'autre, de **−4 % à +56 %** d'erreur évitée : le modèle excelle
quand le coût du crédit pilote le marché et ne sert à rien sinon. Choisir la fenêtre
courte, c'est choisir son résultat.

⚠️ **Le décompte nominatif a dérivé et a été recalé le 2026-08-29.** Cette phrase disait
« perd dans trois épisodes sur huit : la crise financière de 2008-2009, le creux long de
2012-2015 et le Covid » — juste à la rédaction, jamais revérifié. Sur les chiffres publiés
aujourd'hui : `_EPISODES` en compte **sept**, pas huit ; **2009 GAGNE** (+15,9 %) alors que
la phrase le donnait perdant ; **2012-15 est nul** (+0,3 %), pas perdant ; le Covid perd
bien (−3,6 %) ; et **2025-26 perd aussi** (−4,0 %), épisode qui n'existait pas à la
rédaction. Le fond tenait, les exemples nommés étaient faux. **Ne jamais nommer un épisode
gagnant ou perdant sans relire le tableau** : ces skills bougent à chaque rafraîchissement,
et c'est exactement pourquoi la page les AFFICHE au lieu de les raconter. Avant 2009 la recherche de décalages manque
d'historique et retombe sur ses valeurs de repli : ces millésimes ne prouveraient rien.

Corollaire mesuré, à connaître avant de toucher à l'un des deux : **allonger la fenêtre sans
le recalage (ci-dessous) fait passer le KPI de l'accueil de « 4,1 % contre 7,2 % » à « 6,4 %
contre 5,9 % » — donc à un modèle qui PERD à six mois.** Avec le recalage, 5,5 % contre
5,9 %. `tests/test_web_links.py` verrouille ce chiffre contre `archive.json` : les deux
changements doivent arriver ensemble, sinon le site publie pendant un temps un chiffre qui
le dessert.

**Le recalage sur le dernier point observé (`forecast.anchor_of` + `FADE_MONTHS`).** Le
modèle est une régression de NIVEAU : il reconstruit la série depuis la macro sans jamais
regarder où elle se trouve réellement. Son erreur au premier mois projeté valait donc son
résidu d'estimation (~4,2 %) là où recopier le dernier chiffre connu n'en coûte que 1,2 % —
et l'erreur restait PLATE de l'horizon 1 à l'horizon 10, signature d'un biais de niveau et
non d'une erreur d'horizon. `forecast_path` ajoute désormais l'écart observé−ajusté du
dernier mois, avec un poids qui s'éteint linéairement sur `FADE_MONTHS`.

`FADE_MONTHS = 9` est le milieu d'un PLATEAU, pas un réglage ajusté : mesuré sur 48
millésimes puis confirmé sur 210, toutes les valeurs entre 6 et 12 mois donnent la même
erreur à 0,1 point près. C'est ce qui met ce paramètre à l'abri du surapprentissage, et
c'est la raison de le documenter ici — un successeur tenté de « l'optimiser » ne gagnerait
rien et perdrait cette garantie. Gain mesuré : −11 % d'erreur globale, −42 % sur les
horizons 1 à 3, seuil de bascule contre la naïve avancé d'un mois. C'est le seul résultat
de l'audit qui ressort *renforcé* de l'allongement de la fenêtre : il ne corrige pas une
relation économique, mais un défaut de construction, donc il ne dépend pas du régime.

**La bande est calibrée sur l'archive, plus postulée.** Elle valait ±1,28·RMSE, une largeur
CONSTANTE à tous les horizons : couverture réelle 94 % aux horizons 1-10 et 57 % à dix-huit
mois, pour une promesse de 80 % — trop large là où elle rassure, trop étroite là où elle
engage. `band_table()` prend les quantiles 10/90 de l'erreur SIGNÉE par horizon et les écrit
dans `data/forecast_band.csv` (versionné, comme l'archive). L'erreur est signée exprès : le
modèle surestime de façon croissante avec l'horizon, et une bande symétrique autour d'une
prévision biaisée rate d'un côté plus que de l'autre.

**`--calibrate` fait DEUX passes, et l'ordre n'est pas négociable.** La bande se calibre sur
les erreurs de POINT, qui ne dépendent pas d'elle : la première passe les produit avec la
bande constante, la seconde rejoue exactement les mêmes prévisions en n'ayant changé que
`lo`/`hi`. Calibrer sur des erreurs déjà corrigées par une bande précédente ferait dériver
l'étalon à chaque exécution. Un horizon vu moins de 20 fois n'est pas calibré : `forecast_path`
retombe sur la bande constante pour celui-là plutôt que d'extrapoler un quantile sur cinq points.

**`_macro_indexed` n'extrapole plus.** Elle interpolait le chômage trimestriel avec
`limit_direction="both"`, ce qui PROLONGEAIT la série jusqu'à trois mois au-delà de sa
dernière observation. La valeur n'étant alors plus NaN, `forecast_path` ne déclenchait pas
son report explicite et marquait le point `assured=True` : l'hypothèse était faite, elle
n'était simplement plus signalée. `limit_area="inside"` la laisse manquante, donc visible.
Conséquence attendue et voulue : le repère « sans hypothèse » recule, et il dira la vérité —
avec `kc=0`, cette fenêtre est de toute façon structurellement nulle (0 des 864 points
rétro-simulés était assuré).

**La fenêtre d'entraînement LONGUE est la bonne, et c'est mesuré (2026-08-29).**
Objection légitime et récurrente : `fit_tx_model` estime `beta` sur TOUT l'échantillon
(270 mois, novembre 2003 → avril 2026), donc une seule relation linéaire traverse la crise
de 2008, le creux de la dette, l'expansion 2016-19, le Covid et le choc de taux — des
régimes dont les moteurs n'ont rien à voir. Faut-il glisser la fenêtre ?

Testé au protocole exact de la production (troncature macro ET transactions, décalages
recherchés à chaque millésime, ancrage), 54 millésimes trimestriels de 2012 à 2025,
967 points évalués. Erreur évitée contre la prévision naïve :

| fenêtre | 1-3 mois | 4-6 | 7-12 | 13-18 | sens juste |
|---|---|---|---|---|---|
| **extensible (production)** | −40,1 % | **+4,5 %** | **+26,3 %** | **+32,9 %** | 77,3 % |
| 15 ans | −40,2 % | −3,7 % | +15,8 % | +28,4 % | 77,0 % |
| 12 ans | −30,2 % | −0,0 % | +11,2 % | +22,1 % | 76,4 % |
| 10 ans | −15,4 % | −3,1 % | +7,1 % | +20,1 % | 75,8 % |
| 8 ans | **−1,3 %** | **+11,3 %** | +16,7 % | +21,5 % | **80,0 %** |

Trois lectures, et la troisième interdit de « régler » ce paramètre au jugé :

1. **La fenêtre longue gagne là où le modèle sert.** Sur 7-18 mois — la seule zone où la
   page dit de le lire — elle évite **+29,6 %** d'erreur en moyenne contre +19,1 % au mieux
   pour une glissante. L'histoire longue est ce qui permet d'estimer une élasticité aux
   taux qui tienne à travers les cycles ; huit ans n'en voient qu'un.
2. **La fenêtre courte gagne là où le modèle ne sert pas.** Ses avantages (1-3 et 4-6 mois)
   tombent entièrement dans la zone où le site recommande déjà de recopier le dernier
   chiffre connu. Un gain dans une zone qu'on n'utilise pas n'est pas un gain.
3. **Le milieu est le pire des deux extrêmes** — 10, 12 et 15 ans font moins bien que
   l'extensible ET que 8 ans presque partout. Trop court pour la relation structurelle,
   trop long pour coller au régime courant. Non-monotonicité franche.

**Et l'adaptation au régime est déjà là, au bon endroit.** `anchor_of` + `FADE_MONTHS`
recale le modèle sur son dernier point observé : c'est exactement ce qu'une fenêtre
glissante apporterait, mais appliqué à l'ORDONNÉE À L'ORIGINE seule, en gardant la pente
estimée sur l'histoire longue. Gain déjà mesuré : −42 % d'erreur sur les horizons 1-3. La
bonne réponse à l'hétérogénéité des cycles n'est donc pas de raccourcir la fenêtre, c'est
ce découpage-là — et pour aller plus loin, **des prédicteurs couvrant les canaux qui
dominent dans les épisodes perdants** (confiance, offre), pas une réestimation sur moins de
données. Ne pas re-tester la fenêtre glissante sans raison nouvelle.

**Un prédicteur n'entre dans l'étage 2 que s'il gagne HORS ÉCHANTILLON, sur la fenêtre
longue.** Critère : ≥ 5 % d'erreur évitée sur ≥ 3 des 4 blocs d'horizon (1-3, 4-6, 7-12,
13-18), décalage retenu stable sur les millésimes. Jamais sur le R² d'ajustement — c'est
lui qui a fait entrer, dans des tentatives antérieures, la production de crédits et
l'activité rénovation, qui *dégradent* toutes deux la prévision hors échantillon.

**Exemple travaillé, et refus : la demande de crédits BLS (2026-08-24).** Elle était la
candidate évidente — publiée avant les transactions, qualifiée d'« indicateur avancé » par
le site lui-même sur la page Environnement, décalage stable (12 mois, 95 % des
millésimes). Mesurée sur 48 millésimes elle faisait gagner 14 % ; mesurée sur les 210,
avec l'ancrage en place, **+3,7 % et un seul bloc d'horizon franchi sur quatre**. Deux
causes qui se cumulent :

1. la fenêtre courte est le choc de taux, c'est-à-dire l'épisode où la demande de crédit
   s'effondre puis rebondit spectaculairement — son information marginale y est maximale
   et nulle part ailleurs ;
2. **le recalage avait déjà pris le gain.** L'ancrage corrige l'erreur de NIVEAU du modèle,
   or c'est exactement sous cette forme qu'une variable de demande manquante se
   manifestait. Les deux correctifs se disputaient la même variance.

À retenir pour tout candidat suivant : mesurer *après* le lot 1, jamais avant, sinon on
crédite le prédicteur d'un gain que l'ancrage fournit gratuitement. Le peu de gain restant
se concentrait d'ailleurs sur 1-3 mois, la zone où le modèle est de toute façon battu par
une marche aléatoire. Le script de la porte est
`scratchpad/gate_bls.py` dans l'historique de la session — sa recherche de décalage est
CONDITIONNELLE (les trois autres figés), donc conservatrice.

**Le modèle est resté à TROIS prédicteurs, donc `forecast.py` garde ses trois colonnes en
dur.** La généralisation à N prédicteurs (`_design`, `search_tx_lags`, `forecast_path`,
`scenario`, plus `LAG_GRIDS` et le port JS `computeScenario`) a été préparée puis NON
faite : sans quatrième prédicteur qui passe la porte, c'est un refactor large — Python, JS
et tests — pour aucun gain mesurable. À faire le jour où un candidat passe, pas avant.

**L'étage 1 porte un DÉLAI DE RÉPERCUSSION, et il est estimé, pas supposé.** Le crédit
immobilier français est à taux fixe et les banques lissent leurs barèmes : leur réaction aux
taux de marché n'est pas instantanée. Le modèle était contemporain ; il décale désormais
l'OAT et l'Euribor de `search_rate_lag()` mois — **7 sur les données actuelles**. Gains
mesurés, tous dans le même sens :

| | contemporain | décalé |
|---|---|---|
| R² | 0,838 | **0,932** |
| RMSE | 0,474 | **0,307** |
| RMSE **hors échantillon** (entraîné ≤ 2019, jugé sur le choc de 2022) | 0,744 | **0,432** |

Le délai est **cherché à chaque ajustement mais remarquablement stable** : refait à chaque
millésime annuel depuis 2012, il reste entre 5 et 7 mois et ne s'effondre jamais à zéro. Le
profil du R² monte franchement jusqu'à 6-7 mois puis redescend — c'est la forme d'une vraie
relation d'avance. **Ne pas confondre avec le cas des permis de construire**, où la courbe
décroît dès le premier mois : là il n'y a aucune avance, ici il y en a une. Chercher les deux
décalages séparément donne 0,9323 au lieu de 0,9320 — un paramètre de plus pour rien.

**Le graphique de l'étage 1 porte TROIS courbes, et deux d'entre elles sortent du même
modèle — ne pas les recoller par erreur.** Première version livrée, illisible : la
reconstitution s'arrêtait au dernier mois observé (3,75 %) et la projection repartait 0,51 pt
plus bas (3,24 %), parce que la première est la sortie BRUTE et la seconde la sortie RECALÉE.
Deux fragments du même calcul sur des bases différentes, séparés par un saut qu'aucune
légende n'expliquait.

`rate_path` renvoie donc les deux — `modelled` (brute) et `taux` (publiée). La courbe brute
est tracée d'un seul tenant, ajustement puis mois à venir, et l'écart qui la sépare de la
courbe publiée **est** le biais de niveau : 0,59 pt, soit la part du mouvement de marché que
les banques ne répercutent pas. Visible et expliqué, au lieu d'être subi. Un encart « comment
lire ces trois courbes » nomme chacune ; le retirer rendrait la section incompréhensible, ce
qu'elle a été.

Deux détails qui cassent si on prolonge la courbe sans y penser : l'étiquette de fin du réel
doit viser `R.series` et non la dernière ligne (les mois projetés ont un `observed` nul, elle
afficherait « NaN % »), et la vignette de survol doit se caler sur `modelled`, seule série
définie partout.

**Conséquence produit, et c'est la vraie raison de l'avoir fait :** `forecast.rate_path()`
publie les mois de taux de crédit que les taux de marché DÉJÀ parus déterminent — sept mois
d'avance sans la moindre hypothèse. À rapprocher de la projection des transactions, dont la
fenêtre « sans hypothèse » vaut **zéro** mois sur dix-huit. Ancrée en écart sur le dernier
taux observé, comme `scenario`, parce que le modèle sur-prédit le niveau.

**Le récit de l'écart 2023-2025 a changé.** Les deux surfaces l'attribuaient entièrement à
« des banques qui retiennent leurs barèmes ». Avec le délai, l'écart résiduel tombe de 0,77 à
0,59 point : le comportement des banques en explique le reste, pas le tout. `app.py` et
`previsions.md` ont été corrigés ENSEMBLE — deux surfaces qui racontent la même chose
différemment est exactement ce que l'axe compute existe pour empêcher.

**Ce délai n'améliore PAS la prévision de transactions**, et la page le dit : l'étage 2
utilise le taux de crédit *observé*, jamais le reconstitué. C'est un gain d'explication et de
scénario, pas de MAPE.

**La page de prévision porte la frise de période, et son filtrage a DEUX régimes.** Elle ne
rogne que l'affichage : rien n'est recalculé, le modèle reste ajusté sur toute la profondeur
disponible — un modèle réestimé au gré d'un curseur ne serait plus celui que l'archive des
prévisions passées a jugé. La distinction à ne pas perdre : `histo()` applique la frise
entière aux séries observées, `depuis()` n'applique QUE la borne basse aux séries PROJETÉES.
Ces dernières sont postérieures au dernier mois publié, donc au maximum de la frise : leur
appliquer la borne haute les ferait disparaître dès qu'on touche au curseur, c'est-à-dire
masquer la prévision sur une page de prévision. Le repère analyste, daté de fin 2027, relève
du même régime.

Un piège propre au graphique d'alignement : le prédicteur y est décalé avant d'être tracé, et
le rognage doit venir APRÈS ce décalage — filtrer avant ferait glisser la fenêtre affichée du
nombre de mois du décalage, et les deux courbes ne couvriraient plus la même période.

**`BENCHMARK_TAUX` est le repère analyste du taux**, sur le modèle de `BENCHMARK_FNAIM` :
l'Observatoire Crédit Logement/CSA anticipe ~3,95 % fin 2027. Il est plus solide que le
repère des volumes — l'Observatoire PRODUIT la série que le site modélise, donc aucun écart
de périmètre à expliquer — et plus fragile sur un point : son horizon ne recouvre pas celui
que nos taux publiés déterminent (fin 2027 contre ~7 mois). La page dit que les deux se
complètent au lieu de se comparer, et le graphique le MONTRE : le repère est posé à sa date
comme un point isolé, jamais relié à notre trajectoire. L'espace vide entre notre dernier
point (janvier 2027) et le sien (fin 2027) est l'information — tracer un trait entre les deux
suggérerait une trajectoire que ni eux ni nous ne publions. Saisi à la main, donc daté et
testé.

**L'Euribor a été RETIRÉ de l'étage 1 le 2026-08-25, sur mesure.** Il n'apportait rien en
ajustement (R² 0,9320 avec, 0,9282 sans) et **dégradait de 19 % hors échantillon** — RMSE
0,432 contre 0,348 sur un test entraîné jusqu'en 2019 et jugé sur le choc de 2022, avec un
biais deux fois pire (−0,309 contre −0,160). Signature d'un régresseur colinéaire qui ajuste
du bruit : il aide sur le passé, il nuit sur l'inconnu. L'argument économique concordait — le
crédit immobilier français est à taux FIXE, adossé à du financement long, donc c'est l'OAT
10 ans qui le tarife ; l'Euribor décrit un coût court, de second ordre pour un prêt de vingt
ans. Il était là par symétrie, pas par mécanisme.

Trois bénéfices, au-delà de l'erreur : **le coefficient devient lisible tel quel** (0,742 pt
de taux de crédit par point d'OAT — toute la mise en garde « les deux ne se lisent pas
séparément » disparaît), la colinéarité (r 0,83, VIF 3,24) disparaît avec lui, et le curseur
fusionné cesse d'être un contournement pour devenir la forme naturelle du modèle : un taux,
un levier. Le décalage retenu ne bouge pas — 7 mois avec ou sans, c'est une propriété de la
transmission et non de la spécification.

`RATE_DRIVER` porte ce choix dans `forecast.py`. `rate_beta` n'a plus que DEUX éléments, ce
qui touche `forecast.scenario`, le port JS `computeScenario` et `tests/test_web_js_parity.py`
— les trois ont été mis à jour ensemble, le cas de test « +1 pt d'Euribor seul » étant
remplacé par « −1 pt d'OAT » puisqu'il testait un levier qui n'existe plus. **L'Euribor reste
une série publiée** du site (page Environnement, tableau des sources) : seul son rôle de
régresseur tombe.

**Les deux taux de l'étage 1 se pilotent ENSEMBLE, et c'est un correctif.** L'OAT 10 ans et
l'Euribor 3 mois sont corrélés à +0,83 (VIF 3,24) : l'OLS ne peut pas les séparer et
attribue presque tout au premier — coefficients publiés 0,707 et **0,013**. Exposés comme
deux curseurs indépendants sur « Prévision & Scénarios », celui de l'Euribor était donc
INERTE : balayé sur toute sa course, cinq points de taux, il déplaçait la prévision de
0,3 %, contre 11 %, 24 % et 18 % pour les trois autres. Un levier affiché qui ne lève rien
est pire qu'un levier absent — le visiteur en conclut que le taux interbancaire n'agit pas
sur le marché immobilier, ce qui est faux.

La page expose maintenant un seul curseur « taux de marché (écart, en points) » qui déplace
les deux du même écart, et affiche la SOMME des coefficients (0,72 pt de taux de crédit par
point de marché) — la seule des deux quantités qui ait un sens. `fit_rate_model`,
`forecast.scenario` et le port JS `computeScenario` sont **inchangés** : ils reçoivent
toujours les deux valeurs séparément, donc `tests/test_web_js_parity.py` tient sans
retouche. Deux tests de `test_web_links.py` verrouillent l'affaire — la somme des
coefficients doit rester ≥ 0,25, et la page n'a pas le droit de réexposer une étiquette de
curseur portant l'OAT ou l'Euribor seul. Retirer purement et simplement l'Euribor de
l'étage 1 reste une option propre (le R² passe de 0,8378 à 0,8377) mais toucherait les
textes statiques de plusieurs pages et le tableau des sources ; non fait pour cette raison.

**Passe de vocabulaire sur « Prévision & Scénarios » (2026-08-29).** La page portait le
niveau de jargon d'une note interne pour une audience de dirigeants et de particuliers.
Deux trouvailles dépassent la formulation :

* **« Nowcast » était FAUX, pas seulement obscur.** Un nowcast estime le présent avant sa
  publication officielle. La section 2 montre un modèle entraîné jusqu'en 2021 rejoué sur
  les années suivantes : elle ne comble aucun trou de publication, et ses valeurs ajustées
  s'arrêtent même AVANT le dernier chiffre connu (avril contre juin 2026, le chômage
  trimestriel les bornant). Le mot venait de l'intention d'origine du module — encore
  inscrite dans la docstring de `forecast.py`, corrigée aussi.
* **Deux titres d'`app.py` annonçaient des choses supprimées** : l'étage 1 nommait encore
  l'« Euribor 3 mois » (retiré du modèle le 2026-08-25) et le panneau de scénarios encore
  « → chiffre d'affaires » (dataset `revenue` supprimé le 2026-08-24). Un titre de section
  survit aux suppressions parce que personne ne le relit en changeant le calcul.

**La numérotation est redevenue linéaire : 1, 2, 3, 4** (les sections 🔬 et 🧪 restent
hors numérotation, ce sont un outil d'audit et une annexe). « 2 bis » désignait la
PROJECTION — la sortie du modèle, donc la section la plus importante de la page — sous le
numéro le plus apologétique qui soit. Piège rencontré en renumérotant : `app.py` a une
section de plus que le site (« Permis de construire → vos ventes »), qui portait le 4 et
s'est retrouvée en doublon avec le panneau de scénarios ; elle est passée en 5. **Vérifier
les numéros sur les DEUX surfaces après tout déplacement.**

Chaque titre dit désormais ce que le lecteur y trouve plutôt que la méthode employée, et
les libellés de cartes ont perdu le jargon non expliqué : « MAPE » → « erreur moyenne sur
des données non vues », « prédicteur » → « indicateur », « taux implicite » → « taux qui en
résulterait », « impact relatif » → « écart vs aujourd'hui ». Les deux curseurs de scénario
disent leur point de référence au lieu de nommer la statistique (« 0 = inchangé »,
« 0 = moyenne historique ») — ils gardent leur unité sans exiger de savoir ce qu'est un
écart-type.

**La section 2 ne contient PAS le futur, et c'est sa définition — mais le graphique ne le
montrait pas (2026-08-29).** Un backtest confronte ce que le modèle DISAIT à ce qui s'est
réellement passé : au-delà du dernier mois observé il n'y a plus rien à confronter, donc la
comparaison s'arrête là par construction. Le futur est le sujet de la section 3. Les fondre
détruirait le sens du test — une projection n'a pas de réalisé en face.

Deux manques faisaient chercher le futur là où il n'a rien à faire, et ils étaient dans le
graphique :

* **Aucune légende.** `multiLine` ne posait pas `legend: true` et aucun de ses 20 appelants
  n'en fournissait : deux courbes, rien qui les nomme, hors survol. `legendStatic()`
  (nouveau) rend la même chose que `legend()` sans interrupteur — sur un graphique dont
  rien ne se masque, un `<button>` promettrait une action inexistante. Le pointillé est
  reproduit dans la pastille : deux séries distinguées par la seule couleur ne se
  distinguent pas pour tout le monde. ⚠️ Ce correctif-ci n'a traité QUE ce graphique, en
  posant la légende à l'appel ; les douze autres graphiques muets du site sont restés
  muets jusqu'au 2026-09-03 — voir « Une légende n'est pas une option » plus bas.
* **Aucun repère à la frontière.** La courbe du modèle démarrait en plein graphique sans
  que rien ne dise pourquoi. `multiLine` accepte désormais `splitAt: {date, label}`, qui
  trace la limite entraînement / test. C'est ce trait qui rend le graphique lisible : tout
  ce qui est à sa DROITE a été produit sans avoir vu la suite.

Les libellés de séries disent maintenant le rôle et non la source — « Ce que le modèle
annonçait, sans avoir vu la suite » plutôt que « Prévision hors échantillon ». La même
légende a été ajoutée au graphique de la section 3, qui portait quatre objets (observé,
projection, bande, repère FNAIM) sans en nommer aucun.

**Deux exercices différents étaient présentés comme un seul (2026-08-29).** Les cartes de
tête de la section 2 annonçaient « 72 % de bon sens **sur 204 mois déjà échus** », posées
juste au-dessus d'un graphique qui couvre **2022-2026**. Un lecteur cherche forcément les
204 mois dans la courbe, et ne les trouve pas — parce qu'ils n'y sont pas :

| | source | étendue |
|---|---|---|
| les trois cartes | l'**archive** : le modèle réajusté chaque mois depuis 2009, confronté à ce qui a suivi | ~204 prévisions à 6 mois échues |
| le graphique | **un seul** ajustement, arrêté au découpage, prolongé ensuite | 52 mois (2022-2026) |

Les deux sont légitimes et complémentaires — l'un juge, l'autre illustre — mais rien ne les
distinguait. Les sous-titres des cartes nomment désormais leur source (« rejouées chaque
mois depuis 2009 — pas sur le graphique ci-dessous ») et le graphique porte un titre qui
annonce ce qu'il est. **Règle générale : quand deux mesures voisines n'ont pas la même
étendue, chacune doit dire la sienne — sinon la plus grande est lue comme une propriété de
la plus petite.**

**La carte des décalages ne rappelait pas la formule.** « 10 / 2 / 0 mois » ne veut rien
dire seul. Elle porte maintenant la phrase construite depuis `T.lags` : « ventes(mois M)
expliquées par le taux de M−10, les intentions d'achat de M−2 et le chômage de M (sans
décalage) ». Le cas `kc = 0` est écrit en toutes lettres — c'est lui qui fait qu'aucun mois
projeté n'est jamais « sans hypothèse », et un « 0 » nu ne le laisse pas deviner.

**« Huit épisodes » subsistait DEUX FOIS sur la page**, alors que le décompte avait été
corrigé dans `CLAUDE.md` et dans la docstring de `_by_episode` — l'archive en publie sept.
Le nombre a été retiré au profit de « depuis 2009 », qui est une constante
(`BACKFILL_START`) et ne dérivera pas. **Corriger un chiffre dans la doc ne le corrige pas
sur le site : `grep` la valeur dans `web/observable/src/` aussi.**

**La formule de l'étage 2 et celle de la PROJECTION sont publiées (2026-08-29).** L'étage 1
affichait la sienne en clair (`.hm-formula`) depuis toujours ; l'étage 2 ne montrait que ses
décalages — donc QUELLES variables entrent, jamais ce que le modèle en fait. Deux blocs
comblent le trou, et le second était le plus manquant :

* **L'équation** : `2 680 053 − 91 637 × taux(t−10) + 13 157 × intentions(t−2) −
  49 987 × chômage(t)`. Les coefficients se lisent tels quels, en ventes annuelles — un
  point de taux de crédit coûte ~92 000 ventes, un point de chômage ~50 000. C'est aussi ce
  qui rend le modèle vérifiable par un tiers.
* **Le RECALAGE**, qui n'était écrit nulle part : la projection n'est pas la sortie brute de
  l'équation, on lui ajoute l'écart observé−ajusté du dernier mois (`anchor_of`) avec un
  poids qui vaut 1 au premier mois projeté et s'annule au 10ᵉ (`FADE_MONTHS = 9`). Un
  lecteur qui reprenait l'équation seule trouvait un écart de 23 359 ventes sans pouvoir
  comprendre d'où il venait. `engine.projection()` expose donc `anchor` et `fade_months`.

**Les trois entrées ne s'épuisent PAS ensemble, et l'écart est large (2026-08-29).**
`informative_months` (10) est piloté par le prédicteur qui tient le plus longtemps — le
taux, avec ses dix mois d'avance. Mesuré entrée par entrée :

| entrée | décalage | dernier mois publié | observée jusqu'au | puis figée à |
|---|---|---|---|---|
| taux de crédit | 10 mois | juin 2026 | **10ᵉ** mois projeté | 3,16 % |
| intentions d'achat | 2 mois | juillet 2026 | **3ᵉ** mois projeté | −82 |
| taux de chômage | **aucun** | avril 2026 | **aucun — figé dès le 1ᵉʳ** | 8,3 % |

Le chômage entre sans décalage ET accuse deux mois de retard sur les ventes : il est donc
reporté à plat depuis le tout premier mois projeté. Les intentions tiennent trois mois.
**À partir du quatrième mois, le modèle tourne sur une entrée vivante sur trois** — ce que
« 10 mois pilotés par des indicateurs déjà publiés » laissait croire bien meilleur qu'il
n'est. `engine._predictor_horizons` publie le détail, la page le rend en tableau.

C'est aussi l'explication complète de `assured_months = 0` : le repère « sans hypothèse »
ne pouvait jamais apparaître puisque le chômage manque dès le premier mois.

**Le report à plat doit être dit LÀ OÙ LE MODÈLE EST PRÉSENTÉ, pas seulement là où il
s'applique.** Il ne figurait que dans la section 3 (la projection). Un lecteur qui
découvrait le modèle au chapeau puis à son équation en ressortait avec trois indicateurs
vivants en tête, et ne croisait la convention que bien plus bas — s'il descendait jusque-là.
Elle est donc énoncée trois fois, à trois niveaux de profondeur : le **chapeau statique**
(sans chiffre, donc pérenne : « chacun n'est publié que jusqu'à un certain mois, et au-delà
la projection le maintient à sa dernière valeur connue »), la **légende de l'équation de
l'étage 2** (« cette équation décrit le passé, où les trois entrées sont observées »), puis
le **tableau chiffré** de la section 3. Règle générale : une hypothèse de calcul se déclare
au premier endroit où le lecteur se forme une idée du modèle, pas au dernier où elle joue.

⚠️ **Le piège de l'accent grave ne concerne pas que `observablehq.config.js`.** Un
commentaire HTML placé DANS un littéral gabarit est du texte de chaîne comme le reste : y
citer un identifiant entre accents graves **referme la chaîne**, la cellule devient
invalide, et le build la retire SANS RIEN DIRE. Rencontré en écrivant le tableau ci-dessus,
et attrapé par `test_chaque_cellule_js_est_syntaxiquement_valide` — c'est exactement ce
pour quoi ce test existe.

⚠️ **Et une leçon de méthode, apprise deux fois de suite le même jour :** un `cd` en tête
de commande composée PERSISTE pour les commandes suivantes. Deux commits sont partis avec
`pytest` exécuté depuis `web/observable` (« no tests ran », pris pour un succès) et une
mise à jour de `CLAUDE.md` échouée sur `FileNotFoundError` — `git` ayant, lui, fonctionné
depuis n'importe où dans le dépôt. **Chemins absolus pour tout ce qui n'est pas git.**

**Reproductibilité vérifiée, et une convention indispensable pour l'obtenir.** Refait à la
main sur le premier mois projeté : équation (925 473) + recalage (23 359) = **948 833**,
soit exactement la valeur publiée, à 0,00 près. Mais il a fallu savoir qu'**un indicateur
dont le mois demandé n'est pas encore publié est remplacé par sa dernière valeur connue** —
le cas du chômage dès le premier mois, puisqu'il entre sans décalage. Cette convention
figurait dans la légende du graphique, pas dans le bloc de formule ; elle y est maintenant.
**Une formule publiée sans ses conventions n'est pas reproductible, elle est décorative.**

**La page de prévision est rangée par BESOIN DU LECTEUR, plus par architecture du modèle
(2026-08-29).** L'ordre était celui de la construction : verdict, puis étage 1 (taux),
étage 2 (transactions), outil d'audit des décalages, PUIS la projection, puis les
scénarios. **La sortie du modèle arrivait en quatrième position**, après deux sections de
machinerie — un dirigeant traversait la fabrique pour atteindre le produit. Nouvel ordre :

| | section |
|---|---|
| 1 | La projection : où va le marché, et jusqu'où s'y fier |
| 2 | Et si les conditions changeaient ? Le panneau de scénarios |
| 3 | Le taux de crédit : ce que l'OAT 10 ans détermine d'avance |
| 4 | Les transactions : le modèle, et sa mise à l'épreuve |
| — | 🔬 audit des décalages, 🧪 ce qui a échoué |

Aucun calcul ne change : le runtime d'Observable résout les cellules par **flot de données**,
pas par ordre dans le document, donc déplacer des sections de Markdown ne casse rien — les
tests de cellules le confirment. **Ce qui casse, ce sont les renvois écrits en dur** : « =
équation de la section 2 » pointait désormais vers une section placée APRÈS (devenu
« détaillée en section 4 »), et « le tableau de la section 3 » désignait un tableau remonté
en section 1. `grep` « section N », « ci-dessus », « plus bas » après tout réordonnancement.

**Le chapeau était remonté à 704 mots** — presque le double des 370 qui avaient été jugés
inacceptables sur la Synthèse. Il avait absorbé, correctif après correctif, le périmètre,
le report à plat et la méthode. Ramené à **148 mots** ; le reste vit dans un repli
« ℹ️ La méthode, en détail ». ⚠️ Contrairement au `how_to_read` de la Synthèse, qui est une
interpolation depuis le JSON et donc INVISIBLE aux robots, ce repli-ci est du **Markdown
statique** : son contenu reste dans le HTML livré (vérifié). Aucun texte indexé n'est perdu
— c'est la bonne façon de raccourcir un chapeau.

**L'équation est publiée comme une ESTIMATION, plus comme un fait (2026-08-29).** Elle
sortait en coefficients nus : ni période d'ajustement, ni nombre d'observations, ni le
moindre écart-type — sur une page qui admettait par ailleurs que ses résidus sont
autocorrélés à 0,88. Trois manques comblés :

* **Provenance** : « ajustée sur 270 mois, de novembre 2003 à avril 2026 ». Elle n'était
  visible nulle part dans le HTML livré (vérifié : ni « 2003 », ni « 270 »).
* **Incertitude, en DEUX jeux.** `forecast.ols_se` renvoie les écarts-types OLS *et* ceux
  corrigés de l'autocorrélation (Newey-West, noyau de Bartlett). Leur écart EST le
  résultat : la correction les **multiplie par 2,2 à 3,2**. Les trois coefficients restent
  nettement distinguables de zéro (|t| de 4,5 à 11,8) — le lien existe — mais toute lecture
  de précision fondée sur les écarts-types ordinaires serait fausse d'un facteur trois.
  `NW_LAGS = 12` et non la règle usuelle (≈ 4 ici) : celle-ci est calibrée pour des résidus
  faiblement dépendants, ce qui est exactement ce que ce modèle n'a pas. Le choix est DIT
  sur la page.
* **Les résidus sont MONTRÉS.** Le repli « pourquoi le R² n'est pas en tête » affirmait
  depuis longtemps qu'ils « ne sont pas du bruit, ce sont des vagues » sans jamais les
  tracer. C'est le premier graphique qu'un analyste veut voir, et le seul qui rende l'aveu
  vérifiable.

⚠️ **Même corrigés, ces écarts-types restent une BORNE BASSE**, et la page le dit : sur deux
séries tendancielles régressées en niveau, une part du lien peut être fortuite et aucune
correction d'écart-type ne répare ça. C'est le backtest qui tranche. Ne jamais présenter les
Newey-West comme la mesure finale de l'incertitude de ce modèle.

**Le verdict de tête est GÉNÉRÉ, jamais écrit.** « Prévision & Scénarios » publiait les
entrailles du modèle — un R², une MAPE, trois coefficients OLS, un z-score d'intentions
d'achat — et nulle part sa conclusion. `web_export._verdict` produit la phrase (sens,
ampleur, mois visé) et la fiabilité mesurée à cet horizon. Il porte des chiffres, donc il
ne peut PAS vivre dans le chapeau statique, que rien ne régénère : c'est le seul bloc de
tête de page légitimement dynamique. `_VERDICT_HORIZON = 6` — l'horizon auquel un
particulier raisonne, et le premier auquel le modèle bat la naïve. Le seuil de 1,5 %
en deçà duquel il dit « stable » n'est pas cosmétique : l'erreur à six mois vaut 5,7 %,
donc annoncer une variation plus petite reviendrait à commenter son propre bruit.

**L'horizon du verdict est celui du LECTEUR, pas du millésime (corrigé le 2026-09-03).**
`_VERDICT_HORIZON = 6` désignait le 6ᵉ rang de la série projetée. Or celle-ci démarre au
dernier mois **observé**, et l'IGEDD publie avec environ trois mois de retard : en
septembre 2026, le « verdict à six mois » visait **décembre 2026, soit trois mois devant le
lecteur**. La page annonçait donc un horizon qu'elle ne tenait pas.

Le remplacement (`_VERDICT_MOIS_DEVANT = 6` + `_verdict_horizon()`) vise le premier mois
situé à six mois de la **publication**, entre deux bornes qui peuvent se contredire :

* **plancher** `_VERDICT_HORIZON_MIN = 6` — en deçà, recopier le dernier chiffre connu fait
  mieux (voir `crossover_horizon`), donc publier le modèle là le dessert ;
* **plafond** `informative_months` — au-delà, tous les prédicteurs sont reportés à plat et
  la trajectoire RÉPÈTE sa dernière valeur. Aujourd'hui 11, et la série est effectivement
  plate à 868 752 de mai 2027 à décembre 2027. Publier un mois au-delà donnerait un nombre
  que le modèle n'a pas calculé, seulement recopié.

Si le plafond passe sous le plancher, `_verdict_horizon()` rend `None` et l'appelant
retombe sur son repli — il n'y a alors pas d'horizon honnête à publier.

⚠️ **Allonger l'horizon AMÉLIORE mécaniquement la fiabilité affichée**, et il ne faut
jamais présenter le changement ainsi : à l'horizon 6 le modèle n'évite que **+4,2 %** de
l'erreur naïve, contre **+24,2 %** à 9 et **+34,4 %** à 11. La raison du correctif est que
« six mois » doit vouloir dire six mois pour qui lit ; le gain de score est une
conséquence, pas un motif. Ce qui empêche ce réglage d'être une sélection d'horizon
flatteuse : la page publie toujours la table complète par horizon, rangs 1 à 5 compris, où
le modèle PERD.

**Trois corollaires tenus dans la foulée :**

* **`_regime_reliability` prend l'horizon du verdict en paramètre.** C'est un avertissement
  sur le chiffre de tête, pas une statistique indépendante : deux horizons différents
  feraient dire à l'un ce que l'autre ne dit pas.
* **La phrase du verdict porte le TRAJET, plus la seule variation.** « Reculer d'environ
  7 % » n'avait pas de point de départ — le lecteur devait le chercher dans une autre puce.
  Elle dit maintenant « en passant de 954 000 à 879 000 ventes sur douze mois », arrondi au
  millier, et le nombre de mois est écrit en toutes lettres.
* **La fiabilité s'annonce « à cet horizon », sans chiffre.** Écrire « à 9 mois » à côté de
  « dans six mois » ferait cohabiter les deux conventions dans la même phrase. Le rang et
  le décalage de publication sont expliqués une seule fois, dans l'encart des trois
  régimes — dont les bornes se comptent, elles, depuis le dernier mois publié.

⚠️ **Deux conventions coexistent donc sur le site, et chacune doit dire la sienne.**
L'accueil et « Prévisions passées » parlent en horizons **du millésime** (« erreur moyenne
à 6 mois : 5,7 % ») parce que c'est le cadre de l'archive ; le verdict parle en mois **du
lecteur**. C'est la règle générale déjà écrite plus haut — quand deux mesures voisines n'ont
pas la même étendue, chacune doit nommer la sienne.

**Le R² a quitté les cartes de tête, et ne doit pas y revenir.** Autocorrélation des
résidus 0,88, Durbin-Watson 0,24 : sur deux séries tendancielles régressées en niveau, un
R² de 91 % est mécanique et ne prouve rien. Il vit désormais dans un repli avec cette
explication. Les cartes portent à la place le **taux de bon sens** et l'erreur à six mois,
tous deux issus de l'archive — donc de prévisions réellement confrontées au réel.

**TROIS façons de faire disparaître une cellule sans que rien ne le dise**, et trois tests
pour les couvrir. C'est l'angle mort le plus coûteux du framework : `observable build`
valide les liens, jamais l'exécution ni même la syntaxe des cellules. Il construit la page,
annonce ses 240 liens validés, et la cellule fautive n'existe simplement plus dans le HTML
livré.

| Cause | Ce qu'on voit | Test |
|---|---|---|
| `viewof` (syntaxe notebook) | cellule absente, aucun bouton | `test_aucune_page_n_emploie_viewof` |
| Erreur de SYNTAXE dans la cellule | cellule absente | `test_chaque_cellule_js_est_syntaxiquement_valide` |
| Identifiant non importé / inexistant | `RuntimeError: X is not defined` en rouge | `test_chaque_helper_utilise_est_importe` + `test_aucune_cellule_construite_ne_reference_un_identifiant_inconnu` |

**Les deux familles ne se recouvrent pas, et c'est le piège.** Une cellule ABSENTE ne
référence aucun identifiant : le contrôle des entrées non résolues la déclare donc saine.
Vérifier le produit ne suffit jamais — il faut aussi vérifier la source. `node --check` sur
un fichier `.mjs` parse sans exécuter : identifiants inconnus, `await` de premier niveau et
`${…}` du framework passent, seule une vraie erreur de syntaxe échoue.

Le cas rencontré le 2026-08-25 mérite d'être connu : un script d'édition Python a converti
`
` en **vraie nouvelle ligne** à l'intérieur d'une chaîne JavaScript. Syntaxe invalide,
cellule retirée, graphique disparu, build muet. Depuis, **préférer l'outil d'édition à un
script pour toute chaîne contenant des échappements** — la même erreur avait déjà failli
passer sur `previsions.md`.

**Un helper utilisé sans être importé ne casse QUE dans le navigateur.** `observable build`
valide les liens, pas les références de cellules : une page qui emploie `TIP` sans l'importer
se construit sans un mot — 240 liens toujours validés — et affiche
`RuntimeError: TIP is not defined` en rouge à la place du graphique. Arrivé en production sur
le modèle de taux, parce que la vérification portait sur le HTML construit (les textes
étaient bien là) et non sur l'exécution des cellules. C'est le même angle mort que `viewof`
ci-dessous : le build ne dit rien, seul le navigateur le montre.

DEUX tests couvrent désormais ce trou, et ils sont complémentaires.
`test_chaque_helper_utilise_est_importe` compare les exports de `hm.js` aux imports de chaque
page et tourne SANS build. `test_aucune_cellule_construite_ne_reference_un_identifiant_inconnu`
est la preuve structurelle complète : le HTML construit déclare pour chaque cellule ses
`inputs` et ses `outputs`, donc une entrée qui n'est ni un global, ni un nom importé, ni la
sortie d'une autre cellule est un identifiant que le runtime ne résoudra pas. Il couvre TOUT
(y compris un `nf2` qui n'existe nulle part, que le premier test laisse passer), mais il exige
un `dist/` et se saute sans lui.

`test_chaque_helper_utilise_est_importe` couvre les onze pages.
Deux pièges dans sa fabrication, tous deux rencontrés :

* une page a le droit de définir SA propre version d'un helper — `synthese.md` spécialise
  `legend` et `fmtMonthFR` — donc les noms déclarés localement sont exclus ;
* l'opérateur de décomposition `...TIP` commence par un point, si bien qu'une règle naïve
  « pas précédé d'un point » le confond avec un accès de propriété et laisse passer
  exactement le défaut à attraper. Ma première version du test avait ce trou et ne détectait
  rien. Les `...` sont donc protégés AVANT de retirer les accès `objet.membre`, et une
  contre-épreuve vérifie que le test échoue bien sur la version cassée.

Le test structurel a lui aussi ses deux pièges, rencontrés : une cellule qui ne consomme rien
n'a PAS de clé `inputs` (il faut donc lire `inputs` et `outputs` indépendamment, sinon ses
sorties sont ignorées et l'on croit à un défaut — c'est ce qui faisait passer `zscore` pour
inconnu), et les noms importés sont des entrées sans être des sorties.

**`viewof` n'existe pas dans Observable Framework, et son emploi est SILENCIEUX.** C'est
de la syntaxe notebook : Framework retire la cellule entière du build sans erreur ni
avertissement — liens toujours validés, page construite, simplement aucun bouton. Rencontré
en câblant les scénarios nommés (`set(viewof dTaux, …)`), et repérable uniquement en
cherchant le code dans le HTML construit. Le motif correct est de garder la référence à
l'entrée : `const monInput = Inputs.range(…); const maValeur = view(monInput);`.
`tests/test_web_structure.py` refuse désormais `viewof` hors commentaire.

**Le repère externe est saisi à la main et doit porter sa date.** `BENCHMARK_FNAIM` dans
`web_export.py` : la fourchette annuelle de la FNAIM (900-920 k pour 2026) est la SEULE
prévision chiffrée de volumes publiée en France — les Notaires, qui ont pourtant les
avant-contrats, ne projettent que les prix. Notre modèle donne 912 619, dans leur
fourchette. Trois contraintes : c'est un **point de décembre**, jamais une courbe (leur
chiffre est un total d'année, le nôtre un cumul glissant) ; l'écart de périmètre (~0,6 %)
est dit sur la page ; et deux tests de `test_web_links.py` refusent une année révolue ou un
repère sans lien ni date de relevé.

**Le report à plat des prédicteurs n'est PAS une faiblesse : c'est la bonne hypothèse, au
moins pour les taux (mesuré le 2026-08-24).** Au-delà de leur dernière observation, les
prédicteurs sont maintenus à leur dernière valeur. J'ai longtemps décrit ça comme
« transparent mais faible », et suspecté ce report d'être la source du biais croissant
(+0,7 % à un mois, +6,4 % à dix-huit). Testé : **faux**.

La courbe des taux BCE (dataset `YC`, quotidienne depuis 2004) permet de calculer le taux à
10 ans que le marché attend dans h mois, et de reconstruire cette anticipation à N'IMPORTE
QUELLE date passée — la courbe d'hier *est* l'archive de ce qu'on anticipait hier. La
substitution est donc entièrement backtestable, sans avoir à retrouver une prévision
publiée. Chaîne testée : courbe → forwards 10 ans et 3 mois → variation attendue → étage 1
appliqué en ÉCART (donc immunisé à son biais de niveau de 0,77 pt) → étage 2.

Résultat sur 209 millésimes, **0 bloc d'horizon franchi sur 4** :

| bloc | report à plat | forwards | gain |
|---|---|---|---|
| 1-3 | 3,94 % | 3,94 % | +0,0 % |
| 4-6 | 5,35 % | 5,34 % | +0,2 % |
| 7-12 | 6,25 % | 6,19 % | +0,9 % |
| 13-18 | 7,10 % | 7,21 % | **−1,5 %** |

Ce n'est pas un défaut de câblage : 47 % des mois sont effectivement modifiés, et sur
ceux-là précisément le report à plat fait 7,18 % contre 7,20 % aux forwards. Les forwards
sont **légèrement moins bons**. C'est un résultat classique de la littérature sur les taux —
l'hypothèse des anticipations échoue empiriquement et la marche aléatoire est très difficile
à battre — mais il fallait le mesurer ici plutôt que le supposer dans un sens ou dans
l'autre.

Trois conséquences à tenir :

1. **Ne pas re-tenter la substitution par les forwards.** Le builder `build_yield_curve` a
   été écrit, exécuté, mesuré, puis RETIRÉ avec son CSV : laisser une source rafraîchie
   chaque semaine et un fichier versionné pour une hypothèse réfutée est du poids mort.
2. **Le biais croissant a une autre cause.** Il reste à expliquer, et ce n'est pas le report
   à plat des taux. Piste restante : le modèle est une régression de niveau sur des séries
   à supports disjoints selon le régime (voir « les cycles ne sont pas comparables »).
3. **La moitié « chômage » du lot 5b perd son fondement.** Elle supposait qu'une projection
   institutionnelle batte le report à plat. Si les forwards échouent là où le marché est
   profond et liquide, une projection de chômage publiée quatre fois par an a peu de chances
   de faire mieux — et elle coûterait ~68 PDF lus à la main (la Banque de France renvoie 403
   à tout script). Ne pas s'y lancer sans une raison nouvelle.

**Audit de « Prévision & Scénarios » (2026-08-27) — cinq correctifs.** La page est la plus
rigoureuse du site sur le fond, ce qui rendait ses écarts d'autant plus coûteux.

1. **La légende de la bande décrivait la méthode SUPPRIMÉE.** Elle disait « Bande =
   ±1,28·RMSE hors échantillon », c'est-à-dire la bande constante remplacée depuis par
   `band_table()` — quantiles 10/90 de l'erreur SIGNÉE par horizon. Faux deux fois : la
   méthode, et le `±`, qui annonce une symétrie que la bande n'a pas (à 6 mois : −84 515
   en bas contre +62 680 en haut, parce que le modèle surestime plus qu'il ne sous-estime).
2. **La légende renvoyait à un repère qui n'existe pas.** « Jusqu'au repère […] sans
   hypothèse » : le trait est tracé sur le dernier point `assured`, or `assured_months = 0`
   et le `Plot.ruleX` reçoit un tableau vide. C'est **structurel** — `kc = 0`, le chômage
   entre sans décalage, donc il manque toujours au dernier mois. La carte affichait
   d'ailleurs « dont 0 sans hypothèse » juste au-dessus.
3. **L'horizon informatif manquait, et il vaut 10 sur 18.** `kr = 10` : au-delà du dixième
   mois tous les prédicteurs sont reportés à plat et la trajectoire RÉPÈTE sa dernière
   valeur — h=10 à h=18 valent tous 896 738. La page annonçait « horizon 18 mois » et
   publiait le point final comme s'il informait. `engine.projection()` expose désormais
   `informative_months`, **mesuré sur la trajectoire elle-même** (dernier mois où elle
   bouge encore) et non dérivé des décalages : reste juste si le modèle change de
   prédicteurs.
4. **« C'est la preuve que ces indicateurs avancés prévoient réellement » portait sur la
   fenêtre la plus favorable.** Le backtest de la section 2 part de `FORECAST_SPLIT =
   2021-12`, donc teste sur 2022-2026 : le choc de taux, l'épisode qu'un modèle piloté par
   les taux réussit le mieux (4,6 % de MAPE). L'archive, construite pour éviter exactement
   ce biais, mesure sur 210 millésimes et huit épisodes que le modèle est **battu par la
   naïve en deçà de six mois** (−75,6 % à 1-3 mois, −5,5 % à 4-6). La légende nomme
   désormais sa fenêtre et renvoie aux cartes de l'archive juste au-dessus. ⚠️ Deux
   backtests coexistent sur le site : le court (section 2, illustratif) et le long
   (archive, qui juge). **Ne jamais présenter le court comme une preuve.**
5. **`health.transactions_last_month` était mal nommé** : il reportait la dernière ligne de
   la frame AJUSTÉE (avril 2026, bornée par le chômage BIT trimestriel) et non le dernier
   mois de l'IGEDD (juin 2026). De quoi conclure que les ventes ont deux mois de retard.
   Le champ garde son nom pour la vraie date, et la date d'ajustement s'appelle désormais
   `model_last_fitted_month`.

**La page dit maintenant COMMENT l'utiliser, et sur quel marché (2026-08-27).** Trois
ajouts qui n'inventent aucun calcul — ils assemblent ce que la page portait déjà à des
endroits éloignés :

* **Encart des trois régimes, sous le verdict.** Croiser l'horizon de bascule contre la
  naïve (`crossover_horizon`, 6) et l'horizon informatif (`informative_months`, 10) donne
  une règle d'usage que ni l'un ni l'autre ne donnait seul : **moins de 6 mois → s'en tenir
  au dernier chiffre connu** (le modèle y fait moins bien), **6 à 10 mois → la zone utile**,
  **au-delà de 10 → un niveau d'atterrissage, pas un chemin**. Le premier régime est
  contre-intuitif pour qui vient chercher une prévision, et c'est précisément pour ça qu'il
  doit être écrit. `crossover_horizon` reprend la MÊME définition que la page « Prévisions
  passées » (premier horizon à skill > 0) : deux définitions du même seuil finiraient par
  donner deux chiffres.
* **Les mois de taux déjà déterminés passent en PREMIÈRE carte de l'étage 1.** Sept mois de
  taux de crédit fixés par des OAT déjà publiées, contre **zéro** mois « assuré » côté
  transactions : c'est le seul chiffre prospectif du site qui ne repose sur aucune
  hypothèse, et il était présenté après deux cartes techniques comme un sous-produit du
  modèle explicatif.
* **Le chapeau statique nomme le périmètre.** « La série projetée est celle des ventes de
  logements anciens, et elle seule » — ni chantiers, ni rénovation, avec la raison
  (permis → chantiers mesuré puis écarté ; aucune série de volume pour la rénovation) et la
  conséquence pour le lecteur du bâtiment : **indicateur de contexte, pas prévision de son
  carnet**. Sans chiffre, donc pérenne.

**Les chiffres par plage d'horizon ne sont plus écrits en dur.** Le paragraphe qui justifie
le seuil d'entrée d'un prédicteur affirmait « il perd contre une prévision naïve en deçà de
six mois et lui prend 40 % d'erreur au-delà d'un an » : exact au jour où c'était tapé,
régénéré par rien. `_horizon_blocks(con)` produit le tableau depuis l'archive, comme le
verdict, et la page l'affiche.

**`.hm-table` est passée de `actualites.md` au thème global.** Une classe partagée qui vit
dans le `<style>` d'une seule page se casse en silence le jour où une seconde l'emploie :
elle rend sans style, et le build ne dit rien.

**La fiabilité est désormais publiée CONDITIONNELLE AU RÉGIME DE TAUX (2026-08-29).**
C'est la suite directe de la mesure sur la fenêtre d'entraînement. La page publiait deux
ventilations de sa performance — par horizon, par épisode — et les deux décrivent le passé.
Aucune ne disait ce que vaut le chiffre qu'on lit AUJOURD'HUI.

Or la performance dépend massivement d'une seule chose : le taux de crédit bouge-t-il ?
Corrélation de rang entre l'erreur évitée et l'amplitude du mouvement de taux sur douze
mois, sur 209 millésimes : **+0,52**. Par tercile, en agrégeant les erreurs :

| régime | erreur modèle | erreur naïve | erreur évitée | sens juste à 6 mois |
|---|---|---|---|---|
| taux quasi stables | 6,38 % | 5,96 % | **−6,9 %** | **55,2 %** |
| mouvement modéré | 5,53 % | 6,52 % | +15,2 % | 62,3 % |
| fort mouvement | 6,00 % | 11,32 % | **+47,0 %** | **97,1 %** |
| *toutes conditions (ce qui était seul publié)* | 5,97 % | 7,96 % | +25,0 % | 71,6 % |

Le « 72 % de bon sens » affiché à côté du verdict est la moyenne de deux mondes — exacte,
et trompeuse dans les deux sens. `_regime_reliability` publie donc le régime courant et la
fiabilité mesurée dans ce régime, avec un avertissement quand l'avantage est faible.

Trois points de méthode à tenir :

* **Ce n'est pas un réglage.** Le mécanisme était posé AVANT la mesure — l'étage 2 n'a
  qu'un canal, le coût du crédit — et la relation est monotone sur trois terciles de
  ~1 200 points chacun.
* **Agréger les erreurs, jamais moyenner des ratios.** Le premier calcul de cette mesure
  moyennait des skills par millésime et rendait **−110 %** : en régime calme la référence
  naïve est minuscule, donc chaque ratio explose. Le chiffre juste est −6,9 %.
* **Publier le CENTILE à côté du libellé.** Au moment de la mise en place, le mouvement
  courant (0,15 pt) tombait à **0,02 point** de la borne calme/intermédiaire. Une étiquette
  seule cacherait cette fragilité.

**Et le correctif qui semblait en découler a été mesuré puis REJETÉ.** Si le modèle perd en
régime calme et écrase en régime agité, mélanger les deux prévisions selon le régime devrait
battre les deux. Testé hors échantillon (bornes de tercile recalculées en expansion, donc
jamais choisies sur les données qui les jugent), 161 millésimes, 2 745 points :

| | 1-3 | 4-6 | 7-12 | 13-18 | **7-18 (zone utile)** | sens juste |
|---|---|---|---|---|---|---|
| seuil franc | +23,9 % | +8,5 % | −2,1 % | −12,7 % | **−8,0 %** | **45,8 %** |
| poids continu | +37,2 % | +20,1 % | +7,7 % | −9,3 % | **−1,8 %** | 72,7 % |

Le poids continu franchit 3 plages sur 4 — donc la lettre de la porte — mais **uniquement
sur 1 à 6 mois, la zone où le site dit déjà de s'en tenir au dernier chiffre connu**. Au-delà
de six mois il fait moins bien, et sa dégradation **s'aggrave avec le temps** : +7,4 % sur
les millésimes 2013-16, −6,3 % sur 2017-20, **−23,0 % sur 2021-25**. Une relation qui
s'inverse ainsi n'en est pas une. Le seuil franc, lui, effondre le sens du marché annoncé
(45,8 % contre 73,3 %) : en régime calme il recopie la naïve, qui par construction n'annonce
aucun sens. **Même leçon que le candidat BLS : un gain concentré là où le modèle n'est pas
consulté n'est pas un gain.** Publié dans `REFUTATIONS`, ne pas re-tester sans raison neuve.

**Les hypothèses écartées sont PUBLIÉES, dans `REFUTATIONS`.** La page de prévision porte
une section « Ce qu'on a essayé, et qui ne marche pas » qui liste les trois idées plausibles
mesurées puis refusées : la demande de crédit BLS, les anticipations de taux du marché, et
les permis pour prévoir les chantiers. C'est le pendant de « Prévisions passées » — là on
montre où le modèle se trompe, ici ce qu'on a renoncé à lui ajouter. Un site qui n'affiche
que ce qui a marché laisse croire que tout ce qu'on essaie marche, et c'est un biais de
sélection, pas une simplification.

Les trois entrées sont des constantes **stockées et datées** dans `web_export.py`, jamais
recalculées : chaque mesure a coûté un backtest à origine glissante de plusieurs centaines
de millésimes, ce sont des résultats sur la MÉTHODE et ils ne bougent pas d'une semaine à
l'autre. Deux tests de `test_web_links.py` refusent qu'une entrée perde sa date ou que la
section disparaisse de la page. La section rappelle aussi le seuil d'entrée du modèle
(≥ 5 % d'erreur évitée hors échantillon sur ≥ 3 blocs d'horizon), au bon endroit pour qu'il
se comprenne : juste à côté des trois candidats qu'il a refusés.

**Un permis ne précède PAS une mise en chantier — mesuré le 2026-08-24, et c'est
contre-intuitif.** Le plan prévoyait un modèle de prévision du neuf pour le professionnel du
bâtiment, sur une intuition que j'ai répétée sans la vérifier : « une autorisation précède
mécaniquement un chantier, donc SIT@DEL donne une avance gratuite ». Elle est fausse dans
cette série, et de deux façons indépendantes :

* sur les flux mensuels, le R² de `chantiers(t) ~ permis(t−k)` est **maximal à k = 0**
  (0,710) et décroît de façon **monotone** (0,627 à un mois, 0,539 à six, 0,258 à douze).
  Un indicateur avancé donnerait une bosse à un décalage positif ; ici la courbe descend
  dès le premier mois. C'est ce profil que la page publie — la preuve tient en une courbe.
* backtest à origine glissante, 197 millésimes depuis 2010, une régression par horizon
  (`y(t+h) ~ permis12(t) + écart cumulé`) : **0 bloc d'horizon franchi sur 4**, et le
  modèle fait **25 % d'erreur en PLUS** que la persistance (9,15 % contre 7,30 %), en se
  dégradant avec l'horizon (−31 % à 13-18 mois). Sens du marché annoncé juste 52 % du
  temps, c'est-à-dire à pile ou face.

Attention au piège qui m'a d'abord induit en erreur : mesuré sur les **cumuls 12 mois**, le
décalage optimal ressort aussi à 0 — mais pour une raison sans rapport, deux fenêtres de
douze mois se recouvrant presque entièrement. Il faut passer par les **flux mensuels** pour
que la question ait un sens. Et le R² brut donnait le modèle gagnant à h = 18 (0,347 contre
0,203) : artefact d'échantillon, que le backtest hors échantillon renverse complètement.

Cause probable : les deux séries sont CVS-CJO et remontent par la même voie administrative,
si bien que le délai de déclaration pèse davantage que le délai physique de chantier. Le
décalage réel existe projet par projet, mais la moyenne nationale mensuelle l'efface.

**Ce que la page publie à la place : le taux de transformation.** Mises en chantier sur
12 mois ÷ logements autorisés sur 12 mois — 78,0 % aujourd'hui contre 84,8 % en moyenne de
long terme. Il ne prévoit rien, donc il n'a besoin d'aucune validation hors échantillon, et
il dit ce qu'un fournisseur veut savoir : combien d'autorisations deviennent des chantiers.
Ses limites sont écrites sur la page et doivent y rester — il rapporte deux flux d'une même
fenêtre et non une conversion projet par projet, il peut dépasser 100 % quand un stock
ancien se débloque, et une autorisation abandonnée n'est jamais retirée de la série.
`NEUF_GATE` dans `web_export.py` porte le résultat de la mesure, **stocké et daté** plutôt
que recalculé : c'est un résultat sur la méthode, pas une métrique vivante, et rejouer
197 millésimes à chaque export coûterait des minutes au job hebdomadaire pour un chiffre qui
ne bouge pas. `tests/test_web_structure.py` refuse que la formule, le profil de décalage,
l'aveu ou les limites disparaissent de la page.

**La ventilation par épisode est le pendant de la ventilation par horizon.** `_by_episode`
découpe les millésimes en huit épisodes de marché. L'une dit *à quelle distance* le modèle
sert, l'autre *dans quelles conditions* — et c'est la seconde qui explique la première :
les trois épisodes où il perd (crise financière, creux 2012-15, Covid) ont en commun que
le moteur du marché n'y était pas le coût du crédit.

**`by_horizon` porte trois métriques, pas une.** `direction` (part de fois où le SENS annoncé
par rapport au dernier chiffre connu était le bon) est la seule des trois qu'un lecteur non
statisticien peut utiliser telle quelle — et c'est celle sur laquelle une décision d'achat ou
un plan de charge se prennent réellement. `coverage` est la part de mois tombés dans la bande
annoncée : sans elle, rien ne dit qu'une bande « à 80 % » en vaut 80. Les deux sont exportées
dans `archive.json`.

**La garde de contenu évite une archive qui gonfle pour rien.** Le job hebdomadaire tourne
même sans nouveauté ; `append_if_new` compare la prévision aux lignes du dernier
enregistrement DE SON TYPE et n'ajoute rien si elle est identique. D'où l'arrondi à l'unité
des transactions : sans lui, un bruit de calcul créerait une ligne par semaine.

**L'ordre des étapes du workflow compte.** `forecast_archive.py --record` tourne APRÈS
`fetch_new_sources.py` et AVANT `web_export.py`, qui lit l'archive pour construire sa page.
Le script ouvre l'entrepôt avec `refresh=True`, donc il reconstruit lui-même CSV dérivés et
Parquet — il ne dépend pas de l'export pour ça. Un modèle non calibrable n'interrompt pas le
job : on perdrait une publication de données pour une ligne d'archive.

**Le front comptait SIX JSON à l'ajout de l'archive**, pas cinq — et en compte **sept**
depuis le 2026-08-23 (`previsions.json`, voir « L'API HTTP ») : `python
web/export/web_export.py` doit annoncer `0/7 fichier(s) modifié(s)` quand rien n'a bougé.
`archive.json` change, lui, dès qu'une prévision est enregistrée — c'est normal,
contrairement aux autres.

**Un bloc ```` ```js ```` collé sous un `<div>` n'est plus une cellule.** Sans ligne vide
entre les deux, l'analyseur Markdown range la clôture dans le bloc HTML : le code
s'affiche **en toutes lettres** au milieu de la page et les variables qu'il devait définir
manquent, d'où un `RuntimeError: … is not defined` plus bas. Le build ne dit rien — le
Markdown reste valide, il ne veut simplement plus dire la même chose, et la validation de
liens comme le sommaire de page continuent de fonctionner. Rencontré en insérant les
renvois entre sections jumelles ; `tests/test_web_structure.py` refuse désormais toute
ouverture de bloc de code non précédée d'une ligne vide.

**Une interpolation `${…}` ne fonctionne que dans le CONTENU d'un élément.** Dans un
attribut HTML brut (`style=${…}`) elle reste affichée telle quelle, et dans un `<tbody>`
écrit en HTML brut le marqueur du framework est éjecté hors de la table par l'analyseur.
Légendes et tableaux se montent donc en JS (``display(html`…`)``). Les deux cas ont été
rencontrés en écrivant `previsions-passees.md`.

**Une branche « rien à afficher » ne passe pas par `display()`.** Le gabarit vide
`` html`` `` ne rend pas un nœud vide : htl renvoie **`null`** quand le fragment n'a aucun
enfant, et `display()` envoie à l'inspecteur tout ce qui n'est pas un nœud DOM — la page
affiche donc `null` en rouge, tout comme elle afficherait `""` pour une chaîne vide. Écrire
`if (condition) display(…)`. Rencontré sur « Données & Sources » : trois `null` sous
l'encart d'API injoignable, plus huit latents sur « Prévision » et cinq sur
« Environnement ». Le build ne dit rien, et le défaut ne se voit QUE dans l'état où la
donnée manque — API éteinte, aucun fichier importé — c'est-à-dire l'état normal d'un
visiteur du site public. `tests/test_web_structure.py` refuse désormais tout `display()`
dont une branche vaut `` html`` `` ou `""`.
