import { useCallback, useEffect, useState } from "react";

import { isPlatformUser } from "@/auth/permissions";
import { api } from "@/services/apiClient";
import type { AuthUser, TenantOption } from "@/types/api";

type Price = {
  vehicle_type: string;
  price_jpy: number;
};

type Stop = {
  location_name: string;
  stop_type: "pickup" | "waypoint" | "dropoff";
};

type Route = {
  id: number;
  route_code: string;
  route_name: string;
  status: string;
  version: number;
  operations_business_area?: string;
  default_start_time?: string;
  default_end_time?: string;
  standard_duration_minutes?: number;
  applicant_name?: string;
  application_method?: string;
  route_summary?: string;
  document_remark?: string;
  updated_at?: string;
  stops: Stop[];
  prices: Price[];
};

type RouteForm = Omit<Route, "id" | "version" | "updated_at"> & {
  id?: number;
  version?: number;
  updated_at?: string;
};

const fieldLabels: Record<string, string> = {
  route_code: "路线编号",
  route_name: "路线名称",
  operations_business_area: "营业区域",
  default_start_time: "开始时间",
  default_end_time: "结束时间",
  standard_duration_minutes: "标准时长（分钟）",
  applicant_name: "申请公司",
  application_method: "申请方式",
  route_summary: "路线摘要",
  document_remark: "备注",
};

function normalizeStops(stops: Stop[]): Stop[] {
  const next = stops.length >= 2
    ? stops
    : [
        { location_name: stops[0]?.location_name || "", stop_type: "pickup" as const },
        { location_name: "", stop_type: "dropoff" as const },
      ];
  return next.map((stop, index) => ({
    ...stop,
    stop_type: index === 0 ? "pickup" : index === next.length - 1 ? "dropoff" : "waypoint",
  }));
}

function normalizePrices(prices: Price[] = []): Price[] {
  const result = prices.map((item) => ({
    vehicle_type: item.vehicle_type,
    price_jpy: Number(item.price_jpy || 0),
  }));
  if (!result.some((item) => item.vehicle_type.toLowerCase() === "hiace")) {
    result.unshift({ vehicle_type: "Hiace", price_jpy: 0 });
  }
  if (!result.some((item) => item.vehicle_type.toLowerCase() === "alphard")) {
    result.splice(1, 0, { vehicle_type: "Alphard", price_jpy: 0 });
  }
  return result;
}

function blankRoute(): RouteForm {
  return {
    route_code: "",
    route_name: "",
    status: "active",
    operations_business_area: "",
    default_start_time: "09:00",
    default_end_time: "18:00",
    standard_duration_minutes: 540,
    applicant_name: "SPI",
    application_method: "ウェブサイト",
    route_summary: "",
    document_remark: "",
    stops: [
      { location_name: "", stop_type: "pickup" },
      { location_name: "", stop_type: "dropoff" },
    ],
    prices: normalizePrices(),
  };
}

function routeToForm(route: Route): RouteForm {
  return {
    ...route,
    stops: normalizeStops(route.stops || []),
    prices: normalizePrices(route.prices || []),
  };
}

function routePrice(route: Route, vehicleType: string) {
  const found = (route.prices || []).find(
    (item) => item.vehicle_type.toLowerCase() === vehicleType.toLowerCase(),
  );
  return found ? `¥${Number(found.price_jpy || 0).toLocaleString()}` : "-";
}

function routeSaveError(reason: unknown): string {
  const message = reason instanceof Error ? reason.message : String(reason || "");
  if (message.includes("fixed_tour_route_code_exists")) {
    return "该路线编号已经存在。请从下方路线列表选择“编辑”，不要重复新建。";
  }
  return message || "路线保存失败";
}

export function FixedToursPage({ currentUser }: { currentUser: AuthUser }) {
  const platform = isPlatformUser(currentUser);
  const [tenantId, setTenantId] = useState<number | undefined>(
    platform ? undefined : currentUser.tenant_id,
  );
  const [tenants, setTenants] = useState<TenantOption[]>([]);
  const [routes, setRoutes] = useState<Route[]>([]);
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState<RouteForm | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!platform) return;
    api.platformTenants()
      .then((items) => {
        setTenants(items);
        setTenantId((current) => current || items[0]?.id);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "租户列表加载失败"));
  }, [platform]);

  const loadRoutes = useCallback(async () => {
    if (platform && !tenantId) {
      setRoutes([]);
      return;
    }
    setLoading(true);
    try {
      const response = await api.fixedTourRoutes({
        q: query,
        include_inactive: true,
        tenant_id: tenantId,
      });
      setRoutes(response.routes || []);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "路线加载失败");
    } finally {
      setLoading(false);
    }
  }, [platform, query, tenantId]);

  useEffect(() => {
    void loadRoutes();
  }, [loadRoutes]);

  const saveRoute = async () => {
    if (!editing || (platform && !tenantId)) return;
    setLoading(true);
    setError("");
    const payload = {
      ...editing,
      tenant_id: tenantId,
      standard_duration_minutes: Number(editing.standard_duration_minutes || 0),
      stops: normalizeStops(editing.stops),
      prices: editing.prices
        .filter((item) => item.vehicle_type.trim())
        .map((item) => ({ ...item, price_jpy: Number(item.price_jpy || 0) })),
    };
    try {
      if (editing.id) {
        await api.updateFixedTourRoute(editing.id, payload);
      } else {
        await api.createFixedTourRoute(payload);
      }
      setEditing(null);
      await loadRoutes();
    } catch (reason) {
      setError(routeSaveError(reason));
    } finally {
      setLoading(false);
    }
  };

  const copyRoute = async (route: Route) => {
    if (!window.confirm(`复制“${route.route_name}”？`)) return;
    try {
      await api.copyFixedTourRoute(route.id, tenantId);
      await loadRoutes();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "路线复制失败");
    }
  };

  const toggleRoute = async (route: Route) => {
    const nextStatus = route.status === "active" ? "inactive" : "active";
    if (!window.confirm(`${nextStatus === "active" ? "启用" : "停用"}“${route.route_name}”？`)) return;
    try {
      await api.setFixedTourRouteStatus(route.id, nextStatus, tenantId);
      await loadRoutes();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "路线状态更新失败");
    }
  };

  const deleteRoute = async (route: Route) => {
    if (!window.confirm(`确定删除“${route.route_name}”吗？\n删除后无法恢复；已有运行记录的路线不能删除，只能停用。`)) return;
    setLoading(true);
    setError("");
    try {
      await api.deleteFixedTourRoute(route.id, tenantId);
      if (editing?.id === route.id) setEditing(null);
      await loadRoutes();
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : String(reason || "");
      setError(
        message.includes("fixed_tour_route_in_use")
          ? "该路线已经生成过运行记录，不能删除。请使用“停用”保留历史数据。"
          : message || "路线删除失败",
      );
    } finally {
      setLoading(false);
    }
  };

  const updateStop = (index: number, locationName: string) => {
    if (!editing) return;
    const stops = editing.stops.map((stop, current) =>
      current === index ? { ...stop, location_name: locationName } : stop,
    );
    setEditing({ ...editing, stops: normalizeStops(stops) });
  };

  const addStop = () => {
    if (!editing) return;
    const stops = [...editing.stops];
    stops.splice(Math.max(stops.length - 1, 1), 0, {
      location_name: "",
      stop_type: "waypoint",
    });
    setEditing({ ...editing, stops: normalizeStops(stops) });
  };

  const removeStop = (index: number) => {
    if (!editing || editing.stops.length <= 2) return;
    setEditing({
      ...editing,
      stops: normalizeStops(editing.stops.filter((_, current) => current !== index)),
    });
  };

  const moveStop = (index: number, direction: -1 | 1) => {
    if (!editing) return;
    const target = index + direction;
    if (target < 0 || target >= editing.stops.length) return;
    const stops = [...editing.stops];
    [stops[index], stops[target]] = [stops[target], stops[index]];
    setEditing({ ...editing, stops: normalizeStops(stops) });
  };

  const updatePrice = (index: number, key: keyof Price, value: string) => {
    if (!editing) return;
    const prices = editing.prices.map((item, current) =>
      current === index
        ? { ...item, [key]: key === "price_jpy" ? Number(value) : value }
        : item,
    );
    setEditing({ ...editing, prices });
  };

  return (
    <div className="space-y-5 p-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">日游路线库</h1>
          <p className="mt-1 text-sm text-slate-500">维护路线母版；保存会递增版本，历史运行保留原快照。</p>
        </div>
        <div className="flex items-center gap-2">
          {platform && (
            <select
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
              value={tenantId || ""}
              onChange={(event) => {
                setTenantId(event.target.value ? Number(event.target.value) : undefined);
                setEditing(null);
              }}
            >
              <option value="">选择租户</option>
              {tenants.map((tenant) => (
                <option key={tenant.id} value={tenant.id}>{tenant.name}</option>
              ))}
            </select>
          )}
          <button
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
            disabled={loading || (platform && !tenantId)}
            onClick={() => setEditing(blankRoute())}
          >
            新建路线
          </button>
        </div>
      </header>

      <div className="flex gap-2">
        <input
          className="w-full max-w-md rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="搜索路线编号、名称或停靠点"
        />
        <button className="rounded-lg border border-slate-300 px-4 py-2 text-sm" onClick={() => void loadRoutes()}>
          搜索
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{error}</div>
      )}

      {editing && (
        <section className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">{editing.id ? "编辑路线" : "新建路线"}</h2>
            <button className="text-sm text-slate-500" onClick={() => setEditing(null)}>取消</button>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            {Object.keys(fieldLabels).map((key) => (
              <label key={key} className={key === "route_summary" || key === "document_remark" ? "md:col-span-2" : ""}>
                <span className="mb-1 block text-xs font-medium text-slate-600">{fieldLabels[key]}</span>
                <input
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  type={key === "standard_duration_minutes" ? "number" : key.includes("time") ? "time" : "text"}
                  value={String(editing[key as keyof RouteForm] ?? "")}
                  onChange={(event) => setEditing({
                    ...editing,
                    [key]: key === "standard_duration_minutes" ? Number(event.target.value) : event.target.value,
                  })}
                />
              </label>
            ))}
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-slate-900">停靠点顺序</h3>
              <button className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" onClick={addStop}>新增途经点</button>
            </div>
            {editing.stops.map((stop, index) => (
              <div key={`${index}-${stop.stop_type}`} className="grid grid-cols-[72px_1fr_auto] items-center gap-2">
                <span className="text-xs font-medium text-slate-500">
                  {index === 0 ? "上车" : index === editing.stops.length - 1 ? "下车" : "途经"}
                </span>
                <input
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  value={stop.location_name}
                  onChange={(event) => updateStop(index, event.target.value)}
                  placeholder="地点名称"
                />
                <div className="flex gap-1">
                  <button disabled={index === 0} onClick={() => moveStop(index, -1)}>↑</button>
                  <button disabled={index === editing.stops.length - 1} onClick={() => moveStop(index, 1)}>↓</button>
                  <button disabled={editing.stops.length <= 2} onClick={() => removeStop(index)}>删除</button>
                </div>
              </div>
            ))}
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-slate-900">车型建议价</h3>
              <button
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
                onClick={() => setEditing({
                  ...editing,
                  prices: [...editing.prices, { vehicle_type: "其他车型", price_jpy: 0 }],
                })}
              >
                新增其他车型
              </button>
            </div>
            {editing.prices.map((item, index) => {
              const fixed = ["hiace", "alphard"].includes(item.vehicle_type.toLowerCase());
              return (
                <div key={`${index}-${item.vehicle_type}`} className="grid grid-cols-[1fr_1fr_auto] gap-2">
                  <input
                    className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    value={item.vehicle_type}
                    readOnly={fixed}
                    onChange={(event) => updatePrice(index, "vehicle_type", event.target.value)}
                  />
                  <input
                    className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    type="number"
                    min="0"
                    value={item.price_jpy}
                    onChange={(event) => updatePrice(index, "price_jpy", event.target.value)}
                  />
                  <button
                    disabled={fixed}
                    onClick={() => setEditing({
                      ...editing,
                      prices: editing.prices.filter((_, current) => current !== index),
                    })}
                  >
                    删除
                  </button>
                </div>
              );
            })}
          </div>

          <div className="flex justify-end">
            <button
              className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white disabled:opacity-40"
              disabled={loading}
              onClick={() => void saveRoute()}
            >
              {editing.id ? "更新路线" : "保存路线"}
            </button>
          </div>
        </section>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-[1320px] text-left text-sm">
          <thead className="bg-slate-50 text-xs text-slate-500">
            <tr>
              {["路线名称", "编号", "状态", "标准时间", "时长", "起点", "终点", "主要途经点", "Hiace", "Alphard", "版本", "更新时间", "操作"].map((label) => (
                <th key={label} className="whitespace-nowrap px-3 py-3 font-medium">{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {routes.map((route) => (
              <tr key={route.id} className="border-t border-slate-100 align-top">
                <td className="px-3 py-3 font-medium text-slate-900">{route.route_name}</td>
                <td className="px-3 py-3">{route.route_code}</td>
                <td className="px-3 py-3">{route.status === "active" ? "启用" : "停用"}</td>
                <td className="whitespace-nowrap px-3 py-3">{route.default_start_time || "-"}–{route.default_end_time || "-"}</td>
                <td className="whitespace-nowrap px-3 py-3">{route.standard_duration_minutes ? `${route.standard_duration_minutes} 分` : "-"}</td>
                <td className="px-3 py-3">{route.stops?.[0]?.location_name || "-"}</td>
                <td className="px-3 py-3">{route.stops?.[route.stops.length - 1]?.location_name || "-"}</td>
                <td className="max-w-64 px-3 py-3">{route.stops?.slice(1, -1).map((stop) => stop.location_name).join(" → ") || "-"}</td>
                <td className="whitespace-nowrap px-3 py-3">{routePrice(route, "Hiace")}</td>
                <td className="whitespace-nowrap px-3 py-3">{routePrice(route, "Alphard")}</td>
                <td className="px-3 py-3">V{route.version}</td>
                <td className="whitespace-nowrap px-3 py-3">{route.updated_at || "-"}</td>
                <td className="whitespace-nowrap px-3 py-3">
                  <button onClick={() => setEditing(routeToForm(route))}>编辑</button>{" "}
                  <button onClick={() => void copyRoute(route)}>复制</button>{" "}
                  <button onClick={() => void toggleRoute(route)}>{route.status === "active" ? "停用" : "启用"}</button>{" "}
                  <button className="text-red-600" onClick={() => void deleteRoute(route)}>删除</button>
                </td>
              </tr>
            ))}
            {!loading && routes.length === 0 && (
              <tr><td className="px-4 py-10 text-center text-slate-500" colSpan={13}>暂无日游路线</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
