"""Le fond de carte des départements, construit UNE fois et versionné.

    python web/export/fond_de_carte.py

Outil ponctuel, comme `dvf_backfill.py` ou `npm run og-image` : les limites des
départements ne bougent pas d'une semaine à l'autre, donc le job hebdomadaire ne le lance
pas. Il écrit `web/observable/src/data/departements-geo.json`, que la page « Carte des
départements » lit tel quel.

Source : contours administratifs d'Etalab (dérivés d'IGN Admin Express, Licence ouverte
2.0), version déjà simplifiée à 1 000 m. Trois transformations, toutes pour le poids et
la lisibilité, aucune pour la géographie :

* **coordonnées arrondies à 0,001°** (≈ 100 m), très en deçà de la résolution de la
  source et d'un pixel à l'échelle de la page ;
* **simplification de Douglas-Peucker à 0,008°** par anneau (moins d'un demi-pixel sur la
  carte de la page ; 0,002° pour la copie agrandie de Paris et de la petite couronne).
  Chaque polygone est simplifié séparément, donc deux voisins peuvent laisser entre eux
  un interstice de quelques centaines de mètres : le trait blanc de séparation le
  recouvre ;
* **l'outre-mer rapproché en encarts**, à l'ouest de la Bretagne. Chaque territoire
  garde sa forme (échelle uniforme, correction de la latitude) mais pas sa taille : un
  encart n'est pas à l'échelle de la métropole, et la page le dit. Les cadres des
  encarts sont livrés à part (`cadres`), pour être tracés sans être coloriés ;
* **Paris et la petite couronne dupliqués en agrandi** (propriété `zoom`), au nord-est :
  à l'échelle nationale ces quatre départements tiennent en quelques pixels, alors que
  Paris est le cas que chaque lecteur cherche. La copie normale reste à sa place.

Seuls les 101 départements sont gardés : la source porte aussi les collectivités d'outre-
mer (Polynésie, Nouvelle-Calédonie…), que ni DVF ni le site ne couvrent.

La taille visée est de l'ordre de 200 Ko bruts, soit un tiers une fois compressé par le
CDN : le fichier est chargé à chaque ouverture de la page, et la page « Marché du neuf » en
sert déjà plus de 500.
"""
from __future__ import annotations

import json
import math
import os
import sys
import urllib.request

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SOURCE = ("https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/latest/"
          "geojson/departements-1000m.geojson")
SORTIE = os.path.join(_REPO_ROOT, "web", "observable", "src", "data", "departements-geo.json")

DECIMALES = 3
TOLERANCE = 0.008          # en degrés, pour Douglas-Peucker
TOLERANCE_ZOOM = 0.002

#: Encarts de l'outre-mer : centre (lon, lat) de l'encart et hauteur de sa boîte, en
#: degrés. Une colonne à l'ouest de la Bretagne, dans l'Atlantique, où rien d'autre ne
#: s'affiche. La latitude de pose (~42-48°) raccourcit un degré de longitude d'environ
#: 30 % dans la projection conique de la page : on l'étire d'autant pour garder la forme.
ENCARTS = {
    "971": ("Guadeloupe", (-7.6, 48.6)),
    "972": ("Martinique", (-7.6, 47.05)),
    "973": ("Guyane", (-7.6, 45.5)),
    "974": ("La Réunion", (-7.6, 43.95)),
    "976": ("Mayotte", (-7.6, 42.4)),
}
#: Hauteur d'un encart ; l'écart entre deux centres (1,55°) laisse la place de l'étiquette
#: posée au-dessus de chaque cadre.
HAUTEUR_ENCART = 1.0

#: Paris et la petite couronne, recopiés en agrandi. Le centre de pose est au nord-est de
#: la métropole (au-dessus de l'Allemagne, qui n'est pas tracée), le facteur est choisi
#: pour que Paris y soit lisible sans que l'encart déborde de la page.
ZOOM_IDF = ("75", "92", "93", "94")
ZOOM_CENTRE = (8.6, 50.3)
ZOOM_FACTEUR = 5.0

#: La projection de la page (carteDepartements, hm.js) : conique conforme, parallèles
#: 44° et 49°, méridien central 3° E. À GARDER ALIGNÉ avec hm.js. Dans cette projection
#: les méridiens convergent : un encart posé loin du méridien central y apparaît tourné
#: d'un angle n·(λ − λ0) — les cadres de l'outre-mer penchaient de près de 8°. Chaque
#: encart est donc pré-tourné de l'angle opposé, autour de son centre, pour s'afficher
#: droit.
PROJ_PARALLELES = (44.0, 49.0)
PROJ_MERIDIEN = 3.0


def _cone():
    """Constante n de la conique conforme (Snyder, éq. 15-3)."""
    p1, p2 = (math.radians(p) for p in PROJ_PARALLELES)
    return (math.log(math.cos(p1) / math.cos(p2))
            / math.log(math.tan(math.pi / 4 + p2 / 2) / math.tan(math.pi / 4 + p1 / 2)))


def _redresser(geom, centre):
    """Pré-rotation d'une géométrie autour de `centre`, qui compense la convergence des
    méridiens à la longitude de pose. Calculée dans le plan local (est, nord) — la
    longitude pondérée par cos(latitude) —, puis ramenée en degrés."""
    lon0, lat0 = centre
    a = math.radians(-_cone() * (lon0 - PROJ_MERIDIEN))
    k = math.cos(math.radians(lat0))
    ca, sa = math.cos(a), math.sin(a)

    def tourner(x, y):
        e, n = (x - lon0) * k, y - lat0
        return [round(lon0 + (e * ca - n * sa) / k, DECIMALES),
                round(lat0 + e * sa + n * ca, DECIMALES)]

    if geom["type"] == "Polygon":
        return {"type": "Polygon",
                "coordinates": [[tourner(x, y) for x, y in r] for r in geom["coordinates"]]}
    return {"type": "MultiPolygon",
            "coordinates": [[[tourner(x, y) for x, y in r] for r in p]
                            for p in geom["coordinates"]]}


def _telecharger(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "barometre-logement (fond de carte)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def _douglas_peucker(points, tol):
    """Simplification itérative (pas de récursion : certains anneaux ont des milliers de points)."""
    if len(points) < 3:
        return points
    garder = [False] * len(points)
    garder[0] = garder[-1] = True
    pile = [(0, len(points) - 1)]
    while pile:
        a, b = pile.pop()
        (xa, ya), (xb, yb) = points[a], points[b]
        dx, dy = xb - xa, yb - ya
        norme = math.hypot(dx, dy)
        loin, idx = -1.0, None
        for i in range(a + 1, b):
            x, y = points[i]
            d = (abs(dy * x - dx * y + xb * ya - yb * xa) / norme) if norme else math.hypot(x - xa, y - ya)
            if d > loin:
                loin, idx = d, i
        if idx is not None and loin > tol:
            garder[idx] = True
            pile += [(a, idx), (idx, b)]
    return [p for p, k in zip(points, garder) if k]


def _anneau(anneau, tol):
    pts = [(round(x, DECIMALES), round(y, DECIMALES)) for x, y in anneau]
    dedup = [pts[0]] + [p for i, p in enumerate(pts[1:], 1) if p != pts[i - 1]]
    simple = _douglas_peucker(dedup, tol)
    if simple[0] != simple[-1]:
        simple.append(simple[0])
    return [list(p) for p in simple] if len(simple) >= 4 else None


def _polygones(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    return geom["coordinates"]


def _nettoyer(geom, tol):
    polys = []
    for poly in _polygones(geom):
        anneaux = [r for r in (_anneau(a, tol) for a in poly) if r]
        if anneaux:
            polys.append(anneaux)
    return {"type": "MultiPolygon", "coordinates": polys}


def _deplacer(geom, centre, hauteur):
    """Échelle uniforme + translation, pour poser un territoire dans son encart."""
    xs = [x for p in geom["coordinates"] for r in p for x, _ in r]
    ys = [y for p in geom["coordinates"] for r in p for _, y in r]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    lat_src = (y0 + y1) / 2
    # Un degré de longitude vaut cos(lat) degré de latitude : on ramène la source à des
    # distances vraies, puis on les exprime à la latitude de pose.
    etire = math.cos(math.radians(lat_src)) / math.cos(math.radians(centre[1]))
    largeur, haut = (x1 - x0) * etire, (y1 - y0)
    k = hauteur / max(haut, largeur * math.cos(math.radians(centre[1])))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2

    def pos(x, y):
        return [round(centre[0] + (x - cx) * etire * k, DECIMALES),
                round(centre[1] + (y - cy) * k, DECIMALES)]

    coords = [[[pos(x, y) for x, y in r] for r in p] for p in geom["coordinates"]]
    return {"type": "MultiPolygon", "coordinates": coords}


def _cadre(centre, hauteur):
    demi_h = hauteur / 2 + 0.12
    demi_l = demi_h / math.cos(math.radians(centre[1]))
    (cx, cy) = centre
    r = [[cx - demi_l, cy - demi_h], [cx - demi_l, cy + demi_h], [cx + demi_l, cy + demi_h],
         [cx + demi_l, cy - demi_h], [cx - demi_l, cy - demi_h]]
    return {"type": "Polygon", "coordinates": [[[round(x, DECIMALES), round(y, DECIMALES)]
                                                for x, y in r]]}


def _zoomer(geom, centre_src):
    """Agrandit autour du centre de l'Île-de-France et pose la copie à ZOOM_CENTRE."""
    (sx, sy), (cx, cy) = centre_src, ZOOM_CENTRE
    etire = math.cos(math.radians(sy)) / math.cos(math.radians(cy))
    coords = [[[[round(cx + (x - sx) * etire * ZOOM_FACTEUR, DECIMALES),
                 round(cy + (y - sy) * ZOOM_FACTEUR, DECIMALES)] for x, y in r]
               for r in p] for p in geom["coordinates"]]
    return {"type": "MultiPolygon", "coordinates": coords}


def construire(source: dict, codes=None) -> dict:
    """`codes` : les départements à garder (par défaut ceux de `departements.py`)."""
    if codes is None:
        sys.path.insert(0, _REPO_ROOT)
        import departements
        codes = set(departements.DEPARTEMENTS)
    source_feats = [f for f in source["features"] if str(f["properties"]["code"]) in codes]
    features, cadres = [], []
    # Centre de la zone agrandie : le centre de la boîte des quatre départements.
    idf = [_nettoyer(f["geometry"], TOLERANCE_ZOOM) for f in source_feats
           if str(f["properties"]["code"]) in ZOOM_IDF]
    xs = [x for g in idf for p in g["coordinates"] for r in p for x, _ in r]
    ys = [y for g in idf for p in g["coordinates"] for r in p for _, y in r]
    centre_idf = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2) if xs else None
    for f in source_feats:
        code = str(f["properties"]["code"])
        geom = _nettoyer(f["geometry"], TOLERANCE)
        if code in ZOOM_IDF and centre_idf:
            zoom = _zoomer(_nettoyer(f["geometry"], TOLERANCE_ZOOM), centre_idf)
            features.append({"type": "Feature",
                             "properties": {"code": code, "nom": f["properties"]["nom"],
                                            "zoom": True},
                             "geometry": _redresser(zoom, ZOOM_CENTRE)})
        if code in ENCARTS:
            nom_encart, centre = ENCARTS[code]
            geom = _redresser(_deplacer(geom, centre, HAUTEUR_ENCART), centre)
            cadres.append({"type": "Feature", "properties": {"code": code, "nom": nom_encart},
                           "geometry": _redresser(_cadre(centre, HAUTEUR_ENCART), centre)})
        features.append({"type": "Feature",
                         "properties": {"code": code, "nom": f["properties"]["nom"]},
                         "geometry": geom})
    if centre_idf:
        demi_h = (max(ys) - min(ys)) / 2 * ZOOM_FACTEUR + 0.15
        cadres.append({"type": "Feature",
                       "properties": {"code": "idf", "nom": "Paris et petite couronne"},
                       "geometry": _redresser(_cadre(ZOOM_CENTRE, 2 * (demi_h - 0.12)),
                                              ZOOM_CENTRE)})
    features.sort(key=lambda f: (f["properties"]["code"], f["properties"].get("zoom", False)))
    return {"type": "FeatureCollection",
            "source": ("Contours administratifs Etalab (IGN Admin Express), Licence "
                       "ouverte 2.0 — simplifiés ; outre-mer en encarts, hors échelle"),
            "features": features, "cadres": cadres}


def main():
    fond = construire(_telecharger(SOURCE))
    texte = json.dumps(fond, ensure_ascii=False, separators=(",", ":"))
    with open(SORTIE, "w", encoding="utf-8") as f:
        f.write(texte)
    print(f"{SORTIE} : {len(fond['features'])} départements, {len(texte.encode()) / 1024:.0f} Ko")


if __name__ == "__main__":
    sys.exit(main())
