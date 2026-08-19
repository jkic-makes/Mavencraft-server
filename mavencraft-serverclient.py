"""
mavencraft-serverclient.py

A small Tkinter control panel for mavencraft-server.py. Launches the
server as a subprocess, streams its console output into a log window,
and lets you send text back to it (needed for the first-boot wizard,
which asks questions via input()).

Run it with:
    python mavencraft-serverclient.py

It looks for mavencraft-server.py in the same folder by default.
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
SERVER_SCRIPT = SCRIPT_DIR / "mavencraft-server.py"


class ServerClientApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MavenCraft Server Client")
        self.geometry("760x520")
        self.minsize(560, 360)

        self.process: subprocess.Popen | None = None
        self.output_queue: queue.Queue[str] = queue.Queue()
        self.reader_thread: threading.Thread | None = None

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Poll the output queue regularly and flush it into the log widget.
        self.after(80, self._drain_output_queue)

        if not SERVER_SCRIPT.exists():
            messagebox.showerror(
                "mavencraft-server.py not found",
                f"Expected to find it at:\n{SERVER_SCRIPT}\n\n"
                "Place mavencraft-serverclient.py in the same folder as "
                "mavencraft-server.py.",
            )
        else:
            # Auto-start on open.
            self.start_server()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        top_bar = tk.Frame(self, padx=8, pady=8)
        top_bar.pack(fill=tk.X)

        self.status_label = tk.Label(
            top_bar, text="Status: Stopped", font=("Segoe UI", 11, "bold"), fg="#a33"
        )
        self.status_label.pack(side=tk.LEFT)

        btn_frame = tk.Frame(top_bar)
        btn_frame.pack(side=tk.RIGHT)

        self.start_btn = tk.Button(btn_frame, text="Start", width=10, command=self.start_server)
        self.start_btn.pack(side=tk.LEFT, padx=4)

        self.stop_btn = tk.Button(btn_frame, text="Stop", width=10, command=self.stop_server)
        self.stop_btn.pack(side=tk.LEFT, padx=4)

        self.restart_btn = tk.Button(btn_frame, text="Restart", width=10, command=self.restart_server)
        self.restart_btn.pack(side=tk.LEFT, padx=4)

        self.reconfigure_var = tk.BooleanVar(value=False)
        reconfigure_check = tk.Checkbutton(
            btn_frame, text="Reconfigure on next start", variable=self.reconfigure_var
        )
        reconfigure_check.pack(side=tk.LEFT, padx=8)

        # --- Log output ---
        log_frame = tk.Frame(self, padx=8, pady=(0, 8))
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, state="disabled", wrap=tk.WORD, bg="#111", fg="#ddd",
            insertbackground="#ddd", font=("Consolas", 10)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.tag_config("stderr", foreground="#ff8080")
        self.log_text.tag_config("system", foreground="#7fd0ff")

        # --- Input line (answers wizard prompts, sends commands) ---
        input_frame = tk.Frame(self, padx=8, pady=(0, 8))
        input_frame.pack(fill=tk.X)

        tk.Label(input_frame, text="Send to server:").pack(side=tk.LEFT)

        self.input_entry = tk.Entry(input_frame)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        self.input_entry.bind("<Return>", lambda e: self.send_input())

        send_btn = tk.Button(input_frame, text="Send", command=self.send_input)
        send_btn.pack(side=tk.LEFT)

        self._update_button_states()

    # ------------------------------------------------------------------
    # Process control
    # ------------------------------------------------------------------

    def start_server(self):
        if self.process is not None and self.process.poll() is None:
            self._log("Server is already running.", tag="system")
            return

        if not SERVER_SCRIPT.exists():
            messagebox.showerror("Missing file", f"Can't find {SERVER_SCRIPT}")
            return

        args = [sys.executable, str(SERVER_SCRIPT)]
        if self.reconfigure_var.get():
            args.append("--reconfigure")
            self.reconfigure_var.set(False)

        self._log(f"Starting: {' '.join(args)}", tag="system")

        try:
            self.process = subprocess.Popen(
                args,
                cwd=str(SCRIPT_DIR),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env={**os.environ},
            )
        except OSError as e:
            self._log(f"Failed to start server: {e}", tag="stderr")
            messagebox.showerror("Failed to start", str(e))
            return

        self.reader_thread = threading.Thread(
            target=self._read_process_output, daemon=True
        )
        self.reader_thread.start()

        self._set_status_running()
        self._update_button_states()

    def stop_server(self):
        if self.process is None or self.process.poll() is not None:
            self._log("Server isn't running.", tag="system")
            self._set_status_stopped()
            self._update_button_states()
            return

        self._log("Stopping server (sending Ctrl+C equivalent)...", tag="system")
        try:
            self.process.terminate()
            try:
                self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self._log("Server didn't exit in time, killing it.", tag="stderr")
                self.process.kill()
        except Exception as e:
            self._log(f"Error stopping server: {e}", tag="stderr")

        self._set_status_stopped()
        self._update_button_states()

    def restart_server(self):
        self._log("Restarting...", tag="system")
        self.stop_server()
        self.after(400, self.start_server)

    def send_input(self):
        text = self.input_entry.get()
        self.input_entry.delete(0, tk.END)

        if self.process is None or self.process.poll() is not None:
            self._log("Can't send input, server isn't running.", tag="stderr")
            return
        if self.process.stdin is None:
            return

        try:
            self.process.stdin.write(text + "\n")
            self.process.stdin.flush()
            self._log(f"> {text}", tag="system")
        except (BrokenPipeError, OSError) as e:
            self._log(f"Couldn't send input: {e}", tag="stderr")

    # ------------------------------------------------------------------
    # Output streaming
    # ------------------------------------------------------------------

    def _read_process_output(self):
        """Runs in a background thread. Reads stdout and stderr from the
        subprocess and pushes lines onto a thread-safe queue; the Tk main
        loop drains that queue on a timer (Tkinter widgets aren't safe to
        touch directly from a non-GUI thread)."""
        proc = self.process
        if proc is None:
            return

        def pump(stream, tag):
            if stream is None:
                return
            for line in iter(stream.readline, ""):
                self.output_queue.put((line.rstrip("\n"), tag))
            stream.close()

        stdout_thread = threading.Thread(target=pump, args=(proc.stdout, None), daemon=True)
        stderr_thread = threading.Thread(target=pump, args=(proc.stderr, "stderr"), daemon=True)
        stdout_thread.start()
        stderr_thread.start()

        proc.wait()
        stdout_thread.join(timeout=2)
        stderr_thread.join(timeout=2)

        self.output_queue.put((f"[Process exited with code {proc.returncode}]", "system"))
        self.output_queue.put(("__PROCESS_ENDED__", None))

    def _drain_output_queue(self):
        try:
            while True:
                line, tag = self.output_queue.get_nowait()
                if line == "__PROCESS_ENDED__":
                    self._set_status_stopped()
                    self._update_button_states()
                    continue
                self._log(line, tag=tag)
        except queue.Empty:
            pass
        finally:
            self.after(80, self._drain_output_queue)

    def _log(self, text: str, tag: str | None = None):
        self.log_text.configure(state="normal")
        if tag:
            self.log_text.insert(tk.END, text + "\n", tag)
        else:
            self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # Status / button state helpers
    # ------------------------------------------------------------------

    def _set_status_running(self):
        self.status_label.config(text="Status: Running", fg="#3a3")

    def _set_status_stopped(self):
        self.status_label.config(text="Status: Stopped", fg="#a33")

    def _update_button_states(self):
        running = self.process is not None and self.process.poll() is None
        self.start_btn.config(state=tk.DISABLED if running else tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL if running else tk.DISABLED)
        self.restart_btn.config(state=tk.NORMAL if running else tk.DISABLED)

    # ------------------------------------------------------------------

    def _on_close(self):
        if self.process is not None and self.process.poll() is None:
            if not messagebox.askyesno(
                "Server is running",
                "The server is still running. Stop it and quit?",
            ):
                return
            self.stop_server()
        self.destroy()


if __name__ == "__main__":
    app = ServerClientApp()
    app.mainloop()