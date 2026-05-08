import { useQuery } from "@tanstack/react-query";
import { RadioTower } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { shortRoute } from "@/lib/utils";
import { api } from "@/services/apiClient";

export function DriverMonitorPage() {
  const assignments = useQuery({ queryKey: ["assignments"], queryFn: api.assignments });
  const reports = useQuery({ queryKey: ["driver-reports"], queryFn: api.driverReports });

  const reportMap = new Map((reports.data || []).map((report) => [report.assignment_id, report]));

  return (
    <div className="grid gap-6 xl:grid-cols-[1.3fr_0.8fr]">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-violet-50 text-violet-700">
              <RadioTower size={20} />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-950">司机执行中订单</h2>
              <p className="mt-1 text-sm text-slate-500">调度端查看 execution_status 与最新报备。</p>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {assignments.data?.length ? (
            assignments.data.slice(0, 12).map((item) => {
              const report = reportMap.get(item.assignment_id || item.id || 0);
              return (
                <div key={`${item.assignment_id || item.id}-${item.order_id}`} className="rounded-lg border border-border bg-white p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-sm font-bold text-slate-950">{item.driver_name || "未命名司机"} · {item.plate_number || "-"}</p>
                      <p className="mt-1 text-sm text-slate-600">{shortRoute(item.pickup_location, item.dropoff_location)}</p>
                      <p className="mt-2 text-xs text-slate-500">
                        {item.order_date} {item.start_time}-{item.end_time} · 最新报备：{report?.report_type || item.latest_report || "-"}
                      </p>
                    </div>
                    <StatusBadge status={item.execution_status || item.status} />
                  </div>
                </div>
              );
            })
          ) : (
            <EmptyState detail="暂无司机执行记录。" />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="text-base font-bold text-slate-950">最近报备</h2>
        </CardHeader>
        <CardContent className="space-y-3">
          {reports.data?.length ? (
            reports.data.slice(0, 10).map((report) => (
              <div key={report.id} className="rounded-md border border-border px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-slate-950">{report.report_type}</p>
                  <StatusBadge status={report.report_status || "submitted"} />
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  assignment #{report.assignment_id} · {report.report_time || "-"} · {report.location_text || "-"}
                </p>
              </div>
            ))
          ) : (
            <EmptyState detail="暂无 driver_reports。" />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
