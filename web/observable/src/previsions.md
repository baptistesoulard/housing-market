---
title: Prévision & Scénarios
toc: true
---

```js
import {cardGrid, kpiCard, legendStatic, withCsvExport, cadreGraphique, filterYears, nf0, nf1, fmtMonthFR, Plot, TIP, d3} from "./components/hm.js";
import {series, ui} from "./components/theme.js";
import {periodFilter} from "./components/period.js";
import {computeScenario} from "./components/api.js";
```

```js
// Le modèle est réajusté chaque semaine par web_export.py (via api.engine, sans Flask) et
// publié ici en JSON : aucun serveur à joindre pour un visiteur. Les scénarios appliquent
// en JS la même formule fermée que `forecast.scenario` (computeScenario, components/api.js).
//
// PAGE GRAND PUBLIC depuis le 2026-10-20 : une réponse, son pourquoi, jusqu'où s'y fier,
// et des scénarios en unités parlantes. Tout ce qui dit COMMENT le chiffre est fabriqué —
// équations, recalage, entrées figées, régime de taux, comparaison des modèles — est sur
// /methode-prevision. Une explication nouvelle va là-bas, pas ici.
const data = await FileAttachment("./data/previsions.json").json();
const R = data.available ? data.rate : null;
const T = data.available ? data.transactions : null;
const P = data.available ? data.projection : null;
const V = data.available ? data.verdict : null;
const B = data.available ? data.benchmark : null;
const W = V?.pourquoi ?? null;
```

```js
// La frise de période, comme sur les autres onglets. Elle ne rogne que l'AFFICHAGE de
// l'historique : le modèle reste ajusté sur toute la profondeur disponible.
const periode = Generators.input(periodFilter({
  min: data.period.min, max: data.period.max,
  note: "Rogne l'historique affiché. Les projections, postérieures au dernier mois publié, restent visibles.",
}));
```

```js
// --- Mise en forme commune ------------------------------------------------------------
// Des chiffres ARRONDIS, partout où un lecteur les lit : « 902 161 » avec une incertitude
// de ± 80 000 affiche une précision que le modèle n'a pas. Le millier pour un niveau, la
// dizaine de milliers pour les bornes d'une fourchette.
const k1 = (v) => nf0.format(Math.round(v / 1000) * 1000);
const k10 = (v) => nf0.format(Math.round(v / 10000) * 10000);
// Jamais de zéro signé (« −0 ») : une valeur qui s'arrondit à zéro s'écrit sans signe,
// comme partout ailleurs sur le site (commun._variation côté Python).
const signe = (v, f = k1) => {
  const txt = f(Math.abs(v));
  return (/^0([,.]0*)?$/.test(txt) ? "" : v > 0 ? "+" : v < 0 ? "−" : "") + txt;
};
const pct1 = (v) => signe(v, (x) => nf1.format(x)) + " %";
const moisIso = (iso) => fmtMonthFR(new Date(String(iso).slice(0, 10) + "T00:00:00Z"));
const plusMois = (iso, n) => {
  const t = new Date(String(iso).slice(0, 10) + "T00:00:00Z");
  t.setUTCMonth(t.getUTCMonth() + n);
  return t;
};
// « 75 % » se dit « 3 fois sur 4 » : c'est ainsi qu'un lecteur retient une fiabilité.
// Seulement quand la fraction simple tombe juste (à 2 points près) ; sinon le pourcentage.
function frequence(p) {
  for (const d of [2, 3, 4, 5, 10]) {
    const n = Math.round(p * d);
    if (n > 0 && n < d && Math.abs(n / d - p) <= 0.02) return `${n} fois sur ${d}`;
  }
  return `${nf0.format(p * 100)} % du temps`;
}
// Une part dite en mots (« un tiers », « la moitié ») quand elle tombe près d'une fraction
// simple ; sinon en pourcentage arrondi.
function partEnMots(p) {
  const F = [[1 / 4, "un quart"], [1 / 3, "un tiers"], [1 / 2, "la moitié"],
             [2 / 3, "deux tiers"], [3 / 4, "les trois quarts"]];
  const proche = F.find(([v]) => Math.abs(v - p) <= 0.05);
  return proche ? proche[1] : `${nf0.format(p * 100)} %`;
}
const moisCourt = d3.utcFormat("%b %Y");   // « sept. 2026 » (locale française posée par hm.js)
const dernierMois = data.available ? data.health.transactions_last_month : null;
const moisObserve = dernierMois ? moisIso(dernierMois) : "—";
```

# 📡 Prévision des ventes & scénarios

<!--
  CHAPEAU STATIQUE, rendu au build — voir CLAUDE.md, « Texte statique : aucun chiffre, aucun état ».
-->

Cette page projette les **ventes de logements anciens** en France pour les mois qui
viennent. Elle s'appuie sur trois indicateurs publics : le taux du crédit immobilier,
l'envie d'acheter des ménages et le chômage. Elle dit où va le marché, d'où vient ce
mouvement, jusqu'à quel point s'y fier, et ce qui changerait si les conditions changeaient.

C'est un **indicateur de contexte** : ni les mises en chantier ni la rénovation ne sont
prévues ici. La fabrication du chiffre est détaillée sur la page
[Méthode de la prévision](/methode-prevision), et ses résultats passés sur
[Le modèle face au réel](/previsions-passees).

```js
// La date qui compte pour le lecteur : de quand date le dernier chiffre, et pourquoi la
// projection démarre avant aujourd'hui. « Entraînement du backtest ≤ 2021 » qui se trouvait
// ici est un détail de méthode — il est sur la page Méthode.
if (data.available) {
  const auj = new Date(), d = new Date(dernierMois + "T00:00:00Z");
  const retard = (auj.getUTCFullYear() - d.getUTCFullYear()) * 12 + auj.getUTCMonth() - d.getUTCMonth();
  display(html`<div class="hm-caption">Dernier chiffre publié : <b>${moisObserve}</b>. Les
    ventes paraissent avec ${retard > 1 ? html`environ ${retard} mois` : "un mois"} de décalage :
    la projection part donc de ce mois-là, pas d'aujourd'hui.</div>`);
} else display(html`<div class="hm-api-offline">
  <div class="hm-api-offline-title">⚙️ Modèle non calibré à la dernière publication</div>
  <p>${data.reason}</p>
  <p>En attendant, <a href="/synthese">la synthèse du marché</a> et les pages de détail
  restent complètes.</p>
</div>`);
```

```js
// LE VERDICT, en tête de page. La phrase est GÉNÉRÉE (web/export/verdict.py) : elle porte
// des chiffres, donc elle ne peut pas vivre dans le chapeau statique. UNE seule mesure de
// fiabilité ici, celle de l'échéance annoncée ; les autres (par régime de taux, par plage
// d'horizon, par épisode) sont sur les pages Méthode et Face au réel.
if (V) display(html`<div class="hm-takeaways">
  <strong>Ce que dit le modèle aujourd'hui</strong>
  <ul>
    <li><strong>${V.sentence}</strong></li>
    <li><strong>Fourchette probable :</strong> de ${k10(V.lo)} à ${k10(V.hi)} ventes. Lors
      des prévisions passées, le réel est tombé dans une fourchette de ce type 8 fois sur 10.</li>
    ${V.reliability ? html`<li><strong>Fiabilité :</strong> pour une échéance comme
      ${V.target_month}, le modèle a annoncé le bon sens du marché, hausse ou baisse,
      <strong>${frequence(V.reliability.direction)}</strong> sur
      ${nf0.format(V.reliability.n)} prévisions passées déjà vérifiées
      (<a href="/previsions-passees">le détail, y compris ses erreurs</a>).</li>` : ""}
  </ul>
</div>`);
```

## 1. Où va le marché ?

```js
// Les deux cartes qui ouvraient cette section répétaient le verdict juste au-dessus
// (même chiffre, même fourchette) : retirées le 2026-10-20. La fin de projection est
// désormais dite là où elle sert, dans « Peut-on s'y fier ? ».
const finInfo = P && P.available ? moisIso(plusMois(dernierMois, P.informative_months).toISOString()) : null;
const finProj = P && P.available ? moisIso(P.series[P.series.length - 1].date) : null;
```

```js
// Zoom par défaut sur les années récentes : sur l'historique complet, les dix-huit mois
// projetés n'occupaient qu'un liseré au bord droit du graphique — sur téléphone, à peine
// quelques pixels. La prévision est le sujet de la page ; elle doit se voir.
const vueInput = Inputs.radio(new Map([["Années récentes", "recent"], ["Tout l'historique", "tout"]]),
  {value: "recent", label: "Période affichée"});
const vue = view(vueInput);
```

```js
const XDOM = P && P.available && T ? (() => {
  const fin = new Date(P.series[P.series.length - 1].date);
  const lo = Math.min(periode[0], periode[1]);
  const debutFrise = new Date(Date.UTC(lo, 0, 1));
  const debutRecent = new Date(Date.UTC(new Date(dernierMois).getUTCFullYear() - 5, 0, 1));
  const debutSerie = new Date(T.series[0].date);
  const debut = vue === "recent"
    ? new Date(Math.max(debutFrise, debutRecent, debutSerie))
    : new Date(Math.max(debutFrise, debutSerie));
  return [debut, fin];
})() : null;
```

```js
const LEGENDE_PROJ = P && P.available ? legendStatic([
  {name: "Ventes réellement observées", color: series.brick},
  {name: "Projection du modèle", color: series.blue, dash: true},
  {name: "Fourchette probable (8 cas sur 10)", color: "rgba(230, 74, 25, 0.25)"},
  ...(B ? [{name: `Prévision ${B.source} ${B.annee} (décembre)`, color: series.violet}] : []),
]) : null;
```

```js
if (P && P.available) {
  const dansFenetre = (r) => new Date(r.date) >= XDOM[0];
  const observe = T.series.filter((r) => r.observed != null && dansFenetre(r))
    .map((r) => ({date: new Date(r.date), v: r.observed}));
  // La projection est raccordée au dernier point observé : sans ce raccord, la courbe
  // projetée commençait un mois plus tard, à un autre niveau, et rien ne reliait les deux.
  const projete = [{date: new Date(dernierMois + "T00:00:00Z"), v: P.last_observed}]
    .concat(P.series.map((r) => ({date: new Date(r.date), v: r.predicted})));
  const bande = P.series.map((r) => ({date: new Date(r.date), lo: r.lo, hi: r.hi}));
  const cible = V ? [{date: new Date(V.target_date + "T00:00:00Z"), v: V.predicted}] : [];
  display(cadreGraphique({
    titre: "Ventes de logements anciens : observées et projetées",
    sousTitre: "Ventes sur douze mois glissants · France",
    dernier: `${moisObserve} (observé)`, legende: LEGENDE_PROJ,
    source: "IGEDD ; projection du modèle du site (taux de crédit, intentions d'achat, chômage)",
    children: withCsvExport(Plot.plot({
      width, height: 360, marginLeft: 66, marginRight: 24, marginBottom: 34, marginTop: 24,
      x: {type: "utc", label: null, domain: XDOM},
      y: {label: "Ventes sur 12 mois", grid: true, zero: false, tickFormat: (v) => nf0.format(v)},
      marks: [
        Plot.areaY(bande, {x: "date", y1: "lo", y2: "hi", fill: series.brick, fillOpacity: 0.12}),
        Plot.lineY(observe, {x: "date", y: "v", stroke: series.brick, strokeWidth: 2.4}),
        Plot.lineY(projete, {x: "date", y: "v", stroke: series.blue, strokeWidth: 2.4, strokeDasharray: "5 3"}),
        // Le dernier chiffre publié, nommé : c'est la frontière entre ce qu'on sait et ce
        // que le modèle annonce.
        Plot.ruleX([projete[0]], {x: "date", stroke: ui.subtle, strokeDasharray: "2 3"}),
        Plot.text([projete[0]], {x: "date", frameAnchor: "top", dy: -14, text: () => "dernier chiffre publié",
                                 fill: ui.subtle, fontSize: 11, textAnchor: "middle"}),
        // L'échéance du verdict, posée sur la courbe : le chiffre de la phrase de tête se
        // retrouve ainsi à sa place.
        Plot.dot(cible, {x: "date", y: "v", r: 4.5, fill: series.blue, stroke: "white", strokeWidth: 2}),
        // Ancrée à GAUCHE du point : à droite, elle sortait du cadre sur téléphone.
        Plot.text(cible, {x: "date", y: "v", dy: 18, dx: 4, textAnchor: "end", fontWeight: 700, fill: series.blue, fontSize: 12,
                          stroke: "white", strokeWidth: 4, paintOrder: "stroke",
                          text: (d) => `${V.target_month} : ≈ ${k1(d.v)}`}),
        // Le repère FNAIM : un segment sur décembre, jamais une courbe — leur chiffre est un
        // total d'année, comparable au nôtre à ce mois-là seulement.
        B ? Plot.ruleX([B], {x: (d) => new Date(d.date), y1: "lo", y2: "hi",
                             stroke: series.violet, strokeWidth: 6, strokeOpacity: 0.45}) : null,
        Plot.tip(observe.concat(projete.slice(1)), Plot.pointerX({x: "date", y: "v", ...TIP,
          title: (d) => `${fmtMonthFR(d.date)}\n${d.date > projete[0].date ? "projeté" : "observé"} : ≈ ${k1(d.v)} ventes`})),
      ].filter(Boolean),
    }), P.series, "previsions-projection"),
  }));
  display(html`<div class="hm-caption">La zone colorée est la fourchette probable : lors des
    prévisions passées faites à la même distance, les ventes réelles y sont tombées 8 fois
    sur 10. Elle s'élargit avec le temps, et descend plus bas qu'elle ne monte parce que le
    modèle a eu tendance à surestimer.</div>`);
}
```

## 2. Pourquoi ce mouvement ?

```js
// LE POURQUOI, en clair. Le verdict disait où va le marché, jamais pourquoi — et la
// réponse n'est pas celle qu'on attend. La décomposition est calculée par l'export
// (engine.decomposition) et s'additionne exactement au mouvement projeté : l'effet de
// chaque indicateur, plus la résorption de l'écart entre le marché et ce que les
// indicateurs expliquent. C'est cette seconde part, la plus fragile, qu'il fallait dire.
const SEUIL = 500;   // en deçà, un effet est du bruit d'arrondi : « n'ajoute rien »
const NOMS = {kr: "Taux du crédit immobilier", ki: "Intentions d'achat", kc: "Chômage"};
// Libellés courts pour le graphique sur téléphone : les longs étaient coupés par la marge.
const NOMS_COURTS = {kr: "Taux du crédit", ki: "Intentions d'achat", kc: "Chômage",
                     ecart: "Écart qui se résorbe", total: "Total"};
const SUJETS = {kr: "le taux du crédit immobilier", ki: "les intentions d'achat", kc: "le chômage"};
const CONTRIB = W ? [
  ...W.entrees.map((e) => ({cle: e.cle, nom: NOMS[e.cle], v: e.effet})),
  {cle: "ecart", nom: "Écart au modèle qui se résorbe", v: W.resorption},
] : [];
const mouvement = W ? W.cible.valeur - W.depuis.valeur : null;
```

```js
// LA PHRASE-CLÉ d'abord : la part de l'indicateur et celle de l'hypothèse, en mots. Elle
// n'est écrite que si toutes les contributions vont dans le sens du mouvement — sinon des
// « parts » n'auraient pas de sens, et la phrase reste descriptive.
if (W) {
  const entrees = W.entrees.reduce((a, e) => a + e.effet, 0);
  const memeSens = [entrees, W.resorption].every((v) => Math.abs(v) < SEUIL || Math.sign(v) === Math.sign(mouvement));
  const DE = {kr: "du taux du crédit immobilier", ki: "des intentions d'achat", kc: "du chômage"};
  const moteurs = W.entrees.filter((e) => Math.abs(e.effet) >= SEUIL).map((e) => DE[e.cle]);
  const sens = mouvement < 0 ? "recul" : "hausse";
  if (memeSens && Math.abs(mouvement) >= SEUIL && moteurs.length && Math.abs(W.resorption) >= SEUIL)
    display(html`<p class="hm-enbref">En bref : ${partEnMots(entrees / mouvement)} de ce ${sens}
      vient ${moteurs.join(" et ")} ; ${partEnMots(W.resorption / mouvement)} vient d'une
      hypothèse — que le marché, aujourd'hui ${W.ecart_actuel > 0 ? "au-dessus" : "au-dessous"}
      de ce que ses moteurs expliquent, s'en rapproche.</p>`);
  display(html`<p>Entre ${moisIso(W.depuis.mois)} et ${V.target_month}, la projection passe de
    ${k1(W.depuis.valeur)} à ${k1(W.cible.valeur)} ventes sur douze mois, soit
    <b>${signe(mouvement)}</b>. Ce mouvement se décompose ainsi :</p>`);
}
```

```js
if (W) {
  const court = width < 600;
  const rows = CONTRIB.concat([{cle: "total", nom: "Mouvement total", v: mouvement}])
    .map((d) => (court ? {...d, nom: NOMS_COURTS[d.cle]} : d));
  // Le domaine suit les barres : avec un axe symétrique, la moitié du graphique restait
  // vide quand toutes les contributions vont dans le même sens.
  const vals = rows.map((d) => d.v);
  const etendue = (Math.max(0, ...vals) - Math.min(0, ...vals)) || 1;
  const marge = etendue * 0.22;   // place pour l'étiquette au bout des barres courtes
  const domaine = [Math.min(0, ...vals) - marge, Math.max(0, ...vals) + marge];
  display(cadreGraphique({
    titre: `D'où vient le mouvement projeté d'ici ${V.target_month}`,
    sousTitre: "Contribution de chaque facteur, en ventes sur douze mois · France",
    dernier: `${moisObserve} (observé)`,
    source: "IGEDD, Banque de France, INSEE ; décomposition du modèle du site",
    children: withCsvExport(Plot.plot({
      width, height: 44 * rows.length + 30, marginLeft: court ? 120 : 230, marginRight: 30,
      x: {label: "Ventes sur douze mois", grid: true, domain: domaine, tickFormat: (v) => signe(v, nf0.format)},
      y: {label: null, domain: rows.map((d) => d.nom)},
      marks: [
        Plot.barX(rows, {y: "nom", x: "v", fillOpacity: 0.9,
          fill: (d) => d.cle === "total" ? ui.subtle : d.cle === "ecart" ? series.gold : series.blue}),
        Plot.ruleX([0]),
        // Étiquette au bout de la barre, à l'extérieur ; À L'INTÉRIEUR (en blanc) pour les
        // barres longues, sans quoi elle mordait sur les libellés de gauche sur téléphone.
        Plot.text(rows.filter((d) => d.v < 0 && -d.v <= etendue * 0.45), {y: "nom", x: "v", text: (d) => signe(d.v), dx: -6, textAnchor: "end", fontWeight: 700}),
        Plot.text(rows.filter((d) => d.v < 0 && -d.v > etendue * 0.45), {y: "nom", x: "v", text: (d) => signe(d.v), dx: 6, textAnchor: "start", fontWeight: 700, fill: "white"}),
        Plot.text(rows.filter((d) => d.v >= 0 && d.v <= etendue * 0.45), {y: "nom", x: "v", text: (d) => Math.abs(d.v) < SEUIL ? "rien" : signe(d.v), dx: 6, textAnchor: "start", fontWeight: 700}),
        Plot.text(rows.filter((d) => d.v > etendue * 0.45), {y: "nom", x: "v", text: (d) => signe(d.v), dx: -6, textAnchor: "end", fontWeight: 700, fill: "white"}),
      ],
    }), rows.map(({nom, v}) => ({facteur: nom, ventes: Math.round(v)})), "previsions-decomposition"),
  }));
}
```

```js
// Les phrases suivent les chiffres : le sens (« retire » / « ajoute »), les mois et les
// valeurs viennent de la décomposition. Le solde d'opinion des intentions d'achat (« −82 »)
// n'est jamais affiché : il ne parle à personne ; on dit dans quel sens il a bougé.
function phraseEntree(e) {
  const effet = Math.abs(e.effet) < SEUIL ? null : e.effet;
  const verbe = effet == null ? "" : effet < 0 ? `retire environ ${k1(-effet)} ventes` : `ajoute environ ${k1(effet)} ventes`;
  const delai = e.lag ? `avec environ ${e.lag} mois de retard` : "sans délai";
  if (e.cle === "kr") return effet == null ? null
    : html`<li><b>Le taux du crédit immobilier</b> est passé de ${nf1.format(e.de.valeur)} %
      (${moisIso(e.de.mois)}) à ${nf1.format(e.a.valeur)} % (${moisIso(e.a.mois)}). Il agit
      sur les ventes ${delai} : ce mouvement ${verbe}.</li>`;
  if (e.cle === "kc") return effet == null ? null
    : html`<li><b>Le chômage</b> est passé de ${nf1.format(e.de.valeur)} % à
      ${nf1.format(e.a.valeur)} % : ce mouvement ${verbe}.</li>`;
  if (e.cle === "ki") return effet == null ? null
    : html`<li><b>L'envie d'acheter des ménages</b> ${effet > 0 ? "s'est améliorée" : "s'est dégradée"}
      (intentions d'achat de l'INSEE) : ${verbe}.</li>`;
  return null;
}
if (W) {
  const actifs = W.entrees.map(phraseEntree).filter(Boolean);
  const figes = W.entrees.filter((e) => Math.abs(e.effet) < SEUIL);
  const g = W.ecart_actuel;
  display(html`<ul>
    ${actifs}
    ${figes.length ? (() => {
      const pluriel = figes.length > 1 || figes[0].cle === "ki";
      const sujet = figes.map((e) => SUJETS[e.cle]).join(" et ").replace(/^./, (c) => c.toUpperCase());
      return html`<li><b>${sujet}</b> n'${pluriel ? "ajoutent" : "ajoute"} rien :
        ${figes.every((e) => e.a.reporte)
          ? (pluriel ? "leurs derniers chiffres publiés sont maintenus tels quels, faute de valeurs plus récentes."
                     : "son dernier chiffre publié est maintenu tel quel, faute de valeur plus récente.")
          : (pluriel ? "ils n'ont presque pas bougé." : "il n'a presque pas bougé.")}</li>`;
    })() : ""}
    ${Math.abs(W.resorption) >= SEUIL ? html`<li><b>Le marché est aujourd'hui environ
      ${k1(Math.abs(g))} ventes ${g > 0 ? "au-dessus" : "au-dessous"}</b> de ce que ces trois
      indicateurs expliquent. Le modèle suppose que cet écart se réduit :
      ${W.resorption < 0 ? `environ ${k1(-W.resorption)} ventes en moins` : `environ ${k1(W.resorption)} ventes en plus`}
      d'ici ${V.target_month}. C'est la part la plus fragile de la prévision : un marché peut
      rester longtemps ${g > 0 ? "au-dessus" : "au-dessous"} de ce niveau.</li>` : ""}
  </ul>`);
}
```

## 3. Peut-on s'y fier ?

```js
// Les bornes d'usage, en MOIS NOMMÉS et en IMAGE : une frise de la projection en trois
// zones, dont la largeur suit le nombre de mois. Elle remplace trois paragraphes qui
// disaient la même chose (« avant février 2027… de février à juin… au-delà… ») et qu'il
// fallait lire jusqu'au bout pour voir où tombait l'échéance annoncée.
if (P && P.available && data.crossover_horizon) {
  const h0 = Math.max(1, data.crossover_horizon), h1 = P.informative_months, hN = P.series.length;
  const mois = (h) => moisCourt(plusMois(dernierMois, h));
  const zones = [
    h0 > 1 ? {cls: "naive", n: h0 - 1, de: mois(1), a: mois(h0 - 1),
              titre: "Le dernier chiffre connu fait aussi bien",
              texte: `sur quelques mois, un cumul de douze mois bouge peu : s'en tenir à ${k1(P.last_observed)} ventes`} : null,
    h1 >= h0 ? {cls: "modele", n: h1 - h0 + 1, de: mois(h0), a: mois(h1),
              titre: "Le modèle apporte une vraie information",
              texte: V && V.horizon >= h0 && V.horizon <= h1 ? `dont l'échéance annoncée : ${V.target_month}` : ""} : null,
    hN > h1 ? {cls: "niveau", n: hN - h1, de: mois(h1 + 1), a: mois(hN),
              titre: "Un ordre de grandeur",
              texte: `la courbe se fige vers ${k1(P.end_value)} ventes : les indicateurs ne sont pas encore publiés`} : null,
  ].filter(Boolean);
  display(html`<div class="hm-frise" role="img" aria-label=${zones.map((z) => `${z.de} à ${z.a} : ${z.titre}`).join(" ; ")}>
    ${zones.map((z) => html`<div class="hm-frise-zone hm-frise-zone--${z.cls}" style=${{flexGrow: z.n}}>
      <div class="hm-frise-dates">${z.de === z.a ? z.de : `${z.de} → ${z.a}`}</div>
      <div class="hm-frise-titre">${z.titre}</div>
      ${z.texte ? html`<div class="hm-frise-texte">${z.texte}</div>` : ""}
    </div>`)}
  </div>`);
  display(html`<div class="hm-caption">Les mois se comptent depuis le dernier chiffre publié
    (${moisObserve}), là où part la projection. Comment ces bornes sont mesurées, et dans
    quelles conditions le modèle réussit le mieux : <a href="/methode-prevision">méthode de
    la prévision</a>.</div>`);
}
```

```js
// LE SEUL REPÈRE EXTERNE DISPONIBLE, en une phrase. Les précautions de comparaison
// (total d'année contre cumul glissant, périmètres) sont sur la page Méthode.
if (B) display(html`<div class="hm-note"><p><strong>Repère extérieur.</strong> Pour
  ${B.annee}, la <a href=${B.url}>${B.source}</a> annonçait ${k1(B.lo)} à ${k1(B.hi)} ventes.
  Notre modèle en projette environ ${k1(B.notre_prevision)} pour décembre ${B.annee},
  ${B.dans_la_fourchette ? html`<b>dans leur fourchette</b>` : html`<b>en dehors de leur fourchette</b>`}.
  Les deux estimations sont indépendantes : la leur vient de leur réseau d'agences, la nôtre
  de trois indicateurs publics.</p></div>`);
```

## 4. Et si les conditions changeaient ?

<div class="hm-caption">
Choisissez un scénario, ou réglez vous-même les trois leviers. Le résultat se lit par rapport
à la prévision centrale, en fin de projection : c'est le temps qu'il faut pour qu'un
changement d'aujourd'hui atteigne pleinement les ventes.
</div>

```js
const base = data.available ? data.scenario_baseline : null;
const r1 = (v) => Math.round(v * 10) / 10;
const r05 = (v) => Math.round(v * 20) / 20;
```

```js
// Trois curseurs en UNITÉS PARLANTES. Le taux était réglé en « points d'OAT » et l'envie
// d'acheter en écarts-types (« 0,4 ») : deux unités que personne ne lit. Le taux se règle
// désormais directement en taux du crédit, converti en OAT pour la formule (étage 1 :
// le taux du crédit suit l'OAT avec un coefficient publié sur la page Méthode) ; l'envie
// d'acheter se règle en cinq crans relatifs à aujourd'hui, un cran valant un demi
// écart-type de l'enquête INSEE.
//
// Les éléments sont gardés dans des CONSTANTES avant `view()` : c'est ce qui permet aux
// boutons de scénario de leur écrire une valeur (`viewof` n'existe pas dans Framework).
const ENVIES = new Map([["Nettement en baisse", -1], ["En baisse", -0.5], ["Inchangée", 0],
                        ["En hausse", 0.5], ["Nettement en hausse", 1]]);
const tauxInput = base ? Inputs.range([2, 5], {label: "Taux du crédit immobilier (%)",
  step: 0.05, value: r05(base.rate_now)}) : null;
const chomInput = base ? Inputs.range([6.5, 11], {label: "Taux de chômage (%)",
  step: 0.1, value: r1(base.unemployment)}) : null;
// Une liste déroulante plutôt que cinq boutons radio : sur téléphone, les cinq crans
// passaient sur trois lignes, et le libellé se retrouvait loin de son réglage.
const envieInput = base ? Inputs.select(ENVIES, {label: "Envie d'acheter des ménages",
  value: 0}) : null;
```

```js
// SCÉNARIOS NOMMÉS : ils écrivent dans les curseurs, qui restent la source de vérité — le
// lecteur voit ainsi à quelles hypothèses correspond le scénario choisi.
const SCENARIOS = base ? [
  {nom: "Sans changement", taux: r05(base.rate_now), chom: r1(base.unemployment), envie: 0,
   aide: "Les conditions actuelles, prolongées : le résultat est la prévision centrale."},
  {nom: "Détente du crédit", taux: r05(base.rate_now - 0.4), chom: r1(base.unemployment), envie: 0.5,
   aide: "Le taux du crédit baisse de 0,4 point et les ménages reprennent confiance."},
  {nom: "Remontée des taux", taux: r05(base.rate_now + 0.7), chom: r1(base.unemployment), envie: -0.5,
   aide: "Le taux du crédit gagne 0,7 point et l'envie d'acheter recule."},
  {nom: "Choc sur l'emploi", taux: r05(base.rate_now), chom: 9.5, envie: -1,
   aide: "Le chômage monte à 9,5 % et les ménages se retiennent nettement."},
] : [];
function appliquer(sc) {
  const set = (el, v) => {
    if (el && v != null) { el.value = v; el.dispatchEvent(new Event("input", {bubbles: true})); }
  };
  set(tauxInput, sc.taux);
  set(chomInput, sc.chom);
  set(envieInput, sc.envie);
}
// Chaque scénario porte sa description À L'ÉCRAN : elle n'était que dans l'infobulle,
// invisible sur téléphone et pour qui ne survole pas.
if (base) display(html`<div class="hm-scenarios">
  ${SCENARIOS.map((sc) => {
    const b = html`<button class="hm-scenario" type="button">
      <span class="hm-scenario-nom">${sc.nom}</span>
      <span class="hm-scenario-aide">${sc.aide}</span></button>`;
    b.onclick = () => appliquer(sc);
    return b;
  })}
</div>`);
```

```js
const taux = tauxInput ? view(tauxInput) : null;
const chom = chomInput ? view(chomInput) : null;
const envie = envieInput ? view(envieInput) : null;
```

```js
// Même formule qu'avant (computeScenario, vérifiée contre forecast.scenario par
// tests/test_web_js_parity.py) : on lui passe l'OAT qui correspond au taux du crédit
// choisi. Le résultat est l'EFFET du scénario ; il s'ajoute à la prévision centrale de fin
// de projection. Il s'ajoutait au niveau d'aujourd'hui : le scénario « conditions actuelles
// prolongées » affichait alors 951 000 ventes sous une courbe qui en annonçait 893 000.
const sc = base && P && P.available ? (() => {
  const oat = base.oat + (taux - base.rate_now) / R.coefficients.oat;
  const r = computeScenario(R.coefficients, T.coefficients, base,
                            {oat, chom, intentZ: base.intentions_z + envie});
  return {...r, centrale: P.end_value, scenario: P.end_value + r.transactions_change};
})() : null;
```

```js
if (sc) display(cardGrid([
  {label: `Prévision centrale (${finProj})`, value: `≈ ${k1(sc.centrale)}`,
   subs: ["ventes sur douze mois, si rien ne change"]},
  {label: "Dans ce scénario", value: `≈ ${k1(sc.scenario)}`,
   delta: pct1((sc.scenario / sc.centrale - 1) * 100),
   subs: [Math.abs(sc.transactions_change) < SEUIL ? "pas d'écart avec la prévision centrale"
          : `soit ${signe(sc.transactions_change)} ventes par rapport à la prévision centrale`]},
], kpiCard));
```

```js
if (sc) {
  const debut = new Date(Date.UTC(new Date(dernierMois).getUTCFullYear() - 3, 0, 1));
  const observe = T.series.filter((r) => r.observed != null && new Date(r.date) >= debut)
    .map((r) => ({date: new Date(r.date), v: r.observed}));
  const projete = [{date: new Date(dernierMois + "T00:00:00Z"), v: P.last_observed}]
    .concat(P.series.map((r) => ({date: new Date(r.date), v: r.predicted})));
  const fin = projete[projete.length - 1].date;
  const ecart = Math.abs(sc.transactions_change) >= SEUIL;
  display(cadreGraphique({
    titre: "Prévision centrale et scénario choisi",
    sousTitre: "Ventes de logements anciens sur douze mois · le scénario se lit en fin de projection",
    dernier: `${moisObserve} (observé)`,
    legende: legendStatic([
      {name: "Ventes observées", color: series.brick},
      {name: "Prévision centrale", color: series.blue, dash: true},
      {name: "Niveau atteint dans le scénario", color: series.gold}]),
    source: "IGEDD ; scénario calculé avec le modèle du site",
    children: Plot.plot({
      width, height: 280, marginLeft: 66, marginRight: 90, marginBottom: 30,
      x: {type: "utc", label: null},
      y: {label: "Ventes sur 12 mois", grid: true, zero: false, tickFormat: (v) => nf0.format(v),
          domain: [Math.min(...observe.map((d) => d.v), ...projete.map((d) => d.v), sc.scenario) * 0.97,
                   Math.max(...observe.map((d) => d.v), ...projete.map((d) => d.v), sc.scenario) * 1.03]},
      marks: [
        Plot.lineY(observe, {x: "date", y: "v", stroke: series.brick, strokeWidth: 2.4}),
        Plot.lineY(projete, {x: "date", y: "v", stroke: series.blue, strokeWidth: 2.4, strokeDasharray: "5 3"}),
        ecart ? Plot.ruleX([{date: fin}], {x: "date", y1: sc.centrale, y2: sc.scenario, stroke: series.gold, strokeWidth: 2}) : null,
        Plot.dot([{date: fin, v: sc.scenario}], {x: "date", y: "v", r: 6, fill: series.gold, stroke: "white", strokeWidth: 2}),
        Plot.text([{date: fin, v: sc.scenario}], {x: "date", y: "v", dx: 10, textAnchor: "start", fontWeight: 700,
          fill: series.gold, text: (d) => `≈ ${k1(d.v)}`}),
      ].filter(Boolean),
    }),
  }));
}
```

<div class="hm-shortcuts" style="margin-top:1.6rem">
  <span class="lead">Aller plus loin :</span>
  <a class="hm-shortcut" href="/previsions-passees">🎯 Nos prévisions passées, face au réel</a>
  <a class="hm-shortcut" href="/methode-prevision">🧮 Comment la prévision est fabriquée</a>
  <a class="hm-shortcut" href="/carte">📍 Votre département</a>
  <a class="hm-shortcut" href="/donnees">📤 Confronter vos propres ventes</a>
</div>

<div class="hm-caption" style="margin-top:1rem">
Cette prévision est nationale, et c'est délibéré : les taux, le chômage et l'envie d'acheter
se mesurent à l'échelle du pays. Pour votre département, les pages départementales donnent
les prix, les ventes et les logements mis en chantier réellement observés. Pour croiser
cette prévision avec <b>vos</b> ventes, voir la page
<a href="./donnees">📤 Confronter vos ventes</a> — le fichier reste dans votre navigateur.
</div>
