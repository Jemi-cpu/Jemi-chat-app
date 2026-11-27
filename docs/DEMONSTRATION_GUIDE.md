# Deliverable 6: Demonstration & Video Presentation Guide
**Course:** CSC 423 – Computer Networks & Data Communications  
**Platform:** PeerWire Multi-User TCP Chat  
**Student:** Jemimah Omojo Attah | **Instructor:** Mr. Thomas Baidoo  

---

## Overview
This document provides the complete, step-by-step cue card and recording script for the **PeerWire Live Demonstration / Video Submission**. It is designed to allow you to showcase every single required feature to Mr. Thomas Baidoo in approximately **3 minutes**.

---

## 1. Pre-Demonstration Setup (Screen Layout)

Before hitting record (or presenting live):
1. Arrange **three windows** on your desktop screen:
   * **Window 1 (Top or Left-quarter):** Terminal window running the PeerWire TCP Server.
   * **Window 2 (Center-left):** Client 1 GUI (`Alice`).
   * **Window 3 (Center-right):** Client 2 GUI (`Bob`).
2. Make sure your microphone is clear and screen resolution is set to 1080p (Full HD).

---

## 2. Step-by-Step Video Recording Cue Card

### Phase 1: Introduction (0:00 – 0:35)
* **What to Show on Screen:** Title slide or the empty terminal windows.
* **What to Say:**
  > *"Hello Mr. Thomas Baidoo, my name is Jemimah Attah, and this is my submission for the CSC 423 Socket Programming assignment. Today, I am demonstrating **PeerWire**, a real-time multi-user chat application engineered from the ground up using raw Python TCP sockets at Layer 4.*
  > 
  > *In this demonstration, I will show: real-time multi-user communication, transport-layer socket demultiplexing via ephemeral ports, private 1-to-1 direct messaging, dynamic RGB theme customization, and graceful connection teardown."*

---

### Phase 2: Starting the Server & TCP Handshake (0:35 – 1:10)
* **Action:**
  1. In Terminal 1, type:
     ```bash
     python src/server.py 5000
     ```
  2. In Terminal 2, launch Client 1:
     ```bash
     python src/gui_client.py
     ```
  3. Enter Username: `Alice`, click **Connect to PeerWire**.
* **What to Say:**
  > *"First, I start the PeerWire server listening on port 5000. It sets `SO_REUSEADDR` to prevent socket binding conflicts.
  > 
  > Next, I launch Alice's client. When I click connect, the operating system initiates the TCP 3-way handshake—SYN, SYN-ACK, ACK. Once established, Alice sends a registration frame over the socket. Notice the top status bar: Alice is connected to server port 5000, and her operating system assigned her a unique local ephemeral port."*

---

### Phase 3: UI/UX & Interactive RGB Customization (1:10 – 1:35)
* **Action:**
  1. Click **"Customize RGB Theme"** on Alice's window.
  2. Drag the **Red, Green, and Blue sliders** to change the color with the live preview box, then click Apply.
* **What to Say:**
  > *"For the UX/UI requirements, PeerWire defaults to an accessible, crisp Royal Blue. We also built an interactive RGB Color Mixer with pullable sliders from 0 to 255. As I drag these sliders, the preview updates in real-time and dynamically restyles the client's accent colors."*

---

### Phase 4: Connecting Client 2 & Group Broadcast (1:35 – 2:10)
* **Action:**
  1. In Terminal 3, launch Client 2:
     ```bash
     python src/gui_client.py
     ```
  2. Enter Username: `Bob`, click **Connect**.
  3. On Alice's window, type: `"Hello Bob! Can you hear me over TCP?"` and press **Enter**.
  4. On Bob's window, observe the immediate receipt and reply: `"Loud and clear! Zero packet loss."`
* **What to Say:**
  > *"Now I connect Bob in a second window. Notice that both clients immediately see each other in the Online Peers directory. Bob is assigned a completely different ephemeral port.
  > 
  > When Alice sends a public message, the server receives the length-prefixed JSON frame, looks up all active sessions in the `#general` channel, and broadcasts it to Bob instantaneously. Because TCP provides guaranteed, ordered delivery, there is zero risk of dropped or scrambled text."*

---

### Phase 5: One-to-One Private Direct Messaging (2:10 – 2:40)
* **Action:**
  1. In Alice's window, double-click **Bob** in the Online Peers sidebar.
  2. Type: `"This is a private message just between us."` and press **Enter**.
  3. Show the distinct purple tag on both Alice's and Bob's screens.
* **What to Say:**
  > *"To demonstrate one-to-one messaging, Alice double-clicks Bob's name. The application formats a `/msg Bob` command. The server intercepts this direct message packet and routes it exclusively to Bob's dedicated socket descriptor. If other users were in the channel, they would never receive this frame."*

---

### Phase 6: Graceful Teardown & Disconnection (2:40 – 3:15)
* **Action:**
  1. Close Bob's window by clicking the **X** button.
  2. Point to the Server terminal log showing: `[TCP FIN] Client 'Bob' sent disconnect/closed socket.`
  3. Point to Alice's window showing: `SYSTEM: <- Bob has disconnected.` and Bob disappearing from the peer list.
* **What to Say:**
  > *"Finally, when Bob exits the application, his client executes `socket.close()`, transmitting a TCP FIN control segment. The server's `recv()` call returns 0 bytes, signaling end-of-file. The server immediately purges Bob from the active registry and broadcasts a system notice to Alice.
  > 
  > This confirms proper connection lifecycle management with no dangling half-open sockets."*

---

### Phase 7: Automated Integration Test Backup (Optional)
If asked to prove test coverage, run:
```bash
python tests/test_chat.py
```
*Output: All 4 tests pass (OK) in ~2.3 seconds.*
