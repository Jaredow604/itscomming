import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "structural: mark test as a structural audit (no DB required)"
    )
    config.addinivalue_line(
        "markers",
        "mismatch: mark test that documents a known dimensional mismatch"
    )
    config.addinivalue_line(
        "markers",
        "type_check: mark test for data type compatibility"
    )
