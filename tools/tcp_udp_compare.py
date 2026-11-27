"""
PeerWire TCP vs UDP comparison tool (separate from the chat application)
=======================================================================
server mode: runs a TCP echo server AND a UDP echo server on the same port number.
client mode: sends N numbered messages over one protocol, records which come back,
             in what order, and the round-trip time (RTT) of each.

Each message payload is "<seq>|<padding>". TCP messages use the same 4-byte
length prefix as PeerWire; a UDP datagram is one message by itself.

Examples
  python tools/tcp_udp_compare.py server --host 0.0.0.0 --port 6000
  python tools/tcp_udp_compare.py client --proto udp --port 6000 --count 100 --label baseline
  python tools/tcp_udp_compare.py client --proto tcp --port 6000 --count 100 --label baseline
  python tools/tcp_udp_compare.py client --proto tcp --count 5000 --size 1000 --interval 0 --label burst

Per-message results go to experiments/results/<label>_<proto>.csv and one summary
row per run is appended to experiments/results/summary.csv.
"""

import argparse
import csv
import os
import socket
import statistics
import struct
import sys
import threading
import time
from datetime import datetime

HDR = struct.Struct(">I")
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "experiments", "results")


# ------------------------------------------------------------------ server
def tcp_echo(conn):
    with conn:
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        while True:
            try:
                data = conn.recv(65536)
            except OSError:
                return
            if not data:
                return
            conn.sendall(data)  # echo raw bytes; framing is preserved end to end


def run_server(host, port):
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
    udp.bind((host, port))

    def udp_loop():
        while True:
            data, addr = udp.recvfrom(65535)
            udp.sendto(data, addr)

    threading.Thread(target=udp_loop, daemon=True).start()
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp.bind((host, port))
    tcp.listen(10)
    print(f"Echo servers on {host}:{port} (TCP and UDP). Ctrl+C to stop.")
    try:
        while True:
            c, _ = tcp.accept()
            threading.Thread(target=tcp_echo, args=(c,), daemon=True).start()
    except KeyboardInterrupt:
        pass


# ------------------------------------------------------------------ client
def make_payload(seq, size):
    head = f"{seq}|".encode()
    return head + b"x" * max(0, size - len(head))


def run_client(a):
    sent = {}            # seq -> send time
    arrivals = []        # (seq, recv time) in arrival order
    lock = threading.Lock()
    done = threading.Event()

    if a.proto == "udp":
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
        sock.connect((a.host, a.port))
        sock.settimeout(0.2)

        def reader():
            while not done.is_set():
                try:
                    data = sock.recv(65535)
                except (socket.timeout, TimeoutError):
                    continue
                except OSError:
                    continue  # e.g. ICMP port unreachable on Windows
                t = time.perf_counter()
                with lock:
                    arrivals.append((int(data.split(b"|", 1)[0]), t))

        def send(p):
            sock.send(p)
    else:
        sock = socket.create_connection((a.host, a.port))
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(0.2)

        def reader():
            buf = bytearray()
            while not done.is_set():
                try:
                    data = sock.recv(65536)
                except (socket.timeout, TimeoutError):
                    continue
                if not data:
                    return
                t = time.perf_counter()
                buf += data
                while len(buf) >= 4:
                    (n,) = HDR.unpack_from(buf)
                    if len(buf) < 4 + n:
                        break
                    body = bytes(buf[4:4 + n])
                    del buf[:4 + n]
                    with lock:
                        arrivals.append((int(body.split(b"|", 1)[0]), t))

        def send(p):
            sock.sendall(HDR.pack(len(p)) + p)

    th = threading.Thread(target=reader, daemon=True)
    th.start()
    t_start = time.perf_counter()
    for seq in range(1, a.count + 1):
        sent[seq] = time.perf_counter()
        send(make_payload(seq, a.size))
        if a.interval > 0:
            time.sleep(a.interval / 1000)
    # wait for stragglers: stop when everything arrived or nothing new for --wait seconds
    last_n, last_change = -1, time.perf_counter()
    while time.perf_counter() - last_change < a.wait:
        with lock:
            n = len(arrivals)
        if n >= a.count:
            break
        if n != last_n:
            last_n, last_change = n, time.perf_counter()
        time.sleep(0.05)
    done.set()
    th.join(1)
    sock.close()

    # -------------------------------------------------------------- analysis
    seen, rows, rtts = set(), [], []
    dups = ooo = 0
    max_seq = 0
    for idx, (seq, t) in enumerate(arrivals):
        dup = seq in seen
        late = seq < max_seq
        dups += dup
        ooo += (late and not dup)
        seen.add(seq)
        max_seq = max(max_seq, seq)
        rtt = (t - sent[seq]) * 1000
        if not dup:
            rtts.append(rtt)
        rows.append([seq, idx + 1, round(rtt, 3), int(dup), int(late)])
    lost = sorted(set(sent) - seen)
    duration = (max(t for _, t in arrivals) - t_start) if arrivals else 0
    rtts_sorted = sorted(rtts)

    def pct(p):
        return rtts_sorted[min(len(rtts_sorted) - 1, int(p * len(rtts_sorted)))] if rtts_sorted else 0

    summary = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "label": a.label, "proto": a.proto.upper(), "host": a.host,
        "count": a.count, "size_bytes": a.size, "interval_ms": a.interval,
        "received": len(seen), "lost": len(lost), "out_of_order": ooo, "duplicates": dups,
        "rtt_avg_ms": round(statistics.mean(rtts), 3) if rtts else "",
        "rtt_p95_ms": round(pct(0.95), 3) if rtts else "",
        "rtt_max_ms": round(max(rtts), 3) if rtts else "",
        "msgs_per_s": round(len(seen) / duration, 1) if duration else "",
        "throughput_kbit_s": round(len(seen) * a.size * 8 / duration / 1000, 1) if duration else "",
        "notes": a.notes,
    }
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, f"{a.label}_{a.proto}.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["seq", "arrival_index", "rtt_ms", "duplicate", "out_of_order"])
        w.writerows(rows)
        for s in lost:
            w.writerow([s, "", "", "", ""])
    sp = os.path.join(RESULTS, "summary.csv")
    new = not os.path.exists(sp)
    with open(sp, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary))
        if new:
            w.writeheader()
        w.writerow(summary)

    print(f"{a.proto.upper()} {a.label}: received {len(seen)}/{a.count}, lost {len(lost)}, "
          f"out-of-order {ooo}, duplicates {dups}")
    if rtts:
        print(f"  RTT avg {summary['rtt_avg_ms']} ms, p95 {summary['rtt_p95_ms']} ms, "
              f"max {summary['rtt_max_ms']} ms; {summary['msgs_per_s']} msg/s, "
              f"{summary['throughput_kbit_s']} kbit/s")
    if lost:
        print(f"  missing sequence numbers: {lost[:30]}{' ...' if len(lost) > 30 else ''}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    s = sub.add_parser("server")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=6000)
    c = sub.add_parser("client")
    c.add_argument("--proto", choices=["tcp", "udp"], required=True)
    c.add_argument("--host", default="127.0.0.1")
    c.add_argument("--port", type=int, default=6000)
    c.add_argument("--count", type=int, default=100)
    c.add_argument("--size", type=int, default=64, help="payload bytes per message")
    c.add_argument("--interval", type=float, default=10, help="ms between sends (0 = as fast as possible)")
    c.add_argument("--wait", type=float, default=3, help="seconds to wait for late replies")
    c.add_argument("--label", default="run")
    c.add_argument("--notes", default="")
    a = ap.parse_args()
    if a.mode == "server":
        run_server(a.host, a.port)
    else:
        run_client(a)


if __name__ == "__main__":
    sys.exit(main())
