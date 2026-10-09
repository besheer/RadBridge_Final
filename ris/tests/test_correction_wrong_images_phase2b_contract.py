from pathlib import Path
import ast


def source_text():

    return (
        Path(__file__).resolve().parents[1]
        / "app.py"
    ).read_text(
        encoding="utf-8"
    )


def tree():

    return ast.parse(
        source_text()
    )


def function_source(name):

    src=source_text()
    lines=src.splitlines()

    for node in ast.walk(tree()):

        if (
            isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            and node.name==name
        ):
            return "\n".join(
                lines[
                    node.lineno-1:
                    node.end_lineno
                ]
            )

    raise AssertionError(
        f"function not found: {name}"
    )


def test_single_orthanc_delete_primitive():

    src=source_text()

    assert src.count(
        "requests.delete("
    ) == 1


def test_single_delete_preflight_definition():

    src=source_text()

    assert src.count(
        "def granular_delete_images_only_preflight"
    ) == 1


def test_shared_delete_helper_exists():

    helper=function_source(
        "granular_delete_images_only_execute"
    )

    assert (
        "granular_delete_images_only_preflight("
        in helper
    )

    assert helper.count(
        "requests.delete("
    ) == 1


def test_shared_helper_owns_delete_audit():

    helper=function_source(
        "granular_delete_images_only_execute"
    )

    assert (
        "PACS_IMAGES_DELETED_ADMIN"
        in helper
    )

    assert (
        "PACS_IMAGES_DELETE_FAILED_ADMIN"
        in helper
    )


def test_shared_helper_owns_post_delete_verification():

    helper=function_source(
        "granular_delete_images_only_execute"
    )

    assert (
        "ORTHANC_STUDY_STILL_PRESENT"
        in helper
    )

    assert (
        "RIS_STATE_UPDATE_FAILED_AFTER_PACS_DELETE"
        in helper
    )


def test_shared_helper_has_no_request_form_dependency():

    helper=function_source(
        "granular_delete_images_only_execute"
    )

    assert "request.form" not in helper


def test_http_route_is_thin_wrapper():

    wrapper=function_source(
        "granular_delete_order_images_only"
    )

    assert "request.form" in wrapper

    assert (
        "granular_delete_images_only_execute("
        in wrapper
    )

    assert "requests.delete(" not in wrapper

    assert (
        "granular_delete_images_only_preflight("
        not in wrapper
    )

    assert "audit(" not in wrapper


def test_source_never_deletes_ris_objects(app_ctx):
    import inspect

    m=app_ctx

    source=inspect.getsource(
        m.granular_delete_images_only_execute
    )

    forbidden=(
        "db.session.delete(order)",
        "db.session.delete(patient)",
        "db.session.delete(order.patient)",
        "Report.query.delete",
        "Attachment.query.delete",
    )

    for marker in forbidden:
        assert marker not in source



def test_delete_route_is_thin_wrapper_over_shared_primitive(app_ctx):
    import inspect

    m=app_ctx

    helper_source=inspect.getsource(
        m.granular_delete_images_only_execute
    )

    route_source=inspect.getsource(
        m.granular_delete_order_images_only
    )

    assert "requests.delete(" in helper_source

    assert (
        "granular_delete_images_only_preflight("
        in helper_source
    )

    assert (
        "granular_delete_images_only_execute("
        in route_source
    )

    assert "requests.delete(" not in route_source

    assert (
        "granular_delete_images_only_preflight("
        not in route_source
    )

    assert "request.form" in route_source



def test_shared_delete_primitive_has_no_http_route_decorators(app_ctx):
    m=app_ctx

    endpoints={
        rule.endpoint
        for rule in m.app.url_map.iter_rules()
    }

    assert (
        "granular_delete_images_only_execute"
        not in endpoints
    )

    assert (
        "granular_delete_order_images_only"
        in endpoints
    )



def test_shared_delete_primitive_retains_ris_objects(app_ctx):
    import inspect

    m=app_ctx

    source=inspect.getsource(
        m.granular_delete_images_only_execute
    )

    forbidden=(
        "db.session.delete(order)",
        "db.session.delete(patient)",
        "db.session.delete(order.patient)",
        "Report.query.delete",
        "Attachment.query.delete",
    )

    for marker in forbidden:
        assert marker not in source



def test_shared_helper_revalidates_at_irreversible_boundary():

    helper=function_source(
        "granular_delete_images_only_execute"
    )

    assert helper.count(
        "granular_delete_images_only_preflight("
    ) == 2

    refresh_pos=helper.index(
        "db.session.refresh(order)"
    )
    final_preflight_pos=helper.index(
        "final_preflight=granular_delete_images_only_preflight("
    )
    delete_pos=helper.index(
        "requests.delete("
    )

    assert refresh_pos < final_preflight_pos < delete_pos
    assert "FINAL_REVALIDATION_BLOCKED" in helper
    assert "PACS_STUDY_CHANGED_AFTER_PREFLIGHT" in helper
    assert "ACCESSION_CHANGED_AFTER_PREFLIGHT" in helper


def test_phase2b_adapter_has_real_verifying_state_before_completion():

    adapter=function_source(
        "correction_wrong_images_execute"
    )

    primitive_pos=adapter.index(
        "granular_delete_images_only_execute("
    )
    callback_pos=adapter.index(
        "after_delete=enter_verifying"
    )
    complete_pos=adapter.index(
        "'COMPLETED'"
    )

    assert primitive_pos < callback_pos < complete_pos
    assert "'VERIFYING'" in adapter
    assert "execution.status=" not in adapter
