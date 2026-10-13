"""Reviewed demographic requests through explicit persistence and policy ports.

Approval records review only. The caller owns authorization and commit/rollback.
"""
import hashlib
import json
from domain.registration.demographic_correction import FIELDS, IDENTITY_FIELDS, normalize_value


class ReviewDenied(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status=status


class DemographicCorrections:
    def __init__(self, repository, *, registration_rules, validate_registration,
                 actor_id, branch_allowed, audit, today):
        self.repository=repository
        self.registration_rules=registration_rules
        self.validate_registration=validate_registration
        self.actor_id,self.branch_allowed=actor_id,branch_allowed
        self.audit,self.today=audit,today

    def current_value(self, patient, field):
        if field=='nationality':return self.repository.nationality(patient.id)
        return str(getattr(patient,field,'') or '')

    def patient_orders(self, patient):return self.repository.orders(patient.id)

    def snapshot(self, patient):
        rows=[]
        for order in self.patient_orders(patient):
            report=order.report
            rows.append([order.id,order.branch_id,order.status,order.exam_status,
                         order.pacs_study_id,order.pacs_image_count,
                         report.status if report else '',
                         report.version if report and hasattr(report,'version') else '',
                         self.repository.report_version_count(report.id) if report else 0])
        bookings=[[a.id,a.branch_id,a.status,a.order_id,str(a.scheduled)]
                  for a in self.repository.bookings(patient.id)]
        data={'values':{field:self.current_value(patient,field) for field in FIELDS},
              'estimated':bool(patient.dob_estimated),'orders':rows,'bookings':bookings}
        return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

    def impact(self, patient, field):
        orders=self.patient_orders(patient)
        return dict(orders=len(orders),visits=self.repository.visit_count(patient.id),
                    bookings=self.repository.booking_count(patient.id),
                    pacs_orders=sum(bool(o.pacs_study_id) for o in orders),
                    final_reports=sum(bool(o.report and o.report.status=='FINAL') for o in orders),
                    reviewed_reports=sum(bool(o.report and o.report.status=='VERIFIED') for o in orders),
                    branches=len({o.branch_id for o in orders}),identity_change=field in IDENTITY_FIELDS)

    def normalize(self, field, value):
        value=normalize_value(field,value,self.today())
        rule=self.registration_rules().get('patient.'+field)
        ok,message=self.validate_registration(rule,value)
        if not ok:raise ValueError(message)
        return value

    def submit(self, order, field, value, reason, expected_snapshot):
        patient=order.patient
        value=self.normalize(field,value);reason=str(reason or '').strip()
        if len(reason)<5:raise ValueError('Correction reason must contain at least 5 characters')
        if self.current_value(patient,field)==value:raise ValueError('New value must differ / القيمة لم تتغير')
        if self.snapshot(patient)!=expected_snapshot:raise ValueError('Patient or workflow changed. Reload preview / تغيرت البيانات؛ أعد المعاينة')
        if self.repository.open_request(order.id):raise ValueError('An active demographic correction request already exists')
        row=self.repository.add_request(order,reason[:2000],self.actor_id())
        self.repository.add_detail(row,patient,field,self.current_value(patient,field),value,
                                   self.snapshot(patient),json.dumps(self.impact(patient,field)))
        self.audit('PATIENT_DEMOGRAPHICS_CORRECTION_REQUEST','correction_request',row.id,
                   'Structured field='+field+'; clinical data unchanged')
        return row

    def assert_approvable(self, row):
        detail=row.demographic_detail
        if not detail:raise ReviewDenied(409,'Legacy request needs a structured replacement before approval')
        patient=self.repository.lock_patient(detail.patient_id)
        if patient is None:raise ReviewDenied(404,'Patient not found')
        if self.snapshot(patient)!=detail.snapshot_hash:raise ReviewDenied(409,'Patient or workflow changed; submit a new preview')
        for order in self.patient_orders(patient):
            if not self.branch_allowed(order):raise ReviewDenied(403,'Review across all affected branches is required')
        try:self.normalize(detail.field_name,detail.proposed_value)
        except ValueError:raise ReviewDenied(409,'Proposed value no longer meets registration rules')
