"""pymol-agent-bridge: Lightweight bridge connecting agents to PyMOL via TCP socket."""

__version__ = "0.1.0"

from pymol_agent_bridge.connection import (
    PyMOLConnection,
    check_pymol_installed,
    connect_or_launch,
    find_pymol_command,
    launch_pymol,
)
from pymol_agent_bridge.session import PyMOLSession

__all__ = [
    "PyMOLConnection",
    "PyMOLSession",
    "connect_or_launch",
    "launch_pymol",
    "find_pymol_command",
    "check_pymol_installed",
]
