# Deployment Guide

End-to-end walkthrough for getting Axon Remote running for one user, one
PC, one bridge. Assumes you have:

- a GitHub account and a free Railway account (or any container host)
- a Windows 10/11 PC you want to control
- a Raspberry Pi (or any always-on Linux box) on the same LAN as the PC
- an iPhone

Total time: ~45 minutes the first time.

---

## 1. Generate three secrets

You need three independent, long random tokens. Pick any of these:

```bash
# Linux / macOS
openssl rand -hex 32
```

```powershell
# Windows PowerShell
[Convert]::ToHexString((1..32 | ForEach-Object { Get-Random -Maximum 256 }))
```

Or in Python:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

You need three: one for `USER_API_KEY` (phone/dashboard), one for
`PC_AGENT_TOKEN`, one for `BRIDGE_AGENT_TOKEN`. **Don't reuse them.**

---

## 2. Deploy the relay to Railway

1. Push this whole repo to a private GitHub repo.
2. Go to [railway.app](https://railway.app) → **New Project → Deploy from
   GitHub** → choose your repo.
3. **Settings → Service → Root Directory** → set to `relay`.
4. **Variables** → add:
   - `USER_API_KEY` (from step 1)
   - `PC_AGENT_TOKEN`
   - `BRIDGE_AGENT_TOKEN`
   - leave the rest at their defaults
5. **Settings → Networking → Generate Domain** → note the URL,
   e.g. `axon-relay-production.up.railway.app`. The HTTPS domain
   automatically works.

Smoke test:

```bash
curl https://axon-relay-production.up.railway.app/healthz
# → ok
```

If you get back `ok`, the relay is up. If you get a 502 or "service
unavailable", check **Logs** in Railway for the actual error.

---

## 3. Install the PC agent

On the Windows machine:

```powershell
# install Python 3.11+ from https://python.org if you don't have it
# clone the repo
git clone https://github.com/<you>/axon.git
cd axon\agent

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy whitelist.example.yaml whitelist.yaml
copy .env.example .env

notepad whitelist.yaml     # add your real apps and groups
notepad .env               # paste relay URL + PC_AGENT_TOKEN
```

`.env` should look like:

```ini
AXON_RELAY_URL=wss://axon-relay-production.up.railway.app/v1/ws/agent
AXON_AGENT_TOKEN=<the PC_AGENT_TOKEN from step 1>
```

Smoke test it interactively first:

```powershell
.\run-agent.ps1
```

You should see the agent connect, the relay welcome, and a
"whitelist loaded" line.

Now install it as a scheduled task (runs at every login):

```powershell
# right-click PowerShell → Run as Administrator
.\install-task.ps1
```

Verify it's running by signing out and back in, then:

```powershell
Get-Content -Wait .\logs\agent.log
```

---

## 4. Wake-on-LAN setup on the PC

Required only if you want `power.wake` to work. Do this on the PC you
want to wake:

1. **BIOS/UEFI**: enable "Wake on LAN", "Resume by PCIe", or whatever your
   BIOS calls it. Save and reboot.
2. **Windows Device Manager** → Network adapters → your wired NIC →
   **Properties → Power Management**:
   - tick "Allow this device to wake the computer"
   - tick "Only allow a magic packet to wake the computer"
3. **Power Options** → "Choose what the power buttons do" → "Change
   settings that are currently unavailable" → **untick** "Turn on fast
   startup".
4. Find the PC's MAC: `ipconfig /all` → look for "Physical Address" under
   your wired NIC. Note it down.
5. Use a wired Ethernet connection. WoL over Wi-Fi is unreliable.

Verify:

```powershell
shutdown /h /f         # hibernate
# OR shutdown /s /f /t 0 to actually turn off
```

…then on the Pi (after step 5 below), trigger `power.wake`.

---

## 5. Install the WoL bridge on the Pi

```bash
git clone https://github.com/<you>/axon.git
cd axon/bridge

cp .env.example .env
nano .env
```

`.env` should be:

```ini
AXON_RELAY_URL=wss://axon-relay-production.up.railway.app/v1/ws/agent
AXON_BRIDGE_TOKEN=<the BRIDGE_AGENT_TOKEN from step 1>
AXON_TARGET_MAC=AA:BB:CC:DD:EE:FF
# AXON_BROADCAST=192.168.1.255   # only if 255.255.255.255 doesn't work
```

Then:

```bash
sudo ./install-systemd.sh
journalctl -u axon-bridge.service -f
```

You should see "connecting to wss://..." then "relay welcome".

End-to-end smoke test:

```bash
TOKEN=<USER_API_KEY>
curl -X POST https://axon-relay-production.up.railway.app/v1/cmd \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"id":"test-'"$(date +%s)"'","ts":'"$(date +%s)"',"cmd":"power.wake","args":{}}'
```

The Pi log should print
`sent magic packet to AA:BB:CC:DD:EE:FF via 255.255.255.255:9` and your
PC should boot.

---

## 6. iOS app

See [`ios/README.md`](../ios/README.md). Two paths:

- `brew install xcodegen` → `cd ios && xcodegen generate && open AxonRemote.xcodeproj`.
- Or create a new Xcode SwiftUI project manually and drag the source files in.

On first launch the app asks for the relay URL and the bearer token
(`USER_API_KEY`). Token is stored via `@AppStorage`.

---

## 7. Siri Shortcuts

See [`docs/SIRI-SHORTCUTS.md`](./SIRI-SHORTCUTS.md) for templates.

The minimum viable setup is:
- one parameterized "Send PC Command" shortcut that takes `cmd` + `args`
- per-phrase shortcuts that call it with fixed values
  ("Hey Siri, lock my PC" → `power.lock`)

---

## 8. Dashboard (optional)

```bash
cd dashboard
npm install
npm run build
```

Drop `dist/` on:

- **Cloudflare Pages** (free, fastest CDN)
- **Vercel** (free, zero config)
- the same Railway service that runs the relay (mount as static)

Open it, type the relay URL + bearer token, and you have the same control
surface as the app — but on a desktop browser.

---

## Common issues

- **"agent_offline"** when sending commands → the PC agent isn't connected
  to the relay. Check `Get-Content -Wait .\logs\agent.log`.
- **`power.wake` returns 503** → the bridge isn't connected. Check
  `journalctl -u axon-bridge.service -f`.
- **Magic packet sent but PC doesn't wake** → 90% of the time it's "Fast
  Startup" still enabled in Windows. Disable it. The other 10% is the NIC
  losing power; check that the NIC's Power Management settings are
  correct.
- **TLS error on Railway** → the URL you put in clients should always be
  `https://` for HTTPS endpoints and `wss://` for the WebSocket endpoint.
  Same hostname.
- **HTTP 401 from `/v1/status`** → token typo. Tokens are case-sensitive
  hex; copy-paste them.
- **`401` on the WSS connect** → wrong agent token. PC and bridge use
  *different* tokens.

---

## Updating

The agent and bridge are stateless. To update:

```powershell
# on the PC
cd agent
git pull
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Stop-ScheduledTask -TaskName AxonAgent
Start-ScheduledTask -TaskName AxonAgent
```

```bash
# on the Pi
cd bridge
git pull
sudo systemctl restart axon-bridge.service
```

The relay redeploys automatically on `git push` if you're using Railway.
