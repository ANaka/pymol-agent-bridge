"""Unit tests for command execution retry/error behavior."""

import pytest

from pymol_agent_bridge.connection import PyMOLConnection
from pymol_agent_bridge.session import PyMOLSession


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


class TestSessionExecute:
    def test_timeout_error_does_not_trigger_recovery(self, monkeypatch):
        """TimeoutError should not auto-recover/retry execution."""
        session = PyMOLSession()
        calls = {"execute": 0, "recover": 0}

        class TimeoutConnection:
            def is_connected(self):
                return True

            def execute(self, _code):
                calls["execute"] += 1
                raise TimeoutError("slow command")

        session.connection = TimeoutConnection()

        def fake_recover(*_args, **_kwargs):
            calls["recover"] = 1
            return True

        monkeypatch.setattr(session, "recover", fake_recover)

        with pytest.raises(TimeoutError, match="slow command"):
            session.execute("print('hello')", auto_recover=True)

        assert calls["execute"] == 1
        assert calls["recover"] == 0

    def test_connection_error_still_uses_auto_recover(self, monkeypatch):
        """ConnectionError should still recover and retry once."""
        session = PyMOLSession()
        calls = {"recover": 0}

        class FlakyConnection:
            def __init__(self):
                self._attempts = 0

            def is_connected(self):
                return True

            def execute(self, _code):
                self._attempts += 1
                raise ConnectionError("disconnected")

        class HealthyConnection:
            def is_connected(self):
                return True

            def execute(self, _code):
                return "ok"

        session.connection = FlakyConnection()

        def fake_recover(*_args, **_kwargs):
            calls["recover"] += 1
            session.connection = HealthyConnection()
            return True

        monkeypatch.setattr(session, "recover", fake_recover)

        assert session.execute("print('hello')", auto_recover=True) == "ok"
        assert calls["recover"] == 1
