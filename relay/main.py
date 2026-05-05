"""Axon Remote — Cloud Relay.

A small, stateless WebSocket router that:

  * accepts authenticated HTTP POSTs from phone/dashboard at /v1/cmd
  * keeps long-lived WSS connections from the PC agent and LAN bridge
  * forwards commands to the right agent (power.wake → bridge, else → pc)
  * waits for an ack, returns it to the caller
  * rate-limits by token, deduplicates by command id, and writes a JSONL audit

It does NOT store the command whitelist (that lives only on the PC agent),
does NOT interpret command semantics, and does NOT execute anything.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import OrderedDict
from contextlib import asynccontextmanager
from typing import Any

from fastapi import (
    FastAPI,
    Header,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import ValidationError

import audit
from config import Settings, load_settings
from ratelimit import RateLimiter
from schemas import (
    BRIDGE_COMMANDS,
    MAX_BODY_BYTES,
    AgentHello,
    Command,
    CommandAck,
    StatusReport,
)
from ws_manager import AgentConn, WSManager


log = logging.getLogger("axon.relay")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


# --------------------------------------------------------------------------
# App-wide state (instantiated in the lifespan so tests can inject mocks)
# --------------------------------------------------------------------------


class AppState:
    settings: Settings
    ws: WSManager
    limiter: RateLimiter
    seen_ids: "OrderedDict[str, float]"

    def __init__(self) -> None:
        self.settings = load_settings()
        self.ws = WSManager()
        self.limiter = RateLimiter(
            default_per_min=self.settings.rate_limit_per_min,
            power_per_min=self.settings.power_rate_limit_per_min,
        )
        # bounded LRU of recently-seen command ids (replay/dedup window)
        self.seen_ids = OrderedDict()


@asynccontextmanager
async def lifespan(app: FastAPI):
    state = AppState()
    app.state.app = state
    audit.replay_recent_from_disk(state.settings.audit_log_path)
    log.info(
        "relay starting: rate=%s/min power=%s/min replay=%ss timeout=%ss",
        state.settings.rate_limit_per_min,
        state.settings.power_rate_limit_per_min,
        state.settings.replay_window_secs,
        state.settings.command_timeout_secs,
    )
    yield
    log.info("relay shutting down")


app = FastAPI(
    title="Axon Remote — Cloud Relay",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# Dashboard runs on a different origin during dev. Tighten this to your
# deployed dashboard host in production via env var if you care.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Timestamp", "X-Signature"],
    max_age=3600,
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _state(req: Request | WebSocket) -> AppState:
    return req.app.state.app  # type: ignore[no-any-return]


def _check_bearer(authorization: str | None, expected: str, settings: Settings) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing_bearer")
    presented = authorization[len("Bearer ") :].strip()
    if not settings.consteq(presented, expected):
        raise HTTPException(status_code=401, detail="invalid_token")


def _replay_check(state: AppState, cmd: Command) -> None:
    now = int(time.time())
    if abs(now - cmd.ts) > state.settings.replay_window_secs:
        raise HTTPException(status_code=400, detail="stale_or_skewed_timestamp")
    if cmd.id in state.seen_ids:
        raise HTTPException(status_code=409, detail="duplicate_id")
    state.seen_ids[cmd.id] = time.monotonic()
    # Trim: drop entries older than 2x the replay window.
    cutoff = time.monotonic() - 2 * state.settings.replay_window_secs
    while state.seen_ids:
        oldest_id, oldest_t = next(iter(state.seen_ids.items()))
        if oldest_t < cutoff:
            state.seen_ids.popitem(last=False)
        else:
            break


def _route_role(cmd_name: str) -> str:
    return "bridge" if cmd_name in BRIDGE_COMMANDS else "pc"


def _client_ip(req: Request) -> str:
    fwd = req.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return req.client.host if req.client else "?"


# --------------------------------------------------------------------------
# HTTP endpoints
# --------------------------------------------------------------------------


@app.get("/healthz", response_class=PlainTextResponse)
async def healthz() -> str:
    return "ok"


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "service": "axon-relay",
        "version": "1.0.0",
        "endpoints": ["/healthz", "/v1/cmd", "/v1/status", "/v1/audit", "/v1/ws/agent"],
    }


@app.post("/v1/cmd")
async def post_cmd(
    request: Request,
    authorization: str | None = Header(default=None),
) -> JSONResponse:
    state = _state(request)
    settings = state.settings

    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="body_too_large")

    _check_bearer(authorization, settings.user_api_key, settings)

    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="invalid_json")
    try:
        cmd = Command(**payload)
    except ValidationError as e:
        # Pydantic's default error dicts can include a non-serializable
        # `ctx.error` (the raw ValueError); we trim to JSON-safe fields only.
        issues = [
            {"loc": list(err.get("loc", [])), "msg": err.get("msg", ""), "type": err.get("type", "")}
            for err in e.errors()
        ]
        raise HTTPException(status_code=400, detail={"err": "schema", "issues": issues})

    kind = "power" if cmd.cmd.startswith("power.") else "general"
    allowed, retry_after = state.limiter.allow(principal="user", kind=kind)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"status": "rate_limited", "retry_after_seconds": round(retry_after, 2)},
            headers={"Retry-After": str(int(retry_after) + 1)},
        )

    _replay_check(state, cmd)

    role = _route_role(cmd.cmd)

    audit_event = {
        "kind": "cmd_in",
        "id": cmd.id,
        "cmd": cmd.cmd,
        "args": cmd.args,
        "route_to": role,
        "src_ip": _client_ip(request),
    }

    try:
        ack_dict = await state.ws.send_and_wait(
            role=role,
            command=cmd.model_dump(),
            timeout=settings.command_timeout_secs,
        )
    except LookupError:
        audit.write_event(settings.audit_log_path, **audit_event, outcome="agent_offline")
        return JSONResponse(
            status_code=503,
            content={"status": "agent_offline", "role": role, "id": cmd.id},
        )
    except asyncio.TimeoutError:
        audit.write_event(settings.audit_log_path, **audit_event, outcome="timeout")
        return JSONResponse(
            status_code=504,
            content={"status": "timeout", "role": role, "id": cmd.id},
        )

    try:
        ack = CommandAck(**ack_dict)
    except ValidationError:
        ack = CommandAck(id=cmd.id, status="error", code="bad_ack", message="invalid ack from agent")

    audit.write_event(
        settings.audit_log_path,
        **audit_event,
        outcome=ack.status,
        ack_code=ack.code,
        ack_message=ack.message,
    )

    http_status = 200 if ack.status == "ok" else 502
    return JSONResponse(
        status_code=http_status,
        content={
            "status": ack.status,
            "id": cmd.id,
            "code": ack.code,
            "message": ack.message,
            "data": ack.data,
            "latency_ms": ack.latency_ms,
        },
    )


@app.get("/v1/status")
async def get_status(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    state = _state(request)
    _check_bearer(authorization, state.settings.user_api_key, state.settings)
    return state.ws.status()


@app.get("/v1/audit")
async def get_audit(
    request: Request,
    limit: int = 50,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    state = _state(request)
    _check_bearer(authorization, state.settings.user_api_key, state.settings)
    limit = max(1, min(500, limit))
    return {"events": audit.recent(limit), "limit": limit}


# --------------------------------------------------------------------------
# WebSocket endpoint for the PC agent and the bridge
# --------------------------------------------------------------------------


@app.websocket("/v1/ws/agent")
async def ws_agent(ws: WebSocket) -> None:
    state = _state(ws)
    settings = state.settings
    await ws.accept()

    # 1. Auth handshake (first frame must be a hello).
    try:
        first = await asyncio.wait_for(ws.receive_text(), timeout=10.0)
        hello = AgentHello(**json.loads(first))
    except (asyncio.TimeoutError, json.JSONDecodeError, ValidationError, KeyError):
        await ws.close(code=4000, reason="bad_hello")
        return

    expected_token = (
        settings.pc_agent_token if hello.role == "pc" else settings.bridge_agent_token
    )
    if not settings.consteq(hello.token, expected_token):
        await ws.close(code=4401, reason="unauthorized")
        return

    conn: AgentConn = await state.ws.attach(role=hello.role, agent_id=hello.agent_id, ws=ws)
    audit.write_event(
        settings.audit_log_path,
        kind="agent_connect",
        role=hello.role,
        agent_id=hello.agent_id,
        os=hello.os,
        hostname=hello.hostname,
    )
    await ws.send_text(json.dumps({"type": "welcome", "now": int(time.time())}))

    # 2. Receive loop.
    try:
        while True:
            raw = await ws.receive_text()
            conn.last_seen = time.time()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            mtype = msg.get("type")
            if mtype == "ack":
                state.ws.resolve_ack(conn, msg)
            elif mtype == "status":
                try:
                    sr = StatusReport(**msg)
                    conn.last_status = sr.model_dump(exclude_none=True)
                except ValidationError:
                    pass
            elif mtype == "ping":
                await ws.send_text(json.dumps({"type": "pong", "now": int(time.time())}))
            elif mtype == "pong":
                pass
            else:
                # Ignore unknown message types — forward-compat.
                continue
    except WebSocketDisconnect:
        pass
    except Exception as e:  # pragma: no cover  defensive
        log.warning("ws receive error: %s", e)
    finally:
        await state.ws.detach(conn)
        audit.write_event(
            settings.audit_log_path,
            kind="agent_disconnect",
            role=conn.role,
            agent_id=conn.agent_id,
        )


# --------------------------------------------------------------------------
# Standalone runner (Railway uses Procfile / start command)
# --------------------------------------------------------------------------


def run() -> None:
    import uvicorn

    settings = load_settings()
    uvicorn.run(
        "relay.main:app",
        host="0.0.0.0",
        port=settings.port,
        log_level="info",
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    run()
