"""
CSC 423 - PeerWire Application-Layer Protocol (on top of TCP)
=============================================================
TCP gives the application an ordered, reliable BYTE STREAM. It does not keep the
boundaries between the application's send() calls:
  - several small messages can arrive together in one recv() (combined), and
  - one message can be spread over several recv() calls (split).

PeerWire therefore frames every message explicitly with a LENGTH PREFIX:

    +------------------------------+-----------------------------------+
    | 4 bytes: payload length N    | N bytes: UTF-8 encoded JSON object |
    | unsigned int, big-endian     | e.g. {"type": "BROADCAST", ...}    |
    +------------------------------+-----------------------------------+

The receiver first collects exactly 4 bytes, reads N from them, then collects
exactly N more bytes. Whatever is left over belongs to the next message.
Frames larger than MAX_FRAME_BYTES are refused to protect server memory.
"""

import json
import re
import socket
import struct
import sys
from typing import Any, Dict, List, Optional

# Length prefix: 4-byte unsigned int in network byte order (big-endian).
HEADER_STRUCT = struct.Struct(">I")
HEADER_SIZE = HEADER_STRUCT.size  # 4 bytes

MAX_FRAME_BYTES = 64 * 1024          # largest accepted JSON payload (64 KiB)
MAX_MESSAGE_CHARS = 2000             # largest chat message text
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
ROOM_RE = re.compile(r"^#[a-z0-9_-]{1,24}$")

# Message types
MSG_REGISTER = "REGISTER"
MSG_REGISTER_ACK = "REGISTER_ACK"
MSG_REGISTER_FAIL = "REGISTER_FAIL"
MSG_BROADCAST = "BROADCAST"
MSG_DIRECT = "DIRECT"
MSG_ROOM_JOIN = "ROOM_JOIN"
MSG_ROOM_LEAVE = "ROOM_LEAVE"
MSG_USER_LIST = "USER_LIST"
MSG_SYSTEM = "SYSTEM"
MSG_ERROR = "ERROR"
MSG_DISCONNECT = "DISCONNECT"
MSG_PING = "PING"
MSG_PONG = "PONG"


class FrameTooLarge(Exception):
    """The length prefix announced a payload bigger than MAX_FRAME_BYTES."""


class ProtocolError(Exception):
    """A complete frame arrived but its payload is not a valid PeerWire message."""


# ----------------------------------------------------------------------------
# Encoding
# ----------------------------------------------------------------------------
def encode_frame(payload: Dict[str, Any]) -> bytes:
    """Serialise a dict to JSON and prepend the 4-byte length prefix."""
    body = json.dumps(payload).encode("utf-8")
    return HEADER_STRUCT.pack(len(body)) + body


# ----------------------------------------------------------------------------
# Incremental decoding (used by the server)
# ----------------------------------------------------------------------------
class FrameDecoder:
    """Turns arbitrary chunks of a TCP byte stream into complete frames.

    feed() can be given any slice of the stream: half a header, three messages
    at once, a message cut in the middle of a multi-byte UTF-8 character. It
    returns every frame that is now complete and keeps the rest buffered.
    """

    def __init__(self, max_frame: int = MAX_FRAME_BYTES):
        self.buffer = bytearray()
        self.max_frame = max_frame

    def feed(self, data: bytes) -> List[bytes]:
        self.buffer += data
        frames: List[bytes] = []
        while len(self.buffer) >= HEADER_SIZE:
            (length,) = HEADER_STRUCT.unpack_from(self.buffer, 0)
            if length > self.max_frame:
                raise FrameTooLarge(f"frame of {length} bytes exceeds {self.max_frame}")
            if len(self.buffer) < HEADER_SIZE + length:
                break  # the rest of this frame has not arrived yet
            frames.append(bytes(self.buffer[HEADER_SIZE:HEADER_SIZE + length]))
            del self.buffer[:HEADER_SIZE + length]
        return frames

    @property
    def buffered(self) -> int:
        return len(self.buffer)


def parse_payload(raw: bytes) -> Dict[str, Any]:
    """Decode one frame payload. Raises ProtocolError with a readable reason."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ProtocolError("payload is not valid UTF-8")
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        raise ProtocolError("payload is not valid JSON")
    if not isinstance(obj, dict):
        raise ProtocolError("payload must be a JSON object")
    if not isinstance(obj.get("type"), str):
        raise ProtocolError("missing or invalid 'type' field")
    return obj


# ----------------------------------------------------------------------------
# Blocking helpers (used by the clients and tests)
# ----------------------------------------------------------------------------
def recv_exact(sock: socket.socket, num_bytes: int) -> Optional[bytes]:
    """Receive exactly num_bytes. recv(n) may return anything from 1 to n bytes,
    so we loop. Returns None if the peer closed the connection (FIN) or reset it."""
    chunks = []
    received = 0
    while received < num_bytes:
        try:
            chunk = sock.recv(min(num_bytes - received, 4096))
        except (ConnectionResetError, ConnectionAbortedError):
            return None
        if not chunk:  # b"" means the peer sent FIN
            return None
        chunks.append(chunk)
        received += len(chunk)
    return b"".join(chunks)


def send_message(sock: socket.socket, payload: Dict[str, Any]) -> bool:
    """Send one framed message. sendall() keeps writing until every byte is queued."""
    try:
        sock.sendall(encode_frame(payload))
        return True
    except OSError:  # BrokenPipe, ConnectionReset, send timeout, closed socket
        return False


def recv_message(sock: socket.socket) -> Optional[Dict[str, Any]]:
    """Read one complete framed message (blocking). None on EOF or invalid data."""
    header = recv_exact(sock, HEADER_SIZE)
    if not header:
        return None
    (length,) = HEADER_STRUCT.unpack(header)
    if length > MAX_FRAME_BYTES:
        raise FrameTooLarge(f"frame of {length} bytes exceeds {MAX_FRAME_BYTES}")
    body = recv_exact(sock, length) if length else b""
    if body is None:
        return None
    try:
        return parse_payload(body)
    except ProtocolError:
        return None


def abort_connection(sock: socket.socket) -> None:
    """Close with SO_LINGER timeout 0: the OS discards unsent data and sends RST
    instead of the normal FIN handshake (used to demonstrate an abrupt close)."""
    fmt = "HH" if sys.platform == "win32" else "ii"  # struct linger differs per OS
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack(fmt, 1, 0))
    sock.close()
