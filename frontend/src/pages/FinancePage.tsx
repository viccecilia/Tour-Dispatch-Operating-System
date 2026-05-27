import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Banknote, ChevronDown, ChevronRight, Download, HandCoins, Search, WalletCards } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { KpiCard } from "@/components/KpiCard";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { formatCurrency, shortRoute } from "@/lib/utils";
import { api } from "@/services/apiClient";
import type { Driver, DriverSettlementStat, FinanceDriverExpense, FinanceOrder } from "@/types/api";

type FinanceFilters = {
  date_from: string;
  date_to: string;
  agency_name: string;
  driver_id: string;
  order_type: string;
  execution_status: string;
  settlement_status: string;
  driver_settlement_status: string;
};

const defaultFilters: FinanceFilters = {
  date_from: "",
  date_to: "",
  agency_name: "",
  driver_id: "",
  order_type: "",
  execution_status: "",
  settlement_status: "",
  driver_settlement_status: "",
};

const orderTypes = ["接机", "送机", "机场接送", "包车", "市内包车", "charter", "airport_pickup", "airport_dropoff"];

export function FinancePage() {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState(defaultFilters);
  const [message, setMessage] = useState("");

  const ledger = useQuery({ queryKey: ["finance-ledger", filters], queryFn: () => api.financeLedger(filters), refetchInterval: 10000 });
  const driverStats = useQuery({ queryKey: ["finance-driver-stats", filters], queryFn: () => api.driverSettlementStats(filters), refetchInterval: 10000 });
  const driverExpenses = useQuery({
    queryKey: ["finance-driver-expenses", filters],
    queryFn: () => api.financeDriverExpenses({ ...filters, submit_status: "submitted,in_hand" }),
    refetchInterval: 10000,
  });
  const drivers = useQuery({ queryKey: ["resource-drivers"], queryFn: api.resourceDrivers });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<FinanceOrder> }) => api.updateSettlement(id, payload),
    onSuccess: async () => {
      setMessage("财务字段已保存。");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["finance-ledger"] }),
        queryClient.invalidateQueries({ queryKey: ["finance-driver-stats"] }),
        queryClient.invalidateQueries({ queryKey: ["finance-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["orders"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] }),
      ]);
    },
    onError: (error: Error) => setMessage(`保存失败：${error.message}`),
  });

  const exportMutation = useMutation({
    mutationFn: () => api.financeExportCsv(filters),
    onSuccess: (csv) => {
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `finance_ledger_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setMessage("财务台账 CSV 已导出。");
    },
    onError: (error: Error) => setMessage(`导出失败：${error.message}`),
  });

  const expenseMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<FinanceDriverExpense> }) => api.updateFinanceDriverExpense(id, payload),
    onSuccess: async () => {
      setMessage("司机费用状态已更新");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["finance-driver-expenses"] }),
        queryClient.invalidateQueries({ queryKey: ["finance-ledger"] }),
        queryClient.invalidateQueries({ queryKey: ["finance-driver-stats"] }),
        queryClient.invalidateQueries({ queryKey: ["finance-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] }),
      ]);
    },
    onError: (error: Error) => setMessage(`费用更新失败：${error.message}`),
  });

  const summary = ledger.data?.summary;
  const rows = useMemo(() => ledger.data?.orders || [], [ledger.data]);

  return (
    <div className="space-y-5">
      <section className="runtime-strip">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="runtime-eyebrow">FINANCE RUNTIME</p>
            <h2 className="runtime-title">财务订单台账</h2>
            <p className="runtime-subtitle">围绕订单价格、司机垫付、代收和结算状态处理日常财务。</p>
          </div>
          <div className="grid min-w-[520px] grid-cols-3 gap-2">
            <FinanceRuntimeStat label="待旅行社" value={formatCurrency(summary?.agency_pending_amount || 0)} tone="amber" />
            <FinanceRuntimeStat label="待司机" value={formatCurrency(summary?.driver_pending_amount || 0)} tone="red" />
            <FinanceRuntimeStat label="代收" value={formatCurrency(summary?.driver_collect_amount || 0)} tone="blue" />
          </div>
        </div>
      </section>
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
        <KpiCard title="总订单数" value={summary?.total_orders || 0} icon={Banknote} tone="blue" />
        <KpiCard title="总金额" value={formatCurrency(summary?.total_amount || 0)} icon={WalletCards} tone="green" />
        <KpiCard title="待旅行社结算" value={formatCurrency(summary?.agency_pending_amount || 0)} icon={HandCoins} tone="amber" />
        <KpiCard title="待司机结算" value={formatCurrency(summary?.driver_pending_amount || 0)} icon={HandCoins} tone="red" />
        <KpiCard title="司机垫付" value={formatCurrency(summary?.driver_advance_amount || 0)} icon={Banknote} tone="amber" />
        <KpiCard title="司机代收" value={formatCurrency(summary?.driver_collect_amount || 0)} icon={WalletCards} tone="blue" />
      </section>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-bold tracking-[0.18em] text-blue-600">财务视角</p>
              <h2 className="mt-1 text-xl font-bold text-slate-950">订单财务台账</h2>
              <p className="mt-1 text-sm text-slate-500">基于订单大表生成，主表优先显示价格、司机、旅行社、执行状态和结算状态；行程信息默认折叠。</p>
            </div>
            <Button disabled={exportMutation.isPending} onClick={() => exportMutation.mutate()}>
              <Download size={16} />
              导出 CSV
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          <FinanceFilterBar filters={filters} drivers={drivers.data || []} message={message} onChange={setFilters} onReset={() => setFilters(defaultFilters)} />
          <FinanceOrdersTable
            rows={rows}
            loading={ledger.isLoading}
            saving={updateMutation.isPending}
            onSave={(id, payload) => updateMutation.mutate({ id, payload })}
          />
        </CardContent>
      </Card>

      <DriverExpensePendingSection
        rows={driverExpenses.data?.expenses || []}
        summary={driverExpenses.data?.summary || {}}
        loading={driverExpenses.isLoading}
        saving={expenseMutation.isPending}
        onUpdate={(id, payload) => expenseMutation.mutate({ id, payload })}
      />

      <DriverSettlementSection rows={driverStats.data?.stats || []} loading={driverStats.isLoading} />
    </div>
  );
}

function DriverExpensePendingSection({
  rows,
  summary,
  loading,
  saving,
  onUpdate,
}: {
  rows: FinanceDriverExpense[];
  summary: Record<string, number>;
  loading: boolean;
  saving: boolean;
  onUpdate: (id: number, payload: Partial<FinanceDriverExpense>) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-bold tracking-[0.18em] text-blue-600">司机费用待确认</p>
            <h2 className="mt-1 text-xl font-bold text-slate-950">垫付 / 代收财务池</h2>
            <p className="mt-1 text-sm text-slate-500">司机端提交的停车费、高速费、门票、代收车费等，会先进入这里，财务确认后再进入司机结算统计。</p>
          </div>
          <div className="grid grid-cols-3 gap-2 text-right text-sm">
            <div className="rounded-lg bg-amber-50 px-3 py-2 text-amber-700">
              <p className="text-xs">待确认</p>
              <b>{summary.driver_expense_pending_count || 0} 笔</b>
            </div>
            <div className="rounded-lg bg-red-50 px-3 py-2 text-red-700">
              <p className="text-xs">司机垫付</p>
              <b>{formatCurrency(summary.driver_advance_pending_amount || 0)}</b>
            </div>
            <div className="rounded-lg bg-blue-50 px-3 py-2 text-blue-700">
              <p className="text-xs">司机代收</p>
              <b>{formatCurrency(summary.driver_collect_pending_amount || 0)}</b>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? <EmptyState title="正在读取司机费用" /> : !rows.length ? <EmptyState title="暂无待确认司机费用" detail="司机提交垫付或代收后，会显示在这里。" /> : (
          <div className="overflow-hidden rounded-lg border border-border">
            <table className="data-table min-w-[1120px]">
              <thead>
                <tr>
                  <th>提交时间</th>
                  <th>司机</th>
                  <th>订单</th>
                  <th>路线</th>
                  <th>类型</th>
                  <th>类别</th>
                  <th>金额</th>
                  <th>状态</th>
                  <th>备注</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>{row.submitted_at || row.created_at || "-"}<small>{row.order_date || ""} {row.start_time || ""}</small></td>
                    <td className="font-semibold text-slate-950">{row.driver_name || row.driver_code || "-"}</td>
                    <td>{row.oid || row.order_id || "-"}</td>
                    <td>{shortRoute(row.pickup_location, row.dropoff_location)}</td>
                    <td>{row.kind_label || row.expense_kind}</td>
                    <td>{row.category || "-"}</td>
                    <td className="font-semibold">{formatCurrency(row.amount || 0)}</td>
                    <td><span className="rounded-full bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-700">{row.status_label || row.submit_status}</span></td>
                    <td className="max-w-[180px] truncate">{row.note || "-"}</td>
                    <td>
                      <div className="flex gap-2">
                        <Button type="button" className="h-8 px-3" disabled={saving} onClick={() => onUpdate(row.id, { submit_status: "confirmed" })}>确认</Button>
                        <Button type="button" variant="secondary" className="h-8 px-3" disabled={saving} onClick={() => onUpdate(row.id, { submit_status: "rejected" })}>驳回</Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function FinanceRuntimeStat({ label, value, tone }: { label: string; value: string; tone: "blue" | "amber" | "red" }) {
  const toneClass = {
    blue: "bg-blue-50 text-blue-700",
    amber: "bg-amber-50 text-amber-700",
    red: "bg-red-50 text-red-700",
  }[tone];
  return (
    <div className={`rounded-2xl px-4 py-3 ${toneClass}`}>
      <div className="text-xs font-black">{label}</div>
      <div className="mt-1 truncate text-lg font-black">{value}</div>
    </div>
  );
}

function FinanceFilterBar({ filters, drivers, message, onChange, onReset }: { filters: FinanceFilters; drivers: Driver[]; message: string; onChange: (next: FinanceFilters) => void; onReset: () => void }) {
  return (
    <div className="rounded-xl border border-border bg-slate-50 p-4">
      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-7">
        <Field label="开始日期" type="date" value={filters.date_from} onChange={(value) => onChange({ ...filters, date_from: value })} />
        <Field label="结束日期" type="date" value={filters.date_to} onChange={(value) => onChange({ ...filters, date_to: value })} />
        <label className="grid gap-1 text-sm font-medium text-slate-600">
          旅行社
          <span className="flex h-10 items-center gap-2 rounded-md border border-border bg-white px-3">
            <Search size={15} className="text-slate-400" />
            <input className="w-full bg-transparent outline-none" value={filters.agency_name} onChange={(event) => onChange({ ...filters, agency_name: event.target.value })} placeholder="名称/代码" />
          </span>
        </label>
        <label className="grid gap-1 text-sm font-medium text-slate-600">
          司机
          <select className="h-10 rounded-md border border-border bg-white px-3" value={filters.driver_id} onChange={(event) => onChange({ ...filters, driver_id: event.target.value })}>
            <option value="">全部司机</option>
            {drivers.map((driver) => <option key={driver.id} value={driver.id}>{driver.name}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-sm font-medium text-slate-600">
          订单类型
          <select className="h-10 rounded-md border border-border bg-white px-3" value={filters.order_type} onChange={(event) => onChange({ ...filters, order_type: event.target.value })}>
            <option value="">全部类型</option>
            {orderTypes.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-sm font-medium text-slate-600">
          执行状态
          <select className="h-10 rounded-md border border-border bg-white px-3" value={filters.execution_status} onChange={(event) => onChange({ ...filters, execution_status: event.target.value })}>
            <option value="">全部执行</option>
            <option value="not_started">未执行</option>
            <option value="running">执行中</option>
            <option value="finished">已完成</option>
            <option value="returned">已归库</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm font-medium text-slate-600">
          结算状态
          <select className="h-10 rounded-md border border-border bg-white px-3" value={filters.settlement_status} onChange={(event) => onChange({ ...filters, settlement_status: event.target.value })}>
            <option value="">全部结算</option>
            <option value="pending">旅行社未结算</option>
            <option value="settled">旅行社已结算</option>
            <option value="paid">已收款</option>
            <option value="unsettled">未结账</option>
          </select>
        </label>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <label className="grid gap-1 text-sm font-medium text-slate-600">
          司机结算
          <select className="h-10 rounded-md border border-border bg-white px-3" value={filters.driver_settlement_status} onChange={(event) => onChange({ ...filters, driver_settlement_status: event.target.value })}>
            <option value="">全部司机结算</option>
            <option value="pending">司机未结算</option>
            <option value="settled">司机已结算</option>
          </select>
        </label>
        <Button type="button" variant="secondary" onClick={onReset}>清空筛选</Button>
        {message ? <span className="rounded-md bg-white px-3 py-2 text-sm text-slate-600">{message}</span> : null}
      </div>
    </div>
  );
}

function FinanceOrdersTable({ rows, loading, saving, onSave }: { rows: FinanceOrder[]; loading: boolean; saving: boolean; onSave: (id: number, payload: Partial<FinanceOrder>) => void }) {
  const [openId, setOpenId] = useState<number | null>(null);
  const [editing, setEditing] = useState<{ id: number; field: keyof FinanceOrder; value: string } | null>(null);
  if (loading) return <EmptyState title="正在加载财务台账" detail="正在读取订单、派车、司机、车辆和旅行社数据。" />;
  if (!rows.length) return <EmptyState title="暂无财务订单" detail="调整筛选条件或确认是否已有订单。" />;

  function commit(row: FinanceOrder, field: keyof FinanceOrder, rawValue: string) {
    setEditing(null);
    const numericFields = new Set(["price", "driver_advance_amount", "driver_collect_amount", "driver_settlement_amount"]);
    const value = numericFields.has(String(field)) ? Number(rawValue || 0) : rawValue;
    onSave(row.order_id || row.id, { [field]: value } as Partial<FinanceOrder>);
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <table className="data-table min-w-[1380px]">
        <thead>
          <tr>
            <th>日期</th>
            <th>订单号</th>
            <th>旅行社</th>
            <th>司机</th>
            <th>订单类型</th>
            <th>执行状态</th>
            <th>订单价格</th>
            <th>司机垫付</th>
            <th>司机代收</th>
            <th>司机结算</th>
            <th>旅行社结算</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <>
              <tr key={row.order_id || row.id}>
                <td>
                  <div className="font-semibold text-slate-950">{row.order_date || "-"}</div>
                  <div className="mt-1 text-xs font-semibold text-slate-500">{formatOrderTimeRange(row)}</div>
                </td>
                <td className="font-semibold text-slate-950">{row.oid || row.order_id || row.id}</td>
                <td>{row.agency_name || "-"}</td>
                <td>{row.driver_name || "-"}</td>
                <td>{row.order_type || "-"}</td>
                <td><ExecutionStatus status={row.execution_status} group={row.execution_group} /></td>
                <EditableMoney row={row} field="price" editing={editing} saving={saving} onEdit={setEditing} onCommit={commit} />
                <EditableMoney row={row} field="driver_advance_amount" editing={editing} saving={saving} onEdit={setEditing} onCommit={commit} />
                <EditableMoney row={row} field="driver_collect_amount" editing={editing} saving={saving} onEdit={setEditing} onCommit={commit} />
                <td>
                  <select className="h-8 rounded-md border border-border px-2 text-xs" value={row.driver_settlement_status || "pending"} onChange={(event) => onSave(row.order_id || row.id, { driver_settlement_status: event.target.value })}>
                    <option value="pending">未结算</option>
                    <option value="settled">已结算</option>
                    <option value="paid">已支付</option>
                    <option value="unsettled">未结账</option>
                  </select>
                </td>
                <td>
                  <select className="h-8 rounded-md border border-border px-2 text-xs" value={row.agency_settlement_status || row.settlement_status || "pending"} onChange={(event) => onSave(row.order_id || row.id, { agency_settlement_status: event.target.value, settlement_status: event.target.value })}>
                    <option value="pending">未结算</option>
                    <option value="settled">已结算</option>
                    <option value="paid">已收款</option>
                    <option value="unsettled">未结账</option>
                  </select>
                </td>
                <td>
                  <Button type="button" variant="ghost" className="h-8 px-2" onClick={() => setOpenId(openId === (row.order_id || row.id) ? null : (row.order_id || row.id))}>
                    {openId === (row.order_id || row.id) ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                    详情
                  </Button>
                </td>
              </tr>
              {openId === (row.order_id || row.id) ? (
                <tr key={`${row.order_id || row.id}-detail`}>
                  <td colSpan={12} className="bg-slate-50">
                    <div className="grid gap-3 p-3 text-sm md:grid-cols-3">
                      <Info label="路线" value={shortRoute(row.pickup_location, row.dropoff_location)} />
                      <Info label="时间" value={`${row.order_date || "-"} ${row.start_time || ""} - ${row.end_date || row.order_date || "-"} ${row.end_time || ""}`} />
                      <Info label="车辆" value={row.vehicle_plate || row.plate_number || row.vehicle_type || "-"} />
                      <Info label="客人" value={[row.guest_name, row.guest_contact].filter(Boolean).join(" / ") || "-"} />
                      <Info label="费用备注" value={row.fee_remark || row.driver_settlement_note || "-"} />
                      <Info label="备注" value={row.remark || "-"} />
                    </div>
                  </td>
                </tr>
              ) : null}
            </>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatOrderTimeRange(row: FinanceOrder) {
  const start = row.start_time || "--:--";
  const endDate = row.end_date && row.end_date !== row.order_date ? `${row.end_date} ` : "";
  const end = row.end_time || "--:--";
  return `${start} - ${endDate}${end}`;
}

function EditableMoney({ row, field, editing, saving, onEdit, onCommit }: { row: FinanceOrder; field: keyof FinanceOrder; editing: { id: number; field: keyof FinanceOrder; value: string } | null; saving: boolean; onEdit: (value: { id: number; field: keyof FinanceOrder; value: string } | null) => void; onCommit: (row: FinanceOrder, field: keyof FinanceOrder, value: string) => void }) {
  const rowId = row.order_id || row.id;
  const active = editing?.id === rowId && editing.field === field;
  const value = String(row[field] ?? 0);
  return (
    <td className="font-semibold" onDoubleClick={() => onEdit({ id: rowId, field, value })}>
      {active ? (
        <input
          autoFocus
          disabled={saving}
          className="h-8 w-28 rounded-md border border-blue-300 px-2 text-sm outline-none"
          value={editing.value}
          onChange={(event) => onEdit({ id: rowId, field, value: event.target.value })}
          onBlur={(event) => onCommit(row, field, event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") onCommit(row, field, event.currentTarget.value);
            if (event.key === "Escape") onEdit(null);
          }}
        />
      ) : (
        <span>{formatCurrency(Number(value) || 0)}</span>
      )}
    </td>
  );
}

function DriverSettlementSection({ rows, loading }: { rows: DriverSettlementStat[]; loading: boolean }) {
  return (
    <Card>
      <CardHeader>
        <div>
          <p className="text-xs font-bold tracking-[0.18em] text-blue-600">司机结算统计</p>
          <h2 className="mt-1 text-xl font-bold text-slate-950">按时间段统计司机完成订单</h2>
          <p className="mt-1 text-sm text-slate-500">统计已完成/已归库订单，区分机场接送、包车和其他订单。</p>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? <EmptyState title="正在加载司机统计" /> : (
          <div className="overflow-hidden rounded-lg border border-border">
            <table className="data-table min-w-[980px]">
              <thead>
                <tr>
                  <th>司机</th>
                  <th>总完成</th>
                  <th>机场接送</th>
                  <th>包车</th>
                  <th>其他</th>
                  <th>总订单金额</th>
                  <th>垫付</th>
                  <th>代收</th>
                  <th>待司机结算</th>
                  <th>已结算</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.driver_id || row.driver_name}>
                    <td className="font-semibold text-slate-950">{row.driver_name || "未派司机"}</td>
                    <td>{row.completed_order_count}</td>
                    <td>{row.airport_order_count}</td>
                    <td>{row.charter_order_count}</td>
                    <td>{row.other_order_count}</td>
                    <td>{formatCurrency(row.total_order_amount || 0)}</td>
                    <td>{formatCurrency(row.driver_advance_amount || 0)}</td>
                    <td>{formatCurrency(row.driver_collect_amount || 0)}</td>
                    <td>{formatCurrency(row.pending_driver_settlement_amount || 0)}</td>
                    <td>{formatCurrency(row.settled_driver_settlement_amount || 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Field({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (value: string) => void; type?: string }) {
  return (
    <label className="grid gap-1 text-sm font-medium text-slate-600">
      {label}
      <input className="h-10 rounded-md border border-border bg-white px-3 text-sm text-slate-900 outline-none focus:border-primary" type={type} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function ExecutionStatus({ status, group }: { status?: string; group?: string }) {
  return (
    <div className="space-y-1">
      <span className="inline-flex rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">{group || status || "-"}</span>
      <StatusBadge status={status || "assigned"} />
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-white p-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-800">{value}</p>
    </div>
  );
}
