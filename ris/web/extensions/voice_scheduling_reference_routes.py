"""Blueprint ownership for token-protected voice scheduling references."""
from flask import Blueprint


def register_voice_scheduling_reference_routes(app_module):
    app = app_module.app
    bp = Blueprint("voice_scheduling_reference", __name__)

    @bp.get("/api/voice/branches")
    def voice_api_branches():
        return app_module.voice_api_branches()

    @bp.get("/api/voice/procedures")
    def voice_api_procedures():
        return app_module.voice_api_procedures()

    @bp.get("/api/voice/slots")
    def voice_api_slots():
        return app_module.voice_api_slots()

    app.register_blueprint(bp)
    return bp
