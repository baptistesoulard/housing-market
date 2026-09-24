---
title: Carte des départements
toc: true
---

```js
import {carteDepartements, nuageDepartements, formatMesure} from "./components/hm.js";
const geo = await FileAttachment("./data/departements-geo.json").json();
const data = await FileAttachment("./data/carte.json").json();
```

<!--
  TITRE ET CHAPEAU STATIQUES — rendus au build. Les cartes et les nuages sont dessinés dans
  le navigateur : un robot n'en voit rien. Ce texte, et le tableau des 101 départements en
  bas de page (écrit par scripts/postbuild.mjs à chaque build), sont ce qu'il lit.
  Aucun chiffre ici : rien ne régénère ce paragraphe (voir CLAUDE.md, « Texte statique :
  aucun chiffre, aucun état »).
-->

# 🗺️ Carte des départements

Les départements côte à côte : ce que coûte un mètre carré, comment les prix ont bougé,
combien de logements se vendent pour mille habitants, et qui y habite. Chaque carte
colorie une seule mesure, publiée par un organisme public — les prix et les ventes par la
DGFiP (<abbr title="Demandes de valeurs foncières : les ventes enregistrées chez le notaire">DVF</abbr>),
le profil des habitants par le recensement de l'INSEE. Survolez un département pour sa
valeur et son rang parmi les autres ; cliquez pour ouvrir sa page.

Rien ici n'est un score ni un classement de « gagnants » : la page décrit ce qui est
observé, pas où le marché ira. La dernière section montre pourquoi, en confrontant une idée
séduisante — les départements âgés perdraient, les départements attractifs gagneraient —
aux prix réellement enregistrés sur deux périodes successives.

## Une mesure à la fois

<div class="hm-caption">
Une teinte unique, du clair au foncé, pour une grandeur : chaque classe regroupe à peu près
autant de départements, pour que les écarts restent visibles au lieu d'être écrasés par
Paris. Deux teintes de part et d'autre d'un gris pour une évolution : brique en baisse,
bleu en hausse, gris autour de zéro. Aucune couleur ne dit « bien » ou « mal ». Les
départements sans valeur sont hachurés. L'outre-mer est en encarts, hors échelle, et Paris
et la petite couronne sont agrandis au nord-est.
</div>

```js
const MESURES = data.indicateurs;
const RANG_MESURE = new Map(MESURES.map((m, i) => [m.key, i]));

// Les valeurs d'une mesure, par département : le JSON est colonnaire (un tableau de
// valeurs par département, dans l'ordre du catalogue), recomposé ici.
function valeursDe(m) {
  const i = RANG_MESURE.get(m.key);
  return new Map(data.departements.map((d) => [d.code,
    {nom: d.nom, couvert: d.couvert, v: d.v[i], p: d.p[i]}]));
}

const mesureInput = Inputs.select(MESURES, {label: "Mesure affichée",
  format: (m) => m.label, value: MESURES[0]});
const mesure = view(mesureInput);
```

```js
display(carteDepartements({geo, valeurs: valeursDe(mesure), mesure,
                           width: Math.min(width, 760)}));
const fmtMesure = formatMesure(mesure.unite);
display(html`<div class="hm-meta">${mesure.periode} · source : ${mesure.source}${
  mesure.ref != null ? ` · ${mesure.ref_libelle} : ${fmtMesure(mesure.ref)}` : ""} ·
  ${mesure.n} départements renseignés.${mesure.note ? ` Note : ${mesure.note}.` : ""}</div>`);
```

<div class="hm-meta">Fond de carte : contours administratifs d'Etalab (IGN Admin Express),
Licence ouverte 2.0, simplifiés pour le web.</div>

## Deux mesures face à face

<div class="hm-caption">
Chaque point est un département. Les deux lignes pointillées marquent les médianes : elles
découpent les départements en quatre groupes, sans en désigner aucun — c'est au lecteur de
dire ce qu'il y voit. Un nuage qui penche montre que deux mesures vont ensemble sur la
période observée ; il ne dit pas que l'une cause l'autre, ni qu'elles iront encore ensemble
demain.
</div>

```js
const axeX = Inputs.select(MESURES, {label: "En abscisse", format: (m) => m.label,
  value: MESURES.find((m) => m.key === "prix_m2")});
const axeY = Inputs.select(MESURES, {label: "En ordonnée", format: (m) => m.label,
  value: MESURES.find((m) => m.key === "evol_5ans")});
display(html`<div class="hm-choix">${axeX}${axeY}</div>`);
const mesureX = Generators.input(axeX);
const mesureY = Generators.input(axeY);
```

```js
const vx = valeursDe(mesureX), vy = valeursDe(mesureY);
const pointsFace = data.departements
  .map((d) => ({code: d.code, nom: d.nom, x: vx.get(d.code).v, y: vy.get(d.code).v}))
  .filter((d) => d.x != null && d.y != null);
display(nuageDepartements({
  points: pointsFace, xLabel: mesureX.label, yLabel: mesureY.label,
  fmtX: formatMesure(mesureX.unite), fmtY: formatMesure(mesureY.unite),
  xLog: mesureX.unite === "euro", yLog: mesureY.unite === "euro",
  width: Math.min(width, 760), etiquettes: ["75", "23"]}));
display(html`<div class="hm-meta">${pointsFace.length} départements renseignés pour les deux
  mesures · ${mesureX.periode} / ${mesureY.periode}.</div>`);
```

## L'âge des propriétaires et les prix : une relation qui s'est retournée

Une idée revient souvent : dans les départements âgés, où beaucoup de logements
appartiennent à des ménages de plus de soixante-cinq ans, les prix décrocheraient à mesure
que ces logements seront hérités puis vendus, pendant que les départements qui attirent des
habitants monteraient. Avant de la mettre en carte, nous l'avons mesurée sur les prix
réellement enregistrés chez le notaire, sur deux périodes consécutives, en partant à chaque
fois du recensement publié au début de la période.

Chaque point est un département : à gauche les plus jeunes, à droite les plus âgés ; en
haut ceux dont les prix ont le plus progressé par rapport au département médian. L'indice
d'âge du parc multiplie la part de propriétaires par la part des habitants de soixante-cinq
ans et plus : le recensement ne croise l'âge et le statut d'occupation que depuis peu, et ce
produit classe les départements presque exactement comme la mesure directe. La droite
résume la tendance de chaque période.

```js
const R = data.retournement;
const tousX = R.fenetres.flatMap((f) => f.points.map((p) => p.x));
const tousY = R.fenetres.flatMap((f) => f.points.map((p) => p.y));
const signeRho = (r) => (r > 0 ? "+" : r < 0 ? "−" : "") + Math.abs(r).toFixed(2).replace(".", ",");
const sens = (r) => (r <= -0.2 ? "moins que les autres"
  : r >= 0.2 ? "plus que les autres" : "ni plus ni moins que les autres");
const largeurPanneau = Math.max(300, Math.min(460, Math.floor(width / 2) - 16));
const fmtIndice = (v) => v.toFixed(0) + " %";
const fmtEcart = (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(0) + " pts";
display(html`<div class="hm-panels">${R.fenetres.map((f) => html`<div>
  <div class="hm-panel-title">Prix ${f.debut} → ${f.fin}, parc du recensement ${f.millesime}</div>
  <div class="hm-panel-sub">corrélation de rang : ${signeRho(f.rho)} · ${f.n} départements</div>
  ${nuageDepartements({points: f.points, xLabel: "Indice d'âge du parc",
    yLabel: "Écart de croissance du prix", fmtX: fmtIndice, fmtY: fmtEcart,
    medianes: false, tendance: true, zeroY: true, width: largeurPanneau, height: 340,
    xDomain: [Math.min(...tousX), Math.max(...tousX)],
    yDomain: [Math.min(...tousY), Math.max(...tousY)], etiquettes: ["75", "23"]})}
</div>`)}</div>`);
display(html`<p>${R.fenetres.map((f, i) => `${i ? " " : ""}Entre ${f.debut} et ${f.fin}, les
  prix des départements âgés ont progressé ${sens(f.rho)} (corrélation de rang
  ${signeRho(f.rho)}).`).join("")}</p>`);
```

Une relation qui change de sens d'une période à l'autre ne dit pas où iront les prix dans
quinze ans : elle dit dans quel cycle on se trouve. Sur la première période, les
départements âgés étaient surtout les moins chers, à une époque où les métropoles chères
décrochaient du reste du pays ; sur la seconde, le Covid, le littoral puis la correction des
grandes villes ont inversé l'ordre. C'est pourquoi cette page décrit et ne classe pas, et
pourquoi l'idée figure parmi
[ce que nous avons essayé, et qui ne marche pas](/previsions#ce-qu-on-a-essaye-et-qui-ne-marche-pas).

## Les départements en tableau

Les mêmes chiffres, sans carte : le prix médian au mètre carré du dernier trimestre publié
et son évolution sur un an, département par département. Chaque nom ouvre la page du
département, avec son historique complet et son profil.

<details class="hm-howto">
<summary>Afficher le tableau des départements</summary>
<!-- hm:tableau-departements — écrit par scripts/postbuild.mjs à chaque build --><!-- hm:tableau-departements:fin -->
</details>
