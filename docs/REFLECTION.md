# PeerWire: Engineering Reflection & Transport-Layer Lessons

**Course:** CSC 423 – Computer Networks & Data Communications  
**Deliverable:** Project Reflection (Deliverable 7)  
**Author:** Asher  

---

## 1. Technical Challenges Faced During Development

Building a real-time, multi-user socket chat application using raw TCP sockets presented several key engineering challenges that higher-level abstractions (such as HTTP or WebSockets) usually hide:

### Challenge 1: The "Stream vs. Packet" Framing Dilemma
The most critical conceptual hurdle was understanding that **TCP is a byte-stream protocol, not a message-based protocol**. Initially, it was tempting to call `socket.send(data)` and expect `socket.recv(1024)` to return exactly that message. However, during network stress or rapid typing, multiple messages would coalesce into a single buffer, or large messages would be fragmented across MTU boundaries.

**Resolution:** We engineered a 4-byte big-endian length prefix header (`struct.pack('>I', len)`) preceding every JSON payload. Implementing a strict `recv_exact(sock, n)` loop resolved message boundary ambiguity, ensuring zero syntax corruption in the JSON parser.

### Challenge 2: Socket Thread Concurrency & State Mutation
Handling multiple concurrent clients required careful thread synchronization. If Client A disconnected at the exact millisecond Client B broadcasted a room message, iterating over the `clients` dictionary without locking triggered runtime mutation exceptions.

**Resolution:** We introduced a centralized `threading.Lock()` protecting all reads and writes to the client registry. We also ensured that all network I/O (`recv()` and `send()`) happens independently per worker thread, keeping lock hold-times strictly bounded to in-memory dictionary operations.

### Challenge 3: Distinguishing Graceful vs. Abrupt Socket Disconnects
Handling client terminations cleanly was vital. When a user closed their window gracefully, the operating system dispatched a `FIN` packet, causing `recv()` to return an empty byte sequence (`b""`). However, if a user crashed or had their Wi-Fi severed, no `FIN` was sent, leaving a "half-open" socket.

**Resolution:** We implemented dual-layer error trapping:
1. Detecting `b""` for graceful `FIN` shutdowns.
2. Trapping `ConnectionResetError`, `ConnectionAbortedError`, and `BrokenPipeError` on subsequent reads or writes, immediately cleaning up dangling client state.

### Challenge 4: Cloud NAT & Inbound Firewall Traversal
Deploying the server to a cloud virtual machine (AWS EC2) introduced real-world networking realities: the VM's internal IP address (`172.31.X.X`) was behind AWS Elastic IP NAT, and default security groups blocked all incoming traffic on Port 5000.

**Resolution:** We configured inbound security group rules opening Custom TCP Port 5000 to `0.0.0.0/0` and bound the Python server socket to `0.0.0.0` (all local interfaces) rather than `127.0.0.1` (localhost only).

---

## 2. Key Transport-Layer Concepts Learned

1. **The Reality of the BSD Socket API:**
   Working directly with `socket()`, `bind()`, `listen()`, `accept()`, `connect()`, and `close()` grounded classroom networking theory into tangible system calls. Understanding how the operating system kernel maintains separate socket buffers for transmission and reception was particularly illuminating.

2. **Port Multiplexing & Mathematical Uniqueness:**
   Seeing multiple clients connect simultaneously to a single server port (`5000`) while each client is assigned a distinct ephemeral port (e.g., `53324`, `53325`) solidified how the OS demultiplexes incoming packets using the socket 5-tuple.

3. **Trade-offs Between Latency and Reliability:**
   Understanding why TCP is indispensable for text chat—where dropping a single word changes conversational context—versus UDP for real-time voice, where low latency trumps 100% packet preservation.

4. **User-Centered Design in Networked Systems:**
   Designing PeerWire's GUI to expose transport-layer status (active socket state, local ephemeral port, live connection status) bridged the gap between low-level network mechanics and user experience. Allowing interactive RGB theme customization demonstrated that robust network engineering and intuitive frontend design can coexist seamlessly.
