# Static route inventory

Generated from the reviewed source checkpoint. Constant route decorators only; excludes dynamic add_url_rule/blueprint path rewriting and cannot prove authentication, CSRF or runtime reachability. An absent explicit require_perm decorator does not mean an endpoint is public: inspect other decorators and its body. Links point to declarations.

| Method | Declared path | Function/source | Explicit permission |
|---|---|---|---|
| GET | `/admin/access-review` | [admin_access_review](../../ris/app.py#L25326) | inspect source |
| GET | `/admin/assignment-monitor` | [admin_assignment_monitor](../../ris/app.py#L7738) | inspect source |
| GET | `/admin/assignment-strategies/<int:strategy_id>/history` | [admin_assignment_strategy_history](../../ris/app.py#L19945) | inspect source |
| GET | `/admin/booking-control-center` | [admin_booking_control_center](../../ris/app.py#L14845) | inspect source |
| GET | `/admin/cancellation-center` | [admin_cancellation_center](../../ris/app.py#L25259) | inspect source |
| GET | `/admin/cancellation-center/order/<int:order_id>/preview` | [granular_delete_order_preview](../../ris/app.py#L23130) | inspect source |
| GET | `/admin/cancellation-center/patient/<int:patient_id>/preview` | [granular_delete_patient_preview](../../ris/app.py#L23498) | inspect source |
| GET | `/admin/cancellation-center/preview` | [granular_delete_preview_home](../../ris/app.py#L23120) | inspect source |
| GET | `/admin/data-deletion-center` | [admin_data_deletion_center](../../ris/app.py#L25246) | inspect source |
| GET | `/admin/data-management` | [admin_data_management](../../ris/app.py#L30480) | inspect source |
| GET | `/admin/dicom-connections` | [dicom_connections_page](../../ris/app.py#L20449) | inspect source |
| GET | `/admin/insurance-approvals/<int:portal_id>` | [admin_insurance_approval_edit](../../ris/app.py#L6123) | inspect source |
| GET | `/admin/pacs/discovery` | [pacs_discovery](../../ris/app.py#L31005) | inspect source |
| GET | `/admin/users/export.csv` | [export](../../ris/user_csv_transfer.py#L174) | users.view |
| GET | `/admin/users/template.csv` | [template](../../ris/user_csv_transfer.py#L189) | users.view |
| GET | `/analytics` | [analytics](../../ris/analytics_reference_routes.py#L10) | inspect source |
| GET | `/analytics/executive` | [executive_analytics](../../ris/app.py#L30660) | inspect source |
| GET | `/analytics/export.csv` | [analytics_export_csv](../../ris/analytics_reference_routes.py#L14) | inspect source |
| GET | `/api/assignment/offers/pending` | [api_assignment_offer_pending](../../ris/app.py#L31712) | inspect source |
| GET | `/api/booking/procedures` | [api_booking_procedures](../../ris/scheduling_reference_routes.py#L22) | inspect source |
| GET | `/api/booking/smart-availability` | [api_smart_booking_availability](../../ris/app.py#L14483) | inspect source |
| GET | `/api/command-center/case/<int:order_id>/graph-v3` | [api_command_center_case_graph_v3](../../ris/app.py#L16481) | inspect source |
| GET | `/api/command-center/control` | [api_command_center_control_get](../../ris/app.py#L17110) | inspect source |
| GET | `/api/command-center/events/stream` | [command_center_events_stream](../../ris/app.py#L17741) | inspect source |
| GET | `/api/command-center/resources` | [api_command_center_resources](../../ris/app.py#L17667) | inspect source |
| GET | `/api/doctor/workspace` | [doctor_workspace_data](../../ris/app.py#L7471) | inspect source |
| GET | `/api/ohif/onlyoffice/health` | [api_ohif_onlyoffice_health](../../ris/operational_health_routes.py#L14) | inspect source |
| GET | `/api/ohif/report/<int:order_id>` | [api_ohif_report_get](../../ris/app.py#L31931) | inspect source |
| GET | `/api/ohif/report/<int:order_id>/dicom-download` | [download](../../ris/dicom_export_routes.py#L87) | inspect source |
| GET | `/api/ohif/report/<int:order_id>/onlyoffice/config` | [api_ohif_onlyoffice_config](../../ris/app.py#L33989) | inspect source |
| GET | `/api/ohif/report/<int:order_id>/onlyoffice/document` | [api_ohif_onlyoffice_document](../../ris/app.py#L34431) | inspect source |
| GET | `/api/ohif/report/<int:order_id>/onlyoffice/template-options` | [onlyoffice_template_options](../../ris/report_template_routes.py#L164) | inspect source |
| GET | `/api/ohif/report/<int:order_id>/word` | [api_ohif_report_word](../../ris/app.py#L31995) | inspect source |
| GET | `/api/ohif/reporting-agent/download` | [api_ohif_reporting_agent_download](../../ris/reporting_support_routes.py#L34) | inspect source |
| GET | `/api/ohif/reporting/health` | [api_ohif_reporting_health](../../ris/reporting_support_routes.py#L38) | inspect source |
| GET | `/api/ops/health` | [api_ops_health](../../ris/operational_health_routes.py#L10) | inspect source |
| GET | `/api/pricing` | [api_pricing](../../ris/scheduling_reference_routes.py#L14) | inspect source |
| GET | `/api/public-call/config` | [public_call_config](../../ris/app.py#L36864) | inspect source |
| GET | `/api/public-chat/<token>/messages` | [public_chat_messages](../../ris/app.py#L37270) | inspect source |
| GET | `/api/registration/procedures` | [api_registration_procedures](../../ris/scheduling_reference_routes.py#L10) | inspect source |
| GET | `/api/registration/visits` | [api_registration_visits](../../ris/app.py#L7710) | inspect source |
| GET | `/api/report-templates/conversion-source/<source_id>` | [report_template_conversion_source](../../ris/report_template_conversion.py#L41) | inspect source |
| GET | `/api/reporting/health` | [api_reporting_health](../../ris/reporting_support_routes.py#L18) | inspect source |
| GET | `/api/slots` | [api_slots](../../ris/scheduling_reference_routes.py#L18) | inspect source |
| GET | `/api/staff/chat/<int:request_id>/messages` | [staff_chat_messages](../../ris/staff_communications_reference_routes.py#L14) | inspect source |
| GET | `/api/staff/communications/<int:request_id>/attachments` | [staff_contact_attachments](../../ris/staff_communications_reference_routes.py#L21) | inspect source |
| GET | `/api/staff/communications/queue` | [staff_communications_queue](../../ris/staff_communications_reference_routes.py#L10) | inspect source |
| GET | `/api/storage/resolve` | [api_storage_resolve](../../ris/storage_routes.py#L10) | inspect source |
| GET | `/api/telephony/directory` | [telephony_directory](../../ris/telephony_reference_routes.py#L14) | inspect source |
| GET | `/api/telephony/me` | [telephony_me](../../ris/telephony_reference_routes.py#L10) | inspect source |
| GET | `/api/voice/appointments` | [appointment_query](../../ris/voice_ai.py#L194) | inspect source |
| GET | `/api/voice/branches` | [voice_api_branches](../../ris/voice_scheduling_reference_routes.py#L10) | inspect source |
| GET | `/api/voice/health` | [health](../../ris/voice_ai.py#L65) | inspect source |
| GET | `/api/voice/inquiry` | [voice_api_inquiry](../../ris/app.py#L35792) | inspect source |
| GET | `/api/voice/patient/search` | [voice_api_patient_search](../../ris/app.py#L35662) | inspect source |
| GET | `/api/voice/procedures` | [voice_api_procedures](../../ris/voice_scheduling_reference_routes.py#L14) | inspect source |
| GET | `/api/voice/procedures/search` | [procedure_search](../../ris/voice_ai.py#L158) | inspect source |
| GET | `/api/voice/slots` | [voice_api_slots](../../ris/voice_scheduling_reference_routes.py#L18) | inspect source |
| GET | `/approvals` | [insurance_approvals_dashboard](../../ris/app.py#L6204) | inspect source |
| GET | `/assignment/offers` | [my_assignment_offers](../../ris/app.py#L26788) | inspect source |
| GET | `/assignment/open-pool` | [open_pool_cases](../../ris/app.py#L26669) | inspect source |
| GET | `/call` | [public_click_to_call](../../ris/app.py#L36857) | inspect source |
| GET | `/chat` | [chat_home](../../ris/app.py#L15090) | inspect source |
| GET | `/chat/case/<int:order_id>` | [chat_case](../../ris/app.py#L15117) | inspect source |
| GET | `/coordinator` | [coordinator_queue](../../ris/app.py#L30808) | inspect source |
| GET | `/coordinator/assignments` | [coordinator_assignments](../../ris/app.py#L7744) | inspect source |
| GET | `/coordinator/physician-final-counts` | [physician_final_counts](../../ris/physician_final_counts.py#L98) | inspect source |
| GET | `/coordinator/physician-reports` | [physician_report_workload](../../ris/physician_report_workload.py#L94) | inspect source |
| GET | `/coordinator/report-corrections` | [coordinator_report_corrections](../../ris/report_revisions.py#L285) | inspect source |
| GET | `/correction-center` | [correction_center](../../ris/app.py#L24119) | inspect source |
| GET | `/correction-center/executions` | [correction_execution_queue](../../ris/app.py#L24293) | inspect source |
| GET | `/correction-center/requests` | [correction_request_queue](../../ris/app.py#L25162) | inspect source |
| GET | `/correction-center/requests/<int:request_id>/demographics` | [patient_demographics_correction_view](../../ris/app.py#L24159) | inspect source |
| GET | `/doctor/cases/<int:order_id>/open` | [doctor_workspace_open](../../ris/app.py#L7651) | inspect source |
| GET | `/doctor/cases/<int:order_id>/viewers` | [choose](../../ris/viewer_choice.py#L171) | reports.view |
| GET | `/doctor/report-corrections` | [doctor_report_corrections](../../ris/report_revisions.py#L311) | inspect source |
| GET | `/doctor/templates/sample.docx` | [report_template_sample](../../ris/report_template_routes.py#L102) | reports.edit |
| GET | `/doctor/viewers/radiant/setup.zip` | [radiant_setup](../../ris/viewer_choice.py#L198) | reports.view |
| GET | `/documents/<int:document_id>/review` | [document_review](../../ris/app.py#L15190) | inspect source |
| GET | `/finance/discount-approvals` | [discount_approval_queue](../../ris/app.py#L30039) | inspect source |
| GET | `/finance/doctor-earnings` | [doctor_earnings_report](../../ris/app.py#L30072) | inspect source |
| GET | `/intake/smart/<int:intake_id>` | [smart_intake_workspace](../../ris/app.py#L28889) | inspect source |
| GET | `/intake/smart/<int:intake_id>/document/<int:doc_id>/file` | [smart_intake_document_file](../../ris/app.py#L28929) | inspect source |
| GET | `/inventory/consumption-report` | [inventory_consumption_report](../../ris/app.py#L30409) | inspect source |
| GET | `/inventory/ledger` | [inventory_ledger](../../ris/app.py#L30396) | inspect source |
| GET | `/inventory/transfers/<int:transfer_id>` | [inventory_transfer_detail](../../ris/app.py#L30256) | inspect source |
| GET | `/management` | [management_dashboard](../../ris/app.py#L29900) | inspect source |
| GET | `/management/referrals` | [referral_analytics](../../ris/app.py#L29912) | inspect source |
| GET | `/my/quick-actions` | [my_quick_actions](../../ris/app.py#L26002) | inspect source |
| GET | `/notifications` | [notification_center](../../ris/app.py#L28543) | inspect source |
| GET | `/operations/assignment-dashboard` | [assignment_dashboard](../../ris/app.py#L28808) | inspect source |
| GET | `/operations/assignment-report.csv` | [assignment_report_csv](../../ris/app.py#L28857) | inspect source |
| GET | `/operations/assignment-reports` | [assignment_reports](../../ris/app.py#L28802) | inspect source |
| GET | `/operations/booking-board` | [operations_booking_board](../../ris/app.py#L15066) | inspect source |
| GET | `/operations/case-control-center` | [case_operations_control_center](../../ris/app.py#L26946) | inspect source |
| GET | `/operations/case-exceptions` | [case_exception_resolver](../../ris/app.py#L26980) | inspect source |
| GET | `/operations/case-readiness` | [case_readiness_dashboard](../../ris/app.py#L26938) | inspect source |
| GET | `/operations/command-center` | [workflow_command_center](../../ris/app.py#L30676) | inspect source |
| GET | `/operations/dashboard` | [operations_dashboard](../../ris/app.py#L15074) | inspect source |
| GET | `/operations/escalations` | [escalation_board](../../ris/app.py#L28557) | inspect source |
| GET | `/operations/journey` | [operations_journey](../../ris/app.py#L15042) | inspect source |
| GET | `/operations/tat` | [tat_dashboard](../../ris/app.py#L28536) | inspect source |
| GET | `/orders/<int:order_id>/actions` | [order_actions](../../ris/app.py#L28768) | inspect source |
| GET | `/orders/<int:order_id>/attachments` | [order_attachments](../../ris/app.py#L15897) | inspect source |
| GET | `/orders/<int:order_id>/consumables/available-stock` | [order_consumables_available_stock](../../ris/app.py#L30329) | inspect source |
| GET | `/orders/<int:order_id>/label-print` | [order_label_print](../../ris/app.py#L28774) | inspect source |
| GET | `/orders/<int:order_id>/print-center` | [order_print_center](../../ris/app.py#L29737) | inspect source |
| GET | `/orders/<int:order_id>/study-thumbnail` | [order_study_thumbnail](../../ris/app.py#L6861) | inspect source |
| GET | `/pacs/actions/<int:order_id>` | [pacs_case_actions](../../ris/app.py#L30736) | inspect source |
| GET | `/pacs/archive` | [pacs_archive_dashboard](../../ris/app.py#L30801) | inspect source |
| GET | `/pacs/reconciliation/<study_id>/preview` | [pacs_reconciliation_preview](../../ris/app.py#L15996) | inspect source |
| GET | `/pacs/reconciliation/audit` | [pacs_reconciliation_audit](../../ris/app.py#L16037) | inspect source |
| GET | `/pacs/reconciliation/example` | [pacs_reconciliation_example](../../ris/app.py#L16049) | inspect source |
| GET | `/pacs/unregistered` | [pacs_unregistered_cases](../../ris/app.py#L30682) | inspect source |
| GET | `/patients/<int:patient_id>/timeline` | [patient_timeline](../../ris/app.py#L15184) | inspect source |
| GET | `/radiant-images/<int:order_id>/<token>/study.zip` | [radiant_archive](../../ris/viewer_choice.py#L213) | inspect source |
| GET | `/radiotherapy` | [rt_worklist](../../ris/radiotherapy.py#L199) | rt.view |
| GET | `/radiotherapy/<int:course_id>` | [rt_course_detail](../../ris/radiotherapy.py#L222) | rt.view |
| GET | `/receipts/<int:receipt_id>/studio-print` | [receipt_studio_print](../../ris/app.py#L25800) | inspect source |
| GET | `/report-revisions/<int:revision_id>` | [report_revision_view](../../ris/report_revision_editor.py#L260) | inspect source |
| GET | `/report-revisions/<int:revision_id>/config` | [report_revision_config](../../ris/report_revision_editor.py#L285) | inspect source |
| GET | `/report-revisions/<int:revision_id>/document` | [report_revision_document](../../ris/report_revision_editor.py#L316) | inspect source |
| GET | `/report-revisions/<int:revision_id>/download` | [report_revision_download](../../ris/report_revision_editor.py#L426) | inspect source |
| GET | `/report-revisions/<int:revision_id>/original` | [report_revision_original](../../ris/report_revision_editor.py#L436) | inspect source |
| GET | `/report-revisions/<int:revision_id>/state` | [report_revision_state](../../ris/report_revision_editor.py#L419) | inspect source |
| GET | `/reporting-agent/download` | [reporting_agent_download](../../ris/reporting_support_routes.py#L14) | inspect source |
| GET | `/reports-portal` | [reports_portal](../../ris/app.py#L27789) | inspect source |
| GET | `/reports-portal.csv` | [reports_portal_csv](../../ris/app.py#L28067) | inspect source |
| GET | `/reports-portal/<int:order_id>/docx` | [report_portal_download_docx](../../ris/app.py#L27631) | inspect source |
| GET | `/reports-portal/<int:order_id>/download` | [report_portal_download](../../ris/app.py#L27543) | inspect source |
| GET | `/reports-portal/<int:order_id>/pdf` | [report_portal_download_pdf](../../ris/app.py#L27610) | inspect source |
| GET | `/reports/<int:order_id>/ai-assistant` | [ai_report_assistant](../../ris/app.py#L25898) | inspect source |
| GET | `/reports/<int:order_id>/imaging-ai` | [imaging_ai_workspace](../../ris/app.py#L26151) | inspect source |
| GET | `/reports/<int:order_id>/return-case` | [return_case_form](../../ris/app.py#L27346) | inspect source |
| GET | `/reports/<int:order_id>/word-template/<int:template_id>` | [report_word_from_doctor_template](../../ris/app.py#L25824) | inspect source |
| GET | `/returned-cases` | [returned_cases_queue](../../ris/app.py#L27355) | inspect source |
| GET | `/saved-views/<page_key>/<int:view_id>/apply` | [saved_view_apply](../../ris/app.py#L28669) | inspect source |
| GET | `/search` | [universal_search](../../ris/app.py#L26008) | inspect source |
| GET | `/search/advanced` | [advanced_search](../../ris/app.py#L28565) | inspect source |
| GET | `/search/advanced/saved/<int:filter_id>` | [advanced_search_apply_saved](../../ris/app.py#L28761) | inspect source |
| GET | `/staff/public-attachment/<int:attachment_id>` | [staff_public_attachment_view](../../ris/app.py#L38392) | inspect source |
| GET | `/studio/templates/<int:template_id>/preview` | [studio_template_preview](../../ris/app.py#L25816) | inspect source |
| GET | `/technician/<int:order_id>` | [technician_case_workspace](../../ris/app.py#L6900) | inspect source |
| GET | `/telephony/caller/<int:call_id>` | [telephony_caller](../../ris/app.py#L15234) | inspect source |
| GET | `/telephony/calls` | [telephony_calls](../../ris/app.py#L15228) | inspect source |
| GET | `/voice-intake/<int:intake_id>/audio` | [voice_intake_audio](../../ris/app.py#L36299) | inspect source |
| GET | `/voice-intake/<int:intake_id>/caller-history` | [voice_intake_caller_history](../../ris/app.py#L36585) | inspect source |
| GET | `/voice-intake/review` | [voice_intake_review](../../ris/app.py#L36245) | inspect source |
| GET | `/weasis-images/<int:order_id>/<token>/instances/<instance_id>.dcm` | [instance](../../ris/viewer_choice.py#L290) | inspect source |
| GET | `/weasis-images/<int:order_id>/<token>/manifest.xml` | [manifest](../../ris/viewer_choice.py#L254) | inspect source |
| GET | `/word-addin/manifest.xml` | [word_addin_manifest](../../ris/reporting_support_routes.py#L26) | inspect source |
| GET | `/word-addin/taskpane` | [word_addin_taskpane](../../ris/reporting_support_routes.py#L22) | inspect source |
| GET | `/word-addin/taskpane.js` | [word_addin_taskpane_js](../../ris/reporting_support_routes.py#L30) | inspect source |
| GET (implicit) | `/` | [dashboard](../../ris/app.py#L5392) | inspect source |
| GET (implicit) | `/accounting/financial-center` | [financial_center](../../ris/app.py#L18703) | inspect source |
| GET (implicit) | `/accounting/financial-center/export/<fmt>` | [financial_center_export](../../ris/app.py#L18714) | inspect source |
| GET (implicit) | `/accounting/receivables` | [receivables](../../ris/app.py#L18759) | inspect source |
| GET (implicit) | `/accounting/receivables.csv` | [receivables_csv](../../ris/app.py#L18777) | inspect source |
| GET (implicit) | `/accounting/reports` | [accounting_reports](../../ris/app.py#L18941) | inspect source |
| GET (implicit) | `/accounting/reports.csv` | [accounting_reports_csv](../../ris/app.py#L18978) | inspect source |
| GET (implicit) | `/admin` | [admin_home](../../ris/app.py#L20294) | inspect source |
| GET (implicit) | `/admin/` | [admin_home](../../ris/app.py#L20294) | inspect source |
| GET (implicit) | `/admin/audit` | [admin_audit](../../ris/app.py#L20782) | inspect source |
| GET (implicit) | `/admin/diagnostics` | [admin_diagnostics](../../ris/app.py#L18991) | inspect source |
| GET (implicit) | `/admin/export/<entity>.csv` | [admin_export_entity](../../ris/app.py#L15463) | inspect source |
| GET (implicit) | `/admin/inventory/export/<fmt>` | [admin_inventory_export](../../ris/app.py#L20636) | inspect source |
| GET (implicit) | `/admin/inventory/import-template` | [admin_inventory_import_template](../../ris/app.py#L20655) | inspect source |
| GET (implicit) | `/admin/inventory/movements` | [admin_inventory_movements](../../ris/app.py#L20712) | inspect source |
| GET (implicit) | `/admin/ivr` | [admin_ivr](../../ris/app.py#L38519) | inspect source |
| GET (implicit) | `/admin/notifications` | [admin_notifications](../../ris/app.py#L6838) | inspect source |
| GET (implicit) | `/admin/qa-control` | [admin_qa_control](../../ris/app.py#L26277) | inspect source |
| GET (implicit) | `/admin/security` | [admin_security](../../ris/security_dashboard.py#L176) | inspect source |
| GET (implicit) | `/api/command-center/events` | [command_center_events](../../ris/app.py#L17896) | inspect source |
| GET (implicit) | `/api/command-center/snapshot` | [command_center_snapshot](../../ris/app.py#L18505) | inspect source |
| GET (implicit) | `/api/reporting/cases/<accession>` | [api_reporting_case](../../ris/app.py#L8731) | inspect source |
| GET (implicit) | `/api/telephony/credentials` | [telephony_credentials](../../ris/app.py#L36779) | inspect source |
| GET (implicit) | `/assignment/unassigned` | [unassigned_cases](../../ris/app.py#L20151) | inspect source |
| GET (implicit) | `/attachments/<int:attachment_id>` | [attachment_download](../../ris/app.py#L15865) | inspect source |
| GET (implicit) | `/attachments/<int:attachment_id>/preview` | [attachment_preview](../../ris/app.py#L15872) | inspect source |
| GET (implicit) | `/cashier` | [cashier_workstation](../../ris/app.py#L18878) | inspect source |
| GET (implicit) | `/communications` | [communications_dashboard](../../ris/app.py#L37554) | inspect source |
| GET (implicit) | `/company/logo` | [company_logo](../../ris/app.py#L15972) | inspect source |
| GET (implicit) | `/doctor` | [doctor_workspace](../../ris/app.py#L7458) | inspect source |
| GET (implicit) | `/lang/<code>` | [set_language](../../ris/app.py#L5288) | inspect source |
| GET (implicit) | `/logout` | [logout](../../ris/app.py#L5387) | inspect source |
| GET (implicit) | `/nursing` | [nursing_worklist](../../ris/app.py#L6617) | inspect source |
| GET (implicit) | `/operations/live-command-center` | [live_command_center](../../ris/app.py#L17883) | inspect source |
| GET (implicit) | `/orders` | [orders](../../ris/app.py#L5549) | inspect source |
| GET (implicit) | `/orders/<int:order_id>` | [order_detail](../../ris/app.py#L6274) | inspect source |
| GET (implicit) | `/orders/<int:order_id>/sticker` | [order_sticker](../../ris/app.py#L15910) | inspect source |
| GET (implicit) | `/orders/<int:order_id>/sticker/preview` | [order_sticker_preview](../../ris/app.py#L15935) | inspect source |
| GET (implicit) | `/pacs` | [pacs_home](../../ris/app.py#L7382) | inspect source |
| GET (implicit) | `/pacs/` | [pacs_home](../../ris/app.py#L7382) | inspect source |
| GET (implicit) | `/pacs/reconciliation` | [pacs_reconciliation](../../ris/app.py#L16064) | inspect source |
| GET (implicit) | `/pacs/tracking` | [pacs_tracking](../../ris/app.py#L7393) | inspect source |
| GET (implicit) | `/patients` | [patients](../../ris/app.py#L5466) | inspect source |
| GET (implicit) | `/portal/<token>/report` | [patient_portal_report](../../ris/app.py#L6825) | inspect source |
| GET (implicit) | `/receipts/<int:receipt_id>` | [receipt_view](../../ris/app.py#L18832) | inspect source |
| GET (implicit) | `/reports` | [reports](../../ris/app.py#L7853) | inspect source |
| GET (implicit) | `/reports/<int:order_id>/source` | [report_source](../../ris/app.py#L15806) | inspect source |
| GET (implicit) | `/reports/<int:order_id>/word` | [word_template](../../ris/app.py#L8512) | inspect source |
| GET (implicit) | `/schedule/calendar` | [schedule_calendar](../../ris/app.py#L13534) | inspect source |
| GET (implicit) | `/schedule/v2` | [schedule_v2](../../ris/app.py#L14378) | inspect source |
| GET (implicit) | `/schedule/v2/book` | [schedule_v2_book_form](../../ris/app.py#L14383) | inspect source |
| GET (implicit) | `/security/country-gate` | [security_country_gate](../../ris/security_dashboard.py#L171) | inspect source |
| GET (implicit) | `/studio` | [studio_home](../../ris/app.py#L25753) | inspect source |
| GET (implicit) | `/technician` | [technician_worklist](../../ris/app.py#L7075) | inspect source |
| GET (implicit) | `/telephony` | [telephony_console](../../ris/app.py#L36724) | inspect source |
| GET,POST | `/accounting/daily-closing` | [daily_closing](../../ris/app.py#L29937) | inspect source |
| GET,POST | `/accounting/entries` | [financial_entries](../../ris/app.py#L18725) | inspect source |
| GET,POST | `/admin/ai-reporting` | [admin_ai_reporting](../../ris/app.py#L25881) | inspect source |
| GET,POST | `/admin/assignment` | [admin_assignment](../../ris/app.py#L19086) | inspect source |
| GET,POST | `/admin/assignment-distribution` | [admin_assignment_distribution](../../ris/app.py#L7756) | inspect source |
| GET,POST | `/admin/assignment-offers` | [admin_assignment_offers](../../ris/app.py#L26582) | inspect source |
| GET,POST | `/admin/assignment-strategies` | [admin_assignment_strategies](../../ris/app.py#L19223) | inspect source |
| GET,POST | `/admin/assignment-strategies/simulate-ui` | [admin_assignment_strategy_simulate_ui](../../ris/app.py#L19790) | inspect source |
| GET,POST | `/admin/assignment-visits` | [admin_assignment_visits](../../ris/app.py#L7660) | inspect source |
| GET,POST | `/admin/booking-availability` | [admin_booking_availability](../../ris/app.py#L14447) | inspect source |
| GET,POST | `/admin/booking-control` | [admin_booking_control](../../ris/app.py#L14915) | inspect source |
| GET,POST | `/admin/branches` | [admin_branches](../../ris/app.py#L25338) | inspect source |
| GET,POST | `/admin/branches/<int:branch_id>/edit` | [admin_branch_edit](../../ris/app.py#L20505) | inspect source |
| GET,POST | `/admin/communications` | [admin_communications](../../ris/app.py#L26046) | inspect source |
| GET,POST | `/admin/company` | [admin_company](../../ris/app.py#L15955) | inspect source |
| GET,POST | `/admin/company-legal` | [admin_company_legal](../../ris/app.py#L25740) | inspect source |
| GET,POST | `/admin/contracts` | [admin_contracts](../../ris/app.py#L20555) | inspect source |
| GET,POST | `/admin/contracts/<int:contract_id>/prices` | [admin_contract_prices](../../ris/app.py#L20566) | inspect source |
| GET,POST | `/admin/demo/reporting` | [admin_reporting_demo](../../ris/app.py#L19075) | inspect source |
| GET,POST | `/admin/device-schedules` | [admin_device_schedules](../../ris/app.py#L20403) | inspect source |
| GET,POST | `/admin/devices` | [admin_devices](../../ris/app.py#L20523) | inspect source |
| GET,POST | `/admin/devices/<int:device_id>` | [admin_device_page](../../ris/app.py#L25353) | inspect source |
| GET,POST | `/admin/dicom-connections/branches/<int:branch_id>` | [dicom_connection_edit](../../ris/app.py#L20468) | inspect source |
| GET,POST | `/admin/dictionary` | [admin_dictionary](../../ris/app.py#L14820) | inspect source |
| GET,POST | `/admin/discount-policies` | [admin_discount_policies](../../ris/app.py#L30002) | inspect source |
| GET,POST | `/admin/doctor-share-rules` | [admin_doctor_share_rules](../../ris/app.py#L29944) | inspect source |
| GET,POST | `/admin/erp` | [admin_erp](../../ris/app.py#L20740) | inspect source |
| GET,POST | `/admin/external-intake` | [admin_external_intake](../../ris/app.py#L31409) | inspect source |
| GET,POST | `/admin/field-rules` | [admin_field_rules](../../ris/app.py#L25698) | inspect source |
| GET,POST | `/admin/imaging-ai` | [admin_imaging_ai](../../ris/app.py#L26131) | inspect source |
| GET,POST | `/admin/import-export` | [admin_import_export](../../ris/app.py#L15392) | inspect source |
| GET,POST | `/admin/insurance-approvals` | [admin_insurance_approvals](../../ris/app.py#L5952) | inspect source |
| GET,POST | `/admin/inventory` | [admin_inventory](../../ris/app.py#L20578) | inspect source |
| GET,POST | `/admin/inventory/batches` | [admin_inventory_batches](../../ris/app.py#L20718) | inspect source |
| GET,POST | `/admin/label-templates` | [admin_label_templates](../../ris/app.py#L28785) | inspect source |
| GET,POST | `/admin/ocr-settings` | [admin_ocr_settings](../../ris/app.py#L29517) | inspect source |
| GET,POST | `/admin/pacs/destinations` | [pacs_destinations](../../ris/app.py#L30695) | inspect source |
| GET,POST | `/admin/pacs/routing` | [pacs_routing_rules](../../ris/app.py#L30720) | inspect source |
| GET,POST | `/admin/printer-profiles` | [admin_printer_profiles](../../ris/app.py#L29705) | inspect source |
| GET,POST | `/admin/procedure-quality-rules` | [admin_procedure_quality_rules](../../ris/app.py#L27261) | inspect source |
| GET,POST | `/admin/procedures` | [admin_procedures](../../ris/app.py#L20544) | inspect source |
| GET,POST | `/admin/procedures/<int:procedure_id>/consumables` | [procedure_consumables](../../ris/app.py#L6783) | inspect source |
| GET,POST | `/admin/procedures/<int:procedure_id>/staff-workflow` | [procedure_staff_workflow](../../ris/procedure_staff_workflow.py#L138) | procedures.view |
| GET,POST | `/admin/referral-commissions` | [admin_referral_commissions](../../ris/app.py#L29926) | inspect source |
| GET,POST | `/admin/referrers` | [admin_referrers](../../ris/app.py#L15255) | inspect source |
| GET,POST | `/admin/registration-defaults` | [admin_registration_defaults](../../ris/app.py#L29774) | inspect source |
| GET,POST | `/admin/report-header` | [report_header_settings](../../ris/report_template_routes.py#L114) | users.manage |
| GET,POST | `/admin/ribbon-designer` | [admin_ribbon_designer](../../ris/app.py#L15016) | inspect source |
| GET,POST | `/admin/roles` | [admin_roles](../../ris/app.py#L25305) | inspect source |
| GET,POST | `/admin/sticker-templates` | [admin_sticker_templates](../../ris/app.py#L15979) | inspect source |
| GET,POST | `/admin/storage-cloud` | [storage_cloud_manager](../../ris/app.py#L30972) | inspect source |
| GET,POST | `/admin/storage-dr` | [storage_dr_manager](../../ris/app.py#L30892) | inspect source |
| GET,POST | `/admin/tat-policies` | [admin_tat_policies](../../ris/app.py#L28261) | inspect source |
| GET,POST | `/admin/users` | [admin_users](../../ris/app.py#L20324) | inspect source |
| GET,POST | `/admin/users/<int:user_id>/clinical-scope` | [user_clinical_scope](../../ris/clinical_scope.py#L151) | users.manage |
| GET,POST | `/admin/users/import` | [upload](../../ris/user_csv_transfer.py#L194) | inspect source |
| GET,POST | `/api/ohif/report/<int:order_id>/preferences` | [api_ohif_reporting_preferences](../../ris/app.py#L33897) | inspect source |
| GET,POST | `/appointments` | [appointments](../../ris/app.py#L14148) | inspect source |
| GET,POST | `/appointments/<int:appointment_id>/edit` | [appointment_edit](../../ris/app.py#L14258) | inspect source |
| GET,POST | `/case/<int:order_id>/report-corrections` | [report_correction_case](../../ris/report_revisions.py#L267) | inspect source |
| GET,POST | `/chat/<int:thread_id>` | [chat_thread](../../ris/app.py#L15122) | inspect source |
| GET,POST | `/coordinator/manual-assignment` | [coordinator_manual_assignment](../../ris/coordinator_bulk_assignment.py#L213) | inspect source |
| GET,POST | `/correction-center/orders/<int:order_id>/demographics` | [patient_demographics_correction](../../ris/app.py#L24141) | inspect source |
| GET,POST | `/doctor/case/<int:order_id>/workspace` | [doctor_clinical_workspace](../../ris/app.py#L29599) | inspect source |
| GET,POST | `/doctor/templates` | [doctor_templates](../../ris/app.py#L25783) | inspect source |
| GET,POST | `/finance/replacement-settlements` | [replacement_settlements](../../ris/replacement_settlements.py#L284) | inspect source |
| GET,POST | `/intake/smart` | [smart_intake_start](../../ris/app.py#L28878) | inspect source |
| GET,POST | `/inventory/items` | [inventory_items](../../ris/app.py#L30122) | inspect source |
| GET,POST | `/inventory/procedure-defaults` | [inventory_procedure_defaults](../../ris/app.py#L30212) | inspect source |
| GET,POST | `/inventory/stock` | [inventory_stock](../../ris/app.py#L30156) | inspect source |
| GET,POST | `/inventory/stock-policies` | [inventory_stock_policies](../../ris/app.py#L30194) | inspect source |
| GET,POST | `/inventory/transfers` | [inventory_transfers](../../ris/app.py#L30229) | inspect source |
| GET,POST | `/inventory/warehouses` | [inventory_warehouses](../../ris/app.py#L30103) | inspect source |
| GET,POST | `/login` | [login](../../ris/app.py#L5369) | inspect source |
| GET,POST | `/my/profile` | [my_profile](../../ris/app.py#L14713) | inspect source |
| GET,POST | `/my/registration-defaults` | [my_registration_defaults](../../ris/app.py#L29748) | inspect source |
| GET,POST | `/my/ribbon` | [my_ribbon](../../ris/app.py#L14989) | inspect source |
| GET,POST | `/nursing/<int:order_id>` | [nursing_case](../../ris/app.py#L6705) | inspect source |
| GET,POST | `/orders/<int:order_id>/assign` | [assign_case](../../ris/app.py#L20063) | inspect source |
| GET,POST | `/orders/<int:order_id>/clinical-notes` | [order_clinical_notes](../../ris/app.py#L14699) | inspect source |
| GET,POST | `/orders/<int:order_id>/consumables` | [order_consumables](../../ris/app.py#L30342) | inspect source |
| GET,POST | `/orders/new` | [new_order](../../ris/app.py#L5558) | inspect source |
| GET,POST | `/patients/<int:patient_id>/alerts` | [patient_alerts](../../ris/app.py#L25720) | inspect source |
| GET,POST | `/patients/<int:patient_id>/communications` | [patient_communications](../../ris/app.py#L26088) | inspect source |
| GET,POST | `/patients/<int:patient_id>/documents` | [patient_documents](../../ris/app.py#L15146) | inspect source |
| GET,POST | `/patients/<int:patient_id>/external-priors` | [patient_external_priors](../../ris/app.py#L25958) | inspect source |
| GET,POST | `/patients/new` | [new_patient](../../ris/app.py#L5502) | inspect source |
| GET,POST | `/portal/<token>` | [patient_portal](../../ris/app.py#L6805) | inspect source |
| GET,POST | `/profile/password` | [change_password](../../ris/app.py#L5934) | inspect source |
| GET,POST | `/reports/<int:order_id>` | [report_editor](../../ris/app.py#L8035) | inspect source |
| GET,POST | `/scan` | [barcode_scan](../../ris/app.py#L15943) | inspect source |
| GET,POST | `/studio/shortcuts` | [studio_shortcuts](../../ris/app.py#L29818) | inspect source |
| GET,POST | `/studio/templates/<template_type>` | [studio_templates](../../ris/app.py#L25757) | inspect source |
| POST | `/accounting/entries/<int:entry_id>/void` | [financial_entry_void](../../ris/app.py#L18751) | inspect source |
| POST | `/admin/assignment-strategies/<int:strategy_id>/clone` | [admin_assignment_strategy_clone](../../ris/app.py#L19853) | inspect source |
| POST | `/admin/assignment-strategies/<int:strategy_id>/rollback/<int:version_id>` | [admin_assignment_strategy_rollback](../../ris/app.py#L19965) | inspect source |
| POST | `/admin/assignment-strategies/<int:strategy_id>/toggle` | [admin_assignment_strategy_toggle](../../ris/app.py#L19743) | inspect source |
| POST | `/admin/assignment-strategies/simulate` | [admin_assignment_strategy_simulate](../../ris/app.py#L19660) | inspect source |
| POST | `/admin/assignment-visits/<visit_id>/complete-registration` | [complete_visit_registration](../../ris/app.py#L7722) | inspect source |
| POST | `/admin/booking-availability/seed` | [admin_booking_availability_seed](../../ris/app.py#L14669) | inspect source |
| POST | `/admin/booking-control/<int:block_id>/deactivate` | [admin_booking_control_deactivate](../../ris/app.py#L14947) | inspect source |
| POST | `/admin/cancellation-center/appointments/<int:appointment_id>/cancel` | [admin_cancel_appointment](../../ris/app.py#L25265) | inspect source |
| POST | `/admin/cancellation-center/order/<int:order_id>/delete-full-case` | [granular_delete_order_full_case](../../ris/app.py#L23482) | inspect source |
| POST | `/admin/cancellation-center/order/<int:order_id>/delete-images` | [granular_delete_order_images_only](../../ris/app.py#L21322) | inspect source |
| POST | `/admin/cancellation-center/order/<int:order_id>/delete-reports` | [granular_delete_order_reports_only](../../ris/app.py#L23153) | inspect source |
| POST | `/admin/cancellation-center/order/<int:order_id>/delete-ris-case-data` | [granular_delete_order_ris_case_data_only](../../ris/app.py#L23176) | inspect source |
| POST | `/admin/cancellation-center/orders/<int:order_id>/cancel` | [admin_cancel_order](../../ris/app.py#L25274) | inspect source |
| POST | `/admin/cancellation-center/orders/<int:order_id>/remove-referral` | [admin_remove_order_referral](../../ris/app.py#L25294) | inspect source |
| POST | `/admin/communication-templates` | [admin_communication_template_save](../../ris/app.py#L26069) | inspect source |
| POST | `/admin/data-management/anonymize-patient` | [admin_anonymize_patient](../../ris/app.py#L30555) | inspect source |
| POST | `/admin/data-management/backup-all-patients` | [admin_backup_all_patients](../../ris/app.py#L30616) | inspect source |
| POST | `/admin/data-management/create-manifest-backup` | [admin_create_manifest_backup](../../ris/app.py#L30536) | inspect source |
| POST | `/admin/data-management/delete-all-patients` | [admin_delete_all_patients](../../ris/app.py#L30635) | inspect source |
| POST | `/admin/data-management/delete-patient` | [admin_delete_patient](../../ris/app.py#L30574) | inspect source |
| POST | `/admin/data-management/export-patient` | [admin_export_patient](../../ris/app.py#L30489) | inspect source |
| POST | `/admin/data-management/reset-module` | [admin_reset_module](../../ris/app.py#L30594) | inspect source |
| POST | `/admin/device-blocks` | [admin_device_blocks](../../ris/app.py#L20428) | inspect source |
| POST | `/admin/devices/<int:device_id>/edit` | [admin_device_edit](../../ris/app.py#L20534) | inspect source |
| POST | `/admin/dicom-connections/<int:endpoint_id>/echo` | [dicom_connection_echo](../../ris/app.py#L20492) | inspect source |
| POST | `/admin/dictionary/<int:entry_id>/reset` | [admin_dictionary_reset](../../ris/app.py#L14975) | inspect source |
| POST | `/admin/discount-policies/<int:policy_id>/toggle` | [discount_policy_toggle](../../ris/app.py#L30031) | inspect source |
| POST | `/admin/doctor-share-rules/<int:rule_id>/toggle` | [doctor_share_rule_toggle](../../ris/app.py#L29974) | inspect source |
| POST | `/admin/erp/process` | [admin_erp_process](../../ris/app.py#L20759) | inspect source |
| POST | `/admin/erp/sync-items` | [admin_erp_sync_items](../../ris/app.py#L20766) | inspect source |
| POST | `/admin/external-intake/<int:intake_id>/attachments` | [admin_external_intake_attachment_upload](../../ris/app.py#L31479) | inspect source |
| POST | `/admin/external-intake/<int:intake_id>/decision` | [admin_external_intake_decision](../../ris/app.py#L31519) | inspect source |
| POST | `/admin/insurance-approvals/<int:portal_id>/test` | [admin_insurance_approval_test](../../ris/app.py#L6161) | inspect source |
| POST | `/admin/insurance-approvals/<int:portal_id>/toggle` | [admin_insurance_approval_toggle](../../ris/app.py#L6140) | inspect source |
| POST | `/admin/inventory/<int:item_id>/adjust` | [admin_inventory_adjust](../../ris/app.py#L20612) | inspect source |
| POST | `/admin/inventory/<int:item_id>/edit` | [admin_inventory_edit](../../ris/app.py#L20593) | inspect source |
| POST | `/admin/inventory/import` | [admin_inventory_import](../../ris/app.py#L20669) | inspect source |
| POST | `/admin/inventory/seed-defaults` | [admin_inventory_seed_defaults](../../ris/app.py#L20628) | inspect source |
| POST | `/admin/notifications/<int:notification_id>/retry` | [admin_notification_retry](../../ris/app.py#L6851) | inspect source |
| POST | `/admin/notifications/process` | [admin_notifications_process](../../ris/app.py#L6844) | inspect source |
| POST | `/admin/ocr-settings/validate` | [admin_ocr_settings_validate](../../ris/app.py#L29580) | inspect source |
| POST | `/admin/pacs/discovery/<int:node_id>/approve` | [pacs_discovery_approve](../../ris/app.py#L31572) | inspect source |
| POST | `/admin/pacs/discovery/<int:node_id>/block` | [pacs_discovery_block](../../ris/app.py#L31589) | inspect source |
| POST | `/admin/pacs/discovery/<int:node_id>/dismiss` | [pacs_discovery_dismiss](../../ris/app.py#L31658) | inspect source |
| POST | `/admin/pacs/discovery/<int:node_id>/legacy-endpoint` | [pacs_discovery_legacy_endpoint](../../ris/app.py#L31597) | inspect source |
| POST | `/admin/pacs/discovery/manual` | [pacs_discovery_manual](../../ris/app.py#L31675) | inspect source |
| POST | `/admin/printer-profiles/<int:profile_id>/delete` | [admin_printer_profile_delete](../../ris/app.py#L29729) | inspect source |
| POST | `/admin/procedures/<int:procedure_id>/consumables/<int:row_id>/delete` | [procedure_consumable_delete](../../ris/app.py#L6797) | inspect source |
| POST | `/admin/qa-control/retry-failed` | [admin_qa_retry_failed](../../ris/app.py#L26384) | inspect source |
| POST | `/admin/qa-control/run` | [admin_qa_control_run](../../ris/app.py#L26303) | inspect source |
| POST | `/admin/qa-control/workflow/<action>` | [admin_qa_workflow_control](../../ris/app.py#L26423) | inspect source |
| POST | `/admin/security/country-policy` | [security_save_country_policy](../../ris/security_dashboard.py#L215) | inspect source |
| POST | `/admin/security/vpn/<int:peer_id>/revoke` | [security_revoke_vpn](../../ris/security_dashboard.py#L288) | inspect source |
| POST | `/admin/security/vpn/create` | [security_create_vpn](../../ris/security_dashboard.py#L246) | inspect source |
| POST | `/admin/storage-dr/policy/<int:policy_id>/failover` | [dr_failover_request](../../ris/app.py#L30961) | inspect source |
| POST | `/admin/storage-dr/policy/<int:policy_id>/state` | [replication_state_update](../../ris/app.py#L30950) | inspect source |
| POST | `/admin/storage-dr/storage/<int:storage_id>/health` | [storage_target_health](../../ris/app.py#L30944) | inspect source |
| POST | `/admin/users/<int:user_id>/edit` | [admin_user_edit](../../ris/app.py#L20361) | inspect source |
| POST | `/admin/users/<int:user_id>/reset-password` | [admin_user_reset_password](../../ris/app.py#L20387) | inspect source |
| POST | `/admin/users/<int:user_id>/toggle` | [admin_user_toggle](../../ris/app.py#L20350) | inspect source |
| POST | `/admin/users/import/apply` | [apply](../../ris/user_csv_transfer.py#L233) | inspect source |
| POST | `/api/command-center/control` | [api_command_center_control_set](../../ris/app.py#L17119) | inspect source |
| POST | `/api/doctor/presence/heartbeat` | [doctor_presence_heartbeat](../../ris/app.py#L7441) | inspect source |
| POST | `/api/doctor/workspace/column-layout` | [doctor_workspace_column_layout_save](../../ris/app.py#L7600) | inspect source |
| POST | `/api/ohif/report/<int:order_id>/draft` | [api_ohif_report_draft](../../ris/app.py#L33043) | inspect source |
| POST | `/api/ohif/report/<int:order_id>/finalize` | [api_ohif_report_finalize](../../ris/app.py#L33421) | inspect source |
| POST | `/api/ohif/report/<int:order_id>/lease/acquire` | [api_ohif_report_lease_acquire](../../ris/app.py#L32895) | inspect source |
| POST | `/api/ohif/report/<int:order_id>/lease/release` | [api_ohif_report_lease_release](../../ris/app.py#L32987) | inspect source |
| POST | `/api/ohif/report/<int:order_id>/onlyoffice/callback` | [api_ohif_onlyoffice_callback](../../ris/app.py#L35344) | inspect source |
| POST | `/api/ohif/report/<int:order_id>/onlyoffice/commit-draft` | [api_ohif_onlyoffice_commit_draft](../../ris/app.py#L34992) | inspect source |
| POST | `/api/ohif/report/<int:order_id>/onlyoffice/finalize` | [api_ohif_onlyoffice_finalize](../../ris/app.py#L35231) | inspect source |
| POST | `/api/ohif/report/<int:order_id>/onlyoffice/forcesave` | [api_ohif_onlyoffice_forcesave](../../ris/app.py#L34236) | inspect source |
| POST | `/api/ohif/report/<int:order_id>/onlyoffice/verify` | [api_ohif_onlyoffice_verify](../../ris/app.py#L35117) | inspect source |
| POST | `/api/ohif/report/<int:order_id>/return` | [api_ohif_report_return](../../ris/app.py#L33611) | inspect source |
| POST | `/api/ohif/report/<int:order_id>/verify` | [api_ohif_report_verify](../../ris/app.py#L33266) | inspect source |
| POST | `/api/ohif/report/<int:order_id>/word/draft` | [api_ohif_report_word_draft](../../ris/app.py#L32313) | inspect source |
| POST | `/api/ohif/report/<int:order_id>/word/finalize` | [api_ohif_report_word_finalize](../../ris/app.py#L32695) | inspect source |
| POST | `/api/ohif/report/<int:order_id>/word/verify` | [api_ohif_report_word_verify](../../ris/app.py#L32532) | inspect source |
| POST | `/api/public-call/request` | [public_contact_request_create](../../ris/app.py#L37083) | inspect source |
| POST | `/api/public-call/request/<int:request_id>/attachments` | [public_contact_attachment_upload](../../ris/app.py#L38150) | inspect source |
| POST | `/api/public-call/request/<int:request_id>/details` | [public_contact_request_details](../../ris/app.py#L37999) | inspect source |
| POST | `/api/public-chat/<token>/message` | [public_chat_message](../../ris/app.py#L37332) | inspect source |
| POST | `/api/public-chat/start` | [public_chat_start](../../ris/app.py#L37177) | inspect source |
| POST | `/api/qa/callback` | [api_qa_callback](../../ris/app.py#L26458) | inspect source |
| POST | `/api/reporting/cases/<accession>/draft` | [api_reporting_draft](../../ris/app.py#L8880) | inspect source |
| POST | `/api/reporting/cases/<accession>/finalize` | [api_reporting_finalize](../../ris/app.py#L9303) | inspect source |
| POST | `/api/reporting/cases/<accession>/lease/acquire` | [api_reporting_lease_acquire](../../ris/app.py#L8737) | inspect source |
| POST | `/api/reporting/cases/<accession>/lease/release` | [api_reporting_lease_release](../../ris/app.py#L8829) | inspect source |
| POST | `/api/reporting/cases/<accession>/verify` | [api_reporting_verify](../../ris/app.py#L9101) | inspect source |
| POST | `/api/reporting/identity/<int:order_id>` | [renew](../../ris/report_identity_routes.py#L10) | inspect source |
| POST | `/api/staff/attachments/<int:attachment_id>/reject` | [staff_attachment_reject](../../ris/app.py#L38486) | inspect source |
| POST | `/api/staff/attachments/<int:attachment_id>/verify` | [staff_attachment_verify](../../ris/app.py#L38454) | inspect source |
| POST | `/api/staff/chat/<int:request_id>/message` | [staff_chat_message](../../ris/app.py#L37845) | inspect source |
| POST | `/api/staff/communications/<int:request_id>/claim` | [staff_communications_claim](../../ris/app.py#L37629) | inspect source |
| POST | `/api/staff/communications/<int:request_id>/confirm` | [staff_communications_confirm](../../ris/app.py#L37698) | inspect source |
| POST | `/api/staff/communications/<int:request_id>/reject` | [staff_communications_reject](../../ris/app.py#L37769) | inspect source |
| POST | `/api/telephony/incoming` | [telephony_incoming](../../ris/app.py#L15210) | inspect source |
| POST | `/api/voice/appointment/book` | [appointment_book](../../ris/voice_ai.py#L330) | inspect source |
| POST | `/api/voice/book` | [voice_api_book](../../ris/app.py#L36069) | inspect source |
| POST | `/api/voice/complaints` | [complaint_create](../../ris/voice_ai.py#L434) | inspect source |
| POST | `/api/voice/handoff` | [handoff](../../ris/voice_ai.py#L514) | inspect source |
| POST | `/api/voice/patient` | [voice_api_patient_create](../../ris/app.py#L35697) | inspect source |
| POST | `/api/voice/patient/search` | [patient_search](../../ris/voice_ai.py#L117) | inspect source |
| POST | `/api/voice/report/status` | [report_status](../../ris/voice_ai.py#L263) | inspect source |
| POST | `/api/voice/session/start` | [session_start](../../ris/voice_ai.py#L73) | inspect source |
| POST | `/appointments/<int:appointment_id>/<action>` | [appointment_action](../../ris/app.py#L14168) | inspect source |
| POST | `/appointments/<int:appointment_id>/reschedule` | [appointment_reschedule](../../ris/app.py#L14317) | inspect source |
| POST | `/appointments/<int:appointment_id>/status` | [appointment_status](../../ris/app.py#L14346) | inspect source |
| POST | `/assignment/availability` | [assignment_availability_update](../../ris/app.py#L26796) | inspect source |
| POST | `/assignment/offers/<int:offer_id>/respond` | [assignment_offer_respond](../../ris/app.py#L26811) | inspect source |
| POST | `/assignment/offers/expire-now` | [assignment_offers_expire_now](../../ris/app.py#L26929) | inspect source |
| POST | `/attachments/<int:attachment_id>/delete` | [attachment_delete](../../ris/app.py#L15880) | inspect source |
| POST | `/attachments/upload` | [attachment_upload](../../ris/app.py#L15831) | inspect source |
| POST | `/chat/<int:thread_id>/add-to-clinical-note/<int:message_id>` | [chat_message_to_clinical_note](../../ris/app.py#L15138) | inspect source |
| POST | `/chat/direct` | [chat_direct_create](../../ris/app.py#L15097) | inspect source |
| POST | `/chat/group` | [chat_group_create](../../ris/app.py#L15108) | inspect source |
| POST | `/communications/<int:comm_id>/retry` | [communication_retry](../../ris/app.py#L26121) | inspect source |
| POST | `/coordinator/<int:task_id>/action` | [coordinator_action](../../ris/app.py#L30818) | inspect source |
| POST | `/coordinator/report-corrections/<int:revision_id>/review` | [coordinator_report_correction_review](../../ris/report_revisions.py#L296) | inspect source |
| POST | `/correction-center/executions/<int:execution_id>/claim` | [correction_execution_claim_route](../../ris/app.py#L24447) | inspect source |
| POST | `/correction-center/executions/<int:execution_id>/execute` | [correction_execution_execute_route](../../ris/app.py#L25050) | inspect source |
| POST | `/correction-center/executions/<int:execution_id>/hold` | [correction_execution_hold_route](../../ris/app.py#L24510) | inspect source |
| POST | `/correction-center/executions/<int:execution_id>/release` | [correction_execution_release_route](../../ris/app.py#L24572) | inspect source |
| POST | `/correction-center/request` | [correction_request_submit](../../ris/app.py#L24172) | inspect source |
| POST | `/correction-center/requests/<int:request_id>/action` | [correction_request_action](../../ris/app.py#L25181) | inspect source |
| POST | `/correction-center/requests/<int:request_id>/execution/prepare` | [correction_execution_prepare_route](../../ris/app.py#L24384) | inspect source |
| POST | `/devices/<int:device_id>/booking-status` | [device_booking_status](../../ris/app.py#L14426) | inspect source |
| POST | `/doctor/cases/<int:order_id>/start-reading` | [doctor_reading_start](../../ris/app.py#L7840) | inspect source |
| POST | `/doctor/templates/<int:template_id>/deactivate` | [report_template_deactivate](../../ris/report_template_routes.py#L94) | reports.edit |
| POST | `/doctor/viewer-preference` | [save](../../ris/viewer_choice.py#L181) | reports.view |
| POST | `/documents/<int:document_id>/review` | [document_review_save](../../ris/app.py#L15197) | inspect source |
| POST | `/external-priors/<int:prior_id>/confirm-match` | [external_prior_confirm_match](../../ris/app.py#L25988) | inspect source |
| POST | `/external-priors/<int:prior_id>/mark-mismatch` | [external_prior_mark_mismatch](../../ris/app.py#L25994) | inspect source |
| POST | `/finance/discount-approvals/<int:req_id>/decision` | [discount_approval_decision](../../ris/app.py#L30048) | inspect source |
| POST | `/intake/smart/<int:intake_id>/document/<int:doc_id>/review` | [smart_intake_document_review](../../ris/app.py#L29271) | inspect source |
| POST | `/intake/smart/<int:intake_id>/ocr-all` | [smart_intake_run_all_ocr](../../ris/app.py#L29247) | inspect source |
| POST | `/intake/smart/<int:intake_id>/ocr/<int:doc_id>` | [smart_intake_run_ocr](../../ris/app.py#L29224) | inspect source |
| POST | `/intake/smart/<int:intake_id>/review-save` | [smart_intake_review_save](../../ris/app.py#L29378) | inspect source |
| POST | `/intake/smart/<int:intake_id>/upload` | [smart_intake_upload](../../ris/app.py#L28938) | inspect source |
| POST | `/inventory/migrate-legacy-items` | [inventory_migrate_legacy_items](../../ris/app.py#L30140) | inspect source |
| POST | `/inventory/transfers/<int:transfer_id>/approve` | [inventory_transfer_approve](../../ris/app.py#L30263) | inspect source |
| POST | `/inventory/transfers/<int:transfer_id>/dispatch` | [inventory_transfer_dispatch](../../ris/app.py#L30284) | inspect source |
| POST | `/inventory/transfers/<int:transfer_id>/receive` | [inventory_transfer_receive](../../ris/app.py#L30311) | inspect source |
| POST | `/inventory/transfers/<int:transfer_id>/reject` | [inventory_transfer_reject](../../ris/app.py#L30273) | inspect source |
| POST | `/inventory/warehouses/auto-create` | [inventory_warehouses_auto_create](../../ris/app.py#L30419) | inspect source |
| POST | `/inventory/warehouses/create-for-branch/<int:branch_id>` | [inventory_create_for_branch](../../ris/app.py#L30438) | inspect source |
| POST | `/my/registration-style` | [my_registration_style](../../ris/app.py#L25688) | inspect source |
| POST | `/notifications/<int:notification_id>/ack` | [notification_ack](../../ris/app.py#L28550) | inspect source |
| POST | `/nursing/<int:order_id>/correct` | [nursing_consumable_correct](../../ris/app.py#L6762) | inspect source |
| POST | `/nursing/<int:order_id>/exam-status` | [nursing_exam_status](../../ris/procedure_staff_workflow.py#L153) | nursing.worklist |
| POST | `/operations/case-readiness/settings` | [readiness_schedule_settings](../../ris/readiness_operations.py#L139) | users.manage |
| POST | `/orders/<int:order_id>/assign-to-me` | [assign_case_to_me](../../ris/app.py#L26708) | inspect source |
| POST | `/orders/<int:order_id>/assignment-offer/start` | [assignment_offer_start](../../ris/app.py#L26916) | inspect source |
| POST | `/orders/<int:order_id>/consumables/apply-defaults` | [order_consumables_apply_defaults](../../ris/app.py#L30378) | inspect source |
| POST | `/orders/<int:order_id>/convert-to-work-order` | [convert_to_work_order](../../ris/app.py#L6448) | inspect source |
| POST | `/orders/<int:order_id>/delivery/<item_type>` | [mark_delivery](../../ris/app.py#L18841) | inspect source |
| POST | `/orders/<int:order_id>/exam-status` | [order_exam_status](../../ris/app.py#L7306) | inspect source |
| POST | `/orders/<int:order_id>/exam-status/override` | [order_exam_status_override](../../ris/app.py#L7350) | inspect source |
| POST | `/orders/<int:order_id>/exceptions/history` | [case_exception_history_add](../../ris/app.py#L27149) | inspect source |
| POST | `/orders/<int:order_id>/exceptions/image-minimum` | [case_exception_image_minimum](../../ris/app.py#L27178) | inspect source |
| POST | `/orders/<int:order_id>/exceptions/image-minimum/<int:override_id>/deactivate` | [case_exception_image_minimum_deactivate](../../ris/app.py#L27207) | inspect source |
| POST | `/orders/<int:order_id>/exceptions/refresh` | [case_exception_refresh](../../ris/app.py#L27229) | inspect source |
| POST | `/orders/<int:order_id>/exceptions/series-map` | [case_exception_series_map](../../ris/app.py#L27082) | inspect source |
| POST | `/orders/<int:order_id>/exceptions/series-map/<int:alias_id>/deactivate` | [case_exception_series_map_deactivate](../../ris/app.py#L27114) | inspect source |
| POST | `/orders/<int:order_id>/insurance-approval/start` | [insurance_approval_start](../../ris/app.py#L6319) | inspect source |
| POST | `/orders/<int:order_id>/insurance-approval/update` | [insurance_approval_update](../../ris/app.py#L6379) | inspect source |
| POST | `/orders/<int:order_id>/journey/<stage>` | [order_journey_stage](../../ris/app.py#L15050) | inspect source |
| POST | `/orders/<int:order_id>/payment` | [receive_payment](../../ris/app.py#L18792) | inspect source |
| POST | `/orders/<int:order_id>/performing-doctor` | [set_performing_doctor](../../ris/app.py#L29982) | inspect source |
| POST | `/orders/<int:order_id>/readiness/check` | [case_readiness_check](../../ris/app.py#L27252) | inspect source |
| POST | `/orders/<int:order_id>/resend-mwl` | [resend_mwl](../../ris/app.py#L6578) | inspect source |
| POST | `/orders/<int:order_id>/take` | [take_case](../../ris/app.py#L20123) | inspect source |
| POST | `/orders/<int:order_id>/workflow-status` | [order_workflow_status](../../ris/app.py#L14124) | inspect source |
| POST | `/pacs/actions/<int:order_id>/send` | [pacs_case_send](../../ris/app.py#L30747) | inspect source |
| POST | `/pacs/destinations/<int:destination_id>/echo` | [pacs_destination_echo](../../ris/app.py#L30783) | inspect source |
| POST | `/pacs/exam-link` | [pacs_exam_link_create](../../ris/app.py#L16201) | inspect source |
| POST | `/pacs/exam-link/<int:link_id>/remove` | [pacs_exam_link_remove](../../ris/app.py#L16267) | inspect source |
| POST | `/pacs/reconciliation/<study_id>/correct-dicom` | [pacs_reconciliation_correct_dicom](../../ris/app.py#L16016) | inspect source |
| POST | `/pacs/reconciliation/<study_id>/match` | [pacs_reconciliation_match](../../ris/app.py#L16312) | inspect source |
| POST | `/pacs/reconciliation/<study_id>/quarantine` | [pacs_reconciliation_quarantine](../../ris/app.py#L16367) | inspect source |
| POST | `/pacs/reconciliation/auto-safe` | [pacs_reconciliation_auto_safe](../../ris/app.py#L16405) | inspect source |
| POST | `/pacs/tracking/refresh` | [pacs_tracking_refresh](../../ris/app.py#L7401) | inspect source |
| POST | `/pacs/transfers/<int:job_id>/cancel` | [pacs_transfer_cancel](../../ris/app.py#L30773) | inspect source |
| POST | `/pacs/transfers/<int:job_id>/retry` | [pacs_transfer_retry](../../ris/app.py#L30763) | inspect source |
| POST | `/pacs/transfers/process` | [pacs_transfer_process](../../ris/app.py#L30795) | inspect source |
| POST | `/pacs/unregistered/run` | [pacs_unregistered_run](../../ris/app.py#L30688) | inspect source |
| POST | `/patient-alerts/<int:alert_id>/resolve` | [patient_alert_resolve](../../ris/app.py#L25734) | inspect source |
| POST | `/payments/<int:order_id>` | [add_payment](../../ris/app.py#L6610) | inspect source |
| POST | `/payments/<int:payment_id>/refund` | [refund_payment](../../ris/app.py#L18902) | inspect source |
| POST | `/radiotherapy/<int:course_id>/fractions` | [rt_schedule_fraction](../../ris/radiotherapy.py#L274) | rt.schedule |
| POST | `/radiotherapy/<int:course_id>/notes` | [rt_add_note](../../ris/radiotherapy.py#L366) | rt.notes |
| POST | `/radiotherapy/<int:course_id>/pet-links` | [rt_link_pet](../../ris/radiotherapy.py#L260) | rt.pet.link |
| POST | `/radiotherapy/<int:course_id>/plans` | [rt_record_plan](../../ris/radiotherapy.py#L235) | rt.plan.record |
| POST | `/radiotherapy/<int:course_id>/state` | [rt_course_state](../../ris/radiotherapy.py#L351) | rt.course.create |
| POST | `/radiotherapy/courses` | [rt_create_course](../../ris/radiotherapy.py#L213) | rt.course.create |
| POST | `/radiotherapy/fractions/<int:fraction_id>/cancel` | [rt_cancel_fraction](../../ris/radiotherapy.py#L339) | rt.schedule |
| POST | `/radiotherapy/fractions/<int:fraction_id>/complete` | [rt_complete_fraction](../../ris/radiotherapy.py#L317) | rt.session.record |
| POST | `/radiotherapy/fractions/<int:fraction_id>/consumables` | [rt_add_consumable](../../ris/radiotherapy.py#L383) | rt.consumables |
| POST | `/radiotherapy/fractions/<int:fraction_id>/reschedule` | [rt_reschedule_fraction](../../ris/radiotherapy.py#L294) | rt.schedule |
| POST | `/radiotherapy/fractions/<int:fraction_id>/start` | [rt_start_fraction](../../ris/radiotherapy.py#L307) | rt.session.start |
| POST | `/report-revisions/<int:revision_id>/callback` | [report_revision_callback](../../ris/report_revision_editor.py#L329) | inspect source |
| POST | `/report-revisions/<int:revision_id>/commit` | [report_revision_commit](../../ris/report_revision_editor.py#L403) | inspect source |
| POST | `/report-revisions/<int:revision_id>/forcesave` | [report_revision_forcesave](../../ris/report_revision_editor.py#L376) | inspect source |
| POST | `/report-revisions/<int:revision_id>/lease` | [report_revision_lease](../../ris/report_revision_editor.py#L268) | inspect source |
| POST | `/reports/<int:order_id>/admin-reopen` | [admin_report_reopen](../../ris/app.py#L7859) | inspect source |
| POST | `/reports/<int:order_id>/ai-assistant/<int:draft_id>/apply` | [ai_report_apply](../../ris/app.py#L25927) | inspect source |
| POST | `/reports/<int:order_id>/ai-assistant/<int:draft_id>/reject` | [ai_report_reject](../../ris/app.py#L25939) | inspect source |
| POST | `/reports/<int:order_id>/ai-assistant/generate` | [ai_report_generate](../../ris/app.py#L25910) | inspect source |
| POST | `/reports/<int:order_id>/imaging-ai/<int:analysis_id>/analyze` | [imaging_ai_analyze](../../ris/app.py#L26220) | inspect source |
| POST | `/reports/<int:order_id>/imaging-ai/<int:analysis_id>/mark-reviewed` | [imaging_ai_mark_reviewed](../../ris/app.py#L26264) | inspect source |
| POST | `/reports/<int:order_id>/imaging-ai/<int:analysis_id>/override` | [imaging_ai_demographic_override](../../ris/app.py#L26202) | inspect source |
| POST | `/reports/<int:order_id>/imaging-ai/verify-demographics` | [imaging_ai_verify_demographics](../../ris/app.py#L26158) | inspect source |
| POST | `/reports/<int:order_id>/lease/acquire` | [report_lease_acquire](../../ris/app.py#L7905) | inspect source |
| POST | `/reports/<int:order_id>/lease/release` | [report_lease_release](../../ris/app.py#L7988) | inspect source |
| POST | `/reports/<int:order_id>/priors/select` | [report_prior_select](../../ris/app.py#L25946) | inspect source |
| POST | `/reports/<int:order_id>/return-case` | [return_case_to_workflow](../../ris/app.py#L27298) | inspect source |
| POST | `/reports/<int:order_id>/upload` | [report_upload](../../ris/app.py#L15489) | inspect source |
| POST | `/returned-cases/<int:event_id>/resolve` | [resolve_returned_case](../../ris/app.py#L27434) | inspect source |
| POST | `/saved-views/<page_key>/<int:view_id>/default` | [saved_view_set_default](../../ris/app.py#L28689) | inspect source |
| POST | `/saved-views/<page_key>/<int:view_id>/delete` | [saved_view_delete](../../ris/app.py#L28730) | inspect source |
| POST | `/saved-views/<page_key>/<int:view_id>/rename` | [saved_view_rename](../../ris/app.py#L28710) | inspect source |
| POST | `/saved-views/<page_key>/<int:view_id>/update` | [saved_view_update](../../ris/app.py#L28649) | inspect source |
| POST | `/saved-views/<page_key>/save` | [saved_view_save](../../ris/app.py#L28627) | inspect source |
| POST | `/schedule/book` | [schedule_book](../../ris/app.py#L14057) | inspect source |
| POST | `/schedule/maintenance` | [schedule_maintenance](../../ris/app.py#L14361) | inspect source |
| POST | `/schedule/ocr-preview` | [schedule_ocr_preview](../../ris/app.py#L13838) | inspect source |
| POST | `/schedule/unified-submit` | [schedule_unified_submit](../../ris/app.py#L13914) | inspect source |
| POST | `/schedule/v2/book` | [schedule_v2_book_submit](../../ris/app.py#L14388) | inspect source |
| POST | `/search/advanced/save` | [advanced_search_save](../../ris/app.py#L28749) | inspect source |
| POST | `/studio/shortcuts/<int:shortcut_id>/delete` | [studio_shortcut_delete](../../ris/app.py#L29865) | inspect source |
| POST | `/studio/shortcuts/<int:shortcut_id>/toggle` | [studio_shortcut_toggle](../../ris/app.py#L29857) | inspect source |
| POST | `/studio/shortcuts/reorder` | [studio_shortcut_reorder](../../ris/app.py#L29873) | inspect source |
| POST | `/studio/templates/<int:template_id>/publish` | [studio_template_publish](../../ris/app.py#L25772) | inspect source |
| POST | `/technician/<int:order_id>/check-images` | [technician_check_images](../../ris/app.py#L7137) | inspect source |
| POST | `/technician/<int:order_id>/consume` | [technician_case_consume](../../ris/app.py#L7010) | inspect source |
| POST | `/technician/<int:order_id>/image-replacement-request` | [technician_image_replacement_request](../../ris/technician_queue.py#L160) | technician.worklist |
| POST | `/technician/<int:order_id>/note` | [technician_case_note](../../ris/app.py#L6975) | inspect source |
| POST | `/technician/<int:order_id>/returned-note` | [technician_returned_note](../../ris/technician_queue.py#L144) | technician.worklist |
| POST | `/technician/<int:order_id>/status` | [technician_status](../../ris/app.py#L7231) | inspect source |
| POST | `/telephony/calls/<int:call_id>/notes` | [telephony_call_notes](../../ris/app.py#L15243) | inspect source |
| POST | `/ui/language` | [ui_language_switch](../../ris/app.py#L14959) | inspect source |
| POST | `/voice-intake/<int:intake_id>/caller-control` | [voice_intake_caller_control](../../ris/app.py#L36410) | inspect source |
| POST | `/voice-intake/<int:intake_id>/status` | [voice_intake_status](../../ris/app.py#L36352) | inspect source |
