import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  FileText,
  RadioTower,
  Route,
  Truck,
  Wrench,
} from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { KpiCard } from "@/components/KpiCard";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/services/apiClient";
import type { ResourceAlert } from "@/types/api";

export function DashboardPage() {
  const summary = useQuery({ queryKey: ["dashboard-summary"], queryFn: api.dashboardSummary, refetchInterval: 5000 });
  const drafts = useQuery({ queryKey: ["drafts"], queryFn: api.drafts, refetchInterval: 8000 });
  const assignments = useQuery({ queryKey: ["assignments"], queryFn: api.assignments, refetchInterval: 5000 });
  const resourceReminders = useQuery({ queryKey: ["resource-reminders"], queryFn: api.resourceReminders, refetchInterval: 30000 });

  if (summary.isLoading) {
    return <div className="panel p-8 text-sm text-slate-500">正在加载运营数据...</div>;
  }

  if (summary.isError) {
    return <div className="panel p-8 text-sm text-red-600">总览接口加载失败，请检查后端服务。</div>;
  }

  const data = summary.data || {};
  const execution = data.execution || {};
  const recentDrafts = (drafts.data || []).slice(0, 5);
  const recentAssignments = (assignments.data || []).slice(0, 6);

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard title="今日订单" value={data.today_orders} icon={ClipboardList} tone="blue" caption="来自订单与解析确认入库" />
        <KpiCard title="已派车" value={data.assigned_orders} icon={Truck} tone="green" caption="有效派车记录" />
        <KpiCard title="执行中" value={data.in_service_orders || execution.in_service} icon={RadioTower} tone="violet" />
        <KpiCard title="已完成" value={data.completed_orders || execution.completed} icon={CheckCircle2} tone="green" />
        <KpiCard title="未派车" value={data.unassigned_orders} icon={Route} tone="amber" />
        <KpiCard title="解析草稿" value={data.pending_drafts} icon={FileText} tone="blue" />
        <KpiCard title="未报备" value={data.unreported_orders} icon={AlertTriangle} tone="red" />
        <KpiCard title="异常提醒" value={data.open_incidents} icon={AlertTriangle} tone="red" caption={`高优先级 ${data.high_priority_incidents || 0}`} />
        <KpiCard title="资源提醒" value={data.resource_alerts} icon={Wrench} tone="red" caption={`过期 ${data.resource_expired_alerts || 0} · 即将到期 ${data.resource_upcoming_alerts || 0}`} />
        <KpiCard title="车辆出库" value={data.outbound_vehicles} icon={Truck} tone="amber" caption={`服务中 ${data.in_service_vehicles || 0} · 已入库 ${data.returned_vehicles || 0}`} />
      </section>

      <ResourceReminderOverview alerts={resourceReminders.data?.alerts || []} loading={resourceReminders.isLoading} />

      <section className="grid gap-6 xl:grid-cols-[1.3fr_0.9fr]">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-slate-950">今日执行流</h2>
                <p className="mt-1 text-sm text-slate-500">最近派车与司机回传状态。</p>
              </div>
              <StatusBadge status="active" />
            </div>
          </CardHeader>
          <CardContent>
            {recentAssignments.length ? (
              <div className="space-y-3">
                {recentAssignments.map((item) => (
                  <div key={`${item.assignment_id || item.id}-${item.order_id}`} className="flex items-center justify-between rounded-md border border-border px-4 py-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{item.oid || `ORDER-${item.order_id}`}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {item.start_time || "--:--"} {item.pickup_location || "-"} {"->"} {item.dropoff_location || "-"}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-slate-500">{item.driver_name || "-"}</span>
                      <StatusBadge status={item.execution_status || item.status || item.dispatch_status} />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState detail="重置 demo 数据后这里会显示最近派车。" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-base font-bold text-slate-950">最近草稿</h2>
            <p className="mt-1 text-sm text-slate-500">解析结果需要人工确认后进入订单池。</p>
          </CardHeader>
          <CardContent>
            {recentDrafts.length ? (
              <div className="space-y-3">
                {recentDrafts.map((draft) => (
                  <div key={draft.id} className="rounded-md border border-border px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="truncate text-sm font-semibold text-slate-900">{draft.raw_text}</p>
                      <StatusBadge status={draft.parse_status} />
                    </div>
                    <p className="mt-2 text-xs text-slate-500">
                      {draft.order_date || "-"} {draft.start_time || ""} · {draft.pickup_location || "-"} {"->"} {draft.dropoff_location || "-"}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState detail="暂无待确认草稿。" />
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

function ResourceReminderOverview({ alerts, loading }: { alerts: ResourceAlert[]; loading: boolean }) {
  const stats = {
    expired: alerts.filter((item) => item.status === "expired" || item.status === "invalid").length,
    upcoming: alerts.filter((item) => item.status === "upcoming").length,
    maintenance: alerts.filter((item) => item.status === "maintenance").length,
  };
  const visibleAlerts = alerts.slice(0, 4);

  return (
    <section className="panel p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50 text-amber-700">
            <Wrench size={20} />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-950">到期提醒</h2>
            <p className="text-sm text-slate-500">车辆点检、车检、司机体检和驾照到期集中在这里看。</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 text-xs font-bold">
          <span className="rounded-full bg-red-50 px-3 py-1 text-red-700">已过期 {stats.expired}</span>
          <span className="rounded-full bg-amber-50 px-3 py-1 text-amber-700">即将到期 {stats.upcoming}</span>
          <span className="rounded-full bg-blue-50 px-3 py-1 text-blue-700">维修 {stats.maintenance}</span>
        </div>
      </div>

      {loading ? (
        <p className="mt-3 text-sm text-slate-500">正在读取提醒...</p>
      ) : visibleAlerts.length ? (
        <div className="mt-3 grid gap-2 lg:grid-cols-4">
          {visibleAlerts.map((alert) => (
            <div key={`${alert.type}-${alert.id}-${alert.field}`} className="rounded-lg border border-border bg-white px-3 py-2">
              <div className="flex items-center justify-between gap-2">
                <b className="truncate text-sm text-slate-950">{alert.name || "-"}</b>
                <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-bold ${alert.status === "expired" || alert.status === "invalid" ? "bg-red-50 text-red-700" : alert.status === "maintenance" ? "bg-blue-50 text-blue-700" : "bg-amber-50 text-amber-700"}`}>
                  {alert.status === "expired" || alert.status === "invalid" ? "已过期" : alert.status === "maintenance" ? "维修" : "即将到期"}
                </span>
              </div>
              <p className="mt-1 truncate text-xs text-slate-600">{alert.label}</p>
              <p className="mt-0.5 truncate text-xs text-slate-500">{alert.message}</p>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm text-emerald-700">当前没有到期或维修提醒。</p>
      )}
    </section>
  );
}
