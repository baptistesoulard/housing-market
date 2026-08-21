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
import os
import re
import unicodedata

import pytest

_WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "web", "observable", "src")

# Les trois sections du socle commun, dans l'ordre attendu sur les DEUX pages.
SOCLE = ["🔑 Chiffres Clés",
         "📊 Courbes d'évolution du marché",
         "📅 Comparaison Mensuelle par Année"]

JUMELLES = {"neuf": "ancien", "ancien": "neuf"}


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
