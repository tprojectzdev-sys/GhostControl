import { useEffect, useState } from "react";
import { formatClock, greeting } from "../lib/format";
import { CheckCircle2, AlertCircle } from "lucide-react";

interface Props {
  online: boolean;
  hostname?: string;
}

export function Greeting({ online, hostname }: Props) {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="card p-7 flex flex-col gap-5 col-span-1 lg:col-span-2 min-h-[180px]">
      <div className="flex items-baseline justify-between flex-wrap gap-3">
        <div className="text-[44px] leading-none font-semibold tracking-tight">
          {formatClock(now)}
        </div>
        <div className={online ? "pill-ok" : "pill-err"}>
          {online ? <CheckCircle2 size={12} /> : <AlertCircle size={12} />}
          <span className="uppercase tracking-wide">
            {online ? "All systems nominal" : "Agent offline"}
          </span>
        </div>
      </div>
      <div>
        <div className="text-ink-300 text-sm">
          {greeting(now)}
          {hostname ? `, ${hostname}` : ""}
        </div>
        <div className="text-2xl font-medium mt-1">Overview</div>
      </div>
    </div>
  );
}
