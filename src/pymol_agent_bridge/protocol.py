"""
Wire protocol for pymol-agent-bridge.

Uses length-prefixed JSON framing:
  [4-byte big-endian length][JSON payload]

Message types:
  - execute: {"type": "execute", "code": "..."}
  - ping:    {"type": "ping"}
  - pong:    {"type": "pong"}
  - response: {"status": "success"|"error", ...}
  - busy:    {"status": "error", "error": "Server busy ..."}
"""

import json
import socket
import struct

MAX_FRAME_SIZE = 10 * 1024 * 1024  # 10 MB
HEADER_SIZE = 4


def send_message(sock: socket.socket, message: dict) -> None:
    """Send a length-prefixed JSON message."""
    data = json.dumps(message).encode("utf-8")
    if len(data) > MAX_FRAME_SIZE:
        raise ValueError(f"Message too large: {len(data)} bytes")
    header = struct.pack("!I", len(data))
    sock.sendall(header + data)


def recv_message(sock: socket.socket) -> dict:
    """Receive a length-prefixed JSON message."""
    header = _recv_exact(sock, HEADER_SIZE)
    (length,) = struct.unpack("!I", header)
    if length > MAX_FRAME_SIZE:
        raise ValueError(f"Frame too large: {length} bytes")
    if length == 0:
        raise ValueError("Empty frame")
    data = _recv_exact(sock, length)
    return json.loads(data.decode("utf-8"))


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    """Read exactly *n* bytes from *sock*.

    Re-raises ``socket.timeout`` only when zero bytes have been received
    (so callers can use it as a poll signal).  Partial reads keep retrying.
    """
    buf = bytearray()
    while len(buf) < n:
        try:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("Connection closed by peer")
            buf.extend(chunk)
        except socket.timeout:
            if not buf:
                raise  # nothing received yet — let caller decide
            continue  # mid-message — keep reading
    return bytes(buf)
