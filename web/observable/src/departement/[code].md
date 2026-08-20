---
title: Prix de l'immobilier par département
toc: false
---

```js
import {multiLine, cardGrid, kpiCard, nf0, nf1} from "../components/hm.js";
import {series, ui} from "../components/theme.js";
```

```js
// Chargement par fetch(), PAS par FileAttachment — et ce n'est pas un choix de style.
// FileAttachment est résolu au BUILD : le framework lit le nom du fichier dans le code
// source pour savoir quoi copier dans dist/. Avec un nom construit à partir du paramètre
// de route (`../data/departements/${code}.json`), il n'y a rien à lire, donc rien n'est
// copié — vérifié : la page se construit et dist/_file/data/departements/ reste vide.
//
// Les données sont donc copiées à part par scripts/postbuild.mjs, à une adresse STABLE
// (/data/departements/<code>.json), et lues ici au chargement de la page.
const code = observable.params.code;
const dep = await fetch(`/data/departements/${code}.json`).then((r) => r.json());
const index = await fetch("/data/departements.json").then((r) => r.json());
```

```js
const euro = (v) => v == null ? "—" : nf0.format(v) + " €";
const pct = (v) => v == null ? "—" : (v >= 0 ? "+" : "−") + nf1.format(Math.abs(v)) + " %";
// Les dates de l'agrégat sont des débuts de trimestre : « 2025-10-01 » se lit « T4 2025 ».
const trimestre = (iso) => `T${Math.floor(Number(iso.slice(5, 7)) / 3) + 1} ${iso.slice(0, 4)}`;
```

<div class="hm-dep-head">
  <h1>Prix de l'immobilier · ${dep.nom} (${dep.code})</h1>
  <div class="hm-caption">${dep.region} · d'après les ventes réellement enregistrées
  chez le notaire (DVF, DGFiP)</div>
</div>

```js
// Le cas « non couvert » est traité EN PREMIER et arrête la page. Quatre départements
// sont concernés et ils n'ont pas à recevoir une page de graphiques vides qui passerait
// pour une panne du site.
display(dep.couvert ? html`` : html`<div class="hm-absence">
  <div class="hm-absence-titre">Aucune donnée de prix pour ce département</div>
  <p>${dep.absence}</p>
  <p>Les autres pages du site restent valables : elles portent sur la France entière,
  <a href="/ancien">y compris les prix nationaux</a> et
  <a href="/macro">les conditions de financement</a>, qui ne dépendent pas de DVF.</p>
</div>`);
```

```js
// Tout ce qui suit n'a de sens que pour un département couvert.
const ok = dep.couvert === true;
```

```js
display(!ok ? html`` : cardGrid([
  {label: `Prix médian au m² · ${trimestre(dep.dernier.Ensemble.date)}`,
   value: euro(dep.dernier.Ensemble.prix_m2),
   delta: pct(dep.evolution.un_an) + " sur un an",
   subs: [`${nf0.format(dep.dernier.Ensemble.ventes)} ventes ce trimestre`]},
  {label: "Prix médian d'un logement",
   value: euro(dep.dernier.Ensemble.prix),
   subs: ["toutes surfaces confondues"]},
  {label: "Sur cinq ans",
   value: pct(dep.evolution.cinq_ans),
   subs: ["évolution du prix au m²"]},
], kpiCard));
```

## Combien de m² votre capacité d'emprunt achète-t-elle ici ?

```js
// LE chiffre de la page. Il croise la capacité d'emprunt nationale (calculée à partir du
// taux de crédit réel, même formule que le reste du site) et le prix local. La
// comparaison à 2015 est ce qui lui donne son sens : un prix seul ne dit pas si le
// logement s'éloigne, « votre mensualité achetait X m², elle en achète Y » le dit.
display(!ok || !dep.capacite ? html`` : html`<div class="hm-capacite">
  <div class="hm-capacite-chiffre">${nf1.format(dep.capacite.m2_aujourdhui)} m²</div>
  <div class="hm-capacite-legende">
    pour <b>${nf0.format(index.mensualite_ref)} € par mois</b> sur
    ${index.duree_ref_ans} ans, au taux de crédit actuel
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
display(!ok ? html`` : multiLine({
  rows: [
    ...dep.ensemble.dates.map((d, i) => ({
      date: d, value: dep.ensemble.prix_m2[i], series: dep.nom})),
    ...index.national.dates.map((d, i) => ({
      date: d, value: index.national.prix_m2[i], series: "Département médian (France)"}))
  ],
  meta: [{name: dep.nom, color: series.brick},
         {name: "Département médian (France)", color: series.blue, dash: true}],
  yLabel: "Prix médian au m² (€)", valueFmt: (v) => euro(v), tipUnit: ""
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
const parType = !ok ? [] : ["maison", "appartement"]
  .filter((k) => dep[k])
  .flatMap((k) => dep[k].dates.map((d, i) => ({
    date: d, value: dep[k].prix_m2[i],
    series: k === "maison" ? "Maisons" : "Appartements"})));
```

```js
display(!parType.length ? html`` : html`
  <h2>Maisons et appartements</h2>
  ${multiLine({
    rows: parType,
    meta: [{name: "Maisons", color: series.green},
           {name: "Appartements", color: series.brick}],
    yLabel: "Prix médian au m² (€)", valueFmt: (v) => euro(v)
  })}`);
```

## Combien de ventes ? Le marché est-il bloqué ?

```js
display(!ok ? html`` : multiLine({
  rows: dep.ensemble.dates.map((d, i) => ({
    date: d, value: dep.ensemble.ventes[i], series: "Ventes par trimestre"})),
  meta: [{name: "Ventes par trimestre", color: series.blue}],
  yLabel: "Nombre de ventes retenues", valueFmt: (v) => nf0.format(v)
}));
```

<div class="hm-caption">
Le nombre de ventes dit ce que le prix tait. Un marché où les prix tiennent mais où les
volumes s'effondrent est un marché <b>bloqué</b> : vendeurs et acheteurs n'y sont plus
d'accord, et le prix affiché est celui des rares transactions qui aboutissent.
</div>

## Ce que ces chiffres comptent — et ce qu'ils ne comptent pas

<details class="hm-howto">
  <summary>La méthode, en clair</summary>
  <div class="hm-caption">
    <p><b>D'où viennent les données.</b> DVF (Demandes de valeurs foncières), publié par la
    DGFiP sous licence ouverte : ce sont les ventes réellement enregistrées, pas des
    annonces ni des estimations.</p>

    <p><b>Ce qui est retenu.</b> Uniquement les mutations qualifiées de « vente » portant
    sur <b>un seul logement</b> (maison ou appartement). Sont écartées : les ventes en
    l'état futur d'achèvement, dont le prix n'est pas comparable à celui d'un bien
    existant ; les échanges et adjudications ; les ventes portant sur plusieurs logements,
    qu'aucune clé ne permet de répartir.</p>

    <p><b>Les dépendances sont conservées.</b> Une maison vendue avec son garage est une
    vente normale, et c'est le bien que l'on compare. Le prix au m² inclut donc ces
    annexes et <b>surestime légèrement</b> le logement seul. Les exclure aurait coûté
    les deux tiers des ventes et déformé l'échantillon.</p>

    <p><b>Médiane, pas moyenne.</b> La moitié des ventes sont au-dessus, la moitié en
    dessous. Une moyenne serait tirée vers le haut par quelques ventes exceptionnelles.
    Les prix au m² les plus extrêmes (1 % de chaque côté, par département et par année)
    sont écartés.</p>

    <p><b>Un département n'est pas un marché.</b> C'est la limite principale de cette
    page. Entre une métropole et sa campagne, l'écart de prix peut dépasser celui entre
    deux départements. La médiane départementale situe un ordre de grandeur, elle ne dit
    rien du prix d'un bien précis.</p>

    <p><b>Fenêtre de publication.</b> DVF ne republie que les cinq dernières années ;
    l'historique plus ancien a été reconstitué depuis des millésimes archivés, avec une
    méthode dont l'écart mesuré sur la médiane est inférieur à 0,2 %.</p>
  </div>
</details>

```js
display(!ok ? html`` : html`<div class="hm-caption">
  Données jusqu'à ${trimestre(dep.dernier.Ensemble.date)} · source : ${dep.source} ·
  <a href="/a-propos">méthode et limites</a>
</div>`);
```

## Voir un autre département

```js
// Le sélecteur est présent sur CHAQUE page départementale : c'est le chemin naturel du
// visiteur qui arrive par un moteur de recherche sur un département voisin du sien.
const choix = view(Inputs.select(
  index.departements.filter((d) => d.couvert).map((d) => d.code),
  {label: "Département", value: code,
   format: (c) => {
     const d = index.departements.find((x) => x.code === c);
     return `${c} — ${d.nom}`;
   }}));
```

```js
display(choix === code ? html`` : html`<a class="hm-cta" href="/departement/${choix}">
  Voir ${index.departements.find((d) => d.code === choix).nom} →</a>`);
```
