---
title: Marché du neuf
toc: true
---

```js
import {kpiCard, cardGrid, legend, marketChart, multiLine, monthlyByYear,
        filterYears, sumByType, withCsvExport,
        MONTHS_FULL, MONTHS_SHORT, nf0, nf1, fmtMonthFR, TIP} from "./components/hm.js";
import {periodFilter} from "./components/period.js";
import {series} from "./components/theme.js";
const neuf = await FileAttachment("./data/neuf.json").json();
```

# ${neuf.title}

<div class="hm-caption">${neuf.caption}</div>

<details class="hm-howto">
  <summary>ℹ️ Comment lire cette page</summary>
  <div class="hm-caption">${neuf.how_to_read}</div>
</details>

```js
// --- Contrôles de la page (parité avec la barre latérale + le panneau
// « paramètres supplémentaires » de l'app Streamlit). --------------------------------
// La période vient de la frise GLOBALE de la barre latérale (components/period.js) :
// même contrôle et même valeur sur tous les onglets, comme le curseur d'années de la
// barre latérale Streamlit.
const rangeN = Generators.input(periodFilter({min: neuf.period.min, max: neuf.period.max}));
const typesN = view(Inputs.checkbox(neuf.by_type.types.map((t) => t.name),
  {value: neuf.by_type.types.map((t) => t.name), label: "Types de logement (SIT@DEL)"}));
```

```js
// Aucun type coché = tous les types, comme le multiselect vide d'app.py.
const pickedN = neuf.by_type.types.filter((t) => typesN.includes(t.name)).map((t) => t.code);
const codesN = pickedN.length ? pickedN : neuf.by_type.types.map((t) => t.code);
const allTypesN = codesN.length === neuf.by_type.types.length;
// Tous types : on réutilise la série et les KPI déjà prêts. Sinon on somme les types
// retenus (exact) et on lit les KPI pré-calculés côté Python pour ce sous-ensemble.
const seriesRowsN = allTypesN
  ? neuf.main_series.rows
  : sumByType(neuf.by_type, codesN, neuf.main_series.meta);
const kpisN = allTypesN
  ? neuf.kpis
  : [...neuf.kpis_by_type[codesN.slice().sort().join("+")], ...neuf.kpis.slice(2)];
const segLabelN = allTypesN ? "tous types" :
  neuf.by_type.types.filter((t) => codesN.includes(t.code)).map((t) => t.name).join(" + ");
```

## 🔑 Chiffres Clés

<div class="hm-caption">Chiffres nationaux au dernier mois disponible — indépendants de la période affichée, mais calculés sur la segmentation retenue (${segLabelN}).</div>

<div class="hm-shortcuts hm-shortcuts--twin"><a class="hm-shortcut" href="./ancien#chiffres-cles">🏠 la même vue pour l'ancien</a></div>

${cardGrid(kpisN, kpiCard)}

## 📊 Courbes d'évolution du marché


<div class="hm-shortcuts hm-shortcuts--twin"><a class="hm-shortcut" href="./ancien#courbes-d-evolution-du-marche">🏠 la même vue pour l'ancien</a></div>

```js
const viewN = view(Inputs.radio(
  new Map([["Cumul glissant 12 mois", "roll12"], ["Cumul glissant 6 mois", "roll6"],
           ["Cumul glissant 3 mois", "roll3"], ["Données brutes mensuelles", "raw"]]),
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

${marketChart({rows: filterYears(seriesRowsN, rangeN), meta: neuf.main_series.meta, view: viewN, showMA12: maN.includes("Moyenne mobile 12 mois"), showMA6: maN.includes("Moyenne mobile 6 mois"), active: visN, yLabel: "Milliers de logements", filename: "marche-neuf"})}

<div class="hm-meta">${neuf.main_series.source} · dernier point : ${neuf.main_series.last_month} · segmentation : ${segLabelN} · période affichée : ${Math.min(...rangeN)}–${Math.max(...rangeN)}</div>

## 📅 Comparaison Mensuelle par Année

<div class="hm-caption">Comparez un ou plusieurs mois d'une année à l'autre. Par défaut, les 3 derniers mois disponibles.</div>

<div class="hm-shortcuts hm-shortcuts--twin"><a class="hm-shortcut" href="./ancien#comparaison-mensuelle-par-annee">🏠 la même vue pour l'ancien</a></div>

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
  ? monthlyByYear({rows: filterYears(neuf.monthly.rows, rangeN), valueKey: mMetricN, monthNums: monthNumsN, filename: "neuf-comparaison-mensuelle-" + mMetricN})
  : html`<div class="hm-caption">Sélectionnez au moins un mois.</div>`);
```

<div class="hm-meta">Source : SIT@DEL (SDES)</div>

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

<div class="hm-panel-title">${ivMetric === "Permis" ? "Permis de Construire" : "Mises en Chantier"} — maison individuelle pure vs collectif <span style="color:var(--hm-subtle);font-weight:400">(cumul sur 12 mois, en milliers)</span></div>

${multiLine({rows: filterYears(ivBlock.lines, rangeN), meta: ivMeta, yLabel: "Milliers de logements", valueFmt: (v) => nf1.format(v), tipUnit: " k", filename: "neuf-individuel-vs-collectif-" + ivMetric})}

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
    ...filterYears(e.stock_rows, rangeN).map((d) => ({date: d.date, series: "Encours à la vente", value: d.encours})),
    ...filterYears(e.stock_rows, rangeN).map((d) => ({date: d.date, series: "Mises en vente", value: d.mises_en_vente})),
  ];
  return multiLine({rows, meta: [{name: "Encours à la vente", color: series.violet}, {name: "Mises en vente", color: series.blue}],
    yLabel: "Nombre de logements", valueFmt: (v) => nf0.format(v), filename: "neuf-ecln-encours-mises-en-vente"});
}
function eclnDelai() {
  const rows = filterYears(e.delai_rows, rangeN).map((d) => ({...d, _x: new Date(d.date)}));
  const plot = Plot.plot({height: 340, marginLeft: 48, marginRight: 60, y: {label: "Mois", grid: true, zero: true}, x: {label: null},
    marks: [
      Plot.areaY(rows, {x: "_x", y: "delai_mois", fill: series.brick, fillOpacity: 0.12}),
      Plot.lineY(rows, {x: "_x", y: "delai_mois", stroke: series.brick, strokeWidth: 2.4}),
      Plot.ruleY([24], {stroke: "grey", strokeDasharray: "4,4"}),
      Plot.text([{x: rows.at(-1)._x, y: 24}], {x: "x", y: "y", text: () => "≈ 2 ans", dy: -8, fill: "grey"}),
      Plot.tip(rows, Plot.pointerX({x: "_x", y: "delai_mois", ...TIP, title: (d) => `${fmtMonthFR(d._x)}\n${nf0.format(d.delai_mois)} mois`})),
    ]});
  return withCsvExport(plot, rows.map(({_x, ...r}) => r), "neuf-ecln-delai-ecoulement");
}
function eclnCat() {
  const rows = [];
  const map = {particuliers: "Particuliers", sociaux: "Bailleurs sociaux", institutionnels: "Investisseurs institutionnels"};
  for (const d of filterYears(e.cat_rows, rangeN)) for (const k of Object.keys(map)) rows.push({date: d.date, cat: map[k], value: d[k]});
  const plotRows = rows.map((r) => ({...r, date: new Date(r.date)}));
  const plot = Plot.plot({height: 340, marginLeft: 54, x: {label: null}, y: {label: "Réservations", grid: true},
    color: {domain: ["Particuliers", "Bailleurs sociaux", "Investisseurs institutionnels"], range: [series.brick, series.blue, series.gold], legend: true},
    marks: [Plot.rectY(plotRows, {x: "date", y: "value", fill: "cat", interval: "3 months", tip: {...TIP}}), Plot.ruleY([0])]});
  return withCsvExport(plot, rows, "neuf-ecln-reservations-par-categorie");
}
function eclnPrix() {
  const rows = filterYears(e.prixm2_rows, rangeN).map((d) => ({date: d.date, series: "Prix au m²", value: d.prix}));
  return multiLine({rows, meta: [{name: "Prix au m²", color: series.green}], yLabel: "€/m²", valueFmt: (v) => nf0.format(v), tipUnit: " €/m²", filename: "neuf-ecln-prix-m2"});
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
