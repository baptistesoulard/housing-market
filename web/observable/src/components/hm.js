// Composants & helpers partagés par toutes les pages du dashboard.
// Importé par les .md via  import {...} from "./components/hm.js".
import * as Plot from "npm:@observablehq/plot";
import * as d3 from "npm:d3";
import {html} from "npm:htl";
import {ui} from "./theme.js";

// --- Formatage FR ------------------------------------------------------------------
const frLocale = d3.timeFormatLocale({
  dateTime: "%A %e %B %Y à %X", date: "%d/%m/%Y", time: "%H:%M:%S", periods: ["AM", "PM"],
  days: ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"],
  shortDays: ["dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam."],
  months: ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
           "septembre", "octobre", "novembre", "décembre"],
  shortMonths: ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août",
                "sept.", "oct.", "nov.", "déc."],
});
export const fmtMonthFR = frLocale.utcFormat("%B %Y");
export const MONTHS_SHORT = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
                             "juil.", "août", "sept.", "oct.", "nov.", "déc."];
export const MONTHS_FULL = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                            "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"];
export const nf0 = new Intl.NumberFormat("fr-FR", {maximumFractionDigits: 0});
export const nf1 = new Intl.NumberFormat("fr-FR", {maximumFractionDigits: 1});

// --- Carte KPI (miroir st.metric) --------------------------------------------------
export function kpiCard({label, value, delta, yoy, subs}) {
  const d = delta ?? yoy;
  const neg = d && /^-|−/.test(d.replace("−", "-"));
  return html`<div class="hm-card">
    <div class="hm-card-title">${label}</div>
    <div class="hm-card-value">${value}${d ? html` <span class="hm-delta ${neg ? "neg" : "pos"}">${d}</span>` : ""}</div>
    ${(subs || []).map((s) => html`<div class="hm-card-sub">${s}</div>`)}
  </div>`;
}

export function cardGrid(cards, render) {
  return html`<div class="hm-grid">${cards.map(render)}</div>`;
}

// --- Légende cliquable partagée ----------------------------------------------------
export function legend(meta, active, onToggle) {
  return html`<div class="hm-legend">${meta.map((m) => {
    const on = active.has(m.name);
    const sw = m.dash
      ? {borderBottom: `2px dashed ${m.color}`, background: "transparent", height: "0", marginBottom: "3px"}
      : {background: m.color};
    return html`<span class="hm-legend-item ${on ? "" : "off"}" onclick=${() => onToggle(m.name)}>
      <span class="hm-swatch" style=${sw}></span>${m.name}</span>`;
  })}</div>`;
}

// --- Graphique multi-séries générique (lignes) -------------------------------------
// rows : format long {date, series, value}.  meta : [{name,color,dash}].
export function multiLine({rows, meta, yLabel, active = null, height = 360, valueFmt,
                           baseline = null, lastLabels = true, tipUnit = "", yPct = false}) {
  const parsed = rows.map((d) => ({...d, _x: new Date(d.date)}));
  const shown = active ? parsed.filter((d) => active.has(d.series)) : parsed;
  const colorDomain = meta.map((m) => m.name), colorRange = meta.map((m) => m.color);
  const dashed = new Set(meta.filter((m) => m.dash).map((m) => m.name));
  const fmt = valueFmt || ((v) => nf1.format(v));
  const last = meta.filter((m) => !active || active.has(m.name)).map((m) => {
    const s = shown.filter((d) => d.series === m.name); return s[s.length - 1];
  }).filter(Boolean);
  return Plot.plot({
    height, marginLeft: 54, marginRight: 74,
    x: {label: null}, y: {label: yLabel, grid: true, zero: baseline == null && !yPct, percent: false},
    color: {domain: colorDomain, range: colorRange},
    marks: [
      baseline != null ? Plot.ruleY([baseline], {stroke: ui.rule, strokeDasharray: "3,3"}) : null,
      yPct ? Plot.ruleY([0], {stroke: ui.rule, strokeDasharray: "3,3"}) : null,
      Plot.lineY(shown.filter((d) => !dashed.has(d.series)), {x: "_x", y: "value", stroke: "series", strokeWidth: 2.4}),
      Plot.lineY(shown.filter((d) => dashed.has(d.series)), {x: "_x", y: "value", stroke: "series", strokeWidth: 2.4, strokeDasharray: "6,4"}),
      lastLabels ? Plot.text(last, {x: "_x", y: "value", text: (d) => fmt(d.value),
        fill: (d) => (meta.find((m) => m.name === d.series) || {}).color, dx: 8, textAnchor: "start", fontWeight: 700}) : null,
      Plot.dot(shown, Plot.pointer({x: "_x", y: "value", stroke: "series", r: 4, fill: "white", strokeWidth: 2})),
      Plot.tip(shown, Plot.pointer({x: "_x", y: "value", stroke: "series",
        title: (d) => `${d.series}\n${fmtMonthFR(d._x)}\n${fmt(d.value)}${tipUnit}`})),
    ].filter(Boolean),
  });
}

// --- Graphique « marché » : bascule cumul 12m / 6m / brut (+ moyennes mobiles) -----
// rows : {date, series, key, raw, roll12, roll6} (valeurs brutes, divisées par 1000 ici).
export function marketChart({rows, meta, view, showRaw = true, showMA12 = false, showMA6 = false,
                             active, yLabel, height = 420}) {
  const K = 1000;
  const parsed = rows.map((d) => ({...d, _x: new Date(d.date)}));
  const vis = (d) => !active || active.has(d.series);
  const colorDomain = meta.map((m) => m.name), colorRange = meta.map((m) => m.color);
  const dashed = new Set(meta.filter((m) => m.dash).map((m) => m.name));
  const marks = [];
  const tipCol = {roll12: "roll12", roll6: "roll6", raw: "raw"}[view];
  const lastLabels = [];

  const line = (data, col, width, dash) => {
    const d = data.filter((r) => r[col] != null && vis(r)).map((r) => ({...r, v: r[col] / K}));
    marks.push(Plot.lineY(d.filter((r) => !dashed.has(r.series)), {x: "_x", y: "v", stroke: "series", strokeWidth: width, strokeDasharray: dash}));
    marks.push(Plot.lineY(d.filter((r) => dashed.has(r.series)), {x: "_x", y: "v", stroke: "series", strokeWidth: width, strokeDasharray: "6,4"}));
    return d;
  };

  let tipData;
  if (view === "roll12" || view === "roll6") {
    const col = view === "roll12" ? "roll12" : "roll6";
    tipData = line(parsed, col, 3);
    for (const m of meta) { if (active && !active.has(m.name)) continue;
      const s = tipData.filter((r) => r.series === m.name); if (s.length) lastLabels.push(s[s.length - 1]); }
  } else {
    // Vue brute : ligne mensuelle (± estompée) + moyennes mobiles éventuelles.
    if (showRaw || (!showMA12 && !showMA6)) tipData = line(parsed, "raw", 1.6, null);
    if (showMA12) line(parsed.map((r) => ({...r, ma12: r.roll12 == null ? null : r.roll12 / 12})), "ma12", 2.4);
    if (showMA6) line(parsed.map((r) => ({...r, ma6: r.roll6 == null ? null : r.roll6 / 6})), "ma6", 2.4);
    if (!tipData) tipData = parsed.filter((r) => r.raw != null && vis(r)).map((r) => ({...r, v: r.raw / K}));
    for (const m of meta) { if (active && !active.has(m.name)) continue;
      const s = tipData.filter((r) => r.series === m.name); if (s.length) lastLabels.push(s[s.length - 1]); }
  }
  marks.push(Plot.text(lastLabels, {x: "_x", y: "v", text: (d) => `${nf0.format(d.v)}`,
    fill: (d) => (meta.find((m) => m.name === d.series) || {}).color, dx: 8, textAnchor: "start", fontWeight: 700}));
  marks.push(Plot.dot(tipData, Plot.pointer({x: "_x", y: "v", stroke: "series", r: 4, fill: "white", strokeWidth: 2})));
  marks.push(Plot.tip(tipData, Plot.pointer({x: "_x", y: "v", stroke: "series",
    title: (d) => `${d.series}\n${fmtMonthFR(d._x)}\n${nf0.format(d.v)} k`})));

  return Plot.plot({height, marginLeft: 54, marginRight: 74,
    x: {label: null}, y: {label: yLabel, grid: true, zero: true},
    color: {domain: colorDomain, range: colorRange}, marks});
}

// --- Comparaison mensuelle par année (barres groupées) -----------------------------
export function monthlyByYear({rows, valueKey, monthNums, scheme = "YlOrRd"}) {
  const data = [];
  for (const r of rows) {
    const dt = new Date(r.date), mn = dt.getUTCMonth() + 1;
    if (!monthNums.includes(mn)) continue;
    const v = r[valueKey]; if (v == null) continue;
    data.push({year: String(dt.getUTCFullYear()), month: mn, monthName: MONTHS_SHORT[mn - 1], value: v / 1000});
  }
  const order = monthNums.slice().sort((a, b) => a - b).map((m) => MONTHS_SHORT[m - 1]);
  return Plot.plot({
    height: 360, marginBottom: 42, marginLeft: 54,
    fx: {label: null, domain: order},
    x: {axis: null, type: "band"}, y: {label: "en milliers", grid: true},
    color: {type: "ordinal", scheme, legend: true, label: "Année"},
    marks: [
      Plot.barY(data, {fx: "monthName", x: "year", y: "value", fill: "year",
        tip: {format: {fx: false, x: true, y: (v) => `${nf1.format(v)} k`, fill: false}}}),
      Plot.ruleY([0]),
    ],
  });
}

// --- Filtre de période ------------------------------------------------------------
// Rognage des lignes par la frise de la barre latérale (components/period.js), dont le
// domaine vient de l'export Python (`period` dans chaque JSON). Il ne rogne que
// l'AFFICHAGE : cumuls glissants et moyennes mobiles sont calculés en amont sur
// l'historique complet (côté Python), exactement comme app.py qui filtre APRÈS avoir
// calculé. Une fenêtre étroite montre donc les mêmes valeurs qu'en vue complète, jamais
// des cumuls tronqués sur les premiers mois affichés.
export function filterYears(rows, range, field = "date") {
  if (!range || !rows) return rows;
  const lo = Math.min(range[0], range[1]), hi = Math.max(range[0], range[1]);
  return rows.filter((r) => {
    const y = +String(r[field]).slice(0, 4);
    return y >= lo && y <= hi;
  });
}

// --- Segmentation par type de logement (SIT@DEL) ----------------------------------
// Reconstitue les lignes de la courbe principale pour un sous-ensemble de types, à
// partir du bloc colonnaire `by_type`. La somme est exacte : le cumul glissant d'une
// somme vaut la somme des cumuls glissants, et les quatre types démarrent le même mois.
// Avec tous les types sélectionnés, le résultat est identique à `main_series.rows`
// (mêmes lignes, même filtrage des mois sans valeur brute).
export function sumByType({dates, series}, codes, meta) {
  const wanted = new Set(codes);
  const out = [];
  for (const m of meta) {
    const parts = series.filter((s) => s.key === m.key && wanted.has(s.type));
    for (let i = 0; i < dates.length; i++) {
      const row = {date: dates[i], series: m.name, key: m.key};
      for (const f of ["raw", "roll12", "roll6"]) {
        let sum = null;
        for (const p of parts) {
          const v = p[f][i];
          if (v != null) sum = (sum ?? 0) + v;
        }
        row[f] = sum === null ? null : Math.round(sum * 1000) / 1000;
      }
      if (row.raw != null) out.push(row);
    }
  }
  return out;
}
