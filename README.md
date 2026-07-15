# HousingMarket — Market Intelligence Immobilier

Dashboard **Streamlit** d'analyse conjoncturelle du marché immobilier français (national) et d'aide à la prévision. Il met en regard la construction neuve (SIT@DEL / SDES), la commercialisation du neuf (ECLN), les ventes dans l'ancien (IGEDD), les prix (Notaires-INSEE), l'accessibilité, le contexte macro-financier (confiance, taux, Euribor, OAT, intentions d'achat, chômage, volume de crédits) et un module de **prévision des transactions** avec scénarios.

## Aperçu des onglets

1. **Conjoncture rétrospective** — permis, mises en chantier et ventes dans l'ancien (cumuls 12/6 mois, brut, moyennes mobiles, comparaison mensuelle par année), **KPI de glissement** (3 derniers mois vs n-1) et **dynamique Individuel vs Collectif** (driver du second œuvre).
2. **Contexte Macro & Financement** — confiance des ménages, taux de crédit / Euribor / OAT (togglables), intentions d'achat, chômage BIT, **volume de crédits à l'habitat** (production mensuelle + cumul 12 mois) et **demande de crédits (enquête BLS)** — indicateur avancé.
3. **Prix & Accessibilité** — indices de prix des logements anciens (Notaires-INSEE) et **neufs** (INSEE), glissement annuel, **capacité d'emprunt** (à mensualité constante) et **indice d'accessibilité** (capacité ÷ prix).
4. **Commercialisation Neuf (ECLN)** — encours & mises en vente, délai d'écoulement, **réservations par catégorie d'acquéreurs** (particuliers / bailleurs sociaux / investisseurs institutionnels), prix au m².
5. **Prévision & Scénarios** — modèle à deux étages *taux de crédit ~ OAT + Euribor* puis *transactions ~ taux + intentions + chômage* (décalés), **backtest hors échantillon**, **repère des prévisions publiées BPCE L'Observatoire 2026**, et panneau de scénarios (OAT / Euribor / chômage → transactions → chiffre d'affaires benchmark).
6. **Atelier — Time Lag** — atelier exploratoire : décalage d'un indicateur avancé et corrélation avec les ventes (ou un CA d'entreprise réel).
7. **Atelier — Composite** — atelier exploratoire : indicateur composite pondéré (grid-search des lags/poids).
8. **Export SAP IBP** — export de l'indicateur avancé.
9. **Données Source** — inspection / upload des jeux de données.

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
| Taux de crédit habitat & **volume de crédits nouveaux** | Banque de France / BCE | API SDMX BCE (MIR) |
| Euribor 3 mois, OAT 10 ans | BCE | API SDMX BCE |

Les identifiants de séries (idbanks INSEE, clés BCE, ressources DiDo) sont documentés dans [`data_manual_input/Data source.txt`](data_manual_input/Data%20source.txt).

## Limitations connues & feuille de route

Audit du système de données (2026-07-15). Le pipeline est robuste sur le fond (sources réelles, provenance tracée, gestion NaN honnête, cache par `mtime`, reconstruction IGEDD exacte). Les points ci-dessous restent à traiter, par priorité.

### P0 — correction & fiabilité de base

- **🔴 Cohérence ventes ↔ transactions.** Les ventes synthétiques de second œuvre (famille « Sécurité & Domotique ») sont calées sur les transactions **synthétiques** de `generate_historical_data`, ensuite jetées, alors que l'app affiche les ventes **IGEDD réelles**. À recaler sur la série IGEDD réelle. *(Les familles « Fermetures » et « Équipements » sont déjà calées sur les permis SIT@DEL réels.)*
- **🟠 Couverture temporelle désalignée.** `sitadel` va jusqu'à 2026-05, `macro`/`sales` jusqu'à 2026-06 (mois « fantôme » NaN) ; aligner le `date_range` sur l'étendue réelle des données.
- **🟠 Validation de schéma & logging.** Aucun contrôle au chargement (types, dates mensuelles uniques/ordonnées, doublons, plages plausibles) ; `update_with_custom_csv` ne couvre que 4 catégories sur 6 (pas `ecln`/`revenue`). Ajouter un validateur léger exécuté au chargement + un `logging` fichier (remplacer les `print` et les erreurs avalées dans les tuples `(bool, message)`).

### P1 — consolidation

- **Tests automatisés (`pytest`)** sur les invariants : reproduction IGEDD (erreur 0), réindexation macro, helpers `momentum_metrics` / `calculate_rolling`.
- **Métadonnée de provenance** : un `data/_manifest.json` (série → source, dernière date, horodatage du build) affiché dans l'onglet Données Source.
- **Bouton « Reconstruire la macro »** dans l'onglet Données Source, symétrique des boutons IGEDD / ECLN existants.
- **Loader IGEDD fragile** : indices de colonnes en dur (`DATE_COL=1`, `VALUE_COL=3`, nom de feuille) — à fiabiliser (détection d'en-têtes).

### P2 — refonte de fond

- **Registre de sources unique** : centraliser `série → {fichier, colonne, fréquence, clé SDMX}` dans un seul dict partagé par `fetch_new_sources.py` et `data_manager.py` (aujourd'hui dupliqué → risque de dérive).
- **Stockage macro en format long** (`[Date, série, valeur, fréquence]`) : `macro.csv` est aujourd'hui un format large ~35 % NaN (séries trimestrielles réindexées en mensuel).
- **Versionnement des données** : snapshots horodatés avant écrasement, plutôt qu'une réécriture en place.
- **Dernière série synthétique** : remplacer les ventes second œuvre par un proxy réel (seul maillon non réel restant).

## Modules

- `app.py` — interface Streamlit (9 onglets, bilingue FR/EN).
- `data_manager.py` — chargement / génération / cache des jeux de données.
- `analysis.py` — filtres et agrégations.
- `simulation.py` — décalage temporel et indicateur composite.
- `forecast.py` — modèles de prévision (OLS taux + transactions, backtest, scénarios).
- `export.py` — export SAP IBP.
- `fetch_new_sources.py` — acquisition des sources réelles (INSEE / SDES / BCE).

## Stack

Python · Streamlit · pandas · numpy · plotly · xlrd
