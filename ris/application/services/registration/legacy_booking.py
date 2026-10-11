"""The older appointments entry uses the canonical scheduling safety gates."""
from datetime import datetime
from flask import flash, redirect, request, url_for


def create_booking():
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    from registration_policy import require_registration_branch
    branch_id=request.form.get('branch_id',type=int)
    require_registration_branch(branch_id)
    savepoint=m.db.session.begin_nested()
    try:
        branch=m.Branch.query.filter_by(id=branch_id,active=True).first()
        procedure=m.Procedure.query.filter_by(id=request.form.get('procedure_id',type=int),active=True).first()
        patient=m.db.session.get(m.Patient,request.form.get('patient_id',type=int))
        if not branch or not procedure or not patient:
            raise ValueError('Choose an active branch, examination and existing patient.')
        if not m.procedure_available_in_branch(procedure.id,branch.id):
            raise ValueError('Examination is not available in this branch.')
        scheduled=datetime.fromisoformat(request.form.get('scheduled',''))
        if scheduled.tzinfo is not None:
            raise ValueError('Use the local appointment date and time.')
        device_id=request.form.get('device_id',type=int)
        device=m.db.session.get(m.Device,device_id) if device_id else m.route_device(branch.id,procedure.modality)
        if not device or device.branch_id!=branch.id or device.modality.upper()!=procedure.modality.upper():
            raise ValueError('Choose a matching device in this branch.')
        duration=procedure.duration_min or 20
        m.acquire_booking_slot_lock(device.id,scheduled)
        reason=m.booking_restriction_reason(branch,procedure,device,scheduled,duration)
        if reason:
            raise ValueError(reason)
        row=m.Appointment(patient_id=patient.id,branch_id=branch.id,procedure_id=procedure.id,
            device_id=device.id,scheduled=scheduled,duration_min=duration,status='BOOKED',
            source=request.form.get('source','CALL_CENTER'),notes=request.form.get('notes',''),
            created_by=m.current_user().id)
        m.db.session.add(row);m.db.session.flush()
        m.audit('APPOINTMENT_CREATE','appointment',row.id,str(row.scheduled))
        savepoint.commit()
        m.db.session.commit()
        flash('Appointment booked. / تم تسجيل الحجز.','success')
    except (ValueError,TypeError) as exc:
        savepoint.rollback()
        flash('Booking blocked / تعذر الحجز: '+str(exc),'danger')
    return redirect(url_for('appointments'))
