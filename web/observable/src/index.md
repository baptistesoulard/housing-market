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

  Les autres pages construisent leur contenu dans le NAVIGATEUR à partir des JSON : un
  robot d'indexation qui n'exécute pas de JavaScript n'y voit presque rien, et un aperçu
  de partage (LinkedIn, Slack) n'exécute jamais de JavaScript. Le texte ci-dessous est
  donc rendu au build, en HTML : c'est le seul cadrage qu'ait un visiteur arrivé par un
  lien sans savoir ce qu'il regarde.

  L'ORDRE est celui des questions du visiteur (2026-10-04) : où en est le marché (la
  réponse, sous le titre), qu'est-ce que je peux faire ici (les tâches), à quoi ça
  ressemble (la courbe), pourquoi m'y fier, et comment revenir. La page parlait d'abord
  d'elle-même — méthode, références, catalogue des pages, et « À qui ça sert » en dernier.
  Le cœur de cible est le PROFESSIONNEL dont l'activité suit les volumes du logement ; le
  particulier arrive surtout par Google sur les fiches départementales.

  Corollaire à tenir : ce qui compte ici reste en markdown/HTML statique. Les blocs
  dynamiques (sélecteur de département, pastilles, courbe, journal des changements) sont
  des APERÇUS — s'ils ne s'affichent pas, la page dit toujours ce qu'elle a à dire.
-->

<div class="hm-hero hm-hero--band">

<p class="hm-eyebrow">Sources publiques officielles · relues chaque lundi</p>

# Où en est le marché du logement en France ?

<!--
  LA RÉPONSE — réécrite entre les marqueurs hm:reponse par web/export/accueil.py, depuis
  le verdict du modèle et le résumé de la Synthèse, et commitée par le job hebdomadaire.
  Ne pas l'éditer à la main. tests/test_web_links.py vérifie que le passage est bien
  celui que l'export écrirait.
-->
<!-- hm:reponse:début — régénéré par web/export/accueil.py -->
<div class="hm-reponse">
<p><strong>Les ventes de logements anciens devraient reculer d'environ 6 % d'ici avril 2027</strong>, dans six mois : de 956 000 à 899 000 ventes sur douze mois, selon le modèle du site. Aujourd'hui, les ventes de logements anciens plafonnent depuis 7 mois, les permis de construire reculent et le crédit renchérit (3,18 %, +0,2 pt sur un an).</p>
<p class="hm-reponse-maj">Dernier mois publié par les sources : juillet 2026. Elles paraissent avec quelques mois de décalage ; le site les relit chaque lundi.</p>
</div>
<!-- hm:reponse:fin -->

<p class="hm-lead">Le Baromètre du Logement suit les volumes du logement — permis de
construire, mises en chantier, ventes dans l'ancien — et le crédit qui les porte, à partir
des seules sources publiques. Il en tire une prévision des ventes à 12-18 mois, archivée
le jour de sa publication puis confrontée au réel.</p>

<div class="hm-actions">
  <a class="hm-btn hm-btn--onband-primary" href="/synthese">Lire la synthèse →</a>
  <a class="hm-btn hm-btn--onband" href="/previsions">La prévision à 12-18 mois</a>
  <a class="hm-btn hm-btn--onband" href="/previsions-passees">Le modèle face au réel</a>
</div>

<!--
  BANDE DE CHIFFRES — STATIQUE, comme le reste du texte de cette page. L'équivalent
  honnête des « logos clients » d'un site commercial : rassurer en deux secondes un
  visiteur qui ne connaît pas le site. Compactée le 2026-10-04 : la réponse passe avant
  les références.

  Trois sont des grandeurs LENTES, écrites à la main (profondeur d'historique, nombre de
  producteurs, cadence de rafraîchissement). Le quatrième, l'erreur du modèle, bouge à
  chaque publication : il est RÉÉCRIT entre les marqueurs hm:erreur par
  web/export/accueil.py — ne pas l'éditer à la main. Il porte l'erreur à l'horizon du
  VERDICT (« dans six mois » pour qui lit, comme la réponse ci-dessus), dit qu'il vient
  de prévisions rétro-simulées, et cite l'erreur naïve à côté : seul, le chiffre du modèle
  laisserait croire qu'il bat la référence à tous les horizons.
-->
<ul class="hm-stats">
  <!-- hm:erreur:début — régénéré par web/export/accueil.py -->
  <li>
    <span class="n">6,3 %</span>
    <span class="d">d'erreur moyenne à six mois, mesurée sur <abbr title="recalculées après coup en tronquant les données au mois visé">des prévisions rétro-simulées</abbr> depuis 2009 — une prévision naïve se trompe de 8,3 %</span>
  </li>
  <!-- hm:erreur:fin -->
  <li>
    <span class="n">6 institutions</span>
    <span class="d">INSEE, SDES, IGEDD, DGFiP, Banque de France, BCE — aucune donnée achetée</span>
  </li>
  <li>
    <span class="n">26 ans</span>
    <span class="d">d'historique continu, de décembre 2000 au dernier mois publié</span>
  </li>
  <li>
    <span class="n">Chaque lundi</span>
    <span class="d">les sources sont relues et le site reconstruit, sans intervention</span>
  </li>
</ul>

</div>

```js
// --- Votre département ---------------------------------------------------------------
// Une saisie libre plutôt qu'une liste déroulante : on tape « Rhône » ou « 69 », la liste
// de suggestions du navigateur fait le reste. La liste déroulante d'avant s'ouvrait sur
// « 01 — Ain », et son bouton invitait tout le monde dans l'Ain.
//
// Le dernier département choisi (ici, ou en ouvrant sa fiche) est RETENU dans le
// navigateur — localStorage, jamais envoyé nulle part : au retour, l'accueil propose
// d'y revenir. Une préférence d'interface, déclarée dans les mentions légales. Toute
// lecture/écriture est gardée : navigation privée ou stockage bloqué → la page marche
// sans mémoire.
const annuaireDep = await FileAttachment("./data/departements.json").json();
const DEPS = annuaireDep.departements;
const CLE_DEP = "hm-departement";
const sansAccent = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
  .replace(/[-'’]/g, " ").replace(/\s+/g, " ").trim();
const libelleDep = (d) => `${d.code} — ${d.nom}`;
function trouverDep(saisie) {
  const s = sansAccent(saisie || "");
  if (!s) return null;
  const exact = DEPS.find((d) => sansAccent(libelleDep(d)) === s
    || d.code.toLowerCase() === s || sansAccent(d.nom) === s);
  if (exact) return exact;
  const debut = DEPS.filter((d) => sansAccent(d.nom).startsWith(s));
  return s.length >= 3 && debut.length === 1 ? debut[0] : null;
}
function depRetenu() {
  try { return DEPS.find((d) => d.code === localStorage.getItem(CLE_DEP)) ?? null; }
  catch { return null; }
}
function retenirDep(d) {
  try { localStorage.setItem(CLE_DEP, d.code); } catch { /* stockage indisponible */ }
}
```

```js
const champDep = Inputs.text({
  label: "Votre département",
  placeholder: "Nom ou numéro — Rhône, 69…",
  datalist: DEPS.map(libelleDep),
  autocomplete: "off",
  width: 320,
});
// Entrée valide la saisie, comme dans un champ de recherche.
champDep.addEventListener("keydown", (e) => {
  if (e.key !== "Enter") return;
  const d = trouverDep(e.target.value);
  if (d) { retenirDep(d); location.href = `/departement/${d.code}`; }
});
const saisieDep = Generators.input(champDep);
```

```js
// Les cellules qui LISENT la saisie sont séparées de celle qui crée le champ : lue dans
// sa propre cellule, une entrée vaut le générateur, pas sa valeur (CLAUDE.md).
const depTrouve = trouverDep(saisieDep);
const depMemo = depRetenu();
const nf0Dep = new Intl.NumberFormat("fr-FR", {maximumFractionDigits: 0});
const lienDep = (d, texte) => html`<a class="hm-cta" href="/departement/${d.code}"
  onclick=${() => retenirDep(d)}>${texte}</a>`;
```

<div class="hm-dep">
  <p class="hm-dep-titre">Prix, ventes, construction et habitants de votre département —
  les 101, comparables entre eux sur la <a href="/carte">carte des départements</a>.</p>
  ${champDep}
  ${depTrouve
    ? lienDep(depTrouve, depTrouve.couvert ? `Voir la fiche — ${depTrouve.nom} →`
                                           : `${depTrouve.nom} : ce que la fiche contient →`)
    : depMemo
      ? html`<p class="hm-dep-memo">Votre dernier département : ${lienDep(depMemo,
          depMemo.prix_m2 ? `${depMemo.nom} — ${nf0Dep.format(depMemo.prix_m2)} €/m² →`
                          : `${depMemo.nom} →`)}</p>`
      : html`<span></span>`}
</div>

## Ce que vous pouvez faire ici

<!--
  Des TÂCHES, pas des publics : la navigation reste par échelle (site.config.js), et
  personne n'a à se ranger dans une case — « par exemple » donne des profils pour que
  chacun s'y reconnaisse, pas une liste fermée. Ces cartes remplacent le catalogue des
  onze pages (déjà dans la barre latérale et le pied de page) et « À qui ça sert », qui
  arrivait en dernier.
-->

<div class="hm-pages hm-taches">
  <a class="hm-page-card" href="/previsions">
    <span class="t">📡 Anticiper votre activité</span>
    <span class="d">La prévision des ventes de logements anciens à 12-18 mois, un panneau
    de scénarios à trois leviers, et le bilan de toutes les prévisions déjà publiées.</span>
    <span class="p">Par exemple : industriels des matériaux et des équipements, négoces,
    directions commerciales, planification, promoteurs.</span>
  </a>
  <a class="hm-page-card" href="/donnees">
    <span class="t">📤 Tester vos ventes contre le marché</span>
    <span class="d">Chargez vos ventes mensuelles : le site cherche quel indicateur du
    logement les précède, et de combien de mois. Votre fichier ne quitte pas votre
    navigateur.</span>
    <span class="p">Par exemple : directions commerciales, contrôle de gestion,
    planification de la demande.</span>
  </a>
  <a class="hm-page-card" href="/non-residentiel">
    <span class="t">📐 Compter en m²</span>
    <span class="d">La construction neuve en surfaces autorisées et commencées : entrepôts,
    industrie, bureaux, commerces, bâtiments agricoles et publics — et les logements.</span>
    <span class="p">Par exemple : fabricants de matériaux, de structures et d'équipements
    du bâtiment.</span>
  </a>
  <a class="hm-page-card" href="/carte">
    <span class="t">🗺️ Lire un marché local</span>
    <span class="d">Prix au m², ventes, logements et locaux mis en chantier, habitants :
    chaque département a sa fiche, et la carte les compare.</span>
    <span class="p">Par exemple : agents immobiliers, notaires, courtiers, collectivités —
    et particuliers.</span>
  </a>
  <a class="hm-page-card" href="/synthese">
    <span class="t">🧭 Citer un chiffre sourcé</span>
    <span class="d">Chaque série est datée et rattachée à sa source officielle, chaque
    graphique s'exporte en CSV, la méthode et ses limites sont publiques.</span>
    <span class="p">Par exemple : journalistes, analystes, enseignants.</span>
  </a>
</div>

## Le marché en ce moment

Trois courbes suffisent à poser le décor : les permis de construire, les mises en chantier
et les ventes de logements anciens ne tournent ni au même rythme ni toujours dans le même
sens, et c'est leur écart qui porte l'information.

```js
// Aperçu, volontairement mince : les pastilles par pilier et une courbe d'accroche. Le
// détail (chiffres clés, « à retenir », niveaux réels, filtre de période) est sur la
// Synthèse — le répliquer ici donnerait deux pages à maintenir pour un seul contenu.
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
// La même courbe croisée que la Synthèse, en base 100, réduite aux douze dernières
// années (le récent est ce qui décide de rester), sans filtre de période ni bascule de
// niveaux — ces contrôles appartiennent à la Synthèse.
//
// La base 100 et les cumuls 12 mois sont calculés côté Python sur l'historique COMPLET :
// rogner l'affichage ne rogne aucun calcul.
const accrocheRows = filterYears(
  data.chart.rows,
  [Math.max(data.period.min, data.period.max - 12), data.period.max],
).map((d) => ({date: d.date, series: d.series, value: d.index_100}))
 .filter((d) => d.value != null);
```

<div class="hm-accroche">
  <div class="hm-panel-title">Activité du logement — base 100 = ${data.chart.base_label}</div>
  ${multiLine({
    rows: accrocheRows,
    meta: data.chart.series_meta,
    yLabel: "Indice (base 100)",
    // `width` est la largeur réactive fournie par le framework : le graphique occupe
    // toute la colonne et suit le redimensionnement de la fenêtre.
    width: Math.max(320, width - 40),
    height: 300,
    baseline: 100,
    valueFmt: (v) => nf0.format(v),
  })}
</div>

<div class="hm-meta">${data.chart.source} · <a href="/synthese">niveaux réels, historique
complet et chiffres du dernier mois sur la Synthèse</a>.</div>

<div class="hm-meta">Derniers mois publiés — ${data.freshness.join(" · ")}.</div>

## Pourquoi s'y fier

<div class="hm-proof">
  <div>
    <h3>Des sources publiques, et rien d'autre</h3>
    <p>INSEE, SDES (<abbr title="Fichier du SDES qui recense les permis de construire et mises en chantier — voir le vocabulaire sur la page À propos">SIT@DEL</abbr>, <abbr title="Enquête trimestrielle du SDES sur la commercialisation des logements neufs">ECLN</abbr>), <abbr title="Inspection Générale de l'Environnement et du Développement Durable, suivi mensuel des ventes de logements anciens">IGEDD</abbr>, <abbr title="Direction générale des Finances publiques, qui publie les Demandes de valeurs foncières (DVF) : les ventes enregistrées chez le notaire">DGFiP</abbr>, Banque de France et BCE. Chaque série est
    identifiée par sa référence d'origine et récupérée par un script versionné : aucun
    chiffre n'est saisi à la main, aucune donnée n'est achetée. La <a href="/a-propos">méthode</a>,
    les sources et le code sont ouverts.</p>
  </div>
  <div>
    <h3>Un modèle qu'on peut prendre en défaut</h3>
    <p>Chaque prévision produite est <a href="/previsions-passees">archivée puis confrontée
    au réel</a>, y compris là où elle échoue : <!-- hm:bascule — régénéré par web/export/accueil.py -->sur les cinq premiers mois qui suivent le dernier chiffre publié, le modèle fait moins bien qu'une prévision naïve<!-- hm:bascule:fin -->, et la page le dit. Le score et l'incertitude sont publiés,
    pas seulement la courbe.</p>
  </div>
  <div>
    <h3>Tenu à jour tout seul</h3>
    <p>Un automate relit les sources chaque semaine et ne publie que ce qui a réellement
    changé. Le site est reconstruit dans la foulée : ce que vous lisez est l'état des
    données au dernier passage, pas une capture d'un jour.</p>
  </div>
</div>

## Revenir

Le site relit ses sources chaque lundi et ne republie que ce qui a changé : un nouveau
mois de données, une prévision qui bouge, une pastille qui change de couleur. Les derniers
changements sont datés ci-dessous — les mêmes que dans le flux RSS, à suivre dans un
lecteur de flux ou à brancher sur un canal d'équipe.

```js
// --- Le journal des changements --------------------------------------------------------
// Écrit par web/export/changements.py à chaque publication qui change quelque chose, et
// repris par scripts/postbuild.mjs dans /flux.xml. Les liens vers /flux.xml sont posés ici,
// en JavaScript, et pas en HTML statique : le framework vérifie les liens locaux du
// Markdown et ne connaît pas ce fichier, écrit après lui.
const journal = await FileAttachment("./data/changements.json").json();
const dateFr = (iso) => new Date(`${iso}T12:00:00Z`).toLocaleDateString("fr-FR",
  {day: "numeric", month: "long", year: "numeric"});
// Le prochain passage du job hebdomadaire : le lundi qui suit (aujourd'hui exclu).
const prochainLundi = (() => {
  const d = new Date();
  d.setDate(d.getDate() + (((8 - d.getDay()) % 7) || 7));
  return d.toLocaleDateString("fr-FR", {weekday: "long", day: "numeric", month: "long"});
})();
```

<div class="hm-journal">
  ${journal.entrees.slice(0, 4).map((e) => html`<div class="hm-journal-entree">
    <span class="hm-journal-date">${dateFr(e.date)}</span>
    <ul>${e.items.map((i) => html`<li>${i}</li>`)}</ul>
  </div>`)}
</div>

<div class="hm-meta">Prochain passage : ${prochainLundi}.</div>

<div class="hm-shortcuts">
  <span class="lead">Suivre :</span>
  ${html`<a class="hm-shortcut" href="/flux.xml">📶 Flux RSS</a>`}
  <a class="hm-shortcut" href="https://www.linkedin.com/in/baptistesoulard1994">💼 L'auteur sur LinkedIn</a>
  <a class="hm-shortcut" href="/a-propos#me-contacter">✉️ Me contacter</a>
</div>
