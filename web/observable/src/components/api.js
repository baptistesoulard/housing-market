// Client de l'API HTTP (couche 4 du patron : le front ne connaît que des routes JSON).
//
// Les cinq premières pages du site lisent un JSON statique produit au build par
// `web/export/web_export.py`. Les pages Prévision et Données, elles, appellent l'API :
// leurs écrans sont interactifs (curseurs de scénario, curseur de décalage) et ne se
// réduisent pas à une photo des données.
//
// Base de l'API, par ordre de priorité :
//   1. `?api=https://…` dans l'URL — pratique pour pointer une instance le temps d'une démo ;
//      la valeur est mémorisée dans localStorage.
//   2. `localStorage.hmApiBase` — le réglage retenu.
//   3. `http://127.0.0.1:8000` — le serveur local lancé par `python -m api`.
//
// Il n'y a donc AUCUNE URL d'hébergement en dur : le site déployé sur Cloudflare Pages
// reste un site statique qui ne sait pas où vit l'API tant qu'on ne le lui dit pas. C'est
// ce qui permet de repousser le choix d'hébergement sans toucher au code.

const DEFAULT_BASE = "http://127.0.0.1:8000";

export function apiBase() {
  if (typeof window === "undefined") return DEFAULT_BASE;
  const fromQuery = new URLSearchParams(window.location.search).get("api");
  if (fromQuery) {
    try { window.localStorage.setItem("hmApiBase", fromQuery); } catch { /* mode privé */ }
    return fromQuery.replace(/\/$/, "");
  }
  try {
    const saved = window.localStorage.getItem("hmApiBase");
    if (saved) return saved.replace(/\/$/, "");
  } catch { /* mode privé */ }
  return DEFAULT_BASE;
}

/** Erreur portant de quoi afficher un message utile plutôt qu'un « failed to fetch ». */
export class ApiError extends Error {
  constructor(message, {status = null, base = null, path = null} = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.base = base;
    this.path = path;
  }
}

async function request(path, {method = "GET", body = null} = {}) {
  const base = apiBase();
  let resp;
  try {
    resp = await fetch(base + path, {
      method,
      headers: body ? {"Content-Type": "application/json"} : {},
      body: body ? JSON.stringify(body) : null
    });
  } catch (cause) {
    // fetch ne rejette que sur panne réseau / CORS : le serveur n'est pas joignable.
    throw new ApiError("API injoignable", {base, path});
  }
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const j = await resp.json();
      detail = j.detail || j.error || detail;
    } catch { /* corps non JSON */ }
    throw new ApiError(detail, {status: resp.status, base, path});
  }
  return resp.json();
}

// Une fonction = une question métier, en miroir exact de `api/routes.py`.
export const api = {
  health: () => request("/api/health"),
  rateModel: () => request("/api/forecast/rate-model"),
  transactionsModel: () => request("/api/forecast/transactions-model"),
  projection: (horizon = 18) => request(`/api/forecast/projection?horizon=${horizon}`),
  // Les libellés de type contiennent des espaces (« Logement Collectif ») : encoder,
  // sinon l'URL est invalide. Un test de contrat verrouille ce détail côté Python.
  lagSensitivity: (predictor) =>
    request(`/api/forecast/lag-sensitivity?predictor=${encodeURIComponent(predictor)}`),
  scenario: (assumptions) =>
    request("/api/forecast/scenario", {method: "POST", body: assumptions}),
  revenueBenchmarks: () => request("/api/forecast/revenue-benchmarks"),
  transactionsRunRate: () => request("/api/market/transactions-run-rate"),
  housingTypes: () => request("/api/market/housing-types"),
  permitsRunRate: (type, metric = "Permis") =>
    request(`/api/market/permits-run-rate?type=${encodeURIComponent(type)}` +
            `&metric=${encodeURIComponent(metric)}`)
};

/** Encart d'explication quand l'API ne répond pas — le cas NORMAL sur le site déployé. */
export function apiOfflineNotice(error) {
  const div = document.createElement("div");
  div.className = "hm-api-offline";
  const base = error?.base ?? apiBase();
  // Le message s'adresse D'ABORD à un visiteur de passage — le site est public, et cet
  // encart est ce qu'il voit tant qu'aucune instance de l'API n'est désignée. Lui servir
  // une commande `python -m api` en première ligne, c'est lui répondre dans une langue
  // qui n'est pas la sienne : on lui dit donc ce qui manque, où aller en attendant, et on
  // range le mode d'emploi du développeur dans un repli.
  div.innerHTML = `
    <div class="hm-api-offline-title">⚙️ Cette page a besoin d'un moteur de calcul</div>
    <p>Les cinq premières pages du site sont des exports statiques et fonctionnent seules.
    Celle-ci relance un calcul à chaque question posée — c'est tout son intérêt — et
    demande donc qu'un serveur réponde. Aucun n'est joignable pour le moment.</p>
    <p>En attendant, <a href="/synthese">la synthèse du marché</a> et les pages de détail
    restent complètes, et <a href="/a-propos">la méthode</a> explique ce que cette page
    calcule.</p>
    <details>
      <summary>Vous avez le dépôt en local&nbsp;?</summary>
      <p>Depuis sa racine :</p>
      <pre><code>python -m api</code></pre>
      <p>Puis rechargez la page. Pour viser une autre instance, ajoutez
      <code>?api=https://mon-api.example</code> à l'URL — la valeur est mémorisée.</p>
    </details>
    <p class="hm-api-offline-detail">Tentative sur <code>${base}</code> —
    ${error?.message ?? "injoignable"}.</p>`;
  return div;
}

/** Régression linéaire simple y = a + b·x, en JS.
 *
 * Portée ici volontairement : elle sert aux séries de ventes société, qui restent dans le
 * navigateur et ne sont JAMAIS envoyées à l'API. Même formule fermée que `forecast.ols`
 * dans le cas à une variable — il n'y a donc pas deux méthodes concurrentes, juste deux
 * implémentations du même estimateur, chacune du côté où vivent ses données.
 */
export function ols1(xs, ys) {
  const n = xs.length;
  if (n < 8) return null;
  const mx = xs.reduce((a, b) => a + b, 0) / n;
  const my = ys.reduce((a, b) => a + b, 0) / n;
  let sxy = 0, sxx = 0, syy = 0;
  for (let i = 0; i < n; i++) {
    const dx = xs[i] - mx, dy = ys[i] - my;
    sxy += dx * dy; sxx += dx * dx; syy += dy * dy;
  }
  if (sxx === 0 || syy === 0) return null;
  const b = sxy / sxx;
  const a = my - b * mx;
  const r2 = (sxy * sxy) / (sxx * syy);
  return {a, b, r2, n};
}

/** Décale une série de `lag` mois (les dates avancent), comme `simulation.shift_indicator`. */
export function shiftMonths(rows, lag, dateKey = "date") {
  if (!lag) return rows.map((r) => ({...r}));
  return rows.map((r) => {
    const d = new Date(r[dateKey] + "T00:00:00Z");
    d.setUTCMonth(d.getUTCMonth() + lag);
    return {...r, [dateKey]: d.toISOString().slice(0, 10)};
  });
}

/** Cherche le décalage (0..18 mois) qui maximise le R² de `sales ~ driver(t − lag)`.
 *
 * Même critère et même grille que `forecast.best_tx_to_monthly` côté Python : les deux
 * drivers amont (transactions et permis) restent ainsi comparables à armes égales.
 */
export function bestLagFit(driverRows, salesRows, lags = 19) {
  const sales = new Map(salesRows.map((r) => [r.date, r.value]));
  let best = null;
  for (let lag = 0; lag < lags; lag++) {
    const shifted = shiftMonths(driverRows, lag);
    const xs = [], ys = [];
    for (const r of shifted) {
      const y = sales.get(r.date);
      if (y != null && r.value != null) { xs.push(r.value); ys.push(y); }
    }
    const fit = ols1(xs, ys);
    if (fit && (!best || fit.r2 > best.r2)) best = {...fit, lag};
  }
  return best;
}
