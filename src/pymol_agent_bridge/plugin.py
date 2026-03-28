"""
PyMOL Agent Bridge Plugin

Socket listener that receives commands from agents and terminals via TCP.
Auto-starts on load, no UI required.

Usage:
    run /path/to/plugin.py    # Start listening
    bridge_status             # Check connection status
    bridge_stop               # Stop listener
    bridge_start              # Restart listener
"""

import io
import json
import socket
import struct
import threading
import traceback
from contextlib import redirect_stdout

from pymol import cmd

# --- Inline protocol (plugin must be self-contained for `run` loading) ---

_MAX_FRAME_SIZE = 10 * 1024 * 1024  # 10 MB
_HEADER_SIZE = 4


def _send_message(sock, message):
    data = json.dumps(message).encode("utf-8")
    if len(data) > _MAX_FRAME_SIZE:
        raise ValueError(f"Message too large: {len(data)} bytes")
    sock.sendall(struct.pack("!I", len(data)) + data)


def _recv_message(sock):
    header = _recv_exact(sock, _HEADER_SIZE)
    (length,) = struct.unpack("!I", header)
    if length > _MAX_FRAME_SIZE:
        raise ValueError(f"Frame too large: {length} bytes")
    if length == 0:
        raise ValueError("Empty frame")
    data = _recv_exact(sock, length)
    return json.loads(data.decode("utf-8"))


def _recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        try:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("Connection closed by peer")
            buf.extend(chunk)
        except socket.timeout:
            if not buf:
                raise  # nothing received yet - let caller decide
            continue  # mid-message - keep reading
    return bytes(buf)


# --- Server ---

# Global state
_server = None
_port = 9880


class SocketServer:
    def __init__(self, host="localhost", port=9880):
        self.host = host
        self.port = port
        self.socket = None
        self.running = False
        self.thread = None
        self._client_lock = threading.Lock()
        self._active_client = None

    def start(self):
        if self.running:
            return False
        self.running = True
        self.thread = threading.Thread(target=self._run_server, daemon=True)
        self.thread.start()
        return True

    def _run_server(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(1)
            self.socket.settimeout(1.0)

            print(f"Agent bridge listener active on port {self.port}")

            while self.running:
                try:
                    new_client, address = self.socket.accept()
                    with self._client_lock:
                        if self._active_client is not None:
                            try:
                                _send_message(
                                    new_client,
                                    {
                                        "status": "error",
                                        "error": "Server busy",
                                    },
                                )
                            except Exception:
                                pass
                            new_client.close()
                            continue
                        self._active_client = new_client
                    handler = threading.Thread(
                        target=self._handle_client,
                        args=(new_client, address),
                        daemon=True,
                    )
                    handler.start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"Connection error: {e}")
        except Exception as e:
            print(f"Socket server error: {e}")
            traceback.print_exc()
        finally:
            self._cleanup()

    def _handle_client(self, client, address):
        client.settimeout(5.0)
        try:
            while self.running:
                try:
                    message = _recv_message(client)
                    if message.get("type") == "ping":
                        _send_message(client, {"status": "success", "type": "pong"})
                        continue
                    result = self._execute_command(message)
                    _send_message(client, result)
                except socket.timeout:
                    continue
                except (ConnectionError, ValueError):
                    break
                except Exception as e:
                    if self.running:
                        print(f"Client error: {e}")
                    break
        finally:
            try:
                client.close()
            except Exception:
                pass
            with self._client_lock:
                if self._active_client is client:
                    self._active_client = None

    def _execute_command(self, command):
        code = command.get("code", "")
        if not code:
            return {"status": "error", "error": "No code provided"}
        try:
            exec_globals = {"cmd": cmd, "__builtins__": __builtins__}
            output_buffer = io.StringIO()
            with redirect_stdout(output_buffer):
                exec(code, exec_globals)  # noqa: S102 — intentional; this is the bridge's core mechanism
            output = output_buffer.getvalue()
            if "_result" in exec_globals:
                output = str(exec_globals["_result"])
            return {"status": "success", "output": output or "OK"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _cleanup(self):
        with self._client_lock:
            if self._active_client:
                try:
                    self._active_client.close()
                except Exception:
                    pass
                self._active_client = None
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
        self.socket = None
        self.running = False

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(2.0)
        self._cleanup()

    @property
    def is_running(self):
        return self.running and self.thread and self.thread.is_alive()


def bridge_status():
    """Print agent bridge listener status."""
    global _server
    if _server and _server.is_running:
        with _server._client_lock:
            connected = "connected" if _server._active_client else "waiting"
        print(f"Agent bridge listener: running on port {_port} ({connected})")
    else:
        print("Agent bridge listener: not running")


def bridge_stop():
    """Stop the agent bridge listener."""
    global _server
    if _server:
        _server.stop()
        _server = None
        print("Agent bridge listener stopped")
    else:
        print("Agent bridge listener was not running")


def _port_in_use(port):
    """Check if a port is already bound."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("localhost", port))
        return False
    except OSError:
        return True
    finally:
        s.close()


def bridge_start(port=9880):
    """Start the agent bridge listener."""
    global _server, _port
    if _server and _server.is_running:
        print(f"Agent bridge listener already running on port {_port}")
        return
    if _port_in_use(port):
        print(f"Agent bridge listener already active on port {port} (skipping)")
        return
    _port = port
    _server = SocketServer(port=port)
    _server.start()


# Register commands with PyMOL
cmd.extend("bridge_status", bridge_status)
cmd.extend("bridge_stop", bridge_stop)
cmd.extend("bridge_start", bridge_start)

# Auto-start on load
bridge_start()
