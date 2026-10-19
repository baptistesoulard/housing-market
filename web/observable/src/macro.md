---
title: Crédit & conjoncture
toc: true
---

```js
import {legend, multiLine, filterYears, withCsvExport, cadreGraphique, nf0, nf1, fmtMonthFR, TIP} from "./components/hm.js";
import {periodFilter} from "./components/period.js";
import {series} from "./components/theme.js";
const macro = await FileAttachment("./data/macro.json").json();
```

<!--
  TITRE ET CHAPEAU STATIQUES — rendus au build, pas construits dans le navigateur.
  Tout le reste de la page est monté en JS à partir du JSON : un robot d'indexation, comme
  tout aperçu de partage, n'en voit rien. Ces deux blocs sont donc le SEUL texte de la page
  que lisent Google et LinkedIn. Le titre valait auparavant `${macro.title}`, c'est-à-dire un titre
  VIDE dans le HTML livré. Ne pas les reconvertir en interpolation.
  Voir CLAUDE.md, « Texte statique : aucun chiffre, aucun état ».
-->

# 🏦 Crédit & conjoncture — taux, confiance, emploi

Le marché du logement ne se comprend pas sans ce qui le finance et ce qui décide les
ménages. Cette page rassemble les indicateurs qui expliquent le marché plus qu'ils ne le
décrivent, et qui pour la plupart le précèdent : taux du crédit immobilier (toutes durées confondues), <abbr title="Taux auquel les banques de la zone euro se prêtent entre elles à court terme">Euribor</abbr> 3 mois
et <abbr title="Obligation d'État française à 10 ans, référence du coût du crédit à long terme">OAT</abbr> 10 ans, confiance des ménages, intentions d'achat de logement, chômage au sens du
<abbr title="Bureau International du Travail, dont la définition standardisée permet de comparer le chômage entre pays">BIT</abbr>, production de crédits à l'habitat et demande de crédits mesurée par l'enquête <abbr title="Bank Lending Survey : enquête trimestrielle de la BCE sur les conditions de crédit bancaire">BLS</abbr>.

Les soldes d'opinion — confiance, intentions d'achat, demande de crédits — se lisent en
écart à leur repère et non en niveau absolu : c'est leur mouvement qui informe, pas leur
valeur. Ce sont ces séries qui alimentent la prévision de transactions publiée sur ce site.


<details class="hm-howto">
  <summary>ℹ️ Comment lire cette page</summary>
  <div class="hm-caption">${macro.how_to_read}</div>
</details>

```js
// Filtre de période : la frise GLOBALE de la barre latérale, partagée par tous les
// onglets (parité avec le curseur d'années de la barre latérale Streamlit).
const rangeM = Generators.input(periodFilter({min: macro.period.min, max: macro.period.max}));
```

```js
// Légende cliquable pour les 3 taux.
const visR = Mutable(new Set(macro.rates.meta.map((m) => m.name)));
function toggleR(name) { const s = new Set(visR.value); s.has(name) ? s.delete(name) : s.add(name); visR.value = s; }
```

## 📉 Confiance, taux et emploi

<div class="hm-caption">Les quatre indicateurs qui décrivent la capacité et l'envie d'acheter : moral des ménages, coût de l'argent, intentions déclarées et marché du travail.</div>

<div class="hm-panels">
  ${multiLine({rows: filterYears(macro.confidence, rangeM).map((d) => ({...d, series: "Indice de Confiance"})), meta: [{name: "Indice de Confiance", color: series.brick}], yLabel: "Indice, base 100", baseline: 100, valueFmt: (v) => nf0.format(v), filename: "macro-confiance-menages",
    titre: "Confiance des ménages", sousTitre: "Indicateur synthétique CVS, base 100 = moyenne de longue période · France", source: "INSEE, enquête de conjoncture auprès des ménages"})}
  ${multiLine({rows: filterYears(macro.rates.rows, rangeM), meta: macro.rates.meta, active: visR, yLabel: "%", valueFmt: (v) => nf1.format(v) + " %", tipUnit: " %", filename: "macro-taux-interet",
    titre: "Taux du crédit habitat et taux de marché", sousTitre: "Crédit habitat toutes durées, Euribor 3 mois, OAT 10 ans, en %", legende: legend(macro.rates.meta, visR, toggleR),
    source: "Banque de France, BCE"})}
</div>

<div class="hm-panels">
  ${multiLine({rows: filterYears(macro.intentions, rangeM).map((d) => ({...d, series: "Intentions d'achat"})), meta: [{name: "Intentions d'achat", color: series.blue}], yLabel: "Écarts-types", yPct: true, lastLabels: false, valueFmt: (v) => nf1.format(v), filename: "macro-intentions-achat",
    titre: "Intentions d'achat de logement dans l'année", sousTitre: "Solde CVS centré-réduit, en écarts-types (0 = moyenne de long terme) · France", source: "INSEE, enquête de conjoncture auprès des ménages"})}
  ${multiLine({rows: filterYears(macro.chomage, rangeM).map((d) => ({...d, series: "Taux de chômage BIT"})), meta: [{name: "Taux de chômage BIT", color: series.brick}], yLabel: "%", valueFmt: (v) => nf1.format(v) + " %", tipUnit: " %", filename: "macro-chomage-bit",
    titre: "Taux de chômage au sens du BIT", sousTitre: "En % de la population active · France hors Mayotte", source: "INSEE"})}
</div>

```js
// Sections conditionnelles (crédits / BLS / rénovation) rendues via display().
const cr = macro.credit, bls = macro.bls, reno = macro.renovation;

const SOURCE_CREDITS = "BCE, statistiques MIR (achat de logement, France) ; renégociations isolées par la décomposition BPCE, publiée depuis 2019";
function creditMonthly() {
  if (!cr.has_split)
    return multiLine({rows: filterYears(cr.cum, rangeM).map((d) => ({date: d.date, series: "Total", value: d.total})),
      meta: [{name: "Total", color: series.blue}], yLabel: "Md€", valueFmt: (v) => nf0.format(v), filename: "macro-credits-production-mensuelle",
      titre: "Production mensuelle de crédits à l'habitat", sousTitre: "Y compris renégociations, en milliards d'euros par mois", source: SOURCE_CREDITS});
  const rows = [];
  for (const d of filterYears(cr.monthly, rangeM)) {
    rows.push({date: d.date, cat: "Crédits nouveaux (hors renégo.)", value: d.pure});
    rows.push({date: d.date, cat: "Renégociations", value: d.renego});
  }
  const plotRows = rows.map((r) => ({...r, date: new Date(r.date)}));
  const plot = Plot.plot({height: 340, marginLeft: 48, x: {label: null}, y: {label: "Md€", grid: true},
    color: {domain: ["Crédits nouveaux (hors renégo.)", "Renégociations"], range: [series.blue, series.gold], legend: true},
    marks: [Plot.rectY(plotRows, {x: "date", y: "value", fill: "cat", interval: "month", tip: {...TIP}}), Plot.ruleY([0])]});
  return cadreGraphique({titre: "Production mensuelle de crédits à l'habitat",
    sousTitre: "Crédits nouveaux et renégociations, en milliards d'euros par mois", dernier: rows, source: SOURCE_CREDITS,
    children: withCsvExport(plot, rows, "macro-credits-production-mensuelle")});
}
function creditCum() {
  const rows = [...filterYears(cr.cum, rangeM).map((d) => ({date: d.date, series: "Total (y.c. renégo.)", value: d.total}))];
  const meta = [{name: "Total (y.c. renégo.)", color: series.green}];
  if (cr.has_split) {
    rows.push(...filterYears(cr.cum, rangeM).filter((d) => d.pure != null).map((d) => ({date: d.date, series: "Hors renégociations", value: d.pure})));
    meta.push({name: "Hors renégociations", color: series.brick, dash: true});
  }
  return multiLine({rows, meta, yLabel: "Md€", valueFmt: (v) => nf0.format(v), filename: "macro-credits-production-cumulee",
    titre: "Production de crédits à l'habitat sur 12 mois", sousTitre: "Cumul sur 12 mois glissants, en milliards d'euros", source: SOURCE_CREDITS});
}

// Un titre suivi de rien se lit comme une panne du site, alors que c'est une série
// absente de l'export. Ces trois sections restent conditionnelles, mais le disent.
const indisponible = (quoi) => html`<div class="hm-caption">${quoi} : série absente de cet
  export. La page « À propos » liste les séries publiées et leur dernier point.</div>`;
```

## 💶 Volume de crédits à l'habitat

```js
display(cr ? html`<div class="hm-panels">${creditMonthly()}${creditCum()}</div>` : indisponible("Production de crédits à l'habitat"));
```

## 🏦 Demande de crédits à l'habitat (enquête BLS)

```js
if (!bls) display(indisponible("Demande de crédits (BLS)"));
if (bls) display(multiLine({rows: filterYears(bls.rows, rangeM), meta: bls.meta, yLabel: "Solde net (%)", yPct: true, valueFmt: (v) => nf0.format(v) + " %", tipUnit: " %", width, filename: "macro-demande-credits-bls",
  titre: "Demande de crédits à l'habitat vue par les banques", sousTitre: "Solde d'opinion net, en % ; au-dessus de 0, demande en hausse · France",
  source: "BCE, Banque de France, enquête sur la distribution du crédit (Bank Lending Survey)"}));
```

## 🔨 Rénovation & second œuvre

```js
if (!reno.length) display(indisponible("Activité du second œuvre"));
if (reno.length) display(multiLine({rows: reno.flatMap((r) => filterYears(r.rows, rangeM).map((d) => ({...d, series: r.title}))),
  meta: reno.map((r) => ({name: r.title, color: r.color})), yLabel: "Solde d'opinion", yPct: true, valueFmt: (v) => nf0.format(v), width, filename: "macro-renovation-second-oeuvre",
  titre: "Activité des entreprises du second œuvre", sousTitre: "Solde d'opinion ; sous 0, plus d'entreprises signalent une baisse qu'une hausse · France",
  source: "INSEE, enquête mensuelle de conjoncture dans l'industrie du bâtiment (second œuvre)"}));
```
