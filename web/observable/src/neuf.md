---
title: Marché du neuf
toc: true
---

```js
import {kpiCard, cardGrid, legend, marketChart, multiLine,
        filterYears, sumByType, withCsvExport,
        nf0, nf1, fmtMonthFR, TIP, Plot} from "./components/hm.js";
import {periodFilter} from "./components/period.js";
import {series, ui} from "./components/theme.js";
const neuf = await FileAttachment("./data/neuf.json").json();
```

<!--
  TITRE ET CHAPEAU STATIQUES — rendus au build, pas construits dans le navigateur.
  Tout le reste de la page est monté en JS à partir du JSON : un robot d'indexation, comme
  tout aperçu de partage, n'en voit rien. Ces deux blocs sont donc le SEUL texte de la page
  que lisent Google et LinkedIn. Le titre valait auparavant `${neuf.title}`, c'est-à-dire un titre
  VIDE dans le HTML livré. Ne pas les reconvertir en interpolation.
  Voir CLAUDE.md, « Le chapeau des pages de données ».
-->

# 🏗️ Marché du neuf — de l'autorisation à la vente

Le logement neuf se lit comme un tunnel : un permis de construire autorisé devient une mise
en chantier six à douze mois plus tard, puis un logement livré et mis en vente. Cette page
suit ce parcours d'un bout à l'autre, à l'échelle nationale — les permis et les mises en
chantier publiés par le SDES (<abbr title="Fichier du SDES qui recense les permis de construire et mises en chantier — voir « Le vocabulaire » sur la page À propos">SIT@DEL</abbr>), la répartition entre maisons individuelles et
logements collectifs, puis la commercialisation des logements neufs (<abbr title="Enquête trimestrielle du SDES sur la commercialisation des logements neufs">ECLN</abbr>) : encours à la
vente, délai d'écoulement, réservations et prix au m².

Les permis sont l'indicateur le plus précoce du cycle de la construction : ils bougent avant
les chantiers, qui bougent avant les livraisons. Un retournement du marché du neuf se lit
donc ici avant de se voir ailleurs, et c'est ce qui en fait un signal avancé de l'activité
du bâtiment.


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

${marketChart({rows: filterYears(seriesRowsN, rangeN), meta: neuf.main_series.meta, view: viewN, showMA12: maN.includes("Moyenne mobile 12 mois"), showMA6: maN.includes("Moyenne mobile 6 mois"), active: visN, yLabel: "Milliers de logements", width, filename: "marche-neuf"})}

<div class="hm-meta">${neuf.main_series.source} · dernier point : ${neuf.main_series.last_month} · segmentation : ${segLabelN} · période affichée : ${Math.min(...rangeN)}–${Math.max(...rangeN)}</div>

## 🏠 Dynamique Individuel vs Collectif

<div class="hm-caption">Le logement individuel — surtout l'individuel pur — porte bien plus de contenu second œuvre (fermetures, menuiseries, sécurité, domotique) qu'un logement collectif : c'est le driver de volume le plus direct.
Lire chaque segment sur ses deux lignes, parce qu'elles peuvent s'inverser : une croissance forte sur douze mois
décrit parfois un rebond depuis un plancher historique, et le segment le moins dégradé peut être celui dont le rythme
se retourne le premier. C'est l'écart entre ces deux lectures qui décide d'un arbitrage de lignes de produits, pas le
taux annuel seul.</div>

```js
const ivMetrics = view(Inputs.checkbox(
  new Map([["Mises en Chantier", "MisesEnChantier"], ["Permis de Construire", "Permis"]]),
  {value: ["MisesEnChantier"], label: "Indicateur"}));
```

```js
// Légende cliquable, dans SA PROPRE cellule : elle ne dépend pas de `ivMetrics`, donc
// cocher/décocher un indicateur ne recrée pas ce Mutable et ne réinitialise donc pas ce
// que l'utilisateur a déjà masqué. On retient les séries explicitement MASQUÉES plutôt
// que les visibles, comme la courbe d'ouverture de page.
const ivHidden = Mutable(new Set());
function toggleIv(name) { const s = new Set(ivHidden.value); s.has(name) ? s.delete(name) : s.add(name); ivHidden.value = s; }
```

```js
const IV_METRIC_LABELS = {MisesEnChantier: "Mises en Chantier", Permis: "Permis de Construire"};
const ivMulti = ivMetrics.length > 1;
// Une ligne par (groupe, indicateur) : quand les deux indicateurs sont cochés, le nom de
// série est suffixé pour que la légende les distingue, et les Mises en Chantier passent en
// pointillé — la même convention que la courbe d'ouverture de page, plus haut.
const ivLines = ivMetrics.flatMap((metric) => neuf.indiv_collectif[metric].lines.map((d) => ({
  ...d,
  series: ivMulti ? `${d.series} — ${IV_METRIC_LABELS[metric]}` : d.series,
  dash: metric === "MisesEnChantier" ? "dash" : null,
})));
const ivMeta = [...new Map(ivLines.map((d) => [d.series, {name: d.series, color: d.color, dash: d.dash}])).values()];
// `ivHidden` référencé nu (pas `.value`) : cellule EN AVAL de celle qui le définit, donc
// on récupère la valeur courante déballée — même mécanique que `visN`/`visR` ailleurs.
const ivActive = new Set(ivMeta.map((m) => m.name).filter((n) => !ivHidden.has(n)));
function ivSection() {
  return html`<div>
    ${ivMetrics.map((metric) => html`<div>
      ${ivMulti ? html`<div class="hm-panel-title">${IV_METRIC_LABELS[metric]}</div>` : ""}
      ${cardGrid(neuf.indiv_collectif[metric].kpis, (k) => kpiCard({label: k.label, value: k.val12, delta: k.roll12_yoy ? k.roll12_yoy + " sur 12 mois" : null, subs: [`${k.last3_seq} sur 3 mois vs les 3 précédents`, k.niveau]}))}
    </div>`)}
    <div class="hm-panel-title">${ivMulti ? "Mises en Chantier & Permis de Construire" : IV_METRIC_LABELS[ivMetrics[0]]} — maison individuelle pure vs collectif <span style="color:var(--hm-subtle);font-weight:400">(cumul sur 12 mois, en milliers)</span></div>
    ${legend(ivMeta, ivActive, toggleIv)}
    ${multiLine({rows: filterYears(ivLines, rangeN), meta: ivMeta, active: ivActive, yLabel: "Milliers de logements", valueFmt: (v) => nf1.format(v), tipUnit: " k", width, filename: "neuf-individuel-vs-collectif-" + ivMetrics.join("-")})}
  </div>`;
}
```

${ivMetrics.length ? ivSection() : html`<div class="hm-caption">Sélectionnez au moins un indicateur.</div>`}

```js
// ============================ Section ECLN ============================
const e = neuf.ecln;
```

## 🏗️ Commercialisation des logements neufs (ECLN)

<div class="hm-caption">Commercialisation des logements neufs (SDES — ECLN, national, trimestriel CVS-CJO) : encours, mises en vente, délai d'écoulement, prix au m² et réservations par catégorie d'acquéreurs. Le délai d'écoulement — le temps qu'il faudrait pour vendre le stock au rythme actuel — est un signal avancé de la demande de second œuvre : il monte quand le stock ne part plus.</div>

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

## 🔄 Du permis au chantier : ce que les autorisations disent vraiment

<!--
  Cette section publie un RÉSULTAT NÉGATIF autant qu'un indicateur, et c'est délibéré. Le
  plan initial prévoyait ici un modèle de prévision « permis → mises en chantier » pour le
  professionnel du bâtiment, sur l'intuition qu'un permis précède mécaniquement un chantier.
  Mesuré, c'est faux dans cette série : voir le profil de décalage plus bas et CLAUDE.md.
  Ce qui subsiste — le taux de transformation — est descriptif, ne prévoit rien, et n'a
  donc besoin d'aucune validation hors échantillon.
-->

Un logement autorisé n'est pas un logement construit. L'écart entre les deux se mesure, il
bouge beaucoup, et il dit ce que les promoteurs font réellement de leurs autorisations —
une information plus directe, pour qui fournit le chantier, qu'une prévision.

```js
const TR = neuf.transformation ?? null;
```

```js
if (TR) display(cardGrid([
  {label: "Taux de transformation", value: nf1.format(TR.actuel) + " %",
   subs: [`moyenne de long terme : ${nf1.format(TR.moyenne)} %`]},
  {label: "Logements autorisés", value: nf0.format(TR.dernier_permis),
   subs: ["sur les 12 derniers mois"]},
  {label: "Logements mis en chantier", value: nf0.format(TR.dernier_chantier),
   subs: ["sur les 12 derniers mois"]},
], kpiCard));
```

<div class="hm-formula">
  <b>Taux de transformation</b> =
  mises en chantier sur 12 mois ÷ logements autorisés sur 12 mois
</div>

```js
if (TR) display(withCsvExport(Plot.plot({
  width, height: 300, marginLeft: 52, marginBottom: 34,
  x: {type: "utc", label: null},
  y: {label: "Taux de transformation (%)", grid: true, zero: false,
      tickFormat: (v) => nf0.format(v) + " %"},
  marks: [
    Plot.ruleY([TR.moyenne], {stroke: ui.subtle, strokeDasharray: "4 3"}),
    Plot.text([{x: new Date(TR.rows[0].date), y: TR.moyenne}],
              {x: "x", y: "y", text: () => `moyenne ${nf1.format(TR.moyenne)} %`,
               dy: -8, dx: 4, textAnchor: "start", fill: ui.subtle, fontSize: 11}),
    Plot.lineY(TR.rows, {x: (d) => new Date(d.date), y: "taux",
                         stroke: series.violet, strokeWidth: 2.2}),
    Plot.dot([TR.rows[TR.rows.length - 1]], {x: (d) => new Date(d.date), y: "taux",
                                             fill: series.violet, r: 4.5,
                                             stroke: "white", strokeWidth: 2}),
    Plot.crosshairX(TR.rows, {x: (d) => new Date(d.date), y: "taux", color: ui.subtle}),
    Plot.tip(TR.rows, Plot.pointerX({
      x: (d) => new Date(d.date), y: "taux", ...TIP,
      title: (d) => `${fmtMonthFR(new Date(d.date))}\n${nf1.format(d.taux)} % des logements autorisés ouverts en chantier`,
    })),
  ],
}), TR.rows, "neuf-taux-transformation"));
```

```js
if (TR) display(html`<div class="hm-caption">Aujourd'hui
  <b>${nf1.format(TR.actuel)} %</b> des logements autorisés sont effectivement ouverts en
  chantier, contre ${nf1.format(TR.moyenne)} % en moyenne de long terme. Le creux de
  ${nf1.format(TR.min.valeur)} % date de ${fmtMonthFR(new Date(TR.min.date))}, le pic de
  ${nf1.format(TR.max.valeur)} % de ${fmtMonthFR(new Date(TR.max.date))}. Un taux qui
  s'enfonce signale des projets autorisés puis différés — un carnet de commandes qui ne se
  matérialise pas.</div>`);
```

### Pourquoi cette page ne publie pas de prévision du neuf

<div class="hm-caption">
Le plan de ce site prévoyait ici un modèle « permis → mises en chantier », sur une intuition
qui paraît solide : une autorisation précède forcément un chantier, donc elle devrait donner
de l'avance. Mesurée, l'intuition ne tient pas. Publier la mesure vaut mieux que publier le
modèle.
</div>

```js
// La preuve tient dans une seule courbe. Si les permis précédaient les chantiers, le R²
// culminerait à un décalage POSITIF — trois mois, six mois — et redescendrait de part et
// d'autre. Il est maximal à zéro et décroît de façon monotone : les deux séries bougent
// ENSEMBLE, sans avance exploitable.
if (TR && TR.lag_profile.length) display(withCsvExport(Plot.plot({
  width, height: 260, marginLeft: 56, marginBottom: 40, marginTop: 34,
  x: {label: "Décalage appliqué aux permis (mois)", tickFormat: "d", grid: false},
  // Domaine avec marge au-dessus du maximum (k=0) : sans elle, le point le plus haut
  // touche le bord du cadre et son étiquette "maximum à 0 mois" (dy:-14) chevauche le
  // libellé de l'axe Y, rendu par Plot juste au-dessus du cadre au même endroit.
  y: {label: "R² du lien permis → chantiers", grid: true, zero: true, domain: [0, TR.lag_profile[0].r2 * 1.2]},
  marks: [
    Plot.lineY(TR.lag_profile, {x: "lag", y: "r2", stroke: series.brick, strokeWidth: 2.2}),
    Plot.dot(TR.lag_profile.slice(0, 1), {x: "lag", y: "r2", fill: series.brick, r: 5.5}),
    Plot.text(TR.lag_profile.slice(0, 1), {x: "lag", y: "r2", dy: -14, dx: 6,
              text: () => "maximum à 0 mois", fill: series.brick, fontWeight: 600,
              textAnchor: "start"}),
    Plot.tip(TR.lag_profile, Plot.pointerX({
      x: "lag", y: "r2", ...TIP,
      title: (d) => `Permis décalés de ${d.lag} mois\nR² = ${nf1.format(d.r2 * 100)} %`,
    })),
  ],
}), TR.lag_profile, "neuf-profil-decalage"));
```

```js
if (TR) display(html`<details class="hm-howto">
  <summary>Le détail de la mesure, et les limites de cette page</summary>
  <p><b>Ce qui a été testé.</b> Une régression par horizon, mises en chantier sur 12 mois à
  <i>t + h</i> expliquées par les autorisations sur 12 mois et par l'écart cumulé
  autorisations − chantiers, estimée sur la seule fenêtre d'entraînement puis appliquée en
  aveugle sur ${nf0.format(TR.gate.millesimes)} millésimes, de 2010 à aujourd'hui.</p>
  <p><b>Résultat.</b> ${nf1.format(TR.gate.mape)} % d'erreur moyenne contre
  ${nf1.format(TR.gate.naive_mape)} % pour une prévision qui se contente de prolonger le
  dernier niveau connu — soit <b>${nf0.format(Math.abs(TR.gate.skill) * 100)} % d'erreur en
  PLUS</b>, et le sens du marché annoncé juste
  ${nf0.format(TR.gate.direction * 100)} % du temps, c'est-à-dire à pile ou face. Le modèle
  se dégrade à mesure que l'horizon s'allonge. Aucune des quatre plages d'horizon
  (1-3, 4-6, 7-12 et 13-18 mois) ne franchit le seuil d'entrée du site : 5 % d'erreur évitée
  sur des données jamais vues. Mesure du ${TR.gate.mesure_le}.</p>
  <p><b>Pourquoi, probablement.</b> Les deux séries sont corrigées des variations
  saisonnières et remontent par la même voie administrative : le délai de déclaration pèse
  vraisemblablement plus que le délai physique de chantier. Le décalage réel entre
  l'autorisation et la première pelletée existe, mais il est propre à chaque projet, et la
  moyenne nationale mensuelle l'efface.</p>
  <p><b>Limites du taux de transformation lui-même.</b> Il rapporte deux flux mesurés sur
  la même fenêtre de douze mois, alors que les chantiers d'un mois donné proviennent
  d'autorisations réparties sur plusieurs mois antérieurs : le ratio n'est donc pas un taux
  de conversion projet par projet, mais un indicateur de régime. Il peut dépasser 100 %
  quand un stock d'autorisations anciennes se débloque, et une autorisation abandonnée
  n'est jamais retirée de la série. Il se lit en tendance et par rapport à sa moyenne, pas
  comme une probabilité.</p>
  <p><b>Ce que cette page ne fera pas.</b> Publier une prévision du neuf tant qu'un modèle
  n'aura pas battu cette référence naïve hors échantillon. La page
  <a href="/previsions">Prévision &amp; Scénarios</a> couvre le marché de l'ancien, où le
  modèle passe ce test à partir de six mois.</p>
</details>`);
```

<div class="hm-meta">Source : SDES — SIT@DEL2 (CVS-CJO), France entière</div>
