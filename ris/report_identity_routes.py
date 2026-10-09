"""Renew short-lived viewer identity only through an active RIS session."""
from flask import Blueprint, jsonify, request
from itsdangerous import BadSignature


def register(m):
    bp = Blueprint('report_identity', __name__)

    @bp.post('/api/reporting/identity/<int:order_id>')
    def renew(order_id):
        def result(status, **body):
            response = jsonify(**body)
            response.status_code = status
            response.headers['Cache-Control'] = 'no-store'
            response.headers['Vary'] = 'Cookie'
            return response

        user = m.current_user()
        if not user or not user.active:
            return result(401, ok=False, error='RIS_LOGIN_REQUIRED')
        if not m.has_perm('reports.view') or not m.doctor_workspace_user(user):
            return result(403, ok=False, error='DOCTOR_ACCESS_REQUIRED')
        # An expired signature is only a subject binding here, never a login.
        # The session, permissions, assignment and exact study are checked anew.
        token = request.headers.get('X-RadBridge-Doctor-Identity', '')
        try:
            payload = m._ohif_identity_serializer().loads(token)
            bound = (isinstance(payload, dict)
                     and payload.get('purpose') == 'OHIF_REPORTING'
                     and int(payload.get('user_id')) == user.id
                     and int(payload.get('order_id')) == order_id
                     and payload.get('role') == user.role.code.upper())
        except (BadSignature, ValueError, TypeError, AttributeError):
            bound = False
        if not bound:
            return result(403, ok=False, error='DOCTOR_IDENTITY_INVALID')
        order = m.db.session.get(m.Order, order_id)
        if not m.doctor_case_access_allowed(user, order):
            return result(403, ok=False, error='DOCTOR_ASSIGNMENT_REQUIRED')
        if (user.role.code.upper() != 'SUPER_ADMIN' and user.branch_id
                and user.branch_id != order.branch_id):
            return result(403, ok=False, error='BRANCH_ACCESS_DENIED')
        valid, detail = m.validate_ohif_case_context(order)
        if not valid:
            return result(409, ok=False, error=detail['error'])
        identity = m.create_ohif_doctor_identity(user, order)
        m.audit_as_user(user, 'OHIF_DOCTOR_IDENTITY_RENEWED', 'Order', order.id,
                        'Active RIS session; assignment and study revalidated.')
        m.db.session.commit()
        return result(200, ok=True, identity=identity,
                      expires_in=m.OHIF_DOCTOR_IDENTITY_MAX_AGE)

    m.app.register_blueprint(bp)
    return bp
