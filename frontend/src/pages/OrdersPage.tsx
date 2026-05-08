import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { formatCurrency, shortRoute } from "@/lib/utils";
import { api } from "@/services/apiClient";

export function OrdersPage() {
  const [query, setQuery] = useState("");
  const orders = useQuery({ queryKey: ["orders"], queryFn: api.orders });

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    return (orders.data || []).filter((order) => {
      if (!term) return true;
      return [order.oid, order.pickup_location, order.dropoff_location, order.guest_name, order.agency_name]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(term));
    });
  }, [orders.data, query]);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-bold text-slate-950">订单大表</h2>
            <p className="mt-1 text-sm text-slate-500">从真实订单 API 读取，前端分页展示最近 20 单。</p>
          </div>
          <label className="flex h-10 w-80 items-center gap-2 rounded-md border border-border bg-white px-3 text-sm">
            <Search size={16} className="text-slate-400" />
            <input
              className="w-full bg-transparent outline-none"
              placeholder="搜索订单号 / 路线 / 客户 / 旅行社"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
        </div>
      </CardHeader>
      <CardContent className="overflow-x-auto p-0">
        <table className="data-table">
          <thead>
            <tr>
              <th>订单号</th>
              <th>开始日期/时间</th>
              <th>结束时间</th>
              <th>路线</th>
              <th>类型</th>
              <th>车型</th>
              <th>价格</th>
              <th>派车状态</th>
              <th>结算状态</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 20).map((order) => (
              <tr key={order.id}>
                <td className="font-semibold text-slate-950">{order.oid || order.id}</td>
                <td>{order.order_date || "-"} {order.start_time || ""}</td>
                <td>{order.end_time || "-"}</td>
                <td>{shortRoute(order.pickup_location, order.dropoff_location)}</td>
                <td>{order.order_type || "-"}</td>
                <td>{order.vehicle_type || "-"}</td>
                <td>{formatCurrency(order.price)}</td>
                <td><StatusBadge status={order.dispatch_status} /></td>
                <td><StatusBadge status={order.settlement_status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
