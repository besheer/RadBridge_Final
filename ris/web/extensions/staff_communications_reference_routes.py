"""Blueprint registration for read-only staff communication endpoints."""
from flask import Blueprint


def register_staff_communications_reference_routes(app_module):
    app = app_module.app
    bp = Blueprint("staff_communications_reference", __name__)

    @bp.get("/api/staff/communications/queue")
    def staff_communications_queue():
        return app_module.staff_communications_queue()

    @bp.get("/api/staff/chat/<int:request_id>/messages")
    def staff_chat_messages(request_id):
        return app_module.staff_chat_messages(request_id)

    @bp.get(
        "/api/staff/communications/"
        "<int:request_id>/attachments"
    )
    def staff_contact_attachments(request_id):
        return app_module.staff_contact_attachments(request_id)

    app.register_blueprint(bp)
    return bp
