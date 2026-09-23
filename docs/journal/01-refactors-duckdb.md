# Refactors DuckDB : axes stockage et compute

> **Journal daté — ne pas réécrire.** Ce fichier est l'ancien contenu de `CLAUDE.md`,
> déplacé tel quel le 2026-09-23. Chaque paragraphe reflète l'état du dépôt À SA DATE :
> les chiffres, les noms de fichiers (`app.py`, `web_export.py` d'un seul tenant…) et les
> décomptes ont pu changer depuis. L'état courant et les règles en vigueur sont dans
> `CLAUDE.md` ; ce journal garde le POURQUOI et les mesures. On y ajoute des entrées
> datées, on ne corrige pas les anciennes.

## Orientation (l'ancien en-tête de CLAUDE.md)

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

Un troisième chantier, côté front web, est lui aussi **terminé** : les 7 onglets sont
portés vers Observable, et depuis le 2026-08-23 les **7** lisent un JSON statique produit
par `web_export.py` — Prévision et Données appelaient l'API HTTP `api/` jusque-là,
elles lisent maintenant `previsions.json` (Prévision) ou dérivent leurs séries de
`ancien.json`/`neuf.json` déjà publiés (Données). `api/` reste debout et testé
(`python -m api`), mais n'est plus appelée par aucune page du site — seulement par
`web_export.py`, en import Python direct. Voir « L'API HTTP » plus bas et
`web/README.md`.

Un quatrième, **terminé** lui aussi : faire du front un **site publiable**. Deux pages
rédigées se sont ajoutées aux sept pages de données (accueil et À propos), avec les
métadonnées de partage et de référencement qui vont avec. Voir « Le site public » plus bas.

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
`load_or_generate_all()` réécrivait les Parquet à chaque démarrage.

**La garde de fraîcheur est le point porteur** : `warehouse.resolve()` ne retient un
Parquet que s'il est au moins aussi récent que son CSV. Les CSV sont versionnés, les
Parquet gitignorés — donc un `git pull` apportant des CSV rafraîchis laisse mécaniquement
le Parquet local en retard. Les vues SQL appliquent la même règle, donc DuckDB et
`read_dataset()` ne peuvent pas diverger.

**Le job hebdo commite `data/` ENTIER depuis le 2026-09-19, plus une liste de fichiers.**
Son `git add` nommait `ventes_ancien.csv`, `forecast_archive.csv` et `forecast_band.csv`,
et oubliait les CSV dérivés que `load_or_generate_all()` reconstruit sur le runner —
`sitadel`, `macro`, `sales`, `ecln`. Le job les réécrivait puis les perdait à sa fin, et la
copie versionnée prenait du retard sur ses sources à chaque semaine : rattrapée à la main
le 2026-08-24 (`0f7005a`), puis retrouvée en retard le 2026-09-19 (`macro.csv` sans le taux
de crédit de juillet ni l'OAT d'août, pendant que le site les publiait). Une liste écrite à
la main vieillit toujours dans le même sens — elle oublie ce qui a été ajouté depuis, c'est
le mode de panne déjà noté pour la table des branches. D'où le dossier entier : ce qui ne
doit PAS être versionné sous `data/` (Parquet, `_manifest.json`, `company_sales.csv`) est
déjà dit dans `.gitignore`, que `git add <dossier>` respecte — une seule liste au lieu de
deux. Un run sans nouveauté ne produit toujours aucun diff, parce que les dérivés se
reconstruisent à l'identique (`build_sales` fixe sa graine). `tests/test_refresh_workflow.py`
lit le workflow et refuse tout fichier suivi sous `data/` hors de son `git add`, avec la
contre-épreuve que l'ancienne liste échoue bien. Corollaire pour le poste de travail :
un `git pull` apporte désormais les dérivés AVEC leurs sources, et la garde de fraîcheur
ci-dessus fait le reste.
