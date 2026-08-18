# Front statique — PoC de migration hors Streamlit

Preuve de concept : porter le dashboard HousingMarket vers un **site statique moderne**
(Observable Framework) déployable sur Cloudflare Pages / Netlify, **sans réécrire la
couche back-office Python**. Ce PoC couvre les **5 premiers onglets** de l'app.

## Principe

```
  [ INCHANGÉ — back-office Python ]                 [ NOUVEAU — couche produit ]
  data_manager / analysis / forecast  ──►  web_export.py  ──►  5 JSON statiques
  actualites / DataManager (CSV+DuckDB)                              │
                                                                     ▼
                                              Observable Framework  ──►  dist/ (HTML/JS)
                                                                     ▼
                                              Cloudflare Pages / Netlify (CDN, ~0 €)
```

`web_export.py` **réutilise telles quelles** les fonctions de l'app (`analysis`,
`forecast`, `actualites`, `DataManager`) et recompute exactement le contenu des cinq
premiers onglets d'`app.py`, un JSON par page (`synthese`, `neuf`, `ancien`, `macro`,
`actualites`). Le front ne fait que **lire** ces JSON : aucun Python n'est requis au
build du site.

## Arborescence

```
web/
├── export/
│   └── web_export.py            # agrégats Python → 5 JSON statiques
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

## Périmètre du PoC / suite

Les **5 premiers onglets** de l'app Streamlit sont portés, avec les mêmes sections, les
mêmes graphiques et les mêmes options de vue (cumul 12 / 6 mois, brut, moyennes mobiles,
légendes cliquables) :

- ✅ **Synthèse** — pastilles par pilier, à retenir, 3 blocs de cartes, fraîcheur,
  graphique croisé neuf/ancien en deux panneaux (niveaux + base 100).
- ✅ **Marché du neuf** — SIT@DEL (courbes, comparaison mensuelle), individuel vs
  collectif, ECLN (encours & mises en vente, délai d'écoulement, acquéreurs, prix au m²).
- ✅ **Marché de l'ancien** — IGEDD, puis prix Notaires-INSEE, capacité d'emprunt et
  indice d'accessibilité, neuf vs ancien.
- ✅ **Environnement & Financement** — confiance, taux, intentions, chômage, volumes de
  crédits, demande BLS, rénovation.
- ✅ **Actualités & Aides** — filtres, matrice d'impact, échéancier, fiches détaillées.

### Écarts connus avec Streamlit

Le front est fidèle onglet par onglet, à trois exceptions près, assumées à ce stade :

- **FR uniquement.** L'app Streamlit est bilingue (sélecteur FR/EN) ; le front ne sert
  que le français. Les libellés viennent de l'export Python, donc bilinguiser suppose de
  produire un JSON par langue.
- **Pas de filtre de période.** Streamlit a un curseur d'années global en barre latérale
  qui rogne l'affichage de tous les graphiques. Le front affiche toujours l'historique
  complet (les cumuls glissants sont de toute façon calculés sur l'historique entier des
  deux côtés, donc les courbes coïncident sur la plage commune).
- **Pas de segmentation par type de logement** sur la courbe SIT@DEL principale.
  Streamlit permet de ne retenir qu'un sous-ensemble des quatre types (individuel pur,
  individuel groupé, collectif, résidence) via un panneau repliable ; le front agrège
  toujours les quatre. La section « Individuel vs Collectif » couvre le découpage
  principal.

### Suite

- ⏭️ Reste à porter : Prévision, Atelier exploratoire, Données & Export — même patron
  (export Python → page).
- ⏭️ Bilingue FR/EN, filtres interactifs côté client (DuckDB-WASM sur les Parquet
  existants) pour les onglets exploratoires.
