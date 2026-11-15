#!/usr/bin/env bash
# ==============================================================================
# PeerWire Cloud VM Automated Setup Script (AWS EC2 / Azure / GCP)
# Supports Ubuntu 22.04 LTS / 24.04 LTS & Debian 11/12
# ==============================================================================

set -e

echo "=== [1/4] Updating package manager & installing Python ==="
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip git ufw

echo "=== [2/4] Setting up firewall rules for TCP Port 5000 ==="
# Allow SSH so you don't lock yourself out
sudo ufw allow 22/tcp || true
# Allow PeerWire TCP socket port
sudo ufw allow 5000/tcp || true
sudo ufw --force enable || true

echo "=== [3/4] Creating systemd service for PeerWire ==="
SERVICE_FILE="/etc/systemd/system/peerwire.service"
CURRENT_DIR=$(pwd)

sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=PeerWire Real-Time TCP Chat Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$CURRENT_DIR
ExecStart=/usr/bin/python3 $CURRENT_DIR/src/server.py 5000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

echo "=== [4/4] Starting and enabling PeerWire service ==="
sudo systemctl daemon-reload
sudo systemctl enable peerwire.service
sudo systemctl restart peerwire.service

echo ""
echo "=========================================================="
echo " PeerWire Server is now LIVE in the Cloud!"
echo " Check status with: sudo systemctl status peerwire.service"
echo " View live logs:    sudo journalctl -u peerwire.service -f"
echo "=========================================================="
