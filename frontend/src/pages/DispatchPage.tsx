import { type ReactNode, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  RefreshCw,
  Route,
  Search,
  Snowflake,
  Sparkles,
  XCircle,
} from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { formatCurrency, shortRoute, todayIso } from "@/lib/utils";
import { api } from "@/services/apiClient";
import type { Assignment, DispatchRecommendation, Driver, Order, Vehicle } from "@/types/api";

type ResourceFilter = {
  driver: string;
  vehicle: string;
};

type RouteLink = {
  from_order_id: number;
  to_order_id: number;
  handoff: string;
  score?: number;
  risk?: "low" | "medium" | "high";
  reasons?: string[];
  time_gap_minutes?: number | null;
};

type RouteSummary = {
  order_count: number;
  link_count: number;
  average_score: number;
  risk_count: number;
  same_vehicle_suggestion: boolean;
  message: string;
};

function orderKey(order: Pick<Order, "order_date" | "start_time" | "pickup_location" | "id">) {
  return `${order.order_date || ""} ${order.start_time || ""} ${order.pickup_location || ""} ${order.id || 0}`;
}

function vehicleMatches(order: Order, vehicle?: Vehicle | null) {
  if (!order || !vehicle) return false;
  const want = `${order.vehicle_type || ""}`.toLowerCase();
  const got = `${vehicle.vehicle_type || ""}`.toLowerCase();
  if (!want || !got) return false;
  return want.includes(got) || got.includes(want) || want.includes("绿") === got.includes("绿");
}

function inferredLanguage(driver?: Driver | null) {
  if (!driver) return "-";
  return driver.driver_language || driver.language || (/[A-Za-z]/.test(driver.name) ? "中/英" : "中文");
}

function vehicleTags(vehicle?: Vehicle | null) {
  if (!vehicle) return [];
  const tags = [];
  const text = `${vehicle.vehicle_type || ""} ${vehicle.plate_number || ""}`;
  if (text.includes("绿")) tags.push("绿牌");
  if (vehicle.vehicle_color || vehicle.color) tags.push(vehicle.vehicle_color || vehicle.color);
  if (vehicle.snow_tire || text.includes("雪")) tags.push("雪胎");
  return tags;
}

function assignmentId(item: Assignment) {
  return Number(item.assignment_id || item.id || 0);
}

export function DispatchPage() {
  const queryClient = useQueryClient();
  const [selectedOrders, setSelectedOrders] = useState<number[]>([]);
  const [selectedAssignments, setSelectedAssignments] = useState<number[]>([]);
  const [driverId, setDriverId] = useState<number | null>(null);
  const [vehicleId, setVehicleId] = useState<number | null>(null);
  const [filters, setFilters] = useState<ResourceFilter>({ driver: "", vehicle: "" });
  const [orderKeyword, setOrderKeyword] = useState("");
  const [assignmentKeyword, setAssignmentKeyword] = useState("");
  const [message, setMessage] = useState("");
  const [conflicts, setConflicts] = useState<unknown[]>([]);
  const [routeLinks, setRouteLinks] = useState<RouteLink[]>([]);
  const [routeSummary, setRouteSummary] = useState<RouteSummary | null>(null);
  const [recommendations, setRecommendations] = useState<DispatchRecommendation[]>([]);
  const [calendarDate, setCalendarDate] = useState(todayIso());

  const unassigned = useQuery({ queryKey: ["dispatch-unassigned"], queryFn: api.unassignedOrders, refetchInterval: 4000 });
  const assignments = useQuery({ queryKey: ["assignments"], queryFn: api.assignments, refetchInterval: 4000 });
  const drivers = useQuery({ queryKey: ["drivers"], queryFn: api.drivers, refetchInterval: 10000 });
  const vehicles = useQuery({ queryKey: ["vehicles"], queryFn: api.vehicles, refetchInterval: 10000 });
  const calendar = useQuery({ queryKey: ["calendar", "day", calendarDate], queryFn: () => api.calendar("day", calendarDate), refetchInterval: 5000 });

  const driver = drivers.data?.find((item) => item.id === driverId) || null;
  const vehicle = vehicles.data?.find((item) => item.id === vehicleId) || null;

  const visibleOrders = useMemo(() => {
    const keyword = orderKeyword.toLowerCase();
    return (unassigned.data || [])
      .filter((order) => {
        if (!keyword) return true;
        return [order.oid, order.pickup_location, order.dropoff_location, order.order_type, order.vehicle_type, order.guest_name, order.agency_name]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(keyword);
      })
      .sort((left, right) => {
        const leftSelected = selectedOrders.indexOf(left.id);
        const rightSelected = selectedOrders.indexOf(right.id);
        if (leftSelected >= 0 && rightSelected >= 0) return leftSelected - rightSelected;
        if (leftSelected >= 0) return -1;
        if (rightSelected >= 0) return 1;
        return orderKey(left).localeCompare(orderKey(right));
      });
  }, [orderKeyword, selectedOrders, unassigned.data]);

  const selectedOrderRows = useMemo(
    () => selectedOrders.map((id) => (unassigned.data || []).find((order) => order.id === id)).filter(Boolean) as Order[],
    [selectedOrders, unassigned.data],
  );

  const filteredDrivers = useMemo(() => {
    const keyword = filters.driver.toLowerCase();
    return (drivers.data || []).filter((item) =>
      [item.name, item.phone, item.status, item.driver_code, item.office, inferredLanguage(item)].join(" ").toLowerCase().includes(keyword),
    );
  }, [drivers.data, filters.driver]);

  const filteredVehicles = useMemo(() => {
    const keyword = filters.vehicle.toLowerCase();
    return (vehicles.data || []).filter((item) =>
      [item.plate_number, item.plate_short_code, item.vehicle_type_code, item.vehicle_type, item.status, ...vehicleTags(item)].join(" ").toLowerCase().includes(keyword),
    );
  }, [filters.vehicle, vehicles.data]);

  const visibleAssignments = useMemo(() => {
    const keyword = assignmentKeyword.toLowerCase();
    return (assignments.data || []).filter((item) => {
      if (!keyword) return true;
      return [item.oid, item.pickup_location, item.dropoff_location, item.driver_name, item.plate_number, item.status, item.execution_status]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(keyword);
    });
  }, [assignmentKeyword, assignments.data]);

  async function refreshDispatch() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["dispatch-unassigned"] }),
      queryClient.invalidateQueries({ queryKey: ["assignments"] }),
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] }),
      queryClient.invalidateQueries({ queryKey: ["calendar"] }),
      queryClient.invalidateQueries({ queryKey: ["driver-reports"] }),
    ]);
  }

  const assignMutation = useMutation({
    mutationFn: () => {
      if (!window.confirm(`确认派车 ${selectedOrders.length} 单给 ${driver?.name || "所选司机"} / ${vehicle?.plate_number || "所选车辆"}？`)) {
        throw new Error("用户取消派车");
      }
      return api.assign(selectedOrders, driverId!, vehicleId!);
    },
    onSuccess: async (result) => {
      if (result.success === false) {
        setConflicts(result.conflicts || []);
        setMessage("派车失败：发现司机或车辆时间冲突，请查看冲突提示。");
        return;
      }
      setSelectedOrders([]);
      setConflicts([]);
      setRouteLinks([]);
      setRouteSummary(null);
      setRecommendations([]);
      setMessage(`派车完成：写入 ${result.assignment_ids?.length || 0} 条 assignment，日历和司机端已刷新。`);
      await refreshDispatch();
    },
  });

  const recommendMutation = useMutation({
    mutationFn: () => api.dispatchRecommend(selectedOrders),
    onSuccess: (result) => {
      const next = result.recommendations || [];
      setRecommendations(next);
      setConflicts(next.flatMap((item) => item.conflicts || []));
      if (!next.length) {
        setMessage("暂无可用派车建议，请先选择订单，并确认有可用司机和车辆。");
        return;
      }
      setMessage(`已生成 ${next.length} 条智能派车建议。采用建议只会选中司机和车辆，仍需人工点击批量派车确认。`);
    },
    onError: (error: Error) => {
      setRecommendations([]);
      setMessage(`智能推荐失败：${error.message}`);
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (id: number) => {
      if (!window.confirm("确认取消这条派车？订单会回到未派车池。")) {
        throw new Error("用户取消操作");
      }
      return api.cancelAssignment(id);
    },
    onSuccess: async (result) => {
      setMessage(result.success ? "已取消分配，订单回到未派车池。" : `取消失败：${result.error || "未找到 active assignment"}`);
      await refreshDispatch();
    },
  });

  const reassignMutation = useMutation({
    mutationFn: () => {
      if (!window.confirm(`确认将 ${selectedAssignments.length} 条已派订单重新分配给当前司机和车辆？`)) {
        throw new Error("用户取消重新分配");
      }
      const orderIds = visibleAssignments
        .filter((item) => selectedAssignments.includes(assignmentId(item)))
        .map((item) => item.order_id);
      return api.reassign(orderIds, driverId!, vehicleId!);
    },
    onSuccess: async (result) => {
      if (result.success === false) {
        setConflicts(result.conflicts || []);
        setMessage("重新分配失败：发现时间冲突。");
        return;
      }
      setSelectedAssignments([]);
      setConflicts([]);
      setMessage(`重新分配完成：新建 ${result.new_assignment_ids?.length || 0} 条 assignment，历史记录已保留。`);
      await refreshDispatch();
    },
  });

  const canAssign = selectedOrders.length > 0 && Boolean(driverId) && Boolean(vehicleId) && !assignMutation.isPending;
  const canReassign = selectedAssignments.length > 0 && Boolean(driverId) && Boolean(vehicleId) && !reassignMutation.isPending;

  function toggleOrder(id: number) {
    setSelectedOrders((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }

  function toggleAssignment(id: number) {
    setSelectedAssignments((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }

  function moveSelectedOrder(index: number, direction: -1 | 1) {
    setSelectedOrders((current) => {
      const next = [...current];
      const target = index + direction;
      if (target < 0 || target >= next.length) return current;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  async function chainSortSelected() {
    const ids = selectedOrders.length ? selectedOrders : visibleOrders.map((order) => order.id);
    const suggestion = (await api.routeSuggestion(ids)) as {
      orders?: Order[];
      links?: RouteLink[];
      summary?: RouteSummary;
    };
    const optimizedIds = (suggestion.orders || []).map((order) => order.id);
    setSelectedOrders(optimizedIds.length ? optimizedIds : ids);
    setRouteLinks(suggestion.links || []);
    setRouteSummary(suggestion.summary || null);
    setMessage(suggestion.summary?.message || `已按日期、开始时间生成接龙顺序：${optimizedIds.length || ids.length} 单。`);
  }

  return (
    <div className="space-y-5">
      <section className="grid gap-5 2xl:grid-cols-[minmax(760px,1.55fr)_360px_360px]">
        <Card className="min-h-[640px]">
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-bold text-slate-950">未派车订单池</h2>
                <p className="mt-1 text-sm text-slate-500">多选订单后可手动调整顺序，或按时间与地点接龙排序。</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <label className="flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm">
                  <Search size={15} className="text-slate-400" />
                  <input className="w-52 outline-none" value={orderKeyword} onChange={(event) => setOrderKeyword(event.target.value)} placeholder="订单号/地点/客户" />
                </label>
                <Button variant="secondary" onClick={() => setSelectedOrders(visibleOrders.map((order) => order.id))}>
                  全选
                </Button>
                <Button variant="secondary" onClick={() => setSelectedOrders([])}>
                  清空
                </Button>
                <Button variant="secondary" onClick={chainSortSelected}>
                  <Route size={15} />
                  接龙排序
                </Button>
                <Button variant="secondary" disabled={!selectedOrders.length || recommendMutation.isPending} onClick={() => recommendMutation.mutate()}>
                  <Sparkles size={15} />
                  智能推荐
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="mb-3 flex flex-wrap items-center gap-2 text-sm text-slate-500">
              <span>未派车 {visibleOrders.length} 单</span>
              <span>已选 {selectedOrders.length} 单</span>
              {vehicle && selectedOrderRows.length ? (
                <span className={selectedOrderRows.every((order) => vehicleMatches(order, vehicle)) ? "text-emerald-700" : "text-amber-700"}>
                  车型匹配：{selectedOrderRows.filter((order) => vehicleMatches(order, vehicle)).length}/{selectedOrderRows.length}
                </span>
              ) : null}
            </div>
            {visibleOrders.length ? (
              <div className="overflow-hidden rounded-lg border border-border">
                <div className="max-h-[560px] overflow-auto">
                  <table className="min-w-[1060px] w-full border-collapse text-left text-sm">
                    <thead className="sticky top-0 z-10 bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-500">
                      <tr>
                        <th className="w-32 px-3 py-3">顺序</th>
                        <th className="w-36 px-3 py-3">订单号</th>
                        <th className="w-36 px-3 py-3">开始</th>
                        <th className="w-36 px-3 py-3">结束</th>
                        <th className="px-3 py-3">路线</th>
                        <th className="w-24 px-3 py-3">类型</th>
                        <th className="w-32 px-3 py-3">车型</th>
                        <th className="w-24 px-3 py-3">价格</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleOrders.map((order) => {
                        const selectedIndex = selectedOrders.indexOf(order.id);
                        const selected = selectedIndex >= 0;
                        const match = vehicleMatches(order, vehicle);
                        return (
                          <tr
                            key={order.id}
                            onClick={() => toggleOrder(order.id)}
                            className={`h-12 cursor-pointer border-t border-border ${selected ? "bg-blue-50" : "bg-white hover:bg-slate-50"}`}
                          >
                            <td className="px-3 py-2">
                              {selected ? (
                                <div className="flex items-center gap-1">
                                  <span className="rounded bg-blue-100 px-2 py-1 text-xs font-bold text-blue-700">#{selectedIndex + 1}</span>
                                  <button onClick={(event) => { event.stopPropagation(); moveSelectedOrder(selectedIndex, -1); }} className="rounded p-1 hover:bg-white">
                                    <ArrowUp size={14} />
                                  </button>
                                  <button onClick={(event) => { event.stopPropagation(); moveSelectedOrder(selectedIndex, 1); }} className="rounded p-1 hover:bg-white">
                                    <ArrowDown size={14} />
                                  </button>
                                </div>
                              ) : (
                                <span className="text-slate-400">-</span>
                              )}
                            </td>
                            <td className="px-3 py-2 font-semibold text-slate-950">{order.oid || order.id}</td>
                            <td className="px-3 py-2">{order.order_date || "-"} {order.start_time || ""}</td>
                            <td className="px-3 py-2">{order.end_date || order.order_date || "-"} {order.end_time || ""}</td>
                            <td className="max-w-[240px] px-3 py-2 font-medium text-slate-900"><span className="block truncate">{shortRoute(order.pickup_location, order.dropoff_location)}</span></td>
                            <td className="px-3 py-2">{order.order_type || "-"}</td>
                            <td className="px-3 py-2">
                              <div className="flex flex-col gap-1">
                                <span>{order.vehicle_type || "-"}</span>
                                {vehicle ? (
                                  <span className={match ? "text-xs font-semibold text-emerald-700" : "text-xs font-semibold text-amber-700"}>
                                    {match ? "匹配" : "需确认车型"}
                                  </span>
                                ) : null}
                              </div>
                            </td>
                            <td className="px-3 py-2 font-semibold">{formatCurrency(order.price)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <EmptyState title="未派车订单为空" detail="确认订单入库后会出现在这里。" />
            )}
          </CardContent>
        </Card>

        <ResourcePanel
          title="司机池"
          search={filters.driver}
          onSearch={(value) => setFilters((current) => ({ ...current, driver: value }))}
          placeholder="搜索司机/语言/电话"
        >
          {filteredDrivers.map((item) => (
            <button
              key={item.id}
              className={`w-full rounded-lg border p-3 text-left transition ${driverId === item.id ? "border-blue-500 bg-blue-50" : "border-border bg-white hover:border-blue-200"}`}
              onClick={() => setDriverId(item.id)}
            >
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-bold text-slate-950">{item.name}</p>
                  <p className="mt-1 text-xs text-slate-500">{item.phone || "-"} · {item.driver_code || "-"} · {item.office || item.status || "-"}</p>
                </div>
                <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">{inferredLanguage(item)}</span>
              </div>
            </button>
          ))}
        </ResourcePanel>

        <ResourcePanel
          title="车辆池"
          search={filters.vehicle}
          onSearch={(value) => setFilters((current) => ({ ...current, vehicle: value }))}
          placeholder="搜索车牌/车型/绿牌"
        >
          {filteredVehicles.map((item) => {
            const tags = vehicleTags(item);
            return (
              <button
                key={item.id}
                className={`w-full rounded-lg border p-3 text-left transition ${vehicleId === item.id ? "border-blue-500 bg-blue-50" : "border-border bg-white hover:border-blue-200"}`}
                onClick={() => setVehicleId(item.id)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-bold text-slate-950">{item.plate_number}</p>
                    <p className="mt-1 text-xs text-slate-500">{item.vehicle_type || "-"} · {item.vehicle_type_code || "-"} · {item.plate_short_code || "-"} · {item.seat_count || "-"}座</p>
                    {tags.length ? <p className="mt-2 flex flex-wrap gap-1">{tags.map((tag) => <span key={tag} className="rounded bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700">{tag}</span>)}</p> : null}
                  </div>
                  {tags.includes("雪胎") ? <Snowflake size={16} className="text-blue-500" /> : null}
                </div>
              </button>
            );
          })}
        </ResourcePanel>
      </section>

      {recommendations.length ? (
        <Card className="border-blue-100 bg-blue-50/70">
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-bold text-slate-950">智能派车建议</h2>
                <p className="mt-1 text-sm text-slate-600">系统只给出司机和车辆建议，不会自动落库；采用后仍需人工确认派车。</p>
              </div>
              <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-blue-700">{recommendations.length} 条建议</span>
            </div>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {recommendations.map((item, index) => (
              <button
                key={`${item.driver.id}-${item.vehicle.id}-${index}`}
                className={`rounded-xl border p-4 text-left transition ${
                  driverId === item.driver.id && vehicleId === item.vehicle.id ? "border-blue-500 bg-white shadow-sm" : "border-blue-100 bg-white/85 hover:border-blue-300"
                }`}
                onClick={() => {
                  setDriverId(item.driver.id);
                  setVehicleId(item.vehicle.id);
                  setMessage(`已采用建议：${item.driver.name} / ${item.vehicle.plate_number}。请检查订单后点击批量派车。`);
                }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-bold text-slate-950">#{index + 1} {item.driver.name}</p>
                    <p className="mt-1 text-sm font-semibold text-slate-700">{item.vehicle.plate_number}</p>
                    <p className="mt-1 text-xs text-slate-500">{item.vehicle.vehicle_type || "-"} · {item.driver.driver_language || item.driver.language || "语言未标注"}</p>
                  </div>
                  <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${item.score >= 80 ? "bg-emerald-100 text-emerald-700" : item.score >= 55 ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700"}`}>
                    {item.score}
                  </span>
                </div>
                <ul className="mt-3 space-y-1 text-xs text-slate-600">
                  {(item.reasons || []).slice(0, 3).map((reason) => (
                    <li key={reason} className="line-clamp-1">• {reason}</li>
                  ))}
                </ul>
                {item.conflicts?.length ? (
                  <p className="mt-2 rounded bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-700">含 {item.conflicts.length} 条冲突，建议谨慎采用</p>
                ) : null}
              </button>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {(routeSummary || routeLinks.length) ? (
        <Card className="border-amber-100 bg-amber-50/70">
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-bold text-slate-950">路线接龙与空驶风险</h2>
                <p className="mt-1 text-sm text-slate-600">{routeSummary?.message || "已生成接龙顺序，请人工复核。"}</p>
              </div>
              {routeSummary ? (
                <div className="flex flex-wrap gap-2 text-xs font-bold">
                  <span className="rounded-full bg-white px-3 py-1 text-slate-700">均分 {routeSummary.average_score}</span>
                  <span className={routeSummary.risk_count ? "rounded-full bg-red-100 px-3 py-1 text-red-700" : "rounded-full bg-emerald-100 px-3 py-1 text-emerald-700"}>
                    风险 {routeSummary.risk_count}
                  </span>
                  {routeSummary.same_vehicle_suggestion ? <span className="rounded-full bg-blue-100 px-3 py-1 text-blue-700">建议同车多单</span> : null}
                </div>
              ) : null}
            </div>
          </CardHeader>
          <CardContent className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {routeLinks.map((link, index) => (
              <div key={`${link.from_order_id}-${link.to_order_id}-${index}`} className="rounded-lg border border-white bg-white/85 p-3 text-sm">
                <div className="flex items-start justify-between gap-3">
                  <b className="text-slate-950">#{index + 1} {link.handoff || "地点未完整"}</b>
                  <span className={`rounded-full px-2 py-1 text-xs font-bold ${riskClass(link.risk)}`}>{link.risk || "low"} · {link.score ?? "-"}</span>
                </div>
                <p className="mt-1 text-xs text-slate-500">间隔：{link.time_gap_minutes ?? "未知"} 分钟</p>
                <ul className="mt-2 space-y-1 text-xs text-slate-600">
                  {(link.reasons || []).slice(0, 3).map((reason) => <li key={reason}>• {reason}</li>)}
                </ul>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <Card className="border-emerald-100 bg-emerald-50/70">
        <CardContent className="flex flex-wrap items-center justify-between gap-4 p-4">
          <div className="space-y-1 text-sm">
            <p className="font-bold text-slate-950">分配预览</p>
            <p className="text-slate-600">
              订单 {selectedOrders.length} 单 · 司机 {driver?.name || "未选择"} · 车辆 {vehicle?.plate_number || "未选择"} · 预计收入{" "}
              {formatCurrency(selectedOrderRows.reduce((sum, order) => sum + Number(order.price || 0), 0))}
            </p>
            {routeLinks.length ? (
              <p className="text-xs text-slate-500">接龙：{routeLinks.map((link) => link.handoff).join(" / ")}</p>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button disabled={!canAssign} onClick={() => assignMutation.mutate()}>
              <CheckCircle2 size={16} />
              批量派车
            </Button>
            <Button variant="secondary" disabled={!canReassign} onClick={() => reassignMutation.mutate()}>
              <RefreshCw size={16} />
              重新分配已选
            </Button>
          </div>
        </CardContent>
      </Card>

      {(message || conflicts.length > 0 || assignMutation.isError || reassignMutation.isError) && (
        <Card className={conflicts.length ? "border-amber-200 bg-amber-50" : "border-blue-100 bg-blue-50"}>
          <CardContent className="p-4 text-sm">
            <div className="flex items-start gap-2">
              {conflicts.length ? <AlertTriangle className="mt-0.5 text-amber-600" size={18} /> : <CheckCircle2 className="mt-0.5 text-blue-700" size={18} />}
              <div>
                <p className="font-semibold text-slate-950">{message || "操作已完成"}</p>
                {conflicts.length ? (
                  <ul className="mt-2 space-y-1 text-amber-800">
                    {conflicts.map((conflict, index) => (
                      <li key={index}>{JSON.stringify(conflict)}</li>
                    ))}
                  </ul>
                ) : null}
                {assignMutation.error instanceof Error ? <p className="mt-1 text-red-700">{assignMutation.error.message}</p> : null}
                {reassignMutation.error instanceof Error ? <p className="mt-1 text-red-700">{reassignMutation.error.message}</p> : null}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-bold text-slate-950">已派车订单池</h2>
              <p className="mt-1 text-sm text-slate-500">取消分配会保留历史 assignment，订单回到未派车池。</p>
            </div>
            <label className="flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm">
              <Search size={15} className="text-slate-400" />
              <input className="w-56 outline-none" value={assignmentKeyword} onChange={(event) => setAssignmentKeyword(event.target.value)} placeholder="订单/司机/车辆/状态" />
            </label>
          </div>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          <table className="data-table min-w-[1180px]">
            <thead>
              <tr>
                <th>选</th>
                <th>订单号</th>
                <th>开始日期/时间</th>
                <th>结束日期/时间</th>
                <th>路线</th>
                <th>司机</th>
                <th>车辆</th>
                <th>价格</th>
                <th>执行状态</th>
                <th>最新报备</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {visibleAssignments.map((item) => {
                const id = assignmentId(item);
                return (
                  <tr
                    key={`${id}-${item.order_id}`}
                    onClick={() => toggleAssignment(id)}
                    className={`cursor-pointer ${selectedAssignments.includes(id) ? "bg-blue-50" : ""}`}
                  >
                    <td>
                      <span className={`rounded-full px-2 py-1 text-xs font-bold ${selectedAssignments.includes(id) ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-500"}`}>
                        {selectedAssignments.includes(id) ? "已选" : "点击"}
                      </span>
                    </td>
                    <td className="font-semibold text-slate-950">{item.oid || item.order_id}</td>
                    <td>{item.order_date} {item.start_time}</td>
                    <td>{item.end_date || item.order_date} {item.end_time}</td>
                    <td>{shortRoute(item.pickup_location, item.dropoff_location)}</td>
                    <td>{item.driver_name || "-"}</td>
                    <td>{item.plate_number || "-"}</td>
                    <td>{formatCurrency(item.price)}</td>
                    <td><StatusBadge status={item.execution_status || item.status} /></td>
                    <td>
                      <span className="text-xs text-slate-600">{item.latest_report_type || "-"}</span>
                      <br />
                      <span className="text-xs text-slate-400">{item.latest_report_time || item.report_time || "-"}</span>
                    </td>
                    <td>
                      <Button variant="ghost" className="h-8 px-2 text-red-600" onClick={(event) => { event.stopPropagation(); cancelMutation.mutate(id); }} disabled={cancelMutation.isPending}>
                        <XCircle size={14} />
                        取消
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-bold text-slate-950">日历同步预览</h2>
              <p className="mt-1 text-sm text-slate-500">派车后刷新当天日历，司机端也会读取 active assignment。</p>
            </div>
            <input className="h-9 rounded-md border border-border px-3 text-sm" type="date" value={calendarDate} onChange={(event) => setCalendarDate(event.target.value)} />
          </div>
        </CardHeader>
        <CardContent>
          {calendar.data?.items?.length ? (
            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {calendar.data.items.slice(0, 12).map((item) => (
                <div key={`${item.assignment_id || item.id}-${item.order_id}`} className="rounded-lg border border-border bg-white p-3">
                  <div className="flex items-start justify-between gap-3">
                    <p className="font-bold text-slate-950">{item.plate_number || "-"}</p>
                    <StatusBadge status={item.execution_status || item.dispatch_status || item.status} />
                  </div>
                  <p className="mt-2 text-sm text-slate-700">{item.start_time}-{item.end_time} · {shortRoute(item.pickup_location, item.dropoff_location)}</p>
                  <p className="mt-1 text-xs text-slate-500">{item.driver_name || "-"} · {item.oid || item.order_id}</p>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="当天暂无日历派车" detail="选择包含派车记录的日期，或完成新的派车后查看。" />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function ResourcePanel({
  title,
  search,
  onSearch,
  placeholder,
  children,
}: {
  title: string;
  search: string;
  onSearch: (value: string) => void;
  placeholder: string;
  children: ReactNode;
}) {
  return (
    <Card className="min-h-[640px]">
      <CardHeader>
        <div className="space-y-3">
          <h2 className="text-base font-bold text-slate-950">{title}</h2>
          <label className="flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm">
            <Search size={15} className="text-slate-400" />
            <input className="w-full outline-none" value={search} onChange={(event) => onSearch(event.target.value)} placeholder={placeholder} />
          </label>
        </div>
      </CardHeader>
      <CardContent>
        <div className="max-h-[540px] space-y-2 overflow-auto">
          {children || <EmptyState detail="暂无可用资源。" />}
        </div>
      </CardContent>
    </Card>
  );
}

function riskClass(risk?: string) {
  if (risk === "high") return "bg-red-100 text-red-700";
  if (risk === "medium") return "bg-amber-100 text-amber-700";
  return "bg-emerald-100 text-emerald-700";
}
