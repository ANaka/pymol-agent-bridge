"""Unit tests for package-level exports and version."""

import pymol_agent_bridge


class TestPublicExports:
    def test_public_exports_exist(self):
        """All names in __all__ are importable from the package."""
        for name in pymol_agent_bridge.__all__:
            assert hasattr(pymol_agent_bridge, name), f"{name} not found in package"

    def test_version_is_string(self):
        """__version__ is a non-empty string."""
        assert isinstance(pymol_agent_bridge.__version__, str)
        assert len(pymol_agent_bridge.__version__) > 0

    def test_all_matches_actual_exports(self):
        """__all__ contains the expected public API names."""
        expected = {
            "PyMOLConnection",
            "connect_or_launch",
            "launch_pymol",
            "find_pymol_command",
            "check_pymol_installed",
        }
        assert set(pymol_agent_bridge.__all__) == expected
