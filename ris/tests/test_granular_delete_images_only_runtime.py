from datetime import datetime
from unittest.mock import Mock

import app as m


class FakeResponse:
    def __init__(self,status_code,json_data=None,text=""):
        self.status_code=status_code
        self._json=json_data
        self.text=text

    def json(self):
        return self._json or {}


def login(client,user):
    with client.session_transaction() as session:
        session["uid"]=user.id


def make_role(code):
    row=m.Role.query.filter_by(code=code).first()

    if row:
        return row

    row=m.Role(
        code=code,
        name=code,
    )

    m.db.session.add(row)
    m.db.session.flush()

    return row


def make_user(code,username):
    role=make_role(code)

    row=m.User(
        username=username,
        full_name=username,
        password_hash="x",
        role_id=role.id,
        active=True,
    )

    m.db.session.add(row)
    m.db.session.commit()

    return row


def make_case(accession="IMGDEL-001",study="study-001"):
    patient=(
        m.Patient.query
        .filter_by(patient_id="IMGDEL-P1")
        .first()
    )

    if patient is None:
        patient=m.Patient(
            patient_id="IMGDEL-P1",
            name="Images Delete Test",
        )

        m.db.session.add(patient)
        m.db.session.flush()

    order=m.Order(
        accession=accession,
        patient_id=patient.id,
        modality="CT",
        procedure="CT TEST",
        scheduled=m.datetime.utcnow(),
        status="COMPLETED",
        exam_status="EXAM_COMPLETED",
        pacs_study_id=study,
        pacs_status="IMAGES_COMPLETE",
        pacs_image_count=7,
        study_instance_uid="1.2.3.4.5",
    )

    m.db.session.add(order)
    m.db.session.commit()

    return patient,order


def orthanc_payload(accession="IMGDEL-001",patient_id="IMGDEL-P1"):
    return {
        "MainDicomTags":{
            "AccessionNumber":accession,
            "StudyInstanceUID":"1.2.3.4.5",
        },
        "PatientMainDicomTags":{
            "PatientID":patient_id,
        },
    }


def test_success_updates_only_pacs_state(monkeypatch,app_ctx):
    admin=make_user(
        "SUPER_ADMIN",
        "imgdel-admin-success",
    )

    patient,order=make_case()

    before_patient=m.Patient.query.count()
    before_order=m.Order.query.count()
    before_report=m.Report.query.count()

    calls={
        "delete":0,
        "get":0,
    }

    def fake_get(url,*args,**kwargs):
        calls["get"]+=1

        if calls["get"]==1:
            return FakeResponse(
                200,
                orthanc_payload(),
            )

        return FakeResponse(
            404,
            {},
        )

    def fake_delete(url,*args,**kwargs):
        calls["delete"]+=1
        return FakeResponse(
            200,
            {"RemainingAncestor":None},
        )

    monkeypatch.setattr(
        m.requests,
        "get",
        fake_get,
    )

    monkeypatch.setattr(
        m.requests,
        "delete",
        fake_delete,
    )

    client=m.app.test_client()
    login(client,admin)

    response=client.post(
        f"/admin/cancellation-center/order/{order.id}/delete-images",
        data={
            "confirm_accession":order.accession,
            "reason":"Synthetic isolated test",
        },
    )

    assert response.status_code==200

    payload=response.get_json()

    assert payload["ok"] is True
    assert payload["deleted"] is True
    assert payload["ris_state_updated"] is True

    m.db.session.expire_all()

    current=m.db.session.get(
        m.Order,
        order.id,
    )

    assert current is not None
    assert current.pacs_status=="IMAGES_DELETED"
    assert current.pacs_image_count==0
    assert current.pacs_study_id=="study-001"
    assert current.study_instance_uid=="1.2.3.4.5"

    assert m.Patient.query.count()==before_patient
    assert m.Order.query.count()==before_order
    assert m.Report.query.count()==before_report

    assert calls["delete"]==1

    audit=m.AuditLog.query.filter_by(
        action="PACS_IMAGES_DELETED_ADMIN",
        entity_id=str(order.id),
    ).first()

    assert audit is not None


def test_accession_mismatch_blocks_delete(monkeypatch,app_ctx):
    admin=make_user(
        "SUPER_ADMIN",
        "imgdel-admin-accession",
    )

    patient,order=make_case(
        accession="IMGDEL-002",
        study="study-002",
    )

    delete=Mock()

    monkeypatch.setattr(
        m.requests,
        "get",
        lambda *a,**k: FakeResponse(
            200,
            orthanc_payload(
                accession="IMGDEL-002",
            ),
        ),
    )

    monkeypatch.setattr(
        m.requests,
        "delete",
        delete,
    )

    client=m.app.test_client()
    login(client,admin)

    response=client.post(
        f"/admin/cancellation-center/order/{order.id}/delete-images",
        data={
            "confirm_accession":"WRONG",
            "reason":"Valid reason",
        },
    )

    assert response.status_code==409
    assert "ACCESSION_CONFIRMATION_MISMATCH" in response.get_json()["blockers"]
    delete.assert_not_called()


def test_missing_reason_blocks_delete(monkeypatch,app_ctx):
    admin=make_user(
        "SUPER_ADMIN",
        "imgdel-admin-reason",
    )

    patient,order=make_case(
        accession="IMGDEL-003",
        study="study-003",
    )

    delete=Mock()

    monkeypatch.setattr(
        m.requests,
        "get",
        lambda *a,**k: FakeResponse(
            200,
            orthanc_payload(
                accession="IMGDEL-003",
            ),
        ),
    )

    monkeypatch.setattr(
        m.requests,
        "delete",
        delete,
    )

    client=m.app.test_client()
    login(client,admin)

    response=client.post(
        f"/admin/cancellation-center/order/{order.id}/delete-images",
        data={
            "confirm_accession":"IMGDEL-003",
            "reason":"x",
        },
    )

    assert response.status_code==409
    assert "REASON_REQUIRED" in response.get_json()["blockers"]
    delete.assert_not_called()


def test_non_super_admin_blocks_delete(monkeypatch,app_ctx):
    user=make_user(
        "RECEPTION",
        "imgdel-reception",
    )

    patient,order=make_case(
        accession="IMGDEL-004",
        study="study-004",
    )

    delete=Mock()

    monkeypatch.setattr(
        m.requests,
        "delete",
        delete,
    )

    client=m.app.test_client()
    login(client,user)

    response=client.post(
        f"/admin/cancellation-center/order/{order.id}/delete-images",
        data={
            "confirm_accession":"IMGDEL-004",
            "reason":"Valid reason",
        },
    )

    assert response.status_code in (403,409)
    delete.assert_not_called()


def test_shared_study_blocks_delete(monkeypatch,app_ctx):
    admin=make_user(
        "SUPER_ADMIN",
        "imgdel-admin-shared",
    )

    patient,order=make_case(
        accession="IMGDEL-005",
        study="study-shared",
    )

    other_patient=m.Patient(
        patient_id="IMGDEL-P2",
        name="Other Study Owner",
    )

    m.db.session.add(other_patient)
    m.db.session.flush()

    other=m.Order(
        accession="IMGDEL-005-B",
        patient_id=other_patient.id,
        modality="CT",
        procedure="CT TEST",
        scheduled=m.datetime.utcnow(),
        status="COMPLETED",
        pacs_study_id="study-shared",
        pacs_status="IMAGES_COMPLETE",
        pacs_image_count=7,
    )

    m.db.session.add(other)
    m.db.session.commit()

    delete=Mock()

    monkeypatch.setattr(
        m.requests,
        "get",
        lambda *a,**k: FakeResponse(
            200,
            orthanc_payload(
                accession="IMGDEL-005",
            ),
        ),
    )

    monkeypatch.setattr(
        m.requests,
        "delete",
        delete,
    )

    client=m.app.test_client()
    login(client,admin)

    response=client.post(
        f"/admin/cancellation-center/order/{order.id}/delete-images",
        data={
            "confirm_accession":"IMGDEL-005",
            "reason":"Valid reason",
        },
    )

    assert response.status_code==409
    assert "PACS_STUDY_SHARED_BY_OTHER_ORDER" in response.get_json()["blockers"]
    delete.assert_not_called()


def test_active_transfer_blocks_delete(monkeypatch,app_ctx):
    admin=make_user(
        "SUPER_ADMIN",
        "imgdel-admin-transfer",
    )

    patient,order=make_case(
        accession="IMGDEL-006",
        study="study-006",
    )

    destination=(
        m.DicomDestination.query
        .filter_by(key="imgdel-test-destination")
        .first()
    )

    if destination is None:
        destination=m.DicomDestination(
            key="imgdel-test-destination",
            name="Images Delete Test Destination",
            ae_title="IMGDELTEST",
            host="127.0.0.1",
            port=104,
            destination_type="PACS",
            allow_manual_send=True,
            active=True,
        )

        m.db.session.add(destination)
        m.db.session.flush()

    job=m.PacsTransferJob(
        order_id=order.id,
        destination_id=destination.id,
        orthanc_study_id="study-006",
        status="PENDING",
    )

    m.db.session.add(job)
    m.db.session.commit()

    delete=Mock()

    monkeypatch.setattr(
        m.requests,
        "get",
        lambda *a,**k: FakeResponse(
            200,
            orthanc_payload(
                accession="IMGDEL-006",
            ),
        ),
    )

    monkeypatch.setattr(
        m.requests,
        "delete",
        delete,
    )

    client=m.app.test_client()
    login(client,admin)

    response=client.post(
        f"/admin/cancellation-center/order/{order.id}/delete-images",
        data={
            "confirm_accession":"IMGDEL-006",
            "reason":"Valid reason",
        },
    )

    assert response.status_code==409
    assert "ACTIVE_PACS_TRANSFER_JOB" in response.get_json()["blockers"]
    delete.assert_not_called()


def test_orthanc_identity_mismatch_blocks_delete(monkeypatch,app_ctx):
    admin=make_user(
        "SUPER_ADMIN",
        "imgdel-admin-identity",
    )

    patient,order=make_case(
        accession="IMGDEL-007",
        study="study-007",
    )

    delete=Mock()

    monkeypatch.setattr(
        m.requests,
        "get",
        lambda *a,**k: FakeResponse(
            200,
            orthanc_payload(
                accession="WRONG-ACCESSION",
            ),
        ),
    )

    monkeypatch.setattr(
        m.requests,
        "delete",
        delete,
    )

    client=m.app.test_client()
    login(client,admin)

    response=client.post(
        f"/admin/cancellation-center/order/{order.id}/delete-images",
        data={
            "confirm_accession":"IMGDEL-007",
            "reason":"Valid reason",
        },
    )

    assert response.status_code==409
    assert "ORTHANC_ACCESSION_MISMATCH" in response.get_json()["blockers"]
    delete.assert_not_called()


def test_orthanc_delete_http_failure_keeps_ris_state(monkeypatch,app_ctx):
    admin=make_user(
        "SUPER_ADMIN",
        "imgdel-admin-httpfail",
    )

    patient,order=make_case(
        accession="IMGDEL-008",
        study="study-008",
    )

    monkeypatch.setattr(
        m.requests,
        "get",
        lambda *a,**k: FakeResponse(
            200,
            orthanc_payload(
                accession="IMGDEL-008",
            ),
        ),
    )

    monkeypatch.setattr(
        m.requests,
        "delete",
        lambda *a,**k: FakeResponse(
            500,
            {},
        ),
    )

    client=m.app.test_client()
    login(client,admin)

    response=client.post(
        f"/admin/cancellation-center/order/{order.id}/delete-images",
        data={
            "confirm_accession":"IMGDEL-008",
            "reason":"Valid reason",
        },
    )

    assert response.status_code==502

    m.db.session.expire_all()

    current=m.db.session.get(
        m.Order,
        order.id,
    )

    assert current.pacs_status=="IMAGES_COMPLETE"
    assert current.pacs_image_count==7


def test_verify_not_404_keeps_ris_state(monkeypatch,app_ctx):
    admin=make_user(
        "SUPER_ADMIN",
        "imgdel-admin-verifyfail",
    )

    patient,order=make_case(
        accession="IMGDEL-009",
        study="study-009",
    )

    calls={"get":0}

    def fake_get(*args,**kwargs):
        calls["get"]+=1

        if calls["get"]==1:
            return FakeResponse(
                200,
                orthanc_payload(
                    accession="IMGDEL-009",
                ),
            )

        return FakeResponse(
            200,
            orthanc_payload(
                accession="IMGDEL-009",
            ),
        )

    monkeypatch.setattr(
        m.requests,
        "get",
        fake_get,
    )

    monkeypatch.setattr(
        m.requests,
        "delete",
        lambda *a,**k: FakeResponse(
            200,
            {},
        ),
    )

    client=m.app.test_client()
    login(client,admin)

    response=client.post(
        f"/admin/cancellation-center/order/{order.id}/delete-images",
        data={
            "confirm_accession":"IMGDEL-009",
            "reason":"Valid reason",
        },
    )

    assert response.status_code==502

    payload=response.get_json()

    assert payload["deleted"] is True
    assert payload["ris_state_updated"] is False

    m.db.session.expire_all()

    current=m.db.session.get(
        m.Order,
        order.id,
    )

    assert current.pacs_status=="IMAGES_COMPLETE"
    assert current.pacs_image_count==7


def test_source_never_deletes_ris_objects(app_ctx):
    import inspect

    source=inspect.getsource(
        m.granular_delete_order_images_only
    )

    forbidden=(
        "db.session.delete(order)",
        "db.session.delete(patient)",
        "Report.query.delete",
        "Attachment.query.delete",
    )

    for marker in forbidden:
        assert marker not in source
