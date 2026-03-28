"""
PyMOL Connection Module

Provides functions to communicate with PyMOL via TCP socket.
"""

import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

from pymol_agent_bridge.protocol import recv_message, send_message

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 9880
CONNECT_TIMEOUT = 5.0
RECV_TIMEOUT = 30.0

CONFIG_DIR = Path.home() / ".pymol-agent-bridge"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Common PyMOL installation paths
PYMOL_PATHS = [
    # uv environment
    os.path.expanduser("~/.pymol-env/bin/python"),
    # macOS app locations
    "/Applications/PyMOL.app/Contents/MacOS/PyMOL",
    os.path.expanduser("~/Applications/PyMOL.app/Contents/MacOS/PyMOL"),
    # Linux system locations
    "/usr/bin/pymol",
    "/usr/local/bin/pymol",
    # Windows common locations
    os.path.expandvars(r"%PROGRAMFILES%\PyMOL\PyMOL\PyMOLWin.exe"),
    os.path.expandvars(r"%LOCALAPPDATA%\Schrodinger\PyMOL\PyMOLWin.exe"),
]

# --- pymolrc detection (centralized) ---


def find_pymolrc_path() -> Path:
    """Find the PyMOL configuration file path (.pymolrc or pymolrc.py)."""
    home = Path.home()
    # Check common locations
    for name in [".pymolrc", "pymolrc.py", ".pymolrc.py"]:
        p = home / name
        if p.exists():
            return p
    # Default to .pymolrc
    return home / ".pymolrc"


PYMOLRC_PATH = find_pymolrc_path()
_BRIDGE_MARKERS = ("pymol_agent_bridge", "pymol-agent-bridge")


def is_plugin_in_pymolrc() -> bool:
    """Check if the bridge plugin is already configured in ~/.pymolrc."""
    path = find_pymolrc_path()
    if not path.exists():
        return False
    try:
        content = path.read_text()
        return any(marker in content for marker in _BRIDGE_MARKERS)
    except OSError:
        return False


# --- Connection class ---


class PyMOLConnection:
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.socket = None

    def connect(self, timeout=CONNECT_TIMEOUT):
        """Connect to PyMOL socket server."""
        if self.socket:
            if self.is_connected():
                return True
            self.disconnect()
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(timeout)
            self.socket.connect((self.host, self.port))
            self.socket.settimeout(RECV_TIMEOUT)

            # Protocol-level handshake so BUSY rejections surface immediately.
            handshake_timeout = min(timeout, 2.0)
            response = self._send_ping(handshake_timeout)
            if response.get("status") == "error":
                raise ConnectionError(response.get("error", "Connection rejected"))
            if response.get("type") != "pong":
                raise ConnectionError(f"Unexpected handshake response: {response}")
            return True
        except Exception as e:
            self.disconnect()
            raise ConnectionError(
                f"Cannot connect to PyMOL on {self.host}:{self.port}: {e}"
            )

    def disconnect(self):
        """Disconnect from PyMOL."""
        if self.socket:
            try:
                self.socket.close()
            except OSError:
                pass
            self.socket = None

    def is_connected(self):
        """Check if connected to PyMOL."""
        if not self.socket:
            return False
        try:
            self.socket.setblocking(False)
            try:
                data = self.socket.recv(1, socket.MSG_PEEK)
                if data == b"":
                    self.disconnect()
                    return False
            except BlockingIOError:
                pass
            finally:
                if self.socket:
                    self.socket.setblocking(True)
                    self.socket.settimeout(RECV_TIMEOUT)
            return True
        except OSError:
            self.disconnect()
            return False

    def send_command(self, code):
        """Send Python code to PyMOL and return result."""
        if not self.socket:
            raise ConnectionError("Not connected to PyMOL")
        try:
            send_message(self.socket, {"type": "execute", "code": code})
            return recv_message(self.socket)
        except socket.timeout:
            raise TimeoutError("PyMOL command timed out")
        except (ConnectionError, ValueError) as e:
            self.disconnect()
            raise ConnectionError(f"Communication error: {e}")

    def _send_ping(self, timeout):
        """Send ping and return raw response payload."""
        if not self.socket:
            raise ConnectionError("Not connected to PyMOL")
        old_timeout = self.socket.gettimeout()
        try:
            self.socket.settimeout(timeout)
            send_message(self.socket, {"type": "ping"})
            return recv_message(self.socket)
        finally:
            if self.socket:
                self.socket.settimeout(old_timeout)

    def ping(self, timeout=5.0):
        """Send a ping and wait for pong. Returns True if responsive."""
        if not self.socket:
            return False
        try:
            response = self._send_ping(timeout)
            if response.get("status") == "error":
                self.disconnect()
                return False
            return response.get("type") == "pong"
        except (socket.timeout, ConnectionError, ValueError, OSError):
            self.disconnect()
            return False

    def execute(self, code):
        """Execute code, reconnecting if necessary. Returns output string or raises."""
        for attempt in range(3):
            try:
                if not self.is_connected():
                    self.connect()
                result = self.send_command(code)
                if result.get("status") == "success":
                    return result.get("output", "")
                else:
                    raise RuntimeError(result.get("error", "Unknown error"))
            except (ConnectionError, TimeoutError):
                if attempt < 2:
                    time.sleep(0.5)
                    continue
                raise
        raise ConnectionError("Failed to connect after 3 attempts")


# --- PyMOL discovery and launch ---


def find_pymol_command():
    """
    Find how to launch PyMOL.

    Returns:
        List of command arguments (e.g., ["pymol"] or ["python", "-m", "pymol"])
        or None if PyMOL is not found.
    """
    # Check if pymol is in PATH
    pymol_path = shutil.which("pymol")
    if pymol_path:
        return [pymol_path]

    # Check uv environment first
    uv_python = os.path.expanduser("~/.pymol-env/bin/python")
    if os.path.isfile(uv_python) and os.access(uv_python, os.X_OK):
        try:
            result = subprocess.run(
                [uv_python, "-c", "import pymol"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return [uv_python, "-m", "pymol"]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # Check other common paths
    for path in PYMOL_PATHS:
        if path.endswith("/python"):
            continue  # Already checked uv environment above
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return [path]

    return None


def find_pymol_executable():
    """Find PyMOL executable path (legacy compatibility)."""
    cmd = find_pymol_command()
    return cmd[0] if cmd else None


def check_pymol_installed():
    """Check if pymol command is available."""
    return find_pymol_command() is not None


def get_plugin_path():
    """Get the path to the socket plugin file."""
    return Path(__file__).parent / "plugin.py"


def launch_pymol(
    file_path=None,
    wait_for_socket=True,
    timeout=10.0,
    headless=False,
    capture_output=False,
):
    """
    Launch PyMOL with the agent bridge plugin.

    Args:
        file_path: Optional file to open (e.g., .pdb, .cif)
        wait_for_socket: Wait for socket to become available
        timeout: How long to wait for socket
        headless: If True, launch PyMOL in command-line mode (no GUI, -c flag)
        capture_output: If True, capture stdout/stderr (for startup diagnostics)

    Returns:
        subprocess.Popen process handle
    """
    pymol_cmd = find_pymol_command()
    if not pymol_cmd:
        raise RuntimeError(
            "PyMOL not found. Please install PyMOL:\n"
            "  - Run: pymol-agent-bridge setup\n"
            "  - Or: pip install pymol-open-source-whl\n"
            "  - Or: brew install pymol (macOS)"
        )

    plugin_path = get_plugin_path()
    if not plugin_path.exists():
        raise RuntimeError(f"Plugin not found: {plugin_path}")

    # Build command: base pymol command
    cmd_args = list(pymol_cmd)

    # Headless mode: -c must come before -d flags
    if headless:
        cmd_args.append("-c")

    # Optional file to open
    if file_path:
        cmd_args.append(str(file_path))

    # Only inject plugin via -d if .pymolrc doesn't already load it
    if not is_plugin_in_pymolrc():
        cmd_args.extend(["-d", f"run {plugin_path}"])

    # Launch
    popen_kwargs = {}
    if capture_output:
        popen_kwargs["stdout"] = subprocess.PIPE
        popen_kwargs["stderr"] = subprocess.PIPE

    process = subprocess.Popen(cmd_args, **popen_kwargs)

    if wait_for_socket:
        start = time.time()
        while time.time() - start < timeout:
            # Check if process died during startup
            if process.poll() is not None:
                if capture_output:
                    raw_out, raw_err = process.communicate(timeout=1)
                    out = raw_out.decode() if isinstance(raw_out, bytes) else raw_out
                    err = raw_err.decode() if isinstance(raw_err, bytes) else raw_err
                    raise RuntimeError(
                        f"PyMOL exited during startup.\nstdout: {out}\nstderr: {err}"
                    )
                raise RuntimeError("PyMOL exited during startup.")

            try:
                conn = PyMOLConnection()
                conn.connect(timeout=1.0)
                conn.disconnect()
                return process
            except ConnectionError:
                time.sleep(0.5)
        raise TimeoutError(f"PyMOL socket not available after {timeout}s")

    return process


def connect_or_launch(file_path=None, headless=False):
    """
    Connect to existing PyMOL or launch new instance.

    Args:
        file_path: Optional file to open
        headless: If True, launch in command-line mode (no GUI)

    Returns:
        (PyMOLConnection, process_or_None)
    """
    conn = PyMOLConnection()

    # Try connecting to existing instance
    try:
        conn.connect(timeout=1.0)
        return conn, None
    except ConnectionError:
        pass

    # Launch new instance
    process = launch_pymol(file_path=file_path, headless=headless)
    conn.connect()
    return conn, process


# --- Config persistence ---


def get_config():
    """Read persisted config."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_config(config):
    """Save config."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2) + "\n")


def get_configured_python():
    """Get the Python path from persisted config. Returns path string or None."""
    config = get_config()
    python_path = config.get("python_path")
    if python_path and os.path.isfile(python_path) and os.access(python_path, os.X_OK):
        return python_path
    return None
