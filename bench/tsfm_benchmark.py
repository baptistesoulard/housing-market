"""Banc d'essai : modèles de fondation pour séries temporelles face au modèle publié.

Question posée : Chronos-2 (Amazon) ou Timestral (Mistral), utilisés sans entraînement
(« zero-shot »), prévoient-ils les ventes anciennes sur un an mieux que le modèle publié
du site — et mieux que la référence naïve ?

Ce script ne touche à RIEN de la chaîne de publication : il lit les CSV versionnés de
`data/` et écrit dans `bench/results/`. Aucune page, aucun JSON du site, aucune ligne de
l'archive n'en dépend.

## Protocole — le même que la rétro-simulation publiée

- Mêmes millésimes : ceux des lignes `retro` de `data/forecast_archive.csv` (depuis
  2009, un par mois), mêmes horizons 1 à 18 mois, même cible (le cumul 12 mois).
- Même troncature : à chaque millésime, chaque modèle ne voit que les transactions ET la
  macro jusqu'au millésime inclus (comme `forecast_archive.retro_rows`).
- Même réalisé : la série courante, rejointe à la lecture (comme `forecast_archive.evaluate`).
- Même naïve : celle stockée dans l'archive.
- Même découpage : les quatre blocs d'horizon du seuil d'entrée (1-3, 4-6, 7-12, 13-18)
  et les sept épisodes de la page « Prévisions passées ».

Le modèle publié n'est PAS recalculé : ses prévisions rétro sont lues dans l'archive. Le
contrôle de cohérence (`--check`) vérifie que l'évaluation de ce script retrouve les
skills par épisode publiés dans `archive.json`.

## Les variantes testées

- `*_tx12` : le modèle prévoit directement le cumul 12 mois (série lisse, sans
  saisonnalité). Seule variante qui donne une bande 10-90 % propre.
- `*_flux` : le modèle prévoit les ventes MENSUELLES (saisonnalité visible), puis on
  reconstruit le cumul : mois observés + mois prévus. Pas de bande (une somme de quantiles
  n'est pas le quantile d'une somme).
- `*_flux_cov` : idem avec les trois prédicteurs du modèle publié (taux de crédit,
  intentions d'achat, chômage) en covariables PASSÉES seulement. Leur futur n'est pas
  connu : le modèle publié les reporte à plat ; ici, ils ne sont simplement pas donnés.
- `combo_*` : moyenne simple du modèle publié et d'une variante. Les combinaisons battent
  souvent chaque modèle pris seul ; c'est l'usage « challenger » le plus réaliste.

Références statistiques, toujours calculées : `ets_tx12` (Holt amorti sur le cumul) et
`hw_flux` (Holt-Winters amorti, saisonnier, sur les flux mensuels).

## Limite à énoncer avec tout résultat

Chronos-2 a été pré-entraîné en partie sur des séries réelles publiques ; Timestral
surtout sur du synthétique, puis sur un mélange réel + synthétique. Aucun des deux ne
publie la liste exhaustive de ses séries : on ne peut pas exclure qu'une série
macroéconomique française proche ait été vue. La troncature au millésime n'empêche pas
cette fuite-là. Un avantage spectaculaire sur une période ancienne serait donc à lire
avec méfiance ; la comparaison la plus probante est celle des épisodes récents.

Usage :
    python bench/tsfm_benchmark.py                       # références statistiques seules
    python bench/tsfm_benchmark.py --models chronos2 timestral-28M timestral-209M
    python bench/tsfm_benchmark.py --check               # contrôle de cohérence seul
"""
from __future__ import annotations

import argparse
import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
DATA = RACINE / "data"
SORTIE = Path(__file__).resolve().parent / "results"

HORIZON = 18
QUANTILES = (0.1, 0.5, 0.9)

#: Mêmes blocs que `web/export/verdict._HORIZON_BLOCS` (le découpage du seuil d'entrée).
BLOCS = [("1-3", 1, 3), ("4-6", 4, 6), ("7-12", 7, 12), ("13-18", 13, 18)]

#: Mêmes épisodes que `web/export/page_archive._EPISODES`. Copiés plutôt qu'importés :
#: importer l'export tirerait DuckDB et l'entrepôt pour une liste de sept dates.
EPISODES = [
    ("2009-01-01", "2009-12-01", "2009 · sortie de crise financière"),
    ("2010-01-01", "2011-12-01", "2010-11 · rebond"),
    ("2012-01-01", "2015-12-01", "2012-15 · creux long, crise de la dette"),
    ("2016-01-01", "2019-12-01", "2016-19 · expansion, records"),
    ("2020-01-01", "2021-12-01", "2020-21 · Covid puis record"),
    ("2022-01-01", "2024-12-01", "2022-24 · choc de taux"),
    ("2025-01-01", "2030-12-01", "2025-26 · reprise"),
]

#: Les trois prédicteurs de l'étage 2 du modèle publié (`forecast.TX_PREDICTORS`).
COVARIABLES = ["Credit_Logement_Taux_Interet", "Intentions_Achat_Logement", "Taux_Chomage_BIT"]

#: Séries du site testées UNE PAR UNE en quatrième covariable (variantes `flux_cov+<clé>`),
#: chacune jugée contre `flux_cov` du même modèle. Absentes exprès : la demande de crédit
#: déclarée par les banques et les anticipations de taux, déjà réfutées
#: (`reperes.REFUTATIONS`), et l'Euribor, retiré de l'étage 1 le 2026-08-25.
CANDIDATES = {
    "oat": "OAT_10ans",
    "credits": "Production_Credits_Habitat",
    "confiance": "Insee_Confiance_Menages",
    "prix": "Prix_Ancien_Ensemble",
    "reno": "Reno_Activite_Batiment",
}

#: Séries trimestrielles : interpolées ENTRE deux points publiés, jamais au-delà
#: (même règle que `forecast._macro_indexed`).
TRIMESTRIELLES = ["Taux_Chomage_BIT", "Prix_Ancien_Ensemble"]

#: Seuil d'entrée du projet (CLAUDE.md, « Porte d'entrée d'un prédicteur ») : ≥ 5 %
#: d'erreur évitée hors échantillon sur ≥ 3 des 4 blocs. Appliqué ici contre le MODÈLE
#: publié, pas contre la naïve : la question est de savoir s'il faut le remplacer.
SEUIL_SKILL, SEUIL_BLOCS = 0.05, 3


# ----------------------------------------------------------------------------- données
def charger() -> dict:
    ventes = pd.read_csv(DATA / "ventes_ancien.csv", parse_dates=["Date"])
    flux = ventes.groupby("Date")["Transactions"].sum().sort_index().asfreq("MS")
    tx12 = flux.rolling(12).sum().rename("tx12")

    brut = pd.read_csv(DATA / "macro.csv", parse_dates=["Date"]).sort_values("Date")
    macro = brut.set_index("Date")[COVARIABLES + list(CANDIDATES.values())].asfreq("MS")
    for c in TRIMESTRIELLES:
        macro[c] = macro[c].interpolate(limit_area="inside")

    archive = pd.read_csv(DATA / "forecast_archive.csv")
    retro = archive[archive["kind"] == "retro"].copy()
    millesimes = sorted(pd.to_datetime(retro["data_vintage"].unique()))
    return {"flux": flux, "tx12": tx12, "macro": macro, "macro_brut": brut,
            "retro": retro, "millesimes": millesimes}


def _lignes(nom: str, v: pd.Timestamp, point, lo=None, hi=None) -> list[dict]:
    out = []
    for h in range(1, HORIZON + 1):
        out.append({
            "methode": nom,
            "data_vintage": v.strftime("%Y-%m-%d"),
            "target_month": (v + pd.DateOffset(months=h)).strftime("%Y-%m-%d"),
            "horizon": h,
            "predicted": float(point[h - 1]),
            "lo": float(lo[h - 1]) if lo is not None else np.nan,
            "hi": float(hi[h - 1]) if hi is not None else np.nan,
        })
    return out


def flux_vers_tx12(flux_obs: np.ndarray, flux_prev: np.ndarray) -> np.ndarray:
    """Cumul 12 mois à chaque horizon : les mois encore observés + les mois prévus."""
    serie = np.concatenate([flux_obs[-11:], flux_prev])
    return np.array([serie[h: h + 12].sum() for h in range(1, len(flux_prev) + 1)])


# ------------------------------------------------------------- références statistiques
def ets_tx12(d: dict) -> list[dict]:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    lignes = []
    for v in d["millesimes"]:
        y = d["tx12"][:v].dropna()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fit = ExponentialSmoothing(y.values, trend="add", damped_trend=True).fit()
        lignes += _lignes("ets_tx12", v, fit.forecast(HORIZON))
    return lignes


def hw_flux(d: dict) -> list[dict]:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    lignes = []
    for v in d["millesimes"]:
        y = d["flux"][:v].dropna()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fit = ExponentialSmoothing(y.values, trend="add", damped_trend=True,
                                       seasonal="add", seasonal_periods=12).fit()
        lignes += _lignes("hw_flux", v, flux_vers_tx12(y.values, fit.forecast(HORIZON)))
    return lignes


# ----------------------------------------------------------------------- XGBoost
#: Réglages FIXÉS d'avance, jamais ajustés sur la fenêtre d'évaluation (sinon le score
#: serait en partie appris sur ce qu'il prétend prévoir).
XGB_PARAMS = dict(n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.8,
                  colsample_bytree=0.8, min_child_weight=3, n_jobs=2, random_state=0)


def _features_xgb(d: dict, v: pd.Timestamp) -> pd.DataFrame:
    """Une ligne par mois d'origine ≤ v, uniquement de l'information connue à cette date."""
    t = np.log(d["tx12"][:v])
    m = d["macro"][COVARIABLES][:v].ffill()
    X = pd.DataFrame({f"r{k}": t - t.shift(k) for k in (1, 3, 6, 12)})
    X["taux"] = m["Credit_Logement_Taux_Interet"]
    X["taux_d6"] = X["taux"] - X["taux"].shift(6)
    X["taux_d12"] = X["taux"] - X["taux"].shift(12)
    X["intentions"] = m["Intentions_Achat_Logement"]
    X["intentions_d6"] = X["intentions"] - X["intentions"].shift(6)
    X["chomage"] = m["Taux_Chomage_BIT"]
    X["chomage_d12"] = X["chomage"] - X["chomage"].shift(12)
    return X


def xgb_direct(d: dict) -> list[dict]:
    """XGBoost en stratégie DIRECTE : un modèle par horizon, qui prédit la variation
    log du cumul 12 mois entre l'origine et l'horizon h. Réentraîné à chaque millésime sur
    les seules origines dont la cible est observée à cette date."""
    from xgboost import XGBRegressor
    lignes = []
    for v in d["millesimes"]:
        X = _features_xgb(d, v)
        logt = np.log(d["tx12"][:v])
        x0 = X.loc[[v]]
        pred = []
        for h in range(1, HORIZON + 1):
            y = (logt.shift(-h) - logt).rename("y")
            tr = X.join(y).dropna()
            mdl = XGBRegressor(**XGB_PARAMS).fit(tr.drop(columns="y"), tr["y"])
            pred.append(float(np.exp(mdl.predict(x0)[0]) * d["tx12"][v]))
        lignes += _lignes("xgb_direct", v, pred)
    return lignes


# ------------------------------------------------------------ modèles de fondation
def _taux_futur(d: dict, v: pd.Timestamp, index: pd.DatetimeIndex) -> np.ndarray:
    """Taux de crédit sur le contexte PUIS sur l'horizon, connu au millésime v.

    Le barème des banques suit l'OAT avec plusieurs mois de retard (étage 1 du modèle) :
    au millésime, les OAT déjà publiées fixent donc le taux des mois suivants. On reprend
    EXACTEMENT `forecast.fit_rate_model` + `forecast.rate_path` sur la macro tronquée à v,
    puis report à plat au-delà — la convention du modèle publié pour ses prédicteurs."""
    import sys
    sys.path.insert(0, str(RACINE))
    import forecast
    brut = d["macro_brut"][d["macro_brut"]["Date"] <= v]
    futur = pd.Series(dtype=float)
    try:
        mod = forecast.fit_rate_model(brut)
        chemin = forecast.rate_path(brut, mod["beta"], mod["lag"])
        futur = chemin.set_index("Date")["taux"]
    except Exception:          # historique trop court (millésimes 2009) : report à plat
        pass
    obs = d["macro"]["Credit_Logement_Taux_Interet"][:v].dropna()
    s = pd.concat([obs, futur[futur.index > obs.index.max()]])
    return s.reindex(index).ffill().values.astype(float)


def _contextes(d: dict, variante: str):
    """Par millésime : la cible, les covariables passées (C, T) et les covariables
    futures connues (C, T + HORIZON). `None` quand la variante n'en a pas."""
    ctx, passe, connu = [], [], []
    avec_cov = variante.startswith("flux_cov")
    debut = pd.Timestamp("2003-01-01") if avec_cov else None    # 1er taux de crédit publié
    extra = [CANDIDATES[variante.split("+", 1)[1]]] if "+" in variante else []
    futur = variante == "flux_cov_futur"
    for v in d["millesimes"]:
        if variante == "tx12":
            ctx.append(d["tx12"][:v].dropna().values.astype(float))
            continue
        y = d["flux"][debut:v].dropna()
        ctx.append(y.values.astype(float))
        if not avec_cov:
            continue
        # Dernière valeur publiée reportée à plat jusqu'au millésime (chômage et prix
        # trimestriels s'arrêtent avant) : rien d'autre que du passé, et pas de NaN en
        # fin de contexte, que les deux modèles ne traitent pas pareil.
        cols = (COVARIABLES[1:] if futur else COVARIABLES) + extra
        passe.append(d["macro"][cols][:v].reindex(y.index).ffill().values.T.astype(float))
        if futur:
            idx = pd.date_range(y.index[0], periods=len(y) + HORIZON, freq="MS")
            connu.append(_taux_futur(d, v, idx)[None, :])
    return ctx, (passe or None), (connu or None)


def _noms_passe(variante: str) -> list[str]:
    extra = [CANDIDATES[variante.split("+", 1)[1]]] if "+" in variante else []
    return (COVARIABLES[1:] if variante == "flux_cov_futur" else COVARIABLES) + extra


def _gauche(arrays: list[np.ndarray]) -> np.ndarray:
    """Empile des séries de longueurs différentes, complétées à GAUCHE par des NaN."""
    t = max(a.shape[-1] for a in arrays)
    out = np.full((len(arrays),) + arrays[0].shape[:-1] + (t,), np.nan)
    for i, a in enumerate(arrays):
        out[i, ..., t - a.shape[-1]:] = a
    return out


def _vers_lignes(d, nom, variante, ctx, q10, q50, q90) -> list[dict]:
    lignes = []
    for i, v in enumerate(d["millesimes"]):
        if variante == "tx12":
            lignes += _lignes(nom, v, q50[i], q10[i], q90[i])
        else:
            lignes += _lignes(nom, v, flux_vers_tx12(ctx[i], q50[i]))
    return lignes


def chronos2(d: dict, variantes) -> list[dict]:
    import torch
    from chronos import Chronos2Pipeline
    pipe = Chronos2Pipeline.from_pretrained("amazon/chronos-2", device_map="cpu",
                                            torch_dtype=torch.float32)
    lignes = []
    for var in variantes:
        ctx, passe, connu = _contextes(d, var)
        if passe is None:
            entrees = [torch.tensor(c) for c in ctx]
        else:
            noms = _noms_passe(var)
            entrees = []
            for i, c in enumerate(ctx):
                e = {"target": c, "past_covariates": dict(zip(noms, passe[i]))}
                if connu is not None:
                    taux = connu[i][0]
                    e["past_covariates"]["taux_credit"] = taux[:len(c)]
                    e["future_covariates"] = {"taux_credit": taux[len(c):]}
                entrees.append(e)
        q, _ = pipe.predict_quantiles(entrees, prediction_length=HORIZON,
                                      quantile_levels=list(QUANTILES))
        q = np.stack([x.cpu().numpy()[0] for x in q])          # (B, H, 3)
        lignes += _vers_lignes(d, f"chronos2_{var}", var, ctx, q[..., 0], q[..., 1], q[..., 2])
    return lignes


def timestral(d: dict, taille: str, variantes) -> list[dict]:
    from timestral import TimestralForecaster
    fc = TimestralForecaster.from_pretrained(f"mistralai/Timestral-{taille}")
    lignes = []
    for var in variantes:
        ctx, passe, connu = _contextes(d, var)
        x = _gauche(ctx)[:, None, :]                             # (B, 1, T)
        kw = {}
        if passe is not None:
            kw["past_covariates"] = _gauche(passe)
        if connu is not None:
            kw["known_covariates"] = _gauche(connu)              # (B, 1, T + H)
        f = fc.forecast(x, prediction_length=HORIZON, **kw)
        q10, q50, q90 = (np.asarray(f.quantile(a))[:, 0, :] for a in QUANTILES)
        lignes += _vers_lignes(d, f"timestral{taille}_{var}", var, ctx, q10, q50, q90)
    return lignes


# ---------------------------------------------------------------------- évaluation
def evaluer(previsions: pd.DataFrame, d: dict) -> pd.DataFrame:
    """Rejoint réalisé et naïve, ajoute le modèle publié et les combinaisons."""
    retro = d["retro"][["data_vintage", "target_month", "horizon", "predicted", "lo", "hi",
                        "naive"]].assign(methode="modele_publie")
    naive = retro[["data_vintage", "naive"]].drop_duplicates("data_vintage")

    combos = []
    ref = retro.set_index(["data_vintage", "horizon"])["predicted"]
    for nom, g in previsions.groupby("methode"):
        g = g.set_index(["data_vintage", "horizon"])
        c = g.assign(predicted=(g["predicted"] + ref.reindex(g.index)) / 2,
                     lo=np.nan, hi=np.nan, methode=f"combo_{nom}").reset_index()
        combos.append(c)

    tout = pd.concat([retro.drop(columns="naive"), previsions, *combos], ignore_index=True)
    tout = tout.merge(naive, on="data_vintage", how="left")
    obs = d["tx12"].dropna()
    tout["realized"] = pd.to_datetime(tout["target_month"]).map(obs)
    tout = tout[tout["realized"].notna()].copy()
    tout["ape"] = (tout["predicted"] - tout["realized"]).abs() / tout["realized"] * 100
    tout["naive_ape"] = (tout["naive"] - tout["realized"]).abs() / tout["realized"] * 100
    tout["sens_ok"] = (np.sign(tout["predicted"] - tout["naive"])
                       == np.sign(tout["realized"] - tout["naive"])).astype(float)
    tout["dans_bande"] = np.where(tout["lo"].notna(),
                                  ((tout["realized"] >= tout["lo"])
                                   & (tout["realized"] <= tout["hi"])).astype(float), np.nan)
    return tout


def _par_horizon(ev: pd.DataFrame) -> pd.DataFrame:
    return ev.groupby(["methode", "horizon"]).agg(
        mape=("ape", "mean"), naive_mape=("naive_ape", "mean")).reset_index()


def synthese(ev: pd.DataFrame) -> dict:
    """Blocs d'horizon (moyenne des MAPE par horizon, comme `verdict.blocs_horizon`),
    épisodes (moyenne des points, comme `page_archive._by_episode`), seuil d'entrée."""
    ph = _par_horizon(ev)
    modele = ph[ph["methode"] == "modele_publie"].set_index("horizon")["mape"]
    res = {}
    for nom, g in ph.groupby("methode"):
        g = g.set_index("horizon")
        blocs = []
        for lab, lo, hi in BLOCS:
            s = g.loc[lo:hi]
            m, n, mm = s["mape"].mean(), s["naive_mape"].mean(), modele.loc[lo:hi].mean()
            blocs.append({"bloc": lab, "mape": round(m, 2), "naive_mape": round(n, 2),
                          "skill_vs_naive": round(1 - m / n, 3),
                          "skill_vs_modele": round(1 - m / mm, 3)})
        sous = ev[ev["methode"] == nom]
        v = pd.to_datetime(sous["data_vintage"])
        episodes = []
        for a, b, lab in EPISODES:
            s = sous[(v >= a) & (v <= b)]
            if len(s):
                m, n = s["ape"].mean(), s["naive_ape"].mean()
                episodes.append({"label": lab, "n": int(len(s)), "mape": round(m, 2),
                                 "naive_mape": round(n, 2), "skill": round(1 - m / n, 3),
                                 "direction": round(s["sens_ok"].mean(), 3)})
        franchis = sum(b["skill_vs_modele"] >= SEUIL_SKILL for b in blocs)
        res[nom] = {
            "blocs": blocs,
            "episodes": episodes,
            "mape_globale": round(g["mape"].mean(), 2),
            "direction": round(sous["sens_ok"].mean(), 3),
            "couverture_10_90": (round(sous["dans_bande"].mean(), 3)
                                 if sous["dans_bande"].notna().any() else None),
            "blocs_franchis_vs_modele": int(franchis),
            "passe_le_seuil": bool(nom != "modele_publie" and franchis >= SEUIL_BLOCS),
        }
    return res


def controle(ev: pd.DataFrame, res: dict) -> list[str]:
    """Le modèle publié, évalué ici, doit retrouver les épisodes d'`archive.json`.

    Écart toléré : le réalisé est relu sur la série courante, comme sur le site ; s'il a
    été révisé depuis le dernier export, un écart de quelques centièmes est normal."""
    publie = json.loads((RACINE / "web/observable/src/data/archive.json").read_text("utf-8"))
    publies = {e["label"]: e for e in publie.get("episodes", [])}
    ecarts = []
    for e in res["modele_publie"]["episodes"]:
        p = publies.get(e["label"])
        if p and (abs(p["mape"] - e["mape"]) > 0.05 or abs(p["skill"] - e["skill"]) > 0.005):
            ecarts.append(f"{e['label']} : ici {e['mape']} / {e['skill']}, "
                          f"publié {p['mape']} / {p['skill']}")
    return ecarts


# ------------------------------------------------------------------------- rendu
def _pct(x):
    return "—" if x is None else f"{x * 100:+.1f} %".replace(".", ",")


def rapport(res: dict, durees: dict) -> str:
    ordre = sorted(res, key=lambda k: (k != "modele_publie", res[k]["mape_globale"]))
    l = ["# Banc d'essai — modèles de fondation face au modèle publié", "",
         "Cible : cumul 12 mois des ventes anciennes. Rétro-simulation, millésimes de "
         "l'archive (depuis 2009), horizons 1-18. Généré par `bench/tsfm_benchmark.py`.", "",
         "## Erreur par bloc d'horizon (MAPE, %) et part d'erreur évitée", "",
         "| Méthode | 1-3 | 4-6 | 7-12 | 13-18 | Globale | vs naïve 7-12 | vs modèle 7-12 "
         "| Blocs ≥ 5 % vs modèle | Bon sens | Bande 10-90 |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k in ordre:
        r = res[k]
        b = {x["bloc"]: x for x in r["blocs"]}
        l.append(f"| `{k}` | " + " | ".join(f"{b[x]['mape']:.2f}" for x in ("1-3", "4-6", "7-12", "13-18"))
                 + f" | {r['mape_globale']:.2f} | {_pct(b['7-12']['skill_vs_naive'])} "
                 f"| {_pct(b['7-12']['skill_vs_modele'])} | {r['blocs_franchis_vs_modele']}/4"
                 f"{' ✅' if r['passe_le_seuil'] else ''} | {r['direction'] * 100:.0f} % "
                 f"| {'—' if r['couverture_10_90'] is None else f'{r['couverture_10_90'] * 100:.0f} %'} |")
    l += ["", "Naïve (MAPE) : " + " · ".join(
        f"{x['bloc']} {x['naive_mape']:.2f}" for x in res["modele_publie"]["blocs"]), "",
        "## Part d'erreur évitée contre la naïve, par épisode", ""]
    labels = [e["label"] for e in res["modele_publie"]["episodes"]]
    l.append("| Méthode | " + " | ".join(lab.split(" · ")[0] for lab in labels) + " |")
    l.append("|---|" + "---|" * len(labels))
    for k in ordre:
        e = {x["label"]: x["skill"] for x in res[k]["episodes"]}
        l.append(f"| `{k}` | " + " | ".join(_pct(e.get(lab)) for lab in labels) + " |")
    l += _section_covariables(res)
    if durees:
        l += ["", "Durées de calcul (s) : " + ", ".join(f"{k} {v:.0f}" for k, v in durees.items())]
    return "\n".join(l) + "\n"


def _section_covariables(res: dict) -> list[str]:
    """Chaque covariable ajoutée, jugée contre `flux_cov` DU MÊME modèle, au seuil du projet."""
    bases = sorted(k for k in res if k.endswith("_flux_cov") and not k.startswith("combo_"))
    if not bases:
        return []
    l = ["", "## Covariables supplémentaires — erreur évitée contre la variante à 3 prédicteurs",
         "", "Seuil du projet : ≥ 5 % sur ≥ 3 des 4 blocs. `futur` = taux de crédit projeté "
         "par l'étage 1 (OAT décalée), donné comme covariable future connue.", "",
         "| Modèle | Ajout | 1-3 | 4-6 | 7-12 | 13-18 | Verdict |", "|---|---|---|---|---|---|---|"]
    for base in bases:
        modele = base[: -len("_flux_cov")]
        ref = {b["bloc"]: b["mape"] for b in res[base]["blocs"]}
        for k in sorted(res):
            if not (k.startswith(modele + "_flux_cov") and k != base):
                continue
            ajout = k[len(base):].lstrip("+_")
            gains = [1 - b["mape"] / ref[b["bloc"]] for b in res[k]["blocs"]]
            ok = sum(g >= SEUIL_SKILL for g in gains) >= SEUIL_BLOCS
            l.append(f"| `{modele}` | {ajout} | " + " | ".join(_pct(g) for g in gains)
                     + f" | {'✅ passe' if ok else 'refusé'} |")
    return l


#: Les prévisions rétro reprises par le site (page « Prévisions passées », section de
#: comparaison des modèles). La naïve et le modèle publié n'y sont pas : ils sont déjà
#: dans `data/forecast_archive.csv`. La combinaison se recalcule à la lecture. Le réalisé
#: n'est PAS stocké, comme dans l'archive : il est rejoint à chaque export.
METHODES_SITE = {"hw_flux": "holt_winters", "timestral209M_flux_cov": "timestral"}


def exporter_comparaison(prev: pd.DataFrame) -> None:
    sous = prev[prev["methode"].isin(METHODES_SITE)]
    if sous["methode"].nunique() < len(METHODES_SITE):
        return
    out = sous.assign(methode=sous["methode"].map(METHODES_SITE),
                      predicted=sous["predicted"].round(0),
                      mesure_le=time.strftime("%Y-%m-%d"))
    out[["methode", "data_vintage", "target_month", "horizon", "predicted", "mesure_le"]] \
        .to_csv(SORTIE / "comparaison_modeles.csv", index=False)


# --------------------------------------------------------------------------- main
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--models", nargs="*", default=[],
                   help="chronos2, timestral-5M, timestral-28M, timestral-123M, timestral-209M")
    p.add_argument("--variantes", nargs="*",
                   default=["tx12", "flux", "flux_cov", "flux_cov_futur"]
                   + [f"flux_cov+{k}" for k in CANDIDATES])
    p.add_argument("--sans-xgb", action="store_true", help="ne pas lancer XGBoost")
    p.add_argument("--check", action="store_true", help="contrôle de cohérence seul")
    args = p.parse_args()

    d = charger()
    print(f"[bench] {len(d['millesimes'])} millésimes, "
          f"{d['millesimes'][0]:%Y-%m} → {d['millesimes'][-1]:%Y-%m}")
    SORTIE.mkdir(exist_ok=True)

    lignes, durees, erreurs = [], {}, {}
    if not args.check:
        taches = {"ets_tx12": lambda: ets_tx12(d), "hw_flux": lambda: hw_flux(d)}
        if not args.sans_xgb:
            taches["xgb_direct"] = lambda: xgb_direct(d)
        for m in args.models:
            if m == "chronos2":
                taches[m] = lambda: chronos2(d, args.variantes)
            elif m.startswith("timestral-"):
                taille = m.split("-", 1)[1]
                taches[m] = lambda t=taille: timestral(d, t, args.variantes)
            else:
                raise SystemExit(f"modèle inconnu : {m}")
        for nom, f in taches.items():
            t0 = time.time()
            try:
                lignes += f()
            except Exception:       # un modèle qui casse ne doit pas emporter les autres
                import traceback
                erreurs[nom] = traceback.format_exc()
                print(f"[bench] {nom} : ÉCHEC\n{erreurs[nom]}")
                continue
            durees[nom] = time.time() - t0
            print(f"[bench] {nom} : {durees[nom]:.0f} s")

    prev = pd.DataFrame(lignes, columns=["methode", "data_vintage", "target_month", "horizon",
                                         "predicted", "lo", "hi"])
    ev = evaluer(prev, d)
    res = synthese(ev)

    ecarts = controle(ev, res)
    print("[bench] contrôle : " + ("OK, épisodes publiés retrouvés" if not ecarts
                                   else "ÉCARTS\n  " + "\n  ".join(ecarts)))
    if args.check:
        raise SystemExit(1 if ecarts else 0)

    prev.to_csv(SORTIE / "previsions.csv", index=False)
    exporter_comparaison(prev)
    (SORTIE / "synthese.json").write_text(
        json.dumps({"controle_ecarts": ecarts, "durees_s": durees, "erreurs": erreurs,
                    "resultats": res},
                   ensure_ascii=False, indent=1), "utf-8")
    texte = rapport(res, durees)
    if erreurs:
        texte += "\n## Échecs\n\n" + "\n".join(
            f"### {k}\n\n```\n{v[-3000:]}\n```\n" for k, v in erreurs.items())
    (SORTIE / "rapport.md").write_text(texte, "utf-8")
    print((SORTIE / "rapport.md").read_text("utf-8"))


if __name__ == "__main__":
    main()
