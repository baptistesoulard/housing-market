---
title: Synthèse
toc: false
---

```js
const data = await FileAttachment("./data/synthese.json").json();
```

```js
// --- Rendu des pastilles par pilier ------------------------------------------------
function chip(p) {
  const palette = {
    up: ["rgba(56,142,60,0.12)", "#2E7D32"],
    flat: ["rgba(251,192,45,0.20)", "#7A5D00"],
    down: ["rgba(230,74,25,0.12)", "#B23A12"],
  };
  const [bg, fg] = palette[p.status] || ["#ECECEC", "#555555"];
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
  return html`<div class="hm-card">
    <div class="hm-card-title">${c.title}</div>
    <div class="hm-card-value">${c.emoji} ${c.value}</div>
    ${c.sub ? html`<div class="hm-card-sub">${c.sub}</div>` : ""}
  </div>`;
}
```

# ${data.title}

<div class="hm-caption">${data.caption}</div>

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

```js
// --- Les trois blocs de cartes (Activité / Financement / Perspective) --------------
for (const b of data.blocks) {
  display(html`<h3>${b.title}</h3>`);
  display(html`<div class="hm-grid">${b.cards.map(card)}</div>`);
  display(html`<div class="hm-link">${b.link}</div>`);
}
```

---

### Neuf vs ancien — volumes en cumul 12 mois

<div class="hm-caption">
À gauche, les niveaux réels sur une échelle unique : le rapport de masse saute aux yeux
(l'ancien pèse 2 à 3× le neuf). À droite, base 100 à une date de référence commune : on
compare les dynamiques sans distorsion d'échelle.
</div>

```js
// Préparation : parse des dates + métadonnées de séries (noms, couleurs).
const rows = data.chart.rows.map((d) => ({ ...d, date: new Date(d.date) }));
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
    return html`<span class="hm-legend-item ${on ? "" : "off"}" onclick=${() => toggleSeries(m.name)}>
      <span class="hm-swatch" style=${{ background: m.color, borderBottom: m.dash ? `2px dashed ${m.color}` : "none", height: m.dash ? "0" : "3px" }}></span>${m.name}
    </span>`;
  })}</div>`;
}

// Dernier point de chaque série visible, pour l'étiquette de valeur en bout de courbe.
function lastPoints(field, active) {
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

function panel({ y, ylabel, baseline, active }) {
  const shown = (d) => d[y] != null && active.has(d.series);
  const solid = rows.filter((d) => !dashedKeys.has(d.series) && shown(d));
  const dashed = rows.filter((d) => dashedKeys.has(d.series) && shown(d));
  const pts = rows.filter(shown);
  return Plot.plot({
    height: 380,
    marginLeft: 52,
    marginRight: 72,
    x: { label: null },
    y: { label: ylabel, grid: true, zero: baseline == null },
    // Domaine/plage complets : chaque série garde sa couleur même si d'autres sont masquées.
    color: { domain: colorDomain, range: colorRange, legend: false },
    marks: [
      baseline != null ? Plot.ruleY([baseline], { stroke: "#B0B7C3", strokeDasharray: "2,3" }) : null,
      Plot.lineY(solid, { x: "date", y, stroke: "series", strokeWidth: 2.5 }),
      Plot.lineY(dashed, { x: "date", y, stroke: "series", strokeWidth: 2.5, strokeDasharray: "6,4" }),
      Plot.text(lastPoints(y, active), {
        x: "date", y, text: (d) => (y === "level_k" ? `${Math.round(d[y])} k` : `${Math.round(d[y])}`),
        fill: (d) => meta.find((m) => m.name === d.series).color,
        dx: 8, textAnchor: "start", fontWeight: 700,
      }),
      // Survol type Plotly « closest » : point le plus proche + infobulle des valeurs.
      Plot.dot(pts, Plot.pointer({ x: "date", y, stroke: "series", r: 4, strokeWidth: 2, fill: "white" })),
      Plot.tip(pts, Plot.pointer({
        x: "date", y, stroke: "series",
        title: (d) => tipTitle(d, y),
      })),
    ].filter(Boolean),
  });
}
```

${legend(visible)}
<div class="hm-caption" style="margin-top:0.1rem">Cliquez une série de la légende pour la masquer ou l'afficher (les deux graphiques suivent).</div>

<div class="hm-panels">
  <div>
    <div class="hm-panel-title">Niveaux réels — échelle unique</div>
    ${panel({ y: "level_k", ylabel: "Milliers /12 m", baseline: null, active: visible })}
  </div>
  <div>
    <div class="hm-panel-title">Base 100 = ${data.chart.base_date_label}</div>
    ${panel({ y: "index_100", ylabel: "Indice (base 100)", baseline: 100, active: visible })}
  </div>
</div>

<div class="hm-meta">${data.chart.source}</div>

<div class="hm-meta">
  Généré le ${new Date(data.generated_at).toLocaleString("fr-FR")} ·
  front statique Observable Framework · données : pipeline Python existante.
</div>
