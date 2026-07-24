import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { AlertTriangle, CalendarDays, Clock, Flag, MapPinned, Navigation, RadioTower, RefreshCcw, Search, ShieldAlert, UserRound } from "lucide-react";
import { CompanyScopeFilter } from "@/components/CompanyScopeFilter";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/services/apiClient";
import type { DriverSafetyAlert, FleetRouteStop, FleetRouteTrack, LocationLog } from "@/types/api";

const VEHICLE_LABEL: Record<string, string> = {
  available: "可用",
  outbound: "已出库",
  in_service: "服务中",
  returned: "已入库",
  busy: "服务中",
  maintenance: "维修",
  inactive: "停用",
  retired: "退役",
};

const EXECUTION_LABEL: Record<string, string> = {
  assigned: "已派车",
  confirmed: "司机确认",
  departed: "已出库",
  arrived: "到达上车点",
  in_service: "服务中",
  completed: "行程完成",
  returned: "已入库",
};

const ROUTE_COLORS = ["#2563eb", "#16a34a", "#7c3aed", "#f59e0b", "#0f766e", "#dc2626", "#4f46e5", "#0891b2"];

function today() {
  return new Date().toISOString().slice(0, 10);
}

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
  const [tenantScope, setTenantScope] = useState("all");
  const [routeDate, setRouteDate] = useState(today());

  const locationsQuery = useQuery({
    queryKey: ["fleet-latest-locations-map", tenantScope, onlineStatus, vehicleStatus],
    queryFn: () => api.fleetLatestLocations({ tenant_id: tenantScope, online_status: onlineStatus, vehicle_status: vehicleStatus, limit: 200 }),
    refetchInterval: 10000,
  });
  const routeTracksQuery = useQuery({
    queryKey: ["fleet-route-tracks-map", tenantScope, routeDate],
    queryFn: () => api.fleetRouteTracks({ tenant_id: tenantScope, date: routeDate }),
    refetchInterval: 10000,
  });
  const alertsQuery = useQuery({
    queryKey: ["driver-safety-alerts-map", tenantScope],
    queryFn: () => api.driverSafetyAlerts({ tenant_id: tenantScope }),
    refetchInterval: 10000,
  });

  const rows = useMemo(() => locationsQuery.data || [], [locationsQuery.data]);
  const alerts = useMemo(() => alertsQuery.data || [], [alertsQuery.data]);
  const tracks = useMemo(() => routeTracksQuery.data?.tracks || [], [routeTracksQuery.data?.tracks]);

  const filtered = useMemo(() => {
    const text = keyword.trim().toLowerCase();
    if (!text) return rows;
    return rows.filter((item) => searchableLocationText(item).includes(text));
  }, [keyword, rows]);

  const filteredTracks = useMemo(() => {
    const text = keyword.trim().toLowerCase();
    if (!text) return tracks;
    return tracks.filter((item) => searchableTrackText(item).includes(text));
  }, [keyword, tracks]);

  const activeAssignments = filtered.filter((item) => item.assignment_id || item.order_id);
  const nearbyDrivers = filtered
    .filter((item) => item.online_status === "online" && !["in_service", "busy", "retired"].includes(String(item.vehicle_status || "")))
    .slice(0, 8);
  const riskItems = filtered.filter((item) => isRisk(item, alerts)).slice(0, 8);
  const stopCount = filteredTracks.reduce((sum, item) => sum + item.stops.length, 0);

  const metrics = {
    total: rows.length,
    online: rows.filter((item) => item.online_status === "online").length,
    inService: rows.filter((item) => item.vehicle_status === "in_service").length,
    assignments: rows.filter((item) => item.assignment_id || item.order_id).length,
    tracks: filteredTracks.length,
    stops: stopCount,
    risk: rows.filter((item) => isRisk(item, alerts)).length,
  };

  return (
    <div className="space-y-5">
      <section className="runtime-strip">
        <div>
          <p className="runtime-eyebrow">LIVE FLEET RUNTIME</p>
          <h2 className="runtime-title">车辆地图</h2>
          <p className="runtime-subtitle">显示司机最新位置、当天轨迹、行进方向、10 分钟以上停留点，以及司机出库/入库报备时间。</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Metric label="司机" value={metrics.total} />
          <Metric label="在线" value={metrics.online} tone="green" />
          <Metric label="服务中" value={metrics.inService} tone="blue" />
          <Metric label="任务" value={metrics.assignments} tone="indigo" />
          <Metric label="路线" value={metrics.tracks} tone="blue" />
          <Metric label="停留" value={metrics.stops} tone="amber" />
          <Metric label="风险" value={metrics.risk} tone="red" />
        </div>
      </section>

      <Card>
        <CardContent className="flex flex-wrap items-center gap-3 p-4">
          <CompanyScopeFilter value={tenantScope} onChange={setTenantScope} />
          <label className="inline-flex h-10 items-center gap-2 rounded-xl border border-border bg-white px-3 text-sm font-semibold text-slate-700">
            <CalendarDays size={16} className="text-slate-400" />
            <input className="bg-transparent outline-none" type="date" value={routeDate} onChange={(event) => setRouteDate(event.target.value)} />
          </label>
          <div className="relative min-w-72 flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              className="h-10 w-full rounded-xl border border-border bg-white pl-9 pr-3 text-sm outline-none focus:border-blue-400"
              placeholder="搜索司机、车辆、订单号、地点、状态"
            />
          </div>
          <select value={onlineStatus} onChange={(event) => setOnlineStatus(event.target.value)} className="h-10 rounded-xl border border-border bg-white px-3 text-sm font-semibold text-slate-700">
            <option value="">全部在线状态</option>
            <option value="online">在线</option>
            <option value="stale">位置过期</option>
            <option value="unknown">未知</option>
          </select>
          <select value={vehicleStatus} onChange={(event) => setVehicleStatus(event.target.value)} className="h-10 rounded-xl border border-border bg-white px-3 text-sm font-semibold text-slate-700">
            <option value="">全部车辆状态</option>
            <option value="available">可用</option>
            <option value="outbound">已出库</option>
            <option value="in_service">服务中</option>
            <option value="returned">已入库</option>
            <option value="maintenance">维修</option>
          </select>
          <button
            type="button"
            onClick={() => {
              locationsQuery.refetch();
              routeTracksQuery.refetch();
              alertsQuery.refetch();
            }}
            className="inline-flex h-10 items-center gap-2 rounded-xl border border-border bg-white px-4 text-sm font-bold text-slate-700 hover:bg-slate-50"
          >
            <RefreshCcw size={16} />
            刷新
          </button>
          <span className="text-xs text-slate-500">每 10 秒自动刷新</span>
        </CardContent>
      </Card>

      <section className="grid gap-5 2xl:grid-cols-[1.55fr_0.45fr]">
        <Card className="overflow-hidden">
          <CardContent className="p-0">
            <div className="relative min-h-[680px] overflow-hidden bg-[#dcebf5]">
              <LeafletFleetMap locations={filtered} routeTracks={filteredTracks} alerts={alerts} />
              <div className="absolute left-6 top-6 z-10 rounded-2xl border border-white/70 bg-white/90 px-4 py-3 shadow-sm backdrop-blur">
                <div className="flex items-center gap-2 text-sm font-black text-slate-950">
                  <MapPinned size={18} className="text-blue-600" />
                  Live Fleet Map
                </div>
                <div className="mt-1 text-xs font-semibold text-slate-500">实线：当天轨迹 / 三角：行进方向 / 黄点：停留 10 分钟以上 / 红点：风险</div>
              </div>
              <div className="absolute bottom-6 left-6 z-10 max-w-md rounded-2xl border border-white/70 bg-white/90 px-4 py-3 text-xs font-semibold text-slate-500 shadow-sm backdrop-blur">
                路线来自司机端位置上报，不是导航预测路线。没有连续坐标时会保留最新位置点，但不会绘制轨迹线。
              </div>
              {!filtered.some(hasCoordinates) && !filteredTracks.some((track) => track.points.length > 0) ? (
                <div className="absolute inset-0 z-10 flex items-center justify-center text-sm font-semibold text-slate-500">暂无可显示在地图上的司机坐标</div>
              ) : null}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-5">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-black text-slate-950">行驶路线</h3>
                  <p className="mt-1 text-sm text-slate-500">按司机展示当天轨迹、方向、停留点和出入库时间。</p>
                </div>
                <span className="runtime-pill runtime-pill-blue">{filteredTracks.length} 条</span>
              </div>
            </CardHeader>
            <CardContent className="max-h-[440px] space-y-3 overflow-auto">
              {filteredTracks.length ? filteredTracks.map((track, index) => (
                <RouteTrackCard key={`${track.tenant_id}-${track.driver_id}`} track={track} color={ROUTE_COLORS[index % ROUTE_COLORS.length]} />
              )) : (
                <EmptyBlock text="暂无当天路线轨迹" />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-black text-slate-950">订单覆盖层</h3>
                  <p className="mt-1 text-sm text-slate-500">显示正在执行或更新位置的派车任务。</p>
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
                  <div className="mt-1 text-xs font-semibold text-red-700">{item.online_status === "stale" ? "位置超过 15 分钟未更新" : "存在高风险异常"}</div>
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
                    <span>{labelOf(VEHICLE_LABEL, item.vehicle_status)} · {item.vehicle_type || "车辆类型待补"}</span>
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

function LeafletFleetMap({ locations, routeTracks, alerts }: { locations: LocationLog[]; routeTracks: FleetRouteTrack[]; alerts: DriverSafetyAlert[] }) {
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
    const boundsPoints: [number, number][] = [];

    routeTracks.forEach((track, index) => {
      const color = ROUTE_COLORS[index % ROUTE_COLORS.length];
      const points = track.points
        .filter((point) => typeof point.latitude === "number" && typeof point.longitude === "number")
        .map((point) => [Number(point.latitude), Number(point.longitude)] as [number, number]);
      points.forEach((point) => boundsPoints.push(point));
      if (points.length >= 2) {
        const line = L.polyline(points, { color, weight: 4, opacity: 0.72 });
        line.bindPopup(routePopupHtml(track));
        line.addTo(layer);
        const last = points[points.length - 1];
        const arrow = L.marker(last, {
          icon: L.divIcon({
            className: "fleet-direction-icon",
            html: `<div style="width:0;height:0;border-left:7px solid transparent;border-right:7px solid transparent;border-bottom:16px solid ${color};transform:rotate(${Number(track.direction_degrees || 0)}deg);filter:drop-shadow(0 1px 2px rgba(15,23,42,.35));"></div>`,
            iconSize: [18, 18],
            iconAnchor: [9, 9],
          }),
        });
        arrow.bindTooltip(`${track.driver_name || `司机 ${track.driver_id}`} · 行进方向`, { direction: "top", offset: [0, -8] });
        arrow.addTo(layer);
      }
      track.stops.forEach((stop) => {
        const marker = L.circleMarker([Number(stop.latitude), Number(stop.longitude)], {
          radius: 8,
          color: "#f59e0b",
          weight: 3,
          fillColor: "#fbbf24",
          fillOpacity: 0.82,
        });
        marker.bindTooltip(stopTooltipText(stop), {
          direction: "top",
          offset: [0, -8],
          opacity: 0.95,
          sticky: true,
        });
        marker.bindPopup(stopPopupHtml(track, stop), { maxWidth: 300 });
        marker.addTo(layer);
      });
      const pickupLat = Number(track.pickup_latitude);
      const pickupLng = Number(track.pickup_longitude);
      if (!Number.isNaN(pickupLat) && !Number.isNaN(pickupLng)) {
        const pickupPoint: [number, number] = [pickupLat, pickupLng];
        boundsPoints.push(pickupPoint);
        const pickupMarker = L.marker(pickupPoint, {
          icon: L.divIcon({
            className: "fleet-flag-icon",
            html: `<div style="display:flex;align-items:center;gap:4px"><div style="width:12px;height:12px;border-radius:999px;background:#0ea5e9;border:2px solid #fff;box-shadow:0 1px 4px rgba(15,23,42,.28)"></div><div style="font-size:11px;font-weight:800;color:#075985;background:#ecfeff;border:1px solid rgba(14,165,233,.28);padding:2px 6px;border-radius:999px">起</div></div>`,
            iconSize: [40, 18],
            iconAnchor: [10, 9],
          }),
        });
        pickupMarker.bindTooltip(`起点 · ${track.pickup_location || "-"}`, { direction: "top", offset: [0, -8], sticky: true });
        pickupMarker.bindPopup(taskPointPopupHtml("起点", track.pickup_location, track), { maxWidth: 320 });
        pickupMarker.addTo(layer);
      }
      const dropoffLat = Number(track.dropoff_latitude);
      const dropoffLng = Number(track.dropoff_longitude);
      if (!Number.isNaN(dropoffLat) && !Number.isNaN(dropoffLng)) {
        const dropoffPoint: [number, number] = [dropoffLat, dropoffLng];
        boundsPoints.push(dropoffPoint);
        const dropoffMarker = L.marker(dropoffPoint, {
          icon: L.divIcon({
            className: "fleet-flag-icon",
            html: `<div style="display:flex;align-items:center;gap:4px"><div style="width:12px;height:12px;border-radius:999px;background:#f97316;border:2px solid #fff;box-shadow:0 1px 4px rgba(15,23,42,.28)"></div><div style="font-size:11px;font-weight:800;color:#9a3412;background:#fff7ed;border:1px solid rgba(249,115,22,.28);padding:2px 6px;border-radius:999px">终</div></div>`,
            iconSize: [40, 18],
            iconAnchor: [10, 9],
          }),
        });
        dropoffMarker.bindTooltip(`终点 · ${track.dropoff_location || "-"}`, { direction: "top", offset: [0, -8], sticky: true });
        dropoffMarker.bindPopup(taskPointPopupHtml("终点", track.dropoff_location, track), { maxWidth: 320 });
        dropoffMarker.addTo(layer);
      }
    });

    const plotted = locations.filter(hasCoordinates);
    plotted.forEach((location) => {
      const point: [number, number] = [Number(location.latitude), Number(location.longitude)];
      boundsPoints.push(point);
      const color = markerHex(location, alerts);
      const marker = L.circleMarker(point, {
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
      marker.bindPopup(locationPopupHtml(location, alerts), { maxWidth: 320 });
      marker.addTo(layer);
    });

    if (boundsPoints.length) {
      const bounds = L.latLngBounds(boundsPoints);
      map.fitBounds(bounds.pad(0.2), { maxZoom: 14, animate: false });
    } else {
      map.setView([34.6937, 135.5023], 9);
    }
    setTimeout(() => map.invalidateSize(), 0);
  }, [locations, routeTracks, alerts]);

  return <div ref={containerRef} className="absolute inset-0 z-0" />;
}

function RouteTrackCard({ track, color }: { track: FleetRouteTrack; color: string }) {
  return (
    <div className="rounded-2xl border border-border bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full" style={{ background: color }} />
            <div className="truncate text-sm font-black text-slate-950">{track.driver_name || `Driver ${track.driver_id}`}</div>
          </div>
          <div className="mt-1 truncate text-xs font-semibold text-slate-500">{track.plate_number || "No vehicle"} · {track.oid || "No active order"}</div>
        </div>
        <span className="runtime-pill runtime-pill-blue">{track.points.length} points</span>
      </div>
      <div className="mt-3 grid gap-2 text-xs font-semibold text-slate-600">
        <InfoLine icon={<Navigation size={13} />} text={`Direction ${formatBearing(track.direction_degrees)} · ${track.distance_km || 0} km`} />
        <InfoLine icon={<Flag size={13} />} text={`Out ${formatDateTime(track.depart_yard_at)} · In ${formatDateTime(track.return_yard_at)}`} />
        <InfoLine icon={<Clock size={13} />} text={`Stops ${track.stops.length} places, 10 min+`} />
      </div>
      {track.pickup_location || track.dropoff_location ? (
        <div className="mt-3 rounded-xl bg-slate-50 p-3 text-xs font-semibold text-slate-600">
          <div className="truncate">{track.pickup_location || "-"} {"->"} {track.dropoff_location || "-"}</div>
        </div>
      ) : null}
      <div className="mt-3 rounded-xl border border-slate-100 bg-slate-50 p-3">
        <div className="mb-2 text-[11px] font-black uppercase tracking-wide text-slate-500">行程列表</div>
        {track.points.length ? (
          <div className="max-h-40 space-y-1 overflow-auto pr-1">
            {track.points.map((point, index) => (
              <div key={point.id || `${point.reported_at}-${index}`} className="grid grid-cols-[54px_1fr] gap-2 rounded-lg bg-white px-2 py-1.5 text-xs font-semibold text-slate-600">
                <span className="font-black text-slate-900">{formatClock(point.reported_at)}</span>
                <span className="truncate" title={point.location_text || `${coord(point.latitude)}, ${coord(point.longitude)}`}>
                  {point.location_text || `${coord(point.latitude)}, ${coord(point.longitude)}`}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs font-semibold text-slate-400">暂无轨迹点</div>
        )}
      </div>
    </div>
  );
}

function OverlayCard({ item }: { item: LocationLog }) {
  return (
    <div className="rounded-2xl border border-border bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-black text-slate-950">{item.oid || `Order ${item.order_id || "-"}`}</div>
          <div className="mt-1 text-xs font-semibold text-slate-500">{item.driver_name || `Driver ${item.driver_id}`} · {item.plate_number || "No vehicle"}</div>
        </div>
        <span className="runtime-pill runtime-pill-blue">{labelOf(EXECUTION_LABEL, item.execution_status)}</span>
      </div>
      <div className="mt-3 rounded-xl bg-slate-50 p-3 text-xs font-semibold text-slate-600">
        <div>{item.order_date || "-"} {item.start_time || "--:--"} - {item.end_time || "--:--"}</div>
        <div className="mt-1 truncate">{item.pickup_location || "-"} {"->"} {item.dropoff_location || "-"}</div>
      </div>
      <div className="mt-3 grid gap-1 text-xs text-slate-500">
        <span className="inline-flex items-center gap-2"><RadioTower size={13} />{coord(item.latitude)}, {coord(item.longitude)}</span>
        <span className="inline-flex items-center gap-2"><Clock size={13} />{formatDateTime(item.reported_at)}</span>
      </div>
    </div>
  );
}

function InfoLine({ icon, text }: { icon: React.ReactNode; text: string }) {
  return <span className="inline-flex items-center gap-2">{icon}{text}</span>;
}

function EmptyBlock({ text }: { text: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-border bg-slate-50 p-6 text-center text-sm font-semibold text-slate-500">
      <AlertTriangle className="mx-auto mb-2 text-slate-400" size={18} />
      {text}
    </div>
  );
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

function routePopupHtml(track: FleetRouteTrack) {
  return `
    <div style="min-width:230px;font-family:Arial,'Microsoft YaHei',sans-serif">
      <div style="font-weight:900;font-size:14px;color:#0f172a">${escapeHtml(track.driver_name || `司机 ${track.driver_id}`)}</div>
      <div style="margin-top:4px;color:#475569;font-size:12px">${escapeHtml(track.plate_number || "-")} · ${escapeHtml(track.oid || "无当前订单")}</div>
      <div style="margin-top:8px;font-size:12px;color:#334155">轨迹点：${track.points.length} · 距离：${track.distance_km || 0} km</div>
      <div style="margin-top:6px;font-size:12px;color:#64748b">出库：${escapeHtml(formatDateTime(track.depart_yard_at))}</div>
      <div style="margin-top:2px;font-size:12px;color:#64748b">入库：${escapeHtml(formatDateTime(track.return_yard_at))}</div>
      ${track.pickup_location || track.dropoff_location ? `<div style="margin-top:10px;padding:8px;border-radius:8px;background:#f8fafc;color:#334155;font-size:12px">${escapeHtml(track.pickup_location || "-")} -> ${escapeHtml(track.dropoff_location || "-")}</div>` : ""}
    </div>
  `;
}

function taskPointPopupHtml(label: string, locationText: string | undefined, track: FleetRouteTrack) {
  return `
    <div style="min-width:220px;font-family:Arial,'Microsoft YaHei',sans-serif">
      <div style="font-weight:900;font-size:14px;color:#0f172a">${escapeHtml(label)}</div>
      <div style="margin-top:4px;color:#475569;font-size:12px">${escapeHtml(track.driver_name || `司机 ${track.driver_id}`)} · ${escapeHtml(track.plate_number || "-")}</div>
      <div style="margin-top:8px;font-size:12px;color:#334155">${escapeHtml(locationText || "-")}</div>
      <div style="margin-top:6px;font-size:12px;color:#64748b">${escapeHtml(track.oid || "无任务编号")} · ${escapeHtml(formatDateTime(track.depart_yard_at))}</div>
    </div>
  `;
}

function stopPopupHtml(track: FleetRouteTrack, stop: FleetRouteStop) {
  return `
    <div style="min-width:220px;font-family:Arial,'Microsoft YaHei',sans-serif">
      <div style="font-weight:900;font-size:14px;color:#92400e">停留 ${stop.duration_minutes} 分钟</div>
      <div style="margin-top:4px;color:#475569;font-size:12px">${escapeHtml(track.driver_name || `司机 ${track.driver_id}`)} · ${escapeHtml(track.plate_number || "-")}</div>
      <div style="margin-top:8px;font-size:12px;color:#334155">${escapeHtml(formatDateTime(stop.start_at))} -> ${escapeHtml(formatDateTime(stop.end_at))}</div>
      <div style="margin-top:6px;font-size:12px;color:#64748b">${escapeHtml(stop.location_text || `${coord(stop.latitude)}, ${coord(stop.longitude)}`)}</div>
    </div>
  `;
}

function stopTooltipText(stop: FleetRouteStop) {
  return `${stop.location_text || `${coord(stop.latitude)}, ${coord(stop.longitude)}`} · 停留 ${stop.duration_minutes} 分钟`;
}

function locationPopupHtml(location: LocationLog, alerts: DriverSafetyAlert[]) {
  const risk = isRisk(location, alerts) ? "<span style='color:#dc2626;font-weight:800'>风险</span>" : "正常";
  return `
    <div style="min-width:220px;font-family:Arial,'Microsoft YaHei',sans-serif">
      <div style="font-weight:900;font-size:14px;color:#0f172a">${escapeHtml(location.plate_number || `司机 ${location.driver_id}`)}</div>
      <div style="margin-top:4px;color:#475569;font-size:12px">${escapeHtml(location.driver_name || "未命名司机")} · ${escapeHtml(labelOf(EXECUTION_LABEL, location.execution_status))}</div>
      <div style="margin-top:8px;font-size:12px;color:#334155">${escapeHtml(location.location_text || `${coord(location.latitude)}, ${coord(location.longitude)}`)}</div>
      <div style="margin-top:8px;font-size:12px;color:#64748b">车辆：${escapeHtml(labelOf(VEHICLE_LABEL, location.vehicle_status))} · 状态：${risk}</div>
      <div style="margin-top:8px;font-size:12px;color:#64748b">更新：${escapeHtml(formatDateTime(location.reported_at))}</div>
      ${location.oid ? `<div style="margin-top:10px;padding:8px;border-radius:8px;background:#f8fafc;color:#334155;font-size:12px"><b>${escapeHtml(location.oid)}</b><br>${escapeHtml(location.pickup_location || "-")} -> ${escapeHtml(location.dropoff_location || "-")}</div>` : ""}
    </div>
  `;
}

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char] || char));
}

function formatDateTime(value?: string) {
  if (!value) return "-";
  return value.replace("T", " ").slice(0, 16);
}

function formatClock(value?: string) {
  if (!value) return "--:--";
  const normalized = value.replace("T", " ");
  const time = normalized.includes(" ") ? normalized.split(" ")[1] : normalized;
  return time ? time.slice(0, 5) : "--:--";
}

function formatBearing(value?: number | null) {
  if (typeof value !== "number") return "-";
  const directions = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"];
  return `${directions[Math.round(value / 45) % 8]} ${Math.round(value)}°`;
}

function searchableLocationText(item: LocationLog) {
  return [
    item.driver_name,
    item.tenant_name,
    item.tenant_slug,
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
    .toLowerCase();
}

function searchableTrackText(item: FleetRouteTrack) {
  return [
    item.driver_name,
    item.tenant_name,
    item.tenant_slug,
    item.driver_phone,
    item.plate_number,
    item.vehicle_type,
    item.pickup_location,
    item.dropoff_location,
    item.oid,
    item.execution_status,
    item.vehicle_status,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function Metric({ label, value, tone = "slate" }: { label: string; value: string | number; tone?: "slate" | "green" | "blue" | "indigo" | "red" | "amber" }) {
  const cls = {
    slate: "bg-slate-100 text-slate-700",
    green: "bg-emerald-50 text-emerald-700",
    blue: "bg-blue-50 text-blue-700",
    indigo: "bg-indigo-50 text-indigo-700",
    red: "bg-red-50 text-red-700",
    amber: "bg-amber-50 text-amber-700",
  }[tone];
  return (
    <div className={`rounded-2xl px-4 py-3 text-center ${cls}`}>
      <div className="text-xl font-black">{value}</div>
      <div className="text-xs font-bold">{label}</div>
    </div>
  );
}
