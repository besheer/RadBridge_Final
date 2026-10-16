"""Stable correction workflow errors and lifecycle constants."""
CLINICAL_ROLES={'RADIOLOGIST','DOCTOR','CONSULTANT','RADIOLOGY_CONSULTANT'}
COORDINATOR_ROLES={'SUPER_ADMIN','ADMIN','CASE_COORDINATOR','BRANCH_MANAGER'}
ACTIVE={'REQUESTED','DRAFT','VERIFIED'}

class RevisionError(ValueError):
    def __init__(self,code):self.code=code;super().__init__(code)
