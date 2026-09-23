"""Page « Prévisions passées » — la seule qui juge le modèle au lieu de l'exposer."""
from __future__ import annotations

import numpy as np
import pandas as pd

from commun import horodatage, iso_mois, mois_annee

import forecast_archive as fa                   # noqa: E402
import queries as q                             # noqa: E402


def _fmt_vintage(value) -> str:
    """« juin 2024 » — les millésimes sont des MOIS de données, pas des jours."""
    return mois_annee(pd.Timestamp(value))


def build_archive(con, frames: dict) -> dict:
    """Page « Prévisions passées » — la seule qui juge le modèle au lieu de l'exposer.

    Deux natures de lignes cohabitent dans l'archive et ne doivent JAMAIS être agrégées
    ensemble (voir `forecast_archive`) : ce qui a été publié en direct (`archive`) et ce
    qui a été recalculé après coup (`retro`). Tout ce que ce constructeur produit est donc
    ventilé par `kind`, y compris les compteurs — un chiffre unique mélangeant les deux
    laisserait croire à un historique qu'on n'a pas encore.
    """
    archive = fa.read()
    realized = q.transactions_run_rate(con)
    obs = realized.dropna()

    def per_kind(kind: str) -> dict:
        rows = archive[archive["kind"] == kind]
        evaluated = fa.evaluate(rows, realized)
        horizons = fa.by_horizon(evaluated)
        return {
            "n_rows": int(len(rows)),
            "n_vintages": int(rows["data_vintage"].nunique()) if len(rows) else 0,
            "n_evaluated": int(len(evaluated)),
            "first_vintage": (iso_mois(rows["data_vintage"].min()) if len(rows) else None),
            "last_vintage": (iso_mois(rows["data_vintage"].max()) if len(rows) else None),
            # `direction` (part de fois où le SENS annoncé était le bon) et `coverage`
            # (part de mois réellement tombés dans la bande) accompagnent la MAPE : la
            # première est la seule des trois qu'un lecteur non statisticien peut utiliser
            # telle quelle, la seconde est ce qui dit si la bande affichée vaut sa
            # promesse.
            "horizons": [
                {"horizon": int(r.horizon), "n": int(r.n),
                 "mape": round(float(r.mape), 2),
                 "naive_mape": round(float(r.naive_mape), 2),
                 "skill": (round(float(r.skill), 3) if pd.notna(r.skill) else None),
                 "direction": (round(float(r.direction), 3)
                               if pd.notna(r.direction) else None),
                 "coverage": (round(float(r.coverage), 3)
                              if pd.notna(r.coverage) else None)}
                for r in horizons.itertuples()
            ],
            # Les faisceaux : une trajectoire par millésime. La bande n'y est pas — 48
            # bandes superposées ne se lisent pas, et le point du graphique est de montrer
            # la DISPERSION des prévisions successives face à une seule réalité.
            "fans": [
                {"vintage": iso_mois(vintage),
                 "points": [[iso_mois(t), int(p)] for t, p in
                            zip(g["target_month"], g["predicted"])]}
                for vintage, g in rows.sort_values("target_month").groupby("data_vintage")
            ],
        }

    kinds = {kind: per_kind(kind) for kind in ("archive", "retro")}

    # La prévision en cours : le dernier enregistrement en direct, bande comprise. C'est
    # elle que les millésimes suivants viendront juger.
    live = archive[archive["kind"] == "archive"]
    current = None
    if len(live):
        last = live[live["data_vintage"] == live["data_vintage"].max()]
        last = last[last["run_date"] == last["run_date"].max()].sort_values("target_month")
        current = {
            "vintage": iso_mois(last["data_vintage"].iloc[0]),
            "vintage_label": _fmt_vintage(last["data_vintage"].iloc[0]),
            "run_date": str(last["run_date"].iloc[0]),
            "r2": round(float(last["r2"].iloc[0]), 3),
            "points": [{"date": iso_mois(t), "predicted": int(p), "lo": int(lo),
                        "hi": int(hi), "assured": bool(a)}
                       for t, p, lo, hi, a in zip(last["target_month"], last["predicted"],
                                                  last["lo"], last["hi"], last["assured"])],
        }

    # Le réalisé, borné au premier millésime archivé : au-delà, la courbe n'a rien à juger.
    start = min([k["first_vintage"] for k in kinds.values() if k["first_vintage"]],
                default=None)
    observed = obs[obs.index >= pd.Timestamp(start)] if start else obs
    series = [{"date": iso_mois(d), "value": int(v)} for d, v in observed.items()]

    # `commun.pct` signe la valeur (« +4,1 % »), ce qui convient à un glissement mais pas à une
    # ERREUR moyenne, qui est déjà une valeur absolue : un « + » y suggérerait une
    # surestimation systématique alors que le signe a été perdu au calcul.
    def _err(v) -> str:
        return f"{v:.1f} %".replace(".", ",")

    retro_h = {h["horizon"]: h for h in kinds["retro"]["horizons"]}
    kpis = [
        {"label": "Millésimes rétro-simulés", "value": str(kinds["retro"]["n_vintages"]),
         "subs": ["depuis " + _fmt_vintage(kinds["retro"]["first_vintage"])]
                 if kinds["retro"]["first_vintage"] else []},
        {"label": "Prévisions publiées en direct", "value": str(kinds["archive"]["n_vintages"]),
         "subs": ["l'archive commence à sa première publication"]},
    ]
    for h in (6, 12):
        row = retro_h.get(h)
        if row:
            kpis.append({
                "label": f"Erreur moyenne à {h} mois",
                "value": _err(row["mape"]),
                # Le rang d'horizon se compte depuis le dernier mois de DONNÉES, publié avec
                # quelques mois de retard — pas depuis le jour où on lit. L'accueil et le
                # verdict parlent, eux, en mois devant le lecteur : chaque mesure nomme donc
                # sa convention, sinon deux « six mois » voisins ne désignent pas le même mois.
                "subs": [f"une prévision naïve se trompe de {_err(row['naive_mape'])}",
                         "horizon compté depuis le dernier mois de données publié"],
            })

    crossover = next((h["horizon"] for h in kinds["retro"]["horizons"]
                      if h["skill"] is not None and h["skill"] > 0), None)

    episodes = _by_episode(fa.evaluate(archive[archive["kind"] == "retro"], realized))

    return {
        "generated_at": horodatage(),
        "title": "🎯 Prévisions passées — ce que nous annoncions",
        "caption": ("Toutes les prévisions de transactions produites par le modèle, face à ce "
                    "qui s'est réellement passé. Une prévision publiée sans son historique "
                    "n'est qu'une opinion : cette page est là pour qu'on puisse nous prendre "
                    "en défaut."),
        "how_to_read": (
            "Deux natures de prévisions cohabitent ici et ne se valent pas. Les prévisions "
            "PUBLIÉES ont été enregistrées le jour même, avant que la suite ne soit connue — "
            "personne ne peut les retoucher. Les prévisions RÉTRO-SIMULÉES ont été "
            "recalculées après coup en tronquant les données au mois visé : elles montrent "
            "que la méthode tenait, pas que nous l'avions annoncé. Elles sont là parce qu'il "
            "aurait fallu attendre un an avant d'avoir quoi que ce soit à montrer, et elles "
            "restent séparées partout. Leur limite : les transactions sont révisées, donc "
            "une rétro-simulation voit des données un peu meilleures que celles de l'époque."),
        "kpis": kpis,
        "crossover_horizon": crossover,
        "episodes": episodes,
        "kinds": kinds,
        "current": current,
        "realized": series,
        "naive_label": "Prévision naïve (le marché reste où il est)",
    }


#: Les huit épisodes de marché couverts par la rétro-simulation, bornés par millésime.
#: Un score moyen unique répond a la mauvaise question : le modele est pilote par les
#: taux, donc il excelle quand ce sont les taux qui font le marche et decroche quand
#: c'est autre chose. Publier la ventilation, c'est publier son domaine de validite.
_EPISODES = [
    ("2009-01-01", "2009-12-01", "2009 · sortie de crise financière"),
    ("2010-01-01", "2011-12-01", "2010-11 · rebond"),
    ("2012-01-01", "2015-12-01", "2012-15 · creux long, crise de la dette"),
    ("2016-01-01", "2019-12-01", "2016-19 · expansion, records"),
    ("2020-01-01", "2021-12-01", "2020-21 · Covid puis record"),
    ("2022-01-01", "2024-12-01", "2022-24 · choc de taux"),
    ("2025-01-01", "2030-12-01", "2025-26 · reprise"),
]


def _by_episode(evaluated: pd.DataFrame) -> list[dict]:
    """Erreur du modèle contre la naïve, épisode par épisode.

    C'est la ventilation qui manquait le plus : mesuré sur la seule fenêtre 2022-2024, le
    modèle évite près de la moitié de l'erreur naïve ; sur l'ensemble des épisodes, bien
    moins, et il PERD dans certains. Montrer où il perd est le propos de la page, pas un
    aveu — c'est ce qui distingue une prévision publiée d'une opinion.

    Volontairement sans décompte ni exemple nommé ici : ces skills bougent à chaque
    rafraîchissement. La version précédente de cette phrase citait « trois épisodes sur
    huit : 2008-2009, 2012-2015 et le Covid » ; relue le 2026-08-29, elle était fausse sur
    les trois points (sept épisodes, 2009 gagne, 2012-15 est nul) et ignorait 2025-26, qui
    perd. Le tableau est là pour être lu, pas raconté.
    """
    if evaluated.empty:
        return []
    ev = evaluated.copy()
    ev["_v"] = pd.to_datetime(ev["data_vintage"])
    ev["_hit"] = (np.sign(ev["predicted"] - ev["naive"])
                  == np.sign(ev["realized"] - ev["naive"])).astype(float)
    out = []
    for start, end, label in _EPISODES:
        s = ev[(ev["_v"] >= pd.Timestamp(start)) & (ev["_v"] <= pd.Timestamp(end))]
        if s.empty:
            continue
        mape, naive_mape = float(s["ape"].mean()), float(s["naive_ape"].mean())
        out.append({
            "label": label,
            "n": int(len(s)),
            "vintages": int(s["data_vintage"].nunique()),
            "mape": round(mape, 2),
            "naive_mape": round(naive_mape, 2),
            "skill": round(1 - mape / naive_mape, 3) if naive_mape > 0 else None,
            "direction": round(float(s["_hit"].mean()), 3),
        })
    return out
