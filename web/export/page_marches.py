"""Pages « Marché du neuf » et « Marché de l'ancien » — deux pages jumelles.

Elles partagent un socle (chiffres clés, courbes d'évolution) et la même carte KPI
(`_yoy_kpi`) : momentum selon le régime de la série, niveau, dernier mois. Le neuf ajoute
la segmentation par type, individuel contre collectif, l'ECLN et le taux de
transformation ; l'ancien, les prix Notaires-INSEE et l'accessibilité.
"""
from __future__ import annotations

import itertools

import pandas as pd

from commun import (COLOR_BLUE, COLOR_BRICK, COLOR_GREEN, COLOR_TERRACOTTA, COLOR_TEXT,
                    derniere_date, horodatage, iso_mois, ligne_niveau, lignes, milliers,
                    mois_annee, pct)
from mesures import taux_transformation
from reperes import NEUF_GATE

import analysis as ana                          # noqa: E402
import queries as q                             # noqa: E402


# Codes courts et stables pour les quatre types SIT@DEL (clés de `by_type` / `kpis_by_type`).
_TYPE_CODES = {"Maison Individuelle Pure": "ip", "Maison Individuelle Groupée": "ig",
               "Logement Collectif": "co", "Logement en Résidence": "re"}


def _yoy_kpi(kpis, mom, label, month_label, regime=ana.ADJUSTED_SEQUENTIAL,
             level=None, plateau=None):
    """Carte KPI d'un onglet marché (miroir des st.metric d'app.py).

    Alignée sur la Synthèse, et pour les mêmes raisons mesurées :

    * le momentum suit le RÉGIME de la série (`ana.headline_momentum`). Les cartes
      portaient « 3 derniers mois vs n-1 » sur SIT@DEL, c'est-à-dire sur une série déjà
      corrigée des variations saisonnières — le chiffre qui affichait +28,4 % sur les
      mises en chantier au moment exact où le rythme séquentiel disait −2,0 % ;
    * le sous-titre « Mensuel : X (Y % YoY) » perd son YoY. Sur ces séries CVS, il saute
      de 11,2 points par mois sur les permis et de 9,0 sur les chantiers (six dernières
      valeurs des chantiers : +21 +19 +49 +32 +46 +12) : c'est du bruit affiché en carte
      de tête. Le NIVEAU du dernier mois, lui, reste un fait et il est conservé ;
    * une ligne de NIVEAU s'ajoute — une pente ne dit rien de l'altitude. C'est le
      correctif qui a le plus changé la lecture de la Synthèse et il manquait ici.

    Le badge `delta` garde la croissance 12 mois : quand le régime EST le 12 mois
    (l'IGEDD), la ligne de momentum est donc omise pour ne pas répéter le badge, et la
    place revient au plateau — la seule chose que le taux annuel ne peut pas dire.
    """
    head = ana.headline_momentum(mom, regime)
    subs = []
    if head["key"] != "roll12_yoy" and head["value"] is not None:
        subs.append(pct(head["value"]) + " " + head["window"])
    if plateau:
        subs.append(f"au plateau depuis {mois_annee(plateau['since'])} "
                    f"({plateau['months']} mois)")
    if level:
        subs.append(ligne_niveau(level))
    subs.append(f"Dernier mois ({month_label}) : {milliers(kpis['current_val'])}")
    return {
        "label": label,
        "value": milliers(kpis["current_12m"]),
        "delta": pct(kpis["yoy_12m_pct"]) + " YoY",
        "subs": subs,
    }


def build_neuf(con, frames: dict) -> dict:
    df_ecln = frames["ecln"]

    # --- Série principale SIT@DEL (national, tous types) : brut + 12M + 6M + 3M (SQL) --
    roll = q.monthly(con, "sitadel", ["Permis", "MisesEnChantier"], (12, 6, 3))
    series_meta = [
        {"key": "permis", "name": "Permis de Construire", "color": COLOR_BRICK, "dash": None,
         "raw": "Permis", "r12": "Permis_12M", "r6": "Permis_6M", "r3": "Permis_3M"},
        {"key": "mises", "name": "Mises en Chantier", "color": COLOR_TEXT, "dash": "dash",
         "raw": "MisesEnChantier", "r12": "MisesEnChantier_12M", "r6": "MisesEnChantier_6M",
         "r3": "MisesEnChantier_3M"},
    ]
    main_rows = []
    for m in series_meta:
        sub = roll[["Date", m["raw"], m["r12"], m["r6"], m["r3"]]].dropna(subset=[m["raw"]])
        for _, r in sub.iterrows():
            main_rows.append({
                "date": r["Date"].strftime("%Y-%m-%d"), "series": m["name"], "key": m["key"],
                "raw": round(float(r[m["raw"]]), 3),
                "roll12": None if pd.isna(r[m["r12"]]) else round(float(r[m["r12"]]), 3),
                "roll6": None if pd.isna(r[m["r6"]]) else round(float(r[m["r6"]]), 3),
                "roll3": None if pd.isna(r[m["r3"]]) else round(float(r[m["r3"]]), 3)})

    # --- KPIs (national plein, dernier mois) ------------------------------------------
    kpi_permis = ana.calculate_kpis(roll, "Permis")
    kpi_mises = ana.calculate_kpis(roll, "MisesEnChantier")
    mom_permis = ana.momentum_metrics(roll, "Permis")
    mom_mises = ana.momentum_metrics(roll, "MisesEnChantier")
    _sit_month = mois_annee(derniere_date(roll, "Permis"))
    kpis = [
        _yoy_kpi(kpi_permis, mom_permis, "Permis de Construire (Cumul 12m glissant)",
                 _sit_month, level=ana.level_context(roll, "Permis")),
        _yoy_kpi(kpi_mises, mom_mises, "Mises en Chantier (Cumul 12m glissant)",
                 _sit_month, level=ana.level_context(roll, "MisesEnChantier")),
    ]
    # ECLN est publiée CVS-CJO comme SIT@DEL : même régime de lecture, donc séquentiel
    # d'un trimestre au précédent, et la tendance sur quatre trimestres dans le rôle du
    # cumul 12 mois. Le « vs même trimestre n-1 » qui figurait ici est le défaut que la
    # Synthèse a déjà retiré (voir _yoy_kpi).
    if df_ecln is not None and not df_ecln.empty:
        ke = df_ecln.dropna(subset=["Reservations"]).sort_values("Date")
        if len(ke) >= 8:
            r = ke["Reservations"].astype(float)
            e_seq = (float(r.iloc[-1]) / float(r.iloc[-2]) - 1) * 100
            e_trend = (float(r.iloc[-4:].sum()) / float(r.iloc[-8:-4].sum()) - 1) * 100
            kd = ke["Date"].iloc[-1]
            kpis.append({
                "label": "Réservations particuliers ECLN (trimestre)",
                "value": milliers(r.iloc[-1]),
                "delta": pct(e_trend) + " sur 4 trimestres",
                "subs": [pct(e_seq) + " vs le trimestre précédent",
                         "la demande qui décide des mises en vente, donc des chantiers suivants",
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
    sit_types = sorted(r[0] for r in con.execute('SELECT DISTINCT Type FROM sitadel').fetchall())
    codes = {t: _TYPE_CODES.get(t, t[:2].lower()) for t in sit_types}
    date_axis = [d.strftime("%Y-%m-%d") for d in roll["Date"]]

    def _arr(col):
        return [None if pd.isna(v) else round(float(v), 3) for v in col]

    # Séries par type en UNE requête (monthly_by_group), réindexées sur l'axe commun.
    bt = q.monthly_by_group(con, "sitadel", {codes[t]: [t] for t in sit_types},
                            ["Permis", "MisesEnChantier"], (12, 6, 3))
    by_type_series = []
    for t in sit_types:
        sub = bt[bt["Groupe"] == codes[t]].set_index("Date").reindex(roll["Date"])
        for m in series_meta:
            by_type_series.append({
                "type": codes[t], "key": m["key"], "raw": _arr(sub[m["raw"]]),
                "roll12": _arr(sub[m["r12"]]), "roll6": _arr(sub[m["r6"]]),
                "roll3": _arr(sub[m["r3"]])})

    kpis_by_type = {}
    for size in range(1, len(sit_types) + 1):
        for combo in itertools.combinations(sit_types, size):
            roll_c = q.monthly(con, "sitadel", ["Permis", "MisesEnChantier"], (12,), types=list(combo))
            month_c = mois_annee(derniere_date(roll_c, "Permis"))
            kpis_by_type["+".join(sorted(codes[t] for t in combo))] = [
                _yoy_kpi(ana.calculate_kpis(roll_c, "Permis"),
                         ana.momentum_metrics(roll_c, "Permis"),
                         "Permis de Construire (Cumul 12m glissant)", month_c,
                         level=ana.level_context(roll_c, "Permis")),
                _yoy_kpi(ana.calculate_kpis(roll_c, "MisesEnChantier"),
                         ana.momentum_metrics(roll_c, "MisesEnChantier"),
                         "Mises en Chantier (Cumul 12m glissant)", month_c,
                         level=ana.level_context(roll_c, "MisesEnChantier"))]

    # --- Individuel vs collectif -------------------------------------------------------
    iv_groups = [
        ("Maison individuelle pure", ana.SITADEL_INDIVIDUEL_PUR, COLOR_BRICK),
        ("Individuel total (pur + groupé)", ana.SITADEL_INDIVIDUEL, COLOR_TERRACOTTA),
        ("Collectif", ana.SITADEL_COLLECTIF, COLOR_BLUE),
    ]
    # Les 3 groupes (types possiblement chevauchants) en une requête, pour les 2 métriques.
    ivg = q.monthly_by_group(con, "sitadel", {lbl: types for lbl, types, _c in iv_groups},
                             ["MisesEnChantier", "Permis"], (12,))
    iv = {}
    for metric in ("MisesEnChantier", "Permis"):
        g_kpis, g_lines = [], []
        for lbl, types, clr in iv_groups:
            g_roll = ivg[ivg["Groupe"] == lbl].sort_values("Date")
            v12 = g_roll[f"{metric}_12M"].dropna()
            g_mom = ana.momentum_metrics(g_roll, metric)
            # Le NIVEAU par segment est ici plus décisif que partout ailleurs sur le site.
            # Mesuré : la maison individuelle pure affichait « +40,0 % sur 3 mois » —
            # lue comme le segment vedette, et désignée par le chapeau de la section
            # comme « le driver de volume le plus direct » — alors qu'elle est à 42 %
            # SOUS sa normale 2010-19, au 7ᵉ centile de son histoire. C'est un rebond de
            # plancher. Symétriquement, le collectif affichait +25,8 % quand son rythme
            # séquentiel valait −6,9 % : le segment le moins déprimé (−12 %, 36ᵉ centile)
            # est aussi celui qui vient de se retourner. Les deux lectures s'inversent,
            # et c'est un arbitrage de lignes de produits qui se joue dessus.
            g_lvl = ana.level_context(g_roll, metric)
            g_kpis.append({"label": lbl, "color": clr,
                           "val12": milliers(v12.iloc[-1]) if not v12.empty else "—",
                           "roll12_yoy": pct(g_mom["roll12_yoy"]) if g_mom["roll12_yoy"] is not None else None,
                           "last3_seq": pct(g_mom["last3_seq"]) if g_mom["last3_seq"] is not None else "—",
                           "niveau": ligne_niveau(g_lvl)})
            # Courbes : seulement individuel pur + collectif (comme app.py).
            if types in (ana.SITADEL_INDIVIDUEL_PUR, ana.SITADEL_COLLECTIF):
                # La clé DOIT s'appeler "value" : c'est ce que `multiLine` trace (y: "value").
                # Elle s'est appelée "value_k" un temps — seule série de tout l'export à
                # diverger — et le graphique « Individuel vs Collectif » rendait ses axes
                # sans aucune courbe, l'ordonnée étant indéfinie pour chaque point.
                for _, r in g_roll[["Date", f"{metric}_12M"]].dropna().iterrows():
                    g_lines.append({"date": r["Date"].strftime("%Y-%m-%d"), "series": lbl,
                                    "color": clr, "value": round(float(r[f"{metric}_12M"]) / 1000.0, 2)})
        iv[metric] = {"kpis": g_kpis, "lines": g_lines}

    # --- ECLN --------------------------------------------------------------------------
    ecln = None
    if df_ecln is not None and not df_ecln.empty:
        e = df_ecln.dropna(subset=["Reservations"]).sort_values("Date").copy()
        e["DelaiMois"] = e["DelaiEcoulement"] * 3.0
        last = e.iloc[-1]
        lastq = f"{last['Date'].year}-T{(last['Date'].month - 1) // 3 + 1}"
        eb = df_ecln.dropna(subset=["Resa_Sociaux"]).sort_values("Date")

        # Chaque KPI reçoit son momentum SÉQUENTIEL (série CVS-CJO) et, pour le délai,
        # sa référence longue. La Synthèse dit désormais « 22 mois · 15 en moyenne — 53 %
        # de temps de plus » quand cette page de DÉTAIL n'affichait que « 22 mois »,
        # sans repère : la page de zoom en disait moins que la page de survol.
        def _eseq(col):
            s = e[col].astype(float)
            return (float(s.iloc[-1]) / float(s.iloc[-2]) - 1) * 100 if len(s) >= 2 else None

        _dl_moy = float(e["DelaiMois"].mean())
        _dl_now = float(last["DelaiMois"])
        _dl_ecart = (_dl_now / _dl_moy - 1) * 100 if _dl_moy else None
        ecln = {
            "last_quarter": lastq,
            "kpis": [
                {"label": "Réservations particuliers (trim.)", "value": milliers(last["Reservations"]),
                 "subs": [pct(_eseq("Reservations")) + " vs le trimestre précédent"]},
                {"label": "Mises en vente (trim.)", "value": milliers(last["MisesEnVente"]),
                 "subs": [pct(_eseq("MisesEnVente")) + " vs le trimestre précédent"]},
                {"label": "Encours à la vente", "value": milliers(last["Encours"]),
                 "subs": [pct(_eseq("Encours")) + " vs le trimestre précédent",
                          "le stock déjà construit ou en cours qui attend un acheteur"]},
                {"label": "Délai d'écoulement", "value": f"{_dl_now:.0f} mois",
                 "subs": [f"{_dl_moy:.0f} mois en moyenne depuis {int(e['Date'].iloc[0].year)}"
                          + (f" — il faut aujourd'hui {abs(_dl_ecart):.0f} % de temps de plus "
                             "pour écouler le stock" if _dl_ecart and _dl_ecart > 0 else "")]},
            ],
            "stock_rows": lignes(e, {"encours": "Encours", "mises_en_vente": "MisesEnVente"}),
            "delai_rows": lignes(e, {"delai_mois": "DelaiMois"}),
            "cat_rows": lignes(eb, {"particuliers": "Reservations", "sociaux": "Resa_Sociaux",
                                        "institutionnels": "Resa_Institutionnels"}),
            "prixm2_rows": lignes(e.dropna(subset=["PrixM2_Collectif"]), {"prix": "PrixM2_Collectif"}),
        }

    return {
        "generated_at": horodatage(),
        "title": "🏗️ Marché du neuf — de l'autorisation à la vente",
        "caption": ("Le tunnel du logement neuf au niveau national : permis de construire et mises "
                    "en chantier (SIT@DEL), dynamique individuel vs collectif, puis commercialisation "
                    "des logements neufs (ECLN)."),
        "how_to_read": (
            "Le tunnel se lit de gauche à droite : un permis autorisé devient une mise en chantier "
            "6 à 12 mois plus tard, puis un logement commercialisé. SIT@DEL est publiée corrigée des "
            "variations saisonnières et des jours ouvrables : le momentum se lit donc sur les 3 derniers "
            "mois comparés aux 3 précédents, jamais aux mêmes mois d'un an plus tôt. Le cumul 12 mois "
            "glissant donne le niveau annuel courant ; la vue brute montre le mois réel, "
            "beaucoup plus volatil. L'individuel pur porte nettement plus de second œuvre par "
            "logement que le collectif — sa dynamique propre est isolée plus bas. Côté ECLN, le "
            "délai d'écoulement est le meilleur signal de tension : il monte quand le stock ne part plus."),
        "kpis": kpis,
        "main_series": {"meta": [{"key": m["key"], "name": m["name"], "color": m["color"], "dash": m["dash"]}
                                 for m in series_meta],
                        "rows": main_rows, "last_month": mois_annee(derniere_date(roll, "Permis")),
                        "source": "Source : SIT@DEL (SDES)"},
        "by_type": {"dates": date_axis,
                    "types": [{"code": codes[t], "name": t} for t in sit_types],
                    "series": by_type_series},
        "kpis_by_type": kpis_by_type,
        "indiv_collectif": iv,
        "ecln": ecln,
        "transformation": _transformation(con),
    }


def build_ancien(con, frames: dict) -> dict:
    macro_cols = q.macro_data_columns(con)

    roll = q.monthly(con, "ventes_ancien", ["Transactions"], (12, 6, 3))
    kpi_tx = ana.calculate_kpis(roll, "Transactions")
    mom_tx = ana.momentum_metrics(roll, "Transactions")
    tx_month = mois_annee(derniere_date(roll, "Transactions"))

    main_rows = []
    for _, r in roll[["Date", "Transactions", "Transactions_12M", "Transactions_6M", "Transactions_3M"]].dropna(subset=["Transactions"]).iterrows():
        main_rows.append({"date": r["Date"].strftime("%Y-%m-%d"), "series": "Transactions Ancien", "key": "tx",
                          "raw": round(float(r["Transactions"]), 3),
                          "roll12": None if pd.isna(r["Transactions_12M"]) else round(float(r["Transactions_12M"]), 3),
                          "roll6": None if pd.isna(r["Transactions_6M"]) else round(float(r["Transactions_6M"]), 3),
                          "roll3": None if pd.isna(r["Transactions_3M"]) else round(float(r["Transactions_3M"]), 3)})

    monthly_rows = lignes(roll, {"tx": "Transactions"})
    last_month_num = int(pd.Timestamp(roll["Date"].max()).month) if not roll.empty else 12

    # --- Prix & accessibilité (SQL) ----------------------------------------------------
    prix = {"available": False}
    if "Prix_Ancien_Ensemble" in macro_cols:
        labels = {"Prix_Ancien_Ensemble": "Ensemble", "Prix_Ancien_Appartements": "Appartements",
                  "Prix_Ancien_Maisons": "Maisons"}
        colors = {"Prix_Ancien_Ensemble": COLOR_BRICK, "Prix_Ancien_Appartements": COLOR_BLUE,
                  "Prix_Ancien_Maisons": COLOR_GREEN}
        cols = [c for c in labels if c in macro_cols]

        def _long(colmap, yoy=False):
            """Séries longues via SQL : niveaux (macro_series) ou YoY (series_with_lag_pct)."""
            out = []
            for key, (col, name) in colmap.items():
                pts = (q.series_with_lag_pct(con, col, lag=4, digits=3) if yoy
                       else q.macro_series(con, col, digits=3))
                for p in pts:
                    out.append({"date": p["date"], "series": name, "key": key, "value": p["value"]})
            return out

        p_kpis = []
        for c in cols:
            pts = q.macro_series(con, c, digits=10)
            if len(pts) >= 5:
                last, prev = pts[-1]["value"], pts[-5]["value"]
                p_kpis.append({"label": labels[c], "color": colors[c],
                               "value": f"{last:.1f}".replace(".", ","),
                               "yoy": pct((last / prev - 1) * 100)})
        last_date = q.macro_series(con, "Prix_Ancien_Ensemble")[-1]["date"][:7]
        _pmap = {labels[c].lower(): (c, labels[c]) for c in cols}
        levels = _long(_pmap)
        yoy = _long(_pmap, yoy=True)

        # Capacité d'emprunt & accessibilité, pour 25 et 20 ans (base 100 = 2015).
        cap = {str(term): lignes(q.capacity_accessibility(con, term),
                                     {"capidx": "capidx", "prix": "prix", "access": "access"})
               for term in (25, 20)}

        new_vs_old = {"available": False}
        if "Prix_Neuf" in macro_cols:
            _nmap = {"neuf": ("Prix_Neuf", "Neuf"), "ancien": ("Prix_Ancien_Ensemble", "Ancien")}
            new_vs_old = {"available": True, "levels": _long(_nmap), "yoy": _long(_nmap, yoy=True),
                          "series_meta": [{"key": "neuf", "name": "Neuf", "color": COLOR_BLUE},
                                          {"key": "ancien", "name": "Ancien", "color": COLOR_BRICK}]}

        prix = {"available": True, "kpis": p_kpis,
                "last_date": last_date,
                "price_levels": levels, "price_yoy": yoy, "capacity": cap, "new_vs_old": new_vs_old,
                "series_meta": [{"key": labels[c].lower(), "name": labels[c], "color": colors[c]} for c in cols]}

    return {
        "generated_at": horodatage(),
        "title": "🏠 Marché de l'ancien — transactions, prix & accessibilité",
        "caption": ("Le marché des logements anciens au niveau national : volumes de transactions "
                    "(IGEDD), puis prix Notaires-INSEE et lecture de l'accessibilité."),
        "how_to_read": (
            "Le cumul 12 mois glissant reproduit la série publiée par l'IGEDD (« ventes sur un an ») ; "
            "les flux mensuels en sont la reconstruction, utile pour la dynamique récente mais plus "
            "bruitée. Côté accessibilité, la capacité d'emprunt est calculée à mensualité constante : "
            "elle chute donc quand les taux montent, indépendamment des prix. L'indice d'accessibilité "
            "rapporte cette capacité aux prix — sous 100, un ménage type achète moins de surface qu'en 2015."),
        # L'IGEDD est reconstruite en différenciant un cumul 12 mois : ses flux mensuels
        # sont trop bruités pour un momentum séquentiel (10 pt de saut par mois, mesuré).
        # Régime 12 mois, donc, complété par le plateau — la seule chose qu'un taux
        # annuel à base basse ne peut pas dire — et par le niveau.
        "kpi": _yoy_kpi(kpi_tx, mom_tx, "Ventes anciennes IGEDD (Cumul 12m glissant)",
                        tx_month, regime=ana.RAW_TWELVE_MONTHS,
                        level=ana.level_context(roll, "Transactions"),
                        plateau=ana.plateau_months(roll, "Transactions")),
        "main_series": {"meta": [{"key": "tx", "name": "Transactions Ancien", "color": COLOR_GREEN, "dash": None}],
                        "rows": main_rows, "last_month": tx_month, "source": "Source : IGEDD"},
        "monthly": {"rows": monthly_rows, "last_month_num": last_month_num},
        "prix": prix,
    }


def _transformation(con) -> dict:
    """Permis → mises en chantier : le taux de transformation, et la preuve que les permis
    n'ont PAS d'avance.

    L'intuition — « un permis précède mécaniquement un chantier, donc SIT@DEL donne une
    avance gratuite à qui fabrique du second œuvre » — est fausse dans cette série, et
    `lag_profile` le montre sans commentaire : le R² de chantiers(t) ~ permis(t−k) est
    MAXIMAL à k = 0 et décroît de façon monotone. Une courbe qui descend dès le premier
    mois est exactement l'inverse de ce qu'on attend d'un indicateur avancé.

    Ce que les données soutiennent, en revanche, c'est le TAUX DE TRANSFORMATION : la part
    des logements autorisés qui sont effectivement ouverts en chantier. Il ne prévoit rien
    — il décrit ce que les promoteurs font de leurs autorisations, ce qui est déjà une
    information de premier ordre pour un fournisseur.
    """
    import forecast as _fc

    flux = q.monthly(con, "sitadel", ["Permis", "MisesEnChantier"]).set_index("Date").sort_index()
    permis, chantiers = flux["Permis"].dropna(), flux["MisesEnChantier"].dropna()
    p12, m12 = permis.rolling(12).sum(), chantiers.rolling(12).sum()
    taux = taux_transformation(flux)
    if taux.empty:
        return {}

    profil = []
    for k in range(0, 13):
        X = pd.DataFrame({"x": permis.shift(k)}).join(chantiers.rename("y")).dropna()
        if len(X) < 60:
            continue
        _, r2, _, _ = _fc.ols(X[["x"]].values, X["y"].values)
        profil.append({"lag": k, "r2": round(float(r2), 4)})

    return {
        "rows": [{"date": iso_mois(d), "taux": round(float(v) * 100, 2)}
                 for d, v in taux.items()],
        "actuel": round(float(taux.iloc[-1]) * 100, 1),
        "moyenne": round(float(taux.mean()) * 100, 1),
        "min": {"valeur": round(float(taux.min()) * 100, 1), "date": iso_mois(taux.idxmin())},
        "max": {"valeur": round(float(taux.max()) * 100, 1), "date": iso_mois(taux.idxmax())},
        "dernier_permis": int(round(float(p12.dropna().iloc[-1]))),
        "dernier_chantier": int(round(float(m12.dropna().iloc[-1]))),
        "lag_profile": profil,
        "gate": NEUF_GATE,
    }
