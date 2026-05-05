/**
 * Tiny client for the Axon relay.
 * All calls go through this so auth headers and error handling live in one place.
 */

export type CommandName =
  | "power.shutdown"
  | "power.restart"
  | "power.sleep"
  | "power.lock"
  | "power.wake"
  | "app.open"
  | "url.open"
  | "group.run"
  | "status.get";

export interface CommandArgs {
  target?: string;
  url?: string;
  delay_seconds?: number;
}

export interface AgentStatus {
  agent_id: string;
  role: "pc" | "bridge";
  connected_at: number;
  last_seen: number;
  uptime_seconds: number;
  status: {
    online?: boolean;
    uptime_seconds?: number;
    cpu_pct?: number | null;
    ram_pct?: number | null;
    idle_seconds?: number | null;
    foreground_app?: string | null;
    os?: string | null;
    hostname?: string | null;
  };
}

export interface RelayStatus {
  pc: AgentStatus | null;
  bridge: AgentStatus | null;
  now: number;
}

export interface CommandResponse {
  status: "ok" | "error" | "rate_limited" | "agent_offline" | "timeout";
  id?: string;
  code?: string | null;
  message?: string | null;
  data?: Record<string, unknown> | null;
  latency_ms?: number | null;
  retry_after_seconds?: number;
  role?: string;
}

export interface AuditEvent {
  ts_ms: number;
  kind: string;
  id?: string;
  cmd?: string;
  args?: unknown;
  route_to?: string;
  outcome?: string;
  ack_code?: string | null;
  ack_message?: string | null;
  src_ip?: string;
  role?: string;
  agent_id?: string;
  os?: string | null;
  hostname?: string | null;
}

const STORAGE_KEY = "axon.session";

export interface Session {
  baseUrl: string;
  token: string;
}

export function getSession(): Session | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Session;
    if (!parsed.baseUrl || !parsed.token) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function saveSession(s: Session): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
}

export function clearSession(): void {
  window.localStorage.removeItem(STORAGE_KEY);
}

function buildHeaders(session: Session): HeadersInit {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${session.token}`,
  };
}

function buildUrl(session: Session, path: string): string {
  const base = session.baseUrl.replace(/\/+$/, "");
  return `${base}${path}`;
}

function uuid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export async function getStatus(session: Session): Promise<RelayStatus> {
  const res = await fetch(buildUrl(session, "/v1/status"), {
    headers: buildHeaders(session),
  });
  if (res.status === 401) throw new AuthError();
  if (!res.ok) throw new Error(`status ${res.status}`);
  return res.json() as Promise<RelayStatus>;
}

export async function getAudit(session: Session, limit = 50): Promise<AuditEvent[]> {
  const res = await fetch(buildUrl(session, `/v1/audit?limit=${limit}`), {
    headers: buildHeaders(session),
  });
  if (res.status === 401) throw new AuthError();
  if (!res.ok) throw new Error(`audit ${res.status}`);
  const data = (await res.json()) as { events: AuditEvent[] };
  return data.events ?? [];
}

export async function sendCommand(
  session: Session,
  cmd: CommandName,
  args: CommandArgs = {}
): Promise<CommandResponse> {
  const body = JSON.stringify({
    id: uuid(),
    ts: Math.floor(Date.now() / 1000),
    cmd,
    args,
  });
  const res = await fetch(buildUrl(session, "/v1/cmd"), {
    method: "POST",
    headers: buildHeaders(session),
    body,
  });
  if (res.status === 401) throw new AuthError();
  // Parse JSON regardless of status; relay returns structured errors.
  let payload: CommandResponse;
  try {
    payload = (await res.json()) as CommandResponse;
  } catch {
    payload = { status: "error", message: `HTTP ${res.status}` };
  }
  return payload;
}

export class AuthError extends Error {
  constructor() {
    super("unauthorized");
    this.name = "AuthError";
  }
}

export async function probeRelay(baseUrl: string): Promise<boolean> {
  try {
    const res = await fetch(`${baseUrl.replace(/\/+$/, "")}/healthz`);
    return res.ok;
  } catch {
    return false;
  }
}
