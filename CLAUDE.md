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
portés vers Observable, et depuis le 2026-08-23 les **7** lisent un JSON statique produit
par `web_export.py` — Prévision et Données appelaient l'API HTTP `api/` jusque-là,
elles lisent maintenant `previsions.json` (Prévision) ou dérivent leurs séries de
`ancien.json`/`neuf.json` déjà publiés (Données). `api/` reste debout et testé
(`python -m api`), mais n'est plus appelée par aucune page du site — seulement par
`web_export.py`, en import Python direct. Voir « L'API HTTP » plus bas et
`web/README.md`.

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
`load_or_generate_all()` réécrivait les Parquet à chaque démarrage.

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
`momentum_metrics`, `build_market_commentary`, `base_100`) sont, eux, bel et bien appelés.

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

**Base 100 = moyenne annuelle 2015, partout, sans exception.** `analysis.BASE_YEAR` et
`analysis.base_100()` portent la convention ; `app.py` et `web_export.build_synthese`
l'appellent tous deux pour le graphique croisé neuf/ancien, seul indice que le site calcule
lui-même (les indices de prix arrivent déjà en base 2015 de l'INSEE, comme la capacité
d'emprunt). Il était auparavant indexé sur *le premier mois commun de 2022* : une base sans
signification, et surtout différente de celle de tous les autres graphiques — deux courbes
« base 100 » de deux pages ne se comparaient pas, alors que c'est exactement ce qu'une base
commune promet. `base_100()` **refuse une année de référence incomplète** (moins de douze
mois) plutôt que de moyenner ce qu'elle trouve : une « moyenne annuelle » de trois mois
emporterait leur saisonnalité dans le dénominateur de toute la série. L'appelant retombe
alors sur les niveaux, et le manque se voit. Deux tests verrouillent l'affaire :
`tests/test_logic.py` sur le helper, `tests/test_web_links.py` sur le JSON **réellement
publié** (la moyenne des douze indices de 2015 doit valoir 100).

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
doit annoncer `0/7 fichier(s) modifié(s)`. Un diff inattendu signale une divergence de
calcul, pas du bruit — depuis que les agrégations sont en SQL, la sortie ne dépend plus de
la version de pandas/numpy.

## L'API HTTP (`api/`) — ce qui doit rester vrai

> **Depuis le 2026-08-23, plus aucune page du site n'appelle cette API par HTTP.**
> Prévision & Scénarios lisait `api/routes.py` en direct depuis le navigateur ; elle lit
> maintenant `previsions.json`, un septième export produit par `web_export.py` qui
> appelle `api.engine` **en important le module Python**, au build, pas au runtime (voir
> `build_previsions`). Données & Sources, qui appelait `/market/transactions-run-rate`,
> `/market/housing-types` et `/market/permits-run-rate`, dérive maintenant les mêmes
> séries de `ancien.json`/`neuf.json`, déjà publiés pour d'autres pages — aucun nouvel
> export n'était nécessaire pour celles-là. Le panneau de scénarios (quatre curseurs
> continus, un espace d'hypothèses qui ne s'énumère pas) reste un calcul CLIENT, mais en
> JS pur (`computeScenario`, `src/components/api.js`, port de `forecast.scenario`,
> vérifié par `tests/test_web_js_parity.py`) — plus un POST réseau pour huit
> multiplications.
>
> `api/routes.py`, `api/engine.py` et `tests/test_api_contract.py` restent intacts et
> testés : ce n'est pas un retrait de l'API, seulement de son appel HTTP depuis ces deux
> pages. `python -m api` reste une façon légitime d'explorer les mêmes routes en local.
> `src/components/api.js`, en revanche, a perdu tout son client HTTP (`request`,
> `apiBase`, `ApiError`, l'objet `api`, `apiOfflineNotice`) — plus rien ne l'appelait,
> et il ne porte plus que des ports JS de calculs Python (`ols1`, `shiftMonths`,
> `bestLagFit`, `computeScenario`).
>
> **Le benchmark de CA entreprise a été SUPPRIMÉ le 2026-08-24 — dataset compris.** La
> section « → Propagation au chiffre d'affaires benchmark » propageait le choc de
> transactions du panneau de scénarios vers le CA d'Hexaom et de Kingfisher France : une
> élasticité indicative estimée sur des séries d'entreprise courtes (32 et 8 trimestres),
> que personne n'utilisait. Le besoin réel est l'autre module, celui qui compare un CSV
> **importé par le visiteur** aux modèles — `bestLagFit` sur « Données & Sources », calcul
> client, le CSV ne quitte jamais le navigateur. Ne pas confondre les deux : le dataset
> `company_sales` (ventes société importées, mensuel) reste, `revenue` (CA trimestriel
> publié, versionné) est parti.
>
> Sont partis avec lui : `data/revenue.csv`, les trois fichiers `data_manual_input/ca-*`,
> `DataManager.build_revenue_from_manual_inputs`/`ensure_revenue` et l'entrée `revenue` du
> registre de chemins, le contrat pandera `REVENUE` (donc la vue SQL du même nom),
> `forecast.fit_tx_to_ca`/`best_tx_to_ca`, `simulation.resample_quarterly`/
> `find_optimal_lag_quarterly` (écrites pour cette seule série trimestrielle),
> `engine.revenue_benchmarks()` et sa route HTTP, plus la section de la page web et celle
> d'`app.py`. **`read_frames()` et `load_or_generate_all()` rendent désormais SIX frames,
> pas sept** — l'index 4 est `ecln`, plus `revenue` ; tout code qui déballe ce tuple par
> position doit être relu, c'est le seul piège de ce retrait.

Trois couches, chacune ne connaissant que la suivante :

```
web_export.py ──appel Python──► api/engine.py ──► queries.py / forecast.py
                                       ▲
                    (optionnel, local) │
                         navigateur ───┘ fetch() ──► api/routes.py
```

**`api/engine.py` n'importe pas Flask, et ne doit jamais l'importer.** C'est l'invariant
central : le moteur reste exécutable et testable serveur éteint
(`python -c "from api import engine; print(engine.rate_model()['r2'])"`) — c'est cet
invariant qui permet à `web_export.py` de l'appeler directement, en import Python, sans
passer par HTTP. Seul `api/routes.py` connaît HTTP. Un calcul qui se met à importer Flask
est un calcul rangé au mauvais endroit.

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

**Flask est optionnel.** Ni `app.py`, ni `report.py`, ni `web_export.py` n'en dépendent —
ce dernier importe `api.engine`, pas `api.routes`. Le site statique n'appelle plus l'API
du tout (voir l'encart en tête de section) ; l'encart `.hm-api-offline` qui subsiste sur
Prévision et Données ne se déclenche plus que si le modèle n'a pas pu être calibré à la
dernière publication (macro incomplète), pas si un serveur est injoignable.

**Les ventes société ne passent PAS par l'API.** Décision produit : le CSV est lu dans le
navigateur et n'est jamais téléversé. Conséquence directe — la régression qui en dépend
existe en double, en Python (`forecast.best_tx_to_monthly`) et en JS (`bestLagFit` dans
`web/observable/src/components/api.js`). `tests/test_web_js_parity.py` compare les deux sur
les mêmes données : même décalage retenu, même R². Ne pas laisser diverger.

**Les pages du front n'importent jamais `npm:` directement** : elles passent par
`src/components/hm.js`, qui réexporte `Plot`, `d3` et `csvParse`. Une seule façon de
charger une bibliothèque.

**Toute vignette de survol prend `TIP` de `hm.js`** — `Plot.tip(…, {…TIP})`, ou
`tip: {…TIP}` sur une marque. Plot dessine ses vignettes en 10 px ; sur ce site elles
portent les SEULS chiffres exacts (pas de quadrillage fin, pas d'étiquette intermédiaire),
donc la taille est remontée à 13 px. **En option de marque, jamais en CSS** : Plot mesure
le texte avec cette valeur pour dimensionner le cadre, si bien qu'un `font-size` posé en
feuille de style grossirait le texte dans une boîte restée petite, et le rognerait. Six
pages plus `hm.js` la déclarent — un nouveau graphique qui l'oublie se voit à sa vignette
deux fois plus petite que ses voisines.

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

**Le code de l'Atelier a fini d'être retiré le 2026-08-24.** Le retrait du 2026-08-20
avait décâblé l'onglet mais laissé ses moteurs dans `simulation.py` : `find_optimal_lag`
(recherche de décalage par max-r), `min_max_normalize`, `create_composite_indicator` et
`optimize_composite_parameters`, plus le handler de session `opt_applied` en tête
d'`app.py` (il recopiait les paramètres du grid-search composite dans les curseurs, et
plus rien n'écrivait ces clés). Tout est parti, avec le test
`test_composite_optimizer_reports_out_of_sample`. **`simulation.py` ne porte plus que
`shift_indicator`**, qui est de la mise en forme (deux appels dans `app.py`) et non une
méthode rivale de la recherche en grille de `forecast.search_tx_lags` — c'est cette
rivalité sans arbitre qui avait motivé le retrait de l'onglet. Les textes qui présentaient
encore la Prévision comme « la formalisation des onglets Time-Lag / Composite », ou les
ventes importées comme « sélectionnables dans l'Atelier », ont été réécrits : ils
renvoyaient à une interface que le lecteur ne peut plus ouvrir.

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

**Le chapeau des pages de données est STATIQUE — titre compris.** Les huit pages de
données montent leur contenu dans le navigateur à partir des JSON ; le titre valait
`# ${neuf.title}`, ce qui livrait littéralement `<h1></h1>` dans le HTML construit. Toutes
les pages du site sauf l'accueil et À propos étaient donc, pour un moteur de recherche ou
un aperçu de partage, des pages **sans titre** — et l'accroche située juste dessous,
`<div class="hm-caption">${neuf.caption}</div>`, était vide pour les mêmes raisons. Chaque
page porte désormais un titre écrit en clair, suivi de deux paragraphes rendus au build,
avant la première section.

Trois conséquences à tenir :

- **Le chapeau doit rester PÉRENNE : aucun chiffre.** Rien ne le régénère — ni
  `web_export.py`, ni le workflow hebdo. Un nombre écrit là se figerait au jour où il a
  été tapé, et vieillirait en silence sur la seule partie de la page que les robots
  lisent. C'est l'inverse du tableau des sources d'À propos, qui porte des dates
  précisément parce qu'une chaîne Python les y réécrit.
- **Les champs `title` et `caption` des JSON du front ne sont plus lus par le site.** Ils
  restent produits par `web_export.py` : les retirer ferait diffuser un diff sur les sept
  fichiers, alors que le compteur « n/7 fichier(s) modifié(s) » ne vaut que par son
  pouvoir d'alerte. À nettoyer dans une passe qui régénère les JSON délibérément, pas au
  détour d'une édition de texte. `how_to_read` reste, lui, bel et bien consommé — il
  remplit le repli « Comment lire cette page », qui reste dynamique.
- **Ne jamais reconvertir un titre ou un chapeau en interpolation.**
  `tests/test_web_structure.py` refuse un `# ${…}` et exige au moins quarante mots de
  texte réellement statique avant la première section (les `${…}` sont retirés du compte,
  puisqu'ils sont vides dans le HTML livré). Le seuil est bas exprès : il attrape la page
  muette, pas la page brève.

**La bande de chiffres de l'accueil est écrite en dur, et c'est le corollaire du point
précédent.** Les quatre nombres du bandeau (`<ul class="hm-stats">` dans `index.md`) sont
l'équivalent honnête des « logos clients » d'un site commercial : ils doivent rassurer en
deux secondes, donc être lus par les robots de partage, donc rester statiques. Trois sont
des constantes de fait ; le quatrième — l'erreur moyenne à 6 mois — bouge à chaque
publication et est **verrouillé par `tests/test_web_links.py`**, qui le compare au KPI
d'`archive.json` et échoue s'il dérive. Le même test exige que l'erreur naïve soit citée à
côté : publier le chiffre du modèle seul laisserait croire qu'il bat la référence à tous
les horizons, ce qu'il ne fait pas en deçà de 4 mois.

**Le tableau des sources d'À propos est ÉCRIT dans le Markdown par Python.** Même
contrainte que la bande de chiffres, résolue dans l'autre sens. La page doit rester
statique, mais ses treize lignes portent le dernier point publié de chaque série, qui bouge
à chaque rafraîchissement — trop souvent pour être reporté à la main, et invisible aux
robots s'il était rempli par un bloc ```js. `web/export/sources_table.py` déclare les
sources (intitulé, page du producteur, voie d'accès, dataset, colonnes, périodicité) et
réécrit les `<tr>` entre les marqueurs `hm:sources` d'`a-propos.md` ; `web_export.py`
l'appelle en fin de `main()`, **hors du compteur « n/7 »** (ce n'est pas un JSON du front,
et le compteur vaut par son pouvoir d'alerte). Trois conséquences : ne jamais éditer ces
lignes à la main ; `a-propos.md` figure dans le `git add` du workflow hebdo, sans quoi la
page de provenance figerait ses dates à la dernière publication manuelle ;
`tests/test_web_sources.py` échoue si les dates dérivent, si un lien ne suit plus `SOURCES`
ou si une colonne renommée fait afficher « — » — le mode de panne silencieux de ce tableau.

Une ligne = **une page source et une périodicité**. C'est ce qui a fait éclater les lignes
groupées d'origine : « confiance, intentions d'achat, chômage BIT » n'a ni un lien (trois
pages INSEE) ni une date (les deux premières sont mensuelles, le chômage BIT trimestriel).
Quand une ligne garde plusieurs colonnes, la date affichée est la **plus ancienne** des
dernières observations : c'est la borne jusqu'à laquelle la ligne est vraiment complète.

**Le bandeau ne déborde PAS de la colonne, volontairement.** Un vrai bord-à-bord
supposerait des marges négatives calculées sur les marges « auto » de
`#observablehq-main`, qui varient avec la largeur de fenêtre et avec la barre latérale :
le premier écran étroit ferait glisser la page latéralement. Le fond plein suffit à
produire la rupture. Ses couleurs sont DÉRIVÉES des jetons (`color-mix` sur `--hm-ink` et
`--hm-brick`) — aucune valeur hexadécimale n'entre dans `observablehq.config.js`. Le
bouton principal du bandeau est BLANC et non brick : blanc sur brick plafonne à 3,9:1,
sous le seuil de 4,5:1.

**Le CSS du thème vit dans un littéral gabarit JS.** Un accent grave dans un commentaire
CSS referme la chaîne et fait échouer le build sur une erreur de syntaxe sans rapport
apparent (`Unexpected token ':'`, pointant une ligne de prose). Ne jamais citer un
sélecteur entre accents graves dans ce fichier.

**Aucune URL d'hébergement en dur.** Les balises Open Graph et l'URL canonique exigent des
adresses ABSOLUES ; elles viennent de `HM_SITE_URL` (variable d'environnement Cloudflare
Pages), avec pour repli le domaine de production lui-même. Un test injecte une
adresse différente du repli et vérifie que tout suit — c'est ce qui empêche une URL de se
figer dans le code. Une adresse fausse ne casse aucune page : elle casse silencieusement
l'aperçu au partage et le référencement.

**Le formulaire de contact est le SEUL code serveur du site.**
`web/observable/functions/api/contact.js` est une Cloudflare Pages Function, exécutée
parce qu'elle est dans `functions/` à la racine du projet Pages — tout le reste de `dist/`
est servi par un CDN, sans processus derrière. Ce n'est pas l'API Flask de `api/` (qui
expose des calculs et n'est pas hébergée) : cette fonction ne calcule rien, elle valide
quatre champs et relaie vers Resend. Ne pas fusionner les deux.

**L'adresse de destination ne doit JAMAIS entrer dans le dépôt.** Il est public : une
adresse personnelle dans un fichier versionné est moissonnée exactement comme un
`mailto:`. Elle vient de `CONTACT_TO` (variable d'environnement Cloudflare), avec
`RESEND_API_KEY` ; sans l'une des deux la route répond **503** et la page le dit, plutôt
que de remercier sans rien envoyer. C'est aussi pourquoi la page porte un formulaire et
non un lien courriel. Les trois variables sont documentées dans `web/README.md`.

**Le formulaire est du HTML statique, le bloc ```js ne fait que le brancher.** Même
raison que pour le reste de la page — les robots d'aperçu ne l'exécutent pas — mais
surtout : si ce script échoue, le visiteur voit encore les champs et la mention
`<noscript>` au lieu d'un trou. La route n'existe pas sous `npm run dev` (les Pages
Functions ne tournent que chez Cloudflare ou sous `wrangler pages dev`), donc un envoi
depuis la préversion affiche « l'envoi a échoué en route » : c'est attendu.

**L'anti-spam est un pot de miel plus un délai, sans service tiers ni énigme imposée** (un
test que l'humain doit résoudre écarte aussi des humains). Le champ caché l'est **hors
écran**, jamais par `display:none` que les robots savent sauter ; et la page transmet la
**durée** écoulée depuis son chargement, pas l'heure de celui-ci — confronter l'horloge du
visiteur à celle du serveur jetterait en silence les messages de toute machine mal réglée.

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

**La fenêtre du momentum dépend de la SÉRIE, pas du goût (2026-08-26).** La Synthèse
publiait pour ses trois séries le même « X % sur les 3 derniers mois vs les mêmes mois
n-1 ». C'est le bon outil sur une série brute et le mauvais sur les deux autres.

SIT@DEL est chargée en `NAT_SERIES == "CVS-CJO"` ([data_manager.py:289](data_manager.py:289)) :
elle est DÉJÀ corrigée des variations saisonnières et des jours ouvrables. Or comparer aux
mêmes mois de l'an dernier n'a qu'une raison d'être — neutraliser la saisonnalité. Sur une
série déjà corrigée, la comparaison ne neutralise rien et importe gratuitement une base
vieille de douze mois, dont le bruit devient tout le signal. Mesuré sur les mises en
chantier à juin 2026 : l'indicateur affichait **+28,4 %** (dont ~8 points dus au seul creux
d'avril-juin 2025, base 6 % sous la moyenne de l'année) et venait de perdre **13,8 points
en un mois** — la sortie du pic de mars 2026 de la fenêtre — pendant que la tendance
12 mois bougeait de 0,3 point. La même série lue **séquentiellement** disait **−2,0 %** :
le rythme avait cessé de monter. La page publiait un gros chiffre vert au moment exact où
la dynamique se retournait.

L'IGEDD est l'inverse : reconstruite en différenciant un cumul 12 mois, ses flux mensuels
sont très bruités — le séquentiel y saute de **10 points par mois** en moyenne (contre 1,6
pour le cumul 12 mois). Sa lecture honnête reste le niveau 12 mois, complété par
`ana.plateau_months`, qui dit depuis quand ce niveau ne bouge plus : « +5,2 % sur un an »
décrivait une croissance **arrêtée depuis décembre 2025**, ce qu'un taux annuel à base
basse ne peut pas dire.

D'où deux régimes, portés par `ana.ADJUSTED_SEQUENTIAL` / `ana.RAW_TWELVE_MONTHS` et
`ana.headline_momentum`. **Le choix vit dans `analysis.py` et non dans les surfaces**,
précisément pour qu'`app.py` et `web_export.py` ne puissent pas en retenir un chacune.
`momentum_metrics` renvoie désormais aussi `last3_seq` ; `last3_yoy` reste calculée (les
onglets Neuf/Ancien l'affichent encore dans `_yoy_kpi`) mais n'est plus publiée par la
Synthèse. Chaque carte porte les DEUX horizons — momentum, puis tendance 12 mois : publier
l'un sans l'autre laisse croire qu'un retournement de trimestre efface une année.

**Le pilier « Neuf » ne moyenne plus ses deux étages, et c'est le point porteur.** La règle
précédente faisait `(permis + chantiers) / 2` sur deux taux de croissance de séries
d'ampleurs différentes. Au-delà de l'objection arithmétique, elle DÉTRUISAIT l'information
utile : les permis sont l'amont (ce qui alimente les chantiers 12 à 18 mois plus tard), les
mises en chantier l'aval (ce qui consomme des matériaux aujourd'hui). En juin 2026 la
moyenne rendait « +9,7 % → 🟢 en reprise » là où les permis reculaient de 9,8 % et les
chantiers de 2,0 %. `ana.pillar_neuf` nomme la divergence (« amont en repli ») et la
`kind` alimente la puce « à retenir », seul endroit où le mécanisme — l'aval tourne sur le
stock d'autorisations déjà délivrées — peut être écrit en toutes lettres. Corollaire tenu
dans la foulée : la puce « Demande second œuvre » lit l'**amont** pour son horizon 12-18
mois, plus le statut agrégé — sinon l'aval, qui décrit le présent, masque le signal du
futur.

`ana.SEQ_TOL = 2.0` est plus large que le ±1 des taux annuels, et pour une raison mesurée :
le 3 mois séquentiel saute de 5,2 pt par mois sur les permis et de 3,5 pt sur les chantiers.
À ±1 la pastille changerait de couleur au bruit. Cinq tests de `tests/test_logic.py`
verrouillent l'ensemble, dont une **contre-épreuve** explicite : amont −10, aval +30 (la
moyenne dirait « up ») doit rendre `amont_repli` et jamais `up`.

**Le chapeau statique de la Synthèse porte la méthode, donc il devait bouger aussi.** Il
annonçait « les trois derniers mois comparés à la même période un an plus tôt » — devenu
faux. Comme tout chapeau du site il reste sans aucun chiffre (rien ne le régénère) ; il
décrit les deux horizons, les deux régimes et le refus de moyenner, en toutes lettres.

**Une carte porte le momentum ET l'altitude, sur deux lignes séparées (2026-08-26).**
Corriger la fenêtre du momentum a rendu la pente juste et laissé le niveau muet — or les
deux mènent à des décisions différentes. `ana.level_context` situe le cumul 12 mois par
rapport à une décennie de marché ordinaire et par rapport à toute son histoire. Mesuré :
les mises en chantier sont **23 % sous la normale 2010-19** et **plus basses que 91 % des
mois depuis 2000** (9ᵉ percentile — 29 mois sur 307 seulement ont fait moins bien ;
annualisé, ce serait la 3ᵉ pire année sur 26). La même carte annonce « tendance 12 mois
+16,7 % ». Les deux sont vrais : c'est un rebond de creux, pas une reprise, et seul le
second fait dimensionne un outil industriel. À l'inverse, les ventes anciennes sont **17 %
AU-DESSUS** de cette normale alors que leur pastille est orange — le code couleur porte le
momentum, la seconde ligne porte le niveau, et il fallait les deux.

`ana.LEVEL_REF_YEARS = ("2010", "2019")` est **choisi, pas trouvé** : exclut 2004-2007 (la
bulle de crédit, dont le pic mettrait une barre que le marché n'a jamais retrouvée) et
l'après-2020 (Covid puis choc de taux, c'est-à-dire l'anomalie qu'on veut mesurer). Les
deux lignes restent SÉPARÉES à l'affichage (`sub` et `level` dans le JSON, deux
`.hm-card-sub` sur le front, deux `st.caption` dans `app.py`) : les fondre les mettrait
sur le même plan alors qu'elles répondent à deux questions.

**Le bloc « Perspective » publie la prévision DU SITE, plus la cible d'un tiers.** Il
affichait « ventes 12 m vs cible BPCE 2026 » : le même 954 k que la carte d'activité, en
**vert** parce qu'il dépasse la cible d'une banque, à un écran de la même valeur en
**orange**. Un seul nombre, deux jugements. Et « infléchissement attendu » était une chaîne
codée en dur, déclenchée par le simple dépassement du seuil, adossée à aucune prévision —
elle coïncidait avec le modèle par hasard. La carte porte désormais la projection à six
mois, sa fourchette et son taux de bon sens mesuré ; le titre du bloc est construit depuis
les CHAMPS du verdict, jamais par découpe de sa phrase (`sentence` est faite pour être lue,
sa forme peut changer). Repli sur la comparaison BPCE si le modèle n'est pas calibrable :
le bloc ne reste jamais vide.

`_shared_verdict` mémoïse `_verdict` pour la durée du process, parce que **deux pages en
ont maintenant besoin** — la Synthèse et « Prévision & Scénarios ». Le recalculer de chaque
côté rejouerait l'ajustement complet pour aboutir au même nombre, et surtout rien ne
garantirait qu'il le reste. Preuve que la mémoïsation est neutre : `previsions.json` est
resté **inchangé** au passage de `_verdict(payload["projection"], con)` à
`_shared_verdict(con)`.

**L'ECLN aussi est CVS-CJO, et elle a suivi.** Le premier correctif n'avait traité que
SIT@DEL et laissé la carte ECLN en « vs même trimestre un an plus tôt » — le défaut exact
qu'on venait de retirer, sur une série de même nature. Elle se lit maintenant d'un
trimestre au précédent (−4,8 % contre −2,1 % publié), avec la tendance sur quatre
trimestres dans le rôle du cumul 12 mois. **Trois séries corrigées des variations
saisonnières sur le site : permis, mises en chantier, ECLN. Aucune ne doit être comparée à
n-1.**

**Ce qui n'a délibérément PAS été mirroré dans `app.py` : le verdict du modèle.** Les
points « niveau » et « ECLN » y sont (helpers purs, aucun risque) ; la carte de projection
non, et la Synthèse d'`app.py` garde sa carte BPCE. Raison : `app.py` n'importe pas
`api.engine`, et l'y importer ajouterait un second moteur de prévision dans un process
Streamlit multi-sessions — exactement la surface de concurrence que l'invariant « une
requête = un curseur » documente comme ayant déjà produit un bug de production. **Défaut
préexistant découvert au passage, à traiter à part** : l'onglet Prévision d'`app.py` appelle
`fc.forecast_path(...)` **sans `anchor` ni `band`**, là où `api.engine.projection()` passe
les deux. `app.py` publie donc déjà une projection non recalée et à bande constante, c'est-
à-dire des chiffres différents de ceux du site. Ce n'est pas une régression introduite ici,
mais c'est la vraie raison pour laquelle brancher le verdict sur `app.py` demande une passe
dédiée : il faudrait d'abord aligner son moteur.

**Les blocs de la Synthèse sont rangés par HORIZON, plus par source (2026-08-26).**
« Activité / Financement / Perspective » regroupait ce qui vient du même fichier — le plan
mental du producteur. Un lecteur qui décide va du présent vers l'avenir, d'où quatre blocs
dans cet ordre, sur les deux surfaces :

| Bloc | Ce qu'il répond | Cartes |
|---|---|---|
| Aujourd'hui — ce qui se construit et se vend | ce qui consomme des matériaux maintenant | chantiers, ventes anciennes, **stock neuf à vendre** |
| Le carnet — ce qui est déjà autorisé, 12-18 mois | ce qui est engagé | permis, **taux de transformation**, réservations ECLN |
| Ce qui pilote la suite | les entrées du modèle | taux, demande de crédit, accessibilité |
| Où va le marché | la sortie du modèle | projection, rénovation, échéance aides |

Les conditions de financement passent **juste avant** la projection : ce sont ses entrées,
on lit les causes avant le résultat.

**Les deux cartes ajoutées sont les deux ponts qui manquaient**, et toutes deux existaient
déjà ailleurs sur le site :

* **Taux de transformation permis → chantiers**, 78,0 % contre 84,8 % de moyenne depuis
  2000. Sans lui, « 376 k permis » se lit comme 376 k chantiers à venir. À taux habituel
  les permis des douze derniers mois donneraient **319 k chantiers, soit 25 794 logements
  de plus qu'aujourd'hui**. Il ne prévoit rien (voir `NEUF_GATE` : permis → chantiers a été
  mesuré puis réfuté), il décrit ce que les promoteurs font de leurs autorisations.
  `_taux_transformation` est **partagée** par `build_synthese` et `_transformation` : deux
  calculs séparés du même pont finiraient par ne plus tomber sur la même valeur.
* **Stock de logements neufs à vendre**, 124 027, et surtout **22 mois pour l'écouler
  contre 15 en moyenne — 53 % de temps de plus**. ⚠️ `DelaiEcoulement` est publié en
  **TRIMESTRES** : 7,5 se lit 22 mois, pas 7,5. J'ai fait l'erreur en cours de session et
  elle change tout le diagnostic (sept mois de stock est sain, vingt-deux ne l'est pas) —
  les deux surfaces multiplient donc explicitement par 3, avec le commentaire qui le dit.
  Cette carte se lit **à l'envers des autres** : un stock qui s'écoule lentement est ce qui
  FAIT reculer les mises en vente, donc les chantiers de demain. Son statut vient du délai
  comparé à sa moyenne longue, jamais de la variation du stock.

**Le chapeau de la Synthèse est passé de ~350 à ~95 mots.** Il avait absorbé, correctif
après correctif, toute la justification méthodologique — deux régimes de momentum, le refus
de moyenner, le niveau, la projection. C'est le bon contenu au mauvais endroit : un
dirigeant ne lit pas quatre paragraphes de méthode avant de voir un chiffre. Tout est
conservé dans `how_to_read`, derrière le repli « Comment lire cette page ». Le seuil de
`test_web_structure.py` (≥ 40 mots statiques) reste largement tenu. Conséquence à ne pas
oublier : `how_to_read` est une interpolation depuis le JSON, donc **invisible aux robots**
— raccourcir le chapeau réduit réellement le texte indexé, et c'est un arbitrage assumé en
faveur du lecteur.

**Les puces « à retenir » sont le niveau de lecture le plus CHER de la page, et elles
avaient pris du retard.** Trois pastilles pour un coup d'œil, quatre puces pour trente
secondes, douze cartes pour le détail : un dirigeant lit les deux premiers niveaux et ne
descend au troisième que si quelque chose l'accroche. Or le générateur de puces ne lisait
que neuf variables, toutes antérieures aux correctifs — **quatre familles de faits
n'atteignaient pas le niveau 2** : le stock (22 mois), le taux de transformation
(25 794 chantiers manquants), les niveaux (23 % sous la normale) et la projection (−4 %).
La puce vedette disait « la maison individuelle pure : +8,3 % », vrai mais secondaire, et
taisait les deux ans de stock invendu.

Les puces suivent désormais les quatre blocs. Deux points de méthode à tenir :

* **La puce 1 sépare l'ancien du neuf** au lieu de les fondre : ils n'alimentent pas les
  mêmes lignes de produits, et ils ne disent pas la même chose — l'ancien est haut mais
  figé, le neuf est bas et sous stock. Son statut vient des deux VOLUMES du présent, pas
  du stock : celui-ci est un avertissement à l'intérieur de la puce, pas de quoi peindre
  tout le présent en rouge.
* **Chaque moitié tient en une phrase.** Les puces sont passées de 133 à 169 mots pour
  quatre familles de faits en plus ; une première version en faisait 209 et annulait la
  marche entre le résumé et le détail. Ce qui reste sur les cartes : le taux annuel, le
  percentile, l'explication du plateau, la fourchette de la projection.

**Un chiffre juste peut dire l'inverse de ce qu'il veut dire.** La carte du taux de
transformation annonçait « les permis donneraient 319 k chantiers, soit 25 794 logements
**de plus** qu'aujourd'hui ». Arithmétiquement exact, et lu comme une bonne nouvelle :
l'œil accroche « de plus » et comprend croissance, alors que le fait est un MANQUE causé
par un taux de conversion dégradé. Elle énonce maintenant le déficit dans le bon ordre —
« au taux habituel, les permis auraient donné 319 k chantiers **au lieu de** 293 k :
25 794 manquent à l'appel ». À vérifier sur tout écart publié : le signe arithmétique et
le signe ressenti doivent pointer dans le même sens.

**Un contrefactuel n'a pas sa place dans une puce, et la référence du taux de conversion
était contaminée (2026-08-26).** La puce 2 portait « 25 794 manquent à l'appel ». Trois
défauts, à ce niveau de lecture :

1. c'est **la seule quantité des puces qui ne s'est jamais produite** — tout le reste est
   observé, et le lecteur ne fait pas la différence à la vitesse d'une puce ;
2. **précision fantaisiste** : l'écart-type du taux de conversion vaut 4,9 points, ce qui
   déplace l'écart de **±18 328 logements**. Cinq chiffres significatifs sur une grandeur
   connue au millier près ;
3. **le nombre dépend de la fenêtre de référence** — 25 794 / 27 684 / 29 963 selon
   qu'on prend 2000-2026, 2010-19 ou 2001-2022 — et ça ne se voit pas.

La puce ne porte donc plus que **les deux taux** (« seulement 78 % des permis deviennent
des chantiers, contre 85 % dans les années 2010 »). C'est la RUPTURE qui parle, et elle
est franche : le taux tenait entre **85,0 et 87,7 %** sur les quatre sous-périodes de 2001
à 2022, crise de 2008 comprise, avant de tomber à **77,8 %** sur 2023-2026. Le contrefactuel
reste sur la CARTE, où un lecteur descendu jusque-là a le temps de le lire comme tel —
arrondi au millier (`_arrondi_millier`) et avec sa fenêtre nommée.

**Correctif de fond dans la foulée : la référence du taux de conversion est passée de
« moyenne depuis 2000 » (84,8 %) à `ana.LEVEL_REF_YEARS` (85,3 %).** L'ancienne englobait
la rupture de 2023-2026 qu'on cherche précisément à mesurer : **l'anomalie diluait sa
propre référence** et se faisait paraître plus petite. C'est exactement la faute que
`LEVEL_REF_YEARS` a été écrite pour éviter côté niveaux. J'avais d'abord classé cette
double convention « cosmétique, 0,5 point » — vrai sur le nombre, faux sur la méthode.

⚠️ La page « Marché du neuf » garde, elle, `TR.moyenne` = moyenne sur tout l'historique :
c'est légitime là-bas (une ligne de moyenne tracée sur le graphique de toute la série,
labellisée comme telle) et ce n'est pas la même question qu'un contrefactuel. **Les deux
chiffres coexistent donc, mais chacun NOMME sa fenêtre** — « en moyenne sur 2010-19 » d'un
côté, « moyenne de long terme » de l'autre. Ne jamais publier l'un des deux sans sa
fenêtre : c'est ce qui rend la coexistence honnête plutôt qu'incohérente.

**Règle générale sortie de là : le signe arithmétique et le signe RESSENTI doivent pointer
dans le même sens.** Aucun test ne l'attrape. Et sa contrepartie : ne pas retourner une
formulation juste pour frapper plus fort — dire « 22 % des permis ne sortent pas de terre
contre 14 % avant » (+57 % en relatif) plutôt que « 78 % contre 85 % » (−9 %) décrit le
même fait et double l'impression. C'est un choix rhétorique, il revient à l'auteur du
site, pas au générateur.

**Divergence assumée sur la puce 4.** Le site y publie la projection (« ventes anciennes
projetées en recul d'environ 4 % d'ici décembre 2026 ») ; `app.py` retombe sur l'état des
transactions, faute de verdict — même raison que pour sa carte de Perspective, documentée
plus haut. Le code a **une seule forme** (le second membre prend le verdict s'il existe,
sinon le repli), c'est la donnée qui manque d'un côté, pas la logique.

**Reste au backlog, mesuré mais non fait : la SURFACE.** Le fichier SIT@DEL déjà en dépôt
porte `SDP_AUT` / `SDP_COM` (surface de plancher, m²) et `data_manager.py` ne parse que
`LOG_AUT` / `LOG_COM`. Or les matériaux suivent les m², pas le nombre de logements. Mesuré
à juin 2026 : 293 412 logements commencés pour **22,3 M m²**, soit **−32 % vs la moyenne
2010-19 en surface contre −23 % en logements** — le logement moyen est passé de 85,2 à
76,1 m². Neuf points d'écart sur le tonnage adressable, invisibles aujourd'hui. Touche
`data_manager.py`, le contrat pandera et les tests de parité : à faire dans une passe
dédiée.

**Les correctifs de la Synthèse ont été propagés aux deux pages de marché (2026-08-27).**
Ils y étaient restés absents, et c'était le pire endroit pour ça : le **+28,4 %** qui a
motivé toute la révision de la Synthèse était **toujours publié en carte de tête de
« Marché du neuf »**, c'est-à-dire sur la page qu'on ouvre pour zoomer. Trois choses ont
changé sur les deux pages, via `_yoy_kpi` :

* **momentum selon le régime** (`ana.headline_momentum`) — séquentiel sur SIT@DEL et ECLN,
  12 mois sur l'IGEDD, complété par le plateau ;
* **le sous-titre « Mensuel : X (Y % YoY) » perd son YoY.** Sur ces séries CVS il saute de
  **11,2 points par mois** sur les permis et **9,0** sur les chantiers — six dernières
  valeurs des chantiers : `+21 +19 +49 +32 +46 +12`. Du bruit en carte de tête. Le NIVEAU
  du dernier mois reste, c'est un fait ;
* **une ligne de NIVEAU** sur chaque KPI, y compris les 15 sous-ensembles de
  `kpis_by_type`.

**La section « Individuel vs Collectif » est celle où la correction change le plus une
décision.** Son chapeau désigne l'individuel comme « le driver de volume le plus direct »
d'un fabricant de second œuvre, et la page l'affichait à **+40,0 %**. Les deux lectures
s'inversent :

| Mises en chantier | ancien affichage (3 m vs n-1) | séquentiel | niveau vs 2010-19 |
|---|---|---|---|
| Maison individuelle pure | +40,0 % | +8,3 % | **−42 % · 7ᵉ centile** |
| Individuel total | +32,9 % | +7,1 % | −37 % · 8ᵉ centile |
| Collectif | +25,8 % | **−6,9 %** | −12 % · 36ᵉ centile |

La croissance la plus forte est sur le segment le plus effondré (rebond de plancher), et
le segment le moins dégradé est celui qui vient de se retourner. Chaque carte porte donc
ses deux lignes, et le chapeau de la section dit que c'est l'écart entre elles qui décide
d'un arbitrage de lignes de produits.

**« 📅 Comparaison Mensuelle par Année » a quitté le socle des jumelles et la page du
neuf.** Elle ne voulait pas dire la même chose des deux côtés — mesuré sur 2015-2026 :

| série | amplitude saisonnière résiduelle |
|---|---|
| Permis (CVS-CJO) | 6,9 % |
| Chantiers (CVS-CJO) | 7,8 % |
| Ventes anciennes (brut) | **38,6 %** |

Sur l'ancien, comparer juin à juin neutralise une vraie saisonnalité : le graphique fait
son travail. Sur le neuf, il comparait des mois **déjà désaisonnalisés** — donc du bruit,
en invitant à lire une saisonnalité que la source a déjà retirée. `SOCLE` dans
`tests/test_web_structure.py` passe donc à **deux** sections, le renvoi jumeau
correspondant disparaît des deux côtés, et le chapeau de la section côté ancien explique
pourquoi elle n'a pas de jumelle. **Le socle garantit la symétrie de FORME, pas celle du
sens : quand les deux divergent, c'est le sens qui gagne.** Le payload `monthly` de
`neuf.json` est parti avec la section (318 lignes de données mortes), ainsi que les
imports `monthlyByYear` / `MONTHS_FULL` / `MONTHS_SHORT` de `neuf.md`.

**La page de DÉTAIL ne doit jamais en dire moins que la page de survol.** Le délai
d'écoulement ECLN était affiché « 22 mois » tout court sur « Marché du neuf » pendant que
la Synthèse disait déjà « 22 mois · 15 en moyenne — 53 % de temps de plus ». Les quatre
KPI ECLN portent désormais leur momentum séquentiel, et le délai sa référence longue.

**`kpiCard` (`components/hm.js`) rend ses sous-lignes en `<ul>` dès qu'il y en a DEUX**,
comme les cartes de la Synthèse — empilées en `<div>` nues, deux phrases longues qui
wrappent toutes les deux deviennent indiscernables. Une seule sous-ligne reste une `<div>` :
une puce isolée ne sépare rien.

**Ce que l'ancien reste incapable de dire, et c'est structurel.** Pour un industriel des
matériaux, le marché de l'ancien n'est pas un débouché : c'est censé être le signal amont
de la **rénovation**, qui n'a pas de page (elle est un bloc de « Environnement &
Financement »). Or le pont a été mesuré le 2026-08-27 et il ne tient pas : la corrélation
entre la croissance 12 mois des transactions et le solde d'opinion rénovation monte de
+0,16 à +0,25 entre 0 et 18 mois de décalage puis redescend — **plate, faible, sans pic**,
le profil même qui a fait réfuter permis → chantiers. ⚠️ Caveat qui interdit d'en faire une
réfutation publiée : la série rénovation est un **solde d'opinion**, pas un volume, donc le
test est faible par construction. Il ne montre pas que le lien n'existe pas, il montre
qu'on ne sait pas le voir avec ce qu'on a.

**Le texte statique ne doit porter ni chiffre NI ÉTAT (2026-08-27).** La règle « aucun
chiffre dans un chapeau » était connue ; il lui manquait sa moitié. Un chapeau peut geler
le présent **sans écrire un seul nombre** — et c'est plus difficile à repérer, puisqu'il n'y
a rien à `grep`. Deux cas trouvés en auditant les trois onglets, tous deux sur `neuf.md` :

* le chapeau de « Individuel vs Collectif » disait « l'individuel pur remonte vite depuis un
  plancher historique ; le collectif [...] son rythme des trois derniers mois s'est
  retourné ». Vrai en août 2026, faux dès que le collectif repart — et la page aurait alors
  affirmé le contraire de ses propres cartes, qui sont régénérées ;
* le chapeau ECLN disait « le délai d'écoulement — **proche de deux ans** — » : un chiffre
  écrit en toutes lettres, donc figé au jour où il a été tapé.

Les deux énoncent désormais le **mécanisme** (« une croissance forte sur douze mois décrit
parfois un rebond depuis un plancher », « le temps qu'il faudrait pour vendre le stock au
rythme actuel ») et laissent la valeur aux cartes. **Test à faire avant d'écrire une phrase
statique : serait-elle encore vraie dans un an ?** Si la réponse dépend des données, la
phrase appartient au générateur, pas au Markdown.

**Ce qui est régénéré, et ce qui ne l'est pas.** Le workflow hebdo enchaîne
`fetch_new_sources.py` → `forecast_archive.py --record` → `web_export.py` → commit. Donc :

| | régénéré chaque semaine | à maintenir à la main |
|---|---|---|
| Valeurs, momentum, niveaux, plateau, pastilles, puces « à retenir », titres de blocs (verdict compris), cartes ECLN, taux de transformation, graphiques | ✅ | |
| Chapeaux de page et de section, `how_to_read` (chaînes littérales dans `web_export.py`) | | ⚠️ |
| `NEUF_GATE`, `REFUTATIONS`, `BENCHMARK_FNAIM`, `BENCHMARK_TAUX`, `BPCE_*`, `actualites.NEWS_ITEMS` + `MAJ` | | ⚠️ **datés exprès** |

La troisième ligne est un choix documenté (résultats de méthode, relevés externes), pas un
oubli — mais elle vieillit : `actualites.MAJ` avait **six semaines de retard** au moment de
cet audit, et le filtre des échéances compare à `MAJ` plutôt qu'à la date du jour (voir
plus bas). La deuxième ligne, elle, n'a aucune garde.

**Neuf et ancien sont des pages JUMELLES : trois sections communes, même intitulé, même
ordre.** « 🔑 Chiffres Clés », « 📊 Courbes d'évolution du marché », « 📅 Comparaison
Mensuelle par Année » ouvrent les deux pages ; chacune ajoute ensuite ce qui lui est propre
(individuel/collectif et ECLN d'un côté, prix et accessibilité de l'autre). C'est ce socle
qui permet d'apprendre la page une fois et de la relire de l'autre côté — « Dynamique
Individuel vs Collectif » s'intercalait au milieu et a été déplacé APRÈS pour le rétablir.
Chaque section du socle porte un renvoi vers sa jumelle (`.hm-shortcuts--twin`), et les
deux ancres coïncident parce que les deux titres coïncident.

Rien dans le build ne protège cette symétrie : renommer une section d'un seul côté casse
l'ancre visée d'en face **sans faire échouer le build** — la validation de liens
d'Observable Framework ne regarde pas les fragments. D'où `tests/test_web_structure.py`,
qui vérifie le socle, son ordre, les renvois et l'existence des ancres visées, en pur
Python (ni Node ni build requis).

**Le sommaire de page (`toc`) est construit AU BUILD à partir des `<h2>` du Markdown.** Un
titre posé par ``display(html`<h2>…`)`` n'y figure JAMAIS : c'est pourquoi les sections
conditionnelles de `macro.md` portent un titre Markdown statique et affichent un encart
« série absente » plutôt que rien — un titre suivi de vide se lit comme une panne. Le
défaut reste `toc: false` dans la config, chaque page l'active dans son front-matter, et
l'accueil s'en abstient délibérément (page d'atterrissage, dont « Les huit pages » EST déjà
la navigation). Un test refuse qu'une page ait des sections sans sommaire, ou l'inverse.

**Le sommaire ne s'affiche qu'à partir de 1320 px, et c'est un correctif, pas un réglage.**
Le framework le montre dès 1216 px en réservant 208 px de gouttière sur `main` : mesuré à
1250 px, la colonne de contenu tombait de 817 à 659 px et les `.hm-panels` (minmax 340 px)
passaient de deux colonnes à une. Or ces panneaux sont **appariés pour être comparés**
(encours vs délai d'écoulement, capacité d'emprunt vs accessibilité) — et 1280×800 comme
1366×768 tombent en plein dans cette bande. Deux règles sont donc à défaire, pas une : le
sommaire ET sa gouttière (`#observablehq-toc ~ #observablehq-main`), faute de quoi la
colonne reste étroite pour rien. En dessous du seuil, ce sont les renvois entre jumelles
qui assurent la navigation par section.

**Une légende cliquable est un `<button aria-pressed>`, jamais un `<span onclick>`.** Le
barré et l'opacité ne disent l'état qu'à ceux qui les voient ; un `span` n'est atteignable
ni au clavier ni au lecteur d'écran. Les deux légendes du site (`components/hm.js` et
`synthese.md`) sont des boutons dont le CSS neutralise l'apparence — le rendu n'a pas
changé.

**L'encart `.hm-api-offline` a changé de sens le 2026-08-23.** Prévision et Données ne
dépendent plus d'un serveur HTTP (voir « L'API HTTP » plus haut) : un visiteur externe
les voit désormais fonctionner, comme les six autres pages. L'encart subsiste, mais pour
un cas bien plus rare — `available: false` dans `previsions.json`, c'est-à-dire un
modèle non calibrable à la dernière publication hebdomadaire (macro incomplète), pas un
serveur injoignable. `python -m api` reste utile pour explorer les mêmes routes en
local, mais plus aucune page n'en a besoin pour s'afficher.

**« À qui ça sert » met le particulier AVANT le professionnel, depuis le 2026-08-23.**
L'ordre inverse — « il s'adresse à qui doit anticiper une activité liée au logement »
en premier, « et à qui veut simplement suivre le marché » en second — était un cadrage
B2B pour un site dont la bande de chiffres, la courbe d'accroche et depuis le retour des
pages départementales le sélecteur « Et chez vous ? » parlent tous à un particulier.
Le paragraphe professionnel n'a pas été supprimé, seulement rétrogradé en second. Le
même changement a retiré l'encart « Deux pages ont besoin d'un serveur » : il décrivait
une limite que le passage de Prévision/Données au statique (voir « L'API HTTP ») a fait
disparaître — le laisser aurait été une régression documentaire, pas juste une
imprécision.

**Un sigle porte un `<abbr title>` sur sa PREMIÈRE occurrence par page, jamais toutes.**
`SIT@DEL`, `ECLN`, `IGEDD`, `DVF`, `OAT`, `Euribor`, `BLS`, `BIT`, `backtest` sont ainsi
annotés dans le chapeau statique de chaque page où ils apparaissent en premier — un
soulignement pointillé (`abbr[title]` dans `observablehq.config.js`), pas un composant
JS : les chapeaux sont du texte statique (voir plus bas), et `<abbr>` est du HTML brut,
valide directement dans le markdown. Annoter CHAQUE occurrence aurait criblé le texte de
pointillés pour un gain marginal — la définition complète, plus longue, vit dans le
repli « Le vocabulaire » d'À propos, entre « D'où viennent les données » et « Comment le
site est fabriqué ». Un terme qui apparaît seulement dans du contenu JS-rendu (les
libellés de cartes KPI, par exemple `R²`) n'est PAS annoté : le composant `dfn()`
envisagé au départ a été abandonné une fois vérifié que la quasi-totalité du jargon vit
dans des chapeaux statiques, où un `<abbr>` brut suffit sans dépendance JS.

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
  distinguent pas pour tout le monde.
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

**Le verdict de tête est GÉNÉRÉ, jamais écrit.** « Prévision & Scénarios » publiait les
entrailles du modèle — un R², une MAPE, trois coefficients OLS, un z-score d'intentions
d'achat — et nulle part sa conclusion. `web_export._verdict` produit la phrase (sens,
ampleur, mois visé) et la fiabilité mesurée à cet horizon. Il porte des chiffres, donc il
ne peut PAS vivre dans le chapeau statique, que rien ne régénère : c'est le seul bloc de
tête de page légitimement dynamique. `_VERDICT_HORIZON = 6` — l'horizon auquel un
particulier raisonne, et le premier auquel le modèle bat la naïve. Le seuil de 1,5 %
en deçà duquel il dit « stable » n'est pas cosmétique : l'erreur à six mois vaut 5,7 %,
donc annoncer une variation plus petite reviendrait à commenter son propre bruit.

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

## Vérifier la parité

Trois recettes, par ordre de coût croissant. Les tests unitaires seuls ne suffisent pas :
ils ne prouvent rien sur le câblage des surfaces.

**1. Tests de parité** — chaque requête SQL contre son équivalent pandas sur les données
réelles. Nécessite un entrepôt construit (`python -c "from data_manager import
DataManager; DataManager().load_or_generate_all()"`), sinon le module se skippe.

```
python -m pytest tests/ -q          # 249 passés, 1 skip légitime si company_sales est
                                    # vide. Les tests d'API se skippent sans Flask, ceux
                                    # de parité JS et de référencement sans Node.
```

**Piège Windows sur les tests qui appellent Node.** `subprocess.run(text=True)` décode la
sortie avec la page de codes ANSI du système (cp1252), pas en UTF-8 : le thread lecteur
lève sur le premier caractère hors table, `stdout` revient à `None`, et le test échoue sur
un `TypeError` de `json.loads` alors que Node a rendu 0. Les neuf tests de
`test_web_seo.py` erraient ainsi en silence. Toujours passer `encoding="utf-8"`.

**Le panneau navigateur intégré ne rend RIEN si l'onglet n'est pas affiché.**
`document.hidden` vaut alors `true`, `requestAnimationFrame` ne se déclenche jamais, et le
runtime Observable ne calcule aucune cellule : toutes les pages restent en indicateurs de
chargement, y compris celles qu'on n'a pas touchées. Ce n'est pas un bug de page. Pour
vérifier une cellule dans ces conditions, importer le module directement
(`await import("/_import/components/hm.js")`) et l'appeler à la main. **C'est une piste
sérieuse pour l'intermittence des pages départementales** (voir plus haut) — non
démontrée, l'observation d'origine ayant été faite sur le site déployé.

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
| `main` | — | porte les DEUX axes de refactor, le site public, l'archive des prévisions ET les 101 pages départementales |
| `refactor/duckdb-storage` | 0 | axe stockage, fusionné par la PR #3 |
| `refactor/duckdb-engine` | 0 | axe compute, fusionné par la PR #2 |
| `fix/web-lisibilite` | 0 | correctifs de lisibilité du front web, fusionnés |
| `claude/code-audit-ocw25x` | 0 | reliquat, rien que `main` n'ait déjà |
| `claude/website-seo-accessibility-alr8mw` | 0 | site public : accueil rédigée, page À propos, métadonnées de partage/référencement, corrections d'accessibilité (voir « Le site public ») ; entrée dans `main` le 2026-08-20, portée par la fusion de `feat/pages-departementales` |
| `feat/pages-departementales` | 0 | prix au m² par département (DVF) : nettoyage testé, dataset `dvf`, 101 pages + sélecteur (voir « Les pages départementales ») ; fusionnée dans `main` en fast-forward le 2026-08-20 |
| `refactor/fusion-timelag-previsions` | 0 | fusion Time-Lag → Prévision, retrait Atelier + export SAP IBP (voir « Onglets retirés ») ; fusionnée dans `main` en fast-forward le 2026-08-20 |

Les six branches ci-dessus sont **entièrement contenues dans `main`** (`git merge-base
--is-ancestor` vérifié) : leurs copies locales ont été supprimées, il ne reste que les
copies distantes, à supprimer d'un `git push origin --delete`. `claude/duckdb-parquet-
refactor-p2-tvs0b2`, qui figurait ici, n'existe plus ni en local ni sur le distant.
