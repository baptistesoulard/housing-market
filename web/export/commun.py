"""Ce que toutes les pages de l'export partagent : chemins, palette, mise en forme française.

Aucun calcul de marché ici — seulement la façon d'ÉCRIRE un nombre, une date, une pastille.
C'est volontaire : les règles typographiques du site (espace avant « % », pas de « −0,0 »,
milliers séparés par une espace) vivent à UN endroit, donc un correctif les applique à
toutes les pages d'un coup au lieu d'être recopié page par page.

Importé en premier par chaque module de l'export : il met aussi la racine du dépôt sur
`sys.path`, ce qui rend `analysis`, `queries`, `forecast_archive`… importables quel que
soit le répertoire courant.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import pandas as pd

# --- Rendre les modules du dépôt importables quel que soit le CWD -----------------
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import analysis as ana                          # noqa: E402
import theme                                    # noqa: E402  (palette partagée web/theme.json)

DATA_DIR = os.path.join(REPO_ROOT, "web", "observable", "src", "data")

MOIS_FR = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
           "septembre", "octobre", "novembre", "décembre")

# Palette : sourcée depuis le thème partagé (web/theme.json via theme.py), rampe de séries.
COLOR_TEXT = theme.S_VIOLET     # slot 4 (série) — mises en chantier, taux crédit, encours
COLOR_BRICK = theme.S_BRICK     # slot 1 — permis, prix ensemble, particuliers…
COLOR_GREEN = theme.S_GREEN     # slot 3 — ventes anciennes, OAT, maisons…
COLOR_BLUE = theme.S_BLUE       # slot 2 — collectif, euribor, appartements…
COLOR_TERRACOTTA = theme.S_GOLD  # slot 5 — individuel total, institutionnels, renégo.
COLOR_SUNFLOWER = theme.S_GOLD   # slot 5


def horodatage() -> str:
    """L'horloge murale, au format de `generated_at` (exclu des comparaisons d'écriture)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def jalons_a_venir(items):
    """Les jalons encore à venir, triés — comparés à AUJOURD'HUI, pas à `actu.MAJ`.

    La veille d'`actualites.py` est curatée à la main : `MAJ` dit quand elle a été relue,
    et c'est à ce repère que le filtre se comparait. Un jalon tombant entre `MAJ` et le
    jour de la publication restait donc annoncé comme « prochaine échéance » alors qu'il
    était déjà passé — le cas s'est produit avec la suppression des forfaits monogestes
    (2026-09-01) publiée le 2026-09-02. `MAJ` reste ce qu'elle est, la date de dernière
    relecture affichée sur la page ; elle n'a simplement pas à servir d'horloge.
    """
    aujourdhui = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return sorted([(d, it) for it in items for d, _lbl, _typ in it.get("jalons", [])
                   if d > aujourdhui], key=lambda t: t[0])


# ============================ mise en forme ======================================
def _manquant(v) -> bool:
    return v is None or (isinstance(v, float) and pd.isna(v))


def mois_annee(date) -> str:
    if pd.isna(date):
        return "—"
    d = pd.Timestamp(date)
    return f"{MOIS_FR[d.month - 1]} {d.year}"


def milliers(v) -> str:
    """Entier avec espace comme séparateur de milliers ('123 456')."""
    if _manquant(v):
        return "—"
    return f"{int(round(float(v))):,}".replace(",", " ")


def abrege(v) -> str:
    """Nombre 'de titre' : '385 k' au-dessus de 100 000, entier espacé en dessous."""
    if _manquant(v):
        return "—"
    v = float(v)
    if abs(v) >= 100_000:
        return f"{v / 1000.0:,.0f} k".replace(",", " ")
    return f"{int(round(v)):,}".replace(",", " ")


def pct(v) -> str:
    if _manquant(v):
        return "—"
    return f"{v:+.1f}%".replace(".", ",")


def pastille(status: str) -> str:
    return {"up": "🟢", "flat": "🟠", "down": "🔴"}.get(status, "⚪")


def renvoi(icon: str, label: str, path: str) -> dict:
    """Un renvoi vers une page du site, tel que le front l'attend (voir `blocks`)."""
    return {"icon": icon, "label": label, "path": path}


def statut_annuel(v, hi: float = 1.0, lo: float = -1.0) -> str:
    if v is None:
        return "flat"
    return "up" if v > hi else ("down" if v < lo else "flat")


def statut_seq(v) -> str:
    """Statut d'un momentum SÉQUENTIEL, avec sa tolérance propre (voir ana.SEQ_TOL)."""
    return ana._tri(v, ana.SEQ_TOL)


def arrondi_millier(v) -> int:
    """Arrondi au millier — la précision réelle d'un écart contrefactuel.

    Un nombre affiché à l'unité annonce une précision qu'il n'a pas : l'écart de
    conversion dérivé d'un taux dont l'écart-type vaut 4,9 points bouge de ±18 000
    logements. Cinq chiffres significatifs sur une grandeur connue à un près.
    """
    return int(round(float(v) / 1000.0) * 1000)


def ligne_niveau(ctx) -> str:
    """Seconde ligne d'une carte : l'ALTITUDE du niveau, que le momentum ne dit jamais.

    « 293 k, tendance 12 mois +16,7 % » se lit comme un marché qui va bien. Ajouter
    « 23 % sous la normale 2010-19, plus bas que 91 % des mois depuis 2000 » ne change
    aucun chiffre et change la décision : on passe d'une reprise à un rebond de creux.
    Voir ana.level_context pour le choix de la décennie de référence.
    """
    if not ctx:
        return ""
    sens = "sous" if ctx["gap_pct"] < 0 else "au-dessus de"
    ecart = f"{abs(ctx['gap_pct']):.0f} %".replace(".", ",")
    if ctx["rank_pct"] < 50:
        rang = f"plus bas que {100 - ctx['rank_pct']:.0f} % des mois depuis {ctx['since_year']}"
    else:
        rang = f"plus haut que {ctx['rank_pct']:.0f} % des mois depuis {ctx['since_year']}"
    return f"{ecart} {sens} la normale {ctx['ref_label']} · {rang}"


def ligne_momentum(head, trend_12m=None, plateau=None, exact=None) -> str:
    """Sous-titre de carte : le momentum publié, puis la tendance longue, puis le total.

    Deux horizons sur une ligne, et c'est le but : le momentum dit si le rythme tourne,
    la tendance 12 mois dit d'où l'on vient. Publier l'un sans l'autre laisse croire
    qu'un retournement de trimestre efface une année (ou l'inverse) — c'est exactement
    ce que faisait l'ancien « X % vs un an plus tôt (3 derniers mois) », seul sur la
    carte et calculé de la façon que `ana.headline_momentum` documente comme fausse sur
    une série corrigée des variations saisonnières.
    """
    parts = [pct(head["value"]) + " " + head["window"]]
    if trend_12m is not None and head["key"] != "roll12_yoy":
        parts.append("tendance 12 mois : " + pct(trend_12m))
    if plateau is not None:
        parts.append(f"au plateau depuis {mois_annee(plateau['since'])}")
    if exact is not None:
        parts.append("total exact : " + milliers(exact))
    return " · ".join(parts)


# ============================ sérialisation ======================================
def lignes(df, mapping, date_col="Date"):
    """Sérialise un DataFrame en liste de dicts {date: 'YYYY-MM-DD', **mapping} en
    ignorant les valeurs NaN (mapping = {json_key: df_col})."""
    out = []
    for _, r in df.sort_values(date_col).iterrows():
        row = {"date": pd.Timestamp(r[date_col]).strftime("%Y-%m-%d")}
        for k, col in mapping.items():
            v = r.get(col)
            row[k] = None if (v is None or pd.isna(v)) else float(v)
        out.append(row)
    return out


def derniere_date(df, col, date_col="Date"):
    valid = df.dropna(subset=[col])
    return valid[date_col].max() if not valid.empty else pd.NaT


def iso_mois(value) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")
