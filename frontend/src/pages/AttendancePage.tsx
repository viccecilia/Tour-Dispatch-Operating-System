import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, Clock3, Download, Moon, Search, ShieldCheck, TimerReset, Truck } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { KpiCard } from "@/components/KpiCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/services/apiClient";
import type { AttendanceRow } from "@/types/api";

function today() {
  return new Date().toISOString().slice(0, 10);
}

function daysAgo(days: number) {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date.toISOString().slice(0, 10);
}

function datesBetween(from: string, to: string) {
  const start = new Date(`${from}T00:00:00`);
  const end = new Date(`${to}T00:00:00`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start > end) return [];
  const days: string[] = [];
  const cursor = new Date(start);
  while (cursor <= end && days.length < 62) {
    days.push(cursor.toISOString().slice(0, 10));
    cursor.setDate(cursor.getDate() + 1);
  }
  return days;
}

export function AttendancePage() {
  const [filters, setFilters] = useState({ date_from: daysAgo(7), date_to: today(), keyword: "", risk: "" });
  const [selectedDate, setSelectedDate] = useState("");
  const ledger = useQuery({
    queryKey: ["attendance-ledger", filters],
    queryFn: () => api.attendanceLedger(filters),
    refetchInterval: 20_000,
  });
  const exportCsv = useMutation({
    mutationFn: () => api.attendanceExportCsv(filters),
    onSuccess: (csv) => {
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `attendance_ledger_${filters.date_from}_${filters.date_to}.csv`;
      link.click();
      URL.revokeObjectURL(url);
    },
  });
  const rows = ledger.data?.rows || [];
  const summary = ledger.data?.summary;
  const rowsByDate = useMemo(() => {
    return rows.reduce<Record<string, AttendanceRow[]>>((acc, row) => {
      const key = row.date;
      acc[key] = acc[key] || [];
      acc[key].push(row);
      return acc;
    }, {});
  }, [rows]);
  const calendarDays = useMemo(() => datesBetween(filters.date_from, filters.date_to), [filters.date_from, filters.date_to]);
  const tableRows = selectedDate ? rows.filter((row) => row.date === selectedDate) : rows;
  const hasFilter = useMemo(() => Boolean(filters.keyword || filters.risk), [filters.keyword, filters.risk]);

  return (
    <div className="space-y-5">
      <section className="runtime-strip">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="runtime-eyebrow">ATTENDANCE LEDGER</p>
            <h2 className="runtime-title">出勤与拘束时间台账</h2>
            <p className="runtime-subtitle">
              按日期、司机、车牌和睡眠风险筛选。记录人员当日车辆、睡眠申报、出库点呼、入库点呼、休息申报和每日拘束时间。
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="secondary" onClick={() => ledger.refetch()}>
              刷新
            </Button>
            <Button type="button" onClick={() => exportCsv.mutate()} disabled={exportCsv.isPending || !rows.length}>
              <Download size={15} />
              导出 Excel CSV
            </Button>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <KpiCard title="出勤记录" value={summary?.total_rows || 0} icon={Truck} tone="blue" />
        <KpiCard title="已出库" value={summary?.departed || 0} icon={Clock3} tone="green" />
        <KpiCard title="已入库" value={summary?.returned || 0} icon={ShieldCheck} tone="green" />
        <KpiCard title="睡眠风险" value={summary?.sleep_risk || 0} icon={AlertTriangle} tone={(summary?.sleep_risk || 0) ? "red" : "green"} />
        <KpiCard title="平均拘束" value={`${summary?.average_constraint_hours || 0}h`} icon={TimerReset} tone="blue" />
      </section>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-bold text-slate-950">出勤日历</h2>
              <p className="mt-1 text-sm text-slate-500">右上角为当日出勤数，左下角为事故或异常数；点击日期后，下方明细只显示当天记录。</p>
            </div>
            {selectedDate ? (
              <Button type="button" variant="secondary" onClick={() => setSelectedDate("")}>
                显示全部
              </Button>
            ) : null}
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-2 sm:grid-cols-4 lg:grid-cols-7">
            {calendarDays.map((date) => {
              const dayRows = rowsByDate[date] || [];
              const incidentCount = dayRows.filter((row) => row.sleep_risk_level === "danger" || row.report_status === "missing").length;
              const active = selectedDate === date;
              return (
                <button
                  key={date}
                  type="button"
                  onClick={() => setSelectedDate(active ? "" : date)}
                  className={`relative min-h-24 rounded-xl border p-3 text-left transition ${
                    active ? "border-blue-500 bg-blue-50 shadow-sm" : "border-border bg-white hover:border-blue-300"
                  }`}
                >
                  <div className="text-xs font-black text-slate-500">{date.slice(5)}</div>
                  <div className="mt-5 text-sm font-bold text-slate-950">{dayRows.length ? "有出勤" : "无记录"}</div>
                  <span className="absolute right-2 top-2 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-black text-emerald-700">
                    {dayRows.length}
                  </span>
                  {incidentCount ? (
                    <span className="absolute bottom-2 left-2 rounded-full bg-red-50 px-2 py-0.5 text-xs font-black text-red-700">
                      异常 {incidentCount}
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-bold text-slate-950">出勤明细</h2>
              <p className="mt-1 text-sm text-slate-500">出库点呼按出库前 15-20 分钟，入库点呼按入库后 15-20 分钟生成参考记录。</p>
            </div>
            <div className="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700">
              {ledger.data?.date_from || filters.date_from} 至 {ledger.data?.date_to || filters.date_to}
            </div>
          </div>
          <div className="mt-4 grid gap-3 lg:grid-cols-[160px_160px_1fr_150px]">
            <input
              className="h-10 rounded-xl border border-border bg-white px-3 text-sm font-semibold text-slate-800"
              type="date"
              value={filters.date_from}
              onChange={(event) => setFilters({ ...filters, date_from: event.target.value })}
            />
            <input
              className="h-10 rounded-xl border border-border bg-white px-3 text-sm font-semibold text-slate-800"
              type="date"
              value={filters.date_to}
              onChange={(event) => setFilters({ ...filters, date_to: event.target.value })}
            />
            <label className="flex h-10 items-center gap-2 rounded-xl border border-border bg-white px-3 text-sm">
              <Search size={16} className="text-slate-400" />
              <input
                className="w-full bg-transparent outline-none"
                placeholder="搜索司机、司机代码、电话、车牌"
                value={filters.keyword}
                onChange={(event) => setFilters({ ...filters, keyword: event.target.value })}
              />
            </label>
            <select
              className="h-10 rounded-xl border border-border bg-white px-3 text-sm font-semibold text-slate-800"
              value={filters.risk}
              onChange={(event) => setFilters({ ...filters, risk: event.target.value })}
            >
              <option value="">全部风险</option>
              <option value="ok">正常</option>
              <option value="warning">待确认</option>
              <option value="danger">风险</option>
            </select>
          </div>
        </CardHeader>
        <CardContent>
          {ledger.isError ? (
            <EmptyState title="出勤台账加载失败" detail={(ledger.error as Error).message} />
          ) : tableRows.length ? (
            <div className="overflow-x-auto">
              <table className="data-table min-w-[1520px]">
                <thead>
                  <tr>
                    <th>日期</th>
                    <th>车牌</th>
                    <th>司机</th>
                    <th>睡眠时间</th>
                    <th>出库点呼</th>
                    <th>出库时间</th>
                    <th>入库时间</th>
                    <th>休息时间</th>
                    <th>入库点呼</th>
                    <th>每日拘束</th>
                    <th>前次入库</th>
                    <th>睡眠校验</th>
                  </tr>
                </thead>
                <tbody>
                  {tableRows.map((row) => (
                    <AttendanceTableRow key={`${row.date}-${row.driver_id}-${row.vehicle_id || row.vehicle_plate}`} row={row} />
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              title={hasFilter ? "没有匹配的出勤记录" : "暂无出勤数据"}
              detail="当天没有派车或司机出入库报备时，不会生成台账行。"
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function AttendanceTableRow({ row }: { row: AttendanceRow }) {
  return (
    <tr>
      <td className="font-bold text-slate-950">{row.date}</td>
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
      <td className="text-xs text-slate-500">{row.previous_return_time || "-"}</td>
      <td>
        <div className="flex min-w-60 items-start gap-2">
          <span className={`mt-0.5 rounded-full p-1 ${riskClass(row.sleep_risk_level)}`}>
            {row.sleep_risk_level === "ok" ? <Moon size={13} /> : <AlertTriangle size={13} />}
          </span>
          <div>
            <div className="text-xs font-bold text-slate-800">{riskLabel(row.sleep_risk_level)}</div>
            <div className="mt-1 text-xs leading-5 text-slate-500">{row.sleep_risk_message || "-"}</div>
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
  return <span className="font-bold text-slate-950">{value}</span>;
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
