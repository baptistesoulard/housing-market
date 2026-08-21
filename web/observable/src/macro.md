---
title: Environnement & Financement
toc: true
---

```js
import {legend, multiLine, filterYears, nf0, nf1, fmtMonthFR, TIP} from "./components/hm.js";
import {periodFilter} from "./components/period.js";
import {series} from "./components/theme.js";
const macro = await FileAttachment("./data/macro.json").json();
```

# ${macro.title}

<div class="hm-caption">${macro.caption}</div>

<details class="hm-howto">
  <summary>ℹ️ Comment lire cette page</summary>
  <div class="hm-caption">${macro.how_to_read}</div>
</details>

```js
// Filtre de période : la frise GLOBALE de la barre latérale, partagée par tous les
// onglets (parité avec le curseur d'années de la barre latérale Streamlit).
const rangeM = Generators.input(periodFilter({min: macro.period.min, max: macro.period.max}));
```

```js
// Légende cliquable pour les 3 taux.
const visR = Mutable(new Set(macro.rates.meta.map((m) => m.name)));
function toggleR(name) { const s = new Set(visR.value); s.has(name) ? s.delete(name) : s.add(name); visR.value = s; }
```

## 📉 Confiance, taux et emploi

<div class="hm-caption">Les quatre indicateurs qui décrivent la capacité et l'envie d'acheter : moral des ménages, coût de l'argent, intentions déclarées et marché du travail.</div>

<div class="hm-panels">
  <div>
    <div class="hm-panel-title">Indice de Confiance des Ménages (INSEE)</div>
    <div class="hm-panel-sub">CVS, base 100 = moyenne de longue période</div>
    ${multiLine({rows: filterYears(macro.confidence, rangeM).map((d) => ({...d, series: "Indice de Confiance"})), meta: [{name: "Indice de Confiance", color: series.brick}], yLabel: "Indice (base 100)", baseline: 100, valueFmt: (v) => nf0.format(v)})}
  </div>
  <div>
    <div class="hm-panel-title">Taux d'intérêt et conditions de financement</div>
    <div class="hm-panel-sub">taux crédit habitat · Euribor 3 mois · OAT 10 ans — en %</div>
    ${legend(macro.rates.meta, visR, toggleR)}
    ${multiLine({rows: filterYears(macro.rates.rows, rangeM), meta: macro.rates.meta, active: visR, yLabel: "Taux d'intérêt (%)", valueFmt: (v) => nf1.format(v) + " %", tipUnit: " %"})}
  </div>
</div>

<div class="hm-panels">
  <div>
    <div class="hm-panel-title">Intentions d'achat de logement (1 an)</div>
    <div class="hm-panel-sub">solde CVS centré-réduit (écarts-types)</div>
    ${multiLine({rows: filterYears(macro.intentions, rangeM).map((d) => ({...d, series: "Intentions d'achat"})), meta: [{name: "Intentions d'achat", color: series.blue}], yLabel: "Écarts-types", yPct: true, lastLabels: false, valueFmt: (v) => nf1.format(v)})}
  </div>
  <div>
    <div class="hm-panel-title">Taux de chômage au sens du BIT</div>
    <div class="hm-panel-sub">en % de la population active, France hors Mayotte</div>
    ${multiLine({rows: filterYears(macro.chomage, rangeM).map((d) => ({...d, series: "Taux de chômage BIT"})), meta: [{name: "Taux de chômage BIT", color: series.brick}], yLabel: "%", valueFmt: (v) => nf1.format(v) + " %", tipUnit: " %"})}
  </div>
</div>

<div class="hm-meta">Sources : INSEE (confiance, intentions, chômage) · Banque de France / BCE (taux crédit habitat, Euribor, OAT).</div>

```js
// Sections conditionnelles (crédits / BLS / rénovation) rendues via display().
const cr = macro.credit, bls = macro.bls, reno = macro.renovation;

function panel(title, sub, node) {
  return html`<div><div class="hm-panel-title">${title}</div><div class="hm-panel-sub">${sub}</div>${node}</div>`;
}
function creditMonthly() {
  if (!cr.has_split)
    return multiLine({rows: filterYears(cr.cum, rangeM).map((d) => ({date: d.date, series: "Total", value: d.total})),
      meta: [{name: "Total", color: series.blue}], yLabel: "Md€", valueFmt: (v) => nf0.format(v)});
  const rows = [];
  for (const d of filterYears(cr.monthly, rangeM)) {
    rows.push({date: new Date(d.date), cat: "Crédits nouveaux (hors renégo.)", value: d.pure});
    rows.push({date: new Date(d.date), cat: "Renégociations", value: d.renego});
  }
  return Plot.plot({height: 340, marginLeft: 48, x: {label: null}, y: {label: "Md€", grid: true},
    color: {domain: ["Crédits nouveaux (hors renégo.)", "Renégociations"], range: [series.blue, series.gold], legend: true},
    marks: [Plot.rectY(rows, {x: "date", y: "value", fill: "cat", interval: "month", tip: {...TIP}}), Plot.ruleY([0])]});
}
function creditCum() {
  const rows = [...filterYears(cr.cum, rangeM).map((d) => ({date: d.date, series: "Total (y.c. renégo.)", value: d.total}))];
  const meta = [{name: "Total (y.c. renégo.)", color: series.green}];
  if (cr.has_split) {
    rows.push(...filterYears(cr.cum, rangeM).filter((d) => d.pure != null).map((d) => ({date: d.date, series: "Hors renégociations", value: d.pure})));
    meta.push({name: "Hors renégociations", color: series.brick, dash: true});
  }
  return multiLine({rows, meta, yLabel: "Md€", valueFmt: (v) => nf0.format(v)});
}

// Un titre suivi de rien se lit comme une panne du site, alors que c'est une série
// absente de l'export. Ces trois sections restent conditionnelles, mais le disent.
const indisponible = (quoi) => html`<div class="hm-caption">${quoi} : série absente de cet
  export. La page « À propos » liste les séries publiées et leur dernier point.</div>`;
```

## 💶 Volume de crédits à l'habitat

```js
display(cr ? html`<div class="hm-panels">
    ${panel("Production mensuelle de crédits à l'habitat", cr.has_split ? "crédits nouveaux vs renégociations, Md€ par mois" : "y compris renégociations, Md€ par mois", creditMonthly())}
    ${panel("Production cumulée sur 12 mois", "Md€ / an", creditCum())}
  </div>` : indisponible("Production de crédits à l'habitat"));
display(cr ? html`<div class="hm-meta">Source : BCE — statistiques MIR (achat de logement, France). Renégociations isolées (décomposition BPCE ; publiée depuis 2019).</div>` : "");
```

## 🏦 Demande de crédits à l'habitat (enquête BLS)

```js
display(bls ? html`<div class="hm-panel-sub">solde d'opinion net des banques, en % — &gt;0 = demande en hausse · indicateur avancé</div>` : indisponible("Demande de crédits (BLS)"));
display(bls ? multiLine({rows: filterYears(bls.rows, rangeM), meta: bls.meta, yLabel: "Solde net (%)", yPct: true, valueFmt: (v) => nf0.format(v) + " %", tipUnit: " %"}) : "");
display(bls ? html`<div class="hm-meta">Source : BCE / Banque de France — Bank Lending Survey, demande de crédits à l'habitat des ménages, France, pourcentage net.</div>` : "");
```

## 🔨 Rénovation & second œuvre

```js
display(reno.length ? html`<div class="hm-panel-sub">solde d'opinion INSEE (enquête bâtiment) — un solde négatif = plus d'entreprises signalant une baisse d'activité</div>` : indisponible("Activité du second œuvre"));
display(reno.length ? multiLine({rows: reno.flatMap((r) => filterYears(r.rows, rangeM).map((d) => ({...d, series: r.title}))),
  meta: reno.map((r) => ({name: r.title, color: r.color})), yLabel: "Solde d'opinion", yPct: true, valueFmt: (v) => nf0.format(v)}) : "");
display(reno.length ? html`<div class="hm-meta">Source : INSEE — Enquête mensuelle de conjoncture dans l'industrie du bâtiment, second œuvre (idbanks 001586954 / 001586886).</div>` : "");
```
