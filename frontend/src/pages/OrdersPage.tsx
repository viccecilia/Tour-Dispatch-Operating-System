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
      return [
        order.oid,
        order.pickup_location,
        order.dropoff_location,
        order.guest_name,
        order.agency_name,
        order.order_source,
        order.order_note_code,
      ]
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
            <p className="mt-1 text-sm text-slate-500">展示真实运营字段：来源、车型代码、费用备注和订单号。</p>
          </div>
          <label className="flex h-10 w-96 items-center gap-2 rounded-md border border-border bg-white px-3 text-sm">
            <Search size={16} className="text-slate-400" />
            <input
              className="w-full bg-transparent outline-none"
              placeholder="搜索订单号 / 路线 / 客户 / 来源"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
        </div>
      </CardHeader>
      <CardContent className="overflow-x-auto p-0">
        <table className="data-table min-w-[1280px]">
          <thead>
            <tr>
              <th>订单号</th>
              <th>来源</th>
              <th>开始日期/时间</th>
              <th>结束时间</th>
              <th>路线</th>
              <th>类型</th>
              <th>车型/代码</th>
              <th>司机代码</th>
              <th>价格</th>
              <th>费用备注</th>
              <th>派车状态</th>
              <th>结算状态</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 30).map((order) => (
              <tr key={order.id}>
                <td className="font-semibold text-slate-950">{order.oid || order.id}</td>
                <td>
                  <span className="font-semibold">{order.order_note_code || "-"}</span>
                  <span className="ml-2 text-slate-500">{order.order_source || order.agency_name || ""}</span>
                </td>
                <td>
                  {order.order_date || "-"} {order.start_time || ""}
                </td>
                <td>{order.end_time || "-"}</td>
                <td>{shortRoute(order.pickup_location, order.dropoff_location)}</td>
                <td>{order.order_type || "-"}</td>
                <td>
                  {order.vehicle_type || "-"}
                  <span className="ml-2 rounded bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-600">
                    {order.vehicle_type_code || "-"}
                  </span>
                </td>
                <td>{order.driver_code || "-"}</td>
                <td>{formatCurrency(order.price_rmb ?? order.price)}</td>
                <td className="max-w-48 truncate">{order.fee_remark || order.remark || "-"}</td>
                <td>
                  <StatusBadge status={order.dispatch_status} />
                </td>
                <td>
                  <StatusBadge status={order.settlement_status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
