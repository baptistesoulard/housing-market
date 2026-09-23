# L'app Streamlit : onglets retirés, puis retrait complet

> **Journal daté — ne pas réécrire.** Ce fichier est l'ancien contenu de `CLAUDE.md`,
> déplacé tel quel le 2026-09-23. Chaque paragraphe reflète l'état du dépôt À SA DATE :
> les chiffres, les noms de fichiers (`app.py`, `web_export.py` d'un seul tenant…) et les
> décomptes ont pu changer depuis. L'état courant et les règles en vigueur sont dans
> `CLAUDE.md` ; ce journal garde le POURQUOI et les mesures. On y ajoute des entrées
> datées, on ne corrige pas les anciennes.

## Onglets retirés (2026-08-20) — ne pas les restaurer par réflexe

L'app est passée de **8 à 7 onglets**. Deux surfaces ont été supprimées ; les deux
suppressions sont des décisions, pas des oublis.

**« 🔬 Atelier exploratoire » (Time-Lag + Composite) — supprimé.** Il cherchait un
décalage en maximisant le **r de Pearson sur des niveaux lissés**, alors que l'onglet
Prévision répond déjà à la même question par une recherche en grille sur le **R²**,
menée sur la seule fenêtre d'entraînement (`fc.search_tx_lags`, `split=_FORECAST_SPLIT`)
pour ne pas contaminer le backtest. Deux méthodes rivales donnaient deux nombres sans
moyen d'arbitrer — et la plus faible des deux devait afficher son propre avertissement
sur l'auto-corrélation des séries lissées. Le sous-onglet Composite, lui, produisait un
signal pondéré à la main **sans backtest ni score** : invérifiable par construction.

Ce qui en a été **sauvé**, replié dans « 📡 Prévision & Scénarios » :

| Rescapé | Où | Pourquoi il n'était pas redondant |
|---|---|---|
| Graphe d'alignement + curseur de décalage | expander « Vérifier les décalages retenus », section 2 ter | Rend la recherche en grille **auditable** : on déplace un décalage, le modèle est réestimé (`fc.fit_tx_model`) et le R² affiché bouge. Noté avec le critère **du modèle**, pas avec un r concurrent. |
| Permis SIT@DEL → ventes société | section 4, second bloc `with tab_forecast:` | L'étage 2 explique les transactions par taux + intentions + chômage : **SIT@DEL n'y est pas**. Pour du second-œuvre, un permis déposé est une commande à venir — lien que le modèle ne voit pas. Mesuré par `fc.best_tx_to_monthly`, le même estimateur que l'élasticité transactions→ventes, donc les deux drivers sont comparables. |

Sont partis sans remplacement : la recherche de décalage par max-r, la branche « Indicateur
Macro » (ses indicateurs *sont* les prédicteurs du modèle), le benchmark sur ventes
synthétiques (circulaire — le code appelait `synthetic_circularity_warning()`), et tout le
Composite.

**Export SAP IBP — retiré du câblage.** Besoin suspendu côté métier. Le dernier onglet
n'est plus que « ⚙️ Données & Sources » (consultation + import des ventes société) et n'a
plus de sous-onglets. **`export.py` n'est pas supprimé** : le module reste intact pour
pouvoir être rebranché sans réécriture — mais il n'est désormais importé par *rien* et
n'a pas de test, donc rien ne le protège d'une régression silencieuse. Le rebrancher
suppose de le retester.

Les clés de traduction devenues orphelines *par ce retrait* ont été supprimées de
`translations.py` (71 clés × 2 langues). Une dizaine d'autres clés étaient déjà orphelines
avant (reliquat du code géo/carte) et ont été laissées en place, hors périmètre.

**Onglet « Données & Sources » réduit à l'import des ventes société (même jour).** Y ont
aussi été retirés : le navigateur « Données Actuelles du Système » (selectbox + aperçu +
modèle CSV), le téléversement qui écrasait un dataset par CSV, la « Réinitialisation
Générale », et le bouton de reconstruction des ventes anciennes depuis le fichier IGEDD.
Motif : l'acquisition est scriptée de bout en bout (`fetch_new_sources.py` + workflow
hebdo), donc l'écrasement en application était un second chemin de mutation des mêmes
fichiers, non versionné et non tracé.

Deux conséquences à connaître :

- **Le bouton IGEDD ne manque pas.** `load_or_generate_all()` appelle déjà
  `ensure_ventes_ancien()` au démarrage, et celle-ci est mtime-aware : la reconstruction
  se déclenche toute seule dès que le fichier IGEDD source est plus récent que
  `data/ventes_ancien.csv`. Le bouton ne faisait que forcer ce que le démarrage fait.
- **⚠️ On perd le panneau de diagnostic de l'entrepôt typé.** C'était le seul endroit de
  l'interface où l'on voyait `warehouse_status` (contrat pandera respecté ou non, par
  dataset) et `dataset_sources()` (« lu en Parquet » vs « lu en CSV (repli) »). Or la
  garde de fraîcheur est précisément le mécanisme porteur de l'axe stockage : un `git
  pull` qui apporte des CSV rafraîchis fait mécaniquement basculer des datasets en repli
  CSV, et **plus rien ne le signale à l'écran**. Les deux méthodes de `DataManager`
  existent toujours ; si le sujet ressort, la remettre sous forme d'un badge compact
  suffit — il n'est pas nécessaire de restaurer tout l'onglet.

`dm.update_with_custom_csv()` n'est désormais appelée par rien : elle devient du code mort
dans `data_manager.py` (elle figurait au backlog « brancher update_with_custom_csv sur les
contrats/logging » — ce backlog est caduc tant que l'import CSV ad hoc n'est pas rétabli).
21 clés de traduction supplémentaires ont été supprimées. La fonction
`synthetic_circularity_warning()` d'`app.py`, devenue morte avec le benchmark synthétique
du Time-Lag, a été supprimée elle aussi.

**Le code de l'Atelier a fini d'être retiré le 2026-08-24.** Le retrait du 2026-08-20
avait décâblé l'onglet mais laissé ses moteurs dans `simulation.py` : `find_optimal_lag`
(recherche de décalage par max-r), `min_max_normalize`, `create_composite_indicator` et
`optimize_composite_parameters`, plus le handler de session `opt_applied` en tête
d'`app.py` (il recopiait les paramètres du grid-search composite dans les curseurs, et
plus rien n'écrivait ces clés). Tout est parti, avec le test
`test_composite_optimizer_reports_out_of_sample`. **`simulation.py` ne porte plus que
`shift_indicator`**, qui est de la mise en forme (deux appels dans `app.py`) et non une
méthode rivale de la recherche en grille de `forecast.search_tx_lags` — c'est cette
rivalité sans arbitre qui avait motivé le retrait de l'onglet. Les textes qui présentaient
encore la Prévision comme « la formalisation des onglets Time-Lag / Composite », ou les
ventes importées comme « sélectionnables dans l'Atelier », ont été réécrits : ils
renvoyaient à une interface que le lecteur ne peut plus ouvrir.

## Retrait complet de l'app (2026-09-23)

`app.py` a été supprimé, avec ce qui n'existait que pour lui : `report.py` (rapport
PDF), `translations.py`, `simulation.py`, `export.py` (SAP IBP), le commentaire
automatique d'`analysis`, les deux fonctions de ventes société de `forecast.py` et les
imports par téléversement de `DataManager`. Motif : le site avait repris toutes les
pages, et l'app publiait déjà d'autres chiffres que lui (projection sans recalage ni
bande calibrée) — chaque correctif devait être reporté sur deux « surfaces jumelles ».
Tout reste dans l'historique git (dernier commit qui la contient : `3129448`).
