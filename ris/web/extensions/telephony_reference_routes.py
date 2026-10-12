"""Blueprint registration for authenticated telephony reference APIs."""
from flask import Blueprint


def register_telephony_reference_routes(app_module):
    app = app_module.app
    bp = Blueprint("telephony_reference", __name__)

    @bp.get("/api/telephony/me")
    def telephony_me():
        return app_module.telephony_me()

    @bp.get("/api/telephony/directory")
    def telephony_directory():
        return app_module.telephony_directory()

    app.register_blueprint(bp)
    return bp
