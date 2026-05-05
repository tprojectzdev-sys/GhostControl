import type { AgentStatus } from "../api";
import { formatUptime, formatRelative } from "../lib/format";

interface Props {
  pc: AgentStatus | null;
  bridge: AgentStatus | null;
  nowMs: number;
}

export function StatusCard({ pc, bridge, nowMs }: Props) {
  return (
    <div className="card p-6 flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div className="text-sm text-ink-300 uppercase tracking-[0.18em]">Status</div>
        <div className="text-[11px] text-ink-400">
          updated {formatRelative(nowMs)}
        </div>
      </div>
      <Row
        label="PC Agent"
        sub={pc?.status?.hostname ?? pc?.agent_id ?? "—"}
        online={Boolean(pc)}
        right={pc ? formatUptime(pc.uptime_seconds) : "offline"}
      />
      <Row
        label="WoL Bridge"
        sub={bridge?.status?.hostname ?? bridge?.agent_id ?? "—"}
        online={Boolean(bridge)}
        right={bridge ? formatUptime(bridge.uptime_seconds) : "offline"}
      />
      {pc?.status?.os && (
        <div className="text-xs text-ink-400 truncate" title={pc.status.os}>
          {pc.status.os}
        </div>
      )}
    </div>
  );
}

interface RowProps {
  label: string;
  sub: string;
  online: boolean;
  right: string;
}

function Row({ label, sub, online, right }: RowProps) {
  return (
    <div className="flex items-center gap-3">
      <span
        className={
          "w-2.5 h-2.5 rounded-full shrink-0 " +
          (online ? "bg-ok dot-online animate-pulseSoft" : "bg-err dot-offline")
        }
      />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium">{label}</div>
        <div className="text-xs text-ink-400 truncate">{sub}</div>
      </div>
      <div className="text-xs text-ink-300 tabular-nums">{right}</div>
    </div>
  );
}
