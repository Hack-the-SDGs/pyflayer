"""Integration test fixtures.

Integration tests require a running Minecraft server. Skip by default;
run with ``pytest -m integration`` to include them.
"""

import pytest


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip integration tests unless explicitly requested."""
    if "integration" not in (config.getoption("-m", default="") or ""):
        skip = pytest.mark.skip(reason="integration tests need -m integration")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip)
