"""Fixtures for integration tests requiring a live PyMOL instance."""

import subprocess
import time

import pytest

from pymol_agent_bridge.connection import PyMOLConnection, get_plugin_path


@pytest.fixture(scope="session")
def pymol_process():
    """Launch PyMOL headless with the bridge plugin for the test session."""
    plugin_path = get_plugin_path()
    pymol_cmd = ["pymol", "-c", "-d", f"run {plugin_path}"]

    process = subprocess.Popen(
        pymol_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for the socket to become available
    conn = PyMOLConnection()
    deadline = time.time() + 15.0
    while time.time() < deadline:
        if process.poll() is not None:
            out = process.stdout.read().decode() if process.stdout else ""
            err = process.stderr.read().decode() if process.stderr else ""
            pytest.fail(f"PyMOL exited during startup.\nstdout: {out}\nstderr: {err}")
        try:
            conn.connect(timeout=1.0)
            conn.disconnect()
            break
        except ConnectionError:
            time.sleep(0.5)
    else:
        process.kill()
        pytest.fail("PyMOL socket not available after 15s")

    yield process

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


@pytest.fixture
def connection(pymol_process):
    """Provide a connected PyMOLConnection for each test."""
    conn = PyMOLConnection()
    conn.connect(timeout=5.0)
    yield conn
    conn.disconnect()
