import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bell, Camera, CheckCircle2, MapPin, Mic, Navigation, RefreshCw, ShieldAlert } from "lucide-react";
import { api } from "@/services/apiClient";
import type { Assignment } from "@/types/api";

const nextAction: Record<string, string> = {
  assigned: "确认订单",
  confirmed: "出库",
  departed: "到达上车点",
  arrived: "开始服务",
  in_service: "完成订单",
  completed: "归库",
  returned: "流程完成",
};

const statusLabel: Record<string, string> = {
  assigned: "待确认",
  confirmed: "已确认",
  departed: "已出库",
  arrived: "已到达",
  in_service: "服务中",
  completed: "已完成",
  returned: "已归库",
};

export function DriverAppPreviewPage() {
  const [driverId, setDriverId] = useState(1);
  const assignments = useQuery({ queryKey: ["driver-app-assignments", driverId], queryFn: () => api.driverAssignments(driverId), refetchInterval: 10000 });
  const dashboard = useQuery({ queryKey: ["driver-app-dashboard", driverId], queryFn: () => api.driverDashboard(driverId), refetchInterval: 10000 });
  const income = useQuery({ queryKey: ["driver-app-income", driverId], queryFn: () => api.driverIncome(driverId), refetchInterval: 10000 });
  const notifications = useQuery({ queryKey: ["driver-app-notifications", driverId], queryFn: () => api.driverNotifications(driverId), refetchInterval: 10000 });

  const rows = useMemo(() => assignments.data || [], [assignments.data]);
  const current = useMemo(() => pickCurrent(rows), [rows]);
  const activeRows = rows.filter((item) => !["completed", "returned"].includes(item.execution_status || ""));
  const completedRows = rows.filter((item) => ["completed", "returned"].includes(item.execution_status || ""));
  const action = current ? nextAction[current.execution_status || "assigned"] || "确认订单" : "暂无任务";

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-6">
      <div className="mx-auto max-w-[420px] overflow-hidden rounded-[32px] border border-slate-700 bg-slate-100 shadow-2xl">
        <div className="bg-slate-950 px-5 pb-5 pt-7 text-white">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-bold tracking-[0.18em] text-blue-300">司机端预览</p>
              <h1 className="mt-1 text-2xl font-black">今日任务</h1>
              <p className="mt-2 text-xs text-slate-300">浏览器预览用，正式端在微信小程序。</p>
            </div>
            <span className="rounded-full bg-emerald-400/15 px-3 py-1 text-xs font-bold text-emerald-200">在线</span>
          </div>
          <div className="mt-4 flex items-center gap-2 rounded-2xl bg-white/10 p-2">
            <span className="px-2 text-xs text-slate-300">司机ID</span>
            <input className="min-w-0 flex-1 rounded-xl bg-white px-3 py-2 text-sm font-bold text-slate-950 outline-none" value={driverId} onChange={(event) => setDriverId(Number(event.target.value || 1))} />
            <button className="rounded-xl bg-blue-600 px-3 py-2 text-xs font-bold text-white" onClick={() => void assignments.refetch()}>
              <RefreshCw size={14} />
            </button>
          </div>
        </div>

        <div className="space-y-4 p-4">
          <section className="grid grid-cols-3 gap-2">
            <MiniKpi label="今日订单" value={dashboard.data?.today_order_count || rows.length} />
            <MiniKpi label="已完成" value={dashboard.data?.today_completed_count || completedRows.length} />
            <MiniKpi label="今日收入" value={`¥${income.data?.today?.salary_amount || dashboard.data?.today_estimated_amount || 0}`} />
          </section>

          <section className="rounded-3xl border border-border bg-white p-4 shadow-sm">
            {current ? (
              <>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-black text-blue-700">{statusLabel[current.execution_status || "assigned"] || current.execution_status}</span>
                    <h2 className="mt-3 text-lg font-black text-slate-950">{current.start_time}-{current.end_time}</h2>
                    <p className="mt-2 text-xl font-black leading-snug text-slate-950">{current.pickup_location || "-"} → {current.dropoff_location || "-"}</p>
                  </div>
                  <CheckCircle2 className="text-blue-600" size={26} />
                </div>
                <div className="mt-3 rounded-2xl bg-slate-50 p-3 text-sm text-slate-600">
                  <p>{current.order_type || "-"} / {current.vehicle_type || "-"} / {current.plate_number || "-"}</p>
                  <p className="mt-1">订单号：{current.oid || current.order_id}</p>
                </div>
                <button className="mt-4 h-14 w-full rounded-2xl bg-emerald-600 text-lg font-black text-white shadow-lg shadow-emerald-600/20">
                  {action}
                </button>
                <div className="mt-3 grid grid-cols-4 gap-2">
                  <IconButton icon={<Navigation size={16} />} label="导航" />
                  <IconButton icon={<MapPin size={16} />} label="位置" />
                  <IconButton icon={<Camera size={16} />} label="照片" />
                  <IconButton icon={<ShieldAlert size={16} />} label="异常" danger />
                </div>
              </>
            ) : (
              <div className="py-8 text-center text-sm font-semibold text-slate-500">当前司机今天暂无任务</div>
            )}
          </section>

          <section className="rounded-3xl border border-border bg-white p-4">
            <div className="flex items-center justify-between">
              <h3 className="font-black text-slate-950">待执行任务</h3>
              <span className="text-xs font-bold text-slate-500">{activeRows.length} 单</span>
            </div>
            <div className="mt-3 space-y-2">
              {activeRows.slice(0, 5).map((item) => <TaskRow key={`${item.assignment_id || item.id}-${item.order_id}`} item={item} />)}
              {!activeRows.length ? <p className="py-3 text-center text-sm text-slate-500">暂无待执行任务</p> : null}
            </div>
          </section>

          <section className="rounded-3xl border border-border bg-white p-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="font-black text-slate-950">司机通知</h3>
              <Bell size={16} className="text-blue-600" />
            </div>
            {(notifications.data || []).slice(0, 3).map((item) => (
              <div key={item.id} className="border-t border-border py-3 first:border-t-0 first:pt-0">
                <p className="text-sm font-bold text-slate-900">{item.title}</p>
                <p className="mt-1 line-clamp-2 text-xs text-slate-500">{item.body || "-"}</p>
              </div>
            ))}
            {!(notifications.data || []).length ? <p className="text-sm text-slate-500">暂无通知</p> : null}
          </section>

          <section className="rounded-3xl border border-border bg-white p-4">
            <div className="flex items-center gap-2 text-sm font-bold text-slate-700">
              <Mic size={16} className="text-blue-600" />
              语音辅助 / 弱网补发 / 照片凭证已在小程序端实现
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function pickCurrent(rows: Assignment[]) {
  return rows.find((item) => ["confirmed", "departed", "arrived", "in_service"].includes(item.execution_status || "")) ||
    rows.find((item) => !["completed", "returned"].includes(item.execution_status || "")) ||
    rows[0];
}

function MiniKpi({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-2xl border border-border bg-white p-3 text-center">
      <div className="text-lg font-black text-slate-950">{value}</div>
      <div className="mt-1 text-[11px] font-bold text-slate-500">{label}</div>
    </div>
  );
}

function IconButton({ icon, label, danger }: { icon: React.ReactNode; label: string; danger?: boolean }) {
  return (
    <button className={`flex flex-col items-center justify-center rounded-2xl px-2 py-3 text-xs font-bold ${danger ? "bg-red-50 text-red-700" : "bg-blue-50 text-blue-700"}`}>
      {icon}
      <span className="mt-1">{label}</span>
    </button>
  );
}

function TaskRow({ item }: { item: Assignment }) {
  return (
    <div className="rounded-2xl bg-slate-50 p-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-black text-slate-950">{item.start_time}-{item.end_time}</p>
        <span className="rounded-full bg-white px-2 py-1 text-[11px] font-bold text-slate-600">{statusLabel[item.execution_status || "assigned"] || item.execution_status}</span>
      </div>
      <p className="mt-1 text-sm font-semibold text-slate-700">{item.pickup_location || "-"} → {item.dropoff_location || "-"}</p>
    </div>
  );
}
