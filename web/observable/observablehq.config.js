// Configuration Observable Framework — PoC Synthèse.
// Site statique : `npm run build` produit web/observable/dist/ (déployable tel quel
// sur Cloudflare Pages / Netlify — aucun serveur, aucun Python au build du front).
export default {
  title: "HousingMarket — Synthèse",
  root: "src",
  theme: ["air", "wide"],
  // PoC mono-page : pas de barre latérale ni de sommaire.
  sidebar: false,
  toc: false,
  pager: false,
  footer: "PoC de migration — front statique alimenté par la pipeline Python existante.",
};
