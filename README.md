# Baromètre du Logement

Site d'analyse du marché du logement en France, publié sur
**[barometre-logement.com](https://barometre-logement.com)**. Il met en regard la
construction neuve, les ventes dans l'ancien, les prix et les conditions de financement,
en tire une prévision des transactions à 12-18 mois, et publie l'historique de ses
prévisions face au réel. Chaque série vient d'un organisme public ; rien n'est saisi à la
main, rien n'est acheté.

Le dépôt a deux moitiés :

- **Python** (racine) — acquiert les sources, les valide, les agrège et écrit des JSON
  statiques ;
- **le site** (`web/observable/`, Observable Framework, Node) — lit ces JSON et se
  construit en HTML statique, servi par Cloudflare Pages.

```
fetch_new_sources.py ─► data_manual_input/ ─► DataManager ─► data/*.csv + Parquet
                                                                  │
                          queries.py (DuckDB) ◄───────────────────┘
                                  │
      forecast.py / api/engine.py ┤
                                  ▼
                  web/export/web_export.py ─► web/observable/src/data/*.json
                                                        │
                                  Observable Framework ─► dist/ ─► Cloudflare Pages
```

Un workflow GitHub Actions ([`refresh-data.yml`](.github/workflows/refresh-data.yml))
enchaîne chaque lundi : rafraîchir les sources, enregistrer la prévision du jour dans
l'archive, régénérer les JSON, commiter ce qui a changé. Le commit déclenche la
reconstruction du site.

> L'application Streamlit d'origine (`app.py`, onglets et rapport PDF) a été retirée le
> 2026-09-23 : le site en avait repris toutes les pages, et tenir deux interfaces alignées
> coûtait plus qu'il ne rapportait. Elle reste dans l'historique git.

## Les pages

| Page | Contenu |
|---|---|
| Accueil, À propos, Mentions légales | Rédigées, 100 % statiques (lisibles par les robots de partage) |
| Synthèse | État des trois piliers (neuf, ancien, financement), du présent vers l'avenir |
| Marché du neuf | Permis et mises en chantier (SIT@DEL), individuel/collectif, commercialisation (ECLN) |
| Marché de l'ancien | Ventes (IGEDD), prix Notaires-INSEE, capacité d'emprunt et accessibilité |
| Carte des départements | Les départements côte à côte : prix, évolutions, ventes, profil INSEE — et pourquoi la page ne classe pas |
| Environnement & Financement | Taux, OAT, Euribor, confiance, intentions d'achat, chômage, crédits, rénovation |
| Actualités & Aides | Veille curatée des dispositifs publics (`actualites.py`) |
| Prévision & Scénarios | Projection des ventes anciennes, son incertitude, un panneau de scénarios à trois leviers |
| Prévisions passées | Toutes les prévisions produites, face à ce qui s'est passé |
| Données & Sources | Confronter ses propres ventes aux indicateurs, sans que le fichier quitte le navigateur |
| 101 pages départementales | Prix au m² et ventes (DVF), m² accessibles, profil INSEE du département |

## Lancer en local

```bash
pip install -r requirements.txt
python fetch_new_sources.py            # rafraîchit data_manual_input/ (réseau)
python web/export/web_export.py        # reconstruit data/ et écrit les JSON du site
npm --prefix web/observable install
npm --prefix web/observable run dev    # http://localhost:3000
```

`python web/export/web_export.py` doit annoncer **`0/8 fichier(s) modifié(s)`** quand
aucune donnée n'a bougé : un diff inattendu signale une divergence de calcul, pas du
bruit.

Tests :

```bash
python -m pytest tests/ -q
```

Les tests de parité SQL se sautent sans entrepôt construit, ceux de parité JS et de
référencement sans Node, ceux de l'API sans Flask.

## Données

| Indicateur | Producteur | Accès |
|---|---|---|
| Logements autorisés et commencés (SIT@DEL) | SDES | API DiDo (data.gouv.fr) |
| Commercialisation des logements neufs (ECLN) | SDES | API DiDo (data.gouv.fr) |
| Ventes de logements anciens | IGEDD | classeur publié |
| Prix des logements anciens / neufs | Notaires-INSEE / INSEE | API SDMX (BDM) |
| Confiance des ménages, intentions d'achat, chômage BIT | INSEE | API SDMX (BDM) |
| Activité du second œuvre (rénovation) | INSEE, enquête de conjoncture | API SDMX (BDM) |
| Taux et volume des crédits nouveaux à l'habitat | Banque de France / BCE | API SDMX (MIR) |
| Demande de crédits habitat (enquête BLS) | BCE / Banque de France | API SDMX (BLS) |
| Euribor 3 mois, OAT 10 ans | BCE | API SDMX |
| Demandes de valeurs foncières (DVF) | DGFiP | data.gouv.fr (geo-dvf) |
| Recensement, niveau de vie (Filosofi) | INSEE | API Melodi |

La liste détaillée, avec la date du dernier point publié de chaque série, est sur la page
[À propos](https://barometre-logement.com/a-propos) — elle est réécrite par l'export à
chaque publication. Les identifiants de séries sont dans
[`data_manual_input/Data source.txt`](data_manual_input/Data%20source.txt).

## Pour contribuer

[`CLAUDE.md`](CLAUDE.md) porte les invariants à ne pas casser et les pièges connus ; le
journal des décisions et des mesures datées est dans [`docs/journal/`](docs/journal/).
Le front a son propre guide : [`web/README.md`](web/README.md).

Le code est sous licence MIT ([`LICENSE`](LICENSE)). Les données restent sous les
conditions de leurs producteurs (Licence ouverte / Etalab pour la plupart, conditions
propres pour les séries de la BCE).
