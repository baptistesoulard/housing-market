"""Nettoyage de DVF (Demandes de valeurs foncières, DGFiP) vers un prix au m² fiable.

DVF publie des **mutations**, pas des prix au m². Entre les deux il y a un nettoyage qui
n'a rien d'anecdotique : mesuré sur les données 2025, un `valeur_fonciere / surface`
appliqué ligne à ligne surestime la médiane de **+14 % en Lozère et +5,4 % à Paris**. Ce
module porte ce nettoyage, et lui seul — il ne sait rien de DuckDB, du front, ni de
l'application.

## Les deux pièges, vérifiés sur les données

**Une ligne n'est pas une vente.** Le fichier est au grain « lot » : une mutation
s'étale sur plusieurs lignes (3,9 en moyenne en Lozère), et `valeur_fonciere` est le prix
TOTAL de la mutation, **répété à l'identique sur chacune** — vérifié : 0 mutation sur
2 206 ne présente d'écart entre ses lignes. Sommer les lignes multiplie donc le prix ;
diviser ligne à ligne attribue le prix entier à une surface partielle.

**Le prix couvre parfois plus que le logement.** 66 % des mutations portant un seul
logement embarquent aussi une dépendance ou du terrain (garage, cave, jardin).

## Le filtre retenu — et pourquoi

1. `nature_mutation == "Vente"` : écarte les ventes en l'état futur d'achèvement (le prix
   d'une VEFA n'est pas comparable à celui d'un bien existant), les échanges, les
   adjudications et les ventes de terrain à bâtir.
2. Mutations portant **exactement un** local de type Maison ou Appartement. En deçà il n'y
   a pas de logement, au-delà le prix couvre plusieurs biens sans clé de répartition.
3. **Les dépendances sont TOLÉRÉES** (décision du 2026-08-20). Une maison vendue avec son
   garage est une vente normale, et c'est le bien que le particulier compare. Les écarter
   coûterait 66 % de l'échantillon pour ne déplacer la médiane que de −6,9 % (Lozère) et
   −0,8 % (Paris), tout en déformant la composition vers les maisons sans annexes — les
   moins représentatives du marché. Conséquence assumée, à afficher sur la page : le prix
   au m² inclut ces annexes, donc **surestime légèrement** le logement seul.
4. Surface = `surface_reelle_bati`. Ce n'est pas un choix : sur les logements, elle est
   remplie à 100 %, contre 1,5 % (Lozère) à 48 % (Paris) pour la surface Carrez.
5. Bornes sur le prix au m² : **percentiles 1 % et 99 %, par département ET par année**.
   Des bornes nationales fixes sont mal calibrées aux deux extrémités du pays — le 99ᵉ
   percentile parisien est à 25 730 €/m², un plafond fixe à 20 000 € couperait donc des
   ventes authentiques. Enjeu faible au demeurant : on publie une médiane, robuste par
   construction (l'écart mesuré avec/sans bornes est de +3 % en Lozère, +0,03 % à Paris).
   L'écrêtage est suspendu sous 30 ventes dans l'année pour un département — en
   dessous, un quantile à 1 % ne retire plus des aberrations mais le minimum.
6. Médiane, jamais moyenne : les distributions de prix immobiliers ont des queues épaisses.

## Les deux formats d'entrée

Le format **géolocalisé** (Etalab, `files.data.gouv.fr/geo-dvf/`) porte un `id_mutation`
officiel mais ne couvre que les 5 dernières années. Le format **brut DGFiP** (millésimes
archivés) remonte à 2014 mais n'a pas cette clé : il faut la reconstruire.

Les deux ne partitionnent pas identiquement — mais **le chiffre publié ne bouge pas** :
mesuré sur 2025, la clé reconstruite donne +0,00 % (Lozère) et +0,15 % (Paris) d'écart de
médiane. C'est ce qui autorise à raccorder les deux sources sans rupture de série visible,
et `tests/test_dvf_clean.py` verrouille cette équivalence.
"""
from __future__ import annotations

import pandas as pd

# Départements hors DVF : Alsace-Moselle relève du Livre foncier et non du fichier
# immobilier de la DGFiP ; Mayotte n'est pas couverte. Vérifié en interrogeant la source :
# ces quatre codes renvoient 404 sur TOUTES les années publiées, ce n'est pas un trou
# ponctuel. Les pages de ces départements doivent le dire, pas afficher un graphique vide.
DEPARTEMENTS_SANS_DVF = ("57", "67", "68", "976")

DWELLING_TYPES = ("Maison", "Appartement")
NATURE_RETENUE = "Vente"

# Colonnes du format pivot, seul vocabulaire que connaît la suite du module.
CANONICAL = ["mutation", "date", "departement", "type_local",
             "valeur_fonciere", "surface_bati"]


# --------------------------------------------------------------- lecture des formats
def from_geo_dvf(df: pd.DataFrame) -> pd.DataFrame:
    """Format géolocalisé Etalab (CSV, une ligne par lot, `id_mutation` fourni)."""
    out = pd.DataFrame({
        "mutation": df["id_mutation"].astype(str),
        "date": pd.to_datetime(df["date_mutation"], errors="coerce"),
        "departement": df["code_departement"].astype(str).str.zfill(2),
        "type_local": df["type_local"],
        "nature_mutation": df["nature_mutation"],
        "valeur_fonciere": pd.to_numeric(df["valeur_fonciere"], errors="coerce"),
        "surface_bati": pd.to_numeric(df["surface_reelle_bati"], errors="coerce"),
    })
    return out


def from_raw_dgfip(df: pd.DataFrame) -> pd.DataFrame:
    """Format brut DGFiP (millésimes archivés) — la clé de mutation est reconstruite.

    Accepte les deux variantes rencontrées : le `.txt` séparé par `|` (en-têtes « Date
    mutation », dates JJ/MM/AAAA, virgule décimale) et le CSV consolidé du miroir
    (en-têtes en snake_case, dates ISO, point décimal).
    """
    cols = {c.strip().lower().replace(" ", "_"): c for c in df.columns}

    def col(*noms):
        for n in noms:
            if n in cols:
                return df[cols[n]]
        raise KeyError(f"colonne absente : {noms!r} (vu : {sorted(cols)[:12]}…)")

    date = col("date_mutation")
    # Le brut écrit JJ/MM/AAAA, le consolidé du miroir AAAA-MM-JJ. `format="mixed"` ferait
    # deviner ligne à ligne (lent et ambigu sur 01/02) : on choisit sur la première valeur.
    premier = str(date.dropna().iloc[0]) if date.notna().any() else ""
    date = pd.to_datetime(date, format="%d/%m/%Y", errors="coerce") if "/" in premier \
        else pd.to_datetime(date, errors="coerce")

    valeur = col("valeur_fonciere").astype(str).str.replace(",", ".", regex=False)
    # Le consolidé du miroir porte une coquille dans son en-tête — « surface_relle_bati »,
    # sans le second « e ». Constatée en lisant le fichier, pas devinée.
    surface = (col("surface_reelle_bati", "surface_relle_bati")
               .astype(str).str.replace(",", ".", regex=False))
    dep = col("code_departement").astype(str).str.strip().str.zfill(2)
    commune = col("code_commune").astype(str).str.strip()
    dispo = col("no_disposition", "numero_disposition").astype(str).str.strip()

    # Clé de mutation reconstruite. Elle ne reproduit PAS exactement la partition
    # officielle (elle fusionne quelques mutations et en scinde d'autres), mais l'écart
    # sur la médiane publiée est de +0,15 % au maximum — voir l'en-tête du module.
    mutation = (date.dt.strftime("%Y-%m-%d").fillna("~") + "|" + dispo + "|"
                + commune + "|" + valeur.fillna("~"))

    return pd.DataFrame({
        "mutation": mutation,
        "date": date,
        "departement": dep,
        "type_local": col("type_local"),
        "nature_mutation": col("nature_mutation"),
        "valeur_fonciere": pd.to_numeric(valeur, errors="coerce"),
        "surface_bati": pd.to_numeric(surface, errors="coerce"),
    })


# --------------------------------------------------------------------- nettoyage
def clean(df: pd.DataFrame, *, q_low: float = 0.01, q_high: float = 0.99,
          min_obs: int = 30) -> pd.DataFrame:
    """Applique le filtre documenté. Renvoie UNE ligne par vente retenue.

    Colonnes de sortie : mutation, date, departement, type_local, valeur_fonciere,
    surface_bati, prix_m2.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=[*CANONICAL, "prix_m2"])

    d = df.copy()

    # (1) vraies ventes seulement — la VEFA, l'échange et l'adjudication sortent ici.
    d = d[d["nature_mutation"] == NATURE_RETENUE]

    # (2) exactement un local d'habitation dans la mutation. Le décompte porte sur la
    #     mutation ENTIÈRE (avant de ne garder que ses lignes de logement), sinon une
    #     mutation à deux appartements passerait pour deux ventes distinctes.
    logements = d[d["type_local"].isin(DWELLING_TYPES)]
    par_mutation = logements.groupby("mutation")["mutation"].size()
    seules = par_mutation[par_mutation == 1].index
    d = logements[logements["mutation"].isin(seules)].copy()

    # (3) le prix au m². `valeur_fonciere` est le prix TOTAL de la mutation ; comme
    #     celle-ci ne porte plus qu'un logement, le rapport a un sens — au bémol des
    #     dépendances tolérées, assumé et affiché sur la page.
    d = d[(d["valeur_fonciere"] > 0) & (d["surface_bati"] > 0)]
    d["prix_m2"] = d["valeur_fonciere"] / d["surface_bati"]

    if d.empty:
        return d.reindex(columns=[*CANONICAL, "prix_m2"])

    # (4) bornes par département ET par année : un plafond national serait trop bas pour
    #     Paris et trop haut pour la Lozère.
    #
    #     `min_obs` protège les tout petits effectifs. Un quantile à 1 % est TOUJOURS
    #     strictement supérieur au minimum d'un échantillon fini : sur dix ventes, écrêter
    #     revient donc à jeter la moins chère et la plus chère quoi qu'elles vaillent —
    #     l'écrêtage cesserait de retirer des aberrations pour devenir une amputation
    #     systématique. En dessous du seuil on ne borne pas, et la médiane, robuste, s'en
    #     accommode. Les départements réels dépassent tous largement ce seuil sur une
    #     année ; le cas se présente sur des données fabriquées ou un millésime partiel.
    d["_annee"] = d["date"].dt.year
    grp = d.groupby(["departement", "_annee"])["prix_m2"]
    assez = grp.transform("size") >= min_obs
    bas = grp.transform(lambda s: s.quantile(q_low))
    haut = grp.transform(lambda s: s.quantile(q_high))
    d = d[~assez | ((d["prix_m2"] >= bas) & (d["prix_m2"] <= haut))]

    return d.drop(columns="_annee")[[*CANONICAL, "prix_m2"]].reset_index(drop=True)


def aggregate(df: pd.DataFrame, freq: str = "Q") -> pd.DataFrame:
    """Agrège les ventes nettoyées en médianes trimestrielles par département.

    Trimestriel, pas mensuel : la Lozère ne compte que ~700 ventes de logement par AN,
    soit une soixantaine par mois — une médiane mensuelle y serait un générateur de bruit.
    Le trimestre donne des effectifs tenables partout et 4 points par an suffisent
    largement à lire une tendance de prix.

    Trois valeurs de `Type` : « Maison », « Appartement » et « Ensemble » (les deux
    réunis). L'ensemble n'est PAS la moyenne des deux médianes — c'est la médiane du
    marché complet, seule grandeur qui ait un sens quand la composition varie.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["Date", "Department", "Type",
                                     "PrixM2Median", "PrixMedian", "NbVentes"])
    d = df.copy()
    # `to_period` attend "Q" (pandas refuse "QS" ici) ; `start_time` ramène
    # ensuite au premier jour du trimestre, format de date du reste du dépôt.
    d["Date"] = d["date"].dt.to_period(freq).dt.start_time

    def _agg(g, type_label):
        out = g.groupby(["Date", "departement"]).agg(
            PrixM2Median=("prix_m2", "median"),
            PrixMedian=("valeur_fonciere", "median"),
            NbVentes=("mutation", "size"),
        ).reset_index().rename(columns={"departement": "Department"})
        out["Type"] = type_label
        return out

    morceaux = [_agg(d, "Ensemble")]
    for t in DWELLING_TYPES:
        sous = d[d["type_local"] == t]
        if not sous.empty:
            morceaux.append(_agg(sous, t))

    res = pd.concat(morceaux, ignore_index=True)
    res["PrixM2Median"] = res["PrixM2Median"].round(0)
    res["PrixMedian"] = res["PrixMedian"].round(0)
    return res.sort_values(["Department", "Type", "Date"])[
        ["Date", "Department", "Type", "PrixM2Median", "PrixMedian", "NbVentes"]
    ].reset_index(drop=True)
