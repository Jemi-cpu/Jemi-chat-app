# PeerWire System & Network Architecture

This document describes the software architecture, transport-layer data flow, port mappings, and cloud deployment topology for the **PeerWire** chat platform.

---

## 1. High-Level System Architecture

```mermaid
flowchart TD
    subgraph ClientA["Client A (Alice)"]
        UI_A["GUI / CLI Frontend"]
        Sock_A["TCP Socket (Port 52184)"]
        UI_A <--> Sock_A
    end

    subgraph ClientB["Client B (Bob)"]
        UI_B["GUI / CLI Frontend"]
        Sock_B["TCP Socket (Port 58920)"]
        UI_B <--> Sock_B
    end

    subgraph CloudServer["PeerWire Cloud Server (AWS / Azure / GCP)"]
        FW["Cloud Firewall / Security Group (Allow TCP 5000)"]
        Listener["Main Server Thread (Listening Socket 0.0.0.0:5000)"]
        
        subgraph WorkerPool["Threaded Worker Pool"]
            Worker_A["Worker Thread 1 (Alice Socket)"]
            Worker_B["Worker Thread 2 (Bob Socket)"]
        end
        
        Registry["Thread-Safe Client Registry & Room Router"]
        
        FW --> Listener
        Listener -->|accepts connection| Worker_A
        Listener -->|accepts connection| Worker_B
        Worker_A <--> Registry
        Worker_B <--> Registry
    end

    Sock_A <===>|Internet TCP Stream| FW
    Sock_B <===>|Internet TCP Stream| FW
```

---

## 2. Layer 4 Transport & Socket Demultiplexing

```
+-----------------------------------------------------------------------------------+
| OSI Model Layer        | Component in PeerWire                                    |
+------------------------+----------------------------------------------------------+
| Layer 7 (Application)  | PeerWire GUI (Tkinter) / CLI, JSON Command Framing       |
| Layer 4 (Transport)    | TCP Socket Stream (RFC 793), Port Multiplexing           |
| Layer 3 (Network)      | IP Addressing (IPv4 Unicast), Routing                    |
| Layer 2 (Data Link)    | Ethernet / Wi-Fi Frames                                   |
| Layer 1 (Physical)     | Electrical Signals / Fiber Optics                        |
+-----------------------------------------------------------------------------------+
```

### Connection State & Socket 5-Tuple:
Every connected client maintains a mathematically unique socket tuple at the operating system level:

$$\text{Session A} = \langle \text{TCP},\; \text{Client IP}: 52184,\; \text{Server IP}: 5000 \rangle$$
$$\text{Session B} = \langle \text{TCP},\; \text{Client IP}: 58920,\; \text{Server IP}: 5000 \rangle$$

---

## 3. Application-Layer Protocol Framing (TLV)

Because TCP is a continuous byte stream without packet boundaries, PeerWire uses **Length-Prefixed Framing**:

```
+-----------------------------+--------------------------------------------------+
| 4 Bytes (Network Byte Order)| Variable Length (N Bytes) UTF-8 Encoded JSON     |
+-----------------------------+--------------------------------------------------+
| struct.pack('>I', N)        | {"type": "BROADCAST", "content": "Hello!"}       |
+-----------------------------+--------------------------------------------------+
```

### Message Lifecycle Diagram:

```mermaid
sequenceDiagram
    autonumber
    actor Alice as Alice (Client)
    participant Server as PeerWire Server
    actor Bob as Bob (Client)

    Note over Alice,Server: 1. TCP 3-Way Handshake
    Alice->>Server: SYN (Port 52184 -> 5000)
    Server-->>Alice: SYN-ACK (5000 -> 52184)
    Alice->>Server: ACK (5000 -> 52184)

    Note over Alice,Server: 2. Registration Handshake
    Alice->>Server: [4B Header] + {"type": "REGISTER", "username": "Alice"}
    Server-->>Alice: [4B Header] + {"type": "REGISTER_ACK", "room": "#general"}

    Note over Bob,Server: 3. Bob Connects & Registers
    Bob->>Server: [4B Header] + {"type": "REGISTER", "username": "Bob"}
    Server-->>Bob: [4B Header] + {"type": "REGISTER_ACK"}
    Server-->>Alice: [4B Header] + {"type": "SYSTEM", "content": "-> Bob joined #general"}

    Note over Alice,Bob: 4. Real-Time Chat Broadcast
    Alice->>Server: [4B Header] + {"type": "BROADCAST", "room": "#general", "content": "Hello Bob!"}
    Server-->>Bob: [4B Header] + {"type": "BROADCAST", "sender": "Alice", "content": "Hello Bob!"}

    Note over Bob,Alice: 5. 1-to-1 Private Direct Message
    Bob->>Server: [4B Header] + {"type": "DIRECT", "target": "Alice", "content": "Secret notes"}
    Server-->>Alice: [4B Header] + {"type": "DIRECT", "sender": "Bob", "content": "Secret notes"}
```

---

## 4. Cloud Infrastructure Architecture (AWS / Azure / GCP)

```
                            [ Public Internet ]
                                     |
                                     v
                        [ Cloud Elastic Public IP ]
                                     |
                                     v
                       [ Cloud Virtual Firewall ]
                  (Inbound: Allow Port 22 SSH, Port 5000 TCP)
                                     |
                                     v
                  [ Virtual Private Cloud (VPC) / Subnet ]
                                     |
                                     v
                   [ Linux Cloud VM (Ubuntu 22.04 LTS) ]
                   +----------------------------------+
                   | systemd Daemon (peerwire.service)|
                   |      Python 3 Runtime            |
                   |      Listening on 0.0.0.0:5000   |
                   +----------------------------------+
```

### Cloud Security Group Specification:
* **Port 22 (TCP):** SSH Administrative Access (Restricted to developer IP).
* **Port 5000 (TCP):** PeerWire Custom TCP Socket Port (Open to `0.0.0.0/0` for public multi-user chat).
* **Outbound Rules:** All traffic allowed (`0.0.0.0/0`) for system updates.
