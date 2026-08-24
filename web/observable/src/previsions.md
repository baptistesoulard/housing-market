---
title: Prévision & Scénarios
toc: true
---

```js
import {multiLine, cardGrid, kpiCard, withCsvExport, nf0, nf1, fmtMonthFR, Plot} from "./components/hm.js";
import {series, ui} from "./components/theme.js";
import {computeScenario} from "./components/api.js";
```

```js
// Le modèle est réajusté chaque semaine par web_export.py (via api.engine, sans Flask —
// voir CLAUDE.md, « L'API HTTP ») et publié ici comme les cinq premières pages : plus de
// serveur à joindre pour un visiteur. Ce qui restait interactif sans recalcul serveur l'est
// resté : la courbe de sensibilité est pré-calculée pour les 3 prédicteurs (le curseur ne
// fait plus qu'y lire un point), et le panneau de scénarios applique en JS la même formule
// fermée que `forecast.scenario` (voir computeScenario, components/api.js) — huit
// multiplications, pas de quoi justifier un aller-retour réseau.
const data = await FileAttachment("./data/previsions.json").json();
const R = data.available ? data.rate : null;
const T = data.available ? data.transactions : null;
const P = data.available ? data.projection : null;
const pct = (v) => nf1.format(v * 100) + " %";
```

# 📡 Prévision des transactions & scénarios

<!--
  CHAPEAU STATIQUE, rendu au build — voir CLAUDE.md, « Le chapeau des pages de données ».
  Cette page-ci est un cas limite : sans instance de l'API, un visiteur ne voit QUE ce
  texte. Raison de plus pour qu'il dise ce que la page fait.
-->

Prévoir des transactions immobilières revient à prévoir une demande, et ce site le fait
avec les méthodes de la planification, en deux étages. Le premier explique le taux du
crédit immobilier par les taux de marché ; le second explique les ventes de logements
anciens par ce taux de crédit, les intentions d'achat des ménages et le chômage, chacun
pris avec son propre décalage.

La projection est publiée avec son backtest hors échantillon et sa bande d'incertitude, et
les scénarios permettent d'en manipuler les leviers. Les prévisions déjà publiées, elles,
sont archivées et confrontées au réalisé sur leur propre page.

<div class="hm-caption">
Modèle chiffré « indicateurs avancés → transactions », calibré sur les séries réelles.
Deux étages : (1) le taux de crédit est modélisé à partir de l'<abbr title="Obligation d'État française à 10 ans, référence du coût du crédit à long terme">OAT</abbr> 10 ans et de l'<abbr title="Taux auquel les banques de la zone euro se prêtent entre elles à court terme">Euribor</abbr>
3 mois ; (2) les ventes de logements anciens (cumul 12 mois) sont expliquées par le taux
de crédit, les intentions d'achat et le chômage, chacun décalé. Un <abbr title="Test du modèle sur des données qu'il n'a pas vues à l'entraînement">backtest</abbr> hors
échantillon mesure la valeur prédictive.
</div>

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
if (data.available) display(html`<hr>`);
```

## 1. Modèle de taux de crédit (OAT 10 ans + Euribor 3 mois)

```js
if (R) display(html`<div class="hm-panels">
  <div>
    ${multiLine({
      rows: [
        ...R.series.map((d) => ({date: d.date, value: d.observed, series: "Taux observé"})),
        ...R.series.map((d) => ({date: d.date, value: d.modelled, series: "Taux modélisé"}))
      ],
      meta: [{name: "Taux observé", color: series.brick},
             {name: "Taux modélisé", color: series.blue, dash: true}],
      yLabel: "Taux (%)", height: 300,
      valueFmt: (v) => nf1.format(v) + " %", tipUnit: " %",
      filename: "previsions-modele-taux"
    })}
  </div>
  <div>
    ${kpiCard({label: "R² du modèle de taux", value: pct(R.r2)})}
    <div class="hm-caption" style="margin-top:0.6rem">
      <b>Taux ≈ ${nf1.format(R.coefficients.intercept)} +
      ${nf1.format(R.coefficients.oat)}·OAT +
      ${nf1.format(R.coefficients.euribor)}·Euribor</b><br>
      +1 pt de taux de marché ⇒ ~+${nf1.format(R.coefficients.oat + R.coefficients.euribor)} pt
      de taux crédit. Les deux coefficients ne se lisent pas séparément : l'OAT et l'Euribor
      sont corrélés à 0,83 sur la période, si bien que l'ajustement attribue presque tout au
      premier. C'est leur SOMME qui a un sens, et c'est elle que pilote le panneau de
      scénarios.<br>
      L'écart 2023-25 (taux sous l'OAT) reflète des banques qui retiennent leurs barèmes.<br>
      <span style="color:${ui.subtle}">Sources : Banque de France / BCE.</span>
    </div>
  </div>
</div>`);
```

## 2. Nowcast des transactions & backtest hors échantillon

```js
if (T) display(cardGrid([
  {label: "R² (in-sample)", value: pct(T.r2)},
  {label: "Erreur hors échantillon (MAPE)", value: nf1.format(T.backtest.mape) + " %"},
  {label: "Décalages (taux / intentions / chômage)",
   value: `${T.lags.kr} / ${T.lags.ki} / ${T.lags.kc} mois`}
], kpiCard));
```

```js
if (T) display(multiLine({
  rows: [
    ...T.series.map((d) => ({date: d.date, value: d.observed, series: "Observé (IGEDD)"})),
    ...T.backtest.series.map((d) => ({date: d.date, value: d.predicted,
                                      series: "Prévision hors échantillon"}))
  ],
  meta: [{name: "Observé (IGEDD)", color: series.brick},
         {name: "Prévision hors échantillon", color: series.blue, dash: true}],
  yLabel: "Ventes sur 12 mois", valueFmt: (v) => nf0.format(v), width,
  filename: "previsions-backtest-transactions"
}));
```

<div class="hm-caption">
Le modèle entraîné uniquement sur les données antérieures au découpage reproduit la
contraction 2022-24 puis la reprise 2025-26 — sans les avoir vues. C'est la preuve que ces
indicateurs avancés « prévoient » réellement.
</div>

## 🔬 Vérifier les décalages retenus

<div class="hm-caption">
Déplacez le décalage d'un prédicteur : le modèle est réestimé et son R² bouge. C'est ce
qui rend la recherche en grille <i>auditable</i> plutôt qu'affirmée. La courbe entière
arrive en une requête, donc le curseur ne provoque aucun aller-retour réseau.
</div>

```js
const predictorLabels = {rate: "Taux de crédit", intentions: "Intentions d'achat",
                         unemployment: "Taux de chômage"};
const predictor = view(Inputs.select(Object.keys(predictorLabels), {
  label: "Prédicteur à inspecter", format: (k) => predictorLabels[k], value: "rate"
}));
```

```js
// Les 3 courbes (une par prédicteur) sont pré-calculées côté export : changer de
// prédicteur ne fait plus qu'une lecture dans le JSON déjà chargé, jamais de requête.
const sens = data.available ? data.lag_sensitivity[predictor] : null;
```

```js
// Le curseur démarre TOUJOURS sur le décalage retenu par la recherche en grille : c'est
// le point de comparaison, et il se replace quand on change de prédicteur.
const lag = sens
  ? view(Inputs.range([sens.curve[0].lag, sens.curve[sens.curve.length - 1].lag],
                      {label: "Décalage appliqué (mois)", step: 1, value: sens.retained_lag}))
  : null;
```

```js
const lagN = sens ? Math.round(lag) : null;
const atLag = sens ? sens.curve.find((p) => p.lag === lagN) : null;
const dR2 = atLag ? atLag.r2 - sens.retained_r2 : 0;
const dTxt = (dR2 >= 0 ? "+" : "−") + Math.abs(dR2).toFixed(3).replace(".", ",");
```

```js
if (sens) display(html`<div class="hm-panels">
  <div>
    ${kpiCard({label: "R² au décalage choisi",
               value: atLag.r2.toFixed(3).replace(".", ","),
               delta: `${dTxt} vs retenu`})}
    <div class="hm-caption" style="margin-top:0.6rem">
      ${lagN === sens.retained_lag
        ? `Décalage retenu par le modèle : ${sens.retained_lag} mois.`
        : dR2 > 0
          ? `Ce décalage fait mieux que celui retenu (${sens.retained_lag} mois) sur
             l'échantillon complet — attendu : la grille cherche sur la fenêtre
             d'entraînement seule, pour ne pas contaminer le backtest. Un gain ici n'est
             donc pas une erreur du modèle.`
          : `Dégradation de ${Math.abs(dR2).toFixed(3).replace(".", ",")} de R² par rapport
             au décalage retenu (${sens.retained_lag} mois) : la grille avait raison.`}
    </div>
  </div>
  <div>
    ${withCsvExport(Plot.plot({
      height: 240, marginLeft: 58, marginBottom: 34,
      x: {label: "Décalage (mois)", tickFormat: "d"},
      y: {label: "R² du modèle", grid: true},
      marks: [
        Plot.lineY(sens.curve, {x: "lag", y: "r2", stroke: series.blue, strokeWidth: 2}),
        Plot.dot(sens.curve.filter((p) => p.lag === sens.retained_lag),
                 {x: "lag", y: "r2", fill: series.brick, r: 5}),
        Plot.dot(sens.curve.filter((p) => p.lag === lagN),
                 {x: "lag", y: "r2", stroke: series.brick, r: 8, strokeWidth: 2})
      ]
    }), sens.curve, "previsions-sensibilite-decalage-" + predictor)}
    <div class="hm-caption">Point plein = décalage retenu · cercle = votre choix.</div>
  </div>
</div>`);
```

```js
// Superposition prédicteur décalé / transactions. Les deux séries n'ont ni la même unité
// ni le même ordre de grandeur (900 000 ventes contre un taux de 3 %) : elles sont donc
// centrées-réduites, comme la vue « intentions » de la page Environnement. On compare des
// FORMES — c'est bien ce que le décalage cherche à aligner.
function zscore(rows) {
  const vals = rows.map((r) => r.value).filter((v) => v != null);
  const mu = vals.reduce((a, b) => a + b, 0) / vals.length;
  const sd = Math.sqrt(vals.reduce((a, b) => a + (b - mu) ** 2, 0) / vals.length);
  return rows.map((r) => ({...r, value: sd > 0 ? (r.value - mu) / sd : 0}));
}
```

```js
if (sens) display(multiLine({
  rows: [
    ...zscore(sens.transactions_series).map((d) => ({...d, series: "Transactions (cumul 12 m)"})),
    ...zscore(sens.predictor_series).map((d) => {
      const t = new Date(d.date + "T00:00:00Z");
      t.setUTCMonth(t.getUTCMonth() + lagN);
      return {date: t.toISOString().slice(0, 10), value: d.value,
              series: `${predictorLabels[predictor]} décalé +${lagN} m`};
    })
  ],
  meta: [{name: "Transactions (cumul 12 m)", color: series.brick},
         {name: `${predictorLabels[predictor]} décalé +${lagN} m`, color: series.blue, dash: true}],
  yLabel: "Écarts-types (séries centrées-réduites)", height: 320,
  yPct: true, lastLabels: false, valueFmt: (v) => nf1.format(v) + " σ", width,
  filename: "previsions-alignement-" + predictor
}));
```

## 2 bis. Projection à horizon (décalages déjà observés)

```js
if (P) display(!P.available
  ? html`<div class="hm-caption">Les décalages estimés ne permettent pas de projection
         au-delà du dernier point.</div>`
  : cardGrid([
      {label: "Horizon de projection", value: `${P.horizon_months} mois`,
       subs: [`dont ${P.assured_months} sans hypothèse`]},
      {label: "Ventes 12 m projetées (fin)", value: nf0.format(P.end_value),
       delta: (P.end_change_pct >= 0 ? "+" : "−") + nf1.format(Math.abs(P.end_change_pct)) + " %"}
    ], kpiCard));
```

```js
if (P && P.available) display(withCsvExport(Plot.plot({
  width, height: 360, marginLeft: 66, marginBottom: 34,
  x: {type: "utc", label: null},
  y: {label: "Ventes sur 12 mois", grid: true, tickFormat: (v) => nf0.format(v)},
  marks: [
    Plot.areaY(P.series, {x: (d) => new Date(d.date), y1: "lo", y2: "hi",
                          fill: series.brick, fillOpacity: 0.12}),
    Plot.lineY(T.series, {x: (d) => new Date(d.date), y: "observed",
                          stroke: series.brick, strokeWidth: 2.2}),
    Plot.lineY(P.series, {x: (d) => new Date(d.date), y: "predicted",
                          stroke: series.blue, strokeWidth: 2.2, strokeDasharray: "4 3"}),
    // Frontière entre la partie sans hypothèse et le report des indicateurs manquants.
    Plot.ruleX(P.series.filter((d) => d.assured).slice(-1),
               {x: (d) => new Date(d.date), stroke: ui.subtle, strokeDasharray: "3 3"})
  ]
}), P.series, "previsions-projection"));
```

<div class="hm-caption">
Jusqu'au repère, la projection n'utilise que des valeurs d'indicateurs déjà publiées
(décalées de leurs délais estimés) — sans hypothèse. Au-delà, chaque indicateur manquant
est maintenu à sa dernière valeur connue. Bande = ±1,28·RMSE hors échantillon.
</div>

## 3. Panneau de scénarios : macro → marché

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
const dTaux = base ? view(Inputs.range([-2.5, 2.5], {
  label: "Taux de marché (écart, en points)", step: 0.1, value: 0,
})) : null;
const chom = base ? view(Inputs.range([6.5, 11],
  {label: "Taux de chômage (%)", step: 0.1, value: r1(base.unemployment)})) : null;
const intentZ = base ? view(Inputs.range([-2.5, 2.5],
  {label: "Intentions d'achat (écarts-types)", step: 0.1, value: r1(base.intentions_z)})) : null;
```

```js
const oat = base ? base.oat + dTaux : null;
const euribor = base ? base.euribor + dTaux : null;
```

```js
if (base) display(html`<div class="hm-caption">Le curseur déplace l'<abbr title="Obligation d'État française à 10 ans, référence du coût du crédit à long terme">OAT</abbr>
  10 ans et l'<abbr title="Taux auquel les banques de la zone euro se prêtent entre elles à court terme">Euribor</abbr>
  3 mois du même écart : ils sont trop liés dans l'histoire (+0,83) pour que le modèle
  sache les distinguer, et les afficher séparément donnait un levier sans effet.
  Position actuelle : OAT ${nf1.format(oat)} %, Euribor ${nf1.format(euribor)} % —
  soit <b>${nf1.format(R.coefficients.oat + R.coefficients.euribor)} pt</b> de taux de
  crédit par point de taux de marché.</div>`);
```

```js
// Huit multiplications, en JS — computeScenario reproduit forecast.scenario terme à
// terme (voir components/api.js) sur les coefficients exportés. Pas de quoi justifier un
// aller-retour réseau à chaque déplacement de curseur, contrairement au POST que l'API
// exposait pour cette même route.
const sc = base
  ? computeScenario(R.coefficients, T.coefficients, base, {oat, euribor, chom, intentZ})
  : null;
```

```js
if (sc) display(cardGrid([
  {label: "Taux de crédit implicite", value: nf1.format(sc.rate) + " %",
   delta: (sc.rate_change >= 0 ? "+" : "−") + nf1.format(Math.abs(sc.rate_change)) + " pt"},
  {label: "Ventes projetées (12 mois)", value: nf0.format(sc.transactions),
   delta: (sc.transactions_change >= 0 ? "+" : "−") + nf0.format(Math.abs(sc.transactions_change))},
  {label: "Impact relatif",
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

## → Propagation au chiffre d'affaires benchmark

```js
const bench = data.available ? data.revenue_benchmarks : {companies: []};
```

```js
if (sc && bench.companies.length) display(cardGrid(
  bench.companies.map((c) => {
    if (!c.fit) return {label: c.company, value: "—", subs: ["trop peu de points"]};
    const dCa = c.fit.beta_per_transaction * sc.transactions_change;
    return {
      label: c.company,
      value: nf0.format(c.last_revenue_meur + dCa) + " M€",
      delta: (dCa >= 0 ? "+" : "−") + nf0.format(Math.abs(dCa)) + " M€",
      subs: [`R² = ${pct(c.fit.r2)} · décalage ${c.fit.lag_quarters} trimestres`]
    };
  }), kpiCard));
```

<div class="hm-caption">
Élasticité transactions→CA estimée sur les trimestres publiés (indicative — les séries
d'entreprise sont courtes). Hexaom (neuf) et Kingfisher France (rénovation) réagissent aux
transactions avec un décalage. Le choc de transactions propagé est celui du scénario
ci-dessus.
</div>

<div class="hm-caption" style="margin-top:1.4rem">
Pour croiser ces prévisions avec <b>vos</b> ventes, voir la page
<a href="./donnees">⚙️ Données & Sources</a> — le fichier reste dans votre navigateur.
</div>
