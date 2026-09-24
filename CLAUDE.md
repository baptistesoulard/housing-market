# CLAUDE.md — ce qu'il faut savoir avant de toucher au dépôt

Ce fichier dit l'ÉTAT COURANT et les RÈGLES. Il est chargé à chaque session : il doit rester
court. Le pourquoi détaillé, les mesures et l'historique vivent dans
[`docs/journal/`](docs/journal/) — un fichier par thème, entrées datées, jamais réécrites.

**Règle de tenue de ce fichier** : une règle ici, sa justification là-bas. Pas de chiffre
qui bouge avec les données (erreurs du modèle, décomptes d'épisodes, nombre de tests) :
ils dérivent, et c'est exactement ce qui a fait gonfler ce fichier jusqu'à 2 400 lignes
contradictoires. Une mesure datée va au journal.

## Le projet en une page

Site public **barometre-logement.com** (« Baromètre du Logement ») : conjoncture du
logement en France, prévision des ventes anciennes à 12-18 mois, archive des prévisions
face au réel, 101 pages départementales. Tout vient de sources publiques.

```
fetch_new_sources.py ─► data_manual_input/ ─► DataManager ─► data/*.csv (versionnés) + *.parquet (non)
                                                                   │
            queries.py (DuckDB, une vue par dataset) ◄─────────────┘
                  │
  analysis.py / forecast.py / api/engine.py
                  │
  web/export/web_export.py ─► web/observable/src/data/*.json ─► Observable Framework ─► Cloudflare Pages
```

- **Python** (racine) : acquisition, contrats pandera (`housing_data/`), agrégation SQL
  (`queries.py`), modèle (`forecast.py`), archive (`forecast_archive.py`), export
  (`web/export/`). `api/` est une API Flask **optionnelle** que plus aucune page n'appelle.
- **Site** (`web/observable/`, Node) : lit les JSON, se construit en HTML statique. Le
  seul code serveur est le formulaire de contact (`functions/api/contact.js`).
- **Job hebdomadaire** (`.github/workflows/refresh-data.yml`, lundi) : `fetch_new_sources.py`
  → `forecast_archive.py --record` → `web_export.py` → commit de `data_manual_input`, `data`,
  `web/observable/src/data`, `a-propos.md`, `index.md`. Le commit déclenche Cloudflare.
- L'app **Streamlit a été retirée le 2026-09-23** (journal 04). Ne pas la restaurer : le
  site est la seule interface.

## Commandes

```bash
python -m pytest tests/ -q                  # tout ; parité SQL sautée sans entrepôt, JS/SEO sans Node, API sans Flask
python web/export/web_export.py             # doit annoncer 0/8 et 0/102 si rien n'a bougé
python web/export/fond_de_carte.py          # réseau ; fond de carte des départements, à la main (rare)
npm --prefix web/observable run build       # → dist/ (observable build + scripts/postbuild.mjs)
npm --prefix web/observable run dev         # préversion ; ne sert PAS /data/departements/
python fetch_new_sources.py                 # réseau ; --sequential pour déboguer une source
python forecast_archive.py --backfill       # rejoue la rétro-simulation (jamais les lignes publiées)
python forecast_archive.py --calibrate      # recalibre la bande (deux passes, voir plus bas)
```

## L'export du site (`web/export/`)

| Module | Rôle |
|---|---|
| `web_export.py` | orchestration seule : charger, un constructeur par page, écrire ce qui a changé |
| `page_synthese.py` | `faits()` (seule fonction qui lit l'entrepôt) → `rediger()` (phrases, pastilles) |
| `page_marches.py`, `page_contexte.py`, `page_previsions.py`, `page_archive.py`, `page_departements.py`, `page_carte.py` | une page (ou deux jumelles) chacun |
| `commun.py` | mise en forme FR (`pct`, `pt`, `milliers`, `abrege`, `mois_annee`), palette, chemins |
| `mesures.py` | faits partagés entre pages (stock neuf, taux de transformation) — un calcul, un chiffre |
| `verdict.py` | verdict du modèle et sa fiabilité, partagés par Synthèse, Prévision et accueil |
| `reperes.py` | **tout ce que rien ne régénère** : repères saisis à la main et mesures datées |
| `ecriture.py` | point d'écriture unique : arrondi à 9 chiffres significatifs, garde de contenu |
| `sources_table.py`, `accueil.py` | Markdown réécrit entre marqueurs (`a-propos.md`, `index.md`) |
| `fond_de_carte.py` | outil ponctuel : fond de carte des départements, versionné (`departements-geo.json`) |

Règles :

- **Le compteur « n/8 fichier(s) modifié(s) » est une alarme.** Un diff inattendu sur un
  JSON national signale une divergence de calcul. Un refactor doit laisser `0/8` et
  `0/102` ; une régénération délibérée se dit dans le commit. Les départements et le
  Markdown réécrit sont comptés à part, exprès.
- **L'arrondi (`ecriture.arrondir_flottants`) est ce qui rend ce compteur fiable** entre
  Linux (CI) et Windows : en chiffres significatifs (pas en décimales), à 9, jamais sur
  les entiers ni les booléens (journal 02).
- **La rédaction ne lit pas de données.** Toute nouvelle phrase de la Synthèse passe par
  `rediger(faits)`, testable sur des faits fabriqués (`tests/test_redaction.py`).
- **Typographie** : espace avant « % » et « pt », jamais de zéro signé (« 0,0 », pas
  « -0,0 »). Les deux règles vivent dans `commun._variation` ; ne pas formater une
  variation à la main.
- **Le signe arithmétique et le signe ressenti pointent dans le même sens** : un manque
  se dit « manquent à l'appel », pas « de plus » (test + contre-épreuve). Et ne pas
  retourner une formulation juste pour frapper plus fort : c'est un choix d'auteur.
- **Les champs `title`/`caption` des JSON ne sont plus lus par le site** (les chapeaux sont
  statiques). Les retirer se fait dans une régénération délibérée, pas au détour d'autre
  chose.

## Texte statique : aucun chiffre, aucun état

Accueil, À propos, mentions légales et les chapeaux de toutes les pages sont du **HTML
rendu au build** : c'est le seul texte que lisent les robots d'aperçu de partage (aucun
n'exécute de JavaScript), et le seul qui reste quand Google abandonne un module.

- **Test avant d'écrire une phrase statique : serait-elle encore vraie dans un an ?** Si la
  réponse dépend des données, elle appartient au générateur. Un chapeau peut geler le
  présent sans écrire un seul nombre (« le collectif s'est retourné »).
- **Les seules exceptions sont GÉNÉRÉES** et ne s'éditent jamais à la main : le tableau des
  sources d'À propos (`sources_table.py`), les deux affirmations chiffrées de l'accueil —
  erreur du modèle et horizon de bascule — (`accueil.py`), le chapeau chiffré des 101
  pages départementales et le tableau des départements de la page carte
  (`scripts/postbuild.mjs`, à chaque build). Les marqueurs `hm:*` délimitent ce qui est
  réécrit.
- **Jamais de `# ${…}`** ni de chapeau interpolé : ≥ 40 mots statiques avant la première
  section (`tests/test_web_structure.py`).
- **Corriger un chiffre dans la doc ne le corrige pas sur le site** : `grep` la valeur dans
  `web/observable/src/` et `site.config.js` (meta descriptions) aussi.
- **Deux conventions d'horizon coexistent, chacune doit se nommer** : l'archive et ses
  tableaux comptent depuis le dernier mois de DONNÉES ; le verdict, la Synthèse et le
  bandeau de l'accueil comptent en mois devant le LECTEUR. Quand deux mesures voisines
  n'ont pas la même étendue, chacune dit la sienne.

## Données et calcul

- **Le Parquet est le chemin de lecture, le CSV la copie versionnée et le repli.**
  `warehouse.resolve()` ne retient un Parquet que s'il est au moins aussi récent que son
  CSV (un `git pull` qui apporte des CSV frais bascule donc en repli CSV — voulu).
- **`read_frames()` / `load_or_generate_all()` rendent QUATRE frames, déballées par
  POSITION** : sitadel, ventes_ancien, macro, ecln. `dvf` et `territoires` ne rejoignent
  jamais ce tuple : SQL uniquement (l'export les relit à part pour le tableau des
  sources). Ajouter ou retirer un dataset du tuple oblige à relire tous les déballages
  (`web_export.load_frames`, `forecast_archive` et `api/engine` qui lisent `[2]`). Les
  ventes second œuvre synthétiques (`sales`) et les ventes société (`company_sales`) en
  sont sorties le 2026-09-23, faute de consommateur (journal 01).
- **Un dataset sans consommateur se retire.** Il coûte un contrat, une vue SQL, un CSV
  commité chaque semaine et une ligne de chaque déballage ; `git` le garde.
- **`queries.py` est la porte unique des agrégations.** Les agrégateurs d'`analysis.py`
  (`aggregate_*`, `calculate_rolling*`) et `forecast.build_target` ne sont plus appelés :
  ce sont les **références** de `tests/test_queries_parity.py`. Ne pas les supprimer.
- **Une requête = un curseur** (`queries._cur(con)`), jamais `con.execute` sur une
  connexion partagée : sous concurrence, deux threads se volent leur résultat et le
  symptôme est un DataFrame bien formé et FAUX (`tests/test_queries_concurrency.py`).
- **Base 100 = moyenne annuelle 2015**, via `analysis.base_100()`, qui refuse une année
  incomplète.
- **Régime de lecture selon la série** (`analysis.headline_momentum`) : SIT@DEL et ECLN
  sont CVS-CJO → momentum séquentiel (3 mois vs 3 précédents), jamais comparés à n-1 ;
  l'IGEDD (reconstruite d'un cumul) → 12 mois + `plateau_months`. Chaque carte porte le
  momentum ET le niveau (`level_context`, référence `LEVEL_REF_YEARS` = 2010-2019, qui
  sert aussi au taux de transformation).
- **`DelaiEcoulement` (ECLN) est en TRIMESTRES** : ×3 pour des mois.
- **Surfaces SIT@DEL** : les séries CVS de surface ne sont pas additives ; l'entrepôt garde
  la somme des 4 types (≈ 0,8 % sous le total SDES, voulu).
- **Ce qui reste en pandas y reste exprès** : `forecast.build_target` (référence),
  `tx12.resample("QS")` (transformation du modèle), les `groupby("Date").sum()` défensifs
  de `fit_tx_to_monthly`.
- **`api/engine.py` n'importe jamais Flask** (c'est ce qui permet à l'export de l'appeler
  en Python). Aucune logique métier dans `routes.py`. Dates `YYYY-MM-DD`, jamais de `NaN`
  dans une réponse.
- **Calculs en double Python/JS, à garder alignés** : `forecast.best_tx_to_monthly` ↔
  `bestLagFit`, `forecast.scenario` ↔ `computeScenario` (`src/components/api.js`),
  vérifiés par `tests/test_web_js_parity.py`. Le CSV de ventes d'un visiteur ne quitte
  jamais son navigateur.

## Le modèle de prévision et l'archive

Détail et mesures : journal 06.

- **Deux natures de lignes, jamais agrégées ensemble** : `archive` (publiée le jour même,
  intouchable) et `retro` (recalculée après coup). Tout chiffre publié dit laquelle.
- **Ce qui est publié ne se réécrit pas.** `--backfill` rejoue les `retro`, jamais les
  `archive`. Le réalisé n'est pas stocké (joint à la lecture, la source révise) ; la
  référence naïve, elle, est stockée.
- **La référence naïve est toujours publiée à côté.** Le modèle perd contre elle aux
  horizons courts ; la page le montre, c'est le propos.
- **Fenêtre de rétro-simulation : depuis 2009** (`BACKFILL_START`), pas 2022 — la fenêtre
  courte ne couvre que l'épisode que le modèle réussit le mieux.
- **Recalage sur le dernier point observé** (`anchor_of`, `FADE_MONTHS = 9`) : 9 est le
  milieu d'un plateau mesuré, ne pas « l'optimiser ».
- **La bande est calibrée sur l'archive** (quantiles 10/90 de l'erreur SIGNÉE par
  horizon, `data/forecast_band.csv`). `--calibrate` fait deux passes dans cet ordre ; un
  horizon vu moins de 20 fois retombe sur la bande constante.
- **Étage 1** : taux de crédit ~ OAT 10 ans décalée (`RATE_DRIVER`, décalage cherché).
  L'Euribor en est sorti le 2026-08-25 (dégradait hors échantillon) mais reste une série
  publiée. **Étage 2** : ventes ~ taux + intentions d'achat + chômage, décalés. Fenêtre
  d'entraînement extensible (mesuré meilleure que glissante) ; prédicteurs reportés à plat
  au-delà de leur dernier point (mesuré meilleur que les anticipations de marché).
- **Porte d'entrée d'un prédicteur** : ≥ 5 % d'erreur évitée HORS échantillon sur ≥ 3 des
  4 blocs d'horizon (1-3, 4-6, 7-12, 13-18), mesurée APRÈS le recalage. Jamais sur le R².
  Les idées refusées sont publiées dans `reperes.REFUTATIONS` : ne pas les re-tester sans
  raison nouvelle. `forecast.py` garde ses trois colonnes en dur tant qu'aucun quatrième
  prédicteur ne passe.
- **Le verdict vise un mois à six mois du LECTEUR** (`verdict.MOIS_DEVANT`), borné par
  `HORIZON_MIN` (en deçà, la naïve fait mieux) et par `informative_months` (au-delà, la
  trajectoire se répète). Allonger l'horizon flatte la fiabilité : ce n'est jamais un motif.
- **Pas de R² en carte de tête** (résidus autocorrélés) ; les écarts-types Newey-West
  publiés sont une borne basse, pas la mesure de l'incertitude.
- **Les permis ne précèdent pas les mises en chantier** dans cette série (mesuré puis
  réfuté) : le site publie un taux de transformation, pas une prévision du neuf.

## Le front (`web/observable/`)

- **`site.config.js` est la source unique d'identité** (URL, titres, descriptions, NAV,
  logo), lue par le `<head>`, `postbuild.mjs` et les tests. `observablehq.config.js` ne
  porte que le rendu. Aucune URL d'hébergement en dur : `HM_SITE_URL`, repli sur le domaine.
- **Les pages n'importent jamais `npm:`** : tout passe par `src/components/hm.js`, qui pose
  aussi la **locale française de d3** (graduations « 1 000 », mois « janv. »). Vignettes :
  `{...TIP}` en option de marque, jamais en CSS. `multiLine` pose sa légende dès deux
  séries.
- **Cinq façons de faire disparaître du contenu sans que le build le dise**, toutes
  couvertes par `tests/test_web_structure.py` : `viewof` (syntaxe notebook), erreur de
  syntaxe dans une cellule, identifiant non importé, bloc ```` ```js ```` collé sous un
  `<div>` sans ligne vide, `display()` d'un `` html`` `` vide (affiche `null`). Et un
  `${…}` n'est interpolé que dans le CONTENU d'un élément, jamais dans un attribut brut.
- **Accent grave dans un littéral gabarit** (le CSS de `observablehq.config.js`, un
  commentaire HTML dans une cellule) : il referme la chaîne. Ne jamais citer un
  identifiant entre accents graves à ces endroits.
- **Neuf et ancien sont jumelles** : mêmes sections de tête, même intitulé, même ordre,
  renvois croisés. Le socle garantit la forme, pas le sens — quand ils divergent, le
  sens gagne.
- **Pages départementales** : une route paramétrée (`src/departement/[code].md`) ;
  `FileAttachment` n'y marche pas (vérifié), les données sont copiées par `postbuild.mjs` à
  `/data/departements/<code>.json` et lues par `fetch()`. Budget 10 Ko par fichier ; les 4
  départements hors DVF (57, 67, 68, 976) ont une page qui explique l'absence. Pas de
  prévision régionalisée.
- **Carte des départements** (`carte.md`, `page_carte.py`, `carteDepartements` et
  `nuageDepartements` dans `hm.js`) : elle DÉCRIT, elle ne classe pas — pas de score, pas
  de « gagnants » (la porte Territoires a été manquée, journal 07 ; la page le montre).
  Couleurs validées dans `web/theme.json` (`carte`) : une teinte pour une grandeur (classes
  de quantiles), deux teintes et un gris au pivot pour un écart, HACHURES pour « non
  renseigné » (un gris plein se lirait « zéro »). Le fond de carte est versionné et
  pré-tourne ses encarts pour la projection de `hm.js` : les deux doivent rester alignés
  (`tests/test_carte.py`). `components/theme.js` est GÉNÉRÉ : un nom ajouté au thème sans
  régénération casse toutes les pages dans le navigateur, sans erreur de build
  (`test_theme_js_est_a_jour_de_theme_json`).
- **Le formulaire de contact** : l'adresse de destination n'entre JAMAIS dans le dépôt
  (`CONTACT_TO`, `RESEND_API_KEY` côté Cloudflare) ; sans elles la route répond 503.
- **Rien ne teste le RENDU.** Vérifier sur le site construit (`dist/`). Le panneau
  navigateur intégré, masqué, n'exécute aucune cellule (`document.hidden`) : importer
  alors le module construit (`/_import/components/hm.<hash>.js`) et l'appeler à la main.

## Pièges du poste de travail (Windows)

- **Un `cd` en tête de commande persiste** pour les suivantes : chemins absolus, ou
  sous-shell `( cd … && … )`.
- **Scripts Python qui éditent du texte contenant des échappements** : ils écrivent des
  `\n` littéraux ou de vraies nouvelles lignes au mauvais endroit (arrivé encore le
  2026-09-23 dans le workflow). Préférer l'outil d'édition.
- **`subprocess.run(text=True)` décode en cp1252** : toujours `encoding="utf-8"` pour Node.
- **La console est en cp1252** : `PYTHONIOENCODING=utf-8` pour imprimer des émojis.
- `core.autocrlf=true` : les fichiers écrits en CRLF sont normalisés au commit.

## Dette connue, par ordre d'intérêt

- **Le délai anti-spam du formulaire est déclaré par le client** (`_t`) : un script qui
  poste directement le contourne, et il n'y a pas de limite de débit. Une règle de
  limitation de débit Cloudflare sur `/api/contact` suffit, sans code.
- **`DataManager.data_signature()` n'a plus de consommateur à l'exécution** (il servait
  de clé de cache à Streamlit) ; il reste testé.
- **Chapeaux et `how_to_read`** (chaînes littérales de l'export) n'ont aucune garde contre
  la dérive, hors le seuil de mots.
- **Surfaces SIT@DEL** dans l'entrepôt mais pas publiées (lot B : publier l'effet de mix,
  pas le seul total) ; **tertiaire** non intégré (lot C, lecture SQL seulement, fenêtre
  depuis 2013). Détails : journal 05.

## Branches

Une seule branche, `main`. Pour savoir s'il reste quelque chose à fusionner, se fier à
`git branch -r` et `git rev-list --left-right --count`, jamais à une liste écrite ici.

## Le journal (`docs/journal/`)

| Fichier | Contenu |
|---|---|
| `01-refactors-duckdb.md` | axes stockage et compute, phases, garde de fraîcheur |
| `02-invariants-historique.md` | l'histoire des invariants : concurrence, base 100, arrondi du JSON |
| `03-api-http.md` | l'API, puis son abandon côté pages ; retrait du benchmark de CA |
| `04-app-streamlit.md` | les onglets retirés en août, puis le retrait de l'app |
| `05-site-public.md` | site public, SEO, Synthèse, pages de marché, audits de rédaction |
| `06-prevision-et-archive.md` | modèle, archive, bande, étage 1, prédicteurs testés, page de prévision |
| `07-pages-departementales.md` | DVF, filtre, budget, courbe nationale, module Territoires |
| `08-verification-et-branches.md` | recettes de parité, historique des branches |
