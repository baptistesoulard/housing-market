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

// Les faisceaux, en format long : une ligne par (millésime, mois visé). Les 210
// trajectoires ne sont PAS 210 séries à distinguer — c'est un nuage. Elles partagent donc
// une seule teinte discrète, et les couleurs sont réservées à ce qu'on doit lire : le
// réalisé, la prévision en cours, et le millésime éventuellement mis en avant.
const faisceaux = RETRO.fans.flatMap((f) =>
  f.points.map(([date, value]) => ({vintage: f.vintage, date: d(date), value})));
const reel = A.realized.map((r) => ({date: d(r.date), value: r.value}));
const encours = (A.current?.points ?? []).map((p) => ({...p, date: d(p.date)}));
```

<!--
  TITRE ET CHAPEAU STATIQUES — rendus au build, pas construits dans le navigateur.
  Tout le reste de la page est monté en JS à partir du JSON : un robot d'indexation, comme
  tout aperçu de partage, n'en voit rien. Ces deux blocs sont donc le SEUL texte de la page
  que lisent Google et LinkedIn. Le titre valait auparavant `${A.title}`, c'est-à-dire un titre
  VIDE dans le HTML livré. Ne pas les reconvertir en interpolation.
  Voir CLAUDE.md, « Le chapeau des pages de données ».
-->

# 🎯 Prévisions passées — ce que nous annoncions

Une prévision qui n'est jamais vérifiée n'est qu'une opinion. Chaque prévision de
transactions publiée par ce site est enregistrée le jour de sa publication, avant que la
suite ne soit connue, puis confrontée aux chiffres réellement observés — y compris quand
elle a eu tort.

Cette page publie l'erreur du modèle horizon par horizon et la compare à une référence
naïve, qui se contente de prolonger le dernier niveau observé. Le modèle ne bat pas cette
référence à tous les horizons, et c'est précisément ce que cette page sert à montrer.


<div class="hm-takeaways">
  <strong>Ce que dit cette page</strong>
  <ul>
    <li>Le modèle annonce le <strong>bon sens du marché</strong> — hausse ou baisse — dans <strong>${nf0.format((RETRO.horizons.find((h) => h.horizon === 12)?.direction ?? 0) * 100)} %</strong> des cas à douze mois, et <strong>${nf0.format((RETRO.horizons.find((h) => h.horizon === 6)?.direction ?? 0) * 100)} %</strong> à six mois. C'est la mesure qui compte pour décider ; l'erreur en pourcentage vient après.</li>
    <li>Il se trompe de <strong>${nf1.format(RETRO.horizons.find((h) => h.horizon === 6)?.mape ?? 0)} %</strong> en moyenne à six mois, contre <strong>${nf1.format(RETRO.horizons.find((h) => h.horizon === 6)?.naive_mape ?? 0)} %</strong> pour une prévision naïve.</li>
    <li>En deçà de <strong>${A.crossover_horizon} mois</strong>, il fait <strong>moins bien</strong> que cette prévision naïve : à court terme, un cumul 12 mois bouge trop peu pour qu'un modèle apporte quoi que ce soit.</li>
    <li>Son domaine utile est <strong>${A.crossover_horizon} à 18 mois</strong>. Mais ce score moyen cache l'essentiel : le modèle est piloté par les taux, donc il excelle quand ce sont les taux qui font le marché et décroche quand c'est autre chose — voir la ventilation par épisode plus bas.</li>
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
  width, height: 420, marginLeft: 62, marginRight: 16,
  x: {label: null},
  y: {label: "Transactions (cumul 12 mois)", grid: true, zero: false,
      tickFormat: (v) => nf0.format(v / 1000) + " k"},
  marks: [
    // Le nuage des trajectoires : trait fin, teinte neutre, très transparent. Il doit se
    // lire comme une texture — la dispersion est l'information, pas chaque trait.
    // 210 trajectoires, pas 48 : l'opacité et l'épaisseur sont descendues d'autant, sans
    // quoi le nuage vire au aplat gris et la dispersion — la seule information qu'il
    // porte — disparaît. Aucune trajectoire n'est retirée : le nuage doit rester complet,
    // c'est ce qui rend l'export CSV honnête.
    Plot.line(faisceaux, {x: "date", y: "value", z: "vintage",
                          stroke: ui.greyLine, strokeWidth: 0.6, strokeOpacity: 0.14}),
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
  width, height: 360, marginLeft: 52, marginRight: 118, marginBottom: 42,
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

## Où le modèle gagne, où il perd

<div class="hm-caption">
Un score moyen unique répond à la mauvaise question. Ce modèle est piloté par les taux :
il excelle quand ce sont les taux qui font le marché, et décroche quand c'est autre chose.
Publier la ventilation, c'est publier son domaine de validité plutôt que sa meilleure
année.
</div>

```js
// Cette ventilation est le pendant du graphique par horizon : l'un dit "à quelle distance
// le modèle sert", l'autre "dans quelles conditions". C'est le second qui explique le
// premier — les trois épisodes perdants (crise financière, creux 2012-15, Covid) ont en
// commun que le moteur du marché n'y était PAS le coût du crédit.
const EP = A.episodes ?? [];
```

```js
if (EP.length) display(Plot.plot({
  width, height: 42 + EP.length * 38, marginLeft: 220, marginRight: 60, marginTop: 26,
  x: {label: "Erreur moyenne (%)", grid: true, domain: [0, Math.max(...EP.map((e) => e.naive_mape)) * 1.1]},
  y: {label: null, domain: EP.map((e) => e.label)},
  color: {domain: ["Notre modèle", A.naive_label], range: [series.brick, series.blue], legend: true},
  marks: [
    Plot.ruleY(EP, {y: "label", x1: "mape", x2: "naive_mape", stroke: ui.border, strokeWidth: 2}),
    Plot.dot(EP, {y: "label", x: "naive_mape", fill: series.blue, r: 5.5}),
    Plot.dot(EP, {y: "label", x: "mape", fill: series.brick, r: 5.5}),
    Plot.text(EP, {y: "label", x: "naive_mape", dx: 14, textAnchor: "start",
                   text: (e) => (e.skill > 0 ? `−${nf0.format(e.skill * 100)} %` : "perd"),
                   fill: (e) => (e.skill > 0 ? series.green : series.brick), fontWeight: 600}),
    Plot.tip(EP, Plot.pointer({
      y: "label", x: "mape", ...TIP,
      title: (e) => `${e.label}
${e.vintages} millésimes
Modèle : ${nf1.format(e.mape)} %
Naïve : ${nf1.format(e.naive_mape)} %
Bon sens : ${nf0.format(e.direction * 100)} %`,
    })),
  ],
}));
```

<div class="hm-caption">
Point rouge = notre erreur, point bleu = celle d'une prévision naïve. À droite, la part
d'erreur évitée — ou « perd » quand le modèle fait moins bien. Les trois épisodes perdants
ont un point commun : le moteur du marché n'y était pas le coût du crédit. En 2008 c'était
le rationnement bancaire, en 2012-2015 la confiance dans un contexte de taux déjà bas, en
2020 la fermeture administrative des études notariales.
</div>

```js
if (EP.length) display(html`<details class="hm-howto">
  <summary>Les mêmes chiffres en tableau</summary>
  <div class="hm-scroller">
    <table class="hm-sources">
      <caption class="hm-caption">Erreur par épisode de marché, sur les millésimes rétro-simulés.</caption>
      <thead><tr>
        <th scope="col">Épisode</th><th scope="col">Millésimes</th>
        <th scope="col">Erreur du modèle</th><th scope="col">Erreur d'une prévision naïve</th>
        <th scope="col">Erreur évitée</th><th scope="col">Sens annoncé juste</th>
      </tr></thead>
      <tbody>${EP.map((e) => html`<tr>
        <th scope="row">${e.label}</th>
        <td>${e.vintages}</td>
        <td>${nf1.format(e.mape)} %</td>
        <td>${nf1.format(e.naive_mape)} %</td>
        <td>${e.skill == null || e.skill <= 0 ? "aucune" : nf0.format(e.skill * 100) + " %"}</td>
        <td>${nf0.format(e.direction * 100)} %</td>
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
  // « 0 mois échu » se lit comme une page inachevée, alors que c'est une promesse datée :
  // la première prévision publiée sera jugeable à un mois précis, connu d'avance. Un
  // compte à rebours dit la même vérité en la rendant vérifiable.
  {label: LIVE.n_evaluated ? "Mois déjà échus, jugeables" : "Première échéance jugeable",
   value: LIVE.n_evaluated ? nf0.format(LIVE.n_evaluated) : (premierEcheance ?? "—"),
   subs: [LIVE.n_evaluated ? "confrontés au réalisé"
                           : "d'ici là, seules les rétro-simulations ont un verdict"]},
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
