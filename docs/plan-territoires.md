# Plan — module « Territoires » : France héritée, France désirée

> Rédigé le 2026-09-20, à exécuter dans une session ultérieure. Tout ce qui est marqué
> **vérifié** l'a été ce jour-là, par requête réelle ; tout ce qui est marqué ⚠️ **à
> vérifier** est une hypothèse plausible qu'il faut confirmer avant de s'y appuyer.
> Vocabulaire des commits : `feat(territoires) phase N:`.

## 0. Origine, cadrage, et ce qu'on refuse

**Origine.** La vidéo de Xavier Delmas « Immobilier : la France va se couper en deux »
(9 mai 2026, 581 k vues). Thèse : le transfert de patrimoine 2025-2040 ne fera ni monter
ni baisser « l'immobilier », il creusera l'écart entre une France *héritée* (âgée,
propriétaire, pavillonnaire, vacante, en déclin démographique) et une France *désirée*
(attractive, active, solvable) — la maison héritée dans la Creuse devient l'apport d'un
achat à Bordeaux. Méthode : deux indices composites INSEE pondérés « au doigt mouillé »
(60/40), croisés en quatre catégories. Il n'existe pas de version ouverte, régénérée, à
méthode publiée de cette lecture.

**Ce qu'on garde** : le mécanisme (le capital se déplace, les maisons non), l'échelle
(département), le croisement en quatre situations, et surtout la quatrième — « âgé mais
attractif » — qui est précisément le cas qu'un indice moyenné efface.

**Ce qu'on refuse, et pourquoi (ce sont des règles de `CLAUDE.md`, pas des goûts) :**

| Refusé | Règle qui l'interdit |
|---|---|
| Un indice composite à poids choisis | c'est l'indicateur « Composite » supprimé le 2026-08-20 : « signal pondéré à la main sans backtest ni score, invérifiable par construction » |
| Moyenner « âgé » et « attractif » dans un score unique | la leçon du pilier Neuf : ne plus moyenner permis et chantiers, nommer la divergence |
| Un horizon 2040 | « une prévision publiée sans historique n'est qu'une opinion » — rien ne pourra la juger avant quinze ans |
| Une prévision de prix par département | « pas de prévision régionalisée » (les entrées du modèle sont nationales) |
| Publier avant d'avoir mesuré | `NEUF_GATE`, `REFUTATIONS` : une hypothèse plausible se mesure, puis se publie **dans un sens ou dans l'autre** |

**Ce qu'on construit à la place** : deux axes **observés**, sans pondération, dont on
**teste** d'abord, sur les douze ans de prix DVF déjà dans l'entrepôt, s'ils ont séparé
les départements par le passé. Puis, selon le résultat : une page carte nationale et un
bloc « profil » sur les 101 pages départementales — ou seulement le second, plus une
entrée dans `REFUTATIONS`.

## 1. Ce qui a été vérifié le 2026-09-20 (ne pas refaire l'exploration)

### 1.1 L'API Melodi de l'INSEE — JSON, sans clé, sans quota apparent

Point d'entrée : `https://api.insee.fr/melodi/data/<DATASET>?<DIM>=<val>&…&maxResult=N&page=k`.
Catalogue : `https://api.insee.fr/melodi/catalog/all` (147 jeux) et `…/catalog/<DATASET>`.
Chaque observation porte `dimensions` (dont `GEO` au format `2026-DEP-23`, `TIME_PERIOD`)
et `measures.OBS_VALUE_NIVEAU.value`. **Les valeurs RP sont des estimations pondérées,
donc des flottants** (36 804,12 habitants de 65 ans et plus dans la Creuse) : arrondir à
l'entier au moment d'écrire le CSV, jamais avant les ratios.

- **Le filtre par niveau fonctionne** : `GEO=DEP` renvoie **100** départements (Mayotte
  absente des jeux RP, qui couvrent « France hors Mayotte »). Pagination par `page=`,
  le champ `paging.first` en donne la forme.
- Codes de dimension utiles (tous vérifiés sur `GEO=DEP-23`) :

| Jeu | Ce qu'il donne | Dimensions vérifiées | Millésimes |
|---|---|---|---|
| `DS_RP_TD_LOGEMENT_AGE_PRINC` | **résidences principales × statut d'occupation × âge de la personne de référence** — la mesure DIRECTE du stock transmissible | `TSH` : `100` propriétaire, `211`/`212_222`/`221` locataires, `300` logé gratuit, `_T` ; `AGE` : `Y_LT15, Y15T24, Y25T39, Y40T54, Y55T64, Y65T79, Y_GE80, _T` ; `TDW` : `1` maison, `2` appartement, `3T6`, `_T` ; `NOR` pièces ; `OCS=DW_MAIN` | **2023 seulement** via l'API ⚠️ (voir 1.3) |
| `DS_RP_LOGEMENT_PRINC` | logements, RP, propriétaires, vacants, maisons | `TSH`, `TDW`, `OCS` (`DW_MAIN`, …), autres à `_T` | 2012, 2017, 2023 |
| `DS_RP_POPULATION_PRINC` | population par tranche d'âge | `AGE` dont `Y_GE65`, `Y25T39`, `Y40T54`, `Y55T64` ; `SEX=_T` | 2012, 2017, 2023 |
| `DS_RP_MIGRES_PRINC` | **migrations résidentielles** : population selon le lieu de résidence un an plus tôt, par âge | `PREV_RES_AREA` : `11` même logement, `12` autre logement même commune, `21` autre commune même département, `22` autre département même région, `23` autre région, `24`, `25T32` (DOM/étranger ⚠️ libellés exacts à lire dans le catalogue), `_T` ; `AGE` : `Y1T14, Y15T24, Y25T54, Y_GE55, Y_GE1` | 2012, 2017, 2023 |
| `DS_RP_EMPLOI_LR_PRINC` | actifs, chômeurs 15-64 | `EMPSTA` (⚠️ code du chômage à lire), `AGE` | 2012, 2017, 2023 |
| `DS_ESTIMATION_POPULATION` | population **annuelle** par tranche d'âge, 1975 → 2025 | `AGE` dont `Y_GE75`, `Y_GE60`, `Y25T59` ; `EP_MEASURE=POP_JAN_1ST` | annuel — la seule série « fraîche » |
| `DS_FILOSOFI_CC` | niveau de vie médian, taux de pauvreté | — | 2023 |

### 1.2 Le comparateur de territoires — un Parquet de 9,4 Mo que DuckDB lit tel quel

`https://www.insee.fr/fr/statistiques/fichier/2521169/comparateur.parquet` (publié le
2026-09-03, RP 2023, géographie au 1ᵉʳ janvier 2026, licence ouverte). Format long :
`GEO_OBJECT` (`DEP` = 101 lignes, Mayotte comprise ici), `GEO`, `TAB_MEASURE`,
`TIME_PERIOD`, `OBS_VALUE`. Mesures départementales et millésimes **vérifiés** :

| `TAB_MEASURE` | Sens | Millésimes |
|---|---|---|
| `POP` | population | 1968, 1975, 1982, 1990, 1999, 2007, 2012, 2017, 2023 |
| `LVB` / `DTH` | naissances / décès | 2016 → 2025, annuel |
| `DWELLINGS`, `DWELLINGS_OCS_DW_MAIN`, `DWELLINGS_OCS_DW_MAIN_TSH_100`, `DWELLINGS_OCS_DW_SEC_DW_OCC`, `DWELLINGS_OCS_DW_VAC` | logements, RP, RP propriétaires, secondaires, vacants | 2012, 2017, 2023 |
| `POP_AGE_Y15T64`, `NBEMP_EMPFORM_2` | 15-64 ans, emplois salariés | 2012, 2017, 2023 |
| `MED_SL`, `PR_MD60` | niveau de vie médian, taux de pauvreté (97 dép.) | 2023 |
| `UNIT_LOC*` | établissements par secteur et taille | 2024 |

Il ne contient **ni** structure par âge, **ni** chômage, **ni** solde migratoire : ceux-là
viennent de Melodi (1.1). Le **solde migratoire apparent** se calcule :
`(POP_t − POP_t−k − Σ(LVB − DTH))`, annualisé et rapporté à `POP_t−k` — possible pour
2017→2023 avec le comparateur seul (naissances/décès dès 2016) ; pour 2012→2017 il faut
l'état civil 2012-2016 ⚠️ (jeux `DS_ETAT_CIVIL_NAIS_COMMUNES` / `DS_ETAT_CIVIL_DECES_COMMUNES`
sur Melodi, à vérifier — repli : `DS_ESTIMATION_POPULATION` donne la population annuelle).

### 1.3 Ce qui reste à vérifier au premier pas de la phase 1

1. `DS_RP_TD_LOGEMENT_AGE_PRINC` n'a rendu que 2023. Le catalogue expose des fichiers
   par millésime (`accessURLParquet` de la forme `…/melodi/file/<DS>_2023/PARQUET`) :
   tester `_2017` et `_2012`. S'ils n'existent pas, le backtest utilise le **proxy** part
   des 65 ans et plus × part de propriétaires, et il faudra montrer que proxy et mesure
   directe **classent les départements pareil en 2023** (Spearman ≥ 0,9), sinon le
   backtest ne valide pas l'axe qu'on publie.
2. Libellés exacts des codes `PREV_RES_AREA` et `EMPSTA` (catalogue du jeu).
3. Pagination Melodi : la limite réelle de `maxResult` (500 a fonctionné).
4. ⚠️ Chômage localisé trimestriel par département (BDM, dataflow `TAUX-CHOMAGE`,
   `REF_AREA=D23`) : utile pour la fraîcheur, pas nécessaire au module. Ne pas bloquer
   dessus.

## 2. Les deux axes, et le vocabulaire à tenir

**Axe A — « héritée » : part des résidences principales détenues par un ménage dont la
personne de référence a 65 ans ou plus.**
`RP(TSH=100, AGE∈{Y65T79, Y_GE80}) / RP(TSH=_T, AGE=_T)`, TDW=`_T`. C'est le stock qui va
se transmettre, mesuré directement — pas déduit de l'âge de la population ni du taux de
propriétaires pris séparément. Variante « maisons » (`TDW=1`) à publier comme indicateur
de profil, pas comme axe.

**Axe D — « désirée » : deux candidats, à départager par la mesure (phase 1), pas par
préférence.**
- **D1** — solde migratoire apparent annuel (%), 2017→2023 (comparateur).
- **D2** — taux d'arrivée des 25-54 ans depuis un autre département :
  `MIGRES(PREV_RES_AREA∈{22,23}, AGE=Y25T54) / MIGRES(PREV_RES_AREA=_T, AGE=Y25T54)`.

Le piège que le second candidat vise : **Paris et les Hauts-de-Seine ont un solde net
négatif** (on en part faute de logements, pas faute d'envie) tout en étant les marchés les
plus demandés. Un axe D qui les classe « fuis » mesure la contrainte d'offre, pas la
demande. D'où le **test de Paris** en phase 1 : l'axe retenu doit placer 75 et 92 dans le
tiers « désiré ». Si D1 échoue et D2 réussit, D2 gagne ; si les deux échouent, le module
change de nature (voir 3.5).

**Seuils = médianes des 101 départements au dernier millésime, calculées en SQL.** Aucun
réglage : un seuil choisi à la main serait un poids déguisé.

**Quatre situations, nommées par ce qu'elles décrivent, jamais « gagnants/perdants »** —
le site ne prévoit pas, il décrit :

| Axe A | Axe D | Nom publié |
|---|---|---|
| au-dessus | en dessous | **Héritée, peu rejointe** |
| au-dessus | au-dessus | **Héritée et rejointe** (la 4ᵉ catégorie de la vidéo) |
| en dessous | en dessous | **Jeune, peu rejointe** |
| en dessous | au-dessus | **Jeune et rejointe** |

**Indicateurs de profil (page départementale), tous observés, chacun en percentile des
101 :** part des RP détenues par des 65+ (axe A), part de maisons dans les RP, taux de
vacance, part des 65 ans et plus dans la population, solde migratoire apparent, taux
d'arrivée des 25-54, niveau de vie médian. Sept au plus — le budget de 10 Ko par
département est tenu (max mesuré 8,9 Ko), mais on le revérifie à l'écriture.

## 3. Phase 1 — La mesure (la porte), ≈ 1 jour

**But** : savoir, AVANT toute page, si ces deux axes ont séparé les départements sur les
prix et volumes DVF 2014-2025. Protocole et seuils sont écrits ici pour ne pas pouvoir
être déplacés après avoir vu les résultats. Si on veut les changer, on les change
**maintenant**.

### 3.1 Le script : `mesure_territoires.py` à la racine, COMMITÉ

Sur le modèle de `dvf_backfill.py` (outil ponctuel, versionné). `scratchpad/gate_bls.py`
n'avait pas été conservé et `CLAUDE.md` le regrette : cette fois le script reste, pour que
le résultat stocké puisse être rejoué. Il lit l'entrepôt par SQL (`q.open_warehouse(
refresh=False)`, vue `dvf`), interroge Melodi et le comparateur, et imprime un rapport
Markdown, copié dans `docs/mesure-territoires-<date>.md`.

### 3.2 Deux fenêtres, deux millésimes de prédicteurs

| Fenêtre | Prédicteurs (connus AVANT le début de la fenêtre) | Résultat mesuré (DVF, `Type='Ensemble'`) |
|---|---|---|
| W1 | RP **2012** (publié 2015) ; solde migratoire 2012→2017 si l'état civil 2012-2016 est accessible, sinon 2007→2012 ⚠️ | Δlog du prix médian au m² et Δlog des ventes, **moyenne annuelle 2014 → 2019** |
| W2 | RP **2017** (publié 2020) ; solde migratoire 2017→2023 | idem, **2019 → derniers quatre trimestres** |

Chaque résultat est pris **en écart à la médiane nationale de la fenêtre** : ce qu'on
teste, c'est la dispersion entre départements, pas le cycle commun. 97 départements
(les quatre hors DVF sont exclus du test, pas du module).

### 3.3 Statistiques (rang, robustes, n ≈ 97)

Pour chaque axe (A, D1, D2), chaque fenêtre, chaque résultat (prix, ventes) :

1. **Spearman ρ** avec intervalle à 90 % par bootstrap (2 000 tirages, graine fixée).
2. **Le contrôle « déjà dans les prix »** : ρ entre le **niveau** de prix au début de la
   fenêtre et le résultat, puis ρ **partiel** de l'axe à niveau donné. C'est la réponse à
   l'objection que Delmas concède lui-même.
3. **Le croisement** : seuils = médianes du millésime ; résultat médian par situation ;
   écart « Jeune et rejointe » − « Héritée, peu rejointe ».
4. **Le test de Paris** (2.) sur D1 et D2 au millésime 2017 et 2023.
5. Si 1.3-1 l'impose : Spearman entre proxy et mesure directe de A en 2023.

**Agréger, ne jamais moyenner des ratios** — la leçon du −110 % de `_regime_reliability`.

### 3.4 La porte, figée

La **carte** et la page nationale ne sont construites que si, **dans les deux fenêtres**,
avec le même signe :

- ρ(rang moyen des deux axes, prix relatifs) ≥ **0,30** ;
- ρ partiel à niveau de prix donné ≥ **0,15** (l'axe dit quelque chose que le prix ne
  disait pas) ;
- écart de croissance médiane de prix entre « Jeune et rejointe » et « Héritée, peu
  rejointe » ≥ **5 points sur la fenêtre** (≈ 1 point par an) ;
- l'axe D retenu passe le test de Paris.

Le **bloc profil** des pages départementales, lui, ne passe par aucune porte : il est
descriptif, comme le taux de transformation (« il ne prévoit rien, donc il n'a besoin
d'aucune validation »).

### 3.5 Arbre de décision et livrable

| Résultat | Ce qu'on fait |
|---|---|
| Porte franchie | phases 2, 3a, 3b, 4 ; constante `TERRITOIRES_GATE` (datée, avec les chiffres des deux fenêtres) dans `web_export.py`, sur le modèle de `NEUF_GATE` ; la page publie la table « ce que ces axes ont prédit » |
| Porte manquée | phases 2, 3a, 4 seulement ; entrée datée dans `REFUTATIONS` (« l'âge du parc et l'attractivité migratoire n'ont pas séparé les prix départementaux 2014-2025 au-delà de ce que le niveau de prix disait déjà ») ; **pas** de page carte — une carte « héritée/désirée » sans pouvoir séparateur promettrait ce que la mesure a réfuté |
| Porte franchie sur les ventes seulement | page carte, mais titrée et rédigée sur les **volumes** (« où se vendra-t-il encore des logements ? »), jamais sur les prix |

Le rapport de mesure est commité dans `docs/` quel que soit le résultat.

## 4. Phase 2 — Le dataset `territoires`, ≈ 1 jour, INERTE côté publication

Preuve d'inertie attendue en fin de phase : `python web/export/web_export.py` annonce
toujours `0/7` et `0/102`.

### 4.1 `fetch_new_sources.build_territoires()`

- Descend `comparateur.parquet` (9,4 Mo) et le filtre `GEO_OBJECT='DEP'` en DuckDB ;
  interroge Melodi avec `GEO=DEP` (100 départements en un appel paginé par jeu, pas 100
  appels) pour les jeux du tableau 1.1, aux dimensions fixées.
- **Garde annuelle**, sur le modèle exact de `_dvf_publication` : `HEAD` sur le Parquet du
  comparateur, `Last-Modified` parsé puis ISO-8601, empreinte dans
  `data_manual_input/territoires.lastmod.txt` **versionnée** (jamais un mtime : un clone
  CI horodate au checkout). Pour Melodi, comparer le champ `modified` du catalogue ⚠️ (à
  vérifier qu'il existe) ; à défaut, la garde du comparateur suffit — les millésimes RP
  paraissent ensemble. Toute réponse manquante ⇒ on télécharge (défaut sûr, comme DVF).
- Écrit `data_manual_input/territoires-insee.csv`, **format long** : `Department,
  Millesime, Indicateur, Valeur, Source` — des comptes bruts, jamais des ratios (≈ 12 000
  lignes, ~400 Ko). Ajouté à `BUILDERS` avec le commentaire « CONDITIONNEL » comme
  `build_dvf`. Le workflow hebdo fait déjà `git add data_manual_input data …` : rien à
  toucher là.

### 4.2 `DataManager.ensure_territoires()` → `data/territoires.csv`

Format **large**, une ligne par `(Department, Millesime)` : comptes arrondis à l'entier +
ratios calculés **en un seul endroit** (part RP 65+, taux de vacance, part propriétaires,
part maisons, part 65+ dans la population, solde migratoire apparent annuel, taux
d'arrivée 25-54, niveau de vie médian, taux de chômage RP). pandas est légitime ici : c'est
un builder d'ingestion, comme `ensure_dvf`, pas une agrégation sur le chemin d'exécution.

- Ajouter `"territoires"` au registre `self.paths` ; appel **mtime-aware** dans
  `load_or_generate_all()`, comme `ensure_ecln`.
- **Brancher `ensure_dvf()` au même endroit** : `CLAUDE.md` (2026-09-19) note qu'elle n'a
  aucun appelant, donc que `data/dvf.csv` ne suivrait pas une republication DGFiP. Même
  correctif, même commit.
- ⚠️ **Ne PAS ajouter `territoires` au tuple de `read_frames()`** (six frames ; le piège
  documenté du retrait de `revenue`). Lecture par SQL uniquement.

### 4.3 Contrat `TERRITOIRES` dans `housing_data/schema.py`

`Department` avec la regex de `DVF` (`^(\d{2}|2[AB]|\d{3})$`, jamais un entier),
`Millesime` entier dans `[2012, 2035]`, ratios dans `[0, 100]`, `NiveauVieMedian` et les
colonnes 2023-seulement **nullable** (millésimes anciens, Mayotte). `unique=["Department",
"Millesime"]`. L'ajout à `SCHEMAS` crée la vue SQL tout seul (`_available_sources` itère
sur `SCHEMAS`). Compléter la fixture de `tests/test_housing_data.py` : elle casse dès
qu'une colonne déclarée manque — c'est son rôle.

### 4.4 `queries.py`

- `territoires_profil(con, code, millesime=None)` → indicateurs du département au dernier
  millésime, chacun avec son `percent_rank()` sur les départements renseignés et la
  valeur France (comparateur `GEO_OBJECT='FRANCE'` ⚠️ vérifier `GEO` de la France
  métropolitaine vs entière ; sinon somme des départements).
- `territoires_carte(con)` → une ligne par département : `code, a, d, quadrant,
  seuil_a, seuil_d` + les champs du profil pour la vignette ; seuils = `MEDIAN()` en SQL.
- Une requête = un curseur : tout passe par `_cur(con)` / `rows()`. Test de parité minimal
  dans `tests/test_queries_parity.py` : `percent_rank` SQL contre `rank(pct=True)` pandas
  sur les mêmes lignes.

## 5. Phase 3 — Les surfaces, ≈ 2 jours

### 5.1 (3a) Le bloc « profil » sur les 101 pages — `src/departement/[code].md`

- Nouvelle section `## Qui habite ici, et qui arrive ?` (titre Markdown statique, sans
  chiffre — le sommaire est construit au build depuis les `<h2>`), placée après « Combien
  de ventes ? » et avant « Ce que ces chiffres comptent ». Chapeau statique de deux
  phrases qui énonce le **mécanisme** et rien du présent : « un parc détenu par des
  ménages âgés se transmettra dans les quinze ans ; ce que deviennent ces logements dépend
  de qui arrive dans le département ». Test à faire sur chaque phrase : serait-elle encore
  vraie dans un an ?
- `build_departement` ajoute `payload["profil"]` (clés courtes, ratios à une décimale,
  percentiles entiers) ; **revérifier `_verifier_budget`** après écriture. Si un
  département dépasse, retirer la valeur France du payload et la lire depuis l'annuaire
  (`departements.json`), qui porte déjà ce qui est partagé.
- Rendu : `cardGrid([...], kpiCard)` avec **deux** `subs` par carte (« plus âgé que X %
  des départements », « France : Y % ») — le composant les rend en `<ul>` dès deux
  sous-lignes. **Le signe arithmétique et le signe ressenti doivent pointer dans le même
  sens** : « 78ᵉ centile » ne dit pas si c'est bien ou mal ; écrire ce que le lecteur
  ressent.
- **Les quatre départements hors DVF gagnent du contenu réel** : le RP couvre l'Alsace-
  Moselle (Mayotte : partiel, colonnes nullables). Aujourd'hui `if (!couvert)` arrête la
  page ; le bloc profil doit s'afficher **même là**. Restructurer sans casser la logique
  d'absence, et ne jamais écrire `display(html``)` sur une branche vide
  (`if (dep.profil) display(…)`).
- `site.config.depChapeau` (postbuild) : ajouter une phrase chiffrée depuis `profil`
  (« X % des résidences principales appartiennent à un ménage de 65 ans ou plus »), y
  compris pour les quatre non couverts — c'est le seul texte que Google lit sur ces pages.
  Étendre `test_postbuild_ecrit_les_chiffres_du_departement_dans_son_html` et le test
  « remplacé, jamais empilé ».
- Attendu au premier export : `101/102` fichiers départementaux modifiés (normal, une
  fois), compteur national toujours `0/7`.

### 5.2 (3b) La page nationale `/territoires` — « France héritée, France désirée »

Seulement si la porte est franchie (3.5).

- **`site.config.js`** : entrée `NAV` après « Marché de l'ancien » (icône 🗺️),
  description unique et propre ; `toc: true` dans le front-matter ; c'est la source unique
  (sidebar, sitemap, tests suivent).
- **Chapeau statique** ≥ 40 mots, sans chiffre ni état ; `<abbr title>` sur « RP » et
  « Filosofi » à leur première occurrence ; la formule des deux axes en clair.
- **Sections** (titres statiques) :
  1. *La carte : deux axes, quatre situations* — `Plot.geo` sur la métropole + Corse,
     couleur = situation, `Plot.tip(…, {…TIP})`, clic → `/departement/<code>` ; légende
     via `legendStatic` (4 entrées, classe `hm-legend--static`). Les **cinq DOM** en
     rangée de pastilles sous la carte (pas d'encart cartographique dans Plot) ; Mayotte
     « non renseignée » si le RP manque.
  2. *Les 101 départements sur les deux axes* — nuage A × D, médianes en traits, étiquettes
     des extrêmes, mêmes couleurs.
  3. *Ce que ces deux axes ont séparé — et ce qu'ils n'ont pas séparé* — table depuis
     `TERRITOIRES_GATE` (les deux fenêtres, ρ, ρ partiel, écarts par situation), avec la
     phrase honnête sur la part qui était déjà dans les prix. C'est ce qui distingue la
     page de la vidéo.
  4. *Chaque situation, département par département* — quatre listes de liens.
  5. *La méthode, en clair* — `<details>` en **Markdown statique** (indexé, à la
     différence d'un `how_to_read` interpolé) : définitions, sources et millésimes, seuils
     = médianes, limites — Paris/92 et l'axe net, DOM, valeurs RP pondérées, le « 2023 »
     du RP est une collecte 2021-2025, aucune prévision.
- **Données** : `territoires.json` via `build_territoires(con)` dans `_BUILDERS` → le
  compteur passe à **8**. C'est un JSON national, il a sa place dans le compteur (à la
  différence des 101 départementaux). Mettre à jour la docstring de `main()`, `CLAUDE.md`
  et toute prose « n/7 » (`grep -rn "n/7\|0/7"`). Payload ≈ 15-20 Ko. Flottants arrondis
  par `_write_if_changed` comme les autres.
- **Géométrie** : `web/observable/src/data/departements-topo.json` (TopoJSON, **≤ 100 Ko**,
  ids = codes INSEE), produit UNE fois par `web/observable/scripts/build-topojson.mjs`
  depuis les contours Etalab/IGN Admin Express (licence ouverte,
  `https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/latest/geojson/departements-100m.geojson`
  ⚠️ URL à confirmer) via `mapshaper -simplify 5% keep-shapes -o format=topojson`.
  **Commité, pas construit**, comme `og-image.png` ; la commande dans `web/README.md`.
  Chargé par `FileAttachment` (page non paramétrée : ça marche).
- **`hm.js` réexporte `feature` de `npm:topojson-client`** — les pages n'importent jamais
  `npm:` directement. Projection conique conforme centrée sur la France (Plot :
  `projection: {type: "conic-conformal", parallels: [44, 49], rotate: [-3, 0], domain}`).
- **Couleurs** : quatre jetons de `web/theme.json` (`series` : brick, blue, green, violet,
  gold) — jamais un hexadécimal dans une page ; vérifier la distinguabilité pour un
  daltonien avec le validateur du skill `dataviz` avant de figer le quadruplet. Les deux
  situations « héritées » doivent partager une famille, les deux « jeunes » une autre —
  la couleur doit porter l'axe A, la saturation l'axe D, pour que la carte se lise sans
  légende.
- **Accueil** : « Les huit pages » devient « Les neuf pages » (texte statique de
  `index.md`) ; **À propos** : « Le vocabulaire » gagne RP, Filosofi, personne de
  référence, solde migratoire apparent.
- **`sources_table.py`** : une ligne = une page source et une périodicité — donc trois
  lignes (RP via Melodi ; comparateur de territoires ; Filosofi), dataset `territoires`,
  `freq: "A"` ⚠️ (vérifier que le formateur de date connaît l'annuel ; sinon l'ajouter).
  `test_web_sources.py` échouera si une date dérive : c'est voulu.

### 5.3 Tests à écrire ou étendre

| Fichier | Ajout |
|---|---|
| `test_web_structure.py` | `"territoires"` dans `PAGES_DE_DONNEES` (titre statique, chapeau ≥ 40 mots, imports résolus, pas de `viewof`, ligne vide avant chaque bloc de code, `display` jamais vide) |
| `test_web_seo.py` | rien à écrire : la NAV pilote ; postbuild → phrase de profil dans le HTML des 101 pages, y compris les 4 non couvertes |
| `test_web_links.py` | `TERRITOIRES_GATE` porte `date` et `url` ; `territoires.json` a exactement les codes de `departements.DEPARTEMENTS` ; aucune situation vide ; seuils du payload = médianes recalculées ; TopoJSON ≤ 100 Ko et ids = codes |
| `test_queries_parity.py` | `percent_rank` contre pandas |
| `test_housing_data.py` | fixture `territoires` |
| `test_fetch_sources.py` | garde du builder : `Last-Modified` parsé (le piège « Mon, 18 May » < « Tue, 02 Jun »), réponse manquante ⇒ téléchargement |
| `test_dvf_clean.py` / nouveau | le calcul du solde migratoire apparent sur un cas fabriqué |

⚠️ **Rien ne teste le rendu.** La carte, les pastilles DOM, la légende et le clic se
vérifient dans un navigateur sur le site **construit** (`npm run build`, puis `dist/`) —
pas sous `npm run dev`, qui ne sert pas `/data/departements/`.

## 6. Phase 4 — Documentation et mémoire, ≈ ½ jour

- `CLAUDE.md` : section « Le module Territoires — ce qui doit rester vrai » (les deux
  axes et leurs formules, seuils = médianes, porte et sa date, compteur 8, test de Paris,
  `ensure_dvf` désormais branchée, TopoJSON commité) ; corriger « trois questions, pas
  davantage » dans la section des pages départementales et l'en-tête de `[code].md` ;
  compteur « n/7 » → « n/8 » partout.
- `web/README.md` : régénération du TopoJSON, nouveau JSON.
- Mémoire : mettre à jour `idee-attractivite-departementale.md` (porte franchie ou non,
  date).

## 7. Ordre des commits et vérification à chaque pas

```
feat(territoires) phase 1: mesure — script + rapport + TERRITOIRES_GATE ou REFUTATIONS
feat(territoires) phase 2: dataset — builder, ensure, contrat, vues, requêtes, tests   [0/7, 0/102]
feat(territoires) phase 3a: profil sur les 101 pages + chapeau postbuild               [0/7, 101/102 une fois]
feat(territoires) phase 3b: page carte nationale, territoires.json, TopoJSON, NAV      [0/8 ensuite]
docs(territoires): CLAUDE.md, README, mémoire
```

Après chaque commit, **chemins absolus** (un `cd` en tête de commande composée persiste,
et deux commits sont déjà partis avec un `pytest` qui n'avait rien exécuté) :

```
python -m pytest C:\Users\soula\Documents\HousingMarket_v3\tests -q
python C:\Users\soula\Documents\HousingMarket_v3\web\export\web_export.py
```

Puis, pour 3a et 3b : `npm run build` dans `web/observable`, ouverture du site construit,
recompte des légendes et vérification de la carte à 1280 px (la bande 1216-1320 px où le
sommaire réduit la colonne).

## 8. Pièges connus, propres à ce module

- **Paris et les Hauts-de-Seine** : voir 2. Ne pas publier un axe D qui les classe
  « fuis » — et écrire la limite sur la page même si D2 est retenu.
- **Mayotte** : absente des jeux RP (« France hors Mayotte »), présente dans le
  comparateur. Colonnes nullables, page qui le dit.
- **Valeurs RP flottantes** (pondération) : arrondir à l'écriture du CSV, pas avant les
  ratios ; et le secret statistique peut blanchir des cases en dessous de seuils — sans
  effet au niveau départemental, mais ne pas supposer que tout est renseigné.
- **`GEO` préfixé** (`2026-DEP-23`) : extraire le code après le dernier tiret ; `2A`/`2B`
  ne sont pas numériques ; `dtype=str` partout, comme pour DVF.
- **Le « 2023 » d'un RP est une collecte 2021-2025** : ne jamais l'écrire comme une photo
  de l'année.
- **Une carte sans légende ne se lit pas** — mais `multiLine` n'est pas en jeu ici, donc
  le défaut `legend="auto"` ne protège rien : poser `legendStatic` explicitement.
- **Un commentaire HTML dans un littéral gabarit** qui cite un identifiant entre accents
  graves referme la chaîne et fait disparaître la cellule sans un mot. Le test de syntaxe
  l'attrape, mais autant ne pas l'écrire.
- **Le compteur passe à 8** : c'est un changement délibéré, à écrire dans le commit et
  dans `CLAUDE.md`, sinon la prochaine session croira à une divergence.

## 9. Hors périmètre, explicitement

- Aucune prévision par département, aucun score unique, aucun « gagnant/perdant ».
- Pas de mirroir dans `app.py` (Streamlit est national, les pages départementales sont
  web-only depuis leur création).
- Pas de maille communale ni de zone d'emploi : le budget, le sélecteur et l'angle du site
  sont départementaux. Le comparateur les contient — une extension future, pas ce lot.
- Pas de données de successions ni de flux d'héritiers : elles n'existent pas en accès
  ouvert au département, et le module ne doit pas prétendre les mesurer.
