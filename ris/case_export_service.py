# -*- coding: utf-8 -*-
"""
AirScan RIS/PACS - Case & Financial Export Service
Provides structured Excel (.xlsx) and CSV exports for accountants, financial auditors,
and corporate/insurance contract management.
"""

import io
import csv
from datetime import datetime, date, time
from decimal import Decimal
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

def build_cases_query(db, Order, Patient, filters, allowed_branches=None):
    """
    Constructs the SQLAlchemy query with all operational and financial filters.
    """
    q = Order.query.join(Patient, Order.patient_id == Patient.id)
    
    # 1. Date Range Filter
    start_d = filters.get('start_date')
    end_d = filters.get('end_date')
    if start_d:
        if isinstance(start_d, str):
            start_d = date.fromisoformat(start_d)
        q = q.filter(Order.scheduled >= datetime.combine(start_d, time.min))
    if end_d:
        if isinstance(end_d, str):
            end_d = date.fromisoformat(end_d)
        q = q.filter(Order.scheduled <= datetime.combine(end_d, time.max))

    # 2. Branch Filter (respecting user permissions)
    branch_id = filters.get('branch_id')
    if branch_id:
        try:
            branch_id = int(branch_id)
            q = q.filter(Order.branch_id == branch_id)
        except (ValueError, TypeError):
            pass
    elif allowed_branches is not None:
        q = q.filter(Order.branch_id.in_(allowed_branches))

    # 3. Payer / Contract Filter
    payer_type = (filters.get('payer_type') or 'ALL').upper().strip()
    contract_id = filters.get('contract_id')
    
    if contract_id:
        try:
            c_id = int(contract_id)
            q = q.filter(Order.contract_id == c_id)
        except (ValueError, TypeError):
            pass
    elif payer_type == 'CASH':
        q = q.filter(db.or_(Order.contract_id == None, Order.contract_id == 1))
    elif payer_type == 'CONTRACT':
        q = q.filter(Order.contract_id != None, Order.contract_id != 1)

    # 4. Modality Filter
    modality = (filters.get('modality') or 'ALL').upper().strip()
    if modality and modality != 'ALL':
        q = q.filter(db.func.upper(Order.modality) == modality)

    # 5. Report Status Filter
    rep_status = (filters.get('report_status') or 'ALL').upper().strip()
    if rep_status and rep_status != 'ALL':
        from app import Report
        if rep_status == 'UNREPORTED':
            q = q.outerjoin(Report, Order.id == Report.order_id).filter(
                db.or_(Report.id == None, Report.status == 'DRAFT', Report.status == None)
            )
        elif rep_status in ('FINAL', 'FINALIZED', 'VERIFIED'):
            q = q.join(Report, Order.id == Report.order_id).filter(
                Report.status.in_(['FINAL', 'VERIFIED', 'COMPLETED'])
            )
        elif rep_status in ('DRAFT', 'DRAFTED'):
            q = q.join(Report, Order.id == Report.order_id).filter(
                Report.status.in_(['DRAFT', 'PRELIMINARY'])
            )

    # 6. Text Search Filter (Patient Name, Accession, Phone, National ID)
    search_q = (filters.get('search') or '').strip()
    if search_q:
        q = q.filter(db.or_(
            Order.accession.ilike(f'%{search_q}%'),
            Patient.name.ilike(f'%{search_q}%'),
            Patient.patient_id.ilike(f'%{search_q}%'),
            Patient.phone.ilike(f'%{search_q}%'),
            Patient.national_id.ilike(f'%{search_q}%'),
            Order.procedure.ilike(f'%{search_q}%')
        ))

    return q.order_by(Order.scheduled.desc(), Order.id.desc())


def extract_case_row(order, idx, Receipt, User):
    """
    Extracts and standardizes data points for a single examination row.
    """
    p = order.patient
    b = order.branch
    c = order.contract
    proc = order.proc
    dev = order.device
    
    # Financial calculations
    gross = round(float(order.gross_price or 0.0), 2)
    is_contract = bool(c and c.id != 1 and (c.code or '').upper() != 'CASH')
    
    if is_contract:
        payer_label = 'تعاقد / تأمين'
        contract_name = c.name if c else 'غير محدد'
        contract_code = c.code if c else ''
        p_share = round(float(order.patient_share or 0.0), 2)
        c_share = round(float(order.company_share or 0.0), 2)
        disc = max(0.0, round(gross - (p_share + c_share), 2))
    else:
        payer_label = 'نقدي / خاص'
        contract_name = 'نقدي / خاص'
        contract_code = 'CASH'
        p_share = round(float(order.contract_price if order.contract_price is not None else gross), 2)
        c_share = 0.0
        disc = max(0.0, round(gross - p_share, 2))

    paid = round(float(order.paid_amount or 0.0), 2)
    remaining = max(0.0, round(p_share - paid, 2))

    # Payment status text
    if remaining <= 0.001 and paid > 0:
        pay_status = 'خالص (مسدد بالكامل)'
    elif paid > 0 and remaining > 0.001:
        pay_status = 'سداد جزئي (متبقي)'
    elif paid == 0 and p_share > 0:
        pay_status = 'غير مسدد (آجل)'
    elif is_contract and p_share == 0:
        pay_status = 'تعاقد 100% (تحمل الشركة)'
    else:
        pay_status = 'خالص'

    # Latest receipt
    rcpt = Receipt.query.filter_by(order_id=order.id).order_by(Receipt.id.desc()).first()
    receipt_no = rcpt.receipt_no if rcpt else ''
    payment_method = rcpt.payment_method if rcpt else ('CASH' if paid > 0 else '')

    # Clinical & Radiologist
    referring_doc = order.referring_doctor.name if order.referring_doctor else ''
    
    assigned_doc_name = ''
    if order.assigned_doctor:
        assigned_doc_name = getattr(order.assigned_doctor, 'full_name', None) or getattr(order.assigned_doctor, 'username', '')
    if not assigned_doc_name:
        assigned_doc_name = 'غير معين'

    # Report Status
    rep = order.report
    rep_status_label = 'بانتظار الكتابة'
    if rep:
        st = (rep.status or '').upper()
        if st in ('FINAL', 'VERIFIED', 'COMPLETED'):
            rep_status_label = 'معتمد نهائي'
        elif st in ('DRAFT', 'PRELIMINARY'):
            rep_status_label = 'مسودة'

    # Creator
    creator_name = ''
    if order.created_by:
        creator = User.query.get(order.created_by)
        if creator:
            creator_name = getattr(creator, 'full_name', None) or getattr(creator, 'username', '')

    sched_str = order.scheduled.strftime('%Y-%m-%d %H:%M') if order.scheduled else ''

    return {
        'idx': idx,
        'scheduled': sched_str,
        'accession': order.accession or '',
        'patient_id': p.patient_id if p else '',
        'patient_name': p.name if p else '',
        'national_id': f"'{p.national_id}" if p and p.national_id else '',  # keep as text in excel
        'phone': p.phone if p else '',
        'branch': b.name if b else '',
        'modality': order.modality or '',
        'procedure': order.procedure or '',
        'procedure_code': proc.code if proc else '',
        'device': dev.name if dev else '',
        'payer_label': payer_label,
        'contract_name': contract_name,
        'contract_code': contract_code,
        'approval_no': order.approval_no or '',
        'gross': gross,
        'discount': disc,
        'patient_share': p_share,
        'company_share': c_share,
        'paid': paid,
        'remaining': remaining,
        'pay_status': pay_status,
        'receipt_no': receipt_no,
        'payment_method': payment_method,
        'referring_doc': referring_doc,
        'assigned_doc': assigned_doc_name,
        'report_status': rep_status_label,
        'exam_status': order.exam_status or 'مسجل',
        'pacs_images': order.pacs_image_count or 0,
        'creator': creator_name
    }


def export_cases_to_xlsx(rows, meta_info):
    """
    Builds a beautifully styled Right-to-Left Excel (.xlsx) workbook.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "كشف الفحوصات والتعاقدات"
    ws.sheet_view.rightToLeft = True

    # Palette
    navy_dark = "1E3A8A"
    navy_light = "DBEAFE"
    gray_zebra = "F8FAFC"
    border_color = "CBD5E1"

    font_title = Font(name="Segoe UI", size=15, bold=True, color="1E3A8A")
    font_sub = Font(name="Segoe UI", size=9.5, italic=True, color="475569")
    font_meta = Font(name="Segoe UI", size=10, bold=True, color="0F172A")
    font_header = Font(name="Segoe UI", size=10.5, bold=True, color="FFFFFF")
    font_data = Font(name="Segoe UI", size=10, color="0F172A")
    font_bold = Font(name="Segoe UI", size=10, bold=True, color="0F172A")
    font_total = Font(name="Segoe UI", size=11, bold=True, color="1E3A8A")

    fill_header = PatternFill(start_color=navy_dark, end_color=navy_dark, fill_type="solid")
    fill_zebra = PatternFill(start_color=gray_zebra, end_color=gray_zebra, fill_type="solid")
    fill_total = PatternFill(start_color=navy_light, end_color=navy_light, fill_type="solid")
    fill_paid = PatternFill(start_color="D1FAE5", end_color="D1FAE5", fill_type="solid")
    fill_part = PatternFill(start_color="FFEDD5", end_color="FFEDD5", fill_type="solid")
    fill_unpaid = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")

    border_thin = Border(
        left=Side(style="thin", color=border_color),
        right=Side(style="thin", color=border_color),
        top=Side(style="thin", color=border_color),
        bottom=Side(style="thin", color=border_color)
    )

    align_center = Alignment(horizontal="center", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")

    # 1. Header Metadata Section
    ws["A1"] = f"نظام {meta_info.get('company_name', 'AirScan RIS/PACS')} - كشف الفحوصات والحسابات والتعاقدات والمراجعة المالية"
    ws["A1"].font = font_title

    meta_parts = [
        f"📅 الفترة: من {meta_info.get('start_date', '--')} إلى {meta_info.get('end_date', '--')}",
        f"🏢 الفرع: {meta_info.get('branch_name', 'جميع الفروع')}",
        f"💳 نوع السداد: {meta_info.get('payer_name', 'الكل')}",
        f"🎯 القسم: {meta_info.get('modality', 'جميع الأقسام')}",
        f"🕒 تاريخ الاستخراج: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"👤 المستخدم: {meta_info.get('user_name', 'System')}"
    ]
    ws["A2"] = "  |  ".join(meta_parts)
    ws["A2"].font = font_sub

    # 2. Table Column Definitions
    headers = [
        ("م", 6, align_center),
        ("تاريخ الحجز والوقت", 17, align_center),
        ("رقم الحالة (Accession)", 18, align_center),
        ("كود المريض", 13, align_center),
        ("اسم المريض", 26, align_right),
        ("الرقم القومي", 16, align_center),
        ("رقم الهاتف", 14, align_center),
        ("الفرع", 14, align_right),
        ("القسم", 9, align_center),
        ("الفحص المطلوب", 25, align_right),
        ("كود الفحص", 12, align_center),
        ("نوع السداد", 14, align_center),
        ("جهة التعاقد / الشركة", 24, align_right),
        ("رقم الموافقة / الكارنيه", 18, align_center),
        ("السعر الإجمالي", 13, align_center),
        ("الخصم", 11, align_center),
        ("تحمل المريض", 13, align_center),
        ("مطالبة التعاقد", 13, align_center),
        ("المدفوع نقداً", 13, align_center),
        ("المتبقي", 13, align_center),
        ("حالة السداد", 18, align_center),
        ("رقم الإيصال", 14, align_center),
        ("طريقة الدفع", 12, align_center),
        ("الطبيب المحول", 20, align_right),
        ("الطبيب القارئ", 20, align_right),
        ("حالة التقرير", 14, align_center),
        ("حالة الفحص", 12, align_center),
        ("صور PACS", 10, align_center),
        ("مسؤول التسجيل", 16, align_right)
    ]

    header_row_idx = 4
    for col_idx, (title, width, alignment) in enumerate(headers, 1):
        cell = ws.cell(row=header_row_idx, column=col_idx, value=title)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align_center
        cell.border = border_thin
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # 3. Populate Rows
    start_row = 5
    for r_idx, r in enumerate(rows, start_row):
        is_zebra = (r_idx % 2 == 0)
        curr_fill = fill_zebra if is_zebra else None

        values = [
            r['idx'],
            r['scheduled'],
            r['accession'],
            r['patient_id'],
            r['patient_name'],
            r['national_id'].lstrip("'"),
            r['phone'],
            r['branch'],
            r['modality'],
            r['procedure'],
            r['procedure_code'],
            r['payer_label'],
            r['contract_name'],
            r['approval_no'],
            r['gross'],
            r['discount'],
            r['patient_share'],
            r['company_share'],
            r['paid'],
            r['remaining'],
            r['pay_status'],
            r['receipt_no'],
            r['payment_method'],
            r['referring_doc'],
            r['assigned_doc'],
            r['report_status'],
            r['exam_status'],
            r['pacs_images'],
            r['creator']
        ]

        for col_idx, val in enumerate(values, 1):
            cell = ws.cell(row=r_idx, column=col_idx, value=val)
            cell.font = font_data
            cell.border = border_thin
            cell.alignment = headers[col_idx - 1][2]

            # Apply Zebra
            if curr_fill:
                cell.fill = curr_fill

            # Format Currency Columns (Cols 15 through 20: gross, disc, p_share, c_share, paid, rem)
            if 15 <= col_idx <= 20:
                cell.number_format = '#,##0.00'
                cell.font = font_bold

            # Highlight payment status
            if col_idx == 21:  # حالة السداد
                if 'خالص' in str(val):
                    cell.fill = fill_paid
                elif 'جزئي' in str(val):
                    cell.fill = fill_part
                elif 'غير مسدد' in str(val):
                    cell.fill = fill_unpaid

    # 4. Totals / Summary Row
    total_row = start_row + len(rows)
    ws.merge_cells(start_row=total_row, start_column=1, end_row=total_row, end_column=14)
    total_label = ws.cell(row=total_row, column=1, value=f"الإجمالي العام ({len(rows)} فحص)")
    total_label.font = font_total
    total_label.alignment = align_center
    total_label.fill = fill_total

    for c_idx in range(1, 15):
        ws.cell(row=total_row, column=c_idx).border = border_thin
        ws.cell(row=total_row, column=c_idx).fill = fill_total

    # Formulas for financial sums
    sum_cols = [
        (15, 'gross'),
        (16, 'discount'),
        (17, 'patient_share'),
        (18, 'company_share'),
        (19, 'paid'),
        (20, 'remaining')
    ]
    
    if rows:
        for col_idx, field_key in sum_cols:
            col_letter = get_column_letter(col_idx)
            cell = ws.cell(row=total_row, column=col_idx)
            cell.value = f"=SUM({col_letter}{start_row}:{col_letter}{total_row - 1})"
            cell.font = font_total
            cell.fill = fill_total
            cell.border = border_thin
            cell.alignment = align_center
            cell.number_format = '#,##0.00'
    else:
        for col_idx, _ in sum_cols:
            cell = ws.cell(row=total_row, column=col_idx, value=0.00)
            cell.font = font_total
            cell.fill = fill_total
            cell.border = border_thin
            cell.alignment = align_center
            cell.number_format = '#,##0.00'

    for col_idx in range(21, len(headers) + 1):
        c_cell = ws.cell(row=total_row, column=col_idx, value="")
        c_cell.fill = fill_total
        c_cell.border = border_thin

    # Output to buffer
    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio


def export_cases_to_csv(rows, meta_info):
    """
    Builds a UTF-8 with BOM (utf-8-sig) CSV stream for seamless Arabic display in Excel.
    """
    sio = io.StringIO()
    writer = csv.writer(sio)

    # Title & Metadata
    writer.writerow([f"AirScan RIS/PACS - كشف الفحوصات والحسابات والتعاقدات والمراجعة المالية"])
    writer.writerow([
        f"الفترة: من {meta_info.get('start_date','--')} إلى {meta_info.get('end_date','--')}",
        f"الفرع: {meta_info.get('branch_name','جميع الفروع')}",
        f"نوع السداد: {meta_info.get('payer_name','الكل')}",
        f"القسم: {meta_info.get('modality','جميع الأقسام')}",
        f"تاريخ الاستخراج: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"المستخدم: {meta_info.get('user_name','System')}"
    ])
    writer.writerow([])

    # Headers
    headers = [
        "م", "تاريخ الحجز والوقت", "رقم الحالة (Accession)", "كود المريض", "اسم المريض",
        "الرقم القومي", "رقم الهاتف", "الفرع", "القسم", "الفحص المطلوب", "كود الفحص",
        "نوع السداد", "جهة التعاقد / الشركة", "رقم الموافقة / الكارنيه",
        "السعر الإجمالي", "الخصم", "تحمل المريض", "مطالبة التعاقد", "المدفوع نقداً", "المتبقي",
        "حالة السداد", "رقم الإيصال", "طريقة الدفع", "الطبيب المحول", "الطبيب القارئ",
        "حالة التقرير", "حالة الفحص", "صور PACS", "مسؤول التسجيل"
    ]
    writer.writerow(headers)

    # Data Rows
    tot_gross = 0.0
    tot_disc = 0.0
    tot_pshare = 0.0
    tot_cshare = 0.0
    tot_paid = 0.0
    tot_rem = 0.0

    for r in rows:
        tot_gross += r['gross']
        tot_disc += r['discount']
        tot_pshare += r['patient_share']
        tot_cshare += r['company_share']
        tot_paid += r['paid']
        tot_rem += r['remaining']

        writer.writerow([
            r['idx'],
            r['scheduled'],
            r['accession'],
            r['patient_id'],
            r['patient_name'],
            r['national_id'].lstrip("'"),
            r['phone'],
            r['branch'],
            r['modality'],
            r['procedure'],
            r['procedure_code'],
            r['payer_label'],
            r['contract_name'],
            r['approval_no'],
            f"{r['gross']:.2f}",
            f"{r['discount']:.2f}",
            f"{r['patient_share']:.2f}",
            f"{r['company_share']:.2f}",
            f"{r['paid']:.2f}",
            f"{r['remaining']:.2f}",
            r['pay_status'],
            r['receipt_no'],
            r['payment_method'],
            r['referring_doc'],
            r['assigned_doc'],
            r['report_status'],
            r['exam_status'],
            r['pacs_images'],
            r['creator']
        ])

    # Total Row
    writer.writerow([
        f"الإجمالي ({len(rows)} فحص)", "", "", "", "", "", "", "", "", "", "", "", "", "",
        f"{tot_gross:.2f}", f"{tot_disc:.2f}", f"{tot_pshare:.2f}", f"{tot_cshare:.2f}",
        f"{tot_paid:.2f}", f"{tot_rem:.2f}", "", "", "", "", "", "", "", "", ""
    ])

    bio = io.BytesIO(sio.getvalue().encode('utf-8-sig'))
    bio.seek(0)
    return bio
