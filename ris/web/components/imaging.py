"""Runtime-bound web.components.imaging; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0079(_rb):
    def get_ohif_doctor_identity(order_id=None):
        token = (
            _rb.request.headers.get("X-RadBridge-Doctor-Identity")
            or _rb.request.args.get("radbridgeIdentity")
            or ""
        )

        return _rb.verify_ohif_doctor_identity(
            token,
            order_id=order_id
        )
    return get_ohif_doctor_identity


def install_0081(_rb):
    def require_ohif_doctor_user(order_id):
        """Require a valid signed RadBridge doctor identity for OHIF writes."""
        identity, error = _rb.get_ohif_doctor_identity(order_id=order_id)

        if error or not identity or not identity.get('user'):
            return None, (
                _rb.jsonify({
                    'ok': False,
                    'error': error or 'DOCTOR_IDENTITY_REQUIRED',
                    'message': (
                        'Your RadBridge doctor authorization is missing or expired. '
                        'Return to RadBridge RIS and open the case in OHIF again.'
                    )
                }),
                403
            )

        from clinical_scope import allowed as clinical_scope_allowed
        order=_rb.db.session.get(_rb.Order,order_id)
        if not clinical_scope_allowed(_rb._reporting_support_sys.modules[_rb.__name__],identity['user'],order):
            return None,(_rb.jsonify(ok=False,error='CLINICAL_SCOPE_DENIED'),403)
        return identity['user'], None
    return require_ohif_doctor_user


def install_0084(_rb):
    def case_pacs_url(order):
        """
    Browser-facing image viewer URL.

    RadBridge no longer exposes the legacy
    /pacs/ohif/viewer route. Use the current
    public OHIF /radbridge workflow instead.

    For authenticated radiology users this also
    preserves the signed doctor identity generated
    by ohif_url_for_order().
    """
        user=_rb.current_user()
        if order and order.pacs_study_id and _rb.doctor_case_access_allowed(user,order):
            return _rb.url_for('doctor_workspace_open',order_id=order.id)
        return _rb.ohif_url_for_order(order)
    return case_pacs_url


def install_0857(_rb):
    def require_ohif_token(fn):
        from functools import wraps

        @wraps(fn)
        def wrapper(*args, **kwargs):
            supplied = (_rb.request.headers.get("X-RadBridge-OHIF-Token") or "").strip()

            if not _rb.OHIF_REPORTING_TOKEN or supplied != _rb.OHIF_REPORTING_TOKEN:
                return _rb.jsonify({
                    "ok": False,
                    "error": "OHIF_AUTH_REQUIRED"
                }), 401

            return fn(*args, **kwargs)

        return wrapper
    return require_ohif_token


def install_0859(_rb):
    def validate_ohif_case_context(order, requested_study_uid=None):
        """
    Critical patient-safety gate.

    The study displayed by OHIF must be the exact PACS study
    attached to the RIS Order.

    Never trust radbridgeOrderId and StudyInstanceUIDs as two
    independent client-side values.
    """

        expected_uid = _rb._normalize_case_uid(
            _rb.ohif_study_uid(order)
        )

        received_uid = _rb._normalize_case_uid(
            requested_study_uid
            or _rb.request.args.get('studyInstanceUID')
            or _rb.request.args.get('StudyInstanceUIDs')
        )

        if not expected_uid:
            return False, {
                'error': 'RIS_ORDER_HAS_NO_STUDY_UID',
                'message': (
                    'Reporting is blocked because this RIS order '
                    'is not linked to a PACS study.'
                ),
                'expected_study_uid': '',
                'received_study_uid': received_uid,
            }

        if not received_uid:
            return False, {
                'error': 'OHIF_STUDY_UID_REQUIRED',
                'message': (
                    'Reporting is blocked because the displayed '
                    'PACS Study UID was not supplied.'
                ),
                'expected_study_uid': expected_uid,
                'received_study_uid': '',
            }

        if received_uid != expected_uid:
            return False, {
                'error': 'OHIF_STUDY_ORDER_MISMATCH',
                'message': (
                    'Patient safety block: the PACS study displayed '
                    'in OHIF does not belong to the selected RIS order.'
                ),
                'expected_study_uid': expected_uid,
                'received_study_uid': received_uid,
                'order_id': order.id,
                'accession': order.accession,
                'patient_id': (
                    order.patient.patient_id
                    if order.patient else ''
                ),
                'modality': order.modality or '',
                'procedure': order.procedure or '',
            }

        return True, {
            'error': '',
            'expected_study_uid': expected_uid,
            'received_study_uid': received_uid,
        }
    return validate_ohif_case_context


def install_0860(_rb):
    def require_valid_ohif_case_context(order):
        ok, result = _rb.validate_ohif_case_context(order)

        if ok:
            return None

        _rb.audit(
            'CASE_CONTEXT_MISMATCH_BLOCKED',
            'order',
            order.id,
            (
                f"error={result.get('error')} "
                f"expected_uid={result.get('expected_study_uid')} "
                f"received_uid={result.get('received_study_uid')}"
            )
        )

        _rb.db.session.commit()

        payload = {
            'ok': False,
            **result
        }

        return _rb.jsonify(payload), 409
    return require_valid_ohif_case_context


def install_0862(_rb):
    def _ohif_json_body():
        data = _rb.request.get_json(silent=True)
        return data if isinstance(data, dict) else {}
    return _ohif_json_body

