"""Unit tests for connection.py edge cases not covered by other test files."""

import os
import subprocess

import pytest

from pymol_agent_bridge import connection
from pymol_agent_bridge.connection import PyMOLConnection

# ---------------------------------------------------------------------------
# is_connected() edge cases
# ---------------------------------------------------------------------------


class TestIsConnected:
    def test_no_socket_returns_false(self):
        """Returns False when no socket is set."""
        conn = PyMOLConnection()
        assert conn.is_connected() is False

    def test_peer_closed_returns_false(self):
        """Returns False and cleans up when peer has closed the connection."""
        conn = PyMOLConnection()

        class FakeSocket:
            def setblocking(self, flag):
                pass

            def settimeout(self, t):
                pass

            def recv(self, n, flags=0):
                return b""  # peer closed

            def close(self):
                pass

        conn.socket = FakeSocket()
        assert conn.is_connected() is False
        assert conn.socket is None  # disconnect was called

    def test_oserror_returns_false(self):
        """Returns False when socket operations raise OSError."""
        conn = PyMOLConnection()

        class BrokenSocket:
            def setblocking(self, flag):
                raise OSError("broken")

            def close(self):
                pass

        conn.socket = BrokenSocket()
        assert conn.is_connected() is False
        assert conn.socket is None

    def test_active_connection_returns_true(self):
        """Returns True when recv(MSG_PEEK) raises BlockingIOError."""
        conn = PyMOLConnection()

        class AliveSocket:
            def setblocking(self, flag):
                pass

            def settimeout(self, t):
                pass

            def recv(self, n, flags=0):
                raise BlockingIOError  # no data available, connection alive

        conn.socket = AliveSocket()
        assert conn.is_connected() is True


# ---------------------------------------------------------------------------
# launch_pymol() error paths
# ---------------------------------------------------------------------------


class TestLaunchPymol:
    def test_pymol_not_found_raises(self, monkeypatch):
        """Raises RuntimeError when PyMOL cannot be found."""
        monkeypatch.setattr(connection, "find_pymol_command", lambda: None)

        with pytest.raises(RuntimeError, match="PyMOL not found"):
            connection.launch_pymol()

    def test_headless_passes_c_flag(self, monkeypatch):
        """headless=True includes -c in the command arguments."""
        monkeypatch.setattr(
            connection, "find_pymol_command", lambda: ["/usr/bin/pymol"]
        )
        monkeypatch.setattr(connection, "is_plugin_in_pymolrc", lambda: True)

        captured_args = {}

        class FakePopen:
            def __init__(self, cmd, **kwargs):
                captured_args["cmd"] = cmd

        # Don't wait for socket
        monkeypatch.setattr(subprocess, "Popen", FakePopen)
        connection.launch_pymol(headless=True, wait_for_socket=False)

        assert "-c" in captured_args["cmd"]

    def test_file_path_in_args(self, monkeypatch):
        """file_path is appended to the command arguments."""
        monkeypatch.setattr(
            connection, "find_pymol_command", lambda: ["/usr/bin/pymol"]
        )
        monkeypatch.setattr(connection, "is_plugin_in_pymolrc", lambda: True)

        captured_args = {}

        class FakePopen:
            def __init__(self, cmd, **kwargs):
                captured_args["cmd"] = cmd

        monkeypatch.setattr(subprocess, "Popen", FakePopen)
        connection.launch_pymol(file_path="/tmp/test.pdb", wait_for_socket=False)

        assert "/tmp/test.pdb" in captured_args["cmd"]

    def test_plugin_injected_when_not_in_pymolrc(self, monkeypatch):
        """When plugin is not in .pymolrc, -d flag is added to inject it."""
        monkeypatch.setattr(
            connection, "find_pymol_command", lambda: ["/usr/bin/pymol"]
        )
        monkeypatch.setattr(connection, "is_plugin_in_pymolrc", lambda: False)

        captured_args = {}

        class FakePopen:
            def __init__(self, cmd, **kwargs):
                captured_args["cmd"] = cmd

        monkeypatch.setattr(subprocess, "Popen", FakePopen)
        connection.launch_pymol(wait_for_socket=False)

        assert "-d" in captured_args["cmd"]
        # The argument after -d should reference the plugin
        d_index = captured_args["cmd"].index("-d")
        assert "plugin.py" in captured_args["cmd"][d_index + 1]


# ---------------------------------------------------------------------------
# find_pymol_command() fallback paths
# ---------------------------------------------------------------------------


class TestFindPymolCommandFallbacks:
    def test_uv_env_fallback(self, monkeypatch):
        """Falls back to ~/.pymol-env/bin/python when pymol is not in PATH."""
        # shutil.which returns None (not in PATH)
        monkeypatch.setattr(
            "pymol_agent_bridge.connection.shutil.which", lambda _: None
        )

        uv_python = os.path.expanduser("~/.pymol-env/bin/python")

        # uv python exists and is executable
        def fake_isfile(path):
            return path == uv_python

        def fake_access(path, mode):
            return path == uv_python

        monkeypatch.setattr(
            "pymol_agent_bridge.connection.os.path.isfile", fake_isfile
        )
        monkeypatch.setattr(
            "pymol_agent_bridge.connection.os.access", fake_access
        )

        # subprocess check for `import pymol` succeeds
        class FakeResult:
            returncode = 0

        monkeypatch.setattr(
            "pymol_agent_bridge.connection.subprocess.run",
            lambda cmd, **kw: FakeResult(),
        )

        result = connection.find_pymol_command()
        assert result == [uv_python, "-m", "pymol"]

    def test_common_path_fallback(self, monkeypatch):
        """Falls back to a common path when PATH and uv env both fail."""
        monkeypatch.setattr(
            "pymol_agent_bridge.connection.shutil.which", lambda _: None
        )

        target = "/usr/bin/pymol"

        # uv python does NOT exist, but /usr/bin/pymol does
        def fake_isfile(path):
            return path == target

        def fake_access(path, mode):
            return path == target

        monkeypatch.setattr(
            "pymol_agent_bridge.connection.os.path.isfile", fake_isfile
        )
        monkeypatch.setattr(
            "pymol_agent_bridge.connection.os.access", fake_access
        )

        result = connection.find_pymol_command()
        assert result == [target]


# ---------------------------------------------------------------------------
# find_pymol_executable()
# ---------------------------------------------------------------------------


class TestFindPymolExecutable:
    def test_returns_first_element(self, monkeypatch):
        """Delegates to find_pymol_command and returns the first element."""
        monkeypatch.setattr(
            connection, "find_pymol_command", lambda: ["/usr/local/bin/pymol"]
        )
        assert connection.find_pymol_executable() == "/usr/local/bin/pymol"

    def test_returns_none_when_not_found(self, monkeypatch):
        """Returns None when find_pymol_command returns None."""
        monkeypatch.setattr(connection, "find_pymol_command", lambda: None)
        assert connection.find_pymol_executable() is None


# ---------------------------------------------------------------------------
# get_configured_python()
# ---------------------------------------------------------------------------


class TestGetConfiguredPython:
    def test_valid_path_returned(self, tmp_home, tmp_path):
        """Returns the python path when it exists and is executable."""
        fake_python = tmp_path / "python3"
        fake_python.write_text("#!/bin/sh\n")
        fake_python.chmod(0o755)

        connection.save_config({"python_path": str(fake_python)})
        result = connection.get_configured_python()
        assert result == str(fake_python)

    def test_missing_path_returns_none(self, tmp_home):
        """Returns None when the configured path does not exist."""
        connection.save_config({"python_path": "/nonexistent/python3"})
        result = connection.get_configured_python()
        assert result is None

    def test_no_config_returns_none(self, tmp_home):
        """Returns None when no config exists."""
        result = connection.get_configured_python()
        assert result is None
