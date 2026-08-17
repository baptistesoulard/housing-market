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

OUT_PATH = os.path.join(_REPO_ROOT, "web", "observable", "src", "data", "synthese.json")


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


# ============================ construction du payload =============================
def build_payload() -> dict:
    dm = DataManager()
    dm.load_or_generate_all()
    (df_sitadel, df_ventes_ancien, df_macro, df_sales,
     df_revenue, df_ecln, df_company_sales) = dm.read_frames()

    df_sitadel_full = df_sitadel
    df_ventes_ancien_full = df_ventes_ancien
    df_macro_full = df_macro
    df_ecln_full = df_ecln

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


def main():
    payload = build_payload()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[web_export] écrit {OUT_PATH} "
          f"({len(payload['chart']['rows'])} points de graphique, "
          f"{sum(len(b['cards']) for b in payload['blocks'])} cartes)")


if __name__ == "__main__":
    main()
