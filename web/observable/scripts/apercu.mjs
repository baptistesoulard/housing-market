// Captures d'écran du site CONSTRUIT, pour vérifier un rendu sans navigateur sous la main.
//
// CLAUDE.md le dit : « Rien ne teste le RENDU ». Les tests lisent les sources et les JSON,
// le build valide la syntaxe — mais une cellule qui lève une erreur, une légende vide ou un
// tableau mal monté ne se voient qu'à l'écran. Ce script ouvre les pages de `dist/` servies
// en local, attend que les cellules aient tourné, et écrit pour chacune une capture pleine
// page (bureau et téléphone) plus la liste des erreurs de console. Il ne juge rien : il
// montre. Lancé par .github/workflows/apercu-rendu.yml.
//
// Usage : node scripts/apercu.mjs http://localhost:3000 sortie/ /previsions /carte …
import {mkdir, writeFile} from "node:fs/promises";
import {chromium} from "playwright";

const [base, sortie, ...pages] = process.argv.slice(2);
const FORMATS = [{nom: "bureau", width: 1280, height: 900}, {nom: "mobile", width: 390, height: 844}];

await mkdir(sortie, {recursive: true});
const navigateur = await chromium.launch();
const rapport = [];
for (const page of pages) {
  for (const f of FORMATS) {
    const ctx = await navigateur.newContext({viewport: {width: f.width, height: f.height}});
    const p = await ctx.newPage();
    const erreurs = [];
    p.on("console", (m) => { if (m.type() === "error") erreurs.push(m.text()); });
    p.on("pageerror", (e) => erreurs.push(String(e)));
    await p.goto(base + page, {waitUntil: "networkidle"});
    await p.waitForTimeout(1500);                       // cellules asynchrones, polices
    // Une cellule en échec ne casse pas la page : le framework affiche son erreur à la
    // place du contenu. C'est ce texte-là qu'il faut repérer.
    const enEchec = await p.locator(".observablehq--error").count();
    const nom = `${page.replace(/^\//, "").replace(/\//g, "_") || "accueil"}-${f.nom}.png`;
    await p.screenshot({path: `${sortie}/${nom}`, fullPage: true});
    rapport.push({page, format: f.nom, capture: nom, cellules_en_echec: enEchec, erreurs});
    await ctx.close();
  }
}
await navigateur.close();
await writeFile(`${sortie}/rapport.json`, JSON.stringify(rapport, null, 1));
const total = rapport.reduce((n, r) => n + r.cellules_en_echec + r.erreurs.length, 0);
console.log(`[apercu] ${rapport.length} captures, ${total} erreur(s)`);
