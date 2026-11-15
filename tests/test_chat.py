"""
CSC 423 - PeerWire Automated Integration Test Suite
===================================================
Tests core transport-layer socket features:
1. TCP 3-way handshake and connection establishment.
2. User registration and conflict rejection.
3. Group chat broadcast within channels.
4. One-to-one private direct messaging (DM isolation).
5. Presence detection and graceful disconnection (TCP FIN / DISCONNECT).
"""

import sys
import os
import time
import socket
import threading
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
from server import PeerWireServer


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
        time.sleep(0.3)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
