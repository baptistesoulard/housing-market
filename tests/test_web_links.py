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
import sys

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


# --- Les affirmations chiffrées de l'accueil --------------------------------------------
# L'accueil est rédigé et STATIQUE : les robots d'aperçu de partage n'exécutent pas de
# JavaScript. Deux de ses affirmations dépendent pourtant des données — l'erreur du modèle
# dans la bande de chiffres, et l'horizon en deçà duquel il perd contre une prévision
# naïve. Écrites à la main, elles avaient dérivé toutes les deux (« 5,7 % à 6 mois » au rang
# du millésime pendant que la Synthèse parlait de six mois du lecteur ; « à moins de
# quatre mois » quand l'archive disait six). Elles sont désormais RÉÉCRITES par
# web/export/accueil.py entre des marqueurs ; ces tests vérifient que le fichier commité
# est bien ce que l'export écrirait à partir des JSON publiés.
PREVISIONS = WEB / "src" / "data" / "previsions.json"

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "web" / "export"))
import accueil                                                          # noqa: E402


def _json(chemin):
    return json.loads(chemin.read_text(encoding="utf-8"))


def _chiffres_de_l_accueil():
    """Les couples (nombre, légende) de la bande <ul class="hm-stats"> de l'accueil."""
    src = INDEX.read_text(encoding="utf-8")
    bande = re.search(r'<ul class="hm-stats">(.*?)</ul>', src, re.S)
    assert bande, "bande de chiffres introuvable dans index.md"
    couples = re.findall(
        r'<span class="n">(.*?)</span>\s*<span class="d">(.*?)</span>',
        bande.group(1), re.S)
    assert len(couples) == 4, f"4 chiffres attendus dans la bande, {len(couples)} trouvés"
    return [(n.strip(), re.sub(r"<[^>]+>", "", " ".join(d.split()))) for n, d in couples]


def test_les_passages_chiffres_de_l_accueil_sont_ceux_que_l_export_ecrirait():
    """Si ce test échoue, ne pas corriger index.md à la main : relancer
    python web/export/web_export.py, qui réécrit les passages entre leurs marqueurs."""
    attendu = accueil.rendu(_json(PREVISIONS), _json(ARCHIVE))
    present = accueil.passages_du_fichier(str(INDEX))
    for cle, texte in attendu.items():
        if texte is not None:
            assert present[cle] == texte, (
                f"hm:{cle} a dérivé — relancer python web/export/web_export.py")


def test_l_erreur_de_l_accueil_est_celle_du_verdict_et_cite_la_naive():
    """Le chiffre du bandeau est la fiabilité mesurée À L'HORIZON DU VERDICT — celui de la
    prévision publiée sur la Synthèse — et il ne se publie jamais sans l'erreur naïve :
    seul, il laisserait croire que le modèle bat la référence à tous les horizons."""
    rel = _json(PREVISIONS)["verdict"]["reliability"]
    fmt = lambda v: f"{v:.1f} %".replace(".", ",")
    n, legende = next((n, d) for n, d in _chiffres_de_l_accueil() if "erreur moyenne" in d)
    assert n == fmt(rel["mape"])
    assert fmt(rel["naive_mape"]) in legende


def test_l_erreur_de_l_accueil_dit_qu_elle_est_retro_simulee():
    """La page « Prévisions passées » refuse d'agréger prévisions publiées et rétro-simulées.
    Le bandeau cite un chiffre rétro-simulé : il doit le dire, et depuis quand."""
    premier = _json(ARCHIVE)["kinds"]["retro"]["first_vintage"][:4]
    legende = next(d for n, d in _chiffres_de_l_accueil() if "erreur moyenne" in d)
    assert "rétro-simulées" in legende and premier in legende


def test_la_bascule_annoncee_sur_l_accueil_est_celle_de_l_archive():
    crossover = _json(ARCHIVE)["crossover_horizon"]
    src = " ".join(INDEX.read_text(encoding="utf-8").split())
    assert accueil.phrase_bascule(crossover) in src


def test_contre_epreuve_une_bascule_perimee_serait_detectee():
    """Sans elle, le test précédent passerait même si la phrase ne dépendait pas de
    l'horizon : l'ancienne rédaction (bascule à quatre mois) ne doit PAS être acceptée."""
    crossover = _json(ARCHIVE)["crossover_horizon"]
    autre = accueil.phrase_bascule((crossover or 6) - 2)
    src = " ".join(INDEX.read_text(encoding="utf-8").split())
    assert autre not in src


# --- Le nombre de leviers du panneau de scénarios ---------------------------------------
# L'accueil et la description de la page annonçaient « quatre leviers » bien après la
# fusion des curseurs OAT et Euribor en un seul « taux de marché » : trois curseurs à
# l'écran, quatre promis dans la meta description. On compte les curseurs dans la page.
_LETTRES = {2: "deux", 3: "trois", 4: "quatre", 5: "cinq"}


def test_le_nombre_de_leviers_annonce_est_celui_de_la_page():
    page = (WEB / "src" / "previsions.md").read_text(encoding="utf-8")
    n = len(re.findall(r"const \w+Input = base \? Inputs\.range\(", page))
    assert n in _LETTRES, f"{n} curseurs de scénario trouvés"
    for chemin in (INDEX, CONFIG):
        texte = chemin.read_text(encoding="utf-8")
        annonces = set(re.findall(r"(\w+) leviers", texte))
        assert annonces == {_LETTRES[n]}, (
            f"{chemin.name} annonce {annonces} leviers, la page en a {n}")


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


# --- Stabilité d'écriture des flottants ------------------------------------------------
# Le 2026-09-07, le job hebdomadaire (runner Linux) et un export lancé en local ont écrit
# des valeurs distinctes d'un ULP pour la MÊME donnée — numpy n'est pas compilé de la même
# façon des deux côtés. Résultat : 814 lignes de diff sur previsions.json pour zéro
# information, et surtout un compteur « n/7 fichier(s) modifié(s) » qui perd son pouvoir
# d'alerte, puisqu'un fichier qui bouge à chaque exécution ne signale plus rien.

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import ecriture as we                                                   # noqa: E402

#: Les deux valeurs RÉELLEMENT observées, Linux contre Windows, pour le premier mois
#: projeté. Ce sont bien deux doubles différents : `repr` est déterministe pour un double
#: donné, donc deux représentations distinctes ne peuvent pas venir du formatage.
_LINUX, _WINDOWS = 935815.186488427, 935815.1864884269


def test_les_deux_doubles_observes_sont_bien_differents():
    """Contre-épreuve : sans elle, le test suivant pourrait passer pour de mauvaises
    raisons (deux fois la même valeur s'arrondit trivialement au même résultat)."""
    assert _LINUX != _WINDOWS


def test_l_arrondi_absorbe_la_derive_entre_machines():
    assert we.arrondir_flottants(_LINUX) == we.arrondir_flottants(_WINDOWS)


def test_l_arrondi_preserve_ce_qui_est_exact_et_ne_touche_ni_entiers_ni_booleens():
    """Un arrondi qui abîmerait les entiers ou les booléens serait pire que le défaut."""
    charge = {"ventes": 954000, "actif": True, "inactif": False, "taux": 3.18,
              "series": [{"v": _LINUX}, {"v": 0.9145580237141427}], "mois": "2027-03-01"}
    sortie = we.arrondir_flottants(charge)
    assert sortie["ventes"] == 954000 and isinstance(sortie["ventes"], int)
    assert sortie["actif"] is True and sortie["inactif"] is False
    assert sortie["taux"] == 3.18
    assert sortie["mois"] == "2027-03-01"
    # Neuf chiffres significatifs restent bien au-delà de tout besoin d'affichage.
    assert sortie["series"][1]["v"] == 0.914558024


def test_la_precision_reste_largement_au_dela_de_l_affichage():
    """Garde sur la constante : la descendre trop abîmerait des valeurs publiées."""
    assert 6 <= we.PRECISION_JSON <= 12
