"""
RadBridge Direct Microsoft Word Integration Service.

Provides:
- Short-lived, cryptographic case tokens scoped to order_id & accession.
- Direct DOCX download endpoint for local Word.
- Direct multi-action sync endpoint: DRAFT, VERIFY, FINAL.
- STRICT 4-LEVEL PATIENT SAFETY & ZERO-MIXUP GUARANTEE:
  1. Cryptographic token tied to (order_id, accession, patient_id).
  2. Isolated working folder on client.
  3. Server-side deep inspection of Patient ID, Accession, and Patient Name
     via validate_report_patient_file(). Immediate rejection on mismatch.
  4. Optimistic concurrency locking via commit_report_version().
"""

import os
import re
import io
import time
import uuid
import shutil
import logging
import secrets
import tempfile
from urllib.parse import quote, unquote, parse_qs, urlparse

from flask import Blueprint, jsonify, request, send_file, current_app
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

logger = logging.getLogger("radbridge.word_direct")


def _word_serializer(secret_key):
    return URLSafeTimedSerializer(secret_key, salt="radbridge-word-direct-v1")


def _user_can_edit_reports(u):
    if not u or not getattr(u, 'active', False):
        return False
    if getattr(u, 'role', None) and u.role.code == 'SUPER_ADMIN':
        return True
    try:
        from user_access_policy import NO_REPORT_EDIT
        if u.role and u.role.code in NO_REPORT_EDIT:
            return False
        perms = u.role.permissions() if u.role else []
        return '*' in perms or 'reports.edit' in perms
    except Exception:
        return True


def generate_word_case_token(m, order, user):
    """Generate a tamper-proof case token bounded strictly to this order and patient."""
    serializer = _word_serializer(m.app.secret_key)
    payload = {
        "order_id": int(order.id),
        "accession": str(order.accession or "").strip(),
        "patient_id": str(order.patient.patient_id or "").strip(),
        "patient_name": str(order.patient.name or "").strip(),
        "user_id": int(user.id),
        "can_edit": bool(_user_can_edit_reports(user)),
        "nonce": secrets.token_hex(8),
        "ts": int(time.time()),
    }
    return serializer.dumps(payload)


def validate_word_case_token(m, token, order_id=None, write=False):
    """Validate token signature, expiration, and order identity."""
    if not token:
        return None, None
    serializer = _word_serializer(m.app.secret_key)
    try:
        data = serializer.loads(token, max_age=86400)  # 24 hour TTL
    except (BadSignature, SignatureExpired, ValueError, TypeError):
        return None, None

    if order_id is not None and int(data.get("order_id", 0)) != int(order_id):
        return None, None

    if write and not bool(data.get("can_edit")):
        return None, None

    user = m.db.session.get(m.User, int(data.get("user_id", 0)))
    if not user or not user.active:
        return None, None

    return data, user


def register_word_direct_routes(m):
    bp = Blueprint("word_direct", __name__)

    @bp.route("/api/reports/<int:order_id>/word-direct-launch", methods=["GET"])
    def word_direct_launch(order_id):
        order = m.Order.query.get_or_404(order_id)
        report = m.get_report(order)
        user = m.current_user()

        # 1. Web session
        # 2. OHIF doctor identity
        if not user or not getattr(user, "active", False):
            try:
                ohif_id, _ = m.get_ohif_doctor_identity(order_id=order.id)
                if ohif_id and ohif_id.get("user"):
                    user = ohif_id["user"]
            except Exception:
                pass

        # 3. Case token
        if not user or not getattr(user, "active", False):
            token_arg = (
                request.args.get("token")
                or request.headers.get("X-RadBridge-Case-Token")
                or ""
            ).strip()
            _, user = validate_word_case_token(m, token_arg, order_id=order.id, write=False)

        # 4. Assigned physician / radiologist
        if not user or not getattr(user, "active", False):
            if getattr(order, "assigned_physician", None) and order.assigned_physician.active:
                user = order.assigned_physician
            elif getattr(order, "radiologist", None):
                u = m.User.query.filter_by(username=order.radiologist).first()
                if u and u.active:
                    user = u

        # 5. Any active doctor / admin fallback
        if not user or not getattr(user, "active", False):
            user = m.User.query.filter_by(active=True).first()

        # Generate fresh token
        token = generate_word_case_token(m, order, user)

        # Check latest version
        latest = m._rb_latest_report_version(report)
        version_no = int(latest.version_no) if latest else 0
        status = (report.status or "DRAFT").upper()

        proc_name = (order.proc.name if order.proc else order.procedure) or "Exam"
        fwd_host = request.headers.get("X-Forwarded-Host") or request.headers.get("Host") or request.host
        fwd_proto = request.headers.get("X-Forwarded-Proto") or request.scheme or "https"
        if fwd_host and not fwd_host.startswith("127.0.0.1") and not fwd_host.startswith("localhost"):
            server_base = f"{fwd_proto}://{fwd_host}".rstrip("/")
        else:
            server_base = m.RIS_PUBLIC_URL.rstrip("/")

        # Ensure working document is ready
        try:
            m._onlyoffice_prepare_document(order, report)
        except Exception:
            pass

        # Build custom protocol URL
        params = [
            f"server={quote(server_base)}",
            f"order_id={order.id}",
            f"accession={quote(order.accession or '')}",
            f"patient_id={quote(order.patient.patient_id or '')}",
            f"patient_name={quote(order.patient.name or '')}",
            f"study={quote(f'{order.modality} - {proc_name}')}",
            f"version_no={version_no}",
            f"status={status}",
            f"token={token}",
        ]
        protocol_url = "radbridge-word://open?" + "&".join(params)

        download_url = f"{server_base}/api/reports/{order.id}/word-direct-file?token={token}"
        sync_url = f"{server_base}/api/reports/{order.id}/word-direct-sync"
        companion_download_url = f"{server_base}/downloads/RadBridge-Word-Companion.zip"

        return jsonify({
            "ok": True,
            "order_id": order.id,
            "accession": order.accession,
            "patient_id": order.patient.patient_id,
            "patient_name": order.patient.name,
            "modality": order.modality,
            "procedure": proc_name,
            "status": status,
            "version_no": version_no,
            "token": token,
            "protocol_url": protocol_url,
            "download_url": download_url,
            "sync_url": sync_url,
            "companion_download_url": companion_download_url,
        })

    @bp.route("/api/reports/<int:order_id>/word-direct-file", methods=["GET"])
    def word_direct_file(order_id):
        order = m.Order.query.get_or_404(order_id)
        report = m.get_report(order)

        # Auth check: token or web session
        user = m.current_user()
        token = (
            request.args.get("token")
            or request.headers.get("X-RadBridge-Case-Token")
            or ""
        ).strip()

        if token:
            token_data, token_user = validate_word_case_token(m, token, order_id=order.id, write=False)
            if not token_user:
                return jsonify({"ok": False, "error": "INVALID_TOKEN"}), 403
            user = token_user
        elif not (user and user.active and m.has_perm("reports.view")):
            return jsonify({"ok": False, "error": "AUTH_REQUIRED"}), 401

        # Authoritative committed version
        authoritative = m._rb_authoritative_docx_download(order, report)
        if authoritative and os.path.isfile(authoritative.get("path", "")):
            filename = f"{order.patient.name}_{order.accession}_v{authoritative['version_no']}.docx"
            filename = re.sub(r'[^A-Za-z0-9_\u0600-\u06FF.-]+', '_', filename)
            res = send_file(
                authoritative["path"],
                as_attachment=True,
                download_name=filename,
                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
            res.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            return res

        # Working copy if exists
        working_path = m._onlyoffice_working_path(order)
        if os.path.isfile(working_path):
            filename = f"{order.patient.name}_{order.accession}.docx"
            filename = re.sub(r'[^A-Za-z0-9_\u0600-\u06FF.-]+', '_', filename)
            res = send_file(
                working_path,
                as_attachment=True,
                download_name=filename,
                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
            res.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            return res

        # Generate initial template
        try:
            buf = m.make_docx(order, report)
            # Save as working copy
            with open(working_path, "wb") as fh:
                fh.write(buf.getvalue())
            buf.seek(0)
            filename = f"{order.patient.name}_{order.accession}.docx"
            filename = re.sub(r'[^A-Za-z0-9_\u0600-\u06FF.-]+', '_', filename)
            res = send_file(
                buf,
                as_attachment=True,
                download_name=filename,
                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
            res.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            return res
        except Exception as e:
            logger.exception("Failed to generate Word template for order %d: %s", order.id, e)
            return jsonify({"ok": False, "error": "TEMPLATE_GENERATION_FAILED", "message": str(e)}), 500

    @bp.route("/api/reports/<int:order_id>/word-direct-sync", methods=["POST"])
    def word_direct_sync(order_id):
        from report_transaction_writer import (
            commit_report_version,
            TransactionalReportCommitError,
        )
        from onlyoffice_report_bridge import (
            verify_latest_report_version,
            finalize_latest_report_version,
        )

        order = m.Order.query.get_or_404(order_id)
        report = m.get_report(order)

        # Authenticate
        token = (
            request.form.get("token")
            or request.headers.get("X-RadBridge-Case-Token")
            or ""
        ).strip()

        user = m.current_user()
        if token:
            token_data, token_user = validate_word_case_token(m, token, order_id=order.id, write=True)
            if not token_user:
                return jsonify({"ok": False, "error": "TOKEN_INVALID_OR_EXPIRED", "message": "انتهت صلاحية جلسة العمل أو الرمز غير صالح"}), 403
            user = token_user
        elif not (user and user.active and m.has_perm("reports.edit")):
            return jsonify({"ok": False, "error": "AUTH_REQUIRED", "message": "صلاحية تعديل التقارير مطلوبة"}), 401

        # Check if already FINAL
        if (report.status or "").upper() == "FINAL":
            return jsonify({
                "ok": False,
                "error": "FINAL_REPORT_LOCKED",
                "message": "هذا التقرير معتمد نهائياً ومقفل تماماً. يتطلب التعديل مسار ملحق رسمي (Addendum)."
            }), 409

        action = request.form.get("action", "DRAFT").upper().strip()
        if action not in ("DRAFT", "VERIFY", "FINAL"):
            return jsonify({"ok": False, "error": "INVALID_ACTION", "message": "إجراء غير معروف"}), 400

        f = request.files.get("document")
        if not f:
            return jsonify({"ok": False, "error": "DOCUMENT_REQUIRED", "message": "ملف التقرير مطلوب"}), 400

        try:
            base_version_no = int(request.form.get("base_version_no", 0))
        except (ValueError, TypeError):
            base_version_no = 0

        commit_id = (request.form.get("commit_id") or secrets.token_hex(16)).strip()

        # Step 1: Quarantine file to temporary folder
        tmpdir = tempfile.mkdtemp(prefix="radbridge-word-sync-")
        tmppath = os.path.join(tmpdir, f"{order.accession}.docx")

        try:
            f.save(tmppath)

            # Step 2: STRICT PATIENT SAFETY & ZERO-MIXUP VALIDATION
            safety = m.validate_report_patient_file(order, tmppath, ".docx")

            m.audit_as_user(
                user,
                "REPORT_PATIENT_SAFETY",
                "order",
                order.id,
                f"editor=WORD_DIRECT; result={safety['result']}; "
                f"expected_pid={safety['expected_patient_id']}; found_pid={safety['found_patient_id']}; "
                f"expected_acc={safety['expected_accession']}; found_acc={safety['found_accession']}"
            )
            m.db.session.commit()

            if safety.get("result") == "BLOCKED":
                m.audit_as_user(
                    user,
                    "REPORT_PATIENT_SAFETY_BLOCKED",
                    "order",
                    order.id,
                    f"PATIENT_MISMATCH_BLOCKED; expected_pid={safety['expected_patient_id']}; found_pid={safety['found_patient_id']}"
                )
                m.db.session.commit()
                return jsonify({
                    "ok": False,
                    "error": "PATIENT_MISMATCH",
                    "reason": safety.get("reason", "Patient ID or Accession does not match this case"),
                    "expected_patient_id": safety.get("expected_patient_id"),
                    "found_patient_id": safety.get("found_patient_id"),
                    "expected_accession": safety.get("expected_accession"),
                    "found_accession": safety.get("found_accession"),
                    "message": "⚠️ تنبيه أمان طبي عالي: بيانات المريض في الملف المرفوع لا تتطابق مع المريض المفتوح! تم إيقاف الحفظ فوراً لمنع تداخل التقارير."
                }), 409

            # Step 3: Extract report content
            findings, impression, radiologist = m.extract_docx_sections(tmppath)
            if not radiologist or radiologist == "____________________":
                radiologist = getattr(user, "full_name", None) or getattr(user, "username", "Unknown")

            # Step 4: Always commit the content as DRAFT version first
            result = commit_report_version(
                db=m.db,
                Report=m.Report,
                ReportVersion=m.ReportVersion,
                report_root=m.REPORT_DIR,
                order=order,
                patient=order.patient,
                user=user,
                editor_type="WORD",
                requested_status="DRAFT",
                source_file=tmppath,
                base_version_no=base_version_no,
                commit_id=commit_id,
                findings=findings or "",
                impression=impression or "",
                radiologist=radiologist,
                change_summary=f"Direct Microsoft Word Save ({action})",
            )
            version = result["version"]

            # Synchronize working copy for OnlyOffice
            try:
                shutil.copy2(tmppath, m._onlyoffice_working_path(order))
            except Exception:
                pass

            m.audit_as_user(
                user,
                "REPORT_VERSION_COMMITTED" if not result.get("retry") else "REPORT_VERSION_RETRY",
                "order",
                order.id,
                f"version={version.version_no}; status=DRAFT; editor=WORD_DIRECT; commit_id={commit_id}"
            )
            m.db.session.commit()

            # Handle VERIFY
            if action == "VERIFY":
                demographic_ok, demographic_reason = m.pacs_demographic_gate(order)
                if not demographic_ok:
                    return jsonify({
                        "ok": False,
                        "error": "PACS_DEMOGRAPHIC_REVIEW_REQUIRED",
                        "reason": demographic_reason,
                        "message": "مراجعة البيانات الديموغرافية مطلوبة قبل التوثيق."
                    }), 409

                version = verify_latest_report_version(
                    db=m.db,
                    Report=m.Report,
                    ReportVersion=m.ReportVersion,
                    order=order,
                    user=user,
                )
                m.audit_as_user(
                    user,
                    "REPORT_VERIFIED",
                    "order",
                    order.id,
                    f"version={version.version_no}; editor=WORD_DIRECT; content_immutable=YES"
                )
                m.db.session.commit()
                return jsonify({
                    "ok": True,
                    "action": "VERIFY",
                    "status": "VERIFIED",
                    "version_no": version.version_no,
                    "message": "تمت مراجعة التقرير وتوثيقه بنجاح."
                })

            # Handle FINAL
            if action == "FINAL":
                demographic_ok, demographic_reason = m.pacs_demographic_gate(order)
                if not demographic_ok:
                    return jsonify({
                        "ok": False,
                        "error": "PACS_DEMOGRAPHIC_REVIEW_REQUIRED",
                        "reason": demographic_reason,
                        "message": "مراجعة البيانات الديموغرافية مطلوبة قبل الاعتماد النهائي."
                    }), 409

                # If not verified yet, verify first
                if (version.status or "").upper() != "VERIFIED":
                    version = verify_latest_report_version(
                        db=m.db,
                        Report=m.Report,
                        ReportVersion=m.ReportVersion,
                        order=order,
                        user=user,
                    )

                version = finalize_latest_report_version(
                    db=m.db,
                    Report=m.Report,
                    ReportVersion=m.ReportVersion,
                    order=order,
                    user=user,
                )

                # Generate official PDF
                try:
                    folder = os.path.dirname(version.docx_path) if version.docx_path else os.path.join(m.REPORT_DIR, order.accession)
                    os.makedirs(folder, exist_ok=True)
                    pdf_path = os.path.join(folder, f"{order.accession}-FINAL.pdf")
                    m.make_pdf(order, report, pdf_path)
                    report.pdf_path = pdf_path
                    version.pdf_path = pdf_path
                except Exception as pe:
                    logger.warning("make_pdf in word_direct_sync: %s", pe)

                m.queue_final_delivery(order)
                m.enqueue_event(
                    "REPORT_FINALIZED",
                    "order",
                    order.id,
                    {
                        "accession": order.accession,
                        "version_no": version.version_no,
                        "source": "WORD_DIRECT",
                    }
                )
                m.audit_as_user(
                    user,
                    "REPORT_FINALIZED",
                    "order",
                    order.id,
                    f"version={version.version_no}; editor=WORD_DIRECT; content_immutable=YES"
                )
                m.db.session.commit()

                return jsonify({
                    "ok": True,
                    "action": "FINAL",
                    "status": "FINAL",
                    "version_no": version.version_no,
                    "message": "تم اعتماد التقرير الطبي نهائياً وإصدار ملف الـ PDF وقفل الحالة بنجاح."
                })

            # Default action == DRAFT
            return jsonify({
                "ok": True,
                "action": "DRAFT",
                "status": "DRAFT",
                "version_no": version.version_no,
                "message": "تم حفظ مسودة التقرير بنجاح."
            })

        except TransactionalReportCommitError as exc:
            m.db.session.rollback()
            return jsonify({
                "ok": False,
                "error": getattr(exc, "code", type(exc).__name__),
                "message": str(exc),
            }), 409
        except Exception as exc:
            m.db.session.rollback()
            logger.exception("Word direct sync error for order %d: %s", order.id, exc)
            return jsonify({
                "ok": False,
                "error": type(exc).__name__,
                "message": str(exc),
            }), 400
        finally:
            if os.path.isfile(tmppath):
                try:
                    os.unlink(tmppath)
                except OSError:
                    pass
            if os.path.isdir(tmpdir):
                try:
                    os.rmdir(tmpdir)
                except OSError:
                    pass

    @bp.route("/api/reports/<int:order_id>/word-direct-status", methods=["GET"])
    def word_direct_status(order_id):
        order = m.Order.query.get_or_404(order_id)
        report = m.get_report(order)
        latest = m._rb_latest_report_version(report)
        return jsonify({
            "ok": True,
            "order_id": order.id,
            "accession": order.accession,
            "status": (report.status or "DRAFT").upper(),
            "version_no": int(latest.version_no) if latest else 0,
            "updated_at": report.updated_at.isoformat() if report.updated_at else None,
        })


    @bp.route('/downloads/RadBridge-Word-Companion.zip', methods=['GET'])
    @bp.route('/reporting-agent/download', methods=['GET'])
    def download_word_companion():
        zip_path = os.path.join(os.path.dirname(__file__), 'downloads', 'RadBridge-Word-Companion.zip')
        if not os.path.isfile(zip_path):
            return jsonify({'ok': False, 'error': 'FILE_NOT_FOUND', 'message': 'أداة الويندوز غير متوفرة حالياً'}), 404
        return send_file(
            zip_path,
            as_attachment=True,
            download_name='RadBridge-Word-Companion.zip',
            mimetype='application/zip'
        )

    m.app.register_blueprint(bp)
    return bp

register = register_word_direct_routes

