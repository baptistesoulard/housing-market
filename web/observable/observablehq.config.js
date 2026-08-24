// Configuration Observable Framework — Baromètre du Logement (site statique).
// `npm run build` produit web/observable/dist/, déployé sur Cloudflare Pages (Node-only).
//
// Les couleurs ET les polices viennent de web/theme.json (source unique de vérité,
// partagée avec le Python d'export et le module src/components/theme.js), lu par
// site.config.js et réexporté ici. Elles sont projetées en variables CSS --hm-* : aucune
// valeur hexadécimale, aucun nom de police n'est écrit en dur dans ce fichier.
//
// L'IDENTITÉ du site (adresse publique, descriptions de pages, navigation, logo) vit
// dans site.config.js — ce fichier-ci ne porte que le rendu.
import {SITE, NAV, MARK, THEME as T, AUTHOR, pageMeta, DEP_PATHS} from "./site.config.js";

// {--hm-xxx: valeur} à plat, à partir des groupes du thème.
const VARS = Object.entries({
  "font-sans": T.font.sans,
  bg: T.brand.bg,
  surface: T.brand.surface,
  ink: T.brand.ink,
  brick: T.brand.brick,
  // `brick` plafonne à 3,92:1 sur blanc — sous les 4,5:1 qu'exige du texte. Bon pour un
  // fond ou une bordure (>= 3:1), pas pour ce que ces mêmes règles écrivent en `color`.
  // Réutilise `status.down.fg`, déjà calé sur ce seuil (5,99:1) : pas de nouvelle teinte
  // à valider, juste un second rôle pour une couleur qui a déjà la bonne luminosité.
  "brick-text": T.status.down.fg,
  blue: T.brand.blue,
  green: T.brand.green,
  // Assombri depuis #1E88E5 (3,68:1 sur blanc, sous les 4,5:1 requis pour du texte) : les
  // liens ne sont soulignés qu'au survol (`a[href]:hover{text-decoration:underline}` du
  // thème Observable), donc la couleur seule doit suffire à distinguer un lien au repos.
  link: T.ui.link,
  subtle: T.ui.subtle,
  muted: T.ui.muted,
  rule: T.ui.rule,
  border: T.ui.border,
  "border-light": T.ui.borderLight,
  "delta-pos": T.delta.positive,
  "delta-neg": T.delta.negative,
}).map(([k, v]) => `  --hm-${k}: ${v};`).join("\n");

// La barre latérale ne montre pas TOUTES les pages : l'accueil en est retiré (`nav:
// false` dans site.config.js). Il reste atteignable par le bloc de marque en haut de la
// barre, qui pointe déjà sur « / » — l'y répéter en huitième onglet ferait deux entrées
// pour une seule page.
const PAGES = NAV.filter((p) => p.nav !== false).map(({name, path}) => ({name, path}));

// Une règle par onglet : l'emoji en ::before, adressé par le href que rend le framework
// (« ./ » pour la racine, « ./neuf » ailleurs). Ces règles sont concaténées dans STYLE.
const NAV_ICONS = PAGES.map(({path}) => ({icon: NAV.find((n) => n.path === path).icon, path}))
  .map(({icon, path}) =>
  `#observablehq-sidebar > ol:nth-of-type(2) a[href="${path === "/" ? "./" : "." + path}"]::before` +
  ` { content: "${icon}"; }
`).join("");

const STYLE = `
<style>
:root {
${VARS}
  --sans-serif: var(--hm-font-sans);
  --serif: var(--hm-font-sans);
  /* Largeur de la colonne de contenu — cadre commun à l'en-tête et à « main ». */
  --hm-measure: 64rem;
}
/* --- Échelle typographique, relevée dans l'app Streamlit ---------------------------
   Valeurs calculées mesurées dans le navigateur sur l'onglet Synthèse, et reproduites
   ici. Deux surprises qui expliquent l'écart de netteté ressenti :
   1. Streamlit n'emploie AUCUN gris pour le texte — chapô, libellés de cartes,
      sous-titres, ligne de fraîcheur : tout est à son encre pleine. Le front dégradait
      ce texte secondaire sur deux niveaux de gris, ce qui le faisait paraître délavé.
   2. Les titres de l'app rendent en Source Sans, pas en Segoe UI : sa règle
      « h2, h3 {font-family: 'Segoe UI'} » perd en spécificité (voir theme.json).
   Corps 16px/1.6, titre de section 36px/600, sous-titre 14px/1.6 — tous en encre pleine.
   Les cartes de la Synthèse suivaient ici le markdown d'app.py (libellé 16px/600, valeur
   28px/600) ; elles sont passées à l'échelle st.metric ci-dessous, comme celles des
   autres pages — trois blocs de quatre cartes à 28px écrasaient le reste de la page. */
body { font-family: var(--sans-serif); font-size: 16px; line-height: 1.6;
  color: var(--hm-ink); background: var(--hm-bg); }
h1, h2, h3, h4 { font-family: var(--sans-serif); color: var(--hm-ink); }
h1 { font-size: 2.25rem; font-weight: 600; border-bottom: 2px solid var(--hm-brick);
  padding-bottom: 8px; margin-bottom: 0.15rem; }

/* --- UNE seule largeur de colonne -------------------------------------------------
   Trois plafonds de largeur se superposaient ici, et la page avait donc trois bords
   droits différents : le thème « air » plafonne p/h1-h6 à 640 px et ul/ol à 600 px, les
   blocs .hm-* portaient chacun leur propre max-width de 64 rem, et .hm-grid/.hm-meta
   n'avaient aucun plafond. Mesuré à 930 px de large : le filet du h1 s'arrêtait à 672 px,
   le texte de « À retenir » à 671 px, mais sa boîte allait jusqu'à 883 px.
   On neutralise donc les plafonds par élément du thème et on cadre la colonne UNE fois,
   sur « main » — tout partage alors le même bord gauche et le même bord droit. Corollaire :
   ne pas remettre de max-width sur un bloc .hm-*, ça recréerait un second bord. */
#observablehq-main { max-width: var(--hm-measure); }
#observablehq-main :is(p, ul, ol, blockquote, h1, h2, h3, h4, h5, h6,
                       table, figure, figcaption, .note, .tip, .warning, .caution) { max-width: none; }
main h2 { font-size: 1.55rem; font-weight: 600; margin-top: 2.4rem; padding-bottom: 0.3rem; border-bottom: 1px solid var(--hm-border); }
main h3 { font-size: 1.3rem; font-weight: 600; color: var(--hm-ink); margin-top: 2.2rem; margin-bottom: 0.5rem; padding-bottom: 0.3rem; border-bottom: 1px solid var(--hm-border-light); }
/* Sélecteur [href], pas juste l'élément : le thème Observable pose déjà une règle sur ce
   même motif pour donner sa couleur de lien par défaut, à spécificité égale à un simple
   élément seul augmenté d'un attribut. Un simple élément seul, sans l'attribut, se fait
   donc battre en silence pour tout lien jamais cliqué. Vérifié dans le navigateur : sans
   ce correctif, un lien non visité rendait la couleur du thème Observable, jamais
   --hm-link — seul un lien VISITÉ, à spécificité déjà suffisante pour gagner, prenait la
   bonne teinte. Deux bleus différents selon l'état de clic n'a jamais été voulu.

   Exclu si l'élément porte une classe (boutons .hm-btn, pastilles .hm-shortcut,
   .hm-page-card) : sans ce filtre, un de ces liens une fois VISITÉ — cas réel pour un
   lien externe (GitHub, LinkedIn) qu'un visiteur a déjà ouvert — repasserait au bleu de
   lien au lieu de sa couleur de composant, l'état visité l'emportant sur la spécificité
   de ces classes. Ces composants annoncent déjà leur nature par leur forme ; ce n'est pas
   à la couleur de lien de la leur reprendre. */
a[href]:not([class]), a[href]:visited:not([class]) { color: var(--hm-link); }
/* Un lien de PROSE (citation de source, renvoi interne dans un paragraphe) reste
   soulignable en permanence : sans ça, sa seule distinction au repos est la couleur, et
   même assombri à 4,5:1 ça ne suffit pas à qui ne perçoit pas cette teinte. Restreint aux
   liens SANS classe pour ne toucher ni les boutons (.hm-btn), ni les pastilles
   (.hm-shortcut, .hm-page-card) : ceux-là annoncent déjà leur nature par leur forme, et
   remettraient un soulignement que leur propre règle retire exprès. Cantonné au contenu
   de page : la barre latérale et le sommaire ont leurs propres liens sans classe
   (ancres de titres) que le thème Observable stylise déjà à sa façon. */
#observablehq-main a:not([class]) { text-decoration: underline; text-underline-offset: 2px; }
/* Glossaire au fil du texte : un sigle (SIT@DEL, OAT…) porte un <abbr title> sur sa
   première occurrence par page — soulignement pointillé au survol/focus, infobulle
   native du navigateur. Pas de JS : ce sont des chapeaux statiques (voir CLAUDE.md,
   « chapeau statique »), le glossaire complet vit dans le repli d'À propos. */
abbr[title] { text-decoration: underline dotted; text-decoration-color: var(--hm-subtle);
  text-underline-offset: 2px; cursor: help; }
.hm-caption { color: var(--hm-ink); font-size: 0.875rem; margin: 0.2rem 0 1rem; }
.hm-chips { margin: 0.4rem 0 1.2rem; }
.hm-takeaways { background: color-mix(in srgb, var(--hm-blue) 12%, transparent); border-left: 4px solid var(--hm-blue);
  border-radius: 8px; padding: 0.9rem 1.1rem; margin: 0.6rem 0 1rem; }
.hm-takeaways ul { margin: 0.3rem 0 0; padding-left: 1.1rem; }
.hm-takeaways li { margin: 0.35rem 0; line-height: 1.5; }
.hm-meta { color: var(--hm-ink); font-size: 0.875rem; margin: 0.4rem 0 0.2rem; }
.hm-grid { display: grid; gap: 1.8rem 1.6rem; margin: 0.8rem 0 0.4rem;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); }
.hm-card { padding: 0.15rem 0; background: transparent; border: none; }
.hm-card-title { font-weight: 600; font-size: 1rem; color: var(--hm-ink); letter-spacing: 0.2px; }
.hm-card-value { font-size: 1.75rem; font-weight: 600; color: var(--hm-ink); margin: 0.5rem 0 0.4rem; line-height: 1.2; }
.hm-card-sub { font-size: 0.875rem; color: var(--hm-ink); line-height: 1.6; }
/* Cartouches type st.metric (pages Marché / Actualités), via .hm-card--metric.
   Relevé sur st.metric : libellé 14px/400, valeur 24px/700, delta en pastille de 14px à
   rayon plein sur un fond teinté à ~10 %, SUR SA PROPRE LIGNE. C'est ce dernier point qui
   fait la lisibilité : collé derrière la valeur, le delta concurrençait le chiffre. */
.hm-card--metric .hm-card-title { font-size: 0.875rem; font-weight: 400; }
.hm-card--metric .hm-card-value { font-size: 1.5rem; font-weight: 700; margin: 0.1rem 0 0.25rem; }
.hm-card-delta { margin: 0 0 0.4rem; }
/* La pastille de statut de la Synthèse : sous la taille du chiffre, pour que le regard
   tombe sur le nombre. À taille égale (le rendu de Streamlit, où l'emoji est dans le
   « ### »), le rond coloré prend le pas sur la valeur qu'il ne fait que qualifier. */
.hm-card-dot { font-size: 0.8em; }
.hm-delta { display: inline-flex; align-items: center; font-size: 0.875rem; font-weight: 400;
  border-radius: 9999px; padding: 2px 9px; line-height: 1.5; }
.hm-delta.pos { color: var(--hm-delta-pos);
  background: color-mix(in srgb, var(--hm-delta-pos) 12%, transparent); }
.hm-delta.neg { color: var(--hm-delta-neg);
  background: color-mix(in srgb, var(--hm-delta-neg) 12%, transparent); }
/* Renvois de bas de bloc (page Synthèse) : de vrais liens vers les pages de détail,
   présentés en pastilles pour qu'ils se voient comme cliquables — le texte simple
   qu'ils remplacent nommait les onglets sans y mener. */
.hm-shortcuts { display: flex; flex-wrap: wrap; align-items: center; gap: 0.45rem;
  font-size: 0.875rem; margin: 0.5rem 0 2rem; }
.hm-shortcuts .lead { color: var(--hm-subtle); }
/* [href] dans le sélecteur, pas juste la classe : troisième rencontre de ce fichier avec
   le même défaut (voir plus bas « L'onglet courant » et « Boutons sur fond sombre » pour
   les deux précédentes). Le thème Observable pose un a[href] qui vaut UN ÉLÉMENT PLUS UN
   ATTRIBUT — plus spécifique qu'une classe seule. Sans qualifier nos propres classes de
   la même façon, un lien réel s'affichait dans le bleu de focus du thème au lieu de sa
   couleur de composant, silencieusement (mesuré ici sur .hm-page-card : un lien interne
   jamais visité rendait ce bleu-là, pas l'encre attendue). Toujours un anchor pour cette
   classe précise, donc pas de risque à le rendre obligatoire dans le sélecteur. */
.hm-shortcut[href] { display: inline-flex; align-items: center; gap: 0.3rem;
  padding: 0.15rem 0.65rem; border: 1px solid var(--hm-border); border-radius: 9999px;
  background: var(--hm-surface); color: var(--hm-ink); text-decoration: none; }
.hm-shortcut:hover, .hm-shortcut:focus-visible { border-color: var(--hm-brick);
  color: var(--hm-brick-text); background: var(--hm-bg); }
/* Renvoi entre sections JUMELLES (neuf <-> ancien). Les deux pages partagent trois
   sections de même nom, dans le même ordre et avec la même ancre ; ce renvoi est ce qui
   le fait savoir à quelqu'un qui n'a ouvert qu'une des deux. Il est posé sous le chapô de
   section, pas en bas de bloc comme ceux de la Synthèse — d'où la marge réduite : il
   introduit ce qui suit au lieu de le clore. */
.hm-shortcuts--twin { margin: 0.1rem 0 0.9rem; }
/* --- Le sommaire de page ne doit RIEN coûter au contenu ----------------------------
   Le framework l'affiche dès 1216 px quand la barre latérale est ouverte, en réservant
   208 px de gouttière sur « main ». Mesuré à 1250 px : la colonne de contenu tombe de
   817 px à 659 px, et les .hm-panels — dont le minmax est à 340 px — passent de deux
   colonnes à une. Or ces panneaux sont APPARIÉS pour être comparés (encours vs délai
   d'écoulement, capacité d'emprunt vs accessibilité) : les empiler défait leur raison
   d'être. 1280x800 et 1366x768 tombent en plein dans cette bande.
   On retarde donc l'apparition du sommaire jusqu'à 1320 px, largeur à partir de laquelle
   le contenu garde ses 702 px (2 x 340 + gouttière). En dessous, la navigation par
   section reste assurée par les renvois entre sections jumelles.
   La règle ne vise que le cas « barre latérale ouverte » — sidebar fermée, la place ne
   manque pas — et reprend pour cela les sélecteurs du framework, sinon la sienne
   l'emporterait en spécificité.
   Deux règles à défaire, pas une : le framework masque le sommaire d'un côté et réserve
   sa gouttière de l'autre (#observablehq-toc ~ #observablehq-main). Cacher le sommaire
   seul laisserait 208 px de vide à droite du contenu — la colonne resterait étroite pour
   rien. */
@media (max-width: 1319px) {
  #observablehq-sidebar-toggle:checked ~ #observablehq-center #observablehq-toc,
  #observablehq-sidebar-toggle:indeterminate ~ #observablehq-center #observablehq-toc { display: none; }
  #observablehq-sidebar-toggle:checked ~ #observablehq-center #observablehq-toc ~ #observablehq-main,
  #observablehq-sidebar-toggle:indeterminate ~ #observablehq-center #observablehq-toc ~ #observablehq-main { padding-right: 0; }
}
.hm-panels { display: grid; gap: 1rem 1.4rem; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); }
.hm-panel-title { font-weight: 600; font-size: 0.98rem; color: var(--hm-ink); margin: 0.4rem 0 0.1rem; }
.hm-panel-sub { color: var(--hm-ink); font-size: 0.875rem; margin-bottom: 0.2rem; }
.hm-legend { display: flex; flex-wrap: wrap; gap: 0.4rem 1.3rem; margin: 0.6rem 0 0.1rem; }
.hm-legend-item { display: inline-flex; align-items: center; gap: 0.45rem; cursor: pointer; font-size: 0.9rem; user-select: none; }
.hm-legend-item.off { opacity: 0.4; text-decoration: line-through; }
/* Légende NON interactive (page « Prévisions passées ») : mêmes pastilles, mais rien à
   cliquer. Sans ce modificateur, le curseur en main promet une interaction qui n'existe
   pas — un contrôle qui ment sur ce qu'il fait est pire qu'un texte inerte. */
.hm-legend--static .hm-legend-item { cursor: default; }
/* Tableau large replié dans un « details » : c'est le conteneur qui défile, jamais la
   page — un site qui glisse latéralement sur mobile a l'air cassé. */
.hm-scroller { overflow-x: auto; }
.hm-swatch { width: 16px; height: 3px; border-radius: 2px; display: inline-block; }
.hm-chart-title { font-weight: 600; margin: 1rem 0 0; }
.hm-chart-title .sub { color: var(--hm-subtle); font-weight: 400; }
/* --- Export CSV au survol d'un graphique -------------------------------------------
   Le bouton reste invisible tant qu'on n'a pas amené le pointeur (ou le focus clavier)
   sur le graphique : un site de lecture n'a pas à afficher des commandes en permanence.
   :focus-within couvre le clavier, qui n'a pas de survol. */
.hm-chart-card { position: relative; }
.hm-chart-export { position: absolute; top: 0.5rem; right: 0.5rem; z-index: 2;
  display: inline-flex; align-items: center; gap: 0.3rem; font: inherit; font-size: 0.78rem;
  font-weight: 600; line-height: 1; padding: 0.32rem 0.6rem; border-radius: 6px;
  border: 1px solid var(--hm-border); background: var(--hm-bg); color: var(--hm-ink);
  cursor: pointer; opacity: 0; transition: opacity 0.15s ease; }
.hm-chart-card:hover .hm-chart-export,
.hm-chart-card:focus-within .hm-chart-export { opacity: 1; }
.hm-chart-export:hover, .hm-chart-export:focus-visible { border-color: var(--hm-brick); color: var(--hm-brick-text); }
details.hm-howto { margin: 0.2rem 0 0.8rem; }
details.hm-howto summary { cursor: pointer; color: var(--hm-ink); }

/* --- Frise de période (barre latérale) : miroir du curseur « Période (années) »
   de la barre latérale Streamlit. Deux <input type=range> superposés sur un rail
   commun ; seules les poignées captent les clics, pour que les deux cohabitent. */
#hm-period-slot { padding: 0.55rem 1rem 0.75rem; border-bottom: 1px solid var(--hm-border-light); }
.hm-period-label { font-size: 0.82rem; font-weight: 600; color: var(--hm-ink); margin-bottom: 0.15rem; }
.hm-period-values { position: relative; height: 1.05rem; }
.hm-period-val { position: absolute; transform: translateX(-50%); white-space: nowrap;
  font-size: 0.78rem; font-weight: 700; color: var(--hm-brick-text); }
.hm-period-track { position: relative; height: 20px; }
.hm-period-rail { position: absolute; top: 8px; left: 0; right: 0; height: 4px; border-radius: 2px; background: var(--hm-border); }
.hm-period-fill { position: absolute; top: 8px; height: 4px; border-radius: 2px; background: var(--hm-brick); }
.hm-period-track input[type="range"] { position: absolute; top: 0; left: 0; width: 100%; height: 20px;
  margin: 0; background: none; pointer-events: none; -webkit-appearance: none; appearance: none; }
.hm-period-track input[type="range"]:focus { outline: none; }
.hm-period-track input[type="range"]::-webkit-slider-thumb { -webkit-appearance: none; pointer-events: auto;
  width: 14px; height: 14px; border-radius: 50%; background: var(--hm-brick); border: 2px solid var(--hm-surface);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.35); cursor: grab; }
.hm-period-track input[type="range"]::-moz-range-thumb { pointer-events: auto; box-sizing: border-box;
  width: 14px; height: 14px; border-radius: 50%; background: var(--hm-brick); border: 2px solid var(--hm-surface);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.35); cursor: grab; }
.hm-period-track input[type="range"]::-moz-range-track { background: transparent; height: 4px; }
.hm-period-track input[type="range"]:focus-visible::-webkit-slider-thumb { outline: 2px solid var(--hm-blue); outline-offset: 1px; }
.hm-period-track input[type="range"]:focus-visible::-moz-range-thumb { outline: 2px solid var(--hm-blue); outline-offset: 1px; }
.hm-period-bounds { display: flex; justify-content: space-between; font-size: 0.72rem; color: var(--theme-foreground-muted); }
.hm-dep-head h1 { margin-bottom: 0.2rem; }
.hm-dep-invite { font-size: 0.95rem; margin: 0.2rem 0 0.8rem; }
.hm-absence { border: 1px solid var(--hm-border); border-left: 3px solid var(--hm-brick);
  border-radius: 6px; padding: 0.9rem 1.1rem; margin: 1rem 0; background: var(--hm-surface); }
.hm-absence-titre { font-weight: 600; color: var(--hm-ink); margin-bottom: 0.4rem; }
.hm-absence p { margin: 0.35rem 0; font-size: 0.9rem; }
/* Le chiffre personnel de la page départementale : il doit se lire d'un coup d'oeil et
   se retenir, c'est lui qu'on partage. */
.hm-capacite { display: flex; align-items: baseline; gap: 1rem; flex-wrap: wrap;
  border: 1px solid var(--hm-border); border-left: 3px solid var(--hm-green);
  border-radius: 6px; padding: 1rem 1.2rem; margin: 0.6rem 0 0.4rem;
  background: var(--hm-surface); }
.hm-capacite-chiffre { font-size: 2.6rem; font-weight: 700; color: var(--hm-ink);
  line-height: 1.1; }
.hm-capacite-legende { font-size: 0.9rem; color: var(--hm-ink); }
/* [href] dans le sélecteur, MÊME DÉFAUT qu'à .hm-shortcut et .hm-btn : le thème
   Observable pose « a[href] { color: var(--theme-foreground-focus) } », à spécificité
   0,1,1 — la simple classe .hm-cta (0,1,0) se faisait battre en silence, et le bouton
   rendait en BLEU DE LIEN sur son fond brick, dès le premier affichage et pas seulement
   une fois visité. .hm-cta[href] passe à 0,2,0 et l'emporte ; :visited est répété par
   dessus pour l'état visité, comme le fait déjà .hm-btn--primary[href].

   Le FOND est --hm-brick-text, pas --hm-brick : mesuré dans le navigateur, blanc sur
   brick plafonne à 3,92:1, sous les 4,5:1 qu'exige ce libellé (16 px / 600, trop petit
   pour le seuil « grand texte »). Le même jeton assombri sert déjà de fond à .hm-skip,
   pour cette raison exacte, et donne 5,99:1. C'est aussi ce que dit le commentaire de
   --hm-brick en tête de fichier : bon pour un fond derrière rien, pas derrière du
   texte. */
.hm-cta[href], .hm-cta[href]:visited { display: inline-block; margin: 0.5rem 0 1rem;
  padding: 0.5rem 0.9rem;
  border-radius: 6px; background: var(--hm-brick-text); color: var(--hm-bg);
  font-weight: 600; text-decoration: none; }
.hm-cta:hover { filter: brightness(1.08); }
.hm-api-offline { border: 1px solid var(--hm-border); border-left: 3px solid var(--hm-brick);
  border-radius: 6px; padding: 0.9rem 1.1rem; margin: 1rem 0; background: var(--hm-surface); }
.hm-api-offline-title { font-weight: 600; color: var(--hm-ink); margin-bottom: 0.4rem; }
.hm-api-offline p { margin: 0.35rem 0; font-size: 0.875rem; }
.hm-privacy { border: 1px solid var(--hm-border); border-left: 3px solid var(--hm-green);
  border-radius: 6px; padding: 0.75rem 1.1rem; margin: 1rem 0; font-size: 0.875rem;
  background: var(--hm-surface); }
.hm-period-note { font-size: 0.72rem; color: var(--theme-foreground-muted); margin-top: 0.3rem; line-height: 1.35; }

/* --- Barre latérale : bloc de marque + gouttière d'icônes --------------------------
   Deux défauts du rendu par défaut d'Observable Framework, tous deux visibles d'un coup
   d'œil sur la page Synthèse :

   1. Le nom du site est un LIEN DE NAVIGATION comme les autres. Sur la page d'accueil il
      reçoit « observablehq-link-active » — donc le liseré vertical ET la couleur de lien de
      l'onglet courant. L'écran montrait ainsi DEUX éléments actifs, dont un qui ne l'est
      pas, et le nom du produit se lisait comme un huitième onglet. On lui redonne le
      statut d'en-tête : logo, encre pleine, pas de liseré, une accroche en dessous.
   2. Les libellés d'onglets sont en drapeau : l'emoji fait partie du texte du lien et les
      emojis n'ont pas la même chasse (🏠 est plus large que 📡). D'où la gouttière de
      largeur fixe ci-dessous, alimentée par le champ « icon » de NAV. */
#observablehq-sidebar > ol:first-child { padding-bottom: 0.75rem; }
/* Le liseré « actif » du titre — c'est le ::before du <li>, pas celui du <a>. */
#observablehq-sidebar > ol:first-child > li::before { display: none; }
#observablehq-sidebar > ol:first-child > li > a {
  height: auto; align-items: center; gap: 0.55rem;
  padding: 0.1rem 2rem 0.1rem 1.5rem;
  color: var(--hm-ink); font-size: 1.05rem; font-weight: 700; letter-spacing: -0.2px;
  background: none; }
#observablehq-sidebar > ol:first-child > li > a:hover { background: none; color: var(--hm-brick-text); }
#observablehq-sidebar > ol:first-child > li > a::before {
  content: ""; flex: none; width: 26px; height: 26px;
  background: url("${MARK}") center / contain no-repeat; }
/* L'accroche : posée sur le <li> et non dans le lien, pour rester hors de la zone
   cliquable et hors du nom accessible de celui-ci. */
#observablehq-sidebar > ol:first-child > li::after {
  content: "${SITE.tagline}";
  display: block; padding: 0.1rem 1rem 0 calc(1.5rem + 26px + 0.55rem);
  font-size: 0.72rem; font-weight: 500; line-height: 1.25; color: var(--hm-subtle); }
#observablehq-sidebar > ol:nth-of-type(2) .observablehq-link a { gap: 0; }
#observablehq-sidebar > ol:nth-of-type(2) .observablehq-link a::before {
  flex: none; display: inline-block; width: 1.5em; font-size: 0.95rem; line-height: 1; }
${NAV_ICONS}
/* L'onglet courant : liseré à la couleur de marque (il était au bleu de focus du thème,
   la seule teinte de l'écran qui ne vienne pas de theme.json) et libellé à l'encre. */
#observablehq-sidebar > ol:nth-of-type(2) > li.observablehq-link-active::before { background: var(--hm-brick); }
#observablehq-sidebar > ol:nth-of-type(2) > li.observablehq-link-active > a { color: var(--hm-ink); font-weight: 600; }

/* --- Page d'accueil ----------------------------------------------------------------
   Cette page a un rôle que les sept autres n'ont pas : elle s'adresse à quelqu'un qui
   arrive d'un lien LinkedIn et ne sait pas encore ce qu'il regarde. Elle est donc
   RÉDIGÉE, en HTML rendu au build — les autres pages construisent leur contenu dans le
   navigateur à partir des JSON, ce qu'un robot d'indexation qui n'exécute pas de
   JavaScript ne voit pas. C'est ici que vit le texte indexable du site. */
.hm-hero { margin: 0 0 2.4rem; }
.hm-hero h1 { font-size: 2.6rem; line-height: 1.15; border-bottom: none; padding-bottom: 0;
  margin-bottom: 0.6rem; letter-spacing: -0.5px; }
/* --- Le bandeau ---------------------------------------------------------------------
   Les huit pages de données se ressemblent par construction : même colonne, même filet
   sous le titre. L'accueil doit se distinguer AVANT d'être lue, pour quelqu'un qui
   arrive d'un lien et ne sait pas encore où il est — d'où un pavé plein, à contraste
   inversé, qui casse la colonne par la couleur.

   Il ne DÉBORDE PAS de la colonne, volontairement. Un vrai bord-à-bord supposerait des
   marges négatives calculées sur les marges « auto » de #observablehq-main, qui varient
   avec la largeur de la fenêtre et avec la barre latérale : le premier écran étroit
   ferait glisser la page latéralement. Le fond plein suffit à produire la rupture ; le
   dépassement n'y ajouterait rien qu'un risque.

   La couleur est DÉRIVÉE des jetons du thème (color-mix sur --hm-ink et --hm-brick) :
   aucune valeur hexadécimale n'entre ici, conformément à la règle du fichier. Le brick
   n'est qu'une pointe dans le dégradé — theme.json le décrit comme une couleur d'accent,
   à employer avec parcimonie ; un aplat orange plein écraserait la page. */
/* .hm-btn[href] / .hm-btn--primary[href] (couleur pour le cas <a>, voir la classe de
   base .hm-btn plus bas — même défaut qu'à .hm-shortcut plus haut) DOIVENT précéder le
   bloc « Boutons sur fond sombre » ci-dessous : les deux sont à spécificité égale (deux
   classes, ou classe + attribut), et .hm-hero--band .hm-btn--onband(-primary) doit
   rester déclaré APRÈS pour gagner sur cette égalité — sans quoi les boutons du bandeau
   reperdraient leur blanc pour l'encre de .hm-btn[href]. */
.hm-btn[href] { color: var(--hm-ink); }
.hm-btn--primary[href], .hm-btn--primary[href]:visited { color: var(--hm-bg); }
.hm-hero--band { color: var(--hm-bg); border-radius: 16px; margin: 0 0 2rem;
  padding: 2.4rem 2.2rem 0; overflow: hidden;
  background: linear-gradient(135deg,
    color-mix(in srgb, var(--hm-ink) 94%, black) 0%,
    color-mix(in srgb, var(--hm-ink) 74%, var(--hm-brick)) 100%); }
.hm-hero--band h1 { color: var(--hm-bg); margin-bottom: 0.7rem; }
.hm-hero--band .hm-lead { color: var(--hm-bg); max-width: 46rem; opacity: 0.92; }
.hm-eyebrow { text-transform: uppercase; letter-spacing: 1.1px; font-size: 0.74rem;
  font-weight: 700; margin: 0 0 0.8rem; color: var(--hm-bg); opacity: 0.72; }
/* Boutons sur fond sombre. Le primaire est BLANC, pas brick : blanc sur brick plafonne
   à 3,9:1, sous le seuil de 4,5:1 qu'exige un libellé de cette taille, alors qu'encre
   sur blanc dépasse 11:1. C'est aussi ce qui le fait ressortir — sur un fond déjà teinté
   de brick, un bouton brick se fondrait dedans.

   Ces règles sont préfixées par .hm-hero--band, et pas seulement pour se restreindre au
   bandeau : .hm-btn est déclaré PLUS BAS dans cette même feuille, à spécificité égale
   (une classe). Sans le préfixe, c'est lui qui gagne, à l'ordre — mesuré dans le
   navigateur, les trois boutons ressortaient en fond gris clair et texte bleu de lien
   visité. Le sélecteur :visited est répété pour battre a:visited, comme le fait déjà
   .hm-btn--primary.

   (Pas d'accent grave dans ce commentaire : tout ce bloc CSS vit dans un littéral
   gabarit JS, un backtick le refermerait et le build échouerait sur une erreur de
   syntaxe sans rapport apparent.) */
.hm-hero--band .hm-btn--onband-primary,
.hm-hero--band .hm-btn--onband-primary:visited { background: var(--hm-bg);
  border-color: var(--hm-bg); color: var(--hm-ink); }
.hm-hero--band .hm-btn--onband-primary:hover,
.hm-hero--band .hm-btn--onband-primary:focus-visible {
  background: var(--hm-surface); border-color: var(--hm-surface); color: var(--hm-ink); }
.hm-hero--band .hm-btn--onband,
.hm-hero--band .hm-btn--onband:visited { background: transparent; color: var(--hm-bg);
  border-color: color-mix(in srgb, var(--hm-bg) 55%, transparent); }
.hm-hero--band .hm-btn--onband:hover,
.hm-hero--band .hm-btn--onband:focus-visible {
  background: color-mix(in srgb, var(--hm-bg) 14%, transparent);
  border-color: var(--hm-bg); color: var(--hm-bg); }
.hm-hero--band .hm-btn:focus-visible { outline-color: var(--hm-bg); }
/* La bande de chiffres, en pied de bandeau : un liseré et un voile suffisent à la
   détacher sans introduire une seconde boîte. Marges négatives ici, mais INTERNES au
   bandeau — elles annulent exactement son padding, il n'y a rien à déborder. */
/* Quatre colonnes EXPLICITES, puis deux — pas de repeat(auto-fit) ici. Mesuré : dans la
   colonne de 897 px, minmax(190px, 1fr) retombait à trois colonnes et laissait le
   quatrième chiffre seul sur une deuxième ligne. Une bande de preuve qui se termine par
   un orphelin a l'air cassée ; 4 puis 2 (2+2) reste toujours équilibré. */
.hm-stats { list-style: none; display: grid; gap: 1.1rem 1.6rem;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin: 2rem -2.2rem 0; padding: 1.2rem 2.2rem 1.3rem;
  border-top: 1px solid color-mix(in srgb, var(--hm-bg) 22%, transparent);
  background: color-mix(in srgb, var(--hm-bg) 6%, transparent); }
.hm-stats li { margin: 0; }
.hm-stats .n { display: block; font-size: 1.5rem; font-weight: 700; line-height: 1.15;
  color: var(--hm-bg); }
.hm-stats .d { display: block; font-size: 0.83rem; line-height: 1.45; margin-top: 0.2rem;
  color: var(--hm-bg); opacity: 0.82; }
@media (max-width: 820px) {
  .hm-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 640px) {
  .hm-hero--band { padding: 1.8rem 1.3rem 0; border-radius: 12px; }
  .hm-hero--band h1 { font-size: 2rem; }
  .hm-stats { margin: 1.5rem -1.3rem 0; padding: 1.1rem 1.3rem 1.2rem; }
}
/* La courbe d'accroche : cadrée comme un panneau pour qu'on la lise comme une figure et
   non comme un fond de page. */
.hm-accroche { border: 1px solid var(--hm-border); border-radius: 12px;
  padding: 0.9rem 1.1rem 0.4rem; background: var(--hm-surface); margin: 0.6rem 0 0.5rem; }
.hm-accroche .hm-panel-title { margin-top: 0; }
.hm-accroche .hm-legend { margin-top: 0.35rem; }
/* Le chapô sert aussi hors du bandeau (page À propos), et markdown y insère un <p> :
   les deux sélecteurs sont donc nécessaires pour que la taille ne retombe pas. */
.hm-lead, .hm-lead p { font-size: 1.18rem; line-height: 1.55; color: var(--hm-ink); }
.hm-lead { margin: 0 0 1.4rem; }
.hm-rule { width: 88px; height: 4px; border-radius: 2px; background: var(--hm-brick); margin: 0 0 1.3rem; }
.hm-actions { display: flex; flex-wrap: wrap; gap: 0.7rem; margin: 0 0 0.4rem; }
/* .hm-btn décore aussi le bouton <button> du formulaire de contact, sans href : le
   qualifier ici casserait ce cas. Le correctif de couleur pour le cas <a> est plus haut
   (.hm-btn[href], avant le bandeau — voir son commentaire pour la contrainte d'ordre). */
.hm-btn { display: inline-flex; align-items: center; gap: 0.4rem; text-decoration: none;
  padding: 0.5rem 1.1rem; border-radius: 9999px; font-weight: 600; font-size: 0.95rem;
  border: 1px solid var(--hm-border); background: var(--hm-surface); color: var(--hm-ink); }
/* Fond --hm-brick-text et non --hm-brick, même raison qu'à .hm-cta plus haut : blanc sur
   brick mesure 3,92:1, sous les 4,5:1 requis pour ce libellé (15,2 px / 600). Le jeton
   assombri donne 5,99:1. Les deux boutons pleins du site restent ainsi identiques. */
.hm-btn--primary, .hm-btn--primary:visited { background: var(--hm-brick-text); border-color: var(--hm-brick-text);
  color: var(--hm-bg); }
.hm-btn:hover, .hm-btn:focus-visible { border-color: var(--hm-brick); color: var(--hm-brick-text); background: var(--hm-bg); }
.hm-btn--primary:hover, .hm-btn--primary:focus-visible { background: var(--hm-ink); border-color: var(--hm-ink);
  color: var(--hm-bg); }
/* --- Le formulaire de contact (page À propos) -------------------------------------
   Aucune bibliothèque de formulaire : quatre champs empilés, à la largeur de la colonne.
   Trois points qui ne sont pas cosmétiques :
   1. .hm-hp est le pot de miel. Il est caché par position absolue et non par
      display:none ni visibility:hidden — les robots à moitié sérieux sautent ces deux
      propriétés, alors qu'un décalage hors écran leur ressemble à un champ ordinaire.
      aria-hidden et tabindex=-1 le retirent des lecteurs d'écran et du parcours clavier.
   2. font: inherit sur les champs : sans lui le navigateur impose sa police système à
      13 px, seul endroit du site qui ne serait pas en Source Sans.
   3. La bordure passe au brick au focus ET garde un contour visible : la couleur seule
      ne suffit pas (WCAG 1.4.1). */
.hm-form { display: flex; flex-direction: column; gap: 1rem; margin: 1.2rem 0 0.6rem;
  max-width: 44rem; }
.hm-field { display: flex; flex-direction: column; gap: 0.3rem; }
.hm-field label { font-size: 0.9rem; font-weight: 600; color: var(--hm-ink); }
.hm-field-note { font-weight: 400; color: var(--hm-ink); }
.hm-form input, .hm-form select, .hm-form textarea { font: inherit; font-size: 0.95rem;
  color: var(--hm-ink); background: var(--hm-surface); border: 1px solid var(--hm-border);
  border-radius: 8px; padding: 0.55rem 0.7rem; width: 100%; }
.hm-form textarea { resize: vertical; min-height: 7rem; line-height: 1.55; }
.hm-form input:focus-visible, .hm-form select:focus-visible, .hm-form textarea:focus-visible {
  border-color: var(--hm-brick); outline: 2px solid var(--hm-blue); outline-offset: 1px; }
.hm-hp { position: absolute; left: -9999px; width: 1px; height: 1px; overflow: hidden; }
.hm-form-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 0.9rem; }
.hm-form button[type="submit"] { cursor: pointer; }
.hm-form button[disabled] { opacity: 0.6; cursor: progress; }
.hm-form-status { margin: 0; font-size: 0.9rem; color: var(--hm-ink); }
.hm-form-status--ok { color: var(--hm-green); font-weight: 600; }
.hm-form-status--ko { color: var(--hm-brick-text); font-weight: 600; }
.hm-form-legal { font-size: 0.82rem; line-height: 1.5; color: var(--hm-ink);
  margin: 0.2rem 0 0; }
/* Le sommaire des pages : de vrais liens décrits, pas une liste de titres. Ils donnent
   au visiteur le plan du site et aux moteurs le maillage interne qui manquait. */
.hm-pages { display: grid; gap: 0.9rem; margin: 1rem 0 0.6rem;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
/* [href] : toujours un anchor, même défaut qu'à .hm-shortcut plus haut. */
.hm-page-card[href] { display: block; text-decoration: none; color: var(--hm-ink);
  border: 1px solid var(--hm-border); border-radius: 10px; padding: 0.85rem 1rem 0.95rem;
  background: var(--hm-surface); }
.hm-page-card:hover, .hm-page-card:focus-visible { border-color: var(--hm-brick); background: var(--hm-bg); }
.hm-page-card .t { font-weight: 600; display: flex; align-items: baseline; gap: 0.45rem; }
.hm-page-card:hover .t, .hm-page-card:focus-visible .t { color: var(--hm-brick-text); }
.hm-page-card .d { font-size: 0.875rem; line-height: 1.5; margin-top: 0.3rem; color: var(--hm-muted); }
/* Les trois arguments de crédibilité de l'accueil. Trois colonnes courtes plutôt qu'un
   paragraphe : c'est ce qu'un visiteur de passage lit réellement. */
.hm-proof { display: grid; gap: 1.2rem 1.6rem; margin: 1rem 0 0.4rem;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
.hm-proof h3 { margin: 0 0 0.35rem; font-size: 1.02rem; border-bottom: none; padding-bottom: 0; }
.hm-proof p { margin: 0; font-size: 0.92rem; line-height: 1.55; color: var(--hm-muted); }
.hm-note { border: 1px solid var(--hm-border); border-left: 3px solid var(--hm-blue);
  border-radius: 6px; padding: 0.75rem 1.1rem; margin: 1.2rem 0; font-size: 0.9rem;
  background: var(--hm-surface); }
.hm-note p { margin: 0.3rem 0; }
/* Tableau des sources (page À propos) : lisible sans être un tableau de données.
   Quatre colonnes ne tiennent plus sur un téléphone : le tableau défile DANS son
   conteneur plutôt que de pousser la page entière de côté. La colonne de date est
   insécable — « juin 2026 » coupé en deux lignes ne se lit plus comme une date. */
.hm-sources-wrap { overflow-x: auto; }
.hm-sources { width: 100%; border-collapse: collapse; font-size: 0.9rem; margin: 0.6rem 0 1rem; }
.hm-sources th, .hm-sources td { text-align: left; padding: 0.45rem 0.7rem 0.45rem 0;
  border-bottom: 1px solid var(--hm-border-light); vertical-align: top; }
.hm-sources th { font-weight: 600; }
.hm-sources td.hm-when { white-space: nowrap; color: var(--hm-muted); }

/* --- Pied de page ------------------------------------------------------------------
   Le pied par défaut d'Observable (« Built with Observable on <date> ») ne disait rien
   d'utile et avait été coupé. Un site public en a pourtant besoin : c'est là que se
   rangent la provenance des données, le code source et le lien « À propos » — les trois
   choses qu'un visiteur cherche avant de citer un graphique. */
#observablehq-footer { max-width: var(--hm-measure); margin-top: 3rem; padding-top: 1.1rem;
  border-top: 1px solid var(--hm-border); font-size: 0.85rem; color: var(--hm-muted); }
#observablehq-footer nav { display: flex; flex-wrap: wrap; gap: 0.35rem 1.1rem; margin-bottom: 0.4rem; }
#observablehq-footer p { margin: 0.3rem 0; max-width: none; }

/* --- Accessibilité ------------------------------------------------------------------
   La légende cliquable était un <span onclick>. Elle se voyait comme un contrôle, se
   comportait comme un contrôle, mais n'était atteignable ni au clavier ni au lecteur
   d'écran : pas de rôle, pas d'ordre de tabulation, pas d'état annoncé. C'est un
   <button aria-pressed> depuis (voir components/hm.js) ; ces règles lui retirent
   l'apparence par défaut d'un bouton pour que le rendu, lui, ne change pas. */
button.hm-legend-item { font: inherit; color: inherit; background: none; border: none;
  padding: 0; margin: 0; text-align: left; }
.hm-legend-item:focus-visible, .hm-page-card:focus-visible, .hm-btn:focus-visible,
.hm-shortcut:focus-visible, .hm-skip:focus { outline: 2px solid var(--hm-brick); outline-offset: 2px; }
/* Lien d'évitement, injecté au build (scripts/postbuild.mjs) : sans lui, atteindre le
   contenu au clavier suppose de traverser toute la barre latérale, sur chaque page. */
/* Blanc sur brick retombe dans le même défaut que brick en couleur de texte (voir VARS) :
   le rapport est symétrique, donc un aplat brick avec du texte blanc dessus est tout
   autant sous les 4,5:1. Ce lien n'est visible qu'au focus clavier — c'est exactement le
   public qui doit pouvoir le lire. [href] dans le sélecteur : toujours un anchor
   (postbuild.mjs), même défaut de spécificité qu'à .hm-shortcut plus haut. */
.hm-skip[href] { position: absolute; left: -9999px; top: 0; z-index: 100;
  background: var(--hm-brick-text); color: var(--hm-bg); padding: 0.55rem 1rem;
  border-radius: 0 0 6px 0; text-decoration: none; font-weight: 600; }
.hm-skip:focus { left: 0; }
</style>`;


// --- Les métadonnées de <head> -------------------------------------------------------
// Observable Framework écrit lui-même <title> ; tout le reste de ce qu'un moteur de
// recherche ou un aperçu de partage lit doit être fourni ici. Trois familles :
//
//   description  ce que Google affiche sous le titre ;
//   og:* / twitter:*  la CARTE de partage. LinkedIn, Slack et WhatsApp récupèrent la page
//                depuis leurs serveurs et n'exécutent PAS de JavaScript : sans ces
//                balises, un lien partagé s'affiche en URL nue, sans titre ni vignette.
//                Leurs URL doivent être ABSOLUES (d'où SITE.url) ;
//   canonical    une seule adresse de référence par page, pour que « /synthese » et
//                « /synthese.html » ne se comptent pas comme deux pages concurrentes.
//
// `head` est ici une FONCTION : le framework l'appelle par page en lui passant son
// chemin, ce qui est la seule façon de donner à chacune sa propre description. Le CSS,
// lui, est identique partout et suit derrière.
const esc = (v) => String(v).replace(/&/g, "&amp;").replace(/"/g, "&quot;")
  .replace(/</g, "&lt;").replace(/>/g, "&gt;");
const tag = (attr, name, content) => `<meta ${attr}="${esc(name)}" content="${esc(content)}">`;

function META({path}) {
  const page = pageMeta(path);
  const title = page.path === "/" ? SITE.fullName : `${page.title} | ${SITE.name}`;
  const image = SITE.url + SITE.ogImage.path;
  const out = [tag("name", "description", page.description)];

  if (!page.indexable) {
    // La page 404 répond pour n'importe quelle URL fausse : l'indexer reviendrait à
    // publier autant de pages vides que d'adresses erronées.
    out.push(tag("name", "robots", "noindex, follow"));
    return "\n" + out.join("\n") + "\n";
  }

  out.push(`<link rel="canonical" href="${esc(page.url)}">`);
  out.push(tag("name", "author", SITE.author));
  out.push(
    // « website » partout : « article » annoncerait un contenu daté et signé, avec des
    // balises article:* que ces pages n'ont pas — ce sont des tableaux de bord tenus à
    // jour, pas des publications.
    tag("property", "og:type", "website"),
    tag("property", "og:site_name", SITE.name),
    tag("property", "og:locale", SITE.locale),
    tag("property", "og:title", title),
    tag("property", "og:description", page.description),
    tag("property", "og:url", page.url),
    tag("property", "og:image", image),
    tag("property", "og:image:width", SITE.ogImage.width),
    tag("property", "og:image:height", SITE.ogImage.height),
    tag("property", "og:image:alt", SITE.ogImage.alt),
    // « summary_large_image » demande la grande vignette plutôt que la miniature carrée.
    // La famille twitter:* est lue au-delà de X (Slack, Discord, Teams s'en servent en
    // repli quand une balise og: leur manque).
    tag("name", "twitter:card", "summary_large_image"),
    tag("name", "twitter:title", title),
    tag("name", "twitter:description", page.description),
    tag("name", "twitter:image", image),
  );

  // --- Données structurées ------------------------------------------------------------
  // DEUX pages en portent, et une seule chacune : l'accueil décrit le SITE, « À propos »
  // décrit son AUTEUR. Les répéter partout n'ajouterait rien et multiplierait les
  // occasions de divergence — mais les mettre au même endroit serait pire : un nœud
  // Person n'a de poids que sur la page dont il est le sujet, et le sujet de l'accueil
  // est le marché du logement.
  //
  // Les deux nœuds sont RELIÉS par `@id`, et c'est ce qui fait le travail. L'accueil ne
  // recopie pas l'auteur, elle le RÉFÉRENCE par son identifiant ; « À propos » définit
  // cet identifiant. Un moteur voit donc un seul auteur déclaré à un seul endroit, et
  // sait quelle page lire pour le connaître. Recopier le nom des deux côtés en aurait
  // fait deux entités homonymes de plus — exactement le problème qu'on cherche à régler.
  const AUTHOR_ID = SITE.url + AUTHOR.page + "#" + AUTHOR.anchor;
  const ld = (data) =>
    out.push(`<script type="application/ld+json">${JSON.stringify(
      {"@context": "https://schema.org", ...data})}</script>`);

  if (page.path === "/") {
    ld({
      "@type": "WebSite",
      name: SITE.fullName,
      alternateName: SITE.name,
      url: SITE.url + "/",
      inLanguage: SITE.lang,
      description: SITE.description,
      author: {"@id": AUTHOR_ID},
      license: "https://www.etalab.gouv.fr/licence-ouverte-open-licence/",
    });
  }

  if (page.path === AUTHOR.page) {
    // `mainEntity` dit que cette page a pour SUJET la personne — sans quoi elle n'est
    // qu'une page qui la mentionne, ce qu'était la situation d'avant. Le type reste
    // `ProfilePage` bien qu'À propos parle aussi de méthode et de sources : c'est la
    // seule page du site qui présente l'auteur, et Google n'offre pas de demi-mesure.
    ld({
      "@type": "ProfilePage",
      url: page.url,
      inLanguage: SITE.lang,
      mainEntity: {
        "@type": "Person",
        "@id": AUTHOR_ID,
        name: AUTHOR.name,
        url: page.url,
        description: AUTHOR.description,
        knowsAbout: AUTHOR.knowsAbout,
        // Le recoupement des homonymes (voir site.config.js).
        sameAs: AUTHOR.sameAs,
      },
    });
  }
  return "\n" + out.join("\n") + "\n";
}

// --- Pied de page --------------------------------------------------------------------
// Rendu au build sur toutes les pages (donc indexable, contrairement à ce que les pages
// construisent en JavaScript). Les liens relatifs sont réécrits par le framework.
const FOOTER = `<nav>
  <a href="/a-propos">À propos & méthode</a>
  <a href="/donnees">Sources & fraîcheur</a>
  <a href="${SITE.repo}">Code source</a>
</nav>
<p>Données publiques : INSEE, SDES (SIT@DEL, ECLN), IGEDD, Banque de France, BCE —
réutilisées sous Licence ouverte / Etalab. ${esc(SITE.name)} est un travail
d'analyse indépendant, sans lien avec ces organismes.</p>
<p>Les chiffres publiés ici sont des estimations et des projections : ils ne constituent
pas un conseil en investissement.</p>`;

export default {
  // `title` complète le <title> de CHAQUE page (« Synthèse | Baromètre du Logement — marché
  // logement en France ») : c'est la seule ligne que voit quelqu'un qui découvre le site
  // dans une page de résultats, d'où le titre qualifié plutôt que le nom seul. `home`
  // reste le nom court, parce que c'est lui qui s'affiche dans la barre latérale.
  title: SITE.fullName,
  home: SITE.name,
  root: "src",
  theme: ["air", "wide"],
  head: (page) => META(page) + STYLE,
  // Remplace le Source Serif 4 chargé par défaut avec le thème `air` : cette police
  // n'était jamais rendue (--serif est réécrit sur la pile de theme.json), le site la
  // téléchargeait pour rien. Source Sans 3 est, elle, la police du corps de texte.
  globalStylesheets: [
    "https://fonts.googleapis.com/css2?family=Source+Sans+3:ital,wght@0,300..900;1,300..900&display=swap",
  ],
  pages: PAGES,
  // Les 101 pages départementales, générées par src/departement/[code].md.
  // La liste vient des données (site.config.js), pas d'une énumération à la main.
  //
  // Note pour une reprise future : un data loader paramétré (src/departement/
  // [code].json.js avec FileAttachment("./[code].json") côté page) a été essayé ET
  // VÉRIFIÉ NE PAS MARCHER pour ce cas précis. Le build produit bien 101 fichiers
  // distincts, mais chaque page enregistre côté client la même référence LITTÉRALE
  // "./[code].json" (le framework ne substitue pas les paramètres de route avant
  // d'analyser les FileAttachment) — donc les 101 pages reçoivent au runtime le même
  // fichier générique vide, jamais leurs propres données. Vérifié en inspectant
  // dist/departement/75.html : son registerFile("./[code].json", ...) pointe vers un
  // fichier de 2 octets ("{}"), pas vers le Paris à 9 730 €/m². D'où le fetch() vers
  // l'adresse stable ci-dessous (voir scripts/postbuild.mjs) dans la page elle-même.
  dynamicPaths: DEP_PATHS,
  // Sommaire de page, à DROITE. La barre latérale répond à « où suis-je dans le
  // site » ; mêler les sections d'une page à cette liste de dix entrées lui ferait
  // perdre sa lecture d'ensemble. Le défaut reste `false` — l'accueil n'en a pas —
  // et chaque page l'active dans son front-matter.
  //
  // Le sommaire est construit AU BUILD, en relisant les <h2> du HTML rendu : un
  // titre posé par `display(html`<h2>…`)` n'y figure jamais. C'est pourquoi les
  // sections conditionnelles de macro.md portent un titre Markdown statique.
  toc: {show: false, label: "Sur cette page"},
  pager: false,
  footer: FOOTER,
};
