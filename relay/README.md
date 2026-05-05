# Axon Relay

A small, stateless cloud relay that:

- accepts authenticated HTTP POST commands at `/v1/cmd` (phone, dashboard)
- holds a single outbound WebSocket from the **PC agent**
- holds a single outbound WebSocket from the **WoL bridge**
- forwards each command to the right agent and waits for an ack
- writes every event to a JSONL audit log
- enforces bearer-token auth, replay protection, and rate limiting

It does **not** store the command whitelist (that lives only on the PC).
It does **not** interpret command semantics. It does **not** execute anything.

## Endpoints

| Method | Path             | Auth                       | Purpose |
|--------|------------------|----------------------------|---------|
| GET    | `/healthz`       | none                       | Liveness probe |
| GET    | `/`              | none                       | Service banner |
| POST   | `/v1/cmd`        | `Bearer USER_API_KEY`      | Submit a command |
| GET    | `/v1/status`     | `Bearer USER_API_KEY`      | Get PC + bridge status |
| GET    | `/v1/audit?limit=50` | `Bearer USER_API_KEY`  | Recent audit events |
| WS     | `/v1/ws/agent`   | hello frame with token     | Agent connection |

## Wire format

Every command, on every transport, has this shape:

```json
{ "id": "<uuid>", "ts": 1735689600, "cmd": "power.shutdown", "args": {} }
```

Allowed `cmd` values:

```
power.shutdown power.restart power.sleep power.lock power.wake
app.open url.open group.run status.get
```

`power.wake` is routed to the bridge. Everything else is routed to the PC agent.

## Local dev

```bash
cd relay
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env          # then fill in tokens
python -c "import secrets; print(secrets.token_hex(32))"   # generate each token

# load .env in your shell, then:
python -m uvicorn relay.main:app --reload --port 8080
```

Smoke test:

```bash
curl http://localhost:8080/healthz
curl -X POST http://localhost:8080/v1/cmd ^
  -H "Authorization: Bearer $env:USER_API_KEY" ^
  -H "Content-Type: application/json" ^
  -d "{\"id\":\"01J123\",\"ts\":1735689600,\"cmd\":\"status.get\",\"args\":{}}"
```

## Deploy to Railway

1. Push this repo to GitHub.
2. Create a new Railway project from the GitHub repo, root = `relay/`.
3. Set the env vars from `.env.example`. Generate the tokens with `secrets.token_hex(32)`.
4. Railway picks up `Procfile` automatically. Health check is configured in `railway.json`.
5. Note the public URL Railway gives you (e.g. `https://axon-relay-production.up.railway.app`).
   This is the URL your phone, dashboard, PC agent, and bridge all point at.

## Auth model (MVP)

- Phone / dashboard → `Authorization: Bearer <USER_API_KEY>`
- PC agent → first WS frame: `{"type":"hello","role":"pc","agent_id":"...","token":"<PC_AGENT_TOKEN>"}`
- Bridge → first WS frame: `{"type":"hello","role":"bridge","agent_id":"...","token":"<BRIDGE_AGENT_TOKEN>"}`

Each principal has its own token. Rotate by changing the env var on Railway and updating the client.

## What's intentionally NOT here

- No database. State is in-memory; the audit log is JSONL on disk.
- No HMAC signing yet (see Phase 2 in `docs/ARCHITECTURE.md`).
- No multi-tenant. Single user, single PC, single bridge.
- No queue. If the agent is offline, `/v1/cmd` returns 503 immediately.
