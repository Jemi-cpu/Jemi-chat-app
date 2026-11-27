"""
Records real local evidence for the test log (no admin rights needed):

  1. Three simultaneous terminal clients (Alice, Bob, Carol) on one server.
     netstat is captured while all three are connected (one 4-tuple each).
     Carol aborts with /crash (RST); Alice and Bob keep chatting;
     Carol reconnects with the same username and receives messages live.
  2. Live port change: the server is restarted on another port; clients connect
     to the new port and the old port refuses connections.

Each client is the real src/client.py driven through its standard input.
Output: experiments/results/session_*.txt and the server log.

    python tools/session_evidence.py
"""

import os
import socket
import subprocess
import sys
import threading
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "experiments", "results")
PY = sys.executable
PORT, NEW_PORT = 5000, 5050


class Client:
    def __init__(self, name, port):
        self.name = name
        self.lines = []
        self.p = subprocess.Popen(
            [PY, "-u", os.path.join(ROOT, "src", "client.py"),
             "--host", "127.0.0.1", "--port", str(port), "--user", name],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", bufsize=1)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.p.stdout:
            line = line.rstrip("\n").strip()
            while line.startswith(">"):  # strip the client's input prompts
                line = line[1:].strip()
            if line:
                self.lines.append(f"{time.strftime('%H:%M:%S')}  {line}")

    def say(self, text, pause=0.6):
        self.lines.append(f"{time.strftime('%H:%M:%S')}  [typed] {text}")
        try:
            self.p.stdin.write(text + "\n")
            self.p.stdin.flush()
        except OSError:
            pass
        time.sleep(pause)

    def wait(self):
        try:
            self.p.wait(5)
        except subprocess.TimeoutExpired:
            self.p.kill()


def start_server(port, log):
    env = dict(os.environ, LOG_FILE=log, LOG_LEVEL="INFO", PEERWIRE_HOST="0.0.0.0")
    p = subprocess.Popen([PY, os.path.join(ROOT, "src", "server.py"), str(port)], env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), 0.2).close()
            return p
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("server did not start")


def netstat(port):
    out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True).stdout
    return "\n".join(l for l in out.splitlines() if f":{port} " in l)


def main():
    os.makedirs(OUT, exist_ok=True)
    log = os.path.join(OUT, "session_server.log")
    if os.path.exists(log):
        os.remove(log)
    report = [f"PeerWire local session evidence, {time.strftime('%Y-%m-%d %H:%M:%S')}, "
              f"Windows loopback, real src/client.py processes\n"]

    # ------------------------------------------------ part 1: three clients
    server = start_server(PORT, log)
    # (the readiness probe above opens and closes one connection; it appears in the log as unregistered)
    a = Client("Alice", PORT); time.sleep(0.8)
    b = Client("Bob", PORT); time.sleep(0.8)
    c = Client("Carol", PORT); time.sleep(1.0)
    report.append(f"--- netstat while Alice, Bob and Carol are connected (port {PORT}) ---\n{netstat(PORT)}\n")
    a.say("Hello Bob and Carol, this is Alice")
    b.say("Hi Alice, Bob here")
    c.say("Carol here too")
    a.say("/msg Bob this is a private message for Bob only")
    c.say("/crash", pause=1.0)                         # abort with RST
    report.append(f"--- netstat after Carol's /crash ---\n{netstat(PORT)}\n")
    a.say("Bob, can you still see me after Carol crashed?")
    b.say("Yes Alice, still connected")
    carol_first = c
    c = Client("Carol", PORT); time.sleep(1.0)         # reconnect, same username
    b.say("Welcome back Carol")
    c.say("Thanks Bob, I reconnected")
    c.say("/users")
    for x in (a, b, c):
        x.say("/quit", pause=0.3)
    for x in (a, b, c, carol_first):
        x.wait()
    server.terminate()
    server.wait(5)
    time.sleep(0.5)

    # ------------------------------------------------ part 2: port change
    server = start_server(NEW_PORT, log)
    d = Client("Dave", NEW_PORT); time.sleep(0.8)
    d.say("/ping")
    try:
        socket.create_connection(("127.0.0.1", PORT), 6).close()
        old = f"port {PORT}: connection ACCEPTED (unexpected)"
    except OSError as e:
        old = f"port {PORT}: connection refused as expected ({e.__class__.__name__}: {e})"
    report.append(f"--- port change: server restarted on {NEW_PORT} ---\n{netstat(NEW_PORT)}\n{old}\n")
    d.say("/quit", pause=0.3)
    d.wait()
    server.terminate()
    server.wait(5)

    report.append("--- client transcripts ---")
    with open(os.path.join(OUT, "session_evidence.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
        for x, title in ((a, "Alice"), (b, "Bob"), (carol_first, "Carol (first connection, ends with /crash)"),
                         (c, "Carol (reconnected)"), (d, f"Dave (port {NEW_PORT})")):
            f.write(f"\n===== {title} =====\n" + "\n".join(x.lines) + "\n")
    print(open(os.path.join(OUT, "session_evidence.txt"), encoding="utf-8").read())


if __name__ == "__main__":
    main()
