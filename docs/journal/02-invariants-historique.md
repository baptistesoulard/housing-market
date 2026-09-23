# Invariants : leur histoire et leurs mesures

> **Journal daté — ne pas réécrire.** Ce fichier est l'ancien contenu de `CLAUDE.md`,
> déplacé tel quel le 2026-09-23. Chaque paragraphe reflète l'état du dépôt À SA DATE :
> les chiffres, les noms de fichiers (`app.py`, `web_export.py` d'un seul tenant…) et les
> décomptes ont pu changer depuis. L'état courant et les règles en vigueur sont dans
> `CLAUDE.md` ; ce journal garde le POURQUOI et les mesures. On y ajoute des entrées
> datées, on ne corrige pas les anciennes.

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
calcul, pas du bruit.

**Et cette stabilité est OBTENUE, pas donnée (2026-09-07).** Cette page affirmait
qu'« depuis que les agrégations sont en SQL, la sortie ne dépend plus de la version de
pandas/numpy » : c'était trop fort. Le job hebdomadaire (runner Linux) et un export lancé
en local ont écrit, pour la même donnée, `935815.186488427` contre `935815.1864884269` —
deux doubles distincts à un ULP près, parce que l'algèbre linéaire de numpy n'est pas
compilée de la même façon des deux côtés. Ce n'est pas un défaut de mise en forme : `repr`
est déterministe pour un double donné, donc deux représentations différentes viennent
forcément de deux valeurs différentes.

Conséquence, si on ne fait rien : les deux environnements se repoussent `previsions.json`
indéfiniment (814 lignes de diff pour zéro information), et **le compteur « n/7 » perd son
pouvoir d'alerte** — un fichier qui bouge à chaque exécution ne signale plus rien quand il
bouge pour de bon. C'est-à-dire précisément la propriété pour laquelle ce compteur existe.

`_arrondir_flottants` arrondit donc tout flottant à `_PRECISION_JSON = 9` **chiffres
significatifs** au point d'écriture unique (`_write_if_changed`), avant sérialisation ET
avant comparaison. Trois choix à ne pas défaire :

* **Chiffres significatifs, pas décimales.** Le payload mêle des comptes (~9,5 × 10⁵) et
  des coefficients (~10⁻³) : un nombre de décimales fixe écraserait les seconds ou
  laisserait les premiers bruités.
* **9 et non 12.** N'importe quelle troncature couvre une dérive au 16ᵉ chiffre ; ce qui
  départage, c'est le risque qu'une valeur tombe exactement sur une frontière d'arrondi et
  bascule quand même — environ 10^(N−17) par valeur. À 12 chiffres, ~10⁻⁵, soit une
  occurrence attendue sur les ~25 000 flottants publiés ; à 9, ~10⁻⁸.
* **Entiers et booléens ne passent pas par là.** Les entiers sont exacts, et en Python un
  booléen EST un entier — les arrondir serait pire que le défaut.

Mesuré au passage : écart relatif maximal introduit **4,7 × 10⁻⁹**, structure des sept
fichiers identique, aucune valeur affichée modifiée. `tests/test_web_links.py` verrouille
l'affaire avec les **deux doubles réellement observés**, plus une contre-épreuve qui vérifie
qu'ils sont bien différents — sans elle, le test passerait pour de mauvaises raisons.
