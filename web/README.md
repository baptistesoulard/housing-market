# Front statique — PoC de migration hors Streamlit

Preuve de concept : porter le dashboard HousingMarket vers un **site statique moderne**
(Observable Framework) déployable sur Cloudflare Pages / Netlify, **sans réécrire la
couche back-office Python**. Ce PoC couvre les **5 premiers onglets** de l'app.

## Principe

```
  [ INCHANGÉ — back-office Python ]                 [ NOUVEAU — couche produit ]
  data_manager / analysis / forecast  ──►  web_export.py  ──►  5 JSON statiques
  actualites / DataManager (Parquet→CSV)                             │
                                                                     ▼
                                              Observable Framework  ──►  dist/ (HTML/JS)
                                                                     ▼
                                              Cloudflare Pages / Netlify (CDN, ~0 €)
```

`web_export.py` **réutilise telles quelles** les fonctions de l'app (`analysis`,
`forecast`, `actualites`, `DataManager`) et recompute exactement le contenu des cinq
premiers onglets d'`app.py`, un JSON par page (`synthese`, `neuf`, `ancien`, `macro`,
`actualites`). La palette est centralisée dans `web/theme.json` (source unique lue par
`web/export/theme.py`, le CSS de la config et `components/theme.js` généré). Le front ne
fait que **lire** ces JSON : aucun Python n'est requis au build du site.

## Arborescence

```
web/
├── export/
│   ├── web_export.py            # agrégats Python → 5 JSON statiques + theme.js
│   └── theme.py                 # charge web/theme.json, génère components/theme.js
├── observable/
│   ├── observablehq.config.js   # config du site (+ CSS partagé, dont la frise)
│   ├── package.json
│   └── src/
│       ├── index.md             # page Synthèse (chips, cartes, graphique)
│       ├── components/
│       │   ├── hm.js            # graphiques & helpers partagés
│       │   ├── period.js        # frise de période globale (barre latérale)
│       │   └── theme.js         # palette, généré depuis web/theme.json
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

Typo et couleurs alignées sur ce que l'app Streamlit **rend** : corps de texte en Source
Sans 3 (la police que Streamlit embarque ; chargée ici via `globalStylesheets`), titres
dans la pile Segoe UI d'`app.py`, soulignés en rouge brique (#E64A19), texte anthracite
(#2D3748). Les graphiques affichent les valeurs **au survol** (infobulle « closest » type
Plotly, mois en français).

Deux règles de mise en page valent d'être connues avant de toucher au CSS :

- **Une seule largeur de colonne.** `--hm-measure` (64 rem) cadre `main` *et* la barre
  d'en-tête. Les plafonds par élément du thème `air` (640 px sur `p`/`h1-h6`, 600 px sur
  `ul`/`ol`) sont neutralisés : sans ça, la page a trois bords droits différents et les
  encadrés sont plus larges que le texte qu'ils contiennent. Ne pas remettre de
  `max-width` sur un bloc `.hm-*`.
- **La navigation vit dans la barre latérale**, rendue par Observable Framework à partir
  de `PAGES`. Elle ne s'épingle qu'au-delà de 1008 px ; en dessous elle se replie derrière
  un bouton, avec la frise de période qu'elle héberge. Un bandeau d'onglets en en-tête a
  été essayé puis retiré : redondant avec la barre latérale dès qu'elle est visible.

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

### Parité des contrôles

- **Filtre de période** — une **frise à deux poignées dans la barre latérale**
  (`src/components/period.js`), montée sur **toutes** les pages, comme le curseur
  « Période (années) » de la barre latérale Streamlit. Son domaine vient de l'export
  Python (bloc `period` des 5 JSON, même union de datasets qu'`app.py`), donc il est
  identique d'un onglet à l'autre quelle que soit l'étendue des séries de la page.

  Le site étant un ensemble de pages HTML distinctes, changer d'onglet **recharge** la
  page : la position de la frise est donc persistée dans `localStorage`, ce qui lui donne
  le comportement d'un contrôle unique qui suit l'utilisateur — la barre latérale
  Streamlit, elle, survit aux changements d'onglet sans rien faire.

  Il ne rogne que l'affichage : cumuls glissants et moyennes mobiles sont calculés en
  amont sur l'historique complet, exactement comme `app.py` qui filtre après avoir
  calculé — une fenêtre étroite montre donc les mêmes valeurs, jamais des cumuls
  tronqués. Deux nuances par page :

  - *Marché du neuf*, *Marché de l'ancien*, *Environnement & Financement* : tous les
    graphiques suivent la fenêtre ; les cartes « Chiffres clés » restent au dernier mois
    disponible, comme dans Streamlit.
  - *Synthèse* : seul le graphique croisé neuf/ancien suit la fenêtre. Pastilles, « à
    retenir » et cartes restent indépendants du curseur, exactement comme `app.py` qui
    les calcule sur les frames non filtrées.
  - *Actualités & Aides* : la frise est affichée pour rester présente partout, mais la
    page ne la consomme pas (l'échéancier porte sur des mesures à venir, au-delà du
    domaine du curseur). Une mention « Sans effet sur cet onglet » le dit sous le
    contrôle.
- **Segmentation par type de logement** — sur *Marché du neuf*, les quatre types SIT@DEL
  se cochent/décochent et rejouent la courbe **et** les KPI, comme le panneau repliable
  d'`app.py` (aucun type coché = tous, même convention que le multiselect vide).
  L'export publie `by_type` (séries par type, en colonnaire : le front somme les types
  retenus) et `kpis_by_type` (les KPI des 15 sous-ensembles, pré-calculés par les mêmes
  fonctions `analysis` que le reste de l'app — aucune statistique n'est réimplémentée en
  JavaScript).

### Écart connu avec Streamlit

- **FR uniquement.** L'app Streamlit est bilingue (sélecteur FR/EN) ; le front ne sert
  que le français. Les libellés venant de l'export Python, bilinguiser suppose de
  produire un JSON par langue.

### Suite

- ⏭️ Reste à porter : Prévision, Atelier exploratoire, Données & Export — même patron
  (export Python → page).
- ⏭️ Bilingue FR/EN, filtres interactifs côté client (DuckDB-WASM sur les Parquet
  existants) pour les onglets exploratoires.
