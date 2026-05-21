import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CarFront, Clock, MapPinned, Navigation, RadioTower, RefreshCcw, Search } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/services/apiClient";
import type { LocationLog } from "@/types/api";

function coord(value?: number) {
  return typeof value === "number" ? value.toFixed(6) : "-";
}

function positionStyle(location: LocationLog) {
  const lat = typeof location.latitude === "number" ? location.latitude : 35.68;
  const lng = typeof location.longitude === "number" ? location.longitude : 139.76;
  const x = Math.max(6, Math.min(94, ((lng - 135) / 10) * 100));
  const y = Math.max(8, Math.min(92, 100 - ((lat - 32) / 12) * 100));
  return { left: `${x}%`, top: `${y}%` };
}

function onlineLabel(status?: string) {
  return status === "online" ? "在线" : status === "stale" ? "未刷新" : "未知";
}

export function MapPage() {
  const [keyword, setKeyword] = useState("");
  const [status, setStatus] = useState("");
  const locations = useQuery({
    queryKey: ["fleet-latest-locations-map", status],
    queryFn: () => api.fleetLatestLocations({ online_status: status, limit: 100 }),
    refetchInterval: 5000,
  });
  const rows = useMemo(() => locations.data || [], [locations.data]);
  const filtered = useMemo(() => {
    const text = keyword.trim().toLowerCase();
    if (!text) return rows;
    return rows.filter((item) =>
      [
        item.driver_name,
        item.plate_number,
        item.location_text,
        item.pickup_location,
        item.dropoff_location,
        item.oid,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(text),
    );
  }, [keyword, rows]);
  const onlineCount = rows.filter((item) => item.online_status === "online").length;
  const staleCount = rows.filter((item) => item.online_status === "stale").length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-500">司机微信位置上报</p>
          <h2 className="mt-1 text-2xl font-bold text-slate-950">车队实时地图</h2>
          <p className="mt-2 text-sm text-slate-500">司机端上报当前位置后，这里按车辆和司机展示最新位置。当前版本不接第三方地图，先用坐标看板和车辆 marker。</p>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center">
          <Metric label="车辆数" value={rows.length} />
          <Metric label="在线" value={onlineCount} tone="green" />
          <Metric label="未刷新" value={staleCount} tone="amber" />
        </div>
      </div>

      <Card>
        <CardContent className="flex flex-wrap items-center gap-3 p-4">
          <div className="relative min-w-72 flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              className="h-10 w-full rounded-lg border border-border bg-white pl-9 pr-3 text-sm outline-none focus:border-blue-400"
              placeholder="搜索司机、车牌、位置、订单号"
            />
          </div>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            className="h-10 rounded-lg border border-border bg-white px-3 text-sm font-semibold text-slate-700"
          >
            <option value="">全部状态</option>
            <option value="online">在线</option>
            <option value="stale">未刷新</option>
          </select>
          <button
            type="button"
            onClick={() => locations.refetch()}
            className="inline-flex h-10 items-center gap-2 rounded-lg border border-border bg-white px-4 text-sm font-bold text-slate-700 hover:bg-slate-50"
          >
            <RefreshCcw size={16} />
            刷新
          </button>
          <span className="text-xs text-slate-500">每 5 秒自动刷新</span>
        </CardContent>
      </Card>

      <section className="grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-950">位置总览</h3>
                <p className="mt-1 text-sm text-slate-500">车辆 marker 根据经纬度投影到示意面板，适合演示和调度快速判断。</p>
              </div>
              <MapPinned className="text-blue-600" size={22} />
            </div>
          </CardHeader>
          <CardContent>
            <div className="relative h-[560px] overflow-hidden rounded-xl border border-border bg-[linear-gradient(90deg,#dbe3ee_1px,transparent_1px),linear-gradient(#dbe3ee_1px,transparent_1px)] bg-[size:64px_64px] bg-slate-50">
              <div className="absolute left-4 top-4 rounded-lg border border-border bg-white/90 px-3 py-2 text-xs font-semibold text-slate-600 shadow-sm">
                坐标示意图：非第三方地图底图
              </div>
              <div className="absolute bottom-4 left-4 rounded-lg border border-border bg-white/90 px-3 py-2 text-xs text-slate-500 shadow-sm">
                在线为绿色，未刷新为橙色。鼠标悬停可看司机和时间。
              </div>
              {filtered.length ? (
                filtered.map((location) => (
                  <div
                    key={`${location.driver_id}-${location.id}`}
                    title={`${location.driver_name || ""} ${location.reported_at || ""}`}
                    className="absolute -translate-x-1/2 -translate-y-1/2 rounded-xl border border-blue-200 bg-white px-3 py-2 shadow-lg"
                    style={positionStyle(location)}
                  >
                    <div className="flex items-center gap-2">
                      <span className={location.online_status === "online" ? "h-2.5 w-2.5 rounded-full bg-emerald-500" : "h-2.5 w-2.5 rounded-full bg-amber-500"} />
                      <b className="text-sm text-slate-950">{location.plate_number || "未绑定车辆"}</b>
                    </div>
                    <div className="mt-1 max-w-40 truncate text-xs text-slate-500">{location.driver_name || `司机 #${location.driver_id}`}</div>
                  </div>
                ))
              ) : (
                <div className="absolute inset-0 flex items-center justify-center text-sm text-slate-500">暂无司机位置，上报后会显示在这里。</div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h3 className="text-base font-bold text-slate-950">最新位置</h3>
            <p className="mt-1 text-sm text-slate-500">用于确认车辆是否移动到合理区域，后续可替换为正式地图。</p>
          </CardHeader>
          <CardContent className="max-h-[620px] space-y-3 overflow-auto pr-1">
            {filtered.length ? filtered.map((location) => (
              <div key={`${location.driver_id}-${location.id}`} className="rounded-lg border border-border p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-bold text-slate-950">
                      <CarFront size={16} />
                      {location.plate_number || "未绑定车辆"}
                    </div>
                    <div className="mt-1 text-xs text-slate-500">{location.driver_name || `司机 #${location.driver_id}`}</div>
                  </div>
                  <span className={location.online_status === "online" ? "rounded-full bg-emerald-100 px-2 py-1 text-xs font-bold text-emerald-700" : "rounded-full bg-amber-100 px-2 py-1 text-xs font-bold text-amber-700"}>
                    {onlineLabel(location.online_status)}
                  </span>
                </div>
                <div className="mt-3 grid gap-2 text-xs text-slate-600">
                  <span className="inline-flex items-center gap-2"><Navigation size={14} />{location.location_text || "未填写位置说明"}</span>
                  <span className="inline-flex items-center gap-2"><RadioTower size={14} />{coord(location.latitude)}, {coord(location.longitude)}</span>
                  <span className="inline-flex items-center gap-2"><Clock size={14} />{location.reported_at || "-"}</span>
                </div>
                {location.pickup_location || location.dropoff_location ? (
                  <div className="mt-3 rounded-md bg-slate-50 px-3 py-2 text-xs text-slate-600">
                    当前任务：{location.pickup_location || "-"} → {location.dropoff_location || "-"}
                  </div>
                ) : null}
              </div>
            )) : (
              <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-slate-500">暂无位置记录</div>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

function Metric({ label, value, tone = "blue" }: { label: string; value: string | number; tone?: "blue" | "green" | "amber" }) {
  const cls = {
    blue: "text-blue-700 bg-blue-50",
    green: "text-emerald-700 bg-emerald-50",
    amber: "text-amber-700 bg-amber-50",
  }[tone];
  return (
    <div className={`rounded-lg px-4 py-3 ${cls}`}>
      <div className="text-lg font-black">{value}</div>
      <div className="text-xs font-semibold">{label}</div>
    </div>
  );
}
