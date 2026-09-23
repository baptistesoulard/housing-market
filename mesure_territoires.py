"""La PORTE du module « Territoires » : deux axes observés ont-ils séparé les départements ?

Outil ponctuel, versionné (comme `dvf_backfill.py`), à relancer si les données ou le
protocole changent. Il n'écrit rien dans `data/` : il imprime un rapport Markdown, que
l'on copie dans `docs/mesure-territoires-<date>.md`, et dont les chiffres retenus vont
dans `web_export.TERRITOIRES_GATE` (porte franchie) ou `web_export.REFUTATIONS` (manquée).

Le protocole et les seuils sont ceux de `docs/plan-territoires.md` §3, écrits AVANT
d'exécuter quoi que ce soit. Ne pas les déplacer après avoir vu les résultats.

    python mesure_territoires.py            # rapport sur stdout
    python mesure_territoires.py --cache D  # répertoire de cache des appels Melodi
    python mesure_territoires.py --out docs/mesure-territoires-AAAA-MM-JJ.md

Les deux axes
-------------
A « héritée »  : part des résidences principales détenues par un ménage dont la personne
                 de référence a 65 ans ou plus. Mesure DIRECTE disponible pour 2023 seulement
                 (DS_RP_TD_LOGEMENT_AGE_PRINC) ; pour 2012 et 2017, un proxy dont la fidélité
                 est mesurée ici même (Spearman proxy / direct en 2023).
D « désirée »  : deux candidats départagés par la mesure —
                 D1 solde migratoire apparent annuel (%), période intercensitaire précédente ;
                 D2 part des habitants arrivés dans l'année de hors du département (tous
                 âges : le détail par origine n'est publié que pour l'ensemble, la ventilation
                 par âge ne distingue pas un déménagement interne d'une arrivée).

Sources (toutes vérifiées le 2026-09-20, voir le plan §1) : API Melodi de l'INSEE (JSON,
sans clé) pour le RP et l'état civil ; comparateur de territoires (Parquet) pour les
populations légales ; l'entrepôt local pour DVF (vue SQL `dvf`).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import urllib.request
from datetime import date

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import departements  # noqa: E402
import dvf_clean  # noqa: E402
import queries as q  # noqa: E402

MELODI = "https://api.insee.fr/melodi/data/"
COMPARATEUR = "https://www.insee.fr/fr/statistiques/fichier/2521169/comparateur.parquet"
UA = {"User-Agent": "Mozilla/5.0 (barometre-logement; mesure_territoires)"}

# Les fenêtres du test : prédicteurs d'un millésime RP, résultat DVF sur les années qui
# suivent sa PUBLICATION (RP 2012 paraît en 2015, RP 2017 en 2020). Les deux fenêtres ne
# se recouvrent qu'en 2019.
FENETRES = [
    # (nom, millésime RP, année de début du résultat, année de fin, période du solde migratoire)
    ("W1", "2012", 2014, 2019, ("2007", "2012")),
    ("W2", "2017", 2019, 2025, ("2012", "2017")),
]

# Les seuils de la porte (plan §3.4) — figés.
SEUIL_RHO = 0.30
SEUIL_RHO_PARTIEL = 0.15
SEUIL_ECART_PTS = 5.0
BOOTSTRAP = 2000
GRAINE = 20260920


# ------------------------------------------------------------------ accès aux sources --
def _cache_dir(arg):
    d = arg or os.path.join(tempfile.gettempdir(), "hm_territoires")
    os.makedirs(d, exist_ok=True)
    return d


def _get(url, cache):
    """GET mis en cache sur disque (clé = hash de l'URL) : la mesure se relance sans
    réinterroger l'INSEE, et un rapport se reproduit à l'identique."""
    chemin = os.path.join(cache, hashlib.sha1(url.encode()).hexdigest())
    if os.path.exists(chemin):
        with open(chemin, "rb") as f:
            return f.read()
    req = urllib.request.Request(url, headers={**UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        corps = r.read()
    with open(chemin, "wb") as f:
        f.write(corps)
    return corps


def melodi(dataset, filtres, cache):
    """Toutes les observations d'un jeu Melodi au niveau département (GEO=DEP), avec la
    pagination suivie jusqu'au bout. Rend un DataFrame : une colonne par dimension + `value`.

    `GEO` arrive préfixé (`2026-DEP-23`) : on garde le code après le dernier tiret, en
    chaîne — « 01 » perd son zéro en entier et la Corse n'est pas numérique.
    """
    params = "&".join(f"{k}={v}" for k, v in {"GEO": "DEP", **filtres}.items())
    lignes, page = [], 1
    while True:
        url = f"{MELODI}{dataset}?{params}&maxResult=10000&page={page}"
        j = json.loads(_get(url, cache).decode("utf-8", "replace"))
        obs = j.get("observations", [])
        for o in obs:
            d = dict(o["dimensions"])
            # OBS_STATUS « M » (manquant, ex. Mayotte avant 2011) : mesure sans `value`.
            d["value"] = o["measures"]["OBS_VALUE_NIVEAU"].get("value", np.nan)
            lignes.append(d)
        if len(obs) < 10000:
            break
        page += 1
    df = pd.DataFrame(lignes)
    df["dep"] = df["GEO"].str.rsplit("-", n=1).str[-1]
    return df


def comparateur(cache):
    """Le comparateur de territoires, niveau département, en format long."""
    import duckdb
    chemin = os.path.join(cache, "comparateur.parquet")
    if not os.path.exists(chemin):
        req = urllib.request.Request(COMPARATEUR, headers=UA)
        with urllib.request.urlopen(req, timeout=300) as r, open(chemin, "wb") as f:
            f.write(r.read())
    con = duckdb.connect()
    lit = chemin.replace("\\", "/")
    return con.execute(f"""
        SELECT GEO AS dep, TAB_MEASURE AS mesure, TIME_PERIOD AS annee, OBS_VALUE AS value
        FROM read_parquet('{lit}') WHERE GEO_OBJECT = 'DEP'
    """).df()


# ------------------------------------------------------------------ les prédicteurs ----
def _pivot(df, cles, valeur="value"):
    return df.pivot_table(index="dep", columns=cles, values=valeur, aggfunc="sum")


def predicteurs(cache):
    """Une table (dep, millésime) → indicateurs bruts et ratios, pour 2012, 2017, 2023."""
    T = {}

    # -- RP : résidences principales par statut d'occupation, et par type ----------------
    log = melodi("DS_RP_LOGEMENT_PRINC", {"OCS": "DW_MAIN", "NOR": "_T", "BUILD_END": "_T",
                                          "NRG_SRC": "_T", "CARS": "_T", "CARPARK": "_T",
                                          "L_STAY": "_T", "RP_MEASURE": "DWELLINGS"}, cache)
    tot = log[(log.TSH == "_T") & (log.TDW == "_T")].set_index(["dep", "TIME_PERIOD"])["value"]
    prop = log[(log.TSH == "100") & (log.TDW == "_T")].set_index(["dep", "TIME_PERIOD"])["value"]
    maison = log[(log.TSH == "_T") & (log.TDW == "1")].set_index(["dep", "TIME_PERIOD"])["value"]
    T["rp"], T["rp_prop"], T["rp_maison"] = tot, prop, maison

    # -- RP : logements vacants / total logements -----------------------------------------
    logt = melodi("DS_RP_LOGEMENT_PRINC", {"TSH": "_T", "TDW": "_T", "NOR": "_T",
                                           "BUILD_END": "_T", "NRG_SRC": "_T", "CARS": "_T",
                                           "CARPARK": "_T", "L_STAY": "_T",
                                           "RP_MEASURE": "DWELLINGS"}, cache)
    T["log"] = logt[logt.OCS == "_T"].set_index(["dep", "TIME_PERIOD"])["value"]
    T["log_vac"] = logt[logt.OCS == "DW_VAC"].set_index(["dep", "TIME_PERIOD"])["value"]

    # -- RP : population par âge ----------------------------------------------------------
    pop = melodi("DS_RP_POPULATION_PRINC", {"SEX": "_T", "RP_MEASURE": "POP"}, cache)
    T["pop"] = pop[pop.AGE == "_T"].set_index(["dep", "TIME_PERIOD"])["value"]
    T["pop65"] = pop[pop.AGE == "Y_GE65"].set_index(["dep", "TIME_PERIOD"])["value"]

    # -- RP : migrations résidentielles (lieu de résidence un an plus tôt) ----------------
    # PREV_RES_AREA (nomenclature IRAN, déduite par sommation le 2026-09-20) : 11 même
    # logement, 12 autre logement même commune, 21 autre commune du département, 22 autre
    # département de la région, 23 autre région, 24 DOM/COM, 25T32 étranger. Le détail par
    # origine n'existe que pour AGE=Y_GE1 (tous âges) : par tranche d'âge, seul « a changé
    # de commune » (20_30) est publié, qui mêle les déménagements internes au département.
    mig = melodi("DS_RP_MIGRES_PRINC", {"AGE": "Y_GE1", "RP_MEASURE": "POP"}, cache)
    m = mig.set_index(["dep", "TIME_PERIOD", "PREV_RES_AREA"])["value"].unstack("PREV_RES_AREA")
    T["pop_ge1"] = m["_T"]
    T["arrivees"] = m[["22", "23", "24", "25T32"]].sum(axis=1)

    # -- RP 2023 : la mesure DIRECTE de l'axe A ------------------------------------------
    age = melodi("DS_RP_TD_LOGEMENT_AGE_PRINC", {"OCS": "DW_MAIN", "NOR": "_T", "TDW": "_T",
                                                 "RP_MEASURE": "DWELLINGS"}, cache)
    a = age.set_index(["dep", "TIME_PERIOD", "TSH", "AGE"])["value"]
    direct = (a.xs(("100", "Y65T79"), level=("TSH", "AGE"))
              + a.xs(("100", "Y_GE80"), level=("TSH", "AGE")))
    T["rp_prop65"] = direct
    T["rp_direct_total"] = a.xs(("_T", "_T"), level=("TSH", "AGE"))

    X = pd.DataFrame(T)
    X.index.names = ["dep", "millesime"]
    X = X.reset_index()

    # -- Ratios (en %) ----------------------------------------------------------------------
    X["part_prop"] = 100 * X["rp_prop"] / X["rp"]
    X["part_maison"] = 100 * X["rp_maison"] / X["rp"]
    X["taux_vacance"] = 100 * X["log_vac"] / X["log"]
    X["part_65"] = 100 * X["pop65"] / X["pop"]          # X.pop serait la méthode pop()
    X["tx_arrivee"] = 100 * X["arrivees"] / X["pop_ge1"]
    X["A_direct"] = 100 * X["rp_prop65"] / X["rp_direct_total"]   # 2023 seulement
    # Proxy de A pour les millésimes sans croisement : part de propriétaires × part des
    # 65 ans et plus (deux marges du même tableau). Sa fidélité est MESURÉE plus bas.
    X["A_proxy"] = X["part_prop"] * X["part_65"] / 100

    # -- Solde migratoire apparent (comparateur + état civil) ----------------------------
    cmp_ = comparateur(cache)
    popc = cmp_[cmp_.mesure == "POP"].pivot_table(index="dep", columns="annee", values="value")
    nais = melodi("DS_ETAT_CIVIL_NAIS_COMMUNES", {"EC_MEASURE": "LVB"}, cache)
    dec = melodi("DS_ETAT_CIVIL_DECES_COMMUNES", {"EC_MEASURE": "DTH"}, cache)
    nat = (nais.set_index(["dep", "TIME_PERIOD"])["value"]
           - dec.set_index(["dep", "TIME_PERIOD"])["value"]).unstack("TIME_PERIOD")

    def solde(t0, t1):
        """Solde apparent des entrées-sorties, en % annuel de la population de départ.
        L'état civil commence en 2008 : pour 2007→2012, l'année 2007 manquante est
        remplacée par 2008 (une approximation, dite dans le rapport)."""
        annees = [str(y) for y in range(int(t0), int(t1))]
        dispo = [y for y in annees if y in nat.columns]
        s = nat[dispo].sum(axis=1) * (len(annees) / len(dispo))
        return 100 * (popc[t1] - popc[t0] - s) / popc[t0] / (int(t1) - int(t0))

    for mil, (t0, t1) in {"2012": ("2007", "2012"), "2017": ("2012", "2017"),
                          "2023": ("2017", "2023")}.items():
        sm = solde(t0, t1).rename("solde_mig")
        X.loc[X.millesime == mil, "solde_mig"] = X.loc[X.millesime == mil, "dep"].map(sm).values
    return X


# ------------------------------------------------------------------ le résultat (DVF) --
def resultats(con):
    """Par département et par année : prix médian au m² moyen des trimestres, ventes."""
    return q.rows(con, """
        SELECT Department AS dep, year(Date) AS annee,
               AVG(PrixM2Median) AS prix, SUM(NbVentes) AS ventes
        FROM "dvf" WHERE Type = 'Ensemble' GROUP BY 1, 2 ORDER BY 1, 2
    """)


def fenetre(res, debut, fin):
    """Δlog prix et Δlog ventes entre deux années, en écart à la médiane des départements,
    plus le niveau de prix initial (le contrôle « déjà dans les prix »)."""
    r = pd.DataFrame(res)
    p = r.pivot(index="dep", columns="annee", values="prix")
    v = r.pivot(index="dep", columns="annee", values="ventes")
    out = pd.DataFrame({
        "d_prix": 100 * np.log(p[fin] / p[debut]),
        "d_ventes": 100 * np.log(v[fin] / v[debut]),
        "niveau": np.log(p[debut]),
    }).dropna()
    out["d_prix"] -= out["d_prix"].median()
    out["d_ventes"] -= out["d_ventes"].median()
    return out


# ------------------------------------------------------------------ statistiques ------
def spearman(x, y):
    return float(np.corrcoef(pd.Series(x).rank(), pd.Series(y).rank())[0, 1])


def spearman_ic(x, y, rng):
    """ρ et son intervalle à 90 % par bootstrap sur les départements."""
    x, y = np.asarray(x), np.asarray(y)
    n = len(x)
    tirages = []
    for _ in range(BOOTSTRAP):
        i = rng.integers(0, n, n)
        tirages.append(spearman(x[i], y[i]))
    return spearman(x, y), float(np.percentile(tirages, 5)), float(np.percentile(tirages, 95))


def spearman_partiel(x, y, z):
    """ρ de rang entre x et y une fois le rang de z retiré des deux (résidus d'une
    régression linéaire sur les rangs) : ce que x dit de y au-delà de z."""
    rx, ry, rz = (pd.Series(v).rank().to_numpy() for v in (x, y, z))
    Z = np.column_stack([np.ones_like(rz), rz])
    ex = rx - Z @ np.linalg.lstsq(Z, rx, rcond=None)[0]
    ey = ry - Z @ np.linalg.lstsq(Z, ry, rcond=None)[0]
    return float(np.corrcoef(ex, ey)[0, 1])


def quadrants(df, a, d):
    """Situation de chaque département : seuils = médianes (aucun réglage)."""
    ha, hd = df[a] > df[a].median(), df[d] > df[d].median()
    return np.select([ha & ~hd, ha & hd, ~ha & ~hd, ~ha & hd],
                     ["Héritée, peu rejointe", "Héritée et rejointe",
                      "Jeune, peu rejointe", "Jeune et rejointe"], default="")


# ------------------------------------------------------------------ rapport -----------
def _f(x, d=2):
    return ("+" if x > 0 else "") + f"{x:.{d}f}".replace(".", ",")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=None)
    ap.add_argument("--out", default=None, help="fichier Markdown (UTF-8) en plus de stdout")
    args = ap.parse_args()
    cache = _cache_dir(args.cache)
    rng = np.random.default_rng(GRAINE)

    X = predicteurs(cache)
    con = q.open_warehouse(refresh=False)
    res = resultats(con)
    hors = set(dvf_clean.DEPARTEMENTS_SANS_DVF)

    L = []
    P = L.append
    P(f"# Mesure — module Territoires ({date.today().isoformat()})\n")
    P("Protocole et seuils : `docs/plan-territoires.md` §3, figés avant exécution. "
      "Script : `mesure_territoires.py`.\n")

    # -- 0. Fidélité du proxy de l'axe A (2023) -----------------------------------------
    x23 = X[X.millesime == "2023"].dropna(subset=["A_direct"])
    rho_proxy = spearman(x23.A_proxy, x23.A_direct)
    rho_65 = spearman(x23.part_65, x23.A_direct)
    rho_prop = spearman(x23.part_prop, x23.A_direct)
    P("## 0. L'axe A ne se mesure directement qu'en 2023 : fidélité des proxys\n")
    P("Spearman avec la mesure directe (part des RP détenues par un ménage de 65 ans ou "
      f"plus), sur {len(x23)} départements :\n")
    P("| proxy | ρ |\n|---|---|")
    P(f"| part de propriétaires × part des 65 ans et plus | **{_f(rho_proxy)}** |")
    P(f"| part des 65 ans et plus seule | {_f(rho_65)} |")
    P(f"| part de propriétaires seule | {_f(rho_prop)} |\n")
    meilleur = max([("A_proxy", rho_proxy), ("part_65", rho_65), ("part_prop", rho_prop)],
                   key=lambda t: t[1])
    P(f"Proxy retenu pour 2012 et 2017 : `{meilleur[0]}` (ρ = {_f(meilleur[1])}). "
      + ("Le seuil de 0,90 du plan est tenu.\n" if meilleur[1] >= 0.9 else
         "⚠️ Sous le seuil de 0,90 du plan : le backtest ne valide qu'imparfaitement l'axe publié.\n"))
    A_col = meilleur[0]

    # -- 1. Test de Paris ---------------------------------------------------------------
    P("## 1. Le test de Paris : quel axe D mesure la demande, et non l'offre ?\n")
    P("Rang (1 = le plus « rejoint ») de Paris (75) et des Hauts-de-Seine (92) sur les "
      "deux candidats, et tiers atteint :\n")
    P("| millésime | candidat | Paris | Hauts-de-Seine | tiers « désiré » ? |\n|---|---|---|---|---|")
    paris_ok = {"solde_mig": True, "tx_arrivee": True}
    for mil in ("2017", "2023"):
        xm = X[X.millesime == mil].set_index("dep")
        n = len(xm)
        for cand, nom in (("solde_mig", "D1 solde migratoire net"),
                          ("tx_arrivee", "D2 arrivées de hors du département")):
            rg = xm[cand].rank(ascending=False)
            ok = (rg["75"] <= n / 3) and (rg["92"] <= n / 3)
            paris_ok[cand] &= bool(ok)
            P(f"| {mil} | {nom} | {int(rg['75'])}/{n} | {int(rg['92'])}/{n} | {'oui' if ok else '**non**'} |")
    P("")

    # -- 2. Les deux fenêtres ------------------------------------------------------------
    P("## 2. Deux fenêtres, quatre-vingt-dix-sept départements\n")
    resume = {}
    for nom, mil, deb, fin, _ in FENETRES:
        y = fenetre(res, deb, fin)
        xm = X[X.millesime == mil].set_index("dep")
        df = y.join(xm, how="inner")
        df = df[~df.index.isin(hors)].dropna(subset=[A_col, "solde_mig", "tx_arrivee"])
        P(f"### {nom} — prédicteurs RP {mil}, résultat DVF {deb} → {fin} ({len(df)} départements)\n")
        P("| axe | résultat | ρ [IC 90 %] | ρ partiel à niveau de prix donné |\n|---|---|---|---|")
        lignes = {}
        for ax, lab in ((A_col, "A héritée (proxy)"), ("solde_mig", "D1 solde migratoire"),
                        ("tx_arrivee", "D2 arrivées hors dép.")):
            for cible in ("d_prix", "d_ventes"):
                r, lo, hi = spearman_ic(df[ax], df[cible], rng)
                rp = spearman_partiel(df[ax], df[cible], df["niveau"])
                lignes[(ax, cible)] = (r, lo, hi, rp)
                P(f"| {lab} | {'prix' if cible == 'd_prix' else 'ventes'} | "
                  f"{_f(r)} [{_f(lo)} ; {_f(hi)}] | {_f(rp)} |")
        rn = spearman(df["niveau"], df["d_prix"])
        P(f"\nContrôle — le **niveau** de prix {deb} contre la croissance des prix : ρ = {_f(rn)}.\n")

        # Score et quadrants, pour chaque candidat D
        for cand, lab in (("solde_mig", "D1"), ("tx_arrivee", "D2")):
            score = df[cand].rank() - df[A_col].rank()
            r, lo, hi = spearman_ic(score, df["d_prix"], rng)
            rp = spearman_partiel(score, df["d_prix"], df["niveau"])
            rv = spearman(score, df["d_ventes"])
            df["situation"] = quadrants(df, A_col, cand)
            med = df.groupby("situation")[["d_prix", "d_ventes"]].median()
            eff = df["situation"].value_counts()
            ecart = med.loc["Jeune et rejointe", "d_prix"] - med.loc["Héritée, peu rejointe", "d_prix"]
            ecart_v = med.loc["Jeune et rejointe", "d_ventes"] - med.loc["Héritée, peu rejointe", "d_ventes"]
            P(f"**Score rang(D) − rang(A), avec {lab}** : ρ prix = {_f(r)} [{_f(lo)} ; {_f(hi)}], "
              f"ρ partiel = {_f(rp)}, ρ ventes = {_f(rv)}.\n")
            P("| situation | n | croissance prix relative (pts) | croissance ventes relative (pts) |\n|---|---|---|---|")
            for s in ("Héritée, peu rejointe", "Héritée et rejointe", "Jeune, peu rejointe", "Jeune et rejointe"):
                if s in med.index:
                    P(f"| {s} | {eff[s]} | {_f(med.loc[s, 'd_prix'], 1)} | {_f(med.loc[s, 'd_ventes'], 1)} |")
            P(f"\nÉcart « Jeune et rejointe » − « Héritée, peu rejointe » : **{_f(ecart, 1)} pts** de prix, "
              f"{_f(ecart_v, 1)} pts de ventes.\n")
            resume[(nom, cand)] = dict(rho=r, lo=lo, hi=hi, rho_partiel=rp, rho_ventes=rv,
                                       ecart_prix=ecart, ecart_ventes=ecart_v, n=len(df))

    # -- 3. La porte ---------------------------------------------------------------------
    P("## 3. La porte (plan §3.4)\n")
    P(f"Critères, dans LES DEUX fenêtres et de même signe : ρ(score, prix) ≥ {_f(SEUIL_RHO)} ; "
      f"ρ partiel ≥ {_f(SEUIL_RHO_PARTIEL)} ; écart de croissance médiane ≥ {_f(SEUIL_ECART_PTS, 0)} pts ; "
      "test de Paris réussi par l'axe D retenu.\n")
    P("| axe D | test de Paris | W1 ρ / ρp / écart | W2 ρ / ρp / écart | porte |\n|---|---|---|---|---|")
    verdicts = {}
    for cand, lab in (("solde_mig", "D1 solde migratoire"), ("tx_arrivee", "D2 arrivées hors dép.")):
        w1, w2 = resume[("W1", cand)], resume[("W2", cand)]
        ok = (paris_ok[cand]
              and w1["rho"] >= SEUIL_RHO and w2["rho"] >= SEUIL_RHO
              and w1["rho_partiel"] >= SEUIL_RHO_PARTIEL and w2["rho_partiel"] >= SEUIL_RHO_PARTIEL
              and w1["ecart_prix"] >= SEUIL_ECART_PTS and w2["ecart_prix"] >= SEUIL_ECART_PTS)
        ok_ventes = (w1["rho_ventes"] >= SEUIL_RHO and w2["rho_ventes"] >= SEUIL_RHO
                     and w1["ecart_ventes"] >= SEUIL_ECART_PTS and w2["ecart_ventes"] >= SEUIL_ECART_PTS)
        verdicts[cand] = (ok, ok_ventes)
        P(f"| {lab} | {'oui' if paris_ok[cand] else 'non'} | "
          f"{_f(w1['rho'])} / {_f(w1['rho_partiel'])} / {_f(w1['ecart_prix'], 1)} | "
          f"{_f(w2['rho'])} / {_f(w2['rho_partiel'])} / {_f(w2['ecart_prix'], 1)} | "
          f"{'**FRANCHIE (prix)**' if ok else ('franchie sur les VENTES seulement' if ok_ventes else 'manquée')} |")
    P("")
    if any(v[0] for v in verdicts.values()):
        P("**Décision : porte franchie sur les prix** → phases 2, 3a, 3b, 4 ; constante "
          "`TERRITOIRES_GATE` datée dans `web/export/reperes.py`.")
    elif any(v[1] for v in verdicts.values()):
        P("**Décision : porte franchie sur les VENTES seulement** → page carte rédigée sur les "
          "volumes, jamais sur les prix (plan §3.5).")
    else:
        P("**Décision : porte manquée** → phases 2, 3a, 4 seulement ; entrée datée dans "
          "`REFUTATIONS` ; pas de page carte.")
    texte = "\n".join(L)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(texte + "\n")
    # La console Windows est en cp1252 : ne jamais laisser un « ρ » faire échouer le rapport.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(texte)


if __name__ == "__main__":
    main()
