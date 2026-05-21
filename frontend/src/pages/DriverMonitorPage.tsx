import type { ReactNode } from "react";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Clock, MapPin, RadioTower, Siren } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { shortRoute } from "@/lib/utils";
import { api } from "@/services/apiClient";

const STATUS_FLOW = ["assigned", "confirmed", "departed", "arrived", "in_service", "completed", "returned"];

const STATUS_LABEL: Record<string, string> = {
  assigned: "待确认",
  confirmed: "已确认",
  departed: "已出库",
  arrived: "已到达",
  in_service: "服务中",
  completed: "已完成",
  returned: "已归库",
};

export function DriverMonitorPage() {
  const assignments = useQuery({ queryKey: ["assignments"], queryFn: api.assignments, refetchInterval: 4000 });
  const reports = useQuery({ queryKey: ["driver-reports"], queryFn: api.driverReports, refetchInterval: 4000 });
  const locations = useQuery({ queryKey: ["fleet-latest-locations"], queryFn: () => api.fleetLatestLocations(), refetchInterval: 5000 });
  const safetyAlerts = useQuery({ queryKey: ["driver-safety-alerts"], queryFn: api.driverSafetyAlerts, refetchInterval: 5000 });

  const reportMap = new Map((reports.data || []).map((report) => [report.assignment_id, report]));
  const locationMap = new Map((locations.data || []).map((location) => [location.driver_id, location]));
  const rows = useMemo(() => assignments.data || [], [assignments.data]);
  const currentRows = useMemo(
    () => rows.filter((item) => !["completed", "returned"].includes(item.execution_status || "")).slice(0, 12),
    [rows],
  );
  const alerts = safetyAlerts.data || [];
  const stats = {
    active: currentRows.length,
    inService: rows.filter((item) => item.execution_status === "in_service").length,
    completed: rows.filter((item) => ["completed", "returned"].includes(item.execution_status || "")).length,
    online: (locations.data || []).filter((item) => item.online_status === "online").length,
    alerts: alerts.length,
  };

  return (
    <div className="space-y-5">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <MonitorKpi title="执行中任务" value={stats.active} icon={<RadioTower size={18} />} tone="blue" />
        <MonitorKpi title="服务中" value={stats.inService} icon={<Clock size={18} />} tone="violet" />
        <MonitorKpi title="已完成/归库" value={stats.completed} icon={<CheckCircle2 size={18} />} tone="green" />
        <MonitorKpi title="在线车辆" value={stats.online} icon={<MapPin size={18} />} tone="blue" />
        <MonitorKpi title="安全警报" value={stats.alerts} icon={<Siren size={18} />} tone={stats.alerts ? "red" : "green"} />
      </section>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-50 text-red-700">
              <Siren size={20} />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-950">司机安全警报</h2>
              <p className="mt-1 text-sm text-slate-500">SOS、异常报备和长时间未移动提醒会显示在这里。</p>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {alerts.length ? (
            alerts.map((alert) => (
              <div key={`${alert.alert_type}-${alert.incident_id || alert.assignment_id}-${alert.created_at || alert.reported_at}`} className="rounded-xl border border-red-100 bg-red-50 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <AlertTriangle size={18} className="text-red-700" />
                      <p className="text-sm font-black text-red-900">{alert.title || alert.alert_type}</p>
                    </div>
                    <p className="mt-2 text-sm text-red-800">{alert.description || "-"}</p>
                    <p className="mt-2 text-xs text-red-700">
                      {alert.driver_name || `司机 #${alert.driver_id || "-"}`} · {alert.plate_number || "-"} · {alert.oid || alert.order_id || "-"}
                    </p>
                    <p className="mt-1 text-xs text-red-700">{shortRoute(alert.pickup_location, alert.dropoff_location)}</p>
                  </div>
                  <span className="rounded-full bg-white px-2 py-1 text-xs font-bold text-red-700 ring-1 ring-red-200">
                    {alert.severity || "high"}
                  </span>
                </div>
              </div>
            ))
          ) : (
            <EmptyState title="暂无安全警报" detail="司机 SOS、异常报备或长时间未移动提醒会自动显示在这里。" />
          )}
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[1.35fr_0.75fr]">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-violet-50 text-violet-700">
                <RadioTower size={20} />
              </div>
              <div>
                <h2 className="text-base font-bold text-slate-950">司机执行监控</h2>
                <p className="mt-1 text-sm text-slate-500">查看当前任务、下一步状态、最新报备和最新位置。</p>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {currentRows.length ? (
              currentRows.map((item) => {
                const assignmentId = item.assignment_id || item.id || 0;
                const report = reportMap.get(assignmentId);
                const location = locationMap.get(item.driver_id || 0);
                return (
                  <div key={`${assignmentId}-${item.order_id}`} className="rounded-xl border border-border bg-white p-4">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div>
                        <p className="text-sm font-bold text-slate-950">
                          {item.driver_name || "未命名司机"} · {item.plate_number || "-"}
                        </p>
                        <p className="mt-1 text-base font-semibold text-slate-800">{shortRoute(item.pickup_location, item.dropoff_location)}</p>
                        <p className="mt-2 text-xs text-slate-500">
                          {item.order_date} {item.start_time}-{item.end_time} · {item.oid || item.order_id}
                        </p>
                      </div>
                      <StatusBadge status={item.execution_status || item.status} />
                    </div>
                    <StatusTimeline status={item.execution_status || "assigned"} />
                    <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
                      最新报备：{report?.report_type || item.latest_report_type || "-"} · {report?.report_time || item.latest_report_time || "-"} ·{" "}
                      {report?.location_text || item.latest_location_text || "-"}
                    </div>
                    <div className="mt-2 rounded-lg bg-blue-50 px-3 py-2 text-xs text-blue-800">最新位置：{locationText(location)}</div>
                  </div>
                );
              })
            ) : (
              <EmptyState title="暂无执行中任务" detail="派车后的司机任务会显示在这里，司机端报备后会自动刷新状态。" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-base font-bold text-slate-950">车辆位置列表</h2>
            <p className="mt-1 text-sm text-slate-500">第一版显示最新坐标和文字位置，后续可替换为地图。</p>
          </CardHeader>
          <CardContent className="space-y-3">
            {locations.data?.length ? (
              locations.data.slice(0, 12).map((location) => (
                <div key={`${location.driver_id}-${location.id}`} className="rounded-md border border-border px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-slate-950">{location.driver_name || `司机 #${location.driver_id}`}</p>
                    <span
                      className={
                        location.online_status === "online"
                          ? "rounded-full bg-emerald-100 px-2 py-1 text-xs font-bold text-emerald-700"
                          : "rounded-full bg-amber-100 px-2 py-1 text-xs font-bold text-amber-700"
                      }
                    >
                      {location.online_status === "online" ? "在线" : "未刷新"}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-slate-500">
                    {location.plate_number || "-"} · {location.reported_at || "-"} · {location.location_text || "-"}
                  </p>
                  <p className="mt-1 text-xs text-slate-600">{formatCoord(location.latitude, location.longitude)}</p>
                  {location.pickup_location || location.dropoff_location ? (
                    <p className="mt-1 text-xs text-slate-500">{shortRoute(location.pickup_location, location.dropoff_location)}</p>
                  ) : null}
                </div>
              ))
            ) : (
              <EmptyState detail="暂无位置上报。司机端点击上报当前位置或提交状态后会出现在这里。" />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function MonitorKpi({ title, value, icon, tone }: { title: string; value: number; icon: ReactNode; tone: "blue" | "green" | "red" | "violet" }) {
  const toneClass = {
    blue: "border-blue-100 bg-blue-50 text-blue-700",
    green: "border-emerald-100 bg-emerald-50 text-emerald-700",
    red: "border-red-100 bg-red-50 text-red-700",
    violet: "border-violet-100 bg-violet-50 text-violet-700",
  }[tone];
  return (
    <div className={`rounded-xl border p-4 ${toneClass}`}>
      <div className="flex items-center justify-between">
        <span className="text-sm font-bold">{title}</span>
        {icon}
      </div>
      <div className="mt-3 text-3xl font-black">{value}</div>
    </div>
  );
}

function StatusTimeline({ status }: { status: string }) {
  const current = Math.max(0, STATUS_FLOW.indexOf(status));
  return (
    <div className="mt-4 grid grid-cols-7 gap-1">
      {STATUS_FLOW.map((item, index) => (
        <div key={item} className={`rounded-md px-2 py-1 text-center text-[11px] font-bold ${index <= current ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-500"}`}>
          {STATUS_LABEL[item]}
        </div>
      ))}
    </div>
  );
}

function formatCoord(latitude?: number, longitude?: number) {
  if (latitude == null || longitude == null) return "坐标：未上报";
  return `坐标：${Number(latitude).toFixed(5)}, ${Number(longitude).toFixed(5)}`;
}

function locationText(location?: {
  latitude?: number;
  longitude?: number;
  location_text?: string;
  reported_at?: string;
  online_status?: string;
}) {
  if (!location) return "暂无位置";
  const coord = formatCoord(location.latitude, location.longitude);
  return `${location.location_text || coord} · ${location.reported_at || "-"} · ${location.online_status === "online" ? "在线" : "未刷新"}`;
}
