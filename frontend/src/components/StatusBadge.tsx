import { cn } from "@/lib/utils";

const statusMap: Record<string, string> = {
  assigned: "bg-blue-50 text-blue-700 ring-blue-200",
  unconfirmed: "bg-yellow-50 text-yellow-800 ring-yellow-300",
  unassigned: "bg-red-50 text-red-700 ring-red-200",
  confirmed: "bg-cyan-50 text-cyan-700 ring-cyan-200",
  departed: "bg-indigo-50 text-indigo-700 ring-indigo-200",
  arrived: "bg-teal-50 text-teal-700 ring-teal-200",
  in_service: "bg-violet-50 text-violet-700 ring-violet-200",
  completed: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  returned: "bg-slate-100 text-slate-700 ring-slate-200",
  parsed: "bg-blue-50 text-blue-700 ring-blue-200",
  failed: "bg-red-50 text-red-700 ring-red-200",
  confirmed_draft: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  pending: "bg-stone-50 text-stone-700 ring-stone-300",
  settled: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  unsettled: "bg-orange-100 text-orange-800 ring-orange-300",
  exception: "bg-red-50 text-red-700 ring-red-200",
  open: "bg-red-50 text-red-700 ring-red-200",
  processing: "bg-amber-50 text-amber-700 ring-amber-200",
  closed: "bg-slate-100 text-slate-700 ring-slate-200",
  delay: "bg-orange-50 text-orange-700 ring-orange-200",
  complaint: "bg-rose-50 text-rose-700 ring-rose-200",
  accident: "bg-red-50 text-red-700 ring-red-200",
  critical: "bg-red-100 text-red-800 ring-red-300",
  high: "bg-orange-50 text-orange-700 ring-orange-200",
  medium: "bg-blue-50 text-blue-700 ring-blue-200",
  low: "bg-slate-100 text-slate-700 ring-slate-200",
  enabled: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  disabled: "bg-slate-100 text-slate-500 ring-slate-200",
  active: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  available: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  maintenance: "bg-amber-50 text-amber-700 ring-amber-200",
  retired: "bg-slate-100 text-slate-600 ring-slate-200",
  trialing: "bg-blue-50 text-blue-700 ring-blue-200",
  paused: "bg-amber-50 text-amber-700 ring-amber-200",
  cancelled: "bg-red-50 text-red-700 ring-red-200",
};

const statusLabelMap: Record<string, string> = {
  assigned: "已派车",
  unconfirmed: "未确认",
  unassigned: "未派车",
  confirmed: "已确认",
  departed: "已出库",
  arrived: "已到达",
  in_service: "服务中",
  completed: "已完成",
  returned: "已归库",
  parsed: "已解析",
  failed: "失败",
  confirmed_draft: "已确认",
  pending: "待处理",
  settled: "已结算",
  unsettled: "未结算",
  exception: "异常",
  open: "待处理",
  processing: "处理中",
  closed: "已关闭",
  delay: "延误",
  complaint: "客诉",
  accident: "事故",
  critical: "紧急",
  high: "高",
  medium: "中",
  low: "低",
  enabled: "已启用",
  disabled: "已停用",
  active: "启用中",
  available: "正常",
  maintenance: "维修",
  retired: "减车",
  trialing: "试用中",
  paused: "已暂停",
  cancelled: "已取消",
  admin: "管理员",
  dispatcher: "调度员",
  driver: "司机",
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
      {statusLabelMap[key] || key}
    </span>
  );
}
