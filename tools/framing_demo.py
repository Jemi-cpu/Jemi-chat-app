"""
PeerWire framing demonstration
==============================
Shows that the server rebuilds messages correctly when TCP delivers them
COMBINED (several frames in one recv) or SPLIT (one frame over several recvs).

Start the server with debug logging so every recv() is logged:
    Windows PowerShell:  $env:LOG_LEVEL="DEBUG"; python src/server.py 5000
    Linux/macOS:         LOG_LEVEL=DEBUG python src/server.py 5000
Then run:
    python tools/framing_demo.py --host 127.0.0.1 --port 5000

TCP_NODELAY disables Nagle's algorithm so each send() leaves immediately, and
the pauses between the parts of the split frame make the server see them in
separate reads.
"""

import argparse
import os
import socket
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from protocol import encode_frame, recv_message, HEADER_STRUCT  # noqa: E402


def drain(sock, wait=0.6):
    sock.settimeout(wait)
    out = []
    try:
        while True:
            m = recv_message(sock)
            if m is None:
                break
            out.append(m)
    except (socket.timeout, TimeoutError):
        pass
    sock.settimeout(None)
    return out


def show(title, msgs):
    print(f"  server replied ({title}):")
    for m in msgs:
        print(f"    {m}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--user", default="framing_demo")
    a = ap.parse_args()

    s = socket.create_connection((a.host, a.port))
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    print(f"Connected {s.getsockname()} -> {s.getpeername()}")

    # 1. COMBINED: REGISTER + PING + USER_LIST in ONE send() call
    combined = (encode_frame({"type": "REGISTER", "username": a.user})
                + encode_frame({"type": "PING", "id": 1})
                + encode_frame({"type": "USER_LIST"}))
    print(f"\n[1] Sending 3 frames in a single send() ({len(combined)} bytes)")
    s.sendall(combined)
    show("expect REGISTER_ACK, PONG, USER_LIST", drain(s))

    # 2. SPLIT: one BROADCAST frame sent in 3 pieces, 0.5 s apart
    frame = encode_frame({"type": "BROADCAST", "content": "This message was split into three TCP writes"})
    cuts = [2, 20, len(frame)]  # first piece is only half of the 4-byte header
    print(f"\n[2] Sending one {len(frame)}-byte frame as 3 writes: "
          f"{cuts[0]} + {cuts[1]-cuts[0]} + {cuts[2]-cuts[1]} bytes")
    prev = 0
    for c in cuts:
        s.sendall(frame[prev:c])
        prev = c
        time.sleep(0.5)
    show("expect the BROADCAST echoed back once, complete", drain(s))

    # 3. MALFORMED: a correctly framed payload that is not JSON
    bad = b"this is not json"
    print("\n[3] Sending a correctly framed but malformed payload")
    s.sendall(HEADER_STRUCT.pack(len(bad)) + bad)
    show("expect ERROR, connection still open", drain(s))
    s.sendall(encode_frame({"type": "PING", "id": 2}))
    show("expect PONG: the connection survived", drain(s))

    s.sendall(encode_frame({"type": "DISCONNECT"}))
    s.close()
    print("\nDone. Check the server log for lines like "
          "'read N bytes -> K complete frame(s), B byte(s) buffered'.")


if __name__ == "__main__":
    main()
