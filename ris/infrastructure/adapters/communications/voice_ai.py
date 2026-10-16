import os
import re
import secrets
from datetime import datetime

from flask import Blueprint, request, jsonify
from sqlalchemy import text, or_


def register_voice_ai(app_module):
    app = app_module.app
    db = app_module.db

    Patient = app_module.Patient
    Appointment = app_module.Appointment
    Procedure = app_module.Procedure
    Device = app_module.Device
    Branch = app_module.Branch
    CallLog = app_module.CallLog
    Order = getattr(app_module, "Order", None)

    bp = Blueprint("voice_ai", __name__)

    def authorized():
        expected = os.getenv("VOICE_API_TOKEN", "").strip()
        if not expected:
            return False

        received = (
            request.headers.get("X-RadBridge-Voice-Token", "").strip()
            or request.headers.get("Authorization", "")
              .replace("Bearer ", "", 1).strip()
        )

        return secrets.compare_digest(expected, received)

    @bp.before_request
    def voice_auth():
        if request.endpoint == "voice_ai.health":
            return None

        if not authorized():
            return jsonify(
                ok=False,
                error="VOICE_API_UNAUTHORIZED"
            ), 401

    def normalize_phone(value):
        value = re.sub(r"\D+", "", str(value or ""))
        if value.startswith("20") and len(value) >= 12:
            value = value[2:]
        return value[-11:]

    def patient_payload(p):
        return {
            "id": p.id,
            "patient_id": p.patient_id,
            "name": p.name,
            "dob": p.dob,
            "sex": p.sex,
            "phone": p.phone,
        }

    @bp.get("/api/voice/health")
    def health():
        return jsonify(
            ok=True,
            service="RadBridge Voice API",
            version="5.37"
        )

    @bp.post("/api/voice/session/start")
    def session_start():
        data = request.get_json(silent=True) or {}

        caller = normalize_phone(data.get("caller_number"))
        called = str(data.get("called_number") or "")[:60]
        extension = str(data.get("extension") or "")[:30]
        external_call_id = str(
            data.get("external_call_id") or ""
        )[:160]

        patient = None

        if caller:
            patients = Patient.query.filter(
                Patient.phone.isnot(None)
            ).all()

            for p in patients:
                if normalize_phone(p.phone) == caller:
                    patient = p
                    break

        row = CallLog(
            direction="INBOUND",
            caller_number=caller,
            called_number=called,
            extension=extension,
            patient_id=patient.id if patient else None,
            status="AI_CONNECTED",
            external_call_id=external_call_id,
            notes="AI Reception session started",
        )

        db.session.add(row)
        db.session.commit()

        return jsonify(
            ok=True,
            call_id=row.id,
            patient=patient_payload(patient) if patient else None,
            known_patient=bool(patient),
        )

    @bp.post("/api/voice/patient/search")
    def patient_search():
        data = request.get_json(silent=True) or {}

        phone = normalize_phone(data.get("phone"))
        patient_id = str(data.get("patient_id") or "").strip()
        name = str(data.get("name") or "").strip()

        q = Patient.query

        conditions = []

        if patient_id:
            conditions.append(Patient.patient_id == patient_id)

        if name:
            conditions.append(Patient.name.ilike(f"%{name}%"))

        rows = q.filter(or_(*conditions)).limit(20).all() \
            if conditions else []

        if phone:
            phone_matches = [
                p for p in Patient.query.filter(
                    Patient.phone.isnot(None)
                ).all()
                if normalize_phone(p.phone) == phone
            ]

            known = {p.id for p in rows}
            rows.extend(
                p for p in phone_matches
                if p.id not in known
            )

        return jsonify(
            ok=True,
            count=len(rows),
            patients=[patient_payload(p) for p in rows[:20]],
        )

    @bp.get("/api/voice/procedures/search")
    def procedure_search():
        qtext = str(request.args.get("q") or "").strip()

        q = Procedure.query.filter_by(active=True)

        if qtext:
            q = q.filter(
                or_(
                    Procedure.name.ilike(f"%{qtext}%"),
                    Procedure.name_ar.ilike(f"%{qtext}%"),
                    Procedure.code.ilike(f"%{qtext}%"),
                )
            )

        rows = q.order_by(Procedure.name).limit(30).all()

        return jsonify(
            ok=True,
            procedures=[
                {
                    "id": p.id,
                    "code": p.code,
                    "name": p.name,
                    "name_ar": p.name_ar,
                    "modality": p.modality,
                    "body_part": p.body_part,
                    "base_price": p.base_price,
                    "duration_min": p.duration_min,
                    "contrast": bool(p.contrast),
                    "price_type": "BASE_PRICE",
                }
                for p in rows
            ]
        )

    @bp.get("/api/voice/appointments")
    def appointment_query():
        internal_id = request.args.get("patient_db_id", type=int)
        patient_id = str(
            request.args.get("patient_id") or ""
        ).strip()
        phone = normalize_phone(request.args.get("phone"))

        patient = None

        if internal_id:
            patient = db.session.get(Patient, internal_id)

        elif patient_id:
            patient = Patient.query.filter_by(
                patient_id=patient_id
            ).first()

        elif phone:
            for p in Patient.query.filter(
                Patient.phone.isnot(None)
            ).all():
                if normalize_phone(p.phone) == phone:
                    patient = p
                    break

        if not patient:
            return jsonify(
                ok=False,
                error="PATIENT_NOT_FOUND"
            ), 404

        rows = (
            Appointment.query
            .filter(
                Appointment.patient_id == patient.id,
                Appointment.status != "CANCELLED",
            )
            .order_by(Appointment.scheduled.asc())
            .limit(20)
            .all()
        )

        return jsonify(
            ok=True,
            patient=patient_payload(patient),
            appointments=[
                {
                    "id": a.id,
                    "scheduled": a.scheduled.isoformat(),
                    "status": a.status,
                    "branch": a.branch.name if a.branch else "",
                    "procedure": (
                        a.procedure.name
                        if a.procedure else ""
                    ),
                    "procedure_ar": (
                        a.procedure.name_ar
                        if a.procedure else ""
                    ),
                    "device": (
                        a.device.name
                        if a.device else ""
                    ),
                }
                for a in rows
            ],
        )

    @bp.post("/api/voice/report/status")
    def report_status():
        if Order is None:
            return jsonify(
                ok=False,
                error="ORDER_MODEL_UNAVAILABLE"
            ), 500

        data = request.get_json(silent=True) or {}

        accession = str(data.get("accession") or "").strip()
        patient_id = str(data.get("patient_id") or "").strip()

        if not accession and not patient_id:
            return jsonify(
                ok=False,
                error="IDENTIFIER_REQUIRED"
            ), 400

        q = Order.query

        if accession:
            q = q.filter(Order.accession == accession)

        if patient_id:
            q = q.join(Patient).filter(
                Patient.patient_id == patient_id
            )

        rows = q.order_by(Order.id.desc()).limit(10).all()

        result = []

        labels = {
            "UNREPORTED": "لم يبدأ التقرير بعد",
            "DRAFT": "التقرير تحت الكتابة",
            "REPORTING": "التقرير قيد الإعداد",
            "PARTIAL": "التقرير قيد الاستكمال",
            "READY_FORMATTING": "التقرير في مرحلة التنسيق",
            "VERIFIED": "التقرير تمت مراجعته",
            "SECOND_VERIFIED": "التقرير تمت المراجعة الثانية",
            "FINAL": "التقرير جاهز",
        }

        for o in rows:
            report = getattr(o, "report", None)
            status = (
                getattr(report, "status", None)
                or getattr(o, "status", "")
            )

            result.append({
                "order_id": o.id,
                "accession": o.accession,
                "procedure": getattr(o, "procedure", ""),
                "status": status,
                "spoken_status_ar": labels.get(
                    status,
                    "حالة التقرير قيد المتابعة"
                ),
            })

        return jsonify(
            ok=True,
            reports=result
        )

    @bp.post("/api/voice/appointment/book")
    def appointment_book():
        data = request.get_json(silent=True) or {}

        patient_db_id = data.get("patient_db_id")
        procedure_id = data.get("procedure_id")
        branch_id = data.get("branch_id")
        device_id = data.get("device_id")
        scheduled_raw = data.get("scheduled")

        try:
            patient = db.session.get(
                Patient, int(patient_db_id)
            )
            procedure = db.session.get(
                Procedure, int(procedure_id)
            )
            branch = db.session.get(
                Branch, int(branch_id)
            )
            device = db.session.get(
                Device, int(device_id)
            )
            scheduled = datetime.fromisoformat(
                str(scheduled_raw)
            )
        except Exception:
            return jsonify(
                ok=False,
                error="INVALID_BOOKING_DATA"
            ), 400

        if not all([patient, procedure, branch, device]):
            return jsonify(
                ok=False,
                error="BOOKING_REFERENCE_NOT_FOUND"
            ), 404

        duration = procedure.duration_min or 20

        booking_gate = getattr(
            app_module,
            "booking_restriction_reason",
            None,
        )

        if booking_gate:
            reason = booking_gate(
                branch,
                procedure,
                device,
                scheduled,
                duration,
            )

            if reason:
                return jsonify(
                    ok=False,
                    error="BOOKING_RESTRICTED",
                    reason=str(reason),
                ), 409

        overlap = getattr(
            app_module,
            "appointment_overlap",
            None,
        )

        if overlap:
            conflict = overlap(
                device.id,
                scheduled,
                duration,
            )

            if conflict:
                return jsonify(
                    ok=False,
                    error="APPOINTMENT_CONFLICT",
                    conflict_id=conflict.id,
                ), 409

        appt = Appointment(
            patient_id=patient.id,
            branch_id=branch.id,
            procedure_id=procedure.id,
            device_id=device.id,
            scheduled=scheduled,
            duration_min=duration,
            status="BOOKED",
            source="AI_VOICE",
            notes="Booked by RadBridge AI Reception",
        )

        db.session.add(appt)
        db.session.commit()

        return jsonify(
            ok=True,
            appointment_id=appt.id,
            scheduled=appt.scheduled.isoformat(),
            status=appt.status,
        )

    @bp.post("/api/voice/complaints")
    def complaint_create():
        data = request.get_json(silent=True) or {}

        description = str(
            data.get("description") or ""
        ).strip()

        if not description:
            return jsonify(
                ok=False,
                error="DESCRIPTION_REQUIRED"
            ), 400

        ticket_no = (
            "CMP-"
            + datetime.utcnow().strftime("%Y%m%d")
            + "-"
            + secrets.token_hex(3).upper()
        )

        row = db.session.execute(
            text("""
                INSERT INTO complaint_ticket
                (
                    ticket_no,
                    patient_id,
                    call_log_id,
                    appointment_id,
                    order_id,
                    branch_id,
                    category,
                    priority,
                    description,
                    status,
                    created_at
                )
                VALUES
                (
                    :ticket_no,
                    :patient_id,
                    :call_log_id,
                    :appointment_id,
                    :order_id,
                    :branch_id,
                    :category,
                    :priority,
                    :description,
                    'OPEN',
                    NOW()
                )
                RETURNING id
            """),
            {
                "ticket_no": ticket_no,
                "patient_id": data.get("patient_db_id"),
                "call_log_id": data.get("call_id"),
                "appointment_id": data.get("appointment_id"),
                "order_id": data.get("order_id"),
                "branch_id": data.get("branch_id"),
                "category": str(
                    data.get("category") or "GENERAL"
                )[:50],
                "priority": str(
                    data.get("priority") or "NORMAL"
                )[:20],
                "description": description,
            },
        )

        ticket_id = row.scalar()
        db.session.commit()

        return jsonify(
            ok=True,
            ticket_id=ticket_id,
            ticket_no=ticket_no,
            status="OPEN",
        )

    @bp.post("/api/voice/handoff")
    def handoff():
        data = request.get_json(silent=True) or {}

        call_id = data.get("call_id")
        reason = str(data.get("reason") or "")[:500]

        call = db.session.get(CallLog, call_id) \
            if call_id else None

        if call:
            call.status = "HUMAN_HANDOFF"
            call.notes = (
                (call.notes or "")
                + "\nAI HANDOFF: "
                + reason
            ).strip()

            db.session.commit()

        return jsonify(
            ok=True,
            action="TRANSFER_TO_HUMAN",
            reason=reason,
        )

    app.register_blueprint(bp)

    return bp
