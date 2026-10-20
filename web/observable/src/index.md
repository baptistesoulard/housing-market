---
title: Baromètre du Logement — marché immobilier français
toc: false
---

```js
import {status, bandeau} from "./components/theme.js";
import {multiLine, nf0, filterYears, fmtMonthFR, periodeFR, Plot, TIP, d3} from "./components/hm.js";
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

  Depuis le 2026-10-20, elle s'ouvre sur UN chiffre (la variation annoncée) et partage la
  ligne avec la courbe de la prévision : la phrase de soixante mots qu'elle était se
  lisait mal en entier et pas du tout en diagonale. Aucune ligne vide dans la grille
  ci-dessous : une ligne vide fermerait le bloc HTML et la courbe sortirait de la grille.
-->
<div class="hm-hero-grille">
<!-- hm:reponse:début — régénéré par web/export/accueil.py -->
<div class="hm-reponse">
<p class="hm-reponse-chiffre"><span class="n">−5 %</span> <span class="l"><strong>de ventes de logements anciens d'ici avril 2027</strong>, dans six mois : de 951 000 à 902 000 ventes sur douze mois, selon le modèle du site.</span></p>
<p>Aujourd'hui, les ventes de logements anciens plafonnent depuis 9 mois, les permis de construire reculent et le crédit renchérit (3,20 %, +0,2 pt sur un an).</p>
<p class="hm-reponse-maj">Dernier mois publié par les sources : août 2026 — elles paraissent avec quelques mois de décalage.</p>
</div>
<!-- hm:reponse:fin -->
${courbeBandeau}
</div>

<p class="hm-lead">Le Baromètre du Logement suit les permis, les chantiers, les ventes dans
l'ancien et le crédit, à partir des seules sources publiques, et en tire une prévision des
ventes à 12-18 mois — archivée le jour même, puis confrontée au réel.</p>

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
    <span class="n">6,1 %</span>
    <span class="d">d'erreur moyenne pour une échéance comme avril 2027 (<abbr title="recalculées après coup en tronquant les données au mois visé">prévisions rétro-simulées</abbr> depuis 2009) ; 7,5 % pour une prévision naïve</span>
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
// --- La courbe du bandeau -------------------------------------------------------------
// La réponse du titre, dessinée : les ventes réalisées depuis 2019, puis la prévision du
// modèle jusqu'au mois du verdict, avec sa fourchette. Un APERÇU, comme les autres blocs
// dynamiques de la page : si elle ne s'affiche pas, le chiffre à côté dit déjà tout, et
// c'est lui que lisent les robots. Couleurs : jeton `bandeau` de theme.json (la rampe des
// séries manque de contraste sur ce fond). La trajectoire vient de synthese.json, que la
// page charge déjà — pas de previsions.json, trois fois plus lourd, sur la page d'entrée.
const TRAJ = data.trajectoire ?? null;
const realiseBandeau = data.chart.rows
  .filter((r) => r.key === "transactions" && r.level_k != null && r.date >= "2019-01-01")
  .map((r) => ({date: new Date(r.date), v: r.level_k * 1000}));
function traceBandeau(w) {
  const der = realiseBandeau[realiseBandeau.length - 1];
  const prev = [{date: der.date, v: der.v, lo: der.v, hi: der.v},
    ...TRAJ.trajet.map((p) => ({date: new Date(p.date), v: p.predicted, lo: p.lo, hi: p.hi}))];
  const cible = prev[prev.length - 1];
  const k = (v) => `${nf0.format(v / 1000)} k`;
  const y0 = realiseBandeau[0].date.getUTCFullYear(), y1 = cible.date.getUTCFullYear();
  const pas = w < 420 ? 2 : 1;
  const annees = d3.range(y0, y1 + 1, pas).map((a) => new Date(Date.UTC(a, 0, 1)));
  const survol = [...realiseBandeau.map((d) => ({...d, quoi: "réalisé"})),
                  ...prev.slice(1).map((d) => ({...d, quoi: "prévision"}))];
  return Plot.plot({
    width: w, height: Math.round(Math.min(250, Math.max(190, w * 0.52))),
    marginLeft: 46, marginRight: 14, marginTop: 30, marginBottom: 26,
    style: {color: bandeau.texte, background: "transparent", fontSize: "12px"},
    x: {label: null, ticks: annees, tickFormat: (d) => String(d.getUTCFullYear()), tickSize: 0},
    y: {label: null, ticks: 4, tickFormat: k, tickSize: 0},
    marks: [
      Plot.gridY({ticks: 4, stroke: bandeau.grille, strokeOpacity: 1}),
      Plot.areaY(prev, {x: "date", y1: "lo", y2: "hi", fill: bandeau.fourchette, fillOpacity: 0.2}),
      Plot.lineY(realiseBandeau, {x: "date", y: "v", stroke: bandeau.realise, strokeWidth: 2.2}),
      Plot.lineY(prev, {x: "date", y: "v", stroke: bandeau.prevision, strokeWidth: 2.6, strokeDasharray: "5,4"}),
      Plot.dot([der], {x: "date", y: "v", r: 4, fill: bandeau.realise}),
      Plot.dot([cible], {x: "date", y: "v", r: 5, fill: bandeau.prevision}),
      Plot.text([der], {x: "date", y: "v", text: (d) => `${k(d.v)} · ${fmtMonthFR(d.date)}`,
        dy: -14, textAnchor: "end", fill: bandeau.realise, fontWeight: 700}),
      Plot.text([cible], {x: "date", y: "v", text: (d) => `${k(d.v)} · ${fmtMonthFR(d.date)}`,
        dy: 17, textAnchor: "end", fill: bandeau.prevision, fontWeight: 700}),
      Plot.tip(survol, Plot.pointerX({x: "date", y: "v", ...TIP,
        title: (d) => `${periodeFR(d.date)} — ${d.quoi}\n${nf0.format(d.v)} ventes sur douze mois` +
          (d.quoi === "prévision" ? `\nfourchette ${nf0.format(d.lo)} – ${nf0.format(d.hi)}` : "")})),
    ]});
}
const courbeBandeau = TRAJ && realiseBandeau.length
  ? html`<figure class="hm-hero-courbe">
      <figcaption class="hm-hero-courbe-titre">Ventes de logements anciens, cumul sur douze mois</figcaption>
      ${resize((w) => traceBandeau(w))}
      <p class="hm-hero-courbe-legende"><span class="trait"></span>réalisé
        <span class="pointille"></span>prévision du modèle et sa fourchette
        · <a href="/previsions">le détail →</a></p>
    </figure>`
  : html`<span></span>`;
```

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
  arrivait en dernier. SIX cartes depuis le 2026-10-20 (les aides publiques) : cinq
  laissaient une case vide en bout de seconde ligne, sur trois colonnes.
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
  <a class="hm-page-card" href="/actualites">
    <span class="t">📰 Suivre les aides publiques</span>
    <span class="d">Prêt à taux zéro, MaPrimeRénov', diagnostic de performance énergétique :
    où en est chaque mesure, ses prochaines échéances et son effet attendu sur le neuf,
    l'ancien et la rénovation.</span>
    <span class="p">Par exemple : promoteurs, artisans et installateurs, bailleurs,
    conseillers en financement.</span>
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
  ${multiLine({
    titre: "Logements autorisés, commencés et vendus, en indice",
    sousTitre: `Cumul sur 12 mois, base 100 = ${data.chart.base_label} · France`,
    source: "SIT@DEL (SDES), IGEDD",
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

<div class="hm-meta"><a href="/synthese">Niveaux réels, historique complet et chiffres du
dernier mois sur la Synthèse</a>.</div>

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

<!-- L'ancre « revenir » est celle des liens du flux RSS (scripts/postbuild.mjs) : elle
     est posée en dur pour survivre au libellé, qui s'appelait « Revenir ». -->

## <span id="revenir"></span>Ce qui a changé récemment

Chaque lundi, le site relit ses sources et ne republie que ce qui a changé : un nouveau
mois de données, une prévision qui bouge, une pastille qui change de couleur. Les derniers
changements sont datés ci-dessous ; ce sont les mêmes que dans le flux RSS, à suivre dans
un lecteur de flux ou à brancher sur un canal d'équipe.

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
