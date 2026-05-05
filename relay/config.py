"""Relay configuration. Loaded entirely from environment variables so that
it deploys cleanly to Railway / Fly / any container host.

Required env vars:
  USER_API_KEY       - bearer token clients (phone, dashboard) must present
  PC_AGENT_TOKEN     - token the Windows PC agent presents on WSS connect
  BRIDGE_AGENT_TOKEN - token the Pi/LAN bridge presents on WSS connect

Optional:
  RATE_LIMIT_PER_MIN     (default 60)
  POWER_RATE_LIMIT_PER_MIN (default 10)
  AUDIT_LOG_PATH         (default ./audit.jsonl)
  COMMAND_TIMEOUT_SECS   (default 8)
  REPLAY_WINDOW_SECS     (default 120)
  PORT                   (default 8080; Railway sets this)
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass


def _env(name: str, default: str | None = None, *, required: bool = False) -> str:
    val = os.environ.get(name, default)
    if required and not val:
        raise RuntimeError(
            f"Missing required env var {name!r}. "
            f"Set it on the host (e.g. Railway → Variables) before starting the relay."
        )
    return val or ""


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as e:
        raise RuntimeError(f"Env var {name!r} must be an integer, got {raw!r}") from e


@dataclass(frozen=True)
class Settings:
    user_api_key: str
    pc_agent_token: str
    bridge_agent_token: str
    rate_limit_per_min: int
    power_rate_limit_per_min: int
    audit_log_path: str
    command_timeout_secs: int
    replay_window_secs: int
    port: int

    def consteq(self, presented: str, expected: str) -> bool:
        """Constant-time string compare — never short-circuit on length."""
        return secrets.compare_digest(presented.encode(), expected.encode())


def load_settings() -> Settings:
    return Settings(
        user_api_key=_env("USER_API_KEY", required=True),
        pc_agent_token=_env("PC_AGENT_TOKEN", required=True),
        bridge_agent_token=_env("BRIDGE_AGENT_TOKEN", required=True),
        rate_limit_per_min=_env_int("RATE_LIMIT_PER_MIN", 60),
        power_rate_limit_per_min=_env_int("POWER_RATE_LIMIT_PER_MIN", 10),
        audit_log_path=_env("AUDIT_LOG_PATH", "./audit.jsonl"),
        command_timeout_secs=_env_int("COMMAND_TIMEOUT_SECS", 8),
        replay_window_secs=_env_int("REPLAY_WINDOW_SECS", 120),
        port=_env_int("PORT", 8080),
    )
