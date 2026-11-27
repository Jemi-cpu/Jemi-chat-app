"""
CSC 423 - PeerWire Automated Integration Test Suite
===================================================
Tests core transport-layer socket features:
1. TCP 3-way handshake and connection establishment.
2. User registration and conflict rejection.
3. Group chat broadcast within channels.
4. One-to-one private direct messaging (DM isolation).
5. Presence detection and graceful disconnection (TCP FIN / DISCONNECT).
6. Malformed input and validation errors do not crash the server or close the connection.
7. Frames combined in one TCP write or split across several writes on a real socket.
8. Three simultaneous clients: one aborts with RST, the others keep chatting, it reconnects.
9. Oversized frames close only the offending connection.
10. Connection events are written to the server log file.
"""

import sys
import os
import time
import socket
import threading
import tempfile
import unittest
from typing import Optional, Dict, Any

# Ensure src/ is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from protocol import (
    recv_message,
    send_message,
    MSG_REGISTER,
    MSG_REGISTER_ACK,
    MSG_REGISTER_FAIL,
    MSG_BROADCAST,
    MSG_DIRECT,
    MSG_ROOM_JOIN,
    MSG_USER_LIST,
    MSG_DISCONNECT,
)
from protocol import HEADER_STRUCT, encode_frame, abort_connection, MSG_ERROR, MSG_PING, MSG_PONG

LOG_DIR = tempfile.mkdtemp(prefix="peerwire_test_")
LOG_PATH = os.path.join(LOG_DIR, "server.log")
os.environ["LOG_FILE"] = LOG_PATH

from server import PeerWireServer  # noqa: E402


def recv_until(sock: socket.socket, target_type: str, timeout: float = 2.0) -> Optional[Dict[str, Any]]:
    """Helper to read messages from socket until a specific type is received or timeout."""
    start = time.time()
    sock.settimeout(0.3)
    while time.time() - start < timeout:
        try:
            msg = recv_message(sock)
            if msg and msg.get("type") == target_type:
                return msg
        except (socket.timeout, TimeoutError):
            continue
        except OSError:
            break
    return None


class TestPeerWireChat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Starts server in background thread on test port 5099."""
        cls.test_port = 5099
        cls.server = PeerWireServer(host="127.0.0.1", port=cls.test_port)
        cls.server_thread = threading.Thread(target=cls.server.start, daemon=True)
        cls.server_thread.start()
        cls.server.ready.wait(3)

    @classmethod
    def tearDownClass(cls):
        """Shuts down server after tests."""
        cls.server.shutdown()
        time.sleep(0.2)

    def _create_client(self, username: str) -> socket.socket:
        """Helper to create connected socket and register username."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", self.test_port))
        send_message(s, {"type": MSG_REGISTER, "username": username})
        ack = recv_until(s, MSG_REGISTER_ACK, timeout=2.0)
        self.assertIsNotNone(ack, f"Registration failed for {username}")
        return s

    def _close_client(self, sock: socket.socket):
        """Cleanly disconnects client socket."""
        try:
            send_message(sock, {"type": MSG_DISCONNECT})
            sock.close()
        except OSError:
            pass

    def test_01_registration_and_duplicate_rejection(self):
        """Verify username registration and duplicate rejection."""
        s1 = self._create_client("UserOne")
        
        # Second socket attempts to claim identical username
        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s2.connect(("127.0.0.1", self.test_port))
        send_message(s2, {"type": MSG_REGISTER, "username": "UserOne"})
        fail_msg = recv_until(s2, MSG_REGISTER_FAIL, timeout=2.0)
        
        self.assertIsNotNone(fail_msg)
        self.assertIn("already taken", fail_msg.get("reason", ""))
        
        self._close_client(s1)
        self._close_client(s2)
        time.sleep(0.2)

    def test_02_broadcast_messaging_between_peers(self):
        """Verify real-time broadcast messaging between Alice and Bob."""
        alice = self._create_client("Alice")
        bob = self._create_client("Bob")
        
        # Alice broadcasts to #general
        send_message(alice, {
            "type": MSG_BROADCAST,
            "room": "#general",
            "content": "Hello PeerWire network!",
        })
        
        # Bob should receive Alice's broadcast
        received = recv_until(bob, MSG_BROADCAST, timeout=2.0)
        self.assertIsNotNone(received)
        self.assertEqual(received.get("sender"), "Alice")
        self.assertEqual(received.get("content"), "Hello PeerWire network!")
        
        self._close_client(alice)
        self._close_client(bob)
        time.sleep(0.2)

    def test_03_private_direct_message_isolation(self):
        """Verify that private DMs are delivered only to intended recipient."""
        alice = self._create_client("AliceDM")
        bob = self._create_client("BobDM")
        charlie = self._create_client("CharlieDM")
        
        # Bob sends private message to Alice
        send_message(bob, {
            "type": MSG_DIRECT,
            "target": "AliceDM",
            "content": "Confidential transport layer data",
        })
        
        # Alice must receive the DM
        alice_dm = recv_until(alice, MSG_DIRECT, timeout=2.0)
        self.assertIsNotNone(alice_dm)
        self.assertEqual(alice_dm.get("sender"), "BobDM")
        self.assertEqual(alice_dm.get("content"), "Confidential transport layer data")
        
        # Charlie must NOT receive the DM
        charlie_dm = recv_until(charlie, MSG_DIRECT, timeout=0.5)
        self.assertIsNone(charlie_dm, "Private DM was leaked to Charlie!")
        
        self._close_client(alice)
        self._close_client(bob)
        self._close_client(charlie)
        time.sleep(0.2)

    def test_04_graceful_disconnect_handling(self):
        """Verify server cleans up client registry on disconnect."""
        alice = self._create_client("AliceDC")
        bob = self._create_client("BobDC")
        
        # Alice disconnects cleanly
        self._close_client(alice)
        time.sleep(0.25)
        
        # Drain any welcome/registration messages queued in Bob's socket
        drain_start = time.time()
        bob.settimeout(0.1)
        while time.time() - drain_start < 0.3:
            try:
                recv_message(bob)
            except (socket.timeout, TimeoutError, OSError):
                break
        bob.settimeout(None)

        # Bob queries user list; Alice should not be present
        send_message(bob, {"type": MSG_USER_LIST})
        users_resp = recv_until(bob, MSG_USER_LIST, timeout=2.0)
        
        self.assertIsNotNone(users_resp)
        online_names = [u["username"] for u in users_resp.get("users", [])]
        self.assertNotIn("AliceDC", online_names)
        self.assertIn("BobDC", online_names)
        
        self._close_client(bob)


    # ------------------------------------------------------------------ new tests
    def _raw_client(self) -> socket.socket:
        return socket.create_connection(("127.0.0.1", self.test_port))

    def _ping_ok(self, sock) -> bool:
        send_message(sock, {"type": MSG_PING, "id": 99})
        return recv_until(sock, MSG_PONG, timeout=2.0) is not None

    def test_05_malformed_input_gets_error_and_connection_survives(self):
        s = self._create_client("Malformed")
        bad_payloads = [
            b"this is not json",
            bytes([0xFF, 0xFE, 0xFD]),                 # invalid UTF-8
            b"[1, 2, 3]",                              # JSON but not an object
            b'{"content": "no type"}',                 # missing type
            json_bytes({"type": "NO_SUCH_COMMAND"}),
            json_bytes({"type": "BROADCAST", "content": 12345}),
            json_bytes({"type": "BROADCAST", "content": "    "}),
            json_bytes({"type": "BROADCAST", "content": "x" * 2001}),
            json_bytes({"type": "DIRECT", "content": "no target"}),
            json_bytes({"type": "ROOM_JOIN", "room": "bad room name"}),
        ]
        for raw in bad_payloads:
            s.sendall(HEADER_STRUCT.pack(len(raw)) + raw)
            err = recv_until(s, MSG_ERROR, timeout=2.0)
            self.assertIsNotNone(err, f"no ERROR reply for {raw[:40]!r}")
        self.assertTrue(self._ping_ok(s), "connection should still work after malformed input")
        self._close_client(s)
        time.sleep(0.2)

    def test_06_username_validation(self):
        for name in ["ab", "has space", "x" * 21, "semi;colon", 123, None]:
            s = self._raw_client()
            send_message(s, {"type": MSG_REGISTER, "username": name})
            self.assertIsNotNone(recv_until(s, MSG_REGISTER_FAIL, timeout=2.0), f"{name!r} accepted")
            s.close()
        s = self._raw_client()
        send_message(s, {"type": MSG_BROADCAST, "content": "before register"})
        self.assertIsNotNone(recv_until(s, MSG_ERROR, timeout=2.0))
        s.close()

    def test_07_combined_and_split_frames_on_real_socket(self):
        s = self._raw_client()
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        # combined: three frames in one write
        s.sendall(encode_frame({"type": MSG_REGISTER, "username": "Framer"})
                  + encode_frame({"type": MSG_PING, "id": 1})
                  + encode_frame({"type": MSG_USER_LIST}))
        self.assertIsNotNone(recv_until(s, MSG_REGISTER_ACK))
        self.assertIsNotNone(recv_until(s, MSG_PONG))
        self.assertIsNotNone(recv_until(s, MSG_USER_LIST))
        # split: one frame in three writes, the first only 2 bytes of the header
        frame = encode_frame({"type": MSG_BROADCAST, "content": "split across writes ☕"})
        for a, b in [(0, 2), (2, 15), (15, len(frame))]:
            s.sendall(frame[a:b])
            time.sleep(0.15)
        echo = recv_until(s, MSG_BROADCAST, timeout=2.0)
        self.assertIsNotNone(echo)
        self.assertEqual(echo["content"], "split across writes ☕")
        self._close_client(s)
        time.sleep(0.2)

    def test_08_three_clients_abort_and_reconnect(self):
        a = self._create_client("ClientA")
        b = self._create_client("ClientB")
        c = self._create_client("ClientC")
        abort_connection(c)                      # C disappears with RST
        time.sleep(0.3)
        send_message(a, {"type": MSG_BROADCAST, "content": "A still here"})
        got = recv_until(b, MSG_BROADCAST, timeout=2.0)
        self.assertIsNotNone(got)
        self.assertEqual(got["sender"], "ClientA")
        c2 = self._create_client("ClientC")      # name was released by cleanup
        send_message(b, {"type": MSG_BROADCAST, "content": "welcome back C"})
        got = recv_until(c2, MSG_BROADCAST, timeout=2.0)
        self.assertIsNotNone(got)
        self.assertEqual(got["content"], "welcome back C")
        for s in (a, b, c2):
            self._close_client(s)
        time.sleep(0.2)

    def test_09_oversized_frame_closes_only_that_connection(self):
        good = self._create_client("Survivor")
        bad = self._raw_client()
        bad.sendall(HEADER_STRUCT.pack(10 * 1024 * 1024))
        bad.settimeout(2)
        data = b""
        try:
            while True:
                chunk = bad.recv(4096)
                if not chunk:
                    break
                data += chunk
        except OSError:
            pass
        self.assertIn(b"frame too large", data)
        self.assertTrue(self._ping_ok(good), "other clients must be unaffected")
        bad.close()
        self._close_client(good)
        time.sleep(0.2)

    def test_10_server_log_records_connection_events(self):
        c = self._create_client("Logged")
        abort_connection(c)
        time.sleep(0.4)
        for h in self.server_logger_handlers():
            h.flush()
        with open(LOG_PATH, encoding="utf-8") as f:
            log = f.read()
        self.assertIn("[CONNECT] TCP connection from 127.0.0.1:", log)
        self.assertIn("[REGISTERED] 'Logged'", log)
        self.assertIn("RST received", log)
        self.assertIn("[MALFORMED]", log)

    def server_logger_handlers(self):
        import logging
        return logging.getLogger("PeerWireServer").handlers


def json_bytes(obj) -> bytes:
    import json
    return json.dumps(obj).encode()

if __name__ == "__main__":
    unittest.main(verbosity=2)
