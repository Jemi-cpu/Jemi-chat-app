"""
Scripted client for Experiment 3 (connection termination).

  --mode quit   send DISCONNECT then close()          -> FIN/ACK exchange
  --mode crash  SO_LINGER=0 then close()              -> single RST
  --mode hang   stay connected until killed (kill -9) -> OS closes socket, FIN

Example: python tools/lifecycle_client.py --port 5000 --user exp3_quit --mode quit
"""

import argparse
import os
import socket
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from protocol import send_message, recv_message, abort_connection  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--user", required=True)
    ap.add_argument("--mode", choices=["quit", "crash", "hang"], required=True)
    a = ap.parse_args()

    s = socket.create_connection((a.host, a.port))
    print(f"local {s.getsockname()} -> server {s.getpeername()}", flush=True)
    send_message(s, {"type": "REGISTER", "username": a.user})
    print("server:", recv_message(s), flush=True)
    send_message(s, {"type": "BROADCAST", "content": f"{a.user} test message"})
    time.sleep(0.5)

    if a.mode == "quit":
        send_message(s, {"type": "DISCONNECT"})
        s.close()
        print("closed normally (FIN)")
    elif a.mode == "crash":
        abort_connection(s)
        print("aborted (RST)")
    else:
        print(f"hanging, pid {os.getpid()}; kill me with: kill -9 {os.getpid()}", flush=True)
        while True:
            time.sleep(60)


if __name__ == "__main__":
    main()
