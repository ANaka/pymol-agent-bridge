"""Shared pytest configuration for pymol-agent-bridge tests."""

import shutil

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: requires a running PyMOL instance")


@pytest.fixture(autouse=True)
def _skip_integration_without_pymol(request):
    """Auto-skip integration tests when PyMOL is not available."""
    if "integration" in [m.name for m in request.node.iter_markers()]:
        if not shutil.which("pymol"):
            pytest.skip("PyMOL not found in PATH")
