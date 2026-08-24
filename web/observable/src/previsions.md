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
const V = data.available ? data.verdict : null;
const B = data.available ? data.benchmark : null;
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
// LE VERDICT, en tête de page. Jusqu'ici cette page publiait les entrailles du modèle —
// un R², une MAPE, trois coefficients OLS, un z-score d'intentions d'achat — et nulle
// part sa conclusion. Un visiteur repartait sans la phrase qu'il était venu chercher.
//
// Elle est GÉNÉRÉE (web_export._verdict), jamais écrite à la main : elle porte des
// chiffres, donc elle ne peut pas vivre dans le chapeau statique, que rien ne régénère.
// La fiabilité affichée à côté n'est pas le R² mais la part de fois où le SENS annoncé à
// cet horizon s'est avéré le bon, mesurée sur 210 millésimes.
if (V) display(html`<div class="hm-takeaways">
  <strong>Ce que dit le modèle aujourd'hui</strong>
  <ul>
    <li>${V.sentence} La projection centrale est de
      <strong>${nf0.format(V.predicted)}</strong> ventes sur douze mois
      (fourchette ${nf0.format(V.lo)} – ${nf0.format(V.hi)}).</li>
    ${V.reliability ? html`<li>À ${V.reliability.horizon} mois, le modèle a annoncé le
      <strong>bon sens ${nf0.format(V.reliability.direction * 100)} %</strong> du temps sur
      les ${nf0.format(V.reliability.n)} mois déjà jugés, avec une erreur moyenne de
      ${nf1.format(V.reliability.mape)} % contre ${nf1.format(V.reliability.naive_mape)} %
      pour une prévision naïve.</li>` : ""}
    <li>Le détail de ces comptes, épisode par épisode, est sur
      <a href="/previsions-passees">Prévisions passées</a> — y compris les périodes où le
      modèle s'est trompé.</li>
  </ul>
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
// Le R² a QUITTÉ les cartes de tête, et ce n'est pas un détail de mise en page. Deux
// séries fortement tendancielles régressées en niveau produisent mécaniquement un R²
// élevé : celui-ci vaut 91 % avec une autocorrélation des résidus de 0,88 (Durbin-Watson
// 0,24). Il ne prouve rien, et l'afficher en premier invitait le lecteur à admirer le
// chiffre le moins informatif de la page. Il est descendu dans le repli technique, avec
// l'explication qui va avec.
//
// À la place : les deux mesures issues de l'archive, c'est-à-dire de prévisions
// réellement confrontées au réel sur 210 millésimes et huit épisodes de marché.
if (V && V.reliability) display(cardGrid([
  {label: `Sens du marché annoncé juste (${V.reliability.horizon} mois)`,
   value: nf0.format(V.reliability.direction * 100) + " %",
   subs: [`sur ${nf0.format(V.reliability.n)} mois déjà échus`]},
  {label: `Erreur moyenne à ${V.reliability.horizon} mois`,
   value: nf1.format(V.reliability.mape) + " %",
   subs: [`une prévision naïve se trompe de ${nf1.format(V.reliability.naive_mape)} %`]},
  {label: "Décalages (taux / intentions / chômage)",
   value: `${T.lags.kr} / ${T.lags.ki} / ${T.lags.kc} mois`}
], kpiCard));
else if (T) display(cardGrid([
  {label: "Erreur hors échantillon (MAPE)", value: nf1.format(T.backtest.mape) + " %"},
  {label: "Décalages (taux / intentions / chômage)",
   value: `${T.lags.kr} / ${T.lags.ki} / ${T.lags.kc} mois`}
], kpiCard));
```

<details class="hm-howto">
  <summary>Pourquoi le R² n'est pas en tête de page</summary>

```js
if (T) display(html`<p>Le R² de ce modèle vaut <b>${pct(T.r2)}</b>, et ce chiffre n'est
  pas une preuve. Les deux séries qu'il relie sont fortement tendancielles, et une
  régression de niveau entre deux tendances produit mécaniquement un R² élevé —
  l'autocorrélation des résidus au premier retard vaut 0,88, la statistique de
  Durbin-Watson 0,24 quand une régression saine donne 2. Les résidus ne sont pas du bruit,
  ce sont des vagues.</p>
  <p>La vraie mise à l'épreuve est ailleurs, et elle est publiée : chaque prévision est
  rejouée sur les données du moment, puis confrontée à ce qui s'est passé. C'est ce que
  mesurent les deux cartes ci-dessus, et c'est le sujet entier de la page
  <a href="/previsions-passees">Prévisions passées</a>.</p>`);
```

</details>

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
// Les trois entrées sont gardées dans des CONSTANTES avant d'être passées à `view()`.
// C'est ce qui permet aux boutons de scénario plus bas de leur écrire une valeur : dans
// Observable Framework, `viewof x` n'existe pas — c'est de la syntaxe notebook, et une
// cellule qui l'emploie est retirée du build SANS ERREUR. Garder la référence à l'élément
// est le seul moyen documenté d'y accéder depuis une autre cellule.
const dTauxInput = base ? Inputs.range([-2.5, 2.5], {
  label: "Taux de marché (écart, en points)", step: 0.1, value: 0,
}) : null;
const chomInput = base ? Inputs.range([6.5, 11],
  {label: "Taux de chômage (%)", step: 0.1, value: r1(base.unemployment)}) : null;
const intentZInput = base ? Inputs.range([-2.5, 2.5],
  {label: "Intentions d'achat (écarts-types)", step: 0.1, value: r1(base.intentions_z)}) : null;

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

<div class="hm-shortcuts" style="margin-top:1.6rem">
  <span class="lead">Et chez vous :</span>
  <a class="hm-shortcut" href="/#et-chez-vous">📍 Le prix au m² dans votre département</a>
  <a class="hm-shortcut" href="/previsions-passees">🎯 Nos prévisions passées, face au réel</a>
  <a class="hm-shortcut" href="/donnees">⚙️ Croiser avec vos propres ventes</a>
</div>

<div class="hm-caption" style="margin-top:1rem">
Cette page raisonne au niveau NATIONAL, et c'est délibéré : les taux, le chômage et les
intentions d'achat sont des grandeurs nationales. Un modèle « local » publierait cent une
fois la même courbe sous cent un titres. Pour le marché de votre département, les pages
départementales donnent les prix et les volumes réellement observés.
Pour croiser ces prévisions avec <b>vos</b> ventes, voir la page
<a href="./donnees">⚙️ Données & Sources</a> — le fichier reste dans votre navigateur.
</div>
