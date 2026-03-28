"""Unit tests for CLI setup and wrapper script generation."""

import sys

from pymol_agent_bridge import cli


class TestCreateWrapperScript:
    def test_unix_script(self, tmp_home, monkeypatch):
        """On Unix, creates a bash wrapper script."""
        monkeypatch.setattr(sys, "platform", "linux")
        python_path = cli._create_wrapper_script()

        assert python_path == sys.executable
        assert cli.WRAPPER_PATH.exists()
        content = cli.WRAPPER_PATH.read_text()
        assert content.startswith("#!/bin/bash")
        assert sys.executable in content

    def test_windows_script(self, tmp_home, monkeypatch):
        """On Windows, creates a .bat wrapper script."""
        monkeypatch.setattr(sys, "platform", "win32")
        cli._create_wrapper_script()

        bat_path = cli.WRAPPER_PATH.with_suffix(".bat")
        assert bat_path.exists()
        content = bat_path.read_text()
        assert content.startswith("@echo off")

    def test_pymolrc_append(self, tmp_home, monkeypatch):
        """setup_pymol appends the plugin run line to .pymolrc."""
        # Create a pre-existing .pymolrc
        rc_path = tmp_home / ".pymolrc"
        rc_path.write_text("set ray_shadow, 0\n")

        # Patch on cli module (where setup_pymol looks up these names)
        monkeypatch.setattr(cli, "find_pymolrc_path", lambda: rc_path)
        monkeypatch.setattr(cli, "is_plugin_in_pymolrc", lambda: False)

        cli.setup_pymol()

        content = rc_path.read_text()
        assert "set ray_shadow, 0" in content
        assert "pymol_agent_bridge" in content
