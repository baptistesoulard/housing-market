# Front statique — PoC de migration hors Streamlit

Preuve de concept : porter le dashboard HousingMarket vers un **site statique moderne**
(publié sous la marque **Baromètre du Logement**, cf. `SITE` dans `site.config.js`)
(Observable Framework) déployable sur Cloudflare Pages / Netlify, **sans réécrire la
couche back-office Python**. Ce PoC couvre les **5 premiers onglets** de l'app.

## Principe

```
  [ INCHANGÉ — back-office Python ]                 [ NOUVEAU — couche produit ]
  data_manager / analysis / forecast  ──►  web_export.py  ──►  JSON statiques
  actualites / DataManager (Parquet→CSV)                             │
                                                                     ▼
                                              Observable Framework  ──►  dist/ (HTML/JS)
                                                                     ▼
                                              Cloudflare Pages / Netlify (CDN, ~0 €)
```

`web_export.py` **réutilise telles quelles** les fonctions de l'app (`analysis`,
`forecast`, `actualites`, `DataManager`) et recompute exactement le contenu des cinq
premiers onglets d'`app.py`, un JSON par page (`synthese`, `neuf`, `ancien`, `macro`,
`actualites`). La palette est centralisée dans `web/theme.json` (source unique lue par
`web/export/theme.py`, le CSS de la config et `components/theme.js` généré). Le front ne
fait que **lire** ces JSON : aucun Python n'est requis au build du site.

## Arborescence

```
web/
├── export/
│   ├── web_export.py            # agrégats Python → JSON statiques + theme.js
│   └── theme.py                 # charge web/theme.json, génère components/theme.js
├── observable/
│   ├── site.config.js           # IDENTITÉ : adresse publique, descriptions, NAV, logo
│   ├── observablehq.config.js   # RENDU : <head>, CSS partagé, pied de page
│   ├── scripts/
│   │   ├── postbuild.mjs        # lang, lien d'évitement, favicon, sitemap, robots
│   │   └── og-image.mjs         # régénère la vignette de partage (hors build)
│   ├── assets/og-image.png      # vignette 1200×630, committée
│   ├── package.json
│   └── src/
│       ├── index.md             # page d'accueil — RÉDIGÉE, pas de JSON
│       ├── a-propos.md          # méthode, sources, limites — rédigée aussi
│       ├── synthese.md          # page Synthèse (chips, cartes, graphique)
│       ├── previsions-passees.md  # archive : prévisions produites vs réalisé
│       ├── components/
│       │   ├── hm.js            # graphiques & helpers partagés
│       │   ├── period.js        # frise de période globale (barre latérale)
│       │   └── theme.js         # palette, généré depuis web/theme.json
│       └── data/synthese.json   # généré par web_export.py (commité pour le déploiement)
├── ../forecast_archive.py       # (racine) mémoire des prévisions : --record / --backfill
└── README.md
```

Deux fichiers de configuration, et la frontière compte : **`site.config.js` dit ce que le
site EST** (son adresse publique, le titre et la description de chaque page, l'ordre de la
navigation, le logo), **`observablehq.config.js` dit à quoi il RESSEMBLE**. Le premier est
aussi lu par `scripts/postbuild.mjs` et par `tests/test_web_seo.py` : une page ajoutée là
apparaît d'un coup dans la barre latérale, dans le sitemap et dans les tests.

## Coexistence avec l'app Streamlit

Ce PoC est **purement additif** : tout vit sous `web/` et n'importe le back-office Python
qu'en lecture. `app.py` (Streamlit) n'est pas modifié et reste pleinement fonctionnel —
l'objectif est justement de faire tourner **les deux en parallèle pour comparer**.

- **Streamlit (existant)** : `streamlit run app.py` → http://localhost:8501. Reste
  déployé là où il l'est déjà (Streamlit Community Cloud, etc.) : rien à changer.
- **Front statique (PoC)** : voir ci-dessous → http://localhost:3000.

Les deux configs sont dans `.claude/launch.json` (`streamlit-legacy` et `web-synthese`).

## Lancer en local

```bash
# 1) (Ré)générer les données du front depuis la pipeline Python
python web/export/web_export.py

# 2) Installer et lancer le serveur de dev (http://localhost:3000)
npm --prefix web/observable install
npm --prefix web/observable run dev

# (en parallèle, l'app Streamlit d'origine, pour comparer)
streamlit run app.py    # http://localhost:8501
```

## Look & feel

Typo et couleurs alignées sur ce que l'app Streamlit **rend** : corps de texte en Source
Sans 3 (la police que Streamlit embarque ; chargée ici via `globalStylesheets`), titres
dans la pile Segoe UI d'`app.py`, soulignés en rouge brique (#E64A19), texte anthracite
(#2D3748). Les graphiques affichent les valeurs **au survol** (infobulle « closest » type
Plotly, mois en français).

Deux règles de mise en page valent d'être connues avant de toucher au CSS :

- **Une seule largeur de colonne.** `--hm-measure` (64 rem) cadre `main` *et* la barre
  d'en-tête. Les plafonds par élément du thème `air` (640 px sur `p`/`h1-h6`, 600 px sur
  `ul`/`ol`) sont neutralisés : sans ça, la page a trois bords droits différents et les
  encadrés sont plus larges que le texte qu'ils contiennent. Ne pas remettre de
  `max-width` sur un bloc `.hm-*`.
- **La navigation vit dans la barre latérale**, rendue par Observable Framework à partir
  de `PAGES`. Elle ne s'épingle qu'au-delà de 1008 px ; en dessous elle se replie derrière
  un bouton, avec la frise de période qu'elle héberge. Un bandeau d'onglets en en-tête a
  été essayé puis retiré : redondant avec la barre latérale dès qu'elle est visible.

## Construire le site statique

```bash
npm --prefix web/observable run build   # → web/observable/dist/
```

`npm run build` enchaîne deux étapes : `observable build`, puis
`node scripts/postbuild.mjs` qui complète le HTML et ajoute les fichiers de racine (voir
« Être trouvable et partageable » plus bas). Le dossier `dist/` est un site 100 % statique,
servable tel quel.

## Déploiement Cloudflare Pages (recommandé)

Connecter le dépôt à Cloudflare Pages avec :

- **Build command** : `npm ci && npm run build`
- **Build output directory** : `dist`
- **Root directory** : `web/observable`

Et **une variable d'environnement** (Settings → Environment variables) :

- `HM_SITE_URL` = l'adresse publique, aujourd'hui `https://barometre-logement.com`
  (c'est aussi le repli codé dans `site.config.js`, donc un build sans la variable reste
  juste ; la variable sert à construire une préversion sous une autre adresse)

C'est elle qui écrit les URL canoniques, le sitemap et les balises Open Graph. Sans elle,
le repli de `site.config.js` est utilisé et le build l'annonce en clair (`postbuild:
ATTENTION — HM_SITE_URL n'est pas défini`). Une adresse fausse ne casse aucune page : elle
casse silencieusement l'aperçu au partage et le référencement, d'où l'avertissement.

Cloudflare ne construit que le front (**Node uniquement**, pas de Python). Le
`synthese.json` est produit et commité par la pipeline Python (voir ci-dessous), donc
chaque rafraîchissement des données déclenche automatiquement un rebuild du site.

## Le formulaire de contact (`functions/api/contact.js`)

La page « À propos » se termine par un formulaire — nom, courriel, sujet, message. C'est
le **seul bout de code serveur du site** : `web/observable/functions/api/contact.js`, une
*Cloudflare Pages Function*, que Cloudflare exécute automatiquement parce qu'elle se
trouve dans `functions/` à la racine du projet (`web/observable`, cf. ci-dessus). Le reste
de `dist/` est du HTML servi depuis un CDN, sans processus derrière.

Ce n'est **pas** l'API Flask de `api/`, qui expose des calculs et n'est pas hébergée. Les
deux n'ont rien à voir ; cette fonction ne calcule rien, elle valide quatre champs et
relaie vers un service d'envoi.

Trois variables d'environnement, à poser dans Settings → Environment variables :

| Variable | Rôle |
|---|---|
| `RESEND_API_KEY` | clé API [Resend](https://resend.com) (gratuit jusqu'à 3 000 messages/mois) — à marquer **Secret** |
| `CONTACT_TO` | l'adresse de destination — à marquer **Secret** |
| `CONTACT_FROM` | expéditeur, optionnel. Défaut `onboarding@resend.dev`, le domaine de bac à sable de Resend, qui n'autorise l'envoi **que vers l'adresse du compte**. Pour écrire ailleurs, vérifier un domaine chez Resend. |

**L'adresse de destination n'est pas dans le dépôt, et ne doit jamais y entrer.** Le dépôt
est public : une adresse personnelle écrite dans un fichier versionné est moissonnée par
les robots aussi sûrement que dans un `mailto:`. C'est la raison d'être de `CONTACT_TO` —
et aussi celle du formulaire, qui n'expose aucune adresse à la lecture de la page.

Sans `RESEND_API_KEY` ou `CONTACT_TO`, la route répond **503** et la page affiche « la
messagerie du site n'est pas joignable ». C'est délibéré : un formulaire qui remercie sans
rien envoyer est le pire des deux mondes.

**L'anti-spam n'appelle aucun service tiers** et n'impose aucune énigme au visiteur (un
test que l'humain doit résoudre écarte aussi des humains, lecteurs d'écran en tête). Deux
gardes : un champ *pot de miel* caché hors écran — jamais par `display:none`, que les
robots un peu sérieux savent sauter — et un délai minimal de trois secondes entre le
chargement de la page et l'envoi. La page transmet une **durée**, pas l'heure de son
chargement : comparer l'horloge du visiteur à celle du serveur jetterait en silence les
messages de toute machine mal réglée. Si du spam passe malgré ça, l'étage suivant est
Cloudflare Turnstile — même hébergeur, gratuit — à brancher avant l'envoi.

**En local, la route n'existe pas.** `npm run dev` ne sert que le site ; les Pages
Functions ne tournent que chez Cloudflare, ou sous `npx wrangler pages dev dist`. Un envoi
depuis la préversion affiche donc « l'envoi a échoué en route » — c'est attendu, pas une
régression. Pour vérifier la fonction sans navigateur, l'importer et l'appeler à la main :

```bash
node --input-type=module -e "import {onRequest} from './web/observable/functions/api/contact.js'; globalThis.fetch = async () => new Response('{}'); const r = await onRequest({request: new Request('https://x', {method:'POST', body: JSON.stringify({nom:'Test', email:'a@b.fr', message:'Un message assez long.', _t: 9000})}), env:{RESEND_API_KEY:'k', CONTACT_TO:'moi@example.com'}}); console.log(r.status, await r.text())"
```

## Branchement sur le refresh hebdomadaire

**Fait.** `.github/workflows/refresh-data.yml` régénère le JSON du front après le refresh
des sources et avant le commit :

```yaml
      - name: Régénérer les données du front web
        run: python web/export/web_export.py
```

`web/observable/src/data/` est inclus dans le `git add` du job, donc Cloudflare Pages
reconstruit le site à chaque publication de données. L'export est gardé par le contenu
(`generated_at` exclu de la comparaison) : un run sans nouveauté ne produit aucun diff et
donc aucun rebuild inutile.

## Toutes les pages sont statiques — deux ajoutent un calcul client

**Jusqu'au 2026-08-23**, Prévision et Données appelaient une API HTTP (`api/`) à chaque
question posée : le site statique ne fonctionnait pour elles qu'à condition qu'une
instance de l'API soit joignable quelque part, ce qui n'a jamais été le cas pour un
visiteur du site déployé. Ce n'est plus vrai : les **huit pages** lisent maintenant un
JSON statique produit par `web_export.py`, comme les six premières l'ont toujours fait.
Le septième export, `previsions.json`, appelle `api.engine` **au build**, pas au
runtime — voir `build_previsions` dans `web/export/web_export.py`.

Deux pages ajoutent par-dessus un calcul **côté client**, en JavaScript, jamais un appel
réseau :

- **Données & Sources** — la régression contre le fichier de ventes importé par
  l'utilisateur. Ce fichier ne quitte jamais le navigateur (voir plus bas) ; le calcul ne
  peut donc pas être précalculé côté serveur, il n'existe qu'après l'import.
- **Prévision & Scénarios** — le panneau à quatre curseurs continus. Précalculer un point
  par position de curseur est impossible (l'espace d'hypothèses ne s'énumère pas), mais le
  calcul lui-même est une formule fermée à huit multiplications
  (`computeScenario` dans `src/components/api.js`, port terme à terme de
  `forecast.scenario`) appliquée aux coefficients déjà exportés — aucune raison d'en faire
  un aller-retour réseau. La courbe de sensibilité aux décalages, elle, EST précalculée
  pour les trois prédicteurs : déplacer son curseur ne fait qu'une lecture.

Les deux implémentations dupliquées (JS ↔ Python) sont verrouillées par
`tests/test_web_js_parity.py` — voir « Vos ventes société ne quittent pas le
navigateur » plus bas pour la première, et le même fichier pour la seconde
(`test_scenario_matches_python`).

### L'API HTTP (`api/`) reste utilisable, mais n'est plus appelée par le site

Le retrait porte sur l'appel réseau depuis ces deux pages, pas sur `api/` lui-même :
`api/routes.py`, `api/engine.py` et `tests/test_api_contract.py` sont intacts et
continuent de tourner. `python -m api` reste la façon de lancer une instance locale, pour
qui veut explorer les mêmes routes sans passer par le front :

```
pip install flask          # seule dépendance ajoutée, optionnelle
python -m api              # http://127.0.0.1:8000/api/health
```

### L'architecture de l'API

```
web_export.py ──appel Python──► api/engine.py ──► queries.py / forecast.py
                                       ▲
                    (optionnel, local) │
                         navigateur ───┘ fetch() ──► api/routes.py
```

`api/engine.py` est la seule couche que les deux chemins partagent — c'est ce qui garantit
que le JSON publié et une instance locale de l'API calculeraient exactement les mêmes
chiffres. Deux règles à ne pas casser :

1. **`api/engine.py` n'importe pas Flask.** Le moteur reste exécutable et testable serveur
   éteint — c'est cet invariant qui permet à `web_export.py` de l'appeler directement, en
   important le module Python, sans passer par HTTP. Si un calcul se met à importer Flask,
   la couche est au mauvais endroit.
2. **Une route = une question métier**, pas une table. `/api/forecast/projection`, jamais
   `/api/table/macro?filter=…` — ce dernier reviendrait à réinventer SQL par-dessus HTTP
   et ferait migrer la logique métier dans le front.

Les routes sont couvertes par `tests/test_api_contract.py` (statut, forme, **format des
dates**, rejet des paramètres inconnus, et une course concurrente sur un vrai serveur).

### Vos ventes société ne quittent pas le navigateur

La page Données lit votre CSV **localement** : il n'est jamais téléversé, ni vers l'API ni
vers Cloudflare. Les régressions qui en dépendent tournent donc en JavaScript
(`bestLagFit` dans `src/components/api.js`). Comme la même question est répondue en Python
par `forecast.best_tx_to_monthly`, `tests/test_web_js_parity.py` vérifie que les deux
implémentations retiennent le même décalage et le même R² — sinon on aurait deux chiffres
et aucun arbitre.

## L'archive des prévisions

`data/forecast_archive.csv` (à la racine du dépôt, versionné) garde chaque prévision
produite. C'est la brique de crédibilité du site : une prévision publiée sans historique
n'est qu'une opinion.

**Deux natures de lignes**, séparées par la colonne `kind` et jamais agrégées ensemble :

| `kind` | Origine | Valeur de preuve |
|---|---|---|
| `archive` | Enregistrée le jour même par le job hebdomadaire, avant que la suite soit connue. | Une promesse tenue — personne ne peut la retoucher. |
| `retro` | Recalculée après coup, données tronquées au millésime visé. | La méthode tenait ; pas qu'on l'avait annoncé. |

Les lignes `retro` existent pour que la page ne soit pas vide au lancement. Leur limite est
énoncée sur la page : les transactions étant révisées, une rétro-simulation voit des
données un peu meilleures que celles de l'époque.

```bash
python forecast_archive.py --record      # la prévision du jour (le job hebdo le fait)
python forecast_archive.py --backfill    # rejoue les millésimes rétro-simulés (~3 s each)
python forecast_archive.py --report      # erreur par horizon, modèle contre naïve
```

**Le résultat mérite d'être connu** : sur les millésimes rétro-simulés, le modèle est
*moins bon* qu'une prévision naïve (« le marché reste où il est ») en deçà de 4 mois, puis
évite jusqu'à ~65 % de son erreur vers 8-11 mois. Un MAPE unique de 4,7 % aurait masqué le
premier fait ; la page `/previsions-passees` montre la zone où le modèle perd.

Le job hebdomadaire enregistre la prévision **entre** le rafraîchissement des sources et
l'export du front. Une prévision inchangée n'ajoute rien au fichier, donc une semaine sans
nouveauté ne produit aucun diff.

## Être trouvable et partageable

Un tableau de bord et un site public ne demandent pas la même chose. Ce qui a été ajouté
pour le second tient en trois idées.

**Le texte indexable vit sur deux pages écrites.** Les sept pages de données construisent
leur contenu dans le NAVIGATEUR à partir des JSON ; un robot qui n'exécute pas de
JavaScript n'y voit presque rien, et **aucun aperçu de partage n'exécute de JavaScript**.
`src/index.md` (accueil) et `src/a-propos.md` (méthode, sources, limites) sont donc
rédigées en markdown rendu au build. C'est le seul contenu du site que ces robots lisent —
d'où la règle : *ce qui compte sur ces deux pages reste statique*. Le bloc dynamique de
l'accueil (pastilles d'état, fraîcheur) est un aperçu ; s'il ne s'affiche pas, la page dit
toujours ce qu'elle a à dire.

**Le `<head>` est calculé par page.** `head` est une fonction dans
`observablehq.config.js` : le framework l'appelle avec le chemin de la page, elle y lit la
description déclarée dans `site.config.js` et en tire la meta description, l'URL canonique
et les balises Open Graph / Twitter. Sans ces dernières, **un lien collé sur LinkedIn
s'affiche en URL nue**, sans titre ni vignette : LinkedIn récupère la page depuis ses
propres serveurs et ne lit que le HTML servi. Leurs URL doivent être absolues, ce qui est
la raison d'être de `HM_SITE_URL`.

**Quatre choses qu'`observable build` ne pose pas** sont ajoutées par
`scripts/postbuild.mjs`, exécuté juste après lui par `npm run build` :

| Ajout | Pourquoi ce n'est pas dans le framework |
|---|---|
| `lang="fr"` sur `<html>` | Le framework écrit un `<html>` nu et n'offre aucun réglage. Sans lui, un lecteur d'écran prononce le français avec sa voix par défaut (critère WCAG 3.1.1). |
| Lien d'évitement | Sans lui, atteindre le contenu au clavier suppose de traverser toute la barre latérale, sur chaque page. |
| `favicon.svg` | Écrite plutôt que déclarée dans le `<head>` : le framework réécrit les `<link href>` en adresses hachées, alors qu'un robot attend `/favicon.svg` à la racine. |
| `sitemap.xml`, `robots.txt` | Absents du framework. C'est par le sitemap qu'un moteur découvre les pages qu'aucun lien externe ne pointe encore. |

Le script est **idempotent** (relancé sur un `dist/` déjà traité, il ne double rien) et
prend un répertoire en argument, ce qui permet aux tests de le faire tourner sur un
`dist/` jetable.

### Le sommaire de page

Chaque page de contenu affiche à droite la liste de ses sections (« Sur cette page »),
construite **au build** à partir de ses titres de niveau 2 — un titre posé par
``display(html`<h2>…`)`` n'y figure donc jamais. L'accueil s'en abstient : c'est une page
d'atterrissage, dont la section « Les huit pages » tient déjà lieu de navigation.

Il n'apparaît qu'à partir de **1320 px**, et non des 1216 px du framework : celui-ci
réserve 208 px de gouttière, ce qui faisait tomber les panneaux appariés de deux colonnes
à une sur un écran de portable ordinaire. Voir le commentaire dans
`observablehq.config.js` — deux règles sont à défaire, pas une.

### La vignette de partage

`assets/og-image.png` (1200×630) est **committée**, pas produite au build : Cloudflare ne
construit que du Node et la fabriquer demande un navigateur. Elle est régénérée à la
demande, quand l'identité change :

```bash
npm --prefix web/observable install --no-save playwright
npm --prefix web/observable run og-image
```

Le script relit `theme.json` et `site.config.js`, donc la vignette suit la charte au lieu
de dériver. Les polices ne sont pas embarquées : le rendu dépend de la sans-serif
installée sur la machine — sans conséquence puisque le PNG est versionné, mais c'est la
raison pour laquelle on ne la régénère pas à chaque build. `HM_CHROMIUM=/chemin/vers/chrome`
permet de viser un navigateur déjà présent plutôt que d'en télécharger un.

### Ce que les tests tiennent

`tests/test_web_seo.py` fait tourner ces trois modules JavaScript par Node (aucun `npm
install` requis, ils n'importent rien de `node_modules`) et vérifie ce qu'aucun rendu ne
montre : chaque page déclarée a bien un fichier, les descriptions sont uniques et de
longueur utilisable, chaque page indexable porte sa canonique et sa carte de partage, la
404 est désindexée, les URL de partage sont absolues, le sitemap liste exactement les pages
voulues, le post-traitement est idempotent, et la vignette est un vrai PNG aux bonnes
dimensions. Le test injecte une adresse de test différente du repli : c'est ce qui prouve
qu'aucune URL n'est écrite en dur.

## Les pages départementales

> **Remises en ligne le 2026-08-23**, après un retrait du 2026-08-21 pour intermittence
> observée sur le site déployé. La piste de reprise alors documentée (un data loader
> paramétré, pour charger par `FileAttachment` plutôt que par `fetch`) a été essayée et
> s'est révélée ne pas fonctionner : chaque page enregistrait côté client la même
> référence littérale, jamais résolue au département réel — vérifié dans le HTML
> construit. Le mécanisme retenu charge donc par `fetch()`, vers l'adresse stable copiée
> au build, avec la structure de cellules vue s'exécuter correctement en production
> avant le retrait. Voir `CLAUDE.md`, section « Les pages départementales », pour le
> détail des preuves et l'inconnue qui subsiste (l'intermittence d'origine n'a jamais
> été formellement expliquée, seulement débattue par élimination).

101 pages produites par une seule route paramétrée, `src/departement/[code].md`. Le site
passe de 10 à 111 pages, toutes dans le sitemap, chacune avec son titre et sa description.

### Reconstruire les données

Deux moitiés, deux commandes. La première tourne déjà dans le refresh hebdomadaire :

```
python fetch_new_sources.py          # dont build_dvf : fenêtre glissante 2021-2025
```

La seconde est une opération **ponctuelle**, hors CI, qui télécharge 1,1 Go depuis un
miroir de millésimes archivés pour reconstituer les années que DVF ne republie plus :

```
python dvf_backfill.py --download
```

Elle écrit `data_manual_input/dvf-historique-2014-2020.csv` (~0,3 Mo), qui est **commité** —
c'est la seule façon de garder le chiffre publié reproductible sans re-télécharger un Go.
Les fichiers bruts, eux, ne doivent jamais entrer dans le dépôt.

Puis, comme pour les autres pages :

```
python web/export/web_export.py      # écrit src/data/departements/*.json + l'index
npm --prefix web/observable run build
```

`web_export.py` compte les départements **à part** des sept JSON nationaux : la ligne
`0/7 fichier(s) modifié(s)` doit rester lisible, c'est un signal de régression.

### Pourquoi ces pages ne se chargent pas comme les autres

`FileAttachment` est résolu au build : le framework lit le nom du fichier dans le code
source pour savoir quoi copier dans `dist/`. Une page paramétrée construit ce nom à partir
de son paramètre de route — il n'y a rien à lire, donc rien n'est copié. Vérifié : la page
se construit et `dist/_file/data/departements/` reste vide.

`scripts/postbuild.mjs` copie donc les données à une adresse stable
(`/data/departements/<code>.json`) et la page les lit par `fetch()`. Il y réécrit aussi le
`<title>` et le `<h1>` de chaque page, que le framework tire du front-matter et du
markdown — uniques pour les 101 (le `<h1>` markdown reste volontairement générique et
statique, pour ne pas reproduire le défaut du « chapeau statique » ailleurs sur le site :
un titre interpolé ne rendrait qu'un `<h1>` vide tant que le JS n'a pas tourné).

**Conséquence** : en `npm run dev`, une page départementale s'affiche sans ses chiffres,
puisque la copie n'a lieu qu'au build. Vérifier sur `dist/`.

## Périmètre du PoC / suite

Les **5 premiers onglets** de l'app Streamlit sont portés, avec les mêmes sections, les
mêmes graphiques et les mêmes options de vue (cumul 12 / 6 mois, brut, moyennes mobiles,
légendes cliquables) :

- ✅ **Synthèse** — pastilles par pilier, à retenir, 3 blocs de cartes, fraîcheur,
  graphique croisé neuf/ancien en deux panneaux (niveaux + base 100 = moyenne 2015).
- ✅ **Marché du neuf** — SIT@DEL (courbes, comparaison mensuelle), individuel vs
  collectif, ECLN (encours & mises en vente, délai d'écoulement, acquéreurs, prix au m²).
- ✅ **Marché de l'ancien** — IGEDD, puis prix Notaires-INSEE, capacité d'emprunt et
  indice d'accessibilité, neuf vs ancien.

  Ces deux pages sont **jumelles** : elles ouvrent sur les trois mêmes sections, portant le
  même intitulé et dans le même ordre (chiffres clés, courbes d'évolution, comparaison
  mensuelle), puis chacune ajoute ce qui lui est propre. Chaque section du socle renvoie à
  sa jumelle d'en face. `tests/test_web_structure.py` verrouille ce parallèle — le build,
  lui, ne valide pas les fragments d'URL et laisserait passer une ancre morte.
- ✅ **Environnement & Financement** — confiance, taux, intentions, chômage, volumes de
  crédits, demande BLS, rénovation.
- ✅ **Actualités & Aides** — filtres, matrice d'impact, échéancier, fiches détaillées.

Une **huitième page de données** s'est ajoutée, sans équivalent dans l'app Streamlit :
**🎯 Prévisions passées**, l'archive du modèle confrontée au réalisé (voir plus bas).

À ces sept pages de données s'ajoutent **deux pages rédigées**, qui n'existent pas dans
l'app Streamlit et n'ont de sens que pour un site public : l'**accueil** (ce que le site
répond, pourquoi s'y fier, le plan des pages) et **À propos** (méthode, sources, limites,
qui écrit). L'accueil a pris la racine `/` ; la Synthèse est passée à `/synthese`.

### Parité des contrôles

- **Filtre de période** — une **frise à deux poignées dans la barre latérale**
  (`src/components/period.js`), montée sur **toutes** les pages, comme le curseur
  « Période (années) » de la barre latérale Streamlit. Son domaine vient de l'export
  Python (bloc `period` des 5 JSON, même union de datasets qu'`app.py`), donc il est
  identique d'un onglet à l'autre quelle que soit l'étendue des séries de la page.

  Le site étant un ensemble de pages HTML distinctes, changer d'onglet **recharge** la
  page : la position de la frise est donc persistée dans `localStorage`, ce qui lui donne
  le comportement d'un contrôle unique qui suit l'utilisateur — la barre latérale
  Streamlit, elle, survit aux changements d'onglet sans rien faire.

  Il ne rogne que l'affichage : cumuls glissants et moyennes mobiles sont calculés en
  amont sur l'historique complet, exactement comme `app.py` qui filtre après avoir
  calculé — une fenêtre étroite montre donc les mêmes valeurs, jamais des cumuls
  tronqués. Deux nuances par page :

  - *Marché du neuf*, *Marché de l'ancien*, *Environnement & Financement* : tous les
    graphiques suivent la fenêtre ; les cartes « Chiffres clés » restent au dernier mois
    disponible, comme dans Streamlit.
  - *Synthèse* : seul le graphique croisé neuf/ancien suit la fenêtre. Pastilles, « à
    retenir » et cartes restent indépendants du curseur, exactement comme `app.py` qui
    les calcule sur les frames non filtrées.
  - *Actualités & Aides* : la frise est affichée pour rester présente partout, mais la
    page ne la consomme pas (l'échéancier porte sur des mesures à venir, au-delà du
    domaine du curseur). Une mention « Sans effet sur cet onglet » le dit sous le
    contrôle.
- **Segmentation par type de logement** — sur *Marché du neuf*, les quatre types SIT@DEL
  se cochent/décochent et rejouent la courbe **et** les KPI, comme le panneau repliable
  d'`app.py` (aucun type coché = tous, même convention que le multiselect vide).
  L'export publie `by_type` (séries par type, en colonnaire : le front somme les types
  retenus) et `kpis_by_type` (les KPI des 15 sous-ensembles, pré-calculés par les mêmes
  fonctions `analysis` que le reste de l'app — aucune statistique n'est réimplémentée en
  JavaScript).

### Écart connu avec Streamlit

- **FR uniquement.** L'app Streamlit est bilingue (sélecteur FR/EN) ; le front ne sert
  que le français. Les libellés venant de l'export Python, bilinguiser suppose de
  produire un JSON par langue.

### Suite

- ✅ **Les 7 onglets sont portés.** Prévision & Scénarios et Données & Sources ont
  rejoint le site le 2026-08-20 par un chemin différent des cinq premiers (l'API HTTP),
  puis sont passées au **même chemin** que les six autres pages le 2026-08-23 — voir
  « Toutes les pages sont statiques » ci-dessous. Aucune des huit pages de données
  n'a plus besoin d'un serveur pour fonctionner.
- ✅ **Le site est publiable.** Accueil et À propos rédigés, métadonnées de partage et
  de référencement, sitemap, favicon, langue du document et lien d'évitement — voir
  « Être trouvable et partageable ».
- ⏭️ Bilingue FR/EN pour les deux nouvelles pages (les cinq premières le sont déjà via
  l'export Python).
