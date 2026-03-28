"""Unit tests for PyMOL discovery and pymolrc detection."""

from pymol_agent_bridge import connection


class TestFindPymolCommand:
    def test_found_in_path(self, monkeypatch):
        """When pymol is in PATH, return its path."""
        monkeypatch.setattr(
            "pymol_agent_bridge.connection.shutil.which", lambda _: "/usr/bin/pymol"
        )
        assert connection.find_pymol_command() == ["/usr/bin/pymol"]

    def test_not_found(self, monkeypatch):
        """When pymol is nowhere, return None."""
        monkeypatch.setattr(
            "pymol_agent_bridge.connection.shutil.which", lambda _: None
        )
        monkeypatch.setattr(
            "pymol_agent_bridge.connection.os.path.isfile", lambda _: False
        )
        assert connection.find_pymol_command() is None


class TestIsPluginInPymolrc:
    def test_marker_present(self, tmp_path, monkeypatch):
        """Returns True when pymolrc contains the bridge marker."""
        rc = tmp_path / ".pymolrc"
        rc.write_text("run /path/to/pymol_agent_bridge/plugin.py\n")
        monkeypatch.setattr(
            "pymol_agent_bridge.connection.find_pymolrc_path", lambda: rc
        )
        assert connection.is_plugin_in_pymolrc() is True

    def test_marker_absent(self, tmp_path, monkeypatch):
        """Returns False when pymolrc has no bridge marker."""
        rc = tmp_path / ".pymolrc"
        rc.write_text("set ray_shadow, 0\n")
        monkeypatch.setattr(
            "pymol_agent_bridge.connection.find_pymolrc_path", lambda: rc
        )
        assert connection.is_plugin_in_pymolrc() is False

    def test_file_missing(self, tmp_path, monkeypatch):
        """Returns False when pymolrc doesn't exist."""
        monkeypatch.setattr(
            "pymol_agent_bridge.connection.find_pymolrc_path",
            lambda: tmp_path / ".pymolrc",
        )
        assert connection.is_plugin_in_pymolrc() is False
