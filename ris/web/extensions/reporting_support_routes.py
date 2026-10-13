"""Blueprint registration for low-risk reporting support endpoints.

The application module retains the view implementations so existing imports and
tests remain compatible.  Only HTTP registration moves into this module.
"""
from flask import Blueprint


def register_reporting_support_routes(app_module):
    app = app_module.app
    bp = Blueprint("reporting_support", __name__)

    @bp.get("/reporting-agent/download")
    def reporting_agent_download():
        return app_module.reporting_agent_download()

    @bp.get("/api/reporting/health")
    def api_reporting_health():
        return app_module.api_reporting_health()

    @bp.get("/word-addin/taskpane")
    def word_addin_taskpane():
        return app_module.word_addin_taskpane()

    @bp.get("/word-addin/manifest.xml")
    def word_addin_manifest():
        return app_module.word_addin_manifest()

    @bp.get("/word-addin/taskpane.js")
    def word_addin_taskpane_js():
        return app_module.word_addin_taskpane_js()

    @bp.get("/api/ohif/reporting-agent/download")
    def api_ohif_reporting_agent_download():
        return app_module.api_ohif_reporting_agent_download()

    @bp.get("/api/ohif/reporting/health")
    def api_ohif_reporting_health():
        return app_module.api_ohif_reporting_health()

    app.register_blueprint(bp)
    return bp
