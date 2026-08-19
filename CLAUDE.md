# Orientation — refactors en cours

Ce fichier existe parce que le plan de refactor n'avait jamais été écrit : il ne vivait
que dans le fil de conversation qui a produit les premières phases. Une session suivante
devait le reconstituer par archéologie git, et pouvait se tromper d'axe. Tenir ce fichier
à jour fait partie du travail.

## Deux axes de refactor à ne pas confondre

Le dépôt porte **deux** chantiers autour de DuckDB/Parquet. Ils ont des noms proches et
touchent les mêmes fichiers. Les confondre est l'erreur par défaut.

| | Axe **stockage** | Axe **compute** |
|---|---|---|
| Question | *où* les données sont persistées | *qui* calcule les agrégations |
| Livrable | `housing_data/` — contrats pandera + entrepôt Parquet, vue SQL par dataset | `queries.py` — DuckDB comme moteur d'agrégation unique |
| État | **fusionné dans `main`** — socle, puis bascule de la LECTURE par la PR #3 | **fusionné dans `main`** — PR #2, phases 0-4 |
| Vocabulaire des commits | messages libres | `refactor(compute) phase N:` |

L'axe compute **s'appuie** sur l'axe stockage : `queries.open_warehouse()` ouvre une
connexion sur les Parquet que `DataManager` a écrits. Mais leurs plans de phases sont
distincts. « Phase 1 » sans qualificatif désigne l'axe compute.

## Axe compute — plan et état

Objectif : DuckDB est la porte d'entrée **unique** des agrégations pour les trois
surfaces (`app.py`, `web/export/web_export.py`, `report.py`), pour qu'elles affichent les
mêmes chiffres par construction.

| Phase | Portée | Commit | État |
|---|---|---|---|
| 0 | `queries.py` + `tests/test_queries_parity.py`, additif, aucune surface modifiée | `dd428a3` | ✅ |
| 1 | `web_export.py` sur la couche SQL | `f30d02d` | ✅ |
| — | correctif : le workflow hebdo n'installait pas les libs devenues obligatoires en phase 1 | `ab2bc8c` | ✅ |
| 2 | `report.py` et `app.py` (onglets d'affichage) | `6e58bf8` | ✅ |
| 3 | `app.py` (onglets interactifs), `category_col`, `macro_rolling` | `0ddca27` | ✅ |
| 4 | série pilote de la prévision (`transactions_run_rate`) | `cceab61` | ✅ |

**Il ne reste rien de planifié sur cet axe.** Ce qui subsiste en pandas sur le chemin
d'exécution y reste délibérément (voir invariants).

Un chantier **distinct** reste ouvert, côté front web : `web/README.md` liste les onglets
Prévision / Atelier / Données & Export à porter vers Observable. Ce n'est pas du compute.

## Axe stockage — plan et état

Objectif : le Parquet est le chemin de lecture au runtime, les CSV restent la copie
versionnée et diffable — et le repli.

| Étape | Portée | État |
|---|---|---|
| socle | `housing_data/` : contrats pandera + écriture Parquet à côté des CSV | ✅ dans `main` |
| bascule | `read_frames()` lit le Parquet ; garde de fraîcheur ; `signature()` ; diagnostics | ✅ PR #3, fusionnée le 2026-08-19 |

**Pourquoi la bascule compte** : avant elle, l'app lisait les mêmes données par DEUX
chemins — DuckDB sur les Parquet pour les agrégations, pandas sur les CSV pour tout le
reste (options de widgets, entrées macro des modèles). Ils ne s'accordaient que parce que
`load_or_generate_all()` réécrivait les 7 Parquet à chaque démarrage.

**La garde de fraîcheur est le point porteur** : `warehouse.resolve()` ne retient un
Parquet que s'il est au moins aussi récent que son CSV. Les CSV sont versionnés, les
Parquet gitignorés — donc un `git pull` apportant des CSV rafraîchis laisse mécaniquement
le Parquet local en retard. Les vues SQL appliquent la même règle, donc DuckDB et
`read_dataset()` ne peuvent pas diverger.

## Invariants à ne pas casser

**`analysis.py` et `forecast.build_target` ne sont pas du code mort.** Les agrégations
d'`analysis.py` (`aggregate_sitadel`, `aggregate_ventes_ancien`, `calculate_rolling_12m`,
`calculate_rolling`) et `forecast.build_target` ne sont plus appelées au runtime, mais
elles sont l'**implémentation de référence** contre laquelle `tests/test_queries_parity.py`
compare chaque requête SQL. Les supprimer supprime le filet de sécurité de toute la
migration. En revanche les helpers de *post*-agrégation d'`analysis.py` (`calculate_kpis`,
`momentum_metrics`, `build_market_commentary`) sont, eux, bel et bien appelés.

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

**Ce qui reste en pandas y reste exprès.** Un `grep "groupby\|rolling\|resample"` sur le
chemin d'exécution ne doit plus renvoyer que ces quatre cas, et aucun n'est un oubli :

| Emplacement | Pourquoi |
|---|---|
| `app.py` — lissage 12 mois de l'atelier Time-Lag (`min_periods=1`) | Lissage d'*affichage* appliqué en aval à la série déjà agrégée, quelle que soit sa provenance parmi trois branches. Le passer en SQL obligerait à pousser toute la sélection d'indicateur dans la requête, sans gain numérique. |
| `forecast.py` — `build_target` | N'est plus appelée : implémentation de **référence** des tests de parité (voir invariant ci-dessus). |
| `forecast.py` — `tx12.resample("QS").mean()` | Transformation de la série pilote *par le modèle*, pas une agrégation de dataset. |
| `forecast.py` — les deux `groupby("Date").sum()` de `fit_tx_to_monthly` / `fit_sales_two_factor` | Repli défensif contre des dates dupliquées, sur une frame passée en paramètre. Depuis la phase 3 les appelants fournissent déjà une série unique par date : c'est un no-op qu'on garde parce que ces helpers sont génériques. |

`export.py` fait aussi des `groupby`/`resample`, mais c'est un formateur SAP IBP agnostique
du dataset : il opère sur ce qu'on lui donne, il n'a pas de source à interroger.

**Ne pas régénérer les JSON du front sans vérifier.** `python web/export/web_export.py`
doit annoncer `0/5 fichier(s) modifié(s)`. Un diff inattendu signale une divergence de
calcul, pas du bruit — depuis que les agrégations sont en SQL, la sortie ne dépend plus de
la version de pandas/numpy.

## Vérifier la parité

Trois recettes, par ordre de coût croissant. Les tests unitaires seuls ne suffisent pas :
ils ne prouvent rien sur le câblage des surfaces.

**1. Tests de parité** — chaque requête SQL contre son équivalent pandas sur les données
réelles. Nécessite un entrepôt construit (`python -c "from data_manager import
DataManager; DataManager().load_or_generate_all()"`), sinon le module se skippe.

```
python -m pytest tests/ -q          # 59 collectés ; 1 skip légitime si company_sales est vide
```

**2. Rapport PDF, comparaison d'octets** — la plus forte : couvre les graphiques, les KPI
et le commentaire d'un coup. Générer le PDF avec l'ancienne version de `report.py`
(`git show <ref>:report.py`) et la nouvelle, puis comparer après avoir retiré
`/CreationDate`, `/ModDate` et `/ID`, que reportlab régénère à chaque appel.

**3. `app.py` sous plusieurs états de widgets** — indispensable pour les onglets
interactifs : l'état par défaut n'exerce pas les branches conditionnelles. Comparer un
worktree de référence et l'arbre courant :

```python
from streamlit.testing.v1 import AppTest
at = AppTest.from_file(f"{racine}/app.py", default_timeout=1200); at.run()
snap = lambda: {"m": [[x.label, x.value, x.delta] for x in at.metric],
                "md": [x.value for x in at.markdown],
                "cap": [x.value for x in at.caption],
                "tbl": [d.value.to_json() for d in at.dataframe]}
etats = {"defaut": snap()}
at.sidebar.slider[0].set_value((2015, 2020)); at.run(); etats["slicer"] = snap()
at.sidebar.slider[0].set_value((2000, 2026)); at.run()
for sb in at.selectbox:            # bascule chaque liste sur sa DERNIÈRE option :
    if sb.options and len(sb.options) > 1:   # c'est ce qui exerce les branches
        sb.set_value(sb.options[-1])         # Product / Company / Serie
at.run(); etats["selects"] = snap()
```

Streamlit exécute le corps de **tous** les onglets, pas seulement celui affiché — un seul
`run()` couvre donc les 12 onglets pour un état de widgets donné.

## État des branches

| Branche | Devant `main` | Note |
|---|---|---|
| `main` | — | porte les DEUX axes en entier : compute (phases 0-4) et stockage (socle + bascule) |
| `refactor/duckdb-storage` | 0 | axe stockage, fusionné par la PR #3 |
| `refactor/duckdb-engine` | 0 | axe compute, fusionné par la PR #2 |
| `fix/web-lisibilite` | 0 | correctifs de lisibilité du front web, fusionnés |
| `claude/code-audit-ocw25x` | 0 | reliquat, rien que `main` n'ait déjà |

Les quatre branches ci-dessus sont **entièrement contenues dans `main`** (`git merge-base
--is-ancestor` vérifié) : leurs copies locales ont été supprimées, il ne reste que les
copies distantes, à supprimer d'un `git push origin --delete`. `claude/duckdb-parquet-
refactor-p2-tvs0b2`, qui figurait ici, n'existe plus ni en local ni sur le distant.
