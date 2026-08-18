# Front statique — PoC de migration hors Streamlit

Preuve de concept : porter le dashboard HousingMarket vers un **site statique moderne**
(Observable Framework) déployable sur Cloudflare Pages / Netlify, **sans réécrire la
couche back-office Python**. Ce PoC couvre le seul onglet **« Synthèse »**.

## Principe

```
  [ INCHANGÉ — back-office Python ]        [ NOUVEAU — couche produit ]
  DataManager (CSV, acquisition)  ──►  housing_data/ (Parquet + DuckDB, zéro serveur)
       │                                                    │
       ▼                                                    ▼
  analysis / actualites (logique métier)   web/export/queries.py (agrégations SQL :
       │                                    group by, cumuls glissants, YoY, z-score)
       └───────────────────┬────────────────────────────────┘
                            ▼
                     web_export.py  ──►  *.json (statique)
                     (Étape 0)                │
                                              ▼
                              Observable Framework  ──►  dist/ (HTML/JS)
                                              ▼
                              Cloudflare Pages / Netlify (CDN, ~0 €)
```

`web_export.py` ne recalcule plus les agrégations (group by mensuel, cumuls glissants,
YoY, z-score, capacité d'emprunt) à la main en pandas : `web/export/queries.py` les
délègue à **DuckDB**, qui interroge directement les **Parquet** de l'entrepôt
`housing_data/` (déjà alimenté par `DataManager.load_or_generate_all()` à chaque
export). Seule la logique métier partagée avec `app.py` (`analysis.calculate_kpis` /
`momentum_metrics`, `actualites`) reste réutilisée telle quelle — c'est le contrat de
la migration. Le front ne fait que **lire** le JSON produit : aucun Python n'est requis
au build du site.

## Arborescence

```
web/
├── export/
│   ├── web_export.py            # Étape 0 : assemble les payloads JSON par onglet
│   └── queries.py               # Couche SQL : agrégations DuckDB sur les Parquet
├── observable/
│   ├── observablehq.config.js   # config du site
│   ├── package.json
│   └── src/
│       ├── index.md             # page Synthèse (chips, cartes, graphique)
│       └── data/synthese.json   # généré par web_export.py (commité pour le déploiement)
└── README.md
```

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

Typo et couleurs alignées sur l'app Streamlit : pile de polices Calibri / Segoe UI,
titres soulignés en rouge brique (#E64A19), texte anthracite (#2D3748). Les graphiques
affichent les valeurs **au survol** (infobulle « closest » type Plotly, mois en français).

## Construire le site statique

```bash
npm --prefix web/observable run build   # → web/observable/dist/
```

Le dossier `dist/` est un site 100 % statique, servable tel quel.

## Déploiement Cloudflare Pages (recommandé)

Connecter le dépôt à Cloudflare Pages avec :

- **Build command** : `npm ci && npm run build`
- **Build output directory** : `dist`
- **Root directory** : `web/observable`

Cloudflare ne construit que le front (**Node uniquement**, pas de Python). Le
`synthese.json` est produit et commité par la pipeline Python (voir ci-dessous), donc
chaque rafraîchissement des données déclenche automatiquement un rebuild du site.

## Brancher sur le refresh hebdomadaire

Ajouter, à la fin du job de `.github/workflows/refresh-data.yml` (après le refresh des
sources, avant le commit), une étape qui régénère le JSON du front :

```yaml
      - name: Régénérer les données du front (Synthèse)
        run: python web/export/web_export.py
```

`web/observable/src/data/synthese.json` sera alors inclus dans le commit de données, et
Cloudflare Pages reconstruira le site à chaque publication. (Modification de CI laissée
à ta main — non appliquée par le PoC.)

## Périmètre du PoC / suite

- ✅ Onglet **Synthèse** porté à l'identique (FR).
- ⏭️ Restent à porter : Marché du neuf, Marché de l'ancien, Environnement & Financement,
  Actualités, Prévision, Atelier, Données & Export — même patron (export Python → page).
- ⏭️ Bilingue FR/EN, filtres interactifs côté client (DuckDB-WASM sur les Parquet
  existants) pour les onglets exploratoires.
