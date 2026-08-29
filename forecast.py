"""
Prospective module: turn the app's real leading indicators into a small, transparent
two-stage model of existing-home transactions, plus a scenario engine.

Two-stage econometrics (plain OLS via numpy — no extra dependency):
  Stage 1  credit rate  ~ OAT 10y + Euribor 3M               (scenario lever on financing)
  Stage 2  transactions ~ credit rate(lag) + purchase-intentions(lag) + unemployment(lag)

Everything is fit on the app's REAL national series (macro.csv + IGEDD ventes_ancien.csv). The
transactions target is the 12-month rolling sum (the published "ventes sur un an").
A train/test split (fit ≤2021, predict 2022→) provides an honest out-of-sample backtest.
"""
import numpy as np
import pandas as pd

# Stage-2 predictor columns and the sign we expect (for display / sanity only).
TX_PREDICTORS = ["Credit_Logement_Taux_Interet", "Intentions_Achat_Logement", "Taux_Chomage_BIT"]


def ols(X, y):
    """Ordinary least squares with intercept. X:(n,k), y:(n,). Returns (beta[k+1], r2,
    rmse, pred) where beta[0] is the intercept."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    X1 = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
    pred = X1 @ beta
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    rmse = float(np.sqrt(ss_res / len(y))) if len(y) else float("nan")
    return beta, r2, rmse, pred


def build_target(df_ventes_ancien):
    """12-month rolling sum of national existing-home transactions (IGEDD), indexed by
    Date. Reproduces the published 'ventes sur un an' series.

    N'est plus appelée au runtime depuis la phase 4 : la série pilote vient de
    `queries.transactions_run_rate()`, en SQL. Comme les agrégations d'`analysis.py`,
    cette fonction est CONSERVÉE comme implémentation de référence — c'est elle que
    `tests/test_queries_parity.py` compare à la requête. Ne pas la supprimer.
    """
    tx = df_ventes_ancien.groupby("Date")["Transactions"].sum().sort_index()
    return tx.rolling(12).sum().rename("tx12")


def _macro_indexed(df_macro):
    """Date-indexed macro with unemployment interpolated to monthly (it is quarterly).

    L'interpolation remplit les mois INTERMÉDIAIRES, jamais au-delà de la dernière
    observation. `limit_direction="both"`, utilisé jusqu'ici, prolongeait la série de
    jusqu'à trois mois en recopiant le dernier trimestre publié — et comme la valeur
    n'était alors plus NaN, `forecast_path` ne déclenchait pas son report explicite et
    marquait le point `assured=True`. L'hypothèse était faite, elle n'était plus signalée.
    `limit_area="inside"` la laisse manquante, donc visible.
    """
    m = df_macro.set_index("Date").sort_index().copy()
    if "Taux_Chomage_BIT" in m:
        m["Taux_Chomage_BIT"] = m["Taux_Chomage_BIT"].interpolate(limit_area="inside")
    return m


#: Grille du délai de répercussion des taux de marché sur le taux de crédit (étage 1).
RATE_LAG_GRID = range(0, 13)


def search_rate_lag(df_macro, grid=RATE_LAG_GRID, min_obs=100):
    """Le délai, en mois, entre un mouvement des taux de marché et le barème des banques.

    Le crédit immobilier français est à taux fixe et les banques publient des barèmes
    qu'elles lissent : leur réaction à l'OAT n'est pas instantanée. Ignorer ce délai — ce
    que faisait ce modèle — coûte cher, et de façon mesurable : R² 0,838 contre 0,932, RMSE
    0,474 contre 0,307, et **0,744 contre 0,432 hors échantillon** sur un test entraîné
    jusqu'en 2019 et jugé sur le choc de taux qu'il n'avait pas vu.

    Le délai est CHERCHÉ et non figé, mais il est remarquablement stable : refait à chaque
    millésime annuel depuis 2012, il reste entre 5 et 7 mois et ne s'effondre jamais à
    zéro. Le profil du R² monte franchement jusqu'à 6-7 mois puis redescend — la forme
    d'une vraie relation d'avance, à ne pas confondre avec le cas des permis de construire
    (voir CLAUDE.md), où la courbe décroît dès le premier mois et où il n'y a donc aucune
    avance à exploiter.

    Le décalage retenu vaut 7 mois, et il ne change pas selon qu'on régresse sur l'OAT seul
    ou sur l'OAT et l'Euribor — c'est une propriété de la transmission, pas de la
    spécification.
    """
    m = _macro_indexed(df_macro)
    best = None
    for k in grid:
        d = _rate_design(m, k)
        if len(d) < min_obs:
            continue
        _, r2, _, _ = ols(d[["oat"]].values, d["rate"].values)
        if best is None or r2 > best[0]:
            best = (r2, int(k))
    return 0 if best is None else best[1]


#: Le SEUL taux de marché de l'étage 1. L'Euribor 3 mois en a été retiré le 2026-08-25 :
#: mesuré, il n'apportait rien en ajustement (R² 0,9320 contre 0,9282) et DÉGRADAIT de 19 %
#: hors échantillon (RMSE 0,432 contre 0,348), signature d'un régresseur colinéaire — r 0,83
#: avec l'OAT, VIF 3,24 — qui ajuste du bruit. L'argument économique va dans le même sens :
#: le crédit immobilier français est à taux FIXE, adossé à du financement long, donc c'est
#: l'OAT 10 ans qui le tarife ; l'Euribor décrit un coût court, de second ordre pour un prêt
#: de vingt ans. Il reste une série publiée du site (page Environnement) — seul son rôle de
#: régresseur tombe.
RATE_DRIVER = "OAT_10ans"


def _rate_design(m, lag):
    """Frame aligné [oat, rate] pour l'étage 1, marché décalé de `lag` mois."""
    X = pd.DataFrame({"oat": m[RATE_DRIVER].shift(lag)})
    return X.join(m["Credit_Logement_Taux_Interet"].rename("rate")).dropna()


def fit_rate_model(df_macro, lag=None):
    """Stage 1: credit rate ~ OAT + Euribor, market rates lagged by `lag` months.

    `lag=None` cherche le délai (voir `search_rate_lag`) ; `lag=0` restitue exactement le
    modèle contemporain d'avant. Returns dict with beta, r2, rmse, lag and an aligned frame
    [Date, obs, fit].
    """
    m = _macro_indexed(df_macro)
    lag = search_rate_lag(df_macro) if lag is None else int(lag)
    d = _rate_design(m, lag)
    beta, r2, rmse, pred = ols(d[["oat"]].values, d["rate"].values)
    frame = pd.DataFrame({"Date": d.index, "obs": d["rate"].values, "fit": pred})
    return {"beta": beta, "r2": r2, "rmse": rmse, "lag": lag, "frame": frame}


def rate_path(df_macro, beta, lag):
    """Taux de crédit des mois à venir que les taux de marché DÉJÀ PUBLIÉS déterminent.

    C'est la conséquence la plus utile du délai, et elle n'existait pas avant : puisque le
    barème des banques réagit avec `lag` mois de retard, les taux de marché des `lag`
    derniers mois fixent déjà le taux de crédit des `lag` mois à venir. Aucune hypothèse
    sur les marchés n'est nécessaire — à comparer avec la fenêtre « sans hypothèse » de la
    prévision de transactions, qui vaut zéro mois sur dix-huit.

    Ancré EN ÉCART sur le dernier taux réellement observé, comme `scenario` : le modèle
    sur-prédit le niveau (les banques ne répercutent pas tout), donc seules ses variations
    sont fiables.

    Renvoie [Date, taux, modelled, source]. `taux` est la valeur PUBLIÉE, recalée ; `modelled`
    est la sortie BRUTE du même modèle, sur laquelle l'ajustement historique est tracé. Les
    deux sont renvoyées parce que n'en montrer qu'une rendait le graphique inintelligible :
    la courbe d'ajustement s'arrêtait au dernier mois observé (à 3,75 %) et la projection
    repartait 0,51 pt plus bas (à 3,24 %), sans que rien n'explique le saut. Avec les deux,
    la courbe brute est continue et l'écart qui la sépare de la courbe publiée EST le biais
    de niveau — visible, et non plus subi. `source` est le mois de marché qui détermine la
    ligne, pour que la page puisse le montrer.
    """
    m = _macro_indexed(df_macro)
    rate = m["Credit_Logement_Taux_Interet"].dropna()
    oat = m[RATE_DRIVER].dropna()
    cols = ["Date", "taux", "modelled", "source"]
    if rate.empty or oat.empty or lag <= 0:
        return pd.DataFrame(columns=cols)
    last, marche = rate.index.max(), oat.index.max()
    base_o = oat.get(last - pd.DateOffset(months=lag))
    if base_o is None or pd.isna(base_o):
        return pd.DataFrame(columns=cols)

    rows = []
    for h in range(1, lag + 1):
        t = last + pd.DateOffset(months=h)
        src = t - pd.DateOffset(months=lag)
        if src > marche:
            break
        o = oat.get(src)
        if o is None or pd.isna(o):
            break
        rows.append({"Date": t,
                     "taux": float(rate.iloc[-1] + beta[1] * (o - base_o)),
                     "modelled": float(beta[0] + beta[1] * o),
                     "source": src})
    return pd.DataFrame(rows, columns=cols)


def _design(m, tx12, kr, ki, kc):
    """Aligned design matrix for Stage 2 with the given lead-lags (months)."""
    X = pd.DataFrame({
        "rate": m["Credit_Logement_Taux_Interet"].shift(kr),
        "intent": m["Intentions_Achat_Logement"].shift(ki),
        "chom": m["Taux_Chomage_BIT"].shift(kc),
    })
    return X.join(tx12).dropna()


def _grid_common_index(m, tx12, kr_range, ki_range, kc_range, split=None):
    """The months usable by EVERY candidate in the lag grid.

    A larger lag shifts a predictor further forward and so loses more rows at the start of
    the sample: scored on their own natural windows, two candidates are fitted on different
    numbers of observations (here 216 to 228), and their R² are not directly comparable —
    part of the gap between them is just the sample changing underneath. Restricting every
    candidate to this common index makes the comparison apples-to-apples, at the cost of a
    few early months.

    Returns a DatetimeIndex (possibly empty when the grid is wider than the sample).
    """
    cols = {"rate": "Credit_Logement_Taux_Interet",
            "intent": "Intentions_Achat_Logement",
            "chom": "Taux_Chomage_BIT"}
    full = pd.DataFrame({k: m[v] for k, v in cols.items() if v in m}).join(tx12, how="outer")
    if full.empty or "tx12" not in full:
        return pd.DatetimeIndex([])
    # Complete monthly grid, so shifting by k months is exactly a k-row shift.
    idx = pd.date_range(full.index.min(), full.index.max(), freq="MS")
    full = full.reindex(idx)

    usable = full["tx12"].notna()
    for key, rng in (("rate", kr_range), ("intent", ki_range), ("chom", kc_range)):
        if key not in full:
            return pd.DatetimeIndex([])
        observed = full[key].notna()
        for k in rng:                      # month t must be observed at EVERY lag tested
            usable &= observed.shift(k, fill_value=False)
    if split is not None:
        usable &= idx <= pd.Timestamp(split)
    return idx[usable]


def search_tx_lags(df_macro, tx12, kr_range=range(0, 13), ki_range=range(0, 19, 2),
                   kc_range=range(0, 13, 2), min_obs=60, split=None):
    """Grid-search the predictor lead-lags that maximise R² for Stage 2.

    When `split` is given (a date string), the search is run on the TRAIN window only
    (index ≤ split) — exactly the window the backtest then trains on. This avoids the
    leakage of picking the lags on the full sample (including the test period) and then
    reporting an out-of-sample MAPE on that same period, which flatters the metric.

    Every candidate is scored on the SAME months (see _grid_common_index), so the R² that
    picks the winner reflects the lags alone and not a sample that shrinks as lags grow.
    """
    m = _macro_indexed(df_macro)
    common = _grid_common_index(m, tx12, kr_range, ki_range, kc_range, split)
    if len(common) < min_obs:
        return {"kr": 9, "ki": 4, "kc": 0}
    best = None
    for kr in kr_range:
        for ki in ki_range:
            for kc in kc_range:
                d = _design(m, tx12, kr, ki, kc).reindex(common)
                if d.isna().any().any() or len(d) < min_obs:
                    continue
                _, r2, _, _ = ols(d[["rate", "intent", "chom"]].values, d["tx12"].values)
                if best is None or r2 > best[0]:
                    best = (r2, kr, ki, kc)
    if best is None:
        return {"kr": 9, "ki": 4, "kc": 0}
    return {"kr": best[1], "ki": best[2], "kc": best[3]}


def fit_tx_model(df_macro, tx12, kr, ki, kc, split="2021-12-01"):
    """Stage 2 fit on the full sample + an out-of-sample backtest (train ≤ split).
    Returns beta, r2, rmse, an aligned [Date, obs, fit] frame, and backtest metrics."""
    m = _macro_indexed(df_macro)
    d = _design(m, tx12, kr, ki, kc)
    beta, r2, rmse, pred = ols(d[["rate", "intent", "chom"]].values, d["tx12"].values)
    frame = pd.DataFrame({"Date": d.index, "obs": d["tx12"].values, "fit": pred})

    train = d[d.index <= split]
    test = d[d.index > split]
    bt = {"split": split, "n_test": len(test)}
    if len(train) >= 40 and len(test) >= 6:
        bbeta, _, _, _ = ols(train[["rate", "intent", "chom"]].values, train["tx12"].values)
        tp = bbeta[0] + test[["rate", "intent", "chom"]].values @ bbeta[1:]
        err = test["tx12"].values - tp
        bt["rmse"] = float(np.sqrt((err ** 2).mean()))
        bt["mape"] = float(np.abs(err / test["tx12"].values).mean() * 100)
        bt["frame"] = pd.DataFrame({"Date": test.index, "obs": test["tx12"].values, "pred": tp})
        bt["train_beta"] = bbeta
    return {"beta": beta, "r2": r2, "rmse": rmse, "frame": frame,
            "lags": {"kr": kr, "ki": ki, "kc": kc}, "backtest": bt}


#: Durée sur laquelle le recalage sur le dernier point observé s'éteint linéairement.
#: L'optimum est PLAT : mesuré sur 48 millésimes puis confirmé sur 210, toutes les valeurs
#: entre 6 et 12 mois donnent la même erreur à 0,1 point près. 9 est le milieu de ce
#: plateau, pas un réglage ajusté — c'est ce qui met le paramètre à l'abri du
#: surapprentissage.
FADE_MONTHS = 9


def anchor_of(model, tx12, max_gap=6):
    """Erreur de NIVEAU du modèle à son point ajusté le plus récent.

    C'est la correction d'ordonnée à l'origine du prévisionniste : le modèle est une
    régression de niveau, il reconstruit la série depuis la macro sans jamais regarder où
    elle se trouve réellement. Son erreur au premier mois projeté vaut donc son résidu
    d'estimation — 4,2 % en moyenne, quand recopier le dernier chiffre connu n'en coûte
    que 1,2 %. Mesurer cet écart et l'ajouter à la trajectoire rend au modèle l'ancrage
    qui lui manque.

    L'écart est pris sur la DERNIÈRE ligne du frame ajusté, pas sur le dernier mois de
    `tx12`, et les deux ne coïncident pas : le frame s'arrête au dernier mois où *tous* les
    prédicteurs décalés sont observés, or le chômage est trimestriel et n'est plus
    extrapolé (voir `_macro_indexed`) — il manque donc jusqu'à deux mois par rapport aux
    transactions. Exiger la coïncidence renverrait 0.0 en pratique toujours, ce qui
    désactiverait le recalage sans le dire. Sur une série aussi lisse qu'un cumul 12 mois,
    le résidu d'il y a deux mois est un estimateur de niveau tout aussi bon.

    `max_gap` borne cette tolérance : au-delà, l'écart décrit un état du marché qui n'est
    plus le présent, et mieux vaut ne pas recaler du tout. Renvoie alors 0.0, comme quand
    le modèle n'a pas de frame — la projection est celle d'avant, sans recalage.
    """
    frame = model.get("frame") if isinstance(model, dict) else None
    if frame is None or frame.empty:
        return 0.0
    obs = tx12.dropna()
    if obs.empty:
        return 0.0
    fitted = frame.assign(Date=pd.to_datetime(frame["Date"])).sort_values("Date")
    last_fit = fitted["Date"].iloc[-1]
    gap = (obs.index.max().year - last_fit.year) * 12 + (obs.index.max().month - last_fit.month)
    if gap > max_gap or gap < 0:
        return 0.0
    return float(fitted["obs"].iloc[-1] - fitted["fit"].iloc[-1])


def _fade(h, fade_months):
    """Poids du recalage à l'horizon `h` (1 = plein, 0 = éteint), extinction linéaire."""
    if not fade_months or fade_months <= 0:
        return 0.0
    return max(0.0, 1.0 - (h - 1) / float(fade_months))


def forecast_path(df_macro, tx12, lags, beta, sigma, horizon=18, z=1.2816,
                  anchor=0.0, fade_months=FADE_MONTHS, band=None):
    """Forward monthly path of 12-month transactions out to `horizon` months.

    `anchor` (voir `anchor_of`) est ajouté à chaque point avec un poids qui décroît
    linéairement sur `fade_months` : plein au premier mois projeté, nul au-delà. Le modèle
    part ainsi du dernier chiffre connu et rejoint progressivement sa propre trajectoire —
    la seule chose qu'il sait faire à long terme. `anchor=0.0` restitue exactement le
    comportement d'avant.

    `band` : table [horizon, lo_off, hi_off] des décalages empiriques de la bande, calibrée
    sur les erreurs de l'archive (voir `forecast_archive.band_table`). Quand elle est
    absente, on retombe sur l'ancienne bande de largeur CONSTANTE ±`z`·`sigma` — dont la
    couverture réelle vaut 94 % aux horizons courts et 57 % à dix-huit mois pour une
    promesse de 80 %, parce qu'une erreur qui grandit avec l'horizon ne tient pas dans une
    largeur fixe.

    Two regimes, flagged by the `assured` column:
      * assured=True — every predictor is an ALREADY-OBSERVED value (shifted by its estimated
        lag), so the point needs no assumption on where macro goes next. This part reaches
        min over predictors of (last predictor date + its lag).
      * assured=False — beyond that, a predictor has run out; it is HELD FLAT at its last
        observed value (a transparent carry-forward assumption) so the planner still gets a
        full 12-18-month projection. The app draws a marker at the assured/assumed boundary.

    Each point carries an ±`z`·`sigma` band (z=1.2816 ≈ 80%); `sigma` is the out-of-sample
    backtest RMSE when available (else the in-sample RMSE). Returns a
    [Date, pred, lo, hi, assured] frame (empty if no future month is reachable) or None if a
    predictor series is entirely missing.
    """
    m = _macro_indexed(df_macro)
    kr, ki, kc = lags["kr"], lags["ki"], lags["kc"]
    preds = [("Credit_Logement_Taux_Interet", kr),
             ("Intentions_Achat_Logement", ki),
             ("Taux_Chomage_BIT", kc)]
    obs = tx12.dropna()
    if obs.empty:
        return None
    last_obs = obs.index.max()

    last_vals = {}
    for col, _ in preds:
        if col not in m:
            return None
        s = m[col].dropna()
        if s.empty:
            return None
        last_vals[col] = float(s.iloc[-1])  # for carry-forward beyond availability

    end = last_obs + pd.DateOffset(months=horizon)
    future = pd.date_range(last_obs + pd.DateOffset(months=1), end, freq="MS")

    offsets = _band_offsets(band, horizon, z, sigma)

    rows = []
    for h, t in enumerate(future, start=1):
        vals, assured = [], True
        for col, k in preds:
            v = m[col].get(t - pd.DateOffset(months=k))
            if v is None or pd.isna(v):
                v, assured = last_vals[col], False  # carry forward the last observed value
            vals.append(float(v))
        pred = float(beta[0] + beta[1] * vals[0] + beta[2] * vals[1] + beta[3] * vals[2])
        pred += float(anchor) * _fade(h, fade_months)
        lo_off, hi_off = offsets[h]
        rows.append({"Date": t, "pred": pred,
                     "lo": pred + lo_off, "hi": pred + hi_off, "assured": assured})
    return pd.DataFrame(rows, columns=["Date", "pred", "lo", "hi", "assured"])


def _band_offsets(band, horizon, z, sigma):
    """{horizon: (lo_off, hi_off)} — décalages de la bande, calibrés ou constants.

    La bande calibrée est ASYMÉTRIQUE, et c'est voulu : le modèle surestime le réalisé de
    façon croissante avec l'horizon (+0,7 % à un mois, +6,4 % à dix-huit sur la fenêtre
    observée). Une bande symétrique autour d'une prévision biaisée rate d'un côté plus que
    de l'autre ; les quantiles empiriques de l'erreur SIGNÉE, eux, portent le biais avec
    eux.
    """
    flat = (-z * sigma, z * sigma)
    offsets = {h: flat for h in range(1, horizon + 1)}
    if band is None or len(band) == 0:
        return offsets
    for row in band.itertuples():
        h = int(row.horizon)
        if 1 <= h <= horizon:
            offsets[h] = (float(row.lo_off), float(row.hi_off))
    return offsets


def scenario(rate_beta, tx_beta, base, scen):
    """Delta-anchored scenario, robust to the models' level biases (e.g. Stage 1 currently
    over-predicts the rate because banks hold it below what the OAT implies). We apply the
    estimated SENSITIVITIES to the *changes* vs the current actual baseline.

    base : {oat, intent, chom, rate_now, tx_now} — current actual values.
    scen : {oat, intent, chom} — scenario values. (`euribor` peut encore être présent : il
    est simplement ignoré depuis le retrait de l'Euribor de l'étage 1, voir RATE_DRIVER.)
    Returns {rate, d_rate, tx, d_tx}: implied credit rate and 12-month transactions.
    """
    # `rate_beta` ne porte plus qu'un coefficient de marché depuis le retrait de l'Euribor
    # (voir RATE_DRIVER) : un seul taux, un seul levier, et le coefficient se lit tel quel.
    d_rate = rate_beta[1] * (scen["oat"] - base["oat"])
    rate_scen = base["rate_now"] + d_rate
    d_tx = (tx_beta[1] * d_rate
            + tx_beta[2] * (scen["intent"] - base["intent"])
            + tx_beta[3] * (scen["chom"] - base["chom"]))
    return {"rate": rate_scen, "d_rate": d_rate, "tx": base["tx_now"] + d_tx, "d_tx": d_tx}


def fit_tx_to_monthly(df_series, tx12, value_col="Sales", lag_m=0):
    """Elasticity of a MONTHLY company series (e.g. user-imported sales) to the 12-month
    transactions run-rate, at `lag_m` months. `tx12` is a Date-indexed Series (queries.transactions_run_rate).
    The driver is shifted forward by `lag_m` so transactions at t explain sales at t+lag_m.
    Returns {beta, r2, lag_m, n} or None if too few overlapping months."""
    s = (df_series[["Date", value_col]].dropna()
         .assign(Date=lambda d: pd.to_datetime(d["Date"]))
         .groupby("Date")[value_col].sum().sort_index())
    drv = tx12.copy()
    drv.index = pd.to_datetime(drv.index) + pd.DateOffset(months=lag_m)
    d = pd.DataFrame({"y": s}).join(drv.rename("x")).dropna()
    if len(d) < 8:
        return None
    beta, r2, _, _ = ols(d["x"].values.reshape(-1, 1), d["y"].values)
    return {"beta": beta, "r2": r2, "lag_m": lag_m, "n": len(d)}


def best_tx_to_monthly(df_series, tx12, value_col="Sales", lags=range(0, 19)):
    """Pick the transactions→monthly-series month lag with the highest R² (0..18 months)."""
    best = None
    for lg in lags:
        fit = fit_tx_to_monthly(df_series, tx12, value_col, lag_m=lg)
        if fit and (best is None or fit["r2"] > best["r2"]):
            best = fit
    return best


def fit_sales_two_factor(df_series, tx12, reno, value_col="Sales",
                         tx_lags=range(0, 19, 3), reno_lags=range(0, 19, 3), min_obs=12):
    """Two-driver elasticity of a company's monthly sales:

        sales(t) ≈ a + b_tx·tx12(t − l₁) + b_reno·reno(t − l₂)

    Renovation adds the STOCK-driven second-œuvre demand channel that existing-home
    transactions (move-driven) miss — the third driver for a Somfy-type actor, and the path
    that eventually replaces the synthetic sales series. Grid-searches both lags for the best
    in-sample R². `tx12` and `reno` are Date-indexed monthly Series. Returns
    {beta:[a, b_tx, b_reno], r2, tx_lag, reno_lag, n} or None (too few overlapping months
    or reno unavailable).
    """
    if reno is None:
        return None
    reno = reno.dropna()
    if reno.empty:
        return None
    s = (df_series[["Date", value_col]].dropna()
         .assign(Date=lambda d: pd.to_datetime(d["Date"]))
         .groupby("Date")[value_col].sum().sort_index())
    best = None
    for l1 in tx_lags:
        tx_s = tx12.dropna().copy()
        tx_s.index = pd.to_datetime(tx_s.index) + pd.DateOffset(months=l1)
        for l2 in reno_lags:
            rn = reno.copy()
            rn.index = pd.to_datetime(rn.index) + pd.DateOffset(months=l2)
            d = pd.DataFrame({"y": s}).join(tx_s.rename("tx")).join(rn.rename("rn")).dropna()
            if len(d) < min_obs:
                continue
            beta, r2, _, _ = ols(d[["tx", "rn"]].values, d["y"].values)
            if best is None or r2 > best["r2"]:
                best = {"beta": beta, "r2": r2, "tx_lag": l1, "reno_lag": l2, "n": len(d)}
    return best


def propagate_to_series(fit, tx12_obs, tx_path, sales_df, value_col="Sales",
                        sigma_tx=0.0, z=1.2816):
    """Monthly forecast of a company's OWN sales from the transactions forecast path.

    Turns the demand-planning deliverable into a company-level series: with the estimated
    elasticity `fit` (from best_tx_to_monthly: sales ≈ a + b·tx12(t − lag_m)), the future
    transactions path drives a month-by-month projection of the imported sales, out to the
    transactions horizon + the elasticity lag. The band propagates the transactions
    uncertainty `sigma_tx` through the slope b (±z·|b|·sigma_tx, z≈80%).

    fit       : dict {beta:[a,b], lag_m, r2, n} from best_tx_to_monthly.
    tx12_obs  : observed 12-month transactions Series (Date-indexed).
    tx_path   : forecast_path frame [Date, pred, ...] (future transactions).
    sales_df  : the company series [Date, value_col].
    Returns a [Date, pred, lo, hi] frame (empty when nothing is projectable).
    """
    cols = ["Date", "pred", "lo", "hi"]
    if fit is None or sales_df is None or sales_df.empty:
        return pd.DataFrame(columns=cols)
    a, b = float(fit["beta"][0]), float(fit["beta"][1])
    lag = int(fit["lag_m"])
    tx_obs = tx12_obs.dropna()
    parts = [tx_obs]
    if tx_path is not None and not tx_path.empty:
        parts.append(tx_path.set_index("Date")["pred"])
    tx_full = pd.concat(parts).sort_index()
    tx_full = tx_full[~tx_full.index.duplicated(keep="last")]

    s = sales_df[["Date", value_col]].dropna().copy()
    s["Date"] = pd.to_datetime(s["Date"])
    if s.empty:
        return pd.DataFrame(columns=cols)
    last_sales = s["Date"].max()
    end = tx_full.index.max() + pd.DateOffset(months=lag)
    future = pd.date_range(last_sales + pd.DateOffset(months=1), end, freq="MS")
    band = abs(b) * z * sigma_tx

    rows = []
    for t in future:
        drv = tx_full.get(t - pd.DateOffset(months=lag))
        if drv is None or pd.isna(drv):
            continue
        pred = a + b * float(drv)
        rows.append({"Date": t, "pred": pred, "lo": pred - band, "hi": pred + band})
    return pd.DataFrame(rows, columns=cols)
