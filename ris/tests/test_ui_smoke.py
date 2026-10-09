
import os
import pytest

pytestmark=pytest.mark.ui

BASE=os.getenv("TEST_BASE_URL","http://127.0.0.1:8090")

def test_ui_placeholder():
    # Kept dependency-free for default pytest run.
    # Full Playwright runner is scripts/run-playwright-smoke.py
    assert BASE.startswith("http")
