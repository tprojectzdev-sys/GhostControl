# Axon Agent (Windows PC)

Runs on the PC you want to control. Maintains an outbound WebSocket to the
relay and executes only commands whose alias appears in your local
[`whitelist.yaml`](./whitelist.example.yaml).

It opens **no** inbound ports.

## What it can do

| Command           | Effect on Windows                                              |
|-------------------|----------------------------------------------------------------|
| `power.shutdown`  | `shutdown.exe /s /t <delay>` (default 5s)                      |
| `power.restart`   | `shutdown.exe /r /t <delay>`                                   |
| `power.sleep`     | `rundll32 powrprof.dll,SetSuspendState 0,1,0`                  |
| `power.lock`      | `LockWorkStation()`                                            |
| `app.open`        | `CreateProcess` on the path in `whitelist.yaml`                |
| `url.open`        | `os.startfile(url)` after url-policy check                     |
| `group.run`       | Sequence of the above (no power, no nested groups)             |
| `status.get`      | Returns CPU / RAM / uptime / idle seconds / foreground app     |

`power.wake` is **not** handled here — that's the bridge's job.

## Install

Requires Python 3.11+. Then, in this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# whitelist + env
copy whitelist.example.yaml whitelist.yaml
copy .env.example .env
notepad whitelist.yaml      # edit aliases / paths
notepad .env                # paste relay URL + PC_AGENT_TOKEN

# run once interactively to confirm it connects
.\run-agent.ps1
```

You should see something like:

```
INFO axon.agent.client: connecting to wss://...
INFO axon.agent.client: relay welcome: {"type":"welcome","now":...}
INFO axon.agent.whitelist: whitelist loaded: 5 apps, 2 groups, url_policy=allow_any_https
```

Then install the scheduled task so the agent comes up at login:

```powershell
# Open PowerShell as Administrator:
.\install-task.ps1
```

Tail the live log:

```powershell
Get-Content -Wait .\logs\agent.log
```

To uninstall:

```powershell
.\uninstall-task.ps1
```

## Whitelist

The YAML file is the source of truth for what your phone can do on this PC.
The file is watched: save it and the agent reloads within 2 seconds with
no restart.

If parsing fails, the agent runs with an **empty** whitelist (and logs
loudly). It never falls back to "allow everything".

See [`whitelist.example.yaml`](./whitelist.example.yaml) for the schema.

## Why a Scheduled Task and not a Windows Service?

App launches and `LockWorkStation` need to run in your interactive desktop
session. A normal Windows Service runs in session 0, which doesn't have a
visible desktop — apps launch invisibly and you can't see them. The
scheduled task triggers `AtLogOn` so the agent inherits your interactive
session for free.

Side effect: when no user is logged in, the agent isn't running, so
`status.get` returns "agent_offline" until you log in. That's the right
behavior for a personal machine.

If you specifically need power commands while logged out, install a second
copy in `LocalSystem` mode (Phase 2 — not in MVP).

## What it never does

- Never accepts inbound connections.
- Never executes a path it didn't read from `whitelist.yaml`.
- Never invokes a shell. All process launches are argv lists.
- Never trusts the relay blindly: every command is re-validated locally.
