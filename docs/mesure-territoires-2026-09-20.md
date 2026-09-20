# Mesure — module Territoires (2026-09-20)

Protocole et seuils : `docs/plan-territoires.md` §3, figés avant exécution. Script : `mesure_territoires.py`.

## 0. L'axe A ne se mesure directement qu'en 2023 : fidélité des proxys

Spearman avec la mesure directe (part des RP détenues par un ménage de 65 ans ou plus), sur 100 départements :

| proxy | ρ |
|---|---|
| part de propriétaires × part des 65 ans et plus | **+0,99** |
| part des 65 ans et plus seule | +0,96 |
| part de propriétaires seule | +0,86 |

Proxy retenu pour 2012 et 2017 : `A_proxy` (ρ = +0,99). Le seuil de 0,90 du plan est tenu.

## 1. Le test de Paris : quel axe D mesure la demande, et non l'offre ?

Rang (1 = le plus « rejoint ») de Paris (75) et des Hauts-de-Seine (92) sur les deux candidats, et tiers atteint :

| millésime | candidat | Paris | Hauts-de-Seine | tiers « désiré » ? |
|---|---|---|---|---|
| 2017 | D1 solde migratoire net | 100/100 | 95/100 | **non** |
| 2017 | D2 arrivées de hors du département | 1/100 | 2/100 | oui |
| 2023 | D1 solde migratoire net | 100/100 | 88/100 | **non** |
| 2023 | D2 arrivées de hors du département | 1/100 | 2/100 | oui |

## 2. Deux fenêtres, quatre-vingt-dix-sept départements

### W1 — prédicteurs RP 2012, résultat DVF 2014 → 2019 (97 départements)

| axe | résultat | ρ [IC 90 %] | ρ partiel à niveau de prix donné |
|---|---|---|---|
| A héritée (proxy) | prix | -0,43 [-0,56 ; -0,27] | +0,03 |
| A héritée (proxy) | ventes | +0,16 [-0,03 ; +0,33] | +0,38 |
| D1 solde migratoire | prix | +0,12 [-0,06 ; +0,30] | +0,18 |
| D1 solde migratoire | ventes | +0,47 [+0,32 ; +0,60] | +0,48 |
| D2 arrivées hors dép. | prix | +0,21 [+0,03 ; +0,38] | -0,05 |
| D2 arrivées hors dép. | ventes | +0,16 [-0,02 ; +0,33] | +0,11 |

Contrôle — le **niveau** de prix 2014 contre la croissance des prix : ρ = +0,65.

**Score rang(D) − rang(A), avec D1** : ρ prix = +0,57 [+0,43 ; +0,68], ρ partiel = +0,19, ρ ventes = +0,34.

| situation | n | croissance prix relative (pts) | croissance ventes relative (pts) |
|---|---|---|---|
| Héritée, peu rejointe | 15 | -4,8 | -2,0 |
| Héritée et rejointe | 33 | -1,3 | +3,6 |
| Jeune, peu rejointe | 34 | +0,0 | -1,7 |
| Jeune et rejointe | 15 | +2,5 | +2,1 |

Écart « Jeune et rejointe » − « Héritée, peu rejointe » : **+7,3 pts** de prix, +4,1 pts de ventes.

**Score rang(D) − rang(A), avec D2** : ρ prix = +0,42 [+0,27 ; +0,57], ρ partiel = -0,10, ρ ventes = +0,04.

| situation | n | croissance prix relative (pts) | croissance ventes relative (pts) |
|---|---|---|---|
| Héritée, peu rejointe | 30 | -2,7 | -1,1 |
| Héritée et rejointe | 18 | -1,7 | +4,8 |
| Jeune, peu rejointe | 19 | -0,4 | -0,7 |
| Jeune et rejointe | 30 | +2,3 | +0,7 |

Écart « Jeune et rejointe » − « Héritée, peu rejointe » : **+5,0 pts** de prix, +1,8 pts de ventes.

### W2 — prédicteurs RP 2017, résultat DVF 2019 → 2025 (97 départements)

| axe | résultat | ρ [IC 90 %] | ρ partiel à niveau de prix donné |
|---|---|---|---|
| A héritée (proxy) | prix | +0,46 [+0,30 ; +0,60] | +0,46 |
| A héritée (proxy) | ventes | +0,44 [+0,28 ; +0,59] | +0,16 |
| D1 solde migratoire | prix | +0,42 [+0,27 ; +0,56] | +0,46 |
| D1 solde migratoire | ventes | +0,07 [-0,09 ; +0,23] | +0,16 |
| D2 arrivées hors dép. | prix | -0,07 [-0,23 ; +0,12] | -0,01 |
| D2 arrivées hors dép. | ventes | -0,17 [-0,33 ; -0,01] | -0,04 |

Contrôle — le **niveau** de prix 2019 contre la croissance des prix : ρ = -0,20.

**Score rang(D) − rang(A), avec D1** : ρ prix = -0,06 [-0,22 ; +0,10], ρ partiel = +0,15, ρ ventes = -0,37.

| situation | n | croissance prix relative (pts) | croissance ventes relative (pts) |
|---|---|---|---|
| Héritée, peu rejointe | 18 | -0,6 | +3,8 |
| Héritée et rejointe | 30 | +2,2 | +3,1 |
| Jeune, peu rejointe | 31 | -5,6 | -4,2 |
| Jeune et rejointe | 18 | -1,2 | -1,7 |

Écart « Jeune et rejointe » − « Héritée, peu rejointe » : **-0,7 pts** de prix, -5,6 pts de ventes.

**Score rang(D) − rang(A), avec D2** : ρ prix = -0,32 [-0,49 ; -0,13], ρ partiel = -0,26, ρ ventes = -0,43.

| situation | n | croissance prix relative (pts) | croissance ventes relative (pts) |
|---|---|---|---|
| Héritée, peu rejointe | 26 | +1,4 | +3,5 |
| Héritée et rejointe | 22 | +2,0 | +3,7 |
| Jeune, peu rejointe | 23 | -2,6 | -0,6 |
| Jeune et rejointe | 26 | -3,6 | -4,3 |

Écart « Jeune et rejointe » − « Héritée, peu rejointe » : **-5,0 pts** de prix, -7,8 pts de ventes.

## 3. La porte (plan §3.4)

Critères, dans LES DEUX fenêtres et de même signe : ρ(score, prix) ≥ +0,30 ; ρ partiel ≥ +0,15 ; écart de croissance médiane ≥ +5 pts ; test de Paris réussi par l'axe D retenu.

| axe D | test de Paris | W1 ρ / ρp / écart | W2 ρ / ρp / écart | porte |
|---|---|---|---|---|
| D1 solde migratoire | non | +0,57 / +0,19 / +7,3 | -0,06 / +0,15 / -0,7 | manquée |
| D2 arrivées hors dép. | oui | +0,42 / -0,10 / +5,0 | -0,32 / -0,26 / -5,0 | manquée |

**Décision : porte manquée** → phases 2, 3a, 4 seulement ; entrée datée dans `REFUTATIONS` ; pas de page carte.

---

## Lecture (rédigée à la main après la mesure — tout ce qui précède est la sortie du script)

**Ce que la mesure établit, et qui est plus intéressant qu'un simple « non ».**

1. **Le proxy de l'axe A est fidèle** (ρ = 0,99 avec la mesure directe de 2023) : le
   backtest porte bien sur l'axe qu'on aurait publié. Ce n'est pas un défaut de mesure qui
   ferme la porte.
2. **Le solde migratoire net mesure la pénurie, pas le désir.** Paris est 100ᵉ sur 100 : on
   en part faute de logements. Le test de Paris avait été écrit pour ça, et il a tranché
   dans le sens prévu. Le taux d'arrivée de hors du département, lui, met Paris 1ᵉʳ.
3. **Sur 2014-2019, la thèse semble tenir, mais c'est un effet de niveau.** Les départements
   « hérités » sous-performent sur les prix (ρ = −0,43)… et cette relation disparaît
   entièrement à niveau de prix donné (ρ partiel = +0,03). C'était l'époque où les
   métropoles chères décrochaient du reste du pays (niveau contre croissance : ρ = +0,65) :
   l'axe A ne faisait que redessiner la carte des prix.
4. **Sur 2019-2025, le signe s'INVERSE.** Les départements âgés et propriétaires ont vu leurs
   prix (ρ = +0,46, et +0,46 à niveau donné) ET leurs volumes (+0,44) progresser PLUS que
   les jeunes métropoles. Covid, littoral, télétravail, puis une correction 2022-2024 qui a
   d'abord frappé les grandes villes. Tout ce que la vidéo annonce pour 2040 s'est produit
   à l'envers sur les six dernières années.

**Pourquoi c'est une réfutation et non une exception.** Le module devait porter un signal
structurel à quinze ans (le transfert de patrimoine). Une relation qui change de signe
d'un cycle à l'autre n'est pas structurelle : elle dit dans quel cycle on est. Publier la
carte, c'eût été publier la carte de 2014-2019 en la datant de 2040.

**Ce qui reste vrai et publiable — en description, jamais en prévision.** Les indicateurs
de profil (part des résidences principales détenues par des ménages de 65 ans et plus, part
de maisons, vacance, solde migratoire, arrivées, niveau de vie) décrivent un département
aujourd'hui, en percentile des 101. Ils vont sur les pages départementales sans prétendre à
autre chose. Et le renversement 2019-2025 lui-même est un fait à raconter — comme réfutation,
sur la page de prévision, à côté des autres idées mesurées puis écartées.

**Décision (plan §3.5)** : porte manquée → phases 2, 3a, 4 ; entrée datée dans
`web_export.REFUTATIONS` ; pas de page carte.
