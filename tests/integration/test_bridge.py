"""
Integration tests for the pymol-agent-bridge.

These tests require a running PyMOL instance with the bridge plugin loaded.
The pymol_process fixture (session-scoped) handles launch and teardown.

Run with: pytest tests/integration/ -v
"""

import argparse
import json
import time

import pytest

from pymol_agent_bridge.cli import check_status, do_run_code, test_connection
from pymol_agent_bridge.connection import PyMOLConnection, connect_or_launch

pytestmark = pytest.mark.integration


class TestConnection:
    """Test low-level connection to PyMOL."""

    def test_ping(self, connection):
        """ping() should return True when PyMOL is running."""
        assert connection.ping() is True

    def test_is_connected(self, connection):
        """is_connected() should return True for an active connection."""
        assert connection.is_connected() is True


class TestExec:
    """Test executing code in PyMOL."""

    def test_simple_expression(self, connection):
        """Execute a simple Python expression and get output."""
        result = connection.execute("print(1 + 1)")
        assert "2" in result

    def test_pymol_version(self, connection):
        """Execute a PyMOL command to verify the bridge reaches PyMOL."""
        result = connection.execute("print(cmd.get_version()[0])")
        # PyMOL version is a string like "3.1.0"
        assert "." in result

    def test_multiline_code(self, connection):
        """Execute multi-line Python code."""
        code = "x = 42\nprint(x * 2)"
        result = connection.execute(code)
        assert "84" in result

    def test_error_returns_traceback(self, connection):
        """Invalid code should raise with traceback info."""
        with pytest.raises(RuntimeError, match="undefined_variable_xyz"):
            connection.execute("print(undefined_variable_xyz)")

    def test_syntax_error(self, connection):
        """Syntax errors should raise."""
        with pytest.raises(RuntimeError, match="invalid syntax"):
            connection.execute("def f(:")

    def test_result_variable(self, connection):
        """The _result convention should return structured data."""
        result = connection.execute("_result = list(range(3))")
        assert "[0, 1, 2]" in result

    def test_json_output(self, pymol_process):
        """execute() result can be wrapped as JSON for agent consumption."""
        import json

        conn = PyMOLConnection()
        conn.connect(timeout=5.0)
        result = conn.execute("print('hello from pymol')")
        # Verify the result is a string that can be embedded in JSON
        payload = json.dumps({"status": "success", "output": result})
        parsed = json.loads(payload)
        assert parsed["status"] == "success"
        assert "hello from pymol" in parsed["output"]
        conn.disconnect()


class TestCLIFunctions:
    """Test CLI-level functions against a live PyMOL."""

    def test_check_status(self, pymol_process, capsys):
        """check_status() should return 0 when PyMOL is connected."""
        result = check_status()
        assert result == 0
        captured = capsys.readouterr()
        assert "OK" in captured.out

    def test_test_connection(self, pymol_process, capsys):
        """test_connection() should return 0 and show a response."""
        result = test_connection()
        assert result == 0
        captured = capsys.readouterr()
        assert "OK" in captured.out


class TestReconnection:
    """Test connection resilience."""

    def test_execute_after_disconnect(self, pymol_process):
        """execute() should reconnect automatically if disconnected."""
        conn = PyMOLConnection()
        conn.connect(timeout=5.0)
        # Force disconnect
        conn.disconnect()
        # execute() should reconnect and succeed
        result = conn.execute("print('reconnected')")
        assert "reconnected" in result
        conn.disconnect()


class TestServerBusy:
    """Test that the plugin rejects concurrent clients."""

    def test_second_client_rejected(self, connection):
        """A second client should be rejected while one is active."""
        # Small delay to ensure the first client's handler is fully running
        time.sleep(0.1)

        second = PyMOLConnection()
        with pytest.raises(ConnectionError):
            second.connect(timeout=2.0)

        # First connection should still work
        result = connection.execute("print('still alive')")
        assert "still alive" in result


class TestConnectOrLaunch:
    """Test connect_or_launch against a running instance."""

    def test_connects_to_existing_and_executes(self, pymol_process):
        """Connects to running PyMOL, returns (conn, None), and works."""
        conn, process = connect_or_launch()
        try:
            assert process is None, "Should connect to existing, not launch"
            result = conn.execute("print(7 * 6)")
            assert "42" in result
        finally:
            conn.disconnect()


class TestExecFromFile:
    """Test executing code from files via the CLI."""

    def test_exec_file_via_cli(self, pymol_process, tmp_path, capsys):
        """do_run_code with -f flag executes a file in PyMOL."""
        script = tmp_path / "test_script.py"
        script.write_text("print(2 + 2)")

        args = argparse.Namespace(
            code=None, file=str(script), json=False
        )
        ret = do_run_code(args)

        assert ret == 0
        assert "4" in capsys.readouterr().out

    def test_exec_file_json_output(self, pymol_process, tmp_path, capsys):
        """do_run_code with -f and --json returns a JSON envelope."""
        script = tmp_path / "test_json.py"
        script.write_text("print('hello')")

        args = argparse.Namespace(
            code=None, file=str(script), json=True
        )
        ret = do_run_code(args)

        assert ret == 0
        parsed = json.loads(capsys.readouterr().out)
        assert parsed["status"] == "success"
        assert "hello" in parsed["output"]

    def test_exec_file_error_json(self, pymol_process, tmp_path, capsys):
        """do_run_code with bad code and --json returns a JSON error."""
        script = tmp_path / "bad_script.py"
        script.write_text("raise ValueError('test error')")

        args = argparse.Namespace(
            code=None, file=str(script), json=True
        )
        ret = do_run_code(args)

        assert ret == 1
        parsed = json.loads(capsys.readouterr().out)
        assert parsed["status"] == "error"
        assert "test error" in parsed["error"]


class TestConnectionResilience:
    """Test rapid connect/disconnect cycling."""

    def test_rapid_connect_disconnect_cycles(self, pymol_process):
        """Plugin cleans up _active_client properly across cycles."""
        for _ in range(5):
            conn = PyMOLConnection()
            conn.connect(timeout=5.0)
            conn.disconnect()
            # Give the server thread time to clean up _active_client
            time.sleep(0.2)

        # Final connection should work and execute successfully
        conn = PyMOLConnection()
        conn.connect(timeout=5.0)
        result = conn.execute("print('survived cycling')")
        assert "survived cycling" in result
        conn.disconnect()
