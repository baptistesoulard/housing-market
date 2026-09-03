// Composants & helpers partagés par toutes les pages du dashboard.
// Importé par les .md via  import {...} from "./components/hm.js".
import * as Plot from "npm:@observablehq/plot";
import * as d3 from "npm:d3";
import {html} from "npm:htl";
import {ui} from "./theme.js";

// Réexportés pour que les PAGES n'aient jamais à importer `npm:` elles-mêmes :
// toutes les pages passent par ce module, une seule façon de charger une lib.
export {Plot, d3};
export const csvParse = d3.csvParse;

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

// --- Vignette de survol -------------------------------------------------------------
// Plot dessine ses vignettes en 10 px. C'est la taille d'un graphique d'exploration, où
// la vignette n'est qu'une confirmation ; ici elle porte les SEULS chiffres exacts du
// site — les courbes n'ont ni quadrillage fin ni étiquettes intermédiaires, donc lire une
// valeur passe forcément par elle.
//
// La taille se passe en OPTION de la marque, jamais en CSS : Plot mesure le texte avec
// cette valeur pour dimensionner le cadre. Un `font-size` posé en feuille de style
// grossirait le texte sans agrandir la boîte, et le débordement serait rogné.
//
// À importer partout où une vignette est créée (`Plot.tip(..., {...TIP})`, ou
// `tip: {...TIP}` sur une marque) : une seule valeur pour tout le site.
export const TIP = {fontSize: 13};

// --- Export CSV au survol d'un graphique --------------------------------------------
// Bouton discret révélé au survol (.hm-chart-card / .hm-chart-export dans
// observablehq.config.js), qui télécharge les LIGNES ayant servi à tracer la courbe —
// jamais une capture du SVG. Le CSV reste donc exact même là où Plot agrège ou lisse
// l'affichage (cumuls glissants, moyennes mobiles), et reflète le filtrage déjà appliqué
// (période, légende cliquée, segmentation) puisqu'on exporte les données APRÈS filtrage,
// pas la série brute complète.
const DIACRITICS = new RegExp("[" + String.fromCharCode(0x0300) + "-" + String.fromCharCode(0x036f) + "]", "g");
function slug(s) {
  return String(s).normalize("NFD").replace(DIACRITICS, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "graphique";
}
export function withCsvExport(node, rows, filename) {
  if (!rows || !rows.length) return node;                    // rien à offrir : pas de bouton
  const name = slug(filename) + ".csv";
  const btn = html`<button type="button" class="hm-chart-export" title="Télécharger les données affichées (CSV)">⬇ CSV</button>`;
  btn.addEventListener("click", () => {
    const url = URL.createObjectURL(new Blob([d3.csvFormat(rows)], {type: "text/csv;charset=utf-8;"}));
    const a = html`<a href=${url} download=${name}></a>`;
    document.body.append(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  });
  return html`<div class="hm-chart-card">${node}${btn}</div>`;
}

// --- Carte KPI (miroir st.metric) --------------------------------------------------
// Le delta est une PASTILLE sur sa propre ligne, comme le rend st.metric. Il était
// auparavant collé derrière la valeur, sur la même ligne : deux nombres se disputaient
// le même regard, et sur une colonne étroite le delta repoussait la valeur à la ligne.
// La classe hm-card--metric porte l'échelle de st.metric (libellé plus discret, valeur
// plus compacte). C'est désormais l'échelle de TOUTES les cartes du site : la Synthèse
// suivait le `**libellé**` + `### valeur` markdown d'app.py, une taille au-dessus, et
// ses trois blocs de cartes écrasaient le reste de la page.
export function kpiCard({label, value, delta, yoy, subs}) {
  const d = delta ?? yoy;
  const neg = d && /^-|−/.test(d.replace("−", "-"));
  // Deux sous-lignes ou plus -> une <ul>, comme les cartes de la Synthèse. Chacune est
  // une phrase à plusieurs faits (momentum, puis niveau, puis dernier mois) qui prend
  // souvent deux lignes visuelles à elle seule : empilées en <div> nues, elles devenaient
  // indiscernables les unes des autres. Une seule sous-ligne reste une <div> — une puce
  // isolée ne sépare rien et n'ajoute que du bruit.
  const s = (subs || []).filter(Boolean);
  return html`<div class="hm-card hm-card--metric">
    <div class="hm-card-title">${label}</div>
    <div class="hm-card-value">${value}</div>
    ${d ? html`<div class="hm-card-delta"><span class="hm-delta ${neg ? "neg" : "pos"}">${d}</span></div>` : ""}
    ${s.length > 1
      ? html`<ul class="hm-card-subs">${s.map((x) => html`<li class="hm-card-sub">${x}</li>`)}</ul>`
      : s.map((x) => html`<div class="hm-card-sub">${x}</div>`)}
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
    // <button aria-pressed>, pas <span onclick> : la légende EST un interrupteur, elle
    // doit donc être atteignable au clavier et annoncer son état. Le barré et l'opacité
    // ne suffisent pas — un lecteur d'écran ne lit pas du CSS. L'apparence de bouton est
    // neutralisée dans le CSS du thème (button.hm-legend-item).
    return html`<button type="button" class="hm-legend-item ${on ? "" : "off"}"
      aria-pressed=${on ? "true" : "false"} onclick=${() => onToggle(m.name)}>
      <span class="hm-swatch" style=${sw}></span>${m.name}</button>`;
  })}</div>`;
}

// Légende STATIQUE — même apparence que `legend()`, sans interrupteur. `legend()` rend des
// <button aria-pressed> parce qu'elle pilote l'affichage des séries ; sur un graphique dont
// rien ne se masque, un bouton promettrait une action qui n'existe pas. Le trait pointillé
// est reproduit dans la pastille : deux séries qui ne se distinguent que par la couleur
// sont indistinguables pour qui ne perçoit pas cette différence.
// Le modificateur `hm-legend--static` porte `cursor: default`. Il était appliqué sur la
// copie manuscrite de l'accueil, et OUBLIÉ ici, dans le helper partagé : les légendes
// statiques de « Prévision & Scénarios » héritaient donc du `cursor: pointer` de
// `.hm-legend-item` et promettaient un clic qui n'existe pas — précisément ce que le
// commentaire de ce sélecteur, dans observablehq.config.js, dit vouloir éviter. C'est le
// mode de panne ordinaire d'un composant recopié : la version dupliquée est juste, la
// partagée ne l'est pas, et rien ne les confronte. L'accueil emploie celui-ci désormais.
export function legendStatic(meta) {
  return html`<div class="hm-legend hm-legend--static">${meta.map((m) => {
    const sw = m.dash
      ? {borderBottom: `2px dashed ${m.color}`, background: "transparent", height: "0", marginBottom: "3px"}
      : {background: m.color};
    return html`<span class="hm-legend-item"><span class="hm-swatch" style=${sw}></span>${m.name}</span>`;
  })}</div>`;
}

// --- Graphique multi-séries générique (lignes) -------------------------------------
// rows : format long {date, series, value}.  meta : [{name,color,dash}].
export function multiLine({rows, meta, yLabel, active = null, height = 360, valueFmt,
                           baseline = null, lastLabels = true, tipUnit = "", yPct = false,
                           width = undefined, filename = null, splitAt = null,
                           legend = "auto"}) {
  const parsed = rows.map((d) => ({...d, _x: new Date(d.date)}));
  const shown = active ? parsed.filter((d) => active.has(d.series)) : parsed;
  const colorDomain = meta.map((m) => m.name), colorRange = meta.map((m) => m.color);
  const dashed = new Set(meta.filter((m) => m.dash).map((m) => m.name));
  const fmt = valueFmt || ((v) => nf1.format(v));
  const last = meta.filter((m) => !active || active.has(m.name)).map((m) => {
    const s = shown.filter((d) => d.series === m.name); return s[s.length - 1];
  }).filter(Boolean);
  const plot = Plot.plot({
    // `width` est facultatif : sans lui, Plot retient ses 640 px par défaut, ce que font
    // les appelants placés dans une grille (.hm-panels), déjà contrainte par ses colonnes.
    // Un graphique seul sur toute la colonne, lui, doit recevoir la largeur réactive du
    // framework, sinon il flotte à 640 px dans un conteneur qui en fait 900.
    ...(width ? {width} : {}),
    height, marginLeft: 54, marginRight: 74,
    x: {label: null}, y: {label: yLabel, grid: true, zero: baseline == null && !yPct, percent: false},
    color: {domain: colorDomain, range: colorRange},
    marks: [
      baseline != null ? Plot.ruleY([baseline], {stroke: ui.rule, strokeDasharray: "3,3"}) : null,
      yPct ? Plot.ruleY([0], {stroke: ui.rule, strokeDasharray: "3,3"}) : null,
      // `splitAt` : la frontière entraînement / test d'un backtest. Sans elle, la courbe
      // du modèle démarre en plein graphique sans que rien ne dise pourquoi — le lecteur
      // ne peut pas voir que tout ce qui est à droite a été produit SANS avoir vu la suite.
      splitAt ? Plot.ruleX([new Date(splitAt.date)], {stroke: ui.subtle, strokeDasharray: "3,3"}) : null,
      splitAt ? Plot.text([{d: new Date(splitAt.date)}], {x: "d", frameAnchor: "top", dy: 4, dx: 4,
        text: () => splitAt.label, fill: ui.subtle, textAnchor: "start", fontSize: 12}) : null,
      Plot.lineY(shown.filter((d) => !dashed.has(d.series)), {x: "_x", y: "value", stroke: "series", strokeWidth: 2.4}),
      Plot.lineY(shown.filter((d) => dashed.has(d.series)), {x: "_x", y: "value", stroke: "series", strokeWidth: 2.4, strokeDasharray: "6,4"}),
      lastLabels ? Plot.text(last, {x: "_x", y: "value", text: (d) => fmt(d.value),
        fill: (d) => (meta.find((m) => m.name === d.series) || {}).color, dx: 8, textAnchor: "start", fontWeight: 700}) : null,
      Plot.dot(shown, Plot.pointer({x: "_x", y: "value", stroke: "series", r: 4, fill: "white", strokeWidth: 2})),
      Plot.tip(shown, Plot.pointer({x: "_x", y: "value", stroke: "series", ...TIP,
        title: (d) => `${d.series}\n${fmtMonthFR(d._x)}\n${fmt(d.value)}${tipUnit}`})),
    ].filter(Boolean),
  });
  const carte = withCsvExport(plot, shown.map(({_x, ...r}) => r), filename || meta.map((m) => m.name).join(" "));

  // LÉGENDE PAR DÉFAUT, et c'est le point de ce paramètre. `multiLine` n'en posait aucune
  // et il fallait que chaque appelant y pense : sur une vingtaine d'appels, treize
  // traçaient deux ou trois courbes sans que rien ne les nomme hors survol — prix
  // Ensemble/Appartements/Maisons, encours vs mises en vente, activité passée vs prévue,
  // département vs France… Un défaut qu'on ne corrige qu'au cas par cas se réintroduit au
  // graphique suivant ; on le corrige donc ici, où l'oubli n'est plus possible.
  //
  //   "auto" (défaut) : légende statique dès qu'il y a DEUX séries ou plus.
  //   false           : rien — pour un appelant qui pose déjà la sienne autrement.
  //
  // `active` non nul signifie que l'appelant pilote l'affichage avec `legend()`, la
  // version cliquable : en poser une seconde, inerte, à côté d'elle serait absurde.
  const auto = legend === "auto" && active == null && meta.length >= 2;
  if (!auto) return carte;
  return html`<div>${legendStatic(meta)}${carte}</div>`;
}

// --- Graphique « marché » : bascule cumul 12m / 6m / 3m / brut (+ moyennes mobiles) -
// rows : {date, series, key, raw, roll12, roll6, roll3} (valeurs brutes, divisées par 1000 ici).
export function marketChart({rows, meta, view, showRaw = true, showMA12 = false, showMA6 = false,
                             active, yLabel, height = 420, width = undefined, filename = null}) {
  const K = 1000;
  const parsed = rows.map((d) => ({...d, _x: new Date(d.date)}));
  const vis = (d) => !active || active.has(d.series);
  const colorDomain = meta.map((m) => m.name), colorRange = meta.map((m) => m.color);
  const dashed = new Set(meta.filter((m) => m.dash).map((m) => m.name));
  const marks = [];
  const tipCol = {roll12: "roll12", roll6: "roll6", roll3: "roll3", raw: "raw"}[view];
  const lastLabels = [];

  const line = (data, col, width, dash) => {
    const d = data.filter((r) => r[col] != null && vis(r)).map((r) => ({...r, v: r[col] / K}));
    marks.push(Plot.lineY(d.filter((r) => !dashed.has(r.series)), {x: "_x", y: "v", stroke: "series", strokeWidth: width, strokeDasharray: dash}));
    marks.push(Plot.lineY(d.filter((r) => dashed.has(r.series)), {x: "_x", y: "v", stroke: "series", strokeWidth: width, strokeDasharray: "6,4"}));
    return d;
  };

  let tipData;
  if (view === "roll12" || view === "roll6" || view === "roll3") {
    const col = tipCol;
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
  marks.push(Plot.tip(tipData, Plot.pointer({x: "_x", y: "v", stroke: "series", ...TIP,
    title: (d) => `${d.series}\n${fmtMonthFR(d._x)}\n${nf0.format(d.v)} k`})));

  const plot = Plot.plot({
    // Facultatif, comme sur `multiLine` : sans lui, Plot retient ses 640 px par défaut,
    // ce que font les appelants placés dans une grille (.hm-panels), déjà contrainte par
    // ses colonnes.
    ...(width ? {width} : {}),
    height, marginLeft: 54, marginRight: 74,
    x: {label: null}, y: {label: yLabel, grid: true, zero: true},
    color: {domain: colorDomain, range: colorRange}, marks});
  const exportRows = parsed.filter(vis).map(({_x, ...r}) => r);
  return withCsvExport(plot, exportRows, filename || meta.map((m) => m.name).join(" "));
}

// --- Comparaison mensuelle par année (barres groupées) -----------------------------
export function monthlyByYear({rows, valueKey, monthNums, scheme = "YlOrRd", width = undefined,
                               filename = null}) {
  const data = [];
  for (const r of rows) {
    const dt = new Date(r.date), mn = dt.getUTCMonth() + 1;
    if (!monthNums.includes(mn)) continue;
    const v = r[valueKey]; if (v == null) continue;
    data.push({year: String(dt.getUTCFullYear()), month: mn, monthName: MONTHS_SHORT[mn - 1], value: v / 1000});
  }
  const order = monthNums.slice().sort((a, b) => a - b).map((m) => MONTHS_SHORT[m - 1]);
  const plot = Plot.plot({
    ...(width ? {width} : {}),
    height: 360, marginBottom: 42, marginLeft: 54,
    fx: {label: null, domain: order},
    x: {axis: null, type: "band"}, y: {label: "en milliers", grid: true},
    color: {type: "ordinal", scheme, legend: true, label: "Année"},
    marks: [
      Plot.barY(data, {fx: "monthName", x: "year", y: "value", fill: "year",
        tip: {...TIP, format: {fx: false, x: true, y: (v) => `${nf1.format(v)} k`, fill: false}}}),
      Plot.ruleY([0]),
    ],
  });
  return withCsvExport(plot, data, filename || valueKey);
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
      for (const f of ["raw", "roll12", "roll6", "roll3"]) {
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
