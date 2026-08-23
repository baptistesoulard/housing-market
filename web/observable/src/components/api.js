// Ports JS de calculs Python — pas un client HTTP.
//
// Ce fichier portait un client de l'API HTTP (api/routes.py) ; les pages Prévision et
// Données s'en sont détachées le 2026-08-23 pour lire des JSON statiques comme les
// six autres pages du site (voir previsions.json et le commentaire de build_previsions
// dans web/export/web_export.py) — plus de serveur à joindre pour un visiteur.
//
// Ce qui reste ici, ce sont des calculs qui ne PEUVENT PAS être pré-exportés : ils
// dépendent de données qui n'existent que dans le navigateur (le fichier de ventes
// importé sur Données & Sources, jamais envoyé nulle part) ou d'hypothèses posées par
// l'utilisateur (le panneau de scénarios de Prévision). Chacun est un PORT — même
// calcul, même critère qu'une fonction Python nommée en commentaire — et
// `tests/test_web_js_parity.py` verrouille l'accord des deux sur les mêmes données :
// deux implémentations d'un même calcul divergent tôt ou tard si rien ne les compare.
//
// Le backend Flask (api/, python -m api) reste intact et testé : ce n'est pas son
// retrait, seulement celui de son appel depuis ces deux pages. Voir CLAUDE.md,
// « L'API HTTP ».

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

/** Effet à terme d'un jeu d'hypothèses macro sur le taux de crédit et les transactions.
 *
 * Port terme à terme de `forecast.scenario` : approche EN ÉCART, ancrée sur les valeurs
 * actuelles réelles (`base`), pas sur les niveaux bruts des coefficients — le modèle de
 * taux sur-prédit le niveau courant (voir le commentaire de `forecast.scenario`), donc
 * seule la SENSIBILITÉ aux variations est fiable.
 *
 * rateCoef/txCoef : `{intercept, oat, euribor}` / `{intercept, rate, intentions,
 * unemployment}`, tels qu'exportés dans previsions.json (rate.coefficients /
 * transactions.coefficients). base : scenario_baseline du même export. scen :
 * {oat, euribor, chom, intentZ} — les quatre curseurs du panneau.
 */
export function computeScenario(rateCoef, txCoef, base, {oat, euribor, chom, intentZ}) {
  const intent = base.intentions_mean + intentZ * base.intentions_std;
  const dRate = rateCoef.oat * (oat - base.oat) + rateCoef.euribor * (euribor - base.euribor);
  const rateScen = base.rate_now + dRate;
  const dTx = txCoef.rate * dRate
    + txCoef.intentions * (intent - base.intentions)
    + txCoef.unemployment * (chom - base.unemployment);
  const tx0 = base.tx_now;
  return {
    baseline: base,
    rate: rateScen, rate_change: dRate,
    transactions: tx0 + dTx, transactions_change: dTx,
    transactions_change_pct: tx0 ? (dTx / tx0 * 100) : null,
  };
}
