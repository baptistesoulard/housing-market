---
title: Construction non résidentielle
toc: true
---

```js
import {kpiCard, cardGrid, legendStatic, multiLine, filterYears, withCsvExport,
        nf0, nf1, fmtMonthFR, TIP, Plot} from "./components/hm.js";
import {periodFilter} from "./components/period.js";
import {ui} from "./components/theme.js";
const L = await FileAttachment("./data/locaux.json").json();
```

<!--
  TITRE ET CHAPEAU STATIQUES — rendus au build, seul texte de la page que lisent Google et
  les aperçus de partage. AUCUN chiffre ici (voir CLAUDE.md, « Texte statique ») : la part
  des locaux dans la construction, leur niveau, leur tendance changent chaque mois et
  vivent dans locaux.json (web/export/page_locaux.py).
-->

# 🏭 Construction non résidentielle — bureaux, entrepôts, commerces

Les logements ne sont qu'une partie de la construction neuve. L'autre, ce sont les locaux :
entrepôts logistiques, bâtiments industriels et agricoles, commerces et hôtels, bureaux,
écoles et hôpitaux. Leur cycle obéit à d'autres moteurs que celui du logement :
l'investissement des entreprises, le commerce en ligne, la commande publique, les revenus
agricoles, plutôt que le crédit immobilier des ménages. Cette page suit, destination par destination, les surfaces
de locaux autorisées et mises en chantier en France, publiées chaque mois par le SDES
(<abbr title="Fichier du SDES qui recense les permis de construire et les mises en chantier — voir « Le vocabulaire » sur la page À propos">SIT@DEL</abbr>).

Tout y est compté en mètres carrés de surface de plancher. Il n'y a pas d'autre unité pour
un local — un « nombre de locaux » additionnerait un kiosque et une plateforme logistique —
et c'est aussi l'unité dans laquelle un fabricant de matériaux mesure son marché.

<details class="hm-howto">
  <summary>ℹ️ Comment lire cette page</summary>
  <div class="hm-caption">${L.available ? L.how_to_read : "Données indisponibles."}</div>
</details>

```js
// La période vit dans SA cellule : dans la cellule qui la définit, `rangeL` est encore le
// générateur et non sa valeur — un filtre qui s'y référait vidait silencieusement les
// deux graphiques par destination (vu au premier rendu, 2026-09-26).
const rangeL = Generators.input(periodFilter({min: L.period.min, max: L.period.max}));
```

```js
// Les quatre destinations partitionnent le total ; les sous-destinations sont un zoom
// À L'INTÉRIEUR de la leur. Les deux listes sont lues du JSON, jamais recopiées.
const DEST = L.available ? L.tableau.filter((t) => t.niveau === "Destination") : [];
const SOUS = L.available ? L.tableau.filter((t) => t.niveau === "Sous-destination") : [];
const MESURES = new Map([["Surfaces commencées", "SurfaceChantiers"], ["Surfaces autorisées", "SurfacePermis"]]);
const LIB = {SurfaceChantiers: "commencées", SurfacePermis: "autorisées"};

// Séries cumulées 12 mois d'un ensemble de types, en millions de m², format long.
function roll12(types, mesure) {
  const P = L.par_type, rows = [];
  for (const s of P.series.filter((s) => s.mesure === mesure && types.includes(s.type))) {
    s.roll12.forEach((v, i) => { if (v != null) rows.push({date: P.dates[i], series: s.type, value: v / 1e6}); });
  }
  return filterYears(rows, rangeL);
}

// Tableau par destination : les deux mesures côte à côte, parce que l'écart entre ce qui
// est autorisé et ce qui démarre est souvent la première chose à lire. Les variations
// arrivent MISES EN FORME par l'export (commun.pct : espace avant « % », jamais « -0,0 ») —
// ne pas les reformater ici.
function tableau(lignes, avecPart) {
  const cellules = (m) => m
    ? html`<td>${m.val12_txt}</td><td>${m.yoy_txt}</td><td>${m.ecart_ref_txt}</td>`
    : html`<td>—</td><td>—</td><td>—</td>`;
  return html`<div style="overflow-x:auto"><table class="hm-table">
    <thead><tr><th></th>
      <th>Commencées, 12 mois</th><th>vs 12 mois précédents</th><th>vs ${L.ref_label}</th>
      <th>Autorisées, 12 mois</th><th>vs 12 mois précédents</th><th>vs ${L.ref_label}</th>
      ${avecPart ? html`<th>Part des m² commencés</th>` : ""}</tr></thead>
    <tbody>${lignes.map((t) => html`<tr>
      <td>${t.color ? html`<span class="hm-swatch" style=${{background: t.color, width: "10px", height: "10px", marginRight: "0.45rem"}}></span>` : ""}${t.niveau === "Ensemble" ? html`<b>${t.type}</b>` : t.type}</td>
      ${cellules(t.SurfaceChantiers)}${cellules(t.SurfacePermis)}
      ${avecPart ? html`<td>${t.SurfaceChantiers && t.SurfaceChantiers.part != null ? nf1.format(t.SurfaceChantiers.part) + " %" : "—"}</td>` : ""}
    </tr>`)}</tbody>
  </table></div>`;
}
```

## 🔑 Chiffres Clés

<div class="hm-caption">Chiffres nationaux au dernier mois disponible, indépendants de la période affichée. La tendance compare les douze derniers mois aux douze précédents ; le niveau se lit par rapport à la moyenne de la période de référence, nommée sur chaque carte.</div>

```js
if (L.available) display(cardGrid(L.kpis, kpiCard));
```

## 📐 Toute la construction neuve en m²

<div class="hm-caption">Logements et locaux sur la même échelle : la surface de plancher, cumulée sur douze mois. Les deux séries ne sont pas datées de la même façon — les logements à la date réelle estimée de l'événement, les locaux à la date où l'administration enregistre la déclaration, ce qui retarde la courbe des locaux. En cumul sur un an ce décalage pèse peu ; il interdit en revanche de comparer deux mois isolés.</div>

<div class="hm-shortcuts"><a class="hm-shortcut" href="./neuf#en-m-ce-que-voient-les-materiaux">🏗️ les m² de logements, et pourquoi ils reculent plus que les logements</a></div>

```js
const mesureC = view(Inputs.radio(MESURES, {value: "SurfaceChantiers", label: "Mesure"}));
```

```js
if (L.available) display(multiLine({
  rows: filterYears(L.construction.rows[mesureC], rangeL), meta: L.construction.meta,
  yLabel: "Millions de m² (cumul 12 mois)", valueFmt: (v) => nf1.format(v), tipUnit: " M m²",
  width, filename: "construction-neuve-m2-logements-locaux-" + LIB[mesureC]}));
```

## 🏢 Par destination

<div class="hm-caption">Le code de l'urbanisme range chaque local dans une destination : exploitation agricole ou forestière ; commerce et activités de service, hôtels compris ; équipements d'intérêt collectif et services publics — écoles, hôpitaux, équipements sportifs ou culturels ; et les autres activités des secteurs primaire, secondaire et tertiaire, c'est-à-dire l'industrie, les entrepôts et les bureaux. Les quatre destinations s'additionnent exactement au total : leur empilement montre à la fois le volume et le mélange.</div>

```js
const mesureD = view(Inputs.radio(MESURES, {value: "SurfaceChantiers", label: "Mesure"}));
```

```js
// Aires empilées : les destinations partitionnent le total, l'empilement est donc exact.
// La vignette est posée sur le TOTAL de chaque mois et liste les quatre destinations :
// sur des aires empilées, une vignette par couche forcerait à viser une bande étroite.
function destinations() {
  const noms = DEST.map((t) => t.type);
  const rows = roll12(noms, mesureD).map((d) => ({...d, _x: new Date(d.date)}));
  const parMois = Array.from(parDate(rows), ([date, ds]) => ({
    _x: new Date(date), total: ds.reduce((a, d) => a + d.value, 0),
    detail: noms.map((n) => { const x = ds.find((d) => d.series === n); return `${n} : ${x ? nf1.format(x.value) : "—"}`; }).join("\n"),
  }));
  const plot = Plot.plot({
    width, height: 380, marginLeft: 54, marginRight: 20,
    x: {label: null}, y: {label: "Millions de m² (cumul 12 mois)", grid: true},
    color: {domain: noms, range: DEST.map((t) => t.color)},
    marks: [
      Plot.areaY(rows, {x: "_x", y: "value", fill: "series", order: noms, fillOpacity: 0.85}),
      Plot.ruleY([0]),
      Plot.ruleX(parMois, Plot.pointerX({x: "_x", stroke: ui.subtle})),
      Plot.tip(parMois, Plot.pointerX({x: "_x", y: "total", ...TIP,
        title: (d) => `${fmtMonthFR(d._x)} — total ${nf1.format(d.total)} M m²\n${d.detail}`})),
    ]});
  return html`<div>${legendStatic(DEST.map((t) => ({name: t.type, color: t.color})))}${withCsvExport(plot, rows.map(({_x, ...r}) => r), "locaux-par-destination-" + LIB[mesureD])}</div>`;
}
function parDate(rows) {
  const m = new Map();
  for (const r of rows) { if (!m.has(r.date)) m.set(r.date, []); m.get(r.date).push(r); }
  return m;
}
```

```js
if (L.available) display(destinations());
```

```js
if (L.available) display(tableau([...DEST, ...L.tableau.filter((t) => t.niveau === "Ensemble")], true));
```

<div class="hm-caption">La tendance compare les douze derniers mois aux douze précédents ; la dernière colonne de chaque bloc situe le niveau par rapport à la moyenne de la période de référence. Un écart durable entre les deux blocs — des autorisations au-dessus de leur normale, des chantiers en dessous — peut signaler des projets qui tardent à démarrer ; mais les chantiers de locaux remontent avec retard, et une partie des déclarations d'ouverture ne remonte jamais : l'écart se lit dans la durée, pas sur un trimestre.</div>

## 🔍 Entrepôts, industrie, bureaux, hôtels

<div class="hm-caption">Quatre sous-destinations sont publiées à part : les hôtels, au sein du commerce, puis l'industrie, les entrepôts et les bureaux, qui forment ensemble la dernière destination. Ce sont des marchés de nature différente — la logistique, la production, le tertiaire de bureau — qu'un total confond. Chacune est corrigée des variations saisonnières pour elle-même : elles servent à comparer, pas à reconstituer un total.</div>

```js
const mesureS = view(Inputs.radio(MESURES, {value: "SurfaceChantiers", label: "Mesure"}));
```

```js
if (L.available) display(multiLine({
  rows: roll12(SOUS.map((t) => t.type), mesureS), meta: SOUS.map((t) => ({name: t.type, color: t.color})),
  yLabel: "Millions de m² (cumul 12 mois)", valueFmt: (v) => nf1.format(v), tipUnit: " M m²",
  width, filename: "locaux-sous-destinations-" + LIB[mesureS]}));
```

```js
if (L.available) display(tableau(SOUS, false));
```

## ⚠️ Ce que ces chiffres ne disent pas

<div class="hm-caption">
<p><b>Le moment exact des chantiers.</b> Les surfaces de locaux sont datées du jour où l'administration enregistre l'événement, pas du jour où il a lieu. Une autorisation remonte vite ; une déclaration d'ouverture de chantier, qui dépend du maître d'ouvrage, remonte en général dans les dix-huit mois. Les m² commencés d'un mois sont donc des chantiers ouverts au fil de l'année écoulée : un signal en retard, que les m² autorisés précèdent. En contrepartie, la série n'est pas révisée — ce qui est publié reste.</p>
<p><b>Un taux de transformation.</b> La page du neuf rapporte les logements commencés aux logements autorisés. Pour les locaux, ce rapport existe, mais ces données ne permettent pas de dire ce qu'il mesure : une autorisation qui ne se retrouve pas en chantier peut être un projet abandonné, ou une ouverture de chantier jamais déclarée. Un ratio dont on ne sait pas ce qu'il mesure n'est pas publié.</p>
<p><b>Une prévision.</b> Aucun modèle n'a été mesuré sur ces séries. La règle du site vaut ici comme ailleurs : pas de prévision publiée tant qu'un modèle n'a pas battu, sur des données qu'il n'a jamais vues, la simple prolongation du dernier niveau connu.</p>
<p><b>L'entretien et la rénovation.</b> Seules figurent les surfaces de plancher créées par des travaux soumis à autorisation d'urbanisme. L'entretien, la rénovation ou le réaménagement de locaux existants n'y apparaissent pas.</p>
<p><b>Le détail régional.</b> Le SDES publie aussi ces séries par région et par département ; cette page s'en tient au national, comme les autres pages de marché.</p>
</div>

<div class="hm-meta">Source : ${L.source ?? "SDES — SIT@DEL2"} · dernier point : ${L.last_month ?? "—"} · période affichée : ${Math.min(...rangeL)}–${Math.max(...rangeL)}</div>
