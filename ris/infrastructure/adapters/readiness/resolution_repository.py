"""SQL readiness evidence/alias/override operations with explicit model ownership."""


class SqlAlchemyReadinessResolutionRepository:
    def __init__(self,session,Order,Report,ProcedureQualityRule=None,ReadinessSeriesAlias=None,
                 ResolutionEvent=None,CaseReadiness=None,ClinicalNote=None,CaseReadinessOverride=None):
        self.session,self.Order,self.Report=session,Order,Report
        self.QualityRule,self.Alias,self.Event=ProcedureQualityRule,ReadinessSeriesAlias,ResolutionEvent
        self.Readiness,self.Note,self.Override=CaseReadiness,ClinicalNote,CaseReadinessOverride
        self.has_readiness=CaseReadiness is not None
    def lock_order(self,order_id):
        return self.session.query(self.Order).filter(self.Order.id==int(order_id)).with_for_update().one()
    def latest_report_status(self,order_id):
        M=self.Report
        row=self.session.query(M).filter(M.order_id==int(order_id)).order_by(M.id.desc()).first()
        return getattr(row,'status','')
    def lock_readiness(self,order_id):
        M=self.Readiness
        return self.session.query(M).filter(M.order_id==order_id).with_for_update().first()
    def lock_quality_rules(self,modality):
        M=self.QualityRule
        return self.session.query(M).filter(M.active.is_(True),M.modality==modality).with_for_update().all()
    def lock_alias_key(self,rule_id,normalized,field):
        M=self.Alias
        return self.session.query(M).filter(M.rule_id==rule_id,M.alias_normalized==normalized,M.match_field==field).with_for_update().first()
    def lock_alias_id(self,alias_id):
        M=self.Alias
        return self.session.query(M).filter(M.id==int(alias_id)).with_for_update().one()
    def lock_active_override(self,order_id):
        M=self.Override
        return self.session.query(M).filter(M.order_id==order_id,M.blocker=='INCOMPLETE_IMAGES',M.active.is_(True)).with_for_update().first()
    def lock_override_id(self,order_id,override_id):
        M=self.Override
        return self.session.query(M).filter(M.id==int(override_id),M.order_id==order_id).with_for_update().one()
    def create_alias(self,**values):return self.Alias(**values)
    def create_event(self,**values):return self.Event(**values)
    def create_note(self,**values):return self.Note(**values)
    def create_override(self,**values):return self.Override(**values)
    def add(self,row):self.session.add(row)
    def flush(self):self.session.flush()
