# CSC 423: Transport Layer Analysis & Socket Programming Report
**Course:** CSC 423 – Computer Networks & Data Communications  
**Project:** PeerWire – Real-Time Multi-User TCP Chat System  
**Author:** Asher  
**Date:** Academic Year 2026/2027  

---

## Executive Summary
This report provides a rigorous theoretical and empirical analysis of the Transport Layer (OSI Layer 4) mechanisms underpinning the **PeerWire** real-time multi-user chat platform. The report specifically evaluates the design trade-offs between the Transmission Control Protocol (TCP) and the User Datagram Protocol (UDP), detailing connection lifecycles, socket abstractions, multiplexing via port numbers, and the implications of network anomalies.

---

## 1. Why is TCP Suitable for Chat Applications?

Text-based chat applications are fundamentally classified as **loss-intolerant, ordered data transmission systems**. Human conversation relies on grammatical context, semantic continuity, and precise chronological causality.

TCP is uniquely suited for chat systems due to three primary transport-layer characteristics:

1. **Byte-Stream Reliability (Zero Tolerance for Message Loss):**
   Unlike streaming audio or video where an occasional dropped sample causes an imperceptible artifact, dropping words or characters in a chat message alters or destroys its meaning. For example, losing the word *"not"* in *"I am not coming"* inverses the message completely. TCP guarantees that every byte sent by the application is received or an error is raised.

2. **Strict In-Order Sequence Preservation:**
   Chat responses depend strictly on conversational sequence. If User A asks *"Are you free at 3 PM?"* and User B replies *"No"*, followed by *"Yes at 5 PM"*, out-of-order delivery could render the conversation incoherent. TCP sequence numbers ensure that packets arriving out of order are buffered and sorted by the operating system before being presented to the application.

3. **Congestion and Flow Control:**
   TCP actively monitors network capacity using sliding window algorithms (RFC 5681: Slow Start, Congestion Avoidance, Fast Retransmit, and Fast Recovery). This prevents a client on high-speed fiber from overwhelming a mobile client on 3G, ensuring fair buffer utilization at intermediate routers.

---

## 2. What Guarantees Does TCP Provide?

TCP (RFC 793, RFC 9293) provides five mathematical and operational guarantees at the Transport Layer:

| Guarantee | Mechanism in TCP Header / Kernel | Significance in Chat |
| :--- | :--- | :--- |
| **Guaranteed Delivery** | Positive Acknowledgment with Retransmission (PAR) & Retransmission Timeout (RTO) | Messages never vanish unnoticed; unacknowledged segments are resent. |
| **Ordered Sequencing** | 32-bit Sequence Numbers (`SEQ`) & Acknowledgment Numbers (`ACK`) | Messages are reconstructed in exact transmission order regardless of network path variance. |
| **Data Integrity** | 16-bit Internet Checksum (One's complement sum of header, data, and pseudo-header) | Corrupted packets caused by bit flips or electrical noise are discarded and retransmitted. |
| **Flow Control** | Dynamic 16-bit Receive Window (`WIN`) advertising available buffer space | Prevents the sender from overflowing the receiver's OS socket buffer. |
| **Connection-Oriented State** | Finite State Machine (SYN, ESTABLISHED, FIN_WAIT, TIME_WAIT) | Explicit state agreement ensures both endpoints know when data channels are valid. |

---

## 3. Comprehensive Differences: TCP vs. UDP

The fundamental differences between TCP and UDP reflect the classic trade-off between **reliability** and **latency**:

```
+------------------------------------+------------------------------------+
|                TCP                 |                UDP                 |
|       (Connection-Oriented)        |          (Connectionless)          |
+------------------------------------+------------------------------------+
| * 3-Way Handshake before data flow | * No handshake (fire-and-forget)   |
| * Heavy 20–60 byte header          | * Lightweight 8 byte header        |
| * Explicit ACK for every segment   | * No ACKs or sequence tracking     |
| * Kernel retransmissions on loss   | * Packet dropped = lost forever    |
| * Flow & Congestion Control        | * No rate throttling               |
| * Byte-stream abstraction          | * Discrete datagram preservation   |
+------------------------------------+------------------------------------+
```

### Detailed Parameter Comparison:

| Characteristic | TCP (Transmission Control Protocol) | UDP (User Datagram Protocol) |
| :--- | :--- | :--- |
| **OSI Layer** | Layer 4 (Transport) | Layer 4 (Transport) |
| **RFC Reference** | RFC 793, RFC 9293 | RFC 768 |
| **Connection State** | Stateful (SYN $\rightarrow$ SYN-ACK $\rightarrow$ ACK) | Stateless (No handshake) |
| **Header Overhead** | 20 to 60 bytes (with options) | Exactly 8 bytes |
| **Delivery Guarantee** | Yes (Retransmission via RTO / Fast Retransmit) | None (Best-effort delivery) |
| **Ordering Guarantee** | Yes (Sequence numbers reassembled at receiver) | None (Datagrams can arrive out of order) |
| **Boundary Preservation** | No (Continuous byte stream; requires framing) | Yes (Preserves datagram message boundaries) |
| **Transmission Speed** | Slower (Handshake + ACK latency + congestion window) | Maximum throughput / minimum transport delay |
| **Broadcast / Multicast** | Unicast only (Point-to-point) | Supports Unicast, Multicast, and Broadcast |

---

## 4. Which Chat Features Could Use UDP?

While core text messaging requires the reliability of TCP, several supplementary features within modern collaborative chat platforms (such as Discord, WhatsApp, or Slack) benefit significantly from UDP:

1. **Real-Time Voice and Video Streaming (WebRTC / RTP over UDP):**
   In voice calls, human ear sensitivity prioritizes temporal immediacy over 100% fidelity. A delayed audio packet (arriving 500ms late due to TCP retransmission) is useless and sounds like stuttering; dropping that 20ms audio frame is imperceptible.

2. **Ephemeral "User is Typing..." Indicators:**
   Typing indicators are high-frequency, transient status updates. If an update packet is lost, a newer typing packet is already being dispatched 200ms later. TCP retransmission overhead is wasteful here.

3. **Presence Pings & Heartbeats:**
   Keep-alive heartbeats periodically broadcast client vitality. A lost ping can be ignored because the next scheduled interval will confirm presence.

4. **Peer Discovery on Local Networks (LAN Broadcast / Multicast):**
   UDP broadcast (e.g., to `255.255.255.255:5000`) allows clients on the same Wi-Fi network to automatically discover the PeerWire server without requiring pre-configured IP addresses.

---

## 5. What Happens When UDP Messages Are Lost or Arrive Out of Order?

Because UDP is completely stateless and lacks sequence numbering and retransmission logic:

### Case A: Packet Loss in UDP
1. **Network Layer:** A router experiencing queue overflow discards the IP datagram carrying the UDP packet.
2. **Transport Layer:** The UDP kernel driver receives nothing and generates no alert, timeout, or retransmission request.
3. **Application Layer:** The receiving chat application has **zero knowledge** that a message was ever dispatched. The sender assumes the message arrived.
4. **Impact on Text Chat:** Entire sentences or conversation turns silently disappear, producing communication breakdown.

### Case B: Out-of-Order Arrival in UDP
1. **Routing Dynamics:** Packet 1 takes a congested path (Router A $\rightarrow$ B $\rightarrow$ D); Packet 2 takes an uncongested path (Router A $\rightarrow$ C $\rightarrow$ D).
2. **Receiver Kernel:** UDP immediately places datagrams into the socket buffer in the exact order they arrive at the network interface card.
3. **Application Layer:** The chat client reads:
   * `[10:00:02] Bob: Yes, definitely!`
   * `[10:00:03] Bob: Did you finish the CSC 423 assignment?`
4. **Impact on Text Chat:** The answers appear before the questions, inverting chronological causality.

---

## 6. How Sockets and Port Numbers Enable Communication

A network communication endpoint is uniquely identified not merely by an IP address, but by a **Transport Layer Socket Tuple**.

### The Socket 5-Tuple Definition:
$$\text{Socket Connection} = \langle \text{Protocol, Source IP, Source Port, Destination IP, Destination Port} \rangle$$

```
Client A (Alice)                        Server (PeerWire)                       Client B (Bob)
IP: 192.168.1.50                        IP: 54.210.10.5                         IP: 192.168.1.75
Ephemeral Port: 52184                   Listening Port: 5000                    Ephemeral Port: 59312
      |                                       |                                       |
      |--- TCP SYN (52184 -> 5000) ---------->|                                       |
      |<-- TCP SYN-ACK (5000 -> 52184) -------|                                       |
      |--- TCP ACK (52184 -> 5000) ---------->|                                       |
      |    [Socket Tuple A Established]       |                                       |
      |                                       |<-- TCP SYN (59312 -> 5000) -----------|
      |                                       |--- TCP SYN-ACK (5000 -> 59312) ------>|
      |                                       |<-- TCP ACK (59312 -> 5000) -----------|
      |                                       |    [Socket Tuple B Established]       |
```

### Demultiplexing in PeerWire:
1. **Server Well-Known Port (`5000`):** Acts as a public rendezvous point. The operating system binds `0.0.0.0:5000` to the server's listening socket.
2. **Client Ephemeral Ports (`52184`, `59312`):** Dynamically allocated by the client OS from the private port range (49152–65535).
3. **Concurrent Handling:** When Client A and Client B both connect to Port 5000, the server OS creates two distinct socket file descriptors:
   * Client A: `(TCP, 192.168.1.50:52184, 54.210.10.5:5000)`
   * Client B: `(TCP, 192.168.1.75:59312, 54.210.10.5:5000)`
This mathematical uniqueness allows the server to run a single listening port while routing messages independently to hundreds of concurrent users without crosstalk.

---

## 7. What Happens When a TCP Client Disconnects?

In network socket programming, client disconnections manifest in two distinct forms: **Graceful Teardown** and **Abrupt Termination**.

### Scenario A: Graceful Disconnection (The 4-Way FIN Handshake)
When the user types `/quit` or clicks window close `(X)`:
1. **Application Action:** The client invokes `sock.close()`.
2. **FIN Packet:** The client OS sends a TCP segment with the `FIN` control flag set.
3. **Server ACK:** The server OS acknowledges with `ACK` and enters the `CLOSE_WAIT` state.
4. **Application Notification:** In PeerWire's `protocol.py`, `recv(n)` immediately returns `b""` (0 bytes / EOF).
5. **Server Teardown:** The server invokes `_remove_client()`, alerts other users via `MSG_SYSTEM`, and calls its own `client_sock.close()`.
6. **Final FIN/ACK:** Server sends `FIN`, client responds with `ACK`, transitioning through `TIME_WAIT` to ensure no delayed segments remain in transit.

```
Client (PeerWire App)                                  Server (PeerWire Host)
      |                                                       |
      |--- FIN (SEQ=1000) ----------------------------------->|  (recv() returns b"")
      |<-- ACK (ACK=1001) -----------------------------------|  [Enters CLOSE_WAIT]
      |                                                       |  (Removes from registry)
      |<-- FIN (SEQ=2000) -----------------------------------|
      |--- ACK (ACK=2001) ----------------------------------->|  [Socket Closed]
      |    [TIME_WAIT: 2*MSL]                                 |
```

### Scenario B: Abrupt Disconnection (Hard Crash / Cable Pull / Power Cut)
If a user's laptop battery dies or network connection is severed:
1. No `FIN` segment can be dispatched.
2. **Half-Open Socket:** The server socket remains open in the `ESTABLISHED` state, unaware the peer is offline.
3. **Detection via Write (`ConnectionResetError`):** When the server attempts to route a broadcast message to the dead client, the intermediate network returns an `ICMP Destination Unreachable` or the restarted client responds with a `RST` (Reset) packet.
4. **Resolution:** The server catches `BrokenPipeError` or `ConnectionResetError` (handled in lines 141–145 of `server.py`), immediately purges the dead client session, and reclaims socket descriptors.

---

## 8. Summary of Application Layer Protocol Design

Because TCP provides an unformatted byte stream, **PeerWire** enforces an Application-Layer Framing Protocol:
$$\text{Frame} = [\text{4-Byte Big-Endian Header (Length } N\text{)}] + [N\text{-Byte UTF-8 Encoded JSON Body}]$$

This guarantees that:
- Nagle's algorithm cannot concatenate adjacent messages.
- TCP packet fragmentation cannot split JSON objects mid-syntax.
- The receiving socket reads the exact byte boundaries of every chat message.
