// Configuration Observable Framework — dashboard HousingMarket (site statique).
// `npm run build` produit web/observable/dist/, déployé sur Cloudflare Pages (Node-only).
//
// Les couleurs viennent de web/theme.json (source unique de vérité, partagée avec le
// Python d'export et le module src/components/theme.js). Elles sont projetées ici en
// variables CSS --hm-* : aucune valeur hexadécimale n'est écrite en dur dans ce fichier.
import {readFileSync} from "node:fs";
import {fileURLToPath} from "node:url";
import {dirname, join} from "node:path";

const _dir = dirname(fileURLToPath(import.meta.url));
const T = JSON.parse(readFileSync(join(_dir, "..", "theme.json"), "utf-8"));

// {--hm-xxx: valeur} à plat, à partir des groupes du thème.
const VARS = Object.entries({
  "font-sans": T.font.sans,
  bg: T.brand.bg,
  surface: T.brand.surface,
  ink: T.brand.ink,
  brick: T.brand.brick,
  blue: T.brand.blue,
  green: T.brand.green,
  link: T.ui.link,
  subtle: T.ui.subtle,
  muted: T.ui.muted,
  rule: T.ui.rule,
  border: T.ui.border,
  "border-light": T.ui.borderLight,
  "delta-pos": T.delta.positive,
  "delta-neg": T.delta.negative,
}).map(([k, v]) => `  --hm-${k}: ${v};`).join("\n");

const STYLE = `
<style>
:root {
${VARS}
  --sans-serif: var(--hm-font-sans);
  --serif: var(--hm-font-sans);
}
body { font-family: var(--sans-serif); color: var(--hm-ink); background: var(--hm-bg); }
h1, h2, h3, h4 { font-family: var(--sans-serif); color: var(--hm-ink); }
h1 { font-weight: 700; border-bottom: 2px solid var(--hm-brick); padding-bottom: 8px; margin-bottom: 0.15rem; }
main h2 { font-size: 1.55rem; font-weight: 700; margin-top: 2.4rem; padding-bottom: 0.3rem; border-bottom: 1px solid var(--hm-border); }
main h3 { font-size: 1.3rem; font-weight: 700; color: var(--hm-ink); margin-top: 2.2rem; margin-bottom: 0.5rem; padding-bottom: 0.3rem; border-bottom: 1px solid var(--hm-border-light); }
a, a:visited { color: var(--hm-link); }
.hm-caption { color: var(--theme-foreground-muted); font-size: 0.92rem; max-width: 64rem; margin: 0.2rem 0 1rem; }
.hm-chips { margin: 0.4rem 0 1.2rem; }
.hm-takeaways { background: color-mix(in srgb, var(--hm-blue) 12%, transparent); border-left: 4px solid var(--hm-blue);
  border-radius: 8px; padding: 0.9rem 1.1rem; margin: 0.6rem 0 1rem; max-width: 64rem; }
.hm-takeaways ul { margin: 0.3rem 0 0; padding-left: 1.1rem; }
.hm-takeaways li { margin: 0.35rem 0; line-height: 1.5; }
.hm-meta { color: var(--theme-foreground-muted); font-size: 0.85rem; margin: 0.4rem 0 0.2rem; }
.hm-grid { display: grid; gap: 1.8rem 1.6rem; margin: 0.8rem 0 0.4rem;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); }
.hm-card { padding: 0.15rem 0; background: transparent; border: none; }
.hm-card-title { font-weight: 600; font-size: 0.86rem; color: var(--hm-muted); letter-spacing: 0.2px; }
.hm-card-value { font-size: 1.6rem; font-weight: 700; color: var(--hm-ink); margin: 0.5rem 0 0.4rem; line-height: 1.15; }
.hm-card-sub { font-size: 0.8rem; color: var(--theme-foreground-muted); line-height: 1.45; }
.hm-delta { font-size: 0.95rem; font-weight: 700; }
.hm-delta.pos { color: var(--hm-delta-pos); }
.hm-delta.neg { color: var(--hm-delta-neg); }
.hm-link { color: var(--theme-foreground-muted); font-size: 0.83rem; margin: 0.5rem 0 2rem; }
.hm-panels { display: grid; gap: 1rem 1.4rem; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); }
.hm-panel-title { font-weight: 600; font-size: 0.98rem; color: var(--hm-ink); margin: 0.4rem 0 0.1rem; }
.hm-panel-sub { color: var(--theme-foreground-muted); font-size: 0.82rem; margin-bottom: 0.2rem; }
.hm-legend { display: flex; flex-wrap: wrap; gap: 0.4rem 1.3rem; margin: 0.6rem 0 0.1rem; }
.hm-legend-item { display: inline-flex; align-items: center; gap: 0.45rem; cursor: pointer; font-size: 0.9rem; user-select: none; }
.hm-legend-item.off { opacity: 0.4; text-decoration: line-through; }
.hm-swatch { width: 16px; height: 3px; border-radius: 2px; display: inline-block; }
.hm-chart-title { font-weight: 600; margin: 1rem 0 0; }
.hm-chart-title .sub { color: var(--hm-subtle); font-weight: 400; }
details.hm-howto { margin: 0.2rem 0 0.8rem; max-width: 64rem; }
details.hm-howto summary { cursor: pointer; color: var(--theme-foreground-muted); }
</style>`;

export default {
  title: "HousingMarket",
  root: "src",
  theme: ["air", "wide"],
  head: STYLE,
  pages: [
    {name: "🧭 Synthèse", path: "/"},
    {name: "🏗️ Marché du neuf", path: "/neuf"},
    {name: "🏠 Marché de l'ancien", path: "/ancien"},
    {name: "🏦 Environnement & Financement", path: "/macro"},
    {name: "📰 Actualités & Aides", path: "/actualites"},
  ],
  toc: false,
  pager: false,
  footer: "PoC de migration — front statique alimenté par la pipeline Python existante.",
};
