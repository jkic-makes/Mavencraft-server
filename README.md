# MavenCraft Server (Prototype)

Registers your MavenCraft world under a name you choose ("fake domain")
so it can be found in the game's multiplayer menu — without any real
domain registration. Actual player connections still require port
forwarding; see `PORT_FORWARDING.md`.

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

## 2. Configure the server

```bash
pip install -r requirements.txt

export MAVENCRAFT_FIREBASE_URL="https://your-project-id-default-rtdb.firebaseio.com"
# Optional, only needed if you lock down your DB rules with a secret/auth token:
# export MAVENCRAFT_FIREBASE_SECRET="your-secret-or-id-token"
```

(Windows PowerShell: use `$env:MAVENCRAFT_FIREBASE_URL = "..."` instead of `export`.)

## 3. Run it

```bash
python mavencraft-server.py
```

First run walks you through:
- **Server name** — shown to players in the multiplayer list.
- **Fake domain** — anything you want, e.g. `bob-survival` or
  `sub.example.com`. Just a label stored in Firebase, first-come-first-served.
- **RAM allocation (MB)**.
- **Port** (defaults to 25565).

It then detects your public IP and writes everything to Firebase.

**You still need to port forward** the chosen port to this machine —
follow `PORT_FORWARDING.md` or players won't be able to reach you.

Re-running later skips the wizard and reuses `config.json`
(delete it, or pass `--reconfigure`, to redo setup).

## What's NOT built yet

This prototype only handles: the setup wizard, public IP detection, and
Firebase registration/heartbeat/delisting. It does **not** yet include:
- The actual game networking loop (player position sync, block updates)
- `mavencraft-serverclient.exe` launcher wrapper
- The in-game Java client screen that reads the Firebase domain list

Those are separate follow-up pieces.
