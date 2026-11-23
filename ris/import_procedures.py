import csv
import re
from app import app, db, Procedure, ProcedureBranch, Branch

def clean_str(s):
    if not s:
        return ""
    return re.sub(r'\s+', ' ', s).strip()

def determine_modality_category(name_en, name_ar):
    t = (name_en + " " + name_ar).lower()
    
    # Neurophysiology / EEG / EMG
    if any(k in t for k in ['eeg', 'nerve conduction', 'emg', 'brachial plexus', 'رسم']):
        return 'EEG', 'Neurophysiology'
    
    # Doppler
    if 'doppler' in t or 'دوبلر' in t:
        return 'US', 'Doppler'
        
    # Ultrasound / Sonar
    if any(k in t for k in ['us', 'ultrasound', 'سونار', 'تلفزيونية', 'folliculometry', 'شفط سائل']):
        return 'US', 'Ultrasound'
        
    # MRI / Magnetic Resonance
    if any(k in t for k in ['mri', 'mra', 'mrv', 'mrcp', 'mru', 'رنين']):
        return 'MR', 'MRI'
        
    # CT Scan / Computed Tomography
    if any(k in t for k in ['ct', 'مقطعية', 'scanogram', 'virtual colonoscopy', 'vitrual bronchoscopy', 'triphasic ct']):
        return 'CT', 'CT Scan'
        
    # X-Ray / Fluoroscopy
    if any(k in t for k in ['x-ray', 'xray', 'عادية', 'عاديه', 'fistulography', 'cavernosography', 'barium', 'hystrosalpingoraphy', 'i.v.p', 'urethrography', 'cystourethrography', 'larynx plain', 'film']):
        return 'DX', 'X-Ray'
        
    return 'DX', 'General'

def make_code(name_en, modality, existing_codes):
    # Clean text to alphanumeric uppercase
    base = re.sub(r'[^A-Za-z0-9]+', '-', name_en).strip('-').upper()
    if not base:
        base = f"{modality}-PROC"
    code = f"{modality}-{base}"[:35]
    
    # Avoid collisions
    candidate = code
    counter = 1
    while candidate in existing_codes:
        candidate = f"{code[:30]}-{counter}"
        counter += 1
    return candidate

with app.app_context():
    main_branch = Branch.query.filter_by(code="MAIN").first() or Branch.query.first()
    branch_id = main_branch.id if main_branch else 1
    
    # Existing procedures map
    existing_by_code = {p.code: p for p in Procedure.query.all()}
    existing_by_name = {p.name.strip().lower(): p for p in Procedure.query.all()}
    existing_by_name_ar = {p.name_ar.strip(): p for p in Procedure.query.filter(Procedure.name_ar != None).all()}
    all_codes = set(existing_by_code.keys())
    
    inserted = 0
    updated = 0
    skipped = 0
    
    with open('/app/user_procedures.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or len(row) < 1:
                continue
            item_en = clean_str(row[0])
            item_ar = clean_str(row[1]) if len(row) > 1 else ""
            
            # Skip header or empty rows
            if item_en.lower() in ['item', 'الدوبلر', ''] and (not item_ar or item_ar.lower() in ['itemnamea', '']):
                continue
            if not item_en and not item_ar:
                continue
            if not item_en and item_ar:
                item_en = item_ar # Fallback
            if not item_ar and item_en:
                item_ar = item_en # Fallback
                
            modality, category = determine_modality_category(item_en, item_ar)
            contrast = True if any(k in (item_en + " " + item_ar).lower() for k in ['contrast', 'صبغة', 'صبغه', 'triphasic']) else False
            
            # Check if procedure already exists by English name or Arabic name
            proc = existing_by_name.get(item_en.lower()) or existing_by_name_ar.get(item_ar)
            
            if proc:
                # Update existing
                if item_ar and not proc.name_ar:
                    proc.name_ar = item_ar
                proc.active = True
                updated += 1
            else:
                # Create new procedure
                code = make_code(item_en, modality, all_codes)
                all_codes.add(code)
                
                proc = Procedure(
                    code=code,
                    name=item_en,
                    name_ar=item_ar,
                    category=category,
                    modality=modality,
                    contrast=contrast,
                    active=True,
                    base_price=0.0,
                    duration_min=15
                )
                db.session.add(proc)
                db.session.flush()
                existing_by_code[code] = proc
                existing_by_name[item_en.lower()] = proc
                existing_by_name_ar[item_ar] = proc
                inserted += 1
                
            # Ensure branch link
            pb = ProcedureBranch.query.filter_by(branch_id=branch_id, procedure_id=proc.id).first()
            if not pb:
                db.session.add(ProcedureBranch(branch_id=branch_id, procedure_id=proc.id, active=True))
            else:
                pb.active = True

    db.session.commit()
    print(f"IMPORT_COMPLETE: Inserted {inserted} new procedures, Updated {updated} existing procedures.")
