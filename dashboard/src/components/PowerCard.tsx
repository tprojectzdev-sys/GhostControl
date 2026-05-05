import { useState } from "react";
import { Power, RotateCw, Moon, Lock, Zap } from "lucide-react";
import type { CommandName, CommandResponse, Session } from "../api";
import { sendCommand } from "../api";

interface Props {
  session: Session;
  pcOnline: boolean;
  bridgeOnline: boolean;
  onResult: (cmd: CommandName, res: CommandResponse) => void;
}

const POWER_ACTIONS: {
  cmd: CommandName;
  label: string;
  icon: typeof Power;
  destructive?: boolean;
  needsBridge?: boolean;
  needsPc?: boolean;
}[] = [
  { cmd: "power.wake", label: "Wake", icon: Zap, needsBridge: true },
  { cmd: "power.lock", label: "Lock", icon: Lock, needsPc: true },
  { cmd: "power.sleep", label: "Sleep", icon: Moon, needsPc: true },
  { cmd: "power.restart", label: "Restart", icon: RotateCw, needsPc: true, destructive: true },
  { cmd: "power.shutdown", label: "Shutdown", icon: Power, needsPc: true, destructive: true },
];

export function PowerCard({ session, pcOnline, bridgeOnline, onResult }: Props) {
  const [pending, setPending] = useState<CommandName | null>(null);

  async function fire(cmd: CommandName, destructive: boolean) {
    if (destructive) {
      const ok = window.confirm(`Confirm ${cmd}?`);
      if (!ok) return;
    }
    setPending(cmd);
    try {
      const res = await sendCommand(session, cmd);
      onResult(cmd, res);
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="card p-6 flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div className="text-sm text-ink-300 uppercase tracking-[0.18em]">Power</div>
        <div className="text-[11px] text-ink-400">tap to send</div>
      </div>
      <div className="grid grid-cols-5 gap-3">
        {POWER_ACTIONS.map((a) => {
          const Icon = a.icon;
          const disabled =
            pending !== null ||
            (a.needsBridge && !bridgeOnline) ||
            (a.needsPc && !pcOnline);
          return (
            <button
              key={a.cmd}
              type="button"
              onClick={() => fire(a.cmd, Boolean(a.destructive))}
              disabled={disabled}
              className={
                "action-tile h-[112px] " +
                (a.destructive ? " hover:border-err/30" : "")
              }
              title={a.cmd + (disabled ? " (unavailable)" : "")}
            >
              <span
                className={
                  "w-9 h-9 rounded-xl grid place-items-center " +
                  (a.destructive
                    ? "bg-err/10 text-err"
                    : "bg-accent/10 text-accent")
                }
              >
                <Icon size={18} strokeWidth={1.7} />
              </span>
              <div className="mt-auto">
                <div className="text-sm font-medium">{a.label}</div>
                <div className="text-[11px] text-ink-400">{a.cmd}</div>
              </div>
              {pending === a.cmd && (
                <span className="absolute inset-0 grid place-items-center bg-ink-850/70 backdrop-blur-sm rounded-2xl">
                  <span className="text-xs text-ink-200">sending…</span>
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
