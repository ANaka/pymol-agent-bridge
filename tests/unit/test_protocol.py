"""Unit tests for the wire protocol (length-prefixed JSON framing)."""

import json
import struct

import pytest

from pymol_agent_bridge.protocol import (
    HEADER_SIZE,
    MAX_FRAME_SIZE,
    _recv_exact,
    recv_message,
    send_message,
)


class TestSendMessage:
    def test_framing(self, socket_pair):
        """send_message writes a 4-byte BE header followed by JSON."""
        a, b = socket_pair
        msg = {"type": "ping"}
        send_message(a, msg)

        raw = b.recv(4096)
        length = struct.unpack("!I", raw[:HEADER_SIZE])[0]
        payload = json.loads(raw[HEADER_SIZE:])

        assert length == len(json.dumps(msg).encode("utf-8"))
        assert payload == msg

    def test_oversized_message(self, socket_pair):
        """Messages exceeding MAX_FRAME_SIZE raise ValueError."""
        a, _b = socket_pair
        big_msg = {"data": "x" * (MAX_FRAME_SIZE + 1)}
        with pytest.raises(ValueError, match="Message too large"):
            send_message(a, big_msg)


class TestRecvMessage:
    def test_valid_message(self, socket_pair):
        """recv_message decodes a properly framed message."""
        a, b = socket_pair
        msg = {"status": "success", "output": "hello"}
        send_message(a, msg)
        result = recv_message(b)
        assert result == msg

    def test_empty_frame(self, socket_pair):
        """A frame with length 0 raises ValueError."""
        a, b = socket_pair
        a.sendall(struct.pack("!I", 0))
        with pytest.raises(ValueError, match="Empty frame"):
            recv_message(b)

    def test_oversized_frame(self, socket_pair):
        """A frame header claiming > MAX_FRAME_SIZE raises ValueError."""
        a, b = socket_pair
        a.sendall(struct.pack("!I", MAX_FRAME_SIZE + 1))
        with pytest.raises(ValueError, match="Frame too large"):
            recv_message(b)


class TestRecvExact:
    def test_connection_closed(self, socket_pair):
        """Peer closing the socket raises ConnectionError."""
        a, b = socket_pair
        a.close()
        with pytest.raises(ConnectionError, match="Connection closed"):
            _recv_exact(b, 10)


class TestRoundtrip:
    def test_ping_pong(self, socket_pair):
        """Ping message survives a send/recv roundtrip."""
        a, b = socket_pair
        send_message(a, {"type": "ping"})
        assert recv_message(b) == {"type": "ping"}

    def test_execute(self, socket_pair):
        """Execute message with code survives a send/recv roundtrip."""
        a, b = socket_pair
        msg = {"type": "execute", "code": "print('hello')"}
        send_message(a, msg)
        assert recv_message(b) == msg
