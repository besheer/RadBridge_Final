# Static ORM inventory

Generated declarations, not a live DB dump or complete migration/DDL contract. Names marked inferred use the usual Flask-SQLAlchemy CamelCase-to-snake_case convention and require runtime confirmation. Defaults, indexes, composite/check constraints and relationships must be read in source. No records or patient data are included. The app also registers models in extracted modules.

## `ai_draft_report (inferred)`

[AIDraftReport](../../ris/app.py#L935)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `provider_key` | `db.String(40)` |  |
| `model_name` | `db.String(180)` |  |
| `input_context` | `db.Text` |  |
| `findings_draft` | `db.Text` |  |
| `impression_draft` | `db.Text` |  |
| `comparison_draft` | `db.Text` |  |
| `safety_notes` | `db.Text` |  |
| `status` | `db.String(30)` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |
| `reviewed_by` | `db.Integer` |  |
| `reviewed_at` | `db.DateTime` |  |

Foreign keys: `order_id → order.id`, `created_by → user.id`, `reviewed_by → user.id`.

## `ai_provider_setting (inferred)`

[AIProviderSetting](../../ris/app.py#L925)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `provider_key` | `db.String(40)` | unique=True,nullable=False |
| `enabled` | `db.Boolean` |  |
| `base_url` | `db.String(500)` |  |
| `model_name` | `db.String(180)` |  |
| `timeout_seconds` | `db.Integer` |  |
| `updated_by` | `db.Integer` |  |
| `updated_at` | `db.DateTime` |  |

Foreign keys: `updated_by → user.id`.

## `appointment (inferred)`

[Appointment](../../ris/app.py#L1868)

| Column | Declared type | Flags |
|---|---|---|
| `assignment_visit_id` | `db.String(36)` |  |
| `assignment_special_code` | `db.String(80)` |  |
| `id` | `db.Integer` | primary_key=True |
| `patient_id` | `db.Integer` | nullable=False |
| `branch_id` | `db.Integer` | nullable=False |
| `procedure_id` | `db.Integer` | nullable=False |
| `device_id` | `db.Integer` |  |
| `order_id` | `db.Integer` | unique=True |
| `scheduled` | `db.DateTime` | nullable=False |
| `status` | `db.String(30)` |  |
| `source` | `db.String(40)` |  |
| `notes` | `db.Text` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |
| `checked_in_at` | `db.DateTime` |  |
| `cancelled_at` | `db.DateTime` |  |
| `confirmed_at` | `db.DateTime` |  |
| `duration_min` | `db.Integer` |  |
| `priority` | `db.String(20)` |  |
| `waiting_list` | `db.Boolean` |  |

Foreign keys: `assignment_visit_id → assignment_visit.id`, `patient_id → patient.id`, `branch_id → branch.id`, `procedure_id → procedure.id`, `device_id → device.id`, `order_id → order.id`.

## `assignment_distribution_policy`

[AssignmentDistributionPolicy](../../ris/app.py#L1358)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `selection_mode` | `db.String(30)` | nullable=False |
| `max_active_cases` | `db.Integer` | nullable=False |
| `reclaim_enabled` | `db.Boolean` | nullable=False |
| `urgent_percent` | `db.Integer` | nullable=False |
| `stat_percent` | `db.Integer` | nullable=False |
| `rules_json` | `db.Text` | nullable=False |
| `special_rules_json` | `db.Text` | nullable=False |
| `version_no` | `db.Integer` | nullable=False |
| `updated_by` | `db.Integer` |  |
| `updated_at` | `db.DateTime` |  |

Foreign keys: `updated_by → user.id`.

## `assignment_escalation_event (inferred)`

[AssignmentEscalationEvent](../../ris/app.py#L1388)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `offer_id` | `db.Integer` |  |
| `event_type` | `db.String(50)` | nullable=False |
| `details` | `db.Text` |  |
| `created_at` | `db.DateTime` |  |
| `created_by` | `db.Integer` |  |

Foreign keys: `order_id → order.id`, `offer_id → assignment_offer.id`, `created_by → user.id`.

## `assignment_offer (inferred)`

[AssignmentOffer](../../ris/app.py#L1373)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `doctor_user_id` | `db.Integer` | nullable=False |
| `attempt_no` | `db.Integer` |  |
| `status` | `db.String(30)` |  |
| `offered_at` | `db.DateTime` |  |
| `expires_at` | `db.DateTime` | nullable=False |
| `responded_at` | `db.DateTime` |  |
| `response_note` | `db.String(500)` |  |
| `channel_summary` | `db.String(300)` |  |
| `created_by` | `db.Integer` |  |

Foreign keys: `order_id → order.id`, `doctor_user_id → user.id`, `created_by → user.id`.

## `assignment_offer_policy (inferred)`

[AssignmentOfferPolicy](../../ris/app.py#L1211)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `name` | `db.String(120)` |  |
| `enabled` | `db.Boolean` |  |
| `mode` | `db.String(30)` |  |
| `routine_timeout_seconds` | `db.Integer` |  |
| `urgent_timeout_seconds` | `db.Integer` |  |
| `stat_timeout_seconds` | `db.Integer` |  |
| `busy_snooze_minutes` | `db.Integer` |  |
| `max_offer_attempts` | `db.Integer` |  |
| `notification_channels` | `db.String(120)` |  |
| `updated_by` | `db.Integer` |  |
| `updated_at` | `db.DateTime` |  |

Foreign keys: `updated_by → user.id`.

## `assignment_strategy`

[AssignmentStrategy](../../ris/app.py#L1226)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `name` | `db.String(160)` | nullable=False,unique=True |
| `enabled` | `db.Boolean` |  |
| `priority` | `db.Integer` |  |
| `branch_id` | `db.Integer` |  |
| `modality` | `db.String(30)` |  |
| `procedure_pattern` | `db.String(180)` |  |
| `assignment_mode` | `db.String(30)` |  |
| `fallback_mode` | `db.String(30)` |  |
| `pacs_missing_action` | `db.String(20)` |  |
| `images_incomplete_action` | `db.String(20)` |  |
| `documents_missing_action` | `db.String(20)` |  |
| `notes_missing_action` | `db.String(20)` |  |
| `attachments_missing_action` | `db.String(20)` |  |
| `history_missing_action` | `db.String(20)` |  |
| `require_modality_match` | `db.Boolean` |  |
| `require_branch_match` | `db.Boolean` |  |
| `require_online` | `db.Boolean` |  |
| `prefer_online` | `db.Boolean` |  |
| `min_images` | `db.Integer` |  |
| `min_completion_percent` | `db.Integer` |  |
| `stable_seconds` | `db.Integer` |  |
| `routine_timeout_seconds` | `db.Integer` |  |
| `urgent_timeout_seconds` | `db.Integer` |  |
| `stat_timeout_seconds` | `db.Integer` |  |
| `busy_snooze_minutes` | `db.Integer` |  |
| `max_offer_attempts` | `db.Integer` |  |
| `active_from` | `db.String(5)` |  |
| `active_to` | `db.String(5)` |  |
| `version_no` | `db.Integer` |  |
| `updated_by` | `db.Integer` |  |
| `updated_at` | `db.DateTime` |  |

Foreign keys: `branch_id → branch.id`, `updated_by → user.id`.

## `assignment_strategy_version`

[AssignmentStrategyVersion](../../ris/app.py#L1307)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `strategy_id` | `db.Integer` | nullable=False |
| `version_no` | `db.Integer` | nullable=False |
| `snapshot_json` | `db.Text` | nullable=False |
| `changed_by` | `db.Integer` |  |
| `change_note` | `db.String(500)` |  |
| `changed_at` | `db.DateTime` |  |

Foreign keys: `strategy_id → assignment_strategy.id`, `changed_by → user.id`.

## `assignment_visit`

[AssignmentVisit](../../ris/app.py#L1346)

| Column | Declared type | Flags |
|---|---|---|
| `assignment_mode` | `db.String(20)` |  |
| `registration_open` | `db.Boolean` |  |
| `sequence_id` | `db.Integer` | primary_key=True |
| `id` | `db.String(36)` | nullable=False,unique=True |
| `patient_id` | `db.Integer` | nullable=False |
| `branch_id` | `db.Integer` |  |
| `visit_date` | `db.Date` | nullable=False |
| `preferred_doctor_id` | `db.Integer` |  |

Foreign keys: `patient_id → patient.id`, `branch_id → branch.id`, `preferred_doctor_id → user.id`.

## `attachment (inferred)`

[Attachment](../../ris/app.py#L1791)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `patient_id` | `db.Integer` |  |
| `order_id` | `db.Integer` |  |
| `appointment_id` | `db.Integer` |  |
| `external_intake_id` | `db.Integer` |  |
| `category` | `db.String(60)` | nullable=False |
| `original_name` | `db.String(255)` | nullable=False |
| `stored_path` | `db.String(500)` | nullable=False |
| `mime_type` | `db.String(120)` |  |
| `notes` | `db.String(500)` |  |
| `uploaded_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `patient_id → patient.id`, `order_id → order.id`, `appointment_id → appointment.id`, `external_intake_id → external_intake_case.id`.

## `audit_log (inferred)`

[AuditLog](../../ris/app.py#L305)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `created_at` | `db.DateTime` | nullable=False |
| `user_id` | `db.Integer` |  |
| `username` | `db.String(80)` |  |
| `action` | `db.String(100)` | nullable=False |
| `entity` | `db.String(80)` |  |
| `entity_id` | `db.String(80)` |  |
| `details` | `db.Text` |  |
| `ip` | `db.String(80)` |  |

## `backup_run`

[BackupRun](../../ris/app.py#L2752)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `config_id` | `db.Integer` |  |
| `status` | `db.String(30)` |  |
| `started_at` | `db.DateTime` |  |
| `completed_at` | `db.DateTime` |  |
| `reports_files` | `db.Integer` |  |
| `attachments_files` | `db.Integer` |  |
| `database_file` | `db.String(700)` |  |
| `pacs_files` | `db.Integer` |  |
| `last_error` | `db.Text` |  |

Foreign keys: `config_id → cloud_backup_config.id`.

## `booking_block (inferred)`

[BookingBlock](../../ris/app.py#L446)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `block_type` | `db.String(40)` | nullable=False |
| `branch_id` | `db.Integer` |  |
| `device_id` | `db.Integer` |  |
| `procedure_id` | `db.Integer` |  |
| `user_id` | `db.Integer` |  |
| `start_at` | `db.DateTime` | nullable=False |
| `end_at` | `db.DateTime` | nullable=False |
| `reason_code` | `db.String(60)` |  |
| `reason_text` | `db.String(500)` |  |
| `active` | `db.Boolean` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `branch_id → branch.id`, `device_id → device.id`, `procedure_id → procedure.id`, `user_id → user.id`.

## `branch (inferred)`

[Branch](../../ris/app.py#L276)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `code` | `db.String(20)` | unique=True,nullable=False |
| `name` | `db.String(120)` | nullable=False |
| `active` | `db.Boolean` |  |
| `reception_collection_enabled` | `db.Boolean` | nullable=False |

## `call_log (inferred)`

[CallLog](../../ris/app.py#L550)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `direction` | `db.String(20)` |  |
| `caller_number` | `db.String(60)` |  |
| `called_number` | `db.String(60)` |  |
| `extension` | `db.String(30)` |  |
| `patient_id` | `db.Integer` |  |
| `user_id` | `db.Integer` |  |
| `started_at` | `db.DateTime` |  |
| `ended_at` | `db.DateTime` |  |
| `status` | `db.String(30)` |  |
| `notes` | `db.Text` |  |
| `external_call_id` | `db.String(160)` |  |

Foreign keys: `patient_id → patient.id`, `user_id → user.id`.

## `case_assignment (inferred)`

[CaseAssignment](../../ris/app.py#L1842)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `doctor_user_id` | `db.Integer` | nullable=False |
| `assigned_by` | `db.Integer` |  |
| `assignment_type` | `db.String(20)` |  |
| `active` | `db.Boolean` |  |
| `assigned_at` | `db.DateTime` |  |
| `unassigned_at` | `db.DateTime` |  |
| `notes` | `db.String(500)` |  |
| `start_deadline_at` | `db.DateTime` |  |
| `start_timeout_seconds` | `db.Integer` |  |
| `reading_started_at` | `db.DateTime` |  |
| `distribution_snapshot_json` | `db.Text` |  |

Foreign keys: `order_id → order.id`, `doctor_user_id → user.id`.

## `case_exception_resolution_event`

[CaseExceptionResolutionEvent](../../ris/app.py#L1467)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `action` | `db.String(60)` | nullable=False |
| `blocker` | `db.String(80)` | nullable=False |
| `old_value` | `db.String(500)` | nullable=False |
| `new_value` | `db.String(500)` | nullable=False |
| `reason` | `db.String(500)` | nullable=False |
| `actor_user_id` | `db.Integer` |  |
| `created_at` | `db.DateTime` | nullable=False |

Foreign keys: `order_id → order.id`.

## `case_readiness (inferred)`

[CaseReadiness](../../ris/app.py#L1412)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | unique=True,nullable=False |
| `status` | `db.String(40)` |  |
| `score` | `db.Integer` |  |
| `image_count` | `db.Integer` |  |
| `expected_min_images` | `db.Integer` |  |
| `missing_history` | `db.Boolean` |  |
| `missing_attachments` | `db.Boolean` |  |
| `missing_documents` | `db.Boolean` |  |
| `missing_notes` | `db.Boolean` |  |
| `missing_pacs` | `db.Boolean` |  |
| `incomplete_images` | `db.Boolean` |  |
| `missing_series` | `db.Boolean` |  |
| `series_evidence_json` | `db.Text` |  |
| `facts_sha256` | `db.String(64)` |  |
| `series_checked_at` | `db.DateTime` |  |
| `details_json` | `db.Text` |  |
| `checked_at` | `db.DateTime` |  |
| `override_reason` | `db.Text` |  |
| `override_by` | `db.Integer` |  |

Foreign keys: `order_id → order.id`, `override_by → user.id`.

## `case_readiness_override`

[CaseReadinessOverride](../../ris/app.py#L1454)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `blocker` | `db.String(80)` | nullable=False |
| `override_value` | `db.String(255)` | nullable=False |
| `active` | `db.Boolean` | nullable=False |
| `reason` | `db.String(500)` | nullable=False |
| `actor_user_id` | `db.Integer` |  |
| `created_at` | `db.DateTime` | nullable=False |
| `deactivated_at` | `db.DateTime` |  |

Foreign keys: `order_id → order.id`.

## `case_return_reason (inferred)`

[CaseReturnReason](../../ris/app.py#L1490)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `code` | `db.String(100)` | unique=True,nullable=False |
| `label` | `db.String(180)` | nullable=False |
| `route_to` | `db.String(60)` |  |
| `active` | `db.Boolean` |  |

## `case_workflow_event (inferred)`

[CaseWorkflowEvent](../../ris/app.py#L1480)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `event_type` | `db.String(60)` | nullable=False |
| `owner_role` | `db.String(60)` |  |
| `reason_code` | `db.String(100)` |  |
| `note` | `db.Text` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `order_id → order.id`, `created_by → user.id`.

## `chat_message (inferred)`

[ChatMessage](../../ris/app.py#L496)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `thread_id` | `db.Integer` | nullable=False |
| `sender_id` | `db.Integer` | nullable=False |
| `body` | `db.Text` | nullable=False |
| `attachment_path` | `db.String(600)` |  |
| `attachment_name` | `db.String(255)` |  |
| `created_at` | `db.DateTime` |  |
| `deleted_at` | `db.DateTime` |  |

Foreign keys: `thread_id → chat_thread.id`, `sender_id → user.id`.

## `chat_thread (inferred)`

[ChatThread](../../ris/app.py#L475)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `thread_type` | `db.String(30)` | nullable=False |
| `title` | `db.String(200)` |  |
| `order_id` | `db.Integer` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |
| `active` | `db.Boolean` |  |

Foreign keys: `order_id → order.id`, `created_by → user.id`.

## `chat_thread_member (inferred)`

[ChatThreadMember](../../ris/app.py#L485)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `thread_id` | `db.Integer` | nullable=False |
| `user_id` | `db.Integer` | nullable=False |
| `joined_at` | `db.DateTime` |  |
| `last_read_at` | `db.DateTime` |  |
| `muted` | `db.Boolean` |  |

Foreign keys: `thread_id → chat_thread.id`, `user_id → user.id`.

## `clinical_assessment (inferred)`

[ClinicalAssessment](../../ris/app.py#L1652)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False,unique=True |
| `complaint` | `db.Text` |  |
| `history` | `db.Text` |  |
| `examination` | `db.Text` |  |
| `diagnosis` | `db.Text` |  |
| `treatment_plan` | `db.Text` |  |
| `allergy_notes` | `db.Text` |  |
| `clinical_indication` | `db.Text` |  |
| `created_by` | `db.Integer` |  |
| `updated_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |
| `updated_at` | `db.DateTime` |  |

Foreign keys: `order_id → order.id`, `created_by → user.id`, `updated_by → user.id`.

## `clinical_diagnosis (inferred)`

[ClinicalDiagnosis](../../ris/app.py#L1681)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `diagnosis_text` | `db.String(500)` | nullable=False |
| `diagnosis_type` | `db.String(30)` |  |
| `code` | `db.String(80)` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `order_id → order.id`, `created_by → user.id`.

## `clinical_lab_item (inferred)`

[ClinicalLabItem](../../ris/app.py#L1703)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `test_name` | `db.String(250)` | nullable=False |
| `status` | `db.String(30)` |  |
| `result_text` | `db.Text` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `order_id → order.id`, `created_by → user.id`.

## `clinical_medication (inferred)`

[ClinicalMedication](../../ris/app.py#L1690)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `medication_name` | `db.String(250)` | nullable=False |
| `dose` | `db.String(120)` |  |
| `route` | `db.String(80)` |  |
| `frequency` | `db.String(120)` |  |
| `duration` | `db.String(120)` |  |
| `notes` | `db.String(500)` |  |
| `active` | `db.Boolean` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `order_id → order.id`, `created_by → user.id`.

## `clinical_note (inferred)`

[ClinicalNote](../../ris/app.py#L390)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `author_user_id` | `db.Integer` |  |
| `note_type` | `db.String(40)` |  |
| `visibility` | `db.String(30)` |  |
| `text` | `db.Text` | nullable=False |
| `created_at` | `db.DateTime` |  |

Foreign keys: `order_id → order.id`, `author_user_id → user.id`.

## `cloud_backup_config`

[CloudBackupConfig](../../ris/app.py#L2737)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `name` | `db.String(160)` | nullable=False |
| `provider` | `db.String(40)` |  |
| `rclone_remote` | `db.String(120)` |  |
| `remote_root` | `db.String(500)` |  |
| `include_reports` | `db.Boolean` |  |
| `include_attachments` | `db.Boolean` |  |
| `include_database` | `db.Boolean` |  |
| `include_pacs` | `db.Boolean` |  |
| `schedule_hour` | `db.Integer` |  |
| `active` | `db.Boolean` |  |
| `created_at` | `db.DateTime` |  |

## `communication_channel_setting (inferred)`

[CommunicationChannelSetting](../../ris/app.py#L982)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `channel` | `db.String(30)` | unique=True,nullable=False |
| `enabled` | `db.Boolean` |  |
| `provider` | `db.String(60)` |  |
| `base_url` | `db.String(500)` |  |
| `sender` | `db.String(180)` |  |
| `smtp_host` | `db.String(220)` |  |
| `smtp_port` | `db.Integer` |  |
| `smtp_tls` | `db.Boolean` |  |
| `smtp_user` | `db.String(220)` |  |
| `secret_env_name` | `db.String(120)` |  |
| `updated_by` | `db.Integer` |  |
| `updated_at` | `db.DateTime` |  |

Foreign keys: `updated_by → user.id`.

## `communication_template (inferred)`

[CommunicationTemplate](../../ris/app.py#L997)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `code` | `db.String(80)` | unique=True,nullable=False |
| `name_en` | `db.String(180)` | nullable=False |
| `name_ar` | `db.String(180)` |  |
| `channel` | `db.String(30)` |  |
| `event_key` | `db.String(80)` |  |
| `subject_template` | `db.String(300)` |  |
| `body_template` | `db.Text` |  |
| `active` | `db.Boolean` |  |
| `created_by` | `db.Integer` |  |
| `updated_at` | `db.DateTime` |  |

Foreign keys: `created_by → user.id`.

## `company_legal_profile (inferred)`

[CompanyLegalProfile](../../ris/app.py#L881)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `branch_id` | `db.Integer` | unique=True |
| `legal_name` | `db.String(200)` |  |
| `commercial_register` | `db.String(120)` |  |
| `tax_card` | `db.String(120)` |  |
| `tax_number` | `db.String(120)` |  |
| `phone1` | `db.String(80)` |  |
| `phone2` | `db.String(80)` |  |
| `email` | `db.String(180)` |  |
| `website` | `db.String(180)` |  |
| `address` | `db.String(400)` |  |
| `logo_path` | `db.String(500)` |  |
| `receipt_note_ar` | `db.Text` |  |
| `receipt_note_en` | `db.Text` |  |

Foreign keys: `branch_id → branch.id`.

## `company_profile (inferred)`

[CompanyProfile](../../ris/app.py#L2155)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `name_en` | `db.String(180)` |  |
| `name_ar` | `db.String(180)` |  |
| `address_en` | `db.String(255)` |  |
| `address_ar` | `db.String(255)` |  |
| `phone` | `db.String(80)` |  |
| `mobile` | `db.String(80)` |  |
| `email` | `db.String(180)` |  |
| `website` | `db.String(180)` |  |
| `logo_path` | `db.String(500)` |  |
| `updated_at` | `db.DateTime` |  |

## `consumable (inferred)`

[Consumable](../../ris/app.py#L1731)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `code` | `db.String(40)` | unique=True,nullable=False |
| `name` | `db.String(160)` | nullable=False |
| `name_en` | `db.String(160)` |  |
| `name_ar` | `db.String(160)` |  |
| `barcode` | `db.String(80)` |  |
| `category` | `db.String(100)` |  |
| `unit` | `db.String(40)` |  |
| `stock_qty` | `db.Float` |  |
| `reorder_level` | `db.Float` |  |
| `unit_cost` | `db.Float` |  |
| `selling_price` | `db.Float` |  |
| `expiry_tracking` | `db.Boolean` |  |
| `active` | `db.Boolean` |  |

## `contract (inferred)`

[Contract](../../ris/app.py#L1712)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `code` | `db.String(40)` | unique=True,nullable=False |
| `name` | `db.String(160)` | nullable=False |
| `patient_share_percent` | `db.Float` |  |
| `discount_percent` | `db.Float` |  |
| `approval_required` | `db.Boolean` |  |
| `active` | `db.Boolean` |  |

## `contract_price (inferred)`

[ContractPrice](../../ris/app.py#L1721)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `contract_id` | `db.Integer` | nullable=False |
| `procedure_id` | `db.Integer` | nullable=False |
| `price` | `db.Float` | nullable=False |
| `patient_share_percent` | `db.Float` |  |

Foreign keys: `contract_id → contract.id`, `procedure_id → procedure.id`.

## `coordinator_task`

[CoordinatorTask](../../ris/app.py#L2421)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `report_id` | `db.Integer` | nullable=False |
| `assigned_to` | `db.Integer` |  |
| `status` | `db.String(40)` |  |
| `doctor_note` | `db.Text` |  |
| `coordinator_note` | `db.Text` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |
| `started_at` | `db.DateTime` |  |
| `completed_at` | `db.DateTime` |  |
| `returned_at` | `db.DateTime` |  |

Foreign keys: `order_id → order.id`, `report_id → report.id`, `assigned_to → user.id`.

## `correction_execution`

[CorrectionExecution](../../ris/app.py#L2494)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `correction_request_id` | `db.Integer` | nullable=False,unique=True |
| `order_id` | `db.Integer` | nullable=False |
| `branch_id` | `db.Integer` | nullable=True |
| `execution_type` | `db.String(40)` | nullable=False |
| `status` | `db.String(40)` | nullable=False |
| `state_version` | `db.Integer` | nullable=False |
| `claimed_by` | `db.Integer` | nullable=True |
| `executed_by` | `db.Integer` | nullable=True |
| `request_snapshot_json` | `db.Text` | nullable=False |
| `preflight_snapshot_json` | `db.Text` | nullable=False |
| `result_snapshot_json` | `db.Text` | nullable=False |
| `confirmation_token_hash` | `db.String(128)` | nullable=True |
| `confirmation_expires_at` | `db.DateTime` | nullable=True |
| `failure_code` | `db.String(80)` | nullable=True |
| `failure_message` | `db.Text` | nullable=True |
| `created_at` | `db.DateTime` | nullable=False |
| `updated_at` | `db.DateTime` | nullable=False |
| `claimed_at` | `db.DateTime` | nullable=True |
| `started_at` | `db.DateTime` | nullable=True |
| `executed_at` | `db.DateTime` | nullable=True |
| `verified_at` | `db.DateTime` | nullable=True |
| `failed_at` | `db.DateTime` | nullable=True |

Foreign keys: `correction_request_id → correction_request.id`, `order_id → order.id`, `branch_id → branch.id`, `claimed_by → user.id`, `executed_by → user.id`.

## `correction_request`

[CorrectionRequest](../../ris/app.py#L2442)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `branch_id` | `db.Integer` |  |
| `request_type` | `db.String(40)` | nullable=False |
| `status` | `db.String(30)` | nullable=False |
| `reason` | `db.Text` | nullable=False |
| `requested_by` | `db.Integer` | nullable=False |
| `assigned_to` | `db.Integer` |  |
| `review_note` | `db.Text` |  |
| `created_at` | `db.DateTime` | nullable=False |
| `updated_at` | `db.DateTime` | nullable=False |
| `reviewed_at` | `db.DateTime` |  |
| `closed_at` | `db.DateTime` |  |

Foreign keys: `order_id → order.id`, `branch_id → branch.id`, `requested_by → user.id`, `assigned_to → user.id`.

## `daily_closing (inferred)`

[DailyClosing](../../ris/app.py#L807)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `branch_id` | `db.Integer` | nullable=False |
| `closing_date` | `db.Date` | nullable=False |
| `cashier_user_id` | `db.Integer` |  |
| `expected_cash` | `db.Float` |  |
| `expected_card` | `db.Float` |  |
| `expected_other` | `db.Float` |  |
| `counted_cash` | `db.Float` |  |
| `counted_card` | `db.Float` |  |
| `counted_other` | `db.Float` |  |
| `difference` | `db.Float` |  |
| `notes` | `db.Text` |  |
| `status` | `db.String(20)` |  |
| `closed_by` | `db.Integer` |  |
| `closed_at` | `db.DateTime` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `branch_id → branch.id`, `cashier_user_id → user.id`, `closed_by → user.id`.

## `delivery_event (inferred)`

[DeliveryEvent](../../ris/app.py#L1779)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `item_type` | `db.String(30)` | nullable=False |
| `delivery_method` | `db.String(40)` |  |
| `recipient_name` | `db.String(160)` |  |
| `recipient_phone` | `db.String(40)` |  |
| `delivered_by` | `db.Integer` |  |
| `delivered_at` | `db.DateTime` |  |
| `notes` | `db.String(500)` |  |

Foreign keys: `order_id → order.id`.

## `demographic_override_audit (inferred)`

[DemographicOverrideAudit](../../ris/app.py#L1192)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `analysis_id` | `db.Integer` | nullable=False |
| `original_status` | `db.String(40)` |  |
| `override_reason` | `db.Text` | nullable=False |
| `overridden_by` | `db.Integer` | nullable=False |
| `overridden_at` | `db.DateTime` |  |

Foreign keys: `order_id → order.id`, `analysis_id → imaging_ai_analysis.id`, `overridden_by → user.id`.

## `device (inferred)`

[Device](../../ris/app.py#L348)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `branch_id` | `db.Integer` | nullable=False |
| `name` | `db.String(120)` | nullable=False |
| `modality` | `db.String(10)` | nullable=False |
| `ae_title` | `db.String(40)` | nullable=False |
| `ip` | `db.String(80)` |  |
| `port` | `db.Integer` |  |
| `room` | `db.String(80)` |  |
| `priority` | `db.Integer` |  |
| `active` | `db.Boolean` |  |
| `operational_status` | `db.String(30)` |  |
| `booking_enabled` | `db.Boolean` |  |
| `workday_start` | `db.String(5)` |  |
| `workday_end` | `db.String(5)` |  |

Foreign keys: `branch_id → branch.id`.

## `device_block (inferred)`

[DeviceBlock](../../ris/app.py#L1821)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `device_id` | `db.Integer` | nullable=False |
| `start_at` | `db.DateTime` | nullable=False |
| `end_at` | `db.DateTime` | nullable=False |
| `reason` | `db.String(160)` |  |

Foreign keys: `device_id → device.id`.

## `device_schedule (inferred)`

[DeviceSchedule](../../ris/app.py#L1810)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `device_id` | `db.Integer` | nullable=False |
| `weekday` | `db.Integer` | nullable=False |
| `start_time` | `db.String(5)` |  |
| `end_time` | `db.String(5)` |  |
| `break_start` | `db.String(5)` |  |
| `break_end` | `db.String(5)` |  |
| `active` | `db.Boolean` |  |

Foreign keys: `device_id → device.id`.

## `dicom_correction`

[DicomCorrection](../../ris/app.py#L2231)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `source_study_id` | `db.String(120)` | nullable=False,unique=True |
| `new_study_id` | `db.String(120)` |  |
| `new_uid` | `db.String(180)` |  |
| `order_id` | `db.Integer` | nullable=False |
| `actor_user_id` | `db.Integer` | nullable=False |
| `status` | `db.String(30)` | nullable=False |
| `reason` | `db.String(500)` | nullable=False |
| `before_json` | `db.Text` | nullable=False |
| `after_json` | `db.Text` | nullable=False |
| `error_code` | `db.String(80)` |  |
| `created_at` | `db.DateTime` | nullable=False |
| `finished_at` | `db.DateTime` |  |

Foreign keys: `order_id → order.id`.

## `dicom_destination`

[DicomDestination](../../ris/app.py#L2371)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `key` | `db.String(60)` | unique=True,nullable=False |
| `name` | `db.String(160)` | nullable=False |
| `ae_title` | `db.String(40)` | nullable=False |
| `host` | `db.String(120)` | nullable=False |
| `port` | `db.Integer` | nullable=False |
| `destination_type` | `db.String(30)` |  |
| `branch_id` | `db.Integer` |  |
| `active` | `db.Boolean` |  |
| `allow_manual_send` | `db.Boolean` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `branch_id → branch.id`.

## `dicom_endpoint`

[DicomEndpoint](../../ris/app.py#L330)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `branch_id` | `db.Integer` | nullable=False |
| `kind` | `db.String(20)` | nullable=False |
| `ae_title` | `db.String(16)` | nullable=False |
| `calling_ae` | `db.String(16)` | nullable=False |
| `host` | `db.String(253)` | nullable=False |
| `port` | `db.Integer` | nullable=False |
| `active` | `db.Boolean` | nullable=False |
| `echo_result` | `db.String(20)` | nullable=False |
| `echo_message` | `db.String(240)` | nullable=False |
| `echo_checked_at` | `db.DateTime` |  |
| `echo_elapsed_ms` | `db.Integer` |  |

Foreign keys: `branch_id → branch.id`.

## `dictionary_entry (inferred)`

[DictionaryEntry](../../ris/app.py#L416)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `key` | `db.String(160)` | unique=True,nullable=False |
| `module` | `db.String(80)` |  |
| `label_en` | `db.String(255)` | nullable=False |
| `label_ar` | `db.String(255)` | nullable=False |
| `active` | `db.Boolean` |  |

## `discount_approval_request (inferred)`

[DiscountApprovalRequest](../../ris/app.py#L777)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `requested_percent` | `db.Float` |  |
| `requested_amount` | `db.Float` |  |
| `reason` | `db.String(500)` | nullable=False |
| `status` | `db.String(20)` |  |
| `requested_by` | `db.Integer` | nullable=False |
| `decided_by` | `db.Integer` |  |
| `decision_notes` | `db.String(500)` |  |
| `requested_at` | `db.DateTime` |  |
| `decided_at` | `db.DateTime` |  |

Foreign keys: `order_id → order.id`, `requested_by → user.id`, `decided_by → user.id`.

## `discount_policy (inferred)`

[DiscountPolicy](../../ris/app.py#L744)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `name` | `db.String(160)` | nullable=False |
| `role_code` | `db.String(80)` |  |
| `user_id` | `db.Integer` |  |
| `branch_id` | `db.Integer` |  |
| `procedure_id` | `db.Integer` |  |
| `contract_id` | `db.Integer` |  |
| `max_direct_percent` | `db.Float` |  |
| `max_request_percent` | `db.Float` |  |
| `active` | `db.Boolean` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `user_id → user.id`, `branch_id → branch.id`, `procedure_id → procedure.id`, `contract_id → contract.id`, `created_by → user.id`.

## `discovered_dicom_node`

[DiscoveredDicomNode](../../ris/app.py#L2351)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `ae_title` | `db.String(80)` | nullable=False |
| `host` | `db.String(120)` |  |
| `port` | `db.Integer` |  |
| `node_type` | `db.String(30)` |  |
| `modality` | `db.String(30)` |  |
| `source_description` | `db.String(255)` |  |
| `branch_id` | `db.Integer` |  |
| `status` | `db.String(30)` |  |
| `studies_seen` | `db.Integer` |  |
| `first_seen_at` | `db.DateTime` |  |
| `last_seen_at` | `db.DateTime` |  |
| `approved_at` | `db.DateTime` |  |
| `approved_by` | `db.Integer` |  |
| `notes` | `db.Text` |  |

Foreign keys: `branch_id → branch.id`.

## `doctor_assignment_profile (inferred)`

[DoctorAssignmentProfile](../../ris/app.py#L1830)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `user_id` | `db.Integer` | nullable=False,unique=True |
| `modalities` | `db.String(200)` |  |
| `specialties` | `db.String(300)` |  |
| `branches` | `db.String(200)` |  |
| `max_active_cases` | `db.Integer` |  |
| `auto_assign` | `db.Boolean` |  |
| `available` | `db.Boolean` |  |
| `priority_weight` | `db.Integer` |  |

Foreign keys: `user_id → user.id`.

## `doctor_availability_state (inferred)`

[DoctorAvailabilityState](../../ris/app.py#L1202)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `user_id` | `db.Integer` | unique=True,nullable=False |
| `state` | `db.String(30)` |  |
| `busy_until` | `db.DateTime` |  |
| `last_seen_at` | `db.DateTime` |  |
| `updated_at` | `db.DateTime` |  |

Foreign keys: `user_id → user.id`.

## `doctor_signing_key`

[DoctorSigningKey](../../ris/app.py#L3052)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `user_id` | `db.Integer` | nullable=False |
| `key_id` | `db.String(64)` | nullable=False,unique=True |
| `algorithm` | `db.String(50)` | nullable=False |
| `public_key` | `db.Text` | nullable=False |
| `encrypted_private_key` | `db.Text` | nullable=False |
| `active` | `db.Boolean` | nullable=False |
| `created_at` | `db.DateTime` | nullable=False |
| `revoked_at` | `db.DateTime` |  |
| `revoked_reason` | `db.String(255)` |  |

Foreign keys: `user_id → user.id`.

## `doctor_word_template (inferred)`

[DoctorWordTemplate](../../ris/app.py#L907)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `owner_user_id` | `db.Integer` | nullable=False |
| `name` | `db.String(180)` | nullable=False |
| `modality` | `db.String(30)` |  |
| `procedure_id` | `db.Integer` |  |
| `visibility` | `db.String(30)` |  |
| `file_path` | `db.String(600)` | nullable=False |
| `original_name` | `db.String(255)` |  |
| `active` | `db.Boolean` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `owner_user_id → user.id`, `procedure_id → procedure.id`.

## `document_match (inferred)`

[DocumentMatch](../../ris/app.py#L533)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `document_id` | `db.Integer` | nullable=False |
| `field_name` | `db.String(80)` | nullable=False |
| `extracted_value` | `db.Text` |  |
| `ris_value` | `db.Text` |  |
| `confidence` | `db.Float` |  |
| `match_status` | `db.String(30)` |  |

Foreign keys: `document_id → patient_document.id`.

## `erp_item_mapping (inferred)`

[ERPItemMapping](../../ris/app.py#L2797)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `consumable_id` | `db.Integer` | nullable=False,unique=True |
| `erp_item_code` | `db.String(120)` | nullable=False |
| `erp_warehouse_code` | `db.String(120)` |  |
| `active` | `db.Boolean` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `consumable_id → consumable.id`.

## `erp_sync_queue (inferred)`

[ERPSyncQueue](../../ris/app.py#L2806)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `event_type` | `db.String(80)` | nullable=False |
| `reference_type` | `db.String(80)` |  |
| `reference_id` | `db.String(120)` |  |
| `payload_json` | `db.Text` |  |
| `status` | `db.String(30)` |  |
| `attempts` | `db.Integer` |  |
| `last_error` | `db.Text` |  |
| `created_at` | `db.DateTime` |  |
| `sent_at` | `db.DateTime` |  |

## `event_outbox (inferred)`

[EventOutbox](../../ris/app.py#L2143)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `event_type` | `db.String(80)` | nullable=False |
| `entity_type` | `db.String(80)` | nullable=False |
| `entity_id` | `db.String(120)` | nullable=False |
| `payload_json` | `db.Text` |  |
| `status` | `db.String(20)` |  |
| `attempts` | `db.Integer` |  |
| `last_error` | `db.Text` |  |
| `created_at` | `db.DateTime` |  |
| `processed_at` | `db.DateTime` |  |

## `external_center_doctor`

[ExternalCenterDoctor](../../ris/app.py#L2301)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `center_id` | `db.Integer` | nullable=False |
| `doctor_user_id` | `db.Integer` | nullable=False |
| `active` | `db.Boolean` | nullable=False |

Foreign keys: `center_id → external_reporting_center.id`, `doctor_user_id → user.id`.

## `external_intake_case`

[ExternalIntakeCase](../../ris/app.py#L2312)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `center_id` | `db.Integer` | nullable=False |
| `inbox_id` | `db.Integer` | unique=True,nullable=False |
| `order_id` | `db.Integer` | unique=True |
| `status` | `db.String(30)` | nullable=False |
| `review_note` | `db.String(500)` | nullable=False |
| `expected_patient_id` | `db.String(80)` | nullable=False |
| `expected_patient_name` | `db.String(180)` | nullable=False |
| `expected_dob` | `db.String(8)` | nullable=False |
| `expected_sex` | `db.String(1)` | nullable=False |
| `expected_accession` | `db.String(120)` | nullable=False |
| `dicom_patient_id` | `db.String(80)` | nullable=False |
| `dicom_patient_name` | `db.String(180)` | nullable=False |
| `dicom_dob` | `db.String(8)` | nullable=False |
| `dicom_sex` | `db.String(1)` | nullable=False |
| `dicom_accession` | `db.String(120)` | nullable=False |
| `demographic_status` | `db.String(30)` | nullable=False |
| `demographic_score` | `db.Float` | nullable=False |
| `demographic_checks_json` | `db.Text` | nullable=False |
| `demographic_facts_sha256` | `db.String(64)` | nullable=False |
| `demographic_verified_by` | `db.Integer` |  |
| `demographic_verified_at` | `db.DateTime` |  |
| `demographic_override_approved` | `db.Boolean` | nullable=False |
| `demographic_override_reason` | `db.String(500)` | nullable=False |
| `demographic_override_by` | `db.Integer` |  |
| `demographic_override_at` | `db.DateTime` |  |
| `demographic_override_facts_sha256` | `db.String(64)` | nullable=False |
| `reviewed_by` | `db.Integer` |  |
| `reviewed_at` | `db.DateTime` |  |
| `queued_at` | `db.DateTime` |  |
| `created_at` | `db.DateTime` | nullable=False |

Foreign keys: `center_id → external_reporting_center.id`, `inbox_id → pacs_study_inbox.id`, `order_id → order.id`, `demographic_verified_by → user.id`, `demographic_override_by → user.id`, `reviewed_by → user.id`.

## `external_prior_study (inferred)`

[ExternalPriorStudy](../../ris/app.py#L952)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `patient_id` | `db.Integer` | nullable=False |
| `linked_order_id` | `db.Integer` |  |
| `source_type` | `db.String(30)` |  |
| `study_date` | `db.Date` |  |
| `modality` | `db.String(30)` |  |
| `study_description` | `db.String(300)` |  |
| `external_patient_name` | `db.String(200)` |  |
| `external_patient_id` | `db.String(120)` |  |
| `external_dob` | `db.String(40)` |  |
| `file_path` | `db.String(700)` | nullable=False |
| `original_name` | `db.String(300)` |  |
| `dicom_metadata_json` | `db.Text` |  |
| `match_status` | `db.String(30)` |  |
| `match_score` | `db.Float` |  |
| `imported_to_pacs` | `db.Boolean` |  |
| `uploaded_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `patient_id → patient.id`, `linked_order_id → order.id`, `uploaded_by → user.id`.

## `external_reporting_center`

[ExternalReportingCenter](../../ris/app.py#L2280)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `code` | `db.String(40)` | unique=True,nullable=False |
| `name` | `db.String(160)` | nullable=False |
| `ae_title` | `db.String(80)` | unique=True,nullable=False |
| `receiving_enabled` | `db.Boolean` | nullable=False |
| `assignment_enabled` | `db.Boolean` | nullable=False |
| `auto_queue` | `db.Boolean` | nullable=False |
| `default_priority` | `db.String(20)` | nullable=False |
| `required_documents` | `db.Boolean` | nullable=False |
| `billing_enabled` | `db.Boolean` | nullable=False |
| `billing_contract_id` | `db.Integer` |  |
| `default_report_fee` | `db.Float` | nullable=False |
| `active` | `db.Boolean` | nullable=False |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` | nullable=False |
| `updated_at` | `db.DateTime` | nullable=False |

Foreign keys: `billing_contract_id → contract.id`, `created_by → user.id`.

## `external_reporting_setting`

[ExternalReportingSetting](../../ris/app.py#L2272)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `enabled` | `db.Boolean` | nullable=False |
| `updated_by` | `db.Integer` |  |
| `updated_at` | `db.DateTime` | nullable=False |

Foreign keys: `updated_by → user.id`.

## `failover_event`

[FailoverEvent](../../ris/app.py#L2725)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `policy_id` | `db.Integer` | nullable=False |
| `action` | `db.String(30)` | nullable=False |
| `status` | `db.String(30)` |  |
| `requested_by` | `db.Integer` |  |
| `requested_at` | `db.DateTime` |  |
| `completed_at` | `db.DateTime` |  |
| `notes` | `db.Text` |  |

Foreign keys: `policy_id → replication_policy.id`.

## `field_rule (inferred)`

[FieldRule](../../ris/app.py#L567)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `field_key` | `db.String(100)` | unique=True,nullable=False |
| `label_en` | `db.String(160)` |  |
| `label_ar` | `db.String(160)` |  |
| `data_type` | `db.String(30)` |  |
| `min_length` | `db.Integer` |  |
| `max_length` | `db.Integer` |  |
| `exact_length` | `db.Integer` |  |
| `required` | `db.Boolean` |  |
| `visible` | `db.Boolean` |  |
| `read_only` | `db.Boolean` |  |
| `allow_spaces` | `db.Boolean` |  |
| `regex_pattern` | `db.String(500)` |  |
| `updated_by` | `db.Integer` |  |
| `updated_at` | `db.DateTime` |  |

Foreign keys: `updated_by → user.id`.

## `financial_entry (inferred)`

[FinancialEntry](../../ris/app.py#L2818)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `entry_date` | `db.Date` | nullable=False |
| `branch_id` | `db.Integer` |  |
| `entry_type` | `db.String(30)` | nullable=False |
| `category` | `db.String(100)` |  |
| `description` | `db.String(255)` |  |
| `amount` | `db.Numeric(14, 2)` | nullable=False |
| `payment_method` | `db.String(30)` |  |
| `device_id` | `db.Integer` |  |
| `user_id` | `db.Integer` |  |
| `consumable_id` | `db.Integer` |  |
| `quantity` | `db.Float` |  |
| `reference_no` | `db.String(120)` |  |
| `status` | `db.String(30)` |  |
| `notes` | `db.Text` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `branch_id → branch.id`, `device_id → device.id`, `user_id → user.id`, `consumable_id → consumable.id`.

## `imaging_ai_analysis (inferred)`

[ImagingAIAnalysis](../../ris/app.py#L1169)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `provider_key` | `db.String(60)` |  |
| `model_name` | `db.String(180)` |  |
| `study_instance_uid` | `db.String(180)` |  |
| `accession` | `db.String(120)` |  |
| `status` | `db.String(40)` |  |
| `demographic_status` | `db.String(40)` |  |
| `demographic_score` | `db.Float` |  |
| `demographic_details_json` | `db.Text` |  |
| `structured_findings_json` | `db.Text` |  |
| `summary_text` | `db.Text` |  |
| `uncertainty_text` | `db.Text` |  |
| `raw_response_json` | `db.Text` |  |
| `requested_by` | `db.Integer` |  |
| `requested_at` | `db.DateTime` |  |
| `completed_at` | `db.DateTime` |  |
| `reviewed_by` | `db.Integer` |  |
| `reviewed_at` | `db.DateTime` |  |
| `error_text` | `db.Text` |  |

Foreign keys: `order_id → order.id`, `requested_by → user.id`, `reviewed_by → user.id`.

## `imaging_ai_provider (inferred)`

[ImagingAIProvider](../../ris/app.py#L1030)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `provider_key` | `db.String(60)` | unique=True,nullable=False |
| `enabled` | `db.Boolean` |  |
| `base_url` | `db.String(500)` |  |
| `model_name` | `db.String(180)` |  |
| `modalities` | `db.String(120)` |  |
| `timeout_seconds` | `db.Integer` |  |
| `secret_env_name` | `db.String(120)` |  |
| `updated_by` | `db.Integer` |  |
| `updated_at` | `db.DateTime` |  |

Foreign keys: `updated_by → user.id`.

## `insurance_approval_event (inferred)`

[InsuranceApprovalEvent](../../ris/app.py#L2032)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `approval_request_id` | `db.Integer` | nullable=False |
| `event_type` | `db.String(60)` | nullable=False |
| `old_status` | `db.String(30)` |  |
| `new_status` | `db.String(30)` |  |
| `message` | `db.Text` |  |
| `user_id` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `approval_request_id → insurance_approval_request.id`, `user_id → user.id`.

## `insurance_approval_request (inferred)`

[InsuranceApprovalRequest](../../ris/app.py#L1977)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `method` | `db.String(30)` |  |
| `status` | `db.String(30)` |  |
| `approval_no` | `db.String(120)` |  |
| `payer_name` | `db.String(180)` |  |
| `member_no` | `db.String(120)` |  |
| `requested_at` | `db.DateTime` |  |
| `submitted_at` | `db.DateTime` |  |
| `decided_at` | `db.DateTime` |  |
| `last_checked_at` | `db.DateTime` |  |
| `next_check_at` | `db.DateTime` |  |
| `notes` | `db.Text` |  |
| `last_error` | `db.Text` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |
| `updated_at` | `db.DateTime` |  |

Foreign keys: `order_id → order.id`, `created_by → user.id`.

## `insurance_portal_account (inferred)`

[InsurancePortalAccount](../../ris/app.py#L2072)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `branch_id` | `db.Integer` | nullable=False |
| `payer_name` | `db.String(180)` | nullable=False |
| `portal_url` | `db.String(500)` |  |
| `login_url` | `db.String(500)` |  |
| `portal_type` | `db.String(40)` |  |
| `username` | `db.String(180)` |  |
| `credential_ref` | `db.String(255)` |  |
| `requires_otp` | `db.Boolean` |  |
| `workflow_mode` | `db.String(40)` |  |
| `login_notes` | `db.Text` |  |
| `workflow_notes` | `db.Text` |  |
| `training_notes` | `db.Text` |  |
| `selectors_json` | `db.Text` |  |
| `automation_config_json` | `db.Text` |  |
| `last_success_at` | `db.DateTime` |  |
| `last_error_at` | `db.DateTime` |  |
| `last_error` | `db.Text` |  |
| `enabled` | `db.Boolean` |  |
| `telegram_enabled` | `db.Boolean` |  |
| `email_enabled` | `db.Boolean` |  |
| `automation_enabled` | `db.Boolean` |  |
| `created_at` | `db.DateTime` |  |
| `updated_at` | `db.DateTime` |  |

Foreign keys: `branch_id → branch.id`.

## `inventory_batch (inferred)`

[InventoryBatch](../../ris/app.py#L2766)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `consumable_id` | `db.Integer` | nullable=False |
| `batch_no` | `db.String(120)` | nullable=False |
| `expiry_date` | `db.Date` |  |
| `qty` | `db.Float` |  |
| `unit_cost` | `db.Float` |  |
| `branch_id` | `db.Integer` |  |
| `active` | `db.Boolean` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `consumable_id → consumable.id`, `branch_id → branch.id`.

## `inventory_item (inferred)`

[InventoryItem](../../ris/app.py#L601)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `code` | `db.String(80)` | nullable=False,unique=True |
| `name` | `db.String(220)` | nullable=False |
| `category` | `db.String(100)` |  |
| `unit` | `db.String(40)` |  |
| `track_lot` | `db.Boolean` |  |
| `track_expiry` | `db.Boolean` |  |
| `default_cost` | `db.Float` |  |
| `active` | `db.Boolean` |  |
| `created_at` | `db.DateTime` |  |

## `inventory_lot (inferred)`

[InventoryLot](../../ris/app.py#L613)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `item_id` | `db.Integer` | nullable=False |
| `warehouse_id` | `db.Integer` | nullable=False |
| `lot_no` | `db.String(120)` |  |
| `expiry_date` | `db.Date` |  |
| `unit_cost` | `db.Float` |  |
| `qty_on_hand` | `db.Float` |  |
| `qty_reserved` | `db.Float` |  |

Foreign keys: `item_id → inventory_item.id`, `warehouse_id → warehouse.id`.

## `journey_event (inferred)`

[JourneyEvent](../../ris/app.py#L464)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `stage` | `db.String(50)` | nullable=False |
| `entered_at` | `db.DateTime` |  |
| `completed_at` | `db.DateTime` |  |
| `user_id` | `db.Integer` |  |
| `notes` | `db.String(500)` |  |

Foreign keys: `order_id → order.id`, `user_id → user.id`.

## `label_template (inferred)`

[LabelTemplate](../../ris/app.py#L1542)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `name` | `db.String(160)` | nullable=False |
| `branch_id` | `db.Integer` |  |
| `width_mm` | `db.Integer` |  |
| `height_mm` | `db.Integer` |  |
| `layout_json` | `db.Text` |  |
| `active` | `db.Boolean` |  |
| `is_default` | `db.Boolean` |  |

Foreign keys: `branch_id → branch.id`.

## `notification_escalation_rule (inferred)`

[NotificationEscalationRule](../../ris/app.py#L1522)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `event_type` | `db.String(80)` | nullable=False |
| `severity` | `db.String(20)` |  |
| `first_role` | `db.String(60)` |  |
| `escalate_role` | `db.String(60)` |  |
| `escalate_after_min` | `db.Integer` |  |
| `channels` | `db.String(120)` |  |
| `active` | `db.Boolean` |  |

## `notification_event (inferred)`

[NotificationEvent](../../ris/app.py#L2903)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `channel` | `db.String(30)` | nullable=False |
| `recipient` | `db.String(255)` |  |
| `status` | `db.String(30)` |  |
| `attempts` | `db.Integer` |  |
| `last_error` | `db.Text` |  |
| `created_at` | `db.DateTime` |  |
| `sent_at` | `db.DateTime` |  |

Foreign keys: `order_id → order.id`.

## `nursing_consumable_entry (inferred)`

[NursingConsumableEntry](../../ris/app.py#L2877)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `consumable_id` | `db.Integer` | nullable=False |
| `default_qty` | `db.Float` |  |
| `actual_qty` | `db.Float` |  |
| `confirmed` | `db.Boolean` |  |
| `confirmed_by` | `db.Integer` |  |
| `confirmed_at` | `db.DateTime` |  |
| `notes` | `db.String(500)` |  |
| `corrected_by` | `db.Integer` |  |
| `corrected_at` | `db.DateTime` |  |
| `correction_reason` | `db.String(500)` |  |

Foreign keys: `order_id → order.id`, `consumable_id → consumable.id`.

## `ocr_provider_setting (inferred)`

[OCRProviderSetting](../../ris/app.py#L1616)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `provider_key` | `db.String(60)` | unique=True,nullable=False |
| `enabled` | `db.Boolean` |  |
| `base_url` | `db.String(500)` |  |
| `model_name` | `db.String(180)` |  |
| `timeout_seconds` | `db.Integer` |  |
| `secret_env_name` | `db.String(120)` |  |
| `validation_status` | `db.String(40)` |  |
| `validation_details` | `db.Text` |  |
| `validation_config_hash` | `db.String(64)` |  |
| `validation_latency_ms` | `db.Integer` |  |
| `validated_by` | `db.Integer` |  |
| `validated_at` | `db.DateTime` |  |
| `updated_by` | `db.Integer` |  |
| `updated_at` | `db.DateTime` |  |

Foreign keys: `validated_by → user.id`, `updated_by → user.id`.

## `order (inferred)`

[Order](../../ris/app.py#L1904)

| Column | Declared type | Flags |
|---|---|---|
| `assignment_visit_id` | `db.String(36)` |  |
| `assignment_special_code` | `db.String(80)` |  |
| `id` | `db.Integer` | primary_key=True |
| `accession` | `db.String(40)` | unique=True,nullable=False |
| `patient_id` | `db.Integer` | nullable=False |
| `modality` | `db.String(8)` | nullable=False |
| `procedure` | `db.String(120)` | nullable=False |
| `station_ae` | `db.String(40)` |  |
| `scheduled` | `db.DateTime` | nullable=False |
| `status` | `db.String(30)` |  |
| `procedure_id` | `db.Integer` |  |
| `branch_id` | `db.Integer` |  |
| `device_id` | `db.Integer` |  |
| `contract_id` | `db.Integer` |  |
| `referring_doctor_id` | `db.Integer` |  |
| `gross_price` | `db.Float` |  |
| `contract_price` | `db.Float` |  |
| `patient_share` | `db.Float` |  |
| `company_share` | `db.Float` |  |
| `paid_amount` | `db.Float` |  |
| `report_delivered` | `db.Boolean` |  |
| `images_delivered` | `db.Boolean` |  |
| `report_delivered_at` | `db.DateTime` |  |
| `images_delivered_at` | `db.DateTime` |  |
| `approval_no` | `db.String(80)` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |
| `priority` | `db.String(20)` |  |
| `assigned_doctor_id` | `db.Integer` |  |
| `assigned_at` | `db.DateTime` |  |
| `exam_status` | `db.String(30)` |  |
| `exam_started_at` | `db.DateTime` |  |
| `exam_completed_at` | `db.DateTime` |  |
| `pacs_image_count` | `db.Integer` |  |
| `pacs_status` | `db.String(30)` |  |
| `pacs_last_seen_at` | `db.DateTime` |  |
| `pacs_last_change_at` | `db.DateTime` |  |
| `pacs_study_id` | `db.String(120)` |  |
| `study_instance_uid` | `db.String(180)` |  |

Foreign keys: `assignment_visit_id → assignment_visit.id`, `patient_id → patient.id`, `procedure_id → procedure.id`, `branch_id → branch.id`, `device_id → device.id`, `contract_id → contract.id`, `referring_doctor_id → referring_doctor.id`, `assigned_doctor_id → user.id`.

## `order_consumable (inferred)`

[OrderConsumable](../../ris/app.py#L2865)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `consumable_id` | `db.Integer` | nullable=False |
| `qty` | `db.Float` | nullable=False |
| `source` | `db.String(30)` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `order_id → order.id`, `consumable_id → consumable.id`.

## `order_consumable_usage (inferred)`

[OrderConsumableUsage](../../ris/app.py#L649)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `warehouse_id` | `db.Integer` | nullable=False |
| `item_id` | `db.Integer` | nullable=False |
| `lot_id` | `db.Integer` |  |
| `qty` | `db.Float` |  |
| `usage_type` | `db.String(30)` |  |
| `source` | `db.String(30)` |  |
| `reason` | `db.String(500)` |  |
| `unit_cost` | `db.Float` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `order_id → order.id`, `warehouse_id → warehouse.id`, `item_id → inventory_item.id`, `lot_id → inventory_lot.id`, `created_by → user.id`.

## `order_discount (inferred)`

[OrderDiscount](../../ris/app.py#L762)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `discount_type` | `db.String(30)` |  |
| `percent` | `db.Float` |  |
| `amount` | `db.Float` |  |
| `base_amount` | `db.Float` |  |
| `reason` | `db.String(500)` | nullable=False |
| `status` | `db.String(20)` |  |
| `requested_by` | `db.Integer` |  |
| `approved_by` | `db.Integer` |  |
| `approved_at` | `db.DateTime` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `order_id → order.id`, `requested_by → user.id`, `approved_by → user.id`.

## `order_performing_doctor (inferred)`

[OrderPerformingDoctor](../../ris/app.py#L733)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False,unique=True |
| `doctor_user_id` | `db.Integer` | nullable=False |
| `source` | `db.String(30)` |  |
| `assigned_by` | `db.Integer` |  |
| `assigned_at` | `db.DateTime` |  |
| `notes` | `db.String(500)` |  |

Foreign keys: `order_id → order.id`, `doctor_user_id → user.id`, `assigned_by → user.id`.

## `pacs_exam_link`

[PacsExamLink](../../ris/app.py#L2203)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `orthanc_study_id` | `db.String(120)` | nullable=False |
| `order_id` | `db.Integer` | nullable=False |
| `link_role` | `db.String(20)` | nullable=False |
| `active` | `db.Boolean` | nullable=False |
| `reason` | `db.String(500)` | nullable=False |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` | nullable=False |
| `removed_by` | `db.Integer` |  |
| `removed_at` | `db.DateTime` |  |

Foreign keys: `order_id → order.id`.

## `pacs_resolution_event`

[PacsResolutionEvent](../../ris/app.py#L2217)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `event_type` | `db.String(50)` | nullable=False |
| `old_orthanc_study_id` | `db.String(120)` | nullable=False |
| `new_orthanc_study_id` | `db.String(120)` | nullable=False |
| `old_study_instance_uid` | `db.String(180)` | nullable=False |
| `new_study_instance_uid` | `db.String(180)` | nullable=False |
| `reason` | `db.String(500)` | nullable=False |
| `actor_user_id` | `db.Integer` |  |
| `created_at` | `db.DateTime` | nullable=False |

Foreign keys: `order_id → order.id`.

## `pacs_routing_rule`

[PacsRoutingRule](../../ris/app.py#L2386)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `name` | `db.String(160)` | nullable=False |
| `destination_id` | `db.Integer` | nullable=False |
| `branch_id` | `db.Integer` |  |
| `modality` | `db.String(30)` |  |
| `source_ae` | `db.String(80)` |  |
| `min_priority` | `db.String(20)` |  |
| `active` | `db.Boolean` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `destination_id → dicom_destination.id`, `branch_id → branch.id`.

## `pacs_study_inbox`

[PacsStudyInbox](../../ris/app.py#L2249)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `orthanc_study_id` | `db.String(120)` | unique=True,nullable=False |
| `study_instance_uid` | `db.String(180)` | unique=True |
| `order_id` | `db.Integer` |  |
| `pacs_patient_id` | `db.String(80)` |  |
| `pacs_patient_name` | `db.String(180)` |  |
| `accession` | `db.String(120)` |  |
| `modality` | `db.String(30)` |  |
| `study_description` | `db.String(255)` |  |
| `source_ae` | `db.String(80)` |  |
| `image_count` | `db.Integer` |  |
| `state` | `db.String(40)` |  |
| `match_method` | `db.String(60)` |  |
| `error_text` | `db.Text` |  |
| `first_seen_at` | `db.DateTime` |  |
| `last_seen_at` | `db.DateTime` |  |

Foreign keys: `order_id → order.id`.

## `pacs_study_match (inferred)`

[PacsStudyMatch](../../ris/app.py#L2184)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `orthanc_study_id` | `db.String(120)` | unique=True,nullable=False |
| `order_id` | `db.Integer` | nullable=False |
| `match_method` | `db.String(40)` |  |
| `confidence` | `db.String(20)` |  |
| `pacs_patient_id` | `db.String(80)` |  |
| `pacs_patient_name` | `db.String(180)` |  |
| `pacs_accession` | `db.String(120)` |  |
| `confirmed_by` | `db.Integer` |  |
| `confirmed_at` | `db.DateTime` |  |
| `notes` | `db.String(500)` |  |
| `is_current` | `db.Boolean` | nullable=False |
| `superseded_at` | `db.DateTime` |  |
| `superseded_by` | `db.Integer` |  |
| `superseded_reason` | `db.String(500)` | nullable=False |

Foreign keys: `order_id → order.id`.

## `pacs_transfer_job`

[PacsTransferJob](../../ris/app.py#L2400)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` |  |
| `orthanc_study_id` | `db.String(120)` | nullable=False |
| `destination_id` | `db.Integer` | nullable=False |
| `reason` | `db.String(40)` |  |
| `status` | `db.String(30)` |  |
| `attempts` | `db.Integer` |  |
| `last_error` | `db.Text` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |
| `started_at` | `db.DateTime` |  |
| `completed_at` | `db.DateTime` |  |
| `verified_at` | `db.DateTime` |  |
| `cancelled_at` | `db.DateTime` |  |
| `progress_total` | `db.Integer` |  |
| `progress_sent` | `db.Integer` |  |

Foreign keys: `order_id → order.id`, `destination_id → dicom_destination.id`.

## `patient (inferred)`

[Patient](../../ris/app.py#L316)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `patient_id` | `db.String(40)` | unique=True,nullable=False |
| `name` | `db.String(120)` | nullable=False |
| `dob` | `db.String(8)` |  |
| `dob_estimated` | `db.Boolean` | nullable=False |
| `sex` | `db.String(1)` |  |
| `phone` | `db.String(30)` |  |
| `national_id` | `db.String(30)` |  |
| `address` | `db.String(255)` |  |
| `email` | `db.String(180)` |  |
| `created_at` | `db.DateTime` |  |
| `worklist_name` | `db.String(180)` |  |

## `patient_alert (inferred)`

[PatientAlert](../../ris/app.py#L871)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `patient_id` | `db.Integer` | nullable=False |
| `alert_type` | `db.String(50)` | nullable=False |
| `title` | `db.String(180)` |  |
| `notes` | `db.Text` |  |
| `amount` | `db.Float` |  |
| `branch_id` | `db.Integer` |  |
| `status` | `db.String(20)` |  |
| `created_by` | `db.Integer` |  |
| `resolved_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |
| `resolved_at` | `db.DateTime` |  |

Foreign keys: `patient_id → patient.id`, `branch_id → branch.id`, `created_by → user.id`, `resolved_by → user.id`.

## `patient_communication (inferred)`

[PatientCommunication](../../ris/app.py#L1010)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `patient_id` | `db.Integer` | nullable=False |
| `order_id` | `db.Integer` |  |
| `receipt_id` | `db.Integer` |  |
| `channel` | `db.String(30)` | nullable=False |
| `recipient` | `db.String(240)` | nullable=False |
| `template_code` | `db.String(80)` |  |
| `subject` | `db.String(300)` |  |
| `body` | `db.Text` |  |
| `status` | `db.String(30)` |  |
| `provider_message_id` | `db.String(300)` |  |
| `error_text` | `db.Text` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |
| `sent_at` | `db.DateTime` |  |

Foreign keys: `patient_id → patient.id`, `order_id → order.id`, `receipt_id → receipt.id`, `created_by → user.id`.

## `patient_demographics_correction`

[PatientDemographicsCorrection](../../ris/app.py#L2481)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `correction_request_id` | `db.Integer` | nullable=False,unique=True |
| `patient_id` | `db.Integer` | nullable=False |
| `field_name` | `db.String(40)` | nullable=False |
| `old_value` | `db.Text` | nullable=False |
| `proposed_value` | `db.Text` | nullable=False |
| `snapshot_hash` | `db.String(64)` | nullable=False |
| `impact_json` | `db.Text` | nullable=False |

Foreign keys: `correction_request_id → correction_request.id`, `patient_id → patient.id`.

## `patient_demographics_extra (inferred)`

[PatientDemographicsExtra](../../ris/app.py#L916)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `patient_id` | `db.Integer` | unique=True,nullable=False |
| `nationality` | `db.String(100)` |  |
| `id_type` | `db.String(30)` |  |
| `other_id` | `db.String(80)` |  |

Foreign keys: `patient_id → patient.id`.

## `patient_document (inferred)`

[PatientDocument](../../ris/app.py#L509)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `patient_id` | `db.Integer` | nullable=False |
| `order_id` | `db.Integer` |  |
| `document_type` | `db.String(50)` | nullable=False |
| `category` | `db.String(50)` |  |
| `document_date` | `db.Date` |  |
| `expiry_date` | `db.Date` |  |
| `reference_no` | `db.String(120)` |  |
| `file_path` | `db.String(600)` | nullable=False |
| `original_name` | `db.String(255)` |  |
| `extracted_text` | `db.Text` |  |
| `extraction_status` | `db.String(30)` |  |
| `review_status` | `db.String(30)` |  |
| `reviewer_id` | `db.Integer` |  |
| `review_notes` | `db.Text` |  |
| `uploaded_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |
| `reviewed_at` | `db.DateTime` |  |

Foreign keys: `patient_id → patient.id`, `order_id → order.id`, `reviewer_id → user.id`, `uploaded_by → user.id`.

## `payment (inferred)`

[Payment](../../ris/app.py#L2841)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `amount` | `db.Float` | nullable=False |
| `method` | `db.String(30)` | nullable=False |
| `reference` | `db.String(120)` |  |
| `status` | `db.String(20)` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `order_id → order.id`.

## `payment_refund (inferred)`

[PaymentRefund](../../ris/app.py#L2853)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `payment_id` | `db.Integer` | nullable=False |
| `order_id` | `db.Integer` | nullable=False |
| `amount` | `db.Float` | nullable=False |
| `reason` | `db.String(500)` | nullable=False |
| `reference` | `db.String(120)` |  |
| `created_by` | `db.Integer` | nullable=False |
| `created_at` | `db.DateTime` |  |

Foreign keys: `payment_id → payment.id`, `order_id → order.id`.

## `performing_doctor_share_rule (inferred)`

[PerformingDoctorShareRule](../../ris/app.py#L715)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `doctor_user_id` | `db.Integer` | nullable=False |
| `branch_id` | `db.Integer` |  |
| `modality` | `db.String(30)` |  |
| `procedure_id` | `db.Integer` |  |
| `contract_id` | `db.Integer` |  |
| `rule_type` | `db.String(20)` |  |
| `basis` | `db.String(30)` |  |
| `value` | `db.Float` |  |
| `active` | `db.Boolean` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `doctor_user_id → user.id`, `branch_id → branch.id`, `procedure_id → procedure.id`, `contract_id → contract.id`, `created_by → user.id`.

## `portal_access_token (inferred)`

[PortalAccessToken](../../ris/app.py#L2894)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `token` | `db.String(120)` | unique=True,nullable=False |
| `expires_at` | `db.DateTime` | nullable=False |
| `revoked` | `db.Boolean` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `order_id → order.id`.

## `printer_profile (inferred)`

[PrinterProfile](../../ris/app.py#L1635)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `name` | `db.String(160)` | nullable=False |
| `branch_id` | `db.Integer` |  |
| `user_id` | `db.Integer` |  |
| `workstation_code` | `db.String(120)` |  |
| `document_type` | `db.String(30)` | nullable=False |
| `printer_name` | `db.String(255)` |  |
| `paper_size` | `db.String(40)` |  |
| `copies` | `db.Integer` |  |
| `auto_open_print_dialog` | `db.Boolean` |  |
| `active` | `db.Boolean` |  |
| `created_at` | `db.DateTime` |  |
| `updated_at` | `db.DateTime` |  |

Foreign keys: `branch_id → branch.id`, `user_id → user.id`.

## `prior_study_selection (inferred)`

[PriorStudySelection](../../ris/app.py#L972)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `prior_order_id` | `db.Integer` |  |
| `external_prior_id` | `db.Integer` |  |
| `selected_by` | `db.Integer` |  |
| `selected_at` | `db.DateTime` |  |
| `include_in_ai` | `db.Boolean` |  |

Foreign keys: `order_id → order.id`, `prior_order_id → order.id`, `external_prior_id → external_prior_study.id`, `selected_by → user.id`.

## `procedure (inferred)`

[Procedure](../../ris/app.py#L365)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `code` | `db.String(40)` | unique=True,nullable=False |
| `name` | `db.String(180)` | nullable=False |
| `name_ar` | `db.String(180)` |  |
| `category` | `db.String(80)` |  |
| `modality` | `db.String(10)` | nullable=False |
| `body_part` | `db.String(80)` |  |
| `base_price` | `db.Float` |  |
| `duration_min` | `db.Integer` |  |
| `contrast` | `db.Boolean` |  |
| `active` | `db.Boolean` |  |

## `procedure_branch`

[ProcedureBranch](../../ris/app.py#L379)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `branch_id` | `db.Integer` | nullable=False |
| `procedure_id` | `db.Integer` | nullable=False |
| `active` | `db.Boolean` | nullable=False |

Foreign keys: `branch_id → branch.id`, `procedure_id → procedure.id`.

## `procedure_consumable (inferred)`

[ProcedureConsumable](../../ris/app.py#L1747)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `procedure_id` | `db.Integer` | nullable=False |
| `consumable_id` | `db.Integer` | nullable=False |
| `qty` | `db.Float` |  |

Foreign keys: `procedure_id → procedure.id`, `consumable_id → consumable.id`.

## `procedure_consumable_default (inferred)`

[ProcedureConsumableDefault](../../ris/app.py#L638)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `procedure_id` | `db.Integer` | nullable=False |
| `item_id` | `db.Integer` | nullable=False |
| `qty` | `db.Float` |  |
| `required` | `db.Boolean` |  |
| `active` | `db.Boolean` |  |

Foreign keys: `procedure_id → procedure.id`, `item_id → inventory_item.id`.

## `procedure_quality_rule (inferred)`

[ProcedureQualityRule](../../ris/app.py#L1398)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `modality` | `db.String(30)` | nullable=False |
| `procedure_pattern` | `db.String(180)` | nullable=False |
| `min_images` | `db.Integer` |  |
| `warning_images` | `db.Integer` |  |
| `required_series` | `db.Text` |  |
| `require_history` | `db.Boolean` |  |
| `require_attachments` | `db.Boolean` |  |
| `require_pacs_study` | `db.Boolean` |  |
| `block_auto_assign` | `db.Boolean` |  |
| `tolerance_percent` | `db.Integer` |  |
| `active` | `db.Boolean` |  |

## `qa_remediation_action`

[QARemediationAction](../../ris/app.py#L1097)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `run_id` | `db.Integer` |  |
| `test_result_id` | `db.Integer` |  |
| `action_key` | `db.String(120)` | nullable=False |
| `status` | `db.String(30)` |  |
| `requested_by` | `db.Integer` |  |
| `requested_at` | `db.DateTime` |  |
| `completed_at` | `db.DateTime` |  |
| `details_json` | `db.Text` |  |
| `error_text` | `db.Text` |  |

Foreign keys: `run_id → qa_run.id`, `test_result_id → qa_test_result.id`, `requested_by → user.id`.

## `qa_run`

[QARun](../../ris/app.py#L1047)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `run_type` | `db.String(40)` |  |
| `status` | `db.String(30)` |  |
| `release_name` | `db.String(120)` |  |
| `environment` | `db.String(40)` |  |
| `total_tests` | `db.Integer` |  |
| `passed_tests` | `db.Integer` |  |
| `failed_tests` | `db.Integer` |  |
| `critical_tests` | `db.Integer` |  |
| `warning_tests` | `db.Integer` |  |
| `external_execution_id` | `db.String(180)` |  |
| `started_by` | `db.Integer` |  |
| `started_at` | `db.DateTime` |  |
| `finished_at` | `db.DateTime` |  |
| `summary_json` | `db.Text` |  |
| `error_text` | `db.Text` |  |

Foreign keys: `started_by → user.id`.

## `qa_test_result`

[QATestResult](../../ris/app.py#L1073)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `run_id` | `db.Integer` | nullable=False |
| `test_key` | `db.String(120)` | nullable=False |
| `category` | `db.String(80)` |  |
| `title` | `db.String(220)` |  |
| `status` | `db.String(20)` |  |
| `severity` | `db.String(20)` |  |
| `expected` | `db.Text` |  |
| `actual` | `db.Text` |  |
| `details_json` | `db.Text` |  |
| `error_text` | `db.Text` |  |
| `order_id` | `db.Integer` |  |
| `started_at` | `db.DateTime` |  |
| `finished_at` | `db.DateTime` |  |

Foreign keys: `run_id → qa_run.id`, `order_id → order.id`.

## `readiness_series_alias`

[ReadinessSeriesAlias](../../ris/app.py#L1438)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `rule_id` | `db.Integer` | nullable=False |
| `source_alias` | `db.String(255)` | nullable=False |
| `alias_normalized` | `db.String(255)` | nullable=False |
| `canonical_series` | `db.String(120)` | nullable=False |
| `match_field` | `db.String(20)` | nullable=False |
| `active` | `db.Boolean` | nullable=False |
| `created_by` | `db.Integer` |  |
| `reason` | `db.String(500)` | nullable=False |
| `created_at` | `db.DateTime` | nullable=False |

Foreign keys: `rule_id → procedure_quality_rule.id`.

## `receipt (inferred)`

[Receipt](../../ris/app.py#L1767)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `receipt_no` | `db.String(50)` | unique=True,nullable=False |
| `order_id` | `db.Integer` | nullable=False |
| `amount` | `db.Numeric(12, 2)` |  |
| `payment_method` | `db.String(30)` |  |
| `reference_no` | `db.String(120)` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |
| `notes` | `db.String(500)` |  |

Foreign keys: `order_id → order.id`.

## `referral_commission_rule (inferred)`

[ReferralCommissionRule](../../ris/app.py#L792)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `referrer_id` | `db.Integer` | nullable=False |
| `branch_id` | `db.Integer` |  |
| `modality` | `db.String(30)` |  |
| `procedure_id` | `db.Integer` |  |
| `rule_type` | `db.String(20)` |  |
| `value` | `db.Float` |  |
| `active` | `db.Boolean` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `referrer_id → referring_doctor.id`, `branch_id → branch.id`, `procedure_id → procedure.id`, `created_by → user.id`.

## `referring_doctor (inferred)`

[ReferringDoctor](../../ris/app.py#L1757)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `code` | `db.String(40)` | unique=True,nullable=False |
| `name` | `db.String(160)` | nullable=False |
| `specialty` | `db.String(120)` |  |
| `phone` | `db.String(40)` |  |
| `organization` | `db.String(160)` |  |
| `active` | `db.Boolean` |  |

## `registration_default (inferred)`

[RegistrationDefault](../../ris/app.py#L850)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `user_id` | `db.Integer` |  |
| `is_global` | `db.Boolean` |  |
| `default_branch_id` | `db.Integer` |  |
| `default_department` | `db.String(100)` |  |
| `default_procedure_id` | `db.Integer` |  |
| `default_contract_id` | `db.Integer` |  |
| `default_referrer_id` | `db.Integer` |  |
| `default_priority` | `db.String(30)` |  |
| `default_payment_method` | `db.String(40)` |  |
| `default_patient_mode` | `db.String(20)` |  |
| `active` | `db.Boolean` |  |
| `updated_by` | `db.Integer` |  |
| `updated_at` | `db.DateTime` |  |

Foreign keys: `user_id → user.id`, `default_branch_id → branch.id`, `default_procedure_id → procedure.id`, `default_contract_id → contract.id`, `default_referrer_id → referring_doctor.id`, `updated_by → user.id`.

## `replacement_settlement`

[ReplacementSettlement](../../ris/replacement_settlements.py#L55)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `revision_id` | `db.Integer` | nullable=False,unique=True |
| `order_id` | `db.Integer` | nullable=False |
| `branch_id` | `db.Integer` | nullable=False |
| `revision_no` | `db.Integer` | nullable=False |
| `previous_id` | `db.Integer` |  |
| `old_doctor_id` | `db.Integer` | nullable=False |
| `new_doctor_id` | `db.Integer` | nullable=False |
| `old_amount` | `db.Numeric(14, 2)` | nullable=False |
| `new_amount` | `db.Numeric(14, 2)` | nullable=False |
| `linked_paid_amount` | `db.Numeric(14, 2)` | nullable=False |
| `verified_paid_amount` | `db.Numeric(14, 2)` | nullable=False |
| `preview_sha256` | `db.String(64)` | nullable=False |
| `snapshot_json` | `db.Text` | nullable=False |
| `reason` | `db.Text` | nullable=False |
| `created_by` | `db.Integer` | nullable=False |
| `created_at` | `db.DateTime` | nullable=False |

Foreign keys: `revision_id → report_revision.id`, `order_id → order.id`, `branch_id → branch.id`, `previous_id → replacement_settlement.id`, `old_doctor_id → user.id`, `new_doctor_id → user.id`, `created_by → user.id`.

## `replication_node`

[ReplicationNode](../../ris/app.py#L2666)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `code` | `db.String(60)` | unique=True,nullable=False |
| `name` | `db.String(160)` | nullable=False |
| `node_role` | `db.String(30)` |  |
| `branch_id` | `db.Integer` |  |
| `company_code` | `db.String(60)` |  |
| `host` | `db.String(255)` |  |
| `site` | `db.String(160)` |  |
| `active` | `db.Boolean` |  |
| `health_status` | `db.String(30)` |  |
| `last_seen_at` | `db.DateTime` |  |
| `notes` | `db.Text` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `branch_id → branch.id`.

## `replication_policy`

[ReplicationPolicy](../../ris/app.py#L2684)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `code` | `db.String(60)` | unique=True,nullable=False |
| `name` | `db.String(180)` | nullable=False |
| `source_node_id` | `db.Integer` | nullable=False |
| `target_node_id` | `db.Integer` | nullable=False |
| `data_scope` | `db.String(40)` |  |
| `transport` | `db.String(50)` |  |
| `mode` | `db.String(30)` |  |
| `source_storage_id` | `db.Integer` |  |
| `target_storage_id` | `db.Integer` |  |
| `rpo_minutes` | `db.Integer` |  |
| `rto_minutes` | `db.Integer` |  |
| `schedule` | `db.String(120)` |  |
| `active` | `db.Boolean` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `source_node_id → replication_node.id`, `target_node_id → replication_node.id`, `source_storage_id → storage_location.id`, `target_storage_id → storage_location.id`.

## `replication_state`

[ReplicationState](../../ris/app.py#L2711)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `policy_id` | `db.Integer` | nullable=False |
| `status` | `db.String(30)` |  |
| `last_success_at` | `db.DateTime` |  |
| `last_check_at` | `db.DateTime` |  |
| `lag_seconds` | `db.Integer` |  |
| `pending_items` | `db.BigInteger` |  |
| `pending_bytes` | `db.BigInteger` |  |
| `checkpoint` | `db.String(500)` |  |
| `last_error` | `db.Text` |  |

Foreign keys: `policy_id → replication_policy.id`.

## `report (inferred)`

[Report](../../ris/app.py#L2916)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | unique=True,nullable=False |
| `status` | `db.String(20)` |  |
| `findings` | `db.Text` |  |
| `impression` | `db.Text` |  |
| `radiologist` | `db.String(120)` |  |
| `docx_path` | `db.String(500)` |  |
| `pdf_path` | `db.String(500)` |  |
| `source_path` | `db.String(500)` |  |
| `source_type` | `db.String(20)` |  |
| `updated_at` | `db.DateTime` |  |
| `finalized_at` | `db.DateTime` |  |
| `verified_by` | `db.String(160)` |  |
| `verified_at` | `db.DateTime` |  |
| `second_verified_by` | `db.String(160)` |  |
| `second_verified_at` | `db.DateTime` |  |
| `finalized_by` | `db.String(160)` |  |
| `addendum_no` | `db.Integer` |  |

Foreign keys: `order_id → order.id`.

## `report_edit_lease`

[ReportEditLease](../../ris/app.py#L2998)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `report_id` | `db.Integer` | nullable=False |
| `user_id` | `db.Integer` | nullable=False |
| `editor_type` | `db.String(32)` | nullable=False |
| `lease_token_hash` | `db.String(80)` | nullable=False |
| `acquired_at` | `db.DateTime(timezone=True)` | nullable=False |
| `renewed_at` | `db.DateTime(timezone=True)` | nullable=False |
| `expires_at` | `db.DateTime(timezone=True)` | nullable=False |

Foreign keys: `order_id → order.id`, `report_id → report.id`, `user_id → user.id`.

## `report_version (inferred)`

[ReportVersion](../../ris/app.py#L2936)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `report_id` | `db.Integer` | nullable=False |
| `accession` | `db.String(40)` | nullable=False |
| `version_no` | `db.Integer` | nullable=False |
| `action` | `db.String(20)` | nullable=False |
| `findings` | `db.Text` |  |
| `impression` | `db.Text` |  |
| `radiologist` | `db.String(120)` |  |
| `docx_path` | `db.String(500)` |  |
| `pdf_path` | `db.String(500)` |  |
| `source_path` | `db.String(500)` |  |
| `source_type` | `db.String(20)` |  |
| `created_at` | `db.DateTime` | nullable=False |
| `created_by` | `db.Integer` |  |
| `created_role` | `db.String(60)` |  |
| `change_summary` | `db.String(500)` |  |
| `sha256` | `db.String(64)` |  |
| `file_size` | `db.Integer` |  |
| `signature` | `db.Text` |  |
| `signature_algorithm` | `db.String(50)` |  |
| `signing_key_id` | `db.Integer` |  |
| `signed_by_user_id` | `db.Integer` |  |
| `signed_by_name` | `db.String(180)` |  |
| `signed_at` | `db.DateTime` |  |
| `signature_status` | `db.String(30)` |  |
| `signed_payload_sha256` | `db.String(64)` |  |
| `previous_version_sha256` | `db.String(64)` |  |
| `status` | `db.String(30)` | nullable=False |
| `editor_type` | `db.String(30)` | nullable=False |
| `base_version_no` | `db.Integer` |  |
| `commit_id` | `db.String(36)` |  |
| `verified_by_user_id` | `db.Integer` |  |
| `verified_at` | `db.DateTime` |  |
| `finalized_by_user_id` | `db.Integer` |  |
| `finalized_at` | `db.DateTime` |  |

Foreign keys: `report_id → report.id`, `verified_by_user_id → user.id`, `finalized_by_user_id → user.id`.

## `ribbon_action (inferred)`

[RibbonAction](../../ris/app.py#L424)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `action_key` | `db.String(100)` | unique=True,nullable=False |
| `label_en` | `db.String(120)` | nullable=False |
| `label_ar` | `db.String(120)` |  |
| `icon` | `db.String(40)` |  |
| `route_name` | `db.String(120)` | nullable=False |
| `required_permission` | `db.String(120)` |  |
| `context` | `db.String(40)` |  |
| `order_no` | `db.Integer` |  |
| `active` | `db.Boolean` |  |

## `ris_notification (inferred)`

[RISNotification](../../ris/app.py#L1507)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `user_id` | `db.Integer` |  |
| `role_code` | `db.String(60)` |  |
| `branch_id` | `db.Integer` |  |
| `order_id` | `db.Integer` |  |
| `severity` | `db.String(20)` |  |
| `event_type` | `db.String(80)` |  |
| `title` | `db.String(220)` | nullable=False |
| `body` | `db.Text` |  |
| `status` | `db.String(30)` |  |
| `created_at` | `db.DateTime` |  |
| `acknowledged_at` | `db.DateTime` |  |
| `acknowledged_by` | `db.Integer` |  |

Foreign keys: `user_id → user.id`, `branch_id → branch.id`, `order_id → order.id`, `acknowledged_by → user.id`.

## `role (inferred)`

[Role](../../ris/app.py#L283)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `code` | `db.String(40)` | unique=True,nullable=False |
| `name` | `db.String(100)` | nullable=False |
| `permissions_json` | `db.Text` |  |

## `rt_consumable`

[RTConsumable](../../ris/radiotherapy.py#L110)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `fraction_id` | `db.Integer` | nullable=False |
| `name` | `db.String(150)` | nullable=False |
| `quantity` | `db.Numeric(18, 6)` | nullable=False |
| `unit` | `db.String(40)` | nullable=False |
| `recorded_by` | `db.Integer` | nullable=False |
| `recorded_at` | `db.DateTime` | nullable=False |

Foreign keys: `fraction_id → rt_fraction.id`, `recorded_by → user.id`.

## `rt_course`

[RTCourse](../../ris/radiotherapy.py#L39)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `primary_order_id` | `db.Integer` | nullable=False |
| `patient_id` | `db.Integer` | nullable=False |
| `branch_id` | `db.Integer` | nullable=False |
| `reference` | `db.String(100)` | unique=True,nullable=False |
| `status` | `db.String(20)` | nullable=False |
| `version` | `db.Integer` | nullable=False |
| `created_by` | `db.Integer` | nullable=False |
| `created_at` | `db.DateTime` | nullable=False |

Foreign keys: `primary_order_id → order.id`, `patient_id → patient.id`, `branch_id → branch.id`, `created_by → user.id`.

## `rt_fraction`

[RTFraction](../../ris/radiotherapy.py#L70)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `course_id` | `db.Integer` | nullable=False |
| `plan_id` | `db.Integer` | nullable=False |
| `number` | `db.Integer` | nullable=False |
| `attempt` | `db.Integer` | nullable=False |
| `scheduled_at` | `db.DateTime` | nullable=False |
| `device_id` | `db.Integer` | nullable=False |
| `planned_gy` | `db.Numeric(18, 6)` | nullable=False |
| `actual_gy` | `db.Numeric(18, 6)` |  |
| `started_at` | `db.DateTime` |  |
| `ended_at` | `db.DateTime` |  |
| `status` | `db.String(20)` | nullable=False |
| `reason` | `db.Text` |  |
| `operator_id` | `db.Integer` |  |
| `completion_key` | `db.String(80)` |  |
| `completion_hash` | `db.String(64)` |  |
| `delivery_reference` | `db.String(150)` |  |
| `version` | `db.Integer` | nullable=False |

Foreign keys: `course_id → rt_course.id`, `device_id → device.id`, `operator_id → user.id`.

## `rt_note`

[RTNote](../../ris/radiotherapy.py#L101)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `course_id` | `db.Integer` | nullable=False |
| `fraction_id` | `db.Integer` |  |
| `kind` | `db.String(20)` | nullable=False |
| `body` | `db.Text` | nullable=False |
| `recorded_by` | `db.Integer` | nullable=False |
| `recorded_at` | `db.DateTime` | nullable=False |

Foreign keys: `course_id → rt_course.id`, `fraction_id → rt_fraction.id`, `recorded_by → user.id`.

## `rt_pet_link`

[RTPetLink](../../ris/radiotherapy.py#L90)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `course_id` | `db.Integer` | nullable=False |
| `order_id` | `db.Integer` | nullable=False |
| `purpose` | `db.String(30)` | nullable=False |
| `reason` | `db.Text` | nullable=False |
| `linked_by` | `db.Integer` | nullable=False |
| `linked_at` | `db.DateTime` | nullable=False |

Foreign keys: `course_id → rt_course.id`, `order_id → order.id`, `linked_by → user.id`.

## `rt_plan_version`

[RTPlanVersion](../../ris/radiotherapy.py#L52)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `course_id` | `db.Integer` | nullable=False |
| `revision` | `db.Integer` | nullable=False |
| `external_reference` | `db.String(150)` | nullable=False |
| `approved_by` | `db.String(150)` | nullable=False |
| `approved_on` | `db.Date` | nullable=False |
| `attachment_id` | `db.Integer` |  |
| `target` | `db.Text` | nullable=False |
| `total_gy` | `db.Numeric(18, 6)` | nullable=False |
| `fraction_gy` | `db.Numeric(18, 6)` | nullable=False |
| `fractions` | `db.Integer` | nullable=False |
| `status` | `db.String(20)` | nullable=False |
| `reason` | `db.Text` | nullable=False |
| `recorded_by` | `db.Integer` | nullable=False |
| `recorded_at` | `db.DateTime` | nullable=False |

Foreign keys: `course_id → rt_course.id`, `attachment_id → attachment.id`, `recorded_by → user.id`.

## `saved_search_filter (inferred)`

[SavedSearchFilter](../../ris/app.py#L1533)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `user_id` | `db.Integer` | nullable=False |
| `name` | `db.String(160)` | nullable=False |
| `page_key` | `db.String(80)` |  |
| `filter_json` | `db.Text` |  |
| `is_default` | `db.Boolean` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `user_id → user.id`.

## `smart_intake_document (inferred)`

[SmartIntakeDocument](../../ris/app.py#L1576)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `intake_id` | `db.Integer` | nullable=False |
| `document_type` | `db.String(50)` | nullable=False |
| `original_name` | `db.String(300)` |  |
| `file_path` | `db.String(700)` | nullable=False |
| `mime_type` | `db.String(120)` |  |
| `status` | `db.String(40)` |  |
| `ocr_text` | `db.Text` |  |
| `extracted_json` | `db.Text` |  |
| `confidence` | `db.Float` |  |
| `content_sha256` | `db.String(64)` |  |
| `ocr_provider_key` | `db.String(60)` |  |
| `ocr_config_hash` | `db.String(64)` |  |
| `ocr_error` | `db.String(500)` |  |
| `review_notes` | `db.Text` |  |
| `patient_document_id` | `db.Integer` |  |
| `reviewed_by` | `db.Integer` |  |
| `reviewed_at` | `db.DateTime` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `intake_id → smart_intake_session.id`, `patient_document_id → patient_document.id`, `reviewed_by → user.id`.

## `smart_intake_field_review (inferred)`

[SmartIntakeFieldReview](../../ris/app.py#L1597)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `intake_id` | `db.Integer` | nullable=False |
| `source_document_id` | `db.Integer` |  |
| `field_key` | `db.String(80)` | nullable=False |
| `source_type` | `db.String(50)` |  |
| `extracted_value` | `db.Text` |  |
| `normalized_value` | `db.Text` |  |
| `final_value` | `db.Text` |  |
| `confidence` | `db.Float` |  |
| `validation_status` | `db.String(30)` |  |
| `validation_message` | `db.String(500)` |  |
| `review_status` | `db.String(30)` |  |
| `reviewed_by` | `db.Integer` |  |
| `reviewed_at` | `db.DateTime` |  |
| `created_at` | `db.DateTime` |  |
| `updated_at` | `db.DateTime` |  |

Foreign keys: `intake_id → smart_intake_session.id`, `source_document_id → smart_intake_document.id`, `reviewed_by → user.id`.

## `smart_intake_session (inferred)`

[SmartIntakeSession](../../ris/app.py#L1553)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `session_key` | `db.String(80)` | unique=True,nullable=False |
| `patient_id` | `db.Integer` |  |
| `status` | `db.String(40)` |  |
| `extracted_json` | `db.Text` |  |
| `matched_patient_id` | `db.Integer` |  |
| `suggested_procedure_id` | `db.Integer` |  |
| `suggested_contract_id` | `db.Integer` |  |
| `matched_patient_score` | `db.Float` |  |
| `match_resolution` | `db.String(40)` |  |
| `review_notes` | `db.Text` |  |
| `reviewed_by` | `db.Integer` |  |
| `reviewed_at` | `db.DateTime` |  |
| `commit_key` | `db.String(64)` | unique=True |
| `commit_action` | `db.String(30)` |  |
| `committed_by` | `db.Integer` |  |
| `committed_at` | `db.DateTime` |  |
| `completed_at` | `db.DateTime` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |
| `updated_at` | `db.DateTime` |  |

Foreign keys: `patient_id → patient.id`, `matched_patient_id → patient.id`, `suggested_procedure_id → procedure.id`, `suggested_contract_id → contract.id`, `reviewed_by → user.id`, `committed_by → user.id`, `created_by → user.id`.

## `sticker_template (inferred)`

[StickerTemplate](../../ris/app.py#L2168)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `name` | `db.String(120)` | nullable=False |
| `active` | `db.Boolean` |  |
| `is_default` | `db.Boolean` |  |
| `width_mm` | `db.Float` |  |
| `height_mm` | `db.Float` |  |
| `bilingual` | `db.Boolean` |  |
| `show_logo` | `db.Boolean` |  |
| `show_qr` | `db.Boolean` |  |
| `show_barcode` | `db.Boolean` |  |
| `fields_json` | `db.Text` |  |
| `labels_json` | `db.Text` |  |
| `created_at` | `db.DateTime` |  |
| `updated_at` | `db.DateTime` |  |

## `stock_movement (inferred)`

[StockMovement](../../ris/app.py#L2780)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `movement_date` | `db.DateTime` |  |
| `consumable_id` | `db.Integer` | nullable=False |
| `branch_id` | `db.Integer` |  |
| `movement_type` | `db.String(40)` | nullable=False |
| `qty` | `db.Float` | nullable=False |
| `before_qty` | `db.Float` |  |
| `after_qty` | `db.Float` |  |
| `reference_type` | `db.String(60)` |  |
| `reference_id` | `db.String(120)` |  |
| `reason` | `db.String(500)` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `consumable_id → consumable.id`, `branch_id → branch.id`.

## `stock_transfer (inferred)`

[StockTransfer](../../ris/app.py#L685)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `transfer_no` | `db.String(80)` | nullable=False,unique=True |
| `source_warehouse_id` | `db.Integer` | nullable=False |
| `target_warehouse_id` | `db.Integer` | nullable=False |
| `status` | `db.String(30)` |  |
| `requested_by` | `db.Integer` |  |
| `approved_by` | `db.Integer` |  |
| `dispatched_by` | `db.Integer` |  |
| `received_by` | `db.Integer` |  |
| `requested_at` | `db.DateTime` |  |
| `approved_at` | `db.DateTime` |  |
| `dispatched_at` | `db.DateTime` |  |
| `received_at` | `db.DateTime` |  |
| `notes` | `db.Text` |  |

Foreign keys: `source_warehouse_id → warehouse.id`, `target_warehouse_id → warehouse.id`, `requested_by → user.id`, `approved_by → user.id`, `dispatched_by → user.id`, `received_by → user.id`.

## `stock_transfer_line (inferred)`

[StockTransferLine](../../ris/app.py#L703)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `transfer_id` | `db.Integer` | nullable=False |
| `item_id` | `db.Integer` | nullable=False |
| `lot_id` | `db.Integer` |  |
| `qty_requested` | `db.Float` |  |
| `qty_dispatched` | `db.Float` |  |
| `qty_received` | `db.Float` |  |

Foreign keys: `transfer_id → stock_transfer.id`, `item_id → inventory_item.id`, `lot_id → inventory_lot.id`.

## `storage_location`

[StorageLocation](../../ris/app.py#L2633)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `code` | `db.String(40)` | unique=True,nullable=False |
| `label` | `db.String(160)` | nullable=False |
| `path` | `db.String(700)` | nullable=False |
| `storage_type` | `db.String(30)` |  |
| `protocol` | `db.String(30)` |  |
| `role` | `db.String(30)` |  |
| `branch_id` | `db.Integer` |  |
| `company_code` | `db.String(60)` |  |
| `vendor` | `db.String(80)` |  |
| `endpoint` | `db.String(255)` |  |
| `mount_source` | `db.String(500)` |  |
| `filesystem` | `db.String(40)` |  |
| `priority` | `db.Integer` |  |
| `read_only` | `db.Boolean` |  |
| `capacity_bytes` | `db.BigInteger` |  |
| `free_bytes` | `db.BigInteger` |  |
| `health_status` | `db.String(30)` |  |
| `last_health_at` | `db.DateTime` |  |
| `notes` | `db.Text` |  |
| `active` | `db.Boolean` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `branch_id → branch.id`.

## `studio_shortcut (inferred)`

[StudioShortcut](../../ris/app.py#L827)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `title_en` | `db.String(120)` | nullable=False |
| `title_ar` | `db.String(120)` |  |
| `icon` | `db.String(80)` |  |
| `accent` | `db.String(30)` |  |
| `target_type` | `db.String(30)` |  |
| `target` | `db.String(500)` | nullable=False |
| `placement` | `db.String(40)` |  |
| `open_mode` | `db.String(20)` |  |
| `size` | `db.String(20)` |  |
| `sort_order` | `db.Integer` |  |
| `permission_code` | `db.String(120)` |  |
| `role_code` | `db.String(80)` |  |
| `branch_id` | `db.Integer` |  |
| `user_id` | `db.Integer` |  |
| `active` | `db.Boolean` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |
| `updated_at` | `db.DateTime` |  |

Foreign keys: `branch_id → branch.id`, `user_id → user.id`, `created_by → user.id`.

## `studio_template (inferred)`

[StudioTemplate](../../ris/app.py#L891)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `template_type` | `db.String(40)` | nullable=False |
| `name` | `db.String(180)` | nullable=False |
| `scope` | `db.String(40)` |  |
| `branch_id` | `db.Integer` |  |
| `owner_user_id` | `db.Integer` |  |
| `version_no` | `db.Integer` |  |
| `status` | `db.String(20)` |  |
| `layout_json` | `db.Text` |  |
| `notes` | `db.Text` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |
| `published_at` | `db.DateTime` |  |

Foreign keys: `branch_id → branch.id`, `owner_user_id → user.id`, `created_by → user.id`.

## `studio_template_version (inferred)`

[StudioTemplateVersion](../../ris/app.py#L901)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `template_id` | `db.Integer` | nullable=False |
| `version_no` | `db.Integer` | nullable=False |
| `snapshot_json` | `db.Text` | nullable=False |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `template_id → studio_template.id`, `created_by → user.id`.

## `tat_policy (inferred)`

[TATPolicy](../../ris/app.py#L1497)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `priority` | `db.String(30)` |  |
| `modality` | `db.String(30)` |  |
| `ready_to_assign_min` | `db.Integer` |  |
| `assign_to_accept_min` | `db.Integer` |  |
| `accept_to_final_min` | `db.Integer` |  |
| `total_tat_min` | `db.Integer` |  |
| `active` | `db.Boolean` |  |

## `telephony_extension (inferred)`

[TelephonyExtension](../../ris/app.py#L543)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `extension` | `db.String(30)` | unique=True,nullable=False |
| `user_id` | `db.Integer` |  |
| `active` | `db.Boolean` |  |

Foreign keys: `user_id → user.id`.

## `user (inferred)`

[User](../../ris/app.py#L292)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `username` | `db.String(80)` | unique=True,nullable=False |
| `full_name` | `db.String(120)` | nullable=False |
| `password_hash` | `db.String(255)` | nullable=False |
| `role_id` | `db.Integer` | nullable=False |
| `branch_id` | `db.Integer` |  |
| `active` | `db.Boolean` |  |
| `must_change_password` | `db.Boolean` |  |
| `password_changed_at` | `db.DateTime` |  |

Foreign keys: `role_id → role.id`, `branch_id → branch.id`.

## `user_profile (inferred)`

[UserProfile](../../ris/app.py#L401)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `user_id` | `db.Integer` | nullable=False,unique=True |
| `department` | `db.String(80)` |  |
| `specialty` | `db.String(120)` |  |
| `default_workspace` | `db.String(120)` |  |
| `ui_language` | `db.String(10)` |  |
| `theme` | `db.String(20)` |  |
| `accent` | `db.String(30)` |  |
| `density` | `db.String(20)` |  |
| `font_scale` | `db.String(20)` |  |
| `sidebar_mode` | `db.String(20)` |  |
| `settings_json` | `db.Text` |  |

Foreign keys: `user_id → user.id`.

## `user_registration_preference (inferred)`

[UserRegistrationPreference](../../ris/app.py#L579)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `user_id` | `db.Integer` | unique=True,nullable=False |
| `style_key` | `db.String(30)` |  |

Foreign keys: `user_id → user.id`.

## `user_ribbon_action (inferred)`

[UserRibbonAction](../../ris/app.py#L436)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `user_id` | `db.Integer` | nullable=False |
| `ribbon_action_id` | `db.Integer` | nullable=False |
| `order_no` | `db.Integer` |  |
| `visible` | `db.Boolean` |  |

Foreign keys: `user_id → user.id`, `ribbon_action_id → ribbon_action.id`.

## `vital_sign (inferred)`

[VitalSign](../../ris/app.py#L1667)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `order_id` | `db.Integer` | nullable=False |
| `temperature` | `db.Float` |  |
| `pulse` | `db.Integer` |  |
| `systolic` | `db.Integer` |  |
| `diastolic` | `db.Integer` |  |
| `spo2` | `db.Integer` |  |
| `respiratory_rate` | `db.Integer` |  |
| `weight_kg` | `db.Float` |  |
| `height_cm` | `db.Float` |  |
| `recorded_by` | `db.Integer` |  |
| `recorded_at` | `db.DateTime` |  |

Foreign keys: `order_id → order.id`, `recorded_by → user.id`.

## `warehouse (inferred)`

[Warehouse](../../ris/app.py#L589)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `code` | `db.String(60)` | nullable=False,unique=True |
| `name` | `db.String(180)` | nullable=False |
| `warehouse_type` | `db.String(30)` |  |
| `branch_id` | `db.Integer` |  |
| `parent_id` | `db.Integer` |  |
| `active` | `db.Boolean` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `branch_id → branch.id`, `parent_id → warehouse.id`.

## `warehouse_stock_movement`

[WarehouseStockMovement](../../ris/app.py#L667)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `warehouse_id` | `db.Integer` | nullable=False |
| `item_id` | `db.Integer` | nullable=False |
| `lot_id` | `db.Integer` |  |
| `movement_type` | `db.String(40)` | nullable=False |
| `qty` | `db.Float` | nullable=False |
| `unit_cost` | `db.Float` |  |
| `reference_type` | `db.String(40)` |  |
| `reference_id` | `db.Integer` |  |
| `notes` | `db.String(500)` |  |
| `created_by` | `db.Integer` |  |
| `created_at` | `db.DateTime` |  |

Foreign keys: `warehouse_id → warehouse.id`, `item_id → inventory_item.id`, `lot_id → inventory_lot.id`, `created_by → user.id`.

## `warehouse_stock_policy (inferred)`

[WarehouseStockPolicy](../../ris/app.py#L626)

| Column | Declared type | Flags |
|---|---|---|
| `id` | `db.Integer` | primary_key=True |
| `warehouse_id` | `db.Integer` | nullable=False |
| `item_id` | `db.Integer` | nullable=False |
| `min_level` | `db.Float` |  |
| `reorder_level` | `db.Float` |  |
| `target_level` | `db.Float` |  |
| `active` | `db.Boolean` |  |

Foreign keys: `warehouse_id → warehouse.id`, `item_id → inventory_item.id`.
