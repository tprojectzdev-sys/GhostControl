"""Execute a validated command on the local PC.

Hard rules:
  * no shell strings ever — every external invocation uses an argv list
  * apps and groups are resolved through the whitelist; an unknown alias is rejected
  * urls are validated against the local url_policy
  * power.* uses Windows binaries / Win32 calls only

This module raises :class:`CommandRejected` for whitelist failures and
:class:`CommandFailed` for execution failures. The caller turns either into
an ack with `status: "error"`.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import time
from typing import Any

from .status import build_status
from .whitelist import AppEntry, Whitelist


log = logging.getLogger("axon.agent.exec")


class CommandRejected(Exception):
    code = "rejected"


class CommandFailed(Exception):
    code = "failed"


_POWER_DELAY_DEFAULT = 5  # seconds
_GROUP_MAX_STEPS = 16


def execute(cmd: str, args: dict[str, Any], wl: Whitelist) -> dict[str, Any]:
    """Run a single command. Returns the `data` field of the ack on success."""
    started = time.monotonic()

    if cmd == "status.get":
        data = build_status()
    elif cmd == "power.shutdown":
        data = _power_shutdown(args)
    elif cmd == "power.restart":
        data = _power_restart(args)
    elif cmd == "power.sleep":
        data = _power_sleep(args)
    elif cmd == "power.lock":
        data = _power_lock(args)
    elif cmd == "app.open":
        data = _app_open(args, wl)
    elif cmd == "url.open":
        data = _url_open(args, wl)
    elif cmd == "group.run":
        data = _group_run(args, wl)
    else:
        raise CommandRejected(f"unsupported on this agent: {cmd}")

    elapsed = int((time.monotonic() - started) * 1000)
    if isinstance(data, dict):
        data.setdefault("latency_ms", elapsed)
    return data


# --------------------------------------------------------------------------
# Power
# --------------------------------------------------------------------------


def _delay(args: dict[str, Any]) -> int:
    d = args.get("delay_seconds")
    if d is None:
        return _POWER_DELAY_DEFAULT
    if not isinstance(d, int) or not (0 <= d <= 60):
        raise CommandRejected("delay_seconds must be int 0..60")
    return d


def _is_windows() -> bool:
    return platform.system() == "Windows"


def _power_shutdown(args: dict[str, Any]) -> dict[str, Any]:
    if not _is_windows():
        raise CommandFailed("power commands require Windows")
    secs = _delay(args)
    _spawn(["shutdown.exe", "/s", "/t", str(secs)])
    return {"action": "shutdown", "delay_seconds": secs}


def _power_restart(args: dict[str, Any]) -> dict[str, Any]:
    if not _is_windows():
        raise CommandFailed("power commands require Windows")
    secs = _delay(args)
    _spawn(["shutdown.exe", "/r", "/t", str(secs)])
    return {"action": "restart", "delay_seconds": secs}


def _power_sleep(_args: dict[str, Any]) -> dict[str, Any]:
    if not _is_windows():
        raise CommandFailed("power commands require Windows")
    # rundll32 SetSuspendState(Hibernate=0, ForceCritical=0, DisableWakeEvent=0).
    # Note: if hibernation is enabled in Power Options, the first arg may need
    # to be flipped — Microsoft's documented behavior is buggy here. We use
    # the most widely-deployed invocation.
    _spawn(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
    return {"action": "sleep"}


def _power_lock(_args: dict[str, Any]) -> dict[str, Any]:
    if not _is_windows():
        raise CommandFailed("power commands require Windows")
    # Direct Win32 call avoids spawning a process. Fall back to rundll32 if needed.
    try:
        import ctypes
        if ctypes.windll.user32.LockWorkStation() == 0:  # type: ignore[attr-defined]
            raise OSError("LockWorkStation returned 0")
    except Exception:
        _spawn(["rundll32.exe", "user32.dll,LockWorkStation"])
    return {"action": "lock"}


# --------------------------------------------------------------------------
# Apps / URLs / Groups
# --------------------------------------------------------------------------


def _app_open(args: dict[str, Any], wl: Whitelist) -> dict[str, Any]:
    target = args.get("target")
    if not isinstance(target, str) or not target:
        raise CommandRejected("args.target required")
    entry: AppEntry | None = wl.apps.get(target)
    if entry is None:
        raise CommandRejected(f"app alias not in whitelist: {target}")
    if not os.path.isfile(entry.path):
        raise CommandFailed(f"app path not found: {entry.path}")
    argv = [entry.path, *entry.args]
    _spawn(argv)
    return {"action": "app.open", "target": target}


def _url_open(args: dict[str, Any], wl: Whitelist) -> dict[str, Any]:
    url = args.get("url")
    if not isinstance(url, str) or not url:
        raise CommandRejected("args.url required")
    if not wl.url_allowed(url):
        raise CommandRejected(f"url not allowed by policy: {url}")
    if _is_windows():
        # os.startfile uses the OS default handler; never invokes a shell.
        try:
            os.startfile(url)  # type: ignore[attr-defined]
        except OSError as e:
            raise CommandFailed(f"failed to open url: {e}") from e
    else:
        # Non-Windows fallback (useful for dev on macOS/Linux): use webbrowser.
        import webbrowser

        webbrowser.open(url, new=2)
    return {"action": "url.open", "url": url}


def _group_run(args: dict[str, Any], wl: Whitelist) -> dict[str, Any]:
    target = args.get("target")
    if not isinstance(target, str) or not target:
        raise CommandRejected("args.target required")
    steps = wl.groups.get(target)
    if not steps:
        raise CommandRejected(f"group alias not in whitelist: {target}")
    if len(steps) > _GROUP_MAX_STEPS:
        raise CommandRejected(f"group exceeds {_GROUP_MAX_STEPS} steps")

    results: list[dict[str, Any]] = []
    for i, step in enumerate(steps):
        sub_cmd = step.get("cmd", "")
        sub_args = step.get("args", {}) or {}
        # Disallow nested group.run and power.* inside a group — fewer footguns.
        if sub_cmd == "group.run" or sub_cmd.startswith("power."):
            raise CommandRejected(f"step {i}: {sub_cmd} not allowed inside a group")
        try:
            data = execute(sub_cmd, sub_args, wl)
            results.append({"step": i, "cmd": sub_cmd, "status": "ok", "data": data})
        except CommandRejected as e:
            results.append({"step": i, "cmd": sub_cmd, "status": "rejected", "message": str(e)})
        except CommandFailed as e:
            results.append({"step": i, "cmd": sub_cmd, "status": "error", "message": str(e)})

    return {"action": "group.run", "target": target, "steps": results}


# --------------------------------------------------------------------------
# subprocess helper
# --------------------------------------------------------------------------


def _spawn(argv: list[str]) -> None:
    """Launch a process detached from the agent. Never uses a shell."""
    try:
        creationflags = 0
        if _is_windows():
            # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            creationflags = 0x00000008 | 0x00000200
        subprocess.Popen(  # noqa: S603 — argv list, no shell, never user-controlled
            argv,
            shell=False,
            close_fds=True,
            creationflags=creationflags,
        )
    except FileNotFoundError as e:
        raise CommandFailed(f"executable not found: {argv[0]}") from e
    except OSError as e:
        raise CommandFailed(f"spawn failed: {e}") from e
