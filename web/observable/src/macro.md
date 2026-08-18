---
title: Environnement & Financement
toc: false
---

```js
import {legend, multiLine, nf0, nf1, fmtMonthFR} from "./components/hm.js";
import {series} from "./components/theme.js";
const macro = await FileAttachment("./data/macro.json").json();
```

# ${macro.title}

<div class="hm-caption">${macro.caption}</div>

```js
// Légende cliquable pour les 3 taux.
const visR = Mutable(new Set(macro.rates.meta.map((m) => m.name)));
function toggleR(name) { const s = new Set(visR.value); s.has(name) ? s.delete(name) : s.add(name); visR.value = s; }
```

<div class="hm-panels">
  <div>
    <div class="hm-panel-title">Indice de Confiance des Ménages (INSEE)</div>
    <div class="hm-panel-sub">CVS, base 100 = moyenne de longue période</div>
    ${multiLine({rows: macro.confidence.map((d) => ({...d, series: "Indice de Confiance"})), meta: [{name: "Indice de Confiance", color: series.brick}], yLabel: "Indice (base 100)", baseline: 100, valueFmt: (v) => nf0.format(v)})}
  </div>
  <div>
    <div class="hm-panel-title">Taux d'intérêt et conditions de financement</div>
    <div class="hm-panel-sub">taux crédit habitat · Euribor 3 mois · OAT 10 ans — en %</div>
    ${legend(macro.rates.meta, visR, toggleR)}
    ${multiLine({rows: macro.rates.rows, meta: macro.rates.meta, active: visR, yLabel: "Taux d'intérêt (%)", valueFmt: (v) => nf1.format(v) + " %", tipUnit: " %"})}
  </div>
</div>

<div class="hm-panels">
  <div>
    <div class="hm-panel-title">Intentions d'achat de logement (1 an)</div>
    <div class="hm-panel-sub">solde CVS centré-réduit (écarts-types)</div>
    ${multiLine({rows: macro.intentions.map((d) => ({...d, series: "Intentions d'achat"})), meta: [{name: "Intentions d'achat", color: series.blue}], yLabel: "Écarts-types", yPct: true, lastLabels: false, valueFmt: (v) => nf1.format(v)})}
  </div>
  <div>
    <div class="hm-panel-title">Taux de chômage au sens du BIT</div>
    <div class="hm-panel-sub">en % de la population active, France hors Mayotte</div>
    ${multiLine({rows: macro.chomage.map((d) => ({...d, series: "Taux de chômage BIT"})), meta: [{name: "Taux de chômage BIT", color: series.brick}], yLabel: "%", valueFmt: (v) => nf1.format(v) + " %", tipUnit: " %"})}
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
    return multiLine({rows: cr.cum.map((d) => ({date: d.date, series: "Total", value: d.total})),
      meta: [{name: "Total", color: series.blue}], yLabel: "Md€", valueFmt: (v) => nf0.format(v)});
  const rows = [];
  for (const d of cr.monthly) {
    rows.push({date: new Date(d.date), cat: "Crédits nouveaux (hors renégo.)", value: d.pure});
    rows.push({date: new Date(d.date), cat: "Renégociations", value: d.renego});
  }
  return Plot.plot({height: 340, marginLeft: 48, x: {label: null}, y: {label: "Md€", grid: true},
    color: {domain: ["Crédits nouveaux (hors renégo.)", "Renégociations"], range: [series.blue, series.gold], legend: true},
    marks: [Plot.rectY(rows, {x: "date", y: "value", fill: "cat", interval: "month", tip: true}), Plot.ruleY([0])]});
}
function creditCum() {
  const rows = [...cr.cum.map((d) => ({date: d.date, series: "Total (y.c. renégo.)", value: d.total}))];
  const meta = [{name: "Total (y.c. renégo.)", color: series.green}];
  if (cr.has_split) {
    rows.push(...cr.cum.filter((d) => d.pure != null).map((d) => ({date: d.date, series: "Hors renégociations", value: d.pure})));
    meta.push({name: "Hors renégociations", color: series.brick, dash: true});
  }
  return multiLine({rows, meta, yLabel: "Md€", valueFmt: (v) => nf0.format(v)});
}

if (cr) {
  display(html`<h2>Volume de crédits à l'habitat</h2>`);
  display(html`<div class="hm-panels">
    ${panel("Production mensuelle de crédits à l'habitat", cr.has_split ? "crédits nouveaux vs renégociations, Md€ par mois" : "y compris renégociations, Md€ par mois", creditMonthly())}
    ${panel("Production cumulée sur 12 mois", "Md€ / an", creditCum())}
  </div>`);
  display(html`<div class="hm-meta">Source : BCE — statistiques MIR (achat de logement, France). Renégociations isolées (décomposition BPCE ; publiée depuis 2019).</div>`);
}

if (bls) {
  display(html`<h2>Demande de crédits à l'habitat (enquête BLS)</h2>`);
  display(html`<div class="hm-panel-sub">solde d'opinion net des banques, en % — &gt;0 = demande en hausse · indicateur avancé</div>`);
  display(multiLine({rows: bls.rows, meta: bls.meta, yLabel: "Solde net (%)", yPct: true, valueFmt: (v) => nf0.format(v) + " %", tipUnit: " %"}));
  display(html`<div class="hm-meta">Source : BCE / Banque de France — Bank Lending Survey, demande de crédits à l'habitat des ménages, France, pourcentage net.</div>`);
}

if (reno.length) {
  display(html`<h2>Rénovation & second œuvre (pilier complémentaire)</h2>`);
  display(html`<div class="hm-panel-sub">solde d'opinion INSEE (enquête bâtiment) — un solde négatif = plus d'entreprises signalant une baisse d'activité</div>`);
  display(multiLine({rows: reno.flatMap((r) => r.rows.map((d) => ({...d, series: r.title}))),
    meta: reno.map((r) => ({name: r.title, color: r.color})), yLabel: "Solde d'opinion", yPct: true, valueFmt: (v) => nf0.format(v)}));
  display(html`<div class="hm-meta">Source : INSEE — Enquête mensuelle de conjoncture dans l'industrie du bâtiment, second œuvre (idbanks 001586954 / 001586886).</div>`);
}
```
