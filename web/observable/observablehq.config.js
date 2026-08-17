// Configuration Observable Framework — dashboard HousingMarket (site statique).
// `npm run build` produit web/observable/dist/, déployé sur Cloudflare Pages (Node-only).
const STYLE = `
<style>
:root {
  --sans-serif: Calibri, "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
  --serif: Calibri, "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
  --hm-brick: #E64A19;
  --hm-ink: #2D3748;
}
body { font-family: var(--sans-serif); color: var(--hm-ink); background: #FFFFFF; }
h1, h2, h3, h4 { font-family: var(--sans-serif); color: var(--hm-ink); }
h1 { font-weight: 700; border-bottom: 2px solid var(--hm-brick); padding-bottom: 8px; margin-bottom: 0.15rem; }
main h2 { font-size: 1.55rem; font-weight: 700; margin-top: 2.4rem; padding-bottom: 0.3rem; border-bottom: 1px solid #E7E9ED; }
main h3 { font-size: 1.3rem; font-weight: 700; color: var(--hm-ink); margin-top: 2.2rem; margin-bottom: 0.5rem; padding-bottom: 0.3rem; border-bottom: 1px solid #EDEFF2; }
a, a:visited { color: #1E88E5; }
.hm-caption { color: var(--theme-foreground-muted); font-size: 0.92rem; max-width: 64rem; margin: 0.2rem 0 1rem; }
.hm-chips { margin: 0.4rem 0 1.2rem; }
.hm-takeaways { background: color-mix(in srgb, #64B5F6 12%, transparent); border-left: 4px solid #64B5F6;
  border-radius: 8px; padding: 0.9rem 1.1rem; margin: 0.6rem 0 1rem; max-width: 64rem; }
.hm-takeaways ul { margin: 0.3rem 0 0; padding-left: 1.1rem; }
.hm-takeaways li { margin: 0.35rem 0; line-height: 1.5; }
.hm-meta { color: var(--theme-foreground-muted); font-size: 0.85rem; margin: 0.4rem 0 0.2rem; }
.hm-grid { display: grid; gap: 1.8rem 1.6rem; margin: 0.8rem 0 0.4rem;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); }
.hm-card { padding: 0.15rem 0; background: transparent; border: none; }
.hm-card-title { font-weight: 600; font-size: 0.86rem; color: #4A5568; letter-spacing: 0.2px; }
.hm-card-value { font-size: 1.6rem; font-weight: 700; color: var(--hm-ink); margin: 0.5rem 0 0.4rem; line-height: 1.15; }
.hm-card-sub { font-size: 0.8rem; color: var(--theme-foreground-muted); line-height: 1.45; }
.hm-delta { font-size: 0.95rem; font-weight: 700; }
.hm-delta.pos { color: #2E7D32; }
.hm-delta.neg { color: #C0392B; }
.hm-link { color: var(--theme-foreground-muted); font-size: 0.83rem; margin: 0.5rem 0 2rem; }
.hm-panels { display: grid; gap: 1rem 1.4rem; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); }
.hm-panel-title { font-weight: 600; font-size: 0.98rem; color: var(--hm-ink); margin: 0.4rem 0 0.1rem; }
.hm-panel-sub { color: var(--theme-foreground-muted); font-size: 0.82rem; margin-bottom: 0.2rem; }
.hm-legend { display: flex; flex-wrap: wrap; gap: 0.4rem 1.3rem; margin: 0.6rem 0 0.1rem; }
.hm-legend-item { display: inline-flex; align-items: center; gap: 0.45rem; cursor: pointer; font-size: 0.9rem; user-select: none; }
.hm-legend-item.off { opacity: 0.4; text-decoration: line-through; }
.hm-swatch { width: 16px; height: 3px; border-radius: 2px; display: inline-block; }
.hm-chart-title { font-weight: 600; margin: 1rem 0 0; }
.hm-chart-title .sub { color: #6c757d; font-weight: 400; }
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
  ],
  toc: false,
  pager: false,
  footer: "PoC de migration — front statique alimenté par la pipeline Python existante.",
};
