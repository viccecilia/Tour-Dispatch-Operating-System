import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { formatCurrency, shortRoute } from "@/lib/utils";
import { api } from "@/services/apiClient";

export function OrdersPage() {
  const [query, setQuery] = useState("");
  const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null);
  const orders = useQuery({ queryKey: ["orders"], queryFn: api.orders });
  const evidenceChain = useQuery({
    queryKey: ["order-evidence", selectedOrderId],
    queryFn: () => api.orderEvidence(selectedOrderId || 0),
    enabled: Boolean(selectedOrderId),
  });

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
      {selectedOrderId ? (
        <div className="border-t border-border bg-slate-50 p-4">
          <OrderEvidencePanel chain={evidenceChain.data?.evidence_chain} loading={evidenceChain.isFetching} />
        </div>
      ) : null}
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
              <th>执行证据</th>
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
                <td>
                  <button
                    type="button"
                    onClick={() => setSelectedOrderId(order.id)}
                    className="rounded-md border border-blue-200 px-2 py-1 text-xs font-bold text-blue-700 hover:bg-blue-50"
                  >
                    查看证据
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function OrderEvidencePanel({ chain, loading }: { chain?: import("@/types/api").AssignmentEvidenceChain; loading: boolean }) {
  if (loading) return <div className="text-sm text-slate-500">正在加载订单执行证据...</div>;
  if (!chain) return <div className="text-sm text-slate-500">暂无证据链数据。</div>;
  return (
    <div className="rounded-xl border border-border bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-black text-slate-950">执行证据链</h3>
          <p className="mt-1 text-xs text-slate-500">
            照片 {chain.summary.photo_count || 0} · 报备 {chain.summary.report_count || 0} · 小票/费用 {chain.summary.expense_count || 0}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {chain.download_files.length ? chain.download_files.map((file) => (
            <a key={`${file.kind}-${file.id}`} href={file.url} target="_blank" rel="noreferrer" className="rounded-md bg-blue-50 px-2 py-1 text-xs font-bold text-blue-700">
              下载{file.label || "证据"}
            </a>
          )) : <span className="text-xs text-slate-500">暂无可下载文件</span>}
        </div>
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {chain.timeline.length ? chain.timeline.slice(0, 12).map((item) => (
          <div key={`${item.kind}-${item.id}-${item.event_time}`} className="rounded-lg bg-slate-50 p-3 text-xs">
            <div className="font-bold text-slate-900">{item.label || item.kind}</div>
            <div className="mt-1 text-slate-500">{item.event_time || "-"} · {item.status || "-"}</div>
            {item.note ? <div className="mt-1 text-slate-600">备注：{item.note}</div> : null}
            {item.file_url ? <a href={item.file_url} target="_blank" rel="noreferrer" className="mt-2 inline-block font-bold text-blue-700">打开文件</a> : null}
          </div>
        )) : <div className="text-sm text-slate-500">暂无 timeline。</div>}
      </div>
    </div>
  );
}
