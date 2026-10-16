from web.source_contract import read_source as _read_source
from pathlib import Path


def test_full_registration_ocr_autofill_contract():
    ris = Path(__file__).resolve().parents[1]

    app = _read_source(ris / "app.py", encoding="utf-8")
    tpl = _read_source(ris / "templates" / "schedule_calendar.html", encoding="utf-8")

    assert "RB_FULL_REG_OCR_DEMOGRAPHICS_V1" in app
    assert "normalized=normalize_intake_identity(base)" in app

    # Registration must accept YYYYMMDD from the identity helper
    # and convert it to the HTML date input format.
    assert "k==='new_dob'&&/^\\d{8}$/.test(value)" in tpl

    # Successful OCR must apply its suggestions immediately.
    assert "const autoApply=item.querySelector('.accept')" in tpl
    assert "if(autoApply)autoApply.click()" in tpl

    # Saving the patient/order remains a separate manual action.
    assert "Register & Save" in tpl


if __name__ == "__main__":
    test_full_registration_ocr_autofill_contract()
    print("FULL_REGISTRATION_OCR_AUTOFILL_CONTRACT=PASS")
