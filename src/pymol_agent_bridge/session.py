"""
PyMOL Session Manager

Provides reliable session lifecycle management:
- Launch PyMOL with plugin
- Health checks
- Graceful and forced termination
- Crash detection and recovery
"""

import subprocess
import time

from pymol_agent_bridge.connection import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    PyMOLConnection,
    launch_pymol,
)


class PyMOLSession:
    """
    Manages a PyMOL session with health monitoring and recovery.

    Usage:
        session = PyMOLSession()
        session.start()

        # Use the connection
        result = session.execute("cmd.fetch('1ubq')")

        # Check health
        if not session.is_healthy():
            session.recover()

        # Clean up
        session.stop()
    """

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.process = None
        self.connection = None
        self._we_launched = False
        self._headless = False

    @property
    def is_running(self):
        """Check if we have a PyMOL process that's still alive."""
        if self.process is None:
            return False
        return self.process.poll() is None

    @property
    def is_connected(self):
        """Check if we have a socket connection."""
        return self.connection is not None and self.connection.is_connected()

    def is_healthy(self):
        """
        Check if PyMOL is responsive via protocol-level ping.

        Returns True if we can communicate with PyMOL.
        """
        if not self.is_connected or self.connection is None:
            return False
        try:
            return self.connection.ping()
        except Exception:
            return False

    def start(self, timeout=15.0, headless=False):
        """
        Start PyMOL or connect to existing instance.

        No-op when already connected and healthy, preserving ownership
        semantics so ``stop()`` only kills processes this session launched.

        Args:
            timeout: How long to wait for PyMOL to be ready
            headless: If True, launch PyMOL in command-line mode (no GUI)

        Returns:
            True if connected successfully
        """
        self._headless = headless

        # Already connected and healthy — no-op
        if self.is_healthy():
            return True

        # Clean up stale connection before reconnecting
        if self.connection:
            self.connection.disconnect()

        self.connection = PyMOLConnection(self.host, self.port)

        # Try connecting to existing instance first
        try:
            self.connection.connect(timeout=2.0)
            # Preserve _we_launched if we still own a running process
            if not self.is_running:
                self._we_launched = False
            return True
        except ConnectionError:
            pass

        # Launch new instance — delegated to connection.launch_pymol()
        self.process = launch_pymol(
            wait_for_socket=True,
            timeout=timeout,
            headless=headless,
            capture_output=True,
        )
        self._we_launched = True
        self.connection.connect()
        return True

    def stop(self, graceful_timeout=5.0):
        """
        Stop PyMOL session.

        Args:
            graceful_timeout: Time to wait for graceful shutdown before force kill
        """
        if self.connection:
            self.connection.disconnect()
            self.connection = None

        # Only kill process if we launched it
        if self._we_launched and self.process:
            self._kill_process(graceful_timeout)

    def _kill_process(self, graceful_timeout=5.0):
        """Kill the PyMOL process."""
        if not self.process:
            return

        try:
            self.process.terminate()
            self.process.wait(timeout=graceful_timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=2.0)
        except Exception:
            pass

        self.process = None
        self._we_launched = False

    def recover(self, timeout=15.0):
        """
        Recover from a crashed or unresponsive PyMOL.

        This will:
        1. Kill any stale process
        2. Disconnect stale socket
        3. Start fresh

        Returns:
            True if recovery successful
        """
        if self.connection:
            self.connection.disconnect()
            self.connection = None

        if self._we_launched:
            self._kill_process(graceful_timeout=2.0)

        # Brief pause to let OS clean up
        time.sleep(0.5)

        # Start fresh with same headless setting
        return self.start(timeout=timeout, headless=self._headless)

    def execute(self, code, auto_recover=True):
        """
        Execute code in PyMOL with optional auto-recovery.

        Args:
            code: Python code to execute in PyMOL
            auto_recover: If True, attempt recovery on failure

        Returns:
            Output from PyMOL
        """
        try:
            if not self.is_connected:
                if auto_recover:
                    self.recover()
                else:
                    raise ConnectionError("Not connected to PyMOL")

            assert self.connection is not None
            return self.connection.execute(code)

        except ConnectionError:
            if auto_recover:
                self.recover()
                assert self.connection is not None
                return self.connection.execute(code)
            raise

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


# Convenience: global session instance
_session = None


def get_session():
    """Get or create the global PyMOL session."""
    global _session
    if _session is None:
        _session = PyMOLSession()
    return _session


def ensure_running():
    """Ensure PyMOL is running and connected."""
    session = get_session()
    if not session.is_healthy():
        session.start()
    return session


def stop_pymol():
    """Stop the global PyMOL session."""
    global _session
    if _session:
        _session.stop()
        _session = None
