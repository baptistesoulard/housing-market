---
title: Données & Sources
toc: false
---

```js
import {multiLine, cardGrid, kpiCard, nf0, nf1, csvParse} from "./components/hm.js";
import {series, ui} from "./components/theme.js";
import {api, apiOfflineNotice, bestLagFit, shiftMonths} from "./components/api.js";
```

# ⚙️ Données & Sources

<div class="hm-caption">
Les jeux de données de marché (SIT@DEL, IGEDD, macro, ECLN…) sont rafraîchis hors
application, par <code>python fetch_new_sources.py</code> et le workflow hebdomadaire.
Cette page ne sert qu'à une chose : croiser <b>vos</b> ventes mensuelles avec les drivers
amont du marché.
</div>

<div class="hm-privacy">
🔒 <b>Votre fichier ne quitte pas ce navigateur.</b> Il est lu localement, gardé dans le
stockage de l'onglet, et toutes les régressions qui en dépendent sont calculées ici, en
JavaScript. Rien n'est téléversé vers l'API ni vers Cloudflare — c'est pourquoi cette page
fonctionne même si l'API est éteinte, à ceci près qu'elle n'aura alors aucun driver de
marché à croiser.
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
// Lecture locale. `Inputs.file` donne un FileAttachment : `.text()` lit le fichier choisi
// par l'utilisateur sans aucune requête réseau.
const parsed = await (async () => {
  if (!upload) {
    // Reprise de l'import précédent, s'il y en a un dans cet onglet.
    try {
      const saved = localStorage.getItem("hmCompanySales");
      if (saved) return {rows: JSON.parse(saved), source: "mémoire du navigateur"};
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
  try { localStorage.setItem("hmCompanySales", JSON.stringify(rows)); } catch { /* privé */ }
  return {rows, source: upload.name};
})();
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
const market = await (async () => {
  try {
    const [tx, types] = await Promise.all([api.transactionsRunRate(), api.housingTypes()]);
    return {ok: true, tx: tx.series, types: types.types};
  } catch (error) {
    return {ok: false, error};
  }
})();
```

```js
display(market.ok ? html`` : apiOfflineNotice(market.error));
```

```js
const housingType = market.ok
  ? view(Inputs.select(market.types, {label: "Type de logement (permis)",
                                      value: market.types.find((t) => /pure/i.test(t)) ?? market.types[0]}))
  : null;
const metric = market.ok
  ? view(Inputs.select(["Permis", "MisesEnChantier"], {label: "Métrique de construction"}))
  : null;
```

```js
const permits = market.ok && housingType
  ? (await api.permitsRunRate(housingType, metric)).series
  : null;
```

```js
// Les deux ajustements tournent ICI, sur vos données qui n'ont pas bougé de la page.
// `bestLagFit` est la transposition JS de `forecast.best_tx_to_monthly` : même grille,
// même critère (R² maximal), donc les deux drivers sont comparés à armes égales.
const fitTx = mySales && market.ok ? bestLagFit(market.tx, mySales) : null;
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
display(!bestDriver ? html`` : multiLine({
  rows: [
    ...zscore(mySales).map((d) => ({...d, series: "Vos ventes"})),
    ...zscore(shiftMonths(bestDriver.rows, bestDriver.fit.lag))
      .map((d) => ({...d, series: `${bestDriver.name} décalé +${bestDriver.fit.lag} m`}))
  ],
  meta: [{name: "Vos ventes", color: series.brick},
         {name: `${bestDriver.name} décalé +${bestDriver.fit.lag} m`,
          color: series.blue, dash: true}],
  yLabel: "Écarts-types (séries centrées-réduites)", height: 340,
  yPct: true, lastLabels: false, valueFmt: (v) => nf1.format(v) + " σ"
}));
```

```js
display(!bestDriver ? html`` : html`<div class="hm-caption">
  La partie du driver qui dépasse à droite de vos dernières ventes correspond à une
  activité <b>déjà engagée en amont</b> : ces permis sont déposés, ou ces transactions
  réalisées, mais les ventes correspondantes ne le sont pas encore.
  ${bestDriver.fit.r2 < 0.3 ? html`<br><b>Attention :</b> un R² de
    ${nf1.format(bestDriver.fit.r2 * 100)} % est faible — le décalage retenu explique mal
    votre série, ne bâtissez pas de plan dessus.` : ""}
</div>`);
```

```js
display(!mySales ? html`` : html`<div style="margin-top:1.2rem">
  ${Inputs.button("🗑️ Oublier mes ventes (efface le stockage local)", {reduce: () => {
    try { localStorage.removeItem("hmCompanySales"); } catch { /* privé */ }
    location.reload();
  }})}
</div>`);
```
