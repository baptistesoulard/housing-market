"""Reconstitue l'agrégat DVF départemental 2014-2020, à la main et une seule fois.

## Pourquoi ce script est séparé de `fetch_new_sources.py`

Le point de publication officiel (`files.data.gouv.fr/geo-dvf/`) ne porte qu'**une fenêtre
glissante de 5 ans** : vérifié, un seul millésime y est publié (`2025-12`) et il couvre
2021-2025. Les années antérieures n'y sont plus, et aucun millésime archivé n'y subsiste —
il n'y a donc rien à empiler depuis la source officielle.

Elles restent disponibles sur le miroir de Christian Quest (`data.cquest.org/dgfip_dvf/`),
qui conserve les millésimes depuis 2019-04. C'est ce miroir que ce script consomme, pour
**1,1 Go de téléchargement**. Deux raisons de ne pas mettre ça dans le job hebdomadaire :

1. le volume, sur un runner GitHub Actions, pour des données qui ne bougeront plus jamais ;
2. la dépendance à un miroir tiers, acceptable pour une reconstitution ponctuelle dont on
   commite le résultat, beaucoup moins pour une chaîne de production hebdomadaire.

L'agrégat produit est donc **committé** (`data_manual_input/dvf-historique-2014-2020.csv`)
et ce script n'a pas vocation à tourner en CI. Il existe pour que le chiffre publié reste
reproductible par quiconque, ce qui est la seule raison de commiter un dérivé.

## Le raccord avec les années récentes

Le format brut n'a pas d'`id_mutation` : `dvf_clean.from_raw_dgfip` reconstruit la clé.
Elle ne reproduit pas exactement la partition officielle, mais l'écart mesuré sur la
médiane publiée est de **+0,00 % (Lozère) et +0,15 % (Paris)** — voir l'en-tête de
`dvf_clean` et `tests/test_dvf_clean.py`. Le raccord 2020/2021 ne crée donc pas de marche
visible, ce qui est la condition pour publier une série qui traverse la charnière.

## Usage

    python dvf_backfill.py --source <dossier des fichiers bruts>
    python dvf_backfill.py --download          # récupère les fichiers puis agrège

Les fichiers attendus dans le dossier source :

    dvf-2014-2018.csv.gz     consolidé du miroir (294 Mo)
    vf-2019.txt              millésime 202104, brut DGFiP séparé par « | »
    vf-2020.txt              millésime 202104
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.request

import pandas as pd

import dvf_clean as dv

MIROIR = "https://data.cquest.org/dgfip_dvf"
FICHIERS = {
    "dvf-2014-2018.csv.gz": f"{MIROIR}/dvf-2014-2018.csv.gz",
    "vf-2019.txt": f"{MIROIR}/202104/valeursfoncieres-2019.txt",
    "vf-2020.txt": f"{MIROIR}/202104/valeursfoncieres-2020.txt",
}
SORTIE = os.path.join("data_manual_input", "dvf-historique-2014-2020.csv")

# Seules colonnes lues : sur 1,1 Go, tout charger sature la mémoire pour rien.
COLS_BRUT = ["No disposition", "Date mutation", "Nature mutation", "Valeur fonciere",
             "Code departement", "Code commune", "Type local", "Surface reelle bati"]
# « surface_relle_bati » : la coquille est dans le fichier du miroir, pas ici.
COLS_CONSOLIDE = ["numero_disposition", "date_mutation", "nature_mutation",
                  "valeur_fonciere", "code_departement", "code_commune", "type_local",
                  "surface_relle_bati"]


def _telecharger(dossier):
    os.makedirs(dossier, exist_ok=True)
    for nom, url in FICHIERS.items():
        cible = os.path.join(dossier, nom)
        if os.path.exists(cible) and os.path.getsize(cible) > 1_000_000:
            print(f"  [=] {nom} déjà présent")
            continue
        print(f"  [↓] {nom} …")
        urllib.request.urlretrieve(url, cible)
        print(f"      {os.path.getsize(cible) / 1e6:.0f} Mo")


def _nettoyer_par_morceaux(chemin, *, sep, cols, compression=None, taille=500_000):
    """Lit un gros fichier par tranches et n'en garde que les ventes retenues.

    Le nettoyage ne peut pas être appliqué tranche par tranche naïvement : une mutation
    peut être coupée en deux par une frontière de tranche, et le filtre « exactement un
    logement » compterait alors mal. On garde donc le RESTE de la dernière mutation d'une
    tranche pour le recoller à la suivante — les fichiers sont triés par département puis
    par mutation, mais on ne s'appuie pas sur ce tri : on recolle sur la clé.
    """
    morceaux, reste = [], None
    lecteur = pd.read_csv(chemin, sep=sep, usecols=cols, dtype=str,
                          compression=compression, chunksize=taille,
                          encoding="utf-8", on_bad_lines="skip", low_memory=False)
    for i, tranche in enumerate(lecteur):
        canon = dv.from_raw_dgfip(tranche)
        if reste is not None:
            canon = pd.concat([reste, canon], ignore_index=True)
        # La dernière mutation de la tranche est peut-être incomplète : on la met de côté.
        derniere = canon["mutation"].iloc[-1]
        reste = canon[canon["mutation"] == derniere]
        canon = canon[canon["mutation"] != derniere]
        propre = dv.clean(canon)
        if not propre.empty:
            morceaux.append(propre)
        if i % 20 == 0:
            print(f"      tranche {i} — {sum(len(m) for m in morceaux):,} ventes retenues"
                  .replace(",", " "), flush=True)
    if reste is not None and not reste.empty:
        propre = dv.clean(reste)
        if not propre.empty:
            morceaux.append(propre)
    return pd.concat(morceaux, ignore_index=True) if morceaux else pd.DataFrame()


def construire(dossier):
    ventes = []
    chemin = os.path.join(dossier, "dvf-2014-2018.csv.gz")
    print(f"  [·] {chemin} (consolidé 2014-2018)")
    ventes.append(_nettoyer_par_morceaux(chemin, sep=",", cols=COLS_CONSOLIDE,
                                         compression="gzip"))
    for an in (2019, 2020):
        chemin = os.path.join(dossier, f"vf-{an}.txt")
        print(f"  [·] {chemin} (brut DGFiP)")
        ventes.append(_nettoyer_par_morceaux(chemin, sep="|", cols=COLS_BRUT))

    toutes = pd.concat(ventes, ignore_index=True)
    print(f"\n  {len(toutes):,} ventes retenues au total".replace(",", " "))
    agg = dv.aggregate(toutes)

    # Garde-fou : un trimestre départemental trop peu fourni ne signale pas un marché
    # atone mais une année incomplète dans le millésime source. On le retire ET on le
    # signale — un retrait silencieux masquerait la prochaine occurrence du problème.
    maigres = agg[agg["NbVentes"] < MIN_VENTES_TRIMESTRE]
    if not maigres.empty:
        ens = maigres[maigres["Type"] == "Ensemble"]
        print(f"  /!\\ {len(ens)} trimestres sous {MIN_VENTES_TRIMESTRE} ventes, retirés :")
        for an, n in ens.groupby(ens["Date"].dt.year).size().items():
            print(f"        {an} : {n}")
        agg = agg[agg["NbVentes"] >= MIN_VENTES_TRIMESTRE]

    # L'écrêtage a été appliqué tranche par tranche ci-dessus, donc par sous-échantillon ;
    # les bornes exactes diffèrent marginalement d'un calcul en une passe. Sans effet sur
    # une médiane, et c'est le prix à payer pour ne pas charger 1,1 Go en mémoire.
    return agg


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--source", default="dvf_raw",
                   help="dossier contenant les fichiers bruts")
    p.add_argument("--download", action="store_true",
                   help="télécharger les fichiers manquants (1,1 Go)")
    p.add_argument("--out", default=SORTIE)
    a = p.parse_args(argv)

    if a.download:
        print("Téléchargement :")
        _telecharger(a.source)
    manquants = [n for n in FICHIERS if not os.path.exists(os.path.join(a.source, n))]
    if manquants:
        print(f"Fichiers manquants dans {a.source} : {manquants}\n"
              f"Relancer avec --download pour les récupérer.", file=sys.stderr)
        return 1

    print("Nettoyage :")
    agg = construire(a.source)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    agg.to_csv(a.out, index=False)
    an = agg["Date"].dt.year
    print(f"\n→ {a.out}")
    print(f"   {len(agg):,} lignes | {agg['Department'].nunique()} départements | "
          f"{an.min()}-{an.max()} | {os.path.getsize(a.out) / 1e6:.1f} Mo"
          .replace(",", " "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
