from web.source_contract import read_source as _read_source
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Environment


def render(perms, role='CASE_COORDINATOR', branch=42, lang='en'):
    source = Path(__file__).parents[1] / 'templates' / '_coordinator_dashboard.html'
    return Environment(autoescape=True).from_string(_read_source(source)).render(
        has_perm=lambda p: '*' in perms or p in perms,
        me=SimpleNamespace(role=SimpleNamespace(code=role), branch_id=branch),
        ui_lang=lang,
        url_for=lambda endpoint, **kwargs: '/' + endpoint +
        ('?state=' + kwargs['state'] if kwargs else ''),
    )


@pytest.mark.parametrize('perms', [set(), {'orders.view'}, {'reports.view'}])
def test_unrelated_roles_have_no_coordinator_section(perms):
    assert 'coordinator-dashboard' not in render(perms, role='TECHNICIAN')


def test_coordinator_links_match_permissions():
    page = render({'reports.coordinate'})
    assert '/coordinator_queue' in page
    assert '/coordinator_assignments' in page
    assert '/coordinator_manual_assignment' in page
    assert '/assignment_dashboard' not in page
    assert '/correction_center' not in page


@pytest.mark.parametrize('role,branch', [('CASE_COORDINATOR', None), ('TECHNICIAN', 42)])
def test_bulk_assignment_actor_requirements(role, branch):
    assert '/coordinator_manual_assignment' not in render({'reports.coordinate'}, role, branch)


def test_assignment_manager_does_not_receive_report_review_link():
    page = render({'assignment.manage', 'orders.view'}, role='BRANCH_MANAGER')
    assert '/coordinator_queue' not in page
    assert '/coordinator_assignments' in page
    assert '?state=READY_UNASSIGNED' in page
    assert '?state=OVERDUE' in page
    assert '/returned_cases_queue' in page


def test_arabic_and_admin_tools():
    page = render({'*'}, role='SUPER_ADMIN', branch=None, lang='ar')
    assert 'المنسقون وإدارة الحالات' in page
    assert '/coordinator_manual_assignment' in page
    assert '/correction_center' in page
    assert 'Medical approval remains' not in page
