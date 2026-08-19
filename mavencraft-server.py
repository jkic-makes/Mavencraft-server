"""
mavencraft-server.py

The authoritative game server process. Run directly with Python, or
launched/controlled by mavencraft-serverclient.exe.

FIRST BOOT:
  Asks for:
    - Server display name  (shown in the in-game multiplayer list)
    - Fake domain           (e.g. "bob-survival" or "sub.example.com" -
                              just a Firebase key, no real DNS registration)
    - RAM allocation (MB)   (used to size world caches / entity limits)
  Then detects your public IP, writes a record to Firebase, and starts
  listening for player connections on the configured port.

  Requires port forwarding on your router (TCP on the chosen port,
  default 25565) pointed at this machine. See PORT_FORWARDING.md.

SUBSEQUENT BOOTS:
  Reads config.json and skips the wizard. Delete config.json (or run
  with --reconfigure) to redo the wizard.
"""

from __future__ import annotations

import json
import os
import re
import socket
import sys
import time
import threading
from pathlib import Path
from typing import Optional

from firebase_client import FirebaseClient, FirebaseError

CONFIG_PATH = Path(__file__).parent / "config.json"
DEFAULT_PORT = 25565
HEARTBEAT_INTERVAL_SEC = 15

# --- Fill these in once for your Firebase project, or set as env vars ---
FIREBASE_DATABASE_URL = os.environ.get("MAVENCRAFT_FIREBASE_URL", "")
FIREBASE_AUTH_SECRET = os.environ.get("MAVENCRAFT_FIREBASE_SECRET", "")

# Allows letters, numbers, dashes, dots (so "sub.example.com" is fine as *input*)
DOMAIN_INPUT_RE = re.compile(r"^[a-z0-9](?:[a-z0-9\-\.]{0,61}[a-z0-9])?$")


def slugify_domain(raw: str) -> str:
    """Firebase RTDB keys can't contain '.', '#', '$', '[', ']', '/'.
    We keep the original for display but store a safe key."""
    return raw.strip().lower().replace(".", "-dot-")


def validate_domain(raw: str) -> Optional[str]:
    raw = raw.strip().lower()
    if not raw:
        return "Domain can't be empty."
    if len(raw) > 63:
        return "Keep it under 63 characters."
    if not DOMAIN_INPUT_RE.match(raw):
        return "Use only lowercase letters, numbers, dashes, and dots."
    return None


def get_public_ip() -> str:
    """Ask a couple of external services what our public IP is.
    Falls back gracefully if offline (useful for local LAN testing)."""
    import urllib.request

    for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                ip = resp.read().decode().strip()
                if ip:
                    return ip
        except Exception:
            continue
    print("[WARN] Couldn't detect public IP automatically (are you offline?).")
    return input("Enter your public IP manually (check whatismyip.com): ").strip()


def prompt_ram_mb() -> int:
    while True:
        raw = input("RAM to allocate in MB (e.g. 1024, 2048, 4096) [2048]: ").strip()
        if not raw:
            return 2048
        try:
            val = int(raw)
            if val < 256:
                print("  Minimum is 256 MB.")
                continue
            return val
        except ValueError:
            print("  Enter a whole number.")


def run_setup_wizard(firebase: FirebaseClient) -> dict:
    print("=" * 60)
    print(" MavenCraft Server - First Time Setup")
    print("=" * 60)
    print()
    print("This will register your server so it shows up in players'")
    print("multiplayer menu under a name you choose. No real domain")
    print("registration needed - just pick something unique.")
    print()

    # --- Server display name ---
    display_name = ""
    while not display_name:
        display_name = input("Server name (shown in multiplayer list): ").strip()
        if not display_name:
            print("  Can't be blank.")

    # --- Fake domain ---
    domain_key = None
    while domain_key is None:
        raw_domain = input(
            "Choose a fake domain (e.g. 'bob-survival' or 'sub.example.com'): "
        ).strip()
        err = validate_domain(raw_domain)
        if err:
            print(f"  {err}")
            continue

        candidate_key = slugify_domain(raw_domain)
        try:
            taken = firebase.domain_exists(candidate_key)
        except FirebaseError as e:
            print(f"  [WARN] Couldn't check availability ({e}). Proceeding anyway.")
            taken = False

        if taken:
            print(f"  '{raw_domain}' is already taken. Try another.")
            continue

        domain_key = candidate_key
        domain_display = raw_domain

    # --- RAM ---
    ram_mb = prompt_ram_mb()

    # --- Port ---
    port_raw = input(f"Port to host on [{DEFAULT_PORT}]: ").strip()
    port = int(port_raw) if port_raw else DEFAULT_PORT

    print()
    print("Detecting your public IP address...")
    public_ip = get_public_ip()
    print(f"  Public IP: {public_ip}")
    print()
    print("!" * 60)
    print(" IMPORTANT: Players can only connect if port", port, "is")
    print(" forwarded to THIS computer on your router. See")
    print(" PORT_FORWARDING.md for a step-by-step guide.")
    print("!" * 60)
    print()

    config = {
        "display_name": display_name,
        "domain_key": domain_key,
        "domain_display": domain_display,
        "ram_mb": ram_mb,
        "port": port,
        "game_mode_default": "SURVIVAL",
    }

    CONFIG_PATH.write_text(json.dumps(config, indent=2))
    print(f"Saved config to {CONFIG_PATH}")
    print()

    # NOTE ON RACE CONDITIONS:
    # Between the domain_exists() check above and this register_domain()
    # call, another server could theoretically grab the same name if two
    # people set up at the exact same moment. For a hobby project this is
    # an acceptable risk; a production version should use a Firebase
    # Transaction (PUT with If-Match / RTDB transaction endpoint) to make
    # the check-and-set atomic.
    register_with_firebase(firebase, config, public_ip)

    return config


def register_with_firebase(firebase: FirebaseClient, config: dict, public_ip: str) -> None:
    record = {
        "displayName": config["display_name"],
        "ip": public_ip,
        "port": config["port"],
        "ram_mb": config["ram_mb"],
        "mode": config["game_mode_default"],
        "players_online": 0,
        "players_max": max(1, config["ram_mb"] // 256),  # rough heuristic
        "last_heartbeat": int(time.time()),
        "alive": True,
    }
    try:
        firebase.register_domain(config["domain_key"], record)
        print(f"Registered as '{config['domain_display']}' on Firebase.")
    except FirebaseError as e:
        print(f"[WARN] Could not register with Firebase: {e}")
        print("Your server will run, but won't appear in players' multiplayer list.")
        print("Players can still connect directly via IP if you share it manually.")


def heartbeat_loop(firebase: FirebaseClient, config: dict, get_player_count):
    while True:
        try:
            firebase.heartbeat(config["domain_key"], get_player_count())
        except FirebaseError as e:
            print(f"[WARN] Heartbeat failed: {e}")
        time.sleep(HEARTBEAT_INTERVAL_SEC)


def load_config() -> Optional[dict]:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except json.JSONDecodeError:
            print("[WARN] config.json is corrupted, running setup again.")
            return None
    return None


def main():
    reconfigure = "--reconfigure" in sys.argv

    if not FIREBASE_DATABASE_URL:
        print("[WARN] MAVENCRAFT_FIREBASE_URL is not set.")
        print("       Set it as an environment variable, e.g.:")
        print("       export MAVENCRAFT_FIREBASE_URL=https://your-project-default-rtdb.firebaseio.com")
        print("       Continuing in OFFLINE mode (no multiplayer listing).")
        firebase = None
    else:
        firebase = FirebaseClient(FIREBASE_DATABASE_URL, FIREBASE_AUTH_SECRET or None)

    config = None if reconfigure else load_config()

    if config is None:
        if firebase is None:
            print("Cannot run setup wizard without Firebase configured. Exiting.")
            sys.exit(1)
        config = run_setup_wizard(firebase)
    else:
        print(f"Loaded existing config for '{config['display_name']}' "
              f"({config['domain_display']}).")
        if firebase is not None:
            # Re-register on every boot in case public IP changed (common
            # with residential ISPs / dynamic IP).
            register_with_firebase(firebase, config, get_public_ip())

    player_count = 0
    player_count_lock = threading.Lock()

    def get_player_count():
        with player_count_lock:
            return player_count

    if firebase is not None:
        hb_thread = threading.Thread(
            target=heartbeat_loop, args=(firebase, config, get_player_count), daemon=True
        )
        hb_thread.start()

    print()
    print(f"Listening on port {config['port']}... (Ctrl+C to stop)")
    print("Game networking loop not yet implemented in this prototype -")
    print("this script currently only handles the Firebase registration side.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down, unregistering from Firebase...")
        if firebase is not None:
            try:
                firebase.unregister_domain(config["domain_key"])
            except FirebaseError:
                pass
        print("Bye.")


if __name__ == "__main__":
    main()
