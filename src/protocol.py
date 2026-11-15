"""
CSC 423 - Transport Layer Protocol Definition
=============================================
This module defines the Application Layer Framing Protocol layered on top of TCP.

TCP Stream Framing Design:
-------------------------
TCP provides a reliable, ordered, but UNSTRUCTURED stream of bytes (Layer 4).
TCP has NO concept of message boundaries or "packets" at the application layer:
- Multiple client calls to send() may be coalesced by Nagle's algorithm into a single TCP segment.
- A single send() call may be fragmented across multiple TCP segments due to the Maximum Segment Size (MSS) / MTU.

To recover distinct application-layer messages from a continuous TCP stream, this protocol
employs Length-Prefixed Framing (TLV - Type-Length-Value pattern):
  [ 4 Bytes: Payload Length (Big-Endian unsigned int) ] + [ N Bytes: JSON-encoded UTF-8 Payload ]

Header format:
  - 4 bytes: struct.pack('>I', length) -> allows message sizes up to 4,294,967,295 bytes.
  - Body: JSON string containing message metadata and content.
"""

import json
import struct
import socket
from typing import Optional, Dict, Any

# Length prefix is a 4-byte unsigned integer in Network Byte Order (Big-Endian: '>')
HEADER_STRUCT = struct.Struct('>I')
HEADER_SIZE = HEADER_STRUCT.size  # Exactly 4 bytes

# Protocol message types
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


def recv_exact(sock: socket.socket, num_bytes: int) -> Optional[bytes]:
    """
    Receives exactly `num_bytes` from the TCP socket buffer.
    
    Transport-Layer Significance:
    -----------------------------
    sock.recv(n) returns BETWEEN 1 and n bytes depending on network buffering,
    window size, and OS socket buffer availability. It does NOT guarantee
    returning n bytes in a single call. recv_exact loops until the full expected
    byte sequence is gathered.
    
    Returns:
        bytes: The exactly requested byte sequence.
        None: If the peer closed the connection gracefully (EOF / TCP FIN).
    """
    chunks = []
    bytes_recd = 0
    while bytes_recd < num_bytes:
        try:
            chunk = sock.recv(min(num_bytes - bytes_recd, 4096))
        except (ConnectionResetError, ConnectionAbortedError, TimeoutError):
            return None
            
        if not chunk:
            # An empty byte response (b'') indicates peer sent TCP FIN (clean close)
            return None
        chunks.append(chunk)
        bytes_recd += len(chunk)
    return b"".join(chunks)


def send_message(sock: socket.socket, payload: Dict[str, Any]) -> bool:
    """
    Serializes a Python dictionary to JSON, prepends a 4-byte length prefix,
    and sends the complete frame over the TCP socket.
    
    Returns:
        bool: True if sent successfully, False if socket write failed.
    """
    try:
        raw_body = json.dumps(payload).encode("utf-8")
        header = HEADER_STRUCT.pack(len(raw_body))
        # sendall() continues to transmit until all data has been sent or an error occurs
        sock.sendall(header + raw_body)
        return True
    except (BrokenPipeError, ConnectionResetError, OSError):
        return False


def recv_message(sock: socket.socket) -> Optional[Dict[str, Any]]:
    """
    Reads one complete framed message from the TCP socket:
    1. Reads 4-byte length header.
    2. Reads payload of that exact length.
    3. Deserializes JSON into a dictionary.
    
    Returns:
        dict: The parsed message dictionary, or None on EOF/socket error.
    """
    header_data = recv_exact(sock, HEADER_SIZE)
    if not header_data:
        return None
    
    (payload_length,) = HEADER_STRUCT.unpack(header_data)
    
    # Safety guard against corrupted or excessively large frames (max 10MB)
    if payload_length > 10 * 1024 * 1024:
        raise ValueError(f"Message payload exceeds safety limit: {payload_length} bytes")
        
    body_data = recv_exact(sock, payload_length)
    if not body_data:
        return None
        
    try:
        return json.loads(body_data.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
