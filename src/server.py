"""
CSC 423 - PeerWire Multi-User TCP Chat Server
=============================================
This server handles multiple concurrent client connections using multi-threading
and TCP socket programming.

Transport-Layer Concepts Demonstrated:
---------------------------------------
1. socket.socket(AF_INET, SOCK_STREAM): Creates an IPv4 TCP socket (Layer 4).
2. setsockopt(SO_REUSEADDR, 1): Allows immediate reuse of local address after restart
   (bypasses the TIME_WAIT socket state).
3. bind() & listen(): Binds server to an IP and well-known listening port.
4. accept(): Completes TCP 3-way handshake (SYN, SYN-ACK, ACK) and returns a new
   connected socket dedicated to the client, along with the client's ephemeral port.
5. Multi-threading: Dedicated thread per client socket to prevent I/O blocking.
6. Graceful teardown: Detects TCP FIN (recv returns empty bytes) or connection reset.
"""

import sys
import socket
import threading
import logging
from datetime import datetime
from typing import Dict, Tuple, Optional

# Import the shared framing protocol
from protocol import (
    recv_message,
    send_message,
    MSG_REGISTER,
    MSG_REGISTER_ACK,
    MSG_REGISTER_FAIL,
    MSG_BROADCAST,
    MSG_DIRECT,
    MSG_ROOM_JOIN,
    MSG_ROOM_LEAVE,
    MSG_USER_LIST,
    MSG_SYSTEM,
    MSG_DISCONNECT,
    MSG_PING,
    MSG_PONG,
)

# Configure logging with timestamps and transport-layer details
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (Port %(threadName)s) %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("PeerWireServer")


class ClientSession:
    """Represents a connected client and its TCP socket state."""
    def __init__(self, sock: socket.socket, addr: Tuple[str, int], username: str):
        self.sock = sock
        self.addr = addr  # (ip, ephemeral_port)
        self.username = username
        self.room = "#general"
        self.connected_at = datetime.now()


class PeerWireServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 5000):
        self.host = host
        self.port = port
        self.server_sock: Optional[socket.socket] = None
        self.is_running = False
        
        # Registry of active clients: username -> ClientSession
        self.clients: Dict[str, ClientSession] = {}
        # Thread lock to protect client registry from concurrent modifications
        self.lock = threading.Lock()

    def start(self):
        """Initializes and binds the TCP listening socket."""
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # SO_REUSEADDR prevents "Address already in use" errors during rapid restarts
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_sock.bind((self.host, self.port))
            self.server_sock.listen(50)  # Backlog queue for pending connections
            self.is_running = True
            
            logger.info("=" * 60)
            logger.info(f" PeerWire TCP Server listening on {self.host}:{self.port}")
            logger.info(" Transport Layer: TCP (SOCK_STREAM) | Protocol: Length-Prefixed JSON")
            logger.info("=" * 60)
            
            self._accept_loop()
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
        finally:
            self.shutdown()

    def _accept_loop(self):
        """Continuously accepts new incoming TCP connections."""
        while self.is_running:
            try:
                # accept() blocks until a client completes the TCP 3-way handshake
                client_sock, client_addr = self.server_sock.accept()
                
                # client_addr is (client_ip, client_ephemeral_port)
                ip, port = client_addr
                logger.info(f"[HANDSHAKE COMPLETE] Incoming connection from {ip}:{port}")
                
                # Spawn a dedicated worker thread for this client connection
                thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_sock, client_addr),
                    name=str(port),
                    daemon=True,
                )
                thread.start()
            except OSError:
                # Occurs when server socket is closed during shutdown
                break

    def _handle_client(self, client_sock: socket.socket, client_addr: Tuple[str, int]):
        """Manages the lifecycle of a single client's TCP socket."""
        username = None
        try:
            # Step 1: Handshake Registration
            username = self._authenticate_client(client_sock, client_addr)
            if not username:
                client_sock.close()
                return

            # Step 2: Message Processing Loop
            while self.is_running:
                message = recv_message(client_sock)
                if message is None or message.get("type") == MSG_DISCONNECT:
                    logger.info(f"[DISCONNECT] Client '{username}' sent disconnect/closed socket.")
                    break
                
                self._dispatch_message(username, message)

        except (ConnectionResetError, ConnectionAbortedError):
            logger.warning(f"[RST RECEIVED] Client '{username}' connection abruptly aborted.")
        except Exception as e:
            logger.error(f"Error handling client '{username}': {e}")
        finally:
            # Step 3: Cleanup on disconnect
            if username:
                self._remove_client(username)
            try:
                client_sock.close()
            except OSError:
                pass

    def _authenticate_client(self, sock: socket.socket, addr: Tuple[str, int]) -> Optional[str]:
        """Validates and registers the client's requested username."""
        reg_msg = recv_message(sock)
        if not reg_msg or reg_msg.get("type") != MSG_REGISTER:
            send_message(sock, {"type": MSG_REGISTER_FAIL, "reason": "First message must be REGISTER"})
            return None
            
        requested_name = reg_msg.get("username", "").strip()
        if not requested_name or len(requested_name) > 20:
            send_message(sock, {"type": MSG_REGISTER_FAIL, "reason": "Invalid username length (1-20 chars)"})
            return None

        with self.lock:
            if requested_name in self.clients:
                send_message(sock, {"type": MSG_REGISTER_FAIL, "reason": "Username already taken"})
                return None
            
            # Register user
            session = ClientSession(sock, addr, requested_name)
            self.clients[requested_name] = session

        # Confirm registration success
        send_message(sock, {
            "type": MSG_REGISTER_ACK,
            "username": requested_name,
            "room": "#general",
            "info": f"Connected to PeerWire Server on {self.host}:{self.port}",
        })
        
        logger.info(f"[REGISTERED] User '{requested_name}' mapped to port {addr[1]}")
        
        # Broadcast arrival to room and push updated user list
        self._broadcast_system(f"-> {requested_name} joined #general", room="#general")
        self._push_user_list()
        return requested_name

    def _dispatch_message(self, sender: str, msg: dict):
        """Routes application-level message types."""
        msg_type = msg.get("type")
        
        if msg_type == MSG_BROADCAST:
            # Public message to current room
            room = msg.get("room", "#general")
            content = msg.get("content", "")
            self._broadcast_chat(sender, room, content)
            
        elif msg_type == MSG_DIRECT:
            # One-to-one private message
            target = msg.get("target")
            content = msg.get("content", "")
            self._send_direct_message(sender, target, content)
            
        elif msg_type == MSG_ROOM_JOIN:
            new_room = msg.get("room", "#general")
            self._change_room(sender, new_room)
            
        elif msg_type == MSG_USER_LIST:
            self._send_user_list(sender)
            
        elif msg_type == MSG_PING:
            with self.lock:
                if sender in self.clients:
                    send_message(self.clients[sender].sock, {"type": MSG_PONG})
                    
        elif msg_type == MSG_DISCONNECT:
            # Graceful application-level disconnect announcement
            return

    def _broadcast_chat(self, sender: str, room: str, content: str):
        """Sends a chat message to all clients in the same room."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        payload = {
            "type": MSG_BROADCAST,
            "sender": sender,
            "room": room,
            "content": content,
            "timestamp": timestamp,
        }
        with self.lock:
            for user, session in list(self.clients.items()):
                if session.room == room:
                    send_message(session.sock, payload)
        logger.info(f"[{room}] {sender}: {content[:50]}")

    def _send_direct_message(self, sender: str, target: str, content: str):
        """Sends a 1-to-1 private direct message to a specific user."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        with self.lock:
            target_session = self.clients.get(target)
            sender_session = self.clients.get(sender)
            
            if not target_session:
                if sender_session:
                    send_message(sender_session.sock, {
                        "type": MSG_SYSTEM,
                        "content": f"User '{target}' is not online.",
                    })
                return
            
            # Message delivered to recipient
            send_message(target_session.sock, {
                "type": MSG_DIRECT,
                "sender": sender,
                "target": target,
                "content": content,
                "timestamp": timestamp,
            })
            
            # Echo confirmation back to sender
            if sender_session:
                send_message(sender_session.sock, {
                    "type": MSG_DIRECT,
                    "sender": sender,
                    "target": target,
                    "content": content,
                    "timestamp": timestamp,
                    "is_echo": True,
                })
        logger.info(f"[DM] {sender} -> {target}: {content[:40]}")

    def _change_room(self, username: str, new_room: str):
        """Moves client from one channel to another."""
        with self.lock:
            session = self.clients.get(username)
            if not session:
                return
            old_room = session.room
            session.room = new_room
            
        self._broadcast_system(f"<- {username} left {old_room}", room=old_room)
        self._broadcast_system(f"-> {username} joined {new_room}", room=new_room)
        self._push_user_list()

    def _broadcast_system(self, content: str, room: Optional[str] = None):
        """Broadcasts a system notification."""
        payload = {"type": MSG_SYSTEM, "content": content, "room": room}
        with self.lock:
            for session in self.clients.values():
                if room is None or session.room == room:
                    send_message(session.sock, payload)

    def _push_user_list(self):
        """Pushes updated active users list to all connected clients."""
        with self.lock:
            user_list = [
                {"username": s.username, "room": s.room, "port": s.addr[1]}
                for s in self.clients.values()
            ]
        payload = {"type": MSG_USER_LIST, "users": user_list}
        with self.lock:
            for session in self.clients.values():
                send_message(session.sock, payload)

    def _send_user_list(self, username: str):
        """Sends active users list to a single user upon request."""
        with self.lock:
            session = self.clients.get(username)
            if session:
                user_list = [
                    {"username": s.username, "room": s.room, "port": s.addr[1]}
                    for s in self.clients.values()
                ]
                send_message(session.sock, {"type": MSG_USER_LIST, "users": user_list})

    def _remove_client(self, username: str):
        """Safely removes a disconnected client and notifies others."""
        with self.lock:
            session = self.clients.pop(username, None)
            
        if session:
            logger.info(f"[DISCONNECTED] User '{username}' removed from registry.")
            self._broadcast_system(f"<- {username} has disconnected.", room=session.room)
            self._push_user_list()

    def shutdown(self):
        """Gracefully terminates server and closes all active sockets."""
        self.is_running = False
        logger.info("Shutting down PeerWire server...")
        with self.lock:
            for session in self.clients.values():
                try:
                    send_message(session.sock, {
                        "type": MSG_SYSTEM,
                        "content": "Server is shutting down.",
                    })
                    session.sock.close()
                except OSError:
                    pass
            self.clients.clear()
            
        if self.server_sock:
            try:
                self.server_sock.close()
            except OSError:
                pass
        logger.info("PeerWire server stopped cleanly.")


if __name__ == "__main__":
    port = 5000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Usage: python {sys.argv[0]} [port]")
            sys.exit(1)
            
    server = PeerWireServer(host="0.0.0.0", port=port)
    try:
        server.start()
    except KeyboardInterrupt:
        server.shutdown()
