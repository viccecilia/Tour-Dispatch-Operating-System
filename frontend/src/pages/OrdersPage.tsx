import { useMemo, useState, type KeyboardEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { formatCurrency, shortRoute } from "@/lib/utils";
import { api } from "@/services/apiClient";
import type { Agency, AssignmentEvidenceChain, Order } from "@/types/api";

type EditableField = "agency_name" | "order_source";
type EditingState = { id: number; field: EditableField; value: string } | null;

export function OrdersPage() {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [agencyFilter, setAgencyFilter] = useState("");
  const [message, setMessage] = useState("");
  const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null);
  const [editing, setEditing] = useState<EditingState>(null);

  const orders = useQuery({ queryKey: ["orders"], queryFn: api.orders });
  const agencies = useQuery({ queryKey: ["agencies", "active"], queryFn: () => api.agencies({ status: "active" }) });

  const updateOrder = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<Order> }) => api.updateOrder(id, payload),
    onSuccess: async () => {
      await invalidateOrderViews(queryClient);
    },
    onError: (error: Error) => setMessage(`订单更新失败：${error.message}`),
  });

  const createAgency = useMutation({
    mutationFn: api.createAgency,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["agencies"] });
    },
    onError: (error: Error) => setMessage(`新增旅行社失败：${error.message}`),
  });

  const evidenceChain = useQuery({
    queryKey: ["order-evidence", selectedOrderId],
    queryFn: () => api.orderEvidence(selectedOrderId || 0),
    enabled: Boolean(selectedOrderId),
  });

  const agencyOptions = useMemo(() => {
    const byName = new Map<string, Agency>();
    for (const agency of agencies.data || []) {
      const name = displayAgencyName(agency);
      if (name) byName.set(name, agency);
    }
    return [...byName.entries()].map(([name, agency]) => ({ name, agency })).sort((a, b) => a.name.localeCompare(b.name));
  }, [agencies.data]);

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    const agencyTerm = agencyFilter.trim().toLowerCase();
    return (orders.data || []).filter((order) => {
      const agencyName = String(order.agency_name || "").trim().toLowerCase();
      if (agencyTerm && agencyName !== agencyTerm) return false;
      if (!term) return true;
      return [
        order.oid,
        order.pickup_location,
        order.dropoff_location,
        order.guest_name,
        order.agency_name,
        order.order_source,
        order.order_note_code,
        order.driver_code,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(term));
    });
  }, [orders.data, query, agencyFilter]);

  async function saveOrderField(id: number, field: EditableField, value: string, agency?: Agency) {
    const trimmed = value.trim();
    setEditing(null);
    if (field === "agency_name") {
      await updateOrder.mutateAsync({ id, payload: { agency_name: trimmed, agency_id: agency?.id } as Partial<Order> });
      if (trimmed) setAgencyFilter(trimmed);
      setMessage(trimmed ? `已更新旅行社：${trimmed}` : "已清空旅行社。");
      return;
    }
    await updateOrder.mutateAsync({ id, payload: { order_source: trimmed } });
    setMessage("来源编码已更新。");
  }

  async function createAgencyAndSave(orderId: number, value: string) {
    const name = value.trim();
    if (!name) return;
    const result = await createAgency.mutateAsync({
      agency_code: "D",
      company_name: name,
      name,
      status: "active",
      is_portal_enabled: 1,
    });
    await saveOrderField(orderId, "agency_name", name, result.agency);
    setMessage(`已新增旅行社并写入订单：${name}`);
  }

  const busy = updateOrder.isPending || createAgency.isPending;

  return (
    <div className="space-y-4">
      {message ? <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm font-medium text-blue-700">{message}</div> : null}

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-bold text-slate-950">订单大表</h2>
              <p className="mt-1 text-sm text-slate-500">旅行社字段可直接点击编辑；输入新旅行社后点 + 会新增到旅行社台账并回填订单。</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <label className="flex h-10 w-64 items-center gap-2 rounded-md border border-border bg-white px-3 text-sm">
                <Search size={16} className="text-slate-400" />
                <input
                  className="w-full bg-transparent outline-none"
                  placeholder="搜索订单号 / 路线 / 客户 / 来源"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </label>
              <select
                className="h-10 rounded-md border border-border bg-white px-3 text-sm font-medium text-slate-700 outline-none"
                value={agencyFilter}
                onChange={(event) => setAgencyFilter(event.target.value)}
                title="按旅行社筛选"
              >
                <option value="">全部旅行社</option>
                {agencyOptions.map((item) => (
                  <option key={item.agency.id} value={item.name}>{item.name}</option>
                ))}
              </select>
              {agencyFilter ? (
                <button type="button" className="h-10 rounded-md border border-border px-3 text-sm font-bold text-slate-600 hover:bg-slate-50" onClick={() => setAgencyFilter("")}>
                  清除筛选
                </button>
              ) : null}
            </div>
          </div>
        </CardHeader>

        {selectedOrderId ? (
          <div className="border-t border-border bg-slate-50 p-4">
            <OrderEvidencePanel chain={evidenceChain.data?.evidence_chain} loading={evidenceChain.isFetching} />
          </div>
        ) : null}

        <CardContent className="overflow-x-auto p-0">
          <table className="data-table min-w-[1320px]">
            <thead>
              <tr>
                <th>订单号</th>
                <th>来源编码</th>
                <th>日期/时间</th>
                <th>结束时间</th>
                <th>路线</th>
                <th>类型</th>
                <th>车型</th>
                <th>司机代码</th>
                <th>价格</th>
                <th>旅行社</th>
                <th>备注</th>
                <th>派车状态</th>
                <th>结算状态</th>
                <th>证据</th>
              </tr>
            </thead>
            <tbody>
              {orders.isLoading ? (
                <tr><td colSpan={14} className="py-10 text-center text-sm text-slate-500">正在加载订单...</td></tr>
              ) : filtered.length ? (
                filtered.slice(0, 80).map((order) => (
                  <tr key={order.id}>
                    <td className="font-semibold text-slate-950">{order.oid || order.id}</td>
                    <EditableTextCell
                      orderId={order.id}
                      field="order_source"
                      value={formatSourceCode(order)}
                      editing={editing}
                      saving={busy}
                      placeholder="来源编码"
                      onEdit={setEditing}
                      onSave={saveOrderField}
                    />
                    <td>{order.order_date || "-"} {order.start_time || ""}</td>
                    <td>{order.end_time || "-"}</td>
                    <td>{shortRoute(order.pickup_location, order.dropoff_location)}</td>
                    <td>{order.order_type || "-"}</td>
                    <td>
                      {order.vehicle_type || "-"}
                      <span className="ml-2 rounded bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-600">{order.vehicle_type_code || "-"}</span>
                    </td>
                    <td>{order.driver_code || "-"}</td>
                    <td>{formatCurrency(order.price_rmb ?? order.price)}</td>
                    <AgencyOrderCell
                      order={order}
                      agencies={agencyOptions}
                      editing={editing}
                      saving={busy}
                      onEdit={setEditing}
                      onSave={saveOrderField}
                      onCreateAndSave={createAgencyAndSave}
                      onFilter={setAgencyFilter}
                    />
                    <td className="max-w-48 truncate">{order.fee_remark || order.remark || "-"}</td>
                    <td><StatusBadge status={order.dispatch_status} /></td>
                    <td><StatusBadge status={order.settlement_status} /></td>
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
                ))
              ) : (
                <tr>
                  <td colSpan={14} className="p-0">
                    <EmptyState title="暂无订单" detail="调整搜索或旅行社筛选条件后再试。" />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}

function AgencyOrderCell({
  order,
  agencies,
  editing,
  saving,
  onEdit,
  onSave,
  onCreateAndSave,
  onFilter,
}: {
  order: Order;
  agencies: Array<{ name: string; agency: Agency }>;
  editing: EditingState;
  saving: boolean;
  onEdit: (value: EditingState) => void;
  onSave: (id: number, field: EditableField, value: string, agency?: Agency) => void | Promise<void>;
  onCreateAndSave: (orderId: number, value: string) => void | Promise<void>;
  onFilter: (value: string) => void;
}) {
  const active = editing?.id === order.id && editing.field === "agency_name";
  const value = active ? editing.value : order.agency_name || "";
  const match = agencies.find((item) => item.name.trim().toLowerCase() === value.trim().toLowerCase());
  const canCreate = value.trim().length > 0 && !match;

  function commit(nextValue = value) {
    const selected = agencies.find((item) => item.name === nextValue || item.name.trim().toLowerCase() === nextValue.trim().toLowerCase());
    return onSave(order.id, "agency_name", nextValue, selected?.agency);
  }

  return (
    <td className="font-semibold">
      {active ? (
        <div className="flex min-w-56 items-center gap-1">
          <input
            autoFocus
            list="order-agency-options"
            className="h-8 w-40 rounded-md border border-blue-300 px-2 text-sm outline-none"
            value={editing.value}
            disabled={saving}
            placeholder="输入或选择旅行社"
            onChange={(event) => onEdit({ id: order.id, field: "agency_name", value: event.target.value })}
            onBlur={(event) => {
              if (!event.currentTarget.parentElement?.contains(event.relatedTarget as Node | null)) commit(event.target.value);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") commit(event.currentTarget.value);
              if (event.key === "Escape") onEdit(null);
            }}
          />
          {canCreate ? (
            <Button
              type="button"
              className="h-8 w-8 p-0"
              disabled={saving}
              title="新增旅行社并写入订单"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => onCreateAndSave(order.id, value)}
            >
              <Plus size={14} />
            </Button>
          ) : null}
          <datalist id="order-agency-options">
            {agencies.map((item) => <option key={item.agency.id} value={item.name} />)}
          </datalist>
        </div>
      ) : (
        <button
          type="button"
          className="text-left font-semibold text-slate-900 underline-offset-2 hover:text-blue-700 hover:underline"
          title="点击编辑；按住 Ctrl 点击按此旅行社筛选"
          onClick={(event) => {
            if (event.ctrlKey && order.agency_name) {
              onFilter(order.agency_name);
              return;
            }
            onEdit({ id: order.id, field: "agency_name", value: order.agency_name || "" });
          }}
        >
          {order.agency_name || "-"}
        </button>
      )}
    </td>
  );
}

function EditableTextCell({
  orderId,
  field,
  value,
  editing,
  saving,
  placeholder,
  onEdit,
  onSave,
}: {
  orderId: number;
  field: EditableField;
  value: string;
  editing: EditingState;
  saving: boolean;
  placeholder: string;
  onEdit: (value: EditingState) => void;
  onSave: (id: number, field: EditableField, value: string) => void | Promise<void>;
}) {
  const active = editing?.id === orderId && editing.field === field;
  function commit(nextValue = editing?.value || "") {
    onEdit(null);
    if (nextValue.trim() !== value.trim()) onSave(orderId, field, nextValue.trim());
  }
  return (
    <td className="font-semibold" onDoubleClick={() => onEdit({ id: orderId, field, value: value === "-" ? "" : value })}>
      {active ? (
        <input
          autoFocus
          className="h-8 w-32 rounded-md border border-blue-300 px-2 text-sm outline-none"
          value={editing.value}
          disabled={saving}
          placeholder={placeholder}
          onChange={(event) => onEdit({ id: orderId, field, value: event.target.value })}
          onBlur={(event) => commit(event.target.value)}
          onKeyDown={(event: KeyboardEvent<HTMLInputElement>) => {
            if (event.key === "Enter") commit(event.currentTarget.value);
            if (event.key === "Escape") onEdit(null);
          }}
        />
      ) : (
        <span title="双击编辑">{value || "-"}</span>
      )}
    </td>
  );
}

function displayAgencyName(agency: Agency) {
  return String(agency.company_name || agency.name || "").trim();
}

function formatSourceCode(order: Order) {
  const noteCode = String(order.order_note_code || "").trim();
  const sourceCode = String(order.order_source || "").trim();
  if (noteCode && sourceCode && noteCode.toUpperCase() !== sourceCode.toUpperCase()) {
    return `${noteCode} / ${sourceCode}`;
  }
  return noteCode || sourceCode || "-";
}

async function invalidateOrderViews(queryClient: ReturnType<typeof useQueryClient>) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["orders"] }),
    queryClient.invalidateQueries({ queryKey: ["calendar"] }),
    queryClient.invalidateQueries({ queryKey: ["finance-summary"] }),
    queryClient.invalidateQueries({ queryKey: ["analytics-summary"] }),
  ]);
}

function OrderEvidencePanel({ chain, loading }: { chain?: AssignmentEvidenceChain; loading: boolean }) {
  if (loading) return <div className="text-sm text-slate-500">正在加载订单执行证据...</div>;
  if (!chain) return <div className="text-sm text-slate-500">暂无证据数据。</div>;
  const parts = [`照片 ${chain.summary.photo_count || 0}`, `报告 ${chain.summary.report_count || 0}`];
  if ((chain.summary.expense_count || 0) > 0) parts.push(`票据/费用 ${chain.summary.expense_count || 0}`);
  return (
    <div className="rounded-xl border border-border bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-black text-slate-950">执行证据链</h3>
          <p className="mt-1 text-xs text-slate-500">{parts.join(" · ")}</p>
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
        )) : <div className="text-sm text-slate-500">暂无时间线记录。</div>}
      </div>
    </div>
  );
}
