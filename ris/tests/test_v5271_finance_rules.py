
def test_finance_permissions_models_routes():
 import app as m,inspect
 for p in ['finance.discount.request','finance.discount.apply','finance.discount.approve','finance.discount.manage','finance.doctor_share.manage','finance.doctor_share.view']:
  assert p in m.ALL_PERMISSIONS
 for n in ['PerformingDoctorShareRule','OrderPerformingDoctor','DiscountPolicy','OrderDiscount','DiscountApprovalRequest']:
  assert hasattr(m,n)
 rules={r.rule for r in m.app.url_map.iter_rules()}
 for r in ['/admin/doctor-share-rules','/admin/discount-policies','/finance/discount-approvals','/finance/doctor-earnings','/orders/<int:order_id>/performing-doctor']:
  assert r in rules
 assert 'effective_patient_due' in inspect.getsource(m.order_balance)

def test_golden_regressions_preserved():
 import app as m,inspect
 assert hasattr(m,'next_patient_id')
 assert hasattr(m,'StudioShortcut')
 assert hasattr(m,'PrinterProfile')
 assert hasattr(m,'RegistrationDefault')
 assert hasattr(m,'ReferralCommissionRule')
 assert 'CaseReadiness=CaseReadiness' in inspect.getsource(m.advanced_search)
 assert 'active=True' not in inspect.getsource(m.device_booking_reason)
