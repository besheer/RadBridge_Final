from app import app, db, Device, Branch

devices_data = [
    {
        "name": "MRI 0.3T (جهاز الرنين)",
        "modality": "MR",
        "ae_title": "MRI03T",
        "ip": "172.17.2.2",
        "port": 104,
        "room": "غرفة الرنين المغناطيسي",
        "priority": 1,
        "active": True,
        "operational_status": "OPERATIONAL",
        "booking_enabled": True,
        "workday_start": "08:00",
        "workday_end": "23:00"
    },
    {
        "name": "CT Scanner (الأشعة المقطعية)",
        "modality": "CT",
        "ae_title": "CT01",
        "ip": "127.0.0.1",
        "port": 104,
        "room": "غرفة الأشعة المقطعية",
        "priority": 2,
        "active": True,
        "operational_status": "OPERATIONAL",
        "booking_enabled": True,
        "workday_start": "08:00",
        "workday_end": "23:00"
    },
    {
        "name": "Digital X-Ray (الأشعة العادية)",
        "modality": "DX",
        "ae_title": "XRAY01",
        "ip": "127.0.0.1",
        "port": 104,
        "room": "غرفة الأشعة العادية",
        "priority": 3,
        "active": True,
        "operational_status": "OPERATIONAL",
        "booking_enabled": True,
        "workday_start": "08:00",
        "workday_end": "23:00"
    },
    {
        "name": "Ultrasound & Doppler (السونار)",
        "modality": "US",
        "ae_title": "US01",
        "ip": "127.0.0.1",
        "port": 104,
        "room": "عيادة السونار والدوبلر",
        "priority": 4,
        "active": True,
        "operational_status": "OPERATIONAL",
        "booking_enabled": True,
        "workday_start": "08:00",
        "workday_end": "23:00"
    },
    {
        "name": "EEG / EMG (رسم المخ والأعصاب)",
        "modality": "EEG",
        "ae_title": "EEG01",
        "ip": "127.0.0.1",
        "port": 104,
        "room": "غرفة رسم المخ والأعصاب",
        "priority": 5,
        "active": True,
        "operational_status": "OPERATIONAL",
        "booking_enabled": True,
        "workday_start": "08:00",
        "workday_end": "23:00"
    }
]

with app.app_context():
    branch = Branch.query.filter_by(code="MAIN").first() or Branch.query.first()
    branch_id = branch.id if branch else 1
    
    count = 0
    for d in devices_data:
        existing = Device.query.filter_by(name=d["name"]).first()
        if not existing:
            dev = Device(
                branch_id=branch_id,
                name=d["name"],
                modality=d["modality"],
                ae_title=d["ae_title"],
                ip=d.get("ip"),
                port=d.get("port"),
                room=d.get("room"),
                priority=d.get("priority", 1),
                active=d["active"],
                operational_status=d["operational_status"],
                booking_enabled=d["booking_enabled"],
                workday_start=d["workday_start"],
                workday_end=d["workday_end"]
            )
            db.session.add(dev)
            count += 1
        else:
            existing.active = True
            existing.booking_enabled = True
            
    db.session.commit()
    print(f"DEVICES_ADDED: Added {count} devices.")
