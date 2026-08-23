---
title: Baromètre du Logement — marché immobilier français
toc: false
---

```js
import {status} from "./components/theme.js";
import {multiLine, nf0, filterYears} from "./components/hm.js";
const data = await FileAttachment("./data/synthese.json").json();
```

<!--
  PAGE D'ACCUEIL — écrite, pas calculée.

  Les sept autres pages construisent leur contenu dans le NAVIGATEUR à partir des JSON :
  un robot d'indexation qui n'exécute pas de JavaScript n'y voit presque rien, et un
  aperçu de partage (LinkedIn, Slack) n'exécute jamais de JavaScript. Le texte ci-dessous
  est donc rendu au build, en HTML : c'est le seul contenu du site que ces robots lisent,
  et le seul cadrage qu'ait un visiteur arrivé par un lien sans savoir ce qu'il regarde.

  Corollaire à tenir : ce qui compte ici reste en markdown/HTML statique. Le bloc
  dynamique plus bas (pastilles d'état, fraîcheur) est un APERÇU — s'il ne s'affiche pas,
  la page dit toujours ce qu'elle a à dire.
-->

<div class="hm-hero hm-hero--band">

<p class="hm-eyebrow">Sources publiques officielles · rafraîchies chaque semaine</p>

# Où en est le marché du logement en France ?

<p class="hm-lead">Le Baromètre du Logement met en regard la construction neuve, les
ventes dans l'ancien, les prix et les conditions de financement — puis en tire une
prévision des transactions à 12-18 mois. Chacune est archivée le jour de sa publication, puis
confrontée au réel.</p>

<div class="hm-actions">
  <a class="hm-btn hm-btn--onband-primary" href="/synthese">Voir la synthèse du marché →</a>
  <a class="hm-btn hm-btn--onband" href="/previsions-passees">Le modèle face au réel</a>
  <a class="hm-btn hm-btn--onband" href="/a-propos">La méthode</a>
</div>

<!--
  BANDE DE CHIFFRES — volontairement STATIQUE, comme le reste du texte de cette page.

  Ces quatre nombres sont l'équivalent honnête des « logos clients » d'un site
  commercial : ils doivent rassurer en deux secondes un visiteur qui ne connaît pas le
  site, et être lus par les robots d'aperçu de partage, qui n'exécutent pas de
  JavaScript. Les calculer dans le navigateur les rendrait invisibles là où ils comptent.

  Contrepartie assumée : ils ne se mettent pas à jour tout seuls. Ils ont donc été
  choisis parmi les grandeurs LENTES (profondeur d'historique, nombre de producteurs,
  cadence de rafraîchissement) — et le seul qui bouge, l'erreur moyenne à 6 mois, est
  verrouillé par tests/test_web_links.py, qui le compare au KPI d'archive.json et
  échoue s'il dérive. Ne pas modifier la valeur ici sans relancer ce test.

  L'erreur naïve est citée à côté de l'erreur du modèle, et ce n'est pas une coquetterie :
  publier le seul chiffre du modèle laisserait croire qu'il bat la référence à tous les
  horizons, alors qu'il lui est inférieur en deçà de 4 mois (voir /previsions-passees).
-->
<ul class="hm-stats">
  <li>
    <span class="n">26 ans</span>
    <span class="d">d'historique continu, de décembre 2000 au dernier mois publié</span>
  </li>
  <li>
    <span class="n">5 institutions</span>
    <span class="d">INSEE, SDES, IGEDD, Banque de France, BCE — aucune donnée achetée</span>
  </li>
  <li>
    <span class="n">4,1 %</span>
    <span class="d">d'erreur moyenne à 6 mois — une prévision naïve se trompe de 7,2 %</span>
  </li>
  <li>
    <span class="n">Chaque lundi</span>
    <span class="d">les sources sont récupérées et le site reconstruit, sans intervention</span>
  </li>
</ul>

</div>

## Le marché en ce moment

Trois courbes suffisent à poser le décor : les permis de construire, les mises en chantier
et les ventes de logements anciens ne tournent ni au même rythme ni toujours dans le même
sens, et c'est leur écart qui porte l'information.

```js
// Aperçu, volontairement mince : les pastilles par pilier, une courbe d'accroche et la
// fraîcheur des sources. Le détail (chiffres clés, « à retenir », niveaux réels, filtre
// de période) est sur la Synthèse — le répliquer ici donnerait deux pages à maintenir
// pour un seul contenu.
function chip(p) {
  const {bg, fg} = status[p.status] || status.unknown;
  return html`<span style=${{
    background: bg, color: fg, borderRadius: "16px", padding: "6px 14px",
    marginRight: "10px", fontWeight: 600, fontSize: "1.02rem",
    display: "inline-block", marginBottom: "6px",
  }}>${p.dot} ${p.label} · ${p.word}</span>`;
}
```

<div class="hm-chips">${data.pillars.map(chip)}</div>

```js
// --- Courbe d'accroche ---------------------------------------------------------------
// Un site de données dont la page d'accueil ne montre aucune donnée demande au visiteur
// de cliquer sur la foi d'un texte. C'est la même courbe croisée que la Synthèse, en
// base 100 : réduite aux douze dernières années (le récent est ce qui décide de rester),
// sans filtre de période ni bascule de niveaux — ces contrôles appartiennent à la
// Synthèse, les dupliquer ici ferait deux pages à tenir.
//
// La base 100 et les cumuls 12 mois sont calculés côté Python sur l'historique COMPLET :
// rogner l'affichage ne rogne aucun calcul.
const accrocheRows = filterYears(
  data.chart.rows,
  [Math.max(data.period.min, data.period.max - 12), data.period.max],
).map((d) => ({date: d.date, series: d.series, value: d.index_100}))
 .filter((d) => d.value != null);

// Légende NON interactive : sur cette page il n'y a rien à masquer. Des pastilles qui
// changent d'apparence au survol promettraient un contrôle qui n'existe pas (voir
// .hm-legend--static dans le thème).
const accrocheLegend = html`<div class="hm-legend hm-legend--static">${
  data.chart.series_meta.map((m) => html`<span class="hm-legend-item">
    <span class="hm-swatch" style=${{background: m.color}}></span>${m.name}</span>`)
}</div>`;
```

<div class="hm-accroche">
  <div class="hm-panel-title">Activité du logement — base 100 = ${data.chart.base_label}</div>
  ${accrocheLegend}
  ${multiLine({
    rows: accrocheRows,
    meta: data.chart.series_meta,
    yLabel: "Indice (base 100)",
    // `width` est la largeur réactive fournie par le framework : le graphique occupe
    // toute la colonne et suit le redimensionnement de la fenêtre. Sans elle, Plot s'en
    // tiendrait à ses 640 px par défaut, flottants dans un panneau de 900.
    width: Math.max(320, width - 40),
    height: 300,
    baseline: 100,
    valueFmt: (v) => nf0.format(v),
  })}
</div>

<div class="hm-meta">${data.chart.source} · <a href="/synthese">niveaux réels, historique
complet et chiffres du dernier mois sur la Synthèse</a>.</div>

<div class="hm-meta">Dernières données publiées — ${data.freshness.join(" · ")}.</div>

<div class="hm-shortcuts">
  <span class="lead">Le détail :</span>
  <a class="hm-shortcut" href="/synthese">🧭 Synthèse</a>
  <a class="hm-shortcut" href="/previsions">📡 Prévision & Scénarios</a>
</div>

## Pourquoi s'y fier

<div class="hm-proof">
  <div>
    <h3>Des sources publiques, et rien d'autre</h3>
    <p>INSEE, SDES (SIT@DEL, ECLN), IGEDD, Banque de France et BCE. Chaque série est
    identifiée par sa référence d'origine et récupérée par un script versionné : aucun
    chiffre n'est saisi à la main, aucune donnée n'est achetée.</p>
  </div>
  <div>
    <h3>Un modèle qu'on peut prendre en défaut</h3>
    <p>Chaque prévision produite est <a href="/previsions-passees">archivée puis confrontée
    au réel</a>, y compris là où elle échoue : à moins de quatre mois, le modèle fait moins
    bien qu'une prévision naïve, et la page le dit. Le score et l'incertitude sont publiés,
    pas seulement la courbe.</p>
  </div>
  <div>
    <h3>Tenu à jour tout seul</h3>
    <p>Un automate rafraîchit les sources chaque semaine et ne publie que ce qui a
    réellement changé. Le site est reconstruit dans la foulée : ce que vous lisez est
    l'état des données au dernier passage, pas une capture d'un jour.</p>
  </div>
</div>

## Les huit pages

<div class="hm-pages">
  <a class="hm-page-card" href="/synthese">
    <span class="t">🧭 Synthèse</span>
    <span class="d">L'état des trois piliers — neuf, ancien, financement — et les
    chiffres clés du dernier mois publié.</span>
  </a>
  <a class="hm-page-card" href="/neuf">
    <span class="t">🏗️ Marché du neuf</span>
    <span class="d">Permis et mises en chantier, individuel contre collectif, puis la
    commercialisation : encours, délai d'écoulement, acquéreurs, prix au m².</span>
  </a>
  <a class="hm-page-card" href="/ancien">
    <span class="t">🏠 Marché de l'ancien</span>
    <span class="d">Volumes de ventes, prix Notaires-INSEE, et ce que le pouvoir d'achat
    immobilier des ménages devient à mensualité constante.</span>
  </a>
  <a class="hm-page-card" href="/macro">
    <span class="t">🏦 Environnement & Financement</span>
    <span class="d">Taux, Euribor, OAT, confiance des ménages, intentions d'achat,
    chômage, production et demande de crédits habitat.</span>
  </a>
  <a class="hm-page-card" href="/actualites">
    <span class="t">📰 Actualités & Aides</span>
    <span class="d">Les dispositifs en vigueur et à venir, leur impact par pilier et leur
    échéancier.</span>
  </a>
  <a class="hm-page-card" href="/previsions">
    <span class="t">📡 Prévision & Scénarios</span>
    <span class="d">La projection des transactions à 12-18 mois, son backtest, et un
    panneau de scénarios à quatre leviers.</span>
  </a>
  <a class="hm-page-card" href="/previsions-passees">
    <span class="t">🎯 Prévisions passées</span>
    <span class="d">Toutes les prévisions déjà produites, face à ce qui s'est réellement
    passé — et à partir de quel horizon le modèle bat une prévision naïve.</span>
  </a>
  <a class="hm-page-card" href="/donnees">
    <span class="t">⚙️ Données & Sources</span>
    <span class="d">De quoi confronter vos propres ventes aux indicateurs de marché,
    sans que votre fichier quitte votre navigateur.</span>
  </a>
</div>

## À qui ça sert

Le marché du logement se lit rarement d'un seul chiffre : les permis de construire, les
ventes dans l'ancien et le coût du crédit ne tournent ni au même rythme ni dans le même
sens, et c'est leur décalage qui porte l'information. Ce site rassemble ces séries au même
endroit, sur la même période, avec les mêmes conventions de calcul — puis va jusqu'au bout
de l'exercice en publiant une prévision datée et vérifiable plutôt qu'un commentaire.

Il s'adresse à qui doit anticiper une activité liée au logement — second œuvre, matériaux,
financement, aménagement — et à qui veut simplement suivre le marché sans reconstituer
lui-même dix séries publiques. La [méthode](/a-propos), les sources et le code sont
ouverts : les chiffres sont là pour être contredits.

<div class="hm-note">
  <p><strong>Deux pages ont besoin d'un serveur.</strong> Prévision & Scénarios et
  Données & Sources relancent un calcul à chaque question posée : elles interrogent une
  petite API HTTP plutôt qu'un fichier figé. Sans instance de cette API, elles affichent
  un encart qui explique comment en lancer une — les cinq autres pages fonctionnent en
  toute autonomie.</p>
</div>
