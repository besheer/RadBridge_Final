"""Blueprint registration for read-only scheduling reference APIs."""
from flask import Blueprint


def register_scheduling_reference_routes(app_module):
    app = app_module.app
    bp = Blueprint("scheduling_reference", __name__)

    @bp.get("/api/registration/procedures")
    def api_registration_procedures():
        return app_module.api_registration_procedures()

    @bp.get("/api/pricing")
    def api_pricing():
        return app_module.api_pricing()

    @bp.get("/api/slots")
    def api_slots():
        return app_module.api_slots()

    @bp.get("/api/booking/procedures")
    def api_booking_procedures():
        return app_module.api_booking_procedures()

    app.register_blueprint(bp)
    return bp
