# PeerWire Cloud Deployment Guide (AWS, Azure, GCP)

This guide provides step-by-step instructions for deploying the **PeerWire TCP Chat Server** to any major cloud provider (AWS, Azure, or Google Cloud Platform) using free-tier virtual machines.

---

## Option 1: Deploy on AWS (Amazon Web Services EC2) - Recommended

### Step 1: Launch an EC2 Instance
1. Log in to the [AWS Management Console](https://aws.amazon.com/console/).
2. Navigate to **EC2** $\rightarrow$ Click **Launch Instance**.
3. **Name:** `PeerWire-Server`
4. **OS:** `Ubuntu Server 22.04 LTS (HVM), SSD Volume Type` (Free tier eligible).
5. **Instance Type:** `t2.micro` (or `t3.micro`).
6. **Key Pair:** Create a new key pair (e.g., `peerwire-key.pem`) and download it.

### Step 2: Configure Inbound Security Group (Firewall)
Under **Network Settings**, configure the following **Inbound Rules**:

| Type | Protocol | Port Range | Source | Description |
| :--- | :--- | :--- | :--- | :--- |
| **SSH** | TCP | `22` | `My IP` (or `0.0.0.0/0`) | Remote terminal access |
| **Custom TCP** | TCP | `5000` | `0.0.0.0/0` (Anywhere IPv4) | PeerWire Chat Socket Port |

> [!IMPORTANT]
> Opening Port 5000 in your Cloud Security Group is **required** so remote clients can establish TCP connections through the cloud provider's network interface.

### Step 3: Connect and Deploy
1. Open PowerShell or Terminal on your laptop:
   ```bash
   ssh -i "peerwire-key.pem" ubuntu@<YOUR-EC2-PUBLIC-IP>
   ```
2. Clone or copy your PeerWire code to the VM:
   ```bash
   git clone <YOUR-GITHUB-REPO-URL> csc423-chat
   cd csc423-chat
   ```
3. Run the automated deployment script:
   ```bash
   chmod +x deploy/setup_cloud_vm.sh
   ./deploy/setup_cloud_vm.sh
   ```
4. Verify the server is running:
   ```bash
   sudo systemctl status peerwire.service
   ```

---

## Option 2: Deploy on Microsoft Azure (Virtual Machine)

1. Go to the [Azure Portal](https://portal.azure.com/) $\rightarrow$ **Create a resource** $\rightarrow$ **Virtual Machine**.
2. **Basics:**
   * Image: `Ubuntu Server 22.04 LTS - x64 Gen2`
   * Size: `Standard_B1s` (Free tier eligible).
3. **Networking $\rightarrow$ Inbound Port Rules:**
   * Allow `SSH (22)`.
4. Once deployed, go to the VM $\rightarrow$ **Networking** $\rightarrow$ **Add inbound port rule**:
   * **Destination port ranges:** `5000`
   * **Protocol:** `TCP`
   * **Action:** `Allow`
   * **Name:** `Allow-PeerWire-TCP-5000`
5. Connect via SSH and run `./deploy/setup_cloud_vm.sh`.

---

## Option 3: Deploy on Google Cloud Platform (GCP Compute Engine)

1. Open [GCP Console](https://console.cloud.google.com/) $\rightarrow$ **Compute Engine** $\rightarrow$ **VM Instances** $\rightarrow$ **Create Instance**.
2. **Machine configuration:** `e2-micro` (Free tier).
3. **Boot disk:** Ubuntu 22.04 LTS.
4. **VPC Network Firewall:**
   * Go to **VPC Network** $\rightarrow$ **Firewall** $\rightarrow$ **Create Firewall Rule**.
   * Name: `allow-peerwire-5000`
   * Target tags: `peerwire-server`
   * Protocols and ports: Specified protocols $\rightarrow$ `tcp: 5000`
5. Connect via GCP in-browser SSH and execute `./deploy/setup_cloud_vm.sh`.

---

## Connecting Clients to Your Cloud Server

Once your cloud instance is live, any client in the world can connect using your **Cloud Public IPv4 Address**:

### Method A: Using the Graphical App (GUI)
1. Run `python src/gui_client.py` on your laptop.
2. Enter:
   * **Server Host:** `<YOUR-CLOUD-PUBLIC-IP>`
   * **Port:** `5000`
   * **Username:** `Alice`
3. Click **Connect to PeerWire**.

### Method B: Using the Terminal Client (CLI)
```bash
python src/client.py
# Server Host: <YOUR-CLOUD-PUBLIC-IP>
# Server Port: 5000
# Username: Bob
```

---

## Checklist for Capturing Deployment Evidence (Deliverable 5)

To submit 100% complete evidence for Mr. Thomas:
1. [ ] **Public Connection Details:** Note your Server Public IP and Port.
2. [ ] **Cloud Dashboard Screenshot:** Take a screenshot of the AWS/Azure/GCP management console showing the active VM and the inbound security rule for Port 5000.
3. [ ] **Simultaneous Chat Screenshot:** Open two client windows on separate laptops or side-by-side on your desktop connected to `<YOUR-CLOUD-PUBLIC-IP>`, showing:
   * Client 1 (e.g., Alice) typing a message.
   * Client 2 (e.g., Bob) receiving that message in real-time.
   * The top header badge clearly showing the Cloud Public IP and local ephemeral ports.
