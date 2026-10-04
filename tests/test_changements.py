"""Le journal « ce qui a changé » (web/export/changements.py), sur des payloads fabriqués.

Il n'a de valeur que s'il se tait quand rien ne bouge — sinon le job hebdomadaire
commiterait une ligne chaque lundi et le flux RSS deviendrait du bruit — et s'il parle,
en mots simples, dès qu'une source publie, que la prévision bouge ou qu'une pastille
change de couleur.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "web" / "export"))

import changements as ch                                                 # noqa: E402


def _synth(mois="juillet 2026", neuf="flat"):
    return {"freshness": [f"permis et mises en chantier : {mois}",
                          f"ventes de logements anciens : {mois}"],
            "pillars": [{"key": "neuf", "label": "Neuf", "status": neuf, "word": "permis en recul"}]}


def _prev(pct=-5.9, cible="avril 2027", sens="baisse"):
    return {"verdict": {"direction": sens, "change_pct": pct, "target_month": cible}}


def test_rien_ne_bouge_rien_ne_s_ecrit():
    assert ch.evenements(_synth(), _synth(), _prev(), _prev()) == []
    # Une variation sous le point d'arrondi n'est pas une nouvelle.
    assert ch.evenements(_synth(), _synth(), _prev(-5.9), _prev(-6.2)) == []


def test_un_nouveau_mois_de_donnees_se_signale():
    lignes = ch.evenements(_synth(), _synth("août 2026"), _prev(), _prev())
    assert "Nouvelles données — ventes de logements anciens : août 2026." in lignes
    assert len(lignes) == 2


def test_une_prevision_qui_bouge_dit_d_ou_elle_vient():
    lignes = ch.evenements(_synth(), _synth(), _prev(), _prev(-8.0, "mai 2027"))
    assert lignes == ["Prévision mise à jour : ventes de logements anciens projetées en recul "
                      "d'environ 8 % d'ici mai 2027 (contre en recul d'environ 6 % d'ici "
                      "avril 2027 jusqu'ici)."]


def test_une_pastille_qui_change_de_couleur():
    lignes = ch.evenements(_synth(neuf="flat"), _synth(neuf="down"), _prev(), _prev())
    assert lignes == ["Neuf : permis en recul (🟠 → 🔴)."]


def test_le_premier_passage_pose_un_etat_et_le_dit():
    lignes = ch.evenements(None, _synth(), None, _prev())
    assert lignes[0].startswith("Ouverture de ce journal.")
    assert "Prévision en vigueur" in lignes[1]


def test_le_journal_fusionne_le_meme_jour_et_reste_borne():
    j = ch.ajouter(None, ["a"], "2026-10-05")
    j = ch.ajouter(j, ["a", "b"], "2026-10-05")
    assert j["entrees"] == [{"date": "2026-10-05", "items": ["a", "b"]}]
    for k in range(40):
        j = ch.ajouter(j, [f"x{k}"], f"2027-01-{k:02d}")
    assert len(j["entrees"]) == ch.GARDER
    assert ch.ajouter(j, [], "2028-01-01") == j
