"""
Integration tests for the pymol-agent-bridge.

These tests require a running PyMOL instance with the bridge plugin loaded.
The pymol_process fixture (session-scoped) handles launch and teardown.

Run with: pytest tests/integration/ -v
"""

import pytest

from pymol_agent_bridge.cli import check_status, test_connection
from pymol_agent_bridge.connection import PyMOLConnection

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
