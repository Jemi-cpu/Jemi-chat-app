"""
Builds docs/PeerWire_Technical_Report.docx in the department's report style.

    python docs/report/build_report.py

Re-run after new experiment results are added to experiments/results/summary.csv:
the TCP/UDP table is filled from that file automatically. Yellow-highlighted
PENDING paragraphs mark evidence that still has to be produced.
When Word opens the file it asks to update fields: answer Yes to fill the
table of contents and page numbers.
"""

import csv
import os
import re

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ASSETS = os.path.join(ROOT, "docs", "report", "assets")
OUT = os.path.join(ROOT, "docs", "PeerWire_Technical_Report.docx")
SUMMARY = os.path.join(ROOT, "experiments", "results", "summary.csv")

STUDENT = "JEMIMAH OMOJO ATTAH"
MATRIC = "VUG/CSC/XX/XXXX"          # TODO: replace with your matriculation number
LECTURER = "MR. THOMAS BAIDOO"
DATE = "NOVEMBER 2026"
REPO = "https://github.com/Jemi-cpu/Jemi-chat-app"
FONT = "Times New Roman"

doc = Document()


# --------------------------------------------------------------------- styles
def setup_styles():
    st = doc.styles["Normal"]
    st.font.name = FONT
    st.font.size = Pt(12)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    st.paragraph_format.space_after = Pt(6)
    st.paragraph_format.line_spacing = 1.15
    for name, size, before in (("Heading 1", 24, 0), ("Heading 2", 17, 12), ("Heading 3", 13, 8)):
        h = doc.styles[name]
        h.font.name = FONT
        h.font.size = Pt(size)
        h.font.bold = True
        h.font.color.rgb = RGBColor(0, 0, 0)
        rpr = h.element.get_or_add_rPr()
        rf = rpr.find(qn("w:rFonts"))
        if rf is None:
            rf = OxmlElement("w:rFonts")
            rpr.append(rf)
        for att in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            rf.set(qn(att), FONT)
        for att in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            if rf.get(qn(att)) is not None:
                del rf.attrib[qn(att)]
        h.paragraph_format.space_before = Pt(before)
        h.paragraph_format.space_after = Pt(8)
    for sec in doc.sections:
        sec.left_margin = sec.right_margin = Inches(1)
        sec.top_margin = sec.bottom_margin = Inches(1)


# -------------------------------------------------------------------- helpers
INLINE = re.compile(r"(\*\*.+?\*\*|`.+?`)")


def add_runs(p, text, size=None):
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            r = p.add_run(part[2:-2])
            r.bold = True
        elif part.startswith("`") and part.endswith("`"):
            r = p.add_run(part[1:-1])
            r.font.name = "Consolas"
            r.font.size = Pt(10)
        else:
            r = p.add_run(part)
        if size and not part.startswith("`"):
            r.font.size = Pt(size)
    return p


def para(text, align=None, size=None, bold=False, italic=False, after=None):
    p = doc.add_paragraph()
    add_runs(p, text, size)
    if bold or italic:
        for r in p.runs:
            r.bold = r.bold or bold
            r.italic = italic
    if align == "c":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align == "j":
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if after is not None:
        p.paragraph_format.space_after = Pt(after)
    return p


def body(text):
    return para(text, align="j")


def h1(text):
    p = doc.add_heading(text, level=1)
    p.paragraph_format.page_break_before = True
    return p


def h2(text):
    return doc.add_heading(text, level=2)


def bullets(items, numbered=False):
    if numbered == "manual":  # independent 1..n numbering (Word list styles share one counter)
        for i, it in enumerate(items, 1):
            p = para(f"{i}. {it}")
            p.paragraph_format.left_indent = Inches(0.35)
            p.paragraph_format.first_line_indent = Inches(-0.3)
            p.paragraph_format.space_after = Pt(3)
        return
    style = "List Number" if numbered else "List Bullet"
    for it in items:
        p = doc.add_paragraph(style=style)
        add_runs(p, it)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_after = Pt(3)


def shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def table(headers, rows, widths=None, size=10.5, caption=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = ""
        r = c.paragraphs[0].add_run(h)
        r.bold = True
        r.font.size = Pt(size)
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        shade(c, "E7E6E6")
    # repeat header row on each page
    trPr = t.rows[0]._tr.get_or_add_trPr()
    th = OxmlElement("w:tblHeader")
    th.set(qn("w:val"), "true")
    trPr.append(th)
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            text = str(val)
            if text.startswith("PENDING"):
                r = p.add_run(text)
                r.bold = True
                r.font.size = Pt(size)
                r.font.highlight_color = WD_COLOR_INDEX.YELLOW
            else:
                add_runs(p, text, size)
                for r in p.runs:
                    if r.font.size is None:
                        r.font.size = Pt(size)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Inches(w)
    if caption:
        para(caption, align="c", italic=True, size=10, after=10)
    else:
        doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def code(text):
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = t.rows[0].cells[0]
    shade(c, "F2F2F2")
    c.text = ""
    p = c.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.0
    lines = text.strip("\n").split("\n")
    for i, line in enumerate(lines):
        r = p.add_run(line)
        r.font.name = "Consolas"
        r.font.size = Pt(9)
        if i < len(lines) - 1:
            r.add_break()
    # remove borders
    tblPr = t._tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "nil")
        b.append(e)
    tblPr.append(b)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def pending(text):
    p = doc.add_paragraph()
    r = p.add_run("PENDING: " + text)
    r.bold = True
    r.font.highlight_color = WD_COLOR_INDEX.YELLOW
    return p


def figure(path, caption, width=6.3):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(path, width=Inches(width))
    para(caption, align="c", italic=True, size=10, after=10)


def add_field(paragraph, instr):
    r = paragraph.add_run()
    f1 = OxmlElement("w:fldChar")
    f1.set(qn("w:fldCharType"), "begin")
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = instr
    f2 = OxmlElement("w:fldChar")
    f2.set(qn("w:fldCharType"), "separate")
    t = OxmlElement("w:t")
    t.text = "Right-click and choose Update Field to build the table of contents." if "TOC" in instr else "1"
    f3 = OxmlElement("w:fldChar")
    f3.set(qn("w:fldCharType"), "end")
    for el in (f1, it, f2, t, f3):
        r._r.append(el)


def update_fields_on_open():
    s = doc.settings.element
    u = OxmlElement("w:updateFields")
    u.set(qn("w:val"), "true")
    s.append(u)


# ---------------------------------------------------------------------- cover
def cover():
    sec = doc.sections[0]
    sec.different_first_page_header_footer = True
    hp = sec.header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_field(hp, "PAGE")
    for r in hp.runs:
        r.font.name = FONT
        r.font.size = Pt(11)
    sec.header_distance = Inches(0.5)
    # cover page numbering starts at 0, so the TOC page shows 1 (like the template)
    pg = OxmlElement("w:pgNumType")
    pg.set(qn("w:start"), "0")
    sec._sectPr.append(pg)

    for _ in range(3):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(os.path.join(ASSETS, "veritas_logo.jpg"), width=Inches(2.9))
    lines = [
        ("VERITAS UNIVERSITY, ABUJA", 14, True),
        ("FACULTY OF COMPUTING", 14, True),
        ("DEPARTMENT OF COMPUTER SCIENCE", 14, True),
        ("CSC 423: DATA COMMUNICATION AND NETWORKING", 12, True),
        ("TECHNICAL REPORT", 12, True),
        ("DESIGN, IMPLEMENTATION AND CLOUD DEPLOYMENT OF A MULTI-USER TCP CHAT APPLICATION (PEERWIRE)", 12, False),
        ("BY", 12, True),
    ]
    for text, size, bold in lines:
        q = para(text, align="c", size=size, bold=bold, after=10)
    q = doc.add_paragraph()
    q.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = q.add_run("NAME: ")
    r.bold = True
    q.add_run(STUDENT)
    q = doc.add_paragraph()
    q.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = q.add_run("MATRICULATION NUMBER: ")
    r.bold = True
    r = q.add_run(MATRIC)
    if "X" in MATRIC:
        r.font.highlight_color = WD_COLOR_INDEX.YELLOW
    para("A TECHNICAL REPORT SUBMITTED TO THE DEPARTMENT OF COMPUTER SCIENCE, VERITAS UNIVERSITY, "
         "ABUJA, IN PARTIAL FULFILMENT OF THE REQUIREMENTS OF THE COURSE CSC 423: DATA COMMUNICATION "
         "AND NETWORKING", align="c", bold=True, after=14)
    para("COURSE LECTURER:", align="c", bold=True)
    para(LECTURER, align="c")
    para(DATE, align="c", bold=True)


def toc():
    p = doc.add_paragraph()
    p.paragraph_format.page_break_before = True
    r = p.add_run("TABLE OF CONTENTS")
    r.bold = True
    r.font.size = Pt(24)
    p2 = doc.add_paragraph()
    add_field(p2, 'TOC \\o "1-2" \\h \\z \\u')


# ------------------------------------------------------------- results table
def comparison_rows():
    rows, seen = [], set()
    if os.path.exists(SUMMARY):
        with open(SUMMARY, newline="") as f:
            for r in csv.DictReader(f):
                if r["label"].startswith("exp4_"):
                    continue
                seen.add(r["label"])
                rows.append([r["label"], r["proto"], r["notes"] or "",
                             f"{r['received']}/{r['count']}", r["lost"], r["out_of_order"],
                             f"{r['rtt_avg_ms']} / {r['rtt_p95_ms']} / {r['rtt_max_ms']}",
                             r["msgs_per_s"]])
    for label, cond in (("baseline", "Linux loopback, no impairment"),
                        ("loss10", "netem loss 10%"),
                        ("jitter_loss5", "netem delay 20ms 15ms loss 5%")):
        if label not in seen:
            rows.append([label, "UDP/TCP", cond, "PENDING", "", "", "", ""])
    return rows


def exp4_rows():
    out = []
    if os.path.exists(SUMMARY):
        with open(SUMMARY, newline="") as f:
            for r in csv.DictReader(f):
                if r["label"].startswith("exp4_"):
                    out.append([r["label"], r["notes"], f"{r['received']}/{r['count']}",
                                f"{r['rtt_avg_ms']} / {r['rtt_p95_ms']} / {r['rtt_max_ms']}",
                                r["msgs_per_s"], r["throughput_kbit_s"]])
    return out


# ===================================================================== content
def content():
    # 1 -----------------------------------------------------------------------
    h1("1. INTRODUCTION AND OBJECTIVES")
    h2("1.1 Background")
    body("Networked applications rely on the transport layer of the TCP/IP suite to move data between "
         "processes on different machines. The network layer (IP) only delivers packets between hosts, on a "
         "best-effort basis: packets may be lost, duplicated or delivered out of order. The transport layer adds "
         "process-to-process delivery through port numbers and, in the case of TCP, a reliable, ordered, "
         "connection-oriented byte stream.")
    body("A chat application makes these ideas visible. Several users stay connected at the same time, messages "
         "must arrive complete and in order, and the server must notice when a user joins, leaves or disappears "
         "without warning. This report describes **PeerWire**, a multi-user chat application I designed, "
         "implemented and tested, and explains how it uses TCP sockets, port numbers, connections and "
         "application-level message framing.")
    h2("1.2 Objectives")
    bullets([
        "Implement client-server communication using TCP sockets, with a server that accepts and manages many clients at once.",
        "Demonstrate the roles of IP addresses, port numbers, connections and application-layer message framing.",
        "Handle the full connection lifecycle: establishment, normal disconnection and unexpected client termination.",
        "Evaluate TCP and UDP experimentally under normal and impaired network conditions.",
        "Deploy and validate the application on a public cloud platform (Microsoft Azure), with appropriate security and cost controls.",
    ], numbered=True)
    h2("1.3 Source Code")
    body(f"All source code, tests, tools and documentation are in the Git repository **{REPO}**. The README "
         "explains how to install, run, test and deploy the application. PeerWire uses only the Python standard "
         "library, so no packages have to be installed to run it.")

    # 2 -----------------------------------------------------------------------
    h1("2. SYSTEM REQUIREMENTS")
    h2("2.1 Functional Requirements")
    table(["ID", "Requirement", "Where it is met"], [
        ["F1", "A chat server that accepts and manages multiple client connections at the same time", "src/server.py (thread per client)"],
        ["F2", "A client that connects to the server using TCP", "src/gui_client.py, src/client.py"],
        ["F3", "User identification by a unique username", "REGISTER → REGISTER_ACK / REGISTER_FAIL"],
        ["F4", "Real-time text messaging between at least two connected users", "BROADCAST pushed to all users in the room"],
        ["F5", "Group chat and one-to-one messaging", "rooms (#general, …) and DIRECT messages"],
        ["F6", "Handling of connection establishment, disconnection and unexpected termination", "Section 4.4"],
        ["F7", "A documented message format with explicit framing", "Section 4.3, docs/protocol.md"],
        ["F8", "Validation of usernames and messages; malformed input must not crash the server", "Section 4.5"],
        ["F9", "Server-side connection and error logs", "logs/server.log"],
    ], widths=[0.5, 3.6, 2.4])
    h2("2.2 Non-Functional Requirements")
    bullets([
        "**Responsiveness:** messages are pushed to recipients as soon as they arrive; clients never poll.",
        "**Robustness:** one misbehaving or failed client cannot crash the server or block the other users.",
        "**Security:** no secrets are stored in the repository; only the required ports are exposed in the cloud.",
        "**Portability:** server and clients use only the Python standard library and run on Windows, Linux and macOS with Python 3.8 or later.",
    ])
    h2("2.3 Software and Hardware")
    table(["Component", "Technology"], [
        ["Language and runtime", "Python 3.12 (standard library only)"],
        ["TCP server", "socket (AF_INET, SOCK_STREAM) on port 5000, one thread per client (threading)"],
        ["Framing", "4-byte big-endian length prefix + UTF-8 JSON (struct, json)"],
        ["Clients", "Tkinter desktop client; terminal client (socket + threading)"],
        ["Testing and analysis", "unittest, Wireshark, tcpdump, Linux tc netem, ss"],
        ["Cloud", "Microsoft Azure virtual machine, Ubuntu Server, systemd"],
        ["Version control", "Git and GitHub"],
    ], widths=[1.9, 4.6])

    # 3 -----------------------------------------------------------------------
    h1("3. SYSTEM ARCHITECTURE")
    h2("3.1 Overview")
    body("PeerWire is a client-server system. One server process creates a listening TCP socket on **port 5000**. "
         "Each client opens one TCP connection to that port and keeps it open for the whole session. The server "
         "starts a dedicated worker thread for every accepted connection; the threads share an in-memory registry "
         "of connected users, which is protected by a lock. Messages from any client are routed through the "
         "server to the other clients, so a desktop (GUI) user and a terminal user can chat with each other.")
    figure(os.path.join(ROOT, "docs", "architecture_diagram.png"),
           "Figure 1: Application architecture. Every arrow is a TCP connection to port 5000.")
    h2("3.2 Components")
    table(["Component", "Responsibility"], [
        ["TCP chat server (src/server.py)", "Listens on port 5000, accepts connections, starts one worker thread per client, frames the byte stream into messages, validates and routes them, detects disconnections and logs every connection event."],
        ["Framing (src/protocol.py)", "FrameDecoder turns arbitrary chunks of bytes into complete length-prefixed frames; parse_payload checks each one is a valid JSON object with a type."],
        ["Client registry", "Maps each username to its ClientSession (socket, client address and port, current room). Used to route group and private messages and to build the online-users list."],
        ["Desktop client (src/gui_client.py)", "Tkinter window: rooms, online users, chat history, private messages, RGB colour theme. One thread runs the UI, a second thread reads from the socket."],
        ["Terminal client (src/client.py)", "Connects with a TCP socket, prints its 4-tuple, sends commands (/msg, /join, /users, /ping, /quit, /crash) and prints messages as they arrive."],
        ["Tools (tools/)", "framing_demo.py (split/combined frames), tcp_udp_compare.py (separate TCP/UDP experiment), lifecycle_client.py (FIN, RST, killed process)."],
    ], widths=[2.0, 4.5])
    h2("3.3 Data Model")
    body("PeerWire keeps state in memory only. The server holds one dictionary, `clients`, from username to "
         "ClientSession (socket, (IP, port), room, connection time). Rooms are a field on each session, so "
         "joining a room is a single assignment. No chat history is stored: a message that arrives while a user "
         "is offline is not delivered later (see Limitations).")
    h2("3.4 Cloud Deployment Architecture")
    pending("cloud deployment diagram (Figure 2) and description, to be added after the Azure deployment.")

    # 4 -----------------------------------------------------------------------
    h1("4. IMPLEMENTATION AND MESSAGE PROTOCOL")
    h2("4.1 Sockets, Ports and Concurrency")
    body("The server creates its listening socket with `socket.socket(AF_INET, SOCK_STREAM)`, sets "
         "`SO_REUSEADDR` so it can restart while old connections are still in TIME_WAIT, then calls "
         "`bind((host, port))` and `listen(50)`. `PEERWIRE_HOST=0.0.0.0` makes it accept connections on every "
         "network interface and `PEERWIRE_PORT` (or the first command-line argument) sets the port, so the "
         "listening port can be changed without editing code: `python src/server.py 5050`.")
    body("When a client connects, the operating system completes the three-way handshake (SYN, SYN-ACK, ACK) and "
         "queues the connection; `accept()` then returns a **new socket** for that client together with the "
         "client's IP address and ephemeral port. The connection is identified by the 4-tuple (client IP, client "
         "port, server IP, 5000), which is how one server port serves many clients: the operating system "
         "delivers each incoming segment to the right connected socket using all four values. The server logs "
         "both ends, for example `[CONNECT] TCP connection from 127.0.0.1:49786 (handshake complete, server side 127.0.0.1:5000)`, "
         "and the terminal client prints its own 4-tuple when it connects.")
    body("Concurrency uses **one thread per client**. Each worker blocks in `sock.recv(4096)` waiting for its own "
         "client, so a quiet client never delays the others. The shared registry is protected by a "
         "`threading.RLock`; while holding the lock the server only copies the list of recipients, and it sends "
         "after releasing it, so a slow send cannot freeze the whole server. Each socket also has a 5-second "
         "send timeout: a client that stops reading is dropped rather than allowed to block senders.")
    h2("4.2 Message Framing")
    body("TCP provides an ordered **byte stream**, not separate messages. The number of bytes returned by each "
         "`recv()` is decided by the network and the operating system, not by the sender: one read can return "
         "half a message, or several messages joined together. PeerWire therefore marks the length of every "
         "message explicitly. Each message is a JSON object encoded as UTF-8, preceded by a **4-byte unsigned "
         "length in network byte order (big-endian)**.")
    code("""
+---------------------------------+------------------------------------+
| 4 bytes: payload length N       | N bytes: UTF-8 JSON object         |
| unsigned 32-bit, big-endian     | {"type": "BROADCAST", ...}         |
+---------------------------------+------------------------------------+
Example: {"type":"PING"} is 15 bytes  ->  00 00 00 0F 7B 22 74 79 70 65 ...
""")
    body("The receiver (`FrameDecoder.feed`) appends each chunk to a buffer, and while the buffer holds at "
         "least 4 bytes it reads the length; if the whole payload is present it removes the frame and continues, "
         "otherwise it waits for the next read. A length prefix was chosen over newline delimiting because the "
         "receiver knows in advance exactly how many bytes to wait for and the payload may contain any byte. "
         "Any length above 64 KiB is rejected and that connection is closed, which protects server memory.")
    code("""
def feed(self, data: bytes) -> list[bytes]:
    self.buffer += data
    frames = []
    while len(self.buffer) >= HEADER_SIZE:                   # 4 bytes
        (length,) = HEADER_STRUCT.unpack_from(self.buffer, 0)  # '>I'
        if length > self.max_frame:
            raise FrameTooLarge(...)
        if len(self.buffer) < HEADER_SIZE + length:
            break                                             # wait for more bytes
        frames.append(bytes(self.buffer[HEADER_SIZE:HEADER_SIZE + length]))
        del self.buffer[:HEADER_SIZE + length]
    return frames
""")
    body("The demonstration tool `tools/framing_demo.py` sends three frames in a single write, then one frame "
         "split into three writes half a second apart (the first write is only 2 bytes, half of the header), "
         "with Nagle's algorithm disabled (`TCP_NODELAY`). With `LOG_LEVEL=DEBUG` the server log shows exactly "
         "how the reads mapped to frames (Windows 11 loopback, 27 November 2026):")
    code("""
read 106 bytes -> 3 complete frame(s), 0 byte(s) buffered    (three messages, one read)
read 2 bytes -> 0 complete frame(s), 2 byte(s) buffered      (half of the length header)
read 18 bytes -> 0 complete frame(s), 20 byte(s) buffered    (rest of header + start of JSON)
read 64 bytes -> 1 complete frame(s), 0 byte(s) buffered     (message complete)
""")
    h2("4.3 Message Protocol")
    body("Every message has a `type` field. Clients send commands; the server sends replies and pushes events at any time.")
    table(["Client → server", "Fields", "Registered?", "Server reply"], [
        ["REGISTER", "username (3–20 letters, digits, _)", "No (first)", "REGISTER_ACK or REGISTER_FAIL"],
        ["BROADCAST", "content (1–2000 chars)", "Yes", "BROADCAST to everyone in the sender's room"],
        ["DIRECT", "target, content", "Yes", "DIRECT to target + echo to sender (is_echo)"],
        ["ROOM_JOIN", "room (e.g. #study-group)", "Yes", "SYSTEM notices, USER_LIST to all"],
        ["USER_LIST", "none", "Yes", "USER_LIST [{username, room, port}]"],
        ["PING", "id (optional)", "No", "PONG {id}"],
        ["DISCONNECT", "none", "No", "none; server closes and cleans up"],
    ], widths=[1.2, 2.0, 0.9, 2.4])
    body("The server also sends `SYSTEM` notices (joins, leaves, disconnects) and, for any invalid input, "
         "`{\"type\": \"ERROR\", \"message\": \"...\"}`; the connection stays open. An example exchange:")
    code("""
C: {"type": "REGISTER", "username": "Alice"}
S: {"type": "REGISTER_ACK", "username": "Alice", "room": "#general", "client_addr": "127.0.0.1:52184", ...}
S: {"type": "SYSTEM", "content": "-> Alice joined #general", "room": "#general"}
S: {"type": "USER_LIST", "users": [{"username": "Alice", "room": "#general", "port": 52184}]}
C: {"type": "BROADCAST", "content": "Hello everyone"}
S: {"type": "BROADCAST", "sender": "Alice", "room": "#general", "content": "Hello everyone", "timestamp": "14:02:11"}
C: {"type": "DIRECT", "target": "Bob", "content": "Hi Bob"}
S: {"type": "DIRECT", "sender": "Alice", "target": "Bob", "content": "Hi Bob", "is_echo": true, ...}
""")
    body("The full specification is in `docs/protocol.md` in the repository.")
    h2("4.4 Connection Lifecycle")
    table(["Event", "What happens on the wire", "Server behaviour"], [
        ["Connect", "SYN, SYN-ACK, ACK", "accept(); enable keepalive; set 5 s send timeout; log address:port; wait for REGISTER"],
        ["Normal quit", "Client sends DISCONNECT then closes: FIN/ACK in each direction", "Logged as 'client sent DISCONNECT' (or 'FIN received' if it just closes)"],
        ["Crash / abort", "RST (terminal command /crash sets SO_LINGER = 0)", "ConnectionResetError; logged as 'connection reset by peer (RST received)'"],
        ["Process killed", "The OS closes the socket and normally sends FIN", "recv() returns b''; same as a normal close, without DISCONNECT"],
        ["Silent loss (power or network gone)", "Nothing arrives at all", "Keepalive probes after 60 s idle, every 10 s; connection dropped after failed probes"],
        ["Client stops reading", "Client's receive window fills; server's send buffer fills", "sendall() times out after 5 s; that client is shut down so others are not stalled"],
    ], widths=[1.3, 2.4, 2.8])
    body("In every case the `finally` block of `_handle_client` removes the user from the registry, tells the "
         "room that the user left, pushes the new user list, closes the socket and logs the reason, so a failed "
         "client never stays registered and its username can be reused immediately.")
    h2("4.5 Validation, Error Handling and Logging")
    bullets([
        "**Usernames:** 3–20 characters, letters, digits and underscore only, unique (case-insensitive). **Messages:** 1–2000 characters after trimming. **Rooms:** `#` followed by 1–24 lowercase letters, digits, `-` or `_`. Rules are enforced on the server whatever the client sends.",
        "**Malformed input** (invalid UTF-8, text that is not JSON, JSON that is not an object, missing or unknown type, wrong field types, chatting before registering) gets a specific ERROR reply and the connection keeps working. The test suite sends ten malformed inputs and then checks that PING still gets PONG.",
        "**Oversized frames** (length above 64 KiB) receive ERROR and only that connection is closed; other users are unaffected.",
        "**Logging:** connections, registrations, disconnections with their reason (FIN, RST, socket error), malformed input and unexpected errors go to the console and to a rotating log file, `logs/server.log`. With `LOG_LEVEL=DEBUG` every read and its frame count is also logged.",
    ])
    h2("4.6 Security Measures")
    bullets([
        "No secrets exist in the code. Runtime settings (host, port, log level) come from environment variables; `.env` is excluded from Git and only `.env.example` is committed.",
        "Strict input validation and size limits on every field and frame.",
        "In the cloud only the chat port (5000) is open to the Internet; SSH (22) is restricted to my own IP address (Section 8).",
        "Traffic is not encrypted (no TLS); see Section 8 and Limitations.",
    ])

    # 5 -----------------------------------------------------------------------
    h1("5. TCP VERSUS UDP ANALYSIS")
    h2("5.1 Why is TCP suitable for normal chat messages?")
    body("A chat message is only useful if it arrives complete, exactly once and in the order it was written: a "
         "missing word, a repeated message or a reply that appears before the question all confuse a "
         "conversation. TCP provides these properties automatically. Chat messages are small and not "
         "time-critical at the millisecond level, so the extra delay of a retransmission (tens to a few hundred "
         "milliseconds) is acceptable, whereas a lost message is not. A TCP connection also gives the server a "
         "natural notion of a user being online (an open socket) and a clear signal when they leave (FIN or RST); "
         "PeerWire's online-users list is built directly on that.")
    h2("5.2 What transport-layer guarantees does TCP provide?")
    bullets([
        "**Process-to-process delivery** using source and destination port numbers.",
        "**Connection-oriented communication:** a three-way handshake establishes the connection and agrees initial sequence numbers before data flows; an orderly close uses FIN in each direction.",
        "**Reliable delivery:** every byte has a sequence number and is acknowledged; missing data is retransmitted after a timeout or after three duplicate ACKs (fast retransmit).",
        "**In-order delivery without duplicates:** the receiver reorders segments by sequence number and discards duplicates before passing data to the application.",
        "**Error detection:** a checksum covers header and data; corrupted segments are discarded and later retransmitted.",
        "**Flow control:** the receiver advertises a receive window so a fast sender cannot overrun a slow receiver.",
        "**Congestion control:** the sender limits its rate (slow start, congestion avoidance) to avoid overloading the network.",
    ])
    body("TCP does **not** guarantee message boundaries, a maximum delay, or that data was processed by the "
         "receiving application. These are covered in Sections 5.8 and 5.9.")
    h2("5.3 What are the major differences between TCP and UDP?")
    table(["Feature", "TCP", "UDP"], [
        ["Connection", "Connection-oriented (handshake, teardown)", "Connectionless: each datagram is independent"],
        ["Reliability", "Acknowledgements and retransmission", "None: lost datagrams are simply lost"],
        ["Ordering", "Delivered in order", "May arrive out of order"],
        ["Duplicates", "Removed", "Possible"],
        ["Message boundaries", "None (byte stream); the application must frame", "Preserved: one send = one datagram"],
        ["Flow / congestion control", "Yes", "No"],
        ["Header size", "20–60 bytes", "8 bytes"],
        ["Latency", "Handshake plus possible retransmission delays; head-of-line blocking", "Lowest: send immediately, no waiting"],
        ["Typical uses", "Web, email, file transfer, chat, SSH", "DNS, VoIP, video calls, online games, streaming"],
    ], widths=[1.6, 2.5, 2.4])
    h2("5.4 Which parts of a chat application could reasonably use UDP?")
    body("Information that is frequent, short-lived and quickly replaced by newer information could use UDP, "
         "because a lost update is soon corrected by the next one and retransmitting an old one would be pointless:")
    bullets([
        "**Typing indicators** (\"Bob is typing...\").",
        "**Presence and heartbeats** (online / away status sent every few seconds).",
        "**Voice and video calls** inside the chat, where late audio is useless and a small gap is better than a pause.",
        "**Live location or cursor sharing.**",
    ])
    body("The messages themselves, registration and private messages must stay on TCP. In PeerWire everything "
         "uses TCP; UDP is used only in the separate comparison experiment.")
    h2("5.5 What happens if a UDP message is lost or arrives out of order?")
    body("UDP does nothing. A lost datagram is never retransmitted and the receiver is not told; datagrams that "
         "arrive out of order are passed to the application in the order they arrived; duplicates are passed up "
         "too. If the application needs reliability or ordering it must add sequence numbers, acknowledgements, "
         "timeouts and a reorder buffer itself. The comparison tool numbers every message precisely so that "
         "these losses and reorderings become visible (Section 5.10).")
    h2("5.6 How do sockets and port numbers enable communication between processes?")
    body("An IP address identifies a host; a **port number** identifies a process (more precisely, a socket) on "
         "that host. A **socket** is the operating-system endpoint that a program reads from and writes to. In "
         "PeerWire the server binds a listening socket to port 5000. A client's operating system picks a "
         "temporary **ephemeral port** (for example 49786) for its side. The connection is identified by the "
         "4-tuple (client IP, client port, server IP, 5000). When a segment arrives, the server's TCP uses all four "
         "values to deliver it to the correct connected socket, and therefore to the worker thread serving that "
         "user. This is why many clients share the single server port 5000 without confusion, and why the "
         "server's user list shows each user's port.")
    h2("5.7 What happens when a client disconnects while using TCP?")
    body("In a **normal disconnect** the client sends DISCONNECT and calls close(); its TCP sends **FIN**, the "
         "server acknowledges it, and the server's next recv() returns an empty result (end of stream). PeerWire "
         "then removes the user, closes its own side (a second FIN/ACK exchange) and logs the reason. The side "
         "that closed first stays in TIME_WAIT for a short period so that delayed segments from the old "
         "connection cannot be mistaken for a new one.")
    body("If the client **aborts** (the terminal command /crash), the server receives **RST** and recv() raises "
         "ConnectionResetError; the connection is torn down immediately with no orderly exchange. If the client "
         "**disappears silently** (power failure, Wi-Fi lost), nothing is sent at all; the server only finds out "
         "when a send times out or when TCP keepalive probes go unanswered. In all cases the other users stay "
         "connected and unaffected; the automated test in which one of three clients aborts while the other two "
         "keep chatting, and then reconnects with the same username, shows this.")
    h2("5.8 Why TCP needs application-level message framing")
    body("TCP delivers a stream of bytes with no record of where one write ended and the next began. Segment "
         "sizes depend on the MSS, Nagle's algorithm, the receive window and timing, and the receiver's recv() "
         "returns whatever happens to be in its buffer. Without framing, a server could try to parse half a JSON "
         "object, or two objects joined together, and fail. PeerWire's 4-byte length prefix restores message "
         "boundaries at the application layer, and the framing demonstration (Section 4.2) shows one read "
         "containing three messages and one message arriving over three reads. UDP does not need this because "
         "each datagram is delivered whole or not at all.")
    h2("5.9 What TCP cannot guarantee after a connection failure")
    bullets([
        "**Delivery to the application:** an ACK only means the receiving TCP stack has the bytes, not that the application read or processed them.",
        "**Knowing what was received:** when a connection breaks, the sender cannot tell which of its last bytes reached the other application. Data still in the send buffer is lost.",
        "**Continuity across connections:** a new connection starts fresh; TCP does not resume or replay anything from the old one.",
        "**Timely detection:** a silent failure may not be noticed for minutes without keepalive or application heartbeats.",
    ])
    body("PeerWire handles part of this at the application level: the server echoes every BROADCAST back to its "
         "sender and every DIRECT message back with `is_echo`, so the sender sees that the server accepted it; "
         "keepalive and the send timeout bound how long a dead connection can stay registered. Because messages "
         "are not stored, a client that reconnects does not receive what it missed; adding stored history would "
         "be the next step (Section 9).")
    h2("5.10 TCP versus UDP Practical Comparison")
    body("A separate tool, `tools/tcp_udp_compare.py`, runs an echo server for both protocols on the same port "
         "number and a client that sends numbered messages and records which come back, in what order, and the "
         "round-trip time of each. The commands are in Appendix A; raw per-message results are saved as CSV "
         "files in `experiments/results/`.")
    table(["Run", "Proto", "Conditions", "Received", "Lost", "Out of order", "RTT avg / p95 / max (ms)", "Msg/s"],
          comparison_rows(), widths=[0.85, 0.5, 1.6, 0.75, 0.4, 0.5, 1.2, 0.7], size=9,
          caption="Table: TCP/UDP comparison results (100 numbered messages unless stated)")
    body("**Discussion.** On the Windows loopback interface with no impairment both protocols delivered every "
         "message in order, with round-trip times around half a millisecond. Under these ideal conditions UDP's "
         "lack of reliability is invisible, and the throughput figures reflect the CPU and the Python code, not "
         "the network.")
    pending("discussion of the Linux loss and jitter runs: UDP counts lost and reordered messages, TCP delivers "
            "all messages in order but with RTT spikes at each retransmission.")
    body("**What the results do and do not prove.** They show how each protocol behaves on one host under "
         "controlled, artificial impairment, for 100 small messages. They do not measure real Internet paths, "
         "where loss is bursty and correlated, nor do they prove one protocol is \"faster\" in general: on "
         "loopback both are limited by the CPU and the Python code rather than the network.")

    # 6 -----------------------------------------------------------------------
    h1("6. TCP EXPERIMENTS")
    body("All four experiments are automated by `experiments/run_experiments.sh` and run on a Linux machine over "
         "its loopback interface, so no other network or user is affected. Packet captures (.pcap) are written to "
         "`experiments/results/` and analysed in Wireshark. Only throwaway test usernames are used, so no real "
         "chat content or credentials appear in the captures.")
    h2("6.1 Experiment 1: Connection Establishment")
    body("**Method.** tcpdump captures port 5000 while `tools/lifecycle_client.py` connects, registers, sends one "
         "message and quits.")
    body("**Expected observation.** Three segments open the connection: SYN from the client's ephemeral port to "
         "port 5000 (with its initial sequence number and options such as MSS and window scale), SYN-ACK from the "
         "server (its own ISN, acknowledging client ISN + 1), and ACK from the client. The client's REGISTER "
         "frame follows as the first data segment; its first 4 payload bytes are the length prefix.")
    pending("annotated Wireshark screenshot of exp1_handshake.pcap with client/server IP addresses, ports, "
            "sequence and acknowledgement numbers.")
    h2("6.2 Experiment 2: Packet Loss and Retransmission")
    body("**Method.** `tc qdisc add dev lo root netem loss 10%` drops 10% of packets, then 100 numbered messages "
         "are sent over TCP and over UDP, with the TCP run captured.")
    body("**Expected observation.** Wireshark marks [TCP Retransmission], [TCP Dup ACK] and possibly [TCP Fast "
         "Retransmission]; every message still arrives, in order, but affected messages show RTT spikes of "
         "about one retransmission timeout (around 200 ms or more). The UDP run shows missing sequence numbers "
         "instead.")
    pending("retransmission screenshot from exp2_tcp_loss10.pcap and the measured counts.")
    h2("6.3 Experiment 3: Connection Termination")
    body("**Method.** Three captures: a normal quit, an abrupt abort (SO_LINGER = 0), and killing the client "
         "process with SIGKILL. The server log for the same period is saved.")
    body("**Expected observation.** Normal close: FIN/ACK from the client, FIN/ACK from the server (four-way "
         "close). Abort: a single RST. Killed process: the operating system closes the socket and sends FIN, so "
         "the server sees a normal end of stream. In each case the server removes the user from the registry.")
    body("**Server-side result (Windows 11 loopback, 27 November 2026).** The same client actions were run "
         "locally; the server log shows the two different code paths:")
    code("""
[DISCONNECT] exp3_quit @ 127.0.0.1:49787: client sent DISCONNECT
[CLEANUP] 'exp3_quit' removed from registry (0 client(s) remain)
[DISCONNECT] exp3_crash @ 127.0.0.1:49788: connection reset by peer (RST received)
[CLEANUP] 'exp3_crash' removed from registry (0 client(s) remain)
""")
    pending("FIN and RST Wireshark screenshots from exp3_fin_normal.pcap, exp3_rst_abort.pcap and exp3_killed.pcap.")
    h2("6.4 Experiment 4: Flow Control and Performance")
    body("**Method.** RTT (100 messages) and throughput (5000 × 1000-byte messages as fast as possible) are "
         "measured over TCP under two conditions: no impairment, and `netem delay 50ms rate 10mbit` (100 ms RTT, "
         "10 Mbit/s bottleneck). `ss -tin` is sampled during the slow transfer.")
    body("**Expected observation.** RTT rises from well under 1 ms to about 100 ms. Throughput drops and becomes "
         "limited by the bottleneck rate and by the window: at most one window of data per RTT. Wireshark's "
         "window-size column shows the advertised receive window and, under load, its scaling.")
    rows = exp4_rows()
    if rows:
        table(["Run", "Conditions", "Received", "RTT avg / p95 / max (ms)", "Msg/s", "kbit/s"], rows,
              widths=[1.3, 2.0, 0.8, 1.2, 0.6, 0.6], size=9)
    else:
        pending("measured RTT and throughput table and a screenshot of the advertised window values.")

    # 7 -----------------------------------------------------------------------
    h1("7. TESTING AND RESULTS")
    h2("7.1 Automated Tests")
    body("The automated suite (`python -m unittest discover -s tests -v`) starts the real server on a test port "
         "and talks to it over real TCP sockets. The latest run (27 November 2026, Windows 11, Python 3.12.1) "
         "passed **17 of 17 tests** in 3.9 seconds.")
    table(["Test file", "Tests", "What it covers"], [
        ["tests/test_framing.py", "7", "Single and combined frames, every possible split point (including inside multi-byte UTF-8 characters), byte-by-byte delivery, partial frames, oversized frames, payload parse errors"],
        ["tests/test_chat.py", "10", "Registration and duplicate names, group chat, private message isolation, clean disconnect, 10 malformed inputs, username validation, split/combined frames on a real socket, three clients with abort (RST) and reconnect, oversized frame, server log contents"],
    ], widths=[1.6, 0.6, 4.3])
    h2("7.2 Key Results")
    bullets([
        "**Three simultaneous clients with reconnect:** client C aborts with RST while A and B keep chatting; C reconnects with the same username and receives new messages live. The server log shows C's RST and the cleanup.",
        "**Malformed input:** every bad input receives a specific error and the connection keeps working.",
        "**Framing:** both automated tests and the live demonstration show messages split across reads and combined in one read are handled correctly.",
    ])
    body("The complete test log, including manual and cloud tests, is in `docs/test-log.md`.")
    pending("screenshots of two users chatting on the deployed system.")

    # 8 -----------------------------------------------------------------------
    h1("8. CLOUD DEPLOYMENT")
    pending("cloud service selection and reasons, provisioning steps, firewall (NSG) rules, TLS statement, "
            "secrets, start/restart/shutdown/cleanup, cost estimate and spending alert, public address and "
            "evidence of two users chatting.")

    # 9 -----------------------------------------------------------------------
    h1("9. CHALLENGES AND LIMITATIONS")
    h2("9.1 Challenges")
    bullets([
        "**Understanding that TCP has no message boundaries.** Treating each recv() as one message works on a quiet local network but fails as soon as messages are sent quickly or are large. Writing the length-prefix decoder and testing it at every possible split point made the byte-stream nature of TCP concrete.",
        "**Keeping one client from affecting the others.** The first version broadcast while holding the registry lock with blocking sends, so one client that stopped reading could freeze everyone. Copying the recipient list under the lock, sending outside it and adding a send timeout fixed this.",
        "**Malformed input.** Originally invalid JSON was treated like a disconnect. The server now replies with a specific ERROR and keeps the connection open, closing it only when the stream itself is unusable (an oversized length).",
        "**Platform differences.** Windows has no tc netem, so loss and delay experiments need a Linux machine; even the SO_LINGER structure used to force an RST differs between Windows and Linux.",
    ])
    h2("9.2 Limitations")
    bullets([
        "**No TLS:** traffic is not encrypted (see Section 8).",
        "**No authentication or history:** usernames are not password-protected and messages are not stored, so an offline user misses messages and a reconnecting client cannot fetch history.",
        "**Single server process:** the registry lives in memory, so the server cannot be scaled to several processes without a shared message broker.",
        "**Thread per client:** simple and clear, but each connection costs a thread; thousands of clients would call for an event loop (asyncio or selectors).",
        "**Experiments on loopback:** loss and delay are emulated on one machine, which is controlled and repeatable but does not reproduce real Internet behaviour such as bursty loss.",
    ])

    # 10 ----------------------------------------------------------------------
    h1("10. CONCLUSION")
    body("PeerWire meets the core requirements of the assignment: a multi-user chat server that accepts many "
         "simultaneous TCP connections, desktop and terminal clients that talk to it over TCP sockets, group and "
         "one-to-one messaging, a documented length-prefixed JSON protocol, input validation that never crashes "
         "the server, and careful handling of every way a connection can end.")
    body("Building it turned the transport-layer concepts into concrete code. The port number and 4-tuple are what "
         "let one server port serve many users. The byte-stream model is the reason framing exists. FIN and RST "
         "correspond to different branches in the server's code. Keepalive and send timeouts are the answer to "
         "failures TCP cannot report on its own. The comparison experiment shows the trade-off between TCP's "
         "reliability and UDP's simplicity and lower overhead, and why each suits different parts of a chat system.")

    # refs --------------------------------------------------------------------
    h1("REFERENCES")
    bullets([
        "Eddy, W. (Ed.) (2022). RFC 9293: Transmission Control Protocol (TCP). IETF.",
        "Postel, J. (1980). RFC 768: User Datagram Protocol. IETF.",
        "Braden, R. (Ed.) (1989). RFC 1122: Requirements for Internet Hosts – Communication Layers (TCP keep-alives). IETF.",
        "Kurose, J. F. and Ross, K. W. (2021). Computer Networking: A Top-Down Approach (8th ed.). Pearson.",
        "Stevens, W. R., Fenner, B. and Rudoff, A. M. (2003). UNIX Network Programming, Volume 1: The Sockets Networking API (3rd ed.). Addison-Wesley.",
        "Python Software Foundation (2026). socket – Low-level networking interface; threading; struct. docs.python.org.",
        "Linux man-pages. tc-netem(8): Network Emulator; ss(8).",
        "Wireshark Foundation. Wireshark User's Guide: TCP Analysis. wireshark.org.",
        "Microsoft (2026). Azure Virtual Machines and Network Security Groups documentation. learn.microsoft.com.",
    ], numbered="manual")

    # appendix ----------------------------------------------------------------
    h1("APPENDIX A: KEY COMMANDS")
    para("Running locally", bold=True)
    code("""
python src/server.py 5000                                   # server (or PEERWIRE_PORT=5000)
python src/gui_client.py                                    # desktop client
python src/client.py --host 127.0.0.1 --port 5000 --user Carol   # terminal client
python -m unittest discover -s tests -v                     # automated tests
$env:LOG_LEVEL="DEBUG"; python src/server.py 5000           # PowerShell: log every read
python tools/framing_demo.py --port 5000                    # framing demonstration
""")
    para("TCP/UDP comparison", bold=True)
    code("""
python tools/tcp_udp_compare.py server --host 127.0.0.1 --port 6000
python tools/tcp_udp_compare.py client --proto udp --port 6000 --count 100 --label local_baseline
python tools/tcp_udp_compare.py client --proto tcp --port 6000 --count 100 --label local_baseline
python tools/tcp_udp_compare.py client --proto tcp --port 6000 --count 2000 --size 1000 --interval 0 --label local_burst
""")
    para("Network impairment and capture (Linux)", bold=True)
    code("""
sudo tc qdisc add dev lo root netem loss 10%                      # Experiment 2
sudo tc qdisc replace dev lo root netem delay 50ms rate 10mbit    # Experiment 4
sudo tc qdisc replace dev lo root netem delay 20ms 15ms loss 5%   # jitter + loss
sudo tc qdisc del dev lo root                                     # remove impairment
sudo tcpdump -i lo -w exp1_handshake.pcap tcp port 5000
bash experiments/run_experiments.sh                               # runs everything
""")
    para("Inspecting sockets", bold=True)
    code("""
ss -tlnp                         # listening TCP sockets and their ports (Linux)
ss -tnp state established        # open connections (4-tuples)
netstat -ano | findstr :5000     # Windows equivalent
""")


def main():
    setup_styles()
    cover()
    toc()
    content()
    update_fields_on_open()
    doc.save(OUT)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
