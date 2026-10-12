"""Blueprint registration for read-only operational health endpoints."""
from flask import Blueprint


def register_operational_health_routes(app_module):
    app = app_module.app
    bp = Blueprint("operational_health", __name__)

    @bp.get("/api/ops/health")
    def api_ops_health():
        return app_module.api_ops_health()

    @bp.get("/api/ohif/onlyoffice/health")
    def api_ohif_onlyoffice_health():
        return app_module.api_ohif_onlyoffice_health()

    app.register_blueprint(bp)
    return bp
