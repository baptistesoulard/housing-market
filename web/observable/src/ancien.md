---
title: Marché de l'ancien
toc: true
---

```js
import {kpiCard, cardGrid, marketChart, multiLine, monthlyByYear, filterYears,
        MONTHS_FULL, nf0, nf1, fmtMonthFR, TIP} from "./components/hm.js";
import {periodFilter} from "./components/period.js";
import {series} from "./components/theme.js";
const anc = await FileAttachment("./data/ancien.json").json();
```

# ${anc.title}

<div class="hm-caption">${anc.caption}</div>

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

<div class="hm-shortcuts hm-shortcuts--twin"><a class="hm-shortcut" href="./neuf#chiffres-cles">🏗️ la même vue pour le neuf</a></div>

${cardGrid([anc.kpi], kpiCard)}

## 📊 Courbes d'évolution du marché


<div class="hm-shortcuts hm-shortcuts--twin"><a class="hm-shortcut" href="./neuf#courbes-d-evolution-du-marche">🏗️ la même vue pour le neuf</a></div>

```js
const viewA = view(Inputs.radio(
  new Map([["Cumul glissant 12 mois", "roll12"], ["Cumul glissant 6 mois", "roll6"], ["Données brutes mensuelles", "raw"]]),
  {value: "roll12", label: "Type de visualisation"}));
const maA = view(Inputs.checkbox(["Moyenne mobile 12 mois", "Moyenne mobile 6 mois"],
  {label: "Superpositions (vue brute uniquement)"}));
```

${marketChart({rows: filterYears(anc.main_series.rows, rangeA), meta: anc.main_series.meta, view: viewA, showMA12: maA.includes("Moyenne mobile 12 mois"), showMA6: maA.includes("Moyenne mobile 6 mois"), yLabel: "Milliers de transactions"})}

<div class="hm-meta">${anc.main_series.source} · dernier point : ${anc.main_series.last_month}</div>

## 📅 Comparaison Mensuelle par Année

<div class="hm-caption">Comparez un ou plusieurs mois d'une année à l'autre. Par défaut, les 3 derniers mois disponibles.</div>

<div class="hm-shortcuts hm-shortcuts--twin"><a class="hm-shortcut" href="./neuf#comparaison-mensuelle-par-annee">🏗️ la même vue pour le neuf</a></div>

```js
const lmA = anc.monthly.last_month_num;
const defMonthsA = [0, 1, 2].map((k) => MONTHS_FULL[((lmA - k - 1) + 12) % 12]);
const monthsA = view(Inputs.checkbox(MONTHS_FULL, {value: defMonthsA, label: "Mois à comparer"}));
```

```js
const monthNumsA = monthsA.map((m) => MONTHS_FULL.indexOf(m) + 1).filter((n) => n > 0);
display(monthNumsA.length
  ? monthlyByYear({rows: filterYears(anc.monthly.rows, rangeA), valueKey: "tx", monthNums: monthNumsA, scheme: "Greens"})
  : html`<div class="hm-caption">Sélectionnez au moins un mois.</div>`);
```

<div class="hm-meta">Source : IGEDD</div>

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
  <div>
    <div class="hm-panel-title">Prix des logements anciens</div>
    <div class="hm-panel-sub">indices Notaires-INSEE, base 100 = 2015</div>
    ${px.available ? multiLine({rows: filterYears(px.price_levels, rangeA), meta: px.series_meta, yLabel: "Indice (base 100)", valueFmt: (v) => nf0.format(v)}) : ""}
  </div>
  <div>
    <div class="hm-panel-title">Évolution annuelle des prix</div>
    <div class="hm-panel-sub">glissement sur 1 an, %</div>
    ${px.available ? multiLine({rows: filterYears(px.price_yoy, rangeA), meta: px.series_meta, yLabel: "%", yPct: true, lastLabels: false, valueFmt: (v) => nf1.format(v) + " %", tipUnit: " %"}) : ""}
  </div>
</div>

<div class="hm-panels">
  <div>
    <div class="hm-panel-title">Capacité d'emprunt vs prix</div>
    <div class="hm-panel-sub">base 100 = 2015 · mensualité constante, ${term} ans</div>
    ${px.available ? multiLine({rows: capacityRows(), meta: [{name: "Capacité d'emprunt", color: series.green}, {name: "Prix (Ensemble)", color: series.brick}], yLabel: "Indice (base 100)", baseline: 100, valueFmt: (v) => nf0.format(v)}) : ""}
  </div>
  <div>
    <div class="hm-panel-title">Indice d'accessibilité</div>
    <div class="hm-panel-sub">capacité d'emprunt ÷ prix, base 100 = 2015 · sous 100 = moins accessible qu'en 2015</div>
    ${px.available ? accessChart() : ""}
  </div>
</div>

```js
function accessChart() {
  const rows = accessRows().map((d) => ({...d, _x: new Date(d.date)}));
  return Plot.plot({height: 360, marginLeft: 54, marginRight: 60, x: {label: null}, y: {label: "Indice (base 100)", grid: true},
    marks: [
      Plot.areaY(rows, {x: "_x", y: "value", fill: series.brick, fillOpacity: 0.1}),
      Plot.lineY(rows, {x: "_x", y: "value", stroke: series.brick, strokeWidth: 2.2}),
      Plot.ruleY([100], {stroke: "grey", strokeDasharray: "4,4"}),
      Plot.text([{x: rows.at(-1)._x, y: 100}], {x: "x", y: "y", text: () => "niveau 2015", dy: -8, fill: "grey"}),
      Plot.text([rows.at(-1)], {x: "_x", y: "value", text: (d) => nf0.format(d.value), dx: 8, fill: series.brick, fontWeight: 700, textAnchor: "start"}),
      Plot.tip(rows, Plot.pointerX({x: "_x", y: "value", ...TIP, title: (d) => `${fmtMonthFR(d._x)}\n${nf0.format(d.value)}`})),
    ]});
}
```

```js
// Prix neuf vs ancien (conditionnel) — rendu via display() (évite les blocs inline multi-lignes).
if (px.available && px.new_vs_old.available) {
  const nvo = px.new_vs_old;
  display(html`<h3>Prix des logements neufs vs anciens</h3>`);
  display(html`<div class="hm-panels">
    <div>
      <div class="hm-panel-title">Indices de prix</div>
      <div class="hm-panel-sub">neuf & ancien, base 100 = 2015</div>
      ${multiLine({rows: filterYears(nvo.levels, rangeA), meta: nvo.series_meta, yLabel: "Indice (base 100)", valueFmt: (v) => nf0.format(v)})}
    </div>
    <div>
      <div class="hm-panel-title">Croissance en glissement annuel</div>
      <div class="hm-panel-sub">neuf & ancien, %</div>
      ${multiLine({rows: filterYears(nvo.yoy, rangeA), meta: nvo.series_meta, yLabel: "%", yPct: true, lastLabels: false, valueFmt: (v) => nf1.format(v) + " %", tipUnit: " %"})}
    </div>
  </div>`);
}
```

<div class="hm-meta">Sources : INSEE (prix Notaires-INSEE) · Banque de France/BCE (taux crédit habitat) · calcul de l'auteur pour la capacité et l'accessibilité.</div>
