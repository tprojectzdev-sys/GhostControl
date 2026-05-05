import type { AgentStatus } from "../api";
import { formatUptime, pct } from "../lib/format";
import { useEffect, useRef, useState } from "react";

interface Props {
  pc: AgentStatus | null;
}

export function StatsCard({ pc }: Props) {
  const cpu = pc?.status?.cpu_pct ?? null;
  const ram = pc?.status?.ram_pct ?? null;
  const idle = pc?.status?.idle_seconds ?? null;
  const fg = pc?.status?.foreground_app ?? null;

  const [cpuHistory, setCpuHistory] = useState<number[]>([]);
  const [ramHistory, setRamHistory] = useState<number[]>([]);
  const lastCpu = useRef<number | null>(null);
  const lastRam = useRef<number | null>(null);

  useEffect(() => {
    if (cpu != null && cpu !== lastCpu.current) {
      lastCpu.current = cpu;
      setCpuHistory((h) => [...h.slice(-23), cpu]);
    }
    if (ram != null && ram !== lastRam.current) {
      lastRam.current = ram;
      setRamHistory((h) => [...h.slice(-23), ram]);
    }
  }, [cpu, ram]);

  return (
    <div className="card p-6 flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div className="text-sm text-ink-300 uppercase tracking-[0.18em]">System</div>
        <div className="text-[11px] text-ink-400">heartbeat 30s</div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Stat label="CPU" value={pct(cpu)} history={cpuHistory} />
        <Stat label="Memory" value={pct(ram)} history={ramHistory} />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Mini label="Idle" value={idle != null ? formatUptime(idle) : "—"} />
        <Mini label="Foreground" value={fg ?? "—"} mono />
      </div>
    </div>
  );
}

function Stat({ label, value, history }: { label: string; value: string; history: number[] }) {
  return (
    <div className="rounded-2xl bg-ink-800/70 border border-white/[0.04] p-4">
      <div className="text-[11px] text-ink-400 uppercase tracking-wider">{label}</div>
      <div className="text-3xl font-semibold tabular-nums mt-1">{value}</div>
      <Sparkline values={history} />
    </div>
  );
}

function Mini({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-2xl bg-ink-800/70 border border-white/[0.04] p-4">
      <div className="text-[11px] text-ink-400 uppercase tracking-wider">{label}</div>
      <div
        className={
          "text-base font-medium mt-1 truncate " + (mono ? "font-mono text-sm" : "")
        }
        title={value}
      >
        {value}
      </div>
    </div>
  );
}

function Sparkline({ values }: { values: number[] }) {
  if (values.length < 2) {
    return (
      <div className="mt-3 h-10 w-full rounded bg-white/[0.02]" aria-hidden />
    );
  }
  const w = 120;
  const h = 36;
  const pad = 2;
  const max = Math.max(100, ...values);
  const min = Math.min(0, ...values);
  const range = Math.max(1, max - min);
  const step = (w - pad * 2) / Math.max(1, values.length - 1);
  const points = values
    .map((v, i) => {
      const x = pad + i * step;
      const y = h - pad - ((v - min) / range) * (h - pad * 2);
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="mt-3 w-full h-10" preserveAspectRatio="none">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.5" className="text-accent" />
    </svg>
  );
}
