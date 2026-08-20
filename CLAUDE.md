# Orientation — refactors en cours

Ce fichier existe parce que le plan de refactor n'avait jamais été écrit : il ne vivait
que dans le fil de conversation qui a produit les premières phases. Une session suivante
devait le reconstituer par archéologie git, et pouvait se tromper d'axe. Tenir ce fichier
à jour fait partie du travail.

## Deux axes de refactor à ne pas confondre

Le dépôt porte **deux** chantiers autour de DuckDB/Parquet. Ils ont des noms proches et
touchent les mêmes fichiers. Les confondre est l'erreur par défaut.

| | Axe **stockage** | Axe **compute** |
|---|---|---|
| Question | *où* les données sont persistées | *qui* calcule les agrégations |
| Livrable | `housing_data/` — contrats pandera + entrepôt Parquet, vue SQL par dataset | `queries.py` — DuckDB comme moteur d'agrégation unique |
| État | **fusionné dans `main`** — socle, puis bascule de la LECTURE par la PR #3 | **fusionné dans `main`** — PR #2, phases 0-4 |
| Vocabulaire des commits | messages libres | `refactor(compute) phase N:` |

L'axe compute **s'appuie** sur l'axe stockage : `queries.open_warehouse()` ouvre une
connexion sur les Parquet que `DataManager` a écrits. Mais leurs plans de phases sont
distincts. « Phase 1 » sans qualificatif désigne l'axe compute.

## Axe compute — plan et état

Objectif : DuckDB est la porte d'entrée **unique** des agrégations pour les trois
surfaces (`app.py`, `web/export/web_export.py`, `report.py`), pour qu'elles affichent les
mêmes chiffres par construction.

| Phase | Portée | Commit | État |
|---|---|---|---|
| 0 | `queries.py` + `tests/test_queries_parity.py`, additif, aucune surface modifiée | `dd428a3` | ✅ |
| 1 | `web_export.py` sur la couche SQL | `f30d02d` | ✅ |
| — | correctif : le workflow hebdo n'installait pas les libs devenues obligatoires en phase 1 | `ab2bc8c` | ✅ |
| 2 | `report.py` et `app.py` (onglets d'affichage) | `6e58bf8` | ✅ |
| 3 | `app.py` (onglets interactifs), `category_col`, `macro_rolling` | `0ddca27` | ✅ |
| 4 | série pilote de la prévision (`transactions_run_rate`) | `cceab61` | ✅ |

**Il ne reste rien de planifié sur cet axe.** Ce qui subsiste en pandas sur le chemin
d'exécution y reste délibérément (voir invariants).

Un troisième chantier, côté front web, est lui aussi **terminé** : les 7 onglets sont
portés vers Observable. Les cinq premiers lisent un JSON statique produit par
`web_export.py` ; les deux derniers (Prévision, Données) interrogent l'API HTTP `api/`.
Ce n'est pas du compute — `api/` ne recalcule rien, il expose `queries.py` et
`forecast.py` en JSON. Voir « L'API HTTP » plus bas et `web/README.md`.

Un quatrième, **terminé** lui aussi : faire du front un **site publiable**. Deux pages
rédigées se sont ajoutées aux sept pages de données (accueil et À propos), avec les
métadonnées de partage et de référencement qui vont avec. Voir « Le site public » plus bas.

## Axe stockage — plan et état

Objectif : le Parquet est le chemin de lecture au runtime, les CSV restent la copie
versionnée et diffable — et le repli.

| Étape | Portée | État |
|---|---|---|
| socle | `housing_data/` : contrats pandera + écriture Parquet à côté des CSV | ✅ dans `main` |
| bascule | `read_frames()` lit le Parquet ; garde de fraîcheur ; `signature()` ; diagnostics | ✅ PR #3, fusionnée le 2026-08-19 |

**Pourquoi la bascule compte** : avant elle, l'app lisait les mêmes données par DEUX
chemins — DuckDB sur les Parquet pour les agrégations, pandas sur les CSV pour tout le
reste (options de widgets, entrées macro des modèles). Ils ne s'accordaient que parce que
`load_or_generate_all()` réécrivait les 7 Parquet à chaque démarrage.

**La garde de fraîcheur est le point porteur** : `warehouse.resolve()` ne retient un
Parquet que s'il est au moins aussi récent que son CSV. Les CSV sont versionnés, les
Parquet gitignorés — donc un `git pull` apportant des CSV rafraîchis laisse mécaniquement
le Parquet local en retard. Les vues SQL appliquent la même règle, donc DuckDB et
`read_dataset()` ne peuvent pas diverger.

## Invariants à ne pas casser

**`analysis.py` et `forecast.build_target` ne sont pas du code mort.** Les agrégations
d'`analysis.py` (`aggregate_sitadel`, `aggregate_ventes_ancien`, `calculate_rolling_12m`,
`calculate_rolling`) et `forecast.build_target` ne sont plus appelées au runtime, mais
elles sont l'**implémentation de référence** contre laquelle `tests/test_queries_parity.py`
compare chaque requête SQL. Les supprimer supprime le filet de sécurité de toute la
migration. En revanche les helpers de *post*-agrégation d'`analysis.py` (`calculate_kpis`,
`momentum_metrics`, `build_market_commentary`) sont, eux, bel et bien appelés.

**La couche SQL n'est plus optionnelle.** `app.py`, `web_export.py` et `report.py`
importent `queries` au niveau module → `housing_data` → `pandera`/`pyarrow`/`duckdb`. Tout
environnement qui exécute une de ces trois surfaces doit les installer, y compris le
runner GitHub Actions. L'import gardé de `data_manager.py` ne couvre plus que
`fetch_new_sources.py`.

**Une requête = un curseur, jamais la connexion partagée.** `app.py` met sa connexion
DuckDB en cache avec `@st.cache_resource` : UN seul objet connexion sert toutes les
sessions Streamlit, qui tournent chacune dans son thread. Un `DuckDBPyConnection` porte le
résultat de son dernier `execute()`, donc deux threads simultanés se volent leur jeu de
résultats — et le symptôme n'est pas une erreur SQL mais un DataFrame **bien formé et
faux**, celui de la requête de l'autre session (`KeyError: 'Transactions'` en production,
jamais en local où il n'y a qu'une session). Tout `execute()` de `queries.py` passe donc
par `_cur(con)` → `con.cursor()`, connexion indépendante sur la même base en mémoire (les
vues restent visibles, l'état de résultat non). `tests/test_queries_concurrency.py` rejoue
la course. Ne jamais réintroduire un `con.execute(...)` direct sur le chemin Streamlit.

**Ce qui reste en pandas y reste exprès.** Un `grep "groupby\|rolling\|resample"` sur le
chemin d'exécution ne doit plus renvoyer que ces trois cas, et aucun n'est un oubli.
`app.py` n'en a plus aucun : le dernier (le lissage 12 mois de l'atelier Time-Lag, en
`min_periods=1`) est parti avec l'onglet Atelier — la section qui l'a remplacé prend son
cumul 12 mois par `q.monthly(..., windows=(12,))`, donc en SQL.

| Emplacement | Pourquoi |
|---|---|
| `forecast.py` — `build_target` | N'est plus appelée : implémentation de **référence** des tests de parité (voir invariant ci-dessus). |
| `forecast.py` — `tx12.resample("QS").mean()` | Transformation de la série pilote *par le modèle*, pas une agrégation de dataset. |
| `forecast.py` — les deux `groupby("Date").sum()` de `fit_tx_to_monthly` / `fit_sales_two_factor` | Repli défensif contre des dates dupliquées, sur une frame passée en paramètre. Depuis la phase 3 les appelants fournissent déjà une série unique par date : c'est un no-op qu'on garde parce que ces helpers sont génériques. |

`export.py` fait aussi des `groupby`/`resample`, mais c'est un formateur SAP IBP agnostique
du dataset : il opère sur ce qu'on lui donne, il n'a pas de source à interroger.

**Ne pas régénérer les JSON du front sans vérifier.** `python web/export/web_export.py`
doit annoncer `0/5 fichier(s) modifié(s)`. Un diff inattendu signale une divergence de
calcul, pas du bruit — depuis que les agrégations sont en SQL, la sortie ne dépend plus de
la version de pandas/numpy.

## L'API HTTP (`api/`) — ce qui doit rester vrai

Trois couches, chacune ne connaissant que la suivante :

```
navigateur ──fetch()──► api/routes.py ──► api/engine.py ──► queries.py / forecast.py
```

**`api/engine.py` n'importe pas Flask, et ne doit jamais l'importer.** C'est l'invariant
central : le moteur reste exécutable et testable serveur éteint
(`python -c "from api import engine; print(engine.rate_model()['r2'])"`). Seul
`api/routes.py` connaît HTTP. Un calcul qui se met à importer Flask est un calcul rangé au
mauvais endroit.

**Aucune logique métier dans `routes.py`.** Une route lit des paramètres, appelle le
moteur, sérialise. Rien d'autre.

**Une route = une question métier, pas une table.** `/api/forecast/projection` est bon ;
`/api/table/macro?filter=…` réinventerait SQL par-dessus HTTP et déplacerait la logique
dans le front.

**Le format des dates est figé à `YYYY-MM-DD`**, produit par `engine._iso` et verrouillé
par `tests/test_api_contract.py`. Une divergence (`2025-03` d'un côté, `2025-03-01` de
l'autre) ne lève pas : la requête réussit et la jointure renvoie zéro ligne.

**Pas de `NaN` dans les réponses.** `json.dumps` en produit par défaut, ce n'est pas du
JSON valide et `JSON.parse` lève côté navigateur — une seule valeur manquante casserait
la page entière sans erreur serveur. `engine._num` convertit en `null` ; un test le vérifie
sur toutes les routes.

**La concurrence est déjà traitée mais reste fragile.** Un serveur HTTP sert plusieurs
requêtes en parallèle : la règle « une requête = un curseur » de `queries.py` (voir plus
haut) est ce qui empêche deux appels simultanés de se voler leur jeu de résultats.
`tests/test_api_contract.py::test_concurrent_requests_do_not_swap_payloads` rejoue la
course sur un vrai serveur.

**Flask est optionnel.** Ni `app.py`, ni `report.py`, ni `web_export.py` n'en dépendent.
Les deux pages web qui appellent l'API affichent un encart quand elle ne répond pas, donc
le site statique reste déployable seul.

**Les ventes société ne passent PAS par l'API.** Décision produit : le CSV est lu dans le
navigateur et n'est jamais téléversé. Conséquence directe — la régression qui en dépend
existe en double, en Python (`forecast.best_tx_to_monthly`) et en JS (`bestLagFit` dans
`web/observable/src/components/api.js`). `tests/test_web_js_parity.py` compare les deux sur
les mêmes données : même décalage retenu, même R². Ne pas laisser diverger.

**Les pages du front n'importent jamais `npm:` directement** : elles passent par
`src/components/hm.js`, qui réexporte `Plot`, `d3` et `csvParse`. Une seule façon de
charger une bibliothèque.

## Onglets retirés (2026-08-20) — ne pas les restaurer par réflexe

L'app est passée de **8 à 7 onglets**. Deux surfaces ont été supprimées ; les deux
suppressions sont des décisions, pas des oublis.

**« 🔬 Atelier exploratoire » (Time-Lag + Composite) — supprimé.** Il cherchait un
décalage en maximisant le **r de Pearson sur des niveaux lissés**, alors que l'onglet
Prévision répond déjà à la même question par une recherche en grille sur le **R²**,
menée sur la seule fenêtre d'entraînement (`fc.search_tx_lags`, `split=_FORECAST_SPLIT`)
pour ne pas contaminer le backtest. Deux méthodes rivales donnaient deux nombres sans
moyen d'arbitrer — et la plus faible des deux devait afficher son propre avertissement
sur l'auto-corrélation des séries lissées. Le sous-onglet Composite, lui, produisait un
signal pondéré à la main **sans backtest ni score** : invérifiable par construction.

Ce qui en a été **sauvé**, replié dans « 📡 Prévision & Scénarios » :

| Rescapé | Où | Pourquoi il n'était pas redondant |
|---|---|---|
| Graphe d'alignement + curseur de décalage | expander « Vérifier les décalages retenus », section 2 ter | Rend la recherche en grille **auditable** : on déplace un décalage, le modèle est réestimé (`fc.fit_tx_model`) et le R² affiché bouge. Noté avec le critère **du modèle**, pas avec un r concurrent. |
| Permis SIT@DEL → ventes société | section 4, second bloc `with tab_forecast:` | L'étage 2 explique les transactions par taux + intentions + chômage : **SIT@DEL n'y est pas**. Pour du second-œuvre, un permis déposé est une commande à venir — lien que le modèle ne voit pas. Mesuré par `fc.best_tx_to_monthly`, le même estimateur que l'élasticité transactions→ventes, donc les deux drivers sont comparables. |

Sont partis sans remplacement : la recherche de décalage par max-r, la branche « Indicateur
Macro » (ses indicateurs *sont* les prédicteurs du modèle), le benchmark sur ventes
synthétiques (circulaire — le code appelait `synthetic_circularity_warning()`), et tout le
Composite.

**Export SAP IBP — retiré du câblage.** Besoin suspendu côté métier. Le dernier onglet
n'est plus que « ⚙️ Données & Sources » (consultation + import des ventes société) et n'a
plus de sous-onglets. **`export.py` n'est pas supprimé** : le module reste intact pour
pouvoir être rebranché sans réécriture — mais il n'est désormais importé par *rien* et
n'a pas de test, donc rien ne le protège d'une régression silencieuse. Le rebrancher
suppose de le retester.

Les clés de traduction devenues orphelines *par ce retrait* ont été supprimées de
`translations.py` (71 clés × 2 langues). Une dizaine d'autres clés étaient déjà orphelines
avant (reliquat du code géo/carte) et ont été laissées en place, hors périmètre.

**Onglet « Données & Sources » réduit à l'import des ventes société (même jour).** Y ont
aussi été retirés : le navigateur « Données Actuelles du Système » (selectbox + aperçu +
modèle CSV), le téléversement qui écrasait un dataset par CSV, la « Réinitialisation
Générale », et le bouton de reconstruction des ventes anciennes depuis le fichier IGEDD.
Motif : l'acquisition est scriptée de bout en bout (`fetch_new_sources.py` + workflow
hebdo), donc l'écrasement en application était un second chemin de mutation des mêmes
fichiers, non versionné et non tracé.

Deux conséquences à connaître :

- **Le bouton IGEDD ne manque pas.** `load_or_generate_all()` appelle déjà
  `ensure_ventes_ancien()` au démarrage, et celle-ci est mtime-aware : la reconstruction
  se déclenche toute seule dès que le fichier IGEDD source est plus récent que
  `data/ventes_ancien.csv`. Le bouton ne faisait que forcer ce que le démarrage fait.
- **⚠️ On perd le panneau de diagnostic de l'entrepôt typé.** C'était le seul endroit de
  l'interface où l'on voyait `warehouse_status` (contrat pandera respecté ou non, par
  dataset) et `dataset_sources()` (« lu en Parquet » vs « lu en CSV (repli) »). Or la
  garde de fraîcheur est précisément le mécanisme porteur de l'axe stockage : un `git
  pull` qui apporte des CSV rafraîchis fait mécaniquement basculer des datasets en repli
  CSV, et **plus rien ne le signale à l'écran**. Les deux méthodes de `DataManager`
  existent toujours ; si le sujet ressort, la remettre sous forme d'un badge compact
  suffit — il n'est pas nécessaire de restaurer tout l'onglet.

`dm.update_with_custom_csv()` n'est désormais appelée par rien : elle devient du code mort
dans `data_manager.py` (elle figurait au backlog « brancher update_with_custom_csv sur les
contrats/logging » — ce backlog est caduc tant que l'import CSV ad hoc n'est pas rétabli).
21 clés de traduction supplémentaires ont été supprimées. La fonction
`synthetic_circularity_warning()` d'`app.py`, devenue morte avec le benchmark synthétique
du Time-Lag, a été supprimée elle aussi.

## Le site public — ce qui doit rester vrai

Le front est passé de tableau de bord déployé à **site destiné à être partagé** (LinkedIn
et consorts). Dix pages : `/` est désormais une page d'accueil RÉDIGÉE, la Synthèse a
glissé à `/synthese`, `/a-propos` porte méthode, sources et limites, et
`/previsions-passees` publie l'archive des prévisions (voir la section suivante).

**`site.config.js` est la source unique d'identité.** Adresse publique, titre et
description de chaque page, ordre de la navigation, logo. Il est lu par le `<head>`
(`observablehq.config.js`), par `scripts/postbuild.mjs` et par `tests/test_web_seo.py` :
ajouter une page là la fait apparaître d'un coup dans la barre latérale, dans le sitemap et
dans les tests. `observablehq.config.js` ne porte plus que le RENDU — ne pas y redéclarer
de navigation.

**L'accueil et À propos doivent rester en HTML rendu au build.** C'est leur seule raison
d'être : les sept pages de données construisent leur contenu dans le navigateur à partir
des JSON, et **aucun aperçu de partage n'exécute de JavaScript** (LinkedIn, Slack et
WhatsApp récupèrent la page depuis leurs serveurs). Ces deux pages sont donc le seul texte
du site que ces robots lisent. Le bloc dynamique de l'accueil (pastilles, fraîcheur) est un
aperçu : s'il ne s'affiche pas, la page doit encore dire ce qu'elle a à dire. Déplacer son
propos dans un bloc ```js le rendrait invisible là où il compte.

**Aucune URL d'hébergement en dur.** Les balises Open Graph et l'URL canonique exigent des
adresses ABSOLUES ; elles viennent de `HM_SITE_URL` (variable d'environnement Cloudflare
Pages), avec un repli `*.pages.dev` que le build signale en clair. Un test injecte une
adresse différente du repli et vérifie que tout suit — c'est ce qui empêche une URL de se
figer dans le code. Une adresse fausse ne casse aucune page : elle casse silencieusement
l'aperçu au partage et le référencement.

**`scripts/postbuild.mjs` pose ce qu'`observable build` ne pose pas** : `lang="fr"` sur un
`<html>` que le framework écrit NU (WCAG 3.1.1, aucun réglage offert), un lien d'évitement,
`favicon.svg`, `sitemap.xml` et `robots.txt`. Il est **idempotent** et prend son répertoire
de sortie en argument (les tests le lancent sur un `dist/` jetable). Réécrire du HTML après
coup n'est pas élégant : c'est la seule prise disponible tant que le framework n'expose pas
ces réglages.

**La vignette `assets/og-image.png` est committée, pas construite.** Cloudflare ne
construit que du Node et la produire demande un navigateur ; `npm run og-image` la
régénère à la main (Playwright, hors dépendances du site). Elle vit hors de `src/` parce
que les fichiers que le framework copie reçoivent un nom haché, incompatible avec l'URL
absolue qu'annonce `og:image`.

**Une légende cliquable est un `<button aria-pressed>`, jamais un `<span onclick>`.** Le
barré et l'opacité ne disent l'état qu'à ceux qui les voient ; un `span` n'est atteignable
ni au clavier ni au lecteur d'écran. Les deux légendes du site (`components/hm.js` et
`synthese.md`) sont des boutons dont le CSS neutralise l'apparence — le rendu n'a pas
changé.

**L'encart « API injoignable » s'adresse d'abord à un visiteur, pas à un développeur.**
Le site est public : tant qu'aucune instance n'est désignée, c'est ce que voit tout le
monde sur Prévision et Données. Le mode d'emploi `python -m api` est rangé dans un repli,
sous une explication en français courant et des renvois vers les pages qui fonctionnent.
À noter : un site servi en HTTPS ne peut pas appeler le `http://127.0.0.1:8000` de repli
(contenu mixte), donc **ces deux pages resteront en encart pour un visiteur externe tant
que l'API n'est pas hébergée**.

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
bon* qu'elle en deçà de 4 mois (`skill` négatif aux horizons 1-3) et évite ~65 % de son
erreur vers 8-11 mois. Publier un MAPE unique de 4,7 % masquerait le premier fait. La page
montre la zone où le modèle perd — c'est le propos, pas un aveu.

**La garde de contenu évite une archive qui gonfle pour rien.** Le job hebdomadaire tourne
même sans nouveauté ; `append_if_new` compare la prévision aux lignes du dernier
enregistrement DE SON TYPE et n'ajoute rien si elle est identique. D'où l'arrondi à l'unité
des transactions : sans lui, un bruit de calcul créerait une ligne par semaine.

**L'ordre des étapes du workflow compte.** `forecast_archive.py --record` tourne APRÈS
`fetch_new_sources.py` et AVANT `web_export.py`, qui lit l'archive pour construire sa page.
Le script ouvre l'entrepôt avec `refresh=True`, donc il reconstruit lui-même CSV dérivés et
Parquet — il ne dépend pas de l'export pour ça. Un modèle non calibrable n'interrompt pas le
job : on perdrait une publication de données pour une ligne d'archive.

**Le front compte maintenant SIX JSON**, pas cinq : `python web/export/web_export.py` doit
annoncer `0/6 fichier(s) modifié(s)` quand rien n'a bougé. `archive.json` change, lui, dès
qu'une prévision est enregistrée — c'est normal, contrairement aux cinq autres.

**Une interpolation `${…}` ne fonctionne que dans le CONTENU d'un élément.** Dans un
attribut HTML brut (`style=${…}`) elle reste affichée telle quelle, et dans un `<tbody>`
écrit en HTML brut le marqueur du framework est éjecté hors de la table par l'analyseur.
Légendes et tableaux se montent donc en JS (`display(html\`…\`)`). Les deux cas ont été
rencontrés en écrivant `previsions-passees.md`.

## Les pages départementales — ce qui doit rester vrai

101 pages générées par UNE route paramétrée (`web/observable/src/departement/[code].md`),
qui font passer le site de 10 à 111 pages. Elles s'adressent à un particulier et répondent
à trois questions, pas davantage : combien coûte le m² ici, combien de ventes s'y font, et
combien de m² une capacité d'emprunt y achète.

### D'où viennent les données

**Deux sources, parce que DVF ne publie qu'une fenêtre glissante de cinq ans.** Vérifié en
interrogeant la source : `files.data.gouv.fr/geo-dvf/` ne porte qu'un seul millésime
(`2025-12`, couvrant 2021-2025) et aucun millésime archivé — il n'y a rien à empiler.

| Période | Source | Rafraîchie par | Commitée |
|---|---|---|---|
| 2021-2025 | `files.data.gouv.fr/geo-dvf/latest/` (officielle, LOv2) | `fetch_new_sources.build_dvf`, chaque semaine | `data_manual_input/dvf-recent.csv` |
| 2014-2020 | miroir `data.cquest.org/dgfip_dvf/` (millésimes archivés) | `dvf_backfill.py`, à la main, **jamais en CI** | `data_manual_input/dvf-historique-2014-2020.csv` |

`DataManager.ensure_dvf` recolle les deux en `data/dvf.csv` (la moitié récente l'emporte en
cas de recouvrement), et le contrat pandera `dvf` valide le tout.

**Le raccord 2020/2021 ne crée pas de marche**, et ce n'est pas une supposition. Le format
brut n'a pas d'`id_mutation` ; la clé reconstruite ne reproduit pas la partition
officielle, mais l'écart mesuré sur la médiane PUBLIÉE est de +0,00 % (Lozère) et +0,15 %
(Paris), mesuré sur des données où les deux sources coexistent. Sur les 97 départements, la
soudure donne −0,60 % d'écart médian, contre +0,78 % pour un passage de trimestre
ordinaire.

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

**Conséquence pour `npm run dev`** : le serveur de développement ne sert PAS
`/data/departements/` (la copie est faite par `postbuild`, donc au build seulement). Une
page départementale ouverte en préversion affichera sa structure sans ses chiffres. Se
vérifier sur `dist/`.

### Ce que ces pages ne font pas, et ne doivent pas faire

- **Pas de prévision régionalisée.** Les taux, le chômage et les intentions d'achat sont
  nationaux : un modèle « local » publierait 101 fois la même courbe sous 101 titres.
- **Pas de filtre départemental sur les pages existantes.** Un particulier n'a que faire
  des permis SIT@DEL ou du solde d'opinion de l'enquête BLS.
- **Pas d'estimation de bien à l'adresse.** Autre métier, et hors de l'angle du site.
- **Le compteur « n/6 fichier(s) modifié(s) » reste à 6.** `build_departements` est
  volontairement hors de `_BUILDERS` : noyer ce compteur dans un total à 107 lui ferait
  perdre son pouvoir d'alerte, alors qu'un diff inattendu sur l'un des six signale une
  divergence de calcul.

## Vérifier la parité

Trois recettes, par ordre de coût croissant. Les tests unitaires seuls ne suffisent pas :
ils ne prouvent rien sur le câblage des surfaces.

**1. Tests de parité** — chaque requête SQL contre son équivalent pandas sur les données
réelles. Nécessite un entrepôt construit (`python -c "from data_manager import
DataManager; DataManager().load_or_generate_all()"`), sinon le module se skippe.

```
python -m pytest tests/ -q          # 149 collectés ; 1 skip légitime si company_sales
                                    # est vide. Les tests d'API se skippent sans Flask,
                                    # ceux de parité JS et de référencement sans Node.
```

**2. Rapport PDF, comparaison d'octets** — la plus forte : couvre les graphiques, les KPI
et le commentaire d'un coup. Générer le PDF avec l'ancienne version de `report.py`
(`git show <ref>:report.py`) et la nouvelle, puis comparer après avoir retiré
`/CreationDate`, `/ModDate` et `/ID`, que reportlab régénère à chaque appel.

**3. `app.py` sous plusieurs états de widgets** — indispensable pour les onglets
interactifs : l'état par défaut n'exerce pas les branches conditionnelles. Comparer un
worktree de référence et l'arbre courant :

```python
from streamlit.testing.v1 import AppTest
at = AppTest.from_file(f"{racine}/app.py", default_timeout=1200); at.run()
snap = lambda: {"m": [[x.label, x.value, x.delta] for x in at.metric],
                "md": [x.value for x in at.markdown],
                "cap": [x.value for x in at.caption],
                "tbl": [d.value.to_json() for d in at.dataframe]}
etats = {"defaut": snap()}
at.sidebar.slider[0].set_value((2015, 2020)); at.run(); etats["slicer"] = snap()
at.sidebar.slider[0].set_value((2000, 2026)); at.run()
for sb in at.selectbox:            # bascule chaque liste sur sa DERNIÈRE option :
    if sb.options and len(sb.options) > 1:   # c'est ce qui exerce les branches
        sb.set_value(sb.options[-1])         # Product / Company / Serie
at.run(); etats["selects"] = snap()
```

Streamlit exécute le corps de **tous** les onglets, pas seulement celui affiché — un seul
`run()` couvre donc les 12 onglets pour un état de widgets donné.

## État des branches

| Branche | Devant `main` | Note |
|---|---|---|
| `main` | — | porte les DEUX axes en entier : compute (phases 0-4) et stockage (socle + bascule) |
| `refactor/duckdb-storage` | 0 | axe stockage, fusionné par la PR #3 |
| `refactor/duckdb-engine` | 0 | axe compute, fusionné par la PR #2 |
| `fix/web-lisibilite` | 0 | correctifs de lisibilité du front web, fusionnés |
| `claude/code-audit-ocw25x` | 0 | reliquat, rien que `main` n'ait déjà |
| `claude/website-seo-accessibility-alr8mw` | +1 | site public : accueil rédigée, page À propos, métadonnées de partage/référencement, corrections d'accessibilité (voir « Le site public ») |
| `refactor/fusion-timelag-previsions` | 0 | fusion Time-Lag → Prévision, retrait Atelier + export SAP IBP (voir « Onglets retirés ») ; fusionnée dans `main` en fast-forward le 2026-08-20 |

Les quatre branches ci-dessus sont **entièrement contenues dans `main`** (`git merge-base
--is-ancestor` vérifié) : leurs copies locales ont été supprimées, il ne reste que les
copies distantes, à supprimer d'un `git push origin --delete`. `claude/duckdb-parquet-
refactor-p2-tvs0b2`, qui figurait ici, n'existe plus ni en local ni sur le distant.
