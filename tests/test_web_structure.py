"""Les pages « Marché du neuf » et « Marché de l'ancien » restent parallèles.

Les deux pages partagent trois sections — chiffres clés, courbes d'évolution, comparaison
mensuelle — portant le MÊME titre, dans le MÊME ordre. Ce n'est pas une coïncidence de
rédaction : c'est ce qui permet à un lecteur d'apprendre la page une fois et de la relire
de l'autre côté, et c'est ce que le sommaire de page et les renvois entre sections
jumelles donnent à voir.

Rien dans le build ne protège cette symétrie. Renommer « 📊 Courbes d'évolution du
marché » d'un seul côté casserait à la fois l'ancre visée par le renvoi d'en face et le
parallèle des deux sommaires — et le site se construirait sans un mot, la validation de
liens d'Observable Framework ne regardant pas les fragments (#ancre).

Ce test ferme ce trou-là, en pur Python : il n'a besoin ni de Node ni d'un build.
"""
import glob
import json
import shutil
import subprocess
import tempfile
import os
import re
import unicodedata

import pytest

_WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "web", "observable", "src")

# Les sections du socle commun, dans l'ordre attendu sur les DEUX pages.
#
# « 📅 Comparaison Mensuelle par Année » en faisait partie et a été RETIRÉE du socle le
# 2026-08-27, parce qu'elle ne voulait pas dire la même chose des deux côtés. Mesuré sur
# 2015-2026 : la série IGEDD (brute) garde 38,6 % d'amplitude saisonnière, que comparer un
# même mois d'une année à l'autre neutralise — le graphique y fait son travail. Les séries
# SIT@DEL sont publiées CVS-CJO et n'en gardent que 6,9 % (permis) et 7,8 % (chantiers) :
# la même vue n'y comparait plus que du bruit résiduel, en invitant à lire une saisonnalité
# que la source a déjà retirée. La section reste donc sur « ancien » seulement, et son
# chapeau dit pourquoi. Le socle garantit la symétrie de FORME, pas celle du sens : quand
# les deux divergent, c'est le sens qui gagne.
SOCLE = ["🔑 Chiffres Clés",
         "📊 Courbes d'évolution du marché"]

JUMELLES = {"neuf": "ancien", "ancien": "neuf"}


def _composant(nom):
    """Le source d'un module de web/observable/src/components/."""
    with open(os.path.join(_WEB, "components", nom), encoding="utf-8") as f:
        return f.read()


def _page(nom):
    with open(os.path.join(_WEB, f"{nom}.md"), encoding="utf-8") as f:
        return f.read()


def _titres(nom):
    """Les titres de niveau 2, dans l'ordre du fichier."""
    return [t.strip() for t in re.findall(r"^## (.+)$", _page(nom), re.M)]


def _renvois(nom):
    """Les renvois vers la section jumelle : [(page cible, ancre), …]."""
    return re.findall(r'hm-shortcuts--twin"><a class="hm-shortcut" href="\./([^#"]+)#([^"]+)"',
                      _page(nom))


def _ancre(titre):
    """Le fragment que le framework fabrique pour un titre.

    Reproduit le comportement OBSERVÉ sur le HTML construit : « & » devient « and », les
    diacritiques sautent (décomposition NFKD, les combinantes sont retirées), le reste
    des caractères non alphanumériques devient un tiret. Le cas « œ » est instructif —
    il n'a pas de décomposition, il disparaît donc entièrement (« second œuvre » →
    « second-uvre »). test_l_ancre_reproduit_le_build fige trois valeurs relevées sur
    dist/ : si le framework change de règle, c'est là que ça se verra."""
    t = unicodedata.normalize("NFKD", titre.replace("&", " and "))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", t.lower())).strip("-")


def test_l_ancre_reproduit_le_build():
    """Valeurs relevées dans dist/neuf.html et dist/ancien.html après `npm run build`."""
    assert _ancre("🔑 Chiffres Clés") == "chiffres-cles"
    assert _ancre("📊 Courbes d'évolution du marché") == "courbes-d-evolution-du-marche"
    assert _ancre("📅 Comparaison Mensuelle par Année") == "comparaison-mensuelle-par-annee"
    assert _ancre("🏷️ Prix des logements & accessibilité") == "prix-des-logements-and-accessibilite"


@pytest.mark.parametrize("page", sorted(JUMELLES))
def test_le_socle_commun_est_en_tete_et_dans_le_meme_ordre(page):
    """Les trois sections partagées ouvrent la page, dans l'ordre convenu.

    L'ordre compte autant que les noms : c'est lui qui fait qu'on retrouve la même chose
    au même endroit. « Dynamique Individuel vs Collectif » s'intercalait au milieu du
    socle côté neuf — d'où son déplacement après le socle."""
    assert _titres(page)[:len(SOCLE)] == SOCLE, (
        f"{page}.md : socle commun attendu {SOCLE}, trouvé {_titres(page)[:len(SOCLE)]}")


@pytest.mark.parametrize("page", sorted(JUMELLES))
def test_chaque_section_du_socle_renvoie_a_sa_jumelle(page):
    renvois = _renvois(page)
    assert len(renvois) == len(SOCLE), (
        f"{page}.md : {len(renvois)} renvoi(s) jumeau(x), {len(SOCLE)} attendu(s)")
    cibles = {c for c, _ in renvois}
    assert cibles == {JUMELLES[page]}, f"{page}.md renvoie vers {cibles}"
    assert [a for _, a in renvois] == [_ancre(t) for t in SOCLE], (
        f"{page}.md : les ancres visées ne suivent pas le socle — {renvois}")


@pytest.mark.parametrize("page", sorted(JUMELLES))
def test_les_ancres_visees_existent_dans_la_page_cible(page):
    """Le test qui compte : un fragment mort ne fait échouer aucun build.

    Le lecteur atterrit alors en haut de la page cible, sans rien qui signale que le
    renvoi promettait mieux."""
    cible = JUMELLES[page]
    disponibles = {_ancre(t) for t in _titres(cible)}
    for _, ancre in _renvois(page):
        assert ancre in disponibles, (
            f"{page}.md renvoie vers #{ancre}, absent de {cible}.md "
            f"(ancres disponibles : {sorted(disponibles)})")


# L'accueil a quatre sections et PAS de sommaire, délibérément : c'est une page
# d'atterrissage qui se lit d'un trait et se termine par un appel à cliquer. Un sommaire y
# entrerait en concurrence avec « Les huit pages », qui EST la navigation du site.
SANS_SOMMAIRE = {"index"}


def test_le_sommaire_de_page_est_actif_la_ou_il_y_a_des_sections():
    """Le sommaire est construit AU BUILD à partir des <h2> du Markdown : une page qui
    l'active sans titre de section afficherait un cadre vide, et une page qui a des
    sections sans l'activer prive le lecteur de la seule vue d'ensemble disponible."""
    for fichier in sorted(f for f in os.listdir(_WEB) if f.endswith(".md")):
        nom = fichier[:-3]
        if nom in SANS_SOMMAIRE:
            continue
        entete = _page(nom).split("---")[1]
        actif = re.search(r"^toc:\s*true\s*$", entete, re.M) is not None
        sections = len(_titres(nom))
        if actif:
            assert sections >= 2, f"{fichier} : toc: true mais {sections} section(s)"
        else:
            assert sections < 2, (
                f"{fichier} : {sections} sections sans sommaire — ajouter toc: true")


# --- Une clôture de bloc de code doit être précédée d'une ligne vide -------------------
# Mode de panne rencontré en insérant les renvois entre jumelles : un ``` collé sous un
# <div> est avalé par le bloc HTML au lieu d'ouvrir une cellule. Le bloc s'affiche alors
# EN TOUT LETTRES au milieu de la page, et les variables qu'il devait définir manquent —
# « RuntimeError: maN is not defined » plus bas. Le build ne dit rien : le Markdown est
# valide, il ne veut simplement plus dire la même chose.

def test_les_blocs_de_code_sont_precedes_d_une_ligne_vide():
    for fichier in sorted(f for f in os.listdir(_WEB) if f.endswith(".md")):
        lignes = _page(fichier[:-3]).split("\n")
        dans_bloc = False
        for i, ligne in enumerate(lignes):
            if not ligne.startswith("```"):
                continue
            if not dans_bloc:                       # ouverture
                assert i == 0 or not lignes[i - 1].strip(), (
                    f"{fichier} ligne {i + 1} : bloc de code collé à « "
                    f"{lignes[i - 1][:60]} » — insérer une ligne vide, sinon la cellule "
                    "s'affiche en toutes lettres")
            dans_bloc = not dans_bloc
        assert not dans_bloc, f"{fichier} : bloc de code non refermé"


# --- Une branche « rien à afficher » ne passe pas par display() ------------------------
# Mode de panne observé sur la page « Données & Sources » du site déployé : trois « null »
# rouges au milieu de la page, sous l'encart d'API injoignable.
#
# La cause tient en une ligne : html`` (gabarit vide) ne rend pas un nœud vide, il rend
# null — htl renvoie null quand le fragment construit n'a pas d'enfant. Or display() ne
# distingue pas « rien » de « la valeur null » : tout ce qui n'est pas un nœud DOM part à
# l'inspecteur, qui affiche fidèlement null. Idem pour la chaîne vide, rendue "" en rouge.
#
# Le build ne dit rien, les tests de liens non plus, et le défaut ne se voit que dans
# l'état où la donnée manque — API éteinte, aucun fichier importé — c'est-à-dire
# précisément l'état d'un visiteur du site public.
#
# La forme correcte est une garde : « if (x) display(…) », qui n'appelle pas display du
# tout quand il n'y a rien à montrer.

def test_display_ne_recoit_jamais_de_valeur_vide():
    motif = re.compile(r'[?:]\s*(html``|"")(\s|,|\)|$)')
    for fichier in sorted(f for f in os.listdir(_WEB) if f.endswith(".md")):
        lignes = _page(fichier[:-3]).split("\n")
        i = 0
        while i < len(lignes):
            if not lignes[i].startswith("display("):
                i += 1
                continue
            bloc = [lignes[i]]
            while not bloc[-1].rstrip().endswith(");") and i + len(bloc) < len(lignes):
                bloc.append(lignes[i + len(bloc)])
            texte = "\n".join(bloc)
            assert not motif.search(texte), (
                f"{fichier} ligne {i + 1} : display() reçoit une valeur vide "
                "(html`` vaut null, \"\" n'est pas un nœud) — la page affichera « null » "
                "en rouge. Écrire « if (condition) display(…) » à la place.")
            i += len(bloc)


# --- Le chapeau indexable des pages de données ------------------------------------------
# Les huit pages de données construisent leur contenu dans le NAVIGATEUR à partir des JSON.
# Un robot d'indexation, comme tout aperçu de partage, n'en voit rien. Leur titre et leur
# chapeau sont donc le seul texte qu'ils lisent — et ils étaient interpolés, `# ${x.title}`,
# ce qui livrait un titre VIDE dans le HTML : la page la plus importante du site pour un
# moteur était une page sans titre.
#
# Ce test empêche la rechute. Il travaille sur la SOURCE Markdown, en pur Python : une
# interpolation se reconnaît à l'œil nu, et le vérifier ici évite d'exiger un build.

PAGES_DE_DONNEES = ["synthese", "neuf", "ancien", "macro", "actualites",
                    "previsions", "previsions-passees", "donnees"]


def _chapeau(nom):
    """Le texte statique entre le titre de niveau 1 et la première section."""
    corps = _page(nom)
    debut = re.search(r"^# .+$", corps, re.M)
    assert debut, f"{nom} n'a pas de titre de niveau 1"
    suite = corps[debut.end():]
    fin = re.search(r"^## ", suite, re.M)
    tete = suite[:fin.start()] if fin else suite
    # On retire tout ce qu'un robot ne lit PAS : commentaires, blocs de code, balises —
    # et les interpolations `${…}`, qui ne sont remplies qu'une fois le JS exécuté. Ce
    # qui reste est exactement le texte présent dans le HTML livré.
    tete = re.sub(r"<!--.*?-->", " ", tete, flags=re.S)
    tete = re.sub(r"^```.*?^```", " ", tete, flags=re.S | re.M)
    tete = re.sub(r"\$\{[^}]*\}", " ", tete)
    tete = re.sub(r"<[^>]+>", " ", tete)
    return re.sub(r"\s+", " ", tete).strip()


@pytest.mark.parametrize("nom", PAGES_DE_DONNEES)
def test_le_titre_de_page_est_statique(nom):
    """`# ${x.title}` produit `<h1></h1>` : le titre n'existe que pour qui exécute le JS."""
    titre = re.search(r"^# (.+)$", _page(nom), re.M)
    assert titre, f"{nom} n'a pas de titre de niveau 1"
    assert "${" not in titre.group(1), (
        f"{nom} : titre interpolé — le HTML livré porterait un <h1> vide")


@pytest.mark.parametrize("nom", PAGES_DE_DONNEES)
def test_chaque_page_de_donnees_a_un_chapeau_statique(nom):
    """Sans lui, la page n'offre à un moteur qu'une poignée de titres de sections.

    Le seuil est bas volontairement : il attrape la page qui n'a RIEN, pas celle qui est
    brève. Ce qui compte est qu'un texte existe et soit rendu au build."""
    chapeau = _chapeau(nom)
    assert len(chapeau.split()) >= 40, (
        f"{nom} : {len(chapeau.split())} mots de chapeau statique — la page est muette "
        "pour un robot d'indexation")


@pytest.mark.parametrize("nom", PAGES_DE_DONNEES)
def test_aucune_page_n_emploie_viewof(nom):
    """`viewof` est de la syntaxe NOTEBOOK : Framework retire la cellule, sans rien dire.

    Rencontré en câblant les boutons de scénario de « Prévision » : `set(viewof dTaux, …)`
    a fait disparaître le bloc entier du build — pas d'erreur, pas d'avertissement, 240
    liens toujours validés, et simplement aucun bouton sur la page. Le défaut ne se voit
    qu'en cherchant le code dans le HTML construit, ce que personne ne fait par réflexe.

    Le motif correct dans Framework est de garder une référence à l'entrée avant de la
    passer à `view()` :

        const monInput = Inputs.range(…);
        const maValeur = view(monInput);        // monInput reste adressable ailleurs
    """
    # Les lignes de COMMENTAIRE sont exclues : la mise en garde ci-dessus vit aussi dans le
    # code des pages, où elle est le plus utile, et se ferait attraper par sa propre règle.
    fautifs = [ligne.strip() for ligne in _page(nom).splitlines()
               if re.search(r"\bviewof\b", ligne)
               and not ligne.strip().startswith(("//", "*", "<!--"))]
    assert not fautifs, (
        f"{nom} emploie `viewof`, que Framework ne connaît pas — la cellule sera retirée "
        f"du build en silence : {fautifs[:2]}")


def test_la_page_neuf_publie_sa_formule_et_ses_limites():
    """La section « Du permis au chantier » doit garder ce qui la rend honnête.

    Elle publie un RÉSULTAT NÉGATIF autant qu'un indicateur : le modèle de prévision du
    neuf qui était prévu à cet endroit a été mesuré, puis écarté — les permis n'ont aucune
    avance exploitable sur les mises en chantier (R² maximal à zéro décalage, décroissant
    ensuite). Une session ultérieure pourrait « alléger » la page en retirant l'aveu et en
    ne gardant que l'indicateur ; ce serait une régression d'honnêteté, pas une
    simplification. Le taux de transformation, lui, n'a de sens que si l'on dit ce qu'il
    n'est PAS — il rapporte deux flux d'une même fenêtre, pas une conversion projet par
    projet, et peut dépasser 100 %.
    """
    src = _page("neuf")
    assert "hm-formula" in src, (
        "neuf.md : la formule du taux de transformation n'est plus affichée — "
        "un ratio publié sans son calcul n'est pas vérifiable")
    for attendu, pourquoi in [
        ("lag_profile", "la preuve que les permis n'ont pas d'avance"),
        ("ne publie pas de prévision", "l'explication du modèle écarté"),
        ("Limites du taux de transformation", "les limites de l'indicateur"),
        ("gate", "le chiffre de la mesure qui a écarté le modèle"),
    ]:
        assert attendu in src, f"neuf.md : « {attendu} » a disparu — {pourquoi}"


@pytest.mark.parametrize("nom", PAGES_DE_DONNEES + ["index", "a-propos"])
def test_chaque_helper_utilise_est_importe(nom):
    """Un helper employé sans être importé ne casse QUE dans le navigateur.

    `observable build` valide les liens, pas les références de cellules : une page qui
    utilise `TIP` sans l'importer se construit sans un mot, 240 liens toujours validés, et
    affiche `RuntimeError: TIP is not defined` en rouge à la place du graphique. Rencontré
    en ajoutant la vignette au modèle de taux — le défaut a été poussé en production parce
    que la vérification portait sur le HTML construit (les textes étaient bien là) et non
    sur l'exécution des cellules.

    On ne regarde que les identifiants employés SEULS : `Plot.tip` ne compte pas (c'est un
    accès à un objet déjà importé) et `legend:` non plus (c'est une clé d'objet). Restent
    les usages qui exigent vraiment l'import.
    """
    src = _page(nom)
    exports = set(re.findall(r"^export (?:function|const) ([A-Za-z_]\w*)",
                             _composant("hm.js"), re.M))
    importes = set()
    for bloc in re.findall(r'import \{([^}]*)\} from "\./components/[^"]+"', src, re.S):
        importes |= {x.strip() for x in bloc.replace("\n", " ").split(",") if x.strip()}

    # Une page a le droit de définir SA propre version d'un helper plutôt que de
    # l'importer — « synthese » le fait pour `legend` et `fmtMonthFR`, qu'elle spécialise.
    locales = set(re.findall(r"\b(?:function|const|let|var)\s+([A-Za-z_]\w*)", src))

    # On cherche les usages NUS. Deux formes doivent être écartées avant la recherche, et
    # l'ordre compte : l'opérateur de décomposition `...TIP` commence par un point, donc
    # une règle naïve « pas précédé d'un point » le confondrait avec un accès de propriété
    # et laisserait passer exactement le défaut que ce test existe pour attraper. On
    # protège donc `...` d'abord, puis on retire les vrais accès `objet.membre`.
    nettoye = re.sub(r"\.\s*\w+", " ", src.replace("...", " ⋯ "))

    manquants = set()
    for nom_export in exports - importes - locales:
        if re.search(rf"(?<![\w-]){re.escape(nom_export)}(?!\s*:)(?![\w-])", nettoye):
            manquants.add(nom_export)
    assert not manquants, (
        f"{nom}.md utilise {sorted(manquants)} sans l'importer depuis hm.js — "
        "la page se construira sans erreur et cassera dans le navigateur")


# Globaux du runtime Observable et du navigateur : ils n'ont ni import ni cellule qui les
# définisse, et ce sont pourtant des entrées légitimes.
_GLOBAUX = {
    "display", "view", "html", "svg", "Plot", "d3", "Inputs", "FileAttachment", "width",
    "Generators", "Mutable", "now", "dark", "resize", "invalidation",
    "Math", "Date", "Object", "Array", "JSON", "Intl", "Set", "Map", "Number", "String",
    "Event", "console", "URL", "document", "window", "fetch", "Promise", "RegExp",
    "parseFloat", "parseInt", "isNaN", "NaN", "undefined", "Boolean", "Error", "Symbol",
    "WeakMap", "Infinity", "FormData", "localStorage", "location", "navigator", "Blob",
    "TextDecoder", "AbortController", "setTimeout",
}


def test_aucune_cellule_construite_ne_reference_un_identifiant_inconnu():
    """La preuve structurelle qu'aucun « RuntimeError: X is not defined » ne peut survenir.

    Le test d'imports ci-dessus ne couvre que les helpers de hm.js ; celui-ci couvre TOUT.
    Le HTML construit déclare, pour chaque cellule, ses `inputs` et ses `outputs` : une
    entrée qui n'est ni un global, ni un nom importé, ni la sortie d'une autre cellule est
    un identifiant que le runtime ne pourra pas résoudre — et la page affichera l'erreur en
    rouge à la place du graphique, sans que le build ait bronché.

    Deux pièges dans sa fabrication, rencontrés tous les deux : une cellule qui ne consomme
    rien n'a PAS de clé `inputs` (il faut donc lire les deux clés indépendamment, sinon ses
    sorties sont ignorées et l'on croit à un défaut), et les noms importés sont des entrées
    sans être des sorties.

    Se saute sans `dist/` : il exige un build, que la suite ne lance pas.
    """
    dist = os.path.join(os.path.dirname(_WEB), "dist")
    pages = sorted(glob.glob(os.path.join(dist, "*.html")))
    depart = sorted(glob.glob(os.path.join(dist, "departement", "*.html")))
    if not pages:
        pytest.skip("dist/ absent — lancer `npm run build` pour activer ce test")

    for html in pages + depart[:1]:
        md = os.path.join(_WEB, os.path.basename(html).replace(".html", ".md"))
        if not os.path.exists(md):
            md = os.path.join(_WEB, "departement", "[code].md")
            if os.path.basename(html).replace(".html", "") not in dvf_codes():
                continue
        src, page = open(html, encoding="utf-8", errors="replace").read(), open(md, encoding="utf-8").read()
        blocs = re.findall(r'define\(\{id: "[a-f0-9]+",([^\n]*?)body:', src)
        if not blocs:
            continue
        definis, utilises = set(_GLOBAUX) | _noms_importes(page), set()
        for bloc in blocs:
            sorties = re.search(r"outputs: (\[[^]]*\])", bloc)
            entrees = re.search(r"inputs: (\[[^]]*\])", bloc)
            if sorties:
                definis |= set(json.loads(sorties.group(1).replace("'", '"')))
            if entrees:
                utilises |= set(json.loads(entrees.group(1).replace("'", '"')))
        inconnus = sorted(utilises - definis)
        assert not inconnus, (
            f"{os.path.basename(html)} référence {inconnus} sans que rien ne les définisse — "
            "la page affichera « RuntimeError: … is not defined » à la place du graphique")


def _noms_importes(src):
    out = set()
    for bloc in re.findall(r"import \{([^}]*)\} from", src, re.S):
        out |= {x.strip().split(" as ")[-1].strip()
                for x in bloc.replace("\n", " ").split(",") if x.strip()}
    return out | set(re.findall(r"import (\w+) from", src))


def dvf_codes():
    """Les pages départementales partagent un seul source : n'en vérifier qu'une suffit."""
    return {os.path.basename(p).replace(".html", "") for p in
            glob.glob(os.path.join(os.path.dirname(_WEB), "dist", "departement", "*.html"))}


def test_chaque_cellule_js_est_syntaxiquement_valide():
    """Une cellule qui ne compile pas est RETIRÉE du build, en silence.

    C'est le troisième visage du même angle mort. `observable build` ne signale rien —
    240 liens toujours validés, page construite, taille de page à peine différente — et la
    cellule fautive n'existe simplement plus dans le HTML livré. Rencontré deux fois : avec
    `viewof` (syntaxe notebook) puis avec un saut de ligne réel à l'intérieur d'une chaîne,
    introduit par un script d'édition qui avait converti `\n` en vraie nouvelle ligne.

    Les deux autres tests ne l'attrapent pas, et ne le peuvent pas : une cellule ABSENTE ne
    référence aucun identifiant, donc le contrôle des entrées non résolues la déclare
    saine. Il faut donc vérifier la source, pas le produit.

    `node --check` sur un fichier .mjs parse sans exécuter : les identifiants inconnus, le
    `await` de premier niveau et les `${…}` du framework passent, seule une vraie erreur de
    syntaxe échoue.
    """
    node = shutil.which("node")
    if not node:
        pytest.skip("Node absent — ce contrôle a besoin de son analyseur")

    fautifs = []
    for chemin in sorted(glob.glob(os.path.join(_WEB, "*.md"))
                         + glob.glob(os.path.join(_WEB, "departement", "*.md"))):
        src = open(chemin, encoding="utf-8").read()
        for i, bloc in enumerate(re.findall(r"^```js\n(.*?)^```", src, re.S | re.M), start=1):
            with tempfile.TemporaryDirectory() as d:
                f = os.path.join(d, "cellule.mjs")
                with open(f, "w", encoding="utf-8") as fh:
                    fh.write(bloc)
                r = subprocess.run([node, "--check", f], capture_output=True,
                                   text=True, encoding="utf-8", timeout=60)
            if r.returncode != 0:
                detail = (r.stderr or "").strip().splitlines()
                fautifs.append(f"{os.path.basename(chemin)} bloc #{i} : "
                               + " / ".join(detail[:4]))
    assert not fautifs, (
        "cellule(s) JavaScript invalide(s) — le build les retirerait SANS RIEN DIRE :\n"
        + "\n".join(fautifs))
