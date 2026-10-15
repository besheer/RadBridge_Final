"""Apply branch visibility to selected legacy operational read workspaces."""

from flask import abort, current_app, g, has_request_context, request
from sqlalchemy import event, select
from sqlalchemy.orm import Session, with_loader_criteria


BRANCH_SCOPED_ENDPOINTS = frozenset({
    "case_exception_resolver",
    "case_exception_series_map",
    "case_exception_series_map_deactivate",
    "case_exception_history_add",
    "case_exception_image_minimum",
    "case_exception_image_minimum_deactivate",
    "case_exception_refresh",
    "reports_portal",
    "reports_portal_csv",
    "universal_search",
    "advanced_search",
    "dashboard",
    "orders",
    "new_order",
    "new_patient",
    "smart_intake_start",
    "smart_intake_workspace",
    "smart_intake_document_file",
    "smart_intake_upload",
    "smart_intake_run_ocr",
    "smart_intake_run_all_ocr",
    "smart_intake_document_review",
    "smart_intake_review_save",
    "patients",
    "appointments",
    "operations_dashboard",
    "operations_journey",
    "management_dashboard",
    "workflow_command_center",
    "command_center_snapshot",
    "command_center_events",
    "escalation_board",
    "executive_analytics",
    "nursing_worklist",
    "nursing_case",
    "nursing_consumable_correct",
    "technician_worklist",
    "technician_case_workspace",
    "technician_case_consume",
    "order_consumables_available_stock",
    "order_consumables",
    "order_consumables_apply_defaults",
    "inventory_warehouses",
    "inventory_warehouses_auto_create",
    "inventory_create_for_branch",
    "inventory_migrate_legacy_items",
    "inventory_stock",
    "inventory_stock_policies",
    "inventory_ledger",
    "inventory_consumption_report",
    "admin_inventory_batches",
    "admin_inventory_movements",
    "admin_assignment_monitor",
    "coordinator_assignments",
    "admin_users",
    "admin_user_toggle",
    "admin_user_edit",
    "admin_user_reset_password",
    "user_clinical_scope",
    "admin_data_management",
    "admin_create_manifest_backup",
    "admin_export_patient",
    "admin_anonymize_patient",
    "admin_delete_patient",
    "granular_delete_patient_preview",
    "admin_backup_all_patients",
    "admin_delete_all_patients",
    "financial_center",
    "financial_center_export",
    "financial_entries",
    "financial_entry_void",
    "cashier_workstation",
    "accounting_reports",
    "accounting_reports_csv",
    "receivables",
    "receivables_csv",
    "order_detail",
    "order_attachments",
    "patient_timeline",
    "patient_documents",
    "patient_alerts",
    "patient_alert_resolve",
    "patient_external_priors",
    "document_review",
    "document_review_save",
    "attachment_download",
    "attachment_preview",
    "attachment_delete",
    "attachment_upload",
    "pacs_case_actions",
    "pacs_case_send",
    "pacs_transfer_retry",
    "pacs_transfer_cancel",
    "pacs_transfer_process",
    "pacs_destination_echo",
    "pacs_tracking",
    "pacs_tracking_refresh",
    "pacs_archive_dashboard",
    "pacs_reconciliation_preview",
    "pacs_reconciliation_correct_dicom",
    "pacs_reconciliation_audit",
    "pacs_reconciliation",
    "pacs_exam_link_create",
    "pacs_exam_link_remove",
    "pacs_reconciliation_match",
    "pacs_reconciliation_quarantine",
    "pacs_reconciliation_auto_safe",
    "order_actions",
    "order_label_print",
    "order_sticker",
    "order_sticker_preview",
    "patient_communications",
    "resend_mwl",
    "order_study_thumbnail",
})


def register(m):
    """Scope legacy read workspaces without rewriting preserved handlers."""

    def guard_request():
        endpoint = request.endpoint or ""
        if endpoint not in BRANCH_SCOPED_ENDPOINTS:
            return
        from registration_policy import allowed_registration_branches

        allowed = allowed_registration_branches()
        if allowed is None:
            return
        allowed = tuple(int(branch_id) for branch_id in allowed)
        g.rb_branch_scope = allowed

        branch_filter = (request.view_args or {}).get("branch_id")
        if branch_filter is None:
            branch_filter = request.values.get("branch_id", type=int)
        elif branch_filter is not None:
            try:
                branch_filter = int(branch_filter)
            except (TypeError, ValueError):
                abort(400)
        if branch_filter and branch_filter not in allowed:
            abort(403)
        if endpoint in (
            "inventory_warehouses_auto_create", "inventory_create_for_branch",
            "inventory_migrate_legacy_items", "admin_create_manifest_backup",
            "admin_backup_all_patients", "admin_delete_all_patients",
            # This endpoint runs a global matching batch over the PACS inbox.
            "pacs_reconciliation_auto_safe",
            # This endpoint drains the shared transfer queue, not one case.
            "pacs_transfer_process",
        ):
            abort(403)
        if endpoint == "new_patient" and request.method == "POST":
            # Standalone legacy creation creates an unassigned patient; use the
            # branch-bound unified registration workflow instead.
            abort(403)
        if (
            request.method == "POST"
            and endpoint in ("inventory_warehouses", "admin_inventory_batches")
            and branch_filter is None
        ):
            abort(403)
        if (
            request.method == "POST"
            and endpoint in ("admin_users", "admin_user_edit")
            and (m.has_perm("users.manage") or m.has_perm("*"))
            and branch_filter is None
        ):
            # Branch managers cannot create or move accounts into the global scope.
            abort(403)

        user_id = (request.view_args or {}).get("user_id")
        if user_id is not None and endpoint in {
            "admin_user_toggle", "admin_user_edit", "admin_user_reset_password",
            "user_clinical_scope",
        } and m.User.query.filter_by(id=user_id).first() is None:
            # Validate before legacy Query.get_or_404 calls, which may use the
            # identity map without issuing a branch-filtered SQL query.
            abort(403)

        order = None
        order_id = (request.view_args or {}).get("order_id")
        if order_id is None:
            order_id = request.values.get("order_id", type=int)
        if order_id is not None:
            # The ORM guard below limits this lookup to the user's permitted branches.
            order = m.Order.query.filter_by(id=order_id).first()
            if order is None:
                abort(403)
        patient_id = (request.view_args or {}).get("patient_id")
        if patient_id is None:
            patient_id = request.values.get("patient_id", type=int)
        if patient_id is None and endpoint == "new_order":
            # The legacy registration form calls this field "patient". Validate
            # it before Query.get_or_404 can bypass SQL criteria via the identity map.
            if request.values.get("patient_mode", "existing").strip() != "new":
                patient_id = request.values.get("patient", type=int)
        if patient_id is not None:
            # Query explicitly; Query.get() may return an identity-map object without SQL.
            patient = m.Patient.query.filter_by(id=patient_id).first()
            if patient is None:
                abort(403)
        intake_id = (request.view_args or {}).get("intake_id")
        if intake_id is not None and m.SmartIntakeSession.query.filter_by(
            id=intake_id
        ).first() is None:
            abort(403)
        warehouse_id = (request.view_args or {}).get("warehouse_id")
        if warehouse_id is None:
            warehouse_id = request.values.get("warehouse_id", type=int)
        if warehouse_id is not None and m.Warehouse.query.filter_by(
            id=warehouse_id
        ).first() is None:
            abort(403)
        if order is not None and patient_id is not None and order.patient_id != patient_id:
            abort(403)
        appointment_id = (request.view_args or {}).get("appointment_id")
        if appointment_id is None:
            appointment_id = request.values.get("appointment_id", type=int)
        if appointment_id is not None:
            appointment = m.Appointment.query.filter_by(id=appointment_id).first()
            if appointment is None or (
                patient_id is not None and appointment.patient_id != patient_id
            ):
                abort(403)
        linked_order_id = request.values.get("linked_order_id", type=int)
        if linked_order_id is not None:
            linked_order = m.Order.query.filter_by(id=linked_order_id).first()
            if linked_order is None or (
                patient_id is not None and linked_order.patient_id != patient_id
            ):
                abort(403)
        if endpoint == "pacs_exam_link_create":
            for key in ("primary_order_id", "secondary_order_id"):
                candidate_id = request.values.get(key, type=int)
                if candidate_id is not None and m.Order.query.filter_by(
                    id=candidate_id
                ).first() is None:
                    abort(403)
        if endpoint == "pacs_exam_link_remove":
            link_id = (request.view_args or {}).get("link_id")
            if link_id is not None and m.PacsExamLink.query.filter_by(
                id=link_id
            ).first() is None:
                abort(403)
        if endpoint in ("pacs_transfer_retry", "pacs_transfer_cancel"):
            job_id = (request.view_args or {}).get("job_id")
            if job_id is not None and m.PacsTransferJob.query.filter_by(
                id=job_id
            ).first() is None:
                abort(403)
        if endpoint in ("pacs_case_send", "pacs_destination_echo"):
            destination_id = (request.view_args or {}).get("destination_id")
            if destination_id is None:
                destination_id = request.values.get("destination_id", type=int)
            if destination_id is not None and m.DicomDestination.query.filter_by(
                id=destination_id
            ).first() is None:
                abort(403)
        for key, model in (
            ("attachment_id", m.Attachment),
            ("alert_id", m.PatientAlert),
            ("document_id", m.PatientDocument),
            ("prior_id", m.ExternalPriorStudy),
        ):
            object_id = (request.view_args or {}).get(key)
            if object_id is not None and model.query.filter_by(id=object_id).first() is None:
                abort(403)

    def restrict_branch_scoped_queries(state):
        if not has_request_context() or not hasattr(g, "rb_branch_scope"):
            return
        if current_app._get_current_object() is not m.app or not state.is_select or not state.is_orm_statement:
            return
        allowed = g.rb_branch_scope
        order_ids = select(m.Order.id).where(m.Order.branch_id.in_(allowed))
        appointment_ids = select(m.Appointment.id).where(
            m.Appointment.branch_id.in_(allowed)
        )
        warehouse_ids = select(m.Warehouse.id).where(
            m.Warehouse.branch_id.in_(allowed)
        )
        patient_ids = select(m.Order.patient_id).where(
            m.Order.branch_id.in_(allowed)
        ).union(
            select(m.Appointment.patient_id).where(
                m.Appointment.branch_id.in_(allowed)
            )
        )
        intake_user_ids = select(m.User.id).where(m.User.branch_id.in_(allowed))
        intake_ids = select(m.SmartIntakeSession.id).where(
            m.or_(
                m.SmartIntakeSession.created_by.in_(intake_user_ids),
                m.SmartIntakeSession.patient_id.in_(patient_ids),
                m.SmartIntakeSession.matched_patient_id.in_(patient_ids),
            )
        )
        options = [
            with_loader_criteria(
                m.Order, m.Order.branch_id.in_(allowed), include_aliases=True
            ),
            with_loader_criteria(
                m.Branch, m.Branch.id.in_(allowed), include_aliases=True
            ),
            with_loader_criteria(
                m.Patient, m.Patient.id.in_(patient_ids), include_aliases=True
            ),
            with_loader_criteria(
                m.Appointment,
                m.Appointment.branch_id.in_(allowed),
                include_aliases=True,
            ),
            with_loader_criteria(
                m.SmartIntakeSession,
                m.or_(
                    m.SmartIntakeSession.created_by.in_(intake_user_ids),
                    m.SmartIntakeSession.patient_id.in_(patient_ids),
                    m.SmartIntakeSession.matched_patient_id.in_(patient_ids),
                ),
                include_aliases=True,
            ),
            with_loader_criteria(
                m.SmartIntakeDocument,
                m.SmartIntakeDocument.intake_id.in_(intake_ids),
                include_aliases=True,
            ),
            with_loader_criteria(
                m.SmartIntakeFieldReview,
                m.SmartIntakeFieldReview.intake_id.in_(intake_ids),
                include_aliases=True,
            ),
        ]
        assignment_monitor_endpoints = {
            "admin_assignment_monitor", "coordinator_assignments",
        }
        if request.endpoint in (
            "executive_analytics", "advanced_search", "financial_entries"
        ) or request.endpoint in assignment_monitor_endpoints:
            options.append(
                with_loader_criteria(
                    m.User, m.User.branch_id.in_(allowed), include_aliases=True
                )
            )
        if request.endpoint in assignment_monitor_endpoints:
            visible_users = select(m.User.id).where(m.User.branch_id.in_(allowed))
            options.extend((
                with_loader_criteria(
                    m.DoctorAssignmentProfile,
                    m.DoctorAssignmentProfile.user_id.in_(visible_users),
                    include_aliases=True,
                ),
                with_loader_criteria(
                    m.DoctorAvailabilityState,
                    m.DoctorAvailabilityState.user_id.in_(visible_users),
                    include_aliases=True,
                ),
            ))
        if request.endpoint in {
            "admin_users", "admin_user_toggle", "admin_user_edit",
            "admin_user_reset_password", "user_clinical_scope",
        }:
            options.append(
                with_loader_criteria(
                    m.User, m.User.branch_id.in_(allowed), include_aliases=True
                )
            )
        if request.endpoint == "user_clinical_scope":
            options.append(
                with_loader_criteria(
                    m.Device, m.Device.branch_id.in_(allowed), include_aliases=True
                )
            )
        if request.endpoint in (
            "executive_analytics", "financial_center",
            "financial_center_export", "financial_entries",
        ):
            options.append(
                with_loader_criteria(
                    m.Device, m.Device.branch_id.in_(allowed), include_aliases=True
                )
            )
        if request.endpoint in ("command_center_snapshot", "command_center_events"):
            from sqlalchemy import String, cast
            order_ids_text = select(cast(m.Order.id, String)).where(
                m.Order.branch_id.in_(allowed)
            )
            options.append(
                with_loader_criteria(
                    m.EventOutbox,
                    m.and_(
                        m.EventOutbox.entity_type == "order",
                        m.EventOutbox.entity_id.in_(order_ids_text),
                    ),
                    include_aliases=True,
                )
            )
            if request.endpoint == "command_center_events":
                options.append(
                    with_loader_criteria(
                        m.AuditLog,
                        m.and_(
                            m.AuditLog.entity == "order",
                            m.AuditLog.entity_id.in_(order_ids_text),
                        ),
                        include_aliases=True,
                    )
                )
        for mapper in m.db.Model.registry.mappers:
            model = mapper.class_
            if model in (
                m.Order, m.Branch, m.Patient, m.Appointment,
                m.SmartIntakeSession, m.SmartIntakeDocument,
                m.SmartIntakeFieldReview,
            ):
                continue
            relations = []
            if "order_id" in mapper.columns:
                order_relation = model.order_id.in_(order_ids)
                fallback = []
                if "appointment_id" in mapper.columns:
                    fallback.append(model.appointment_id.in_(appointment_ids))
                if "patient_id" in mapper.columns:
                    fallback.append(model.patient_id.in_(patient_ids))
                if "branch_id" in mapper.columns:
                    fallback.append(model.branch_id.in_(allowed))
                if fallback:
                    from sqlalchemy import and_, or_
                    order_relation = or_(
                        order_relation,
                        and_(model.order_id.is_(None), or_(*fallback)),
                    )
                relations.append(order_relation)
            elif "appointment_id" in mapper.columns:
                relations.append(model.appointment_id.in_(appointment_ids))
            elif "patient_id" in mapper.columns:
                relations.append(model.patient_id.in_(patient_ids))
            elif "branch_id" in mapper.columns:
                if (
                    model is m.DicomDestination
                    and request.endpoint in {
                        "pacs_case_actions", "pacs_case_send", "pacs_transfer_retry",
                        "pacs_transfer_cancel", "pacs_destination_echo", "pacs_archive_dashboard",
                    }
                ):
                    from sqlalchemy import or_
                    relations.append(or_(model.branch_id.in_(allowed), model.branch_id.is_(None)))
                else:
                    relations.append(model.branch_id.in_(allowed))
            if "warehouse_id" in mapper.columns:
                relations.append(model.warehouse_id.in_(warehouse_ids))
            if relations:
                from sqlalchemy import and_
                options.append(
                    with_loader_criteria(
                        model, and_(*relations), include_aliases=True
                    )
                )
        state.statement = state.statement.options(*options)

    m.app.before_request(guard_request)
    @m.app.teardown_request
    def clear_branch_scope(error=None):
        g.pop("rb_branch_scope", None)

    event.listen(Session, "do_orm_execute", restrict_branch_scoped_queries)
    m.app.extensions.setdefault("radbridge_orm_listeners", []).append(
        (Session, "do_orm_execute", restrict_branch_scoped_queries)
    )
