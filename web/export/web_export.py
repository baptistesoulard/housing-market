"""Adaptateur d'export web (Étape 0 du PoC de migration hors Streamlit).

Réutilise TELLE QUELLE la couche back-office Python pour tout ce qui est logique
métier partagée avec `app.py` (`analysis.momentum_metrics` / `calculate_kpis`,
`actualites`) — c'est le contrat de la migration : on ne réécrit que la couche
d'affichage. Mais les AGRÉGATIONS (group by mensuel, cumuls glissants, YoY, z-score,
capacité d'emprunt) ne sont plus recalculées à la main en pandas : elles sont déléguées
à DuckDB via `web/export/queries.py`, qui interroge directement les Parquet de
l'entrepôt `housing_data/` (déjà alimenté par `DataManager.load_or_generate_all()`).
Ce script recompute le contenu des onglets Synthèse / Neuf / Ancien / Macro / Actualités
et le sérialise en JSON statique que le front Observable Framework lit au build.

Usage :
    python web/export/web_export.py            # écrit web/observable/src/data/*.json

Aucune dépendance nouvelle : pandas / numpy / duckdb suffisent (déjà dans
requirements.txt, la couche `housing_data` existait déjà pour l'app Streamlit).
À brancher en fin du refresh hebdo (GitHub Actions) pour que Cloudflare Pages
reconstruise le site à chaque publication de données.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd

# --- Rendre les modules du dépôt importables quel que soit le CWD -----------------
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
_EXPORT_DIR = os.path.dirname(__file__)
if _EXPORT_DIR not in sys.path:
    sys.path.insert(0, _EXPORT_DIR)

import analysis as ana                         # noqa: E402
import actualites as actu                      # noqa: E402
import queries as q                            # noqa: E402
import theme                                   # noqa: E402

# Cible BPCE 2026 (miroir des constantes d'app.py, bloc Perspective).
BPCE_TX_ANCIEN_2026 = 890_000

_FR_MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin",
              "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

DATA_DIR = os.path.join(_REPO_ROOT, "web", "observable", "src", "data")
OUT_PATH = os.path.join(DATA_DIR, "synthese.json")

# Rampe catégorielle des graphiques (source unique : web/theme.json — voir theme.py).
# Ce sont les COULEURS DE DONNÉES, distinctes des accents d'interface de la charte :
# l'anthracite #2D3748 y était utilisé comme couleur de courbe alors que c'est un jeton
# de texte (il se lit comme un gris), et le bleu ciel / jaune tournesol de la charte
# passent sous 3:1 de contraste sur blanc. Chaque slot garde la teinte, calée sur un
# niveau qui passe les contrôles d'accessibilité.
COLOR_BRICK = theme.S_BRICK        # slot 1 — permis, prix ensemble, particuliers…
COLOR_BLUE = theme.S_BLUE          # slot 2 — collectif, euribor, appartements…
COLOR_GREEN = theme.S_GREEN        # slot 3 — ventes anciennes, OAT, maisons…
COLOR_VIOLET = theme.S_VIOLET      # slot 4 — mises en chantier, taux crédit, encours
COLOR_GOLD = theme.S_GOLD          # slot 5 — individuel total, institutionnels, renégo.


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


def _rows_from(df, mapping, date_col="Date"):
    """Sérialise un DataFrame déjà agrégé en liste de dicts {date, **mapping}, NaN
    ignorées (mapping = {json_key: df_col}). Pure mise en forme — l'agrégation en amont
    (group by, rolling) est faite par DuckDB via `queries.py`, pas ici."""
    out = []
    for _, r in df.sort_values(date_col).iterrows():
        row = {"date": pd.Timestamp(r[date_col]).strftime("%Y-%m-%d")}
        for k, col in mapping.items():
            v = r.get(col)
            row[k] = None if (v is None or pd.isna(v)) else float(v)
        out.append(row)
    return out


def _last_prev(con, col, months=12):
    """Dernière valeur d'un indicateur macro + sa valeur d'au moins `months` mois plus
    tôt — lookup fait par DuckDB (`queries.macro_last_and_year_ago`), pas par un
    `set_index("Date")` + recherche pandas."""
    return q.macro_last_and_year_ago(con, col, months)


# ============================ construction du payload =============================
def build_synthese(con) -> dict:
    macro_cols = q.macro_data_columns(con)

    # --- Momentum & niveaux 12 m (indépendants de tout filtre, comme dans app.py) ---
    # `sit`/`va` portent à la fois la série brute ET son cumul 12M : un seul aller-retour
    # SQL (group by + fenêtre) remplace `aggregate_* -> calculate_rolling_12m`.
    sit = q.monthly(con, "sitadel", ["Permis", "MisesEnChantier"], windows=(12,))
    va = q.monthly(con, "ventes_ancien", ["Transactions"], windows=(12,))
    m_permis = ana.momentum_metrics(sit, "Permis")
    m_mises = ana.momentum_metrics(sit, "MisesEnChantier")
    m_tx = ana.momentum_metrics(va, "Transactions")
    k_permis = ana.calculate_kpis(sit, "Permis")
    k_mises = ana.calculate_kpis(sit, "MisesEnChantier")
    k_tx = ana.calculate_kpis(va, "Transactions")

    # ---------------------------- Pastilles par pilier ----------------------------
    neuf_l3 = [v for v in (m_permis.get("last3_yoy"), m_mises.get("last3_yoy")) if v is not None]
    pill_neuf = _status_yoy(sum(neuf_l3) / len(neuf_l3)) if neuf_l3 else "flat"
    pill_ancien = _status_yoy(m_tx.get("last3_yoy"))
    r_now, r_yr = _last_prev(con, "Credit_Logement_Taux_Interet")
    dr_yr = None if (r_now is None or r_yr is None) else r_now - r_yr
    pill_fin = ("flat" if dr_yr is None
                else ("down" if dr_yr > 0.1 else ("up" if dr_yr < -0.1 else "flat")))
    bls_now, _ = _last_prev(con, "Demande_Credit_Perspectives")

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
    ip = q.monthly(con, "sitadel", ["MisesEnChantier"], windows=(12,), types=ana.SITADEL_INDIVIDUEL_PUR)
    mom_ip = ana.momentum_metrics(ip, "MisesEnChantier")
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
        f"SIT@DEL : {_fmt_month_year(_last_valid(sit, 'Permis'))}",
        f"IGEDD : {_fmt_month_year(_last_valid(va, 'Transactions'))}",
    ]
    ecln_last = q.scalar(con, "SELECT max(Date) FROM ecln WHERE Reservations IS NOT NULL")
    if ecln_last is not None:
        e_last = pd.Timestamp(ecln_last)
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
    e_yoy_row = q.scalar(con, """
        WITH e AS (SELECT Date, Reservations FROM ecln WHERE Reservations IS NOT NULL ORDER BY Date)
        SELECT (last.v / prev.v - 1) * 100
        FROM (SELECT Reservations AS v FROM e ORDER BY Date DESC LIMIT 1) last,
             (SELECT Reservations AS v FROM e ORDER BY Date DESC LIMIT 1 OFFSET 4) prev
    """)
    if e_yoy_row is not None:
        e_last_val = q.scalar(con, "SELECT Reservations FROM ecln WHERE Reservations IS NOT NULL ORDER BY Date DESC LIMIT 1")
        cards_act.append({
            "emoji": _dot(_status_yoy(e_yoy_row)),
            "title": "Réservations particuliers neuf (ECLN)",
            "value": _th(e_last_val) + " /trim.",
            "sub": _pct_fr(e_yoy_row) + " vs même trimestre un an plus tôt"})

    # ---------------------- Bloc 2 : Financement ----------------------------------
    cards_fin = []
    r_last, r_prev = _last_prev(con, "Credit_Logement_Taux_Interet")
    if r_last is None:
        cards_fin.append({"emoji": "⚪", "title": "Taux de crédit habitat", "value": "—", "sub": ""})
    else:
        dr = None if r_prev is None else r_last - r_prev
        r_status = "flat" if dr is None else ("down" if dr > 0.1 else ("up" if dr < -0.1 else "flat"))
        r_sub = "sur un an : " + (_pct_fr(dr).replace("%", " pt") if dr is not None else "—")
        cards_fin.append({"emoji": _dot(r_status), "title": "Taux de crédit habitat",
                          "value": f"{r_last:.2f} %".replace(".", ","), "sub": r_sub})
    bls_last, _ = _last_prev(con, "Demande_Credit_Perspectives")
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
    if "Prix_Ancien_Ensemble" in macro_cols:
        capdf = q.capacity_accessibility(con, 25)
        acc_s = capdf.set_index("Date")["access"].dropna() if not capdf.empty else pd.Series(dtype=float)
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
    # Cumul 12m des ventes anciennes déjà calculé par SQL dans `va` (Transactions_12M) :
    # pas de second calcul via `forecast.build_target` (même agrégation, en double avant).
    tx12 = va.set_index("Date")["Transactions_12M"].dropna()
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
    if "Reno_Activite_Batiment" in macro_cols:
        rn_last, rn_prev = _last_prev(con, "Reno_Activite_Batiment")
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
        sit[["Date", "Permis_12M", "MisesEnChantier_12M"]],
        va[["Date", "Transactions_12M"]],
        on="Date", how="outer").sort_values("Date")
    idx_cols = ["Permis_12M", "MisesEnChantier_12M", "Transactions_12M"]
    base_rows = merged.dropna(subset=idx_cols)
    base_2022 = base_rows[base_rows["Date"] >= pd.Timestamp("2022-01-01")]
    base_rows = base_2022 if not base_2022.empty else base_rows
    base_date = base_rows["Date"].iloc[0] if not base_rows.empty else None
    base = base_rows.iloc[0] if base_date is not None else None

    series_defs = [
        ("Permis_12M", "permis", "Permis de construire", COLOR_BRICK, None),
        ("MisesEnChantier_12M", "mises", "Mises en chantier", COLOR_VIOLET, "dash"),
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


def build_neuf(con) -> dict:
    # --- Série principale SIT@DEL (national, tous types) : brut + 12M + 6M en 1 requête --
    roll = q.monthly(con, "sitadel", ["Permis", "MisesEnChantier"], windows=(12, 6))
    series_meta = [
        {"key": "permis", "name": "Permis de Construire", "color": COLOR_BRICK, "dash": None,
         "raw": "Permis", "r12": "Permis_12M", "r6": "Permis_6M"},
        {"key": "mises", "name": "Mises en Chantier", "color": COLOR_VIOLET, "dash": "dash",
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
    mom_permis = ana.momentum_metrics(roll, "Permis")
    mom_mises = ana.momentum_metrics(roll, "MisesEnChantier")
    _sit_month = _fmt_month_year(_last_valid_date(roll, "Permis"))
    kpis = [
        _yoy_kpi(kpi_permis, mom_permis, "Permis de Construire (Cumul 12m glissant)", _sit_month),
        _yoy_kpi(kpi_mises, mom_mises, "Mises en Chantier (Cumul 12m glissant)", _sit_month),
    ]
    ecln_yoy = q.scalar(con, """
        WITH e AS (SELECT Date, Reservations FROM ecln WHERE Reservations IS NOT NULL ORDER BY Date)
        SELECT (last.v / prev.v - 1) * 100
        FROM (SELECT Reservations AS v FROM e ORDER BY Date DESC LIMIT 1) last,
             (SELECT Reservations AS v FROM e ORDER BY Date DESC LIMIT 1 OFFSET 4) prev
    """)
    ecln_last_row = q.scalar(con, "SELECT max(Date) FROM ecln WHERE Reservations IS NOT NULL")
    if ecln_last_row is not None:
        e_last_val, e_last_date = q.rows(con, """
            SELECT Reservations AS v, Date AS d FROM ecln
            WHERE Reservations IS NOT NULL ORDER BY Date DESC LIMIT 1
        """)[0].values()
        kpis.append({
            "label": "Réservations particuliers ECLN (trimestre)",
            "value": _th(e_last_val),
            "delta": (_pct_fr(ecln_yoy) + " YoY") if ecln_yoy is not None else "",
            "subs": ["Trimestre vs même trimestre n-1",
                     f"Dernier trimestre disponible : {e_last_date.year}-T{(e_last_date.month - 1) // 3 + 1}"]})

    # --- Individuel vs collectif : 1 requête SQL par métrique (au lieu de 3 passes
    # aggregate+rolling par métrique, une par groupe) -----------------------------------
    iv_groups = [
        ("Maison individuelle pure", ana.SITADEL_INDIVIDUEL_PUR, COLOR_BRICK),
        ("Individuel total (pur + groupé)", ana.SITADEL_INDIVIDUEL, COLOR_GOLD),
        ("Collectif", ana.SITADEL_COLLECTIF, COLOR_BLUE),
    ]
    group_types = {lbl: types for lbl, types, _clr in iv_groups}
    iv = {}
    for metric in ("MisesEnChantier", "Permis"):
        gdf = q.monthly_by_group(con, "sitadel", group_types, [metric], windows=(12,))
        g_kpis, g_lines = [], []
        for lbl, types, clr in iv_groups:
            g_roll = gdf[gdf["Groupe"] == lbl]
            v12 = g_roll[f"{metric}_12M"].dropna()
            g_mom = ana.momentum_metrics(g_roll, metric)
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
    monthly_rows = _rows_from(roll, {"permis": "Permis", "mises": "MisesEnChantier"})
    last_month_num = int(pd.Timestamp(roll["Date"].max()).month) if not roll.empty else 12

    # --- ECLN (source : vue DuckDB/Parquet, pas le CSV) --------------------------------
    ecln = None
    df_ecln = q.frame(con, "SELECT * FROM ecln ORDER BY Date")
    if not df_ecln.empty:
        e = df_ecln.dropna(subset=["Reservations"]).sort_values("Date").copy()
        if not e.empty:
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
        "kpis": kpis,
        "main_series": {"meta": [{"key": m["key"], "name": m["name"], "color": m["color"], "dash": m["dash"]}
                                 for m in series_meta],
                        "rows": main_rows, "last_month": _fmt_month_year(_last_valid_date(roll, "Permis")),
                        "source": "Source : SIT@DEL (SDES)"},
        "indiv_collectif": iv,
        "monthly": {"rows": monthly_rows, "last_month_num": last_month_num,
                    "metrics": [{"key": "permis", "name": "Permis de Construire"},
                                {"key": "mises", "name": "Mises en Chantier"}]},
        "ecln": ecln,
    }


def build_ancien(con) -> dict:
    roll = q.monthly(con, "ventes_ancien", ["Transactions"], windows=(12, 6))
    kpi_tx = ana.calculate_kpis(roll, "Transactions")
    mom_tx = ana.momentum_metrics(roll, "Transactions")
    tx_month = _fmt_month_year(_last_valid_date(roll, "Transactions"))

    main_rows = []
    for _, r in roll[["Date", "Transactions", "Transactions_12M", "Transactions_6M"]].dropna(subset=["Transactions"]).iterrows():
        main_rows.append({"date": r["Date"].strftime("%Y-%m-%d"), "series": "Transactions Ancien", "key": "tx",
                          "raw": round(float(r["Transactions"]), 3),
                          "roll12": None if pd.isna(r["Transactions_12M"]) else round(float(r["Transactions_12M"]), 3),
                          "roll6": None if pd.isna(r["Transactions_6M"]) else round(float(r["Transactions_6M"]), 3)})

    monthly_rows = _rows_from(roll, {"tx": "Transactions"})
    last_month_num = int(pd.Timestamp(roll["Date"].max()).month) if not roll.empty else 12

    # --- Prix & accessibilité (agrégations : LAG SQL pour le YoY, AVG SQL pour la base
    # 2015 de capacité d'emprunt — plus de pct_change()/numpy vectorisé) ----------------
    macro_cols = q.macro_data_columns(con)
    prix = {"available": False}
    if "Prix_Ancien_Ensemble" in macro_cols:
        labels = {"Prix_Ancien_Ensemble": "Ensemble", "Prix_Ancien_Appartements": "Appartements",
                  "Prix_Ancien_Maisons": "Maisons"}
        colors = {"Prix_Ancien_Ensemble": COLOR_BRICK, "Prix_Ancien_Appartements": COLOR_BLUE,
                  "Prix_Ancien_Maisons": COLOR_GREEN}
        cols = [c for c in labels if c in macro_cols]

        def _long(colmap, yoy=False):
            rows_ = []
            for key, (col, name) in colmap.items():
                pts = (q.series_with_lag_pct(con, col, lag=4) if yoy else q.macro_series(con, col, digits=3))
                for p in pts:
                    rows_.append({"date": p["date"], "series": name, "key": key, "value": p["value"]})
            return rows_

        p_kpis = []
        for c in cols:
            s = q.rows(con, f'SELECT "{c}" AS v FROM "macro" WHERE "{c}" IS NOT NULL ORDER BY Date')
            if len(s) >= 5:
                last, prev = float(s[-1]["v"]), float(s[-5]["v"])
                p_kpis.append({"label": labels[c], "color": colors[c],
                               "value": f"{last:.1f}".replace(".", ","),
                               "yoy": _pct_fr((last / prev - 1) * 100)})
        last_date = q.scalar(con, 'SELECT max(Date) FROM "macro" WHERE "Prix_Ancien_Ensemble" IS NOT NULL')
        _pmap = {labels[c].lower(): (c, labels[c]) for c in cols}
        levels = _long(_pmap)
        yoy = _long(_pmap, yoy=True)

        # Capacité d'emprunt & accessibilité, pour 25 et 20 ans (base 100 = 2015).
        cap = {}
        for term in (25, 20):
            capdf = q.capacity_accessibility(con, term)
            cap[str(term)] = _rows_from(capdf, {"capidx": "capidx", "prix": "prix", "access": "access"})

        new_vs_old = {"available": False}
        if "Prix_Neuf" in macro_cols:
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
        "kpi": _yoy_kpi(kpi_tx, mom_tx, "Ventes anciennes IGEDD (Cumul 12m glissant)", tx_month),
        "main_series": {"meta": [{"key": "tx", "name": "Transactions Ancien", "color": COLOR_GREEN, "dash": None}],
                        "rows": main_rows, "last_month": tx_month, "source": "Source : IGEDD"},
        "monthly": {"rows": monthly_rows, "last_month_num": last_month_num},
        "prix": prix,
    }


def build_macro(con) -> dict:
    macro_cols = q.macro_data_columns(con)

    # Taux : format long des 3 séries togglables.
    rate_defs = [("Credit_Logement_Taux_Interet", "Taux Crédit Habitat", COLOR_VIOLET),
                 ("Euribor_3M", "Euribor 3 mois", COLOR_BLUE),
                 ("OAT_10ans", "OAT 10 ans", COLOR_GREEN)]
    rate_rows, rate_meta = [], []
    for col, name, color in rate_defs:
        if col in macro_cols:
            rate_meta.append({"name": name, "color": color})
            for r in q.macro_series(con, col, digits=4):
                rate_rows.append({"date": r["date"], "series": name, "value": r["value"]})

    # Intentions d'achat : centrées-réduites (z-score AVG/STDDEV_SAMP calculés par DuckDB).
    intentions = q.macro_zscore(con, "Intentions_Achat_Logement") if "Intentions_Achat_Logement" in macro_cols else []

    # Volume de crédits (mensuel stacked + cumul 12m), conditionnel. Cas particulier
    # conservé en pandas : le cumul 12m « Pure » du code d'origine est calculé sur les
    # dates où *Habitat* (pas Pure) est renseigné — un couplage spécifique qu'il vaut
    # mieux garder explicite plutôt que de le généraliser dans `queries.py`.
    credit = None
    if "Production_Credits_Habitat" in macro_cols:
        m = q.frame(con, 'SELECT Date, "Production_Credits_Habitat", "Production_Credits_Pure", '
                          '"Production_Credits_Renego" FROM "macro" ORDER BY Date')
        cr = m.dropna(subset=["Production_Credits_Habitat"]).sort_values("Date").copy()
        cr["_cum12"] = cr["Production_Credits_Habitat"].rolling(12).sum()
        has_split = "Production_Credits_Pure" in macro_cols
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
    if "Demande_Credit_Perspectives" in macro_cols:
        rows = []
        for col, name in (("Demande_Credit_Realisee", "Réalisé (3 derniers mois)"),
                          ("Demande_Credit_Perspectives", "Perspectives (3 prochains mois)")):
            if col in macro_cols:
                for r in q.macro_series(con, col, digits=4):
                    rows.append({"date": r["date"], "series": name, "value": r["value"]})
        bls = {"rows": rows,
               "meta": [{"name": "Réalisé (3 derniers mois)", "color": theme.UI["greyLine"]},
                        {"name": "Perspectives (3 prochains mois)", "color": COLOR_BRICK, "dash": None}]}

    # Rénovation, conditionnel.
    reno_defs = [("Reno_Activite_Batiment", "Activité passée — second œuvre", COLOR_BRICK),
                 ("Reno_Activite_Prevue", "Activité prévue — second œuvre", COLOR_GREEN)]
    reno = [{"title": name, "color": color, "rows": q.macro_series(con, col, digits=4)}
            for col, name, color in reno_defs if col in macro_cols]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "title": "🏦 Contexte Macroéconomique et Financement",
        "caption": ("Indicateurs de contexte macroéconomique et de conditions de financement : confiance "
                    "des ménages (INSEE), taux du crédit habitat (BdF/BCE), Euribor 3 mois et OAT 10 ans "
                    "(BCE), intentions d'achat de logement et taux de chômage BIT (INSEE)."),
        "confidence": q.macro_series(con, "Insee_Confiance_Menages", digits=4),
        "rates": {"rows": rate_rows, "meta": rate_meta},
        "intentions": intentions,
        "chomage": q.macro_series(con, "Taux_Chomage_BIT", digits=4),
        "credit": credit,
        "bls": bls,
        "renovation": reno,
    }


def build_actualites(con) -> dict:
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


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    # Projection JS du thème : régénérée à chaque export pour ne jamais diverger de
    # web/theme.json (le CSS de observablehq.config.js lit ce même JSON directement).
    theme.write_theme_js()
    print("[web_export] écrit components/theme.js")
    con = q.open_warehouse(refresh=True)
    try:
        for name, builder in _BUILDERS.items():
            payload = builder(con)
            path = os.path.join(DATA_DIR, f"{name}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"[web_export] écrit {name}.json")
    finally:
        con.close()


if __name__ == "__main__":
    main()
