"""Tests de CONTRAT de l'API HTTP — statut, forme de la réponse, format des clés.

Ils ne testent pas les calculs (`test_queries_parity.py` s'en charge, contre pandas) mais
le **câblage** : ce que le navigateur reçoit réellement. C'est le seul filet qui attrape
les pannes où le calcul est juste et la réponse inutilisable.

Chaque bloc correspond à un mode de panne précis, pas à une ligne de code à couvrir :

* `test_dates_are_iso_days` — le format de date figé. Le piège nommé par le patron : un
  côté écrit `2025-03`, l'autre `2025-03-01`, la requête réussit et renvoie zéro ligne.
* `test_payloads_are_strict_json` — `json.dumps` sérialise `NaN` par défaut, ce qui n'est
  PAS du JSON valide : `JSON.parse` lève côté navigateur. Une valeur manquante quelque
  part dans une série casse alors la page entière, sans erreur serveur.
* `test_concurrent_requests_do_not_swap_payloads` — deux requêtes simultanées sur des
  routes différentes. Le symptôme de la panne n'est pas une erreur mais un corps de
  réponse **bien formé et faux**, celui de la requête d'à côté (voir `CLAUDE.md`,
  « une requête = un curseur »).
"""
import json
import re
import threading
import urllib.parse
import urllib.request
from wsgiref.simple_server import make_server

import pytest

pytest.importorskip("flask")

from api import engine  # noqa: E402
from api.routes import create_app  # noqa: E402

ISO_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Toutes les routes de lecture, avec des paramètres valides.
GET_ROUTES = [
    "/api/health",
    "/api/forecast/rate-model",
    "/api/forecast/transactions-model",
    "/api/forecast/projection",
    "/api/forecast/lag-sensitivity?predictor=rate",
    "/api/forecast/lag-sensitivity?predictor=intentions",
    "/api/forecast/lag-sensitivity?predictor=unemployment",
    "/api/market/transactions-run-rate",
    "/api/market/housing-types",
]


@pytest.fixture(scope="module")
def client():
    try:
        engine.health()
    except Exception as e:                                    # pragma: no cover
        pytest.skip(f"entrepôt indisponible : {e}")
    if engine.health().get("status") != "ok":
        pytest.skip("moteur dégradé (séries macro incomplètes) — rien à contractualiser")
    return create_app().test_client()


def _walk_dates(node, found):
    """Collecte toute valeur portée par une clé `date`, à n'importe quelle profondeur."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "date" and isinstance(v, str):
                found.append(v)
            else:
                _walk_dates(v, found)
    elif isinstance(node, list):
        for v in node:
            _walk_dates(v, found)


# ------------------------------------------------------------------ forme générale
@pytest.mark.parametrize("route", GET_ROUTES)
def test_get_routes_answer_200_json(client, route):
    r = client.get(route)
    assert r.status_code == 200, r.data[:200]
    assert r.headers["Content-Type"].startswith("application/json")
    assert isinstance(r.get_json(), dict)


@pytest.mark.parametrize("route", GET_ROUTES)
def test_payloads_are_strict_json(client, route):
    """Aucun `NaN`/`Infinity` : ce sont des extensions Python, pas du JSON."""
    body = client.get(route).data.decode("utf-8")
    json.loads(body, parse_constant=_reject_constant)


def _reject_constant(name):
    raise AssertionError(f"JSON non standard : {name} présent dans la réponse")


@pytest.mark.parametrize("route", GET_ROUTES)
def test_dates_are_iso_days(client, route):
    dates = []
    _walk_dates(client.get(route).get_json(), dates)
    bad = [d for d in dates if not ISO_DAY.match(d)]
    assert not bad, f"{route} : dates hors format YYYY-MM-DD → {bad[:5]}"


def test_cors_header_present(client):
    """Le front Observable est servi sur un autre port : sans cet en-tête, tout échoue."""
    assert client.get("/api/health").headers.get("Access-Control-Allow-Origin")


# ------------------------------------------------------------------ contrats de fond
def test_transactions_model_exposes_lags_and_backtest(client):
    d = client.get("/api/forecast/transactions-model").get_json()
    assert set(d["lags"]) == {"kr", "ki", "kc"}
    assert all(isinstance(v, int) for v in d["lags"].values())
    assert set(d["coefficients"]) == {"intercept", "rate", "intentions", "unemployment"}
    bt = d["backtest"]
    assert bt["split"] == engine.FORECAST_SPLIT
    assert bt["n_test"] > 0 and bt["mape"] is not None
    assert bt["series"], "backtest sans série : le graphe hors échantillon serait vide"
    assert d["series"][0]["date"] < d["series"][-1]["date"], "série non triée"


def test_projection_marks_the_assumption_free_part(client):
    d = client.get("/api/forecast/projection").get_json()
    if not d["available"]:
        pytest.skip("décalages trop courts pour projeter")
    assert d["series"] and all("assured" in r for r in d["series"])
    assert isinstance(d["series"][0]["assured"], bool)
    # La partie sans hypothèse vient EN PREMIER : une fois qu'un indicateur manque, il
    # manque pour tous les mois suivants. Un `assured` qui redeviendrait vrai après un
    # faux signalerait une erreur d'alignement des décalages.
    flags = [r["assured"] for r in d["series"]]
    assert flags == sorted(flags, reverse=True)
    assert all(r["lo"] <= r["predicted"] <= r["hi"] for r in d["series"])


def test_lag_sensitivity_curve_contains_the_retained_lag(client):
    d = client.get("/api/forecast/lag-sensitivity?predictor=rate").get_json()
    lags = [p["lag"] for p in d["curve"]]
    assert d["retained_lag"] in lags
    at_retained = next(p["r2"] for p in d["curve"] if p["lag"] == d["retained_lag"])
    assert at_retained == pytest.approx(d["retained_r2"], abs=1e-9), (
        "le R² de la courbe au décalage retenu doit être CELUI du modèle affiché ; "
        "sinon le curseur et les indicateurs racontent deux histoires")
    assert d["predictor_series"] and d["transactions_series"]


def test_lag_sensitivity_rejects_unknown_predictor(client):
    r = client.get("/api/forecast/lag-sensitivity?predictor=meteo")
    assert r.status_code == 400
    assert "allowed" in r.get_json()


# ------------------------------------------------------------------ scénarios (POST)
def test_scenario_without_body_reproduces_the_baseline(client):
    """Sans hypothèse, l'écart doit être nul : le scénario est ancré sur le réel."""
    d = client.post("/api/forecast/scenario", json={}).get_json()
    assert d["transactions_change"] == pytest.approx(0.0, abs=1e-6)
    assert d["rate_change"] == pytest.approx(0.0, abs=1e-9)
    assert d["transactions"] == pytest.approx(d["baseline"]["tx_now"], rel=1e-9)


def test_scenario_rate_shock_moves_transactions_the_right_way(client):
    base = client.post("/api/forecast/scenario", json={}).get_json()["baseline"]
    up = client.post("/api/forecast/scenario",
                     json={"oat": base["oat"] + 1.0}).get_json()
    assert up["rate_change"] > 0, "+1 pt d'OAT doit monter le taux de crédit"
    assert up["transactions_change"] < 0, "un taux plus haut doit baisser les transactions"


def test_scenario_rejects_unknown_fields(client):
    r = client.post("/api/forecast/scenario", json={"taux_directeur": 3.0})
    assert r.status_code == 400


# ------------------------------------------------------------------ marché
def test_permits_run_rate_requires_a_known_type(client):
    types = client.get("/api/market/housing-types").get_json()["types"]
    assert types
    ok = client.get(f"/api/market/permits-run-rate?type={types[0]}")
    assert ok.status_code == 200 and ok.get_json()["series"]
    assert client.get("/api/market/permits-run-rate").status_code == 400
    assert client.get(
        f"/api/market/permits-run-rate?type={types[0]}&metric=Chiffre").status_code == 400


def test_permits_and_transactions_share_the_same_date_grid(client):
    """Les deux drivers sont comparés à armes égales côté front : même cadence mensuelle,
    même format de date. Sans ça, la jointure JS renvoie zéro ligne en silence."""
    types = client.get("/api/market/housing-types").get_json()["types"]
    p = client.get(f"/api/market/permits-run-rate?type={types[0]}").get_json()["series"]
    t = client.get("/api/market/transactions-run-rate").get_json()["series"]
    assert {d["date"] for d in p} & {d["date"] for d in t}, "aucun mois en commun"
    assert all(d["date"].endswith("-01") for d in p + t), "dates non calées au 1er du mois"


# ------------------------------------------------------------------ concurrence
def test_concurrent_requests_do_not_swap_payloads():
    """Deux routes différentes martelées en parallèle sur un VRAI serveur.

    Rejoue la course décrite dans `CLAUDE.md` : un `DuckDBPyConnection` porte le résultat
    de son dernier `execute()`, donc deux threads qui partagent la connexion se volent
    leur jeu de résultats. La panne ne lève pas — elle renvoie la réponse de l'autre.
    """
    if engine.health().get("status") != "ok":
        pytest.skip("moteur dégradé")
    app = create_app()
    srv = make_server("127.0.0.1", 0, app)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def fetch(path):
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))

    results, errors = {}, []

    def hammer(name, path, marker):
        try:
            for _ in range(4):
                got = fetch(path)
                assert marker in got, f"{name} a reçu la réponse d'une autre route : {list(got)[:5]}"
            results[name] = True
        except Exception as e:                                # pragma: no cover
            errors.append(f"{name}: {e}")

    # Les libellés de type contiennent des espaces (« Logement Collectif ») : ils DOIVENT
    # être encodés dans l'URL. Le front a la même obligation — d'où `encodeURIComponent`
    # dans `web/observable/src/components/api.js`.
    types = fetch("/api/market/housing-types")["types"]
    q_type = urllib.parse.quote(types[0])
    threads = [
        threading.Thread(target=hammer, args=("types", "/api/market/housing-types", "types")),
        threading.Thread(target=hammer, args=("permits", f"/api/market/permits-run-rate?type={q_type}", "housing_type")),
        threading.Thread(target=hammer, args=("tx", "/api/market/transactions-run-rate", "series")),
        threading.Thread(target=hammer, args=("rate", "/api/forecast/rate-model", "coefficients")),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=180)
    srv.shutdown()

    assert not errors, errors
    assert len(results) == 4
