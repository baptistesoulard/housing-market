"""Export des données du site : du dépôt vers les JSON statiques que lit le front Observable.

Usage :
    python web/export/web_export.py

Ce fichier n'est plus que l'ORCHESTRATION : charger les données, appeler un constructeur
par page, écrire ce qui a changé. Chaque page a son module :

    page_synthese.py      Synthèse — faits, puis rédaction
    page_marches.py       Marché du neuf, Marché de l'ancien
    page_contexte.py      Environnement & Financement, Actualités & Aides
    page_previsions.py    Prévision & Scénarios
    page_archive.py       Prévisions passées
    page_departements.py  les 101 pages départementales + l'annuaire

et les briques qu'elles partagent :

    commun.py      chemins, palette, mise en forme française (%, milliers, mois)
    mesures.py     faits calculés une fois pour plusieurs pages (stock neuf, transformation)
    verdict.py     le verdict du modèle et sa fiabilité (Synthèse, Prévision, accueil)
    reperes.py     ce que RIEN ne régénère : repères saisis à la main, mesures datées
    ecriture.py    le point d'écriture unique (arrondi, garde de contenu)
    sources_table.py, accueil.py   texte statique réécrit entre marqueurs (À propos, accueil)

La sortie doit annoncer « 0/7 fichier(s) modifié(s) » quand aucune donnée n'a bougé : un
diff inattendu signale une divergence de calcul, pas du bruit (voir CLAUDE.md).
"""
from __future__ import annotations

import os

import pandas as pd

import accueil                                  # chiffres de l'accueil (index.md)
from commun import DATA_DIR
from ecriture import ecrire_si_change
import page_archive                             # noqa: E402
import page_contexte                            # noqa: E402
import page_departements                        # noqa: E402
import page_marches                             # noqa: E402
import page_previsions                          # noqa: E402
import page_synthese                            # noqa: E402
import sources_table                            # noqa: E402  (tableau de la page À propos)
import theme                                    # noqa: E402  (palette partagée web/theme.json)

import queries as q                             # noqa: E402  (couche SQL DuckDB partagée)
from data_manager import DataManager            # noqa: E402

#: Un constructeur par JSON national. L'ordre est celui des messages, rien d'autre.
_BUILDERS = {"synthese": page_synthese.build_synthese,
             "neuf": page_marches.build_neuf,
             "ancien": page_marches.build_ancien,
             "macro": page_contexte.build_macro,
             "actualites": page_contexte.build_actualites,
             "archive": page_archive.build_archive,
             "previsions": page_previsions.build_previsions}


# ============================ chargement partagé des frames =======================
def load_frames() -> dict:
    """Charge les datasets une seule fois (réutilisé par tous les builders de pages)."""
    dm = DataManager()
    dm.load_or_generate_all()
    df_sitadel, df_ventes_ancien, df_macro, df_ecln = dm.read_frames()
    frames = {"sitadel": df_sitadel, "ventes_ancien": df_ventes_ancien, "macro": df_macro,
              "ecln": df_ecln}
    # Les deux datasets PAR DÉPARTEMENT (prix DVF, profil INSEE) ne servent ici qu'au
    # tableau des sources d'À propos (dernier point publié) : les pages, elles, les lisent
    # par SQL. Hors du tuple de read_frames() — voir CLAUDE.md.
    for cle in ("dvf", "territoires"):
        chemin = dm.paths.get(cle)
        if chemin and os.path.exists(chemin):
            df = pd.read_csv(chemin, dtype={"Department": str})
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"])
            frames[cle] = df
    return frames


def _period_bounds(frames: dict) -> dict:
    """Bornes du curseur d'années partagé par tout le front (barre latérale).

    Union de SIT@DEL, des ventes anciennes et de la macro. Publiée dans les sept payloads
    pour que la frise ait exactement le même domaine sur toutes les pages, quelle que soit
    l'étendue des séries de la page affichée."""
    dates = pd.concat([frames[k]["Date"] for k in ("sitadel", "ventes_ancien", "macro")
                       if frames.get(k) is not None and not frames[k].empty]).dropna()
    return {"min": int(dates.dt.year.min()), "max": int(dates.dt.year.max())}


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    theme.write_theme_js()  # régénère components/theme.js depuis web/theme.json
    frames = load_frames()  # rafraîchit les CSV + miroirs Parquet validés
    con = q.open_warehouse(refresh=False)  # vue DuckDB sur les Parquet déjà à jour
    period = _period_bounds(frames)        # domaine de la frise de la barre latérale
    changed, payloads = [], {}
    for name, builder in _BUILDERS.items():
        path = os.path.join(DATA_DIR, f"{name}.json")
        payload = builder(con, frames)
        payload["period"] = period
        payloads[name] = payload
        if ecrire_si_change(path, payload):
            changed.append(name)
            print(f"[web_export] écrit {name}.json")
        else:
            print(f"[web_export] {name}.json inchangé")
    print(f"[web_export] {len(changed)}/{len(_BUILDERS)} fichier(s) modifié(s)"
          + (f" ({', '.join(changed)})" if changed else " — rien de neuf."))
    # Les 101 pages départementales, comptées à part (voir page_departements).
    page_departements.build_departements(con)
    # Le tableau des sources de la page « À propos », lui aussi hors du compteur ci-dessus :
    # ce n'est pas un JSON du front mais du Markdown complété sur place, et le compteur
    # « n/7 » vaut par sa capacité d'alerte sur une divergence de calcul (voir CLAUDE.md).
    if sources_table.ecrire(frames):
        print("[web_export] a-propos.md : dates du tableau des sources mises à jour")
    else:
        print("[web_export] a-propos.md : tableau des sources inchangé")
    # Les deux affirmations chiffrées de l'accueil (erreur du modèle, horizon de bascule),
    # même régime que le tableau des sources : Markdown réécrit entre marqueurs, hors compteur.
    if accueil.ecrire(payloads["previsions"], payloads["archive"]):
        print("[web_export] index.md : chiffres de l'accueil mis à jour")
    else:
        print("[web_export] index.md : chiffres de l'accueil inchangés")


if __name__ == "__main__":
    main()
