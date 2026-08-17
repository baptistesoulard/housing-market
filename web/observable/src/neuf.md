---
title: Marché du neuf
toc: false
---

```js
import {kpiCard, cardGrid, legend, marketChart, multiLine, monthlyByYear,
        MONTHS_FULL, MONTHS_SHORT, nf0, nf1, fmtMonthFR} from "./components/hm.js";
const neuf = await FileAttachment("./data/neuf.json").json();
```

# ${neuf.title}

<div class="hm-caption">${neuf.caption}</div>

## 🔑 Chiffres Clés

<div class="hm-caption">Chiffres nationaux au dernier mois disponible — indépendants de toute segmentation.</div>

${cardGrid(neuf.kpis, kpiCard)}

## 📊 Courbes d'évolution du marché

```js
const viewN = view(Inputs.radio(
  new Map([["Cumul glissant 12 mois", "roll12"], ["Cumul glissant 6 mois", "roll6"], ["Données brutes mensuelles", "raw"]]),
  {value: "roll12", label: "Type de visualisation"}));
const maN = view(Inputs.checkbox(["Moyenne mobile 12 mois", "Moyenne mobile 6 mois"],
  {label: "Superpositions (vue brute uniquement)"}));
```

```js
// État réactif : séries visibles (clic-légende comme Plotly). Partagé avec le graphique.
const visN = Mutable(new Set(neuf.main_series.meta.map((m) => m.name)));
function toggleN(name) { const s = new Set(visN.value); s.has(name) ? s.delete(name) : s.add(name); visN.value = s; }
```

<div class="hm-caption">Cliquez une série de la légende pour la masquer / l'afficher.</div>

${legend(neuf.main_series.meta, visN, toggleN)}

${marketChart({rows: neuf.main_series.rows, meta: neuf.main_series.meta, view: viewN, showMA12: maN.includes("Moyenne mobile 12 mois"), showMA6: maN.includes("Moyenne mobile 6 mois"), active: visN, yLabel: "Milliers de logements"})}

<div class="hm-meta">${neuf.main_series.source} · dernier point : ${neuf.main_series.last_month}</div>

## 🏠 Dynamique Individuel vs Collectif

<div class="hm-caption">Le logement individuel — surtout l'individuel pur — porte bien plus de contenu second œuvre (fermetures, menuiseries, sécurité, domotique) qu'un logement collectif : c'est le driver de volume le plus direct.</div>

```js
const ivMetric = view(Inputs.radio(
  new Map([["Mises en Chantier", "MisesEnChantier"], ["Permis de Construire", "Permis"]]),
  {value: "MisesEnChantier", label: "Indicateur"}));
```

```js
const ivBlock = neuf.indiv_collectif[ivMetric];
const ivMeta = [...new Map(ivBlock.lines.map((d) => [d.series, {name: d.series, color: d.color}])).values()];
```

${cardGrid(ivBlock.kpis, (k) => kpiCard({label: k.label, value: k.val12, delta: k.roll12_yoy ? k.roll12_yoy + " sur 12 mois" : null, subs: [`3 derniers mois vs n-1 : ${k.last3_yoy}`]}))}

<div class="hm-panel-title">${ivMetric === "Permis" ? "Permis de Construire" : "Mises en Chantier"} — maison individuelle pure vs collectif <span style="color:#6c757d;font-weight:400">(cumul sur 12 mois, en milliers)</span></div>

${multiLine({rows: ivBlock.lines, meta: ivMeta, yLabel: "Milliers de logements", valueFmt: (v) => nf1.format(v), tipUnit: " k"})}

## 📅 Comparaison Mensuelle par Année

<div class="hm-caption">Comparez un ou plusieurs mois d'une année à l'autre. Par défaut, les 3 derniers mois disponibles.</div>

```js
const lmN = neuf.monthly.last_month_num;
const defMonthsN = [0, 1, 2].map((k) => MONTHS_FULL[((lmN - k - 1) + 12) % 12]);
const mMetricN = view(Inputs.radio(
  new Map([["Permis de Construire", "permis"], ["Mises en Chantier", "mises"]]),
  {value: "permis", label: "Indicateur"}));
const monthsN = view(Inputs.checkbox(MONTHS_FULL, {value: defMonthsN, label: "Mois à comparer"}));
```

```js
const monthNumsN = monthsN.map((m) => MONTHS_FULL.indexOf(m) + 1).filter((n) => n > 0);
display(monthNumsN.length
  ? monthlyByYear({rows: neuf.monthly.rows, valueKey: mMetricN, monthNums: monthNumsN})
  : html`<div class="hm-caption">Sélectionnez au moins un mois.</div>`);
```

<div class="hm-meta">Source : SIT@DEL (SDES)</div>

```js
// ============================ Section ECLN ============================
const e = neuf.ecln;
```

## 🏗️ Commercialisation des logements neufs (ECLN)

<div class="hm-caption">Commercialisation des logements neufs (SDES — ECLN, national, trimestriel CVS-CJO) : encours, mises en vente, délai d'écoulement, prix au m² et réservations par catégorie d'acquéreurs. Le délai d'écoulement — proche de deux ans — est un signal avancé de la demande de second œuvre.</div>

${e ? cardGrid(e.kpis, (k) => kpiCard({label: k.label, value: k.value})) : html`<div class="hm-caption">Données ECLN indisponibles.</div>`}

${e ? html`<div class="hm-meta">Dernier trimestre disponible : ${e.last_quarter} · Source : SDES — ECLN (CVS-CJO).</div>` : ""}

```js
// Charts ECLN (rendus seulement si les données existent).
function eclnStock() {
  const rows = [
    ...e.stock_rows.map((d) => ({date: d.date, series: "Encours à la vente", value: d.encours})),
    ...e.stock_rows.map((d) => ({date: d.date, series: "Mises en vente", value: d.mises_en_vente})),
  ];
  return multiLine({rows, meta: [{name: "Encours à la vente", color: "#2D3748"}, {name: "Mises en vente", color: "#64B5F6"}],
    yLabel: "Nombre de logements", valueFmt: (v) => nf0.format(v)});
}
function eclnDelai() {
  const rows = e.delai_rows.map((d) => ({...d, _x: new Date(d.date)}));
  return Plot.plot({height: 340, marginLeft: 48, marginRight: 60, y: {label: "Mois", grid: true, zero: true}, x: {label: null},
    marks: [
      Plot.areaY(rows, {x: "_x", y: "delai_mois", fill: "#E64A19", fillOpacity: 0.12}),
      Plot.lineY(rows, {x: "_x", y: "delai_mois", stroke: "#E64A19", strokeWidth: 2.4}),
      Plot.ruleY([24], {stroke: "grey", strokeDasharray: "4,4"}),
      Plot.text([{x: rows.at(-1)._x, y: 24}], {x: "x", y: "y", text: () => "≈ 2 ans", dy: -8, fill: "grey"}),
      Plot.tip(rows, Plot.pointerX({x: "_x", y: "delai_mois", title: (d) => `${fmtMonthFR(d._x)}\n${nf0.format(d.delai_mois)} mois`})),
    ]});
}
function eclnCat() {
  const rows = [];
  const map = {particuliers: "Particuliers", sociaux: "Bailleurs sociaux", institutionnels: "Investisseurs institutionnels"};
  for (const d of e.cat_rows) for (const k of Object.keys(map)) rows.push({date: new Date(d.date), cat: map[k], value: d[k]});
  return Plot.plot({height: 340, marginLeft: 54, x: {label: null}, y: {label: "Réservations", grid: true},
    color: {domain: ["Particuliers", "Bailleurs sociaux", "Investisseurs institutionnels"], range: ["#E64A19", "#64B5F6", "#F5B041"], legend: true},
    marks: [Plot.rectY(rows, {x: "date", y: "value", fill: "cat", interval: "3 months", tip: true}), Plot.ruleY([0])]});
}
function eclnPrix() {
  const rows = e.prixm2_rows.map((d) => ({date: d.date, series: "Prix au m²", value: d.prix}));
  return multiLine({rows, meta: [{name: "Prix au m²", color: "#388E3C"}], yLabel: "€/m²", valueFmt: (v) => nf0.format(v), tipUnit: " €/m²"});
}
```

<div class="hm-panels">
  <div>
    <div class="hm-panel-title">Encours & mises en vente</div>
    <div class="hm-panel-sub">encours = stock fin de trimestre · mises en vente = flux trimestriel</div>
    ${e ? eclnStock() : ""}
  </div>
  <div>
    <div class="hm-panel-title">Délai d'écoulement du stock</div>
    <div class="hm-panel-sub">mois de commercialisation</div>
    ${e ? eclnDelai() : ""}
  </div>
</div>

<div class="hm-panels">
  <div>
    <div class="hm-panel-title">Réservations par catégorie d'acquéreurs</div>
    <div class="hm-panel-sub">logements neufs, par trimestre</div>
    ${e ? eclnCat() : ""}
  </div>
  <div>
    <div class="hm-panel-title">Prix des appartements neufs</div>
    <div class="hm-panel-sub">prix moyen au m² (collectif)</div>
    ${e ? eclnPrix() : ""}
  </div>
</div>

<div class="hm-meta">Source : SDES — ECLN (CVS-CJO)</div>
