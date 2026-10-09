
def test_reauth_data_admin():
 import app as m
 assert hasattr(m,'verify_current_user_password')
 assert hasattr(m,'create_all_patient_backup')
 assert hasattr(m,'delete_all_patient_operational_data')
 rules={r.rule for r in m.app.url_map.iter_rules()}
 assert '/admin/data-management/backup-all-patients' in rules
 assert '/admin/data-management/delete-all-patients' in rules
 assert 'backup.all_patients' in m.ALL_PERMISSIONS
 assert 'data.delete.all_patients' in m.ALL_PERMISSIONS
 assert 'audit_log' not in m.operational_patient_table_order()
 assert 'user' not in m.operational_patient_table_order()
 assert 'branch' not in m.operational_patient_table_order()
