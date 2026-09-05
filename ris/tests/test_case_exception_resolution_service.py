from types import SimpleNamespace

import pytest

from case_exception_resolution_service import (
    CaseExceptionResolutionError,
    apply_series_aliases,
    assert_editable,
    normalize,
)


def alias(source, canonical, field="EITHER", active=True):
    return SimpleNamespace(
        source_alias=source,
        alias_normalized=normalize(source),
        canonical_series=canonical,
        match_field=field,
        active=active,
    )


def test_series_alias_enriches_copy_without_changing_source():
    source = [{"description": "Brain Routine", "protocol": "Head",
               "modality": "CT", "instance_count": 30}]
    result = apply_series_aliases(source, [alias("Brain Routine", "AXIAL")])
    assert result[0]["description"] == "Brain Routine AXIAL"
    assert result[0]["mapped_series"] == ["AXIAL"]
    assert source[0]["description"] == "Brain Routine"


def test_alias_field_and_active_state_are_respected():
    source = [{"description": "Routine", "protocol": "Thin Ax",
               "modality": "CT", "instance_count": 10}]
    result = apply_series_aliases(source, [
        alias("Thin Ax", "AXIAL", "DESCRIPTION"),
        alias("Thin Ax", "CORONAL", "PROTOCOL", active=False),
    ])
    assert "mapped_series" not in result[0]


@pytest.mark.parametrize("order_status,report_status", [
    ("FINAL", "UNREPORTED"),
    ("IMAGES_RECEIVED", "VERIFIED"),
    ("CANCELLED", "DRAFT"),
])
def test_terminal_cases_are_locked(order_status, report_status):
    with pytest.raises(CaseExceptionResolutionError):
        assert_editable(order_status, report_status)


def test_editable_case_is_allowed():
    assert_editable("IMAGES_RECEIVED", "UNREPORTED")
