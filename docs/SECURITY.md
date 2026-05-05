# Security model

A short, honest description of what this system protects against and what
it doesn't. Read it once. It will save you from bad assumptions later.

## Threat model

This is a **single-user, personal** system. The realistic adversaries are:

1. **Someone who steals or finds the iPhone.** Worst case: they get
   bearer-token access to your PC's whitelisted commands. They cannot
   execute arbitrary code on the PC because of the local whitelist.
2. **A scanner that finds the relay's public URL.** Without the bearer
   token, they get 401 on every endpoint, with no information leak.
3. **A determined attacker on the network path** (e.g., a hostile Wi-Fi
   AP). Defeated by HTTPS / WSS with a valid TLS chain.
4. **Someone who compromises the relay host (Railway).** They can
   forward arbitrary commands to your PC — but only commands that pass
   the local whitelist. They cannot exfiltrate the whitelist; the relay
   never sees it.

Out of scope: nation-state actors, physical access to the PC, supply-chain
attacks on Python / npm, hostile Apple developer ID, etc.

## Defense layers

```
  iPhone ---HTTPS+Bearer--->  Relay  ---WSS+Bearer--->  PC Agent
                              |                         |
                              | rate limit              | local YAML whitelist
                              | replay window           | argv-only spawn
                              | JSONL audit             | per-id dedup
```

### Transport
- TLS 1.2+ (Railway terminates with managed certs).
- HSTS via Railway's HTTPS-only domains.
- WSS (`wss://`) for both agent and bridge connections.

### Authentication
- Three independent bearer tokens (user, pc-agent, bridge-agent).
- Tokens are 32 bytes of CSPRNG hex. Constant-time compare on the relay.
- Stored hashed? No — they're stored as-is in env vars on Railway. The
  relay only ever compares them in constant time. (Hashing a single user's
  long-random token doesn't add much; rotation is what matters.)
- Rotation: change the env var on the relay, redeploy, update clients.
  The whole roundtrip is < 2 minutes.

### Authorization
- The relay routes by command name (`power.wake` → bridge, else → pc).
- The PC agent re-validates **every** command against
  [`whitelist.yaml`](../agent/whitelist.example.yaml). An alias not in the
  YAML is dropped with an audit log entry.
- `app.open` paths come from the YAML, never from the wire.
- `url.open` is filtered by `url_policy` (`allow_any_https` or hostname
  allowlist) before launch.
- `group.run` cannot include `power.*` or nested groups.

### Replay / dedup
- Relay rejects commands with `|now - ts| > 120s`.
- Relay rejects re-used `id` values (LRU keeps the last few thousand for
  ~4 minutes).
- PC agent has a 5-minute dedup window on incoming commands as a second
  layer.

### Rate limiting
- 60 req/min per token at the relay edge (general bucket).
- 10 req/min per token for `power.*` (stricter bucket).
- Buckets are per-token, in-memory, single-process. If you scale the
  relay, swap for Redis.

### Audit log
- Every command, agent connect, agent disconnect → JSONL line on the
  relay.
- Includes `id`, `cmd`, `args`, src IP, outcome, ack code/message.
- The dashboard's Activity tab and the iOS app's Activity card both read
  the last 50 events from `/v1/audit`.

## What is **not** in this model

We deliberately omitted:

- **HMAC request signing.** Pure bearer-over-TLS is enough at this scale.
  Adding HMAC would require either complicated Shortcut "Run JavaScript"
  steps or a custom iOS app. Phase 2 if/when you want it.
- **OAuth / OIDC / device pairing UI.** A single user with a single
  password manager is the auth flow.
- **mTLS.** Overkill for one user. The relay's TLS cert is good enough.
- **Hardware-backed token storage on iPhone.** `@AppStorage` writes to
  `UserDefaults`. Lock the Shortcuts app behind Face ID and trust the
  iOS sandbox. If you stop being the only user, move to Keychain.
- **Persistent command queues.** If the agent is offline,
  `/v1/cmd` returns 503 immediately. The phone retries. Simple is good.

## What you should still do

- **Use a wired Ethernet for the PC.** WoL is unreliable on Wi-Fi.
- **Disable Fast Startup in Windows.** Several power features (especially
  WoL) misbehave with it on.
- **Don't put your `USER_API_KEY` into a public Shortcut.** Keep
  Shortcuts behind Face ID.
- **Rotate tokens twice a year.** Or sooner if you suspect leakage. It
  takes two minutes.
- **Read the audit log occasionally.** If you see commands you didn't
  send, rotate everything immediately.

## What an attacker actually can't do

Even with a fully compromised relay AND a leaked iPhone token:

- They can't exfiltrate files. There's no file-read command.
- They can't run arbitrary executables. There's no path-on-the-wire
  command.
- They can't `cmd /c whatever`. There's no shell anywhere.
- They can't pivot. The agent is outbound-only and only trusts the relay
  hostname.

The blast radius is limited to:
- Your whitelisted apps (so don't whitelist `cmd.exe`).
- The URLs allowed by your `url_policy`.
- Power state changes.

That is exactly the design intent.
