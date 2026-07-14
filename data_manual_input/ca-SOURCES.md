# Séries de CA « entreprise réel » — provenance & méthodologie

Ces séries servent de **benchmark de ventes réelles** dans l'onglet « Moteur de
Simulation Prospective », en remplacement optionnel des ventes synthétiques.
Granularité : **trimestrielle** (date = 1er mois du trimestre calendaire).
Unité : **M€** (`CA_MEUR`).

## `ca-hexaom.csv` — Hexaom (ex-Maisons France Confort)

- Proxy **construction neuve** (constructeur de maisons individuelles + rénovation +
  promotion, quasi 100 % France). Coté Euronext Paris (ALHEX / FR0004159473).
- Exercice **calendaire** (T1 = janv.–mars), CA publié en €. Idéal pour l'alignement.
- Trimestres reconstruits à partir des CA cumulés publiés (T1 / S1 / 9 mois / annuel) :
  `Qk = cumul(k) − cumul(k−1)`. **La somme des 4 trimestres réconcilie exactement
  le CA annuel publié** pour chaque exercice (vérifié 2018→2025).
- Périmètre retenu : **2018→2025**. Volontairement PAS avant 2018 : la période
  Maisons France Confort (≤2017) affichait des croissances de +20 à +25 %/an portées
  par des **acquisitions** (rachats de constructeurs régionaux), pas par le cycle
  immobilier — ce qui polluerait la corrélation avec les indicateurs de cycle.
- Sources : communiqués financiers Hexaom (hexaom.fr/investisseurs), un par période.
  CA annuels de contrôle : 2018=804,2 ; 2019=840,8 ; 2020=881,3 ; 2021=996,6 ;
  2022=1065,3 ; 2023=1016,2 ; 2024=727,2 ; 2025=616,3 M€.
- Note : T1 2019 (201,1) dérivé du taux publié (+5,8 % vs T1 2018=190,1), le communiqué
  ne titrant que le %. S1/9M/annuel 2019 sont des montants publiés.

## `ca-kingfisher-france.csv` — Kingfisher France (Castorama + Brico Dépôt)

- Proxy **rénovation / bricolage** (GSB). Segment « France » du groupe Kingfisher plc
  (coté Londres, KGF). Périmètre = Castorama + Brico Dépôt (hors Screwfix France).
- Ventes France publiées en **£m** par trimestre dans les « results data tables ».
  Converties en €m à un **taux de change CONSTANT de 1,16 €/£** — choix délibéré :
  un taux glissant importerait le bruit GBP/EUR (Brexit…) sans rapport avec le
  logement français ; un multiplicateur constant préserve la forme du signal d'activité.
- Exercice fiscal Kingfisher clôturant **fin janvier** ; les trimestres fiscaux
  (Q1≈févr.–avr., … Q4≈nov.–janv.) sont mappés au trimestre calendaire de plus fort
  recouvrement (décalage ≈ 1 mois assumé).
- Ventes France (£m) par trimestre fiscal utilisées :
  - FY2023/24 : Q1=1116, Q2=1195, Q3=1034, Q4=901 (somme 4246, = FY publié).
  - FY2024/25 : Q1=1026, Q2=1073, Q3=967, Q4=817 (somme 3883, = FY publié).
- Source : Kingfisher plc, « 2024/25 FY results data tables » (tableaux trimestriels
  par géographie, colonne N-1 fournissant FY2023/24).
- **TODO / limite connue** : série actuellement limitée à 2023-2024 (calendaire).
  Extension aux exercices FY2018/19→FY2022/23 à compléter depuis les data tables /
  RNS historiques Kingfisher (sourcing en cours).
