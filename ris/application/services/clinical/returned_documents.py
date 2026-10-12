"""Read-only document prerequisite checks; no image or review approval."""


class ReturnedDocuments:
    def __init__(self, repository, *, quality_rule, attachment_count):
        self.repository = repository
        self.quality_rule = quality_rule
        self.attachment_count = attachment_count

    def ready(self, order, state):
        rule = self.quality_rule(order)
        history_required = bool((rule and rule.require_history) or state['reason'] == 'MISSING_HISTORY')
        if history_required and not self.repository.has_history(order.id):
            return False
        return not (rule and rule.require_attachments and self.attachment_count(order) < 1)
