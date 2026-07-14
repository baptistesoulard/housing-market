# HousingMarket — Market Intelligence Immobilier

Dashboard **Streamlit** d'analyse conjoncturelle du marché immobilier français (national) et d'aide à la prévision. Il centralise et met en regard les indicateurs de construction (SIT@DEL / SDES), de ventes dans l'ancien (IGEDD) et le contexte macro-financier (confiance des ménages, taux de crédit, Euribor, OAT 10 ans, intentions d'achat, chômage BIT).

## Aperçu des onglets

- **Conjoncture** — évolution des permis, mises en chantier et ventes (cumuls 12/6 mois, brut, moyennes mobiles).
- **Contexte Macro & Financement** — confiance des ménages, taux, intentions d'achat, chômage.
- Analyse, simulation et export des indicateurs.

## Lancer en local

```bash
pip install -r requirements.txt
streamlit run app.py
```

L'application s'ouvre sur http://localhost:8501.

## Données

Les fichiers de `data/` sont générés/rafraîchis à partir de sources publiques officielles :

| Indicateur | Source |
|---|---|
| Ventes dans l'ancien | IGEDD |
| Logements autorisés / commencés | SDES (data.gouv.fr) |
| Confiance des ménages, intentions d'achat, chômage BIT | INSEE (API SDMX BDM) |
| Taux de crédit habitat | Banque de France / BCE (MIR) |
| Euribor 3 mois, OAT 10 ans | BCE (SDMX) |

Les ventes de produits second-œuvre sont **synthétiques et anonymisées** (3 familles génériques).

## Stack

Python · Streamlit · pandas · numpy · plotly · xlrd
