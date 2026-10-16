import pytest

from domain.inventory.transfer_policy import can_perform_transfer_action, can_request_transfer


@pytest.mark.parametrize("source_linked,allowed,expected", [
    (True, [4], True),
    (False, [4], False),
    (True, [5], False),
    (True, [], False),
])
def test_request_policy_requires_linked_central_and_allowed_target(source_linked, allowed, expected):
    assert can_request_transfer(
        is_central_operator=False,
        allowed_branch_ids=allowed,
        target_branch_id=4,
        source_is_linked_to_target=source_linked,
    ) is expected


def test_central_operator_cannot_create_branch_request():
    assert not can_request_transfer(
        is_central_operator=True, allowed_branch_ids=[4], target_branch_id=4,
        source_is_linked_to_target=True,
    )


@pytest.mark.parametrize("action,central,permission,expected", [
    ("approve", True, True, True),
    ("reject", True, True, True),
    ("dispatch", True, True, True),
    ("approve", True, False, False),
    ("approve", False, True, False),
    ("unknown", True, True, False),
])
def test_central_actions_require_central_operator_and_permission(action, central, permission, expected):
    assert can_perform_transfer_action(
        action=action, is_central_operator=central, has_approval_permission=permission,
        allowed_branch_ids=[4],
    ) is expected


def test_receive_is_limited_to_authorized_branch():
    assert can_perform_transfer_action(
        action="receive", is_central_operator=False, has_approval_permission=False,
        allowed_branch_ids=[4], target_branch_id=4,
    )
    assert not can_perform_transfer_action(
        action="receive", is_central_operator=False, has_approval_permission=False,
        allowed_branch_ids=[4], target_branch_id=5,
    )
