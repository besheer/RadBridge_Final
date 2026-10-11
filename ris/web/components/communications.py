"""Runtime-bound web.components.communications; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0903(_rb):
    def _voice_api_authorized():
        expected = (_rb.os.getenv("VOICE_API_TOKEN") or "").strip()
        auth = (_rb.request.headers.get("Authorization") or "").strip()

        return bool(
            expected and
            auth == "Bearer " + expected
        )
    return _voice_api_authorized


def install_0904(_rb):
    def _voice_api_unauthorized():
        return _rb.jsonify(
            ok=False,
            error="VOICE_API_UNAUTHORIZED"
        ), 401
    return _voice_api_unauthorized


def install_0905(_rb):
    def voice_api_branches():
        if not _rb._voice_api_authorized():
            return _rb._voice_api_unauthorized()

        rows = (
            _rb.Branch.query
            .filter_by(active=True)
            .order_by(_rb.Branch.name)
            .all()
        )

        return _rb.jsonify(
            ok=True,
            branches=[
                {
                    "id": x.id,
                    "name": x.name,
                    "working_hours": (
                        lambda devices: (
                            (
                                min(
                                    str(d.workday_start or "08:00")
                                    for d in devices
                                )
                                + " - " +
                                max(
                                    str(d.workday_end or "22:00")
                                    for d in devices
                                )
                            )
                            if devices
                            else None
                        )
                    )(
                        _rb.Device.query.filter_by(
                            branch_id=x.id,
                            active=True
                        ).all()
                    ),
                }
                for x in rows
            ]
        )
    return voice_api_branches


def install_0906(_rb):
    def voice_api_procedures():
        if not _rb._voice_api_authorized():
            return _rb._voice_api_unauthorized()

        branch_id = _rb.request.args.get("branch_id", type=int)
        search = (_rb.request.args.get("q") or "").strip().lower()

        rows = (
            _rb.Procedure.query
            .filter_by(active=True)
            .order_by(
                _rb.Procedure.modality,
                _rb.Procedure.name
            )
            .all()
        )

        if branch_id:
            rows = [
                x for x in rows
                if _rb.procedure_available_in_branch(
                    x.id,
                    branch_id
                )
            ]

        if search:
            def matches(x):
                haystack = " ".join([
                    str(x.code or ""),
                    str(x.name or ""),
                    str(x.name_ar or ""),
                    str(x.modality or ""),
                    str(x.body_part or ""),
                ]).lower()

                return search in haystack

            rows = [x for x in rows if matches(x)]

        return _rb.jsonify(
            ok=True,
            procedures=[
                {
                    "id": x.id,
                    "code": x.code,
                    "name": x.name,
                    "name_ar": x.name_ar,
                    "modality": x.modality,
                    "body_part": x.body_part,
                    "duration_min": x.duration_min,
                    "base_price": x.base_price,
                    "contrast": x.contrast,
                }
                for x in rows[:100]
            ]
        )
    return voice_api_procedures


def install_0910(_rb):
    def voice_api_slots():
        if not _rb._voice_api_authorized():
            return _rb._voice_api_unauthorized()

        branch_id = _rb.request.args.get(
            "branch_id",
            type=int
        )

        procedure_id = _rb.request.args.get(
            "procedure_id",
            type=int
        )

        date_text = (
            _rb.request.args.get("date") or ""
        ).strip()

        if not all([
            branch_id,
            procedure_id,
            date_text
        ]):
            return _rb.jsonify(
                ok=False,
                error="BRANCH_PROCEDURE_DATE_REQUIRED"
            ), 400

        try:
            selected_date = _rb.datetime.fromisoformat(
                date_text
            ).date()
        except ValueError:
            return _rb.jsonify(
                ok=False,
                error="INVALID_DATE"
            ), 400

        branch = _rb.db.session.get(
            _rb.Branch,
            branch_id
        )

        procedure = _rb.db.session.get(
            _rb.Procedure,
            procedure_id
        )

        if not branch or not procedure:
            return _rb.jsonify(
                ok=False,
                error="BRANCH_OR_PROCEDURE_NOT_FOUND"
            ), 404

        if not branch.active or not procedure.active:
            return _rb.jsonify(
                ok=False,
                error="BRANCH_OR_PROCEDURE_INACTIVE"
            ), 409

        if not _rb.procedure_available_in_branch(
            procedure.id,
            branch.id
        ):
            return _rb.jsonify(
                ok=False,
                error="PROCEDURE_NOT_AVAILABLE_IN_BRANCH"
            ), 409

        devices = (
            _rb.Device.query
            .filter_by(
                branch_id=branch.id,
                active=True
            )
            .filter(
                _rb.Device.modality == procedure.modality
            )
            .order_by(_rb.Device.name)
            .all()
        )

        duration = max(
            5,
            int(procedure.duration_min or 20)
        )

        slots = []

        for device in devices:
            for slot in _rb.booking_v2_slots(
                selected_date,
                device
            ):
                reason = _rb.booking_restriction_reason(
                    branch,
                    procedure,
                    device,
                    slot,
                    duration
                )

                if not reason:
                    slots.append({
                        "device_id": device.id,
                        "device_name": device.name,
                        "scheduled": slot.isoformat(),
                        "duration_min": duration,
                    })

        slots.sort(
            key=lambda x: x["scheduled"]
        )

        return _rb.jsonify(
            ok=True,
            branch_id=branch.id,
            procedure_id=procedure.id,
            date=selected_date.isoformat(),
            slots=slots[:50]
        )
    return voice_api_slots


def install_0917(_rb):
    @_rb.login_required
    def telephony_me():

        u = _rb.current_user()

        ext = _rb.TelephonyExtension.query.filter_by(
            user_id=u.id,
            active=True
        ).first()

        return _rb.jsonify(
            ok=True,
            user={
                'id': u.id,
                'username': u.username,
                'full_name': u.full_name,
                'role': u.role.code if u.role else '',
            },
            extension=ext.extension if ext else None,
            telephony_enabled=bool(ext)
        )
    return telephony_me


def install_0918(_rb):
    @_rb.login_required
    def telephony_directory():

        rows = (
            _rb.TelephonyExtension.query
            .filter_by(active=True)
            .order_by(_rb.TelephonyExtension.extension)
            .all()
        )

        return _rb.jsonify(
            ok=True,
            agents=[
                {
                    'extension': x.extension,
                    'user_id': x.user.id if x.user else None,
                    'name': (
                        x.user.full_name
                        if x.user else x.extension
                    ),
                    'username': (
                        x.user.username
                        if x.user else ''
                    ),
                    'role': (
                        x.user.role.code
                        if x.user and x.user.role else ''
                    )
                }
                for x in rows
                if x.user and x.user.active
            ]
        )
    return telephony_directory


def install_0934(_rb):
    @_rb.login_required
    def staff_communications_queue():

        if not _rb._rb_staff_role_allowed():
            _rb.abort(403)

        rows = _rb.db.session.execute(
            _rb.db.text("""
            SELECT
                r.id,
                r.reference,
                r.patient_name,
                r.phone,
                r.booking_reference,
                r.request_type,
                r.message,
                r.status,
                r.assigned_user_id,
                r.confirmed,
                r.created_at,

                c.id AS chat_session_id,
                c.state AS chat_state,
                c.assigned_user_id
                    AS chat_assigned_user_id

            FROM public_contact_request r

            LEFT JOIN public_chat_session c
                ON c.contact_request_id=r.id

            WHERE r.status NOT IN (
                'REJECTED',
                'CLOSED'
            )

            ORDER BY
                CASE
                    WHEN r.status='WAITING_HUMAN'
                    THEN 0
                    ELSE 1
                END,
                r.id DESC

            LIMIT 100
        """)
        ).mappings().all()

        return _rb.jsonify(
            ok=True,
            items=[
                {
                    **dict(x),
                    "created_at":
                        x["created_at"].isoformat()
                        if x["created_at"]
                        else None,
                }
                for x in rows
            ]
        )
    return staff_communications_queue


def install_0938(_rb):
    @_rb.login_required
    def staff_chat_messages(request_id):

        if not _rb._rb_staff_role_allowed():
            _rb.abort(403)

        rows = _rb.db.session.execute(
            _rb.db.text("""
            SELECT
                m.id,
                m.sender_type,
                m.sender_user_id,
                m.message,
                m.created_at

            FROM public_chat_message m

            JOIN public_chat_session s
                ON s.id=m.session_id

            WHERE s.contact_request_id=:id

            ORDER BY m.id
        """),
            {
                "id": request_id
            }
        ).mappings().all()

        return _rb.jsonify(
            ok=True,
            messages=[
                {
                    **dict(x),
                    "created_at":
                        x["created_at"].isoformat()
                        if x["created_at"]
                        else None,
                }
                for x in rows
            ]
        )
    return staff_chat_messages


def install_0944(_rb):
    @_rb.login_required
    def staff_contact_attachments(request_id):

        if not _rb._rb_staff_role_allowed():
            _rb.abort(403)

        rows = _rb.db.session.execute(
            _rb.db.text("""
            SELECT
                id,
                attachment_type,
                description,
                original_filename,
                mime_type,
                size_bytes,
                verification_status,
                created_at

            FROM public_contact_attachment

            WHERE contact_request_id=:id

            ORDER BY id
        """),
            {"id": request_id}
        ).mappings().all()

        return _rb.jsonify(
            ok=True,
            attachments=[
                {
                    **dict(x),
                    "created_at":
                        x["created_at"].isoformat()
                        if x["created_at"]
                        else None,

                    "view_url":
                        (
                            "/staff/public-attachment/"
                            + str(x["id"])
                        )
                }
                for x in rows
            ]
        )
    return staff_contact_attachments

