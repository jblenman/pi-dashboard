# Operating the dashboard + Pi-hole

How the pieces fit together, how to route your network through Pi-hole on a
Netgear Nighthawk, what happens if the Pi goes down, and day-to-day upkeep.

## How it fits together

```
                          ┌─────────────────────────── Raspberry Pi ───────────────────────────┐
   every device           │                                                                    │
   (phones, TVs, PCs)     │   Pi-hole (FTL)            speedtest timer        dashboard (web)   │
        │                 │   DNS :53  ── blocks ads   every 30 min ──┐       FastAPI :8080     │
        │  DNS lookups     │     │        + forwards          │        │          ▲   ▲         │
        ▼                 │     │        clean queries        ▼        ▼          │   │         │
     router  ───────────► │     │       upstream         SQLite DB   Ookla     reads  reads    │
   (DHCP + DNS relay)     │     │            │           (history)    CLI       DB    Pi-hole   │
        ▲                 │     └────────────┼──────────────────────────────────────┘   API    │
        │                 └──────────────────┼─────────────────────────────────────────────────┘
        │                                    ▼
        └──────────────── internet ◄──── upstream DNS (1.1.1.1, etc.)
```

- **Pi-hole** is a DNS server. Point your network's DNS at it; it answers every
  lookup, returns `0.0.0.0` for ad/tracker domains (so they never load) and
  forwards everything else to a real upstream resolver.
- **The dashboard** is independent of DNS. It logs a speedtest every 30 minutes to
  a local SQLite DB and reads Pi-hole's live stats through Pi-hole's v6 API. It
  serves a single 800x480 screen on `http://<PI_IP>:8080`.
- Both run as **systemd services** (`pihole-FTL`, `pidash-web`, `pidash-speedtest.timer`)
  — they start on boot and restart on crash.

## Network setup (Netgear Nighthawk, e.g. RAXE500)

Two steps: give the Pi a fixed address, then route DNS through it.

### 1. Reserve a fixed IP for the Pi

A DNS server must keep the same IP, or the whole network loses name resolution
when its DHCP lease changes. Reserve the **wired** NIC (if the Pi is on Ethernet,
its eth0 MAC differs from the Wi-Fi MAC — reserve the one you're actually using).

1. Browse to **`https://<router-ip>`** (e.g. `https://192.168.1.1`) and sign in. Use
   **https + the IP directly** — plain `http`/`routerlogin.net` bounces to a stub page
   that redirects to `www.routerlogin.net/index.htm`, which browsers frequently serve a
   stale **404** for from cache. Accept the self-signed-cert warning; the login is a
   browser Basic-auth popup.
2. **ADVANCED → Setup → LAN Setup**.
3. Under **Address Reservation**, click **Add**.
4. Pick the Pi from the device list (or enter its **MAC** manually), set the **IP
   Address** you want it pinned to, **Add**, then **Apply**.
5. Reboot the Pi (or `sudo dhclient -r && sudo dhclient`) so it picks up the
   reserved lease.

### 2. Route DNS through Pi-hole

> **Nighthawk limitation:** these routers have **no field to hand a custom DNS
> server to LAN/DHCP clients** — the only DNS box is for the *WAN/Internet* side.
> So you can't just type the Pi's IP into "DHCP DNS." Two ways around it:

**Option A — Set the router's Internet (WAN) DNS to the Pi (simplest).**
1. **ADVANCED → Setup → Internet Setup**.
2. Under **Domain Name Server (DNS) Address**, choose **Use These DNS Servers**.
3. **Primary DNS = `<PI_IP>`**. For Secondary, see *Resilience* below.
4. **Apply.**

The router's built-in DNS relay now forwards every client lookup to the Pi:
`client → router (192.168.1.1) → Pi-hole → upstream`.
- ✅ Dead simple, fully reversible, gives a built-in fallback (secondary DNS).
- ⚠️ Pi-hole sees **every query as coming from the router** (one client), so you
  lose the per-device breakdown in Pi-hole's dashboard.
- ⚠️ The router may keep a **hidden ISP/modem DNS fallback** of its own — some
  Nighthawks still resolve a few lookups *unfiltered* even with the Pi set as WAN DNS,
  so the odd ad leaks through. **Option B** (Pi hands DNS to clients directly) is the
  airtight fix.

**Option B — Let Pi-hole run DHCP (full per-device stats).**
1. Router: **ADVANCED → Setup → LAN Setup → uncheck "Use Router as DHCP Server"**, Apply.
2. Pi-hole UI: **Settings → DHCP → enable**, set the range + gateway (`192.168.1.1`).

Now the Pi hands out IPs *and* itself as DNS directly to each client.
- ✅ Real per-device stats, no relay in the middle.
- ⚠️ The Pi is now your DHCP server too — a bigger dependency (see *Resilience*).
  Only one DHCP server may be active, so the router's must be off.

**Recommendation:** start with **Option A** (with a public secondary for safety).
Move to **Option B** later if you want per-device visibility.

## Resilience: what if the Pi goes down?

Once clients depend on the Pi for DNS, a Pi that's off/rebooting/crashed makes
devices act like the internet is down (the link is fine — names just don't
resolve). This is the one real cost of Pi-hole. Mitigations:

**Built-in fallback (Option A):** set the router's **Secondary** WAN DNS to a
public resolver (e.g. `1.1.1.1`). If the Pi stops answering, the router fails over
to it and the internet keeps working — **unfiltered** during the outage.
- Trade-off: a reachable secondary may get used *occasionally even when the Pi is
  up*, so a few queries skip filtering. For strict filtering, leave Secondary
  blank (Pi-only) and accept that a Pi outage = a DNS outage until you fix it.

**Emergency recovery (Pi dead, need DNS now — ~2 min):**
- *Option A:* router → **Internet Setup → DNS → Get Automatically from ISP** (or
  set `1.1.1.1`) → Apply. Resolution returns immediately (unfiltered).
- *Option B:* re-enable the router's DHCP server; clients get ISP DNS on renew.
- *One urgent device:* set its DNS manually to `1.1.1.1`.

**Lower the odds of downtime:**
- Services already auto-restart (systemd) and start on boot.
- Move the OS to the **NVMe SSD** — SD cards are the #1 Pi failure point.
- A small **UPS** rides out power blips.
- True redundancy = a **second Pi-hole** (another Pi/container) as the secondary
  DNS, kept in sync (e.g. `nebula-sync`). Overkill for most homes.

## Switching to Pi-hole as the DHCP server (Option B)

Gives **per-device** stats (each client shows individually instead of everything
appearing as the router) and lets Pi-hole serve DNS to every device directly.
Trade-off: the Pi becomes your DHCP server too — if it's down, devices can't get
*new* leases (existing ones keep working until they expire).

Pre-stage the range while DHCP is still **off** (no disruption):

```
sudo pihole-FTL --config dhcp.start     "192.168.1.100"
sudo pihole-FTL --config dhcp.end       "192.168.1.249"
sudo pihole-FTL --config dhcp.router    "<router-ip>"
sudo pihole-FTL --config dhcp.netmask   "255.255.255.0"
sudo pihole-FTL --config dhcp.leaseTime "24h"
```

Keep the Pi's own IP **out** of that range. The cutover (do it where you can recover
— ideally with a screen attached):

1. **Give the Pi a static IP** (it can't rely on the router's DHCP once that's off).
   Reuse the IP it already has so your SSH session survives the change:
   ```
   sudo nmcli con mod "<eth-connection>" ipv4.method manual \
     ipv4.addresses <PI_IP>/24 ipv4.gateway <router-ip> ipv4.dns 127.0.0.1 \
     connection.autoconnect yes
   sudo nmcli dev reapply eth0      # in-place; keeps the IP (and SSH) up
   ```
   `dev reapply` is gentler than `con up` (no full down/up), so an unchanged IP won't
   drop your session. The Pi is about to be the *only* DHCP server, so confirm the static
   config **persisted** and will come up on its own after a reboot:
   ```
   nmcli -g ipv4.method,connection.autoconnect con show "<eth-connection>"   # -> manual / yes
   ```
   Modern Raspberry Pi OS is plain NetworkManager (the `/etc/netplan/90-NM-*.yaml` files
   are often empty stubs, so `nmcli` is authoritative). If yours **is** netplan-managed
   (name like `netplan-eth0`) and a reboot reverts the change, set the static IP in
   `/etc/netplan/*.yaml` + `sudo netplan apply` instead.
2. **Disable the router's DHCP** — RAXE500: ADVANCED → Setup → LAN Setup → uncheck
   **"Use Router as DHCP Server"** → Apply.
3. **Enable Pi-hole's DHCP:** `sudo pihole-FTL --config dhcp.active true` (or Pi-hole UI
   → Settings → DHCP → enable).
4. **Verify:** reboot a client (or `ipconfig /renew`) — it should pull an IP in the new
   range with the Pi as DNS and show up as its own client in Pi-hole.
5. **Re-create any router IP reservations** as Pi-hole static leases — see *Static
   reservations* below. The Pi itself is static (step 1), so it needs no lease.

Rollback: re-enable the router's DHCP and `sudo pihole-FTL --config dhcp.active false`.

### Static reservations (pin a device to a fixed IP)

Reservations live in Pi-hole's `dhcp.hosts` array (dnsmasq `dhcp-host` format,
`MAC,IP[,hostname]`). Setting it **replaces the whole array**, so include every entry:

```
sudo pihole-FTL --config dhcp.hosts \
  '["aa:bb:cc:dd:ee:01,192.168.1.10,desktop", "aa:bb:cc:dd:ee:02,192.168.1.11,nas"]'
```

Keep reserved IPs **outside** the dynamic range (`dhcp.start`–`dhcp.end`). A device picks
up its reserved IP on its next lease renewal (reboot, or toggle its network).

**Find a device's MAC without touching it** — ping it from the Pi to force an ARP resolve,
then read the table (works even if the device's firewall blocks ping; ARP is layer-2):

```
ping -c1 -W1 192.168.1.50 >/dev/null 2>&1; ip neigh show dev eth0 | grep 192.168.1.50
```

**Apple devices use a randomized "Private Wi-Fi Address"** that can rotate and slide off a
MAC reservation. On the device, set that Wi-Fi network's **Private Wi-Fi Address → Fixed**
(or Off), then reserve the MAC it shows.

## Day-to-day operations

Everything lives under `~/pi-dashboard` on the Pi; the Pi-hole admin password is
in `~/pi-dashboard/deploy/secrets.env` (git-ignored).

| Task | Command |
|------|---------|
| Dashboard | open `http://<PI_IP>:8080` |
| Pi-hole admin | open `http://<PI_IP>/admin` |
| Service status | `systemctl status pidash-web pihole-FTL` |
| Speedtest timer | `systemctl list-timers pidash-speedtest.timer` |
| Run a speedtest now | `sudo systemctl start pidash-speedtest.service` |
| Restart the dashboard | `sudo systemctl restart pidash-web` |
| Update the dashboard | `cd ~/pi-dashboard && git pull && bash deploy/install.sh` |
| Update Pi-hole | `pihole -up` |
| Refresh blocklists | `pihole -g` |
| Change Pi-hole password | `sudo pihole setpassword` (then update `deploy/secrets.env` + `sudo systemctl restart pidash-web`) |
| Logs | `journalctl -u pidash-web -e` / `journalctl -u pihole-FTL -e` |

## Troubleshooting

- **Whole network "loses internet" right after the DNS change** → the Pi isn't
  resolving. Check `systemctl status pihole-FTL`; verify `dig @<PI_IP> google.com`
  returns an answer. Recover via the emergency steps above while you debug.
- **Ads not blocked** → confirm clients actually use the Pi: `nslookup doubleclick.net`
  should return `0.0.0.0`. With Option A, a public **secondary** DNS can leak
  queries past Pi-hole — remove it to test.
- **Dashboard Pi-hole panel shows mock data / a DEMO badge** → the app can't reach
  Pi-hole. Check `PIDASH_PIHOLE_APP_PASSWORD` in `deploy/secrets.env`, then
  `sudo systemctl restart pidash-web`.
- **Blocklist count shows a negative number right after install** → FTL hadn't
  finished loading gravity; `sudo systemctl restart pihole-FTL`.
- **Pi reachable on two IPs** → it's connected by both Ethernet and Wi-Fi. Pick one
  (wired is steadier); optionally disable Wi-Fi with `sudo nmcli radio wifi off`.
