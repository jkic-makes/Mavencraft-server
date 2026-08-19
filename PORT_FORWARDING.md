# Port Forwarding Guide for MavenCraft Servers

To let other players connect to your MavenCraft server over the internet,
you need to forward a port on your home router to your computer. This is
the same thing classic Minecraft servers require.

Default MavenCraft port: **25565** (TCP). If you changed it during setup,
substitute your chosen port everywhere below.

---

## Step 1: Find your computer's local IP address

**Windows:**
1. Press `Win + R`, type `cmd`, hit Enter.
2. Type `ipconfig` and press Enter.
3. Look for "IPv4 Address" under your active adapter (Wi-Fi or Ethernet) —
   it looks like `192.168.1.XX`.

**Mac:**
1. Open **System Settings → Network**.
2. Click your active connection, the local IP is shown there (e.g. `192.168.1.XX`).

**Linux:**
1. Open a terminal and run `ip addr show` or `hostname -I`.

Write this address down — you'll need it in Step 3.

---

## Step 2: Give your computer a fixed local IP (recommended)

By default, routers can reassign your computer's local IP over time (DHCP),
which would silently break your port forward. Two ways to fix this:

**Option A - Router-side DHCP reservation (recommended):**
In your router's admin page (see Step 3), look for "DHCP Reservation,"
"Static Lease," or "Address Reservation." Reserve the IP you found in
Step 1 for your computer's MAC address.

**Option B - Set a static IP directly on your computer:**
Simpler to explain but easier to misconfigure (can knock you off your
network if done wrong) — Option A is safer for most people.

---

## Step 3: Log in to your router

1. Find your router's gateway IP:
   - Windows: in the same `ipconfig` output, look for "Default Gateway"
     (e.g. `192.168.1.1`).
   - Mac/Linux: run `netstat -nr | grep default` (Mac) or `ip route` (Linux).
2. Type that IP into your web browser's address bar.
3. Log in. If you've never changed it, check the sticker on the router
   itself for default credentials, or look up your router model online
   (e.g. "Netgear Nighthawk default login").

---

## Step 4: Create the port forward rule

Look for a section called **"Port Forwarding,"** "Virtual Server," or
"NAT Forwarding" (varies by brand — Netgear, TP-Link, Asus, and ISP-issued
routers all label this a little differently).

Create a new rule with:

| Field | Value |
|---|---|
| Service Name | MavenCraft (or anything) |
| External/Public Port | 25565 |
| Internal/Local Port | 25565 |
| Protocol | TCP (or "TCP/UDP" if there's no separate TCP-only option) |
| Internal/Local IP | The IP from Step 1 (e.g. `192.168.1.XX`) |

Save/Apply. Some routers reboot briefly after saving.

---

## Step 5: Allow the port through your computer's firewall

**Windows:**
1. Open **Windows Defender Firewall → Advanced Settings**.
2. **Inbound Rules → New Rule → Port**.
3. TCP, Specific local port: `25565` → Allow the connection → apply to
   all profiles → name it "MavenCraft".

**Mac:**
1. **System Settings → Network → Firewall → Options**.
2. Add `mavencraft-server.py` (or the `.exe` launcher) to the allowed list.

**Linux (ufw):**
```bash
sudo ufw allow 25565/tcp
```

---

## Step 6: Verify the port is actually open

With `mavencraft-server.py` running, use an external checker (opens the
port check from outside your network, which is the only way to test this
correctly — checking from inside your own network can give a false positive):

- https://www.yougetsignal.com/tools/open-ports/
- https://canyouseeme.org/

Enter port `25565` and check. "Open" means you're good to go. "Closed"
means double-check Steps 2, 4, and 5 — reservation not applied yet, wrong
internal IP, or firewall still blocking it are the most common causes.

---

## Common issues

- **ISP uses CGNAT (Carrier-Grade NAT):** Some ISPs (common on mobile
  data, some cable/fiber plans, and satellite internet) don't give you a
  real public IP at all, so port forwarding has nothing to attach to.
  Symptom: the external port checker always says "closed" no matter what
  you configure. Fix: call your ISP and ask for a "public IP address" or
  "bridge mode" — sometimes free, sometimes a small add-on fee.
- **Double NAT:** If you have a modem *and* a separate router, you may
  need to forward the port on both, or put the modem in bridge mode.
- **Dynamic public IP:** Your public IP can change when your router
  restarts or periodically per your ISP's policy. MavenCraft's server
  script re-detects and re-registers your IP with Firebase on every boot,
  but if your IP changes while the server is running without a restart,
  players may need to reconnect via a fresh domain lookup.
