---
title: Actualités & Aides
toc: false
---

```js
import {kpiCard, cardGrid} from "./components/hm.js";
import {series, delta, ui} from "./components/theme.js";
const A = await FileAttachment("./data/actualites.json").json();
```

# ${A.title}

<div class="hm-caption">${A.caption}</div>

<details class="hm-howto">
  <summary>ℹ️ Comment lire cette page</summary>
  <div class="hm-caption">${A.how_to_read}</div>
</details>
<div class="hm-meta">⚠️ Contenu éditorial mis à jour manuellement (dernière revue : ${A.maj}). Les impacts sont des lectures qualitatives, pas des sorties de modèle.</div>

${cardGrid(A.kpis, kpiCard)}

## 🔎 Filtres

```js
const catSel = view(Inputs.checkbox(Object.keys(A.category_labels), {value: Object.keys(A.category_labels), format: (k) => A.category_labels[k], label: "Périmètre"}));
const statSel = view(Inputs.checkbox(Object.keys(A.statut_labels), {value: Object.keys(A.statut_labels), format: (k) => A.statut_labels[k], label: "Statut"}));
const pilSel = view(Inputs.checkbox(Object.keys(A.pilier_labels), {value: Object.keys(A.pilier_labels), format: (k) => A.pilier_labels[k], label: "Pilier impacté (non neutre)"}));
```

```js
const items = A.items.filter((it) =>
  catSel.includes(it.categorie) && statSel.includes(it.statut) &&
  (pilSel.length === 0 || pilSel.some((p) => it.impacts[p] !== 0) || Object.values(it.impacts).every((v) => v === 0)));
```

## 🎯 Matrice d'impact par pilier

<div class="hm-caption">Lecture qualitative de la direction attendue : ⬆⬆ soutien fort · ⬆ soutien · ➖ neutre/mitigé · ⬇ frein.</div>

```js
function impactColor(v) { return v > 0 ? delta.positive : v < 0 ? delta.negative : delta.neutral; }
function impactMatrix(items) {
  const pil = Object.keys(A.pilier_labels);
  return html`<table class="hm-table">
    <thead><tr><th>Dispositif</th>${pil.map((p) => html`<th>${A.pilier_labels[p]}</th>`)}</tr></thead>
    <tbody>${items.map((it) => html`<tr>
      <td>${A.category_labels[it.categorie].split(" ")[0]} ${it.court}</td>
      ${pil.map((p) => html`<td style=${{color: impactColor(it.impacts[p]), fontWeight: 600, whiteSpace: "nowrap"}}>${A.impact_labels[it.impacts[p]]}</td>`)}
    </tr>`)}</tbody></table>`;
}
```

```js
display(items.length ? impactMatrix(items) : html`<div class="hm-caption">Aucune mesure ne correspond aux filtres.</div>`);
```

## 🗓️ Échéancier des mesures

```js
function timeline(items) {
  const rows = [];
  for (const it of items) for (const j of it.jalons)
    rows.push({date: new Date(j.date), dispositif: it.court, jalon: j.label, type: j.type, categorie: it.categorie});
  if (!rows.length) return html`<div class="hm-caption">Aucun jalon à afficher.</div>`;
  const order = [...new Set(items.map((it) => it.court))];
  const symMap = {effet: "circle", jalon: "diamond", echeance: "times"};
  return Plot.plot({
    height: Math.max(240, 54 + 30 * order.length), marginLeft: 170, marginTop: 30,
    x: {label: null}, y: {domain: order, label: null},
    color: {domain: ["FR", "EU"], range: [series.brick, series.blue], legend: true, label: "Périmètre"},
    symbol: {domain: ["effet", "jalon", "echeance"], range: ["circle", "diamond", "times"],
             legend: true, label: "Type", tickFormat: (t) => A.jalon_types[t].label},
    marks: [
      Plot.ruleX([new Date(A.maj)], {stroke: ui.greyLine, strokeDasharray: "4,4"}),
      Plot.dot(rows, {x: "date", y: "dispositif", fill: "categorie", symbol: "type", r: 6, stroke: "white",
        channels: {jalon: "jalon"}, tip: {format: {x: (d) => d.toLocaleDateString("fr-FR"), fill: false, symbol: false, y: true, jalon: true}}}),
    ],
  });
}
display(timeline(items));
```

<div class="hm-meta">🔴 mesures françaises · 🔵 mesures européennes. ● entrée en vigueur · ◆ jalon · ✕ échéance/attendu. Ligne pointillée = date de la dernière revue.</div>

## 🗞️ Le détail des mesures

```js
function measureCard(it) {
  const pil = ["neuf", "ancien", "renovation"];
  return html`<details class="hm-measure">
    <summary>${A.category_labels[it.categorie].split(" ")[0]} <b>${it.titre}</b> — ${A.statut_labels[it.statut]}</summary>
    <div class="hm-measure-body">
      <div style="white-space:pre-line;margin-bottom:0.6rem">${it.resume}</div>
      <div class="hm-meta">
        ${it.montant ? html`<span><b>💶 Chiffre clé :</b> ${it.montant} &nbsp;·&nbsp; </span>` : ""}
        <span><b>⏳ Horizon :</b> ${it.horizon}</span>
        ${it.echeance ? html`<span> &nbsp;·&nbsp; <b>📅 Échéance :</b> ${it.echeance.date} — ${it.echeance.label}</span>` : ""}
      </div>
      <div class="hm-impacts">${pil.map((p) => html`<div><div class="hm-card-sub">${A.pilier_labels[p]}</div><div style=${{color: impactColor(it.impacts[p]), fontWeight: 700}}>${A.impact_labels[it.impacts[p]]}</div></div>`)}</div>
      <div style="margin-top:0.5rem"><b>🎯 Impact potentiel</b> — ${it.impact_detail}</div>
      <div class="hm-meta" style="margin-top:0.4rem">Sources : ${it.sources.map((s, i) => html`${i ? " · " : ""}<a href=${s.url} target="_blank" rel="noopener">${s.label}</a>`)}</div>
    </div>
  </details>`;
}
display(html`<div>${items.map(measureCard)}</div>`);
```

<style>
.hm-table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
.hm-table th, .hm-table td { text-align: left; padding: 0.45rem 0.7rem; border-bottom: 1px solid var(--hm-border-light); }
.hm-table th { font-weight: 700; color: var(--hm-ink); }
.hm-measure { border: 1px solid var(--hm-border); border-radius: 8px; margin: 0.5rem 0; padding: 0.2rem 0.9rem; }
.hm-measure summary { cursor: pointer; padding: 0.55rem 0; font-size: 1rem; }
.hm-measure-body { padding: 0.2rem 0 0.7rem; }
.hm-impacts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.6rem; margin: 0.6rem 0; }
</style>
