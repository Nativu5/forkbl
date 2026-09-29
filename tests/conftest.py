import sys

import pytest


def pytest_collection_modifyitems(items):
    """Run native terminal tests only where their backend can be imported."""
    for item in items:
        if "windows" in item.keywords and sys.platform != "win32":
            item.add_marker(pytest.mark.skip(reason="requires Windows ConPTY"))
        elif "posix" in item.keywords and sys.platform == "win32":
            item.add_marker(pytest.mark.skip(reason="requires a Unix PTY"))
