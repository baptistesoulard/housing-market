"""Helpers d'analyse en pandas.

Statut depuis la phase 2 du refactor compute : les agrégations (`aggregate_sitadel`,
`aggregate_ventes_ancien`, `calculate_rolling_12m`, `calculate_rolling`) ne sont plus sur
le chemin d'exécution — les trois surfaces (app.py, web_export.py, report.py) passent par
la couche SQL `queries.py`. Elles sont CONSERVÉES à dessein comme **implémentation de
référence** : `tests/test_queries_parity.py` compare chaque requête DuckDB à son
équivalent pandas ici. Les supprimer supprimerait le filet de sécurité de la migration.

Les helpers de POST-agrégation (`calculate_kpis`, `momentum_metrics`,
`build_market_commentary`) restent eux bel et bien appelés au runtime : ils opèrent sur
les petites frames déjà agrégées que renvoie la couche SQL.
"""
import pandas as pd

def aggregate_sitadel(df_sitadel, types=None):
    """
    Aggregates SIT@DEL data by Date.
    If 'types' is provided, filters for those housing types.
    """
    df = df_sitadel.copy()
    if types:
        df = df[df["Type"].isin(types)]
        
    df_agg = df.groupby("Date")[["Permis", "MisesEnChantier"]].sum().reset_index()
    df_agg = df_agg.sort_values("Date")
    return df_agg

def aggregate_ventes_ancien(df_ventes_ancien, types=None):
    """
    Aggregates existing-home sales (IGEDD) data by Date.
    If 'types' is provided, filters for those property types.
    """
    df = df_ventes_ancien.copy()
    if types:
        df = df[df["Type"].isin(types)]
        
    df_agg = df.groupby("Date")[["Transactions"]].sum().reset_index()
    df_agg = df_agg.sort_values("Date")
    return df_agg

def calculate_rolling_12m(df, value_cols):
    """
    Calculates the 12-month rolling sum (cumul glissant sur 12 mois) for the given column names.
    Appends columns with suffix '_12m'.
    Assumes df is ordered chronologically by 'Date' (at monthly interval).
    """
    df_rolling = df.copy()
    for col in value_cols:
        # Since frequency is monthly, window=12 calculates the 12-month rolling sum
        # min_periods=12 ensures we don't display incomplete rolling sums at the start, or min_periods=1 to show what's available
        df_rolling[f"{col}_12M"] = df_rolling[col].rolling(window=12, min_periods=12).sum()
    return df_rolling

def calculate_rolling(df, value_cols, window):
    """
    Calculates the N-month rolling sum for the given columns, appending columns with
    suffix '_{window}M' (e.g. '_6M', '_12M'). Assumes monthly-ordered 'Date'.
    """
    df_rolling = df.copy()
    for col in value_cols:
        df_rolling[f"{col}_{window}M"] = df_rolling[col].rolling(window=window, min_periods=window).sum()
    return df_rolling

# --- Base 100 : la convention est celle de l'INSEE, pas la nôtre ---
# Tous les indices publiés par le site sont ramenés à 100 sur la MOYENNE ANNUELLE 2015.
# C'est déjà la base des séries qu'on reçoit telles quelles (indices Notaires-INSEE des
# prix anciens, IPLN pour le neuf) et celle de la capacité d'emprunt. Y ramener aussi les
# séries que le site indexe lui-même a un effet précis : un lecteur peut poser deux
# graphiques côte à côte et lire l'écart entre les courbes, ce qu'une base propre à chaque
# graphique interdit. Une base « récente » (le premier mois commun de 2022, retenu
# initialement) donnait en plus un point de comparaison sans signification — un mois
# quelconque du creux post-2021.
BASE_YEAR = 2015
BASE_LABEL = "moyenne 2015"
BASE_LABEL_EN = "2015 average"


def base_100(df, value_cols, year=BASE_YEAR, date_col="Date"):
    """Le dénominateur base 100 de chaque colonne : sa moyenne sur `year`, ou None.

    Renvoie {colonne: float|None}. None quand l'année de référence n'est pas COMPLÈTE :
    une « moyenne annuelle » calculée sur trois mois n'en est pas une, elle emporterait la
    saisonnalité de ces trois mois-là dans le dénominateur de toute la série. Mieux vaut
    ne pas indexer une courbe que l'indexer sur une base fausse — l'appelant affiche alors
    les niveaux, et le manque se voit.

    Sur une série déjà en cumul 12 mois, la moyenne des 12 valeurs de 2015 est bien la
    moyenne annuelle au sens INSEE. Prendre la seule valeur de décembre (= le total de
    l'année civile) serait plus direct mais ferait dépendre toute la base d'un unique
    point, révisions comprises."""
    an = df[df[date_col].dt.year == year]
    bases = {}
    for col in value_cols:
        serie = an[col].dropna() if col in an.columns else pd.Series(dtype="float64")
        moyenne = float(serie.mean()) if len(serie) == 12 else None
        bases[col] = moyenne if moyenne else None      # 0 est aussi inutilisable
    return bases


# --- SIT@DEL housing-type groupings (individual vs collective) ---
# A single individual house carries far more "second-œuvre" content (fermetures,
# menuiseries, sécurité, domotique) than a collective dwelling, so these groupings
# isolate the individual-housing signal that drives building-materials demand.
SITADEL_INDIVIDUEL_PUR = ["Maison Individuelle Pure"]
SITADEL_INDIVIDUEL = ["Maison Individuelle Pure", "Maison Individuelle Groupée"]
SITADEL_COLLECTIF = ["Logement Collectif", "Logement en Résidence"]


def momentum_metrics(df, value_col, date_col="Date"):
    """Momentum ratios in the BPCE style, from a monthly series of `value_col`:
      - roll12_yoy: latest 12-month sum vs the previous 12-month sum ("+X % sur 12 mois
        par rapport aux 12 mois précédents");
      - last3_yoy: sum of the last 3 months vs the same 3 calendar months a year earlier
        ("+X % sur les 3 derniers mois par rapport aux mêmes mois n-1") — the metric BPCE
        uses to flag an acceleration or a "coup d'arrêt";
      - last3_seq: sum of the last 3 months vs the 3 months IMMEDIATELY BEFORE — the
        sequential read, which carries no year-old base (see `headline_momentum`).
    Returns {"roll12_yoy", "last3_yoy", "last3_seq"}, each float|None. Assumes monthly.
    """
    s = df.dropna(subset=[value_col]).sort_values(date_col)
    vals = s[value_col].values
    out = {"roll12_yoy": None, "last3_yoy": None, "last3_seq": None}
    if len(vals) >= 24:
        last12, prev12 = vals[-12:].sum(), vals[-24:-12].sum()
        if prev12 > 0:
            out["roll12_yoy"] = round((last12 - prev12) / prev12 * 100.0, 1)
    if len(vals) >= 15:
        last3, prev3 = vals[-3:].sum(), vals[-15:-12].sum()
        if prev3 > 0:
            out["last3_yoy"] = round((last3 - prev3) / prev3 * 100.0, 1)
    if len(vals) >= 6:
        last3, before3 = vals[-3:].sum(), vals[-6:-3].sum()
        if before3 > 0:
            out["last3_seq"] = round((last3 - before3) / before3 * 100.0, 1)
    return out


# ---------------------------------------------------------------------------------
# Quelle lecture de momentum pour quelle série — un choix de MESURE, pas de goût
# ---------------------------------------------------------------------------------
# SIT@DEL est chargée en `NAT_SERIES == "CVS-CJO"` (data_manager.py) : elle est DÉJÀ
# corrigée des variations saisonnières et des jours ouvrables. Or comparer « les 3
# derniers mois aux mêmes mois de l'an dernier » n'a qu'une raison d'être : neutraliser
# la saisonnalité. Sur une série déjà corrigée, cette comparaison ne neutralise rien et
# importe gratuitement une base vieille de douze mois — dont le bruit devient tout le
# signal. Mesuré sur les mises en chantier à juin 2026 : le « 3 mois vs n-1 » affichait
# +28,4 % (dont ~8 points dus au seul creux d'avril-juin 2025, base 6 % sous la moyenne
# de l'année) et perdait 13,8 points en un mois — la sortie du pic de mars 2026 de la
# fenêtre — pendant que la tendance 12 mois bougeait de 0,3 point. La même série lue
# séquentiellement disait −2,0 % : le rythme avait cessé de monter.
#
# L'IGEDD (ventes anciennes) est l'inverse : elle est reconstruite en différenciant un
# cumul 12 mois, donc ses flux mensuels sont très bruités. Mesuré : le séquentiel y saute
# de 10 points par mois en moyenne (contre 1,6 pour le cumul 12 mois) — inutilisable.
# Sa lecture honnête est le niveau 12 mois, complété par `plateau_months` qui dit depuis
# quand ce niveau ne bouge plus.
#
# D'où DEUX régimes, et une fonction qui porte le choix pour les deux surfaces (app.py
# et web_export.py) afin qu'elles ne puissent pas en retenir un chacune.
ADJUSTED_SEQUENTIAL = "seq"      # série CVS : lire le séquentiel
RAW_TWELVE_MONTHS = "roll12"     # série brute ou reconstruite : lire le cumul 12 mois


def headline_momentum(mom, regime):
    """Le momentum à PUBLIER pour une série, selon son régime de mesure.

    `mom` est un dict de `momentum_metrics`, `regime` l'une des deux constantes
    ci-dessus. Renvoie {"value": float|None, "key": str, "window": str} — `window` étant
    l'intitulé court de la fenêtre, à afficher tel quel à côté du chiffre.
    """
    if regime == ADJUSTED_SEQUENTIAL:
        return {"value": mom.get("last3_seq"), "key": "last3_seq",
                "window": "sur 3 mois vs les 3 précédents"}
    return {"value": mom.get("roll12_yoy"), "key": "roll12_yoy",
            "window": "sur 12 mois vs les 12 précédents"}


def plateau_months(df, value_col, date_col="Date", tol_pct=1.0, window=12):
    """Depuis combien de mois le cumul `window` mois ne bouge plus.

    Remonte la série tant que le cumul reste dans ±`tol_pct` % de sa valeur actuelle.
    Répond à la question qu'un taux de croissance annuel ne peut pas poser : « +5,2 %
    sur douze mois » décrit une croissance qui peut très bien s'être arrêtée il y a six
    mois, la base étant basse. Le plateau, lui, se voit tout de suite.

    Renvoie {"months": int, "since": Timestamp, "level": float} ou None si la série est
    trop courte, ou si elle bouge encore (moins de trois mois dans la tolérance).
    """
    s = df.dropna(subset=[value_col]).sort_values(date_col)
    if len(s) < window + 3:
        return None
    roll = s[value_col].rolling(window).sum()
    dates = s[date_col].values
    valid = roll.notna().values
    if not valid.any():
        return None
    vals = roll.values
    last_i = len(vals) - 1
    level = float(vals[last_i])
    if level <= 0:
        return None
    i = last_i
    while i - 1 >= 0 and valid[i - 1] and abs(vals[i - 1] / level - 1.0) * 100.0 <= tol_pct:
        i -= 1
    months = last_i - i
    if months < 3:
        return None
    return {"months": months, "since": pd.Timestamp(dates[i]), "level": level}


# Seuil de bascule du momentum séquentiel, en points de %. Plus large que le ±1 utilisé
# sur les taux annuels, et pour une raison mesurée : le 3 mois séquentiel saute en moyenne
# de 5,2 pt par mois sur les permis et de 3,5 pt sur les chantiers. À ±1 la pastille
# changerait de couleur au bruit ; à ±2 elle ne bouge que sur un mouvement qui dépasse la
# moitié de l'écart mensuel typique.
SEQ_TOL = 2.0


def _tri(v, tol=SEQ_TOL):
    """Trois états à partir d'un pourcentage (au-dessus / dans / sous la tolérance)."""
    if v is None:
        return "flat"
    return "up" if v > tol else ("down" if v < -tol else "flat")


def pillar_neuf(mom_permis, mom_mises, tol=SEQ_TOL, lang="FR"):
    """Statut du pilier « Neuf » à partir de SES DEUX ÉTAGES, sans les moyenner.

    L'ancienne règle faisait la moyenne arithmétique des deux taux de croissance
    (`(permis + chantiers) / 2`). Deux objections, et c'est la seconde qui compte :
    la moyenne de deux pourcentages portant sur des séries d'ampleurs différentes n'a pas
    de sens arithmétique ; surtout, elle DÉTRUIT l'information utile. Les permis sont
    l'amont (ce qui alimentera les chantiers de 12 à 18 mois plus tard) et les mises en
    chantier l'aval (ce qui consomme des matériaux aujourd'hui) : quand les deux
    divergent, c'est précisément le fait qu'un industriel doit voir. En juin 2026 la
    moyenne rendait « +9,7 % → en reprise » là où les permis reculaient de 9,8 % et les
    chantiers de 2,0 %.

    Renvoie {"status", "word", "kind", "amont", "aval"}. Le statut d'une divergence est
    « flat » : ni vent franchement favorable ni vent franchement contraire — c'est le mot
    qui porte l'information, et la puce « à retenir » qui en donne le mécanisme.
    """
    amont = _tri(mom_permis.get("last3_seq"), tol)
    aval = _tri(mom_mises.get("last3_seq"), tol)
    if amont == aval:
        kind = {"up": "reprise", "flat": "stable", "down": "repli"}[amont]
        word = {"reprise": ("en reprise", "recovering"),
                "stable": ("stable", "flat"),
                "repli": ("en repli", "declining")}[kind]
        status = amont
    elif amont == "down":
        kind, word, status = "amont_repli", ("amont en repli", "upstream declining"), "flat"
    elif amont == "up":
        kind, word, status = "amont_reprise", ("amont en reprise", "upstream recovering"), "flat"
    elif aval == "up":
        kind, word, status = "aval_hausse", ("chantiers en hausse", "starts rising"), "flat"
    else:
        kind, word, status = "aval_repli", ("chantiers en repli", "starts declining"), "flat"
    return {"status": status, "kind": kind, "amont": amont, "aval": aval,
            "word": word[0] if lang == "FR" else word[1]}


def _trend_phrase(v, lang="FR"):
    """Qualitative wording for a growth rate (%), used in the auto commentary."""
    if v is None:
        return "—"
    if lang == "EN":
        return ("accelerating sharply" if v > 5 else "rising" if v > 1
                else "broadly stable" if v >= -1 else "slowing" if v >= -5 else "falling sharply")
    return ("accélère nettement" if v > 5 else "progresse" if v > 1
            else "se stabilise" if v >= -1 else "ralentit" if v >= -5 else "recule nettement")


def build_market_commentary(kpi_permis, kpi_mises, kpi_tx,
                            mom_permis, mom_mises, mom_tx,
                            mom_indiv_pur=None, lang="FR"):
    """Short data-driven narrative (3 sentences, BPCE « à retenir » style) summarising new
    construction, existing-home sales and the overall momentum. Inputs are the dicts from
    calculate_kpis (current_12m, yoy_12m_pct) and momentum_metrics (roll12_yoy, last3_yoy).
    Fully derived from the numbers, so it stays in sync with the KPIs."""
    def pct(v):
        if v is None:
            return "—"
        s = f"{v:+.1f}%"
        return s.replace(".", ",") if lang == "FR" else s

    def th(v):
        return f"{int(v):,}".replace(",", " ")

    p_yoy, m_yoy, t_yoy = kpi_permis["yoy_12m_pct"], kpi_mises["yoy_12m_pct"], kpi_tx["yoy_12m_pct"]
    m3, t3 = mom_mises.get("last3_yoy"), mom_tx.get("last3_yoy")
    ip3 = mom_indiv_pur.get("last3_yoy") if mom_indiv_pur else None

    if lang == "EN":
        s1 = (f"New construction is {_trend_phrase(p_yoy, lang)}: building permits {pct(p_yoy)} and "
              f"housing starts {pct(m_yoy)} over 12 months (starts {pct(m3)} over the last 3 months "
              f"vs a year earlier"
              + (f", led by detached houses at {pct(ip3)}" if ip3 is not None else "") + ").")
        s2 = (f"Existing-home sales stand at {th(kpi_tx['current_12m'])} over 12 months ({pct(t_yoy)}), "
              f"but momentum is {_trend_phrase(t3, lang)} at {pct(t3)} over the last 3 months vs a year earlier.")
        if (t3 is not None and t3 < 0) and (m3 is not None and m3 > 0):
            s3 = ("Leading construction indicators are turning up while existing-home transactions cool "
                  "— a lead the second-œuvre pipeline should follow with its usual lag.")
        elif t3 is not None and t3 < 0:
            s3 = "The recent slowdown in transactions warrants caution on near-term demand."
        else:
            s3 = "Overall, indicators point to a gradual recovery in activity."
    else:
        s1 = (f"La construction neuve {_trend_phrase(p_yoy, lang)} : permis {pct(p_yoy)} et mises en "
              f"chantier {pct(m_yoy)} sur 12 mois (mises en chantier {pct(m3)} sur 3 mois vs un an plus tôt"
              + (f", portées par l'individuel pur à {pct(ip3)}" if ip3 is not None else "") + ").")
        s2 = (f"Les ventes de logements anciens s'établissent à {th(kpi_tx['current_12m'])} sur 12 mois "
              f"({pct(t_yoy)}), mais la dynamique {_trend_phrase(t3, lang)} : {pct(t3)} sur les 3 derniers "
              f"mois par rapport à l'an dernier.")
        if (t3 is not None and t3 < 0) and (m3 is not None and m3 > 0):
            s3 = ("Les indicateurs avancés de construction se redressent tandis que les transactions "
                  "anciennes ralentissent — une avance que la demande de second œuvre devrait suivre "
                  "avec son décalage habituel.")
        elif t3 is not None and t3 < 0:
            s3 = "Le ralentissement récent des transactions invite à la prudence sur la demande à court terme."
        else:
            s3 = "Globalement, les indicateurs pointent vers une reprise graduelle de l'activité."
    return " ".join([s1, s2, s3])


def calculate_kpis(df, value_col, date_col="Date"):
    """
    Calculates key metrics for indicator summary cards:
    - Current Value
    - Current 12M Cumulative Value
    - Year-over-Year (YoY) Change for 12M Cumulative Value (comparing latest month to same month last year)
    - Year-over-Year (YoY) Change for monthly value
    """
    df_sorted = df.sort_values(date_col).copy()
    if len(df_sorted) < 13:
        return {
            "current_val": 0,
            "current_12m": 0,
            "yoy_12m_pct": 0.0,
            "yoy_monthly_pct": 0.0,
            "trend": "Stable"
        }
        
    latest_row = df_sorted.iloc[-1]
    latest_date = latest_row[date_col]
    
    # 12-month rolling column
    col_12m = f"{value_col}_12M"
    if col_12m not in df_sorted.columns:
        df_sorted = calculate_rolling_12m(df_sorted, [value_col])
        latest_row = df_sorted.iloc[-1]
        
    current_val = latest_row[value_col]
    current_12m = latest_row[col_12m]
    
    # Look for 12 months ago row
    date_1y_ago = latest_date - pd.DateOffset(years=1)
    # Find matching row closest to date_1y_ago
    row_1y_ago_candidates = df_sorted[df_sorted[date_col] == date_1y_ago]
    
    if len(row_1y_ago_candidates) > 0:
        row_1y_ago = row_1y_ago_candidates.iloc[0]
        val_1y_ago = row_1y_ago[value_col]
        val_12m_1y_ago = row_1y_ago[col_12m]
        
        yoy_monthly_pct = ((current_val - val_1y_ago) / val_1y_ago * 100.0) if val_1y_ago > 0 else 0.0
        yoy_12m_pct = ((current_12m - val_12m_1y_ago) / val_12m_1y_ago * 100.0) if pd.notna(val_12m_1y_ago) and val_12m_1y_ago > 0 else 0.0
    else:
        yoy_monthly_pct = 0.0
        yoy_12m_pct = 0.0
        
    # Determine general trend
    if yoy_12m_pct > 2.0:
        trend = "Haussier"
    elif yoy_12m_pct < -2.0:
        trend = "Baissier"
    else:
        trend = "Stable"
        
    return {
        "current_val": int(current_val) if not pd.isna(current_val) else 0,
        "current_12m": int(current_12m) if not pd.isna(current_12m) else 0,
        "yoy_12m_pct": round(yoy_12m_pct, 1),
        "yoy_monthly_pct": round(yoy_monthly_pct, 1),
        "trend": trend
    }
