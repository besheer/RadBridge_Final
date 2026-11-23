from app import app, db, User, Role, Branch, UserProfile
from werkzeug.security import generate_password_hash

users_to_create = [
    {
        "username": "it_admin",
        "full_name": "مسؤول تقنية المعلومات - IT Admin",
        "role_code": "IT",
        "department": "IT",
        "specialty": "Information Technology"
    },
    {
        "username": "reception",
        "full_name": "الاستقبال - Receptionist",
        "role_code": "RECEPTION",
        "department": "Reception",
        "specialty": "Patient Intake & Scheduling"
    },
    {
        "username": "callcenter",
        "full_name": "خدمة العملاء - Call Center",
        "role_code": "CALL_CENTER",
        "department": "Call Center",
        "specialty": "Appointments & Support"
    },
    {
        "username": "nurse",
        "full_name": "طاقم التمريض - Staff Nurse",
        "role_code": "NURSING",
        "department": "Nursing",
        "specialty": "Patient Preparation"
    },
    {
        "username": "technician",
        "full_name": "فني الرنين والأشعة - Technician",
        "role_code": "TECHNICIAN",
        "department": "Radiology",
        "specialty": "MRI & CT Acquisition"
    },
    {
        "username": "doctor_mri",
        "full_name": "د. أحمد - طبيب أشعة (Radiologist)",
        "role_code": "RADIOLOGIST",
        "department": "Radiology",
        "specialty": "MRI & Diagnostic Imaging"
    },
    {
        "username": "coordinator",
        "full_name": "منسق الحالات - Case Coordinator",
        "role_code": "CASE_COORDINATOR",
        "department": "Coordination",
        "specialty": "Case Assignment & Tracking"
    },
    {
        "username": "manager",
        "full_name": "مدير الفرع - Branch Manager",
        "role_code": "BRANCH_MANAGER",
        "department": "Administration",
        "specialty": "Branch Operations"
    },
    {
        "username": "cashier",
        "full_name": "الخزينة والكاشير - Cashier",
        "role_code": "CASHIER",
        "department": "Finance",
        "specialty": "Billing & Payments"
    },
    {
        "username": "contracts",
        "full_name": "مسؤول التعاقدات - Contracts",
        "role_code": "CONTRACTS",
        "department": "Contracts",
        "specialty": "Insurance & Companies"
    },
    {
        "username": "inventory",
        "full_name": "مسؤول المخازن - Inventory",
        "role_code": "INVENTORY",
        "department": "Inventory",
        "specialty": "Consumables & Stock"
    },
    {
        "username": "management",
        "full_name": "الإدارة العليا - General Management",
        "role_code": "MANAGEMENT",
        "department": "Executive",
        "specialty": "Strategic Management"
    },
    {
        "username": "service",
        "full_name": "الخدمات والصيانة - Service",
        "role_code": "SERVICE",
        "department": "Support",
        "specialty": "Maintenance & Services"
    },
    {
        "username": "doctor_rt",
        "full_name": "طبيب علاج إشعاعي - RT Physician",
        "role_code": "RADIOTHERAPY_PHYSICIAN",
        "department": "Radiotherapy",
        "specialty": "Radiation Oncology"
    }
]

DEFAULT_PASSWORD = "Password@2026"

with app.app_context():
    main_branch = Branch.query.filter_by(code="MAIN").first() or Branch.query.first()
    branch_id = main_branch.id if main_branch else None
    
    created_count = 0
    updated_count = 0
    
    for u_data in users_to_create:
        role = Role.query.filter_by(code=u_data["role_code"]).first()
        if not role:
            print(f"Role {u_data['role_code']} not found, skipping...")
            continue
            
        existing_user = User.query.filter_by(username=u_data["username"]).first()
        if existing_user:
            existing_user.full_name = u_data["full_name"]
            existing_user.role_id = role.id
            existing_user.branch_id = branch_id
            existing_user.password_hash = generate_password_hash(DEFAULT_PASSWORD)
            existing_user.active = True
            existing_user.must_change_password = False
            updated_count += 1
            user_obj = existing_user
        else:
            user_obj = User(
                username=u_data["username"],
                full_name=u_data["full_name"],
                password_hash=generate_password_hash(DEFAULT_PASSWORD),
                role_id=role.id,
                branch_id=branch_id,
                active=True,
                must_change_password=False
            )
            db.session.add(user_obj)
            db.session.flush()
            created_count += 1
            
        # Ensure user profile
        prof = UserProfile.query.filter_by(user_id=user_obj.id).first()
        if not prof:
            prof = UserProfile(
                user_id=user_obj.id,
                department=u_data["department"],
                specialty=u_data["specialty"],
                ui_language="ar",
                theme="light"
            )
            db.session.add(prof)
        else:
            prof.department = u_data["department"]
            prof.specialty = u_data["specialty"]
            prof.ui_language = "ar"
            
    db.session.commit()
    print(f"SUCCESS: Created {created_count} users, Updated {updated_count} users with default password '{DEFAULT_PASSWORD}'.")
