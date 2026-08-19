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
| État | **fusionné dans `main`** (`c21950d`, `fa38edb`, `d7f38e7`) | **branche `refactor/duckdb-engine`**, 5 commits devant `main` |
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

**Il ne reste rien de planifié sur cet axe.** Une seule agrégation pandas subsiste sur le
chemin d'exécution, délibérément (voir invariants).

Un chantier **distinct** reste ouvert, côté front web : `web/README.md` liste les onglets
Prévision / Atelier / Données & Export à porter vers Observable. Ce n'est pas du compute.

## Invariants à ne pas casser

**`analysis.py` n'est pas du code mort.** Ses agrégations (`aggregate_sitadel`,
`aggregate_ventes_ancien`, `calculate_rolling_12m`, `calculate_rolling`) ne sont plus
appelées au runtime, mais elles sont l'**implémentation de référence** contre laquelle
`tests/test_queries_parity.py` compare chaque requête SQL. Les supprimer supprime le filet
de sécurité de toute la migration. Ses helpers de *post*-agrégation (`calculate_kpis`,
`momentum_metrics`, `build_market_commentary`) sont, eux, bel et bien appelés.

**La couche SQL n'est plus optionnelle.** `app.py`, `web_export.py` et `report.py`
importent `queries` au niveau module → `housing_data` → `pandera`/`pyarrow`/`duckdb`. Tout
environnement qui exécute une de ces trois surfaces doit les installer, y compris le
runner GitHub Actions. L'import gardé de `data_manager.py` ne couvre plus que
`fetch_new_sources.py`.

**Un calcul reste en pandas, exprès** : le lissage 12 mois de l'atelier Time-Lag
(`app.py`, `min_periods=1`). C'est un lissage d'affichage appliqué en aval à la série déjà
agrégée, quelle que soit sa provenance parmi trois branches ; le passer en SQL obligerait
à pousser toute la sélection d'indicateur dans la requête, sans gain numérique. La raison
est écrite à côté du code — ce n'est pas un oubli.

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
python -m pytest tests/ -q          # 58 collectés ; 1 skip légitime si company_sales est vide
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
| `main` | — | porte l'axe stockage, pas l'axe compute |
| `refactor/duckdb-engine` | 5 | phases 0-3 + correctif CI. **Non fusionnée, aucune PR ouverte.** |
| `claude/duckdb-parquet-refactor-p2-tvs0b2` | 1 | abandonnée sur décision utilisateur — travail hors sujet (axe stockage). À supprimer. |
| `claude/code-audit-ocw25x` | 0 | reliquat, rien que `main` n'ait déjà |
