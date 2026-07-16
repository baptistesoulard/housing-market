# HousingMarket — Market Intelligence Immobilier

Dashboard **Streamlit** d'analyse conjoncturelle du marché immobilier français (national) et d'aide à la prévision. Il met en regard la construction neuve (SIT@DEL / SDES), la commercialisation du neuf (ECLN), les ventes dans l'ancien (IGEDD), les prix (Notaires-INSEE), l'accessibilité, le contexte macro-financier (confiance, taux, Euribor, OAT, intentions d'achat, chômage, volume et demande de crédits) et un module de **prévision des transactions** avec scénarios.

L'outil permet aussi d'**importer les ventes mensuelles d'une société** (CSV) pour les corréler aux indicateurs de marché dans les moteurs Time-Lag / Composite / Prévision, et de **générer un bilan PDF** (chiffres clés, commentaire d'analyse, graphiques, repère BPCE) depuis la barre latérale.

## Aperçu des onglets

0. **Synthèse** — page d'accueil : lecture « feu tricolore » (🟢/🟠/🔴) de 6 signaux (permis, mises en chantier, ventes anciennes, taux de crédit, demande BLS, ventes 12 m vs cible BPCE), commentaire d'analyse auto-généré et fraîcheur des données par source. Chiffres nationaux, indépendants du filtre de période.
1. **Conjoncture rétrospective** — permis, mises en chantier et ventes dans l'ancien (cumuls 12/6 mois, brut, moyennes mobiles, comparaison mensuelle par année), **KPI de glissement** (3 derniers mois vs n-1), **commentaire d'analyse auto-généré** sous les chiffres clés et **dynamique Individuel vs Collectif** (driver du second œuvre).
2. **Contexte Macro & Financement** — confiance des ménages, taux de crédit / Euribor / OAT (togglables), intentions d'achat, chômage BIT, **volume de crédits à l'habitat** (production mensuelle + cumul 12 mois) et **demande de crédits (enquête BLS)** — indicateur avancé.
3. **Prix & Accessibilité** — indices de prix des logements anciens (Notaires-INSEE) et **neufs** (INSEE), glissement annuel, **capacité d'emprunt** (à mensualité constante) et **indice d'accessibilité** (capacité ÷ prix).
4. **Commercialisation Neuf (ECLN)** — encours & mises en vente, délai d'écoulement, **réservations par catégorie d'acquéreurs** (particuliers / bailleurs sociaux / investisseurs institutionnels), prix au m².
5. **Prévision & Scénarios** — modèle à deux étages *taux de crédit ~ OAT + Euribor* puis *transactions ~ taux + intentions + chômage* (décalés, **lags cherchés sur le train seul**), **backtest hors échantillon**, **projection mensuelle à horizon 12-18 mois** (partie « sans hypothèse » tant que les indicateurs décalés sont déjà observés, puis extension par report avec repère visuel et bande ±1,28·RMSE ; **exportable vers SAP IBP**), **propagation à une prévision mensuelle des ventes société** par famille (également exportable), **rénovation en 3ᵉ driver** (comparatif R² transactions seules vs transactions+rénovation), **repère BPCE L'Observatoire 2026**, et panneau de scénarios à 4 leviers (OAT / Euribor / chômage / **intentions d'achat** → transactions → CA benchmark).
6. **Atelier — Time Lag** — atelier exploratoire : décalage d'un indicateur avancé et corrélation avec les ventes (ou un CA d'entreprise réel).
7. **Atelier — Composite** — atelier exploratoire : indicateur composite pondéré (grid-search des lags/poids).
8. **Export SAP IBP** — export de l'indicateur avancé.
9. **Données Source** — inspection / upload des jeux de données (les uploads sont **validés par les contrats pandera** avant écrasement), et **import des ventes mensuelles d'une société** (CSV `Date, Sales` — **multi-séries** : une colonne `Serie`/`Produit`/`Famille` crée une famille de produits par valeur, sélectionnable dans les moteurs). Ces ventes réelles sont la **cible par défaut** des ateliers Time-Lag / Composite / Prévision (les ventes synthétiques ne servent que de repli, avec avertissement de circularité).

## Lancer en local

```bash
pip install -r requirements.txt
streamlit run app.py
```

L'application s'ouvre sur http://localhost:8501.

## Données

Toutes les séries de `data/` sont **réelles**, issues de sources publiques officielles (seules les ventes de produits second-œuvre restent synthétiques et anonymisées — 3 familles génériques). L'acquisition des séries les plus récentes est scriptée dans **`fetch_new_sources.py`** (hors-runtime, via `urllib` de la bibliothèque standard) ; l'application, elle, ne fait aucun appel réseau.

| Indicateur | Source | Accès |
|---|---|---|
| Ventes dans l'ancien (cumul 12 m) | IGEDD | fichier `.xls` |
| Logements autorisés / commencés (SIT@DEL) | SDES | data.gouv.fr |
| Commercialisation des logements neufs (ECLN : réservations, mises en vente, encours, délai, prix, acquéreurs) | SDES | data.gouv / API DiDo |
| Prix des logements anciens (Notaires-INSEE) & neufs | INSEE | API SDMX BDM |
| Confiance des ménages, intentions d'achat, chômage BIT | INSEE | API SDMX BDM |
| Taux de crédit habitat & **volume de crédits** (décomposé hors renégociations / renégociations) | Banque de France / BCE | API SDMX BCE (MIR) |
| **Demande de crédits habitat** (enquête BLS, réalisé + perspectives 3 mois) | BCE / Banque de France | API SDMX BCE (BLS) |
| Euribor 3 mois, OAT 10 ans | BCE | API SDMX BCE |
| **Activité du second œuvre** (rénovation — activité passée & prévue) | INSEE (enquête conjoncture bâtiment) | API SDMX BDM |

Les identifiants de séries (idbanks INSEE, clés BCE, ressources DiDo) sont documentés dans [`data_manual_input/Data source.txt`](data_manual_input/Data%20source.txt).

Les **ventes mensuelles d'une société** importées via l'onglet Données Source sont des **données utilisateur** (stockées dans `data/company_sales.csv`, non versionnées / `.gitignore`) ; elles ne sont pas une source publique. Le **rapport PDF** est généré localement (aucun appel réseau).

## Limitations connues & feuille de route

Audit du système de données (2026-07-15). Le pipeline est robuste sur le fond (sources réelles, provenance tracée, gestion NaN honnête, cache par `mtime`, reconstruction IGEDD exacte). Les points ci-dessous restent à traiter, par priorité.

### P0 — correction & fiabilité de base

- ✅ **Cohérence ventes ↔ transactions (résolu 2026-07-15).** Les ventes synthétiques de second œuvre sont désormais construites (`build_sales`) à partir des **permis SIT@DEL réels** et des **transactions IGEDD réelles** — la série que l'app affiche —, via la série des ventes anciennes réelle (IGEDD) chargée *avant* la génération des ventes. L'ancienne série de transactions synthétique (jetée) et `macro_model` ont été supprimés. Corrélation « Sécurité & Domotique » ↔ IGEDD décalé 2 mois = 0,99.
- ✅ **Couverture temporelle alignée (résolu 2026-07-15).** Plus de `date_range` hardcodé : `generate_sitadel_and_macro` dérive la borne de la donnée réelle (SIT@DEL + buffer, puis trim des mois de queue tout-NaN → macro se termine sur la dernière observation réelle, ex. 2026-06 pour confiance/Euribor/OAT/intentions) ; `build_sales` est borné à `min(SIT@DEL, IGEDD)` (2026-05) — plus aucun mois fabriqué sans donnée marché.
- ✅ **Validation de schéma sur les uploads (résolu 2026-07-16).** `update_with_custom_csv` et `import_company_sales` valident désormais la donnée contre le contrat pandera (`hd.validate(..., lazy=False)`) avant écriture : un fichier aux bonnes colonnes mais au contenu invalide (NaN parasite, compte négatif, ligne non-nationale, doublon Date/Type, catégorie inconnue) est rejeté avec un message clair au lieu de casser un onglet plus loin. Reste ouvert : un vrai `logging` fichier (les `print` et les tuples `(bool, message)` subsistent).

### P1 — consolidation

- ✅ **Tests automatisés (résolu 2026-07-16).** `tests/test_logic.py` couvre les invariants clés : reproduction IGEDD (dérive ≤ 12 sur le cumul 12 m), `momentum_metrics`, `calculate_kpis`, `ols`/`scenario`, et `forecast_path` (horizon + report). Standalone ou pytest, comme `tests/test_housing_data.py`.
- **Métadonnée de provenance** : un `data/_manifest.json` (série → source, dernière date, horodatage du build) affiché dans l'onglet Données Source.
- **Bouton « Reconstruire la macro »** dans l'onglet Données Source, symétrique des boutons IGEDD / ECLN existants.
- **Loader IGEDD fragile** : indices de colonnes en dur (`DATE_COL=1`, `VALUE_COL=3`, nom de feuille) — à fiabiliser (détection d'en-têtes).

### P2 — refonte de fond

- **Registre de sources unique** : centraliser `série → {fichier, colonne, fréquence, clé SDMX}` dans un seul dict partagé par `fetch_new_sources.py` et `data_manager.py` (aujourd'hui dupliqué → risque de dérive).
- **Stockage macro en format long** (`[Date, série, valeur, fréquence]`) : `macro.csv` est aujourd'hui un format large ~35 % NaN (séries trimestrielles réindexées en mensuel).
- **Versionnement des données** : snapshots horodatés avant écrasement, plutôt qu'une réécriture en place.
- **Dernière série synthétique** : remplacer les ventes second œuvre par un proxy réel (seul maillon non réel restant). ✅ **Pilier rénovation actif (2026-07-16)** : 2 séries INSEE réelles (activité passée/prévue du second œuvre, idbanks 001586954/001586886) branchées comme 2ᵉ facteur du modèle de ventes — le mécanisme de remplacement du synthétique est en place ; reste à disposer de vraies ventes Somfy pour retirer `build_sales`.

### Réalisés le 2026-07-16 (première vague)

- **Cache de chargement** : `read_frames()` + `@st.cache_data` keyé sur les mtimes → plus de relecture des CSV ni de réécriture des 7 Parquet à chaque interaction (le miroir entrepôt ne tourne qu'à la (re)génération).
- **Ventes société multi-séries** : format `[Date, Company, Serie, Sales]`, sélecteur de famille de produits dans les 3 moteurs ; cible réelle par défaut + avertissement de circularité sur le synthétique.
- **Prévision à horizon** (voir onglet 5) et **export SAP IBP** de cette prévision.
- **Page Synthèse** feu-tricolore (onglet 0).
- **Extraction i18n** : dictionnaire `T` sorti dans `translations.py` ; étiquettes corrigées (catégorie « Ventes second-œuvre (synthétiques) », texte de reset, clés mortes de la carte supprimées).

### Réalisés le 2026-07-16 (seconde vague — robustesse & pertinence)

- **Anti-fuite / anti-overfit** : (e3) recherche de décalages du modèle de transactions sur le **train uniquement** (`search_tx_lags(split=)`) — le MAPE hors échantillon n'est plus flatté ; (e2) l'**optimiseur composite** sélectionne sur un **split train/test** et affiche le **r hors échantillon** (le seul honnête sur ~9 500 combinaisons) ; (e1) l'atelier Time-Lag affiche la **corrélation sur variations annuelles** + le **n de points** à côté du r sur niveaux, avec avertissement d'auto-corrélation quand l'indicateur est lissé ; (e4) **slider « Intentions d'achat »** ajouté au panneau de scénarios (3ᵉ prédicteur enfin pilotable).
- **Prévision mensuelle des ventes société** : `forecast.propagate_to_series` propage la trajectoire de transactions projetée à travers l'élasticité estimée → prévision par famille + bande, **exportable SAP IBP** (4ᵉ source d'export).
- **Pilier rénovation comme 3ᵉ driver — ACTIF (2026-07-16)** : deux séries **réelles** INSEE (Enquête mensuelle de conjoncture dans l'industrie du bâtiment, **second œuvre**, CVS, mensuel 1975→2026-06) — activité **passée** (idbank 001586954) et **prévue** (001586886, avancée). Affichées dans l'onglet Contexte Macro (section « Rénovation & second œuvre »), pastille Synthèse, et 2ᵉ facteur du modèle `forecast.fit_sales_two_factor` (ventes ~ transactions + rénovation) — comparatif R² dans l'onglet Prévision. Acquisition : `fetch_new_sources.build_renovation()`. Enrichissement futur possible : un proxy de volume (MaPrimeRénov'/éco-PTZ).
- **Import versionné des ventes** : `data_manual_input/ventes-<famille>.csv` (comme `ca-*.csv`), ingérés automatiquement quand aucun upload ad-hoc n'est présent ; **table récap « une famille = un décalage »** dans l'onglet Prévision.
- **Tests étendus** (`tests/test_logic.py`, 10 tests) : anti-fuite du lag search, propagation ventes, modèle 2 facteurs, split de l'optimiseur composite.

## Modules

- `app.py` — interface Streamlit (10 onglets dont la Synthèse, bilingue FR/EN).
- `translations.py` — dictionnaire de traductions `T` (FR/EN) extrait d'`app.py`.
- `data_manager.py` — chargement / génération / cache des jeux de données (dont import des ventes société).
- `analysis.py` — filtres, agrégations, cumuls glissants, momentum et commentaire d'analyse auto-généré.
- `simulation.py` — décalage temporel et indicateur composite.
- `forecast.py` — modèles de prévision (OLS taux + transactions, backtest, scénarios, élasticité transactions→CA/ventes).
- `export.py` — export SAP IBP.
- `fetch_new_sources.py` — acquisition des sources réelles (INSEE / SDES / BCE).
- `report.py` — génération du **rapport PDF** (bilan : chiffres clés, commentaire, graphiques, repère BPCE) via reportlab + matplotlib. Bouton « 📄 Rapport PDF » dans la barre latérale.

## Stack

Python · Streamlit · pandas · numpy · plotly · xlrd · matplotlib · reportlab
