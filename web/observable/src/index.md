---
title: HousingMarket — Marché du logement en France
toc: false
---

```js
import {status} from "./components/theme.js";
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

<div class="hm-hero">

# Où en est le marché du logement en France ?

<div class="hm-rule"></div>

<p class="hm-lead">HousingMarket met en regard la construction neuve, les ventes dans
l'ancien, les prix et les conditions de financement — puis en tire une prévision des
transactions à 12-18 mois. Toutes les séries proviennent de sources publiques
officielles, rafraîchies automatiquement chaque semaine.</p>

<div class="hm-actions">
  <a class="hm-btn hm-btn--primary" href="/synthese">Voir la synthèse du marché →</a>
  <a class="hm-btn" href="/a-propos">La méthode</a>
  <a class="hm-btn" href="https://github.com/baptistesoulard/housing-market">Le code source</a>
</div>

</div>

## Le marché en ce moment

```js
// Aperçu, volontairement mince : les pastilles par pilier et la fraîcheur des sources.
// Le détail (chiffres clés, « à retenir », graphique croisé) est sur la Synthèse — le
// répliquer ici donnerait deux pages à maintenir pour un seul contenu.
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
    <span class="d">D'où vient chaque série, à quelle date elle s'arrête, et de quoi
    confronter vos propres ventes aux indicateurs de marché.</span>
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
