---
title: Prix de l'immobilier par département
toc: false
---

<!--
  REPRISE APRÈS RETRAIT (2026-08-21) — voir docs/journal/07-pages-departementales.md.

  L'ancienne version chargeait par fetch() vers une adresse construite au runtime avec
  observable.params.code, et s'affichait PAR INTERMITTENCE une fois déployée — même
  code, même URL, un rendu correct puis, sans aucun changement, plus rien que des
  indicateurs de chargement.

  Un data loader paramétré (src/departement/[code].json.js, avec
  FileAttachment("./[code].json") côté page) était la piste documentée ici pour la
  reprise. ESSAYÉE, et ÉCARTÉE : le build produit bien 101 fichiers distincts, mais
  chaque page enregistre côté client la MÊME référence littérale « [code].json » — le
  framework ne substitue pas les paramètres de route avant d'analyser les appels
  FileAttachment (voir findFiles dans son code source, qui ne reçoit pas `params`).
  Vérifié en inspectant le HTML construit : les 101 pages pointaient vers le même
  fichier générique de 2 octets ("{}"), jamais vers leurs propres données.

  Cette version revient donc à fetch(), mais vers l'adresse stable que
  scripts/postbuild.mjs copie au build (comme l'ancienne version) — PAS vers une URL
  construite à partir d'un gabarit — et reprend la structure de cellules que la
  dernière investigation avait vue s'exécuter correctement en production : un bloc
  d'imports seul, un bloc par await. Le doute qui reste, honnêtement : l'ancienne
  investigation n'a jamais isolé la cause exacte de l'intermittence (observée sur le
  site DÉPLOYÉ, non reproduite en local) ; ce correctif change la source des données,
  pas la mécanique fetch() elle-même. À surveiller après mise en ligne.

  Le titre « Prix de l'immobilier par département » reste volontairement STATIQUE et
  générique : un titre interpolé rendrait un <h1> vide tant que le JS n'a pas tourné —
  le défaut déjà corrigé ailleurs sur le site (voir « chapeau statique » dans
  CLAUDE.md). scripts/postbuild.mjs le réécrit ensuite avec le nom du département, un
  par un, à partir des mêmes données (voir depMeta dans site.config.js). Ne pas
  modifier ce texte sans répercuter le changement dans H1_GENERIQUE côté postbuild.

  Chaque branche « rien à afficher » passe par if (condition) display(...), jamais par
  un display(condition ? html vide : X) : un gabarit vide affiche littéralement "null"
  (voir l'invariant du même nom dans CLAUDE.md).
-->

# Prix de l'immobilier par département

<div class="hm-caption">France métropolitaine et d'outre-mer · d'après les ventes réellement enregistrées chez le notaire (<abbr title="Demandes de Valeurs Foncières : fichier de la DGFiP recensant les ventes immobilières réellement enregistrées">DVF</abbr>, DGFiP)</div>

```js
import {multiLine, cardGrid, kpiCard, withCsvExport, nf0, nf1, fmtMonthFR, Plot, TIP} from "../components/hm.js";
import {series, ui} from "../components/theme.js";
```

```js
// Bloc SEUL, par await : structure vue s'exécuter correctement en production avant le
// retrait du 2026-08-21 (voir le commentaire de tête). L'annuaire (non paramétré) passe
// par FileAttachment, qui fonctionne pour un fichier dont le nom ne dépend pas de la
// route — vérifié : les huit autres pages du site l'utilisent déjà sans souci.
const annuaire = await FileAttachment("../data/departements.json").json();
```

```js
// Le département courant, lui, DOIT passer par fetch() : voir le commentaire de tête
// pour pourquoi FileAttachment ne convient pas ici. L'adresse est stable, copiée au
// build par scripts/postbuild.mjs — pas hachée, donc prévisible depuis le paramètre de
// route sans dépendre d'un manifeste.
const dep = await fetch(`/data/departements/${observable.params.code}.json`).then((r) => r.json());
```

```js
const euro = (v) => v == null ? "—" : nf0.format(v) + " €";
const pct = (v) => v == null ? "—" : (v >= 0 ? "+" : "−") + nf1.format(Math.abs(v)) + " %";
// Les dates de l'agrégat sont des débuts de trimestre : « 2025-10-01 » se lit « T4 2025 ».
const trimestre = (iso) => `T${Math.floor(Number(iso.slice(5, 7)) / 3) + 1} ${iso.slice(0, 4)}`;
const couvert = dep.couvert === true;
```

```js
// Le cas « non couvert » arrête la page ici. Quatre départements sont concernés et ils
// n'ont pas à recevoir des graphiques vides, qui passeraient pour une panne du site.
if (!couvert) display(html`<div class="hm-absence">
  <div class="hm-absence-titre">Aucune donnée de prix pour ${dep.nom}</div>
  <p>${dep.absence}</p>
  <p>Les autres pages du site restent valables : elles portent sur la France entière,
  <a href="/ancien">y compris les prix nationaux</a> et
  <a href="/macro">les conditions de financement</a>, qui ne dépendent pas de DVF.</p>
</div>`);
```

```js
if (couvert) display(cardGrid([
  {label: `Prix médian au m² · ${trimestre(dep.dernier.Ensemble.date)}`,
   value: euro(dep.dernier.Ensemble.prix_m2),
   delta: pct(dep.evolution.un_an) + " sur un an",
   subs: [`${nf0.format(dep.dernier.Ensemble.ventes)} ventes ce trimestre`]},
  {label: "Prix médian d'un logement", value: euro(dep.dernier.Ensemble.prix),
   subs: ["toutes surfaces confondues"]},
  {label: "Sur cinq ans", value: pct(dep.evolution.cinq_ans),
   subs: ["évolution du prix au m²"]},
], kpiCard));
```

## Combien de m² votre capacité d'emprunt achète-t-elle ici ?

```js
// LE chiffre de la page. Il croise la capacité d'emprunt nationale (calculée sur le taux
// de crédit réel, même formule que le reste du site) et le prix local. La comparaison à
// 2015 lui donne son sens : un prix seul ne dit pas si le logement s'éloigne, « votre
// mensualité achetait X m², elle en achète Y » le dit.
if (couvert && dep.capacite) display(html`<div class="hm-capacite">
  <div class="hm-capacite-chiffre">${nf1.format(dep.capacite.m2_aujourdhui)} m²</div>
  <div class="hm-capacite-legende">
    pour <b>${nf0.format(annuaire.mensualite_ref)} € par mois</b> sur
    ${annuaire.duree_ref_ans} ans, au taux de crédit actuel
    ${dep.capacite.m2_2015 != null ? html`<br>
      contre <b>${nf1.format(dep.capacite.m2_2015)} m²</b> pour la même mensualité en 2015,
      soit ${pct((dep.capacite.m2_aujourdhui / dep.capacite.m2_2015 - 1) * 100)}` : ""}
  </div>
</div>`);
```

<div class="hm-caption">
Cette mensualité est une <b>unité de mesure</b>, pas une simulation de prêt : elle sert à
comparer les départements entre eux à conditions égales. Votre capacité réelle dépend de
votre apport, de votre taux et de votre assurance.
</div>

## Le prix au m², trimestre par trimestre

```js
if (couvert) display(multiLine({
  rows: [
    ...dep.ensemble.dates.map((d, i) => ({date: d, value: dep.ensemble.prix_m2[i], series: dep.nom})),
    ...annuaire.national.dates.map((d, i) => ({date: d, value: annuaire.national.prix_m2[i],
                                               series: "Département médian (France)"}))
  ],
  meta: [{name: dep.nom, color: series.brick},
         {name: "Département médian (France)", color: series.blue, dash: true}],
  yLabel: "Prix médian au m² (€)", valueFmt: (v) => euro(v), width,
  filename: "departement-" + dep.code + "-prix-m2"
}));
```

<div class="hm-caption">
La courbe de référence est le <b>département médian</b>, pas le prix moyen français : la
moitié des départements sont au-dessus, la moitié en dessous. Une moyenne nationale serait
écrasée par l'Île-de-France et ne dirait rien d'utile ici.
</div>

```js
// Maisons et appartements séparés : dans un département rural la médiane « ensemble » est
// celle des maisons, dans une métropole celle des appartements. Les confondre masque le
// seul écart que le lecteur regarde vraiment.
const parType = !couvert ? [] : ["maison", "appartement"]
  .filter((k) => dep[k])
  .flatMap((k) => dep[k].dates.map((d, i) => ({
    date: d, value: dep[k].prix_m2[i], series: k === "maison" ? "Maisons" : "Appartements"})));
```

```js
if (parType.length) display(html`<h2>Maisons et appartements</h2>`);
```

```js
if (parType.length) display(multiLine({
  rows: parType,
  meta: [{name: "Maisons", color: series.green}, {name: "Appartements", color: series.brick}],
  yLabel: "Prix médian au m² (€)", valueFmt: (v) => euro(v), width,
  filename: "departement-" + dep.code + "-prix-m2-par-type"
}));
```

## Combien de ventes ? Le marché est-il bloqué ?

```js
// DEUX AXES, et c'est la seule façon honnête de superposer ces deux séries : un
// département compte quelques milliers de ventes par trimestre quand la France en compte
// cent cinquante mille. Ramenées au même axe, la courbe départementale serait écrasée sur
// zéro. Le second axe autorise la comparaison des FORMES — la seule question qui vaille
// ici : est-ce que ce marché suit le pays, ou fait-il autre chose ?
//
// La série nationale vient de l'annuaire, déjà chargé pour le sélecteur : elle est
// calculée sur les MÊMES données DVF, avec le MÊME filtre et la même maille trimestrielle
// (voir `q.dvf_national_median`). Comparer un département à une France construite
// autrement n'aurait rien voulu dire.
const ventesDep = couvert
  ? dep.ensemble.dates.map((d, i) => ({date: new Date(d), value: dep.ensemble.ventes[i]}))
  : [];
const ventesNat = (annuaire.national?.dates ?? [])
  .map((d, i) => ({date: new Date(d), value: annuaire.national.ventes[i]}))
  .filter((r) => r.value != null);

// Facteur d'échelle : on aligne les MAXIMA, si bien que les deux courbes occupent la même
// hauteur et que seule leur forme se compare. L'axe de droite annule ce facteur pour
// réafficher les vrais effectifs nationaux — le lecteur n'a jamais à faire la conversion.
const kNat = (ventesDep.length && ventesNat.length)
  ? Math.max(...ventesDep.map((r) => r.value)) / Math.max(...ventesNat.map((r) => r.value))
  : 1;
```

```js
if (couvert && ventesNat.length) display(html`<div class="hm-legend hm-legend--static">${[
  {name: `${dep.nom} — ventes par trimestre (axe de gauche)`, color: series.blue},
  {name: "France entière — même méthode (axe de droite)", color: series.violet, dash: true},
].map((m) => html`<span class="hm-legend-item">
  <span class="hm-swatch" style=${m.dash
    ? {borderBottom: `2px dashed ${m.color}`, background: "transparent", height: "0", marginBottom: "3px"}
    : {background: m.color}}></span>${m.name}</span>`)}</div>`);
```

```js
if (couvert) display(ventesNat.length
  ? withCsvExport(Plot.plot({
      width, height: 340, marginLeft: 62, marginRight: 78, marginBottom: 34,
      x: {type: "utc", label: null},
      y: {label: "Ventes retenues dans le département", grid: true, zero: true,
          tickFormat: (v) => nf0.format(v)},
      marks: [
        Plot.axisY({anchor: "right", label: "France entière", labelAnchor: "top",
                    tickFormat: (v) => nf0.format(Math.round(v / kNat / 1000)) + " k",
                    stroke: series.violet, color: series.violet}),
        Plot.lineY(ventesNat, {x: "date", y: (d) => d.value * kNat, stroke: series.violet,
                               strokeWidth: 2, strokeDasharray: "5 3"}),
        Plot.lineY(ventesDep, {x: "date", y: "value", stroke: series.blue, strokeWidth: 2.4}),
        Plot.dot(ventesDep.slice(-1), {x: "date", y: "value", fill: series.blue, r: 4,
                                       stroke: "white", strokeWidth: 2}),
        Plot.crosshairX(ventesDep, {x: "date", y: "value", color: ui.subtle}),
        Plot.tip(ventesDep, Plot.pointerX({
          x: "date", y: "value", ...TIP,
          title: (d) => {
            const n = ventesNat.find((r) => +r.date === +d.date);
            return [
              fmtMonthFR(d.date),
              `${dep.nom} : ${nf0.format(d.value)} ventes`,
              n ? `France entière : ${nf0.format(n.value)} ventes` : null,
            ].filter(Boolean).join("\n");
          },
        })),
      ],
    }), ventesDep.map((r, i) => ({date: dep.ensemble.dates[i], departement: r.value,
                                  france: ventesNat.find((n) => +n.date === +r.date)?.value ?? null})),
       "departement-" + dep.code + "-ventes")
  : multiLine({
      rows: dep.ensemble.dates.map((d, i) => ({date: d, value: dep.ensemble.ventes[i],
                                               series: "Ventes par trimestre"})),
      meta: [{name: "Ventes par trimestre", color: series.blue}],
      yLabel: "Nombre de ventes retenues", valueFmt: (v) => nf0.format(v), width,
      filename: "departement-" + dep.code + "-ventes"
    }));
```

<div class="hm-caption">
Le nombre de ventes dit ce que le prix tait. Un marché où les prix tiennent mais où les
volumes s'effondrent est un marché <b>bloqué</b> : vendeurs et acheteurs n'y sont plus
d'accord, et le prix affiché est celui des rares transactions qui aboutissent.
La courbe nationale, en pointillé, sert de repère : les deux axes ont des échelles
différentes — un département pèse quelques milliers de ventes par trimestre, la France
plus de cent cinquante mille — et seules les <b>formes</b> se comparent. Un décrochage
local quand le pays tient, ou l'inverse, est ce qu'il faut y chercher.
</div>

## Qui habite ici, et qui arrive ?

<div class="hm-caption">
Le prix d'un logement dépend de qui l'occupe et de qui voudrait l'occuper. Les repères
ci-dessous décrivent le département tel que le <abbr title="Recensement de la population : enquête annuelle de l'INSEE, dont chaque millésime agrège cinq années de collecte">recensement</abbr>
le voit : l'âge de ses propriétaires — un parc détenu par des ménages âgés se transmettra
dans les quinze ans qui viennent —, la forme de son parc, la vacance, et les mouvements de
population, qui disent si l'on vient s'y installer ou si l'on en part. Chaque repère est
situé parmi les départements couverts : c'est la position qui parle, plus que la valeur.
Ils décrivent, ils ne prévoient pas.
</div>

```js
// Le profil est DESCRIPTIF, et c'est mesuré : la porte qui aurait autorisé un classement
// « France héritée / France désirée » a été manquée (les deux axes changent de signe d'un
// cycle à l'autre — voir la section des hypothèses écartées de la page de prévision).
// D'où sept repères, chacun avec son percentile et la valeur France, et aucun score.
// La valeur France vient de l'annuaire (`profil_france`, une fois pour tout le site) :
// ratio du pays (somme sur somme) pour les parts, département médian pour le solde
// migratoire et le niveau de vie — le libellé le dit à chaque fois.
const nf2 = new Intl.NumberFormat("fr-FR", {minimumFractionDigits: 2, maximumFractionDigits: 2});
const PROFIL_META = {
  part_rp_65: {label: "Résidences principales détenues par un ménage de 65 ans ou plus",
               fmt: (v) => nf1.format(v) + " %", fr: "France"},
  part_maisons: {label: "Part de maisons parmi les résidences principales",
                 fmt: (v) => nf1.format(v) + " %", fr: "France"},
  taux_vacance: {label: "Logements vacants", fmt: (v) => nf1.format(v) + " %", fr: "France"},
  part_65: {label: "Habitants de 65 ans et plus", fmt: (v) => nf1.format(v) + " %", fr: "France"},
  solde_migratoire: {label: "Solde migratoire apparent, par an",
                     fmt: (v) => (v >= 0 ? "+" : "−") + nf2.format(Math.abs(v)) + " %",
                     fr: "département médian",
                     note: "arrivées moins départs, rapportés à la population, sur la période entre deux recensements"},
  taux_arrivee: {label: "Habitants arrivés d'un autre département dans l'année",
                 fmt: (v) => nf1.format(v) + " %", fr: "France"},
  niveau_vie: {label: "Niveau de vie médian", fmt: (v) => nf0.format(v) + " € par an",
               fr: "département médian"},
};
// Le percentile est la part des AUTRES départements strictement en dessous (percent_rank :
// le département ne se compte pas lui-même — « 100 % des 100 départements » serait faux
// d'une unité). La phrase change de sens à la médiane pour que le nombre cité soit
// toujours la majorité — « plus bas que dans 98 % des autres » se lit, « plus élevé que
// dans 2 % » se relit deux fois. L'effectif couvert est dit une fois, en légende.
const position = (p) => p >= 50
  ? `plus élevé que dans ${p} % des autres départements couverts`
  : `plus bas que dans ${100 - p} % des autres départements couverts`;
```

```js
if (dep.profil) display(cardGrid(dep.profil.items.filter((it) => PROFIL_META[it.key]).map((it) => {
  const m = PROFIL_META[it.key];
  return {label: m.label, value: m.fmt(it.v),
          subs: [position(it.p),
                 annuaire.profil_france?.[it.key] != null
                   ? `${m.fr} : ${m.fmt(annuaire.profil_france[it.key])}` : null,
                 m.note].filter(Boolean)};
}), kpiCard));
```

```js
if (dep.profil) display(html`<div class="hm-caption">
  Recensement de la population, millésime ${dep.profil.millesime} — chaque millésime agrège
  cinq années de collecte, ce n'est pas la photo d'une année ; état civil et Filosofi
  (INSEE). ${Math.max(...dep.profil.items.map((it) => it.n))} départements couverts, le
  niveau de vie sur ${dep.profil.items.find((it) => it.key === "niveau_vie")?.n ?? "—"}. Le solde migratoire est dit « apparent » parce qu'il est déduit : variation de
  population moins solde naturel. Mesurés sur douze ans de prix, ces repères ont changé
  de sens d'un cycle à l'autre — c'est pourquoi ils décrivent et ne classent pas :
  <a href="/previsions#ce-qu-on-a-essaye-et-qui-ne-marche-pas">ce qu'on a essayé, et qui
  ne marche pas</a>.</div>`);
```

```js
if (!dep.profil) display(html`<div class="hm-caption">Le recensement de la population ne
  couvre pas ${dep.nom} dans les jeux de données utilisés ici (« France hors Mayotte ») :
  aucun profil n'est publié pour ce département.</div>`);
```

## Ce que ces chiffres comptent — et ce qu'ils ne comptent pas

<details class="hm-howto">
  <summary>La méthode, en clair</summary>
  <div class="hm-caption">

**D'où viennent les données.** DVF (Demandes de valeurs foncières), publié par la
DGFiP sous licence ouverte : ce sont les ventes réellement enregistrées, pas des
annonces ni des estimations.

**Ce qui est retenu.** Uniquement les mutations qualifiées de « vente » portant
sur **un seul logement** (maison ou appartement). Sont écartées : les ventes en
l'état futur d'achèvement, dont le prix n'est pas comparable à celui d'un bien
existant ; les échanges et adjudications ; les ventes portant sur plusieurs logements,
qu'aucune clé ne permet de répartir.

**Les dépendances sont conservées.** Une maison vendue avec son garage est une
vente normale, et c'est le bien que l'on compare. Le prix au m² inclut donc ces
annexes et **surestime légèrement** le logement seul. Les exclure aurait coûté les
deux tiers des ventes et déformé l'échantillon.

**Médiane, pas moyenne.** La moitié des ventes sont au-dessus, la moitié en
dessous. Une moyenne serait tirée vers le haut par quelques ventes exceptionnelles.
Les prix au m² les plus extrêmes (1 % de chaque côté, par département et par année)
sont écartés.

**Un département n'est pas un marché.** C'est la limite principale de cette
page. Entre une métropole et sa campagne, l'écart de prix peut dépasser celui entre
deux départements. La médiane départementale situe un ordre de grandeur, elle ne dit
rien du prix d'un bien précis.

**Fenêtre de publication.** DVF ne republie que les cinq dernières années ;
l'historique plus ancien a été reconstitué depuis des millésimes archivés, avec une
méthode dont l'écart mesuré sur la médiane est inférieur à 0,2 %.

  </div>
</details>

```js
if (couvert) display(html`<div class="hm-caption">
  Données jusqu'à ${trimestre(dep.dernier.Ensemble.date)} · source : ${dep.source} ·
  <a href="/a-propos">méthode et limites</a></div>`);
```

## Voir un autre département

```js
// Le sélecteur est sur CHAQUE page départementale : c'est le chemin naturel du visiteur
// qui arrive par un moteur de recherche sur un département voisin du sien.
const choix = view(Inputs.select(
  annuaire.departements.filter((d) => d.couvert).map((d) => d.code),
  {label: "Département", value: dep.code,
   format: (c) => `${c} — ${annuaire.departements.find((x) => x.code === c).nom}`}));
```

```js
if (choix !== dep.code) display(html`<a class="hm-cta" href="/departement/${choix}">
  Voir ${annuaire.departements.find((d) => d.code === choix).nom} →</a>`);
```
