"""Unit tests for command execution retry/error behavior."""

import pytest

from pymol_agent_bridge.connection import PyMOLConnection


class TestConnectionExecute:
    def test_timeout_error_is_not_retried(self, monkeypatch):
        """TimeoutError should bubble immediately to avoid re-running code."""
        conn = PyMOLConnection()
        attempts = {"count": 0}

        monkeypatch.setattr(conn, "is_connected", lambda: True)

        def fake_send_command(_code):
            attempts["count"] += 1
            raise TimeoutError("command timed out")

        monkeypatch.setattr(conn, "send_command", fake_send_command)

        with pytest.raises(TimeoutError, match="command timed out"):
            conn.execute("print('hello')")

        assert attempts["count"] == 1

    def test_connection_error_is_retried(self, monkeypatch):
        """ConnectionError should still retry up to 3 attempts."""
        conn = PyMOLConnection()
        attempts = {"count": 0}

        monkeypatch.setattr(conn, "is_connected", lambda: True)
        monkeypatch.setattr("pymol_agent_bridge.connection.time.sleep", lambda _s: None)

        def fake_send_command(_code):
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise ConnectionError("socket dropped")
            return {"status": "success", "output": "ok"}

        monkeypatch.setattr(conn, "send_command", fake_send_command)

        assert conn.execute("print('hello')") == "ok"
        assert attempts["count"] == 3

    def test_error_response_includes_traceback_in_exception(self, monkeypatch):
        """Plugin traceback text should be surfaced to callers."""
        conn = PyMOLConnection()
        monkeypatch.setattr(conn, "is_connected", lambda: True)
        monkeypatch.setattr(
            conn,
            "send_command",
            lambda _code: {
                "status": "error",
                "error": "boom",
                "traceback": "Traceback (most recent call last): ...",
            },
        )

        with pytest.raises(RuntimeError) as exc_info:
            conn.execute("raise RuntimeError('boom')")

        message = str(exc_info.value)
        assert "boom" in message
        assert "PyMOL traceback:" in message
