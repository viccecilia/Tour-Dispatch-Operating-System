import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { AlertTriangle, Clock, MapPinned, RadioTower, RefreshCcw, Search, ShieldAlert, UserRound } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/services/apiClient";
import type { DriverSafetyAlert, LocationLog } from "@/types/api";

const VEHICLE_LABEL: Record<string, string> = {
  available: "正常",
  outbound: "已出库",
  in_service: "服务中",
  returned: "已入库",
  busy: "正常",
  maintenance: "维修",
  inactive: "正常",
  retired: "减车",
};

const EXECUTION_LABEL: Record<string, string> = {
  assigned: "已派车",
  confirmed: "已确认",
  departed: "已出库",
  arrived: "已到达",
  in_service: "服务中",
  completed: "已完成",
  returned: "已归库",
};

function coord(value?: number) {
  return typeof value === "number" ? value.toFixed(5) : "-";
}

function labelOf(map: Record<string, string>, value?: string) {
  return value ? map[value] || value : "-";
}

function isRisk(location: LocationLog, alerts: DriverSafetyAlert[]) {
  return (
    location.online_status === "stale" ||
    alerts.some((alert) => Number(alert.driver_id) === Number(location.driver_id) && ["high", "critical"].includes(String(alert.severity || "")))
  );
}

export function MapPage() {
  const [keyword, setKeyword] = useState("");
  const [onlineStatus, setOnlineStatus] = useState("");
  const [vehicleStatus, setVehicleStatus] = useState("");

  const locationsQuery = useQuery({
    queryKey: ["fleet-latest-locations-map", onlineStatus, vehicleStatus],
    queryFn: () => api.fleetLatestLocations({ online_status: onlineStatus, vehicle_status: vehicleStatus, limit: 200 }),
    refetchInterval: 5000,
  });
  const alertsQuery = useQuery({
    queryKey: ["driver-safety-alerts-map"],
    queryFn: api.driverSafetyAlerts,
    refetchInterval: 8000,
  });

  const rows = useMemo(() => locationsQuery.data || [], [locationsQuery.data]);
  const alerts = useMemo(() => alertsQuery.data || [], [alertsQuery.data]);

  const filtered = useMemo(() => {
    const text = keyword.trim().toLowerCase();
    if (!text) return rows;
    return rows.filter((item) =>
      [
        item.driver_name,
        item.driver_phone,
        item.plate_number,
        item.vehicle_type,
        item.location_text,
        item.pickup_location,
        item.dropoff_location,
        item.oid,
        item.execution_status,
        item.vehicle_status,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(text),
    );
  }, [keyword, rows]);

  const activeAssignments = filtered.filter((item) => item.assignment_id || item.order_id);
  const nearbyDrivers = filtered
    .filter((item) => item.online_status === "online" && !["in_service", "busy", "retired"].includes(String(item.vehicle_status || "")))
    .slice(0, 8);
  const riskItems = filtered.filter((item) => isRisk(item, alerts)).slice(0, 8);

  const metrics = {
    total: rows.length,
    online: rows.filter((item) => item.online_status === "online").length,
    inService: rows.filter((item) => item.vehicle_status === "in_service").length,
    assignments: rows.filter((item) => item.assignment_id || item.order_id).length,
    risk: rows.filter((item) => isRisk(item, alerts)).length,
  };

  return (
    <div className="space-y-5">
      <section className="runtime-strip">
        <div>
          <p className="runtime-eyebrow">LIVE FLEET RUNTIME</p>
          <h2 className="runtime-title">车队实时地图</h2>
          <p className="runtime-subtitle">司机位置、当前订单、车辆状态和异常风险集中在同一个运行视图中。</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Metric label="司机" value={metrics.total} />
          <Metric label="在线" value={metrics.online} tone="green" />
          <Metric label="服务中" value={metrics.inService} tone="blue" />
          <Metric label="订单覆盖" value={metrics.assignments} tone="indigo" />
          <Metric label="风险" value={metrics.risk} tone="red" />
        </div>
      </section>

      <Card>
        <CardContent className="flex flex-wrap items-center gap-3 p-4">
          <div className="relative min-w-72 flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              className="h-10 w-full rounded-xl border border-border bg-white pl-9 pr-3 text-sm outline-none focus:border-blue-400"
              placeholder="搜索司机、车辆、订单号、地点、状态"
            />
          </div>
          <select
            value={onlineStatus}
            onChange={(event) => setOnlineStatus(event.target.value)}
            className="h-10 rounded-xl border border-border bg-white px-3 text-sm font-semibold text-slate-700"
          >
            <option value="">全部在线状态</option>
            <option value="online">在线</option>
            <option value="stale">位置过期</option>
            <option value="unknown">未知</option>
          </select>
          <select
            value={vehicleStatus}
            onChange={(event) => setVehicleStatus(event.target.value)}
            className="h-10 rounded-xl border border-border bg-white px-3 text-sm font-semibold text-slate-700"
          >
            <option value="">全部车辆状态</option>
            <option value="available">正常</option>
            <option value="maintenance">维修</option>
          </select>
          <button
            type="button"
            onClick={() => {
              locationsQuery.refetch();
              alertsQuery.refetch();
            }}
            className="inline-flex h-10 items-center gap-2 rounded-xl border border-border bg-white px-4 text-sm font-bold text-slate-700 hover:bg-slate-50"
          >
            <RefreshCcw size={16} />
            刷新
          </button>
          <span className="text-xs text-slate-500">每 5 秒自动刷新</span>
        </CardContent>
      </Card>

      <section className="grid gap-5 2xl:grid-cols-[1.55fr_0.45fr]">
        <Card className="overflow-hidden">
          <CardContent className="p-0">
            <div className="relative min-h-[680px] overflow-hidden bg-[#dcebf5]">
              <LeafletFleetMap locations={filtered} alerts={alerts} />
              <div className="absolute left-6 top-6 z-10 rounded-2xl border border-white/70 bg-white/90 px-4 py-3 shadow-sm backdrop-blur">
                <div className="flex items-center gap-2 text-sm font-black text-slate-950">
                  <MapPinned size={18} className="text-blue-600" />
                  Live Fleet Map
                </div>
                <div className="mt-1 text-xs font-semibold text-slate-500">蓝：已出库 / 绿：服务中 / 红：风险 / 灰：已入库</div>
              </div>
              <div className="absolute bottom-6 left-6 z-10 max-w-md rounded-2xl border border-white/70 bg-white/90 px-4 py-3 text-xs font-semibold text-slate-500 shadow-sm backdrop-blur">
                正式地图底图已接入，坐标来自司机端位置上报。无坐标的司机会保留在列表中，不显示在地图点位上。
              </div>
              {!filtered.some(hasCoordinates) ? (
                <div className="absolute inset-0 z-10 flex items-center justify-center text-sm font-semibold text-slate-500">
                  暂无可显示在地图上的司机坐标
                </div>
              ) : null}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-5">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-black text-slate-950">订单覆盖层</h3>
                  <p className="mt-1 text-sm text-slate-500">显示正在执行或刚更新位置的派车任务。</p>
                </div>
                <span className="runtime-pill runtime-pill-blue">{activeAssignments.length} 单</span>
              </div>
            </CardHeader>
            <CardContent className="max-h-80 space-y-3 overflow-auto">
              {activeAssignments.length ? activeAssignments.slice(0, 10).map((item) => (
                <OverlayCard key={`${item.assignment_id}-${item.order_id}-${item.id}`} item={item} />
              )) : (
                <EmptyBlock text="暂无订单覆盖层" />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-black text-slate-950">风险高亮</h3>
                  <p className="mt-1 text-sm text-slate-500">位置过期或异常司机会在地图中标红。</p>
                </div>
                <ShieldAlert className="text-red-500" size={20} />
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {riskItems.length ? riskItems.map((item) => (
                <div key={`risk-${item.driver_id}-${item.id}`} className="rounded-xl border border-red-100 bg-red-50 p-3">
                  <div className="text-sm font-black text-red-800">{item.driver_name || `司机 ${item.driver_id}`}</div>
                  <div className="mt-1 text-xs font-semibold text-red-700">
                    {item.online_status === "stale" ? "位置超过 15 分钟未刷新" : "存在高风险异常"}
                  </div>
                  <div className="mt-1 truncate text-xs text-red-600">{item.location_text || item.plate_number || "-"}</div>
                </div>
              )) : (
                <EmptyBlock text="暂无高亮风险" />
              )}
            </CardContent>
          </Card>
        </div>
      </section>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-black text-slate-950">附近可派司机</h3>
              <p className="mt-1 text-sm text-slate-500">优先展示在线、非服务中、非维修的司机，供临时派车半径判断。</p>
            </div>
            <span className="runtime-pill runtime-pill-green">{nearbyDrivers.length} 人可参考</span>
          </div>
        </CardHeader>
        <CardContent>
          {nearbyDrivers.length ? (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {nearbyDrivers.map((item) => (
                <div key={`nearby-${item.driver_id}-${item.id}`} className="rounded-2xl border border-border bg-white p-4 shadow-sm">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-50 text-blue-700">
                        <UserRound size={17} />
                      </div>
                      <div>
                        <div className="text-sm font-black text-slate-950">{item.driver_name || `司机 ${item.driver_id}`}</div>
                        <div className="text-xs font-semibold text-slate-500">{item.plate_number || "未绑定车辆"}</div>
                      </div>
                    </div>
                    <span className="rounded-full bg-emerald-50 px-2 py-1 text-xs font-black text-emerald-700">在线</span>
                  </div>
                  <div className="mt-3 grid gap-1 text-xs font-semibold text-slate-500">
                    <span>{labelOf(VEHICLE_LABEL, item.vehicle_status)} · {item.vehicle_type || "车型待补"}</span>
                    <span className="truncate">{item.location_text || `${coord(item.latitude)}, ${coord(item.longitude)}`}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyBlock text="暂无可派司机" />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function LeafletFleetMap({ locations, alerts }: { locations: LocationLog[]; alerts: DriverSafetyAlert[] }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, {
      center: [34.6937, 135.5023],
      zoom: 9,
      zoomControl: true,
      attributionControl: true,
    });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    const layer = L.layerGroup().addTo(map);
    mapRef.current = map;
    layerRef.current = layer;
    setTimeout(() => map.invalidateSize(), 0);
    return () => {
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    layer.clearLayers();
    const plotted = locations.filter(hasCoordinates);
    plotted.forEach((location) => {
      const color = markerHex(location, alerts);
      const marker = L.circleMarker([Number(location.latitude), Number(location.longitude)], {
        radius: 9,
        color,
        weight: 3,
        fillColor: color,
        fillOpacity: 0.78,
      });
      marker.bindTooltip(`${location.plate_number || `司机 ${location.driver_id}`} · ${location.driver_name || "-"}`, {
        direction: "top",
        offset: [0, -8],
      });
      marker.bindPopup(popupHtml(location, alerts), { maxWidth: 320 });
      marker.addTo(layer);
    });
    if (plotted.length) {
      const bounds = L.latLngBounds(plotted.map((item) => [Number(item.latitude), Number(item.longitude)] as [number, number]));
      map.fitBounds(bounds.pad(0.2), { maxZoom: 13, animate: false });
    } else {
      map.setView([34.6937, 135.5023], 9);
    }
    setTimeout(() => map.invalidateSize(), 0);
  }, [locations, alerts]);

  return <div ref={containerRef} className="absolute inset-0 z-0" />;
}

function hasCoordinates(location: LocationLog) {
  return typeof location.latitude === "number" && typeof location.longitude === "number";
}

function markerHex(location: LocationLog, alerts: DriverSafetyAlert[]) {
  if (isRisk(location, alerts)) return "#ef4444";
  if (location.vehicle_status === "in_service") return "#10b981";
  if (location.vehicle_status === "outbound") return "#3b82f6";
  if (location.vehicle_status === "returned") return "#64748b";
  return "#6366f1";
}

function popupHtml(location: LocationLog, alerts: DriverSafetyAlert[]) {
  const risk = isRisk(location, alerts) ? "<span style='color:#dc2626;font-weight:800'>风险</span>" : "正常";
  return `
    <div style="min-width:220px;font-family:Arial,'Microsoft YaHei',sans-serif">
      <div style="font-weight:900;font-size:14px;color:#0f172a">${escapeHtml(location.plate_number || `司机 ${location.driver_id}`)}</div>
      <div style="margin-top:4px;color:#475569;font-size:12px">${escapeHtml(location.driver_name || "未命名司机")} · ${escapeHtml(labelOf(EXECUTION_LABEL, location.execution_status))}</div>
      <div style="margin-top:8px;font-size:12px;color:#334155">${escapeHtml(location.location_text || `${coord(location.latitude)}, ${coord(location.longitude)}`)}</div>
      <div style="margin-top:8px;font-size:12px;color:#64748b">车辆：${escapeHtml(labelOf(VEHICLE_LABEL, location.vehicle_status))} · 状态：${risk}</div>
      <div style="margin-top:8px;font-size:12px;color:#64748b">更新：${escapeHtml(location.reported_at || "-")}</div>
      ${location.oid ? `<div style="margin-top:10px;padding:8px;border-radius:8px;background:#f8fafc;color:#334155;font-size:12px"><b>${escapeHtml(location.oid)}</b><br>${escapeHtml(location.pickup_location || "-")} -> ${escapeHtml(location.dropoff_location || "-")}</div>` : ""}
    </div>
  `;
}

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char] || char));
}

function Metric({ label, value, tone = "slate" }: { label: string; value: string | number; tone?: "slate" | "green" | "blue" | "indigo" | "red" }) {
  const cls = {
    slate: "bg-slate-100 text-slate-700",
    green: "bg-emerald-50 text-emerald-700",
    blue: "bg-blue-50 text-blue-700",
    indigo: "bg-indigo-50 text-indigo-700",
    red: "bg-red-50 text-red-700",
  }[tone];
  return (
    <div className={`rounded-2xl px-4 py-3 text-center ${cls}`}>
      <div className="text-xl font-black">{value}</div>
      <div className="text-xs font-bold">{label}</div>
    </div>
  );
}

function OverlayCard({ item }: { item: LocationLog }) {
  return (
    <div className="rounded-2xl border border-border bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-black text-slate-950">{item.oid || `订单 ${item.order_id || "-"}`}</div>
          <div className="mt-1 text-xs font-semibold text-slate-500">
            {item.driver_name || `司机 ${item.driver_id}`} · {item.plate_number || "未绑定车辆"}
          </div>
        </div>
        <span className="runtime-pill runtime-pill-blue">{labelOf(EXECUTION_LABEL, item.execution_status)}</span>
      </div>
      <div className="mt-3 rounded-xl bg-slate-50 p-3 text-xs font-semibold text-slate-600">
        <div>{item.order_date || "-"} {item.start_time || "--:--"} - {item.end_time || "--:--"}</div>
        <div className="mt-1 truncate">{item.pickup_location || "-"} → {item.dropoff_location || "-"}</div>
      </div>
      <div className="mt-3 grid gap-1 text-xs text-slate-500">
        <span className="inline-flex items-center gap-2"><RadioTower size={13} />{coord(item.latitude)}, {coord(item.longitude)}</span>
        <span className="inline-flex items-center gap-2"><Clock size={13} />{item.reported_at || "-"}</span>
      </div>
    </div>
  );
}

function EmptyBlock({ text }: { text: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-border bg-slate-50 p-6 text-center text-sm font-semibold text-slate-500">
      <AlertTriangle className="mx-auto mb-2 text-slate-400" size={18} />
      {text}
    </div>
  );
}
