# PeerWire Message Protocol

PeerWire runs over a single TCP connection per client to the server (default port **5000**).

## 1. Framing

TCP is a byte stream, so every message is framed with a length prefix:

```
+---------------------------------+------------------------------------+
| 4 bytes: payload length N       | N bytes: UTF-8 JSON object         |
| unsigned 32-bit, big-endian     | {"type": "...", ...}               |
+---------------------------------+------------------------------------+
```

* Example: `{"type":"PING"}` is 15 bytes, so the frame is `00 00 00 0F` + `{"type":"PING"}`.
* The receiver buffers bytes until it has 4 header bytes, then until it has N body bytes.
  Any extra bytes belong to the next frame (`FrameDecoder` in `src/protocol.py`).
* Maximum payload: **64 KiB**. A larger length makes the server reply `ERROR "frame too large"` and close that connection.

## 2. Client → server

| type | fields | needs registration | server reply |
|---|---|---|---|
| `REGISTER` | `username` (3–20 letters/digits/underscore, unique, case-insensitive) | no (must be first) | `REGISTER_ACK` or `REGISTER_FAIL` |
| `BROADCAST` | `content` (1–2000 chars after trimming) | yes | `BROADCAST` to everyone in the sender's room (including sender) |
| `DIRECT` | `target`, `content` | yes | `DIRECT` to target, plus a copy with `is_echo: true` to sender; `SYSTEM` if target offline |
| `ROOM_JOIN` | `room` (`#` + 1–24 of `a-z 0-9 _ -`) | yes | `SYSTEM` notices to old and new room, `USER_LIST` to all |
| `USER_LIST` | – | yes | `USER_LIST` |
| `PING` | optional `id` | no | `PONG` (same `id`) |
| `DISCONNECT` | – | no | none; server closes and cleans up |

## 3. Server → client

| type | fields |
|---|---|
| `REGISTER_ACK` | `username`, `room`, `info`, `client_addr` (the client's IP:port as the server sees it) |
| `REGISTER_FAIL` | `reason` (connection stays open so the client may retry) |
| `BROADCAST` | `sender`, `room`, `content`, `timestamp` |
| `DIRECT` | `sender`, `target`, `content`, `timestamp`, optional `is_echo` |
| `SYSTEM` | `content`, optional `room` (joins, leaves, disconnects, shutdown) |
| `USER_LIST` | `users`: list of `{username, room, port}` |
| `ERROR` | `message` (malformed or invalid input; connection stays open) |
| `PONG` | `id` |

## 4. Errors

Every problem with a complete frame produces `{"type":"ERROR","message":"..."}` and the connection keeps working:
invalid UTF-8, not JSON, JSON that is not an object, missing `type`, unknown `type`, wrong field types,
empty or too-long messages, invalid room, sending chat before registering.
Only an oversized frame closes the connection, because the stream can no longer be trusted.

## 5. Example exchange

```
C: {"type": "REGISTER", "username": "Alice"}
S: {"type": "REGISTER_ACK", "username": "Alice", "room": "#general", "info": "...", "client_addr": "127.0.0.1:52184"}
S: {"type": "SYSTEM", "content": "-> Alice joined #general", "room": "#general"}
S: {"type": "USER_LIST", "users": [{"username": "Alice", "room": "#general", "port": 52184}]}
C: {"type": "BROADCAST", "content": "Hello everyone"}
S: {"type": "BROADCAST", "sender": "Alice", "room": "#general", "content": "Hello everyone", "timestamp": "14:02:11"}
C: {"type": "DIRECT", "target": "Bob", "content": "Hi Bob"}
S: {"type": "DIRECT", "sender": "Alice", "target": "Bob", "content": "Hi Bob", "timestamp": "14:02:20", "is_echo": true}
C: {"type": "DISCONNECT"}
```
