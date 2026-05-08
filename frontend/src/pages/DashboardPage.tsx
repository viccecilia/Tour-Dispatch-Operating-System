import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  FileText,
  RadioTower,
  Route,
  Timer,
  Truck,
} from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { KpiCard } from "@/components/KpiCard";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/services/apiClient";

export function DashboardPage() {
  const summary = useQuery({ queryKey: ["dashboard-summary"], queryFn: api.dashboardSummary });
  const drafts = useQuery({ queryKey: ["drafts"], queryFn: api.drafts });
  const assignments = useQuery({ queryKey: ["assignments"], queryFn: api.assignments });

  if (summary.isLoading) {
    return <div className="panel p-8 text-sm text-slate-500">正在加载运营数据...</div>;
  }

  if (summary.isError) {
    return <div className="panel p-8 text-sm text-red-600">Dashboard API 加载失败，请检查后端服务。</div>;
  }

  const data = summary.data || {};
  const execution = data.execution || {};
  const recentDrafts = (drafts.data || []).slice(0, 5);
  const recentAssignments = (assignments.data || []).slice(0, 6);

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard title="今日订单" value={data.today_orders} icon={ClipboardList} tone="blue" caption="来自订单与解析确认入库" />
        <KpiCard title="已派车" value={data.assigned_orders} icon={Truck} tone="green" caption="active assignments" />
        <KpiCard title="执行中" value={data.in_service_orders || execution.in_service} icon={RadioTower} tone="violet" />
        <KpiCard title="已完成" value={data.completed_orders || execution.completed} icon={CheckCircle2} tone="green" />
        <KpiCard title="未派车" value={data.unassigned_orders} icon={Route} tone="amber" />
        <KpiCard title="parser 草稿" value={data.pending_drafts} icon={FileText} tone="blue" />
        <KpiCard title="未报备" value={data.unreported_orders} icon={AlertTriangle} tone="red" />
        <KpiCard title="待结算" value={data.pending_settlement_orders} icon={Timer} tone="amber" />
      </section>

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
