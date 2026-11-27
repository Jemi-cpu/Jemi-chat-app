#!/usr/bin/env bash
# =============================================================================
# PeerWire TCP experiments 1-4 and the TCP/UDP comparison (Linux only).
#
# Runs everything over the LOOPBACK interface (lo) so no other network or user
# is affected. Needs: python3, tcpdump, iproute2 (tc, ss), sudo.
#   sudo apt-get install -y tcpdump iproute2
#   bash experiments/run_experiments.sh
# Outputs: experiments/results/*.pcap, *.csv, *.log, *.txt
# Open the .pcap files in Wireshark for the annotated screenshots.
# Only throwaway test usernames are used; no passwords or real chat content.
# =============================================================================
set -u
cd "$(dirname "$0")/.."
R=experiments/results
mkdir -p "$R"
PORT=5000
CMP_PORT=6000
PY=python3

cleanup() {
  sudo tc qdisc del dev lo root 2>/dev/null || true
  [ -n "${SERVER_PID:-}" ] && kill "$SERVER_PID" 2>/dev/null
  [ -n "${ECHO_PID:-}" ] && kill "$ECHO_PID" 2>/dev/null
  sudo pkill -f "tcpdump -i lo" 2>/dev/null || true
}
trap cleanup EXIT

capture_start() {  # $1 = pcap file, $2 = filter
  sudo tcpdump -i lo -s 0 -U -w "$1" $2 >/dev/null 2>&1 &
  CAP_PID=$!
  sleep 1
}
capture_stop() { sleep 1; sudo kill "$CAP_PID" 2>/dev/null; wait "$CAP_PID" 2>/dev/null; }

echo "=== Starting PeerWire server (DEBUG log -> $R/server_experiments.log)"
LOG_LEVEL=DEBUG LOG_FILE="$R/server_experiments.log" PEERWIRE_HOST=127.0.0.1 \
  $PY src/server.py $PORT >/dev/null 2>&1 &
SERVER_PID=$!
$PY tools/tcp_udp_compare.py server --host 127.0.0.1 --port $CMP_PORT >/dev/null 2>&1 &
ECHO_PID=$!
sleep 1

# ---------------------------------------------------------------- Experiment 1
echo "=== Experiment 1: connection establishment (SYN, SYN-ACK, ACK)"
capture_start "$R/exp1_handshake.pcap" "tcp port $PORT"
$PY tools/lifecycle_client.py --port $PORT --user exp1_user --mode quit | tee "$R/exp1_client.txt"
capture_stop
tcpdump -nn -S -r "$R/exp1_handshake.pcap" 2>/dev/null | head -12 | tee "$R/exp1_summary.txt"

# ---------------------------------------------------------------- Experiment 2
echo "=== Experiment 2: 10% packet loss, TCP retransmission"
sudo tc qdisc add dev lo root netem loss 10%
capture_start "$R/exp2_tcp_loss10.pcap" "tcp port $CMP_PORT"
$PY tools/tcp_udp_compare.py client --proto tcp --port $CMP_PORT --count 100 --wait 10 \
  --label loss10 --notes "Linux lo, netem loss 10%"
capture_stop
$PY tools/tcp_udp_compare.py client --proto udp --port $CMP_PORT --count 100 \
  --label loss10 --notes "Linux lo, netem loss 10%"
sudo tc qdisc del dev lo root
echo "TCP retransmissions seen in capture:" | tee "$R/exp2_summary.txt"
(command -v tshark >/dev/null && tshark -r "$R/exp2_tcp_loss10.pcap" -Y tcp.analysis.retransmission 2>/dev/null | wc -l \
  || echo "install tshark or open the pcap in Wireshark, filter: tcp.analysis.retransmission") | tee -a "$R/exp2_summary.txt"

# ---------------------------------------------------------------- Experiment 3
echo "=== Experiment 3: normal close (FIN) vs abort (RST) vs killed process"
capture_start "$R/exp3_fin_normal.pcap" "tcp port $PORT"
$PY tools/lifecycle_client.py --port $PORT --user exp3_quit --mode quit
capture_stop
capture_start "$R/exp3_rst_abort.pcap" "tcp port $PORT"
$PY tools/lifecycle_client.py --port $PORT --user exp3_crash --mode crash
capture_stop
capture_start "$R/exp3_killed.pcap" "tcp port $PORT"
$PY tools/lifecycle_client.py --port $PORT --user exp3_kill --mode hang &
HANG_PID=$!
sleep 2; kill -9 $HANG_PID
capture_stop
for f in exp3_fin_normal exp3_rst_abort exp3_killed; do
  echo "--- $f"; tcpdump -nn -r "$R/$f.pcap" 2>/dev/null | grep -E "Flags \[(F|R)" ;
done | tee "$R/exp3_summary.txt"
grep -E "exp3_|DISCONNECT|CLEANUP" "$R/server_experiments.log" | tail -12 | tee -a "$R/exp3_summary.txt"

# ---------------------------------------------------------------- Experiment 4
echo "=== Experiment 4: RTT and throughput, two conditions"
capture_start "$R/exp4_baseline.pcap" "tcp port $CMP_PORT"
$PY tools/tcp_udp_compare.py client --proto tcp --port $CMP_PORT --count 100 --label exp4_rtt_baseline --notes "Linux lo, no impairment"
$PY tools/tcp_udp_compare.py client --proto tcp --port $CMP_PORT --count 5000 --size 1000 --interval 0 \
  --label exp4_tput_baseline --notes "Linux lo, no impairment, 5000 x 1000 B"
capture_stop
sudo tc qdisc add dev lo root netem delay 50ms rate 10mbit
capture_start "$R/exp4_delay50_rate10.pcap" "tcp port $CMP_PORT"
$PY tools/tcp_udp_compare.py client --proto tcp --port $CMP_PORT --count 100 --wait 10 \
  --label exp4_rtt_delay50 --notes "netem delay 50ms rate 10mbit (100 ms RTT)"
$PY tools/tcp_udp_compare.py client --proto tcp --port $CMP_PORT --count 5000 --size 1000 --interval 0 --wait 20 \
  --label exp4_tput_delay50 --notes "netem delay 50ms rate 10mbit, 5000 x 1000 B" &
TP=$!
sleep 3; ss -tin "( dport = :$CMP_PORT or sport = :$CMP_PORT )" > "$R/exp4_ss_during_transfer.txt"
wait $TP
capture_stop
sudo tc qdisc del dev lo root

# ------------------------------------------------- TCP/UDP comparison matrix
echo "=== TCP vs UDP: baseline, loss 10%, delay+jitter+loss 5%"
for proto in udp tcp; do
  $PY tools/tcp_udp_compare.py client --proto $proto --port $CMP_PORT --count 100 --label baseline --notes "Linux lo, no impairment"
done
sudo tc qdisc add dev lo root netem delay 20ms 15ms loss 5%
for proto in udp tcp; do
  $PY tools/tcp_udp_compare.py client --proto $proto --port $CMP_PORT --count 100 --wait 10 \
    --label jitter_loss5 --notes "netem delay 20ms 15ms loss 5%"
done
sudo tc qdisc del dev lo root

echo
echo "=== Done. Summary:"
column -s, -t < "$R/summary.csv" | cut -c1-200
ls -la "$R"
