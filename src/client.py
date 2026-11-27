"""
CSC 423 - PeerWire Terminal (CLI) Client
========================================
A lightweight command-line client for PeerWire using standard Python sockets and threads.

Features:
- Dual-threaded design:
  * Thread 1 (Background): Reads incoming TCP frames via recv_message() and prints to stdout.
  * Thread 2 (Main): Captures user input from stdin and sends frames via send_message().
- Supports commands: /msg, /join, /users, /help, /quit
"""

import argparse
import sys
import os
import socket
import threading
from datetime import datetime

# Ensure src/ is in python path
sys.path.insert(0, os.path.dirname(__file__))

from protocol import (
    abort_connection,
    recv_message,
    send_message,
    MSG_REGISTER,
    MSG_REGISTER_ACK,
    MSG_REGISTER_FAIL,
    MSG_BROADCAST,
    MSG_DIRECT,
    MSG_ROOM_JOIN,
    MSG_USER_LIST,
    MSG_SYSTEM,
    MSG_DISCONNECT,
    MSG_ERROR,
    MSG_PONG,
)


def receiver_loop(sock: socket.socket, stop_event: threading.Event, my_username: str):
    """Continuously receives messages from server and prints them."""
    while not stop_event.is_set():
        try:
            msg = recv_message(sock)
            if msg is None:
                if not stop_event.is_set():  # the server closed it, not us
                    print("\n[!] Connection closed by server (TCP FIN). Press Enter to exit.")
                stop_event.set()
                break

            m_type = msg.get("type")
            ts = msg.get("timestamp", datetime.now().strftime("%H:%M:%S"))

            if m_type == MSG_BROADCAST:
                sender = msg.get("sender")
                content = msg.get("content")
                room = msg.get("room", "#general")
                if sender != my_username:
                    print(f"\n[{ts}] [{room}] {sender}: {content}\n> ", end="", flush=True)

            elif m_type == MSG_DIRECT:
                sender = msg.get("sender")
                target = msg.get("target")
                content = msg.get("content")
                is_echo = msg.get("is_echo", False)
                if is_echo:
                    print(f"\n[{ts}] [DM to {target}]: {content}\n> ", end="", flush=True)
                else:
                    print(f"\n[{ts}] [DM from {sender}]: {content}\n> ", end="", flush=True)

            elif m_type == MSG_SYSTEM:
                content = msg.get("content")
                print(f"\n[*] SYSTEM: {content}\n> ", end="", flush=True)

            elif m_type == MSG_ERROR:
                print(f"\n[!] SERVER ERROR: {msg.get('message')}\n> ", end="", flush=True)

            elif m_type == MSG_PONG:
                print("\n[*] PONG received\n> ", end="", flush=True)

            elif m_type == MSG_USER_LIST:
                users = msg.get("users", [])
                user_strs = [f"{u['username']} (Port {u['port']})" for u in users]
                print(f"\n[Online Users ({len(users)})]: {', '.join(user_strs)}\n> ", end="", flush=True)

        except Exception:
            stop_event.set()
            break


def main():
    parser = argparse.ArgumentParser(description="PeerWire terminal client")
    parser.add_argument("--host", help="server IP or hostname")
    parser.add_argument("--port", type=int, help="server TCP port (default 5000)")
    parser.add_argument("--user", help="username")
    args = parser.parse_args()

    print("=" * 55)
    print("         PeerWire - Terminal TCP Chat Client        ")
    print("=" * 55)

    host = args.host or input("Server Host [127.0.0.1]: ").strip() or "127.0.0.1"
    port_input = str(args.port) if args.port else (input("Server Port [5000]: ").strip() or "5000")
    username = args.user or input("Enter your username: ").strip()

    if not username:
        print("Username cannot be empty.")
        return

    try:
        port = int(port_input)
    except ValueError:
        print("Invalid port number.")
        return

    # Create TCP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        print(f"Connecting to {host}:{port} via TCP (SYN)...")
        sock.connect((host, port))
        lip, lport = sock.getsockname()[:2]
        rip, rport = sock.getpeername()[:2]
        print("[+] TCP three-way handshake complete.")
        print(f"    4-tuple: local {lip}:{lport} (ephemeral)  <->  server {rip}:{rport}")
    except Exception as e:
        print(f"[-] Could not connect to server: {e}")
        return

    # Register username
    send_message(sock, {"type": MSG_REGISTER, "username": username})
    resp = recv_message(sock)

    if not resp or resp.get("type") != MSG_REGISTER_ACK:
        reason = resp.get("reason", "Registration rejected.") if resp else "Connection closed."
        print(f"[-] Registration failed: {reason}")
        sock.close()
        return

    print(f"[+] Welcome to PeerWire, {username}!")
    print("Type /help for commands or start typing messages.\n")

    stop_event = threading.Event()
    recv_thread = threading.Thread(
        target=receiver_loop,
        args=(sock, stop_event, username),
        daemon=True,
    )
    recv_thread.start()

    current_room = "#general"
    aborted = False

    try:
        while not stop_event.is_set():
            user_input = input("> ").strip()
            if stop_event.is_set():
                break
            if not user_input:
                continue

            if user_input.startswith("/"):
                parts = user_input.split(" ", 2)
                cmd = parts[0].lower()

                if cmd in ["/quit", "/exit"]:
                    break  # finally-block sends DISCONNECT and closes (FIN)

                elif cmd == "/crash":
                    # Abort the connection: SO_LINGER with timeout 0 makes close()
                    # discard unsent data and send RST instead of FIN.
                    stop_event.set()
                    abort_connection(sock)
                    aborted = True
                    print("Connection aborted with RST (/crash).")
                    break

                elif cmd == "/ping":
                    send_message(sock, {"type": "PING"})

                elif cmd in ["/msg", "/dm"]:
                    if len(parts) < 3:
                        print("[!] Usage: /msg <username> <message>")
                        continue
                    send_message(sock, {
                        "type": MSG_DIRECT,
                        "target": parts[1],
                        "content": parts[2],
                    })

                elif cmd == "/join":
                    if len(parts) < 2:
                        print("[!] Usage: /join <room>")
                        continue
                    room = parts[1] if parts[1].startswith("#") else "#" + parts[1]
                    current_room = room
                    send_message(sock, {"type": MSG_ROOM_JOIN, "room": room})

                elif cmd == "/users":
                    send_message(sock, {"type": MSG_USER_LIST})

                elif cmd == "/help":
                    print("\nCommands:")
                    print("  /msg <user> <message> : Send private message")
                    print("  /join <#room>         : Switch channel")
                    print("  /users                : List online users")
                    print("  /ping                 : Send PING, expect PONG")
                    print("  /quit                 : Disconnect cleanly (FIN)")
                    print("  /crash                : Abort the connection (RST), for Experiment 3\n")
                else:
                    print(f"[!] Unknown command '{cmd}'. Type /help for options.")
            else:
                send_message(sock, {
                    "type": MSG_BROADCAST,
                    "room": current_room,
                    "content": user_input,
                })
    except (KeyboardInterrupt, EOFError):
        print("\nExiting...")
    finally:
        if not aborted:
            stop_event.set()  # tell the receiver thread this close is ours
            send_message(sock, {"type": MSG_DISCONNECT})
            try:
                sock.close()
            except OSError:
                pass
            print("Disconnected cleanly from PeerWire (FIN sent).")


if __name__ == "__main__":
    main()
