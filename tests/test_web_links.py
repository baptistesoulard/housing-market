"""Les renvois de la page Synthèse pointent vers des pages qui existent.

Ces liens sont construits dans le NAVIGATEUR (`synthese.md` lit `blocks[].links` de
synthese.json et fabrique l'href), donc la validation de liens d'Observable Framework,
qui ne regarde que le Markdown, ne les voit pas. Renommer un chemin dans
`site.config.js` sans toucher `web_export.py` ne casserait donc rien au build : le site se
construirait sans avertissement, et le clic donnerait un 404 en production.

C'est ce trou-là que ferme ce test — il compare les chemins des deux côtés.
"""
import datetime
import json
import pathlib
import re

WEB = pathlib.Path(__file__).resolve().parent.parent / "web" / "observable"
# La navigation vit dans site.config.js — observablehq.config.js ne porte que le rendu.
CONFIG = WEB / "site.config.js"
SYNTHESE = WEB / "src" / "data" / "synthese.json"
ARCHIVE = WEB / "src" / "data" / "archive.json"
INDEX = WEB / "src" / "index.md"


def _declared_paths():
    """Les chemins de la barre latérale, lus dans le tableau NAV de la config."""
    nav = re.search(r"const NAV = \[(.*?)\n\];", CONFIG.read_text(encoding="utf-8"), re.S)
    assert nav, "tableau NAV introuvable dans site.config.js"
    return set(re.findall(r'path:\s*"([^"]+)"', nav.group(1)))


def test_shortcut_paths_exist():
    blocks = json.loads(SYNTHESE.read_text(encoding="utf-8"))["blocks"]
    declared = _declared_paths()
    used = {link["path"] for b in blocks for link in b["links"]}
    assert used, "aucun renvoi dans synthese.json"
    assert used <= declared, f"chemins inconnus : {sorted(used - declared)}"


def test_shortcut_labels_match_the_sidebar():
    """Le libellé du renvoi est celui de l'onglet : deux noms pour une même page
    obligeraient le lecteur à faire le rapprochement lui-même."""
    src = CONFIG.read_text(encoding="utf-8")
    nav = re.search(r"const NAV = \[(.*?)\n\];", src, re.S).group(1)
    names = dict(zip(re.findall(r'path:\s*"([^"]+)"', nav),
                     re.findall(r'name:\s*"([^"]+)"', nav)))
    blocks = json.loads(SYNTHESE.read_text(encoding="utf-8"))["blocks"]
    for b in blocks:
        for link in b["links"]:
            assert link["label"] == names[link["path"]], (
                f"{link['path']} : « {link['label']} » côté Synthèse, "
                f"« {names[link['path']]} » côté barre latérale")


# --- La bande de chiffres de l'accueil ------------------------------------------------
# Ces quatre nombres sont écrits en DUR dans index.md, et c'est délibéré : ils doivent
# être lus par les robots d'aperçu de partage, qui n'exécutent pas de JavaScript (voir le
# commentaire de la page). Trois d'entre eux sont des constantes de fait — profondeur
# d'historique, nombre de producteurs, cadence du rafraîchissement. Le quatrième, lui,
# est recalculé à chaque publication de données : sans garde, il dérive en silence et
# l'accueil finit par annoncer une performance que la page « Prévisions passées »
# contredit deux clics plus loin.
_ERREUR_6M = "Erreur moyenne à 6 mois"


def _chiffres_de_l_accueil():
    """Les couples (nombre, légende) de la bande <ul class="hm-stats"> de l'accueil."""
    src = INDEX.read_text(encoding="utf-8")
    bande = re.search(r'<ul class="hm-stats">(.*?)</ul>', src, re.S)
    assert bande, "bande de chiffres introuvable dans index.md"
    couples = re.findall(
        r'<span class="n">(.*?)</span>\s*<span class="d">(.*?)</span>',
        bande.group(1), re.S)
    assert len(couples) == 4, f"4 chiffres attendus dans la bande, {len(couples)} trouvés"
    return [(n.strip(), " ".join(d.split())) for n, d in couples]


def _kpi_archive(label):
    kpis = json.loads(ARCHIVE.read_text(encoding="utf-8"))["kpis"]
    trouve = [k for k in kpis if k["label"] == label]
    assert trouve, f"KPI « {label} » absent d'archive.json"
    return trouve[0]


def test_l_erreur_annoncee_sur_l_accueil_est_celle_de_l_archive():
    """L'accueil et la page « Prévisions passées » doivent citer le MÊME chiffre.

    Si ce test échoue, ce n'est pas archive.json qu'il faut corriger : c'est la valeur
    codée dans la bande de chiffres de web/observable/src/index.md qu'il faut reporter.
    """
    kpi = _kpi_archive(_ERREUR_6M)
    modele = next(n for n, d in _chiffres_de_l_accueil() if "erreur moyenne à 6 mois" in d)
    assert modele == kpi["value"], (
        f"l'accueil annonce {modele} d'erreur à 6 mois, l'archive {kpi['value']} — "
        "reporter la valeur dans la bande de chiffres d'index.md")


def test_l_accueil_cite_aussi_la_reference_naive():
    """Le chiffre du modèle ne se publie jamais seul.

    Isolé, il laisse croire que le modèle bat la référence naïve à tous les horizons,
    alors qu'il lui est INFÉRIEUR en deçà de quatre mois (voir « Prévisions passées »).
    La légende doit donc porter l'erreur naïve, et la même que l'archive.
    """
    kpi = _kpi_archive(_ERREUR_6M)
    naif = re.search(r"([\d,]+\s*%)", " ".join(kpi["subs"]))
    assert naif, f"erreur naïve absente des sous-titres du KPI « {_ERREUR_6M} »"
    legende = next(d for n, d in _chiffres_de_l_accueil() if "erreur moyenne à 6 mois" in d)
    assert naif.group(1) in legende, (
        f"l'accueil doit citer l'erreur naïve ({naif.group(1)}) à côté de celle du "
        f"modèle ; légende actuelle : « {legende} »")


# --- La base 100 du graphique croisé --------------------------------------------------
# Le graphique neuf/ancien est le seul du site dont le site CALCULE lui-même l'indice (les
# indices de prix arrivent déjà en base 2015 de l'INSEE). Il a d'abord été indexé sur le
# premier mois commun de 2022 : une base sans signification, et différente de celle de tous
# les autres graphiques — deux courbes « base 100 » de deux pages ne se comparaient pas.
# Ce test verrouille la convention INSEE, sur le fichier RÉELLEMENT publié.
_TOLERANCE = 0.05          # les valeurs de l'export sont arrondies à 0,01


def _chart():
    return json.loads(SYNTHESE.read_text(encoding="utf-8"))["chart"]


def test_le_graphique_croise_est_en_base_100_sur_2015():
    """Pour chaque série, la moyenne des douze indices de 2015 doit valoir 100."""
    rows = [r for r in _chart()["rows"] if r["index_100"] is not None]
    assert rows, "aucun point indexé dans synthese.json"
    par_serie = {}
    for r in rows:
        if r["date"].startswith("2015"):
            par_serie.setdefault(r["series"], []).append(r["index_100"])
    assert par_serie, "aucun point de 2015 — la base ne peut pas être vérifiée"
    for serie, valeurs in par_serie.items():
        assert len(valeurs) == 12, f"{serie} : {len(valeurs)} mois en 2015, 12 attendus"
        moyenne = sum(valeurs) / 12
        assert abs(moyenne - 100.0) < _TOLERANCE, (
            f"{serie} : moyenne 2015 = {moyenne:.2f} au lieu de 100 — la base a dérivé, "
            "relancer python web/export/web_export.py")


def test_le_libelle_de_base_annonce_la_meme_annee():
    """Le titre du panneau vient de ce champ : une base 2015 annoncée « 2022 » serait
    pire qu'une base arbitraire assumée."""
    label = _chart()["base_label"]
    assert label and "2015" in label, f"libellé de base inattendu : {label!r}"


# --- Aucun levier de scénario ne doit être inerte -------------------------------------
# Histoire de ce garde-fou, qui explique sa forme actuelle. L'étage 1 régressait sur l'OAT
# ET l'Euribor, corrélés à +0,83 : l'ajustement attribuait presque tout au premier (0,707
# contre 0,013), si bien que le curseur Euribor de la page était INERTE — balayé sur toute
# sa course il déplaçait la prévision de 0,3 %, contre 11 à 24 % pour les trois autres. On
# a d'abord fusionné les deux curseurs, puis mesuré que l'Euribor ne servait à rien du tout
# (voir forecast.RATE_DRIVER) et on l'a retiré du modèle. Il reste UN taux de marché, dont
# ces deux tests vérifient qu'il pilote réellement quelque chose.
PREVISIONS_JSON = WEB / "src" / "data" / "previsions.json"
PREVISIONS_MD = WEB / "src" / "previsions.md"


def test_la_sensibilite_du_financement_est_materielle():
    """Le seul coefficient de marché doit rester un levier réel."""
    data = json.loads(PREVISIONS_JSON.read_text(encoding="utf-8"))
    if not data.get("available"):
        return                                   # modèle non calibré : rien à vérifier
    coef = data["rate"]["coefficients"]
    assert coef["oat"] >= 0.25, (
        f"+1 pt d'OAT ne déplace le taux de crédit que de {coef['oat']:.3f} pt — "
        "le panneau de scénarios n'a plus de levier de financement digne de ce nom")


def test_la_page_n_expose_pas_de_curseur_de_taux_hors_marche():
    """Un curseur par taux ramènerait le levier inerte d'avant.

    La page peut parfaitement nommer l'OAT dans son texte — c'est même souhaitable — mais
    pas exposer plusieurs taux comme des entrées indépendantes.
    """
    src = PREVISIONS_MD.read_text(encoding="utf-8")
    etiquettes = re.findall(r'Inputs\.range\([^)]*?\{[^}]*?label:\s*"([^"]+)"', src, re.S)
    fautives = [e for e in etiquettes if "Euribor" in e]
    assert not fautives, (
        f"curseur(s) Euribor exposé(s) : {fautives} — l'Euribor ne fait plus partie du "
        "modèle de taux (voir forecast.RATE_DRIVER)")


def test_le_modele_de_taux_publie_son_delai_de_repercussion():
    """Sans le délai affiché, le coefficient de l'étage 1 est illisible.

    Il dit de combien le taux de crédit bouge, mais pas QUAND — et c'est cette seconde
    moitié qui manquait avant que le délai ne soit estimé.
    """
    data = json.loads(PREVISIONS_JSON.read_text(encoding="utf-8"))
    if not data.get("available"):
        return
    r = data["rate"]
    assert isinstance(r.get("lag"), int) and 0 <= r["lag"] <= 12, (
        f"délai de répercussion absent ou invraisemblable : {r.get('lag')}")
    coef = r["coefficients"]
    assert "euribor" not in coef, "l'Euribor a été retiré de l'étage 1 — voir RATE_DRIVER"
    assert abs(coef["marche"] - coef["oat"]) < 1e-9, (
        "`marche` doit valoir le coefficient de l'OAT : un seul taux, un seul levier")
    for p in r.get("projected", []):
        assert p["source"] < p["date"], (
            "un mois projeté doit venir d'un mois de marché ANTÉRIEUR — sinon la "
            "projection contient une hypothèse au lieu de taux déjà publiés")


def test_les_hypotheses_ecartees_sont_publiees_avec_leur_date():
    data = json.loads(PREVISIONS_JSON.read_text(encoding="utf-8"))
    refs = data.get("refutations")
    assert refs, "les hypothèses écartées ont disparu de previsions.json"
    for r in refs:
        for champ in ("titre", "idee", "mesure", "lecon", "mesure_le"):
            assert r.get(champ), f"« {r.get('titre', '?')} » : champ {champ} manquant"
        datetime.date.fromisoformat(r["mesure_le"])       # lève si la date est mal formée


def test_la_page_de_prevision_affiche_la_section_des_hypotheses_ecartees():
    src = PREVISIONS_MD.read_text(encoding="utf-8")
    assert "refutations" in src, (
        "previsions.md n'affiche plus les hypothèses écartées — publier uniquement ce qui "
        "a marché est un biais de sélection, pas une simplification")


def test_le_repere_de_taux_dit_sa_source_et_sa_date_de_releve():
    """Le repère analyste sur le taux de crédit, même discipline que celui des volumes.

    Il est plus solide que le repère FNAIM sur un point : l'Observatoire Crédit Logement/CSA
    PRODUIT la série que le site modélise, donc sa prévision porte exactement sur la même
    grandeur — aucun écart de périmètre à expliquer. Il est plus fragile sur un autre : son
    horizon ne recouvre pas celui que nos taux de marché publiés permettent de déterminer,
    et la page doit le dire plutôt que de laisser croire à une comparaison terme à terme.
    """
    data = json.loads(PREVISIONS_JSON.read_text(encoding="utf-8"))
    if not data.get("available") or not data.get("benchmark_taux"):
        return
    b = data["benchmark_taux"]
    assert b.get("url", "").startswith("http"), "le repère de taux doit porter son lien"
    datetime.date.fromisoformat(b["releve_le"])
    assert 0 < b["valeur"] < 15, f"repère de taux invraisemblable : {b['valeur']}"
    assert b.get("note"), "le décalage d'horizon doit être explicité"
