"""Permission-filtered entry points for the administrator control centre."""
GROUPS = (
 ('people', 'People & access', 'المستخدمون والصلاحيات'),
 ('registration', 'Registration & booking', 'التسجيل والحجز'),
 ('clinical', 'Examinations & assignment', 'الفحوصات وتوزيع الحالات'),
 ('reporting', 'Reports & templates', 'التقارير والقوالب'),
 ('pacs', 'PACS & integrations', 'الباكس والتكامل'),
 ('finance', 'Finance & contracts', 'الحسابات والتعاقدات'),
 ('inventory', 'Inventory & supplies', 'المخازن والمستهلكات'),
 ('communication', 'Communication & appearance', 'التواصل والمظهر'),
 ('operations', 'Dashboards & monitoring', 'لوحات المتابعة'),
 ('governance', 'Audit & system management', 'المراجعة وإدارة النظام'),
)
# Each entry links to an existing GET page; its own route remains authoritative.
DATA = '''people|admin_users|users.view|Users & contact details|المستخدمون وبيانات الاتصال
people|admin_roles|roles.manage|Roles & permissions|الأدوار والصلاحيات
people|admin_access_review|roles.manage|Access review|مراجعة الصلاحيات
people|admin_branches|branches.manage|Branches|الفروع
people|admin_referrers|referrers.manage|Referring doctors|الأطباء المحولون
registration|admin_field_rules|users.view|Required registration fields|خانات التسجيل الإلزامية
registration|admin_registration_defaults|users.view|Registration defaults|إعدادات التسجيل الافتراضية
registration|admin_devices|devices.manage|Devices & rooms|الأجهزة والغرف
registration|admin_device_schedules|devices.manage|Device schedules|مواعيد الأجهزة
registration|admin_booking_availability|devices.manage|Booking availability|إتاحة الحجز
registration|admin_booking_control_center|devices.manage|Booking control centre|مركز التحكم في الحجز
registration|admin_procedures|procedures.view|Examination catalogue|دليل الفحوصات
registration|admin_ocr_settings|users.view|OCR settings|إعدادات قراءة المستندات
registration|admin_printer_profiles|users.view|Printer profiles|إعدادات الطابعات
registration|admin_label_templates|users.view|Label templates|قوالب الملصقات
registration|admin_sticker_templates|users.view|Sticker templates|قوالب الاستيكر
clinical|admin_assignment_strategies|assignment.manage|Assignment strategies|سياسات توزيع الحالات
clinical|admin_assignment_distribution|assignment.manage|Assignment distribution|توزيع الحالات
clinical|admin_assignment_visits|assignment.manage|Linked visits|الزيارات المربوطة
clinical|admin_assignment_monitor|assignment.manage|Doctor workload monitor|متابعة الأطباء والحالات
clinical|admin_assignment_offers|users.view|Assignment offers|عروض إسناد الحالات
clinical|admin_procedure_quality_rules|users.view|Image & examination policies|سياسات الصور والفحوصات
clinical|admin_tat_policies|assignment.manage|Turnaround time policies|سياسات وقت إنجاز الحالات
clinical|admin_qa_control|users.view|Quality assurance|ضبط الجودة
reporting|report_header_settings|users.manage|Report header & A4 layout|هيدر التقرير وتنسيق A4
reporting|doctor_templates|reports.edit|Report templates|قوالب التقارير
reporting|admin_ai_reporting|users.view|Reporting assistance settings|إعدادات المساعدة في كتابة التقارير
reporting|admin_doctor_share_rules|finance.doctor_share.manage|Doctor share rules|قواعد مستحقات الأطباء
pacs|dicom_connections_page|devices.manage|DICOM connections & Worklist|اتصالات DICOM وقائمة العمل
pacs|pacs_discovery|pacs.discovery.view|Incoming devices & permissions|الأجهزة الواردة وصلاحيات الاتصال
pacs|pacs_destinations|pacs.destinations.manage|Image transfer destinations|وجهات إرسال الصور
pacs|pacs_routing_rules|pacs.archive.manage|Automatic routing rules|قواعد تحويل الصور التلقائي
pacs|admin_external_intake|assignment.manage|External RIS intake|استقبال بيانات RIS خارجي
pacs|admin_imaging_ai|users.view|Imaging assistance settings|إعدادات المساعدة في الصور
finance|admin_contracts|contracts.manage|Contracts & price lists|التعاقدات وقوائم الأسعار
finance|admin_insurance_approvals|contracts.manage|Insurance approvals|موافقات التأمين
finance|admin_discount_policies|finance.discount.manage|Discount policies|سياسات الخصومات
finance|admin_referral_commissions|users.view|Referral commissions|عمولات التحويل
finance|financial_center|financial.view|Financial centre|المركز المالي
finance|accounting_reports|financial.view|Financial reports|التقارير المالية
finance|receivables|receivables.view|Outstanding balances|تقرير البواقي
finance|daily_closing|financial.view|Daily closing|التقفيل اليومي
inventory|admin_inventory|inventory.manage|Consumables|المستهلكات
inventory|inventory_warehouses|inventory.manage|Warehouses|المخازن
inventory|inventory_items|inventory.manage|Stock items|أصناف المخزون
inventory|inventory_stock|inventory.view|Stock balances|أرصدة المخزون
inventory|inventory_stock_policies|inventory.manage|Stock policies|سياسات المخزون
inventory|inventory_procedure_defaults|inventory.manage|Examination supplies|مستهلكات الفحوصات الافتراضية
inventory|inventory_transfers|inventory.view|Stock transfers|تحويلات المخازن
inventory|inventory_ledger|inventory.reports|Inventory ledger|سجل حركة المخزون
inventory|inventory_consumption_report|inventory.reports|Consumption report|تقرير الاستهلاك
communication|admin_communications|users.view|Communication settings|إعدادات التواصل
communication|admin_notifications|audit.view|Notifications|الإشعارات
communication|admin_dictionary|users.view|Arabic & English dictionary|القاموس العربي والإنجليزي
communication|admin_ribbon_designer|users.view|Shortcut ribbon|شريط الاختصارات
communication|admin_company|users.view|Company identity|بيانات المؤسسة
communication|admin_company_legal|users.view|Legal company details|البيانات القانونية للمؤسسة
operations|case_readiness_dashboard|orders.view|Case readiness|جاهزية الحالات
operations|coordinator_assignments|assignment.manage,reports.coordinate|Coordinator assignment monitor|متابعة التوزيع للمنسقين
operations|coordinator_queue|reports.coordinate|Coordinator workspace|شاشة المنسقين
operations|executive_analytics|analytics.executive.view|Executive dashboard|لوحة متابعة الإدارة
operations|analytics_reference.analytics|analytics.view|Analytics|الإحصائيات
 governance|admin_audit|audit.view|Audit log|سجل المراجعة
 governance|admin_diagnostics|users.view|System diagnostics|تشخيص النظام
 governance|admin_import_export|import.manage,export.view|Import & export|استيراد وتصدير البيانات
 governance|admin_data_management|backup.view|Backup & data management|النسخ الاحتياطي وإدارة البيانات
 governance|storage_dr_manager|storage.targets.view|Storage & disaster recovery|التخزين والتعافي
 governance|storage_cloud_manager|storage.cloud.view|Cloud storage|التخزين السحابي
 governance|admin_cancellation_center|data.cancel.case|Cancellation centre|مركز الإلغاء
 governance|admin_data_deletion_center|*|Data deletion centre|مركز حذف البيانات'''
ENTRIES = tuple(tuple(part.strip() for part in line.split('|')) for line in DATA.splitlines())

def visible_sections(has_perm, url_for, endpoints):
    result = []
    for code, en, ar in GROUPS:
        links = []
        for group, endpoint, permissions, title_en, title_ar in ENTRIES:
            if group != code or endpoint not in endpoints:
                continue
            if not (has_perm('*') or any(has_perm(p) for p in permissions.split(','))):
                continue
            links.append({'url': url_for(endpoint), 'en': title_en, 'ar': title_ar})
        if links:
            result.append({'code': code, 'en': en, 'ar': ar, 'links': links})
    return result
