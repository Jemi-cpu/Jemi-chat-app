"""
CSC 423 - PeerWire Graphical User Interface (GUI) Client
========================================================
Interactive desktop client built using Python's standard Tkinter.
No external dependencies required (runs out of the box on Windows/macOS/Linux).

UI/UX Features:
- Platform Name: PeerWire
- Default Accent: Safe Crisp Blue (#2563EB)
- Interactive RGB Pullable Sliders: Red, Green, Blue sliders (0-255) with live preview
- Left Navigation: Channels (#general, #study-group, #announcements) & Active Users
- Transport-Layer Monitor: Live display of Server IP, Server Port, and Local Ephemeral Port
- Threaded TCP Socket: Background thread reads from socket, thread-safe UI updates
"""

import sys
import os
import socket
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional

# Ensure src/ is in python path
sys.path.insert(0, os.path.dirname(__file__))

from protocol import (
    recv_message,
    send_message,
    MSG_REGISTER,
    MSG_REGISTER_ACK,
    MSG_REGISTER_FAIL,
    MSG_BROADCAST,
    MSG_DIRECT,
    MSG_ROOM_JOIN,
    MSG_USER_LIST,
    MSG_SYSTEM,
    MSG_DISCONNECT,
)


class PeerWireGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PeerWire — Real-Time TCP Chat")
        self.root.geometry("980x680")
        self.root.minsize(800, 550)

        # Network State
        self.sock: Optional[socket.socket] = None
        self.username = ""
        self.current_room = "#general"
        self.connected = False
        self.local_port = None
        self.server_host = "127.0.0.1"
        self.server_port = 5000

        # UI Color Theme (Default: Safe Blue)
        self.accent_color = "#2563EB"
        self.r_val = 37
        self.g_val = 99
        self.b_val = 235

        self.bg_dark = "#1E1E2E"
        self.panel_bg = "#181825"
        self.card_bg = "#26263A"
        self.text_light = "#E0E2EC"
        self.text_dim = "#9399B2"

        self._apply_base_theme()
        self._build_login_screen()

    def _apply_base_theme(self):
        self.root.configure(bg=self.bg_dark)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=self.bg_dark, foreground=self.text_light)

    # --------------------------------------------------------------------------
    # SCREEN 1: LOGIN / CONNECTION SCREEN
    # --------------------------------------------------------------------------
    def _build_login_screen(self):
        """Displays connection configuration (Server, Port, Nickname)."""
        self.login_frame = tk.Frame(self.root, bg=self.bg_dark)
        self.login_frame.place(relx=0.5, rely=0.5, anchor="center")

        title = tk.Label(
            self.login_frame,
            text="PeerWire",
            font=("Segoe UI", 28, "bold"),
            fg=self.accent_color,
            bg=self.bg_dark,
        )
        title.pack(pady=(0, 4))

        subtitle = tk.Label(
            self.login_frame,
            text="Multi-User TCP Socket Chat Platform",
            font=("Segoe UI", 11),
            fg=self.text_dim,
            bg=self.bg_dark,
        )
        subtitle.pack(pady=(0, 24))

        card = tk.Frame(self.login_frame, bg=self.card_bg, padx=30, pady=24)
        card.pack()

        # Host
        tk.Label(card, text="Server Host / IP:", font=("Segoe UI", 9, "bold"), fg=self.text_light, bg=self.card_bg).pack(anchor="w")
        self.entry_host = tk.Entry(card, font=("Segoe UI", 11), width=28, bg="#11111B", fg="white", insertbackground="white")
        self.entry_host.insert(0, "127.0.0.1")
        self.entry_host.pack(pady=(2, 12))

        # Port
        tk.Label(card, text="TCP Port:", font=("Segoe UI", 9, "bold"), fg=self.text_light, bg=self.card_bg).pack(anchor="w")
        self.entry_port = tk.Entry(card, font=("Segoe UI", 11), width=28, bg="#11111B", fg="white", insertbackground="white")
        self.entry_port.insert(0, "5000")
        self.entry_port.pack(pady=(2, 12))

        # Username
        tk.Label(card, text="Username / Nickname:", font=("Segoe UI", 9, "bold"), fg=self.text_light, bg=self.card_bg).pack(anchor="w")
        self.entry_user = tk.Entry(card, font=("Segoe UI", 11), width=28, bg="#11111B", fg="white", insertbackground="white")
        self.entry_user.insert(0, "User" + str(int(datetime.now().timestamp()) % 1000))
        self.entry_user.pack(pady=(2, 20))
        self.entry_user.focus()

        # Connect Button
        self.btn_connect = tk.Button(
            card,
            text="Connect to PeerWire",
            font=("Segoe UI", 11, "bold"),
            bg=self.accent_color,
            fg="white",
            activebackground="#1D4ED8",
            activeforeground="white",
            relief="flat",
            padx=16,
            pady=8,
            cursor="hand2",
            command=self._handle_connect,
        )
        self.btn_connect.pack(fill="x")
        self.root.bind("<Return>", lambda e: self._handle_connect())

    def _handle_connect(self):
        host = self.entry_host.get().strip()
        port_str = self.entry_port.get().strip()
        username = self.entry_user.get().strip()

        if not host or not port_str or not username:
            messagebox.showerror("Error", "Please fill in all connection fields.")
            return

        try:
            port = int(port_str)
        except ValueError:
            messagebox.showerror("Error", "Port must be an integer (e.g., 5000).")
            return

        self.btn_connect.config(text="Connecting (SYN-ACK)...", state="disabled")
        self.root.update()

        try:
            # 1. Create IPv4 TCP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # 2. Perform 3-way handshake with server
            sock.connect((host, port))
            self.sock = sock
            self.local_port = sock.getsockname()[1]
            self.server_host = host
            self.server_port = port

            # 3. Send REGISTER handshake message
            send_message(sock, {"type": MSG_REGISTER, "username": username})
            resp = recv_message(sock)

            if not resp or resp.get("type") != MSG_REGISTER_ACK:
                reason = resp.get("reason", "Registration failed.") if resp else "Connection closed by server."
                sock.close()
                self.sock = None
                self.btn_connect.config(text="Connect to PeerWire", state="normal")
                messagebox.showerror("Registration Rejected", reason)
                return

            self.username = username
            self.connected = True

            # Destroy login frame and transition to main chat UI
            self.login_frame.destroy()
            self._build_main_chat_screen()

            # Start background socket receiver thread
            recv_thread = threading.Thread(target=self._socket_receiver_loop, daemon=True)
            recv_thread.start()

        except Exception as e:
            if self.sock:
                self.sock.close()
                self.sock = None
            self.btn_connect.config(text="Connect to PeerWire", state="normal")
            messagebox.showerror("Connection Failed", f"Could not establish TCP connection:\n{e}")

    # --------------------------------------------------------------------------
    # SCREEN 2: MAIN CHAT INTERFACE
    # --------------------------------------------------------------------------
    def _build_main_chat_screen(self):
        self.root.unbind("<Return>")
        self.main_container = tk.Frame(self.root, bg=self.bg_dark)
        self.main_container.pack(fill="both", expand=True)

        # 1. TOP HEADER (Transport Layer Status & Customization Trigger)
        self._build_top_header()

        # 2. BODY SPLIT (Sidebar + Chat Area)
        self.body_frame = tk.Frame(self.main_container, bg=self.bg_dark)
        self.body_frame.pack(fill="both", expand=True)

        self._build_sidebar()
        self._build_chat_panel()

        # RGB Customization Drawer (Hidden by default, toggled via button)
        self._build_rgb_slider_panel()

    def _build_top_header(self):
        header = tk.Frame(self.main_container, bg=self.panel_bg, height=52, padx=16, pady=8)
        header.pack(fill="x")

        # Left: App Logo & Current User
        logo = tk.Label(header, text="PeerWire", font=("Segoe UI", 14, "bold"), fg=self.accent_color, bg=self.panel_bg)
        logo.pack(side="left")

        user_tag = tk.Label(
            header,
            text=f"Logged in as: {self.username}",
            font=("Segoe UI", 10, "bold"),
            fg=self.text_light,
            bg=self.panel_bg,
            padx=12,
        )
        user_tag.pack(side="left")

        # Right: Transport layer status badge
        self.status_badge = tk.Label(
            header,
            text=f"TCP: ESTABLISHED | Server {self.server_host}:{self.server_port} | Local Port: {self.local_port}",
            font=("Consolas", 9),
            fg="#A6E3A1",
            bg="#1E1E2E",
            padx=10,
            pady=4,
        )
        self.status_badge.pack(side="right", padx=(10, 0))

        # RGB Color Customizer Button
        self.btn_toggle_rgb = tk.Button(
            header,
            text="Customize RGB Theme",
            font=("Segoe UI", 9, "bold"),
            bg="#313244",
            fg=self.text_light,
            relief="flat",
            padx=10,
            pady=2,
            cursor="hand2",
            command=self._toggle_rgb_panel,
        )
        self.btn_toggle_rgb.pack(side="right")

    def _build_sidebar(self):
        sidebar = tk.Frame(self.body_frame, bg=self.panel_bg, width=220, padx=12, pady=12)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # Channels Section
        tk.Label(sidebar, text="CHANNELS", font=("Segoe UI", 9, "bold"), fg=self.text_dim, bg=self.panel_bg).pack(anchor="w", pady=(0, 6))

        self.channels_listbox = tk.Listbox(
            sidebar,
            font=("Segoe UI", 10),
            bg="#11111B",
            fg=self.text_light,
            selectbackground=self.accent_color,
            selectforeground="white",
            relief="flat",
            height=3,
        )
        for room in ["#general", "#study-group", "#announcements"]:
            self.channels_listbox.insert(tk.END, room)
        self.channels_listbox.select_set(0)
        self.channels_listbox.pack(fill="x", pady=(0, 16))
        self.channels_listbox.bind("<<ListboxSelect>>", self._on_room_select)

        # Users Section
        tk.Label(sidebar, text="ONLINE PEERS", font=("Segoe UI", 9, "bold"), fg=self.text_dim, bg=self.panel_bg).pack(anchor="w", pady=(0, 6))

        self.users_listbox = tk.Listbox(
            sidebar,
            font=("Segoe UI", 10),
            bg="#11111B",
            fg="#A6E3A1",
            selectbackground="#45475A",
            selectforeground="white",
            relief="flat",
        )
        self.users_listbox.pack(fill="both", expand=True, pady=(0, 12))
        self.users_listbox.bind("<Double-Button-1>", self._on_user_double_click)

        # Help hint
        hint = tk.Label(
            sidebar,
            text="Double-click a user to send a private DM.",
            font=("Segoe UI", 8),
            fg=self.text_dim,
            bg=self.panel_bg,
            wraplength=190,
            justify="left",
        )
        hint.pack(side="bottom", anchor="w")

    def _build_chat_panel(self):
        chat_container = tk.Frame(self.body_frame, bg=self.bg_dark, padx=14, pady=12)
        chat_container.pack(side="right", fill="both", expand=True)

        # Room Title Header
        self.room_title_label = tk.Label(
            chat_container,
            text=f"#general",
            font=("Segoe UI", 14, "bold"),
            fg=self.text_light,
            bg=self.bg_dark,
        )
        self.room_title_label.pack(anchor="w", pady=(0, 8))

        # Scrolled Message Area
        self.chat_display = scrolledtext.ScrolledText(
            chat_container,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            bg="#11111B",
            fg=self.text_light,
            relief="flat",
            padx=12,
            pady=10,
            state="disabled",
        )
        self.chat_display.pack(fill="both", expand=True, pady=(0, 10))

        # Tag configurations for styled message types
        self.chat_display.tag_config("system", foreground="#94E2D5", font=("Segoe UI", 9, "italic"))
        self.chat_display.tag_config("self", foreground=self.accent_color, font=("Segoe UI", 10, "bold"))
        self.chat_display.tag_config("peer", foreground="#89B4FA", font=("Segoe UI", 10, "bold"))
        self.chat_display.tag_config("dm", foreground="#CBA6F7", font=("Segoe UI", 10, "bold"))
        self.chat_display.tag_config("body", foreground=self.text_light, font=("Segoe UI", 10))
        self.chat_display.tag_config("time", foreground=self.text_dim, font=("Segoe UI", 8))

        # Input Row
        input_row = tk.Frame(chat_container, bg=self.bg_dark)
        input_row.pack(fill="x")

        self.entry_message = tk.Entry(
            input_row,
            font=("Segoe UI", 11),
            bg="#181825",
            fg="white",
            insertbackground="white",
            relief="flat",
            highlightthickness=1,
            highlightcolor=self.accent_color,
            highlightbackground="#313244",
        )
        self.entry_message.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=6)
        self.entry_message.focus()
        self.entry_message.bind("<Return>", lambda e: self._send_chat_message())

        self.btn_send = tk.Button(
            input_row,
            text="Send",
            font=("Segoe UI", 10, "bold"),
            bg=self.accent_color,
            fg="white",
            activebackground="#1D4ED8",
            activeforeground="white",
            relief="flat",
            padx=18,
            pady=6,
            cursor="hand2",
            command=self._send_chat_message,
        )
        self.btn_send.pack(side="right")

    # --------------------------------------------------------------------------
    # RGB COLOR CUSTOMIZATION PANEL (Pullable Sliders)
    # --------------------------------------------------------------------------
    def _build_rgb_slider_panel(self):
        """Builds an interactive pullable RGB slider bar panel with live preview."""
        self.rgb_window = None

    def _toggle_rgb_panel(self):
        if self.rgb_window and tk.Toplevel.winfo_exists(self.rgb_window):
            self.rgb_window.lift()
            return

        self.rgb_window = tk.Toplevel(self.root)
        self.rgb_window.title("PeerWire — Theme & RGB Customizer")
        self.rgb_window.geometry("380x360")
        self.rgb_window.configure(bg=self.card_bg)
        self.rgb_window.resizable(False, False)

        tk.Label(
            self.rgb_window,
            text="Custom RGB Color Mixer",
            font=("Segoe UI", 13, "bold"),
            fg=self.text_light,
            bg=self.card_bg,
        ).pack(pady=(14, 4))

        tk.Label(
            self.rgb_window,
            text="Drag the pullable sliders to pick your exact chat accent color:",
            font=("Segoe UI", 9),
            fg=self.text_dim,
            bg=self.card_bg,
        ).pack(pady=(0, 12))

        slider_box = tk.Frame(self.rgb_window, bg=self.card_bg, padx=20)
        slider_box.pack(fill="x")

        # RED SLIDER
        tk.Label(slider_box, text="Red (R):", font=("Segoe UI", 9, "bold"), fg="#F38BA8", bg=self.card_bg).pack(anchor="w")
        self.scale_r = tk.Scale(
            slider_box,
            from_=0,
            to=255,
            orient="horizontal",
            bg=self.card_bg,
            fg=self.text_light,
            highlightthickness=0,
            troughcolor="#11111B",
            activebackground="#F38BA8",
            command=self._on_rgb_change,
        )
        self.scale_r.set(self.r_val)
        self.scale_r.pack(fill="x", pady=(0, 6))

        # GREEN SLIDER
        tk.Label(slider_box, text="Green (G):", font=("Segoe UI", 9, "bold"), fg="#A6E3A1", bg=self.card_bg).pack(anchor="w")
        self.scale_g = tk.Scale(
            slider_box,
            from_=0,
            to=255,
            orient="horizontal",
            bg=self.card_bg,
            fg=self.text_light,
            highlightthickness=0,
            troughcolor="#11111B",
            activebackground="#A6E3A1",
            command=self._on_rgb_change,
        )
        self.scale_g.set(self.g_val)
        self.scale_g.pack(fill="x", pady=(0, 6))

        # BLUE SLIDER
        tk.Label(slider_box, text="Blue (B):", font=("Segoe UI", 9, "bold"), fg="#89B4FA", bg=self.card_bg).pack(anchor="w")
        self.scale_b = tk.Scale(
            slider_box,
            from_=0,
            to=255,
            orient="horizontal",
            bg=self.card_bg,
            fg=self.text_light,
            highlightthickness=0,
            troughcolor="#11111B",
            activebackground="#89B4FA",
            command=self._on_rgb_change,
        )
        self.scale_b.set(self.b_val)
        self.scale_b.pack(fill="x", pady=(0, 10))

        # LIVE COLOR PREVIEW SWATCH
        preview_box = tk.Frame(self.rgb_window, bg=self.card_bg)
        preview_box.pack(fill="x", padx=20, pady=4)

        self.color_preview_box = tk.Label(
            preview_box,
            text=f"Preview: {self.accent_color}",
            font=("Segoe UI", 10, "bold"),
            bg=self.accent_color,
            fg="white",
            height=2,
            relief="ridge",
        )
        self.color_preview_box.pack(fill="x")

        # Preset Quick Pickers
        preset_frame = tk.Frame(self.rgb_window, bg=self.card_bg)
        preset_frame.pack(fill="x", padx=20, pady=(8, 12))

        btn_default_blue = tk.Button(
            preset_frame,
            text="Default Blue",
            font=("Segoe UI", 8, "bold"),
            bg="#2563EB",
            fg="white",
            relief="flat",
            command=lambda: self._set_preset(37, 99, 235),
        )
        btn_default_blue.pack(side="left", expand=True, fill="x", padx=2)

        btn_emerald = tk.Button(
            preset_frame,
            text="Emerald Green",
            font=("Segoe UI", 8, "bold"),
            bg="#059669",
            fg="white",
            relief="flat",
            command=lambda: self._set_preset(5, 150, 105),
        )
        btn_emerald.pack(side="left", expand=True, fill="x", padx=2)

        btn_purple = tk.Button(
            preset_frame,
            text="Violet Purple",
            font=("Segoe UI", 8, "bold"),
            bg="#7C3AED",
            fg="white",
            relief="flat",
            command=lambda: self._set_preset(124, 58, 237),
        )
        btn_purple.pack(side="left", expand=True, fill="x", padx=2)

    def _on_rgb_change(self, _=None):
        r = self.scale_r.get()
        g = self.scale_g.get()
        b = self.scale_b.get()
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        self.accent_color = hex_color
        self.r_val, self.g_val, self.b_val = r, g, b

        # Update preview box
        if hasattr(self, "color_preview_box") and self.color_preview_box.winfo_exists():
            self.color_preview_box.config(bg=hex_color, text=f"Preview: {hex_color.upper()}")

        # Update UI accent elements dynamically
        self.btn_send.config(bg=hex_color)
        self.channels_listbox.config(selectbackground=hex_color)
        self.entry_message.config(highlightcolor=hex_color)
        self.chat_display.tag_config("self", foreground=hex_color)

    def _set_preset(self, r: int, g: int, b: int):
        self.scale_r.set(r)
        self.scale_g.set(g)
        self.scale_b.set(b)
        self._on_rgb_change()

    # --------------------------------------------------------------------------
    # CHAT ACTIONS & NETWORKING
    # --------------------------------------------------------------------------
    def _send_chat_message(self):
        text = self.entry_message.get().strip()
        if not text or not self.sock:
            return

        self.entry_message.delete(0, tk.END)

        # Check for commands
        if text.startswith("/"):
            self._handle_slash_command(text)
            return

        # Regular broadcast message to current channel
        send_message(self.sock, {
            "type": MSG_BROADCAST,
            "room": self.current_room,
            "content": text,
        })

    def _handle_slash_command(self, cmd_text: str):
        parts = cmd_text.split(" ", 2)
        cmd = parts[0].lower()

        if cmd == "/msg" or cmd == "/dm":
            if len(parts) < 3:
                self._append_message("SYSTEM", "Usage: /msg <username> <message>", "system")
                return
            target = parts[1]
            content = parts[2]
            send_message(self.sock, {
                "type": MSG_DIRECT,
                "target": target,
                "content": content,
            })

        elif cmd == "/join":
            if len(parts) < 2:
                self._append_message("SYSTEM", "Usage: /join <#room-name>", "system")
                return
            room = parts[1]
            if not room.startswith("#"):
                room = "#" + room
            self.current_room = room
            self.room_title_label.config(text=room)
            send_message(self.sock, {"type": MSG_ROOM_JOIN, "room": room})

        elif cmd == "/users":
            send_message(self.sock, {"type": MSG_USER_LIST})

        elif cmd == "/quit" or cmd == "/exit":
            self.on_closing()

        elif cmd == "/help":
            help_text = (
                "--- PeerWire Commands ---\n"
                "/msg <user> <text> : Send private direct message\n"
                "/join <#channel>   : Switch channel\n"
                "/users             : Refresh online users list\n"
                "/quit              : Cleanly disconnect from server\n"
                "Or simply type and press Enter to chat in the active channel!"
            )
            self._append_message("SYSTEM", help_text, "system")
        else:
            self._append_message("SYSTEM", f"Unknown command '{cmd}'. Type /help for list.", "system")

    def _on_room_select(self, event):
        selection = self.channels_listbox.curselection()
        if selection:
            room = self.channels_listbox.get(selection[0])
            if room != self.current_room:
                self.current_room = room
                self.room_title_label.config(text=room)
                send_message(self.sock, {"type": MSG_ROOM_JOIN, "room": room})

    def _on_user_double_click(self, event):
        selection = self.users_listbox.curselection()
        if selection:
            entry = self.users_listbox.get(selection[0])
            # entry is formatted as "Alice (Port 52182)"
            target = entry.split(" ")[0]
            if target != self.username:
                self.entry_message.delete(0, tk.END)
                self.entry_message.insert(0, f"/msg {target} ")
                self.entry_message.focus()

    # --------------------------------------------------------------------------
    # BACKGROUND SOCKET RECEIVER LOOP (Thread-Safe UI Updating)
    # --------------------------------------------------------------------------
    def _socket_receiver_loop(self):
        """Dedicated thread listening for incoming TCP frames."""
        while self.connected and self.sock:
            try:
                msg = recv_message(self.sock)
                if msg is None:
                    # TCP FIN received
                    self.root.after(0, self._handle_disconnect, "Server closed the connection (TCP FIN).")
                    break

                self.root.after(0, self._process_incoming_message, msg)
            except Exception as e:
                self.root.after(0, self._handle_disconnect, f"TCP Socket Error: {e}")
                break

    def _process_incoming_message(self, msg: dict):
        msg_type = msg.get("type")

        if msg_type == MSG_BROADCAST:
            sender = msg.get("sender")
            content = msg.get("content")
            timestamp = msg.get("timestamp", datetime.now().strftime("%H:%M:%S"))
            tag = "self" if sender == self.username else "peer"
            self._append_message(f"[{timestamp}] {sender}:", f" {content}", tag)

        elif msg_type == MSG_DIRECT:
            sender = msg.get("sender")
            target = msg.get("target")
            content = msg.get("content")
            timestamp = msg.get("timestamp", datetime.now().strftime("%H:%M:%S"))
            is_echo = msg.get("is_echo", False)
            
            if is_echo:
                header = f"[{timestamp}] [DM to {target}]:"
            else:
                header = f"[{timestamp}] [DM from {sender}]:"
            self._append_message(header, f" {content}", "dm")

        elif msg_type == MSG_SYSTEM:
            content = msg.get("content", "")
            self._append_message("SYSTEM:", f" {content}", "system")

        elif msg_type == MSG_USER_LIST:
            users = msg.get("users", [])
            self.users_listbox.delete(0, tk.END)
            for u in users:
                uname = u.get("username")
                port = u.get("port")
                display = f"{uname} (Port {port})" if uname != self.username else f"{uname} (You)"
                self.users_listbox.insert(tk.END, display)

    def _append_message(self, header: str, body: str, tag: str):
        self.chat_display.config(state="normal")
        self.chat_display.insert(tk.END, header, tag)
        self.chat_display.insert(tk.END, body + "\n", "body")
        self.chat_display.see(tk.END)
        self.chat_display.config(state="disabled")

    def _handle_disconnect(self, reason: str):
        self.connected = False
        if hasattr(self, "status_badge"):
            self.status_badge.config(text="TCP: DISCONNECTED (Socket Closed)", fg="#F38BA8")
        self._append_message("DISCONNECTED:", f" {reason}", "system")
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def on_closing(self):
        """Handles user clicking the window close (X) button."""
        if self.sock and self.connected:
            try:
                send_message(self.sock, {"type": MSG_DISCONNECT})
                self.sock.close()
            except OSError:
                pass
        self.root.destroy()


def launch_gui():
    root = tk.Tk()
    app = PeerWireGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
