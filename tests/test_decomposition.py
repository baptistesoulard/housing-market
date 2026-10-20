"""La décomposition « d'où vient ce mouvement » s'additionne exactement à la prévision.

Publiée sur la page Prévision (section 2), elle partage le mouvement projeté entre l'effet
de chaque indicateur et la résorption de l'écart entre le marché et l'équation. Une
décomposition qui n'additionnerait pas au chiffre de tête serait pire que pas de
décomposition : le lecteur referait la somme et ne retomberait pas sur ses pieds.

Testée sur le fichier RÉELLEMENT publié, comme les autres invariants du front.
"""
import json
from pathlib import Path

import pytest

PREVISIONS = Path(__file__).resolve().parents[1] / "web" / "observable" / "src" / "data" / "previsions.json"


def _verdict():
    data = json.loads(PREVISIONS.read_text(encoding="utf-8"))
    if not data.get("available") or not (data.get("verdict") or {}).get("pourquoi"):
        pytest.skip("pas de verdict publié")
    return data, data["verdict"]


def test_les_contributions_s_additionnent_au_mouvement():
    _, v = _verdict()
    w = v["pourquoi"]
    total = sum(e["effet"] for e in w["entrees"]) + w["resorption"]
    assert total == pytest.approx(w["cible"]["valeur"] - w["depuis"]["valeur"], abs=1.0)


def test_la_decomposition_vise_le_chiffre_du_verdict():
    data, v = _verdict()
    w = v["pourquoi"]
    assert w["horizon"] == v["horizon"]
    assert w["cible"]["valeur"] == pytest.approx(v["predicted"], abs=1.0)
    assert w["depuis"]["valeur"] == pytest.approx(data["projection"]["last_observed"], abs=1.0)
    point = data["projection"]["series"][v["horizon"] - 1]
    assert w["cible"]["mois"] == point["date"]
