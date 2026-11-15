# PeerWire — Real-Time Multi-User TCP Chat Application
**CSC 423 Assignment: Socket Programming & Transport Layer Engineering**  
**Student Name:** Asher  
**Course Instructor:** Mr. Thomas  

---

## Deliverables Compliance Matrix

This repository fulfills every deliverable specified in the CSC 423 assignment guidelines:

| Deliverable | Description | Location in Repository |
| :--- | :--- | :--- |
| **1. Source Code** | Complete, runnable multi-user TCP socket client & server source code. | [`src/server.py`](src/server.py), [`src/gui_client.py`](src/gui_client.py), [`src/client.py`](src/client.py), [`src/protocol.py`](src/protocol.py) |
| **2. README** | Instructions for installing, running, testing, and deploying. | This document ([`README.md`](README.md)) |
| **3. Architecture Diagram** | Detailed visual diagrams showing clients, server, ports, sockets, and cloud topology. | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| **4. Transport-Layer Report** | Comprehensive academic report answering all 7 required TCP vs. UDP questions. | [`docs/TRANSPORT_LAYER_REPORT.md`](docs/TRANSPORT_LAYER_REPORT.md) |
| **5. Deployment Evidence** | Public cloud IP setup, verification guide, and screenshot checklist. | [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md) |
| **6. Demonstration** | Live test suite and multi-user chat walkthrough instructions. | [`tests/test_chat.py`](tests/test_chat.py) & [Demonstration Guide](#live-demonstration-guide) |
| **7. Reflection** | Analysis of technical challenges faced and transport-layer lessons learned. | [`docs/REFLECTION.md`](docs/REFLECTION.md) |

---

## Application Overview: PeerWire

**PeerWire** is a multi-user real-time chat application designed from the ground up using **raw TCP socket programming** (OSI Layer 4). It avoids high-level third-party web frameworks, demonstrating transport-layer principles directly through standard Python sockets (`socket.socket(AF_INET, SOCK_STREAM)`).

### Core Features:
- **TCP Stream Framing:** Uses a 4-byte big-endian length prefix header (`struct.pack('>I', N)`) to solve TCP byte-stream fragmentation and concatenation.
- **Concurrent Connections:** Multi-threaded server architecture servicing each client on an independent worker thread.
- **Real-Time Group Chat:** Room-based public channels (`#general`, `#study-group`, `#announcements`).
- **One-to-One Private Messaging:** Direct messages (`/msg <username> <message>`) with cryptographic isolation.
- **Live User Directory:** Active presence tracking with dynamic broadcast updates.
- **Graceful Teardown:** Handles TCP `FIN` 4-way handshakes and recovers from dirty disconnects (`RST`).
- **Interactive UI/UX with RGB Color Mixer:** 
  - Platform Title: **PeerWire**
  - Default Accent: **Safe Crisp Blue (`#2563EB`)**
  - **Pullable RGB Sliders:** Interactive Red, Green, and Blue sliders (0–255) with a live color preview swatch, enabling full custom theme personalization.
  - **Transport-Layer Monitor:** Live header displaying server IP, destination port (`5000`), and the client's local **ephemeral port**.

---

## Project Structure

```
csc423-tcp-chat/
│
├── src/                          # Application Source Code
│   ├── protocol.py               # Framing (4-byte length prefix) & JSON serialization
│   ├── server.py                 # Multi-threaded TCP Chat Server
│   ├── gui_client.py             # Desktop Graphical Client (Tkinter + RGB Sliders)
│   └── client.py                 # Command-line Terminal Client
│
├── tests/
│   └── test_chat.py              # Automated integration tests (Unittest)
│
├── deploy/                       # Cloud Deployment Configurations
│   ├── Dockerfile                # Docker container definition
│   ├── docker-compose.yml        # Multi-container orchestration
│   ├── setup_cloud_vm.sh         # 1-Click VM deployment script (AWS/Azure/GCP)
│   └── peerwire.service          # systemd background daemon service
│
├── docs/                         # Assignment Documentation
│   ├── TRANSPORT_LAYER_REPORT.md # 7-question in-depth transport-layer analysis
│   ├── ARCHITECTURE.md           # System and cloud architecture diagrams
│   ├── DEPLOYMENT_GUIDE.md       # Step-by-step cloud deployment guide
│   └── REFLECTION.md             # Engineering challenges and lessons learned
│
└── README.md                     # Master project documentation
```

---

## Installation & Running Locally

### Prerequisites
* Python 3.8 or newer (tested on Python 3.12).
* **Zero external libraries needed!** PeerWire uses Python standard libraries (`socket`, `threading`, `json`, `struct`, `tkinter`).

### Step 1: Start the PeerWire Server
Open a terminal and run:
```bash
cd csc423-tcp-chat
python src/server.py 5000
```
*The server will start listening on `0.0.0.0:5000`.*

### Step 2: Start Client 1 (Graphical Interface)
Open a second terminal:
```bash
python src/gui_client.py
```
* Enter `127.0.0.1`, Port `5000`, Username `Alice`.
* Click **Connect to PeerWire**.

### Step 3: Start Client 2 (Simultaneous Chat)
Open a third terminal:
```bash
python src/gui_client.py
```
* Enter `127.0.0.1`, Port `5000`, Username `Bob`.
* Click **Connect to PeerWire**.
* **You now have two live clients communicating over TCP sockets!**

*(Alternatively, run `python src/client.py` if you prefer the terminal CLI interface).*

---

## Running Automated Tests

PeerWire includes a complete automated test suite verifying socket registration, duplicate username rejection, broadcast messaging, private direct messaging isolation, and graceful disconnection:

```bash
python tests/test_chat.py
```

**Expected Output:**
```
test_01_registration_and_duplicate_rejection ... ok
test_02_broadcast_messaging_between_peers ... ok
test_03_private_direct_message_isolation ... ok
test_04_graceful_disconnect_handling ... ok

----------------------------------------------------------------------
Ran 4 tests in 2.3s

OK
```

---

## Cloud Deployment (AWS / Azure / GCP)

PeerWire is cloud-ready and can be deployed to an **AWS EC2**, **Azure Virtual Machine**, or **GCP Compute Engine** instance in under 3 minutes:

1. Launch an Ubuntu 22.04 VM (Free Tier).
2. Configure Cloud Firewall / Security Group:
   * Allow **Inbound TCP Port 5000** from `0.0.0.0/0`.
   * Allow **Inbound TCP Port 22 (SSH)**.
3. SSH into the cloud VM and run:
   ```bash
   git clone <YOUR-REPO-URL> csc423-chat
   cd csc423-chat
   chmod +x deploy/setup_cloud_vm.sh
   ./deploy/setup_cloud_vm.sh
   ```
4. On any computer, launch `python src/gui_client.py` and point to `<YOUR-CLOUD-PUBLIC-IP>:5000`.

*See [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md) for full instructions and screenshot evidence guidelines.*

---

## Live Demonstration Guide

To record your demonstration video or take screenshots for Mr. Thomas:
1. Launch `python src/server.py` in the background.
2. Launch two GUI instances side-by-side (`Alice` and `Bob`).
3. Click **Customize RGB Theme** on one window and drag the Red, Green, and Blue sliders to demonstrate interactive theme customization.
4. Send a public broadcast message in `#general`.
5. Double-click Bob's name in Alice's user list and send a private direct message (`/msg Bob hello`).
6. Point out the top status bar showing the local ephemeral port and active TCP socket state.
7. Close Bob's window to show Alice receiving the graceful system disconnect alert.

---

## Security Notice
- No hardcoded secrets, API keys, or credentials are used or committed.
- Input validation protects against username collisions and oversized frames (capped at 10 MB).
