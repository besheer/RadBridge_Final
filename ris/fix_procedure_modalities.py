import re
from app import app, db, Procedure

with app.app_context():
    procs = Procedure.query.all()
    updated = 0
    
    for p in procs:
        en = p.name or ""
        ar = p.name_ar or ""
        full = f"{en} {ar}".lower()
        
        old_m = p.modality
        old_c = p.category
        
        # Rule 1: Neurophysiology
        if any(w in ar for w in ['رسم']) or re.search(r'\b(eeg|emg|nerve|brachial)\b', en, re.I):
            p.modality = 'EEG'
            p.category = 'Neurophysiology'
        # Rule 2: Fluoroscopy / Special X-Ray
        elif any(w in ar for w in ['باريوم', 'صبغة صاعدة', 'مجرى بولي بالصبغة', 'مسالك بالصبغة', 'رحم h.c.g', 'ناصور بالصبغة']) or re.search(r'\b(barium|fistulography|cavernosography|cystourethrography|hystrosalpingoraphy|urethrography|i\.v\.p)\b', en, re.I):
            p.modality = 'RF'
            p.category = 'Fluoroscopy'
        # Rule 3: MRI
        elif any(w in ar for w in ['رنين']) or re.search(r'\b(mri|mra|mrv|mrcp|mru)\b', en, re.I):
            p.modality = 'MR'
            p.category = 'MRI'
        # Rule 4: CT Scan
        elif any(w in ar for w in ['مقطعية', 'مقطعيه']) or re.search(r'\b(ct|scanogram|virtual colonoscopy|vitrual bronchoscopy)\b', en, re.I):
            p.modality = 'CT'
            p.category = 'CT Scan'
        # Rule 5: Doppler
        elif any(w in ar for w in ['دوبلر']) or re.search(r'\b(doppler)\b', en, re.I):
            p.modality = 'US'
            p.category = 'Doppler'
        # Rule 6: Ultrasound
        elif any(w in ar for w in ['تلفزيونية', 'تلفزيونيه', 'سونار', 'موجات صوتية', 'موجات فوق']) or re.search(r'\b(us|ultrasound|folliculometry)\b', en, re.I):
            p.modality = 'US'
            p.category = 'Ultrasound'
        # Rule 7: General / Plain X-Ray
        elif any(w in ar for w in ['عادية', 'عاديه', 'أشعة سينية', 'اشعة سينية', 'فيلم كبير']) or re.search(r'\b(x-ray|xray|plain|humerus|clavicle|pelvis|skull|spine|chest|femur|knee|ankle|wrist|elbow|radius|ulna|tibia|fibula)\b', en, re.I):
            p.modality = 'DX'
            p.category = 'X-Ray'
            
        if p.modality != old_m or p.category != old_c:
            updated += 1
            
    db.session.commit()
    print(f"RECLASSIFICATION_COMPLETE: Updated {updated} procedures.")
