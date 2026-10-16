from web.source_contract import get_source as _get_source
def test_v527():
 import app as m, inspect
 assert hasattr(m,'ReferralCommissionRule')
 assert hasattr(m,'DailyClosing')
 rules={r.rule for r in m.app.url_map.iter_rules()}
 for r in ['/management','/management/referrals','/admin/referral-commissions','/accounting/daily-closing','/studio/shortcuts','/admin/printer-profiles','/my/registration-defaults']:
  assert r in rules
 assert hasattr(m,'next_patient_id')
 assert 'CaseReadiness=CaseReadiness' in _get_source(m.advanced_search)
 assert 'active=True' not in _get_source(m.device_booking_reason)
