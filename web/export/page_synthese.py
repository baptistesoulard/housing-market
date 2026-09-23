"""Page « Synthèse » : des FAITS, puis leur RÉDACTION — deux étapes qui ne se mélangent pas.

`faits()` interroge l'entrepôt et ne rend que des nombres (momentum, niveaux, stock, taux,
verdict…). `rediger()` ne reçoit que ce dictionnaire et n'accède à aucune donnée : il
choisit les pastilles et écrit les phrases. La séparation n'est pas cosmétique — c'est ce
qui permet de tester la rédaction sur des faits fabriqués (un écart négatif, un zéro, un
modèle non calibrable) sans construire l'entrepôt, et donc de verrouiller des règles comme
« le signe arithmétique et le signe ressenti pointent dans le même sens »
(voir tests/test_redaction.py).
"""
from __future__ import annotations

import pandas as pd

from commun import (COLOR_BRICK, COLOR_GREEN, COLOR_TEXT, abrege, arrondi_millier, horodatage,
                    jalons_a_venir, ligne_momentum, ligne_niveau, milliers, mois_annee,
                    pastille, pct, pt, renvoi, statut_annuel, statut_seq)
from mesures import stock_neuf, taux_transformation
from reperes import BPCE_TX_ANCIEN_2026
from verdict import partage

import actualites as actu                       # noqa: E402
import analysis as ana                          # noqa: E402
import queries as q                             # noqa: E402


def build_synthese(con, frames: dict) -> dict:
    f = faits(con, frames)
    texte = rediger(f)
    return {
        "generated_at": horodatage(),
        "title": "🧭 Synthèse — vue d'ensemble du marché",
        "caption": ("L'état du marché immobilier en un coup d'œil : tendance par pilier, "
                    "chiffres clés et implication pour la demande second œuvre."),
        "pillars": texte["pillars"],
        "takeaways": texte["takeaways"],
        "freshness": texte["freshness"],
        "how_to_read": COMMENT_LIRE,
        "blocks": texte["blocks"],
        "chart": f["graphique"],
    }


# =================================== FAITS ===========================================
def faits(con, frames: dict) -> dict:
    """Tous les nombres de la page, sans une phrase. Seule fonction qui lit l'entrepôt."""
    df_ecln = frames["ecln"]
    macro_cols = q.macro_data_columns(con)

    # --- Momentum & niveaux 12 m (SQL, national plein, indépendant de tout filtre) ---
    roll_sit = q.monthly(con, "sitadel", ["Permis", "MisesEnChantier"], (12,))
    roll_va = q.monthly(con, "ventes_ancien", ["Transactions"], (12,))
    m_permis = ana.momentum_metrics(roll_sit, "Permis")
    m_mises = ana.momentum_metrics(roll_sit, "MisesEnChantier")
    m_tx = ana.momentum_metrics(roll_va, "Transactions")
    k_permis = ana.calculate_kpis(roll_sit, "Permis")
    k_mises = ana.calculate_kpis(roll_sit, "MisesEnChantier")
    k_tx = ana.calculate_kpis(roll_va, "Transactions")

    def _last_prev(col, months=12):
        if col not in macro_cols:
            return None, None
        return q.macro_last_and_year_ago(con, col, months)

    def _ecart(now, before):
        return None if (now is None or before is None) else now - before

    # --- Taux de transformation permis → chantiers ------------------------------------
    # La référence du taux de conversion est la MÊME décennie que celle des niveaux
    # (ana.LEVEL_REF_YEARS), et c'est un correctif : la moyenne sur tout l'historique
    # (84,8 %) englobe la rupture de 2023-2026 qu'on cherche justement à mesurer —
    # l'anomalie diluait sa propre référence et se faisait paraître plus petite. Le
    # taux tenait entre 85 et 88 % sur les quatre sous-périodes de 2001 à 2022, crise
    # de 2008 comprise, donc le choix de fenêtre ne change presque rien au niveau
    # (85,3 % contre 84,8 %) mais rend la comparaison honnête et auditable. La fenêtre
    # est NOMMÉE partout où le chiffre apparaît, jamais laissée implicite.
    taux_tr = taux_transformation(roll_sit.set_index("Date").sort_index())
    tr = None
    if not taux_tr.empty:
        ref = taux_tr.loc[ana.LEVEL_REF_YEARS[0]:ana.LEVEL_REF_YEARS[1]]
        if not ref.empty:
            tr_now, tr_moy = float(taux_tr.iloc[-1]) * 100, float(ref.mean()) * 100
            implied = k_permis["current_12m"] * tr_moy / 100.0
            tr = {"now": tr_now, "moy": tr_moy, "implied": implied,
                  "ecart": implied - k_mises["current_12m"],
                  "ref_label": f"{ana.LEVEL_REF_YEARS[0]}-{ana.LEVEL_REF_YEARS[1][-2:]}"}

    # --- Réservations ECLN : lecture séquentielle (série CVS-CJO, comme SIT@DEL) --------
    ecln = None
    if df_ecln is not None and not df_ecln.empty:
        se = df_ecln.dropna(subset=["Reservations"]).sort_values("Date")
        if len(se) >= 8:
            r = se["Reservations"].astype(float)
            ecln = {"dernier": float(r.iloc[-1]),
                    "seq": (float(r.iloc[-1]) / float(r.iloc[-2]) - 1) * 100,
                    "tendance": (float(r.iloc[-4:].sum()) / float(r.iloc[-8:-4].sum()) - 1) * 100}

    # --- Financement --------------------------------------------------------------------
    r_now, r_yr = _last_prev("Credit_Logement_Taux_Interet")
    bls_now, _ = _last_prev("Demande_Credit_Perspectives")
    # Indice d'accessibilité (capacité d'emprunt ÷ prix, base 100 = 2015, prêt 25 ans).
    acces = None
    if "Prix_Ancien_Ensemble" in macro_cols:
        _acc_df = q.capacity_accessibility(con, 25)
        if not _acc_df.empty:
            acc_s = _acc_df.set_index("Date")["access"].dropna()
            if not acc_s.empty:
                a_last = float(acc_s.iloc[-1])
                older = acc_s[acc_s.index <= acc_s.index[-1] - pd.DateOffset(months=12)]
                acces = {"now": a_last,
                         "sur_un_an": (a_last - float(older.iloc[-1])) if not older.empty else None}

    # --- Perspective --------------------------------------------------------------------
    renovation = None
    if "Reno_Activite_Batiment" in macro_cols:
        rn_last, rn_prev = _last_prev("Reno_Activite_Batiment")
        if rn_last is not None:
            renovation = {"now": rn_last, "delta": _ecart(rn_last, rn_prev)}
    jalons = jalons_a_venir(actu.items_sorted())
    tx12 = roll_va.set_index("Date")["Transactions_12M"].dropna()

    # --- Fraîcheur ----------------------------------------------------------------------
    def _last_valid(df, col):
        valid = df.dropna(subset=[col])
        return valid["Date"].max() if not valid.empty else pd.NaT

    ecln_date = None
    if df_ecln is not None and not df_ecln.empty:
        e_last = df_ecln.dropna(subset=["Reservations"])["Date"].max()
        ecln_date = e_last if pd.notna(e_last) else None

    mom_ip = ana.momentum_metrics(
        q.monthly(con, "sitadel", ["MisesEnChantier"], (12,), types=ana.SITADEL_INDIVIDUEL_PUR),
        "MisesEnChantier")

    return {
        "kpi": {"permis": k_permis, "mises": k_mises, "tx": k_tx},
        # Momentum publié : séquentiel sur SIT@DEL (CVS-CJO), 12 mois sur l'IGEDD. Le
        # régime dépend de la série, pas du goût : voir analysis.headline_momentum.
        "momentum": {"permis": ana.headline_momentum(m_permis, ana.ADJUSTED_SEQUENTIAL),
                     "mises": ana.headline_momentum(m_mises, ana.ADJUSTED_SEQUENTIAL),
                     "tx": ana.headline_momentum(m_tx, ana.RAW_TWELVE_MONTHS)},
        # Le pilier « Neuf » ne moyenne plus ses deux étages : quand l'amont (permis) et
        # l'aval (chantiers) divergent, c'est la divergence qui est l'information.
        "pilier_neuf": ana.pillar_neuf(m_permis, m_mises),
        "plateau_tx": ana.plateau_months(roll_va, "Transactions"),
        # Altitude du niveau — l'autre moitié de la question (voir ana.level_context).
        "niveau": {"permis": ana.level_context(roll_sit, "Permis"),
                   "mises": ana.level_context(roll_sit, "MisesEnChantier"),
                   "tx": ana.level_context(roll_va, "Transactions")},
        "individuel_pur": {"seq": mom_ip.get("last3_seq"), "annuel": mom_ip.get("roll12_yoy")},
        "stock": stock_neuf(df_ecln),
        "transformation": tr,
        "ecln": ecln,
        "taux": None if r_now is None else {"now": r_now, "sur_un_an": _ecart(r_now, r_yr)},
        "bls": bls_now,
        "accessibilite": acces,
        "verdict": partage(con),
        "tx12_dernier": float(tx12.iloc[-1]) if not tx12.empty else None,
        "renovation": renovation,
        "prochain_jalon": ({"date": jalons[0][0], "libelle": jalons[0][1]["court"]["FR"]}
                           if jalons else None),
        "fraicheur": {"sitadel": _last_valid(roll_sit, "Permis"),
                      "igedd": _last_valid(roll_va, "Transactions"),
                      "ecln": ecln_date},
        "graphique": graphique(roll_sit, roll_va),
    }


def graphique(roll_sit, roll_va) -> dict:
    """Neuf vs ancien, en cumul 12 mois : niveaux (en milliers) et base 100."""
    merged = pd.merge(
        roll_sit[["Date", "Permis_12M", "MisesEnChantier_12M"]],
        roll_va[["Date", "Transactions_12M"]],
        on="Date", how="outer").sort_values("Date")
    idx_cols = ["Permis_12M", "MisesEnChantier_12M", "Transactions_12M"]
    # Base 100 = moyenne annuelle 2015, comme les indices de prix affichés ailleurs sur le
    # site (voir analysis.BASE_YEAR).
    base = ana.base_100(merged, idx_cols)

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
            idx = (lvl / base[col] * 100.0) if base.get(col) else None
            chart_rows.append({
                "date": row["Date"].strftime("%Y-%m-%d"),
                "series": name, "key": key,
                "level_k": round(lvl / 1000.0, 2),
                "index_100": round(idx, 2) if idx is not None else None})

    return {
        "base_label": ana.BASE_LABEL if any(base.values()) else None,
        "series_meta": [{"key": k, "name": n, "color": c, "dash": d}
                        for _c, k, n, c, d in series_defs],
        "rows": chart_rows,
        "source": "Source : SIT@DEL (SDES) · IGEDD (CGEDD) — cumul 12 mois glissant",
    }


# ================================= RÉDACTION =========================================
def _statut_taux(delta_pt) -> str:
    """Pour un taux, 🟢 veut dire des conditions qui s'améliorent, donc un taux qui BAISSE."""
    if delta_pt is None:
        return "flat"
    return "down" if delta_pt > 0.1 else ("up" if delta_pt < -0.1 else "flat")


def _statut_bls(v) -> str:
    return "up" if v > 0 else ("down" if v < -10 else "flat")


def rediger(f: dict) -> dict:
    """Pastilles, puces, fraîcheur et blocs de cartes, depuis les seuls `faits`."""
    head, pn, plateau_tx, taux = f["momentum"], f["pilier_neuf"], f["plateau_tx"], f["taux"]
    dr_yr = taux["sur_un_an"] if taux else None

    # ---------------------------- Pastilles par pilier ----------------------------
    pill_neuf = pn["status"]
    # Ancien : un plateau EST un état stable, et il se lit sur le niveau — plus fiable
    # qu'un taux de croissance annuel dont la base est basse (voir plateau_months).
    pill_ancien = "flat" if plateau_tx else statut_annuel(head["tx"]["value"])
    pill_fin = _statut_taux(dr_yr)

    w_market = {"up": "en reprise", "flat": "stable", "down": "en repli"}
    w_fin = {"up": "en amélioration", "flat": "stable", "down": "en durcissement"}
    w_ancien = f"au plateau depuis {plateau_tx['months']} mois" if plateau_tx else w_market[pill_ancien]
    pillars = [
        {"key": "neuf", "label": "Neuf", "status": pill_neuf,
         "dot": pastille(pill_neuf), "word": pn["word"]},
        {"key": "ancien", "label": "Ancien", "status": pill_ancien,
         "dot": pastille(pill_ancien), "word": w_ancien},
        {"key": "fin", "label": "Financement", "status": pill_fin,
         "dot": pastille(pill_fin), "word": w_fin[pill_fin]},
    ]

    return {
        "pillars": pillars,
        "takeaways": _puces(f, pill_ancien, pill_fin),
        "freshness": _fraicheur(f["fraicheur"]),
        "blocks": _blocs(f, pill_ancien),
    }


def _puces(f: dict, pill_ancien: str, pill_fin: str) -> list:
    """« À retenir » : le niveau de lecture le plus CHER de la page.

    Trois pastilles pour un coup d'œil, quatre puces pour trente secondes, douze cartes
    pour le détail. Un lecteur qui s'arrête après les puces doit y trouver les faits les
    plus tranchants, pas seulement ceux qui existaient quand ce générateur a été écrit :
    le stock, le taux de transformation et la projection y montent donc aussi.
    """
    k, head, niv = f["kpi"], f["momentum"], f["niveau"]
    pn, plateau_tx, stock, tr = f["pilier_neuf"], f["plateau_tx"], f["stock"], f["transformation"]
    verdict, taux, bls_now = f["verdict"], f["taux"], f["bls"]
    takeaways = []

    # --- Puce 1 : AUJOURD'HUI — l'ancien d'abord, puis le neuf ---------------------
    # Les deux marchés sont séparés à l'intérieur de la puce plutôt que fondus : ils
    # n'alimentent pas les mêmes lignes de produits, et ils ne disent pas la même chose
    # en ce moment — l'ancien est haut mais figé, le neuf est bas et sous stock.
    # Chaque moitié tient en une phrase : niveau, altitude, et le fait qui pique. Le
    # détail (taux annuel, percentile, explication du plateau) reste sur les cartes —
    # une puce qui déborde annule la marche entre le résumé et le détail.
    def _altitude(ctx):
        return ("" if not ctx else
                (", " + f"{abs(ctx['gap_pct']):.0f} %".replace(".", ",")
                 + (" sous" if ctx["gap_pct"] < 0 else " au-dessus de")
                 + f" la normale {ctx['ref_label']}"))

    anc = f"**Ancien** : {abrege(k['tx']['current_12m'])} ventes sur 12 mois" + _altitude(niv["tx"])
    if plateau_tx:
        anc += f", mais au plateau depuis {mois_annee(plateau_tx['since'])}"
    neu = f"**Neuf** : {abrege(k['mises']['current_12m'])} chantiers" + _altitude(niv["mises"])
    if stock:
        neu += (f", sur un stock de {milliers(stock['encours'])} invendus qui met "
                f"{stock['mois']:.0f} mois à s'écouler contre {stock['moy_mois']:.0f} "
                "habituellement")
    # Statut de la puce : les deux VOLUMES du présent. Le stock est un avertissement à
    # l'intérieur de la puce, pas de quoi peindre tout le présent en rouge.
    _now = {statut_seq(head["mises"]["value"]), pill_ancien}
    st_now = "down" if "down" in _now else ("up" if _now == {"up"} else "flat")
    takeaways.append(f"{pastille(st_now)} **Aujourd'hui** — {anc}. {neu}.")

    # --- Puce 2 : LE CARNET — ce qui est déjà autorisé ------------------------------
    # Nomme la divergence quand il y en a une : c'est le seul endroit où le mécanisme
    # peut être écrit en toutes lettres, puis le taux de conversion qui dit combien
    # s'ouvriront vraiment.
    p3, m3 = pct(head["permis"]["value"]), pct(head["mises"]["value"])
    m12 = pct(k["mises"]["yoy_12m_pct"])
    if pn["kind"] == "amont_repli":
        # Pas « tiennent sur le stock d'autorisations » : le site MESURE ce lien
        # (lag_profile dans page_marches._transformation) et le RÉFUTE — le R² de
        # chantiers(t) ~ permis(t−k) est maximal à k=0 et décroît, signe qu'il n'y a pas
        # d'avance mesurable. Affirmer une courroie de transmission contredirait la page
        # « Marché du neuf ». On ne rapporte que le fait : les chantiers ralentissent
        # moins vite que les permis, sans en attribuer la cause au stock de permis.
        corps = (f"les permis reculent ({p3} sur 3 mois) plus vite que les chantiers, qui "
                 f"marquent le pas après une forte année ({m3} sur 3 mois, "
                 f"{m12} sur 12 mois)")
    elif pn["kind"] == "amont_reprise":
        corps = (f"les permis repartent ({p3} sur 3 mois) avant les chantiers "
                 f"({m3} sur 3 mois, {m12} sur 12 mois) — l'effet se verra dans 12 à 18 mois")
    elif pn["kind"] == "reprise":
        corps = (f"les deux étages accélèrent — permis {p3} et chantiers {m3} sur 3 mois "
                 f"({m12} sur 12 mois)")
    elif pn["kind"] == "repli":
        corps = (f"les deux étages reculent — permis {p3} et chantiers {m3} sur 3 mois "
                 f"({m12} sur 12 mois)")
    else:
        corps = f"permis {p3} et chantiers {m3} sur 3 mois ; tendance 12 mois {m12}"
    l2 = f"{pastille(pn['amont'])} **Le carnet** — {corps}"
    if tr:
        # La puce porte les DEUX TAUX et rien d'autre. Le volume contrefactuel qui s'y
        # trouvait (« 25 794 manquent à l'appel ») avait trois défauts à ce niveau de
        # lecture : c'est la seule quantité des puces qui ne s'est jamais produite ;
        # l'écart-type du taux (4,9 pt) la déplace de ±18 000 logements, donc cinq
        # chiffres significatifs sur une grandeur connue à un près ; et sa valeur dépend
        # de la fenêtre de référence (25,8 k / 27,7 k / 30,0 k selon le choix), ce qui
        # ne se voit pas. La paire de taux se suffit — c'est la RUPTURE qui parle.
        l2 += (". Et seulement " + f"{tr['now']:.0f} %"
               + " des permis deviennent des chantiers, contre "
               + f"{tr['moy']:.0f} % dans les années 2010")
    ip = f["individuel_pur"]
    if ip["seq"] is not None:
        l2 += (f". La maison individuelle pure reste le segment porteur "
               f"({pct(ip['seq'])} sur 3 mois, {pct(ip['annuel'])} sur 12 mois).")
    else:
        l2 += "."
    takeaways.append(l2)

    # --- Puce 3 : FINANCEMENT -----------------------------------------------------------
    l3_parts = []
    if taux is not None:
        part = f"taux de crédit à {taux['now']:.2f} %".replace(".", ",")
        if taux["sur_un_an"] is not None:
            part += f" ({pt(taux['sur_un_an'])} sur un an)"
        l3_parts.append(part)
    if bls_now is not None:
        bls_word = ("en hausse" if bls_now > 0 else ("en baisse" if bls_now < -10 else "stable"))
        l3_parts.append(f"les banques anticipent une demande de crédit {bls_word}")
    if l3_parts:
        takeaways.append(f"{pastille(pill_fin)} **Financement** — " + " ; ".join(l3_parts) + ".")

    # --- Puce 4 : CE QUE ÇA IMPLIQUE ----------------------------------------------------
    # L'horizon 12-18 mois est piloté par l'AMONT — les permis —, pas par la pastille du
    # pilier : c'est l'autorisation d'aujourd'hui qui devient le chantier de l'an
    # prochain. Lire ici le statut agrégé laisserait l'aval, qui décrit le présent,
    # masquer le signal du futur — le défaut même que la fin de la moyenne corrige.
    impl_neuf = {"up": "signal favorable à 12-18 mois via le neuf (fermetures & menuiseries) : "
                       "les permis repartent",
                 "flat": "signal neuf neutre à 12-18 mois : les permis ne bougent pas",
                 "down": "vent contraire à 12-18 mois côté neuf : les permis reculent"}[pn["amont"]]
    # Le second membre porte la PROJECTION quand elle existe : c'est le seul chiffre
    # prospectif du site, il n'avait aucune raison de rester cantonné aux cartes. Repli
    # sur l'état des transactions quand le modèle n'est pas calibrable.
    if verdict:
        ampleur = f"{abs(verdict['change_pct']):.0f} %".replace(".", ",")
        mouvement = {"hausse": f"en hausse d'environ {ampleur}",
                     "baisse": f"en recul d'environ {ampleur}",
                     "stable": "à peu près stables"}[verdict["direction"]]
        impl_ancien = (f"ventes anciennes projetées {mouvement} d'ici "
                       f"{verdict['target_month']}")
    else:
        impl_ancien = ("transactions au plateau, pas de relais à court terme" if plateau_tx
                       else {"up": "soutien à court terme (~2 mois) via les transactions "
                                   "(sécurité & domotique)",
                             "flat": "transactions neutres à court terme",
                             "down": "prudence à court terme (~2 mois) sur les produits liés "
                                     "aux déménagements (sécurité & domotique)"}[pill_ancien])
    takeaways.append(f"🎯 **Ce que ça implique** — {impl_neuf} ; {impl_ancien}.")
    return takeaways


def _fraicheur(fr: dict) -> list:
    out = [f"SIT@DEL : {mois_annee(fr['sitadel'])}",
           f"IGEDD : {mois_annee(fr['igedd'])}"]
    if fr["ecln"] is not None:
        e = fr["ecln"]
        out.append(f"ECLN : {e.year}-T{(e.month - 1) // 3 + 1}")
    return out


def _blocs(f: dict, pill_ancien: str) -> list:
    """Les quatre blocs de cartes, rangés par HORIZON et non par source de données.

    « Activité / Financement / Perspective » était le plan mental du producteur — il
    regroupait ce qui vient du même fichier. Un lecteur qui décide, lui, va du présent vers
    l'avenir : ce qui se consomme maintenant, ce qui est déjà engagé, ce qui pilote la
    suite, puis où le modèle voit le marché. Les conditions de financement passent juste
    AVANT la projection : ce sont ses entrées, on lit les causes avant le résultat.

    `links` : le front en fait de vrais liens. On exporte le CHEMIN CANONIQUE (« /neuf »),
    celui de la barre latérale, et non un href : c'est le front qui sait où il se trouve.
    """
    k, head, niv = f["kpi"], f["momentum"], f["niveau"]
    stock, tr = f["stock"], f["transformation"]

    # ---------------------- Bloc 1 : aujourd'hui ----------------------------------
    cards_act = [
        {"emoji": pastille(statut_seq(head["mises"]["value"])), "title": "Mises en chantier",
         "value": abrege(k["mises"]["current_12m"]) + " /12 m",
         "sub": ligne_momentum(head["mises"], trend_12m=k["mises"]["yoy_12m_pct"],
                               exact=k["mises"]["current_12m"]),
         "level": ligne_niveau(niv["mises"])},
        {"emoji": pastille(pill_ancien), "title": "Ventes de logements anciens",
         "value": abrege(k["tx"]["current_12m"]) + " /12 m",
         "sub": ligne_momentum(head["tx"], plateau=f["plateau_tx"], exact=k["tx"]["current_12m"]),
         "level": ligne_niveau(niv["tx"])},
    ]
    # L'ENCOURS ferme le bloc « aujourd'hui » : c'est le stock de logements neufs déjà
    # construits ou en cours qui attendent un acheteur. Un fournisseur le lit à l'envers
    # des autres cartes — un stock qui grossit ou qui s'écoule lentement est ce qui FAIT
    # reculer les mises en vente, donc les chantiers de demain. D'où un statut piloté par
    # le délai d'écoulement comparé à sa moyenne longue, et non par la variation du stock.
    if stock:
        cards_act.append({
            "emoji": pastille(stock["status"]), "title": "Stock de logements neufs à vendre",
            "value": milliers(stock["encours"]),
            "sub": (f"{stock['mois']:.0f} mois pour l'écouler au rythme actuel · "
                    f"{pct(stock['seq'])} vs le trimestre précédent"),
            "level": (f"{stock['moy_mois']:.0f} mois en moyenne depuis {stock['since']} — "
                      f"il faut aujourd'hui {abs(stock['ecart_pct']):.0f} % de temps de "
                      "plus pour écouler le stock")})

    # ------------ Bloc 2 : le carnet — ce qui est déjà autorisé (12-18 mois) ----------
    cards_carnet = [
        {"emoji": pastille(statut_seq(head["permis"]["value"])), "title": "Permis de construire",
         "value": abrege(k["permis"]["current_12m"]) + " /12 m",
         "sub": ligne_momentum(head["permis"], trend_12m=k["permis"]["yoy_12m_pct"],
                               exact=k["permis"]["current_12m"]),
         "level": ligne_niveau(niv["permis"])},
    ]
    # Le TAUX DE TRANSFORMATION est le pont entre les deux cartes de permis et de
    # chantiers : sans lui, « 376 k permis » se lit comme 376 k chantiers à venir. Il ne
    # prévoit rien — il décrit ce que les promoteurs font réellement de leurs autorisations.
    if tr:
        tr_status = ("down" if tr["now"] < tr["moy"] - 2
                     else ("up" if tr["now"] > tr["moy"] + 2 else "flat"))
        cards_carnet.append({
            "emoji": pastille(tr_status), "title": "Taux de transformation permis → chantiers",
            "value": f"{tr['now']:.1f} %".replace(".", ","),
            "sub": ("part des logements autorisés effectivement ouverts en chantier · "
                    + f"contre {tr['moy']:.1f} %".replace(".", ",")
                    + f" en moyenne sur {tr['ref_label']}"),
            "level": phrase_contrefactuel(tr, k["mises"]["current_12m"])})
    # ECLN est elle aussi publiée CVS-CJO : même lecture séquentielle que SIT@DEL — d'un
    # trimestre au précédent, sans repasser par le même trimestre de l'an dernier. La
    # tendance sur quatre trimestres joue ici le rôle du cumul 12 mois.
    e = f["ecln"]
    if e:
        cards_carnet.append({
            "emoji": pastille(statut_seq(e["seq"])),
            "title": "Réservations particuliers neuf (ECLN)",
            "value": milliers(e["dernier"]) + " /trim.",
            "sub": (pct(e["seq"]) + " vs le trimestre précédent · tendance 4 trimestres : "
                    + pct(e["tendance"])),
            "level": "la demande qui décide des mises en vente, donc des chantiers suivants"})

    # ---------------------- Bloc 3 : conditions de financement ----------------------
    cards_fin = []
    taux = f["taux"]
    if taux is None:
        cards_fin.append({"emoji": "⚪", "title": "Taux de crédit habitat (toutes durées)", "value": "—", "sub": ""})
    else:
        dr = taux["sur_un_an"]
        r_sub = "toutes durées confondues · sur un an : " + (pt(dr) if dr is not None else "—")
        cards_fin.append({"emoji": pastille(_statut_taux(dr)), "title": "Taux de crédit habitat",
                          "value": f"{taux['now']:.2f} %".replace(".", ","), "sub": r_sub})
    bls = f["bls"]
    if bls is None:
        cards_fin.append({"emoji": "⚪", "title": "Demande de crédit (banques)", "value": "—", "sub": ""})
    else:
        bls_word = ("attendue en hausse" if bls > 0
                    else ("attendue en baisse" if bls < -10 else "attendue stable"))
        cards_fin.append({"emoji": pastille(_statut_bls(bls)), "title": "Demande de crédit (banques)",
                          "value": f"{bls:+.0f}",
                          "sub": bls_word + " par les banques · enquête BLS, 3 prochains mois"})
    acc = f["accessibilite"]
    if acc:
        da = acc["sur_un_an"]
        a_status = "flat" if da is None else ("up" if da > 1 else ("down" if da < -1 else "flat"))
        gap15 = 100.0 - acc["now"]
        if gap15 > 0.5:
            a_txt = f"logement ≈ {gap15:.0f} % moins accessible qu'en 2015"
        elif gap15 < -0.5:
            a_txt = f"logement ≈ {-gap15:.0f} % plus accessible qu'en 2015"
        else:
            a_txt = "accessibilité au niveau de 2015"
        a_sub = a_txt + " · sur un an : " + (pt(da) if da is not None else "—")
        cards_fin.append({"emoji": pastille(a_status), "title": "Indice d'accessibilité",
                          "value": f"{acc['now']:.0f}", "sub": a_sub})

    # ---------------------- Bloc 4 : où va le marché ------------------------------
    cards_persp, persp_verdict = _cartes_perspective(f)
    if f["renovation"]:
        rn = f["renovation"]
        rn_last, rn_d = rn["now"], rn["delta"]
        rn_status = "flat" if rn_d is None else ("up" if rn_d > 0 else ("down" if rn_d < 0 else "flat"))
        rn_word = ("activité en baisse" if rn_last < 0
                   else ("activité en hausse" if rn_last > 0 else "activité stable"))
        cards_persp.append({"emoji": pastille(rn_status), "title": "Activité rénovation (second œuvre)",
                            "value": f"{rn_last:+.0f}", "sub": f"solde d'opinion INSEE — {rn_word}",
                            "level": ""})
    if f["prochain_jalon"]:
        j = f["prochain_jalon"]
        cards_persp.append({"emoji": "🗓️", "title": "Prochaine échéance aides",
                            "value": pd.Timestamp(j["date"]).strftime("%m/%Y"),
                            "sub": j["libelle"], "level": ""})

    return [
        {"title": "Aujourd'hui — ce qui se construit et se vend", "cards": cards_act,
         "links": [renvoi("🏗️", "Marché du neuf", "/neuf"),
                   renvoi("🏠", "Marché de l'ancien", "/ancien")]},
        {"title": "Le carnet — ce qui est déjà autorisé, pour les 12 à 18 prochains mois",
         "cards": cards_carnet,
         "links": [renvoi("🏗️", "Marché du neuf", "/neuf")]},
        {"title": "Ce qui pilote la suite — conditions de financement", "cards": cards_fin,
         "links": [renvoi("🏦", "Environnement & Financement", "/macro"),
                   renvoi("🏠", "Marché de l'ancien", "/ancien")]},
        {"title": "Où va le marché" + (f" — {persp_verdict}" if persp_verdict else ""),
         "cards": cards_persp,
         "links": [renvoi("📡", "Prévision & Scénarios", "/previsions"),
                   renvoi("📰", "Actualités & Aides", "/actualites")]},
    ]


def phrase_contrefactuel(tr: dict, chantiers_12m: float) -> str:
    """Ce que les permis auraient donné au taux de transformation habituel.

    La carte est l'endroit où un contrefactuel a sa place — le lecteur descendu jusque-là a
    le temps de le lire comme tel — à deux conditions : que la fenêtre de référence soit
    NOMMÉE, et que le nombre soit arrondi à la précision qu'il a vraiment (±18 000 à un
    écart-type du taux, donc le millier au mieux).

    Le SENS doit aussi sauter aux yeux. La formulation d'origine — « les permis donneraient
    321 k chantiers, soit 28 000 de PLUS qu'aujourd'hui » — se lisait comme une bonne
    nouvelle : l'œil accroche « de plus » et comprend croissance, alors que le fait est un
    MANQUE causé par un taux de conversion dégradé. Le signe arithmétique et le signe
    ressenti doivent pointer dans le même sens (tests/test_redaction.py).
    """
    manque = "manquent à l'appel" if tr["ecart"] > 0 else "de plus"
    return (f"au taux des années 2010, les permis des 12 derniers mois auraient "
            f"donné {abrege(tr['implied'])} chantiers au lieu de "
            f"{abrege(chantiers_12m)} — environ "
            f"{milliers(arrondi_millier(abs(tr['ecart'])))} {manque}")


def _cartes_perspective(f: dict):
    """La première carte du bloc porte la PRÉVISION DU SITE, pas la cible d'un tiers.

    Le bloc affichait « ventes 12 m vs cible BPCE 2026 » : le même 954 k que la carte
    d'activité, en vert parce qu'il dépasse la cible d'une banque, à un écran de la même
    valeur en orange. Un seul nombre, deux jugements. Le site A une prévision, backtestée
    et publiée sur « Prévisions passées » : ne pas la montrer ici revenait à garder son
    seul actif prospectif hors de sa porte d'entrée.

    Repli si le modèle n'est pas calibrable (macro incomplète) : la comparaison BPCE, qui
    ne dépend que de la série publiée. Le bloc ne reste jamais vide.
    """
    verdict = f["verdict"]
    cards = []
    if verdict:
        v_status = {"hausse": "up", "stable": "flat", "baisse": "down"}[verdict["direction"]]
        rel = verdict.get("reliability") or {}
        bits = [f"{pct(verdict['change_pct'])} vs les 12 derniers mois",
                f"fourchette {abrege(verdict['lo'])} – {abrege(verdict['hi'])}"]
        if rel.get("direction") is not None:
            bits.append(f"sens juste {rel['direction'] * 100:.0f} % du temps à cet horizon "
                        f"({rel['n']} millésimes)")
        # Construit depuis les CHAMPS du verdict, jamais par découpe de sa phrase :
        # `sentence` est destinée à être lue, sa forme peut changer.
        # Le titre NOMME la série projetée : sans elle, un lecteur du bâtiment y lit « le
        # marché », donc le sien, alors que le modèle ne projette QUE les ventes de
        # logements anciens. Il n'existe pas de projection des mises en chantier sur ce
        # site, et c'est délibéré (le lien permis → chantiers a été mesuré puis réfuté).
        ampleur = f"{abs(verdict['change_pct']):.0f} %".replace(".", ",")
        persp_verdict = {
            "hausse": f"ventes anciennes en hausse d'environ {ampleur} d'ici {verdict['target_month']}",
            "baisse": f"ventes anciennes en recul d'environ {ampleur} d'ici {verdict['target_month']}",
            "stable": f"ventes anciennes à peu près stables d'ici {verdict['target_month']}",
        }[verdict["direction"]]
        cards.append({
            "emoji": pastille(v_status),
            "title": f"Ventes anciennes projetées ({verdict['target_month']})",
            "value": abrege(verdict["predicted"]),
            "sub": " · ".join(bits),
            "level": "prévision du modèle du site, ajustée sur les taux, les intentions "
                     "d'achat et le chômage — voir « Prévisions passées » pour ses erreurs"})
        return cards, persp_verdict

    last_tx = f["tx12_dernier"]
    gap = (None if last_tx is None
           else (last_tx - BPCE_TX_ANCIEN_2026) / BPCE_TX_ANCIEN_2026 * 100.0)
    if gap is None:
        cards.append({"emoji": "⚪", "title": "Ventes 12 m vs cible BPCE 2026",
                      "value": "—", "sub": "", "level": ""})
        return cards, ""
    persp_verdict = ("marché au-dessus de la cible BPCE 2026" if gap > 3
                     else ("marché aligné sur la cible BPCE 2026" if gap >= -3
                           else "marché sous la cible BPCE 2026"))
    cards.append({
        "emoji": pastille("up" if gap > 3 else ("flat" if gap > -3 else "down")),
        "title": "Ventes 12 m vs cible BPCE 2026", "value": abrege(last_tx),
        "sub": pct(gap) + (" au-dessus de la cible BPCE 2026 (890 k)" if gap >= 0
                           else " sous la cible BPCE 2026 (890 k)"),
        "level": "modèle non calibrable à cette publication — repli sur la cible BPCE"})
    return cards, persp_verdict


COMMENT_LIRE = (
    "🟢 vent favorable · 🟠 stable ou signaux partagés · 🔴 vent contraire. "
    "Les blocs sont rangés par horizon et non par source : ce qui se consomme "
    "aujourd'hui, puis ce qui est déjà autorisé pour les 12 à 18 prochains mois, "
    "puis les conditions de crédit — qui sont les entrées du modèle, d'où leur "
    "place juste avant sa projection. "
    "Chaque carte porte deux horizons : le momentum court terme, puis la tendance "
    "sur douze mois. La fenêtre du momentum dépend de la série. Les permis et les "
    "mises en chantier (SIT@DEL) sont publiés corrigés des variations saisonnières "
    "et des jours ouvrables : on les lit donc sur les 3 derniers mois comparés aux "
    "3 précédents, sans repasser par une base vieille d'un an qui n'apporterait "
    "que son propre bruit. Les ventes anciennes (IGEDD) sont reconstruites à "
    "partir d'un cumul annuel, donc trop bruitées d'un mois sur l'autre : on les "
    "lit sur douze mois, complétées par la date depuis laquelle le niveau ne bouge "
    "plus. Le pilier « Neuf » ne moyenne pas ses deux étages : quand les permis "
    "(l'amont, qui alimente les chantiers 12 à 18 mois plus tard) et les mises en "
    "chantier (l'aval, qui consomme aujourd'hui) divergent, la pastille le dit. "
    "Les cartes d'activité portent une seconde ligne : le NIVEAU, c'est-à-dire "
    "l'écart à la moyenne d'une décennie de marché ordinaire (2010-2019, choisie "
    "parce qu'elle exclut la bulle de crédit de 2004-2007 et l'après-2020) et le "
    "rang de ce niveau dans toute l'histoire de la série. Une pente ne dit rien de "
    "l'altitude : un marché qui progresse vite depuis un creux profond reste un "
    "petit marché, et c'est le niveau qui dimensionne un outil industriel. Le bloc "
    "« Perspective » publie la projection du modèle du site à six mois, avec sa "
    "fourchette et la part de fois où le sens annoncé s'est avéré juste sur les "
    "millésimes rétro-simulés — ses erreurs détaillées sont sur « Prévisions "
    "passées ». Pour les taux et l'accessibilité, 🟢 signifie des conditions qui "
    "s'améliorent (taux en baisse), pas une valeur qui monte. Chiffres nationaux.")
