import os
import pytest

# Force an isolated in-memory DB for tests before importing the application.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["RADBRIDGE_BOOTSTRAP_ON_IMPORT"] = "0"

import app as m


@pytest.fixture(scope="session")
def app_ctx():
    m.app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        WTF_CSRF_ENABLED=False,
    )

    with m.app.app_context():
        m.db.drop_all()
        m.db.create_all()

        # Seed only the minimum role records required by tests.
        for code, name in [
            ("SUPER_ADMIN", "Super Admin"),
            ("RECEPTION", "Reception"),
            ("RADIOLOGIST", "Radiologist"),
            ("TECHNICIAN", "Technician"),
            ("CASE_COORDINATOR", "Case Coordinator"),
        ]:
            if not m.Role.query.filter_by(code=code).first():
                m.db.session.add(
                    m.Role(
                        code=code,
                        name=name,
                        permissions_json="[]",
                    )
                )

        # Minimal company profile for templates/login.
        if not m.CompanyProfile.query.first():
            m.db.session.add(
                m.CompanyProfile(
                    name_en="RadBridge Test",
                    name_ar="RadBridge Test",
                )
            )

        m.db.session.commit()

        yield m

        m.db.session.remove()
        m.db.drop_all()
