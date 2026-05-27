import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Clock3, Moon, ShieldCheck, TimerReset, Truck } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { KpiCard } from "@/components/KpiCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/services/apiClient";
import type { AttendanceRow } from "@/types/api";

function today() {
  return new Date().toISOString().slice(0, 10);
}

export function AttendancePage() {
  const [date, setDate] = useState(today());
  const attendance = useQuery({
    queryKey: ["attendance-daily", date],
    queryFn: () => api.attendanceDaily(date),
    refetchInterval: 20_000,
  });
  const rows = attendance.data?.rows || [];
  const summary = attendance.data?.summary;

  return (
    <div className="space-y-5">
      <section className="runtime-strip">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="runtime-eyebrow">ATTENDANCE RUNTIME</p>
            <h2 className="runtime-title">出勤与拘束时间台账</h2>
            <p className="runtime-subtitle">
              面向全员查看司机出库、入库、睡眠申报与每日拘束时间。睡眠校验规则：前日入库到今日出库不足 8 小时，6.5 小时睡眠申报会标记风险。
            </p>
          </div>
          <div className="flex items-center gap-2">
            <input
              className="h-10 rounded-xl border border-border bg-white px-3 text-sm font-semibold text-slate-800"
              type="date"
              value={date}
              onChange={(event) => setDate(event.target.value)}
            />
            <Button type="button" variant="secondary" onClick={() => attendance.refetch()}>
              刷新
            </Button>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <KpiCard title="出勤司机" value={summary?.total_drivers || 0} icon={Truck} tone="blue" />
        <KpiCard title="已出库" value={summary?.departed || 0} icon={Clock3} tone="green" />
        <KpiCard title="已入库" value={summary?.returned || 0} icon={ShieldCheck} tone="green" />
        <KpiCard title="睡眠风险" value={summary?.sleep_risk || 0} icon={AlertTriangle} tone={(summary?.sleep_risk || 0) ? "red" : "green"} />
        <KpiCard title="平均拘束" value={`${summary?.average_constraint_hours || 0}h`} icon={TimerReset} tone="blue" />
      </section>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-bold text-slate-950">每日出入库与拘束时间</h2>
              <p className="mt-1 text-sm text-slate-500">点呼时间按出库前 15-20 分钟、入库后 15-20 分钟生成稳定参考值；司机未申报字段会显示为未申报。</p>
            </div>
            <div className="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700">{attendance.data?.date || date}</div>
          </div>
        </CardHeader>
        <CardContent>
          {attendance.isError ? (
            <EmptyState title="出勤台账加载失败" detail={(attendance.error as Error).message} />
          ) : rows.length ? (
            <div className="overflow-x-auto">
              <table className="data-table min-w-[1180px]">
                <thead>
                  <tr>
                    <th>出库车辆</th>
                    <th>司机</th>
                    <th>睡眠时间（司机申报）</th>
                    <th>出库点呼时间</th>
                    <th>出库时间（司机申报）</th>
                    <th>入库时间（司机申报）</th>
                    <th>休息时间（司机申报）</th>
                    <th>入库点呼时间</th>
                    <th>每日拘束时间</th>
                    <th>睡眠校验</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <AttendanceTableRow key={`${row.date}-${row.driver_id}`} row={row} />
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title="暂无出勤数据" detail="当天没有派车或司机出入库报备。司机完成出库/入库后会自动进入台账。" />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function AttendanceTableRow({ row }: { row: AttendanceRow }) {
  return (
    <tr>
      <td>
        <div className="font-bold text-slate-950">{row.vehicle_plate || "-"}</div>
        <div className="text-xs text-slate-500">{row.assignment_count || 0} 单</div>
      </td>
      <td>
        <div className="font-bold text-slate-950">{row.driver_name || `司机 #${row.driver_id}`}</div>
        <div className="text-xs text-slate-500">{row.driver_code || row.driver_phone || "-"}</div>
      </td>
      <td>{formatHours(row.sleep_hours_reported)}</td>
      <td>{row.depart_call_time || "-"}</td>
      <td>{timeWithStatus(row.depart_time)}</td>
      <td>{timeWithStatus(row.return_time)}</td>
      <td>{formatHours(row.rest_hours_reported)}</td>
      <td>{row.return_call_time || "-"}</td>
      <td>
        <span className="text-sm font-black text-slate-950">{formatHours(row.constraint_hours)}</span>
      </td>
      <td>
        <div className="flex min-w-60 items-start gap-2">
          <span className={`mt-0.5 rounded-full p-1 ${riskClass(row.sleep_risk_level)}`}>
            {row.sleep_risk_level === "ok" ? <Moon size={13} /> : <AlertTriangle size={13} />}
          </span>
          <div>
            <div className="text-xs font-bold text-slate-800">{riskLabel(row.sleep_risk_level)}</div>
            <div className="mt-1 text-xs leading-5 text-slate-500">{row.sleep_risk_message || "-"}</div>
            {row.previous_return_time ? <div className="mt-1 text-[11px] text-slate-400">前次入库 {row.previous_return_time}</div> : null}
          </div>
        </div>
      </td>
    </tr>
  );
}

function formatHours(value?: number | null) {
  if (value === null || value === undefined) return "未申报";
  return `${Number(value).toFixed(Number.isInteger(value) ? 0 : 1)}h`;
}

function timeWithStatus(value?: string | null) {
  if (!value) return "未申报";
  return (
    <div>
      <div className="font-bold text-slate-950">{value}</div>
    </div>
  );
}

function riskLabel(level?: string) {
  if (level === "ok") return "正常";
  if (level === "danger") return "风险";
  return "待确认";
}

function riskClass(level?: string) {
  if (level === "ok") return "bg-emerald-50 text-emerald-700";
  if (level === "danger") return "bg-red-50 text-red-700";
  return "bg-amber-50 text-amber-700";
}
