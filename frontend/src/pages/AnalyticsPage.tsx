import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  CircleDollarSign,
  Clock3,
  Medal,
  Route,
  UserCheck,
} from "lucide-react";
import { KpiCard } from "@/components/KpiCard";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/services/apiClient";

function isoDate(offsetDays: number) {
  const date = new Date();
  date.setDate(date.getDate() + offsetDays);
  return date.toISOString().slice(0, 10);
}

function money(value?: number) {
  return `JPY ${Math.round(value || 0).toLocaleString()}`;
}

function rate(value?: number) {
  return `${Number(value || 0).toFixed(1)}%`;
}

function metricTone(value: number, good = 90) {
  if (value >= good) return "text-emerald-700 bg-emerald-50 ring-emerald-200";
  if (value >= 70) return "text-amber-700 bg-amber-50 ring-amber-200";
  return "text-red-700 bg-red-50 ring-red-200";
}

export function AnalyticsPage() {
  const [dateFrom, setDateFrom] = useState(isoDate(-29));
  const [dateTo, setDateTo] = useState(isoDate(0));
  const analytics = useQuery({
    queryKey: ["analytics-summary", dateFrom, dateTo],
    queryFn: () => api.analyticsSummary({ date_from: dateFrom, date_to: dateTo }),
  });

  const maxOrders = useMemo(() => {
    return Math.max(...(analytics.data?.trend || []).map((item) => item.order_count), 1);
  }, [analytics.data?.trend]);

  if (analytics.isLoading) {
    return <div className="panel p-8 text-sm text-slate-500">正在加载经营分析...</div>;
  }
  if (analytics.isError || !analytics.data) {
    return <div className="panel p-8 text-sm text-red-600">经营分析接口加载失败，请检查后端运行状态。</div>;
  }

  const data = analytics.data;
  const topIncomeDriver = data.driver_performance[0];
  const avgOnTime = data.kpis.avg_driver_ontime_rate || 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-500">SaaS 经营分析</p>
          <h2 className="mt-1 text-2xl font-bold text-slate-950">司机绩效与运营 BI</h2>
          <p className="mt-1 text-sm text-slate-500">以订单、派车、执行报备和异常记录为基础，不做复杂 HR 绩效。</p>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-border bg-white p-2">
          <input className="h-9 rounded-md border border-border px-3 text-sm" type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
          <span className="text-xs text-slate-400">至</span>
          <input className="h-9 rounded-md border border-border px-3 text-sm" type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
        </div>
      </div>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
        <KpiCard title="订单数" value={data.kpis.order_count} icon={BarChart3} tone="blue" caption={`${data.date_from} - ${data.date_to}`} />
        <KpiCard title="总收入" value={money(data.kpis.revenue)} icon={CircleDollarSign} tone="green" />
        <KpiCard title="已派车" value={data.kpis.assigned_count} icon={Route} tone="violet" />
        <KpiCard title="整体完成率" value={rate(data.kpis.completion_rate)} icon={CheckCircle2} tone={data.kpis.completion_rate >= 80 ? "green" : "amber"} />
        <KpiCard title="司机准时率" value={rate(avgOnTime)} icon={Clock3} tone={avgOnTime >= 80 ? "green" : "amber"} />
        <KpiCard title="客诉率" value={rate(data.kpis.incident_rate)} icon={AlertTriangle} tone={data.kpis.incident_rate > 5 ? "red" : "slate"} />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardHeader>
            <h3 className="text-base font-bold text-slate-950">司机 KPI 排行</h3>
            <p className="mt-1 text-sm text-slate-500">按司机收入、完成单、准时率和客诉率综合查看。</p>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] text-sm">
                <thead className="text-left text-xs font-semibold text-slate-500">
                  <tr>
                    <th className="py-2">排名</th>
                    <th className="py-2">司机</th>
                    <th className="py-2">订单</th>
                    <th className="py-2">完成</th>
                    <th className="py-2">完成率</th>
                    <th className="py-2">准时率</th>
                    <th className="py-2">客诉率</th>
                    <th className="py-2 text-right">司机收入</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {data.driver_performance.map((driver) => (
                    <tr key={`${driver.driver_id}-${driver.driver_name}`}>
                      <td className="py-3">
                        <span className="inline-flex h-7 min-w-7 items-center justify-center rounded-full bg-blue-50 px-2 text-xs font-bold text-blue-700">
                          {driver.rank || "-"}
                        </span>
                      </td>
                      <td className="py-3">
                        <div className="font-semibold text-slate-950">{driver.driver_name || "未分配司机"}</div>
                        <div className="text-xs text-slate-500">{driver.driver_code || "-"}</div>
                      </td>
                      <td className="py-3">{driver.order_count}</td>
                      <td className="py-3">{driver.completed_count}</td>
                      <td className="py-3">
                        <span className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ring-1 ${metricTone(driver.completion_rate, 85)}`}>
                          {rate(driver.completion_rate)}
                        </span>
                      </td>
                      <td className="py-3">
                        <span className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ring-1 ${metricTone(driver.ontime_rate || 0, 85)}`}>
                          {rate(driver.ontime_rate)}
                        </span>
                      </td>
                      <td className="py-3">
                        <span className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ring-1 ${(driver.complaint_rate || 0) > 5 ? "bg-red-50 text-red-700 ring-red-200" : "bg-slate-100 text-slate-700 ring-slate-200"}`}>
                          {rate(driver.complaint_rate)}
                        </span>
                      </td>
                      <td className="py-3 text-right font-bold text-slate-950">{money(driver.driver_income)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h3 className="text-base font-bold text-slate-950">收入排行</h3>
            <p className="mt-1 text-sm text-slate-500">优先显示司机结算收入；没有工资字段时会显示 0。</p>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.driver_performance.slice(0, 8).map((driver) => (
              <div key={`income-${driver.driver_id}-${driver.driver_name}`} className="rounded-lg border border-border p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-bold text-slate-950">
                      #{driver.rank} {driver.driver_name || "未分配司机"}
                    </div>
                    <div className="text-xs text-slate-500">
                      完成 {driver.completed_count} / {driver.order_count} 单，准时 {rate(driver.ontime_rate)}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-bold text-slate-950">{money(driver.driver_income)}</div>
                    <div className="text-xs text-slate-500">客诉 {driver.complaint_count || 0}</div>
                  </div>
                </div>
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-emerald-500"
                    style={{
                      width: `${Math.min(((driver.driver_income || 0) / Math.max(topIncomeDriver?.driver_income || 1, 1)) * 100, 100)}%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <h3 className="text-base font-bold text-slate-950">订单趋势</h3>
            <p className="mt-1 text-sm text-slate-500">按日期展示订单数量和完成占比。</p>
          </CardHeader>
          <CardContent>
            <div className="flex h-72 items-end gap-2 overflow-x-auto border-b border-slate-200 pb-3">
              {data.trend.map((item) => (
                <div key={item.date} className="flex min-w-9 flex-1 flex-col items-center justify-end gap-2">
                  <div className="flex w-full flex-col justify-end rounded-t-md bg-blue-100" style={{ height: `${Math.max((item.order_count / maxOrders) * 220, item.order_count ? 18 : 4)}px` }}>
                    <div className="rounded-t-md bg-blue-500" style={{ height: `${Math.max((item.completed_count / Math.max(item.order_count, 1)) * 100, 8)}%` }} />
                  </div>
                  <span className="text-[10px] font-semibold text-slate-400">{item.date.slice(5)}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h3 className="text-base font-bold text-slate-950">旅行社收入</h3>
            <p className="mt-1 text-sm text-slate-500">按收入和待结算金额查看主要来源。</p>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.agency_revenue.slice(0, 8).map((agency) => (
              <div key={agency.agency_name} className="rounded-lg border border-border p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-bold text-slate-950">{agency.agency_name}</div>
                    <div className="text-xs text-slate-500">{agency.order_count} 单 · 已派 {agency.assigned_count} 单</div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-bold text-slate-950">{money(agency.revenue)}</div>
                    <div className="text-xs text-amber-600">待结算 {money(agency.pending_amount)}</div>
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <h3 className="text-base font-bold text-slate-950">车辆利用率</h3>
            <p className="mt-1 text-sm text-slate-500">按服务时间估算车辆占用，不接地图和排班系统。</p>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.vehicle_utilization.map((vehicle) => (
              <div key={`${vehicle.vehicle_id}-${vehicle.plate_number}`} className="rounded-lg border border-border p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-bold text-slate-950">{vehicle.plate_number || "未分配车辆"}</div>
                    <div className="text-xs text-slate-500">{vehicle.vehicle_type || "-"} · {vehicle.order_count} 单 · {vehicle.busy_hours} 小时</div>
                  </div>
                  <div className="text-sm font-bold text-slate-950">{rate(vehicle.utilization_rate)}</div>
                </div>
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full bg-emerald-500" style={{ width: `${Math.min(vehicle.utilization_rate, 100)}%` }} />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h3 className="text-base font-bold text-slate-950">司机绩效口径</h3>
            <p className="mt-1 text-sm text-slate-500">第一版口径保持简单，方便试运行时校准。</p>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-slate-600">
            <div className="flex items-start gap-3 rounded-lg bg-slate-50 p-3">
              <UserCheck className="mt-0.5 text-blue-600" size={18} />
              <p>完成率 = 已完成或已归库订单 / 已分配订单。</p>
            </div>
            <div className="flex items-start gap-3 rounded-lg bg-slate-50 p-3">
              <Clock3 className="mt-0.5 text-emerald-600" size={18} />
              <p>准时率 = 到达上车点或开始服务报备时间不晚于计划开始时间 15 分钟。</p>
            </div>
            <div className="flex items-start gap-3 rounded-lg bg-slate-50 p-3">
              <AlertTriangle className="mt-0.5 text-red-600" size={18} />
              <p>客诉率 = 客诉异常数量 / 已分配订单。当前只统计系统内 incident_type=complaint。</p>
            </div>
            <div className="flex items-start gap-3 rounded-lg bg-slate-50 p-3">
              <Medal className="mt-0.5 text-amber-600" size={18} />
              <p>收入排行优先使用订单里的司机工资字段，后续可接入更完整的司机结算规则。</p>
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
