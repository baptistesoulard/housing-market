# Vérifier la parité, état des branches

> **Journal daté — ne pas réécrire.** Ce fichier est l'ancien contenu de `CLAUDE.md`,
> déplacé tel quel le 2026-09-23. Chaque paragraphe reflète l'état du dépôt À SA DATE :
> les chiffres, les noms de fichiers (`app.py`, `web_export.py` d'un seul tenant…) et les
> décomptes ont pu changer depuis. L'état courant et les règles en vigueur sont dans
> `CLAUDE.md` ; ce journal garde le POURQUOI et les mesures. On y ajoute des entrées
> datées, on ne corrige pas les anciennes.

## Vérifier la parité

Trois recettes, par ordre de coût croissant. Les tests unitaires seuls ne suffisent pas :
ils ne prouvent rien sur le câblage des surfaces.

**1. Tests de parité** — chaque requête SQL contre son équivalent pandas sur les données
réelles. Nécessite un entrepôt construit (`python -c "from data_manager import
DataManager; DataManager().load_or_generate_all()"`), sinon le module se skippe.

```
python -m pytest tests/ -q          # 249 passés, 1 skip légitime si company_sales est
                                    # vide. Les tests d'API se skippent sans Flask, ceux
                                    # de parité JS et de référencement sans Node.
```

**Piège Windows sur les tests qui appellent Node.** `subprocess.run(text=True)` décode la
sortie avec la page de codes ANSI du système (cp1252), pas en UTF-8 : le thread lecteur
lève sur le premier caractère hors table, `stdout` revient à `None`, et le test échoue sur
un `TypeError` de `json.loads` alors que Node a rendu 0. Les neuf tests de
`test_web_seo.py` erraient ainsi en silence. Toujours passer `encoding="utf-8"`.

**Le panneau navigateur intégré ne rend RIEN si l'onglet n'est pas affiché.**
`document.hidden` vaut alors `true`, `requestAnimationFrame` ne se déclenche jamais, et le
runtime Observable ne calcule aucune cellule : toutes les pages restent en indicateurs de
chargement, y compris celles qu'on n'a pas touchées. Ce n'est pas un bug de page. Pour
vérifier une cellule dans ces conditions, importer le module directement
(`await import("/_import/components/hm.js")`) et l'appeler à la main. **C'est une piste
sérieuse pour l'intermittence des pages départementales** (voir plus haut) — non
démontrée, l'observation d'origine ayant été faite sur le site déployé.

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

**Il n'y a plus qu'une branche : `main` (2026-09-03).** Les neuf branches distantes qui
subsistaient ont été supprimées, ainsi que la dernière copie locale
(`feat/accueil-bandeau`). Elles étaient toutes **ancêtres de `main`** — vérifié une à une
par `git merge-base --is-ancestor` avant suppression — donc aucun commit n'a été perdu :
supprimer une référence ne supprime pas ce qu'elle désignait quand `main` y mène déjà.

Ce qu'elles portaient, et qui vit désormais dans `main` : les deux axes de refactor
DuckDB (`refactor/duckdb-storage` par la PR #3, `refactor/duckdb-engine` par la PR #2),
la lisibilité du front (`fix/web-lisibilite`), le site public et son référencement
(`claude/website-seo-accessibility-alr8mw`, `claude/seo-immobilier-france-visibility-ke5t2g`),
les 101 pages départementales (`feat/pages-departementales`), le bandeau d'accueil
(`feat/accueil-bandeau`), la fusion Time-Lag → Prévision (`refactor/fusion-timelag-previsions`)
et un reliquat d'audit (`claude/code-audit-ocw25x`).

⚠️ **Cette section avait dérivé, et c'est le mode de panne à connaître :** elle n'en
listait que six alors qu'il en existait neuf, et affirmait que « les copies locales ont
été supprimées » alors que `feat/accueil-bandeau` traînait encore en local. Une table de
branches écrite à la main vieillit toujours dans le même sens — elle oublie ce qui a été
créé depuis. **Se fier à `git branch -r` et à `git rev-list --left-right --count`, jamais
à cette page**, et la réécrire quand la topologie change.

Corollaire pratique : un `git diff main..<branche>` sur une branche en retard affiche un
écart énorme qui n'est PAS du travail à récupérer — c'est ce que `main` a ajouté depuis,
vu à l'envers. Le seul test qui répond à « reste-t-il quelque chose à fusionner ? » est le
compte de commits en avance, ou `merge-base --is-ancestor`.
