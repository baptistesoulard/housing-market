// Ce que `observable build` ne sait pas faire, et qu'un site public doit avoir.
//
// Lancé par `npm run build`, juste après le build du framework, sur dist/ :
//
//   1. lang="fr" sur <html> — Observable Framework écrit un <html> NU, sans attribut de
//      langue, et n'offre pas d'option pour le changer. Sans lui, un lecteur d'écran
//      prononce le français avec la voix par défaut (souvent l'anglais) et les moteurs
//      doivent deviner la langue de la page. C'est le critère WCAG 3.1.1.
//   2. Un lien d'évitement en tête de <body> — sinon, atteindre le contenu au clavier
//      suppose de traverser les huit liens de la barre latérale, sur CHAQUE page.
//   3. Une favicon — le framework n'en pose aucune, et un onglet sans icône dans une
//      barre d'onglets pleine est un onglet qu'on ne retrouve pas. Elle est ÉCRITE ici
//      plutôt que déclarée dans le <head> du framework : celui-ci réécrit les chemins de
//      <link href>, ce qui donnerait une adresse hachée impossible à annoncer, alors
//      qu'un robot d'indexation attend /favicon.svg à la racine.
//   4. La vignette de partage, copiée à une adresse STABLE — les fichiers de src/ que le
//      framework copie reçoivent un nom haché, incompatible avec l'URL absolue que les
//      balises Open Graph doivent annoncer. Elle vit donc dans assets/, hors de src/.
//   5. robots.txt et sitemap.xml — absents du framework, et c'est par le second qu'un
//      moteur découvre les pages qu'aucun lien externe ne pointe encore.
//
// Réécrire du HTML après coup n'est pas élégant ; c'est la seule prise disponible pour
// les points 1 et 2 tant que le framework n'expose pas ces réglages. Le traitement est
// idempotent : relancé sur un dist/ déjà traité, il ne double rien.
import {copyFile, mkdir, readdir, readFile, writeFile} from "node:fs/promises";
import {existsSync} from "node:fs";
import {fileURLToPath} from "node:url";
import {dirname, join, resolve} from "node:path";
import {SITE, INDEXABLE, MARK_SVG, depMeta} from "../site.config.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
// Le répertoire de sortie est paramétrable pour que les tests puissent faire tourner ce
// script sur un dist/ jetable plutôt que sur celui du dépôt.
const DIST = process.argv[2] ? resolve(process.argv[2]) : join(ROOT, "dist");
const SKIP = `<a class="hm-skip" href="#observablehq-main">Aller au contenu</a>`;
const ICON = `<link rel="icon" href="/favicon.svg" type="image/svg+xml">`;

/** Tous les .html de dist/, à n'importe quelle profondeur. */
async function htmlFiles(dir) {
  const out = [];
  for (const entry of await readdir(dir, {withFileTypes: true})) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...await htmlFiles(full));
    else if (entry.name.endsWith(".html")) out.push(full);
  }
  return out;
}

const pages = await htmlFiles(DIST);
if (pages.length === 0) throw new Error(`Aucun HTML dans ${DIST} — le build a-t-il tourné ?`);

let patched = 0;
for (const file of pages) {
  const before = await readFile(file, "utf-8");
  let after = before;
  // `<html>` nu uniquement : si un attribut lang est déjà là, on ne le touche pas.
  after = after.replace(/<html>/i, `<html lang="${SITE.lang}">`);
  if (!after.includes('class="hm-skip"')) after = after.replace(/<body>/i, `<body>${SKIP}`);
  if (!after.includes('rel="icon"')) after = after.replace(/<meta charset="utf-8">/i, `$&\n${ICON}`);
  if (after !== before) { await writeFile(file, after); patched++; }
}

await writeFile(join(DIST, "favicon.svg"), MARK_SVG + "\n");

// La vignette de partage est un fichier COMMITÉ (scripts/og-image.mjs la régénère), pas
// un artefact de build : Cloudflare Pages ne construit que du Node, et la produire
// demanderait un navigateur. Son absence n'arrête donc pas le build — elle dégrade
// l'aperçu au partage, ce que ce message signale.
const og = join(ROOT, "assets", "og-image.png");
if (existsSync(og)) await copyFile(og, join(DIST, "og-image.png"));
else console.warn(
  `postbuild: ATTENTION — ${og} est absent. Les balises og:image pointent vers une image ` +
  "qui n'existe pas : un lien partagé s'affichera sans vignette. Régénérer avec `npm run og-image`.");

// 6. Les données départementales, copiées à une adresse STABLE.
//
//    Le framework ne copie dans dist/ que les fichiers qu'il voit référencés par un
//    `FileAttachment` littéral. Une page paramétrée construit le nom de son fichier à
//    partir de son paramètre de route : il n'y a rien à voir au build, donc rien n'est
//    copié — vérifié, dist/_file/data/departements/ reste vide. La page les lit donc par
//    fetch("/data/departements/<code>.json"), ce qui suppose qu'elles soient là.
//
//    Même raison que pour la vignette de partage : les fichiers que le framework copie
//    reçoivent un nom haché, incompatible avec une URL construite à l'exécution.
const depSrc = join(ROOT, "src", "data", "departements");
if (existsSync(depSrc)) {
  const cible = join(DIST, "data", "departements");
  await mkdir(cible, {recursive: true});
  const fichiers = (await readdir(depSrc)).filter((f) => f.endsWith(".json"));
  for (const f of fichiers) await copyFile(join(depSrc, f), join(cible, f));
  const index = join(ROOT, "src", "data", "departements.json");
  if (existsSync(index)) await copyFile(index, join(DIST, "data", "departements.json"));
  console.log(`postbuild: ${fichiers.length} fichier(s) départemental(aux) copié(s) vers /data/departements/`);
} else {
  console.warn(
    "postbuild: ATTENTION — src/data/departements/ est absent. Les pages départementales " +
    "se construiront mais ne trouveront aucune donnée. Lancer `python web/export/web_export.py`.");
}

// 7. Le <title> des pages départementales.
//
//    Observable Framework écrit <title> à partir du front-matter de la page. Une route
//    paramétrée n'a qu'UN front-matter pour ses 101 pages : sans ce correctif, les 101
//    portent le même titre, ce qui est exactement la cannibalisation que des descriptions
//    distinctes cherchent à éviter — le titre est la première chose que lit un moteur.
//
//    `head()` ne peut pas le faire : le framework y ajoute son propre <title> APRÈS. La
//    réécriture après coup est, là encore, la seule prise disponible.
let titres = 0;
for (const file of pages) {
  const rel = file.slice(DIST.length).replace(/\\/g, "/").replace(/\.html$/, "");
  const meta = depMeta(rel);
  if (!meta) continue;
  const html = await readFile(file, "utf-8");
  const attendu = `<title>${meta.title} | ${SITE.name}</title>`;
  const patched = html.replace(/<title>[\s\S]*?<\/title>/i, attendu);
  if (patched !== html) { await writeFile(file, patched); titres++; }
}
if (titres) console.log(`postbuild: ${titres} titre(s) départemental(aux) personnalisé(s)`);

// Le sitemap ne liste QUE les pages voulues (site.config.js), jamais le contenu de
// dist/ : celui-ci contient aussi la 404 et les modules internes du framework, qui n'ont
// rien à faire dans un index de moteur de recherche.
const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${INDEXABLE.map((p) => `  <url><loc>${SITE.url}${p === "/" ? "/" : p}</loc></url>`).join("\n")}
</urlset>
`;
await writeFile(join(DIST, "sitemap.xml"), sitemap);

const robots = `User-agent: *
Allow: /

Sitemap: ${SITE.url}/sitemap.xml
`;
await writeFile(join(DIST, "robots.txt"), robots);

console.log(
  `postbuild: ${patched}/${pages.length} page(s) complétée(s) (lang="${SITE.lang}", lien d'évitement, favicon), ` +
  `sitemap de ${INDEXABLE.length} URL, robots.txt → ${SITE.url}`
);
if (SITE.url.includes("pages.dev") && !process.env.HM_SITE_URL) {
  console.warn(
    "postbuild: ATTENTION — HM_SITE_URL n'est pas défini, l'adresse de repli de " +
    "site.config.js a été utilisée. Les URL canoniques, le sitemap et l'aperçu de " +
    "partage pointent donc vers " + SITE.url + "."
  );
}
