"""Le verdict du modèle et la fiabilité qui l'accompagne — partagés par trois surfaces.

La Synthèse (bloc « Où va le marché »), la page « Prévision & Scénarios » (bloc de tête) et
le bandeau de l'accueil publient le MÊME chiffre, calculé une fois par exécution
(`partage`). Tout ce qui juge ce chiffre — erreur par plage d'horizon, fiabilité dans le
régime de taux courant — vit ici aussi, parce que c'est l'horizon du verdict qui décide à
quel rang de l'archive on le mesure.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from commun import MOIS_FR, arrondi_millier

import forecast_archive as fa                   # noqa: E402
import queries as q                             # noqa: E402
from api import engine                          # noqa: E402  (moteur de prévision, sans Flask)


#: Le verdict vise un mois situé à six mois du LECTEUR — pas du millésime de données.
#:
#: C'est un correctif du 2026-09-03, et il compte. L'horizon était figé à 6 rangs de la
#: série projetée, or celle-ci démarre au dernier mois OBSERVÉ, et l'IGEDD publie avec
#: environ trois mois de retard : en septembre 2026, le « verdict à six mois » visait
#: décembre 2026, soit trois mois devant le lecteur. Deux conséquences, toutes deux
#: mauvaises — la page annonçait un horizon qu'elle ne tenait pas, et elle le prenait là
#: où le modèle est le plus faible (+4,2 % d'erreur évitée à l'horizon 6, contre +24,2 %
#: à 9 et +34,4 % à 11).
#:
#: ⚠️ Allonger l'horizon AMÉLIORE mécaniquement la fiabilité affichée. Ce n'est pas la
#: raison du changement et il ne faut pas le présenter ainsi : la raison est que « six
#: mois » doit vouloir dire six mois pour qui lit. La page continue de publier la table
#: complète par horizon, y compris les rangs 1 à 5 où le modèle PERD contre une simple
#: reconduction — c'est ce qui empêche ce réglage d'être une sélection d'horizon flatteuse.
MOIS_DEVANT = 6

#: Plancher : jamais un horizon où le modèle est battu par la reconduction du dernier
#: chiffre connu (voir `crossover_horizon`, publié par la page « Prévisions passées »).
HORIZON_MIN = 6


def _verdict_horizon(projection: dict) -> int | None:
    """Le rang de la série projetée que le verdict doit viser.

    Deux bornes, et elles peuvent se contredire :
      * le PLANCHER (`HORIZON_MIN`) — en deçà, recopier le dernier chiffre connu
        fait mieux, donc publier le modèle là serait le desservir ;
      * le PLAFOND (`informative_months`) — au-delà, tous les prédicteurs sont reportés à
        plat et la trajectoire RÉPÈTE sa dernière valeur. Publier un mois au-delà
        donnerait un nombre que le modèle n'a pas calculé, seulement recopié.

    Entre les deux, on prend le premier mois situé à `MOIS_DEVANT` du jour de
    publication. Si le plafond est sous le plancher, il n'y a pas d'horizon honnête à
    publier et on rend None — l'appelant retombe sur son repli.
    """
    series = projection.get("series") or []
    if not series:
        return None
    plafond = min(len(series), int(projection.get("informative_months") or len(series)))
    if plafond < HORIZON_MIN:
        return None
    cible = (pd.Timestamp.today().normalize().replace(day=1)
             + pd.DateOffset(months=MOIS_DEVANT))
    rang = next((i for i, pt in enumerate(series, 1)
                 if pd.Timestamp(pt["date"]) >= cible), None)
    if rang is None:                       # la cible dépasse la série : dernier mois utile
        rang = plafond
    return max(HORIZON_MIN, min(rang, plafond))


def _verdict(projection: dict, con) -> dict | None:
    """La phrase que la page ne disait pas : où va le marché, et à quel point s'y fier.

    Jusqu'ici « Prévision & Scénarios » publiait les ENTRAILLES du modèle — un R², une
    MAPE, trois coefficients OLS, un z-score d'intentions d'achat — et nulle part sa
    conclusion. Ce bloc la calcule, avec la seule mesure de fiabilité qu'un lecteur non
    statisticien peut utiliser telle quelle : la part de fois où le SENS annoncé à cet
    horizon s'est avéré le bon.

    Tout est dérivé des nombres, donc rien à maintenir à la main — c'est la contrainte
    qui interdisait de mettre ce verdict dans le chapeau statique de la page.
    """
    series = projection.get("series") or []
    horizon = _verdict_horizon(projection)
    if horizon is None:
        return None
    point = series[horizon - 1]
    base = projection.get("last_observed")
    if not base:
        return None
    change = (point["predicted"] / base - 1) * 100

    horizons = fa.by_horizon(fa.evaluate(
        fa.read().query("kind == 'retro'"), q.transactions_run_rate(con)))
    row = horizons[horizons["horizon"] == horizon]
    reliability = None if row.empty else {
        "horizon": horizon,
        "direction": round(float(row["direction"].iloc[0]), 3),
        "mape": round(float(row["mape"].iloc[0]), 2),
        "naive_mape": round(float(row["naive_mape"].iloc[0]), 2),
        "n": int(row["n"].iloc[0]),
    }

    # Le seuil de 1,5 % n'est pas cosmétique : l'erreur du modèle à six mois est de
    # l'ordre de 5,7 %, donc annoncer une variation plus petite que ça reviendrait à
    # commenter son propre bruit. En deçà, le verdict dit « stable » — et c'est une
    # information, pas une dérobade.
    if abs(change) < 1.5:
        sens, phrase = "stable", "devrait rester à peu près stable"
    elif change > 0:
        sens, phrase = "hausse", f"devrait progresser d'environ {abs(change):.0f} %"
    else:
        sens, phrase = "baisse", f"devrait reculer d'environ {abs(change):.0f} %"

    target = pd.Timestamp(point["date"])
    mois_cible = f"{MOIS_FR[target.month - 1]} {target.year}"
    # Combien de mois séparent le LECTEUR de la cible : c'est ce nombre-là qui rend la
    # phrase honnête, pas le rang dans la série projetée.
    aujourdhui = pd.Timestamp.today().normalize().replace(day=1)
    devant = max(1, (target.year - aujourdhui.year) * 12 + target.month - aujourdhui.month)

    # La tendance était énoncée en VARIATION seule (« reculer d'environ 7 % »), sans son
    # point de départ : le lecteur devait aller chercher le niveau actuel dans une autre
    # puce pour savoir de quoi on parlait. Un « de X à Y » se lit d'un trait et porte la
    # direction dans sa forme même.
    depart, arrivee = arrondi_millier(base), arrondi_millier(point["predicted"])
    ent = lambda v: f"{int(v):,}".replace(",", " ")      # 878 708 -> « 879 000 », pas « 879 k »
    trajet = f"de {ent(depart)} à {ent(arrivee)} ventes sur douze mois"
    corps = (f"devrait rester à peu près stable, autour de {ent(arrivee)} ventes sur "
             f"douze mois" if sens == "stable" else f"{phrase}, en passant {trajet}")
    # Un nombre en chiffres au milieu d'une phrase de prose se lit mal quand il est petit.
    _LETTRES = ("", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf",
                "dix", "onze", "douze")
    devant_txt = _LETTRES[devant] if devant < len(_LETTRES) else str(devant)

    return {
        "horizon": horizon,
        "months_ahead": devant,
        "target_month": mois_cible,
        "target_date": target.strftime("%Y-%m-%d"),
        "direction": sens,
        "change_pct": round(change, 1),
        "from_value": int(round(base)),
        "predicted": int(round(point["predicted"])),
        "lo": int(round(point["lo"])),
        "hi": int(round(point["hi"])),
        "sentence": (f"D'ici {mois_cible}, dans {devant_txt} mois, le marché des "
                     f"logements anciens {corps}."),
        "reliability": reliability,
    }


#: Verdict du modèle, calculé UNE fois par exécution et partagé par les deux pages qui en
#: ont besoin — la Synthèse pour son bloc « Perspective », « Prévision & Scénarios » pour
#: son bloc de tête. Le recalculer de chaque côté rejouerait l'ajustement complet des deux
#: étages pour aboutir, par construction, au même nombre ; surtout, rien ne garantirait
#: qu'il le reste si les deux chemins venaient à diverger. Un seul calcul, un seul chiffre
#: sur les deux pages — c'est exactement ce que l'axe compute existe pour garantir.
_VERDICT_CACHE: dict = {}


#: Plages d'horizon du seuil d'entrée d'un prédicteur (voir REFUTATIONS et la page de
#: prévision). Les mêmes quatre partout : c'est le découpage sur lequel le seuil est écrit.
_HORIZON_BLOCS = [("1-3", 1, 3), ("4-6", 4, 6), ("7-12", 7, 12), ("13-18", 13, 18)]


def blocs_horizon(con) -> list:
    """Erreur du modèle et de la référence naïve, par plage d'horizon, depuis l'archive.

    Ces chiffres étaient ÉCRITS EN DUR dans le texte de la page (« il perd contre une
    prévision naïve en deçà de six mois et lui prend 40 % d'erreur au-delà d'un an ») :
    exacts au jour où ils ont été tapés, et régénérés par rien. Ils viennent maintenant de
    l'archive, comme le verdict — mêmes 210 millésimes, mêmes huit épisodes.
    """
    rows = fa.by_horizon(fa.evaluate(
        fa.read().query("kind == 'retro'"), q.transactions_run_rate(con)))
    if rows.empty:
        return {"blocks": [], "crossover": None}
    out = []
    for label, lo, hi in _HORIZON_BLOCS:
        sub = rows[(rows["horizon"] >= lo) & (rows["horizon"] <= hi)]
        if sub.empty:
            continue
        mape, naive = float(sub["mape"].mean()), float(sub["naive_mape"].mean())
        out.append({"bloc": label, "mape": round(mape, 2), "naive_mape": round(naive, 2),
                    "skill_pct": round((1 - mape / naive) * 100, 1) if naive else None})
    # Premier horizon où le modèle passe devant la prévision naïve. MÊME définition que
    # `crossover_horizon` de la page « Prévisions passées » (premier skill > 0) : deux
    # définitions du même seuil finiraient par donner deux chiffres.
    crossover = next((int(r["horizon"]) for _, r in rows.sort_values("horizon").iterrows()
                      if r["skill"] is not None and float(r["skill"]) > 0), None)
    return {"blocks": out, "crossover": crossover}


#: Fenêtre sur laquelle on mesure si le taux de crédit BOUGE. Douze mois : c'est l'échelle
#: à laquelle la transmission du taux au marché se joue (le décalage estimé vaut 10 mois),
#: et c'est aussi la fenêtre du cumul que le modèle prédit.
_REGIME_WINDOW_M = 12
_REGIME_LABELS = {"calme": "taux quasi stables", "inter": "taux en mouvement modéré",
                  "agite": "taux en fort mouvement"}


def fiabilite_regime(con, horizon: int = HORIZON_MIN) -> dict | None:
    """Fiabilité du modèle DANS LE RÉGIME DE TAUX COURANT — la ventilation qui manquait.

    La page publie deux ventilations de sa performance : par horizon et par épisode. Les
    deux décrivent le passé. Aucune ne dit ce que vaut le chiffre qu'on lit AUJOURD'HUI.

    Or la performance du modèle dépend massivement d'une seule chose : le taux de crédit
    bouge-t-il ? Mesuré sur 209 millésimes, corrélation de rang entre l'erreur évitée et
    l'amplitude du mouvement du taux sur douze mois : **+0,52**. Découpé en terciles, le
    modèle passe de −6,9 % d'erreur évitée (taux quasi stables) à +47,0 % (fort mouvement),
    et son taux de bon sens à six mois de 55 % à 97 %. Le « 72 % » affiché à côté du verdict
    est une moyenne de ces deux mondes — exacte, et trompeuse dans les deux sens.

    Ce n'est pas un réglage : le mécanisme était posé avant la mesure (l'étage 2 n'a qu'un
    canal, le coût du crédit) et la relation est monotone sur trois terciles de ~1 200
    points chacun.

    Le `percentile` est publié à CÔTÉ du libellé, et ce n'est pas décoratif : à la dernière
    mesure le mouvement courant tombait à 0,02 point de la borne calme/intermédiaire. Une
    étiquette seule cacherait cette fragilité ; le centile la montre.
    """
    pts = q.macro_series(con, "Credit_Logement_Taux_Interet")
    if not pts:
        return None
    taux = pd.Series({pd.Timestamp(p["date"]): p["value"] for p in pts}).sort_index()
    if len(taux) < _REGIME_WINDOW_M + 1:
        return None

    def _mouvement(d):
        av = taux.index[taux.index <= d - pd.DateOffset(months=_REGIME_WINDOW_M)]
        return None if len(av) == 0 else abs(float(taux.asof(d)) - float(taux.loc[av[-1]]))

    ev = fa.evaluate(fa.read().query("kind == 'retro'"), q.transactions_run_rate(con))
    if ev.empty:
        return None
    ev = ev.copy()
    ev["_v"] = pd.to_datetime(ev["data_vintage"])
    ev["_mv"] = ev["_v"].map(_mouvement)
    ev = ev.dropna(subset=["_mv"])
    if ev.empty:
        return None

    par_millesime = ev.groupby("_v")["_mv"].first()
    t1, t2 = par_millesime.quantile([1 / 3, 2 / 3])
    now = _mouvement(taux.index[-1])
    if now is None:
        return None
    kind = "calme" if now <= t1 else ("inter" if now <= t2 else "agite")

    sel = ev[ev["_mv"] <= t1] if kind == "calme" else (
        ev[ev["_mv"] > t2] if kind == "agite" else ev[(ev["_mv"] > t1) & (ev["_mv"] <= t2)])
    if sel.empty:
        return None
    # Erreurs AGRÉGÉES, jamais une moyenne de ratios : quand la référence naïve est
    # minuscule (ce qui arrive précisément en régime calme), un ratio par point explose et
    # sa moyenne devient ininterprétable — le premier calcul de cette mesure rendait
    # −110 % pour cette raison.
    mape, naive = float(sel["ape"].mean()), float(sel["naive_ape"].mean())
    hit = (np.sign(sel["predicted"] - sel["naive"])
           == np.sign(sel["realized"] - sel["naive"])).astype(float)
    h = sel[sel["horizon"] == horizon]
    hit_h = (np.sign(h["predicted"] - h["naive"])
             == np.sign(h["realized"] - h["naive"])).astype(float) if not h.empty else None
    return {
        "kind": kind,
        "label": _REGIME_LABELS[kind],
        "mouvement_pt": round(float(now), 2),
        "percentile": round(float((par_millesime <= now).mean()) * 100),
        "fenetre_mois": _REGIME_WINDOW_M,
        "n": int(len(sel)),
        "mape": round(mape, 2),
        "naive_mape": round(naive, 2),
        "skill_pct": round((1 - mape / naive) * 100, 1) if naive else None,
        "direction": round(float(hit.mean()), 3),
        "direction_horizon": (None if hit_h is None or hit_h.empty
                              else round(float(hit_h.mean()), 3)),
        "horizon": horizon,
    }


def partage(con):
    """`_verdict` mémoïsé pour la durée du process. None si le modèle n'est pas calibrable."""
    if "value" not in _VERDICT_CACHE:
        engine.reset()
        try:
            _VERDICT_CACHE["value"] = _verdict(engine.projection(), con)
        except engine.EngineUnavailable:
            _VERDICT_CACHE["value"] = None
        finally:
            engine.reset()
    return _VERDICT_CACHE["value"]
