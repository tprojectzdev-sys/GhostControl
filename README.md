# Axon Remote

A strict, command-based remote control system for a personal Windows PC.
Phone, web dashboard, and Siri Shortcuts all hit the **same** small cloud
relay over HTTPS. The PC and a tiny LAN bridge dial out to the relay over
WebSocket. No port forwarding. No VPN on the phone. No arbitrary command
execution.

```
┌────────────┐      HTTPS POST      ┌─────────────┐     WSS      ┌─────────────┐
│  iPhone    │ ───────────────────► │             │ ───────────► │ Windows PC  │
│ (Siri /    │                      │ Cloud Relay │              │   Agent     │
│  app /     │                      │  (Railway)  │              └─────────────┘
│  browser)  │                      │             │     WSS      ┌─────────────┐
└────────────┘                      │             │ ───────────► │  WoL Bridge │
                                    └─────────────┘              │ (Pi/Linux)  │
                                                                 └─────────────┘
```

**It is not an AI assistant.** It speaks one tiny wire format, every
command is enumerated, and every alias is enforced by a YAML whitelist on
the PC.

---

## What's in this repo

| Folder        | What it is                                                                |
|---------------|---------------------------------------------------------------------------|
| [`relay/`](./relay)         | FastAPI cloud relay. Bearer auth, WSS routing, JSONL audit, Railway-ready. |
| [`agent/`](./agent)         | Windows PC agent. Python service, YAML whitelist, all 8 commands.          |
| [`bridge/`](./bridge)       | Wake-on-LAN bridge. Tiny Python, runs on Raspberry Pi or any Linux box.    |
| [`dashboard/`](./dashboard) | Vite + React + Tailwind dark dashboard. Same auth as the iOS app.          |
| [`ios/`](./ios)             | Native SwiftUI app for iPhone/iPad. Universal, dark mode.                  |
| [`docs/`](./docs)           | Deployment, security, Siri Shortcuts, BIOS / Windows WoL setup.            |

## Wire format

One canonical message used by every transport (HTTPS body, WSS frames
both ways):

```json
{ "id": "<uuid>", "ts": 1735689600, "cmd": "power.shutdown", "args": {} }
```

| `cmd`            | Routed to | Args                       | Effect                                                  |
|------------------|-----------|----------------------------|---------------------------------------------------------|
| `power.wake`     | bridge    | —                          | LAN-broadcast magic packet for the PC's MAC             |
| `power.shutdown` | pc        | `delay_seconds?` (0–60)    | `shutdown.exe /s /t <delay>`                            |
| `power.restart`  | pc        | `delay_seconds?`           | `shutdown.exe /r /t <delay>`                            |
| `power.sleep`    | pc        | —                          | `SetSuspendState`                                       |
| `power.lock`     | pc        | —                          | `LockWorkStation`                                       |
| `app.open`       | pc        | `target` (alias)           | Resolve to whitelisted exe path → `CreateProcess`       |
| `url.open`       | pc        | `url` (https)              | Pass to default browser via `os.startfile`              |
| `group.run`      | pc        | `target` (alias)           | Run a sequence (no `power.*`, no nested groups)         |
| `status.get`     | pc        | —                          | Returns CPU/RAM/uptime/idle/foreground app              |

## Auth

- **Phone, dashboard, app** → `Authorization: Bearer <USER_API_KEY>`
- **PC agent** WSS connect → `{"type":"hello","role":"pc","token":"<PC_AGENT_TOKEN>"}`
- **Bridge** WSS connect → `{"type":"hello","role":"bridge","token":"<BRIDGE_AGENT_TOKEN>"}`

Each principal has its own token. Rotate on the relay (env vars) and update
the affected client.

## Quick start

1. **Deploy the relay.** Push this repo to GitHub, create a Railway project
   from the `relay/` folder, and set the three env vars from
   [`relay/.env.example`](./relay/.env.example). Railway gives you a public
   HTTPS URL — that's what every client points at. See
   [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md) for details.

2. **Run the PC agent.** On the Windows PC you want to control:

   ```powershell
   cd agent
   python -m venv .venv ; .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   copy whitelist.example.yaml whitelist.yaml
   copy .env.example .env
   notepad whitelist.yaml      # add your apps
   notepad .env                # paste relay URL + PC_AGENT_TOKEN
   .\run-agent.ps1             # smoke test

   # then, as Administrator:
   .\install-task.ps1
   ```

3. **Run the WoL bridge** on a Pi (or any always-on Linux box on the same LAN):

   ```bash
   cd bridge
   cp .env.example .env
   nano .env                   # relay URL, BRIDGE_AGENT_TOKEN, PC MAC
   sudo ./install-systemd.sh
   ```

4. **Set up the phone.** You have two options, both can coexist:
   - **Native app** — `ios/` is a SwiftUI app. Generate the project with
     `xcodegen generate` (see `ios/README.md`) and run on your iPhone.
   - **Siri Shortcuts** — copy the templates in
     [`docs/SIRI-SHORTCUTS.md`](./docs/SIRI-SHORTCUTS.md). Voice-first.

5. **(Optional) Deploy the dashboard.** From `dashboard/`, run
   `npm install && npm run build`, drop `dist/` on Cloudflare Pages /
   Vercel, then sign in with your relay URL + bearer token.

## Security model

- Cloud relay never sees app paths or URL contents until you're already
  authenticated.
- Cloud relay never executes anything. It is a switchboard.
- The PC agent re-validates **every** command against `whitelist.yaml`.
  An alias that isn't in the YAML is dropped — even if the relay was
  fully compromised.
- Replay window: 120 s skew + per-id dedupe (5 min) on both relay and agent.
- Rate limit: 60 req/min per token (10/min for `power.*`).
- TLS everywhere. Outbound only from the home network.

See [`docs/SECURITY.md`](./docs/SECURITY.md) for the full threat model.

## Cost

- Railway hobby tier: $0–$5/month. The relay uses ~50 MB RAM and is mostly
  idle.
- Pi Zero 2 W: ~$15 (one-time). Optional if you have an always-on Linux
  device already.
- Total: ~$0–$5/month + ~$15 hardware once.

## Phases (status)

- ✅ **Phase 1 — MVP**: relay, agent, bridge, dashboard, iOS app, Siri
  Shortcuts. All in this repo.
- ⏳ **Phase 2**: HMAC request signing, command queueing while agent is
  reconnecting, WoL setup verifier, agent self-update.
- ⏳ **Phase 3**: APNs push for command outcomes, schedules, multi-PC,
  whitelist editor in the dashboard.

## License

MIT. See `LICENSE` (add one if you fork this).
