import { useState } from "react";
import {
  Monitor,
  Activity,
  Wifi,
  Settings,
  LogOut,
  Power,
} from "lucide-react";

interface Props {
  active: string;
  onChange: (v: string) => void;
  onLogout: () => void;
}

const tabs = [
  { id: "overview", icon: Monitor, label: "Overview" },
  { id: "actions", icon: Power, label: "Actions" },
  { id: "activity", icon: Activity, label: "Activity" },
  { id: "network", icon: Wifi, label: "Network" },
  { id: "settings", icon: Settings, label: "Settings" },
];

export function Sidebar({ active, onChange, onLogout }: Props) {
  const [hover, setHover] = useState<string | null>(null);
  return (
    <aside className="flex flex-col items-center justify-between py-6 px-3 bg-ink-900 border border-white/[0.04] rounded-card w-[68px] shrink-0">
      <div className="flex flex-col items-center gap-2">
        <div className="w-10 h-10 rounded-2xl bg-accent/15 text-accent grid place-items-center font-semibold text-lg">
          A
        </div>
        <div className="h-px w-6 bg-white/[0.06] my-3" />
        {tabs.map((t) => {
          const Icon = t.icon;
          const isActive = active === t.id;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => onChange(t.id)}
              onMouseEnter={() => setHover(t.id)}
              onMouseLeave={() => setHover(null)}
              className={
                "icon-btn relative " + (isActive ? "icon-btn-active" : "")
              }
              aria-label={t.label}
              aria-current={isActive ? "page" : undefined}
            >
              <Icon size={18} strokeWidth={1.6} />
              {hover === t.id && !isActive && (
                <span className="absolute left-[56px] whitespace-nowrap pill-mute z-10">
                  {t.label}
                </span>
              )}
            </button>
          );
        })}
      </div>
      <button
        type="button"
        onClick={onLogout}
        className="icon-btn"
        aria-label="Sign out"
        title="Sign out"
      >
        <LogOut size={18} strokeWidth={1.6} />
      </button>
    </aside>
  );
}
