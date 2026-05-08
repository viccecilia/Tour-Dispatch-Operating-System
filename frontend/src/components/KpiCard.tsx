import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export function KpiCard({
  title,
  value,
  icon: Icon,
  tone = "blue",
  caption,
}: {
  title: string;
  value?: number | string;
  icon: LucideIcon;
  tone?: "blue" | "green" | "amber" | "red" | "slate" | "violet";
  caption?: string;
}) {
  const toneMap = {
    blue: "bg-blue-50 text-blue-700",
    green: "bg-emerald-50 text-emerald-700",
    amber: "bg-amber-50 text-amber-700",
    red: "bg-red-50 text-red-700",
    slate: "bg-slate-100 text-slate-700",
    violet: "bg-violet-50 text-violet-700",
  };

  return (
    <div className="panel p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-slate-500">{title}</p>
          <p className="mt-2 text-3xl font-bold tracking-normal text-slate-950">{value ?? 0}</p>
        </div>
        <div className={cn("flex h-10 w-10 items-center justify-center rounded-lg", toneMap[tone])}>
          <Icon size={20} />
        </div>
      </div>
      {caption ? <p className="mt-3 text-xs text-slate-500">{caption}</p> : null}
    </div>
  );
}
