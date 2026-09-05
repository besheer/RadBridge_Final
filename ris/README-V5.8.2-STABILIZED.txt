RIS Web v5.8.2 Stabilized
============================
Purpose: stabilization only.

Known fixes consolidated:
- base.html Jinja permission block fixed.
- User.role relationship filters replaced by Role.code query.
- Order SQLAlchemy model includes priority / assigned_doctor_id / assigned_at / assigned_doctor.
- Existing PostgreSQL schema migration includes matching Order columns.
- New Order includes Priority and safe Auto Assign.
- Assignment failures do not abort Order creation.
- Admin Assignment / Doctor Workspace / Unassigned Queue share one assignable-doctor query.
- Patient Safety / Word / LibreOffice / Upload / Reporting Workflow retained.

Validation tools:
  python3 preflight.py
  docker exec ris-web python /app/schema_check.py
  docker exec ris-web python /app/stabilization_self_test.py

Do not add new features until stabilization_self_test.py reports TOTAL FAILURES: 0.
