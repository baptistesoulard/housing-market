// Composants & helpers partagés par toutes les pages du dashboard.
// Importé par les .md via  import {...} from "./components/hm.js".
import * as Plot from "npm:@observablehq/plot";
import * as d3 from "npm:d3";
import {html, svg} from "npm:htl";
import {ui, series, carte} from "./theme.js";

// Réexportés pour que les PAGES n'aient jamais à importer `npm:` elles-mêmes :
// toutes les pages passent par ce module, une seule façon de charger une lib.
export {Plot, d3};
export const csvParse = d3.csvParse;

// --- Formatage FR ------------------------------------------------------------------
const FR_TEMPS = {
  dateTime: "%A %e %B %Y à %X", date: "%d/%m/%Y", time: "%H:%M:%S", periods: ["AM", "PM"],
  days: ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"],
  shortDays: ["dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam."],
  months: ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
           "septembre", "octobre", "novembre", "décembre"],
  shortMonths: ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août",
                "sept.", "oct.", "nov.", "déc."],
};
const frLocale = d3.timeFormatLocale(FR_TEMPS);

// Les graduations des AXES ne passent par aucun de nos formateurs : Plot les écrit avec
// la locale PAR DÉFAUT de d3, qui est l'anglais — « 1,000 · 1,100 » sur l'axe des volumes
// de la Synthèse, et des mois « Jan · Apr » dès que la frise resserre la période. Les
// vignettes, elles, passent par nf0/nf1 (Intl fr-FR) et étaient déjà justes. Poser la
// locale française par défaut ICI, dans le module que toutes les pages importent avant
// de tracer quoi que ce soit, corrige tous les axes du site d'un coup — plutôt qu'un
// tickFormat par graphique, qu'un graphique suivant oublierait. Séparateur de milliers :
// l'espace fine insécable, comme Intl.NumberFormat("fr-FR").
d3.formatDefaultLocale({decimal: ",", thousands: "\u202f", grouping: [3],
                        currency: ["", "\u00a0\u20ac"], percent: "\u202f%"});
d3.timeFormatDefaultLocale(FR_TEMPS);
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

// --- Cartes et nuages de départements (page « Carte des départements ») -------------
// Une mesure s'affiche partout de la même façon : même unité, même rang, mêmes mots que
// sur les pages départementales. `formatMesure` et `positionRang` sont la seule définition
// de ces deux choses côté navigateur.

/** Le formateur d'une mesure, selon son unité (champ `unite` de carte.json). */
export function formatMesure(unite) {
  // Pas de zéro signé : une variation qui s'arrondit à 0 ne porte ni « + » ni « − ».
  const signe = (v) => (Math.round(Math.abs(v) * 10) === 0 ? "" : v > 0 ? "+" : "−");
  switch (unite) {
    case "euro": return (v) => `${nf0.format(v)} €`;
    case "euro_an": return (v) => `${nf0.format(v)} € par an`;
    case "pct": return (v) => `${nf1.format(v)} %`;
    case "pct_signe": return (v) => `${signe(v)}${nf1.format(Math.abs(v))} %`;
    case "m2": return (v) => `${nf0.format(v)} m²`;
    default: return (v) => nf1.format(v);
  }
}

/** Le rang d'un département, dit comme sur sa propre page. `p` = part des AUTRES
 *  départements renseignés strictement en dessous (percent_rank, 0-100). */
export function positionRang(p) {
  if (p == null) return "";
  return p >= 50
    ? `plus élevé que dans ${p} % des autres départements`
    : `plus bas que dans ${100 - p} % des autres départements`;
}

/**
 * Carte des départements coloriée par UNE mesure.
 *
 * geo      : le fond de carte (departements-geo.json : features + cadres des encarts).
 * valeurs  : Map code -> {nom, couvert, v, p}.
 * mesure   : l'entrée de carte.json (echelle, unite, label, ref, ref_libelle).
 *
 * Deux échelles, jamais d'arc-en-ciel (voir « carte » dans web/theme.json, validé) :
 *  - « sequentielle » : sept classes de QUANTILES — chaque couleur regroupe à peu près le
 *    même nombre de départements, sinon Paris seul occupe la moitié du dégradé ;
 *  - « divergente » : un pivot à zéro en gris neutre, brique en dessous, bleu au-dessus,
 *    bornée au 95e centile des écarts pour qu'un département hors norme ne délave pas
 *    tous les autres (il prend la teinte extrême, sa valeur exacte reste au survol).
 * Un département sans valeur est HACHURÉ, jamais gris : un gris plein se confondrait avec
 * le pivot du divergent, c'est-à-dire avec « zéro ».
 */
export function carteDepartements({geo, valeurs, mesure, width = 640,
                                   href = (code) => `/departement/${code}`}) {
  const fmt = formatMesure(mesure.unite);
  const val = (f) => valeurs.get(f.properties.code) ?? {};
  const xs = geo.features.map((f) => val(f).v).filter((v) => v != null);
  let echelle;
  if (mesure.echelle === "divergente") {
    const m = d3.quantile(xs.map(Math.abs).sort(d3.ascending), 0.95) || 1;
    const n = carte.divergente.length;
    echelle = {type: "linear", domain: d3.range(n).map((i) => -m + (2 * m * i) / (n - 1)),
               range: carte.divergente, interpolate: "lab", clamp: true};
  } else {
    echelle = {type: "quantile", domain: xs, n: carte.sequentielle.length,
               range: carte.sequentielle};
  }
  const couleur = Plot.scale({color: echelle});
  // Un identifiant par carte : deux cartes sur une page ne doivent pas se voler le motif.
  const motif = "hm-hachures-" + Math.random().toString(36).slice(2, 9);
  const titre = (f) => {
    const d = val(f), code = f.properties.code;
    const nom = `${d.nom ?? f.properties.nom} (${code})`;
    if (d.v == null) {
      return nom + "\n" + (d.couvert === false
        ? "Hors DVF : Alsace-Moselle (Livre foncier) ou Mayotte"
        : "Non renseigné pour cette mesure");
    }
    const ref = mesure.ref != null ? `\n${mesure.ref_libelle} : ${fmt(mesure.ref)}` : "";
    return `${nom}\n${fmt(d.v)}\n${positionRang(d.p)}${ref}`;
  };
  // Étiquettes des encarts, au-dessus de chaque cadre (en longitude/latitude). Le point
  // d'ancrage est posé un peu SOUS le bord haut du cadre, et le texte remonté par `dy` :
  // ancré sur le bord, le cadre parisien — le plus haut, donc le bord même de l'emprise —
  // tombait hors du domaine projeté et son étiquette disparaissait sans erreur.
  const etiquettes = (geo.cadres ?? []).map((c) => {
    const pts = c.geometry.coordinates[0];
    return {nom: c.properties.nom, x: d3.mean(pts, (p) => p[0]),
            y: d3.max(pts, (p) => p[1]) - 0.08};
  });
  const plot = Plot.plot({
    // marginTop : l'étiquette de l'encart parisien, posée au-dessus de son cadre, sortirait
    // sinon du SVG. La projection DOIT rester alignée avec web/export/fond_de_carte.py,
    // qui pré-tourne les encarts pour cette projection précise.
    width, marginTop: 20,
    projection: {type: "conic-conformal", parallels: [44, 49], rotate: [-3, 0],
                 // Les cadres des encarts débordent des départements qu'ils entourent :
                 // ils doivent entrer dans l'emprise, sinon leur étiquette sort du SVG.
                 domain: {type: "FeatureCollection",
                          features: [...geo.features, ...(geo.cadres ?? [])]}},
    color: {type: "identity"},
    marks: [
      Plot.geo(geo.features, {
        fill: (f) => (val(f).v == null ? `url(#${motif})` : couleur.apply(val(f).v)),
        stroke: carte.contour, strokeWidth: 0.7,
        href: (f) => href(f.properties.code), title: titre, tip: {...TIP}}),
      Plot.geo(geo.cadres ?? [], {fill: "none", stroke: carte.cadre, strokeWidth: 0.8}),
      // clip: false — l'étiquette de l'encart le plus haut (Paris) déborde dans la marge,
      // au-dessus du cadre de la carte, que la projection rogne par défaut.
      Plot.text(etiquettes, {x: "x", y: "y", text: "nom", dy: -12, fontSize: 11,
                             fill: ui.muted, textAnchor: "middle", clip: false}),
    ],
  });
  plot.insertBefore(hachures(motif), plot.firstChild);
  const legende = Plot.legend({color: echelle, label: mesure.label, tickFormat: fmt,
                               width: Math.min(420, width), ticks: 5});
  const aucune = geo.features.some((f) => val(f).v == null);
  const temoin = aucune ? html`<span class="hm-carte-nd">${svg`<svg width="16" height="12"
      aria-hidden="true">${hachures(motif + "-l")}<rect width="16" height="12"
      fill=${"url(#" + motif + "-l)"} stroke=${carte.cadre}/></svg>`} non renseigné</span>` : "";
  return html`<div class="hm-carte">
    <div class="hm-carte-legende">${legende}${temoin}</div>
    ${plot}
  </div>`;
}

// Le motif des départements sans valeur : des hachures, et non un aplat gris.
function hachures(id) {
  return svg`<defs><pattern id=${id} width="6" height="6" patternUnits="userSpaceOnUse"
      patternTransform="rotate(45)"><rect width="6" height="6" fill="#FFFFFF"/>
      <line x1="0" y1="0" x2="0" y2="6" stroke=${carte.sans_donnee} stroke-width="1.6"/>
    </pattern></defs>`;
}

/**
 * Nuage de départements : un point par département, deux mesures en abscisse et en
 * ordonnée. Les MÉDIANES tracées découpent le nuage en quatre groupes sans en nommer
 * aucun — c'est au lecteur de dire ce qu'il y voit, pas à un score.
 *
 * points : [{code, nom, x, y}] ; etiquettes : codes à nommer sur le graphique (peu !).
 * xLog / yLog : échelle logarithmique, pour un prix au m² que Paris écraserait sinon
 * (le nuage tiendrait dans le premier quart de l'axe).
 */
export function nuageDepartements({points, fmtX, fmtY, xLabel, yLabel, width = 640,
                                   height = 380, medianes = true, tendance = false,
                                   zeroY = false, xDomain, yDomain, etiquettes = [],
                                   xLog = false, yLog = false,
                                   href = (code) => `/departement/${code}`}) {
  const nommes = points.filter((d) => etiquettes.includes(d.code));
  return Plot.plot({
    // marginRight : une étiquette de département au bord droit (Paris, la Creuse) serait
    // rognée sans elle.
    width, height, marginLeft: 56, marginBottom: 44, marginRight: 72,
    x: {label: xLabel, domain: xDomain, grid: true, tickFormat: fmtX, ticks: 5,
        ...(xLog ? {type: "log"} : {})},
    y: {label: yLabel, domain: yDomain, grid: true, tickFormat: fmtY,
        ...(yLog ? {type: "log"} : {})},
    marks: [
      medianes ? Plot.ruleX([d3.median(points, (d) => d.x)],
                            {stroke: ui.greyLine, strokeDasharray: "4,3"}) : null,
      medianes ? Plot.ruleY([d3.median(points, (d) => d.y)],
                            {stroke: ui.greyLine, strokeDasharray: "4,3"}) : null,
      zeroY ? Plot.ruleY([0], {stroke: ui.rule}) : null,
      tendance ? Plot.linearRegressionY(points, {x: "x", y: "y", stroke: series.brick,
                                                 strokeWidth: 2, ci: 0}) : null,
      Plot.dot(points, {x: "x", y: "y", r: 4, fill: series.blue, fillOpacity: 0.8,
                        stroke: "#FFFFFF", strokeWidth: 1, href: (d) => href(d.code),
                        title: (d) => `${d.nom} (${d.code})\n${xLabel} : ${fmtX(d.x)}\n` +
                                      `${yLabel} : ${fmtY(d.y)}`,
                        tip: {...TIP}}),
      Plot.text(nommes, {x: "x", y: "y", text: "nom", dx: 7, textAnchor: "start",
                         fontSize: 11, fill: ui.muted}),
    ],
  });
}
