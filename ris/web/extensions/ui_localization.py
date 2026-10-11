"""Translations for explicitly marked UI text. Clinical values are never scanned."""
from infrastructure.resources import RIS_ROOT
import json
from pathlib import Path

CATALOG = json.loads((RIS_ROOT / 'ui_phrase_catalog.json').read_text(encoding='utf-8'))
ROLES = {
 'SUPER_ADMIN': ('Super Admin', 'الأدمن الرئيسي'),
 'ADMIN': ('Administrator', 'مدير النظام'),
 'RECEPTION': ('Reception', 'الاستقبال'),
 'TECHNICIAN': ('Technician', 'الفني'),
 'NURSING': ('Nursing', 'التمريض'),
 'RADIOLOGIST': ('Radiologist', 'طبيب الأشعة'),
 'CASE_COORDINATOR': ('Case Coordinator', 'منسق الحالات'),
 'CASHIER': ('Cashier', 'الكاشير'),
 'BRANCH_MANAGER': ('Branch Manager', 'مدير الفرع'),
 'CALL_CENTER': ('Call Center', 'الكول سنتر'),
 'CONTRACTS': ('Contracts', 'التعاقدات'),
 'INVENTORY': ('Inventory', 'المخازن'),
 'IT': ('IT', 'تقنية المعلومات'),
 'MANAGEMENT': ('Management', 'الإدارة'),
}

def translate(text, language='en'):
    if not isinstance(text, str):
        return text
    key = ' '.join(text.split())
    pair = CATALOG.get(key)
    return pair[1 if language == 'ar' else 0] if pair else text

def role_label(role, language='en'):
    if role is None:
        return ''
    pair = ROLES.get(getattr(role, 'code', ''))
    return pair[1 if language == 'ar' else 0] if pair else getattr(role, 'name', '')

CLIENT_KEYS = ('Delete saved view?',)

def client_catalog(language="en"):
    return {key:translate(key,language) for key in CLIENT_KEYS}
