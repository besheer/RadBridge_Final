"""Read-only RT worklist/detail projections over an explicit repository."""
from domain.clinical.rt_course_policy import RTWorkflowError


class RTReadQueries:
    def __init__(self, repository):
        self.repository=repository

    def worklist(self, *, global_access, branch_id, scope, search=''):
        return self.repository.worklist(global_access,branch_id,scope,str(search or '').strip())

    def device_allowed(self, scope, device):
        return not scope or self.repository.device_matches(scope,device)

    def detail(self, *, course_id, authorize_course, scope_provider):
        course=self.repository.course(course_id)
        if course is None:raise RTWorkflowError('COURSE_NOT_FOUND')
        authorize_course(course)
        plan=self.repository.current_plan(course.id)
        devices=self.repository.devices(course.branch_id)
        scope=scope_provider()
        if scope:
            devices=[device for device in devices if self.repository.device_matches(scope,device)]
        ids=[device.id for device in devices]
        return dict(course=course,plan=plan,devices=devices,
            plans=self.repository.plans(course.id),fractions=self.repository.fractions(course.id,ids),
            pet_links=self.repository.pet_links(course.id),notes=self.repository.notes(course.id,ids),
            consumables=self.repository.consumables(course.id,ids))
