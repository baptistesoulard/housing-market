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


def decomposition_surface(par_type, compte, surface, ref=("2010", "2019"), fenetre=12):
    """Pourquoi les m² reculent plus que les logements : VOLUME, MIX et TAILLE.

    `par_type` est la frame mensuelle SIT@DEL par type [Date, Type, <compte>, <surface>].
    On compare les `fenetre` derniers mois à la moyenne annuelle de la période `ref`.
    Avec N le nombre de logements, w_t la part du type t et s_t sa surface moyenne,
    M = N × Σ w_t s_t, et le rapport des surfaces se factorise EXACTEMENT :

        M1/M0 = (N1/N0) × (Σ w1 s0 / Σ w0 s0) × (Σ w1 s1 / Σ w1 s0)
                 volume      mix (à tailles figées)   taille (à mix actuel)

    Les trois facteurs sont convertis en POINTS enchaînés, qui s'additionnent au recul
    total : volume = N1/N0 − 1, mix = (N1/N0)(mix − 1), taille = (N1/N0) × mix × (taille − 1).

    Pourquoi publier la décomposition et pas seulement l'écart : l'explication intuitive
    (« les logements rétrécissent ») est la MAUVAISE. Mesuré le 2026-08-31 puis revérifié le
    2026-09-26 : de l'écart entre le recul des m² et celui des logements, la taille ne pèse
    qu'un tiers ; les deux tiers viennent du MIX — moins de maisons individuelles (environ
    120 m² par logement), plus de résidences gérées (moins de 50 m²).
    Un écart agrégé plus grand que tous les écarts à type figé EST la signature d'un effet
    de mix (voir journal 05). Pour un fabricant de matériaux, ce n'est pas la même
    nouvelle : un parc qui rétrécit touche tout le monde, un mix qui bascule déplace la
    demande d'une ligne de produits à l'autre.

    Renvoie {"total", "volume", "mix", "taille"} en points de %, plus `types` (part et
    surface moyenne de chaque type, période de référence contre fenêtre récente) et
    `surface_moyenne` (m² par logement, les deux périodes). None si l'historique manque.
    """
    p = par_type.pivot_table(index="Date", columns="Type", values=[compte, surface])
    N, M = p[compte], p[surface]
    periode = N.loc[ref[0]:ref[1]]
    if len(N) < fenetre or periode.empty:
        return None
    annees = periode.index.year.nunique()
    N1, M1 = N.iloc[-fenetre:].sum(), M.iloc[-fenetre:].sum()
    N0, M0 = N.loc[ref[0]:ref[1]].sum() / annees, M.loc[ref[0]:ref[1]].sum() / annees
    if (N0 <= 0).any() or (N1 <= 0).any():
        return None
    w0, w1 = N0 / N0.sum(), N1 / N1.sum()
    s0, s1 = M0 / N0, M1 / N1
    volume = N1.sum() / N0.sum()
    mix = float((w1 * s0).sum() / (w0 * s0).sum())
    taille = float((w1 * s1).sum() / (w1 * s0).sum())
    return {
        "total": (M1.sum() / M0.sum() - 1) * 100,
        "volume": (volume - 1) * 100,
        "mix": volume * (mix - 1) * 100,
        "taille": volume * mix * (taille - 1) * 100,
        "ref_label": f"{ref[0]}-{ref[1][-2:]}",
        "surface_moyenne": {"ref": float(M0.sum() / N0.sum()),
                            "recent": float(M1.sum() / N1.sum())},
        "types": [{"type": t, "part_ref": float(w0[t]) * 100, "part_recent": float(w1[t]) * 100,
                   "m2_ref": float(s0[t]), "m2_recent": float(s1[t])}
                  for t in N.columns],
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
