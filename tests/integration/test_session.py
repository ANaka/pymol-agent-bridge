"""
Tests for PyMOL session management.

Run with: pytest tests/integration/test_session.py -v
"""

import time

import pytest

from pymol_agent_bridge.session import PyMOLSession

pytestmark = pytest.mark.integration


@pytest.fixture
def session():
    """Create a fresh session for each test."""
    s = PyMOLSession()
    yield s
    s.stop()


class TestSessionLifecycle:
    """Test basic session start/stop."""

    def test_start_creates_connection(self, session):
        """Starting a session should create a working connection."""
        session.start(timeout=20.0)

        assert session.is_connected
        assert session.is_healthy()

    def test_stop_closes_connection(self, session):
        """Stopping a session should close the connection."""
        session.start(timeout=20.0)
        session.stop()

        assert not session.is_connected

    def test_context_manager(self):
        """Session should work as a context manager."""
        with PyMOLSession() as session:
            assert session.is_healthy()

        assert not session.is_connected

    def test_start_twice_is_safe(self, session):
        """Starting an already-started session should be safe."""
        session.start(timeout=20.0)
        session.start(timeout=5.0)

        assert session.is_healthy()


class TestHealthCheck:
    """Test health check functionality."""

    def test_healthy_session_responds(self, session):
        """A running session should respond to health checks."""
        session.start(timeout=20.0)

        assert session.is_healthy()

    def test_disconnected_session_not_healthy(self, session):
        """A disconnected session should not be healthy."""
        assert not session.is_healthy()


class TestCommandExecution:
    """Test command execution."""

    def test_execute_simple_command(self, session):
        """Should be able to execute simple commands."""
        session.start(timeout=20.0)

        result = session.execute("print('hello world')")

        assert "hello world" in result

    def test_execute_pymol_command(self, session):
        """Should be able to execute PyMOL-specific commands."""
        session.start(timeout=20.0)

        result = session.execute("cmd.reinitialize()")
        assert result is not None


class TestRecovery:
    """Test crash detection and recovery."""

    def test_recover_from_killed_process(self, session):
        """Should recover when PyMOL process is killed."""
        session.start(timeout=20.0)
        assert session.is_healthy()

        if session.process and session._we_launched:
            session.process.kill()
            time.sleep(1)

            assert not session.is_running

            session.recover(timeout=20.0)
            assert session.is_healthy()

    def test_auto_recover_on_execute(self, session):
        """Execute with auto_recover should recover from failures."""
        session.start(timeout=20.0)

        if session.process and session._we_launched:
            session.process.kill()
            time.sleep(1)

            result = session.execute("print('recovered')", auto_recover=True)
            assert "recovered" in result


class TestConnectToExisting:
    """Test connecting to an already-running PyMOL."""

    def test_connect_to_existing_instance(self):
        """If PyMOL is already running, should connect to it."""
        session1 = PyMOLSession()
        session1.start(timeout=20.0)

        try:
            session2 = PyMOLSession()
            session2.start(timeout=5.0)

            assert session2.is_healthy()
            assert not session2._we_launched

            session2.stop()
            assert session1.is_healthy()

        finally:
            session1.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
