# PeerWire Test Log

Entries marked **PENDING** must be run and filled in with real results. Nothing here is invented.

## A. Automated tests (run 2026-11-27, Windows 11, Python 3.12.1, loopback)

Command: `python -m unittest discover -s tests -v` → **17 / 17 passed** in 3.9 s.

| # | Test | Covers | Result |
|---|---|---|---|
| 1 | test_01_registration_and_duplicate_rejection | handshake, register, duplicate name refused | Pass |
| 2 | test_02_broadcast_messaging_between_peers | real-time group chat between two users | Pass |
| 3 | test_03_private_direct_message_isolation | DM reaches only the target (3 clients) | Pass |
| 4 | test_04_graceful_disconnect_handling | DISCONNECT/FIN, user removed from list | Pass |
| 5 | test_05_malformed_input_gets_error_and_connection_survives | 10 malformed inputs each get ERROR, then PING still works | Pass |
| 6 | test_06_username_validation | 6 invalid usernames refused; chat before register refused | Pass |
| 7 | test_07_combined_and_split_frames_on_real_socket | 3 frames in one write; 1 frame in 3 writes (first cut inside header, UTF-8 content) | Pass |
| 8 | test_08_three_clients_abort_and_reconnect | 3 clients; C aborts with RST; A→B still works; C reconnects with same name and receives live | Pass |
| 9 | test_09_oversized_frame_closes_only_that_connection | 10 MB length prefix → ERROR + close; other client unaffected | Pass |
| 10 | test_10_server_log_records_connection_events | log file contains CONNECT, REGISTERED, RST, MALFORMED | Pass |
| 11–17 | tests/test_framing.py (7 tests) | FrameDecoder: single, combined, every split point incl. inside UTF-8, byte-by-byte, partial, oversized, parse errors | Pass |

## B. Framing demonstration (run 2026-11-27, Windows 11 loopback)

Command: server with `LOG_LEVEL=DEBUG`, then `python tools/framing_demo.py --port 5000`.
Raw output: `experiments/results/local_framing_demo.txt`, server log: `experiments/results/local_server_demo.log`.

```
read 106 bytes -> 3 complete frame(s), 0 byte(s) buffered    (REGISTER + PING + USER_LIST in one write)
read 2 bytes -> 0 complete frame(s), 2 byte(s) buffered      (half of the 4-byte header)
read 18 bytes -> 0 complete frame(s), 20 byte(s) buffered    (rest of header + start of JSON)
read 64 bytes -> 1 complete frame(s), 0 byte(s) buffered     (message complete)
[MALFORMED] from 127.0.0.1:49786: payload is not valid JSON  (ERROR returned, next PING answered)
```

## C. Connection termination (run 2026-11-27, Windows 11 loopback, server log only)

| Client action | Server log |
|---|---|
| `lifecycle_client.py --mode quit` | `[DISCONNECT] exp3_quit @ 127.0.0.1:49787: client sent DISCONNECT` then `[CLEANUP]` |
| `lifecycle_client.py --mode crash` (SO_LINGER 0) | `[DISCONNECT] exp3_crash @ 127.0.0.1:49788: connection reset by peer (RST received)` then `[CLEANUP]` |

Packet captures of the same: **PENDING** (Linux, `experiments/run_experiments.sh`).

## D. Manual tests

| # | Test | Steps | Expected | Result |
|---|---|---|---|---|
| M1 | Two GUI users chat locally | server + 2 × `gui_client.py` (Alice, Bob) | messages both ways, user list updates | PENDING (screenshot) |
| M2 | Three simultaneous clients, one reconnects | `python tools/session_evidence.py`: Alice, Bob, Carol (real `src/client.py` processes); Carol `/crash`; Alice and Bob keep chatting; Carol reconnects | others keep chatting; rejoin works | **Pass** 2026-11-27 (section E). GUI screenshot still to take |
| M3 | Malformed input by hand | `framing_demo.py` step 3 | ERROR, connection open | Pass (section B) |
| M4 | Change listening port live | server restarted on 5050; client Dave connects to 5050; connect to 5000 attempted | connects on new port; old port refused | **Pass** 2026-11-27 (section E) |
| M5 | Cloud access, two users | two machines → `<AZURE-IP>:5000` | messages both ways | PENDING (Azure) |
| M6 | Cloud: closed port refused | connect to `<AZURE-IP>:6000` | timeout (NSG drops) | PENDING (Azure) |

## E. Three simultaneous clients and live port change (run 2026-11-27, Windows 11 loopback)

Command: `python tools/session_evidence.py`. Full transcripts of every client and the netstat output:
`experiments/results/session_evidence.txt`; server log: `experiments/results/session_server.log`.

netstat while Alice, Bob and Carol were connected: one listening socket, three connected sockets on the server
side (same port 5000, different client ephemeral ports):

```
TCP    0.0.0.0:5000           0.0.0.0:0              LISTENING       1960
TCP    127.0.0.1:5000         127.0.0.1:63329        ESTABLISHED     1960   (Alice)
TCP    127.0.0.1:5000         127.0.0.1:63330        ESTABLISHED     1960   (Bob)
TCP    127.0.0.1:5000         127.0.0.1:63331        ESTABLISHED     1960   (Carol)
```

Server log for the crash, the reconnect and the clean exits:

```
[DISCONNECT] Carol @ 127.0.0.1:63331: connection reset by peer (RST received)
[CLEANUP] 'Carol' removed from registry (2 client(s) remain)
... Alice: "Bob, can you still see me after Carol crashed?"  Bob: "Yes Alice, still connected"
... Carol reconnects as 127.0.0.1:54639, receives "Welcome back Carol" live
[DISCONNECT] Alice @ 127.0.0.1:63329: client sent DISCONNECT
```

Port change: server restarted with `python src/server.py 5050`; Dave connected to 5050 and received PONG;
connecting to 5000 gave `ConnectionRefusedError: [WinError 10061] ... actively refused it` (the OS answers the SYN
with RST because nothing listens there any more).
