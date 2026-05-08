import { cn } from "@/lib/utils";

const statusMap: Record<string, string> = {
  assigned: "bg-blue-50 text-blue-700 ring-blue-200",
  unassigned: "bg-amber-50 text-amber-700 ring-amber-200",
  confirmed: "bg-cyan-50 text-cyan-700 ring-cyan-200",
  departed: "bg-indigo-50 text-indigo-700 ring-indigo-200",
  arrived: "bg-teal-50 text-teal-700 ring-teal-200",
  in_service: "bg-violet-50 text-violet-700 ring-violet-200",
  completed: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  returned: "bg-slate-100 text-slate-700 ring-slate-200",
  parsed: "bg-blue-50 text-blue-700 ring-blue-200",
  failed: "bg-red-50 text-red-700 ring-red-200",
  confirmed_draft: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  pending: "bg-amber-50 text-amber-700 ring-amber-200",
  settled: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  unsettled: "bg-orange-50 text-orange-700 ring-orange-200",
};

export function StatusBadge({ status, className }: { status?: string | null; className?: string }) {
  const key = status || "pending";
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center rounded-full px-2 text-xs font-semibold ring-1",
        statusMap[key] || "bg-slate-100 text-slate-700 ring-slate-200",
        className,
      )}
    >
      {key}
    </span>
  );
}
