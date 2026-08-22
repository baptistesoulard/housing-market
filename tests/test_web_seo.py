"""Le site est-il PARTAGEABLE et INDEXABLE — les balises qu'aucun rendu ne montre.

Rien de ce que ce module vérifie n'est visible à l'écran : une balise `og:` absente, une
URL canonique qui pointe ailleurs ou un sitemap qui liste une page morte ne cassent aucune
page. Ils cassent l'aperçu d'un lien partagé sur LinkedIn et le référencement — deux choses
qu'on ne découvre qu'une fois le lien publié, c'est-à-dire trop tard.

Les descriptions et la navigation vivent dans `web/observable/site.config.js`, que le
`<head>` (`observablehq.config.js`) et le post-traitement de build (`scripts/postbuild.mjs`)
consomment. Ces trois fichiers étant en JavaScript, le test les fait tourner par Node —
comme `tests/test_web_js_parity.py`. Il se skippe si Node est absent ; aucun `npm install`
n'est nécessaire, ces modules n'important rien de `node_modules`.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile

import pytest

NODE = shutil.which("node")
WEB = pathlib.Path(__file__).resolve().parent.parent / "web" / "observable"
SITE_CONFIG = WEB / "site.config.js"
OHQ_CONFIG = WEB / "observablehq.config.js"

pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js absent")

# Une adresse de test, DIFFÉRENTE du repli codé dans site.config.js : c'est ce qui prouve
# que les URL absolues sont bien construites à partir du réglage, et non écrites en dur.
SITE_URL = "https://exemple.test"


# `encoding="utf-8"` n'est pas décoratif : sans lui, `text=True` décode la sortie de
# Node avec la page de codes ANSI du système (cp1252 sous Windows). Le thread lecteur de
# subprocess lève alors sur le premier caractère hors table — un tiret cadratin suffit —,
# `stdout` revient à None et le test échoue sur un TypeError de json.loads sans rapport
# apparent, alors que Node a rendu 0. Node écrit toujours en UTF-8.
def _node(script, **env):
    """Exécute un module ES et renvoie ce qu'il a écrit sur stdout, décodé en JSON."""
    with tempfile.TemporaryDirectory() as d:
        probe = pathlib.Path(d) / "probe.mjs"
        probe.write_text(script, encoding="utf-8")
        out = subprocess.run([NODE, str(probe)], capture_output=True, text=True, encoding="utf-8", timeout=120,
                             env={**os.environ, "HM_SITE_URL": SITE_URL, **env})
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@pytest.fixture(scope="module")
def heads():
    """Le <head> rendu par la config, page par page, plus l'identité du site."""
    return _node(f"""
import {{SITE, NAV, INDEXABLE, AUTHOR, pageMeta}} from {json.dumps(SITE_CONFIG.as_uri())};
import config from {json.dumps(OHQ_CONFIG.as_uri())};
// Le framework appelle head() par page en lui passant son chemin INTERNE : « /index »
// pour l'accueil, « /404 » pour la page d'erreur.
const paths = [...NAV.map((p) => (p.path === "/" ? "/index" : p.path)), "/404"];
process.stdout.write(JSON.stringify({{
  site: SITE, nav: NAV, indexable: INDEXABLE, author: AUTHOR,
  title: config.title, pages: config.pages,
  meta: Object.fromEntries(paths.map((p) => [p, pageMeta(p)])),
  head: Object.fromEntries(paths.map((p) => [p, config.head({{path: p, title: null, data: {{}}}})])),
}}));
""")


def test_chaque_page_declaree_existe(heads):
    """Une entrée de NAV sans fichier donnerait un lien de barre latérale vers un 404."""
    for page in heads["nav"]:
        name = "index" if page["path"] == "/" else page["path"].lstrip("/")
        assert (WEB / "src" / f"{name}.md").exists(), f"{page['path']} n'a pas de source"


def test_descriptions_uniques_et_courtes(heads):
    """Deux pages qui partagent leur description se cannibalisent dans les résultats ;
    au-delà d'environ 160 caractères, Google et LinkedIn tronquent."""
    descriptions = [p["description"] for p in heads["nav"]]
    assert len(set(descriptions)) == len(descriptions), "description dupliquée entre deux pages"
    for page in heads["nav"]:
        assert 60 <= len(page["description"]) <= 165, (
            f"{page['path']} : description de {len(page['description'])} caractères")


def test_les_pages_indexables_portent_leurs_balises(heads):
    """Description, adresse canonique et carte de partage — sur CHAQUE page servie."""
    for page in heads["nav"]:
        internal = "/index" if page["path"] == "/" else page["path"]
        head = heads["head"][internal]
        attendu = SITE_URL + page["path"]
        assert f'<link rel="canonical" href="{attendu}">' in head, page["path"]
        for balise in ("og:title", "og:description", "og:url", "og:image", "twitter:card"):
            assert balise in head, f"{page['path']} : {balise} manquante"
        assert 'name="robots"' not in head, f"{page['path']} ne doit pas être désindexée"


def test_les_url_de_partage_sont_absolues(heads):
    """Open Graph n'accepte pas les chemins relatifs : les robots des réseaux sociaux
    récupèrent la page depuis LEURS serveurs, où « /og-image.png » ne veut rien dire."""
    for internal, head in heads["head"].items():
        for ligne in head.splitlines():
            if 'property="og:url"' in ligne or 'property="og:image"' in ligne or 'name="twitter:image"' in ligne:
                assert f'content="{SITE_URL}/' in ligne, f"{internal} : URL relative — {ligne}"


def test_la_page_404_est_desindexee(heads):
    """Elle répond pour n'importe quelle adresse fausse : l'indexer publierait autant de
    pages vides que d'URL erronées, et une canonique n'y aurait aucun sens."""
    head = heads["head"]["/404"]
    assert '<meta name="robots" content="noindex, follow">' in head
    assert "rel=\"canonical\"" not in head
    assert heads["meta"]["/404"]["indexable"] is False


def test_le_titre_situe_le_site(heads):
    """« HousingMarket » seul ne dit ni de quel marché ni de quel pays il s'agit, alors
    que c'est souvent la seule ligne lue avant le clic."""
    assert heads["title"] == heads["site"]["fullName"]
    assert heads["site"]["name"] in heads["title"] and len(heads["title"]) <= 60


def test_l_accueil_n_est_pas_un_onglet(heads):
    """Il est atteint par le bloc de marque de la barre latérale ; l'ajouter aux onglets
    ferait deux entrées de navigation pour une seule page."""
    assert "/" not in [p["path"] for p in heads["pages"]]
    assert "/" in heads["indexable"], "l'accueil doit rester dans le sitemap"


def _ld(head):
    """Les blocs JSON-LD d'un <head>, décodés."""
    out = []
    for morceau in head.split('<script type="application/ld+json">')[1:]:
        out.append(json.loads(morceau.split("</script>")[0]))
    return out


def test_l_auteur_est_une_entite_reliee_et_non_un_nom_recopie(heads):
    """Le nœud Person doit exister sur « À propos », et l'accueil doit le RÉFÉRENCER.

    Avant, l'accueil portait `author: {"@type": "Person", name: "Baptiste Soulard"}` — un
    nom nu, que rien ne reliait à un profil. Le nom est porté par plusieurs personnes :
    sans identifiant partagé entre les deux pages, un moteur ne voit pas un auteur mais
    deux mentions homonymes de plus.
    """
    auteur = heads["author"]
    attendu = SITE_URL + auteur["page"] + "#" + auteur["anchor"]

    (site,) = [n for n in _ld(heads["head"]["/index"]) if n["@type"] == "WebSite"]
    assert site["author"] == {"@id": attendu}, "l'accueil doit référencer l'auteur, pas le recopier"

    (profil,) = [n for n in _ld(heads["head"][auteur["page"]]) if n["@type"] == "ProfilePage"]
    personne = profil["mainEntity"]
    assert personne["@id"] == attendu, "l'identifiant défini ici doit être celui que l'accueil vise"
    assert personne["name"] == heads["site"]["author"]
    assert personne["sameAs"] == auteur["sameAs"]


def test_les_profils_de_l_auteur_sont_des_url_canoniques(heads):
    """Un lien de profil copié depuis une application mobile arrive avec ses paramètres de
    suivi (`?utm_source=share_via&…`). Ils identifient le PARTAGE, pas le profil : déclarés
    en `sameAs`, ils désignent une adresse qui ne se recoupe avec aucune autre."""
    for url in heads["author"]["sameAs"]:
        assert url.startswith("https://"), url
        assert "?" not in url and "utm_" not in url, f"paramètre de suivi dans {url}"
    assert len(set(heads["author"]["sameAs"])) == len(heads["author"]["sameAs"])


def test_la_page_auteur_lie_les_memes_profils_qu_elle_declare(heads):
    """Le balisage déclare la correspondance entre profils, les liens visibles la
    corroborent — les deux doivent dire la même chose. Un profil ajouté d'un seul côté
    laisse l'appariement à moitié fait, sans que rien ne le signale.

    `rel="me"` est le pendant HTML de `sameAs` : le JSON-LD s'adresse aux moteurs, cet
    attribut est dans le document lui-même et d'autres consommateurs s'en servent. Les
    deux listes doivent coïncider.
    """
    page = (WEB / "src" / (heads["author"]["page"].lstrip("/") + ".md")).read_text(encoding="utf-8")
    for url in heads["author"]["sameAs"]:
        assert url in page, f"{url} est déclaré en sameAs mais n'est lié nulle part dans la page"
        assert re.search(rf'rel="me"\s+href="{re.escape(url)}"', page), (
            f"{url} est lié sans rel=\"me\" : la page ne le déclare pas comme un profil de l'auteur")

    # ...et l'inverse : un rel="me" vers une adresse absente du sameAs laisse l'autre
    # moitié de l'appariement muette.
    for url in re.findall(r'rel="me"\s+href="([^"]+)"', page):
        assert url in heads["author"]["sameAs"], f"{url} est déclaré rel=\"me\" mais absent de sameAs"


def test_aucune_adresse_electronique_dans_l_identite_publique(heads):
    """Le dépôt est public : une adresse écrite dans un fichier versionné est moissonnée
    aussi sûrement que dans un `mailto:`. Le contact passe par le formulaire, dont la
    destination est une variable d'environnement (voir web/README.md)."""
    # Les deux motifs cherchent une ADRESSE, pas le mot « mailto » : les commentaires de
    # ces fichiers expliquent justement pourquoi il n'y en a pas, et se citer soi-même ne
    # doit pas déclencher l'alerte.
    for fichier in (SITE_CONFIG, WEB / "src" / (heads["author"]["page"].lstrip("/") + ".md")):
        texte = fichier.read_text(encoding="utf-8")
        assert not re.search(r"mailto:\S*@", texte), f"{fichier.name} expose une adresse en clair"
        assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]{2,}", texte), f"{fichier.name} contient une adresse"


def test_postbuild_complete_le_html_et_ecrit_le_sitemap(heads, tmp_path):
    """Trois choses qu'`observable build` ne pose pas : la langue du document, un lien
    d'évitement et un sitemap. Le script est lancé sur un dist/ jetable."""
    page = tmp_path / "index.html"
    page.write_text('<!DOCTYPE html>\n<html>\n<head>\n<meta charset="utf-8">\n</head>\n'
                    '<body><main id="observablehq-main">x</main></body>\n</html>\n', encoding="utf-8")
    out = subprocess.run([NODE, str(WEB / "scripts" / "postbuild.mjs"), str(tmp_path)],
                         capture_output=True, text=True, encoding="utf-8", timeout=120,
                         env={**os.environ, "HM_SITE_URL": SITE_URL})
    assert out.returncode == 0, out.stderr

    html = page.read_text(encoding="utf-8")
    assert '<html lang="fr">' in html, "WCAG 3.1.1 : la langue du document doit être déclarée"
    assert 'class="hm-skip"' in html, "lien d'évitement absent"
    assert 'rel="icon"' in html

    sitemap = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    attendus = {SITE_URL + p for p in heads["indexable"]}
    assert set(__import__("re").findall(r"<loc>([^<]+)</loc>", sitemap)) == attendus
    assert "/404" not in sitemap, "la page d'erreur n'a rien à faire dans un sitemap"
    assert f"Sitemap: {SITE_URL}/sitemap.xml" in (tmp_path / "robots.txt").read_text(encoding="utf-8")


def test_postbuild_est_idempotent(tmp_path):
    """Il est relancé à chaque build, parfois sur un dist/ déjà traité (rebuild partiel) :
    il ne doit pas empiler deux liens d'évitement ni deux attributs de langue."""
    page = tmp_path / "index.html"
    page.write_text('<!DOCTYPE html>\n<html>\n<head>\n<meta charset="utf-8">\n</head>\n'
                    '<body><main id="observablehq-main">x</main></body>\n</html>\n', encoding="utf-8")
    for _ in range(2):
        subprocess.run([NODE, str(WEB / "scripts" / "postbuild.mjs"), str(tmp_path)],
                       capture_output=True, text=True, encoding="utf-8", timeout=120, check=True)
    html = page.read_text(encoding="utf-8")
    assert html.count("hm-skip") == 1 and html.count('lang="fr"') == 1 and html.count('rel="icon"') == 1


def test_la_vignette_de_partage_existe(heads):
    """Sans elle, les balises og:image annoncent une image absente et un lien partagé
    s'affiche en URL nue. Elle est committée, pas produite au build (voir og-image.mjs)."""
    image = WEB / "assets" / heads["site"]["ogImage"]["path"].lstrip("/")
    assert image.exists(), f"{image} manquante — régénérer avec `npm run og-image`"
    # Signature PNG + dimensions lues dans l'entête IHDR : LinkedIn refuse d'agrandir une
    # vignette trop petite et rogne les rapports d'aspect exotiques.
    entete = image.read_bytes()[:24]
    assert entete[:8] == b"\x89PNG\r\n\x1a\n", "ce n'est pas un PNG"
    largeur = int.from_bytes(entete[16:20], "big")
    hauteur = int.from_bytes(entete[20:24], "big")
    assert (largeur, hauteur) == (heads["site"]["ogImage"]["width"],
                                  heads["site"]["ogImage"]["height"])
