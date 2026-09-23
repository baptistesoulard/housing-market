"""Ce que le job hebdomadaire (.github/workflows/refresh-data.yml) commite.

Le runner reconstruit les CSV dérivés de `data/` (`load_or_generate_all` : sitadel, macro,
sales, ecln) puis les PERDAIT à la fin du job : son `git add` était une liste écrite à la
main, qui ne nommait que ventes_ancien / forecast_archive / forecast_band. La copie
versionnée prenait donc du retard sur ses sources à chaque semaine, rattrapée à la main le
2026-08-24 (0f7005a) puis le 2026-09-19. Une liste écrite à la main oublie toujours ce qui
a été ajouté depuis — ces tests lisent le workflow et exigent que TOUT fichier suivi sous
`data/` soit couvert, ce qui est la seule façon d'empêcher la liste de redériver.

Pas de PyYAML dans l'environnement : le `git add` est extrait en texte, continuations de
ligne recollées. Aucun réseau, aucun entrepôt requis.
"""
import os
import shutil
import subprocess

import pytest

_RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_WORKFLOW = os.path.join(_RACINE, ".github", "workflows", "refresh-data.yml")

# La liste telle qu'elle était avant le 2026-09-19 : sert de contre-épreuve.
_ANCIENNE_LISTE = ["data_manual_input", "data/ventes_ancien.csv", "data/forecast_archive.csv",
                   "data/forecast_band.csv", "web/observable/src/data",
                   "web/observable/src/a-propos.md"]


def _chemins_ajoutes_par_le_job():
    """Les arguments du `git add` du workflow, continuations de ligne recollées."""
    with open(_WORKFLOW, encoding="utf-8") as f:
        texte = f.read().replace("\\\n", " ")
    lignes = [l.strip() for l in texte.splitlines() if l.strip().startswith("git add ")]
    assert len(lignes) == 1, f"un seul `git add` attendu dans le workflow : {lignes}"
    return [t.rstrip("/") for t in lignes[0].split()[2:]]


def _couvert(chemin, ajoutes):
    """Vrai si `chemin` est l'un des chemins ajoutés, ou se trouve sous l'un d'eux."""
    return any(chemin == a or chemin.startswith(a + "/") for a in ajoutes)


def _fichiers_suivis_sous_data():
    git = shutil.which("git")
    if git is None:
        pytest.skip("git absent de l'environnement")
    # encoding explicite : sous Windows, `text=True` décoderait la sortie en cp1252 et
    # échouerait sur le premier caractère hors table (voir CLAUDE.md, « Piège Windows »).
    res = subprocess.run([git, "ls-files", "data"], cwd=_RACINE, capture_output=True,
                         encoding="utf-8", check=True)
    suivis = [l.strip() for l in res.stdout.splitlines() if l.strip()]
    assert suivis, "aucun fichier suivi sous data/ — le test ne prouverait rien"
    return suivis


def test_le_job_hebdo_commite_tout_ce_qu_il_reecrit_sous_data():
    ajoutes = _chemins_ajoutes_par_le_job()
    oublies = [f for f in _fichiers_suivis_sous_data() if not _couvert(f, ajoutes)]
    assert not oublies, (
        "suivis par git, réécrits par le job, mais hors de son `git add` — la copie "
        f"versionnée prendrait du retard à chaque semaine : {oublies}")


def test_le_job_hebdo_commite_aussi_les_sources_le_front_et_les_pages_reecrites():
    """Les autres cibles du `git add` ont chacune leur raison (voir le workflow) : les
    sources, les JSON du front (sinon Cloudflare ne reconstruit rien), et les deux pages
    dont Python réécrit des passages entre marqueurs parce qu'elles doivent rester du HTML
    statique — `a-propos.md` (tableau des sources) et `index.md` (chiffres de l'accueil)."""
    ajoutes = _chemins_ajoutes_par_le_job()
    for attendu in ("data_manual_input", "web/observable/src/data",
                    "web/observable/src/a-propos.md", "web/observable/src/index.md"):
        assert _couvert(attendu, ajoutes), f"{attendu} a quitté le `git add` du job"


def test_contre_epreuve_l_ancienne_liste_oubliait_bien_les_derives():
    """Sans elle, le test principal passerait pour de mauvaises raisons si `_couvert`
    acceptait tout. L'ancienne liste DOIT laisser macro.csv et sales.csv de côté."""
    assert not _couvert("data/macro.csv", _ANCIENNE_LISTE)
    assert not _couvert("data/sales.csv", _ANCIENNE_LISTE)
    assert _couvert("data/ventes_ancien.csv", _ANCIENNE_LISTE)
