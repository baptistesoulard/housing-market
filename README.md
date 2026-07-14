# HousingMarket — Market Intelligence Immobilier

Dashboard **Streamlit** d'analyse conjoncturelle du marché immobilier français (national) et d'aide à la prévision. Il met en regard la construction neuve (SIT@DEL / SDES), la commercialisation du neuf (ECLN), les ventes dans l'ancien (IGEDD), les prix (Notaires-INSEE), l'accessibilité, le contexte macro-financier (confiance, taux, Euribor, OAT, intentions d'achat, chômage, volume de crédits) et un module de **prévision des transactions** avec scénarios.

## Aperçu des onglets

1. **Conjoncture rétrospective** — permis, mises en chantier et ventes dans l'ancien (cumuls 12/6 mois, brut, moyennes mobiles, comparaison mensuelle par année).
2. **Contexte Macro & Financement** — confiance des ménages, taux de crédit / Euribor / OAT (togglables), intentions d'achat, chômage BIT, et **volume de crédits à l'habitat** (production mensuelle + cumul 12 mois).
3. **Prix & Accessibilité** — indices de prix des logements anciens (Notaires-INSEE) et **neufs** (INSEE), glissement annuel, **capacité d'emprunt** (à mensualité constante) et **indice d'accessibilité** (capacité ÷ prix).
4. **Commercialisation Neuf (ECLN)** — encours & mises en vente, délai d'écoulement, **réservations par catégorie d'acquéreurs** (particuliers / bailleurs sociaux / investisseurs institutionnels), prix au m².
5. **Prévision & Scénarios** — modèle à deux étages *taux de crédit ~ OAT + Euribor* puis *transactions ~ taux + intentions + chômage* (décalés), **backtest hors échantillon**, et panneau de scénarios (OAT / Euribor / chômage → transactions → chiffre d'affaires benchmark).
6. **Simulation Time Lag** — décalage d'un indicateur avancé et corrélation avec les ventes (ou un CA d'entreprise réel).
7. **Modèle Composite** — indicateur composite pondéré (grid-search des lags/poids).
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
