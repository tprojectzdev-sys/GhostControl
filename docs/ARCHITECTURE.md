# Architecture (build edition)

This is the executable companion to the design doc in
`.cursor/plans/remote_pc_control_architecture_*.plan.md`. The plan
explains *why*; this doc explains *what's actually here*.

## Component map

```
┌────────────────────────────────────────────────────────────────┐
│ relay/                                                         │
│   FastAPI + websockets + uvicorn, single process, stateless    │
│   /v1/cmd, /v1/status, /v1/audit, /healthz, /v1/ws/agent       │
│   ┌────────────┐  ┌────────────┐  ┌────────────┐               │
│   │ schemas.py │  │ ratelimit  │  │ ws_manager │               │
│   │ Command    │  │ buckets    │  │ pc + bridge│               │
│   │ Ack, Hello │  │ token      │  │ pending    │               │
│   └────────────┘  └────────────┘  └────────────┘               │
└──────────────────┬───────────────────┬─────────────────────────┘
                   │ HTTPS             │ WSS (outbound)
                   │                   │
        ┌──────────▼──────────┐ ┌──────▼──────────┐
        │  iOS app (SwiftUI)  │ │ agent/  bridge/ │
        │  dashboard (Vite)   │ │ Python long-    │
        │  Siri Shortcuts     │ │ running clients │
        └─────────────────────┘ └─────────────────┘
```

## Wire format

Every transport speaks the same JSON message. Schema enforced in
[`relay/schemas.py`](../relay/schemas.py) and re-validated on the agent.

```json
{ "id": "<uuid>", "ts": <unix>, "cmd": "<dotted.name>", "args": { ... } }
```

| `cmd`            | `args`                          | Returned `data`                                         |
|------------------|---------------------------------|---------------------------------------------------------|
| `power.wake`     | —                               | `{ action, mac, broadcast, port }` (from bridge)        |
| `power.shutdown` | `{ delay_seconds? }`            | `{ action, delay_seconds }`                             |
| `power.restart`  | `{ delay_seconds? }`            | `{ action, delay_seconds }`                             |
| `power.sleep`    | —                               | `{ action: "sleep" }`                                   |
| `power.lock`     | —                               | `{ action: "lock" }`                                    |
| `app.open`       | `{ target }`                    | `{ action, target }`                                    |
| `url.open`       | `{ url }`                       | `{ action, url }`                                       |
| `group.run`      | `{ target }`                    | `{ action, target, steps[] }`                           |
| `status.get`     | —                               | full status report (CPU/RAM/uptime/idle/foreground/os/host) |

## Auth frames

Agent / bridge first WS frame:

```json
{
  "type": "hello",
  "role": "pc" | "bridge",
  "agent_id": "<your-id>",
  "token": "<PC_AGENT_TOKEN or BRIDGE_AGENT_TOKEN>",
  "version": "1.0",
  "os": "Windows 11",
  "hostname": "denis-desktop"
}
```

Relay reply:

```json
{ "type": "welcome", "now": <unix> }
```

Subsequent agent → relay frames:

- `{ "type": "ack", "id": "...", "status": "ok"|"error", "code": "...", "message": "...", "data": {...}, "latency_ms": 42 }`
- `{ "type": "status", ...full status report... }`
- `{ "type": "pong", "now": <unix> }` (in response to relay pings)

Subsequent relay → agent frames:

- `{ "type": "cmd", "command": { id, ts, cmd, args } }`
- `{ "type": "ping", "now": <unix> }`

## Agent state machine

```
              connect
          ┌───────────────►
          │
   [DISCONNECTED] ──────hello───────► [AUTHENTICATING]
          ▲                                 │
          │ disconnect / error              │ welcome
          │                                 ▼
          └─────────[ONLINE: status loop + cmd loop]
```

- Reconnect backoff: 1, 2, 5, 10, 30, 60s with jitter.
- Heartbeat: status report every 30 s.
- Dedup: per-command-id, 5-minute window, max 256 entries.

## Replay / rate-limit budgets

- Replay window: 120 s (configurable via env `REPLAY_WINDOW_SECS`).
- Per-id LRU: cleared on entry age > 2× replay window.
- Tokens consumed: 1 per `/v1/cmd` call. Buckets refill at the configured
  rate per minute.

## Storage

Nothing is persisted that can't be reconstructed except the JSONL audit
log. Token state, pending commands, status — all in process memory.

The relay's audit log is plain JSONL on disk. On startup it backfills the
in-memory ring buffer (last 200) by reading the tail of the file. So
`/v1/audit` returns useful history even after a restart.

## Why a separate bridge?

A magic packet is a layer-2 broadcast. NATs don't forward it. The PC has
no IP while powered off. *Something* has to be on the LAN to emit the
packet, and that something has to be on while the PC is off — i.e. a
different device. We picked the smallest, cheapest, least-privileged
device that works (a Pi Zero 2 W). Any always-on Linux box works equally
well. See [`bridge/`](../bridge).

## What's intentionally NOT here

- No interpretation of intent. The system is a router for fixed commands.
- No file or process introspection beyond `status.get`.
- No remote desktop / streaming. Out of scope.
- No multi-tenant. One user, one set of tokens, one PC, one bridge.

## Code map (line counts approximate)

```
relay/main.py            ~280  HTTP + WSS endpoints
relay/schemas.py          ~95  pydantic models
relay/ws_manager.py      ~115  conn registry, send_and_wait
relay/audit.py            ~75  JSONL append + ring buffer
relay/ratelimit.py        ~50  token-bucket
relay/config.py           ~55  env var loader

agent/axon_agent/client.py    ~210  WS reconnect loop, dedup, ack
agent/axon_agent/executor.py  ~170  command dispatch + Win32
agent/axon_agent/whitelist.py ~150  YAML loader + watcher
agent/axon_agent/status.py    ~100  CPU/RAM/idle/foreground

bridge/bridge.py         ~165  hello + power.wake handler

dashboard/src/**         ~700  React components + api client + theme
ios/AxonRemote/**        ~900  SwiftUI views + relay client + models
```

Total executable surface for the entire system: well under 3 KLoC.
