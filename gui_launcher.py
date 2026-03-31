#!/usr/bin/env python3
from __future__ import annotations

import json
import queue
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk


ROOT_DIR = Path(__file__).resolve().parent
STATE_FILE = ROOT_DIR / ".gui_launcher_state.json"
START_DELAY_SECONDS = 2.0
REFRESH_INTERVAL_MS = 2000
SSH_CONNECT_TIMEOUT = 8
CARD_LOG_HEIGHT = 6


@dataclass
class ComponentSpec:
    kind: str
    idx: int

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.idx}"

    @property
    def label(self) -> str:
        if self.kind == "generator":
            return "GENERATOR"
        return f"{self.kind.upper()} {self.idx}"

    @property
    def command(self) -> str:
        if self.kind == "generator":
            return "python3 main.py generator"
        return f"python3 main.py {self.kind} {self.idx}"


@dataclass
class ComponentState:
    ip: str = ""
    workdir: str = ""
    status: str = "idle"
    pid: str = ""
    last_message: str = ""
    output: list[str] = field(default_factory=list)


class ParametersConfigReader:
    COUNT_PATTERNS = {
        "rx_count": re.compile(r"\brx_count\s*:\s*int\s*=\s*(\d+)"),
        "ris_count": re.compile(r"\bris_count\s*:\s*int\s*=\s*(\d+)"),
    }
    IP_PATTERNS = {
        "generator_ip_address": re.compile(r"\bgenerator_ip_address\s*:\s*str\s*=\s*[\"']([^\"']+)[\"']"),
        "system_controller_ip_address": re.compile(r"\bsystem_controller_ip_address\s*:\s*str\s*=\s*[\"']([^\"']+)[\"']"),
    }

    @classmethod
    def read_config(cls, file_path: Path) -> dict[str, Any]:
        content = file_path.read_text(encoding="utf-8")
        result: dict[str, Any] = {}

        for key, pattern in cls.COUNT_PATTERNS.items():
            match = pattern.search(content)
            if not match:
                raise ValueError(f"Nie znaleziono pola {key} w {file_path}")
            result[key] = int(match.group(1))

        for key, pattern in cls.IP_PATTERNS.items():
            match = pattern.search(content)
            result[key] = match.group(1) if match else ""

        return result


class StateStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class LauncherGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ContRIS GUI Launcher")
        self.geometry("1600x980")
        self.minsize(1260, 760)
        self.configure(bg="#eef2f7")

        self.store = StateStore(STATE_FILE)
        self.persisted = self.store.load()
        self.specs: list[ComponentSpec] = []
        self.component_state: dict[str, ComponentState] = {}
        self.cards: dict[str, dict[str, Any]] = {}
        self.events: queue.Queue[tuple[str, str, str]] = queue.Queue()
        self.parameters_mtime: float | None = None

        persisted_repo = self.persisted.get("repo_dir", "")
        self.repo_dir_var = tk.StringVar(value=persisted_repo or str(ROOT_DIR))
        self.system_ip_var = tk.StringVar(value=self.persisted.get("system_ip", ""))
        self.delay_var = tk.StringVar(value=str(self.persisted.get("start_delay_seconds", START_DELAY_SECONDS)))
        self.auto_scroll_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Gotowy")
        self.summary_var = tk.StringVar(value="Brak aktywnych procesów")

        self._configure_styles()
        self._build_layout()
        self._reload_specs(force=True)
        self.after(300, self._drain_events)
        self.after(REFRESH_INTERVAL_MS, self._watch_parameters_file)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("App.TFrame", background="#eef2f7")
        style.configure("Panel.TFrame", background="#ffffff")
        style.configure("Header.TLabel", font=("Segoe UI", 18, "bold"), background="#eef2f7", foreground="#14213d")
        style.configure("SubHeader.TLabel", font=("Segoe UI", 10), background="#eef2f7", foreground="#526071")
        style.configure("Card.TLabelframe", background="#ffffff", borderwidth=1, relief="solid")
        style.configure("Card.TLabelframe.Label", font=("Segoe UI", 11, "bold"), background="#ffffff", foreground="#14213d")
        style.configure("Key.TLabel", background="#ffffff", foreground="#526071", font=("Segoe UI", 9, "bold"))
        style.configure("Value.TLabel", background="#ffffff", foreground="#111827", font=("Segoe UI", 10))
        style.configure("StatusIdle.TLabel", background="#ffffff", foreground="#6b7280", font=("Segoe UI", 10, "bold"))
        style.configure("StatusStarting.TLabel", background="#ffffff", foreground="#b45309", font=("Segoe UI", 10, "bold"))
        style.configure("StatusStarted.TLabel", background="#ffffff", foreground="#047857", font=("Segoe UI", 10, "bold"))
        style.configure("StatusError.TLabel", background="#ffffff", foreground="#b91c1c", font=("Segoe UI", 10, "bold"))
        style.configure("StatusStopped.TLabel", background="#ffffff", foreground="#1d4ed8", font=("Segoe UI", 10, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=(12, 8))
        style.configure("Small.TButton", font=("Segoe UI", 9), padding=(10, 5))
        style.configure("Summary.TLabel", background="#eef2f7", foreground="#1f2937", font=("Segoe UI", 10, "bold"))

    def _build_layout(self) -> None:
        root = ttk.Frame(self, style="App.TFrame", padding=14)
        root.pack(fill="both", expand=True)
        root.rowconfigure(3, weight=1)
        root.columnconfigure(0, weight=1)

        header = ttk.Frame(root, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="ContRIS Control Panel", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Dynamiczne GUI dla generatora, RIS i RX. Konfiguracja czytana z helpers/parameters.py",
            style="SubHeader.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 10))

        top = ttk.Frame(root, style="Panel.TFrame", padding=14)
        top.grid(row=1, column=0, sticky="ew")
        for col in range(6):
            top.columnconfigure(col, weight=1 if col in (1, 4) else 0)

        ttk.Label(top, text="Repo dir", style="Key.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.repo_dir_var).grid(row=0, column=1, columnspan=2, sticky="ew", padx=(8, 10))
        ttk.Button(top, text="Git Pull", style="Accent.TButton", command=self.git_pull).grid(row=0, column=3, padx=6)
        ttk.Button(top, text="Reload config", style="Small.TButton", command=lambda: self._reload_specs(force=True)).grid(row=0, column=4, sticky="w")

        ttk.Label(top, text="System IP", style="Key.TLabel").grid(row=1, column=0, sticky="w", pady=(12, 0))
        ttk.Entry(top, textvariable=self.system_ip_var).grid(row=1, column=1, sticky="ew", padx=(8, 10), pady=(12, 0))
        ttk.Label(top, text="Start-all delay [s]", style="Key.TLabel").grid(row=1, column=2, sticky="e", pady=(12, 0))
        ttk.Entry(top, textvariable=self.delay_var, width=10).grid(row=1, column=3, sticky="w", pady=(12, 0))
        ttk.Checkbutton(top, text="Auto-scroll log", variable=self.auto_scroll_var).grid(row=1, column=4, sticky="w", pady=(12, 0))

        actions = ttk.Frame(root, style="App.TFrame", padding=(0, 12, 0, 10))
        actions.grid(row=2, column=0, sticky="ew")
        ttk.Button(actions, text="Start Main (system)", style="Accent.TButton", command=self.start_main).pack(side="left")
        ttk.Button(actions, text="Start All", style="Accent.TButton", command=self.start_all).pack(side="left", padx=8)
        ttk.Button(actions, text="Stop All", style="Small.TButton", command=self.stop_all).pack(side="left")
        ttk.Label(actions, textvariable=self.summary_var, style="Summary.TLabel").pack(side="right")

        content = ttk.Frame(root, style="App.TFrame")
        content.grid(row=3, column=0, sticky="nsew")
        content.rowconfigure(0, weight=1)
        content.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(content, bg="#eef2f7", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(content, orient="vertical", command=self.canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.cards_container = ttk.Frame(self.canvas, style="App.TFrame")
        self.cards_window = self.canvas.create_window((0, 0), window=self.cards_container, anchor="nw")

        self.cards_container.bind("<Configure>", self._on_cards_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        status_bar = ttk.Label(root, textvariable=self.status_var, anchor="w", relief="sunken")
        status_bar.grid(row=4, column=0, sticky="ew", pady=(8, 0))

    def _on_cards_configure(self, _: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfig(self.cards_window, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> None:
        try:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    def _repo_dir(self) -> Path:
        return Path(self.repo_dir_var.get().strip()).expanduser().resolve()

    def _status_style(self, text: str) -> str:
        normalized = text.lower()
        if normalized.startswith("started"):
            return "StatusStarted.TLabel"
        if normalized.startswith("starting") or normalized.startswith("stopping"):
            return "StatusStarting.TLabel"
        if normalized.startswith("error"):
            return "StatusError.TLabel"
        if normalized.startswith("stopped"):
            return "StatusStopped.TLabel"
        return "StatusIdle.TLabel"

    def _save_global_state(self) -> None:
        data = {
            "repo_dir": self.repo_dir_var.get().strip(),
            "system_ip": self.system_ip_var.get().strip(),
            "start_delay_seconds": self.delay_var.get().strip(),
            "components": {
                key: {
                    "ip": state.ip,
                    "workdir": state.workdir,
                }
                for key, state in self.component_state.items()
            },
        }
        self.store.save(data)

    def _reload_specs(self, force: bool = False) -> None:
        repo_dir = self._repo_dir()
        params_path = repo_dir / "helpers" / "parameters.py"

        if not params_path.exists():
            params_path = repo_dir / "ris_system-final" / "helpers" / "parameters.py"
        if not params_path.exists():
            messagebox.showerror("Błąd", f"Nie znaleziono pliku: {params_path}")
            return

        try:
            config = ParametersConfigReader.read_config(params_path)
        except Exception as exc:
            messagebox.showerror("Błąd konfiguracji", str(exc))
            return

        if not self.system_ip_var.get().strip() and config.get("system_controller_ip_address"):
            self.system_ip_var.set(config["system_controller_ip_address"])

        new_specs = [ComponentSpec("generator", 0)]
        new_specs += [ComponentSpec("ris", i) for i in range(config["ris_count"])]
        new_specs += [ComponentSpec("rx", i) for i in range(config["rx_count"])]

        if not force and [s.key for s in new_specs] == [s.key for s in self.specs]:
            return

        self.specs = new_specs
        old_components = self.persisted.get("components", {})
        for spec in self.specs:
            if spec.key not in self.component_state:
                state = ComponentState()
                if spec.key in old_components:
                    state.ip = old_components[spec.key].get("ip", "")
                    state.workdir = old_components[spec.key].get("workdir", "")
                elif spec.kind == "generator" and config.get("generator_ip_address"):
                    state.ip = config["generator_ip_address"]
                    state.workdir = str(repo_dir)
                else:
                    state.workdir = str(repo_dir)
                self.component_state[spec.key] = state
            elif spec.kind == "generator" and not self.component_state[spec.key].ip and config.get("generator_ip_address"):
                self.component_state[spec.key].ip = config["generator_ip_address"]

        for child in self.cards_container.winfo_children():
            child.destroy()
        self.cards.clear()

        for index, spec in enumerate(self.specs):
            row = index // 2
            col = index % 2
            self._create_component_card(spec, row, col)

        self.status_var.set(
            f"Załadowano konfigurację: generator=1, ris_count={config['ris_count']}, rx_count={config['rx_count']}"
        )
        self._refresh_summary()
        self._save_global_state()

    def _create_component_card(self, spec: ComponentSpec, row: int, col: int) -> None:
        state = self.component_state[spec.key]
        frame = ttk.LabelFrame(self.cards_container, text=spec.label, style="Card.TLabelframe", padding=12)
        frame.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)
        self.cards_container.columnconfigure(col, weight=1)
        self.cards_container.rowconfigure(row, weight=1)

        ip_var = tk.StringVar(value=state.ip)
        workdir_var = tk.StringVar(value=state.workdir or str(self._repo_dir()))
        status_var = tk.StringVar(value=state.status)
        pid_var = tk.StringVar(value=state.pid)
        command_var = tk.StringVar(value=spec.command)

        ttk.Label(frame, text="IP hosta", style="Key.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=ip_var).grid(row=0, column=1, columnspan=3, sticky="ew", padx=(8, 0))

        ttk.Label(frame, text="Remote dir", style="Key.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frame, textvariable=workdir_var).grid(row=1, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=(8, 0))

        ttk.Label(frame, text="Komenda", style="Key.TLabel").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frame, textvariable=command_var, state="readonly").grid(row=2, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=(8, 0))

        ttk.Label(frame, text="Status", style="Key.TLabel").grid(row=3, column=0, sticky="w", pady=(10, 0))
        status_label = ttk.Label(frame, textvariable=status_var, style=self._status_style(status_var.get()))
        status_label.grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(10, 0))
        ttk.Label(frame, text="PID", style="Key.TLabel").grid(row=3, column=2, sticky="e", pady=(10, 0))
        ttk.Label(frame, textvariable=pid_var, style="Value.TLabel").grid(row=3, column=3, sticky="w", padx=(8, 0), pady=(10, 0))

        btns = ttk.Frame(frame, style="Panel.TFrame")
        btns.grid(row=4, column=0, columnspan=4, sticky="w", pady=(12, 8))
        ttk.Button(btns, text="Start", style="Accent.TButton", command=lambda s=spec: self.start_component(s)).pack(side="left")
        ttk.Button(btns, text="Stop", style="Small.TButton", command=lambda s=spec: self.stop_component(s)).pack(side="left", padx=8)
        ttk.Button(btns, text="Clear log", style="Small.TButton", command=lambda s=spec: self.clear_log(s)).pack(side="left")

        log_widget = scrolledtext.ScrolledText(
            frame,
            height=CARD_LOG_HEIGHT,
            wrap="word",
            font=("Consolas", 9),
            bg="#f8fafc",
            fg="#0f172a",
            relief="solid",
            borderwidth=1,
        )
        log_widget.grid(row=5, column=0, columnspan=4, sticky="nsew", pady=(4, 0))
        frame.rowconfigure(5, weight=1)
        for c in range(4):
            frame.columnconfigure(c, weight=1)

        if state.output:
            log_widget.insert("end", "".join(state.output))
            log_widget.see("end")

        def persist_vars(*_: Any) -> None:
            current = self.component_state[spec.key]
            current.ip = ip_var.get().strip()
            current.workdir = workdir_var.get().strip()
            self._save_global_state()

        ip_var.trace_add("write", persist_vars)
        workdir_var.trace_add("write", persist_vars)

        self.cards[spec.key] = {
            "frame": frame,
            "ip_var": ip_var,
            "workdir_var": workdir_var,
            "status_var": status_var,
            "pid_var": pid_var,
            "status_label": status_label,
            "command_var": command_var,
            "log_widget": log_widget,
        }

    def _refresh_summary(self) -> None:
        started = sum(1 for state in self.component_state.values() if state.status.startswith("started"))
        total = len(self.specs)
        self.summary_var.set(f"Aktywne: {started}/{total}")

    def _set_component_status(self, spec: ComponentSpec, status: str, msg: str = "", pid: str = "") -> None:
        state = self.component_state[spec.key]
        state.status = status
        state.last_message = msg
        if pid or status.startswith("stopped"):
            state.pid = pid
        shown = status if not msg else f"{status} | {msg}"
        if spec.key in self.cards:
            self.cards[spec.key]["status_var"].set(shown)
            self.cards[spec.key]["pid_var"].set(state.pid)
            self.cards[spec.key]["status_label"].configure(style=self._status_style(status))
        self._refresh_summary()

    def _append_log(self, spec: ComponentSpec, text: str) -> None:
        state = self.component_state[spec.key]
        state.output.append(text)
        if spec.key in self.cards:
            widget = self.cards[spec.key]["log_widget"]
            widget.insert("end", text)
            if self.auto_scroll_var.get():
                widget.see("end")

    def clear_log(self, spec: ComponentSpec) -> None:
        self.component_state[spec.key].output.clear()
        if spec.key in self.cards:
            widget = self.cards[spec.key]["log_widget"]
            widget.delete("1.0", "end")

    def _run_background(self, target, *args) -> None:
        thread = threading.Thread(target=target, args=args, daemon=True)
        thread.start()

    def _drain_events(self) -> None:
        while True:
            try:
                event_type, key, payload = self.events.get_nowait()
            except queue.Empty:
                break

            spec = next((s for s in self.specs if s.key == key), None)
            if spec is None:
                continue

            if event_type == "log":
                self._append_log(spec, payload)
            elif event_type == "status":
                data = json.loads(payload)
                self._set_component_status(spec, data["status"], data.get("message", ""), data.get("pid", ""))

        self.after(300, self._drain_events)

    def _emit_log(self, spec: ComponentSpec, text: str) -> None:
        self.events.put(("log", spec.key, text))

    def _emit_status(self, spec: ComponentSpec, status: str, message: str = "", pid: str = "") -> None:
        self.events.put(("status", spec.key, json.dumps({"status": status, "message": message, "pid": pid})))

    def _watch_parameters_file(self) -> None:
        params_path = self._repo_dir() / "helpers" / "parameters.py"
        try:
            mtime = params_path.stat().st_mtime
            if self.parameters_mtime is None:
                self.parameters_mtime = mtime
            elif mtime != self.parameters_mtime:
                self.parameters_mtime = mtime
                self._reload_specs(force=True)
        except FileNotFoundError:
            pass
        self.after(REFRESH_INTERVAL_MS, self._watch_parameters_file)

    def _validate_component(self, spec: ComponentSpec) -> tuple[str, str]:
        card = self.cards[spec.key]
        ip = card["ip_var"].get().strip()
        workdir = card["workdir_var"].get().strip() or str(self._repo_dir())
        if not ip:
            raise ValueError(f"Brak IP dla {spec.label}")
        return ip, workdir

    def _ssh_command(self, ip: str, remote_cmd: str) -> list[str]:
        return [
            "ssh",
            "-o",
            f"ConnectTimeout={SSH_CONNECT_TIMEOUT}",
            "-o",
            "StrictHostKeyChecking=no",
            ip,
            remote_cmd,
        ]

    def _start_remote_component_worker(self, spec: ComponentSpec) -> None:
        try:
            ip, workdir = self._validate_component(spec)
        except Exception as exc:
            self._emit_status(spec, "error", str(exc))
            return

        cmd = spec.command
        remote_script = (
            f"cd {sh_quote(workdir)} && "
            f"nohup {cmd} > .launcher_{spec.kind}_{spec.idx}.log 2>&1 & echo $!"
        )

        self._emit_status(spec, "starting", f"SSH -> {ip}")
        self._emit_log(spec, f"\n[{timestamp()}] START {ip}: {cmd}\n")
        try:
            proc = subprocess.run(
                self._ssh_command(ip, remote_script),
                capture_output=True,
                text=True,
                check=False,
                timeout=20,
            )
        except Exception as exc:
            self._emit_status(spec, "error", str(exc))
            self._emit_log(spec, f"Błąd: {exc}\n")
            return

        if proc.returncode != 0:
            msg = (proc.stderr or proc.stdout or f"SSH exit={proc.returncode}").strip()
            self._emit_status(spec, "error", msg)
            self._emit_log(spec, f"SSH error: {msg}\n")
            return

        pid = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout.strip() else ""
        self._emit_status(spec, "started", "proces uruchomiony", pid)
        self._emit_log(spec, f"PID: {pid or 'unknown'}\n")

    def start_component(self, spec: ComponentSpec) -> None:
        self._run_background(self._start_remote_component_worker, spec)

    def _stop_remote_component_worker(self, spec: ComponentSpec) -> None:
        try:
            ip, workdir = self._validate_component(spec)
        except Exception as exc:
            self._emit_status(spec, "error", str(exc))
            return

        pattern = spec.command.replace("'", "")
        remote_script = f"cd {sh_quote(workdir)} && pkill -f {sh_quote(pattern)} || true"
        self._emit_status(spec, "stopping", f"SSH -> {ip}")
        self._emit_log(spec, f"\n[{timestamp()}] STOP {ip}: {pattern}\n")

        try:
            proc = subprocess.run(
                self._ssh_command(ip, remote_script),
                capture_output=True,
                text=True,
                check=False,
                timeout=20,
            )
        except Exception as exc:
            self._emit_status(spec, "error", str(exc))
            self._emit_log(spec, f"Błąd: {exc}\n")
            return

        if proc.returncode not in (0, 1):
            msg = (proc.stderr or proc.stdout or f"SSH exit={proc.returncode}").strip()
            self._emit_status(spec, "error", msg)
            self._emit_log(spec, f"SSH error: {msg}\n")
            return

        self.component_state[spec.key].pid = ""
        self._emit_status(spec, "stopped", "proces zatrzymany")

    def stop_component(self, spec: ComponentSpec) -> None:
        self._run_background(self._stop_remote_component_worker, spec)

    def start_main(self) -> None:
        repo_dir = self._repo_dir()
        ip = self.system_ip_var.get().strip()
        if not ip:
            messagebox.showerror("Błąd", "Brak System IP")
            return

        def worker() -> None:
            remote_script = f"cd {sh_quote(str(repo_dir))} && nohup python3 main.py > .launcher_system.log 2>&1 & echo $!"
            self.status_var.set(f"Start main przez SSH -> {ip}")
            try:
                proc = subprocess.run(
                    self._ssh_command(ip, remote_script),
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=20,
                )
            except Exception as exc:
                self.status_var.set(f"Błąd startu main: {exc}")
                return
            if proc.returncode != 0:
                self.status_var.set((proc.stderr or proc.stdout or "Błąd startu main").strip())
                return
            pid = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout.strip() else ""
            self.status_var.set(f"Main uruchomiony na {ip}, PID={pid or 'unknown'}")

        self._run_background(worker)

    def start_all(self) -> None:
        try:
            delay = float(self.delay_var.get().strip())
        except ValueError:
            messagebox.showerror("Błąd", "Niepoprawne opóźnienie")
            return

        def worker() -> None:
            ordered = [s for s in self.specs if s.kind == "generator"]
            ordered += [s for s in self.specs if s.kind == "ris"]
            ordered += [s for s in self.specs if s.kind == "rx"]
            for i, spec in enumerate(ordered):
                self._start_remote_component_worker(spec)
                if i < len(ordered) - 1:
                    time.sleep(delay)
            self.status_var.set("Sekwencja Start All zakończona")

        self._run_background(worker)

    def stop_all(self) -> None:
        def worker() -> None:
            for spec in self.specs:
                self._stop_remote_component_worker(spec)
            self.status_var.set("Sekwencja Stop All zakończona")

        self._run_background(worker)

    def git_pull(self) -> None:
        repo_dir = self._repo_dir()

        def worker() -> None:
            self.status_var.set(f"Git pull w {repo_dir}")
            proc = subprocess.run(
                ["git", "-C", str(repo_dir), "pull"],
                capture_output=True,
                text=True,
                check=False,
            )
            out = (proc.stdout or "") + (proc.stderr or "")
            if proc.returncode == 0:
                self.status_var.set("git pull zakończony poprawnie")
                messagebox.showinfo("Git Pull", out.strip() or "OK")
                self._reload_specs(force=True)
            else:
                self.status_var.set("git pull nie powiódł się")
                messagebox.showerror("Git Pull", out.strip() or f"exit={proc.returncode}")

        self._run_background(worker)

    def _on_close(self) -> None:
        self._save_global_state()
        self.destroy()


def timestamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def sh_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


if __name__ == "__main__":
    app = LauncherGUI()
    app.mainloop()
