---
title: Prévisions passées
toc: true
---

```js
import {cardGrid, kpiCard, withCsvExport, nf0, nf1, fmtMonthFR, Plot, TIP} from "./components/hm.js";
import {series, ui} from "./components/theme.js";
import {periodFilter} from "./components/period.js";
const A = await FileAttachment("./data/archive.json").json();
```

```js
// La frise reste montée pour être présente sur tous les onglets, mais cette page ne la
// consomme pas : elle porte sur des prévisions à venir, hors du domaine du curseur.
const periodeArchive = periodFilter({min: A.period.min, max: A.period.max,
                                     note: "Sans effet sur cet onglet."});
```

```js
const RETRO = A.kinds.retro;
const LIVE = A.kinds.archive;
const d = (s) => new Date(s);
const moisFR = (s) => fmtMonthFR(d(s));

// Les faisceaux, en format long : une ligne par (millésime, mois visé). Les 48
// trajectoires ne sont PAS 48 séries à distinguer — c'est un nuage. Elles partagent donc
// une seule teinte discrète, et les couleurs sont réservées à ce qu'on doit lire : le
// réalisé, la prévision en cours, et le millésime éventuellement mis en avant.
const faisceaux = RETRO.fans.flatMap((f) =>
  f.points.map(([date, value]) => ({vintage: f.vintage, date: d(date), value})));
const reel = A.realized.map((r) => ({date: d(r.date), value: r.value}));
const encours = (A.current?.points ?? []).map((p) => ({...p, date: d(p.date)}));
```

# ${A.title}

<div class="hm-caption">${A.caption}</div>

<div class="hm-takeaways">
  <strong>Ce que dit cette page</strong>
  <ul>
    <li>Sur les millésimes rétro-simulés, le modèle se trompe de <strong>${nf1.format(RETRO.horizons.find((h) => h.horizon === 6)?.mape ?? 0)} %</strong> en moyenne à six mois, contre <strong>${nf1.format(RETRO.horizons.find((h) => h.horizon === 6)?.naive_mape ?? 0)} %</strong> pour une prévision naïve.</li>
    <li>En deçà de <strong>${A.crossover_horizon} mois</strong>, il fait <strong>moins bien</strong> qu'une prévision naïve : à court terme, un cumul 12 mois bouge trop peu pour qu'un modèle apporte quoi que ce soit.</li>
    <li>Son domaine utile est <strong>${A.crossover_horizon} à 12 mois</strong> ; au-delà, son erreur croît vite parce que ses prédicteurs doivent eux-mêmes être prolongés.</li>
  </ul>
</div>

<details class="hm-howto">
  <summary>Comment lire cette page — et pourquoi deux natures de prévisions</summary>
  <p>${A.how_to_read}</p>
</details>

## Toutes nos prévisions, face au réel

```js
// Un millésime peut être mis en avant : « que disions-nous en juin 2024 ? » est la
// question que se pose un lecteur devant un faisceau, et elle n'a pas de réponse tant
// qu'on ne peut pas isoler une trajectoire.
const millesimes = ["Aucun"].concat(RETRO.fans.map((f) => f.vintage));
const spot = view(Inputs.select(millesimes, {
  label: "Mettre en avant un millésime",
  format: (v) => (v === "Aucun" ? "Aucun — tout le faisceau" : moisFR(v)),
}));
```

```js
const spotRows = spot === "Aucun" ? [] : faisceaux.filter((r) => r.vintage === spot);
const dernierReel = reel[reel.length - 1];

const legende = [
  {name: "Réalisé (transactions, cumul 12 mois)", color: series.brick},
  {name: "Prévisions rétro-simulées, un trait par millésime", color: ui.greyLine},
  {name: `Prévision en cours (millésime ${A.current ? A.current.vintage_label : "—"})`,
   color: series.green, dash: true},
].concat(spot === "Aucun" ? [] : [{name: `Millésime ${moisFR(spot)}`, color: series.blue}]);
```

<div class="hm-legend hm-legend--static">${legende.map((m) => html`<span class="hm-legend-item">
  <span class="hm-swatch" style=${m.dash
    ? {borderBottom: `2px dashed ${m.color}`, background: "transparent", height: "0", marginBottom: "3px"}
    : {background: m.color}}></span>${m.name}</span>`)}</div>

```js
const faisceauExport = [
  ...reel.map((r) => ({type: "realise", date: r.date, value: r.value})),
  ...faisceaux.map((r) => ({type: "retro", vintage: r.vintage, date: r.date, value: r.value})),
  ...encours.map((r) => ({type: "en_cours", date: r.date, lo: r.lo, hi: r.hi, predicted: r.predicted})),
];
display(withCsvExport(Plot.plot({
  height: 420, marginLeft: 62, marginRight: 16,
  x: {label: null},
  y: {label: "Transactions (cumul 12 mois)", grid: true, zero: false,
      tickFormat: (v) => nf0.format(v / 1000) + " k"},
  marks: [
    // Le nuage des trajectoires : trait fin, teinte neutre, très transparent. Il doit se
    // lire comme une texture — la dispersion est l'information, pas chaque trait.
    Plot.line(faisceaux, {x: "date", y: "value", z: "vintage",
                          stroke: ui.greyLine, strokeWidth: 1, strokeOpacity: 0.3}),
    // La bande de la prévision en cours, sous les traits : c'est elle que les millésimes
    // à venir viendront juger.
    encours.length ? Plot.areaY(encours, {x: "date", y1: "lo", y2: "hi",
                                          fill: series.green, fillOpacity: 0.1}) : null,
    encours.length ? Plot.line(encours, {x: "date", y: "predicted", stroke: series.green,
                                         strokeWidth: 2, strokeDasharray: "5 3"}) : null,
    spotRows.length ? Plot.line(spotRows, {x: "date", y: "value", stroke: series.blue,
                                           strokeWidth: 2.5}) : null,
    spotRows.length ? Plot.dot([spotRows[0]], {x: "date", y: "value", r: 4,
                                               fill: series.blue, stroke: "white", strokeWidth: 2}) : null,
    // Le réalisé passe DERNIER : il doit rester lisible par-dessus le nuage.
    Plot.line(reel, {x: "date", y: "value", stroke: series.brick, strokeWidth: 2.5}),
    Plot.dot([dernierReel], {x: "date", y: "value", r: 4.5, fill: series.brick,
                             stroke: "white", strokeWidth: 2}),
    Plot.ruleY([0], {opacity: 0}),
    Plot.crosshairX(reel, {x: "date", y: "value", color: ui.subtle}),
    Plot.tip(reel, Plot.pointerX({
      x: "date", y: "value", ...TIP,
      title: (r) => `${fmtMonthFR(r.date)}\nRéalisé : ${nf0.format(r.value)} transactions`,
    })),
  ],
}), faisceauExport, "previsions-passees-faisceau"));
```

<div class="hm-caption">Chaque trait gris est une prévision à 18 mois produite à partir des seules
données connues à sa date. La courbe rouge est ce qui s'est passé. Le faisceau s'écarte du réel
au moment où les prédicteurs doivent être prolongés — c'est là que l'incertitude vit.</div>

## À partir de quand le modèle sert-il à quelque chose ?

<div class="hm-caption">Comparé à la prévision la plus paresseuse qui soit : « le marché restera
là où il est aujourd'hui ». Un modèle qui ne bat pas celle-là ne mérite pas d'être publié.</div>

```js
const parHorizon = RETRO.horizons.flatMap((h) => [
  {horizon: h.horizon, serie: "Notre modèle", valeur: h.mape},
  {horizon: h.horizon, serie: A.naive_label, valeur: h.naive_mape},
]);
const yMaxErr = Math.max(...parHorizon.map((r) => r.valeur)) * 1.12;
const finLignes = ["Notre modèle", A.naive_label].map((s) => {
  const pts = parHorizon.filter((r) => r.serie === s);
  return pts[pts.length - 1];
});
```

```js
// La légende est construite en JS, pas en HTML brut : un `${…}` placé dans un ATTRIBUT
// (ici `style`) n'est pas interprété par le framework — il resterait affiché tel quel.
// Les interpolations ne fonctionnent que dans le contenu d'un élément.
display(html`<div class="hm-legend hm-legend--static">${[
  {name: "Notre modèle", color: series.brick},
  {name: A.naive_label, color: series.blue},
].map((m) => html`<span class="hm-legend-item">
  <span class="hm-swatch" style=${{background: m.color}}></span>${m.name}</span>`)}</div>`);
```

```js
display(withCsvExport(Plot.plot({
  height: 360, marginLeft: 52, marginRight: 118, marginBottom: 42,
  x: {label: "Horizon de la prévision (mois)", ticks: [1, 3, 6, 9, 12, 15, 18], grid: false},
  y: {label: "Erreur moyenne (%)", grid: true, domain: [0, yMaxErr]},
  color: {domain: ["Notre modèle", A.naive_label], range: [series.brick, series.blue]},
  marks: [
    // La zone où le modèle PERD. La montrer est le propos de ce graphique : la masquer
    // derrière un score moyen unique reviendrait à vendre le modèle au-delà de son domaine.
    A.crossover_horizon ? Plot.rect([{x1: 0.6, x2: A.crossover_horizon - 0.4}], {
      x1: "x1", x2: "x2", y1: 0, y2: yMaxErr, fill: ui.border, fillOpacity: 0.55}) : null,
    A.crossover_horizon ? Plot.text([{x: (0.6 + A.crossover_horizon - 0.4) / 2, y: yMaxErr * 0.94}], {
      x: "x", y: "y", text: () => "le modèle\nfait moins bien", fill: ui.subtle,
      fontSize: 11, lineHeight: 1.2, textAnchor: "middle"}) : null,
    Plot.line(parHorizon, {x: "horizon", y: "valeur", stroke: "serie", strokeWidth: 2}),
    Plot.dot(parHorizon, {x: "horizon", y: "valeur", fill: "serie", r: 3}),
    // Étiquettes en bout de ligne : l'identité ne repose jamais sur la seule couleur.
    Plot.text(finLignes, {x: "horizon", y: "valeur", text: (r) => ` ${nf1.format(r.valeur)} %`,
                          fill: "serie", textAnchor: "start", dx: 6, fontWeight: 600}),
    Plot.crosshairX(parHorizon, {x: "horizon", y: "valeur", color: ui.subtle}),
    Plot.tip(parHorizon, Plot.pointerX({
      x: "horizon", y: "valeur", ...TIP,
      title: (r) => `${r.horizon} mois\n${r.serie} : ${nf1.format(r.valeur)} % d'erreur`,
    })),
  ],
}), parHorizon, "previsions-passees-erreur-par-horizon"));
```

```js
// Le tableau est monté en JS pour la même raison que la légende, aggravée d'un cas propre
// aux tables : un `<observablehq-loading>` posé dans un `<tbody>` écrit en HTML brut est
// éjecté hors de la table par l'analyseur HTML, et les lignes atterrissent avant elle.
//
// Il existe parce qu'un graphique n'est pas lisible par tout le monde : les mêmes chiffres
// doivent être disponibles sous une forme qu'un lecteur d'écran parcourt.
display(html`<details class="hm-howto">
  <summary>Les mêmes chiffres en tableau</summary>
  <div class="hm-scroller">
    <table class="hm-sources">
      <caption class="hm-caption">Erreur moyenne par horizon sur les millésimes rétro-simulés.</caption>
      <thead><tr>
        <th scope="col">Horizon</th><th scope="col">Mois évalués</th>
        <th scope="col">Erreur du modèle</th><th scope="col">Erreur d'une prévision naïve</th>
        <th scope="col">Erreur évitée</th>
      </tr></thead>
      <tbody>${RETRO.horizons.map((h) => html`<tr>
        <th scope="row">${h.horizon} mois</th>
        <td>${h.n}</td>
        <td>${nf1.format(h.mape)} %</td>
        <td>${nf1.format(h.naive_mape)} %</td>
        <td>${h.skill == null ? "—" : h.skill > 0 ? nf0.format(h.skill * 100) + " %" : "aucune"}</td>
      </tr>`)}</tbody>
    </table>
  </div>
</details>`);
```

## L'archive en direct

```js
const premierEcheance = A.current
  ? fmtMonthFR(new Date(A.current.points[0].date))
  : null;
display(cardGrid([
  {label: "Prévisions publiées et enregistrées", value: nf0.format(LIVE.n_vintages),
   subs: [LIVE.n_vintages ? `depuis ${moisFR(LIVE.first_vintage)}` : "aucune pour l'instant"]},
  {label: "Mois déjà échus, jugeables", value: nf0.format(LIVE.n_evaluated),
   subs: [LIVE.n_evaluated ? "confrontés au réalisé" : `le premier sera ${premierEcheance ?? "—"}`]},
  {label: "Millésimes rétro-simulés", value: nf0.format(RETRO.n_vintages),
   subs: [`${nf0.format(RETRO.n_evaluated)} mois confrontés au réalisé`]},
], kpiCard));
```

<div class="hm-note">
  <p><strong>Pourquoi si peu de prévisions « publiées » pour l'instant.</strong> L'archive
  ne peut enregistrer que l'avenir : elle a commencé le jour de sa mise en service, et
  chaque semaine ajoute au plus une prévision — seulement si le modèle a changé d'avis.
  Les millésimes rétro-simulés comblent le vide en montrant ce que la méthode aurait dit,
  mais ils ne remplacent pas une promesse tenue. Cette colonne se remplira toute seule.</p>
</div>

```js
display(A.current ? html`<div class="hm-meta">Prévision en cours, enregistrée le
  ${A.current.run_date} sur les données arrêtées à ${A.current.vintage_label} (R² =
  ${nf1.format(A.current.r2 * 100)} %) : de
  <strong>${nf0.format(A.current.points[0].predicted)}</strong> transactions en
  ${fmtMonthFR(new Date(A.current.points[0].date))} à
  <strong>${nf0.format(A.current.points[A.current.points.length - 1].predicted)}</strong> en
  ${fmtMonthFR(new Date(A.current.points[A.current.points.length - 1].date))}.</div>`
  : html`<div class="hm-meta">Aucune prévision en direct enregistrée pour l'instant.</div>`);
```

<div class="hm-shortcuts">
  <span class="lead">Voir aussi :</span>
  <a class="hm-shortcut" href="/previsions">📡 La prévision en cours</a>
  <a class="hm-shortcut" href="/a-propos">ℹ️ La méthode</a>
</div>
