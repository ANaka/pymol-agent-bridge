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
        rc_path = tmp_home / ".pymolrc"
        rc_path.write_text("set ray_shadow, 0\n")

        monkeypatch.setattr(cli, "find_pymolrc_path", lambda: rc_path)
        monkeypatch.setattr(cli, "is_plugin_in_pymolrc", lambda: False)
        monkeypatch.setattr(cli, "find_pymol_command", lambda: ["/usr/bin/pymol"])

        cli.setup_pymol()

        content = rc_path.read_text()
        assert "set ray_shadow, 0" in content
        assert "pymol_agent_bridge" in content


class TestSetupPymolDetection:
    def test_setup_pymol_found(self, tmp_home, monkeypatch, capsys):
        """When PyMOL is installed, setup reports it and completes."""
        rc_path = tmp_home / ".pymolrc"
        monkeypatch.setattr(cli, "find_pymolrc_path", lambda: rc_path)
        monkeypatch.setattr(cli, "is_plugin_in_pymolrc", lambda: False)
        monkeypatch.setattr(cli, "find_pymol_command", lambda: ["/usr/bin/pymol"])

        result = cli.setup_pymol()
        out = capsys.readouterr().out

        assert result == 0
        assert "PyMOL found: /usr/bin/pymol" in out
        assert "Setup complete!" in out

    def test_setup_pymol_not_found_non_tty(self, tmp_home, monkeypatch, capsys):
        """When PyMOL is missing and non-interactive, warns but still configures."""
        rc_path = tmp_home / ".pymolrc"
        monkeypatch.setattr(cli, "find_pymolrc_path", lambda: rc_path)
        monkeypatch.setattr(cli, "is_plugin_in_pymolrc", lambda: False)
        monkeypatch.setattr(cli, "find_pymol_command", lambda: None)
        monkeypatch.setattr("os.isatty", lambda _: False)

        result = cli.setup_pymol()
        captured = capsys.readouterr()

        assert result == 0
        assert "PyMOL not found" in captured.out
        assert "Install options:" in captured.err
        assert "Bridge configured" in captured.out
        # .pymolrc should still be created
        assert rc_path.exists()
        assert "pymol_agent_bridge" in rc_path.read_text()

    def test_setup_pymol_not_found_interactive_decline(
        self, tmp_home, monkeypatch, capsys
    ):
        """When user declines install, shows manual instructions."""
        rc_path = tmp_home / ".pymolrc"
        monkeypatch.setattr(cli, "find_pymolrc_path", lambda: rc_path)
        monkeypatch.setattr(cli, "is_plugin_in_pymolrc", lambda: False)
        monkeypatch.setattr(cli, "find_pymol_command", lambda: None)

        class _Stdin:
            def fileno(self):
                return 0

        monkeypatch.setattr(sys, "stdin", _Stdin())
        monkeypatch.setattr("os.isatty", lambda _: True)
        monkeypatch.setattr("builtins.input", lambda _: "n")

        result = cli.setup_pymol()
        out = capsys.readouterr().out

        assert result == 0
        assert "PyMOL not found" in out
        assert "Install options:" in out
        assert "Bridge configured" in out

    def test_setup_pymol_not_found_interactive_install(
        self, tmp_home, monkeypatch, capsys
    ):
        """When user accepts install, runs install commands."""
        rc_path = tmp_home / ".pymolrc"
        monkeypatch.setattr(cli, "find_pymolrc_path", lambda: rc_path)
        monkeypatch.setattr(cli, "is_plugin_in_pymolrc", lambda: False)

        # First call returns None (before install), second returns the command
        call_count = 0

        def mock_find():
            nonlocal call_count
            call_count += 1
            return ["/usr/bin/pymol"] if call_count > 1 else None

        monkeypatch.setattr(cli, "find_pymol_command", mock_find)

        class _Stdin:
            def fileno(self):
                return 0

        monkeypatch.setattr(sys, "stdin", _Stdin())
        monkeypatch.setattr("os.isatty", lambda _: True)
        monkeypatch.setattr("builtins.input", lambda _: "y")

        ran_commands = []

        def mock_run(cmd, **kwargs):
            ran_commands.append(cmd)

            class Result:
                returncode = 0

            return Result()

        monkeypatch.setattr("subprocess.run", mock_run)
        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/uv" if name == "uv" else None)

        result = cli.setup_pymol()
        out = capsys.readouterr().out

        assert result == 0
        assert len(ran_commands) == 2
        assert "uv" in ran_commands[0]
        assert "pymol-open-source-whl" in ran_commands[1]
        assert "PyMOL installed" in out
        assert "Setup complete!" in out
