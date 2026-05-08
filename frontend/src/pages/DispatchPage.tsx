import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { formatCurrency, shortRoute } from "@/lib/utils";
import { api } from "@/services/apiClient";

export function DispatchPage() {
  const queryClient = useQueryClient();
  const [selectedOrders, setSelectedOrders] = useState<number[]>([]);
  const [driverId, setDriverId] = useState<number | null>(null);
  const [vehicleId, setVehicleId] = useState<number | null>(null);

  const unassigned = useQuery({ queryKey: ["dispatch-unassigned"], queryFn: api.unassignedOrders });
  const assignments = useQuery({ queryKey: ["assignments"], queryFn: api.assignments });
  const drivers = useQuery({ queryKey: ["drivers"], queryFn: api.drivers });
  const vehicles = useQuery({ queryKey: ["vehicles"], queryFn: api.vehicles });

  const selectedPreview = useMemo(
    () => (unassigned.data || []).filter((order) => selectedOrders.includes(order.id)),
    [selectedOrders, unassigned.data],
  );

  const assignMutation = useMutation({
    mutationFn: () => api.assign(selectedOrders, driverId!, vehicleId!),
    onSuccess: () => {
      setSelectedOrders([]);
      void queryClient.invalidateQueries({ queryKey: ["dispatch-unassigned"] });
      void queryClient.invalidateQueries({ queryKey: ["assignments"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
  });

  const canAssign = selectedOrders.length > 0 && driverId && vehicleId && !assignMutation.isPending;

  return (
    <div className="space-y-6">
      <section className="grid gap-6 xl:grid-cols-[1.4fr_0.9fr_0.9fr_0.9fr]">
        <Card className="min-h-[520px]">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-slate-950">未分配订单池</h2>
                <p className="mt-1 text-sm text-slate-500">选择订单后，在右侧选择司机和车辆。</p>
              </div>
              <span className="text-sm font-semibold text-blue-700">已选 {selectedOrders.length} 单</span>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {unassigned.data?.length ? (
              unassigned.data.slice(0, 12).map((order) => {
                const selected = selectedOrders.includes(order.id);
                return (
                  <button
                    key={order.id}
                    className={`w-full rounded-lg border p-4 text-left transition ${
                      selected ? "border-blue-500 bg-blue-50" : "border-border bg-white hover:border-blue-200"
                    }`}
                    onClick={() =>
                      setSelectedOrders((current) =>
                        current.includes(order.id) ? current.filter((id) => id !== order.id) : [...current, order.id],
                      )
                    }
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="text-sm font-bold text-slate-950">{order.oid || order.id}</p>
                        <p className="mt-1 text-sm text-slate-600">{shortRoute(order.pickup_location, order.dropoff_location)}</p>
                        <p className="mt-2 text-xs text-slate-500">
                          {order.order_date} {order.start_time}-{order.end_time} · {order.order_type || "-"} · {order.vehicle_type || "-"}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-semibold text-slate-900">{formatCurrency(order.price)}</p>
                        <StatusBadge status={order.dispatch_status || "unassigned"} className="mt-2" />
                      </div>
                    </div>
                  </button>
                );
              })
            ) : (
              <EmptyState title="未分配订单为空" detail="demo 数据重置后会保留固定未派车订单。" />
            )}
          </CardContent>
        </Card>

        <ResourceList
          title="选择司机"
          items={(drivers.data || []).map((driver) => ({
            id: driver.id,
            title: driver.name,
            subtitle: `${driver.phone || "-"} · ${driver.status || "-"}`,
          }))}
          selectedId={driverId}
          onSelect={setDriverId}
        />

        <ResourceList
          title="选择车辆"
          items={(vehicles.data || []).map((vehicle) => ({
            id: vehicle.id,
            title: vehicle.plate_number,
            subtitle: `${vehicle.vehicle_type || "-"} · ${vehicle.seat_count || "-"}座 · ${vehicle.status || "-"}`,
          }))}
          selectedId={vehicleId}
          onSelect={setVehicleId}
        />

        <Card className="bg-emerald-50">
          <CardHeader>
            <h2 className="text-base font-bold text-slate-950">分配预览</h2>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 text-sm">
              <p className="font-semibold text-slate-900">订单：{selectedPreview.map((order) => order.oid || order.id).join(", ") || "未选择"}</p>
              <p className="text-slate-600">司机：{drivers.data?.find((driver) => driver.id === driverId)?.name || "未选择"}</p>
              <p className="text-slate-600">车辆：{vehicles.data?.find((vehicle) => vehicle.id === vehicleId)?.plate_number || "未选择"}</p>
              {assignMutation.isError ? <p className="text-red-600">派车失败，请检查冲突信息或后端日志。</p> : null}
              {assignMutation.isSuccess ? <p className="text-emerald-700">派车完成，订单已进入已分配池。</p> : null}
            </div>
            <Button className="mt-5 w-full" disabled={!canAssign} onClick={() => assignMutation.mutate()}>
              <CheckCircle2 size={16} />
              确认分配
            </Button>
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <h2 className="text-base font-bold text-slate-950">已分配订单池</h2>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          <table className="data-table">
            <thead>
              <tr>
                <th>订单号</th>
                <th>开始日期/时间</th>
                <th>路线</th>
                <th>司机</th>
                <th>车辆</th>
                <th>价格</th>
                <th>执行状态</th>
              </tr>
            </thead>
            <tbody>
              {(assignments.data || []).slice(0, 12).map((item) => (
                <tr key={`${item.assignment_id || item.id}-${item.order_id}`}>
                  <td className="font-semibold text-slate-950">{item.oid || item.order_id}</td>
                  <td>{item.order_date} {item.start_time}</td>
                  <td>{shortRoute(item.pickup_location, item.dropoff_location)}</td>
                  <td>{item.driver_name || "-"}</td>
                  <td>{item.plate_number || "-"}</td>
                  <td>{formatCurrency(item.price)}</td>
                  <td><StatusBadge status={item.execution_status || item.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}

function ResourceList({
  title,
  items,
  selectedId,
  onSelect,
}: {
  title: string;
  items: Array<{ id: number; title: string; subtitle: string }>;
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  return (
    <Card className="min-h-[520px]">
      <CardHeader>
        <h2 className="text-base font-bold text-slate-950">{title}</h2>
      </CardHeader>
      <CardContent className="space-y-3">
        {items.map((item) => (
          <button
            key={item.id}
            className={`flex w-full items-center justify-between rounded-lg border p-4 text-left transition ${
              selectedId === item.id ? "border-blue-500 bg-blue-50" : "border-border bg-white hover:border-blue-200"
            }`}
            onClick={() => onSelect(item.id)}
          >
            <div>
              <p className="text-sm font-bold text-slate-950">{item.title}</p>
              <p className="mt-1 text-xs text-slate-500">{item.subtitle}</p>
            </div>
            <ArrowRight size={16} className="text-slate-400" />
          </button>
        ))}
      </CardContent>
    </Card>
  );
}
