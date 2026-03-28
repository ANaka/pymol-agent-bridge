"""Fixtures for unit tests — no PyMOL dependency."""

import socket

import pytest


@pytest.fixture
def socket_pair():
    """Create a connected socket pair for protocol testing."""
    a, b = socket.socketpair()
    yield a, b
    a.close()
    b.close()


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    """Monkeypatch module-level Path.home() derivatives to tmp_path.

    Patches CONFIG_DIR/CONFIG_FILE in connection.py and
    WRAPPER_DIR/WRAPPER_PATH in cli.py to avoid touching the real home directory.
    """
    from pymol_agent_bridge import cli, connection

    config_dir = tmp_path / ".pymol-agent-bridge"
    config_file = config_dir / "config.json"
    wrapper_dir = tmp_path / ".pymol-agent-bridge" / "bin"
    wrapper_path = wrapper_dir / "pymol-agent-bridge"

    monkeypatch.setattr(connection, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(connection, "CONFIG_FILE", config_file)
    monkeypatch.setattr(cli, "WRAPPER_DIR", wrapper_dir)
    monkeypatch.setattr(cli, "WRAPPER_PATH", wrapper_path)

    return tmp_path
