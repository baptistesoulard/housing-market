"""Adaptateur d'export web (Étape 0 du PoC de migration hors Streamlit).

Réutilise TELLE QUELLE la couche back-office Python (data_manager, analysis,
forecast, actualites) — c'est le contrat de la migration : on ne réécrit que la
couche d'affichage. Ce script recompute le contenu de l'onglet « Synthèse » de
`app.py` (pastilles par pilier, cartes Activité / Financement / Perspective, à
retenir, fraîcheur des données, et les deux séries du graphique neuf/ancien) et
le sérialise en JSON statique que le front Observable Framework lit au build.

Usage :
    python web/export/web_export.py            # écrit web/observable/src/data/synthese.json

Aucune dépendance nouvelle : pandas / numpy suffisent (déjà dans requirements.txt).
À brancher en fin du refresh hebdo (GitHub Actions) pour que Cloudflare Pages
reconstruise le site à chaque publication de données.
"""
from __future__ import annotations

import itertools
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

# --- Rendre les modules du dépôt importables quel que soit le CWD -----------------
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from data_manager import DataManager          # noqa: E402
import analysis as ana                         # noqa: E402
import forecast as fc                          # noqa: E402
import actualites as actu                      # noqa: E402

# Cible BPCE 2026 (miroir des constantes d'app.py, bloc Perspective).
BPCE_TX_ANCIEN_2026 = 890_000

# Palette (miroir d'app.py).
COLOR_TEXT = "#2D3748"
COLOR_BRICK = "#E64A19"
COLOR_GREEN = "#388E3C"

_FR_MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin",
              "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

DATA_DIR = os.path.join(_REPO_ROOT, "web", "observable", "src", "data")
OUT_PATH = os.path.join(DATA_DIR, "synthese.json")

# Palette étendue (miroir d'app.py) pour les onglets Neuf/Ancien.
COLOR_BLUE = "#64B5F6"
COLOR_TERRACOTTA = "#C1694F"
COLOR_SUNFLOWER = "#F5B041"

# Codes courts et stables pour les quatre types SIT@DEL (clés de `by_type` / `kpis_by_type`).
_TYPE_CODES = {"Maison Individuelle Pure": "ip", "Maison Individuelle Groupée": "ig",
               "Logement Collectif": "co", "Logement en Résidence": "re"}


# ============================ helpers de formatage ================================
def _fmt_month_year(date) -> str:
    if pd.isna(date):
        return "—"
    d = pd.Timestamp(date)
    return f"{_FR_MONTHS[d.month - 1]} {d.year}"


def _th(v) -> str:
    """Entier avec espace comme séparateur de milliers ('123 456')."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{int(round(float(v))):,}".replace(",", " ")


def _human(v) -> str:
    """Nombre 'de titre' : '385 k' au-dessus de 100 000, entier espacé en dessous."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    v = float(v)
    if abs(v) >= 100_000:
        return f"{v / 1000.0:,.0f} k".replace(",", " ")
    return f"{int(round(v)):,}".replace(",", " ")


def _pct_fr(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{v:+.1f}%".replace(".", ",")


def _dot(status: str) -> str:
    return {"up": "🟢", "flat": "🟠", "down": "🔴"}.get(status, "⚪")


def _status_yoy(v, hi: float = 1.0, lo: float = -1.0) -> str:
    if v is None:
        return "flat"
    return "up" if v > hi else ("down" if v < lo else "flat")


def _delta3m_sub(v, exact=None) -> str:
    txt = _pct_fr(v) + " vs un an plus tôt (3 derniers mois)"
    if exact is not None:
        txt += " · total exact : " + _th(exact)
    return txt


def _borrow_capacity_factor(rate_pct, years):
    """Valeur actuelle d'une mensualité unitaire sur `years` ans au taux annuel
    `rate_pct` (miroir d'app.py, utilisé par la carte d'accessibilité)."""
    i = np.asarray(rate_pct, dtype=float) / 100.0 / 12.0
    n = years * 12
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(i > 0, (1.0 - (1.0 + i) ** (-n)) / i, float(n))


# ============================ chargement partagé des frames =======================
def load_frames() -> dict:
    """Charge les 7 datasets une seule fois (réutilisé par tous les builders d'onglets)."""
    dm = DataManager()
    dm.load_or_generate_all()
    (df_sitadel, df_ventes_ancien, df_macro, df_sales,
     df_revenue, df_ecln, df_company_sales) = dm.read_frames()
    return {"sitadel": df_sitadel, "ventes_ancien": df_ventes_ancien, "macro": df_macro,
            "sales": df_sales, "revenue": df_revenue, "ecln": df_ecln,
            "company_sales": df_company_sales}


def _rows_from(df, mapping, date_col="Date"):
    """Sérialise un DataFrame en liste de dicts {date: 'YYYY-MM-DD', **mapping} en
    ignorant les valeurs NaN (mapping = {json_key: df_col})."""
    out = []
    for _, r in df.sort_values(date_col).iterrows():
        row = {"date": pd.Timestamp(r[date_col]).strftime("%Y-%m-%d")}
        for k, col in mapping.items():
            v = r.get(col)
            row[k] = None if (v is None or pd.isna(v)) else float(v)
        out.append(row)
    return out


# ============================ construction du payload =============================
def build_synthese(frames: dict) -> dict:
    df_sitadel_full = frames["sitadel"]
    df_ventes_ancien_full = frames["ventes_ancien"]
    df_macro_full = frames["macro"]
    df_ecln_full = frames["ecln"]

    # --- Momentum & niveaux 12 m (indépendants de tout filtre, comme dans app.py) ---
    sit = ana.aggregate_sitadel(df_sitadel_full)
    va = ana.aggregate_ventes_ancien(df_ventes_ancien_full)
    roll_sit = ana.calculate_rolling_12m(sit, ["Permis", "MisesEnChantier"])
    roll_va = ana.calculate_rolling_12m(va, ["Transactions"])
    m_permis = ana.momentum_metrics(sit, "Permis")
    m_mises = ana.momentum_metrics(sit, "MisesEnChantier")
    m_tx = ana.momentum_metrics(va, "Transactions")
    k_permis = ana.calculate_kpis(roll_sit, "Permis")
    k_mises = ana.calculate_kpis(roll_sit, "MisesEnChantier")
    k_tx = ana.calculate_kpis(roll_va, "Transactions")

    mi = df_macro_full.set_index("Date").sort_index()

    def _last_prev(col, months=12):
        if col not in mi.columns:
            return None, None
        s = mi[col].dropna()
        if s.empty:
            return None, None
        last = float(s.iloc[-1])
        cutoff = s.index[-1] - pd.DateOffset(months=months)
        older = s[s.index <= cutoff]
        return last, (float(older.iloc[-1]) if not older.empty else None)

    # ---------------------------- Pastilles par pilier ----------------------------
    neuf_l3 = [v for v in (m_permis.get("last3_yoy"), m_mises.get("last3_yoy")) if v is not None]
    pill_neuf = _status_yoy(sum(neuf_l3) / len(neuf_l3)) if neuf_l3 else "flat"
    pill_ancien = _status_yoy(m_tx.get("last3_yoy"))
    r_now, r_yr = _last_prev("Credit_Logement_Taux_Interet")
    dr_yr = None if (r_now is None or r_yr is None) else r_now - r_yr
    pill_fin = ("flat" if dr_yr is None
                else ("down" if dr_yr > 0.1 else ("up" if dr_yr < -0.1 else "flat")))
    bls_now, _ = _last_prev("Demande_Credit_Perspectives")

    w_market = {"up": "en reprise", "flat": "stable", "down": "en repli"}
    w_fin = {"up": "en amélioration", "flat": "stable", "down": "en durcissement"}
    pillars = [
        {"key": "neuf", "label": "Neuf", "status": pill_neuf,
         "dot": _dot(pill_neuf), "word": w_market[pill_neuf]},
        {"key": "ancien", "label": "Ancien", "status": pill_ancien,
         "dot": _dot(pill_ancien), "word": w_market[pill_ancien]},
        {"key": "fin", "label": "Financement", "status": pill_fin,
         "dot": _dot(pill_fin), "word": w_fin[pill_fin]},
    ]

    # ------------------------------- À retenir ------------------------------------
    mom_ip = ana.momentum_metrics(
        ana.aggregate_sitadel(df_sitadel_full, ana.SITADEL_INDIVIDUEL_PUR), "MisesEnChantier")
    takeaways = []
    neuf_head = {"up": "la construction accélère", "flat": "la construction est stable",
                 "down": "la construction recule"}[pill_neuf]
    l1 = (f"{_dot(pill_neuf)} **Neuf** — {neuf_head} : permis "
          f"{_pct_fr(k_permis['yoy_12m_pct'])} et mises en chantier "
          f"{_pct_fr(k_mises['yoy_12m_pct'])} sur 12 mois")
    if mom_ip.get("last3_yoy") is not None:
        l1 += f" (maison individuelle pure : {_pct_fr(mom_ip['last3_yoy'])} sur 3 mois)."
    else:
        l1 += "."
    takeaways.append(l1)

    tx_l3 = m_tx.get("last3_yoy")
    l2 = (f"{_dot(pill_ancien)} **Ancien** — {_human(k_tx['current_12m'])} ventes sur 12 mois "
          f"({_pct_fr(k_tx['yoy_12m_pct'])})")
    if tx_l3 is not None:
        if pill_ancien == "down":
            l2 += f", mais la dynamique ralentit : {_pct_fr(tx_l3)} sur les 3 derniers mois."
        else:
            l2 += f" ; {_pct_fr(tx_l3)} sur les 3 derniers mois."
    else:
        l2 += "."
    takeaways.append(l2)

    l3_parts = []
    if r_now is not None:
        part = f"taux de crédit à {r_now:.2f} %".replace(".", ",")
        if dr_yr is not None:
            part += f" ({_pct_fr(dr_yr).replace('%', ' pt')} sur un an)"
        l3_parts.append(part)
    if bls_now is not None:
        bls_word = ("en hausse" if bls_now > 0 else ("en baisse" if bls_now < -10 else "stable"))
        l3_parts.append(f"les banques anticipent une demande de crédit {bls_word}")
    if l3_parts:
        takeaways.append(f"{_dot(pill_fin)} **Financement** — " + " ; ".join(l3_parts) + ".")

    impl_neuf = {"up": "signal favorable à 12-18 mois via le neuf (fermetures & menuiseries)",
                 "flat": "signal neuf neutre à 12-18 mois",
                 "down": "vent contraire à 12-18 mois côté neuf"}[pill_neuf]
    impl_ancien = {"up": "soutien à court terme (~2 mois) via les transactions (sécurité & domotique)",
                   "flat": "transactions neutres à court terme",
                   "down": "prudence à court terme (~2 mois) sur les produits liés aux "
                           "déménagements (sécurité & domotique)"}[pill_ancien]
    takeaways.append(f"🎯 **Demande second œuvre** — {impl_neuf} ; {impl_ancien}.")

    # ------------------------------ Fraîcheur -------------------------------------
    def _last_valid(df, col):
        valid = df.dropna(subset=[col])
        return valid["Date"].max() if not valid.empty else pd.NaT

    freshness = [
        f"SIT@DEL : {_fmt_month_year(_last_valid(roll_sit, 'Permis'))}",
        f"IGEDD : {_fmt_month_year(_last_valid(roll_va, 'Transactions'))}",
    ]
    if df_ecln_full is not None and not df_ecln_full.empty:
        e_last = df_ecln_full.dropna(subset=["Reservations"])["Date"].max()
        if pd.notna(e_last):
            freshness.append(f"ECLN : {e_last.year}-T{(e_last.month - 1) // 3 + 1}")

    # ---------------------- Bloc 1 : Activité -------------------------------------
    cards_act = [
        {"emoji": _dot(_status_yoy(m_permis.get("last3_yoy"))), "title": "Permis de construire",
         "value": _human(k_permis["current_12m"]) + " /12 m",
         "sub": _delta3m_sub(m_permis.get("last3_yoy"), exact=k_permis["current_12m"])},
        {"emoji": _dot(_status_yoy(m_mises.get("last3_yoy"))), "title": "Mises en chantier",
         "value": _human(k_mises["current_12m"]) + " /12 m",
         "sub": _delta3m_sub(m_mises.get("last3_yoy"), exact=k_mises["current_12m"])},
        {"emoji": _dot(_status_yoy(m_tx.get("last3_yoy"))), "title": "Ventes de logements anciens",
         "value": _human(k_tx["current_12m"]) + " /12 m",
         "sub": _delta3m_sub(m_tx.get("last3_yoy"), exact=k_tx["current_12m"])},
    ]
    if df_ecln_full is not None and not df_ecln_full.empty:
        se = df_ecln_full.dropna(subset=["Reservations"]).sort_values("Date")
        if len(se) >= 5:
            e_yoy = (float(se["Reservations"].iloc[-1]) / float(se["Reservations"].iloc[-5]) - 1) * 100
            cards_act.append({
                "emoji": _dot(_status_yoy(e_yoy)),
                "title": "Réservations particuliers neuf (ECLN)",
                "value": _th(float(se["Reservations"].iloc[-1])) + " /trim.",
                "sub": _pct_fr(e_yoy) + " vs même trimestre un an plus tôt"})

    # ---------------------- Bloc 2 : Financement ----------------------------------
    cards_fin = []
    r_last, r_prev = _last_prev("Credit_Logement_Taux_Interet")
    if r_last is None:
        cards_fin.append({"emoji": "⚪", "title": "Taux de crédit habitat", "value": "—", "sub": ""})
    else:
        dr = None if r_prev is None else r_last - r_prev
        r_status = "flat" if dr is None else ("down" if dr > 0.1 else ("up" if dr < -0.1 else "flat"))
        r_sub = "sur un an : " + (_pct_fr(dr).replace("%", " pt") if dr is not None else "—")
        cards_fin.append({"emoji": _dot(r_status), "title": "Taux de crédit habitat",
                          "value": f"{r_last:.2f} %".replace(".", ","), "sub": r_sub})
    bls_last, _ = _last_prev("Demande_Credit_Perspectives")
    if bls_last is None:
        cards_fin.append({"emoji": "⚪", "title": "Demande de crédit (banques)", "value": "—", "sub": ""})
    else:
        bls_status = "up" if bls_last > 0 else ("down" if bls_last < -10 else "flat")
        bls_word = ("attendue en hausse" if bls_last > 0
                    else ("attendue en baisse" if bls_last < -10 else "attendue stable"))
        cards_fin.append({"emoji": _dot(bls_status), "title": "Demande de crédit (banques)",
                          "value": f"{bls_last:+.0f}",
                          "sub": bls_word + " par les banques · enquête BLS, 3 prochains mois"})
    # Indice d'accessibilité (capacité d'emprunt ÷ prix, base 100 = 2015, prêt 25 ans).
    if "Prix_Ancien_Ensemble" in df_macro_full.columns:
        af = df_macro_full.dropna(subset=["Credit_Logement_Taux_Interet", "Prix_Ancien_Ensemble"]).copy()
        cap15 = _borrow_capacity_factor(
            df_macro_full.loc[(df_macro_full["Date"].dt.year == 2015)
                              & df_macro_full["Credit_Logement_Taux_Interet"].notna(),
                              "Credit_Logement_Taux_Interet"], 25).mean() if not af.empty else None
        if cap15 and cap15 > 0:
            af["_access"] = (_borrow_capacity_factor(af["Credit_Logement_Taux_Interet"], 25)
                             / cap15 * 100) / af["Prix_Ancien_Ensemble"] * 100
            acc_s = af.set_index("Date")["_access"].dropna()
            if not acc_s.empty:
                a_last = float(acc_s.iloc[-1])
                older = acc_s[acc_s.index <= acc_s.index[-1] - pd.DateOffset(months=12)]
                da = (a_last - float(older.iloc[-1])) if not older.empty else None
                a_status = "flat" if da is None else ("up" if da > 1 else ("down" if da < -1 else "flat"))
                gap15 = 100.0 - a_last
                if gap15 > 0.5:
                    a_txt = f"logement ≈ {gap15:.0f} % moins accessible qu'en 2015"
                elif gap15 < -0.5:
                    a_txt = f"logement ≈ {-gap15:.0f} % plus accessible qu'en 2015"
                else:
                    a_txt = "accessibilité au niveau de 2015"
                a_sub = a_txt + " · sur un an : " + (_pct_fr(da).replace("%", " pt") if da is not None else "—")
                cards_fin.append({"emoji": _dot(a_status), "title": "Indice d'accessibilité",
                                  "value": f"{a_last:.0f}", "sub": a_sub})

    # ---------------------- Bloc 3 : Perspective ----------------------------------
    tx12 = fc.build_target(df_ventes_ancien_full).dropna()
    gap = None
    last_tx = None
    if not tx12.empty:
        last_tx = float(tx12.iloc[-1])
        gap = (last_tx - BPCE_TX_ANCIEN_2026) / BPCE_TX_ANCIEN_2026 * 100.0
    if gap is None:
        persp_verdict = ""
    elif gap > 3:
        persp_verdict = "marché au-dessus de la cible BPCE 2026, infléchissement attendu"
    elif gap >= -3:
        persp_verdict = "marché aligné sur la cible BPCE 2026"
    else:
        persp_verdict = "marché sous la cible BPCE 2026"

    cards_persp = []
    if gap is None:
        cards_persp.append({"emoji": "⚪", "title": "Ventes 12 m vs cible BPCE 2026", "value": "—", "sub": ""})
    else:
        f_status = "up" if gap > 3 else ("flat" if gap > -3 else "down")
        cards_persp.append({
            "emoji": _dot(f_status), "title": "Ventes 12 m vs cible BPCE 2026",
            "value": _human(last_tx),
            "sub": _pct_fr(gap) + (" au-dessus de la cible BPCE 2026 (890 k)" if gap >= 0
                                   else " sous la cible BPCE 2026 (890 k)")})
    if ("Reno_Activite_Batiment" in df_macro_full.columns
            and df_macro_full["Reno_Activite_Batiment"].notna().any()):
        rn_last, rn_prev = _last_prev("Reno_Activite_Batiment")
        if rn_last is not None:
            rn_d = None if rn_prev is None else rn_last - rn_prev
            rn_status = "flat" if rn_d is None else ("up" if rn_d > 0 else ("down" if rn_d < 0 else "flat"))
            rn_word = ("activité en baisse" if rn_last < 0
                       else ("activité en hausse" if rn_last > 0 else "activité stable"))
            cards_persp.append({"emoji": _dot(rn_status), "title": "Activité rénovation (second œuvre)",
                                "value": f"{rn_last:+.0f}", "sub": f"solde d'opinion INSEE — {rn_word}"})
    jalons = sorted(
        [(d, it) for it in actu.items_sorted() for d, _lbl, _typ in it.get("jalons", [])
         if d > actu.MAJ], key=lambda t: t[0])
    if jalons:
        j_d, j_it = jalons[0]
        cards_persp.append({"emoji": "🗓️", "title": "Prochaine échéance aides",
                            "value": pd.Timestamp(j_d).strftime("%m/%Y"), "sub": j_it["court"]["FR"]})

    blocks = [
        {"title": "Activité", "cards": cards_act,
         "link": "→ détail : « 🏗️ Marché du neuf » · « 🏠 Marché de l'ancien »"},
        {"title": "Conditions de financement", "cards": cards_fin,
         "link": "→ détail : « 🏦 Environnement & Financement » · « 🏠 Marché de l'ancien »"},
        {"title": "Perspective" + (f" — {persp_verdict}" if persp_verdict else ""), "cards": cards_persp,
         "link": "→ détail : « 📡 Prévision & Scénarios » · « 📰 Actualités & Aides »"},
    ]

    # ---------------------- Graphique neuf vs ancien ------------------------------
    # Séries en cumul 12 mois : niveaux (en milliers) + base 100 à une date de réf.
    merged = pd.merge(
        roll_sit[["Date", "Permis_12M", "MisesEnChantier_12M"]],
        roll_va[["Date", "Transactions_12M"]],
        on="Date", how="outer").sort_values("Date")
    idx_cols = ["Permis_12M", "MisesEnChantier_12M", "Transactions_12M"]
    base_rows = merged.dropna(subset=idx_cols)
    base_2022 = base_rows[base_rows["Date"] >= pd.Timestamp("2022-01-01")]
    base_rows = base_2022 if not base_2022.empty else base_rows
    base_date = base_rows["Date"].iloc[0] if not base_rows.empty else None
    base = base_rows.iloc[0] if base_date is not None else None

    series_defs = [
        ("Permis_12M", "permis", "Permis de construire", COLOR_BRICK, None),
        ("MisesEnChantier_12M", "mises", "Mises en chantier", COLOR_TEXT, "dash"),
        ("Transactions_12M", "transactions", "Ventes anciennes", COLOR_GREEN, None),
    ]
    chart_rows = []
    for col, key, name, color, dash in series_defs:
        sub = merged[["Date", col]].dropna()
        for _, row in sub.iterrows():
            lvl = float(row[col])
            idx = (lvl / float(base[col]) * 100.0) if base is not None and float(base[col]) else None
            chart_rows.append({
                "date": row["Date"].strftime("%Y-%m-%d"),
                "series": name, "key": key,
                "level_k": round(lvl / 1000.0, 2),
                "index_100": round(idx, 2) if idx is not None else None})

    chart = {
        "base_date_label": _fmt_month_year(base_date) if base_date is not None else None,
        "series_meta": [{"key": k, "name": n, "color": c, "dash": d}
                        for _c, k, n, c, d in series_defs],
        "rows": chart_rows,
        "source": "Source : SIT@DEL (SDES) · IGEDD (CGEDD) — cumul 12 mois glissant",
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "title": "🧭 Synthèse — vue d'ensemble du marché",
        "caption": ("L'état du marché immobilier en un coup d'œil : tendance par pilier, "
                    "chiffres clés et implication pour la demande second œuvre."),
        "pillars": pillars,
        "takeaways": takeaways,
        "freshness": freshness,
        "how_to_read": ("Chaque pastille résume la tendance des 3 derniers mois vs un an plus tôt : "
                        "🟢 vent favorable · 🟠 stable · 🔴 vent contraire. Pour les taux et "
                        "l'accessibilité, 🟢 signifie des conditions qui s'améliorent (taux en "
                        "baisse), pas une valeur qui monte. Chiffres nationaux."),
        "blocks": blocks,
        "chart": chart,
    }


def _yoy_kpi(kpis, mom, label, month_label):
    """Carte KPI d'un onglet marché (miroir des st.metric d'app.py)."""
    return {
        "label": label,
        "value": _th(kpis["current_12m"]),
        "delta": _pct_fr(kpis["yoy_12m_pct"]) + " YoY",
        "subs": [
            f"Mensuel : {_th(kpis['current_val'])} ({_pct_fr(kpis['yoy_monthly_pct'])} YoY)",
            "3 derniers mois vs n-1 : " + (_pct_fr(mom.get("last3_yoy")) if mom.get("last3_yoy") is not None else "—"),
            f"Dernier mois disponible : {month_label}",
        ],
    }


def build_neuf(frames: dict) -> dict:
    df_sitadel_full = frames["sitadel"]
    df_ecln = frames["ecln"]

    # --- Série principale SIT@DEL (national, tous types) : brut + 12M + 6M -------------
    agg = ana.aggregate_sitadel(df_sitadel_full)
    roll = ana.calculate_rolling_12m(agg, ["Permis", "MisesEnChantier"])
    roll = ana.calculate_rolling(roll, ["Permis", "MisesEnChantier"], 6)
    series_meta = [
        {"key": "permis", "name": "Permis de Construire", "color": COLOR_BRICK, "dash": None,
         "raw": "Permis", "r12": "Permis_12M", "r6": "Permis_6M"},
        {"key": "mises", "name": "Mises en Chantier", "color": COLOR_TEXT, "dash": "dash",
         "raw": "MisesEnChantier", "r12": "MisesEnChantier_12M", "r6": "MisesEnChantier_6M"},
    ]
    main_rows = []
    for m in series_meta:
        sub = roll[["Date", m["raw"], m["r12"], m["r6"]]].dropna(subset=[m["raw"]])
        for _, r in sub.iterrows():
            main_rows.append({
                "date": r["Date"].strftime("%Y-%m-%d"), "series": m["name"], "key": m["key"],
                "raw": round(float(r[m["raw"]]), 3),
                "roll12": None if pd.isna(r[m["r12"]]) else round(float(r[m["r12"]]), 3),
                "roll6": None if pd.isna(r[m["r6"]]) else round(float(r[m["r6"]]), 3)})

    # --- KPIs (national plein, dernier mois) ------------------------------------------
    kpi_permis = ana.calculate_kpis(roll, "Permis")
    kpi_mises = ana.calculate_kpis(roll, "MisesEnChantier")
    mom_permis = ana.momentum_metrics(agg, "Permis")
    mom_mises = ana.momentum_metrics(agg, "MisesEnChantier")
    _sit_month = _fmt_month_year(_last_valid_date(roll, "Permis"))
    kpis = [
        _yoy_kpi(kpi_permis, mom_permis, "Permis de Construire (Cumul 12m glissant)", _sit_month),
        _yoy_kpi(kpi_mises, mom_mises, "Mises en Chantier (Cumul 12m glissant)", _sit_month),
    ]
    if df_ecln is not None and not df_ecln.empty:
        ke = df_ecln.dropna(subset=["Reservations"]).sort_values("Date")
        if not ke.empty:
            yoy = ((float(ke["Reservations"].iloc[-1]) / float(ke["Reservations"].iloc[-5]) - 1) * 100
                   if len(ke) >= 5 else None)
            kd = ke["Date"].iloc[-1]
            kpis.append({
                "label": "Réservations particuliers ECLN (trimestre)",
                "value": _th(ke["Reservations"].iloc[-1]),
                "delta": (_pct_fr(yoy) + " YoY") if yoy is not None else "",
                "subs": ["Trimestre vs même trimestre n-1",
                         f"Dernier trimestre disponible : {kd.year}-T{(kd.month - 1) // 3 + 1}"]})

    # --- Segmentation par type de logement (parité avec le sélecteur d'app.py) ---------
    # Streamlit laisse ne retenir qu'un sous-ensemble des quatre types SIT@DEL, ce qui
    # rejoue AUSSI les deux KPI de la page. Pour ne pas réimplémenter les statistiques
    # côté front (et risquer qu'elles divergent), on exporte :
    #   - `by_type` : les séries par type, en colonnaire (un tableau de valeurs aligné sur
    #     `dates`). Le front additionne les types sélectionnés, ce qui est exact : le cumul
    #     glissant d'une somme est la somme des cumuls glissants, et les quatre types
    #     commencent le même mois, donc leurs trous initiaux coïncident.
    #   - `kpis_by_type` : les KPI PRÉ-CALCULÉS pour chacun des 15 sous-ensembles non
    #     vides, produits ici par les mêmes fonctions `analysis` que le reste de l'app.
    sit_types = sorted(df_sitadel_full["Type"].unique())
    codes = {t: _TYPE_CODES.get(t, t[:2].lower()) for t in sit_types}
    date_axis = [d.strftime("%Y-%m-%d") for d in roll["Date"]]

    def _arr(col):
        return [None if pd.isna(v) else round(float(v), 3) for v in col]

    by_type_series = []
    for t in sit_types:
        agg_t = ana.aggregate_sitadel(df_sitadel_full, [t])
        roll_t = ana.calculate_rolling_12m(agg_t, ["Permis", "MisesEnChantier"])
        roll_t = ana.calculate_rolling(roll_t, ["Permis", "MisesEnChantier"], 6)
        roll_t = roll_t.set_index("Date").reindex(roll["Date"])
        for m in series_meta:
            by_type_series.append({
                "type": codes[t], "key": m["key"], "raw": _arr(roll_t[m["raw"]]),
                "roll12": _arr(roll_t[m["r12"]]), "roll6": _arr(roll_t[m["r6"]])})

    kpis_by_type = {}
    for size in range(1, len(sit_types) + 1):
        for combo in itertools.combinations(sit_types, size):
            agg_c = ana.aggregate_sitadel(df_sitadel_full, list(combo))
            roll_c = ana.calculate_rolling_12m(agg_c, ["Permis", "MisesEnChantier"])
            month_c = _fmt_month_year(_last_valid_date(roll_c, "Permis"))
            kpis_by_type["+".join(sorted(codes[t] for t in combo))] = [
                _yoy_kpi(ana.calculate_kpis(roll_c, "Permis"),
                         ana.momentum_metrics(agg_c, "Permis"),
                         "Permis de Construire (Cumul 12m glissant)", month_c),
                _yoy_kpi(ana.calculate_kpis(roll_c, "MisesEnChantier"),
                         ana.momentum_metrics(agg_c, "MisesEnChantier"),
                         "Mises en Chantier (Cumul 12m glissant)", month_c)]

    # --- Individuel vs collectif -------------------------------------------------------
    iv_groups = [
        ("Maison individuelle pure", ana.SITADEL_INDIVIDUEL_PUR, COLOR_BRICK),
        ("Individuel total (pur + groupé)", ana.SITADEL_INDIVIDUEL, COLOR_TERRACOTTA),
        ("Collectif", ana.SITADEL_COLLECTIF, COLOR_BLUE),
    ]
    iv = {}
    for metric in ("MisesEnChantier", "Permis"):
        g_kpis, g_lines = [], []
        for lbl, types, clr in iv_groups:
            g_agg = ana.aggregate_sitadel(df_sitadel_full, types)
            g_roll = ana.calculate_rolling_12m(g_agg, [metric])
            v12 = g_roll[f"{metric}_12M"].dropna()
            g_mom = ana.momentum_metrics(g_agg, metric)
            g_kpis.append({"label": lbl, "color": clr,
                           "val12": _th(v12.iloc[-1]) if not v12.empty else "—",
                           "roll12_yoy": _pct_fr(g_mom["roll12_yoy"]) if g_mom["roll12_yoy"] is not None else None,
                           "last3_yoy": _pct_fr(g_mom["last3_yoy"]) if g_mom["last3_yoy"] is not None else "—"})
            # Courbes : seulement individuel pur + collectif (comme app.py).
            if types in (ana.SITADEL_INDIVIDUEL_PUR, ana.SITADEL_COLLECTIF):
                for _, r in g_roll[["Date", f"{metric}_12M"]].dropna().iterrows():
                    g_lines.append({"date": r["Date"].strftime("%Y-%m-%d"), "series": lbl,
                                    "color": clr, "value_k": round(float(r[f"{metric}_12M"]) / 1000.0, 2)})
        iv[metric] = {"kpis": g_kpis, "lines": g_lines}

    # --- Comparaison mensuelle par année ----------------------------------------------
    monthly_rows = _rows_from(agg, {"permis": "Permis", "mises": "MisesEnChantier"})
    last_month_num = int(pd.Timestamp(agg["Date"].max()).month) if not agg.empty else 12

    # --- ECLN --------------------------------------------------------------------------
    ecln = None
    if df_ecln is not None and not df_ecln.empty:
        e = df_ecln.dropna(subset=["Reservations"]).sort_values("Date").copy()
        e["DelaiMois"] = e["DelaiEcoulement"] * 3.0
        last = e.iloc[-1]
        lastq = f"{last['Date'].year}-T{(last['Date'].month - 1) // 3 + 1}"
        eb = df_ecln.dropna(subset=["Resa_Sociaux"]).sort_values("Date")
        ecln = {
            "last_quarter": lastq,
            "kpis": [
                {"label": "Réservations particuliers (trim.)", "value": _th(last["Reservations"])},
                {"label": "Mises en vente (trim.)", "value": _th(last["MisesEnVente"])},
                {"label": "Encours à la vente", "value": _th(last["Encours"])},
                {"label": "Délai d'écoulement", "value": f"{last['DelaiMois']:.0f} mois"},
            ],
            "stock_rows": _rows_from(e, {"encours": "Encours", "mises_en_vente": "MisesEnVente"}),
            "delai_rows": _rows_from(e, {"delai_mois": "DelaiMois"}),
            "cat_rows": _rows_from(eb, {"particuliers": "Reservations", "sociaux": "Resa_Sociaux",
                                        "institutionnels": "Resa_Institutionnels"}),
            "prixm2_rows": _rows_from(e.dropna(subset=["PrixM2_Collectif"]), {"prix": "PrixM2_Collectif"}),
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "title": "🏗️ Marché du neuf — de l'autorisation à la vente",
        "caption": ("Le tunnel du logement neuf au niveau national : permis de construire et mises "
                    "en chantier (SIT@DEL), dynamique individuel vs collectif, puis commercialisation "
                    "des logements neufs (ECLN)."),
        "how_to_read": (
            "Le tunnel se lit de gauche à droite : un permis autorisé devient une mise en chantier "
            "6 à 12 mois plus tard, puis un logement commercialisé. Le cumul 12 mois glissant lisse "
            "la saisonnalité et donne le niveau annuel courant ; la vue brute montre le mois réel, "
            "beaucoup plus volatil. L'individuel pur porte nettement plus de second œuvre par "
            "logement que le collectif — sa dynamique propre est isolée plus bas. Côté ECLN, le "
            "délai d'écoulement est le meilleur signal de tension : il monte quand le stock ne part plus."),
        "kpis": kpis,
        "main_series": {"meta": [{"key": m["key"], "name": m["name"], "color": m["color"], "dash": m["dash"]}
                                 for m in series_meta],
                        "rows": main_rows, "last_month": _fmt_month_year(_last_valid_date(roll, "Permis")),
                        "source": "Source : SIT@DEL (SDES)"},
        "by_type": {"dates": date_axis,
                    "types": [{"code": codes[t], "name": t} for t in sit_types],
                    "series": by_type_series},
        "kpis_by_type": kpis_by_type,
        "indiv_collectif": iv,
        "monthly": {"rows": monthly_rows, "last_month_num": last_month_num,
                    "metrics": [{"key": "permis", "name": "Permis de Construire"},
                                {"key": "mises", "name": "Mises en Chantier"}]},
        "ecln": ecln,
    }


def build_ancien(frames: dict) -> dict:
    df_va_full = frames["ventes_ancien"]
    df_macro = frames["macro"]

    agg = ana.aggregate_ventes_ancien(df_va_full)
    roll = ana.calculate_rolling_12m(agg, ["Transactions"])
    roll = ana.calculate_rolling(roll, ["Transactions"], 6)
    kpi_tx = ana.calculate_kpis(roll, "Transactions")
    mom_tx = ana.momentum_metrics(agg, "Transactions")
    tx_month = _fmt_month_year(_last_valid_date(roll, "Transactions"))

    main_rows = []
    for _, r in roll[["Date", "Transactions", "Transactions_12M", "Transactions_6M"]].dropna(subset=["Transactions"]).iterrows():
        main_rows.append({"date": r["Date"].strftime("%Y-%m-%d"), "series": "Transactions Ancien", "key": "tx",
                          "raw": round(float(r["Transactions"]), 3),
                          "roll12": None if pd.isna(r["Transactions_12M"]) else round(float(r["Transactions_12M"]), 3),
                          "roll6": None if pd.isna(r["Transactions_6M"]) else round(float(r["Transactions_6M"]), 3)})

    monthly_rows = _rows_from(agg, {"tx": "Transactions"})
    last_month_num = int(pd.Timestamp(agg["Date"].max()).month) if not agg.empty else 12

    # --- Prix & accessibilité ----------------------------------------------------------
    prix = {"available": False}
    if "Prix_Ancien_Ensemble" in df_macro.columns and not df_macro["Prix_Ancien_Ensemble"].dropna().empty:
        labels = {"Prix_Ancien_Ensemble": "Ensemble", "Prix_Ancien_Appartements": "Appartements",
                  "Prix_Ancien_Maisons": "Maisons"}
        colors = {"Prix_Ancien_Ensemble": COLOR_BRICK, "Prix_Ancien_Appartements": COLOR_BLUE,
                  "Prix_Ancien_Maisons": COLOR_GREEN}
        cols = [c for c in labels if c in df_macro.columns]

        def _long(colmap, yoy=False):
            """Séries en format long, un dropna PAR série puis pct_change(4)=1 an si yoy."""
            rows = []
            for key, (col, name) in colmap.items():
                s = df_macro.dropna(subset=[col]).sort_values("Date")
                vals = (s[col].pct_change(4) * 100) if yoy else s[col]
                for d, v in zip(s["Date"], vals):
                    if pd.notna(v):
                        rows.append({"date": pd.Timestamp(d).strftime("%Y-%m-%d"),
                                     "series": name, "key": key, "value": round(float(v), 3)})
            return rows

        p_kpis = []
        for c in cols:
            s = df_macro.dropna(subset=[c])
            if len(s) >= 5:
                last, prev = float(s[c].iloc[-1]), float(s[c].iloc[-5])
                p_kpis.append({"label": labels[c], "color": colors[c],
                               "value": f"{last:.1f}".replace(".", ","),
                               "yoy": _pct_fr((last / prev - 1) * 100)})
        last_date = df_macro.dropna(subset=["Prix_Ancien_Ensemble"])["Date"].iloc[-1]
        _pmap = {labels[c].lower(): (c, labels[c]) for c in cols}
        levels = _long(_pmap)
        yoy = _long(_pmap, yoy=True)

        # Capacité d'emprunt & accessibilité, pour 25 et 20 ans (base 100 = 2015).
        cap = {}
        full = df_macro.dropna(subset=["Credit_Logement_Taux_Interet"]).copy()
        acc_base = df_macro.dropna(subset=["Credit_Logement_Taux_Interet", "Prix_Ancien_Ensemble"]).copy()
        for term in (25, 20):
            cap15 = _borrow_capacity_factor(
                full.loc[full["Date"].dt.year == 2015, "Credit_Logement_Taux_Interet"], term).mean()
            if not (cap15 and cap15 > 0):
                cap15 = _borrow_capacity_factor(full["Credit_Logement_Taux_Interet"].iloc[:1], term)[0]
            a = acc_base.copy()
            a["_capidx"] = _borrow_capacity_factor(a["Credit_Logement_Taux_Interet"], term) / cap15 * 100
            a["_access"] = a["_capidx"] / a["Prix_Ancien_Ensemble"] * 100
            cap[str(term)] = _rows_from(a, {"capidx": "_capidx", "prix": "Prix_Ancien_Ensemble", "access": "_access"})

        new_vs_old = {"available": False}
        if "Prix_Neuf" in df_macro.columns and df_macro["Prix_Neuf"].notna().any():
            _nmap = {"neuf": ("Prix_Neuf", "Neuf"), "ancien": ("Prix_Ancien_Ensemble", "Ancien")}
            new_vs_old = {"available": True, "levels": _long(_nmap), "yoy": _long(_nmap, yoy=True),
                          "series_meta": [{"key": "neuf", "name": "Neuf", "color": COLOR_BLUE},
                                          {"key": "ancien", "name": "Ancien", "color": COLOR_BRICK}]}

        prix = {"available": True, "kpis": p_kpis,
                "last_date": pd.Timestamp(last_date).strftime("%Y-%m"),
                "price_levels": levels, "price_yoy": yoy, "capacity": cap, "new_vs_old": new_vs_old,
                "series_meta": [{"key": labels[c].lower(), "name": labels[c], "color": colors[c]} for c in cols]}

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "title": "🏠 Marché de l'ancien — transactions, prix & accessibilité",
        "caption": ("Le marché des logements anciens au niveau national : volumes de transactions "
                    "(IGEDD), puis prix Notaires-INSEE et lecture de l'accessibilité."),
        "how_to_read": (
            "Le cumul 12 mois glissant reproduit la série publiée par l'IGEDD (« ventes sur un an ») ; "
            "les flux mensuels en sont la reconstruction, utile pour la dynamique récente mais plus "
            "bruitée. Côté accessibilité, la capacité d'emprunt est calculée à mensualité constante : "
            "elle chute donc quand les taux montent, indépendamment des prix. L'indice d'accessibilité "
            "rapporte cette capacité aux prix — sous 100, un ménage type achète moins de surface qu'en 2015."),
        "kpi": _yoy_kpi(kpi_tx, mom_tx, "Ventes anciennes IGEDD (Cumul 12m glissant)", tx_month),
        "main_series": {"meta": [{"key": "tx", "name": "Transactions Ancien", "color": COLOR_GREEN, "dash": None}],
                        "rows": main_rows, "last_month": tx_month, "source": "Source : IGEDD"},
        "monthly": {"rows": monthly_rows, "last_month_num": last_month_num},
        "prix": prix,
    }


def build_macro(frames: dict) -> dict:
    m = frames["macro"]

    def series(col):
        s = m.dropna(subset=[col]).sort_values("Date")
        return [{"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 4)}
                for d, v in zip(s["Date"], s[col])]

    # Taux : format long des 3 séries togglables.
    rate_defs = [("Credit_Logement_Taux_Interet", "Taux Crédit Habitat", COLOR_TEXT),
                 ("Euribor_3M", "Euribor 3 mois", COLOR_BLUE),
                 ("OAT_10ans", "OAT 10 ans", COLOR_GREEN)]
    rate_rows, rate_meta = [], []
    for col, name, color in rate_defs:
        if col in m.columns and m[col].notna().any():
            rate_meta.append({"name": name, "color": color})
            for r in series(col):
                rate_rows.append({"date": r["date"], "series": name, "value": r["value"]})

    # Intentions d'achat : centrées-réduites (z-score).
    intentions = []
    if "Intentions_Achat_Logement" in m.columns:
        s = m.dropna(subset=["Intentions_Achat_Logement"])
        mu, sd = s["Intentions_Achat_Logement"].mean(), s["Intentions_Achat_Logement"].std()
        if pd.notna(sd) and sd > 0:
            intentions = [{"date": d.strftime("%Y-%m-%d"), "value": round(float((v - mu) / sd), 4)}
                          for d, v in zip(s["Date"], s["Intentions_Achat_Logement"])]

    # Volume de crédits (mensuel stacked + cumul 12m), conditionnel.
    credit = None
    if "Production_Credits_Habitat" in m.columns and m["Production_Credits_Habitat"].notna().any():
        cr = m.dropna(subset=["Production_Credits_Habitat"]).sort_values("Date").copy()
        cr["_cum12"] = cr["Production_Credits_Habitat"].rolling(12).sum()
        has_split = bool("Production_Credits_Pure" in m.columns and m["Production_Credits_Pure"].notna().any())
        monthly, cum = [], []
        if has_split:
            cr["_pure_cum12"] = cr["Production_Credits_Pure"].rolling(12).sum()
            sp = m.dropna(subset=["Production_Credits_Pure"]).sort_values("Date")
            monthly = _rows_from(sp, {"pure": "Production_Credits_Pure", "renego": "Production_Credits_Renego"})
        cum = _rows_from(cr.dropna(subset=["_cum12"]),
                         {"total": "_cum12", **({"pure": "_pure_cum12"} if has_split else {})})
        credit = {"has_split": has_split, "monthly": monthly, "cum": cum}

    # Demande de crédits (BLS), conditionnel.
    bls = None
    if "Demande_Credit_Perspectives" in m.columns and m["Demande_Credit_Perspectives"].notna().any():
        rows = []
        for col, name in (("Demande_Credit_Realisee", "Réalisé (3 derniers mois)"),
                          ("Demande_Credit_Perspectives", "Perspectives (3 prochains mois)")):
            if col in m.columns:
                for r in series(col):
                    rows.append({"date": r["date"], "series": name, "value": r["value"]})
        bls = {"rows": rows,
               "meta": [{"name": "Réalisé (3 derniers mois)", "color": "#9AA5B1"},
                        {"name": "Perspectives (3 prochains mois)", "color": COLOR_BRICK, "dash": None}]}

    # Rénovation, conditionnel.
    reno_defs = [("Reno_Activite_Batiment", "Activité passée — second œuvre", COLOR_BRICK),
                 ("Reno_Activite_Prevue", "Activité prévue — second œuvre", COLOR_GREEN)]
    reno = [{"title": name, "color": color, "rows": series(col)}
            for col, name, color in reno_defs if col in m.columns and m[col].notna().any()]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "title": "🏦 Contexte Macroéconomique et Financement",
        "caption": ("Indicateurs de contexte macroéconomique et de conditions de financement : confiance "
                    "des ménages (INSEE), taux du crédit habitat (BdF/BCE), Euribor 3 mois et OAT 10 ans "
                    "(BCE), intentions d'achat de logement et taux de chômage BIT (INSEE)."),
        "how_to_read": (
            "Ces indicateurs expliquent le marché plus qu'ils ne le décrivent, et la plupart le "
            "précèdent. Les soldes d'opinion (confiance, intentions, rénovation, BLS) se lisent en "
            "écart à leur repère — le zéro ou la moyenne de longue période — pas en niveau absolu. "
            "La demande de crédits (BLS) est l'indicateur le plus avancé de la page : les banques la "
            "constatent avant que les transactions ne bougent. Sur les volumes, les renégociations "
            "sont isolées car elles ne déclenchent ni transaction ni chantier."),
        "confidence": series("Insee_Confiance_Menages"),
        "rates": {"rows": rate_rows, "meta": rate_meta},
        "intentions": intentions,
        "chomage": series("Taux_Chomage_BIT"),
        "credit": credit,
        "bls": bls,
        "renovation": reno,
    }


def build_actualites(frames: dict) -> dict:
    items_all = actu.items_sorted()
    L = "FR"

    def item_dict(it):
        echs = [(d, lbl) for d, lbl, typ in it.get("jalons", []) if typ == "echeance"]
        return {
            "id": it["id"], "categorie": it["categorie"], "statut": it["statut"],
            "court": it["court"][L], "titre": it["titre"][L], "resume": it["resume"][L],
            "montant": it["montant"][L] if it.get("montant") else None,
            "horizon": it["horizon"][L], "impacts": it["impacts"],
            "impact_detail": it["impact_detail"][L],
            "echeance": ({"date": pd.Timestamp(echs[0][0]).strftime("%d/%m/%Y"),
                          "label": echs[0][1][L]} if echs else None),
            "jalons": [{"date": pd.Timestamp(d).strftime("%Y-%m-%d"), "label": lbl[L], "type": typ}
                       for d, lbl, typ in it.get("jalons", [])],
            "sources": [{"label": lbl, "url": url} for lbl, url in it["sources"]],
        }

    items = [item_dict(it) for it in items_all]
    n_vigueur = sum(1 for it in items_all if it["statut"] == "vigueur")
    next_jalons = sorted([(d, it) for it in items_all
                          for d, _lbl, _typ in it.get("jalons", []) if d > actu.MAJ], key=lambda t: t[0])
    kpis = [
        {"label": "Dispositifs suivis", "value": str(len(items_all))},
        {"label": "En vigueur", "value": str(n_vigueur)},
        {"label": "Budget MaPrimeRénov' 2026", "value": "3,6 Md€"},
    ]
    if next_jalons:
        nd, nit = next_jalons[0]
        kpis.append({"label": "Prochaine échéance", "value": pd.Timestamp(nd).strftime("%m/%Y"),
                     "subs": [nit["court"]["FR"]]})

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "title": "📰 Actualités — aides & plans de relance logement",
        "caption": ("Veille sur les grands dispositifs publics français et européens qui soutiennent (ou "
                    "freinent) le marché du logement, avec pour chaque mesure : statut, jalons, montants et "
                    "impact potentiel sur les trois piliers du modèle (neuf, ancien, rénovation)."),
        "how_to_read": (
            "Cette page est une grille de lecture qualitative, pas une sortie de modèle. Chaque mesure "
            "est notée de ⬇⬇ à ⬆⬆ sur les trois piliers selon le sens et l'intensité de son effet "
            "attendu : c'est une appréciation d'auteur, révisable, pas un résultat calculé. Le statut "
            "distingue ce qui est en vigueur de ce qui est seulement adopté ou en discussion — seules "
            "les mesures en vigueur agissent déjà sur les séries des autres onglets."),
        "maj": actu.MAJ,
        "kpis": kpis,
        "items": items,
        "impact_labels": actu.IMPACT_LABELS[L],
        "pilier_labels": actu.PILIERS[L],
        "statut_labels": actu.STATUTS[L],
        "category_labels": actu.CATEGORIES[L],
        "jalon_types": {k: {"label": v[L], "symbol": v["symbol"]} for k, v in actu.JALON_TYPES.items()},
    }


def _last_valid_date(df, col, date_col="Date"):
    valid = df.dropna(subset=[col])
    return valid[date_col].max() if not valid.empty else pd.NaT


_BUILDERS = {"synthese": build_synthese, "neuf": build_neuf, "ancien": build_ancien,
             "macro": build_macro, "actualites": build_actualites}


def _payload_without_timestamp(payload):
    """Le payload privé de son horodatage — la partie qui décide s'il a vraiment changé."""
    return {k: v for k, v in payload.items() if k != "generated_at"}


def _write_if_changed(path, payload):
    """Écrit le JSON uniquement si son contenu a réellement changé, `generated_at` exclu
    de la comparaison.

    `generated_at` étant l'horloge murale, une écriture inconditionnelle produirait un
    diff sur les 5 fichiers à CHAQUE passage, y compris quand aucune donnée n'a bougé —
    le refresh hebdomadaire committerait donc du bruit toutes les semaines. Même
    garde-fou que _write_if_changed dans fetch_new_sources.py, avec la même conséquence
    utile : « Généré le » affiché par le front date de la dernière évolution réelle des
    données, pas de la dernière exécution du script. Renvoie True si le fichier a été
    (ré)écrit."""
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                old = json.load(f)
        except (OSError, json.JSONDecodeError):
            old = None                      # illisible / tronqué -> on réécrit
        if old is not None:
            # Comparer le payload APRÈS un aller-retour JSON : la sérialisation convertit
            # les clés non-str en str (impact_labels est indexé par des int), si bien que
            # l'objet Python et sa relecture ne sont jamais égaux tels quels — sans cela
            # actualites.json serait réécrit à chaque passage.
            if _payload_without_timestamp(old) == _payload_without_timestamp(json.loads(text)):
                return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return True


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    frames = load_frames()
    changed = []
    for name, builder in _BUILDERS.items():
        path = os.path.join(DATA_DIR, f"{name}.json")
        if _write_if_changed(path, builder(frames)):
            changed.append(name)
            print(f"[web_export] écrit {name}.json")
        else:
            print(f"[web_export] {name}.json inchangé")
    print(f"[web_export] {len(changed)}/{len(_BUILDERS)} fichier(s) modifié(s)"
          + (f" ({', '.join(changed)})" if changed else " — rien de neuf."))


if __name__ == "__main__":
    main()
