---
title: Prévision & Scénarios
toc: true
---

```js
import {multiLine, cardGrid, kpiCard, withCsvExport, filterYears, nf0, nf1, fmtMonthFR, Plot, TIP} from "./components/hm.js";
import {series, ui, delta} from "./components/theme.js";
import {periodFilter} from "./components/period.js";
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
  CHAPEAU STATIQUE, rendu au build — voir CLAUDE.md, « Le chapeau des pages de données ».
  Cette page-ci est un cas limite : sans instance de l'API, un visiteur ne voit QUE ce
  texte. Raison de plus pour qu'il dise ce que la page fait.
-->

Prévoir des transactions immobilières revient à prévoir une demande, et ce site le fait
avec les méthodes de la planification, en deux étages. Le premier explique le taux du
crédit immobilier (toutes durées confondues) par l'OAT 10 ans ; le second explique les ventes de logements
anciens par ce taux de crédit, les intentions d'achat des ménages et le chômage, chacun
pris avec son propre décalage.

La projection est publiée avec son backtest hors échantillon et sa bande d'incertitude, et
les scénarios permettent d'en manipuler les leviers. Les prévisions déjà publiées, elles,
sont archivées et confrontées au réalisé sur leur propre page.

**Ce que cette page prévoit, et ce qu'elle ne prévoit pas.** La série projetée est celle des
**ventes de logements anciens**, et elle seule. Ni les mises en chantier, ni l'activité de
rénovation ne font l'objet d'une prévision sur ce site, et c'est un choix documenté plutôt
qu'un oubli : le lien entre les permis de construire et les chantiers a été mesuré puis
écarté faute d'avance réelle, et aucune série de volume publiée ne permet aujourd'hui de
modéliser la rénovation. Un lecteur venu pour anticiper une activité de construction doit
donc lire cette projection comme un **indicateur de contexte** — le marché de l'ancien
décrit la santé de la demande de logement en général — et non comme une prévision de son
propre carnet.

<div class="hm-caption">
Modèle chiffré « indicateurs avancés → transactions », calibré sur les séries réelles.
Deux étages : (1) le taux de crédit est modélisé à partir de l'<abbr title="Obligation d'État française à 10 ans, référence du coût du crédit à long terme">OAT</abbr> 10 ans, avec le délai
que les banques mettent à répercuter ; (2) les ventes de logements anciens (cumul 12 mois) sont expliquées par le taux
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
// LE RÉGIME COURANT — la ventilation qui manquait, et la seule qui porte sur AUJOURD'HUI.
//
// La page publie déjà sa performance par horizon et par épisode : deux descriptions du
// passé. Aucune ne dit ce que vaut le chiffre qu'on est en train de lire. Or la
// performance du modèle dépend massivement d'une chose — le taux de crédit bouge-t-il ? —
// et le « 72 % de bon sens » affiché à côté du verdict est la moyenne de deux mondes :
// 97 % quand les taux bougent fort, 55 % quand ils sont calmes.
//
// Affiché en `hm-note` et non en `hm-takeaways` : c'est un avertissement sur le chiffre
// du dessus, pas un second verdict. Le ton suit le régime — inutile d'alarmer quand le
// modèle est dans sa zone de confort.
if (RG && V) {
  const faible = RG.skill_pct !== null && RG.skill_pct < 5;
  const dir = RG.direction_horizon ?? RG.direction;
  display(html`<div class="hm-note">
    <p><strong>Dans quel régime cette prévision est-elle publiée ?</strong>
    Le taux de crédit a bougé de <b>${RG.mouvement_pt.toLocaleString("fr-FR",
      {minimumFractionDigits: 2, maximumFractionDigits: 2})} point</b> sur
    ${RG.fenetre_mois} mois — ${RG.label}, au ${RG.percentile}<sup>e</sup> centile des
    millésimes archivés.</p>
    <p>Le modèle n'a qu'un moteur, le coût du crédit, et sa valeur en dépend
    entièrement. Dans des conditions comparables, sur ${nf0.format(RG.n)} points archivés,
    il a annoncé le bon sens <strong>${nf0.format(dir * 100)} %</strong> du temps et fait
    ${RG.skill_pct >= 0
      ? html`<strong>${nf1.format(RG.skill_pct)} % de mieux</strong>`
      : html`<strong>${nf1.format(Math.abs(RG.skill_pct))} % de moins bien</strong>`}
    qu'une simple prolongation du dernier chiffre — contre
    ${V.reliability ? html`${nf0.format(V.reliability.direction * 100)} %` : "—"} toutes
    conditions confondues.
    ${faible
      ? html`<b>La projection ci-dessus est donc à prendre avec prudence : le régime
             actuel est celui où ce modèle a historiquement le moins d'avantage.</b>`
      : html`Le régime actuel est favorable à ce modèle.`}</p>
    <p class="hm-caption">Régimes définis par terciles de l'amplitude du mouvement de taux
    sur ${RG.fenetre_mois} mois, mesurés sur les millésimes archivés. Le centile est donné
    à côté du libellé parce qu'un régime peut être proche d'une frontière.</p>
  </div>`);
}
```

```js
// COMMENT UTILISER CETTE PRÉVISION — l'assemblage que la page ne faisait pas.
//
// Les deux chiffres qui la déterminent existaient déjà, mais à deux endroits éloignés :
// l'horizon de bascule contre la prévision naïve (archive, section « Prévisions passées »)
// et l'horizon informatif de la trajectoire (carte de la section 2 bis). Croisés, ils
// donnent trois régimes d'usage — et notamment le fait, contre-intuitif pour qui vient
// chercher une prévision, qu'en deçà de la bascule il vaut mieux recopier le dernier
// chiffre connu. Le dire ici coûte quatre lignes et évite un contresens de planification.
if (V && P && P.available && data.crossover_horizon) display(html`<div class="hm-note">
  <p><strong>Comment lire cette prévision, selon l'horizon.</strong> Le modèle n'est pas
  utile partout de la même façon, et les deux bornes ci-dessous sont mesurées, pas
  choisies.</p>
  <table class="hm-table">
    <thead><tr><th>Horizon</th><th>Ce qu'il faut retenir</th><th>Pourquoi</th></tr></thead>
    <tbody>
      <tr><td><b>Moins de ${data.crossover_horizon} mois</b></td>
        <td>s'en tenir au dernier chiffre connu
          (${nf0.format(P.last_observed)} ventes sur douze mois)</td>
        <td>sur l'archive, le modèle fait <i>moins bien</i> que cette simple prolongation
          jusqu'à ${data.crossover_horizon} mois</td></tr>
      <tr><td><b>${data.crossover_horizon} à ${P.informative_months} mois</b></td>
        <td>la zone où le modèle apporte quelque chose</td>
        <td>il passe devant la prévision naïve, et sa trajectoire est encore pilotée par
          des indicateurs déjà publiés</td></tr>
      <tr><td><b>Au-delà de ${P.informative_months} mois</b></td>
        <td>lire un <i>niveau d'atterrissage</i> (${nf0.format(P.end_value)}), pas un
          chemin mois par mois</td>
        <td>tous les indicateurs sont alors maintenus à leur dernière valeur : la courbe
          répète ce niveau au lieu de le faire évoluer</td></tr>
    </tbody>
  </table>
  ${R && R.projected && R.projected.length ? html`<p class="hm-caption">À côté de ça, le
    <b>taux de crédit des ${R.projected.length} prochains mois est déjà déterminé</b> par
    des taux de marché publiés — c'est la seule projection du site qui ne repose sur
    aucune hypothèse (section 1).</p>` : ""}
</div>`);
```

```js
if (data.available) display(html`<hr>`);
```

## 1. Modèle de taux de crédit (OAT 10 ans)

Le crédit immobilier français est à taux fixe, et les banques publient des barèmes qu'elles
lissent : leur réaction aux taux de marché n'est pas immédiate. Le modèle **mesure ce délai**
au lieu de le supposer — et c'est ce qui lui donne son intérêt, puisque les taux de marché
déjà publiés déterminent alors le taux de crédit des mois à venir.

```js
// LÉGENDE STATIQUE. Le graphique porte trois courbes dont deux se ressemblent beaucoup, et
// les étiquettes de fin de ligne donnaient la valeur sans jamais dire l'identité : rien
// n'indiquait laquelle était l'observé. Statique et non cliquable, contrairement aux
// légendes de « Marché du neuf » : à trois séries dont une projection, masquer l'une ne
// sert à rien — la comparaison EST le propos de ce graphique.
const legendeTaux = R ? [
  {name: "Taux réellement pratiqué", color: series.brick},
  {name: `Sortie brute du modèle (OAT décalée de ${R.lag} mois)`,
   color: series.blue, dash: true},
  ...(R.projected.length
      ? [{name: "Ce que nous publions : brut recalé sur le dernier taux connu",
          color: series.green, dash: true}]
      : []),
  ...(B2 ? [{name: `Anticipation ${B2.source} (${B2.horizon})`, color: series.violet}] : []),
] : [];
```

```js
if (R) display(html`<div class="hm-legend hm-legend--static">${legendeTaux.map((m) => html`<span class="hm-legend-item">
  <span class="hm-swatch" style=${m.dash
    ? {borderBottom: `2px dashed ${m.color}`, background: "transparent", height: "0", marginBottom: "3px"}
    : {background: m.color}}></span>${m.name}</span>`)}</div>`);
```

```js
const tauxPlot = () => {
  // La courbe BRUTE est tracée d'un seul tenant, ajustement puis mois à venir. Elle
  // s'arrêtait auparavant au dernier mois observé et la projection repartait 0,5 pt plus
  // bas, sans que rien n'explique le saut : deux fragments du MÊME modèle, calculés sur des
  // bases différentes, que personne ne pouvait interpréter. Continue, elle rend l'écart
  // avec la courbe publiée lisible — cet écart EST le biais de niveau qu'on corrige.
  // `publie` est transporté jusqu'ici, sans quoi la vignette de survol ne peut pas montrer
  // la valeur verte : les mois projetés ne portaient que la sortie brute, et le lecteur
  // survolait la courbe publiée sans jamais pouvoir en lire le chiffre.
  const rows = histo(R.series).concat(
    depuis(R.projected).map((d) => ({date: d.date, observed: null,
                                     modelled: d.modelled, publie: d.rate})));
  const proj = depuis(R.projected).map((d) => ({date: d.date, value: d.rate}));
  return withCsvExport(Plot.plot({
    height: 300, marginLeft: 54, marginRight: 78, marginBottom: 34,
    x: {type: "utc", label: null},
    y: {label: "Taux (%)", grid: true, zero: false, tickFormat: (v) => nf1.format(v) + " %"},
    marks: [
      Plot.lineY(rows, {x: (d) => new Date(d.date), y: "modelled", stroke: series.blue,
                        strokeWidth: 2.2, strokeDasharray: "6 4"}),
      Plot.lineY(rows, {x: (d) => new Date(d.date), y: "observed", stroke: series.brick,
                        strokeWidth: 2.4}),
      proj.length ? Plot.lineY(proj, {x: (d) => new Date(d.date), y: "value",
                                      stroke: series.green, strokeWidth: 2.4,
                                      strokeDasharray: "3 3"}) : null,
      proj.length ? Plot.dot(proj.slice(-1), {x: (d) => new Date(d.date), y: "value",
                                              fill: series.green, r: 4.5, stroke: "white",
                                              strokeWidth: 2}) : null,
      proj.length ? Plot.text(proj.slice(-1), {x: (d) => new Date(d.date), y: "value",
                    text: (d) => " " + nf1.format(d.value) + " %", fill: series.green,
                    textAnchor: "start", dx: 6, dy: -10, fontWeight: 700}) : null,
      // LE REPÈRE ANALYSTE, posé à sa date. Un point isolé et non un prolongement de
      // courbe : son horizon (fin 2027) est bien au-delà du dernier mois que nos taux de
      // marché publiés déterminent (janvier 2027), et tracer un trait entre les deux
      // suggérerait une trajectoire que ni eux ni nous ne publions. L'espace vide entre le
      // dernier point vert et ce repère EST l'information — il montre que les deux
      // prévisions ne portent pas sur le même moment.
      B2 && depuis([B2]).length ? Plot.dot([B2], {x: (d) => new Date(d.date), y: "valeur",
                    fill: series.violet, r: 5, stroke: "white", strokeWidth: 2}) : null,
      B2 && depuis([B2]).length ? Plot.text([B2], {x: (d) => new Date(d.date), y: "valeur",
                    text: (d) => nf1.format(d.valeur) + " %", fill: series.violet,
                    dy: -12, fontWeight: 700}) : null,
      // L'étiquette de fin du RÉEL doit viser le dernier mois RÉELLEMENT observé, pas la
      // dernière ligne : depuis que la courbe brute se prolonge, les derniers points ont
      // un `observed` nul et l'étiquette se serait affichée « NaN % » dans le vide.
      Plot.text(histo(R.series).slice(-1), {x: (d) => new Date(d.date), y: "observed",
                text: (d) => " " + nf1.format(d.observed) + " %", fill: series.brick,
                textAnchor: "start", dx: 6, dy: 12, fontWeight: 700}),
      Plot.crosshairX(rows, {x: (d) => new Date(d.date), y: "modelled", color: ui.subtle}),
      Plot.tip(rows, Plot.pointerX({
        x: (d) => new Date(d.date), y: "modelled", ...TIP,
        title: (d) => [
          fmtMonthFR(new Date(d.date)),
          d.observed == null
            ? "Taux pratiqué : pas encore publié"
            : `Taux pratiqué : ${nf1.format(d.observed)} %`,
          `Modèle brut (marché décalé de ${R.lag} mois) : ${nf1.format(d.modelled)} %`,
          // La valeur recalée n'existe que sur les mois projetés : sur l'historique c'est
          // le taux pratiqué lui-même qui sert d'ancrage, l'afficher n'aurait pas de sens.
          // L'écart corrigé est donc rappelé là, et là seulement, où il se lit.
          ...(d.publie == null ? [] : [
            `Ce que nous publions : ${nf1.format(d.publie)} %`,
            `Écart corrigé : ${nf1.format(d.modelled - d.publie)} pt`,
          ]),
        ].join("\n"),
      })),
      // Le repère analyste a SA propre vignette : il n'appartient à aucune des séries
      // mensuelles, donc le pointeur en X du graphique ne l'atteindrait jamais.
      B2 && depuis([B2]).length ? Plot.tip([B2], Plot.pointer({
        x: (d) => new Date(d.date), y: "valeur", ...TIP,
        title: (d) => [
          d.source,
          `Anticipation : ${nf1.format(d.valeur)} % à l'horizon ${d.horizon}`,
          `Relevé le ${d.releve_le}`,
          "Horizon plus lointain que le nôtre :",
          "les deux se complètent, elles ne portent pas sur le même mois.",
        ].join("\n"),
      })) : null,
    ].filter(Boolean),
  }), rows, "previsions-modele-taux");
};
```

```js
if (R) display(html`<div class="hm-panels">
  <div>${tauxPlot()}</div>
  <div>
    ${cardGrid([
      // Cette carte est le RÉSULTAT de l'étage 1, pas un sous-produit : c'est le seul
      // chiffre prospectif du site qui ne repose sur aucune hypothèse. Les taux de marché
      // déjà parus déterminent le barème des banques `R.lag` mois plus tard, donc autant
      // de mois de taux de crédit sont écrits d'avance. À comparer aux ZÉRO mois assurés
      // de la projection de transactions. Elle passait après les deux cartes techniques.
      ...(R.projected && R.projected.length ? [{
        label: "Taux de crédit déjà déterminé",
        value: `${R.projected.length} mois`,
        subs: ["par des taux de marché déjà publiés — aucune hypothèse",
               `jusqu'à ${fmtMonthFR(new Date(R.projected[R.projected.length - 1].date))}`]
      }] : []),
      {label: "Délai de répercussion", value: `${R.lag} mois`,
       subs: ["entre le marché et le barème des banques"]},
      {label: "Part du mouvement répercutée",
       value: nf0.format(R.coefficients.marche * 100) + " %",
       subs: ["par point de taux de marché"]},
    ], kpiCard)}
    <div class="hm-caption" style="margin-top:0.6rem">
      <b>Un point de taux de marché en plus ⇒ environ
      +${nf1.format(R.coefficients.marche)} pt de taux de crédit, atteint en
      ${R.lag} mois.</b><br>
      <span style="color:${ui.subtle}">Sources : Banque de France / BCE.</span>
    </div>
  </div>
</div>`);
```

```js
// COMMENT LIRE CE GRAPHIQUE. Il portait trois courbes sans dire ce que chacune est, et
// deux d'entre elles sortaient du MÊME modèle sur des bases différentes : la reconstitution
// brute s'arrêtait au dernier mois observé, la projection repartait 0,5 pt plus bas. Le
// lecteur voyait un saut inexpliqué. Les deux formant maintenant une lecture cohérente, il
// reste à dire laquelle sert à quoi — sans quoi l'écart entre elles reste énigmatique.
if (R && R.projected.length) display(html`<div class="hm-note">
  <p><strong>Comment lire ces trois courbes.</strong></p>
  <ul>
    <li><b style="color:${series.brick}">Le taux réellement pratiqué</b> — ce que
    l'Observatoire Crédit Logement a mesuré. Il s'arrête à
    ${fmtMonthFR(new Date(R.series[R.series.length - 1].date))}, dernier mois publié.</li>
    <li><b style="color:${series.blue}">La sortie brute du modèle</b> — ce que la formule
    donne à partir des taux de marché d'il y a ${R.lag} mois. Elle continue au-delà du
    réel, puisque ces taux de marché-là sont déjà connus. Elle est plus nerveuse que le
    réel : les marchés bougent chaque jour, les barèmes bancaires par paliers.</li>
    <li><b style="color:${series.green}">Ce que nous publions</b> — la même sortie brute,
    recalée sur le dernier taux réellement pratiqué.</li>
  </ul>
  <p>L'écart entre la courbe bleue et la verte, aujourd'hui
  <b>${nf1.format(R.projected[0].modelled - R.projected[0].rate)} point</b>, n'est pas une
  erreur : c'est la part du mouvement des marchés que les banques ne répercutent pas. Le
  modèle sur-prédit systématiquement le niveau, donc seules ses <i>variations</i> sont
  fiables — et c'est le recalage qui les transforme en un taux publiable.</p>
</div>`);
```

```js
// LA FORMULE, EN CLAIR. Elle avait disparu en réécrivant la section : les cartes donnaient
// le délai et la sensibilité totale, mais plus l'équation ni les deux coefficients. Or
// c'est elle qui rend le modèle vérifiable — un lecteur doit pouvoir refaire le calcul.
// Même dispositif que le taux de transformation sur « Marché du neuf » (.hm-formula), pour
// que les deux pages présentent leurs calculs de la même façon.
//
// Le décalage est écrit DANS l'équation, sur chaque terme, et non relégué en légende :
// c'est le paramètre qui a le plus changé le modèle, et le lire hors de la formule
// laisserait croire à une relation contemporaine.
// Un seul format pour les coefficients : hm.js n'expose que nf0 et nf1, et un coefficient
// de 0,669 arrondi a une decimale deviendrait 0,7 -- l'equation ne serait plus verifiable.
const nfCoef = new Intl.NumberFormat("fr-FR", {minimumFractionDigits: 2, maximumFractionDigits: 3});

if (R) display(html`<div class="hm-formula">
  <b>Taux de crédit du mois <i>t</i></b> (toutes durées) =
  ${nfCoef.format(R.coefficients.intercept)}
  + ${nfCoef.format(R.coefficients.oat)} × OAT(<i>t</i> − ${R.lag} mois)
  <div class="hm-caption" style="margin-top:0.5rem">
    Un seul coefficient, et il se lit tel quel : un point d'OAT en plus finit par ajouter
    <b>${nf1.format(R.coefficients.oat)} point</b> au taux de crédit, au bout de
    ${R.lag} mois. L'Euribor 3 mois figurait ici jusqu'au 25 août 2026 ; mesuré, il
    n'apportait rien à l'ajustement et dégradait la prévision de 19 % sur des données
    jamais vues. Le crédit immobilier français est à taux fixe, adossé à du financement
    long : c'est l'OAT qui le tarife.
  </div>
</div>`);
```

```js
// Ce que le délai rend possible, et qui n'existait pas avant : des mois de taux de crédit
// déterminés SANS aucune hypothèse. À rapprocher de la projection des transactions, dont
// la fenêtre « sans hypothèse » vaut zéro mois sur dix-huit.
if (R && R.projected.length) display(html`<div class="hm-note">
  <p><strong>${R.projected.length} mois de taux de crédit sont déjà joués.</strong> Puisque
  les barèmes réagissent avec ${R.lag} mois de retard, les taux de marché déjà publiés
  déterminent le taux de crédit jusqu'en
  ${fmtMonthFR(new Date(R.projected[R.projected.length - 1].date))} :
  <strong>${nf1.format(R.projected[R.projected.length - 1].rate)} %</strong>, contre
  ${nf1.format(R.series[R.series.length - 1].observed)} % au dernier mois observé. Aucune
  hypothèse de marché n'entre dans ce chiffre — seulement des taux déjà publiés et le délai
  mesuré.</p>
  ${B2 ? html`<p class="hm-caption">Pour situer : ${B2.source} anticipe
  <b>${nf1.format(B2.valeur)} %</b> à l'horizon ${B2.horizon}. ${B2.note}
  (Relevé le ${B2.releve_le}.)</p>` : ""}
</div>`);
```

<details class="hm-howto">
  <summary>Pourquoi un délai, et ce qu'il ne dit pas</summary>

```js
if (R) display(html`<p>Sans délai, le modèle expliquait <b>83,8 %</b> de la variance du taux
  de crédit ; avec, <b>${pct(R.r2)}</b>. L'écart ne vient pas d'un paramètre de plus ajusté
  au passé : testé à l'aveugle — entraîné jusqu'en 2019, jugé sur le choc de taux de 2022
  qu'il n'avait pas vu — le délai réduit l'erreur de <b>42 %</b>. Et il est stable :
  recherché à chaque millésime annuel depuis 2012, il reste entre 5 et 7 mois sans jamais
  s'effondrer à zéro.</p>
  <p>Il change aussi la lecture de l'écart 2023-2025, quand le taux de crédit est resté sous
  ce que l'OAT laissait attendre. On l'attribuait entièrement à des banques retenant leurs
  barèmes ; une bonne part n'était que ce délai de répercussion. L'écart résiduel passe de
  0,77 à 0,59 point — le comportement des banques en explique donc le reste, pas le tout.</p>
  <p><b>Trois limites.</b> Le délai est une <i>moyenne</i> : la transmission a été plus
  rapide lors de la remontée de 2022 que pendant les années de taux bas. Le modèle
  sur-prédit le niveau, parce que les banques ne répercutent jamais la totalité d'un
  mouvement — c'est pourquoi tout ce qui en découle, projection comme scénarios, est ancré
  sur le dernier taux réellement observé et n'en utilise que les <i>variations</i>. Enfin ce
  modèle n'améliore <b>pas</b> la prévision de transactions : celle-ci utilise le taux de
  crédit observé, jamais le taux reconstitué.</p>`);
```

</details>

## 2. Modèle des transactions — et sa mise à l'épreuve

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
    ...histo(T.series).map((d) => ({date: d.date, value: d.observed, series: "Observé (IGEDD)"})),
    ...histo(T.backtest.series).map((d) => ({date: d.date, value: d.predicted,
                                             series: "Prévision hors échantillon"}))
  ],
  meta: [{name: "Observé (IGEDD)", color: series.brick},
         {name: "Prévision hors échantillon", color: series.blue, dash: true}],
  yLabel: "Ventes sur 12 mois", valueFmt: (v) => nf0.format(v), width,
  filename: "previsions-backtest-transactions"
}));
```

```js
// La légende disait « c'est LA PREUVE que ces indicateurs avancés prévoient réellement ».
// Deux problèmes : c'est une surinterprétation, et elle porte sur la fenêtre la PLUS
// FAVORABLE au modèle — le test commence au découpage, donc couvre le choc de taux, soit
// l'épisode qu'un modèle piloté par les taux réussit le mieux. L'archive, construite pour
// éviter ce biais, mesure le contraire aux horizons courts. La fenêtre est donc nommée, et
// les chiffres de l'archive viennent immédiatement après relativiser.
if (T) display(html`<div class="hm-caption">
  Entraîné uniquement sur les données antérieures au découpage, le modèle retrouve le
  mouvement des années suivantes sans les avoir vues. À lire en sachant ce que cette courbe
  ne montre pas : la fenêtre de test commence en
  ${fmtMonthFR(new Date(T.backtest.split))} et couvre donc surtout le choc de taux,
  c'est-à-dire l'épisode qu'un modèle piloté par les taux réussit le mieux. Les cartes
  ci-dessus donnent la mesure honnête — celle de l'archive, sur huit épisodes de marché.
</div>`);
```

## 🔬 Vérifier les décalages retenus

<div class="hm-caption">
Déplacez le décalage d'un prédicteur : le modèle est réestimé et son R² bouge. C'est ce
qui rend la recherche en grille <i>auditable</i> plutôt qu'affirmée. La courbe entière
arrive en une requête, donc le curseur ne provoque aucun aller-retour réseau.
</div>

```js
const predictorLabels = {rate: "Taux de crédit (toutes durées)", intentions: "Intentions d'achat",
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
    ...histo(zscore(sens.transactions_series)).map((d) => ({...d, series: "Transactions (cumul 12 m)"})),
    // Rogné APRÈS le décalage : filtrer avant ferait glisser la fenêtre affichée du
    // nombre de mois du décalage, et les deux courbes ne couvriraient plus la même période.
    ...histo(zscore(sens.predictor_series).map((d) => {
      const t = new Date(d.date + "T00:00:00Z");
      t.setUTCMonth(t.getUTCMonth() + lagN);
      return {date: t.toISOString().slice(0, 10), value: d.value,
              series: `${predictorLabels[predictor]} décalé +${lagN} m`};
    }))
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
       subs: [`dont ${P.informative_months} pilotés par des indicateurs déjà publiés`,
              `au-delà, la courbe répète sa dernière valeur`]},
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

```js
// La légende disait deux choses fausses, corrigées ensemble le 2026-08-27 :
//
// 1. « Jusqu'au repère [...] sans hypothèse » — le repère n'existe pas. Il est tracé sur
//    le dernier point `assured`, or aucun point ne l'est : le chômage entre sans décalage
//    (kc = 0), donc il manque toujours au moins un prédicteur. La carte affiche d'ailleurs
//    « dont 0 sans hypothèse » juste au-dessus. La phrase envoyait chercher une frontière
//    introuvable.
// 2. « Bande = ±1,28·RMSE » — c'est la bande CONSTANTE d'avant, remplacée depuis par une
//    bande calibrée par horizon sur les quantiles 10/90 de l'erreur signée de l'archive.
//    Elle est donc asymétrique, et le « ± » annonçait une symétrie qu'elle n'a pas.
//
// S'y ajoute l'horizon INFORMATIF (`informative_months`), qui manquait : la trajectoire
// cesse de bouger dès que tous les prédicteurs sont reportés à plat.
if (P && P.available) display(html`<div class="hm-caption">
  La projection est pilotée par des valeurs d'indicateurs déjà publiées, décalées de leurs
  délais estimés, tant qu'il en reste : au-delà du
  <strong>${P.informative_months}<sup>e</sup> mois</strong> tous les indicateurs sont
  maintenus à leur dernière valeur connue et la courbe répète sa dernière valeur — les
  ${P.horizon_months - P.informative_months} derniers mois n'ajoutent donc pas d'information,
  seulement de l'incertitude. Aucun mois n'est entièrement « sans hypothèse » : le chômage
  entre dans le modèle sans décalage, il manque donc toujours au dernier mois.
  La bande n'est pas symétrique — elle vient des quantiles 10 % / 90 % des erreurs
  réellement commises par l'archive, horizon par horizon, et le modèle surestime davantage
  qu'il ne sous-estime.
</div>`);
```

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
  {label: "Taux de crédit implicite (toutes durées)", value: nf1.format(sc.rate) + " %",
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

## 🧪 Ce qu'on a essayé, et qui ne marche pas

Un site qui ne montre que ce qui a marché laisse croire que tout ce qu'on essaie marche.
Les trois idées ci-dessous paraissaient bonnes — deux figuraient au plan de ce site, et la
troisième a été affirmée pendant des semaines avant d'être vérifiée. Toutes les trois ont
été mesurées, puis écartées. Les publier est le pendant naturel de la page des prévisions
passées : là on montre où le modèle se trompe, ici ce qu'on a renoncé à lui ajouter.

Le seuil pour qu'un indicateur entre dans le modèle est le même pour tous : **éviter au
moins 5 % d'erreur sur des données qu'il n'a pas vues**, et l'éviter sur au moins **trois
des quatre plages d'horizon — 1 à 3 mois, 4 à 6, 7 à 12, et 13 à 18**. Jamais sur sa
capacité à coller au passé : c'est exactement ce qui fait entrer des indicateurs inutiles.

Pourquoi quatre plages plutôt qu'une moyenne ? Parce que l'erreur du modèle n'a rien à voir
d'une plage à l'autre, comme le montre le tableau ci-dessous. Une moyenne unique laisserait
passer un indicateur qui n'améliore qu'une plage étroite, ce qui n'est pas un progrès du
modèle mais une coïncidence localisée. C'est précisément le cas de la première idée
ci-dessous : la seule plage qu'elle franchit est celle où le modèle est de toute façon
battu par une simple prolongation du dernier chiffre connu.

```js
// Ces chiffres étaient ÉCRITS EN DUR dans le paragraphe ci-dessus (« il perd en deçà de six
// mois et lui prend 40 % d'erreur au-delà d'un an ») : exacts au jour où ils ont été tapés,
// et régénérés par rien. Ils viennent maintenant de l'archive, comme le verdict.
if (data.horizon_blocks && data.horizon_blocks.length) display(html`<table class="hm-table">
  <thead><tr><th>Plage d'horizon</th><th>Erreur du modèle</th>
    <th>Erreur d'une prévision naïve</th><th>Erreur évitée</th></tr></thead>
  <tbody>${data.horizon_blocks.map((b) => html`<tr>
    <td>${b.bloc} mois</td>
    <td>${nf1.format(b.mape)} %</td>
    <td>${nf1.format(b.naive_mape)} %</td>
    <td style=${{color: b.skill_pct >= 0 ? delta.positive : delta.negative, fontWeight: 600}}>
      ${b.skill_pct >= 0 ? "+" : "−"}${nf1.format(Math.abs(b.skill_pct))} %</td>
  </tr>`)}</tbody>
</table>`);
```

```js
// Ces trois entrées sont des CONSTANTES DATÉES côté export (voir REFUTATIONS dans
// web_export.py), pas des métriques recalculées : chaque mesure a coûté un backtest de
// plusieurs centaines de millésimes, et ce sont des résultats sur la MÉTHODE, qui ne
// bougent pas d'une semaine à l'autre.
const REF = data.refutations ?? [];
```

```js
if (REF.length) display(html`<div class="hm-refutations">
  ${REF.map((r) => html`<article class="hm-refutation">
    <h3>${r.titre}</h3>
    <p class="hm-refutation__idee"><b>L'idée.</b> ${r.idee}</p>
    <p class="hm-refutation__mesure">${r.mesure}</p>
    <p class="hm-refutation__lecon"><b>Ce qu'on en retient.</b> ${r.lecon}</p>
    ${r.page ? html`<p class="hm-caption"><a href=${r.page.href}>${r.page.libelle}</a></p>` : ""}
    <p class="hm-caption">Mesuré le ${r.mesure_le}.</p>
  </article>`)}
</div>`);
```

<div class="hm-caption">
Aucune de ces trois idées n'est absurde, et deux d'entre elles sont utilisées ailleurs dans
la profession. Elles ne résistent simplement pas à l'épreuve qui compte : faire mieux, sur
des données jamais vues, qu'une prévision qui se contente de prolonger le dernier chiffre
connu.
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
