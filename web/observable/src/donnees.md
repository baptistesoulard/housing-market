---
title: Confronter vos ventes
toc: true
---

```js
import {multiLine, cardGrid, kpiCard, nf0, nf1, csvParse} from "./components/hm.js";
import {series, ui} from "./components/theme.js";
import {bestLagFit, shiftMonths} from "./components/api.js";
```

```js
// Les deux drivers amont (transactions IGEDD, permis SIT@DEL par type) viennent des
// mêmes JSON que les pages Logement ancien / Logement neuf — pas d'un serveur à
// joindre : le cumul 12 mois de ancien.json EST la série que l'ancienne route API
// /market/transactions-run-rate exposait (vérifié : même valeur au dernier point).
const ancienData = await FileAttachment("./data/ancien.json").json();
const neufData = await FileAttachment("./data/neuf.json").json();
```

# 📤 Confronter vos ventes au marché du logement

<!--
  CHAPEAU STATIQUE, rendu au build — voir CLAUDE.md, « Texte statique : aucun chiffre, aucun état ».
-->

Chargez vos ventes mensuelles — chiffre d'affaires, volumes, commandes — et cette page
cherche lequel des indicateurs du logement les précède le mieux, et de combien de mois :
les ventes de logements anciens, ou les permis et mises en chantier d'un type de logement.
Si vos ventes suivent les permis avec plusieurs mois de retard, les permis d'aujourd'hui
annoncent déjà une partie de votre activité à venir.

Pas de fichier sous la main ? Le modèle de fichier et la série d'exemple, juste en
dessous, montrent ce que la page en tire. Les séries de marché sont celles du site, et la
date de leur dernier point figure dans le
[tableau des sources](/a-propos#d-ou-viennent-les-donnees).

<div class="hm-privacy">
🔒 <b>Votre fichier ne quitte pas ce navigateur.</b> Il est lu localement, et toutes les
régressions qui en dépendent sont calculées ici, en JavaScript : rien n'est téléversé
nulle part. Il n'est <b>conservé sur cet appareil que si vous le demandez</b> (case
« Garder mon fichier »), pour le retrouver à votre prochaine visite face aux indicateurs
mis à jour.
</div>

## 1. Importer vos ventes mensuelles

<div class="hm-caption">
CSV avec une colonne <code>Date</code> (mensuelle, ex. <code>2023-01-01</code>) et une
colonne de valeurs — <code>Sales</code>, <code>Ventes</code> ou <code>CA</code>. Une
colonne facultative <code>Serie</code> sépare vos familles de produits.
</div>

```js
const upload = view(Inputs.file({label: "Fichier CSV", accept: ".csv,.txt"}));
```

```js
// Le modèle de fichier, fabriqué ici (aucun fichier servi) : trois lignes au bon format.
const MODELE = ["Date,Ventes,Serie", "2024-01-01,1250,Gamme A", "2024-02-01,1310,Gamme A",
  "2024-03-01,1480,Gamme A"].join("\n") + "\n";
display(html`<div class="hm-shortcuts">
  <a class="hm-shortcut" download="modele-ventes.csv"
     href=${"data:text/csv;charset=utf-8," + encodeURIComponent(MODELE)}>⬇️ Modèle de fichier</a>
</div>`);
```

```js
const essai = view(Inputs.button("Essayer avec une série d'exemple", {value: false,
  reduce: () => true}));
```

```js
// Garder le fichier est un CHOIX (2026-10-04) : jusque-là il restait dans le navigateur
// sans que la page le dise — elle affirmait même que « rien n'en est conservé ». La case
// est cochée d'office seulement si un fichier est déjà gardé, pour ne pas l'effacer en
// silence à l'ouverture.
const CLE_VENTES = "hmCompanySales";
const dejaGarde = (() => { try { return !!localStorage.getItem(CLE_VENTES); } catch { return false; } })();
```

```js
const garder = view(Inputs.toggle({label: "Garder mon fichier sur cet appareil", value: dejaGarde}));
```

```js
// Lecture locale. `Inputs.file` donne un FileAttachment : `.text()` lit le fichier choisi
// par l'utilisateur sans aucune requête réseau.
const parsed = await (async () => {
  if (!upload && essai) {
    // Une série FABRIQUÉE, et dite telle : les ventes anciennes du site décalées de cinq
    // mois, mises à l'échelle d'une entreprise et bruitées. La page doit retrouver un
    // décalage voisin de cinq mois — c'est ce qu'elle montre à qui n'a pas de fichier.
    const source = ancienData.main_series.rows.filter((r) => r.roll12 != null && r.date >= "2012-01-01");
    // Arrêtée au dernier mois publié : des ventes datées dans le futur n'existent pas.
    const dernier = source[source.length - 1].date;
    const rows = source.map((r, i) => {
        const d = new Date(`${r.date}T00:00:00Z`);
        d.setUTCMonth(d.getUTCMonth() + 5);
        const date = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-01`;
        return {date, value: Math.round(r.roll12 / 800 * (1 + 0.04 * Math.sin(i * 1.7))),
                serie: "Toutes"};
      }).filter((r) => r.date <= dernier);
    return {rows, source: "série d'exemple fabriquée (ventes anciennes décalées de cinq mois)",
            exemple: true};
  }
  if (!upload) {
    // Reprise du fichier gardé sur cet appareil, s'il y en a un.
    try {
      const saved = localStorage.getItem(CLE_VENTES);
      if (saved) return {rows: JSON.parse(saved), source: "fichier gardé sur cet appareil"};
    } catch { /* stockage indisponible */ }
    return null;
  }
  const text = await upload.text();
  const raw = csvParse(text);
  const cols = raw.columns.map((c) => c.trim());
  const dateCol = cols.find((c) => /^date$/i.test(c));
  const valueCol = cols.find((c) => /^(sales|ventes|ca|valeur|value)$/i.test(c));
  const serieCol = cols.find((c) => /^(serie|série|famille|produit|product)$/i.test(c));
  if (!dateCol || !valueCol) {
    return {error: `Colonnes attendues : « Date » et « Sales »/« Ventes »/« CA ». ` +
                   `Trouvé : ${cols.join(", ")}`};
  }
  const rows = raw.map((r) => {
    const d = new Date(r[dateCol]);
    if (isNaN(d)) return null;
    // Toute date est ramenée au 1er du mois : c'est la grille de l'API, et une jointure
    // sur des dates au 15 ou au 31 renverrait zéro ligne, en silence.
    const date = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-01`;
    const value = Number(String(r[valueCol]).replace(",", ".").replace(/\s/g, ""));
    return isNaN(value) ? null : {date, value, serie: serieCol ? r[serieCol] : "Toutes"};
  }).filter(Boolean).sort((a, b) => a.date.localeCompare(b.date));
  if (!rows.length) return {error: "Aucune ligne exploitable dans ce fichier."};
  return {rows, source: upload.name};
})();
```

```js
// Le fichier n'est écrit sur l'appareil que si la case est cochée, et effacé dès qu'elle
// est décochée. La série d'exemple n'est jamais gardée.
try {
  if (!garder) localStorage.removeItem(CLE_VENTES);
  else if (parsed?.rows && !parsed.exemple) localStorage.setItem(CLE_VENTES, JSON.stringify(parsed.rows));
} catch { /* stockage indisponible */ }
```

```js
display(!parsed ? html`<div class="hm-caption">Aucun fichier chargé pour l'instant.</div>`
  : parsed.error ? html`<div class="hm-api-offline"><b>Import impossible.</b>
      <p>${parsed.error}</p></div>`
  : html`<div class="hm-caption">✅ ${parsed.rows.length} mois lus depuis
      <b>${parsed.source}</b> — de ${parsed.rows[0].date} à
      ${parsed.rows[parsed.rows.length - 1].date}.</div>`);
```

```js
const salesRows = parsed && parsed.rows ? parsed.rows : null;
const seriesNames = salesRows ? [...new Set(salesRows.map((r) => r.serie))] : [];
```

```js
const serie = seriesNames.length > 1
  ? view(Inputs.select(seriesNames, {label: "Famille de produits"}))
  : (seriesNames[0] ?? null);
```

```js
// Agrégation mensuelle de la famille retenue (somme si plusieurs lignes le même mois).
const mySales = (() => {
  if (!salesRows) return null;
  const acc = new Map();
  for (const r of salesRows) {
    if (serie && r.serie !== serie) continue;
    acc.set(r.date, (acc.get(r.date) ?? 0) + r.value);
  }
  return [...acc.entries()].map(([date, value]) => ({date, value}))
                           .sort((a, b) => a.date.localeCompare(b.date));
})();
```

## 2. Quel driver amont explique le mieux vos ventes ?

<div class="hm-caption">
Deux candidats sont testés sur <i>votre</i> série, avec le même estimateur et la même
grille de décalage (0 à 18 mois, R² maximal) : les <b>transactions</b> de logements
anciens, et les <b>permis de construire</b>. C'est la seule façon honnête de les
départager — deux méthodes différentes donneraient deux gagnants.
</div>

```js
// Cumul 12 mois des transactions IGEDD, déjà calculé côté export (queries.monthly) —
// c'est exactement la série que l'ancienne route /market/transactions-run-rate exposait.
const txSeries = ancienData.main_series.rows
  .filter((r) => r.roll12 != null)
  .map((r) => ({date: r.date, value: r.roll12}));
const housingTypesList = neufData.by_type.types.map((t) => t.name);

// Cumul 12 mois des permis (ou mises en chantier) d'UN type SIT@DEL, reconstruit depuis
// by_type.series de neuf.json — même donnée que l'ancienne route /market/permits-run-rate,
// juste indexée par nom plutôt que recalculée à la demande.
function permitsSeries(typeName, metric) {
  const t = neufData.by_type.types.find((x) => x.name === typeName);
  const s = t && neufData.by_type.series.find(
    (x) => x.type === t.code && x.key === (metric === "Permis" ? "permis" : "mises"));
  if (!s) return null;
  return neufData.by_type.dates
    .map((date, i) => ({date, value: s.roll12[i]}))
    .filter((r) => r.value != null);
}
```

```js
const market = {tx: txSeries, types: housingTypesList};
```

```js
const housingType = view(Inputs.select(market.types, {label: "Type de logement (permis)",
  value: market.types.find((t) => /pure/i.test(t)) ?? market.types[0]}));
const metric = view(Inputs.select(["Permis", "MisesEnChantier"], {label: "Métrique de construction"}));
```

```js
const permits = housingType ? permitsSeries(housingType, metric) : null;
```

```js
// Les deux ajustements tournent ICI, sur vos données qui n'ont pas bougé de la page.
// `bestLagFit` est la transposition JS de `forecast.best_tx_to_monthly` : même grille,
// même critère (R² maximal), donc les deux drivers sont comparés à armes égales.
const fitTx = mySales ? bestLagFit(market.tx, mySales) : null;
const fitPm = mySales && permits ? bestLagFit(permits, mySales) : null;
```

```js
display(!mySales ? html`<div class="hm-caption">Chargez un fichier pour lancer la
    comparaison.</div>`
  : !fitTx && !fitPm ? html`<div class="hm-caption">Trop peu de mois communs entre vos
      ventes et les séries de marché (8 minimum).</div>`
  : cardGrid([
      {label: "Transactions → vos ventes",
       value: fitTx ? `${fitTx.lag} mois` : "—",
       delta: fitTx ? `R² = ${nf1.format(fitTx.r2 * 100)} %` : null,
       subs: fitTx ? [`estimé sur ${fitTx.n} mois communs`] : ["trop peu de points"]},
      {label: `${metric} → vos ventes`,
       value: fitPm ? `${fitPm.lag} mois` : "—",
       delta: fitPm ? `R² = ${nf1.format(fitPm.r2 * 100)} %` : null,
       subs: fitPm ? [`estimé sur ${fitPm.n} mois communs`] : ["trop peu de points"]},
      {label: "Meilleur driver amont",
       value: (fitTx && fitPm) ? (fitPm.r2 >= fitTx.r2 ? "Les permis" : "Les transactions") : "—",
       subs: (fitTx && fitPm)
         ? [`écart de R² : ${nf1.format(Math.abs(fitPm.r2 - fitTx.r2) * 100)} points`] : []}
    ], kpiCard));
```

```js
// Superposition du meilleur driver, décalé, et de vos ventes. Les deux séries n'ont pas
// la même unité : centrées-réduites, on compare les formes.
function zscore(rows) {
  const vals = rows.map((r) => r.value).filter((v) => v != null);
  if (!vals.length) return rows;
  const mu = vals.reduce((a, b) => a + b, 0) / vals.length;
  const sd = Math.sqrt(vals.reduce((a, b) => a + (b - mu) ** 2, 0) / vals.length);
  return rows.map((r) => ({...r, value: sd > 0 ? (r.value - mu) / sd : 0}));
}
```

```js
const bestDriver = (fitTx && fitPm)
  ? (fitPm.r2 >= fitTx.r2 ? {rows: permits, fit: fitPm, name: `${metric} — ${housingType}`}
                          : {rows: market.tx, fit: fitTx, name: "Transactions (IGEDD)"})
  : (fitPm ? {rows: permits, fit: fitPm, name: `${metric} — ${housingType}`}
           : fitTx ? {rows: market.tx, fit: fitTx, name: "Transactions (IGEDD)"} : null);
```

```js
if (bestDriver) display(multiLine({
  rows: [
    ...zscore(mySales).map((d) => ({...d, series: "Vos ventes"})),
    ...zscore(shiftMonths(bestDriver.rows, bestDriver.fit.lag))
      .map((d) => ({...d, series: `${bestDriver.name} décalé +${bestDriver.fit.lag} m`}))
  ],
  meta: [{name: "Vos ventes", color: series.brick},
         {name: `${bestDriver.name} décalé +${bestDriver.fit.lag} m`,
          color: series.blue, dash: true}],
  yLabel: "Écarts-types (séries centrées-réduites)", height: 340,
  yPct: true, lastLabels: false, valueFmt: (v) => nf1.format(v) + " σ", width,
  filename: "donnees-alignement-ventes"
}));
```

```js
if (bestDriver) display(html`<div class="hm-caption">
  La partie du driver qui dépasse à droite de vos dernières ventes correspond à une
  activité <b>déjà engagée en amont</b> : ces permis sont déposés, ou ces transactions
  réalisées, mais les ventes correspondantes ne le sont pas encore.
  ${bestDriver.fit.r2 < 0.3 ? html`<br><b>Attention :</b> un R² de
    ${nf1.format(bestDriver.fit.r2 * 100)} % est faible — le décalage retenu explique mal
    votre série, ne bâtissez pas de plan dessus.` : ""}
</div>`);
```

```js
if (mySales) display(html`<div style="margin-top:1.2rem">
  ${Inputs.button("🗑️ Oublier mes ventes (efface le stockage local)", {reduce: () => {
    try { localStorage.removeItem(CLE_VENTES); } catch { /* privé */ }
    location.reload();
  }})}
</div>`);
```
