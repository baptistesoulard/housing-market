# Les pages départementales et le module Territoires

> **Journal daté — ne pas réécrire.** Ce fichier est l'ancien contenu de `CLAUDE.md`,
> déplacé tel quel le 2026-09-23. Chaque paragraphe reflète l'état du dépôt À SA DATE :
> les chiffres, les noms de fichiers (`app.py`, `web_export.py` d'un seul tenant…) et les
> décomptes ont pu changer depuis. L'état courant et les règles en vigueur sont dans
> `CLAUDE.md` ; ce journal garde le POURQUOI et les mesures. On y ajoute des entrées
> datées, on ne corrige pas les anciennes.

## Les pages départementales — ce qui doit rester vrai

> **⚠️ ÉTAT AU 2026-08-23 : les pages sont REVENUES en ligne, sur un mécanisme de
> chargement différent — la piste documentée ci-dessous jusqu'au 2026-08-21 a été
> essayée et s'est révélée **fausse**.
>
> Le retrait du 2026-08-21 avait laissé une piste de reprise : un *data loader
> paramétré* (`src/departement/[code].json.js`) avec `FileAttachment("./[code].json")`
> côté page, présenté comme « la première chose à essayer » pour supprimer le `fetch`
> soupçonné de l'intermittence observée en production. Essayé, et écarté sur preuve —
> pas sur préférence : le build produit bien 101 fichiers distincts, mais **chaque page
> enregistre côté client la même référence LITTÉRALE `[code].json`**, jamais résolue au
> code réel. `findFiles` (l'analyseur de `FileAttachment` dans le framework) ne reçoit
> `params` à aucun moment — vérifié dans son code source. Constaté dans le HTML construit
> de chaque département : `registerFile("./[code].json", {…"path":
> "../_file/departement/[code].xxxxxxxx.json", "size":2…})` — 2 octets, un `{}` vide,
> le même pour les 101 pages. Sans ce contrôle, les 101 pages seraient reparties en ligne
> avec des données vides partout, une régression pire que l'intermittence.
>
> **Ce qui remplace le data loader** : `fetch()` vers l'adresse stable que
> `scripts/postbuild.mjs` copie au build (`/data/departements/<code>.json` — le mécanisme
> déjà en place avant le retrait), mais avec la structure de cellules que la dernière
> investigation avait vue s'exécuter correctement en production : un bloc d'imports
> seul, un bloc par `await`. Le paramètre de route n'est PAS lu depuis
> `observable.params.code` au runtime comme avant — le framework substitue en fait la
> valeur au BUILD, dans le corps transpilé de la cellule (vérifié dans le HTML construit
> de deux départements différents : `` fetch(`/data/departements/${"75"}.json`) ``,
> `` fetch(`/data/departements/${"57"}.json`) `` — la valeur est un littéral, pas une
> référence). L'annuaire partagé (non paramétré, `departements.json`), lui, passe par
> `FileAttachment` sans problème — c'est le même mécanisme que les huit autres pages du
> site, et rien dans son fonctionnement ne dépend d'un paramètre de route.
>
> **Ce qui reste une inconnue honnête** : l'intermittence originale a été observée sur le
> site **déployé** (Cloudflare Pages), jamais reproduite en local, et l'investigation
> d'origine ne l'a jamais formellement expliquée — seulement débattue par élimination.
> Ce correctif change la SOURCE des données (adresse stable + structure de cellules
> vérifiée) mais pas la mécanique `fetch()` elle-même ; si la cause réelle était ailleurs
> (edge Cloudflare, cache, bootstrap du runtime client), elle pourrait resurgir. À
> surveiller après une période en production — un test « ça marche une fois » ne suffit
> pas à trancher, exactement le piège que l'investigation d'origine avait déjà signalé.
>
> Vérifié avant remise en ligne : build propre à 111 pages (236 liens validés), 101
> fichiers copiés vers l'adresse stable, 101 titres/`<h1>` personnalisés, aucune page
> `noindex` (un défaut latent de la toute première version, jamais vu avant faute
> d'avoir cherché), 225 tests Python verts, `web_export.py` toujours à `0/6` + `0/102`.
> La vérification visuelle en navigateur intégré n'a pas pu confirmer le rendu final des
> cartes/graphiques : l'onglet du panneau de prévisualisation ne composite aucune frame
> tant qu'il n'est pas affiché (voir plus bas, section « Vérifier la parité ») — y
> compris sur des pages déjà stables comme `neuf.md`, donc ce n'est pas spécifique à
> cette page. La preuve retenue est le HTML construit lui-même : titres, adresses de
> données et valeurs substituées, inspectés directement.

101 pages générées par UNE route paramétrée (`web/observable/src/departement/[code].md`),
qui font passer le site de 10 à 111 pages. Elles s'adressent à un particulier et répondent
à quatre questions, pas davantage : combien coûte le m² ici, combien de ventes s'y font,
combien de m² une capacité d'emprunt y achète — et, depuis le 2026-09-20, qui y habite et
qui y arrive (le profil du recensement, voir « Le module Territoires » plus bas).

### D'où viennent les données

**Deux sources, parce que DVF ne publie qu'une fenêtre glissante de cinq ans.** Vérifié en
interrogeant la source : `files.data.gouv.fr/geo-dvf/` ne porte qu'un seul millésime
(`2025-12`, couvrant 2021-2025) et aucun millésime archivé — il n'y a rien à empiler.

| Période | Source | Rafraîchie par | Commitée |
|---|---|---|---|
| 2021-2025 | `files.data.gouv.fr/geo-dvf/latest/` (officielle, LOv2) | `fetch_new_sources.build_dvf`, **à la main** (voir ci-dessous) | `data_manual_input/dvf-recent.csv` |
| 2014-2020 | miroir `data.cquest.org/dgfip_dvf/` (millésimes archivés) | `dvf_backfill.py`, à la main, **jamais en CI** | `data_manual_input/dvf-historique-2014-2020.csv` |

`DataManager.ensure_dvf` recolle les deux en `data/dvf.csv` (la moitié récente l'emporte en
cas de recouvrement), et le contrat pandera `dvf` valide le tout.

**Le raccord 2020/2021 ne crée pas de marche**, et ce n'est pas une supposition. Le format
brut n'a pas d'`id_mutation` ; la clé reconstruite ne reproduit pas la partition
officielle, mais l'écart mesuré sur la médiane PUBLIÉE est de +0,00 % (Lozère) et +0,15 %
(Paris), mesuré sur des données où les deux sources coexistent. Sur les 97 départements, la
soudure donne −0,60 % d'écart médian, contre +0,78 % pour un passage de trimestre
ordinaire.

**`build_dvf` est dans `BUILDERS` depuis le 2026-09-03, et il est CONDITIONNEL.** Il n'y
était pas : le builder existait, marchait, et n'était jamais exécuté automatiquement — les
pages départementales avançaient au rythme des lancements à la main, pendant que cette page
affirmait « chaque semaine ». Le câbler tel quel aurait fait descendre ~500 Mo tous les
lundis pour un fichier que la DGFiP republie **deux fois par an**, ce qui était la vraie
raison de son absence.

D'où la garde : `_dvf_publication()` interroge le `Last-Modified` d'**un fichier par année
publiée** (5 requêtes `HEAD`, quelques octets) et le compare à une empreinte stockée. Si
rien n'a bougé, le builder rend la main en ~2 s au lieu de plusieurs minutes.

Deux points de conception à ne pas défaire :

* **L'empreinte est un fichier VERSIONNÉ** (`data_manual_input/dvf-recent.lastmod.txt`), pas
  le `mtime` de `dvf-recent.csv`. Un `git clone` — ou le checkout d'un runner CI — horodate
  les fichiers à l'instant du checkout : le CSV paraîtrait donc toujours plus récent que la
  source, et la garde sauterait **toujours**, sur la machine même où elle compte le plus.
  C'est le symétrique exact du piège que la garde de fraîcheur de `warehouse.resolve()`
  traite côté poste de travail.
* **Les en-têtes HTTP sont parsés avant d'être comparés.** `max()` sur des chaînes
  `Last-Modified` trie sur le nom du jour : « Mon, 18 May 2026 » passerait après
  « Tue, 02 Jun 2025 ». Le retour est une chaîne ISO-8601 UTC, comparable telle quelle et
  lisible dans le fichier versionné. J'ai écrit le bug avant de le corriger ; il ne se voit
  qu'au moment d'une republication, c'est-à-dire deux fois par an.

Toute réponse manquante (`Last-Modified` absent, HEAD en échec) rend `None` et **déclenche
le téléchargement** : ne jamais inverser ce défaut — mieux vaut descendre un demi-giga pour
rien que rater une publication en silence. `force=True` court-circuite la garde.

⚠️ **`ensure_dvf` n'a AUCUN appelant (constaté le 2026-09-19), donc la chaîne s'arrête à
mi-chemin.** `build_dvf` rafraîchit bien `dvf-recent.csv` deux fois l'an, mais rien ne
rejoue le recollage vers `data/dvf.csv` — ni `load_or_generate_all()` (qui ne connaît pas
ce dataset), ni le workflow. Or c'est `data/dvf.csv` que la vue SQL `dvf` lit, donc les 101
pages départementales resteraient figées au recollage du 2026-08-20 même après une
republication DGFiP, sans erreur ni signal. À brancher (un appel mtime-aware au démarrage,
comme `ensure_ecln`) : depuis que le job commite `data/` entier, le fichier recollé suivrait
alors tout seul.

**Ne jamais commiter les fichiers DVF bruts** : ~500 Mo pour la fenêtre glissante, 1,1 Go
pour l'historique. `build_dvf` les télécharge, les nettoie et les JETTE.

**Le millésime d'une année ne doit jamais être celui qui la clôt.** DVF publie avec un
décalage : le millésime 202104 ne porte que 27 lignes de Côte-d'Or au T3 2020 contre 6 666
au T1, parce qu'il a été publié avant que le second semestre ne remonte. Agréger là-dessus
produisait 19 trimestres fantômes. D'où `MIN_VENTES_TRIMESTRE = 50` dans `dvf_backfill`, un
plancher qui **signale** ce qu'il retire — il reste 21 trimestres écartés en 2018, dernière
année du consolidé, pour la même raison.

### Le filtre retenu, et pourquoi

Documenté en tête de `dvf_clean.py`, résumé sur chaque page dans le repli « La méthode, en
clair ». Deux décisions ont été prises **par l'utilisateur**, sur mesures, parce qu'elles
changent les chiffres publiés :

- **Les dépendances sont tolérées.** Une maison vendue avec son garage est une vente
  normale. Les écarter coûterait 66 % de l'échantillon pour ne déplacer la médiane que de
  −6,9 % (Lozère) / −0,8 % (Paris), en déformant la composition vers les maisons sans
  annexes. Conséquence assumée et affichée : le prix au m² surestime légèrement le
  logement seul.
- **Écrêtage aux percentiles 1 %/99 % par département ET par année**, pas de bornes
  nationales : le 99ᵉ percentile parisien est à 25 730 €/m², un plafond fixe à 20 000 €
  couperait des ventes authentiques. Enjeu faible — on publie une médiane.

Le reste n'était pas un arbitrage mais une contrainte des données : `surface_reelle_bati`
est remplie à 100 % sur les logements quand la surface Carrez ne l'est qu'à 1,5 % en
Lozère, et `valeur_fonciere` est le prix TOTAL de la mutation répété sur chaque ligne (0
mutation sur 2 206 ne varie) — un calcul ligne à ligne surestime de +14 % / +5,4 %.

### Les quatre départements sans données

`57`, `67`, `68`, `976` — vérifié un par un, chacun renvoie 404 sur toutes les années.
L'Alsace-Moselle relève du Livre foncier, Mayotte n'est pas couverte. La liste vit dans
`dvf_clean.DEPARTEMENTS_SANS_DVF` et un test la verrouille. **Ces quatre pages existent et
expliquent l'absence** au lieu d'afficher des graphiques vides : une page blanche passe
pour une panne du site.

### Poids et rendu

**Budget : 10 Ko bruts par département**, vérifié à l'écriture (`_verifier_budget` alerte
en clair). Mesuré : 8,9 Ko au maximum, 8,3 Ko en moyenne, 0 dépassement, pour 12 ans
d'historique et trois types de biens. Le format est **colonnaire** (dates une fois, valeurs
en tableaux nus) contrairement au reste du site : sur 48 trimestres × 3 types, répéter les
clés coûte plus que la donnée.

**Un fichier par département, chargé à la demande** — un fichier unique ferait télécharger
le pays entier à qui veut voir le sien. L'index (`departements.json`) est le seul chargé
d'emblée, pour le sélecteur.

**`FileAttachment` ne fonctionne PAS dans une page paramétrée**, et c'est vérifié, pas
supposé : le framework le résout au build en lisant le nom du fichier dans le source, or il
n'y a rien à lire quand le nom vient du paramètre de route. La page se construit et
`dist/_file/data/departements/` reste vide. D'où le repli : `postbuild.mjs` copie les
données à une adresse **stable** (`/data/departements/<code>.json`) et la page les lit par
`fetch()`. Même raison que pour la vignette de partage — les fichiers que le framework
copie reçoivent un nom haché.

**Le `<title>` est réécrit par `postbuild.mjs`.** Une route paramétrée n'a qu'UN
front-matter pour ses 101 pages : sans ce correctif, les 101 portent le même titre, ce qui
est exactement la cannibalisation que des descriptions distinctes cherchent à éviter.
`head()` ne peut pas le faire — le framework ajoute son `<title>` après. Vérifié après
build : 101 titres distincts, 101 descriptions distinctes, 0 doublon.

**Et depuis le 2026-09-19, `postbuild.mjs` écrit aussi un CHAPEAU CHIFFRÉ sous l'accroche
de chacune des 101 pages** — prix médian au m², évolutions à un et cinq ans, ventes du
trimestre, prix médian d'un logement, m² accessibles, France entière au même trimestre ;
et pour les quatre départements hors DVF, le texte d'`absence`. C'est **l'exception
légitime** à la règle « aucun chiffre dans le texte statique » : cette règle existe parce
que rien ne régénère un chapeau écrit à la main, or celui-ci est écrit par la machine à
CHAQUE build (`site.config.depChapeau`, depuis le même JSON que la page lit au runtime),
donc exactement aussi frais que les cartes. Pourquoi il fallait le faire : un tiers a
montré que le moteur de rendu de Google avait indexé, sur `/donnees`, le message
`RuntimeError: Failed to fetch dynamically imported module` **à la place des graphiques**.
Vérifié : le hash cité était bien celui servi en production (200), inchangé depuis le 23
août — donc pas une course entre crawl et déploiement, mais un `import()` **abandonné par
le renderer** (budget de temps ou de requêtes), que le runtime écrit ensuite en rouge dans
le DOM. Confirmé dans la Search Console (inspection d'URL → page explorée → « Plus
d'infos ») : sur `/donnees`, **5 ressources sur 54** non chargées, dont deux modules du
site en « Other error » — `theme.b3350452.js` et le module `isoformat` 0.2.1 sous `_npm/` — qui servent
tous deux en 200 ; sur `/departement/48`, 2 sur 52, et ce sont une police Google et le
beacon Cloudflare Insights, aucun module du site. Le renderer de Google n'est donc pas
déterministe d'une page à l'autre : c'est bien un abandon de sa part, pas un défaut de la
page, et il peut frapper n'importe quelle page au prochain passage. Sur `/donnees`, 305
mots statiques survivaient. Sur les pages départementales,
dont tout le contenu arrive par `fetch()`, il n'y avait **aucun chiffre** à indexer — pour
la requête « prix m² + département », la seule qui amène du trafic ici. Trois tests de
`test_web_seo.py` : le prix du JSON est en clair dans le HTML sous l'accroche et avant la
première section, l'absence est expliquée en statique, et deux passes de postbuild
laissent UN paragraphe (remplacé, jamais empilé). Le nom du département est apposé en
tête, sans préposition — même raison que pour la description (« en Paris »).

**Conséquence pour `npm run dev`** : le serveur de développement ne sert PAS
`/data/departements/` (la copie est faite par `postbuild`, donc au build seulement). Une
page départementale ouverte en préversion affichera sa structure sans ses chiffres. Se
vérifier sur `dist/`.

### La courbe nationale sur le graphique des ventes

Le graphique « Combien de ventes ? » superpose le département et la France entière sur
**deux axes**, et c'est la seule superposition honnête possible : un département compte
quelques milliers de ventes par trimestre (272 au maximum en Lozère) quand la France en
compte jusqu'à 269 000. Ramenées au même axe, la courbe départementale serait écrasée sur
zéro. Le facteur d'échelle aligne les MAXIMA — les deux courbes occupent alors la même
hauteur — et l'axe de droite annule ce facteur pour réafficher les vrais effectifs, si bien
que le lecteur n'a jamais de conversion à faire.

Ce qu'on compare est donc une **forme**, pas un niveau, et la légende comme le chapeau le
disent. La question à laquelle le graphique répond : ce marché suit-il le pays, ou fait-il
autre chose ?

**La série nationale vient de l'annuaire déjà chargé** (`departements.json`, `national`),
jamais du fichier départemental : elle y est stockée une seule fois pour tout le site, ce qui
laisse intact le budget de 10 Ko par département. Elle est calculée par
`q.dvf_national_median` sur les MÊMES données DVF, le MÊME filtre et la même maille
trimestrielle — comparer un département à une France construite autrement (l'IGEDD, par
exemple, qui est mensuel, en cumul 12 mois et couvre l'Alsace-Moselle) n'aurait rien voulu
dire. Corollaire : cette « France entière » exclut les quatre départements sans DVF.

Le graphique retombe sur l'ancien tracé à une seule courbe si la série nationale manque, et
les quatre départements non couverts ne l'affichent pas du tout — ils sont déjà derrière le
garde `couvert`.

### Ce que ces pages ne font pas, et ne doivent pas faire

- **Pas de prévision régionalisée.** Les taux, le chômage et les intentions d'achat sont
  nationaux : un modèle « local » publierait 101 fois la même courbe sous 101 titres.
- **Pas de filtre départemental sur les pages existantes.** Un particulier n'a que faire
  des permis SIT@DEL ou du solde d'opinion de l'enquête BLS.
- **Pas d'estimation de bien à l'adresse.** Autre métier, et hors de l'angle du site.
- **Le compteur « n/7 fichier(s) modifié(s) » reste à 7.** `build_departements` est
  volontairement hors de `_BUILDERS` : noyer ce compteur dans un total à 108 lui ferait
  perdre son pouvoir d'alerte, alors qu'un diff inattendu sur l'un des sept signale une
  divergence de calcul.

### Le module « Territoires » — ce qui doit rester vrai (2026-09-20)

Plan : `docs/plan-territoires.md` ; mesure : `docs/mesure-territoires-2026-09-20.md` ;
script : `mesure_territoires.py`. Origine : la vidéo de Xavier Delmas « la France va se
couper en deux » (mai 2026), deux indices composites INSEE croisés en quatre catégories de
départements. Le plan en gardait le mécanisme et en refusait la forme (indice pondéré à la
main, horizon 2040 infalsifiable), et posait une **porte mesurée AVANT toute page**.

**La porte a été MANQUÉE, et c'est le résultat le plus utile du module.** Deux axes
observés — part des résidences principales détenues par un ménage de 65 ans ou plus, et
attractivité migratoire — testés sur les prix DVF départementaux en deux fenêtres :
sur 2014-2019 les départements âgés et propriétaires sous-performent (ρ = −0,43), mais
**entièrement par effet de niveau** (ρ partiel à prix donné : +0,03 ; c'était l'époque où
les métropoles chères décrochaient) ; sur **2019-2025 le signe s'inverse** (ρ = +0,46, et
+0,46 à niveau donné ; ventes +0,44). Une relation qui change de signe d'un cycle à
l'autre n'est pas un signal structurel à quinze ans. Au passage : le **solde migratoire
net classe Paris dernier des 100** — il mesure la pénurie de logements, pas l'attrait.
D'où : **pas de page carte, pas de classement**, une cinquième entrée dans `REFUTATIONS`,
et les indicateurs publiés **en description seulement**.

**Ce qui existe :**

| Pièce | Où | À savoir |
|---|---|---|
| builder | `fetch_new_sources.build_territoires` | UNE source, l'API Melodi de l'INSEE (JSON, sans clé, `GEO=DEP` paginé) : RP 2012/2017/2023, série historique des populations légales, état civil 2008→, Filosofi 2023. Le comparateur de territoires (Parquet) est une compilation de ces mêmes jeux — vérifié octet pour octet — et insee.fr ne le date pas. Garde annuelle par le champ `modified` du catalogue de trois jeux témoins, empreinte VERSIONNÉE `territoires.lastmod.txt` ; 5 s à froid, 0,4 s sous garde. Format long, comptes entiers, **aucun ratio**. |
| dérivé | `DataManager.ensure_territoires` → `data/territoires.csv` | le SEUL endroit qui calcule les ratios et le solde migratoire apparent (période intercensitaire précédente ; 2007 approché par la moyenne 2008-2011). Mayotte, hors des jeux RP, n'a pas de ligne. |
| contrat | `housing_data.schema.TERRITOIRES` | code département comme DVF ; ratios bornés 0-100 ; colonnes limitées à 2023 (croisement âge × statut) ou à 97 départements (Filosofi) nullables. |
| requête | `queries.territoires_profil` | valeur, percentile (part des **autres** départements en dessous : `percent_rank` ne compte pas le département lui-même — « 100 % des 100 » serait faux d'une unité) et valeur France (ratio des sommes, ou département médian pour le solde et le niveau de vie). |
| surface | `[code].md`, section « Qui habite ici, et qui arrive ? » | sept cartes, pas de score ; les **quatre départements hors DVF** la reçoivent (le RP ne dépend pas de DVF) ; `postbuild` ajoute la phrase du recensement au chapeau statique, y compris pour eux — leur premier chiffre indexable. |
| sources | `sources_table.py`, deux lignes `freq: "A"` | datées par le **millésime** (colonne `Millesime`, pas `Date`) ; « millésime 2023 » plutôt que « 2023 », parce qu'un millésime agrège cinq années de collecte. |

**Trois choses à ne pas défaire :**

* **`load_or_generate_all()` appelle désormais `ensure_dvf()` ET `ensure_territoires()`**,
  et persiste les deux datasets par département dans l'entrepôt (`dvf` a gagné un Parquet
  validé qu'il n'avait pas). `ensure_dvf` n'avait AUCUN appelant — le défaut noté ici le
  2026-09-19. **`read_frames()` rend toujours six frames** ; `web_export.load_frames()`
  ajoute une clé `territoires` à son *dict* (pour le tableau des sources), jamais au tuple.
* **Le compteur reste à `n/7`.** Aucun JSON national n'a été ajouté (la page carte n'a pas
  été construite) ; `previsions.json` a bougé deux fois, par la nouvelle entrée de
  `REFUTATIONS` puis par son diagnostic `sources` — jamais par un chiffre.
* **Les valeurs France du profil vivent dans l'annuaire (`departements.json`,
  `profil_france`)**, pas dans les 101 fichiers : identiques partout, elles avaient amené
  le plus gros à 150 octets du budget de 10 Ko. Maximum après : 9,9 Ko.

**Si l'idée de la carte revient** : refaire tourner `python mesure_territoires.py` avec une
fenêtre de plus. La porte (plan §3.4) ne bouge pas.

## 2026-09-23 — DVF entre au tableau des sources d'À propos

La source qui alimente le plus de pages du site (101) n'avait pas de ligne dans le tableau
de provenance : elle n'apparaissait que dans le vocabulaire. Ligne ajoutée dans
`sources_table.SOURCES` (dataset `dvf`, colonnes `PrixM2Median` et `NbVentes`,
trimestriel), liée au jeu géolocalisé d'Etalab sur data.gouv.fr — celui que `build_dvf`
télécharge. `web_export.load_frames` relit `data/dvf.csv` à côté de `territoires` pour
dater la ligne ; le dernier point affiché est le dernier trimestre publié, tous
départements confondus (T4 2025 à l'ajout).
