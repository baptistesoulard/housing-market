---
title: Prévision & Scénarios
toc: true
---

```js
import {multiLine, cardGrid, kpiCard, legendStatic, withCsvExport, filterYears, nf0, nf1, fmtMonthFR, Plot, TIP} from "./components/hm.js";
import {series, ui, delta} from "./components/theme.js";
import {periodFilter} from "./components/period.js";
import {computeScenario} from "./components/api.js";
```

```js
// Le modèle est réajusté chaque semaine par web_export.py (via api.engine, sans Flask —
// voir docs/journal/03-api-http.md) et publié ici comme les cinq premières pages : plus de
// serveur à joindre pour un visiteur. Ce qui restait interactif sans recalcul serveur l'est
// resté : la courbe de sensibilité est pré-calculée pour les 3 prédicteurs (le curseur ne
// fait plus qu'y lire un point), et le panneau de scénarios applique en JS la même formule
// fermée que `forecast.scenario` (voir computeScenario, components/api.js) — huit
// multiplications, pas de quoi justifier un aller-retour réseau.
const data = await FileAttachment("./data/previsions.json").json();
// La comparaison des modèles vit dans archive.json (page « Le modèle face au réel ») ;
// cette page n'en lit que la phrase de statut, pour dire ce qui est publié et pourquoi.
const CMP = (await FileAttachment("./data/archive.json").json()).comparaison ?? null;
const R = data.available ? data.rate : null;
const T = data.available ? data.transactions : null;
const P = data.available ? data.projection : null;
const V = data.available ? data.verdict : null;
const B = data.available ? data.benchmark : null;
const RG = data.available ? (data.regime ?? null) : null;
const B2 = data.available ? data.benchmark_taux : null;
const pct = (v) => nf1.format(v * 100) + " %";
```

```js
// La frise de période, comme sur les autres onglets. Elle ne rogne que l'AFFICHAGE de
// l'historique : rien n'est recalculé, le modèle reste ajusté sur toute la profondeur
// disponible — un modèle réestimé au gré d'un curseur ne serait plus celui que l'archive
// des prévisions passées a jugé.
const periode = Generators.input(periodFilter({
  min: data.period.min, max: data.period.max,
  note: "Rogne l'historique affiché. Les projections, postérieures au dernier mois publié, restent visibles.",
}));
```

```js
// Deux façons de rogner, et la distinction n'est pas cosmétique. `histo` applique la frise
// entière aux séries observées. `depuis` n'applique QUE la borne basse, et sert aux séries
// PROJETÉES : elles sont postérieures au dernier mois publié, donc au maximum de la frise,
// et la borne haute les ferait disparaître dès qu'on touche au curseur — c'est-à-dire
// masquer la prévision sur une page de prévision.
const histo = (rows, field = "date") => filterYears(rows, periode, field);
const depuis = (rows, field = "date") => {
  const lo = Math.min(periode[0], periode[1]);
  return rows.filter((r) => +String(r[field]).slice(0, 4) >= lo);
};
```

# 📡 Prévision des transactions & scénarios

<!--
  CHAPEAU STATIQUE, rendu au build — voir CLAUDE.md, « Texte statique : aucun chiffre, aucun état ».
  Page SYNTHÉTIQUE depuis le 2026-10-17 : le verdict, la courbe, jusqu'où s'y fier, les
  scénarios. Tout ce qui explique COMMENT le chiffre est produit (équations, recalage,
  entrées figées, décalages, idées écartées) est sur /methode-prevision, intact.
-->

Cette page projette les **ventes de logements anciens** en France sur les dix-huit mois qui
suivent le dernier mois publié. Elle s'appuie sur trois indicateurs publics : le taux du
crédit immobilier, les intentions d'achat des ménages et le chômage. La projection est
publiée avec sa fourchette et, surtout, avec les horizons auxquels elle mérite d'être lue.

Ni les mises en chantier ni l'activité de rénovation ne sont prévues ici : un lecteur venu
anticiper une activité de construction doit lire cette projection comme un **indicateur de
contexte**, pas comme son carnet de commandes. La fabrication du chiffre est détaillée sur
la page [Méthode de la prévision](/methode-prevision), et ses résultats passés sur
[Le modèle face au réel](/previsions-passees).

```js
// `available: false` ne peut venir que d'un macro incomplet au moment de la publication
// hebdomadaire (voir EngineUnavailable, api/engine.py) — pas d'un serveur injoignable,
// cette page n'en appelle plus aucun. Cas rare, jamais vu en pratique ; l'encart explique
// quand même ce qui manque plutôt que de laisser des graphiques vides.
if (data.available) display(html`<div class="hm-caption">Données jusqu'à
    ${fmtMonthFR(new Date(data.health.transactions_last_month + "T00:00:00Z"))} ·
    entraînement du backtest ≤ ${data.health.forecast_split.slice(0, 4)}.</div>`);
else display(html`<div class="hm-api-offline">
  <div class="hm-api-offline-title">⚙️ Modèle non calibré à la dernière publication</div>
  <p>${data.reason}</p>
  <p>En attendant, <a href="/synthese">la synthèse du marché</a> et les pages de détail
  restent complètes.</p>
</div>`);
```

```js
// LE VERDICT, en tête de page. Jusqu'ici cette page publiait les entrailles du modèle —
// un R², une MAPE, trois coefficients OLS, un z-score d'intentions d'achat — et nulle
// part sa conclusion. Un visiteur repartait sans la phrase qu'il était venu chercher.
//
// Elle est GÉNÉRÉE (web/export/verdict.py), jamais écrite à la main : elle porte des
// chiffres, donc elle ne peut pas vivre dans le chapeau statique, que rien ne régénère.
// La fiabilité affichée à côté n'est pas le R² mais la part de fois où le SENS annoncé à
// cet horizon s'est avéré le bon, mesurée sur 210 millésimes.
if (V) display(html`<div class="hm-takeaways">
  <strong>Ce que dit le modèle aujourd'hui</strong>
  <ul>
    <li><strong>${V.sentence}</strong> Fourchette
      ${nf0.format(V.lo)} – ${nf0.format(V.hi)}.</li>
    ${V.reliability ? html`<li><strong>À cet horizon</strong>, le modèle a annoncé le
      <strong>bon sens ${nf0.format(V.reliability.direction * 100)} %</strong> du temps sur
      les ${nf0.format(V.reliability.n)} mois déjà jugés, avec une erreur moyenne de
      ${nf1.format(V.reliability.mape)} % contre ${nf1.format(V.reliability.naive_mape)} %
      pour une prévision naïve.</li>` : ""}
    <li>Le détail de ces comptes, épisode par épisode, est sur
      <a href="/previsions-passees">Le modèle face au réel</a> — y compris les périodes où le
      modèle s'est trompé.</li>
  </ul>
</div>`);
```

## 1. Où va le marché, et jusqu'où s'y fier

```js
// L'INDICATEUR DE TÊTE vise le MÊME mois que le verdict (six mois devant le lecteur).
// Jusqu'au 2026-10-17, il montrait la fin d'horizon — le mois le moins informatif de la
// trajectoire, puisqu'au-delà de `informative_months` tous les indicateurs sont figés et la
// courbe ne fait que répéter son niveau — et il ne disait pas le même chiffre que le
// verdict juste au-dessus. La fin d'horizon reste affichée, sous son vrai nom.
if (V && P && P.available) display(cardGrid([
  {label: `Dans ${V.months_ahead} mois (${V.target_month})`, value: nf0.format(V.predicted),
   delta: (V.change_pct >= 0 ? "+" : "−") + nf1.format(Math.abs(V.change_pct)) + " %",
   subs: [`fourchette ${nf0.format(V.lo)} – ${nf0.format(V.hi)}`, "ventes sur douze mois"]},
  {label: "Niveau d'atterrissage", value: nf0.format(P.end_value),
   delta: (P.end_change_pct >= 0 ? "+" : "−") + nf1.format(Math.abs(P.end_change_pct)) + " %",
   subs: [`au-delà du ${P.informative_months}e mois, la courbe ne bouge plus`,
          "à lire comme un niveau, pas comme un chemin"]}
], kpiCard));
```

```js
// Même manque qu'en section 2 : quatre objets sur ce graphique (l'observé, la trajectoire
// projetée, sa bande, le repère FNAIM) et rien qui les nomme. La légende est statique —
// aucune de ces séries ne se masque.
if (P && P.available) display(legendStatic([
  {name: "Ventes réellement observées", color: series.brick},
  {name: "Projection du modèle", color: series.blue, dash: true},
  ...(B ? [{name: `Fourchette ${B.source} ${B.annee} (décembre seulement)`, color: series.violet}] : []),
]));
```

```js
if (P && P.available) display(withCsvExport(Plot.plot({
  width, height: 360, marginLeft: 66, marginBottom: 34,
  x: {type: "utc", label: null},
  y: {label: "Ventes sur 12 mois", grid: true, tickFormat: (v) => nf0.format(v)},
  marks: [
    // La bande et la trajectoire projetées ne reçoivent que la borne basse : elles sont
    // postérieures au dernier mois publié, donc au maximum de la frise.
    Plot.areaY(depuis(P.series), {x: (d) => new Date(d.date), y1: "lo", y2: "hi",
                          fill: series.brick, fillOpacity: 0.12}),
    Plot.lineY(histo(T.series), {x: (d) => new Date(d.date), y: "observed",
                          stroke: series.brick, strokeWidth: 2.2}),
    Plot.lineY(depuis(P.series), {x: (d) => new Date(d.date), y: "predicted",
                          stroke: series.blue, strokeWidth: 2.2, strokeDasharray: "4 3"}),
    // Frontière entre la partie sans hypothèse et le report des indicateurs manquants.
    Plot.ruleX(P.series.filter((d) => d.assured).slice(-1),
               {x: (d) => new Date(d.date), stroke: ui.subtle, strokeDasharray: "3 3"}),
    // Le repère FNAIM : un SEGMENT VERTICAL sur décembre, jamais une courbe. Leur chiffre
    // est un total d'année, comparable au nôtre uniquement à ce mois-là ; le tracer en
    // continu suggérerait une prévision mensuelle qu'ils ne publient pas.
    B ? Plot.ruleX([B], {x: (d) => new Date(d.date), y1: "lo", y2: "hi",
                         stroke: series.violet, strokeWidth: 6, strokeOpacity: 0.35}) : null,
    B ? Plot.text([B], {x: (d) => new Date(d.date), y: "hi", dy: -12,
                        text: () => `fourchette ${B.source} ${B.annee}`,
                        fill: series.violet, fontWeight: 600, textAnchor: "end", dx: -6}) : null
  ]
}), P.series, "previsions-projection"));
```

```js
if (P && P.available) display(html`<div class="hm-caption">
  La bande n'est pas symétrique : elle vient des erreurs réellement commises par le modèle
  dans le passé, horizon par horizon (quantiles 10 % et 90 %). Au-delà du
  <strong>${P.informative_months}<sup>e</sup> mois</strong>, tous les indicateurs sont
  maintenus à leur dernière valeur connue : la courbe n'ajoute plus d'information, seulement
  de l'incertitude.
</div>`);
```

```js
// JUSQU'OÙ S'Y FIER — en une note. La page en portait trois avant le 2026-10-17 (régime de
// taux, tableau des horizons, mise en garde sur le décompte des mois), toutes placées AVANT
// la courbe. Les trois sont intactes sur /methode-prevision ; ici ne restent que les
// bornes d'usage et le régime en une phrase.
if (V && P && P.available && data.crossover_horizon) display(html`<div class="hm-note">
  <p><strong>Jusqu'où s'y fier.</strong> Les horizons se comptent depuis le dernier mois
  publié (${fmtMonthFR(new Date(data.health.transactions_last_month + "T00:00:00Z"))}).
  En deçà de <b>${data.crossover_horizon} mois</b>, le dernier chiffre connu
  (${nf0.format(P.last_observed)}) fait mieux que le modèle ; de ${data.crossover_horizon}
  à ${P.informative_months} mois, le modèle apporte quelque chose ; au-delà, ne retenir
  qu'un niveau d'atterrissage.${RG ? html` Régime actuel : <b>${RG.label}</b> — dans des
  conditions comparables, le modèle a annoncé le bon sens
  ${nf0.format((RG.direction_horizon ?? RG.direction) * 100)} % du temps.` : ""}</p>
  ${CMP ? html`<p>${CMP.statut} <a href="/previsions-passees#d-autres-modeles-juges-de-la-meme-facon">Voir
    la comparaison des modèles</a>.</p>` : ""}
  <p class="hm-caption">Pourquoi ces bornes, comment le régime est mesuré, et les équations :
  <a href="/methode-prevision">méthode de la prévision</a>.</p>
</div>`);
```

```js
// LE SEUL REPÈRE EXTERNE DISPONIBLE. Personne ne publie de prévision mensuelle de volumes
// en France — les Notaires, qui disposent pourtant des avant-contrats, ne s'en servent que
// pour projeter les prix. La fourchette annuelle de la FNAIM est donc notre unique point
// de contrôle, et il ne vaut qu'en décembre : leur chiffre est un total d'année, le nôtre
// un cumul 12 mois glissants.
if (B) display(html`<div class="hm-note">
  <p><strong>Face à la seule autre prévision chiffrée du marché.</strong> Pour
  ${B.annee}, la <a href=${B.url}>${B.source}</a> annonçait
  <strong>${nf0.format(B.lo)} à ${nf0.format(B.hi)}</strong> ventes. Notre modèle projette
  <strong>${nf0.format(B.notre_prevision)}</strong> —
  ${B.dans_la_fourchette
    ? html`<b>dans leur fourchette</b>, à ${nf1.format(Math.abs(B.ecart_au_milieu_pct))} %
           de son milieu`
    : html`<b>en dehors</b>, à ${nf1.format(Math.abs(B.ecart_au_milieu_pct))} % de son
           milieu`}. Les deux estimations sont indépendantes : la leur vient de leur réseau
  d'agences, la nôtre de trois indicateurs macro publics.</p>
  <p class="hm-caption">${B.note} Fourchette relevée le ${B.releve_le}.</p>
</div>`);
```

## 2. Et si les conditions changeaient ?

<div class="hm-caption">
Effet à terme (après les décalages estimés) si ces conditions persistent, appliqué au
niveau actuel réel — approche en écart, robuste au biais de niveau du modèle de taux.
</div>

```js
const base = data.available ? data.scenario_baseline : null;
const r1 = (v) => Math.round(v * 10) / 10;
```

```js
// UN SEUL curseur de financement, et c'est un correctif, pas une simplification.
// L'OAT 10 ans et l'Euribor 3 mois sont corrélés à +0,83 : l'OLS de l'étage 1 ne peut pas
// les séparer et attribue tout au premier (0,707 contre 0,013). Exposés séparément, le
// curseur Euribor était donc INERTE — balayé sur toute sa course, cinq points de taux, il
// déplaçait la prévision de 0,3 %, contre 11 à 24 % pour les trois autres. Un levier
// affiché qui ne lève rien est pire qu'un levier absent : le visiteur en conclut que le
// taux interbancaire n'agit pas sur le marché immobilier, ce qui est faux.
// Les deux bougent ensemble, comme dans la réalité, et la sensibilité affichée est leur
// somme. `computeScenario` est inchangée — elle reçoit toujours les deux valeurs.
// Les trois entrées sont gardées dans des CONSTANTES avant d'être passées à `view()`.
// C'est ce qui permet aux boutons de scénario plus bas de leur écrire une valeur : dans
// Observable Framework, `viewof x` n'existe pas — c'est de la syntaxe notebook, et une
// cellule qui l'emploie est retirée du build SANS ERREUR. Garder la référence à l'élément
// est le seul moyen documenté d'y accéder depuis une autre cellule.
const dTauxInput = base ? Inputs.range([-2.5, 2.5], {
  label: "Taux de marché (0 = inchangé, en points)", step: 0.1, value: 0,
}) : null;
const chomInput = base ? Inputs.range([6.5, 11],
  {label: "Taux de chômage (%)", step: 0.1, value: r1(base.unemployment)}) : null;
const intentZInput = base ? Inputs.range([-2.5, 2.5],
  {label: "Intentions d'achat (0 = moyenne historique)", step: 0.1, value: r1(base.intentions_z)}) : null;

const dTaux = dTauxInput ? view(dTauxInput) : null;
const chom = chomInput ? view(chomInput) : null;
const intentZ = intentZInput ? view(intentZInput) : null;
```

```js
// SCÉNARIOS NOMMÉS. Les curseurs restent la source de vérité — ces boutons ne font que
// leur écrire une valeur puis émettre l'événement "input" qui réveille les cellules qui
// en dépendent. C'est le patron documenté d'Observable Inputs, et il a l'avantage que le
// curseur BOUGE : le lecteur voit à quelles hypothèses correspond le scénario qu'il a
// choisi, au lieu d'un résultat sorti d'une boîte.
//
// Pourquoi ils existent : « OAT 10 ans » et « Euribor 3 mois » ne veulent rien dire pour
// un particulier, alors que « si la BCE baisse ses taux d'un demi-point » lui parle
// immédiatement. Aucun calcul nouveau — les mêmes valeurs, poussées dans les mêmes
// curseurs.
const SCENARIOS = [
  {nom: "Aujourd'hui", dTaux: 0, chom: base?.unemployment, z: base?.intentions_z,
   aide: "Les conditions actuelles, prolongées."},
  {nom: "Détente du crédit", dTaux: -0.5, chom: base?.unemployment, z: (base?.intentions_z ?? 0) + 0.5,
   aide: "La BCE baisse d'un demi-point et les ménages reprennent confiance."},
  {nom: "Remontée des taux", dTaux: 1, chom: base?.unemployment, z: (base?.intentions_z ?? 0) - 0.5,
   aide: "Un point de taux de marché en plus, et l'envie d'acheter recule."},
  {nom: "Choc sur l'emploi", dTaux: 0, chom: 9.5, z: (base?.intentions_z ?? 0) - 1,
   aide: "Le chômage monte à 9,5 %, sans mouvement de taux."},
];

function appliquer(sc) {
  const set = (el, v) => {
    if (el && v != null) { el.value = v; el.dispatchEvent(new Event("input", {bubbles: true})); }
  };
  set(dTauxInput, sc.dTaux);
  set(chomInput, sc.chom);
  set(intentZInput, sc.z);
}

if (base) display(html`<div class="hm-shortcuts">
  <span class="lead">Scénarios prêts :</span>
  ${SCENARIOS.map((sc) => {
    const b = html`<button class="hm-shortcut" type="button" title=${sc.aide}>${sc.nom}</button>`;
    b.onclick = () => appliquer(sc);
    return b;
  })}
</div>`);
```

```js
const oat = base ? base.oat + dTaux : null;
```

```js
if (base) display(html`<div class="hm-caption">Le curseur déplace l'<abbr title="Obligation d'État française à 10 ans, référence du coût du crédit à long terme">OAT</abbr>
  10 ans, seul taux de marché que le modèle retient : c'est lui qui tarife un crédit à taux
  fixe adossé à du financement long. Position actuelle
  <b>${nf1.format(oat)} %</b>, soit <b>${nf1.format(R.coefficients.oat)} pt</b> de taux de
  crédit par point d'OAT, au bout de ${R.lag} mois.</div>`);
```

```js
// Huit multiplications, en JS — computeScenario reproduit forecast.scenario terme à
// terme (voir components/api.js) sur les coefficients exportés. Pas de quoi justifier un
// aller-retour réseau à chaque déplacement de curseur, contrairement au POST que l'API
// exposait pour cette même route.
const sc = base
  ? computeScenario(R.coefficients, T.coefficients, base, {oat, chom, intentZ})
  : null;
```

```js
if (sc) display(cardGrid([
  {label: "Taux de crédit qui en résulterait", value: nf1.format(sc.rate) + " %",
   delta: (sc.rate_change >= 0 ? "+" : "−") + nf1.format(Math.abs(sc.rate_change)) + " pt"},
  {label: "Ventes projetées (12 mois)", value: nf0.format(sc.transactions),
   delta: (sc.transactions_change >= 0 ? "+" : "−") + nf0.format(Math.abs(sc.transactions_change))},
  {label: "Écart vs aujourd'hui",
   value: (sc.transactions_change_pct >= 0 ? "+" : "−") + nf1.format(Math.abs(sc.transactions_change_pct)) + " %"}
], kpiCard));
```

```js
if (sc) display(Plot.plot({
  width, height: 230, marginLeft: 72, marginBottom: 30,
  x: {label: null}, y: {label: "Ventes 12 mois", grid: true, tickFormat: (v) => nf0.format(v)},
  marks: [
    Plot.barY([{k: "Actuel", v: sc.baseline.tx_now}, {k: "Scénario", v: sc.transactions}],
              {x: "k", y: "v", fill: (d) => d.k === "Actuel" ? ui.subtle : series.brick}),
    Plot.text([{k: "Actuel", v: sc.baseline.tx_now}, {k: "Scénario", v: sc.transactions}],
              {x: "k", y: "v", text: (d) => nf0.format(d.v), dy: -8, fontWeight: 700}),
    Plot.ruleY([0], {stroke: ui.border})
  ]
}));
```

<div class="hm-shortcuts" style="margin-top:1.6rem">
  <span class="lead">Aller plus loin :</span>
  <a class="hm-shortcut" href="/previsions-passees">🎯 Nos prévisions passées, face au réel</a>
  <a class="hm-shortcut" href="/methode-prevision">🧮 Comment la prévision est fabriquée</a>
  <a class="hm-shortcut" href="/carte">📍 Votre département</a>
  <a class="hm-shortcut" href="/donnees">📤 Confronter vos propres ventes</a>
</div>

<div class="hm-caption" style="margin-top:1rem">
Cette page raisonne au niveau NATIONAL, et c'est délibéré : les taux, le chômage et les
intentions d'achat sont des grandeurs nationales. Un modèle « local » publierait cent une
fois la même courbe sous cent un titres. Pour le marché de votre département, les pages
départementales donnent les prix, les ventes et les logements mis en chantier
réellement observés.
Pour croiser ces prévisions avec <b>vos</b> ventes, voir la page
<a href="./donnees">📤 Confronter vos ventes</a> — le fichier reste dans votre navigateur.
</div>
