import csv
import io
import json
import re
import uuid

import app as m
import user_csv_transfer as transfer


def _row(username, role_code, branch_code):
    row = {column: "" for column in transfer.COLUMNS}
    row.update(username=username, full_name="Synthetic branch staff",
               role_code=role_code, branch_code=branch_code, active="true")
    return row


def _upload(client, csrf, row):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=transfer.COLUMNS)
    writer.writeheader()
    writer.writerow(row)
    return client.post(
        "/admin/users/import",
        data={"csrf_token": csrf,
              "file": (io.BytesIO(stream.getvalue().encode("utf-8-sig")), "users.csv")},
    )


def _token(response):
    found = re.search(rb'name="preview_token" value="([^"]+)"', response.data)
    return found.group(1).decode() if found else None


def test_branch_user_csv_is_limited_to_managed_branch_and_roles(app_ctx, monkeypatch):
    monkeypatch.setattr(m.db.session, "commit", m.db.session.flush)
    transfer._stages.clear()
    suffix = uuid.uuid4().hex[:8].upper()
    own = m.Branch(code=f"CSV-A-{suffix}", name=f"CSV branch A {suffix}", active=True)
    foreign = m.Branch(code=f"CSV-B-{suffix}", name=f"CSV branch B {suffix}", active=True)
    manager_role = m.Role(
        code=f"CSV-MANAGER-{suffix}", name="Branch CSV manager",
        permissions_json=json.dumps(["users.view", "users.manage"]),
    )
    staff_role = m.Role(
        code=f"CSV-STAFF-{suffix}", name="Branch CSV staff",
        permissions_json="[]",
    )
    m.db.session.add_all([own, foreign, manager_role, staff_role])
    m.db.session.flush()
    manager = m.User(
        username=f"csv-manager-{suffix}", full_name="Synthetic branch manager",
        password_hash="DISABLED-SYNTHETIC", role_id=manager_role.id,
        branch_id=own.id, active=True,
    )
    foreign_user = m.User(
        username=f"csv-foreign-{suffix}", full_name="Synthetic foreign user",
        password_hash="DISABLED-SYNTHETIC", role_id=staff_role.id,
        branch_id=foreign.id, active=True,
    )
    m.db.session.add_all([manager, foreign_user])
    m.db.session.flush()
    monkeypatch.setattr(m, "current_user", lambda: manager)
    client = m.app.test_client()
    with client.session_transaction() as state:
        state["uid"] = manager.id
        state["user_csv_csrf"] = "synthetic-csv-csrf"

    try:
        export = client.get("/admin/users/export.csv")
        assert export.status_code == 200
        exported_usernames = {
            row["username"]
            for row in csv.DictReader(io.StringIO(export.data.decode("utf-8-sig")))
        }
        assert manager.username in exported_usernames
        assert foreign_user.username not in exported_usernames

        import_page = client.get("/admin/users/import")
        assert import_page.status_code == 200
        assert own.code.encode() in import_page.data
        assert foreign.code.encode() not in import_page.data

        denied = _upload(
            client, "synthetic-csv-csrf",
            _row(f"csv-denied-{suffix}", staff_role.code, foreign.code),
        )
        assert denied.status_code == 200
        assert _token(denied) is None
        assert b"unauthorized" in denied.data.lower()

        unassigned = _upload(
            client, "synthetic-csv-csrf",
            _row(f"csv-unassigned-{suffix}", staff_role.code, ""),
        )
        assert _token(unassigned) is None
        assert b"required" in unassigned.data.lower()

        preview = _upload(
            client, "synthetic-csv-csrf",
            _row(f"csv-owned-{suffix}", staff_role.code, own.code),
        )
        preview_token = _token(preview)
        assert preview.status_code == 200 and preview_token
        applied = client.post(
            "/admin/users/import/apply",
            data={"csrf_token": "synthetic-csv-csrf", "preview_token": preview_token,
                  "temporary_password": "Synthetic-Only-Password"},
        )
        assert applied.status_code == 302
        created = m.User.query.filter_by(username=f"csv-owned-{suffix}").one()
        assert created.branch_id == own.id
    finally:
        m.db.session.rollback()
        m.db.session.remove()
        transfer._stages.clear()
