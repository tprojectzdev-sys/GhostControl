"""Wire-format schemas shared by HTTP and WebSocket layers.

The schema is intentionally tiny and strict. Every command a phone/dashboard
sends, and every command the relay forwards to an agent, has the same shape:

    { "id": "<uuid>", "ts": <unix>, "cmd": "<dotted.name>", "args": { ... } }

Unknown fields are dropped (extra="ignore" is the Pydantic v2 default for
BaseModel; we explicitly forbid extra to make schema drift loud).
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


COMMAND_NAMES = (
    "power.shutdown",
    "power.restart",
    "power.sleep",
    "power.lock",
    "power.wake",
    "app.open",
    "url.open",
    "group.run",
    "status.get",
)

# Commands that are routed to the bridge (LAN side) instead of the PC agent.
BRIDGE_COMMANDS = {"power.wake"}

# Cap on body size to prevent abuse; commands are tiny.
MAX_BODY_BYTES = 4 * 1024

# Replay window: reject if |now - ts| exceeds this (seconds).
REPLAY_WINDOW_SECONDS = 120

_TARGET_RE = re.compile(r"^[a-zA-Z0-9_\-\.]{1,64}$")


class Command(BaseModel):
    """Canonical command. The wire format every client speaks."""

    model_config = {"extra": "forbid"}

    id: str = Field(..., min_length=8, max_length=64)
    ts: int = Field(..., ge=0)
    cmd: str
    args: dict[str, Any] = Field(default_factory=dict)

    @field_validator("cmd")
    @classmethod
    def _check_cmd(cls, v: str) -> str:
        if v not in COMMAND_NAMES:
            raise ValueError(f"unknown command: {v!r}")
        return v

    @field_validator("args")
    @classmethod
    def _check_args(cls, v: dict[str, Any]) -> dict[str, Any]:
        # Args are typed per-command; we do shallow shape checks here to avoid
        # hostile payloads. The agent re-validates against its whitelist.
        target = v.get("target")
        if target is not None and not (isinstance(target, str) and _TARGET_RE.match(target)):
            raise ValueError("args.target must be a short alphanumeric string")
        url = v.get("url")
        if url is not None and not (isinstance(url, str) and url.startswith(("http://", "https://"))):
            raise ValueError("args.url must be an http(s) URL")
        delay = v.get("delay_seconds")
        if delay is not None and not (isinstance(delay, int) and 0 <= delay <= 60):
            raise ValueError("args.delay_seconds must be int 0..60")
        return v

    @classmethod
    def new(cls, cmd: str, args: dict[str, Any] | None = None) -> "Command":
        return cls(id=str(uuid.uuid4()), ts=int(time.time()), cmd=cmd, args=args or {})


class CommandAck(BaseModel):
    """Agent's acknowledgement after executing (or rejecting) a command."""

    model_config = {"extra": "ignore"}

    id: str
    status: Literal["ok", "error"]
    code: str | None = None
    message: str | None = None
    data: dict[str, Any] | None = None
    latency_ms: int | None = None


class AgentHello(BaseModel):
    """First frame an agent sends after the WSS handshake."""

    model_config = {"extra": "ignore"}

    type: Literal["hello"] = "hello"
    role: Literal["pc", "bridge"]
    agent_id: str = Field(..., min_length=1, max_length=64)
    token: str = Field(..., min_length=16, max_length=256)
    version: str = "1.0"
    os: str | None = None
    hostname: str | None = None


class StatusReport(BaseModel):
    """Heartbeat payload from agent → relay."""

    model_config = {"extra": "ignore"}

    type: Literal["status"] = "status"
    online: bool = True
    uptime_seconds: int | None = None
    cpu_pct: float | None = None
    ram_pct: float | None = None
    idle_seconds: int | None = None
    foreground_app: str | None = None
    os: str | None = None
    hostname: str | None = None


class AgentMessage(BaseModel):
    """Wrapper the relay uses to receive any frame from an agent."""

    model_config = {"extra": "ignore"}

    type: Literal["hello", "ack", "status", "pong"]
    # The other fields are populated depending on type and parsed lazily by
    # the WS handler — see ws_manager.handle_agent_message.
    payload: dict[str, Any] | None = None
