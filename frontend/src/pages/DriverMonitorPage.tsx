import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Clock, MapPin, RadioTower, Siren } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { shortRoute } from "@/lib/utils";
import { api } from "@/services/apiClient";
import type { AssignmentEvidenceChain } from "@/types/api";

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

const REPORT_LABEL: Record<string, string> = {
  confirm_order: "接单回执",
  depart_yard: "点呼出库",
  arrive_pickup: "到达上车点",
  start_service: "开始服务",
  complete_order: "完成订单",
  return_yard: "点呼入库",
};

function reportLabel(type?: string) {
  return type ? REPORT_LABEL[type] || type : "-";
}

export function DriverMonitorPage() {
  const [selectedAssignmentId, setSelectedAssignmentId] = useState<number | null>(null);
  const assignments = useQuery({ queryKey: ["assignments"], queryFn: api.assignments, refetchInterval: 4000 });
  const reports = useQuery({ queryKey: ["driver-reports"], queryFn: api.driverReports, refetchInterval: 4000 });
  const locations = useQuery({ queryKey: ["fleet-latest-locations"], queryFn: () => api.fleetLatestLocations(), refetchInterval: 5000 });
  const safetyAlerts = useQuery({ queryKey: ["driver-safety-alerts"], queryFn: api.driverSafetyAlerts, refetchInterval: 5000 });
  const evidenceChain = useQuery({
    queryKey: ["assignment-evidence", selectedAssignmentId],
    queryFn: () => api.assignmentEvidence(selectedAssignmentId || 0),
    enabled: Boolean(selectedAssignmentId),
  });

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
    outboundVehicles: rows.filter((item) => item.vehicle_status === "outbound").length,
    inServiceVehicles: rows.filter((item) => item.vehicle_status === "in_service").length,
    returnedVehicles: rows.filter((item) => item.vehicle_status === "returned").length,
    online: (locations.data || []).filter((item) => item.online_status === "online").length,
    alerts: alerts.length,
  };

  return (
    <div className="space-y-5">
      <section className="runtime-strip">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="runtime-eyebrow">LIVE DRIVER RUNTIME</p>
            <h2 className="runtime-title">司机实时监控</h2>
            <p className="runtime-subtitle">接单、出库、到达、服务中、入库和位置上报自动刷新。</p>
          </div>
          <div className="grid min-w-[560px] grid-cols-4 gap-2">
            <MonitorRuntimeStat label="执行中" value={stats.active} tone="blue" />
            <MonitorRuntimeStat label="在线" value={stats.online} tone="green" />
            <MonitorRuntimeStat label="已入库" value={stats.returnedVehicles || stats.completed} tone="green" />
            <MonitorRuntimeStat label="警报" value={stats.alerts} tone={stats.alerts ? "red" : "green"} />
          </div>
        </div>
      </section>
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <MonitorKpi title="执行中任务" value={stats.active} icon={<RadioTower size={18} />} tone="blue" />
        <MonitorKpi title="车辆出库" value={stats.outboundVehicles} icon={<RadioTower size={18} />} tone="blue" />
        <MonitorKpi title="车辆服务中" value={stats.inServiceVehicles || stats.inService} icon={<Clock size={18} />} tone="violet" />
        <MonitorKpi title="车辆已入库" value={stats.returnedVehicles || stats.completed} icon={<CheckCircle2 size={18} />} tone="green" />
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
                      <StatusBadge status={item.vehicle_status || "available"} />
                    </div>
                    <StatusTimeline status={item.execution_status || "assigned"} />
                    <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
                      最新报备：{reportLabel(report?.report_type || item.latest_report_type)} · {report?.report_time || item.latest_report_time || "-"} ·{" "}
                      {report?.location_text || item.latest_location_text || "-"}
                    </div>
                    <div className="mt-2 rounded-lg bg-blue-50 px-3 py-2 text-xs text-blue-800">最新位置：{locationText(location)}</div>
                    <button
                      type="button"
                      onClick={() => setSelectedAssignmentId(assignmentId)}
                      className="mt-3 rounded-lg border border-blue-200 bg-white px-3 py-2 text-xs font-bold text-blue-700 hover:bg-blue-50"
                    >
                      查看执行证据
                    </button>
                  </div>
                );
              })
            ) : (
              <EmptyState title="暂无执行中任务" detail="派车后的司机任务会显示在这里，司机端报备后会自动刷新状态。" />
            )}
          </CardContent>
        </Card>

        <EvidenceViewer chain={evidenceChain.data?.evidence_chain} loading={evidenceChain.isFetching} />

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

function EvidenceViewer({ chain, loading }: { chain?: AssignmentEvidenceChain; loading: boolean }) {
  if (loading) {
    return (
      <Card>
        <CardContent className="p-5 text-sm text-slate-500">正在加载执行证据...</CardContent>
      </Card>
    );
  }
  if (!chain) {
    return (
      <Card>
        <CardHeader>
          <h2 className="text-base font-bold text-slate-950">订单执行证据</h2>
          <p className="mt-1 text-sm text-slate-500">点击任务中的“查看执行证据”，这里会显示照片、小票、报备和费用 timeline。</p>
        </CardHeader>
      </Card>
    );
  }
  const assignment = chain.assignment;
  return (
    <Card>
      <CardHeader>
        <h2 className="text-base font-bold text-slate-950">订单执行证据</h2>
        <p className="mt-1 text-sm text-slate-500">
          {assignment?.oid || assignment?.order_id || "-"} · {shortRoute(assignment?.pickup_location, assignment?.dropoff_location)}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-4 gap-2 text-center">
          <EvidenceMetric label="照片" value={chain.summary.photo_count || 0} />
          <EvidenceMetric label="报备" value={chain.summary.report_count || 0} />
          <EvidenceMetric label="小票" value={chain.summary.expense_count || 0} />
          <EvidenceMetric label="下载" value={chain.summary.download_count || 0} />
        </div>
        <div className="space-y-2">
          {chain.timeline.length ? chain.timeline.map((item) => (
            <div key={`${item.kind}-${item.id}-${item.event_time}`} className="rounded-lg border border-border p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-bold text-slate-900">{item.label || item.kind}</p>
                  <p className="mt-1 text-xs text-slate-500">{item.event_time || "-"} · {item.status || "-"}</p>
                </div>
                <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-bold text-slate-600">{item.kind}</span>
              </div>
              {item.location_text ? <p className="mt-2 text-xs text-slate-600">位置：{item.location_text}</p> : null}
              {item.amount != null ? <p className="mt-2 text-xs text-slate-600">金额：{item.amount} {item.currency || "JPY"}</p> : null}
              {item.note ? <p className="mt-2 text-xs text-slate-600">备注：{item.note}</p> : null}
              {item.file_url ? (
                <a className="mt-2 inline-block text-xs font-bold text-blue-700 hover:underline" href={item.file_url} target="_blank" rel="noreferrer">
                  打开 / 下载证据
                </a>
              ) : null}
            </div>
          )) : (
            <div className="rounded-lg border border-dashed border-border p-5 text-center text-sm text-slate-500">暂无执行证据</div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function EvidenceMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg bg-slate-50 px-2 py-3">
      <div className="text-lg font-black text-slate-950">{value}</div>
      <div className="text-[11px] font-bold text-slate-500">{label}</div>
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

function MonitorRuntimeStat({ label, value, tone }: { label: string; value: number; tone: "blue" | "green" | "red" }) {
  const toneClass = {
    blue: "bg-blue-50 text-blue-700",
    green: "bg-emerald-50 text-emerald-700",
    red: "bg-red-50 text-red-700",
  }[tone];
  return (
    <div className={`rounded-2xl px-4 py-3 ${toneClass}`}>
      <div className="text-xs font-black">{label}</div>
      <div className="mt-1 text-2xl font-black">{value}</div>
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
