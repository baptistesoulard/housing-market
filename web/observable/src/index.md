---
title: Synthèse
toc: false
---

```js
const data = await FileAttachment("./data/synthese.json").json();
```

<style>
/* --- Typo & thème alignés sur l'app Streamlit (Calibri / Segoe UI, accent brique) --- */
:root {
  --sans-serif: Calibri, "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
  --serif: Calibri, "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
  --hm-brick: #E64A19;
  --hm-ink: #2D3748;
}
body { font-family: var(--sans-serif); color: var(--hm-ink); background: #FFFFFF; }
h1, h2, h3, h4 { font-family: var(--sans-serif); color: var(--hm-ink); }
h1 { font-weight: 700; border-bottom: 2px solid var(--hm-brick); padding-bottom: 8px; margin-bottom: 0.15rem; }
a, a:visited { color: #1E88E5; }

/* Titres de section (Activité, Financement…) : 2ᵉ niveau net, avec filet de séparation. */
main h3 {
  font-size: 1.35rem; font-weight: 700; color: var(--hm-ink);
  margin-top: 2.6rem; margin-bottom: 0.6rem;
  padding-bottom: 0.35rem; border-bottom: 1px solid #E7E9ED;
}

.hm-caption { color: var(--theme-foreground-muted); font-size: 0.92rem; max-width: 62rem; margin: 0.2rem 0 1rem; }
.hm-chips { margin: 0.4rem 0 1.2rem; }
.hm-takeaways {
  background: color-mix(in srgb, #64B5F6 12%, transparent);
  border-left: 4px solid #64B5F6;
  border-radius: 8px; padding: 0.9rem 1.1rem; margin: 0.6rem 0 1rem; max-width: 62rem;
}
.hm-takeaways ul { margin: 0.3rem 0 0; padding-left: 1.1rem; }
.hm-takeaways li { margin: 0.35rem 0; line-height: 1.5; }
.hm-meta { color: var(--theme-foreground-muted); font-size: 0.85rem; margin: 0.4rem 0 0.2rem; }
.hm-grid {
  display: grid; gap: 2.1rem 1.6rem; margin: 1rem 0 0.6rem;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
}
.hm-card {
  padding: 0.15rem 0; background: transparent; border: none;
}
/* Libellé de carte (3ᵉ niveau) : discret pour laisser le chiffre dominer. */
.hm-card-title { font-weight: 600; font-size: 0.86rem; color: #4A5568; letter-spacing: 0.2px; }
.hm-card-value { font-size: 1.6rem; font-weight: 700; color: var(--hm-ink); margin: 0.5rem 0 0.4rem; line-height: 1.1; }
.hm-card-sub { font-size: 0.8rem; color: var(--theme-foreground-muted); line-height: 1.45; }
.hm-link { color: var(--theme-foreground-muted); font-size: 0.83rem; margin: 0.5rem 0 2rem; }
.hm-panels { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); }
.hm-legend { display: flex; flex-wrap: wrap; gap: 0.4rem 1.3rem; margin: 0.6rem 0 0.1rem; }
.hm-legend-item { display: inline-flex; align-items: center; gap: 0.45rem; cursor: pointer;
  font-size: 0.9rem; user-select: none; }
.hm-legend-item.off { opacity: 0.4; text-decoration: line-through; }
.hm-swatch { width: 16px; height: 3px; border-radius: 2px; display: inline-block; }
.hm-panel-title { font-weight: 600; font-size: 0.95rem; color: var(--hm-ink); margin-bottom: 0.2rem; }
details.hm-howto { margin: 0.2rem 0 0.8rem; max-width: 62rem; }
details.hm-howto summary { cursor: pointer; color: var(--theme-foreground-muted); }
</style>

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
