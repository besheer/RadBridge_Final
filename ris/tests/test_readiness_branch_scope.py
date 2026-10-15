import json
from datetime import datetime
from uuid import uuid4

import app as m


def _scoped_order(suffix, branch):
    patient = m.Patient(patient_id=f"RB{suffix}", name=f"Readiness {suffix}")
    procedure = m.Procedure(
        code=f"RB{suffix}", name=f"Readiness {suffix}",
        modality="CT", active=True,
    )
    m.db.session.add_all([patient, procedure])
    m.db.session.flush()
    order = m.Order(
        accession=f"RB{suffix}", patient_id=patient.id, branch_id=branch.id,
        procedure_id=procedure.id, procedure=procedure.name, modality="CT",
        scheduled=datetime.utcnow(), status="REGISTERED",
    )
    m.db.session.add(order)
    m.db.session.flush()
    m.db.session.add(m.CaseReadiness(order_id=order.id, status="BLOCKED"))
    m.db.session.flush()
    return order, patient, procedure


def test_readiness_queues_and_exception_actions_are_branch_scoped(app_ctx):
    suffix = uuid4().hex[:8].upper()
    branch = m.Branch(code=f"RB{suffix}", name=f"Readiness branch {suffix}", active=True)
    other_branch = m.Branch(code=f"RO{suffix}", name=f"Other branch {suffix}", active=True)
    m.db.session.add_all([branch, other_branch])
    m.db.session.flush()
    own, own_patient, own_procedure = _scoped_order(suffix + "A", branch)
    other, other_patient, other_procedure = _scoped_order(suffix + "B", other_branch)
    role = m.Role(
        code=f"RB{suffix}", name="Synthetic readiness scope",
        permissions_json=json.dumps(["orders.view", "pacs.reconcile"]),
    )
    user = m.User(
        username=f"rb-{suffix}", full_name="Synthetic readiness user",
        password_hash="DISABLED-SYNTHETIC", role=role,
        branch_id=branch.id, active=True,
    )
    m.db.session.add_all([role, user])
    m.db.session.flush()
    client = m.app.test_client()
    with client.session_transaction() as state:
        state["uid"] = user.id

    try:
        dashboard = client.get("/operations/case-readiness")
        assert dashboard.status_code == 200
        assert own.accession.encode() in dashboard.data
        assert other.accession.encode() not in dashboard.data

        tat_dashboard = client.get("/operations/tat")
        assert tat_dashboard.status_code == 200
        assert own.accession.encode() in tat_dashboard.data
        assert other.accession.encode() not in tat_dashboard.data

        resolver = client.get(f"/operations/case-exceptions?q=RB{suffix}")
        assert resolver.status_code == 200
        assert own.accession.encode() in resolver.data
        assert other.accession.encode() not in resolver.data
        assert client.get(
            f"/operations/case-exceptions?order_id={other.id}"
        ).status_code == 403
        assert client.post(
            f"/orders/{other.id}/exceptions/series-map",
            data={"source_alias": "synthetic", "canonical_series": "synthetic"},
        ).status_code == 403
    finally:
        m.db.session.rollback()
        for order, patient, procedure in (
            (own, own_patient, own_procedure),
            (other, other_patient, other_procedure),
        ):
            m.CaseReadiness.query.filter_by(order_id=order.id).delete()
            m.Order.query.filter_by(id=order.id).delete()
            m.Patient.query.filter_by(id=patient.id).delete()
            m.Procedure.query.filter_by(id=procedure.id).delete()
        m.User.query.filter_by(id=user.id).delete()
        m.Role.query.filter_by(id=role.id).delete()
        m.Branch.query.filter(m.Branch.id.in_([branch.id, other_branch.id])).delete(
            synchronize_session=False
        )
        m.db.session.commit()


def test_pacs_reconciliation_and_exam_links_are_branch_scoped(app_ctx):
    suffix = uuid4().hex[:8].upper()
    branch = m.Branch(code=f"PB{suffix}", name=f"PACS branch {suffix}", active=True)
    other_branch = m.Branch(code=f"PO{suffix}", name=f"Other PACS branch {suffix}", active=True)
    m.db.session.add_all([branch, other_branch])
    m.db.session.flush()
    own, own_patient, own_procedure = _scoped_order(suffix + "A", branch)
    other, other_patient, other_procedure = _scoped_order(suffix + "B", other_branch)
    own_inbox = m.PacsStudyInbox(
        orthanc_study_id=f"OWN-STUDY-{suffix}", order_id=own.id,
        accession=own.accession, pacs_patient_name=f"Own PACS {suffix}",
        state="REVIEW_REQUIRED",
    )
    other_inbox = m.PacsStudyInbox(
        orthanc_study_id=f"OTHER-STUDY-{suffix}", order_id=other.id,
        accession=other.accession, pacs_patient_name=f"Secret PACS {suffix}",
        state="REVIEW_REQUIRED",
    )
    other_link = m.PacsExamLink(
        orthanc_study_id=f"FOREIGN-LINK-{suffix}", order_id=other.id,
        link_role="SECONDARY", active=True, reason="synthetic secret link",
    )
    role = m.Role(
        code=f"PR{suffix}", name="Synthetic PACS branch scope",
        permissions_json=json.dumps([
            "orders.view", "pacs.reconcile", "pacs.exam_link", "audit.view",
            "correction.review",
        ]),
    )
    user = m.User(
        username=f"pr-{suffix}", full_name="Synthetic PACS branch user",
        password_hash="DISABLED-SYNTHETIC", role=role,
        branch_id=branch.id, active=True,
    )
    m.db.session.add_all([own_inbox, other_inbox, other_link, role, user])
    m.db.session.flush()
    client = m.app.test_client()
    with client.session_transaction() as state:
        state["uid"] = user.id

    try:
        response = client.get("/pacs/reconciliation")
        assert response.status_code == 200
        assert own.accession.encode() in response.data
        assert other.accession.encode() not in response.data
        assert f"Secret PACS {suffix}".encode() not in response.data
        assert client.get(
            f"/pacs/reconciliation/{other_inbox.orthanc_study_id}/preview?order_id={other.id}"
        ).status_code == 403
        assert client.post(
            f"/pacs/reconciliation/{other_inbox.orthanc_study_id}/match",
            data={"order_id": other.id, "reason": "synthetic cross-branch match"},
        ).status_code == 403
        assert client.post(
            f"/pacs/reconciliation/{other_inbox.orthanc_study_id}/match",
            data={"order_id": own.id, "reason": "synthetic wrong-study link"},
        ).status_code == 404
        assert client.post(
            "/pacs/exam-link",
            data={
                "primary_order_id": own.id,
                "secondary_order_id": other.id,
                "reason": "synthetic cross-branch link",
            },
        ).status_code == 403
        assert client.post(
            f"/pacs/exam-link/{other_link.id}/remove",
            data={"reason": "synthetic cross-branch removal"},
        ).status_code == 403
        assert client.post("/pacs/reconciliation/auto-safe").status_code == 403
        assert m.PacsExamLink.query.filter_by(id=other_link.id).first() is not None
    finally:
        m.db.session.rollback()
        m.PacsExamLink.query.filter_by(id=other_link.id).delete()
        m.PacsStudyInbox.query.filter(
            m.PacsStudyInbox.orthanc_study_id.in_(
                [own_inbox.orthanc_study_id, other_inbox.orthanc_study_id]
            )
        ).delete(synchronize_session=False)
        for order, patient, procedure in (
            (own, own_patient, own_procedure),
            (other, other_patient, other_procedure),
        ):
            m.CaseReadiness.query.filter_by(order_id=order.id).delete()
            m.Order.query.filter_by(id=order.id).delete()
            m.Patient.query.filter_by(id=patient.id).delete()
            m.Procedure.query.filter_by(id=procedure.id).delete()
        m.User.query.filter_by(id=user.id).delete()
        m.Role.query.filter_by(id=role.id).delete()
        m.Branch.query.filter(m.Branch.id.in_([branch.id, other_branch.id])).delete(
            synchronize_session=False
        )
        m.db.session.commit()


def test_pacs_transfer_retry_and_cancel_are_case_branch_scoped(app_ctx, monkeypatch):
    suffix = uuid4().hex[:8].upper()
    branch = m.Branch(code=f"TB{suffix}", name=f"Transfer branch {suffix}", active=True)
    other_branch = m.Branch(code=f"TO{suffix}", name=f"Other transfer {suffix}", active=True)
    m.db.session.add_all([branch, other_branch])
    m.db.session.flush()
    own, own_patient, own_procedure = _scoped_order(suffix + "A", branch)
    other, other_patient, other_procedure = _scoped_order(suffix + "B", other_branch)
    own_destination = m.DicomDestination(
        key=f"OWN{suffix}", name="Synthetic own PACS", ae_title="OWNPACS",
        host="127.0.0.1", port=104, branch_id=None, active=True,
    )
    other_destination = m.DicomDestination(
        key=f"OTHER{suffix}", name="Synthetic other PACS", ae_title="OTHERPACS",
        host="127.0.0.1", port=104, branch_id=other_branch.id, active=True,
    )
    role = m.Role(
        code=f"TR{suffix}", name="Synthetic PACS transfer scope",
        permissions_json=json.dumps(["pacs.transfer"]),
    )
    user = m.User(
        username=f"tr-{suffix}", full_name="Synthetic PACS transfer user",
        password_hash="DISABLED-SYNTHETIC", role=role,
        branch_id=branch.id, active=True,
    )
    m.db.session.add_all([own_destination, other_destination, role, user])
    m.db.session.flush()
    own_retry = m.PacsTransferJob(
        order_id=own.id, orthanc_study_id=f"OWN-{suffix}",
        destination_id=own_destination.id, status="FAILED",
    )
    other_retry = m.PacsTransferJob(
        order_id=other.id, orthanc_study_id=f"OTHER-R-{suffix}",
        destination_id=other_destination.id, status="FAILED",
    )
    own_cancel = m.PacsTransferJob(
        order_id=own.id, orthanc_study_id=f"OWN-C-{suffix}",
        destination_id=own_destination.id, status="PENDING",
    )
    other_cancel = m.PacsTransferJob(
        order_id=other.id, orthanc_study_id=f"OTHER-C-{suffix}",
        destination_id=other_destination.id, status="PENDING",
    )
    m.db.session.add_all([own_retry, other_retry, own_cancel, other_cancel])
    m.db.session.flush()
    client = m.app.test_client()
    with client.session_transaction() as state:
        state["uid"] = user.id

    try:
        actions = client.get(f"/pacs/actions/{own.id}")
        assert actions.status_code == 200
        assert b"Synthetic own PACS" in actions.data
        assert b"Synthetic other PACS" not in actions.data
        monkeypatch.setattr(m, "test_dicom_destination", lambda destination: None)
        assert client.post(
            f"/pacs/destinations/{own_destination.id}/echo?order_id={own.id}"
        ).status_code == 302
        assert client.post(
            f"/pacs/destinations/{other_destination.id}/echo?order_id={own.id}"
        ).status_code == 403
        assert client.post(
            f"/pacs/actions/{own.id}/send",
            data={"destination_id": other_destination.id},
        ).status_code == 403
        assert client.post(f"/pacs/transfers/{own_retry.id}/retry").status_code == 302
        assert client.post(f"/pacs/transfers/{own_cancel.id}/cancel").status_code == 302
        assert client.post(f"/pacs/transfers/{other_retry.id}/retry").status_code == 403
        assert client.post(f"/pacs/transfers/{other_cancel.id}/cancel").status_code == 403
        assert client.post("/pacs/transfers/process").status_code == 403
        m.db.session.refresh(own_retry)
        m.db.session.refresh(own_cancel)
        m.db.session.refresh(other_retry)
        m.db.session.refresh(other_cancel)
        assert own_retry.status == "PENDING"
        assert own_cancel.status == "CANCELLED"
        assert other_retry.status == "FAILED"
        assert other_cancel.status == "PENDING"
    finally:
        m.db.session.rollback()
        for job in (own_retry, other_retry, own_cancel, other_cancel):
            m.PacsTransferJob.query.filter_by(id=job.id).delete()
        for order, patient, procedure in (
            (own, own_patient, own_procedure),
            (other, other_patient, other_procedure),
        ):
            m.CaseReadiness.query.filter_by(order_id=order.id).delete()
            m.Order.query.filter_by(id=order.id).delete()
            m.Patient.query.filter_by(id=patient.id).delete()
            m.Procedure.query.filter_by(id=procedure.id).delete()
        m.DicomDestination.query.filter(
            m.DicomDestination.id.in_([own_destination.id, other_destination.id])
        ).delete(synchronize_session=False)
        m.User.query.filter_by(id=user.id).delete()
        m.Role.query.filter_by(id=role.id).delete()
        m.Branch.query.filter(m.Branch.id.in_([branch.id, other_branch.id])).delete(
            synchronize_session=False
        )
        m.db.session.commit()


def test_branch_user_management_is_limited_to_assigned_branch(app_ctx):
    suffix = uuid4().hex[:8].upper()
    branch = m.Branch(code=f"UM{suffix}", name=f"User branch {suffix}", active=True)
    other_branch = m.Branch(code=f"UO{suffix}", name=f"Other user branch {suffix}", active=True)
    role = m.Role(
        code=f"UR{suffix}", name="Synthetic branch user manager",
        permissions_json=json.dumps(["users.view", "users.manage", "orders.view"]),
    )
    m.db.session.add_all([branch, other_branch, role])
    m.db.session.flush()
    actor = m.User(
        username=f"um-{suffix}", full_name="Synthetic branch manager",
        password_hash="DISABLED-SYNTHETIC", role=role,
        branch_id=branch.id, active=True,
    )
    own_user = m.User(
        username=f"uo-{suffix}", full_name="Own branch account",
        password_hash="DISABLED-SYNTHETIC", role=role,
        branch_id=branch.id, active=True,
    )
    foreign_user = m.User(
        username=f"uf-{suffix}", full_name="Foreign branch secret",
        password_hash="DISABLED-SYNTHETIC", role=role,
        branch_id=other_branch.id, active=True,
    )
    unassigned_user = m.User(
        username=f"ug-{suffix}", full_name="Unassigned central account",
        password_hash="DISABLED-SYNTHETIC", role=role,
        branch_id=None, active=True,
    )
    m.db.session.add_all([actor, own_user, foreign_user, unassigned_user])
    m.db.session.flush()
    own_profile = m.UserProfile(user_id=own_user.id, specialty="Own specialty")
    foreign_profile = m.UserProfile(user_id=foreign_user.id, specialty="Foreign secret specialty")
    m.db.session.add_all([own_profile, foreign_profile])
    m.db.session.commit()
    client = m.app.test_client()
    with client.session_transaction() as state:
        state["uid"] = actor.id

    try:
        response = client.get("/admin/users")
        assert response.status_code == 200
        assert b"Own branch account" in response.data
        assert b"Foreign branch secret" not in response.data
        assert b"Unassigned central account" not in response.data
        assert b"Foreign secret specialty" not in response.data

        assert client.post(
            f"/admin/users/{foreign_user.id}/edit",
            data={"full_name": "Changed", "role_id": role.id, "branch_id": branch.id, "active": "1"},
        ).status_code == 403
        assert client.post(
            f"/admin/users/{foreign_user.id}/toggle",
        ).status_code == 403
        assert client.post(
            f"/admin/users/{foreign_user.id}/reset-password",
            data={"new_password": "synthetic-password-123"},
        ).status_code == 403
        assert client.get(
            f"/admin/users/{foreign_user.id}/clinical-scope",
        ).status_code == 403
        assert client.post(
            "/admin/users",
            data={"username": f"unscoped-{suffix}", "full_name": "Unscoped", "password": "synthetic-password-123", "role_id": role.id},
        ).status_code == 403
        assert m.User.query.filter_by(id=foreign_user.id).first().full_name == "Foreign branch secret"
        assert m.User.query.filter_by(id=unassigned_user.id).first() is not None
    finally:
        m.UserProfile.query.filter(m.UserProfile.user_id.in_([own_user.id, foreign_user.id])).delete(synchronize_session=False)
        m.User.query.filter(m.User.id.in_([actor.id, own_user.id, foreign_user.id, unassigned_user.id])).delete(synchronize_session=False)
        m.Role.query.filter_by(id=role.id).delete()
        m.Branch.query.filter(m.Branch.id.in_([branch.id, other_branch.id])).delete(synchronize_session=False)
        m.db.session.commit()


def test_search_and_reports_portal_are_branch_scoped(app_ctx):
    suffix = uuid4().hex[:8].upper()
    branch = m.Branch(code=f"SB{suffix}", name=f"Search branch {suffix}", active=True)
    other_branch = m.Branch(code=f"SO{suffix}", name=f"Other search branch {suffix}", active=True)
    m.db.session.add_all([branch, other_branch])
    m.db.session.flush()
    own, own_patient, own_procedure = _scoped_order(suffix + "A", branch)
    other, other_patient, other_procedure = _scoped_order(suffix + "B", other_branch)
    role = m.Role(
        code=f"SB{suffix}", name="Synthetic branch search",
        permissions_json=json.dumps(["orders.view", "reports.view", "patients.view"]),
    )
    user = m.User(
        username=f"sb-{suffix}", full_name="Synthetic branch search user",
        password_hash="DISABLED-SYNTHETIC", role=role,
        branch_id=branch.id, active=True,
    )
    m.db.session.add_all([role, user])
    m.db.session.flush()
    client = m.app.test_client()
    with client.session_transaction() as state:
        state["uid"] = user.id

    try:
        portal = client.get(f"/reports-portal?q=RB{suffix}")
        assert portal.status_code == 200
        assert own.accession.encode() in portal.data
        assert other.accession.encode() not in portal.data
        csv_report = client.get(f"/reports-portal.csv?q=RB{suffix}")
        assert csv_report.status_code == 200
        assert own.accession.encode() in csv_report.data
        assert other.accession.encode() not in csv_report.data
        search = client.get(f"/search?q=RB{suffix}")
        assert search.status_code == 200
        assert own_patient.name.encode() in search.data
        assert other_patient.name.encode() not in search.data
        assert client.get(
            f"/reports-portal?branch_id={other_branch.id}"
        ).status_code == 403
    finally:
        m.db.session.rollback()
        for order, patient, procedure in (
            (own, own_patient, own_procedure),
            (other, other_patient, other_procedure),
        ):
            m.CaseReadiness.query.filter_by(order_id=order.id).delete()
            m.Order.query.filter_by(id=order.id).delete()
            m.Patient.query.filter_by(id=patient.id).delete()
            m.Procedure.query.filter_by(id=procedure.id).delete()
        m.User.query.filter_by(id=user.id).delete()
        m.Role.query.filter_by(id=role.id).delete()
        m.Branch.query.filter(m.Branch.id.in_([branch.id, other_branch.id])).delete(
            synchronize_session=False
        )
        m.db.session.commit()


def test_operational_workspaces_are_branch_scoped(app_ctx, tmp_path):
    suffix = uuid4().hex[:8].upper()
    branch = m.Branch(code=f"DB{suffix}", name=f"Dashboard branch {suffix}", active=True)
    other_branch = m.Branch(code=f"DO{suffix}", name=f"Other dashboard {suffix}", active=True)
    m.db.session.add_all([branch, other_branch])
    m.db.session.flush()
    own, own_patient, own_procedure = _scoped_order(suffix + "A", branch)
    other, other_patient, other_procedure = _scoped_order(suffix + "B", other_branch)
    own_patient.name = f"Own patient only {suffix}"
    other_patient.name = f"Other patient only {suffix}"
    # The dashboard defines "today" in the server's local timezone.
    now = datetime.now()
    own.scheduled = now
    other.scheduled = now
    own_appointment = m.Appointment(
        patient_id=own_patient.id, branch_id=branch.id,
        procedure_id=own_procedure.id, scheduled=now, status="BOOKED",
        notes=f"OWN-APPOINTMENT-{suffix}",
    )
    other_appointment = m.Appointment(
        patient_id=other_patient.id, branch_id=other_branch.id,
        procedure_id=other_procedure.id, scheduled=now, status="BOOKED",
        notes=f"OTHER-APPOINTMENT-{suffix}",
    )
    role = m.Role(
        code=f"DB{suffix}", name="Synthetic branch operations",
        permissions_json=json.dumps([
            "orders.view", "patients.view", "appointments.manage",
            "attachments.view", "pacs.transfer", "devices.manage",
        ]),
    )
    user = m.User(
        username=f"db-{suffix}", full_name="Synthetic branch operations user",
        password_hash="DISABLED-SYNTHETIC", role=role,
        branch_id=branch.id, active=True,
    )
    m.db.session.add_all([own_appointment, other_appointment, role, user])
    m.db.session.flush()
    client = m.app.test_client()
    with client.session_transaction() as state:
        state["uid"] = user.id

    try:
        for path in ("/", "/orders", "/patients", "/appointments",
                     "/operations/dashboard", "/operations/journey", "/management"):
            response = client.get(path)
            assert response.status_code == 200, (path, response.status_code)
            if path == "/patients":
                assert own_patient.name.encode() in response.data
                assert other_patient.name.encode() not in response.data
            elif path == "/operations/dashboard":
                assert b"Today Visits" in response.data
                assert b"<b>1</b>" in response.data
            elif path == "/management":
                assert b"Total Exams" in response.data
                assert b"<b>1</b>" in response.data
            else:
                assert own.accession.encode() in response.data, path
                assert other.accession.encode() not in response.data, path
        appointments = client.get("/appointments")
        assert own_patient.name.encode() in appointments.data
        assert other_patient.name.encode() not in appointments.data
        patients = client.get("/patients")
        assert own_patient.name.encode() in patients.data
        assert other_patient.name.encode() not in patients.data
        assert client.get(f"/orders/{own.id}").status_code == 200
        assert client.get(f"/orders/{other.id}").status_code == 403
        assert client.get(f"/orders/{own.id}/attachments").status_code == 200
        assert client.get(f"/orders/{other.id}/attachments").status_code == 403
        assert client.get(f"/patients/{own_patient.id}/timeline").status_code == 200
        assert client.get(f"/patients/{other_patient.id}/timeline").status_code == 403
        for suffix_path in ("documents", "alerts", "external-priors"):
            assert client.get(
                f"/patients/{own_patient.id}/{suffix_path}"
            ).status_code == 200
            assert client.get(
                f"/patients/{other_patient.id}/{suffix_path}"
            ).status_code == 403

        own_file = tmp_path / f"own-{suffix}.txt"
        own_file.write_text("synthetic", encoding="utf-8")
        own_attachment = m.Attachment(
            patient_id=own_patient.id, order_id=own.id,
            category="OTHER", original_name=own_file.name,
            stored_path=str(own_file),
        )
        other_attachment = m.Attachment(
            patient_id=other_patient.id, order_id=other.id,
            category="OTHER", original_name=f"other-{suffix}.txt",
            stored_path=str(tmp_path / "does-not-exist.txt"),
        )
        m.db.session.add_all([own_attachment, other_attachment])
        m.db.session.flush()
        assert client.get(f"/attachments/{own_attachment.id}").status_code == 200
        assert client.get(f"/attachments/{other_attachment.id}").status_code == 403
        own_document = m.PatientDocument(
            patient_id=own_patient.id, order_id=own.id,
            document_type="OTHER", file_path=str(own_file),
        )
        other_document = m.PatientDocument(
            patient_id=other_patient.id, order_id=other.id,
            document_type="OTHER", file_path=str(tmp_path / "other-doc.txt"),
        )
        own_alert = m.PatientAlert(
            patient_id=own_patient.id, alert_type="OTHER", title="Synthetic own alert",
        )
        other_alert = m.PatientAlert(
            patient_id=other_patient.id, alert_type="OTHER", title="Synthetic other alert",
        )
        m.db.session.add_all([own_document, other_document, own_alert, other_alert])
        m.db.session.flush()
        assert client.get(f"/documents/{own_document.id}/review").status_code == 200
        assert client.get(f"/documents/{other_document.id}/review").status_code == 403
        assert client.post(f"/patient-alerts/{own_alert.id}/resolve").status_code == 302
        assert client.post(f"/patient-alerts/{other_alert.id}/resolve").status_code == 403
        assert client.get(f"/pacs/actions/{own.id}").status_code == 200
        assert client.get(f"/pacs/actions/{other.id}").status_code == 403
        for path in (
            f"/orders/{other.id}/actions",
            f"/orders/{other.id}/label-print",
            f"/orders/{other.id}/sticker",
            f"/orders/{other.id}/sticker/preview",
            f"/orders/{other.id}/study-thumbnail",
            f"/patients/{other_patient.id}/communications",
        ):
            assert client.get(path).status_code == 403, path
        assert client.post(f"/orders/{other.id}/resend-mwl").status_code == 403
        pacs_tracking = client.get("/pacs/tracking")
        assert own.accession.encode() in pacs_tracking.data
        assert other.accession.encode() not in pacs_tracking.data
    finally:
        m.db.session.rollback()
        for appointment in (own_appointment, other_appointment):
            m.Appointment.query.filter_by(id=appointment.id).delete()
        if "own_attachment" in locals():
            m.Attachment.query.filter(m.Attachment.id.in_(
                [own_attachment.id, other_attachment.id]
            )).delete(synchronize_session=False)
        if "own_document" in locals():
            m.PatientDocument.query.filter(m.PatientDocument.id.in_(
                [own_document.id, other_document.id]
            )).delete(synchronize_session=False)
            m.PatientAlert.query.filter(m.PatientAlert.id.in_(
                [own_alert.id, other_alert.id]
            )).delete(synchronize_session=False)
        for order, patient, procedure in (
            (own, own_patient, own_procedure),
            (other, other_patient, other_procedure),
        ):
            m.CaseReadiness.query.filter_by(order_id=order.id).delete()
            m.Order.query.filter_by(id=order.id).delete()
            m.Patient.query.filter_by(id=patient.id).delete()
            m.Procedure.query.filter_by(id=procedure.id).delete()
        m.User.query.filter_by(id=user.id).delete()
        m.Role.query.filter_by(id=role.id).delete()
        m.Branch.query.filter(m.Branch.id.in_([branch.id, other_branch.id])).delete(
            synchronize_session=False
        )
        m.db.session.commit()


def test_receivables_and_csv_export_are_branch_scoped(app_ctx):
    suffix = uuid4().hex[:8].upper()
    branch = m.Branch(code=f"RB{suffix}", name=f"Receivables {suffix}", active=True)
    other_branch = m.Branch(code=f"RO{suffix}", name=f"Other receivables {suffix}", active=True)
    m.db.session.add_all([branch, other_branch])
    m.db.session.flush()
    own, own_patient, own_procedure = _scoped_order(suffix + "A", branch)
    other, other_patient, other_procedure = _scoped_order(suffix + "B", other_branch)
    own_patient.name = f"Own finance patient {suffix}"
    other_patient.name = f"Other finance patient {suffix}"
    own.gross_price = 125
    other.gross_price = 275
    role = m.Role(
        code=f"RF{suffix}", name="Synthetic receivables branch scope",
        permissions_json=json.dumps(["receivables.view", "export.view"]),
    )
    user = m.User(
        username=f"rf-{suffix}", full_name="Synthetic receivables user",
        password_hash="DISABLED-SYNTHETIC", role=role,
        branch_id=branch.id, active=True,
    )
    m.db.session.add_all([role, user])
    m.db.session.flush()
    client = m.app.test_client()
    with client.session_transaction() as state:
        state["uid"] = user.id

    try:
        page = client.get("/accounting/receivables")
        assert page.status_code == 200
        assert own_patient.name.encode() in page.data
        assert other_patient.name.encode() not in page.data
        csv_report = client.get("/accounting/receivables.csv")
        assert csv_report.status_code == 200
        assert own.accession.encode() in csv_report.data
        assert other.accession.encode() not in csv_report.data
        assert client.get(
            f"/accounting/receivables?branch_id={other_branch.id}"
        ).status_code == 403
    finally:
        m.db.session.rollback()
        for order, patient, procedure in (
            (own, own_patient, own_procedure),
            (other, other_patient, other_procedure),
        ):
            m.Order.query.filter_by(id=order.id).delete()
            m.Patient.query.filter_by(id=patient.id).delete()
            m.Procedure.query.filter_by(id=procedure.id).delete()
        m.User.query.filter_by(id=user.id).delete()
        m.Role.query.filter_by(id=role.id).delete()
        m.Branch.query.filter(m.Branch.id.in_([branch.id, other_branch.id])).delete(
            synchronize_session=False
        )
        m.db.session.commit()


def test_finance_reports_and_entries_are_branch_scoped(app_ctx):
    suffix = uuid4().hex[:8].upper()
    branch = m.Branch(code=f"FB{suffix}", name=f"Finance {suffix}", active=True)
    other_branch = m.Branch(code=f"FO{suffix}", name=f"Other finance {suffix}", active=True)
    m.db.session.add_all([branch, other_branch])
    m.db.session.flush()
    own, own_patient, own_procedure = _scoped_order(suffix + "A", branch)
    other, other_patient, other_procedure = _scoped_order(suffix + "B", other_branch)
    own_patient.name = f"Own finance patient {suffix}"
    other_patient.name = f"Other finance patient {suffix}"
    role = m.Role(
        code=f"FF{suffix}", name="Synthetic finance scope",
        permissions_json=json.dumps(["financial.view", "export.view"]),
    )
    user = m.User(
        username=f"ff-{suffix}", full_name="Synthetic finance user",
        password_hash="DISABLED-SYNTHETIC", role=role,
        branch_id=branch.id, active=True,
    )
    own_entry = m.FinancialEntry(
        entry_date=datetime.utcnow().date(), branch_id=branch.id,
        entry_type="EXPENSE", description=f"Own entry {suffix}", amount=10,
    )
    other_entry = m.FinancialEntry(
        entry_date=datetime.utcnow().date(), branch_id=other_branch.id,
        entry_type="EXPENSE", description=f"Other entry {suffix}", amount=20,
    )
    m.db.session.add_all([role, user, own_entry, other_entry])
    m.db.session.flush()
    client = m.app.test_client()
    with client.session_transaction() as state:
        state["uid"] = user.id

    try:
        for path in ("/accounting/reports", "/accounting/reports.csv"):
            response = client.get(path)
            assert response.status_code == 200
            assert own.accession.encode() in response.data
            assert other.accession.encode() not in response.data
        for path in (
            "/accounting/financial-center",
            "/accounting/financial-center/export/csv?report=maintenance",
            "/accounting/entries",
        ):
            response = client.get(path)
            assert response.status_code == 200
            assert f"Other entry {suffix}".encode() not in response.data
        assert client.get(
            f"/accounting/financial-center?branch_id={other_branch.id}"
        ).status_code == 403
        assert client.post(
            "/accounting/entries",
            data={"entry_type": "EXPENSE", "branch_id": other_branch.id},
        ).status_code == 403
    finally:
        m.db.session.rollback()
        m.FinancialEntry.query.filter(
            m.FinancialEntry.id.in_([own_entry.id, other_entry.id])
        ).delete(synchronize_session=False)
        for order, patient, procedure in (
            (own, own_patient, own_procedure),
            (other, other_patient, other_procedure),
        ):
            m.CaseReadiness.query.filter_by(order_id=order.id).delete()
            m.Order.query.filter_by(id=order.id).delete()
            m.Patient.query.filter_by(id=patient.id).delete()
            m.Procedure.query.filter_by(id=procedure.id).delete()
        m.User.query.filter_by(id=user.id).delete()
        m.Role.query.filter_by(id=role.id).delete()
        m.Branch.query.filter(m.Branch.id.in_([branch.id, other_branch.id])).delete(
            synchronize_session=False
        )
        m.db.session.commit()


def test_staff_and_warehouse_workspaces_are_branch_scoped(app_ctx):
    suffix = uuid4().hex[:8].upper()
    branch = m.Branch(code=f"WB{suffix}", name=f"Warehouse {suffix}", active=True)
    other_branch = m.Branch(code=f"WO{suffix}", name=f"Other warehouse {suffix}", active=True)
    m.db.session.add_all([branch, other_branch])
    m.db.session.flush()
    own, own_patient, own_procedure = _scoped_order(suffix + "A", branch)
    other, other_patient, other_procedure = _scoped_order(suffix + "B", other_branch)
    own_wh = m.Warehouse(code=f"WH{suffix}", name=f"Own warehouse {suffix}", branch_id=branch.id, active=True)
    other_wh = m.Warehouse(code=f"WO{suffix}X", name=f"Other warehouse secret {suffix}", branch_id=other_branch.id, active=True)
    own_item = m.InventoryItem(code=f"II{suffix}A", name=f"Own item {suffix}", active=True)
    other_item = m.InventoryItem(code=f"II{suffix}B", name=f"Other item {suffix}", active=True)
    role = m.Role(
        code=f"FW{suffix}", name="Synthetic warehouse scope",
        permissions_json=json.dumps([
            "inventory.view", "inventory.reports", "inventory.manage",
            "consumables.use", "technician.worklist",
        ]),
    )
    user = m.User(
        username=f"fw-{suffix}", full_name="Synthetic warehouse user",
        password_hash="DISABLED-SYNTHETIC", role=role,
        branch_id=branch.id, active=True,
    )
    m.db.session.add_all([own_wh, other_wh, own_item, other_item, role, user])
    m.db.session.flush()
    own_lot = m.InventoryLot(
        warehouse_id=own_wh.id, item_id=own_item.id, lot_no=f"OWN{suffix}", qty_on_hand=4,
    )
    other_lot = m.InventoryLot(
        warehouse_id=other_wh.id, item_id=other_item.id, lot_no=f"OTHER{suffix}", qty_on_hand=9,
    )
    own_policy = m.WarehouseStockPolicy(warehouse_id=own_wh.id, item_id=own_item.id, active=True)
    other_policy = m.WarehouseStockPolicy(warehouse_id=other_wh.id, item_id=other_item.id, active=True)
    own_movement = m.WarehouseStockMovement(
        warehouse_id=own_wh.id, item_id=own_item.id, movement_type="RECEIPT", qty=4,
        notes=f"Own ledger {suffix}",
    )
    other_movement = m.WarehouseStockMovement(
        warehouse_id=other_wh.id, item_id=other_item.id, movement_type="RECEIPT", qty=9,
        notes=f"Other ledger secret {suffix}",
    )
    own_usage = m.OrderConsumableUsage(
        order_id=own.id, warehouse_id=own_wh.id, item_id=own_item.id, qty=1,
        unit_cost=2, usage_type="USED",
    )
    other_usage = m.OrderConsumableUsage(
        order_id=other.id, warehouse_id=other_wh.id, item_id=other_item.id, qty=1,
        unit_cost=2, usage_type="USED",
    )
    m.db.session.add_all([
        own_lot, other_lot, own_policy, other_policy,
        own_movement, other_movement, own_usage, other_usage,
    ])
    m.db.session.flush()
    client = m.app.test_client()
    with client.session_transaction() as state:
        state["uid"] = user.id

    try:
        warehouses = client.get("/inventory/warehouses")
        assert warehouses.status_code == 200
        assert own_wh.name.encode() in warehouses.data
        assert other_wh.name.encode() not in warehouses.data
        assert client.get(f"/inventory/stock?warehouse_id={other_wh.id}").status_code == 403
        assert client.post(
            "/inventory/warehouses",
            data={"code": f"FORGED{suffix}", "name": "Forbidden", "branch_id": other_branch.id},
        ).status_code == 403
        assert client.post(
            "/inventory/warehouses",
            data={"code": f"NOBRANCH{suffix}", "name": "Forbidden"},
        ).status_code == 403
        assert client.post(
            "/admin/inventory/batches",
            data={"consumable_id": own_item.id, "branch_id": other_branch.id},
        ).status_code == 403
        assert client.post("/inventory/warehouses/auto-create").status_code == 403
        assert client.post(
            f"/inventory/warehouses/create-for-branch/{other_branch.id}"
        ).status_code == 403
        assert client.post("/inventory/migrate-legacy-items").status_code == 403
        assert client.post(
            "/inventory/stock",
            data={"warehouse_id": other_wh.id, "item_id": own_item.id, "qty": 1, "reason": "forged"},
        ).status_code == 403
        policies = client.get("/inventory/stock-policies")
        assert policies.status_code == 200
        assert other_wh.name.encode() not in policies.data
        ledger = client.get("/inventory/ledger")
        assert ledger.status_code == 200
        assert f"Own ledger {suffix}".encode() in ledger.data
        assert f"Other ledger secret {suffix}".encode() not in ledger.data
        usage = client.get("/inventory/consumption-report")
        assert usage.status_code == 200
        assert own.accession.encode() in usage.data
        assert other.accession.encode() not in usage.data
        assert client.get(f"/nursing/{other.id}").status_code == 403
        assert client.get(f"/technician/{other.id}").status_code == 403
    finally:
        m.db.session.rollback()
        for model, ids in (
            (m.InventoryLot, [own_lot.id, other_lot.id]),
            (m.WarehouseStockPolicy, [own_policy.id, other_policy.id]),
            (m.WarehouseStockMovement, [own_movement.id, other_movement.id]),
            (m.OrderConsumableUsage, [own_usage.id, other_usage.id]),
        ):
            model.query.filter(model.id.in_(ids)).delete(synchronize_session=False)
        m.db.session.flush()
        for order, patient, procedure in (
            (own, own_patient, own_procedure),
            (other, other_patient, other_procedure),
        ):
            m.CaseReadiness.query.filter_by(order_id=order.id).delete()
            m.Order.query.filter_by(id=order.id).delete()
            m.Patient.query.filter_by(id=patient.id).delete()
            m.Procedure.query.filter_by(id=procedure.id).delete()
        m.User.query.filter_by(id=user.id).delete()
        m.Role.query.filter_by(id=role.id).delete()
        m.Warehouse.query.filter(m.Warehouse.id.in_([own_wh.id, other_wh.id])).delete(
            synchronize_session=False
        )
        m.InventoryItem.query.filter(m.InventoryItem.id.in_([own_item.id, other_item.id])).delete(
            synchronize_session=False
        )
        m.Branch.query.filter(m.Branch.id.in_([branch.id, other_branch.id])).delete(
            synchronize_session=False
        )
        m.db.session.commit()


def test_smart_intake_sessions_and_documents_are_branch_scoped(app_ctx, tmp_path):
    suffix = uuid4().hex[:8].upper()
    branch = m.Branch(code=f"IB{suffix}", name=f"Intake {suffix}", active=True)
    other_branch = m.Branch(code=f"IO{suffix}", name=f"Other intake {suffix}", active=True)
    m.db.session.add_all([branch, other_branch])
    m.db.session.flush()
    role = m.Role(
        code=f"IR{suffix}", name="Synthetic intake branch scope",
        permissions_json=json.dumps(["patients.create"]),
    )
    own_user = m.User(
        username=f"ir-{suffix}", full_name="Synthetic intake user",
        password_hash="DISABLED-SYNTHETIC", role=role,
        branch_id=branch.id, active=True,
    )
    other_user = m.User(
        username=f"ior-{suffix}", full_name="Other intake user",
        password_hash="DISABLED-SYNTHETIC", role=role,
        branch_id=other_branch.id, active=True,
    )
    m.db.session.add_all([role, own_user, other_user])
    m.db.session.flush()
    own_intake = m.SmartIntakeSession(
        session_key=f"OWN-{suffix}", created_by=own_user.id,
        status="UPLOADING", extracted_json="{}",
    )
    other_intake = m.SmartIntakeSession(
        session_key=f"OTHER-{suffix}", created_by=other_user.id,
        status="UPLOADING", extracted_json="{}",
    )
    m.db.session.add_all([own_intake, other_intake])
    m.db.session.flush()
    own_path = tmp_path / f"own-intake-{suffix}.txt"
    other_path = tmp_path / f"other-intake-{suffix}.txt"
    own_path.write_text("synthetic own document", encoding="utf-8")
    other_path.write_text("synthetic other document", encoding="utf-8")
    own_doc = m.SmartIntakeDocument(
        intake_id=own_intake.id, document_type="OTHER",
        file_path=str(own_path), original_name=own_path.name,
    )
    other_doc = m.SmartIntakeDocument(
        intake_id=other_intake.id, document_type="OTHER",
        file_path=str(other_path), original_name=other_path.name,
    )
    m.db.session.add_all([own_doc, other_doc])
    m.db.session.flush()
    client = m.app.test_client()
    with client.session_transaction() as state:
        state["uid"] = own_user.id

    try:
        recent = client.get("/intake/smart")
        assert recent.status_code == 200
        assert f"/intake/smart/{own_intake.id}".encode() in recent.data
        assert f"/intake/smart/{other_intake.id}".encode() not in recent.data
        own_page = client.get(f"/intake/smart/{own_intake.id}")
        assert own_page.status_code == 200, own_page.data.decode(errors="replace")[:500]
        assert client.get(f"/intake/smart/{other_intake.id}").status_code == 403
        assert client.get(
            f"/intake/smart/{other_intake.id}/document/{other_doc.id}/file"
        ).status_code == 403
        assert client.get(
            f"/intake/smart/{own_intake.id}/document/{own_doc.id}/file"
        ).status_code == 200
    finally:
        m.db.session.rollback()
        for model, ids in (
            (m.SmartIntakeDocument, [own_doc.id, other_doc.id]),
            (m.SmartIntakeSession, [own_intake.id, other_intake.id]),
            (m.User, [own_user.id, other_user.id]),
        ):
            model.query.filter(model.id.in_(ids)).delete(synchronize_session=False)
        m.Role.query.filter_by(id=role.id).delete()
        m.Branch.query.filter(m.Branch.id.in_([branch.id, other_branch.id])).delete(
            synchronize_session=False
        )
        m.db.session.commit()


def test_patient_export_and_destruction_tools_respect_branch_scope(app_ctx):
    suffix = uuid4().hex[:8].upper()
    branch = m.Branch(code=f"DB{suffix}", name=f"Data {suffix}", active=True)
    other_branch = m.Branch(code=f"DO{suffix}", name=f"Other data {suffix}", active=True)
    m.db.session.add_all([branch, other_branch])
    m.db.session.flush()
    own, own_patient, own_procedure = _scoped_order(suffix + "A", branch)
    other, other_patient, other_procedure = _scoped_order(suffix + "B", other_branch)
    role = m.Role(
        code=f"DR{suffix}", name="Synthetic patient data scope",
        permissions_json=json.dumps([
            "backup.view", "data.export", "data.anonymize", "data.delete.patient",
            "data.cancel.case", "backup.all_patients", "data.delete.all_patients",
        ]),
    )
    user = m.User(
        username=f"dr-{suffix}", full_name="Synthetic data user",
        password_hash="DISABLED-SYNTHETIC", role=role,
        branch_id=branch.id, active=True,
    )
    m.db.session.add_all([role, user])
    m.db.session.flush()
    client = m.app.test_client()
    with client.session_transaction() as state:
        state["uid"] = user.id

    try:
        assert client.get("/admin/data-management").status_code == 200
        exported = client.post(
            "/admin/data-management/export-patient",
            data={"patient_key": str(other_patient.id)},
        )
        assert exported.status_code == 302
        assert exported.mimetype != "application/zip"
        assert client.post(
            "/admin/data-management/anonymize-patient",
            data={"patient_id": other_patient.id},
        ).status_code == 403
        assert client.post(
            "/admin/data-management/delete-patient",
            data={"patient_id": other_patient.id},
        ).status_code == 403
        assert client.get(
            f"/admin/cancellation-center/patient/{other_patient.id}/preview"
        ).status_code == 403
        assert client.post("/admin/data-management/backup-all-patients").status_code == 403
        assert client.post("/admin/data-management/delete-all-patients").status_code == 403
        assert m.Patient.query.filter_by(id=other_patient.id).first() is other_patient
    finally:
        m.db.session.rollback()
        for order, patient, procedure in (
            (own, own_patient, own_procedure),
            (other, other_patient, other_procedure),
        ):
            m.CaseReadiness.query.filter_by(order_id=order.id).delete()
            m.Order.query.filter_by(id=order.id).delete()
            m.Patient.query.filter_by(id=patient.id).delete()
            m.Procedure.query.filter_by(id=procedure.id).delete()
        m.User.query.filter_by(id=user.id).delete()
        m.Role.query.filter_by(id=role.id).delete()
        m.Branch.query.filter(m.Branch.id.in_([branch.id, other_branch.id])).delete(
            synchronize_session=False
        )
        m.db.session.commit()


def test_executive_analytics_are_branch_scoped(app_ctx):
    suffix = uuid4().hex[:8].upper()
    branch = m.Branch(code=f"EA{suffix}", name=f"Analytics {suffix}", active=True)
    other_branch = m.Branch(code=f"EO{suffix}", name=f"Other analytics {suffix}", active=True)
    m.db.session.add_all([branch, other_branch])
    m.db.session.flush()
    own, own_patient, own_procedure = _scoped_order(suffix + "A", branch)
    other, other_patient, other_procedure = _scoped_order(suffix + "B", other_branch)
    own.gross_price = 125
    other.gross_price = 275
    role = m.Role(
        code=f"EA{suffix}", name="Synthetic executive analytics scope",
        permissions_json=json.dumps(["analytics.executive.view"]),
    )
    user = m.User(
        username=f"ea-{suffix}", full_name="Synthetic analytics user",
        password_hash="DISABLED-SYNTHETIC", role=role,
        branch_id=branch.id, active=True,
    )
    other_user = m.User(
        username=f"eo-{suffix}", full_name=f"Other branch doctor {suffix}",
        password_hash="DISABLED-SYNTHETIC", role=role,
        branch_id=other_branch.id, active=True,
    )
    own_device = m.Device(
        branch_id=branch.id, name=f"Own device {suffix}", modality="CT",
        ae_title=f"OWN{suffix[:12]}",
    )
    other_device = m.Device(
        branch_id=other_branch.id, name=f"Other device {suffix}", modality="MR",
        ae_title=f"OTH{suffix[:12]}",
    )
    m.db.session.add_all([role, user, other_user, own_device, other_device])
    m.db.session.flush()
    client = m.app.test_client()
    with client.session_transaction() as state:
        state["uid"] = user.id

    try:
        today = datetime.utcnow().date().isoformat()
        page = client.get(f"/analytics/executive?start={today}&end={today}")
        assert page.status_code == 200
        assert branch.name.encode() in page.data
        assert other_branch.name.encode() not in page.data
        assert other_user.full_name.encode() not in page.data
        assert own_device.name.encode() in page.data
        assert other_device.name.encode() not in page.data
        assert client.get(
            f"/analytics/executive?start={today}&end={today}&branch_id={other_branch.id}"
        ).status_code == 403
    finally:
        m.db.session.rollback()
        for order, patient, procedure in (
            (own, own_patient, own_procedure),
            (other, other_patient, other_procedure),
        ):
            m.Order.query.filter_by(id=order.id).delete()
            m.Patient.query.filter_by(id=patient.id).delete()
            m.Procedure.query.filter_by(id=procedure.id).delete()
        m.User.query.filter(m.User.id.in_([user.id, other_user.id])).delete(
            synchronize_session=False
        )
        m.Device.query.filter(m.Device.id.in_([own_device.id, other_device.id])).delete(
            synchronize_session=False
        )
        m.Role.query.filter_by(id=role.id).delete()
        m.Branch.query.filter(m.Branch.id.in_([branch.id, other_branch.id])).delete(
            synchronize_session=False
        )
        m.db.session.commit()


def test_advanced_search_and_doctor_filter_are_branch_scoped(app_ctx):
    suffix = uuid4().hex[:8].upper()
    branch = m.Branch(code=f"AS{suffix}", name=f"Advanced {suffix}", active=True)
    other_branch = m.Branch(code=f"AO{suffix}", name=f"Other advanced {suffix}", active=True)
    m.db.session.add_all([branch, other_branch])
    m.db.session.flush()
    own, own_patient, own_procedure = _scoped_order(suffix + "A", branch)
    other, other_patient, other_procedure = _scoped_order(suffix + "B", other_branch)
    user_role = m.Role(
        code=f"AS{suffix}", name="Synthetic advanced search user",
        permissions_json="[]",
    )
    actor = m.User(
        username=f"as-{suffix}", full_name="Synthetic advanced search actor",
        password_hash="DISABLED-SYNTHETIC", role=user_role,
        branch_id=branch.id, active=True,
    )
    radiologist_role = m.Role.query.filter_by(code="RADIOLOGIST").first()
    own_doctor = m.User(
        username=f"ad-{suffix}", full_name=f"Own doctor {suffix}",
        password_hash="DISABLED-SYNTHETIC", role=radiologist_role,
        branch_id=branch.id, active=True,
    )
    other_doctor = m.User(
        username=f"od-{suffix}", full_name=f"Other doctor {suffix}",
        password_hash="DISABLED-SYNTHETIC", role=radiologist_role,
        branch_id=other_branch.id, active=True,
    )
    m.db.session.add_all([user_role, actor, own_doctor, other_doctor])
    m.db.session.flush()
    client = m.app.test_client()
    with client.session_transaction() as state:
        state["uid"] = actor.id

    try:
        page = client.get("/search/advanced")
        assert page.status_code == 200
        assert own_patient.name.encode() in page.data
        assert other_patient.name.encode() not in page.data
        assert branch.name.encode() in page.data
        assert other_branch.name.encode() not in page.data
        assert own_doctor.full_name.encode() in page.data
        assert other_doctor.full_name.encode() not in page.data
    finally:
        m.db.session.rollback()
        for order, patient, procedure in (
            (own, own_patient, own_procedure),
            (other, other_patient, other_procedure),
        ):
            m.Order.query.filter_by(id=order.id).delete()
            m.Patient.query.filter_by(id=patient.id).delete()
            m.Procedure.query.filter_by(id=procedure.id).delete()
        m.User.query.filter(m.User.id.in_([actor.id, own_doctor.id, other_doctor.id])).delete(
            synchronize_session=False
        )
        m.Role.query.filter_by(id=user_role.id).delete()
        m.Branch.query.filter(m.Branch.id.in_([branch.id, other_branch.id])).delete(
            synchronize_session=False
        )
        m.db.session.commit()


def test_command_center_and_escalation_reads_are_branch_scoped(app_ctx, monkeypatch):
    suffix = uuid4().hex[:8].upper()
    branch = m.Branch(code=f"CC{suffix}", name=f"Command center {suffix}", active=True)
    other_branch = m.Branch(code=f"CO{suffix}", name=f"Other command center {suffix}", active=True)
    m.db.session.add_all([branch, other_branch])
    m.db.session.flush()
    own, own_patient, own_procedure = _scoped_order(suffix + "A", branch)
    other, other_patient, other_procedure = _scoped_order(suffix + "B", other_branch)
    own.pacs_status = "PACS_OFFLINE"
    other.pacs_status = "PACS_OFFLINE"
    role = m.Role(
        code=f"CC{suffix}", name="Synthetic command center scope",
        permissions_json=json.dumps([
            "audit.view", "orders.view", "workflow.command.view",
        ]),
    )
    user = m.User(
        username=f"cc-{suffix}", full_name="Synthetic command center user",
        password_hash="DISABLED-SYNTHETIC", role=role,
        branch_id=branch.id, active=True,
    )
    own_notification = m.RISNotification(
        branch_id=branch.id, severity="WARNING", event_type="SYNTHETIC",
        title=f"Own escalation {suffix}", body=own.accession, status="NEW",
    )
    other_notification = m.RISNotification(
        branch_id=other_branch.id, severity="CRITICAL", event_type="SYNTHETIC",
        title=f"Other escalation {suffix}", body=other.accession, status="NEW",
    )
    own_event = m.EventOutbox(
        event_type="ORDER_MWL_CREATE", entity_type="order",
        entity_id=str(own.id), payload_json="{}", status="PENDING",
    )
    other_event = m.EventOutbox(
        event_type="ORDER_MWL_CREATE", entity_type="order",
        entity_id=str(other.id), payload_json="{}", status="PENDING",
    )
    m.db.session.add_all([
        role, user, own_notification, other_notification, own_event, other_event,
    ])
    m.db.session.flush()
    monkeypatch.setattr(m, "orthanc_ok", lambda: False)
    client = m.app.test_client()
    with client.session_transaction() as state:
        state["uid"] = user.id

    try:
        escalation = client.get("/operations/escalations")
        assert escalation.status_code == 200
        assert own_notification.title.encode() in escalation.data
        assert other_notification.title.encode() not in escalation.data

        command_center = client.get("/operations/command-center")
        assert command_center.status_code == 200
        assert own.accession.encode() in command_center.data
        assert other.accession.encode() not in command_center.data

        events = client.get("/api/command-center/events?limit=200")
        assert events.status_code == 200
        assert own.accession.encode() in events.data
        assert other.accession.encode() not in events.data

        snapshot = client.get("/api/command-center/snapshot")
        assert snapshot.status_code == 200
        data = snapshot.get_json()
        assert data["orders"]["status"].get("REGISTERED") == 1
        assert data["events"]["outbox_status"].get("PENDING") == 1
    finally:
        m.db.session.rollback()
        m.RISNotification.query.filter(
            m.RISNotification.id.in_([own_notification.id, other_notification.id])
        ).delete(synchronize_session=False)
        m.EventOutbox.query.filter(
            m.EventOutbox.id.in_([own_event.id, other_event.id])
        ).delete(synchronize_session=False)
        for order, patient, procedure in (
            (own, own_patient, own_procedure),
            (other, other_patient, other_procedure),
        ):
            m.Order.query.filter_by(id=order.id).delete()
            m.Patient.query.filter_by(id=patient.id).delete()
            m.Procedure.query.filter_by(id=procedure.id).delete()
        m.User.query.filter_by(id=user.id).delete()
        m.Role.query.filter_by(id=role.id).delete()
        m.Branch.query.filter(m.Branch.id.in_([branch.id, other_branch.id])).delete(
            synchronize_session=False
        )
        m.db.session.commit()
