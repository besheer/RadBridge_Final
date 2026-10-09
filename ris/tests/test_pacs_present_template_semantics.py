from pathlib import Path
from types import SimpleNamespace
from jinja2 import Environment


TEMPLATE_PATH=Path(
    "/app/templates/admin_cancellation_preview.html"
)


def _source():
    return TEMPLATE_PATH.read_text()


def _pacs_row_template():
    src=_source()

    marker="<td>PACS Images</td>"
    marker_pos=src.index(marker)

    start=src.rfind("<tr>",0,marker_pos)
    end=src.index("</tr>",marker_pos)+len("</tr>")

    env = Environment()
    env.globals['ui_phrase'] = __import__('ui_localization').translate
    return env.from_string(
        src[start:end]
    )


def _action_template():
    src=_source()

    marker="<!-- RB_GRANULAR_DELETE_IMAGES_ONLY_UI_V2 -->"
    start=src.index(marker)

    end=src.index(
        "{% endif %}",
        start,
    )+len("{% endif %}")

    env=Environment()
    env.globals['ui_phrase'] = __import__('ui_localization').translate

    env.globals["url_for"]=(
        lambda endpoint,**kwargs:
        f"/TEST/{endpoint}/{kwargs.get('order_id')}"
    )

    return env.from_string(
        src[start:end]
    )


def _preview(
    linked,
    present,
    status,
    image_count,
):
    return SimpleNamespace(
        kind="ORDER",
        order=SimpleNamespace(
            id=38,
            accession="TEST-ACCESSION",
        ),
        pacs=SimpleNamespace(
            linked=linked,
            present=present,
            status=status,
            image_count=image_count,
            study_id=(
                "TEST-STUDY"
                if linked
                else None
            ),
        ),
    )


def _render_status(
    linked,
    present,
    status,
    image_count,
):
    template=_pacs_row_template()

    rendered=template.render(
        preview=_preview(
            linked,
            present,
            status,
            image_count,
        )
    )

    return " ".join(rendered.split())


def _render_action(
    linked,
    present,
    status,
    image_count,
):
    template=_action_template()

    rendered=template.render(
        preview=_preview(
            linked,
            present,
            status,
            image_count,
        )
    )

    return " ".join(rendered.split())


def test_visible_status_none():
    rendered=_render_status(
        False,
        False,
        None,
        0,
    )

    assert "NONE / NOT LINKED" in rendered


def test_visible_status_present():
    rendered=_render_status(
        True,
        True,
        "IMAGES_COMPLETE",
        3,
    )

    assert "> PRESENT <" in rendered


def test_visible_status_deleted():
    rendered=_render_status(
        True,
        False,
        "IMAGES_DELETED",
        0,
    )

    assert "> DELETED <" in rendered
    assert "> PRESENT <" not in rendered


def test_visible_status_missing():
    rendered=_render_status(
        True,
        False,
        "IMAGES_COMPLETE",
        3,
    )

    assert "MISSING — REVIEW" in rendered


def test_visible_status_unknown():
    rendered=_render_status(
        True,
        None,
        "IMAGES_COMPLETE",
        3,
    )

    assert "> REVIEW <" in rendered


def test_delete_action_active_only():
    rendered=_render_action(
        True,
        True,
        "IMAGES_COMPLETE",
        3,
    )

    assert 'name="confirm_accession"' in rendered
    assert "> Delete PACS Images Only <" in rendered


def test_delete_action_hidden_deleted():
    rendered=_render_action(
        True,
        False,
        "IMAGES_DELETED",
        0,
    )

    assert 'name="confirm_accession"' not in rendered


def test_delete_action_hidden_missing():
    rendered=_render_action(
        True,
        False,
        "IMAGES_COMPLETE",
        3,
    )

    assert 'name="confirm_accession"' not in rendered


def test_delete_action_hidden_unknown():
    rendered=_render_action(
        True,
        None,
        "IMAGES_COMPLETE",
        3,
    )

    assert 'name="confirm_accession"' not in rendered


def test_delete_action_hidden_no_link():
    rendered=_render_action(
        False,
        False,
        None,
        0,
    )

    assert 'name="confirm_accession"' not in rendered


def test_delete_action_hidden_zero_images():
    rendered=_render_action(
        True,
        True,
        "IMAGES_COMPLETE",
        0,
    )

    assert 'name="confirm_accession"' not in rendered


def test_delete_action_hidden_deleted_status_even_if_present():
    rendered=_render_action(
        True,
        True,
        "IMAGES_DELETED",
        3,
    )

    assert 'name="confirm_accession"' not in rendered

def test_delete_action_is_not_nested_under_safety_blockers():
    src=_source()

    action_pos=src.index(
        "<!-- RB_GRANULAR_DELETE_IMAGES_ONLY_UI_V2 -->"
    )
    blockers_pos=src.index(
        "{% if preview.safety.blockers %}"
    )
    safety_heading_pos=src.index(
        "<h3>Safety Blockers</h3>"
    )

    assert action_pos < blockers_pos < safety_heading_pos

