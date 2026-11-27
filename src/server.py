"""
CSC 423 - PeerWire Multi-User TCP Chat Server
=============================================
One listening TCP socket, one worker thread per connected client.

Transport-layer behaviour demonstrated:
1. socket(AF_INET, SOCK_STREAM)  -> an IPv4 TCP socket.
2. bind((host, port)), listen()  -> a passive socket on a well-known port (5000).
3. accept()                      -> returns a NEW connected socket after the
   kernel has completed the three-way handshake (SYN, SYN-ACK, ACK). Every
   connection is identified by the 4-tuple (client IP, client ephemeral port,
   server IP, 5000), which is how one port serves many clients.
4. Explicit length-prefixed framing on top of the byte stream (protocol.py).
5. Connection teardown: recv() returning b"" means FIN (orderly close);
   ConnectionResetError means RST (abort). Keepalive detects silent loss.

Configuration (environment variables, see .env.example):
  PEERWIRE_HOST  (default 0.0.0.0)   PEERWIRE_PORT (default 5000)
  LOG_LEVEL      (default INFO; DEBUG logs every recv() and its frame count)
  LOG_FILE       (default logs/server.log)
A port given on the command line overrides PEERWIRE_PORT.
"""

import logging
import logging.handlers
import os
import socket
import struct
import sys
import threading
from datetime import datetime
from typing import Dict, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from protocol import (  # noqa: E402
    FrameDecoder,
    FrameTooLarge,
    ProtocolError,
    parse_payload,
    send_message,
    MAX_MESSAGE_CHARS,
    USERNAME_RE,
    ROOM_RE,
    MSG_REGISTER,
    MSG_REGISTER_ACK,
    MSG_REGISTER_FAIL,
    MSG_BROADCAST,
    MSG_DIRECT,
    MSG_ROOM_JOIN,
    MSG_USER_LIST,
    MSG_SYSTEM,
    MSG_ERROR,
    MSG_DISCONNECT,
    MSG_PING,
    MSG_PONG,
)

SEND_TIMEOUT_SECONDS = 5      # a client that stops reading is dropped after this
KEEPALIVE_IDLE_SECONDS = 60   # first keepalive probe after 60 s of silence
KEEPALIVE_INTERVAL_SECONDS = 10
KEEPALIVE_PROBES = 3

logger = logging.getLogger("PeerWireServer")


def configure_logging() -> None:
    """Console + rotating file log. Safe to call more than once."""
    if logger.handlers:
        return
    level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)
    log_file = os.environ.get("LOG_FILE", os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "logs", "server.log"))
    try:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(log_file, maxBytes=1_000_000,
                                                  backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError as e:
        logger.warning(f"File logging disabled: {e}")


def enable_keepalive(sock: socket.socket) -> None:
    """Ask the OS to probe idle connections so silent client loss is detected."""
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    if hasattr(socket, "SIO_KEEPALIVE_VALS"):  # Windows
        sock.ioctl(socket.SIO_KEEPALIVE_VALS,
                   (1, KEEPALIVE_IDLE_SECONDS * 1000, KEEPALIVE_INTERVAL_SECONDS * 1000))
    else:  # Linux
        for opt, val in (("TCP_KEEPIDLE", KEEPALIVE_IDLE_SECONDS),
                         ("TCP_KEEPINTVL", KEEPALIVE_INTERVAL_SECONDS),
                         ("TCP_KEEPCNT", KEEPALIVE_PROBES)):
            if hasattr(socket, opt):
                sock.setsockopt(socket.IPPROTO_TCP, getattr(socket, opt), val)


def set_send_timeout(sock: socket.socket, seconds: int) -> None:
    """Limit how long sendall() may block, without affecting recv()."""
    try:
        if sys.platform == "win32":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, seconds * 1000)
        else:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, struct.pack("ll", seconds, 0))
    except OSError:
        pass


class ClientSession:
    """A registered client and its connected TCP socket."""

    def __init__(self, sock: socket.socket, addr: Tuple[str, int], username: str):
        self.sock = sock
        self.addr = addr  # (client IP, client ephemeral port)
        self.username = username
        self.room = "#general"
        self.connected_at = datetime.now()


class PeerWireServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 5000):
        configure_logging()
        self.host = host
        self.port = port
        self.server_sock: Optional[socket.socket] = None
        self.is_running = False
        self.ready = threading.Event()
        self.clients: Dict[str, ClientSession] = {}  # username -> session
        self.lock = threading.RLock()

    # ------------------------------------------------------------------ start
    def start(self):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # SO_REUSEADDR lets the server restart while old connections sit in TIME_WAIT
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_sock.bind((self.host, self.port))
            self.server_sock.listen(50)
            self.is_running = True
            self.ready.set()
            logger.info(f"PeerWire TCP server listening on {self.host}:{self.port} "
                        f"(SOCK_STREAM, 4-byte length-prefixed JSON)")
            self._accept_loop()
        except OSError as e:
            logger.error(f"Failed to start server on {self.host}:{self.port}: {e}")
            self.ready.set()
        finally:
            self.shutdown()

    def _accept_loop(self):
        while self.is_running:
            try:
                client_sock, client_addr = self.server_sock.accept()
            except OSError:
                break  # listening socket closed during shutdown
            ip, port = client_addr
            try:
                sip, sport = client_sock.getsockname()[:2]
            except OSError:
                sip, sport = self.host, self.port
            logger.info(f"[CONNECT] TCP connection from {ip}:{port} "
                        f"(handshake complete, server side {sip}:{sport})")
            threading.Thread(target=self._handle_client, args=(client_sock, client_addr),
                             name=f"{ip}:{port}", daemon=True).start()

    # ------------------------------------------------------- per-connection
    def _handle_client(self, sock: socket.socket, addr: Tuple[str, int]):
        username: Optional[str] = None
        reason = "unknown"
        decoder = FrameDecoder()
        try:
            enable_keepalive(sock)
            set_send_timeout(sock, SEND_TIMEOUT_SECONDS)
            while self.is_running:
                data = sock.recv(4096)
                if not data:
                    reason = "client closed the connection (FIN received)"
                    break
                frames = decoder.feed(data)
                logger.debug(f"read {len(data)} bytes -> {len(frames)} complete frame(s), "
                             f"{decoder.buffered} byte(s) buffered")
                for raw in frames:
                    try:
                        msg = parse_payload(raw)
                    except ProtocolError as e:
                        logger.warning(f"[MALFORMED] from {addr[0]}:{addr[1]}: {e}")
                        send_message(sock, {"type": MSG_ERROR, "message": str(e)})
                        continue
                    if username is None:
                        username = self._handle_unregistered(sock, addr, msg)
                        continue
                    if msg["type"] == MSG_DISCONNECT:
                        reason = "client sent DISCONNECT"
                        return
                    self._dispatch_message(username, msg)
        except FrameTooLarge as e:
            reason = f"oversized frame ({e}); connection closed"
            logger.warning(f"[MALFORMED] {addr[0]}:{addr[1]}: {e}")
            send_message(sock, {"type": MSG_ERROR, "message": "frame too large"})
        except (ConnectionResetError, ConnectionAbortedError):
            reason = "connection reset by peer (RST received)"
        except OSError as e:
            reason = f"socket error: {e}"
        except Exception as e:  # never let one client take the server down
            reason = f"unexpected error: {e!r}"
            logger.exception(f"Unexpected error for {addr[0]}:{addr[1]}")
        finally:
            logger.info(f"[DISCONNECT] {username or 'unregistered'} @ {addr[0]}:{addr[1]}: {reason}")
            if username:
                self._remove_client(username)
            try:
                sock.close()
            except OSError:
                pass

    def _handle_unregistered(self, sock, addr, msg) -> Optional[str]:
        """Before registration only REGISTER, PING and DISCONNECT are accepted."""
        mtype = msg["type"]
        if mtype == MSG_PING:
            send_message(sock, {"type": MSG_PONG})
            return None
        if mtype == MSG_DISCONNECT:
            sock.shutdown(socket.SHUT_RDWR)
            return None
        if mtype != MSG_REGISTER:
            send_message(sock, {"type": MSG_ERROR, "message": "register first"})
            return None

        name = msg.get("username")
        if not isinstance(name, str) or not USERNAME_RE.match(name.strip()):
            send_message(sock, {"type": MSG_REGISTER_FAIL,
                                "reason": "Invalid username: 3-20 letters, digits or underscore"})
            logger.info(f"[REGISTER FAIL] {addr[0]}:{addr[1]} invalid username {str(name)[:30]!r}")
            return None
        name = name.strip()
        with self.lock:
            if name.lower() in (u.lower() for u in self.clients):
                send_message(sock, {"type": MSG_REGISTER_FAIL, "reason": "Username already taken"})
                logger.info(f"[REGISTER FAIL] {addr[0]}:{addr[1]} username {name!r} taken")
                return None
            self.clients[name] = ClientSession(sock, addr, name)

        send_message(sock, {
            "type": MSG_REGISTER_ACK,
            "username": name,
            "room": "#general",
            "info": f"Connected to PeerWire server port {self.port}",
            "client_addr": f"{addr[0]}:{addr[1]}",
        })
        logger.info(f"[REGISTERED] '{name}' on {addr[0]}:{addr[1]}")
        self._broadcast_system(f"-> {name} joined #general", room="#general")
        self._push_user_list()
        return name

    # -------------------------------------------------------------- routing
    def _error(self, username: str, text: str):
        with self.lock:
            s = self.clients.get(username)
        if s:
            self._send(s, {"type": MSG_ERROR, "message": text})

    def _valid_content(self, username: str, msg: dict) -> Optional[str]:
        content = msg.get("content")
        if not isinstance(content, str):
            self._error(username, "'content' must be a string")
            return None
        content = content.strip()
        if not content:
            self._error(username, "message is empty")
            return None
        if len(content) > MAX_MESSAGE_CHARS:
            self._error(username, f"message longer than {MAX_MESSAGE_CHARS} characters")
            return None
        return content

    def _dispatch_message(self, sender: str, msg: dict):
        mtype = msg["type"]
        if mtype == MSG_BROADCAST:
            content = self._valid_content(sender, msg)
            if content is None:
                return
            with self.lock:
                room = self.clients[sender].room if sender in self.clients else "#general"
            self._broadcast_chat(sender, room, content)
        elif mtype == MSG_DIRECT:
            target = msg.get("target")
            if not isinstance(target, str) or not target:
                self._error(sender, "'target' must be a username")
                return
            content = self._valid_content(sender, msg)
            if content is not None:
                self._send_direct_message(sender, target, content)
        elif mtype == MSG_ROOM_JOIN:
            room = msg.get("room")
            if not isinstance(room, str) or not ROOM_RE.match(room):
                self._error(sender, "invalid room name (e.g. #general)")
                return
            self._change_room(sender, room)
        elif mtype == MSG_USER_LIST:
            self._send_user_list(sender)
        elif mtype == MSG_PING:
            with self.lock:
                s = self.clients.get(sender)
            if s:
                self._send(s, {"type": MSG_PONG, "id": msg.get("id")})
        else:
            logger.warning(f"[MALFORMED] '{sender}' sent unknown type {str(mtype)[:30]!r}")
            self._error(sender, f"unknown message type {str(mtype)[:30]!r}")

    def _send(self, session: ClientSession, payload: dict) -> None:
        """Send to one client; a client whose send fails or times out is dropped."""
        if not send_message(session.sock, payload):
            logger.warning(f"[SEND FAILED] '{session.username}' not accepting data; dropping")
            try:
                session.sock.shutdown(socket.SHUT_RDWR)  # wakes its recv() thread
            except OSError:
                pass

    def _broadcast_chat(self, sender: str, room: str, content: str):
        payload = {"type": MSG_BROADCAST, "sender": sender, "room": room,
                   "content": content, "timestamp": datetime.now().strftime("%H:%M:%S")}
        with self.lock:
            targets = [s for s in self.clients.values() if s.room == room]
        for s in targets:
            self._send(s, payload)
        logger.info(f"[{room}] message from '{sender}' ({len(content)} chars) "
                    f"to {len(targets)} client(s)")

    def _send_direct_message(self, sender: str, target: str, content: str):
        ts = datetime.now().strftime("%H:%M:%S")
        with self.lock:
            target_s = self.clients.get(target)
            sender_s = self.clients.get(sender)
        if not target_s:
            if sender_s:
                self._send(sender_s, {"type": MSG_SYSTEM, "content": f"User '{target}' is not online."})
            return
        payload = {"type": MSG_DIRECT, "sender": sender, "target": target,
                   "content": content, "timestamp": ts}
        self._send(target_s, payload)
        if sender_s and sender_s is not target_s:
            self._send(sender_s, dict(payload, is_echo=True))
        logger.info(f"[DM] '{sender}' -> '{target}' ({len(content)} chars)")

    def _change_room(self, username: str, new_room: str):
        with self.lock:
            s = self.clients.get(username)
            if not s:
                return
            old_room, s.room = s.room, new_room
        self._broadcast_system(f"<- {username} left {old_room}", room=old_room)
        self._broadcast_system(f"-> {username} joined {new_room}", room=new_room)
        self._push_user_list()

    def _broadcast_system(self, content: str, room: Optional[str] = None):
        payload = {"type": MSG_SYSTEM, "content": content, "room": room}
        with self.lock:
            targets = [s for s in self.clients.values() if room is None or s.room == room]
        for s in targets:
            self._send(s, payload)

    def _user_list(self):
        with self.lock:
            return [{"username": s.username, "room": s.room, "port": s.addr[1]}
                    for s in self.clients.values()]

    def _push_user_list(self):
        payload = {"type": MSG_USER_LIST, "users": self._user_list()}
        with self.lock:
            targets = list(self.clients.values())
        for s in targets:
            self._send(s, payload)

    def _send_user_list(self, username: str):
        with self.lock:
            s = self.clients.get(username)
        if s:
            self._send(s, {"type": MSG_USER_LIST, "users": self._user_list()})

    def _remove_client(self, username: str):
        with self.lock:
            s = self.clients.pop(username, None)
        if s:
            logger.info(f"[CLEANUP] '{username}' removed from registry "
                        f"({len(self.clients)} client(s) remain)")
            self._broadcast_system(f"<- {username} has disconnected.", room=s.room)
            self._push_user_list()

    # ------------------------------------------------------------- shutdown
    def shutdown(self):
        if not self.is_running and self.server_sock is None:
            return
        self.is_running = False
        logger.info("Shutting down PeerWire server...")
        with self.lock:
            sessions = list(self.clients.values())
            self.clients.clear()
        for s in sessions:
            send_message(s.sock, {"type": MSG_SYSTEM, "content": "Server is shutting down."})
            try:
                s.sock.close()
            except OSError:
                pass
        if self.server_sock:
            try:
                self.server_sock.close()
            except OSError:
                pass
            self.server_sock = None
        logger.info("PeerWire server stopped.")


def main():
    host = os.environ.get("PEERWIRE_HOST", "0.0.0.0")
    port_text = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PEERWIRE_PORT", "5000")
    try:
        port = int(port_text)
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        print(f"Invalid port {port_text!r}. Usage: python {sys.argv[0]} [port]")
        sys.exit(1)
    server = PeerWireServer(host=host, port=port)
    try:
        server.start()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
