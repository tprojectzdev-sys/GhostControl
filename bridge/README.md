# Axon Bridge (Wake-on-LAN)

A 200-line Python script for a tiny always-on Linux box on your home LAN —
a Raspberry Pi Zero 2 W is the canonical choice (~$15, 1 W idle).

It connects out to the cloud relay (the same one as the PC agent) and waits
for a single command: `power.wake`. When that arrives, it emits a Wake-on-LAN
magic packet on the LAN broadcast address for your PC's MAC.

That's it. The bridge does nothing else. Ever.

## One-time setup on the PC you want to wake

1. Enable Wake-on-LAN in the BIOS/UEFI (often labeled "Wake on LAN", "Power
   on by PCIe", or "Resume by PCI-E Device").
2. In Windows Device Manager → Network Adapter → Properties → Power
   Management:
   - tick "Allow this device to wake the computer"
   - tick "Only allow a magic packet to wake the computer"
3. In Power Options → Choose what the power buttons do → Change settings
   that are currently unavailable: **untick** "Turn on fast startup".
   (Fast startup hibernates instead of shutting down, and many NICs lose
   their WoL state during fast startup.)
4. Find the PC's NIC MAC address: `ipconfig /all` → Physical Address.

Use a wired ethernet connection. WoL over Wi-Fi is unreliable.

## Install on the Pi (or any Linux box on the LAN)

```bash
# clone this repo, then:
cd bridge
cp .env.example .env
nano .env                    # fill in relay URL, bridge token, PC MAC

# install + start as a systemd service:
sudo ./install-systemd.sh

# tail the log:
journalctl -u axon-bridge.service -f
```

You should see something like:

```
INFO axon.bridge: connecting to wss://your-relay.../v1/ws/agent as bridge id=axon-pi
INFO axon.bridge: relay welcome: {"type":"welcome","now":...}
```

Trigger a wake from the relay:

```bash
curl -X POST https://your-relay.up.railway.app/v1/cmd \
  -H "Authorization: Bearer $USER_API_KEY" -H "Content-Type: application/json" \
  -d '{"id":"01J-test","ts":'"$(date +%s)"',"cmd":"power.wake","args":{}}'
```

The bridge log should print `sent magic packet to AA:BB:CC:DD:EE:FF via 255.255.255.255:9`.

## Tuning

If `255.255.255.255` is dropped by your router, switch to your subnet
broadcast (e.g. `192.168.1.255`):

```ini
AXON_BROADCAST=192.168.1.255
```

Find it with `ip -br a` — it's the broadcast at the end of the line for your
LAN interface, or compute it from your subnet mask.

## Don't I need a Pi? Can my router do this?

Some routers can — ASUS, Fritz!Box, OpenWrt all have WoL features — but
each one requires a vendor-specific integration and exposes more attack
surface than a $15 Pi. The bridge is the universal answer.

If you already have an always-on Linux device (NAS, Home Assistant box,
old laptop), use that and skip the Pi. The script doesn't care about the
hardware.
