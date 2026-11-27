# PeerWire: Multi-User TCP Chat Application

**CSC 423: Data Communication and Networking, Veritas University Abuja**
**Student:** Jemimah Omojo Attah · **Lecturer:** Mr. Thomas Baidoo

PeerWire is a real-time chat application built directly on TCP sockets. One server accepts many clients on
port 5000. Users pick a username, chat in rooms (`#general`, `#study-group`, `#announcements`) and send private
messages. Messages are JSON objects framed with a 4-byte length prefix (see [docs/protocol.md](docs/protocol.md)).

Only the Python 3.8+ standard library is needed (`socket`, `threading`, `json`, `struct`, `tkinter`).

## Layout

| Path | What it is |
|---|---|
| `src/server.py` | Multi-threaded TCP chat server (one thread per client) |
| `src/protocol.py` | Length-prefix framing, `FrameDecoder`, validation rules, message types |
| `src/gui_client.py` | Tkinter desktop client |
| `src/client.py` | Terminal client (`/msg /join /users /ping /quit /crash`) |
| `tests/` | 17 automated tests over real TCP sockets |
| `tools/framing_demo.py` | Shows split / combined / malformed frames live |
| `tools/tcp_udp_compare.py` | Separate TCP vs UDP comparison (numbered messages, loss, order, RTT) |
| `tools/session_evidence.py` | Records 3 real clients, crash, reconnect, port change (evidence) |
| `tools/lifecycle_client.py` | Scripted normal close / RST abort / killed process (Experiment 3) |
| `experiments/run_experiments.sh` | Runs TCP experiments 1–4 and the comparison on Linux with tcpdump + netem |
| `experiments/results/` | Raw CSV results, logs and packet captures |
| `deploy/` | Cloud VM setup script (systemd), Dockerfile |
| `docs/` | Report, protocol, test log, diagrams, deployment and demo guides |

## Run locally

```bash
python src/server.py 5000                      # or set PEERWIRE_PORT; see .env.example
python src/gui_client.py                       # window 2: host 127.0.0.1, port 5000, user Alice
python src/gui_client.py                       # window 3: user Bob
python src/client.py --host 127.0.0.1 --port 5000 --user Carol   # terminal client
```

To reach the server from another device on the same network, use the server machine's LAN IP and allow
TCP 5000 through its firewall.

Server log: console and `logs/server.log`. Set `LOG_LEVEL=DEBUG` to log every `recv()` and how many frames it held.

Change the port live (for the demonstration): stop the server, run `python src/server.py 5050`, connect clients to 5050.

## Test

```bash
python -m unittest discover -s tests -v
```

## Framing demonstration

```powershell
$env:LOG_LEVEL="DEBUG"; python src/server.py 5000      # Windows PowerShell
python tools/framing_demo.py --port 5000
```

## TCP vs UDP comparison

```bash
python tools/tcp_udp_compare.py server --host 127.0.0.1 --port 6000
python tools/tcp_udp_compare.py client --proto udp --count 100 --label baseline
python tools/tcp_udp_compare.py client --proto tcp --count 100 --label baseline
```

Results: `experiments/results/<label>_<proto>.csv` and `experiments/results/summary.csv`.

## TCP experiments (Linux)

Run on a Linux machine you own (it changes the loopback interface with `tc netem`):

```bash
sudo apt-get install -y tcpdump iproute2
bash experiments/run_experiments.sh
```

## Cloud deployment

Deployment target is a Microsoft Azure Ubuntu VM. Steps are in [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md).
Public address and evidence: **PENDING**.

## Deliverables

| # | Deliverable | Location |
|---|---|---|
| 1 | Source code + README | this repository |
| 2 | Technical report | `docs/PeerWire_Technical_Report.docx` |
| 3 | Application and cloud architecture diagrams | `docs/architecture_diagram.png`; cloud diagram PENDING |
| 4 | Screenshots of two users on the deployed system | PENDING (Azure) |
| 5 | Live demonstration | `docs/DEMONSTRATION_GUIDE.md` |
| 6 | Packet captures for 4 TCP experiments | `experiments/results/*.pcap`: PENDING (Linux run) |
| 7 | TCP/UDP comparison table + commands | `experiments/results/summary.csv`, report section 5.10 |
| 8 | Test log | `docs/test-log.md` |

No secrets are stored in this repository. `.env` is git-ignored.
