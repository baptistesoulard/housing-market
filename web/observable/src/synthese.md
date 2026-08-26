---
title: Synthèse
toc: true
---

```js
import {status, ui} from "./components/theme.js";
import {filterYears, withCsvExport, TIP} from "./components/hm.js";
import {periodFilter} from "./components/period.js";
const data = await FileAttachment("./data/synthese.json").json();
```

```js
// Frise de période GLOBALE (barre latérale) — même contrôle sur tous les onglets.
// Les cartes et les pastilles de cette page n'en dépendent pas : comme dans `app.py`,
// elles lisent le national plein au dernier mois disponible, indépendamment du curseur.
// Seul le graphique croisé neuf/ancien ci-dessous suit la fenêtre choisie.
const rangeS = Generators.input(periodFilter({min: data.period.min, max: data.period.max}));
```

```js
// --- Rendu des pastilles par pilier ------------------------------------------------
function chip(p) {
  const {bg, fg} = status[p.status] || status.unknown;
  return html`<span style=${{
    background: bg, color: fg, borderRadius: "16px", padding: "6px 14px",
    marginRight: "10px", fontWeight: 600, fontSize: "1.02rem",
    display: "inline-block", marginBottom: "6px",
  }}>${p.dot} ${p.label} · ${p.word}</span>`;
}

// **gras** markdown minimal → <strong> (les puces « à retenir » en contiennent).
function bold(s) {
  const parts = s.split(/\*\*(.+?)\*\*/g);
  return parts.map((t, i) => (i % 2 ? html`<strong>${t}</strong>` : t));
}

function card(c) {
  // Échelle st.metric (hm-card--metric), comme les cartes des autres pages. Ces cartes
  // reprenaient l'échelle du markdown `**libellé**` + `### valeur` d'app.py — 16 px de
  // libellé et 28 px de valeur : trois blocs de quatre à cette taille écrasaient le
  // reste de la page. La pastille de statut est ramenée sous la taille du chiffre
  // (voir .hm-card-dot) pour que ce soit le nombre qu'on lise en premier, pas le rond.
  return html`<div class="hm-card hm-card--metric">
    <div class="hm-card-title">${c.title}</div>
    <div class="hm-card-value"><span class="hm-card-dot">${c.emoji}</span> ${c.value}</div>
    ${c.sub ? html`<div class="hm-card-sub">${c.sub}</div>` : ""}
  </div>`;
}
```

<!--
  TITRE ET CHAPEAU STATIQUES — rendus au build, pas construits dans le navigateur.
  Tout le reste de la page est monté en JS à partir du JSON : un robot d'indexation, comme
  tout aperçu de partage, n'en voit rien. Ces deux blocs sont donc le SEUL texte de la page
  que lisent Google et LinkedIn. Le titre valait auparavant `${data.title}`, c'est-à-dire un titre
  VIDE dans le HTML livré. Ne pas les reconvertir en interpolation.
  Voir CLAUDE.md, « Le chapeau des pages de données ».
-->

# 🧭 Synthèse — vue d'ensemble du marché

Cette page rassemble en une vue l'essentiel du marché immobilier français : où en sont la
construction neuve, les ventes de logements anciens, les prix et les conditions de crédit.
Chaque pilier est résumé par une pastille de tendance, puis détaillé sur sa propre page.

Chaque chiffre est donné sur **deux horizons** : le momentum des derniers mois, qui dit si
le rythme est en train de tourner, et la tendance sur douze mois, qui dit d'où l'on vient.
Les deux ne pointent pas toujours dans le même sens, et c'est précisément quand ils
divergent qu'ils sont utiles. La fenêtre du momentum dépend de la série : les permis et les
mises en chantier sont publiés corrigés des variations saisonnières, donc comparés aux mois
qui précèdent immédiatement ; les ventes de logements anciens, reconstruites à partir d'un
cumul annuel, sont trop irrégulières d'un mois sur l'autre et se lisent sur douze mois,
complétées par la date depuis laquelle leur niveau ne bouge plus.

Le pilier de la construction neuve ne moyenne pas ses deux étages. Les permis sont l'amont,
ce qui alimentera les chantiers douze à dix-huit mois plus tard ; les mises en chantier sont
l'aval, ce qui consomme des matériaux aujourd'hui. Quand l'un se retourne avant l'autre, la
pastille le dit au lieu de compenser l'un par l'autre.

Les chiffres sont nationaux et proviennent d'organismes publics. Les dates de dernière
publication diffèrent d'une série à l'autre : chaque producteur a son propre calendrier et
son propre délai.


<div class="hm-chips">${data.pillars.map(chip)}</div>

<div class="hm-takeaways">
  <strong>À retenir</strong>
  <ul>${data.takeaways.map((t) => html`<li>${bold(t)}</li>`)}</ul>
</div>

<div class="hm-meta">📅 Dernières données — ${data.freshness.join(" · ")}</div>

<details class="hm-howto">
  <summary>ℹ️ Comment lire cette page</summary>
  <div class="hm-caption">${data.how_to_read}</div>
</details>

## 📇 Les chiffres du dernier mois publié

```js
// --- Les trois blocs de cartes (Activité / Financement / Perspective) --------------
for (const b of data.blocks) {
  display(html`<h3>${b.title}</h3>`);
  display(html`<div class="hm-grid">${b.cards.map(card)}</div>`);
  // Renvois vers les pages de détail. Le JSON donne le chemin canonique de la barre
  // latérale (« /neuf ») ; l'href est relatif à cette page, qui est la racine du site.
  display(html`<div class="hm-shortcuts"><span class="lead">→ détail :</span>${
    b.links.map((l) => html`<a class="hm-shortcut" href=".${l.path}">${l.icon} ${l.label}</a>`)}</div>`);
}
```

---

## 📈 Neuf vs ancien — volumes en cumul 12 mois

<div class="hm-caption">
À gauche, les niveaux réels sur une échelle unique : le rapport de masse saute aux yeux
(l'ancien pèse 2 à 3× le neuf). À droite, base 100 sur la moyenne 2015 — la base des
indices INSEE, donc celle de tous les indices du site : on compare les dynamiques sans
distorsion d'échelle, et le repère reste le même d'un graphique à l'autre.
</div>

```js
// Métadonnées de séries (noms, couleurs). Les lignes, elles, dépendent de la frise :
// elles sont préparées dans leur propre bloc pour que bouger le curseur ne réinitialise
// pas l'état `visible` de la légende, défini ici.
const meta = data.chart.series_meta;
const colorDomain = meta.map((m) => m.name);
const colorRange = meta.map((m) => m.color);
const dashedKeys = new Set(meta.filter((m) => m.dash).map((m) => m.name));

// État réactif : séries visibles (toutes au départ). Cliquer une entrée de légende
// masque/affiche la série dans les DEUX panneaux (comme le clic-légende de Plotly).
const visible = Mutable(new Set(meta.map((m) => m.name)));
function toggleSeries(name) {
  const s = new Set(visible.value);
  s.has(name) ? s.delete(name) : s.add(name);
  visible.value = s;
}

// Légende cliquable partagée (active = ensemble des séries visibles).
function legend(active) {
  return html`<div class="hm-legend">${meta.map((m) => {
    const on = active.has(m.name);
    // <button aria-pressed> plutôt que <span onclick> : même raison que dans
    // components/hm.js — un interrupteur doit être atteignable au clavier et annoncer
    // son état, que le barré CSS ne dit qu'à ceux qui le voient.
    return html`<button type="button" class="hm-legend-item ${on ? "" : "off"}"
      aria-pressed=${on ? "true" : "false"} onclick=${() => toggleSeries(m.name)}>
      <span class="hm-swatch" style=${{ background: m.color, borderBottom: m.dash ? `2px dashed ${m.color}` : "none", height: m.dash ? "0" : "3px" }}></span>${m.name}
    </button>`;
  })}</div>`;
}

// Dernier point de chaque série visible, pour l'étiquette de valeur en bout de courbe.
function lastPoints(rows, field, active) {
  return meta.filter((m) => active.has(m.name)).map((m) => {
    const s = rows.filter((d) => d.series === m.name && d[field] != null);
    return s[s.length - 1];
  }).filter(Boolean);
}

// Formatage FR du survol (mois année + valeur selon le panneau).
const fmtMonthFR = d3.timeFormatLocale({
  dateTime: "%A %e %B %Y à %X", date: "%d/%m/%Y", time: "%H:%M:%S", periods: ["AM", "PM"],
  days: ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"],
  shortDays: ["dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam."],
  months: ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
           "septembre", "octobre", "novembre", "décembre"],
  shortMonths: ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août",
                "sept.", "oct.", "nov.", "déc."],
}).utcFormat("%B %Y");
function tipTitle(d, y) {
  const val = y === "level_k" ? `${d.level_k.toLocaleString("fr-FR")} k` : d.index_100.toFixed(1);
  return `${d.series}\n${fmtMonthFR(d.date)}\n${val}`;
}

function panel({ rows, y, ylabel, baseline, active }) {
  const shown = (d) => d[y] != null && active.has(d.series);
  const solid = rows.filter((d) => !dashedKeys.has(d.series) && shown(d));
  const dashed = rows.filter((d) => dashedKeys.has(d.series) && shown(d));
  const pts = rows.filter(shown);
  const plot = Plot.plot({
    height: 380,
    marginLeft: 52,
    marginRight: 72,
    x: { label: null },
    y: { label: ylabel, grid: true, zero: baseline == null },
    // Domaine/plage complets : chaque série garde sa couleur même si d'autres sont masquées.
    color: { domain: colorDomain, range: colorRange, legend: false },
    marks: [
      baseline != null ? Plot.ruleY([baseline], { stroke: ui.rule, strokeDasharray: "2,3" }) : null,
      Plot.lineY(solid, { x: "date", y, stroke: "series", strokeWidth: 2.5 }),
      Plot.lineY(dashed, { x: "date", y, stroke: "series", strokeWidth: 2.5, strokeDasharray: "6,4" }),
      Plot.text(lastPoints(rows, y, active), {
        x: "date", y, text: (d) => (y === "level_k" ? `${Math.round(d[y])} k` : `${Math.round(d[y])}`),
        fill: (d) => meta.find((m) => m.name === d.series).color,
        dx: 8, textAnchor: "start", fontWeight: 700,
      }),
      // Survol type Plotly « closest » : point le plus proche + infobulle des valeurs.
      Plot.dot(pts, Plot.pointer({ x: "date", y, stroke: "series", r: 4, strokeWidth: 2, fill: "white" })),
      Plot.tip(pts, Plot.pointer({
        x: "date", y, stroke: "series", ...TIP,
        title: (d) => tipTitle(d, y),
      })),
    ].filter(Boolean),
  });
  return withCsvExport(plot, pts, "synthese-neuf-vs-ancien-" + y);
}
```

```js
// Parse des dates, après le filtre de période : `filterYears` lit l'année sur la chaîne
// 'YYYY-MM-DD' de l'export. Comme ailleurs, le filtre ne rogne que l'AFFICHAGE — les
// cumuls 12 mois et la base 100 sont calculés côté Python sur l'historique complet.
const rows = filterYears(data.chart.rows, rangeS).map((d) => ({ ...d, date: new Date(d.date) }));
```

${legend(visible)}
<div class="hm-caption" style="margin-top:0.1rem">Cliquez une série de la légende pour la masquer ou l'afficher (les deux graphiques suivent).</div>

<div class="hm-panels">
  <div>
    <div class="hm-panel-title">Niveaux réels — échelle unique</div>
    ${panel({ rows, y: "level_k", ylabel: "Milliers /12 m", baseline: null, active: visible })}
  </div>
  <div>
    <div class="hm-panel-title">Base 100 = ${data.chart.base_label}</div>
    ${panel({ rows, y: "index_100", ylabel: "Indice (base 100)", baseline: 100, active: visible })}
  </div>
</div>

<div class="hm-meta">${data.chart.source}</div>

<div class="hm-meta">
  Généré le ${new Date(data.generated_at).toLocaleString("fr-FR")} ·
  front statique Observable Framework · données : pipeline Python existante.
</div>
