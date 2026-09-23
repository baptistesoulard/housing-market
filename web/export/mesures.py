"""Les faits partagés entre plusieurs pages — calculés UNE fois, lus par toutes.

Un même pont affiché sur deux pages (le taux de transformation sur la Synthèse et sur
« Marché du neuf », le stock de logements neufs sur la Synthèse) doit tomber sur la même
valeur des deux côtés : deux calculs séparés finiraient par ne plus s'accorder. Ces
fonctions ne produisent que des nombres ; la façon de les dire reste aux pages.
"""
from __future__ import annotations


def stock_neuf(df_ecln):
    """Stock de logements neufs à vendre, et le temps qu'il met à s'écouler.

    ⚠️ `DelaiEcoulement` est publié en TRIMESTRES (voir data_manager.py) : 7,5 se lit
    22 mois, pas 7,5. La confusion est facile et retourne le diagnostic — sept mois de
    stock est sain, vingt-deux ne l'est pas. La conversion est faite ici, une fois, et
    les deux surfaces lisent le résultat.

    Le statut se lit à l'ENVERS des autres cartes : un stock qui s'écoule lentement est
    ce qui fait reculer les mises en vente, donc les chantiers de demain. Il vient donc
    du délai comparé à sa moyenne longue, jamais de la variation du stock lui-même.
    """
    if df_ecln is None or df_ecln.empty:
        return None
    sd = df_ecln.dropna(subset=["Encours", "DelaiEcoulement"]).sort_values("Date")
    if len(sd) < 5:
        return None
    enc = sd["Encours"].astype(float)
    dl_t = sd["DelaiEcoulement"].astype(float)
    mois, moy = float(dl_t.iloc[-1]) * 3, float(dl_t.mean()) * 3
    return {
        "encours": float(enc.iloc[-1]),
        "mois": mois, "moy_mois": moy,
        "ecart_pct": (mois / moy - 1) * 100 if moy else None,
        "seq": (float(enc.iloc[-1]) / float(enc.iloc[-2]) - 1) * 100,
        "since": int(sd["Date"].iloc[0].year),
        "status": "down" if mois > moy * 1.1 else ("up" if mois < moy * 0.9 else "flat"),
    }


def taux_transformation(flux):
    """Part des logements autorisés effectivement ouverts en chantier, en cumuls 12 mois.

    UNE seule implémentation, appelée par la Synthèse et par la page « Marché du neuf » :
    c'est le chiffre qui fait le pont entre les deux cartes « permis » et « chantiers »,
    et deux calculs séparés du même pont finiraient par ne plus tomber sur la même valeur.
    `flux` est la frame mensuelle indexée par Date (colonnes Permis / MisesEnChantier).
    """
    p12 = flux["Permis"].dropna().rolling(12).sum()
    m12 = flux["MisesEnChantier"].dropna().rolling(12).sum()
    return (m12 / p12).dropna()
