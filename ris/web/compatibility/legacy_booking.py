"""The older appointments entry uses the canonical scheduling safety gates."""
from flask import flash, redirect, request, url_for
from application.services.registration.appointment_creation import AppointmentCreation
from infrastructure.adapters.registration.appointment_repository import SqlAlchemyAppointmentRepository


def create_booking():
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    from registration_policy import require_registration_branch
    branch_id=request.form.get('branch_id',type=int)
    require_registration_branch(branch_id)
    savepoint=m.db.session.begin_nested()
    try:
        repository=SqlAlchemyAppointmentRepository(m.db.session,Branch=m.Branch,Procedure=m.Procedure,
            Patient=m.Patient,Device=m.Device,Appointment=m.Appointment)
        service=AppointmentCreation(repository,procedure_available=m.procedure_available_in_branch,
            route_device=m.route_device,lock_slot=m.acquire_booking_slot_lock,
            restriction_reason=m.booking_restriction_reason,actor_id=lambda:m.current_user().id,audit=m.audit)
        service.create(dict(branch_id=branch_id,procedure_id=request.form.get('procedure_id',type=int),
            patient_id=request.form.get('patient_id',type=int),device_id=request.form.get('device_id',type=int),
            scheduled=request.form.get('scheduled',''),source=request.form.get('source','CALL_CENTER'),
            notes=request.form.get('notes','')))
        savepoint.commit()
        m.db.session.commit()
        flash('Appointment booked. / تم تسجيل الحجز.','success')
    except (ValueError,TypeError) as exc:
        savepoint.rollback()
        flash('Booking blocked / تعذر الحجز: '+str(exc),'danger')
    return redirect(url_for('appointments'))
