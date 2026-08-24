"""Couche 3 — routes HTTP. Traduction pure : requête → appel du moteur → JSON.

**Aucune logique métier ici.** Si une route fait autre chose que lire des paramètres,
appeler `api.engine` et sérialiser, le calcul est au mauvais endroit.

Une route = une question métier, pas une table : `/api/forecast/projection`, pas
`/api/table/macro?filter=...`. Le second reviendrait à réinventer SQL par-dessus HTTP et
ferait migrer la logique dans le front.

`GET` lit, `POST` déclenche un calcul — `/api/forecast/scenario` est un POST bien qu'il ne
persiste rien : il produit un nouvel état de référence à partir d'hypothèses soumises.
"""
from __future__ import annotations

from flask import Blueprint, Flask, jsonify, request

from api import engine

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.errorhandler(engine.EngineUnavailable)
def _unavailable(e):
    return jsonify({"error": "engine_unavailable", "detail": str(e)}), 503


@bp.get("/health")
def health():
    return jsonify(engine.health())


@bp.get("/forecast/rate-model")
def rate_model():
    return jsonify(engine.rate_model())


@bp.get("/forecast/transactions-model")
def transactions_model():
    return jsonify(engine.transactions_model())


@bp.get("/forecast/projection")
def projection():
    try:
        horizon = int(request.args.get("horizon", 18))
    except ValueError:
        return jsonify({"error": "bad_request", "detail": "horizon must be an integer"}), 400
    if not 1 <= horizon <= 36:
        return jsonify({"error": "bad_request", "detail": "horizon must be 1..36"}), 400
    return jsonify(engine.projection(horizon=horizon))


@bp.get("/forecast/lag-sensitivity")
def lag_sensitivity():
    predictor = request.args.get("predictor", "rate")
    try:
        return jsonify(engine.lag_sensitivity(predictor))
    except KeyError:
        return jsonify({"error": "unknown_predictor",
                        "allowed": sorted(engine.LAG_GRIDS)}), 400


@bp.post("/forecast/scenario")
def scenario():
    body = request.get_json(silent=True) or {}
    allowed = {"oat", "euribor", "unemployment", "intentions_z"}
    unknown = set(body) - allowed
    if unknown:
        return jsonify({"error": "bad_request",
                        "detail": f"unknown fields: {sorted(unknown)}"}), 400
    try:
        return jsonify(engine.run_scenario(**{k: body[k] for k in body}))
    except (TypeError, ValueError) as e:
        return jsonify({"error": "bad_request", "detail": str(e)}), 400


@bp.get("/market/transactions-run-rate")
def transactions_run_rate():
    return jsonify(engine.transactions_run_rate())


@bp.get("/market/permits-run-rate")
def permits_run_rate():
    housing_type = request.args.get("type")
    metric = request.args.get("metric", "Permis")
    if not housing_type:
        return jsonify({"error": "bad_request", "detail": "type is required"}), 400
    try:
        return jsonify(engine.permits_run_rate(housing_type, metric))
    except ValueError:
        return jsonify({"error": "bad_request",
                        "detail": "metric must be Permis or MisesEnChantier"}), 400


@bp.get("/market/housing-types")
def housing_types():
    return jsonify(engine.housing_types())


def create_app(origins: str = "*") -> Flask:
    """Application Flask. `origins` autorise le front Observable, servi sur un autre port.

    CORS est fait à la main plutôt qu'avec `flask-cors` : trois en-têtes suffisent et le
    patron tient à ce que la pile reste installable d'un seul `pip install flask`.
    """
    app = Flask(__name__)
    app.register_blueprint(bp)

    @app.after_request
    def _cors(resp):
        resp.headers["Access-Control-Allow-Origin"] = origins
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return resp

    @app.get("/")
    def _index():
        return jsonify({
            "service": "housing-market-api",
            "routes": sorted(str(r) for r in app.url_map.iter_rules()
                             if str(r).startswith("/api")),
        })

    return app
