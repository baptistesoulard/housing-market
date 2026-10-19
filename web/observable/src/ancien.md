---
title: Logement ancien
toc: true
---

```js
import {kpiCard, cardGrid, marketChart, multiLine, monthlyByYear, filterYears, withCsvExport,
        cadreGraphique, MONTHS_FULL, nf0, nf1, fmtMonthFR, TIP} from "./components/hm.js";
import {periodFilter} from "./components/period.js";
import {series} from "./components/theme.js";
const anc = await FileAttachment("./data/ancien.json").json();
```

<!--
  TITRE ET CHAPEAU STATIQUES — rendus au build, pas construits dans le navigateur.
  Tout le reste de la page est monté en JS à partir du JSON : un robot d'indexation, comme
  tout aperçu de partage, n'en voit rien. Ces deux blocs sont donc le SEUL texte de la page
  que lisent Google et LinkedIn. Le titre valait auparavant `${anc.title}`, c'est-à-dire un titre
  VIDE dans le HTML livré. Ne pas les reconvertir en interpolation.
  Voir CLAUDE.md, « Texte statique : aucun chiffre, aucun état ».
-->

# 🏠 Logement ancien — transactions, prix & accessibilité

L'essentiel des transactions immobilières en France porte sur des logements anciens. Cette
page en suit le volume, mesuré par l'<abbr title="Inspection Générale de l'Environnement et du Développement Durable, qui publie le suivi mensuel des ventes de logements anciens">IGEDD</abbr> en cumul sur douze mois glissants, puis les prix
publiés par les Notaires et l'INSEE, et enfin l'accessibilité : combien de mètres carrés un
ménage peut acheter à mensualité constante.

Cette dernière lecture est celle qui décrit le mieux le pouvoir d'achat immobilier, parce
qu'elle réunit les deux forces qui s'opposent — le prix au m² et le taux du crédit. Un prix
stable dans un marché où les taux montent est en réalité une perte d'accessibilité, et c'est
exactement ce qu'un indice de prix seul ne montre pas.


<details class="hm-howto">
  <summary>ℹ️ Comment lire cette page</summary>
  <div class="hm-caption">${anc.how_to_read}</div>
</details>

```js
// Filtre de période : la frise GLOBALE de la barre latérale, partagée par tous les
// onglets (parité avec le curseur d'années de la barre latérale Streamlit).
const rangeA = Generators.input(periodFilter({min: anc.period.min, max: anc.period.max}));
```

## 🔑 Chiffres Clés

<div class="hm-caption">Chiffres nationaux au dernier mois disponible — indépendants de tout filtre.</div>

<div class="hm-shortcuts hm-shortcuts--twin"><a class="hm-shortcut" href="./neuf#chiffres-cles">🏗️ la même vue pour le neuf</a><a class="hm-shortcut" href="./carte">📍 prix et ventes dans votre département</a></div>

${cardGrid([anc.kpi], kpiCard)}

## 📊 Courbes d'évolution du marché


<div class="hm-shortcuts hm-shortcuts--twin"><a class="hm-shortcut" href="./neuf#courbes-d-evolution-du-marche">🏗️ la même vue pour le neuf</a></div>

```js
const viewA = view(Inputs.radio(
  new Map([["Cumul glissant 12 mois", "roll12"], ["Cumul glissant 6 mois", "roll6"],
           ["Cumul glissant 3 mois", "roll3"], ["Données brutes mensuelles", "raw"]]),
  {value: "roll12", label: "Type de visualisation"}));
const maA = view(Inputs.checkbox(["Moyenne mobile 12 mois", "Moyenne mobile 6 mois"],
  {label: "Superpositions (vue brute uniquement)"}));
// Ce que montre la courbe, selon la vue choisie : le sous-titre du graphique.
const VUE_LIBELLE = {roll12: "Cumul sur 12 mois glissants", roll6: "Cumul sur 6 mois glissants",
                     roll3: "Cumul sur 3 mois glissants", raw: "Ventes mensuelles"};
```

${marketChart({rows: filterYears(anc.main_series.rows, rangeA), meta: anc.main_series.meta, view: viewA, showMA12: maA.includes("Moyenne mobile 12 mois"), showMA6: maA.includes("Moyenne mobile 6 mois"), yLabel: "Milliers de ventes", width, filename: "marche-ancien",
  titre: "Ventes de logements anciens en France", sousTitre: `${VUE_LIBELLE[viewA]}, en milliers de ventes`, source: anc.main_series.source})}

## 📅 Comparaison Mensuelle par Année

<div class="hm-caption">Comparez un ou plusieurs mois d'une année à l'autre. Par défaut, les 3 derniers mois disponibles.
Cette vue n'existe que sur l'ancien, et c'est mesuré : les ventes IGEDD sont publiées BRUTES et gardent
une saisonnalité de près de 40 % d'amplitude, que comparer un même mois d'une année à l'autre neutralise.
Les séries SIT@DEL du neuf sont, elles, déjà corrigées des variations saisonnières — la même vue n'y
comparerait que du bruit résiduel (7 à 8 %), c'est pourquoi elle en a été retirée.</div>

```js
const lmA = anc.monthly.last_month_num;
const defMonthsA = [0, 1, 2].map((k) => MONTHS_FULL[((lmA - k - 1) + 12) % 12]);
const monthsA = view(Inputs.checkbox(MONTHS_FULL, {value: defMonthsA, label: "Mois à comparer"}));
```

```js
const monthNumsA = monthsA.map((m) => MONTHS_FULL.indexOf(m) + 1).filter((n) => n > 0);
display(monthNumsA.length
  ? monthlyByYear({rows: filterYears(anc.monthly.rows, rangeA), valueKey: "tx", monthNums: monthNumsA, scheme: "Greens", width, filename: "ancien-comparaison-mensuelle",
      titre: "Ventes de logements anciens, même mois d'une année à l'autre", sousTitre: "Ventes mensuelles brutes, en milliers · France", source: "IGEDD"})
  : html`<div class="hm-caption">Sélectionnez au moins un mois.</div>`);
```

```js
const px = anc.prix;
```

## 🏷️ Prix des logements & accessibilité

<div class="hm-caption">Indices de prix des logements anciens (Notaires-INSEE, base 100 = 2015, France métropolitaine) et lecture de l'accessibilité : capacité d'emprunt à mensualité constante et indice d'accessibilité (capacité rapportée aux prix).</div>

${px.available ? cardGrid(px.kpis, (k) => kpiCard({label: k.label, value: k.value, yoy: k.yoy})) : html`<div class="hm-caption">Indices de prix indisponibles.</div>`}

${px.available ? html`<div class="hm-meta">Dernier point : ${px.last_date} · base 100 = moyenne 2015 · variation en glissement annuel.</div>` : ""}

```js
const term = px.available ? view(Inputs.radio(new Map([["25 ans", "25"], ["20 ans", "20"]]),
  {value: "25", label: "Durée d'emprunt (modèle de capacité)"})) : "25";
```

```js
// Séries dérivées pour capacité / accessibilité selon la durée choisie.
function capacityRows() {
  const rows = filterYears(px.capacity[term], rangeA);
  return [
    ...rows.map((d) => ({date: d.date, series: "Capacité d'emprunt", value: d.capidx})),
    ...rows.map((d) => ({date: d.date, series: "Prix (Ensemble)", value: d.prix})),
  ];
}
function accessRows() { return filterYears(px.capacity[term], rangeA).map((d) => ({date: d.date, value: d.access})); }
```

<div class="hm-panels">
  ${px.available ? multiLine({rows: filterYears(px.price_levels, rangeA), meta: px.series_meta, yLabel: "Indice, base 100", valueFmt: (v) => nf0.format(v), filename: "ancien-prix-indices",
    titre: "Prix des logements anciens", sousTitre: "Indices Notaires-INSEE, base 100 = moyenne 2015 · France métropolitaine", source: "Notaires-INSEE"}) : ""}
  ${px.available ? multiLine({rows: filterYears(px.price_yoy, rangeA), meta: px.series_meta, yLabel: "%", yPct: true, lastLabels: false, valueFmt: (v) => nf1.format(v) + " %", tipUnit: " %", filename: "ancien-prix-evolution-annuelle",
    titre: "Évolution annuelle des prix des logements anciens", sousTitre: "Glissement sur un an, en % · France métropolitaine", source: "Notaires-INSEE"}) : ""}
</div>

<div class="hm-panels">
  ${px.available ? multiLine({rows: capacityRows(), meta: [{name: "Capacité d'emprunt", color: series.green}, {name: "Prix (Ensemble)", color: series.brick}], yLabel: "Indice, base 100", baseline: 100, valueFmt: (v) => nf0.format(v), filename: "ancien-capacite-emprunt-vs-prix",
    titre: "Capacité d'emprunt et prix des logements anciens", sousTitre: `Base 100 = 2015 · mensualité constante, prêt sur ${term} ans`, source: "Notaires-INSEE, Banque de France (taux du crédit habitat) ; calcul du site"}) : ""}
  ${px.available ? accessChart() : ""}
</div>

```js
function accessChart() {
  const rows = accessRows().map((d) => ({...d, _x: new Date(d.date)}));
  const plot = Plot.plot({height: 360, marginLeft: 54, marginRight: 60, x: {label: null}, y: {label: "Indice (base 100)", grid: true},
    marks: [
      Plot.areaY(rows, {x: "_x", y: "value", fill: series.brick, fillOpacity: 0.1}),
      Plot.lineY(rows, {x: "_x", y: "value", stroke: series.brick, strokeWidth: 2.2}),
      Plot.ruleY([100], {stroke: "grey", strokeDasharray: "4,4"}),
      Plot.text([{x: rows.at(-1)._x, y: 100}], {x: "x", y: "y", text: () => "niveau 2015", dy: -8, fill: "grey"}),
      Plot.text([rows.at(-1)], {x: "_x", y: "value", text: (d) => nf0.format(d.value), dx: 8, fill: series.brick, fontWeight: 700, textAnchor: "start"}),
      Plot.tip(rows, Plot.pointerX({x: "_x", y: "value", ...TIP, title: (d) => `${fmtMonthFR(d._x)}\n${nf0.format(d.value)}`})),
    ]});
  return cadreGraphique({titre: "Indice d'accessibilité du logement ancien",
    sousTitre: `Capacité d'emprunt ÷ prix, base 100 = 2015 ; sous 100, moins accessible qu'en 2015 · prêt sur ${term} ans`,
    dernier: rows, source: "Notaires-INSEE, Banque de France (taux du crédit habitat) ; calcul du site",
    children: withCsvExport(plot, rows.map(({_x, ...r}) => r), "ancien-indice-accessibilite")});
}
```

```js
// Prix neuf vs ancien (conditionnel) — rendu via display() (évite les blocs inline multi-lignes).
if (px.available && px.new_vs_old.available) {
  const nvo = px.new_vs_old;
  display(html`<h3>Prix des logements neufs vs anciens</h3>`);
  display(html`<div class="hm-panels">
    ${multiLine({rows: filterYears(nvo.levels, rangeA), meta: nvo.series_meta, yLabel: "Indice, base 100", valueFmt: (v) => nf0.format(v), filename: "ancien-prix-neuf-vs-ancien-indices",
      titre: "Prix des logements neufs et anciens", sousTitre: "Indices, base 100 = 2015 · France", source: "INSEE (prix des logements neufs, indices Notaires-INSEE)"})}
    ${multiLine({rows: filterYears(nvo.yoy, rangeA), meta: nvo.series_meta, yLabel: "%", yPct: true, lastLabels: false, valueFmt: (v) => nf1.format(v) + " %", tipUnit: " %", filename: "ancien-prix-neuf-vs-ancien-evolution-annuelle",
      titre: "Évolution annuelle des prix, neuf et ancien", sousTitre: "Glissement sur un an, en % · France", source: "INSEE (prix des logements neufs, indices Notaires-INSEE)"})}
  </div>`);
}
```
