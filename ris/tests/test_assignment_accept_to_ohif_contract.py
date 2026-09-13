from pathlib import Path

import app as m


def _response_source():
    source = Path(m.__file__).read_text(encoding="utf-8")
    start = source.index("def assignment_offer_respond(offer_id):")
    end = source.index(
        "@app.post('/orders/<int:order_id>/assignment-offer/start')",
        start,
    )
    return source[start:end]


def test_accept_redirects_to_integrated_ohif_after_commit():
    body = _response_source()

    assert "RB_ASSIGNMENT_ACCEPT_TO_OHIF_V1" in body
    assert "if action=='ACCEPT':" in body
    assert "ohif_url_for_order(row.order)" in body
    assert "or case_pacs_url(row.order)" in body
    assert "return redirect(viewer_url)" in body

    final_commit = body.rfind("db.session.commit()")
    viewer_redirect = body.index("return redirect(viewer_url)")

    assert final_commit >= 0
    assert final_commit < viewer_redirect


def test_non_accept_responses_keep_offer_page_redirect():
    body = _response_source()

    assert "elif action in ('BUSY','REJECT'):" in body
    assert "return redirect(url_for('my_assignment_offers'))" in body
    assert body.index("return redirect(viewer_url)") < body.rfind(
        "return redirect(url_for('my_assignment_offers'))"
    )
