# MavenCraft Server

Registers your MavenCraft world under a name you choose ("fake domain")
so it can be found in the game's multiplayer menu — without any real
domain registration. Actual player connections still require port
forwarding; see `PORT_FORWARDING.md`.

## Files in this folder

| File | What it is |
|---|---|
| `mavencraft-serverclient.py` | **Open this one.** Tkinter control panel — start/stop/restart the server, view its log, answer setup prompts. |
| `mavencraft-server.py` | The actual server process. Launched automatically by the control panel — you shouldn't need to run this directly. |
| `firebase_client.py` | Small helper the server uses to talk to Firebase. |
| `config.json` | Created after your first setup (server name, domain, RAM, port). Delete it, or use the "Reconfigure" option, to redo setup. |
| `PORT_FORWARDING.md` | Step-by-step router setup guide. |
| `requirements.txt` | Python dependencies. |

## 1. Create a free Firebase project (one-time)

1. Go to https://console.firebase.google.com and create a project (free tier is enough).
2. In the left sidebar: **Build → Realtime Database → Create Database**.
   - Choose any region.
   - Start in **test mode** for now (open read/write) — fine for a
     hobby project, but anyone can read/write your domain list while
     it's in test mode. Lock it down later with Database Rules if you
     care about that.
3. Copy your Database URL — it looks like:
   `https://your-project-id-default-rtdb.firebaseio.com`

## 2. Install dependencies

```bash
pip install -r requirements.txt
```

Tkinter (used by the control panel) ships with standard Python installs
on Windows and macOS. On Linux, if it's missing, install it separately,
e.g. `sudo apt install python3-tk` on Debian/Ubuntu.

## 3. Set your Firebase URL

```bash
export MAVENCRAFT_FIREBASE_URL="https://your-project-id-default-rtdb.firebaseio.com"
# Optional, only needed if you lock down your DB rules with a secret/auth token:
# export MAVENCRAFT_FIREBASE_SECRET="your-secret-or-id-token"
```

(Windows PowerShell: use `$env:MAVENCRAFT_FIREBASE_URL = "..."` instead of `export`.)

Set this in the same terminal/session you'll launch the control panel from.

## 4. Run it

**Open the control panel, not the server script directly:**

```bash
python mavencraft-serverclient.py
```

This opens a window and automatically starts `mavencraft-server.py` for
you in the background. Everything the server prints shows up in the log
box inside the window.

**First run:** the server runs its setup wizard, which asks questions
(server name, fake domain, RAM, port) via plain text prompts. Answer
them using the **"Send to server"** box at the bottom of the control
panel window — type your answer and hit Enter or click Send, just like
you would in a terminal.

It then detects your public IP and writes everything to Firebase.

**You still need to port forward** the chosen port to this machine —
follow `PORT_FORWARDING.md` or players won't be able to reach you.

**Subsequent runs** skip the wizard and reuse `config.json` automatically.
To redo setup, check "Reconfigure on next start" in the control panel
before clicking Start (or delete `config.json` manually).

### Control panel buttons

- **Start / Stop / Restart** — control the server process without closing the window.
- **Reconfigure on next start** — passes `--reconfigure` so the wizard runs again.
- **Send to server** — sends a line of text to the server's input (used for wizard prompts).

Closing the window will ask for confirmation if the server is still running, then stops it cleanly.

## What's NOT built yet

This prototype currently handles: the setup wizard, public IP detection,
Firebase registration/heartbeat/delisting, and the control panel GUI.
It does **not** yet include:
- The actual game networking loop (player position sync, block updates)
- The in-game Java client's actual multiplayer join flow (server
  discovery works, but joining a game isn't wired up yet)

Those are separate follow-up pieces.
