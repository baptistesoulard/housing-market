// Génère assets/og-image.png — la vignette qu'affichent LinkedIn, Slack ou WhatsApp
// quand on partage un lien du site.
//
// Pourquoi un script et pas un fichier dessiné à la main : les couleurs, le logo et le
// nom viennent de theme.json et site.config.js, donc la vignette suit l'identité du site
// au lieu de dériver silencieusement dès qu'on retouche la palette.
//
// Pourquoi le PNG est COMMITÉ et pas produit au build : Cloudflare Pages ne construit que
// du Node, et fabriquer cette image demande un navigateur. Le build se contente donc de
// copier le fichier (scripts/postbuild.mjs) ; ce script-ci se relance à la main, quand
// l'identité change :
//
//     npm --prefix web/observable install --no-save playwright
//     npm --prefix web/observable run og-image
//
// 1200×630 est le format que LinkedIn, X et Slack recadrent le moins ; le texte reste
// donc à bonne distance des bords, chaque plateforme rognant un peu différemment.
//
// ⚠️ Les polices ne sont PAS embarquées : l'image est rendue avec la meilleure sans-serif
// installée sur la machine qui exécute ce script. Deux machines peuvent donc produire des
// vignettes légèrement différentes — sans conséquence, puisque le résultat est versionné,
// mais c'est la raison pour laquelle on ne régénère pas cette image à chaque build.
import {mkdir, writeFile} from "node:fs/promises";
import {fileURLToPath} from "node:url";
import {dirname, join} from "node:path";
import {SITE, THEME as T, MARK_SVG} from "../site.config.js";

let chromium;
try {
  ({chromium} = await import("playwright"));
} catch {
  console.error(
    "og-image : playwright est introuvable. Il n'est pas une dépendance du site (le build " +
    "de production n'en a pas besoin) ; l'installer le temps de la génération :\n" +
    "    npm --prefix web/observable install --no-save playwright");
  process.exit(1);
}

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const OUT = join(ROOT, "assets", "og-image.png");
const {width, height} = SITE.ogImage;

const html = `<!doctype html><meta charset="utf-8">
<style>
  @page { margin: 0 }
  * { box-sizing: border-box; margin: 0; }
  body { width: ${width}px; height: ${height}px; background: ${T.brand.bg};
         font-family: "Source Sans 3", "Segoe UI", system-ui, sans-serif;
         color: ${T.brand.ink}; display: flex; flex-direction: column;
         justify-content: space-between; padding: 54px 64px 50px; overflow: hidden; }
  .brand { display: flex; align-items: center; gap: 18px; }
  .brand svg { width: 54px; height: 54px; }
  .brand .n { font-size: 34px; font-weight: 700; letter-spacing: -0.5px; }
  /* Les tailles sont calées pour tenir SANS police web : ce script rend avec la
     sans-serif de la machine, souvent plus large que Source Sans 3. Une valeur ajustée
     sur la police idéale déborderait ailleurs. */
  h1 { font-size: 50px; line-height: 1.1; font-weight: 700; letter-spacing: -1.2px;
       max-width: 20ch; }
  .rule { width: 104px; height: 7px; border-radius: 4px; background: ${T.brand.brick};
          margin: 22px 0 20px; }
  .sub { font-size: 26px; line-height: 1.35; color: ${T.ui.muted}; max-width: 34ch; }
  /* L'adresse du site n'est PAS gravée dans l'image : elle vit dans HM_SITE_URL et peut
     changer, alors qu'un PNG committé, lui, resterait sur l'ancienne. */
  .foot { display: flex; align-items: flex-end; justify-content: space-between; gap: 32px; }
  .foot .src { font-size: 19px; color: ${T.ui.subtle}; line-height: 1.4; }
  /* Trois barres croissantes aux couleurs de séries : le sujet du site (des séries qui
     montent et descendent) plutôt qu'un aplat décoratif. */
  .bars { display: flex; align-items: flex-end; gap: 11px; height: 72px; flex: none; }
  .bars i { width: 24px; border-radius: 5px 5px 0 0; display: block; }
</style>
<div class="brand">${MARK_SVG}<span class="n">${SITE.name}</span></div>
<div>
  <h1>Où en est le marché du logement en France&nbsp;?</h1>
  <div class="rule"></div>
  <div class="sub">Neuf, ancien, prix, financement — et la prévision des transactions à 12-18 mois.</div>
</div>
<div class="foot">
  <div class="src">Données publiques : INSEE · SDES · IGEDD · Banque de France · BCE<br>
    Mises à jour chaque semaine, méthode et code ouverts.</div>
  <div class="bars">
    <i style="height: 38%; background: ${T.series.brick}"></i>
    <i style="height: 62%; background: ${T.series.blue}"></i>
    <i style="height: 100%; background: ${T.series.green}"></i>
  </div>
</div>`;

// HM_CHROMIUM permet de viser un Chromium déjà présent sur la machine plutôt que celui
// que Playwright télécharge — utile quand `npx playwright install` n'est pas envisageable
// (poste sans accès réseau, image de conteneur qui embarque déjà un navigateur).
const browser = await chromium.launch(
  process.env.HM_CHROMIUM ? {executablePath: process.env.HM_CHROMIUM} : {});
const page = await browser.newPage({viewport: {width, height}, deviceScaleFactor: 1});
await page.setContent(html, {waitUntil: "load"});
await mkdir(join(ROOT, "assets"), {recursive: true});
await writeFile(OUT, await page.screenshot({type: "png"}));
console.log(`og-image : ${OUT} (${width}×${height})`);

// Les favicons matricielles, rendues ici pour la même raison (il faut un navigateur).
// La favicon SVG suffit aux navigateurs, pas à Google : il la pixellise sur un fond BLANC
// opaque, et le logo apparaissait dans un carré blanc au milieu de sa pastille grise
// (constaté le 2026-11-01). Un PNG transparent, lui, est repris tel quel. Taille multiple
// de 48 px, comme Google le demande ; favicon.ico (le même PNG à 48 px dans un conteneur
// ICO) parce que des robots la cherchent à la racine sans lire le <head>.
const icon = async (size) => {
  const p = await browser.newPage({viewport: {width: size, height: size}, deviceScaleFactor: 1});
  await p.setContent(`<!doctype html><style>*{margin:0}svg{display:block;width:${size}px;height:${size}px}</style>${MARK_SVG}`);
  const png = await p.screenshot({type: "png", omitBackground: true});
  await p.close();
  return png;
};
await writeFile(join(ROOT, "assets", "favicon-96.png"), await icon(96));
const png48 = await icon(48);
// En-tête ICO (6 octets) + une entrée de répertoire (16 octets), puis le PNG brut.
const ico = Buffer.alloc(22);
ico.writeUInt16LE(1, 2);                 // type : icône
ico.writeUInt16LE(1, 4);                 // une image
ico.writeUInt8(48, 6); ico.writeUInt8(48, 7);
ico.writeUInt16LE(1, 10);                // plans
ico.writeUInt16LE(32, 12);               // bits par pixel
ico.writeUInt32LE(png48.length, 14);
ico.writeUInt32LE(22, 18);               // décalage de l'image
await writeFile(join(ROOT, "assets", "favicon.ico"), Buffer.concat([ico, png48]));
await browser.close();
console.log("og-image : assets/favicon-96.png et assets/favicon.ico");
