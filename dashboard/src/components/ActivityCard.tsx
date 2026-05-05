import { useEffect, useMemo, useState } from "react";
import { Activity, CheckCircle2, XCircle, AlertTriangle } from "lucide-react";
import type { AuditEvent, Session } from "../api";
import { getAudit } from "../api";
import { formatRelative } from "../lib/format";

interface Props {
  session: Session;
  trigger: number; // bump to force a refresh
}

export function ActivityCard({ session, trigger }: Props) {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const list = await getAudit(session, 50);
        if (!cancelled) {
          setEvents(list.slice().reverse());
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    }
    load();
    const t = setInterval(load, 5000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [session, trigger]);

  const grouped = useMemo(() => events, [events]);

  return (
    <div className="card p-6 flex flex-col gap-4 min-h-[340px]">
      <div className="flex items-center justify-between">
        <div className="text-sm text-ink-300 uppercase tracking-[0.18em] flex items-center gap-2">
          <Activity size={14} strokeWidth={1.6} /> Activity
        </div>
        <div className="text-[11px] text-ink-400">last 50</div>
      </div>
      {error && <div className="text-xs text-err">audit fetch failed: {error}</div>}
      <div className="flex flex-col divide-y divide-white/[0.04] scrollbar-thin overflow-y-auto max-h-[420px] pr-1">
        {grouped.length === 0 && (
          <div className="text-sm text-ink-400 py-8 text-center">No activity yet.</div>
        )}
        {grouped.map((e, i) => (
          <Row key={`${e.ts_ms}-${i}`} e={e} />
        ))}
      </div>
    </div>
  );
}

function Row({ e }: { e: AuditEvent }) {
  const isCmd = e.kind === "cmd_in";
  const ok = e.outcome === "ok";
  const Icon = ok ? CheckCircle2 : e.outcome === "agent_offline" || e.outcome === "timeout" ? AlertTriangle : XCircle;
  const tone = ok
    ? "text-ok"
    : e.outcome === "agent_offline" || e.outcome === "timeout"
    ? "text-warn"
    : isCmd
    ? "text-err"
    : "text-ink-300";
  const title = isCmd
    ? `${e.cmd}${getTarget(e)}`
    : e.kind === "agent_connect"
    ? `${e.role} connected (${e.agent_id})`
    : e.kind === "agent_disconnect"
    ? `${e.role} disconnected (${e.agent_id})`
    : e.kind;
  const detail = isCmd
    ? e.outcome + (e.ack_message ? ` · ${e.ack_message}` : "")
    : e.os ?? e.hostname ?? "";

  return (
    <div className="flex items-center gap-3 py-3">
      <span className={"shrink-0 w-7 h-7 rounded-lg grid place-items-center bg-white/[0.03] " + tone}>
        <Icon size={14} strokeWidth={1.7} />
      </span>
      <div className="flex-1 min-w-0">
        <div className="text-sm truncate">{title}</div>
        <div className="text-[11px] text-ink-400 truncate">{detail}</div>
      </div>
      <div className="text-[11px] text-ink-400 shrink-0 tabular-nums">
        {formatRelative(e.ts_ms)}
      </div>
    </div>
  );
}

function getTarget(e: AuditEvent): string {
  const args = e.args as Record<string, unknown> | undefined;
  if (!args) return "";
  if (typeof args.target === "string") return ` ${args.target}`;
  if (typeof args.url === "string") return ` ${args.url}`;
  return "";
}
