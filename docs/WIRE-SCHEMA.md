# Wire schema (canonical reference)

Every client (Siri Shortcuts, dashboard, iOS app, debug `curl`) MUST send
this exact JSON to `POST /v1/cmd`:

```json
{
  "id":   "01J9YDR4KZ-...",          // UUIDv4 or ULID, 8..64 chars
  "ts":   1735689600,                // unix seconds, must be within ±120s of relay clock
  "cmd":  "power.lock",              // one of the 9 enum values
  "args": { "target": "vscode" }     // optional, schema depends on cmd
}
```

Required HTTP headers:

```
Authorization: Bearer <USER_API_KEY>
Content-Type:  application/json
```

The relay forwards the same `{ id, ts, cmd, args }` (untouched) to the
target agent, wrapped as `{ "type": "cmd", "command": ... }`.

## Enum: cmd

```
power.shutdown power.restart power.sleep power.lock power.wake
app.open url.open group.run status.get
```

Anything else → 400 with `{ "detail": "schema", ... }`.

## args by cmd

```
power.shutdown   { delay_seconds?: 0..60 }
power.restart    { delay_seconds?: 0..60 }
power.sleep      {}
power.lock       {}
power.wake       {}
app.open         { target: "alias-from-pc-yaml" }     # ^[a-zA-Z0-9_\-\.]{1,64}$
url.open         { url:    "https://..." }            # http(s):// only
group.run        { target: "alias-from-pc-yaml" }
status.get       {}
```

Unknown args keys → 400.

## Response shape

200 / 502 (success or agent rejection):

```json
{
  "status":     "ok" | "error",
  "id":         "01J...",
  "code":       null | "rejected" | "failed" | "internal",
  "message":    null | "<human-readable>",
  "data":       null | { ...command-specific... },
  "latency_ms": 42
}
```

Special non-2xx outcomes:

- **400** → `{ "detail": "<error-key>" }` (bad schema, body too large, etc.)
- **401** → `{ "detail": "missing_bearer" }` or `{ "detail": "invalid_token" }`
- **409** → `{ "detail": "duplicate_id" }`  (replay)
- **413** → `{ "detail": "body_too_large" }`
- **429** → `{ "status": "rate_limited", "retry_after_seconds": 1.7 }`
- **503** → `{ "status": "agent_offline", "role": "pc"|"bridge", "id": "..." }`
- **504** → `{ "status": "timeout", "role": "pc"|"bridge", "id": "..." }`

## Quick reference: curl

```bash
TOKEN=<USER_API_KEY>
URL=https://your-relay.up.railway.app

# status
curl -H "Authorization: Bearer $TOKEN" $URL/v1/status

# lock
curl -X POST $URL/v1/cmd \
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d "{\"id\":\"$(uuidgen)\",\"ts\":$(date +%s),\"cmd\":\"power.lock\",\"args\":{}}"

# open app
curl -X POST $URL/v1/cmd \
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d "{\"id\":\"$(uuidgen)\",\"ts\":$(date +%s),\"cmd\":\"app.open\",\"args\":{\"target\":\"vscode\"}}"

# audit
curl -H "Authorization: Bearer $TOKEN" "$URL/v1/audit?limit=20"
```
