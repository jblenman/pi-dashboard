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

1. Browse to `http://routerlogin.net` (or the router's LAN IP) and sign in.
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
