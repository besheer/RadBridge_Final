"""Pure authorization rules for central-to-branch stock transfers."""


CENTRAL_ACTIONS = frozenset({"approve", "reject", "dispatch"})
TRANSFER_TRANSITIONS = {
    ("REQUESTED", "approve"): "APPROVED",
    ("REQUESTED", "reject"): "REJECTED",
    ("APPROVED", "reject"): "REJECTED",
    ("APPROVED", "dispatch"): "DISPATCHED",
    ("DISPATCHED", "receive"): "RECEIVED",
}


def transfer_status_after(current_status, action):
    """Return the next valid transfer status, or None when the transition is invalid."""
    return TRANSFER_TRANSITIONS.get((str(current_status or "").upper(), str(action or "").lower()))


def can_request_transfer(*, is_central_operator, allowed_branch_ids, target_branch_id,
                         source_is_linked_to_target):
    """Branches may request stock only from their linked central warehouse."""
    allowed = {branch_id for branch_id in (allowed_branch_ids or ()) if branch_id is not None}
    return (
        not is_central_operator
        and target_branch_id is not None
        and target_branch_id in allowed
        and bool(source_is_linked_to_target)
    )


def can_perform_transfer_action(*, action, is_central_operator, has_approval_permission,
                                allowed_branch_ids, target_branch_id=None):
    """Central approval permission gates central actions; receiving stays branch-scoped."""
    if action in CENTRAL_ACTIONS:
        return bool(is_central_operator and has_approval_permission)
    if action == "receive":
        allowed = {branch_id for branch_id in (allowed_branch_ids or ()) if branch_id is not None}
        return not is_central_operator and target_branch_id is not None and target_branch_id in allowed
    return False
