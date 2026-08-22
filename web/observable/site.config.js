import {readFileSync} from "node:fs";
import {fileURLToPath} from "node:url";
import {dirname, join} from "node:path";

const _dir = dirname(fileURLToPath(import.meta.url));

/** Le thème du site — mêmes couleurs pour le CSS, le logo et la vignette de partage. */
export const THEME = JSON.parse(readFileSync(join(_dir, "..", "theme.json"), "utf-8"));

// --- Le logo -------------------------------------------------------------------------
// Dessiné en SVG plutôt que servi en fichier binaire : les deux couleurs viennent de
// theme.json, comme le reste du thème. Motif : le toit d'une maison au-dessus de trois
// barres croissantes — logement + série temporelle.
//
// Il vit ici, et non dans observablehq.config.js, parce qu'il a maintenant TROIS
// consommateurs : le bloc de marque de la barre latérale (en CSS, via une data URI), la
// favicon écrite au build, et la vignette de partage. Une seule définition.
export const MARK_SVG =
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">` +
  `<rect width="32" height="32" rx="8" fill="${THEME.brand.brick}"/>` +
  `<path d="M6.5 15.2 16 7.5l9.5 7.7" fill="none" stroke="${THEME.brand.bg}" ` +
  `stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>` +
  `<g fill="${THEME.brand.bg}">` +
  `<rect x="9.6" y="21.6" width="4" height="3.9" rx="1.1"/>` +
  `<rect x="14.9" y="19" width="4" height="6.5" rx="1.1"/>` +
  `<rect x="20.2" y="16.3" width="4" height="9.2" rx="1.1"/>` +
  `</g></svg>`;

/** Le même logo en data URI, pour être posé directement dans du CSS (aucune requête). */
export const MARK = "data:image/svg+xml," + encodeURIComponent(MARK_SVG);

// Identité publique du site — source unique, lue par TROIS cibles :
//   1. observablehq.config.js  — <head> (title, description, Open Graph, canonique) et
//      barre latérale (NAV) ;
//   2. scripts/postbuild.mjs   — robots.txt, sitemap.xml, attribut lang ;
//   3. scripts/og-image.mjs    — la vignette partagée sur les réseaux.
//
// Le fichier est volontairement séparé de observablehq.config.js : celui-ci porte déjà
// tout le CSS du site, et une adresse publique n'a pas à être cherchée au milieu de
// 200 lignes de styles.
//
// ── L'ADRESSE DU SITE ──────────────────────────────────────────────────────────────
// `url` sert à écrire des URL ABSOLUES, seule forme que Open Graph accepte : LinkedIn,
// Slack ou WhatsApp récupèrent la page depuis leurs serveurs, où un chemin relatif ne
// veut rien dire. Une valeur fausse ne casse pas le site — elle casse silencieusement
// l'aperçu au partage et la balise canonique.
//
// Elle se règle par la variable d'environnement HM_SITE_URL (Cloudflare Pages :
// Settings → Environment variables), sans toucher au code. Le repli ci-dessous est
// l'adresse *.pages.dev par défaut du projet ; à remplacer par le domaine définitif le
// jour où il y en a un.
const DEFAULT_URL = "https://housing-market.pages.dev";

const url = (process.env.HM_SITE_URL || DEFAULT_URL).replace(/\/+$/, "");

// --- L'auteur ------------------------------------------------------------------------
// Déclaré comme une ENTITÉ, pas comme une chaîne de caractères, et c'est tout l'enjeu.
// Le JSON-LD de l'accueil portait `author: {"@type": "Person", name: "Baptiste Soulard"}` :
// un nom nu, que rien ne relie à quoi que ce soit. Or « Baptiste Soulard » est porté par
// plusieurs personnes — un arbitre de la FFF, un traileur classé à l'UTMB, un dirigeant
// de société — et aucune ne domine les résultats de recherche. Sans `sameAs`, un moteur
// n'a aucun moyen de savoir laquelle publie ce site, ni que l'auteur du dépôt GitHub est
// la même personne : il voit trois homonymes et n'en recoupe aucun.
//
// `sameAs` est précisément le mécanisme prévu pour ça : il déclare « ces profils sont la
// même personne que moi ». C'est ce qui permet à un moteur de fusionner des profils épars
// en UNE entité, et de rattacher ce site à elle.
//
// Les adresses sont NETTOYÉES de leurs paramètres de suivi — le lien LinkedIn partagé
// depuis l'application arrive avec `?utm_source=share_via&utm_content=profile&…`, qui
// identifie le PARTAGE et non le profil. Une URL déclarée canonique doit être stable et
// n'exister qu'en un exemplaire, sinon elle se recoupe avec elle-même.
//
// Ce qui n'y figure PAS est aussi délibéré : aucune adresse électronique. Le dépôt est
// public, et une adresse dans un fichier versionné est moissonnée exactement comme un
// `mailto:` — c'est la raison d'être du formulaire de contact et de `CONTACT_TO` (voir
// web/README.md). Le contact passe par le formulaire, jamais par une balise.
export const AUTHOR = {
  name: "Baptiste Soulard",
  // La page qui parle de lui. Il n'y a PAS de page dédiée — choix assumé : le site parle
  // du marché du logement, pas de son auteur. La section « Qui écrit » d'À propos porte
  // donc l'entité, et cette ancre est son identifiant stable.
  page: "/a-propos",
  anchor: "auteur",
  // Une phrase, à la troisième personne : c'est ce qu'un moteur peut afficher sous le nom.
  description:
    "Auteur de HousingMarket, un baromètre indépendant du marché du logement en France " +
    "construit sur des données publiques, en accès libre et au code ouvert.",
  // Les sujets que le site DÉMONTRE, pas une liste de compétences déclarées : chacun est
  // adossé à des pages publiées. Le logement passe en premier — l'ordre n'a rien
  // d'obligatoire, mais une liste dont les trois premiers termes divergent dit mal de
  // quoi son sujet est l'expert.
  //
  // Pas de `jobTitle`. « Supply chain and tech enthusiast » est une description de soi,
  // pas un intitulé de poste : le champ attend un rôle (« Analyste de données »,
  // « Planificateur »), et le renseigner de travers vaut moins que de le laisser vide.
  // Ce trait est dit dans la PROSE de la page, où il explique quelque chose au lieu de
  // remplir une case — voir la section « Qui écrit » d'a-propos.md.
  knowsAbout: [
    "Marché immobilier français",
    "Marché du logement",
    "Prévision de la demande",
    "Prévision de séries temporelles",
    "Analyse de données",
    "Données publiques ouvertes",
    "Supply chain",
  ],
  // Les profils à recouper. L'ordre n'a pas d'importance pour un moteur ; il suit ici
  // celui du site (code, écrits, professionnel).
  sameAs: [
    "https://github.com/baptistesoulard",
    "https://soulard-baptiste-bs.medium.com/",
    "https://www.linkedin.com/in/baptistesoulard1994",
  ],
};

export const SITE = {
  url,
  name: "HousingMarket",
  tagline: "Marché du logement en France",
  // Le nom qualifié : ce qui part dans <title> et dans la carte de partage. « HousingMarket »
  // seul ne dit pas de quel marché il s'agit, ni dans quel pays — or c'est souvent la seule
  // ligne lue avant le clic.
  fullName: "HousingMarket — Marché du logement en France",
  // Description par défaut : celle de l'accueil, reprise par toute page qui n'en
  // déclare pas (page 404, page ajoutée sans entrée dans PAGES).
  // ~155 caractères : au-delà, Google tronque et LinkedIn coupe l'aperçu. Le propos
  // long tient dans le corps de la page d'accueil, pas dans la balise.
  description:
    "Baromètre du marché du logement en France : construction neuve, ventes dans " +
    "l'ancien, prix, financement et prévision des transactions. Données publiques.",
  locale: "fr_FR",
  lang: "fr",
  // Le nom vient de AUTHOR : deux copies d'un nom propre finissent par diverger.
  author: AUTHOR.name,
  repo: "https://github.com/baptistesoulard/housing-market",
  // Vignette de partage. 1200×630 est le format que LinkedIn, X et Slack recadrent le
  // moins ; le fichier est COMMITÉ (voir scripts/og-image.mjs pour le régénérer).
  ogImage: {path: "/og-image.png", width: 1200, height: 630,
            alt: "HousingMarket — baromètre du marché du logement en France"},
};

// Les pages du site, dans l'ordre de la barre latérale.
//
//   icon        emoji de la gouttière (séparé du libellé : les emojis n'ont pas tous la
//               même chasse, cf. le CSS de la barre latérale) ;
//   name        libellé de navigation ;
//   path        chemin servi, sans extension ;
//   description meta description ET texte du sommaire de l'accueil. UNE phrase, propre
//               à la page : deux pages qui partagent leur description se cannibalisent
//               dans les résultats de recherche.
//   nav: false  page servie et indexée, mais absente de la barre latérale.
//   seoTitle    <title> et og:title, quand le libellé de navigation ne suffit pas. « À
//               propos » est parfait dans une barre latérale, où le contexte est donné
//               par tout ce qui l'entoure, et muet dans une page de résultats, où il
//               n'est entouré de rien. Le libellé reste court, le titre porte le nom.
export const NAV = [
  {icon: "🏡", name: "Accueil", path: "/", nav: false,
   description: SITE.description},
  {icon: "🧭", name: "Synthèse", path: "/synthese",
   description: "L'état du marché du logement français en un coup d'œil : neuf, ancien " +
     "et financement, avec les chiffres clés du dernier mois publié."},
  {icon: "🏗️", name: "Marché du neuf", path: "/neuf",
   description: "Permis et mises en chantier (SIT@DEL), individuel contre collectif, " +
     "commercialisation ECLN : encours, délai d'écoulement, acquéreurs et prix au m²."},
  {icon: "🏠", name: "Marché de l'ancien", path: "/ancien",
   description: "Ventes de logements anciens (IGEDD), prix Notaires-INSEE, capacité " +
     "d'emprunt à mensualité constante et indice d'accessibilité, neuf contre ancien."},
  {icon: "🏦", name: "Environnement & Financement", path: "/macro",
   description: "Taux de crédit, Euribor et OAT, confiance des ménages, intentions " +
     "d'achat, chômage, production de crédits habitat et demande de crédits (enquête BLS)."},
  {icon: "📰", name: "Actualités & Aides", path: "/actualites",
   description: "Veille des dispositifs d'aide au logement en France et en Europe : " +
     "MaPrimeRénov', PTZ, DPE, CEE — impacts par pilier et échéancier des mesures."},
  // Les deux pages suivantes n'ont PAS de JSON statique : elles appellent l'API HTTP
  // (voir src/components/api.js). Sans instance désignée, elles affichent un encart qui
  // explique où en lancer une — le reste du site continue de fonctionner seul.
  {icon: "📡", name: "Prévision & Scénarios", path: "/previsions",
   description: "Prévision des transactions de logements à 12-18 mois : modèle à deux " +
     "étages, backtest hors échantillon et scénarios à quatre leviers."},
  {icon: "🎯", name: "Prévisions passées", path: "/previsions-passees",
   description: "Toutes les prévisions de transactions produites par le modèle, face au " +
     "réalisé : erreur par horizon et comparaison avec une prévision naïve."},
  {icon: "⚙️", name: "Données & Sources", path: "/donnees",
   description: "Sources, fraîcheur des séries et méthode de calcul, avec import local " +
     "d'un fichier de ventes pour le confronter aux indicateurs de marché."},
  {icon: "ℹ️", name: "À propos", path: "/a-propos",
   seoTitle: "À propos — Baptiste Soulard",
   description: "Baptiste Soulard publie ce baromètre du marché du logement : " +
     "sources publiques, méthode, limites et calculs reproductibles."},
];

/** Les pages indexables, dans l'ordre du sitemap. */
export const INDEXABLE = NAV.map(({path}) => path);

/**
 * Métadonnées de la page servie à `path`.
 *
 * Observable Framework passe à `head()` le chemin INTERNE de la page, où l'accueil
 * s'appelle « /index » ; c'est aussi lui qui sert la page 404. On normalise les deux
 * ici pour que le reste du code ne connaisse qu'un seul vocabulaire de chemins.
 */
export function pageMeta(path) {
  const clean = path === "/index" ? "/" : path;
  const entry = NAV.find((p) => p.path === clean);
  return {
    path: clean,
    // La 404 ne doit pas être indexée : elle répond pour n'importe quelle URL fausse,
    // et une adresse canonique n'aurait aucun sens.
    indexable: Boolean(entry),
    // Le libellé de navigation par défaut ; `seoTitle` prend le dessus quand la page
    // en déclare un (voir l'en-tête de NAV).
    title: entry ? (entry.seoTitle || entry.name) : null,
    description: entry ? entry.description : SITE.description,
    url: SITE.url + (clean === "/" ? "/" : clean),
  };
}
