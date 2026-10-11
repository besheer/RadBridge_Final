"""Blueprint ownership for permission-protected analytics reference views."""
from flask import Blueprint


def register_analytics_reference_routes(app_module):
    app = app_module.app
    bp = Blueprint("analytics_reference", __name__)

    @bp.get("/analytics")
    def analytics():
        return app_module.analytics()

    @bp.get("/analytics/export.csv")
    def analytics_export_csv():
        return app_module.analytics_export_csv()

    app.register_blueprint(bp)
    return bp
