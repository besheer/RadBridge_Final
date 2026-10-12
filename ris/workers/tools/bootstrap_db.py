from app import app,db,seed_quality_defaults,seed_assignment_offer_policy,seed_communication_defaults,seed_v521_functional_defaults,migrate_existing_schema,seed_master_data
with app.app_context():
    db.create_all(); seed_quality_defaults(); seed_assignment_offer_policy(); seed_communication_defaults(); seed_v521_functional_defaults(); migrate_existing_schema(); seed_master_data()
print('BOOTSTRAP_OK')
