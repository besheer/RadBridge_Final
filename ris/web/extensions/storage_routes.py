"""Storage HTTP routes; dependencies are supplied by the application."""
from flask import Blueprint, jsonify, request


def register_storage_routes(app, require_perm, resolve_target):
    bp = Blueprint("storage", __name__)

    @bp.get("/api/storage/resolve")
    @require_perm("storage.targets.view")
    def api_storage_resolve():
        row = resolve_target(
            request.args.get("type") or "PACS",
            request.args.get("branch_id", type=int),
            request.args.get("company_code") or "",
            request.args.get("role") or "PRIMARY",
        )
        if not row:
            return jsonify({"ok": False, "error": "NO_STORAGE_TARGET"}), 404
        return jsonify({
            "ok": True,
            "id": row.id,
            "code": row.code,
            "path": row.path,
            "protocol": row.protocol,
            "role": row.role,
            "health": row.health_status,
            "branch_id": row.branch_id,
            "company_code": row.company_code,
        })

    app.register_blueprint(bp)
    return api_storage_resolve
