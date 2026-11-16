# PeerWire — Real-Time TCP Chat Application
**CSC 423 Assignment: Socket Programming & Transport Layer Engineering**  
**Student:** Asher | **Instructor:** Mr. Thomas  

This README provides operational instructions for **installing**, **running**, **testing**, and **deploying** the PeerWire application.

---

## 1. Installation Instructions

### Prerequisites
* **Python 3.8 or higher** (Python 3.12 recommended).
* **Operating System:** Windows, macOS, or Linux.
* **Dependencies:** None! PeerWire is built entirely with Python standard libraries (`socket`, `threading`, `json`, `struct`, `tkinter`).

### Setup Steps
1. Navigate to the project directory:
   ```bash
   cd "C:\Users\asher\Documents\chat app"
   ```
2. Verify Python is available:
   ```bash
   python --version
   ```

---

## 2. Running the Application

PeerWire consists of a central **TCP Server** and two client options: a **Graphical Desktop App (GUI)** and a **Terminal Client (CLI)**.

### Step 2.1: Start the Server
Open a terminal and start the server on TCP port `5000`:
```bash
python src/server.py 5000
```
*The server binds to `0.0.0.0:5000` and waits for incoming client connections.*

### Step 2.2: Launch Client 1 (GUI)
Open a new terminal window:
```bash
python src/gui_client.py
```
1. Enter Server Host: `127.0.0.1` (or your cloud server IP).
2. Enter Port: `5000`.
3. Enter Username: `Alice`.
4. Click **Connect to PeerWire**.
5. *(Optional)* Click **"Customize RGB Theme"** to adjust the pullable Red, Green, and Blue sliders to your preferred accent color.

### Step 2.3: Launch Client 2 (Simultaneous Chat)
Open another terminal window:
```bash
python src/gui_client.py
```
1. Enter Server Host: `127.0.0.1`.
2. Enter Port: `5000`.
3. Enter Username: `Bob`.
4. Click **Connect to PeerWire**.

*Alice and Bob can now chat in real-time in `#general`, switch channels, or double-click each other to send private direct messages (`/msg`).*

### Alternative: Running the Terminal (CLI) Client
If running without a graphical display (e.g. over SSH):
```bash
python src/client.py
```

---

## 3. Testing the Application

An automated integration test suite (`tests/test_chat.py`) is provided to verify all core transport-layer requirements without manual intervention:

```bash
python tests/test_chat.py
```

### What the Automated Tests Verify:
1. **TCP Handshake & Registration:** Verifies connection establishment and duplicate username rejection.
2. **Real-Time Broadcast:** Verifies message delivery across peers in `#general`.
3. **Private Direct Messaging:** Verifies that `/msg` delivers only to the target recipient and is isolated from other peers.
4. **Graceful Disconnection:** Verifies socket cleanup and peer presence notifications when a client sends `TCP FIN`.

---

## 4. Deploying the Application to the Cloud

PeerWire can be deployed to any major cloud provider (AWS EC2, Microsoft Azure, or GCP Compute Engine) using a standard Ubuntu 22.04 LTS virtual machine.

### Step 4.1: Cloud VM & Firewall Setup
1. Launch a cloud instance (e.g., AWS EC2 `t2.micro` Free Tier).
2. Open **Inbound Cloud Security Group / Firewall Rules**:
   * **TCP Port 22:** SSH terminal access.
   * **TCP Port 5000:** PeerWire custom socket port (Source: `0.0.0.0/0`).

### Step 4.2: Automated 1-Click Server Setup
1. SSH into your cloud VM:
   ```bash
   ssh -i "your-key.pem" ubuntu@<CLOUD-PUBLIC-IP>
   ```
2. Clone or upload your repository and run the setup script:
   ```bash
   chmod +x deploy/setup_cloud_vm.sh
   ./deploy/setup_cloud_vm.sh
   ```
   *This automatically configures firewall rules, sets up a systemd background daemon (`peerwire.service`), and starts the server.*

3. Verify status:
   ```bash
   sudo systemctl status peerwire.service
   ```

### Step 4.3: Connecting Remote Clients to the Cloud
On your local laptop, run:
```bash
python src/gui_client.py
```
Set **Server Host** to your `<CLOUD-PUBLIC-IP>` and **Port** to `5000`.

---

## Deliverables Index

* **Deliverable 1 (Source code):** `src/` (`server.py`, `gui_client.py`, `client.py`, `protocol.py`).
* **Deliverable 2 (README):** This document (`README.md`).
* **Deliverable 3 (Architecture diagram):** `docs/architecture_diagram.png` and `docs/ARCHITECTURE.md`.
* **Deliverable 4 (Transport-layer report):** `docs/PeerWire_Transport_Layer_Report.docx` and `docs/TRANSPORT_LAYER_REPORT.md`.
* **Deliverable 5 (Deployment evidence):** `docs/DEPLOYMENT_EVIDENCE.md` and screenshot evidence.
* **Deliverable 6 (Demonstration):** `docs/DEMONSTRATION_GUIDE.md` (video recording script & cue card).
* **Deliverable 7 (Reflection):** `docs/PeerWire_Reflection.docx` and `docs/REFLECTION.md`.
