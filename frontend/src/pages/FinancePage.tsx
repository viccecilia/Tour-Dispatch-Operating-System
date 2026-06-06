import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Banknote, Download, HandCoins, Receipt, Search, WalletCards } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { KpiCard } from "@/components/KpiCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { formatCurrency, shortRoute } from "@/lib/utils";
import { API_BASE_URL, api } from "@/services/apiClient";
import type { Driver, DriverSettlementStat, FinanceDriverExpense, FinanceOrder } from "@/types/api";

type FinanceFilters = {
  date_from: string;
  date_to: string;
  agency_name: string;
  driver_id: string;
  order_type: string;
  settlement_status: string;
};

const defaultFilters: FinanceFilters = {
  date_from: "",
  date_to: "",
  agency_name: "",
  driver_id: "",
  order_type: "",
  settlement_status: "",
};

const orderTypes = ["包车", "接机", "送机"];

export function FinancePage() {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState(defaultFilters);
  const [salaryMonth, setSalaryMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [charterUnit, setCharterUnit] = useState("0");
  const [transferUnit, setTransferUnit] = useState("0");
  const [message, setMessage] = useState("");

  const salaryDates = useMemo(() => monthRange(salaryMonth), [salaryMonth]);
  const ledger = useQuery({
    queryKey: ["finance-ledger", filters],
    queryFn: () => api.financeLedger(filters),
    refetchInterval: 10000,
  });
  const driverStats = useQuery({
    queryKey: ["finance-driver-stats", salaryDates],
    queryFn: () => api.driverSettlementStats({ date_from: salaryDates.date_from, date_to: salaryDates.date_to }),
    refetchInterval: 10000,
  });
  const driverExpenses = useQuery({
    queryKey: ["finance-driver-expenses", filters],
    queryFn: () => api.financeDriverExpenses({ date_from: filters.date_from, date_to: filters.date_to, submit_status: "submitted,in_hand,confirmed,rejected" }),
    refetchInterval: 10000,
  });
  const drivers = useQuery({ queryKey: ["resource-drivers"], queryFn: api.resourceDrivers });

  const updateOrder = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<FinanceOrder> }) => api.updateSettlement(id, payload),
    onSuccess: async () => {
      setMessage("财务状态已保存。");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["finance-ledger"] }),
        queryClient.invalidateQueries({ queryKey: ["finance-driver-stats"] }),
        queryClient.invalidateQueries({ queryKey: ["finance-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["orders"] }),
      ]);
    },
    onError: (error: Error) => setMessage(`保存失败：${error.message}`),
  });

  const updateExpense = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<FinanceDriverExpense> }) => api.updateFinanceDriverExpense(id, payload),
    onSuccess: async () => {
      setMessage("司机费用状态已保存。");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["finance-driver-expenses"] }),
        queryClient.invalidateQueries({ queryKey: ["finance-ledger"] }),
        queryClient.invalidateQueries({ queryKey: ["finance-driver-stats"] }),
      ]);
    },
    onError: (error: Error) => setMessage(`费用保存失败：${error.message}`),
  });

  const exportCsv = useMutation({
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
    },
  });

  const rows = ledger.data?.orders || [];
  const upstreamRows = rows.filter((row) => row.agency_name || row.agency_id || row.agency_code);
  const summary = ledger.data?.summary;
  const salaryRows = buildSalaryRows(driverStats.data?.stats || [], Number(charterUnit || 0), Number(transferUnit || 0));

  return (
    <div className="space-y-5">
      <section className="runtime-strip">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="runtime-eyebrow">FINANCE</p>
            <h2 className="runtime-title">车公司财务</h2>
            <p className="runtime-subtitle">处理旅行社应收、司机工资、司机垫付报销和代收上交。</p>
          </div>
          <div className="grid min-w-[520px] grid-cols-3 gap-2">
            <FinanceRuntimeStat label="旅行社未结" value={formatCurrency(summary?.agency_pending_amount || 0)} tone="amber" />
            <FinanceRuntimeStat label="司机待结" value={formatCurrency(summary?.driver_pending_amount || 0)} tone="red" />
            <FinanceRuntimeStat label="司机代收" value={formatCurrency(summary?.driver_collect_amount || 0)} tone="blue" />
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
        <KpiCard title="订单数" value={summary?.total_orders || 0} icon={Receipt} tone="blue" />
        <KpiCard title="订单金额" value={formatCurrency(summary?.total_amount || 0)} icon={WalletCards} tone="green" />
        <KpiCard title="旅行社待结" value={formatCurrency(summary?.agency_pending_amount || 0)} icon={HandCoins} tone="amber" />
        <KpiCard title="司机待结" value={formatCurrency(summary?.driver_pending_amount || 0)} icon={HandCoins} tone="red" />
        <KpiCard title="垫付待确认" value={formatCurrency(summary?.driver_advance_pending_amount || 0)} icon={Banknote} tone="amber" />
        <KpiCard title="代收待确认" value={formatCurrency(summary?.driver_collect_pending_amount || 0)} icon={WalletCards} tone="blue" />
      </section>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-bold tracking-[0.18em] text-blue-600">UPSTREAM</p>
              <h2 className="mt-1 text-xl font-bold text-slate-950">旅行社应收结算表</h2>
              <p className="mt-1 text-sm text-slate-500">车公司接到旅行社订单后，在这里查看是否已结算；未结算订单可以发起付款请求。</p>
            </div>
            <Button disabled={exportCsv.isPending} onClick={() => exportCsv.mutate()}>
              <Download size={16} />
              导出 CSV
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <FinanceFilterBar filters={filters} drivers={drivers.data || []} message={message} onChange={setFilters} onReset={() => setFilters(defaultFilters)} />
          <AgencySettlementTable
            rows={upstreamRows}
            loading={ledger.isLoading}
            saving={updateOrder.isPending}
            onRequest={(row) => updateOrder.mutate({ id: row.order_id || row.id, payload: { agency_settlement_status: "payment_requested", settlement_status: "payment_requested" } })}
            onMarkPaid={(row) => updateOrder.mutate({ id: row.order_id || row.id, payload: { agency_settlement_status: "paid", settlement_status: "paid" } })}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div>
            <p className="text-xs font-bold tracking-[0.18em] text-blue-600">DRIVER PAYROLL</p>
            <h2 className="mt-1 text-xl font-bold text-slate-950">司机工资单</h2>
            <p className="mt-1 text-sm text-slate-500">按月份统计送迎数量和包车数量，乘以对应单价得到司机本月应结工资。</p>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 rounded-xl border border-border bg-slate-50 p-4 md:grid-cols-4">
            <Field label="结算月份" type="month" value={salaryMonth} onChange={setSalaryMonth} />
            <Field label="送迎单价 JPY" type="number" value={transferUnit} onChange={setTransferUnit} />
            <Field label="包车单价 JPY" type="number" value={charterUnit} onChange={setCharterUnit} />
            <div className="flex items-end text-sm text-slate-500">{salaryDates.date_from} 至 {salaryDates.date_to}</div>
          </div>
          <DriverSalaryTable rows={salaryRows} loading={driverStats.isLoading} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div>
            <p className="text-xs font-bold tracking-[0.18em] text-blue-600">ADVANCE / COLLECTION</p>
            <h2 className="mt-1 text-xl font-bold text-slate-950">司机垫付与代收表</h2>
            <p className="mt-1 text-sm text-slate-500">垫付是司机替公司先付款，需要公司报销；代收是司机替公司收款，需要上交公司。垫付记录可查看领収书照片。</p>
          </div>
        </CardHeader>
        <CardContent>
          <DriverCashflowTable
            rows={driverExpenses.data?.expenses || []}
            loading={driverExpenses.isLoading}
            saving={updateExpense.isPending}
            onUpdate={(id, payload) => updateExpense.mutate({ id, payload })}
          />
        </CardContent>
      </Card>
    </div>
  );
}

function FinanceFilterBar({ filters, drivers, message, onChange, onReset }: { filters: FinanceFilters; drivers: Driver[]; message: string; onChange: (next: FinanceFilters) => void; onReset: () => void }) {
  return (
    <div className="rounded-xl border border-border bg-slate-50 p-4">
      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Field label="开始日期" type="date" value={filters.date_from} onChange={(value) => onChange({ ...filters, date_from: value })} />
        <Field label="结束日期" type="date" value={filters.date_to} onChange={(value) => onChange({ ...filters, date_to: value })} />
        <label className="grid gap-1 text-sm font-medium text-slate-600">
          旅行社
          <span className="flex h-10 items-center gap-2 rounded-md border border-border bg-white px-3">
            <Search size={15} className="text-slate-400" />
            <input className="w-full bg-transparent outline-none" value={filters.agency_name} onChange={(event) => onChange({ ...filters, agency_name: event.target.value })} placeholder="名称或代码" />
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
          类型
          <select className="h-10 rounded-md border border-border bg-white px-3" value={filters.order_type} onChange={(event) => onChange({ ...filters, order_type: event.target.value })}>
            <option value="">全部类型</option>
            {orderTypes.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-sm font-medium text-slate-600">
          旅行社结算
          <select className="h-10 rounded-md border border-border bg-white px-3" value={filters.settlement_status} onChange={(event) => onChange({ ...filters, settlement_status: event.target.value })}>
            <option value="">全部状态</option>
            <option value="pending">未请求</option>
            <option value="payment_requested">已请求</option>
            <option value="receipt_uploaded">旅行社已上传回执</option>
            <option value="paid">已确认收款</option>
            <option value="unsettled">未结算</option>
          </select>
        </label>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button type="button" variant="secondary" onClick={onReset}>清空筛选</Button>
        {message ? <span className="rounded-md bg-white px-3 py-2 text-sm font-semibold text-slate-600">{message}</span> : null}
      </div>
    </div>
  );
}

function AgencySettlementTable({ rows, loading, saving, onRequest, onMarkPaid }: { rows: FinanceOrder[]; loading: boolean; saving: boolean; onRequest: (row: FinanceOrder) => void; onMarkPaid: (row: FinanceOrder) => void }) {
  if (loading) return <EmptyState title="正在读取旅行社结算订单" />;
  if (!rows.length) return <EmptyState title="暂无旅行社结算订单" detail="接到旅行社订单后会出现在这里。" />;
  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <table className="data-table min-w-[1200px]">
        <thead>
          <tr>
            <th>订单</th>
            <th>旅行社</th>
            <th>日期时间</th>
            <th>路线</th>
            <th>金额</th>
            <th>结算状态</th>
            <th>司机/车辆</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const status = row.agency_settlement_status || row.settlement_status || "pending";
            return (
              <tr key={row.order_id || row.id}>
                <td className="font-semibold text-slate-950">{row.oid || row.order_id || row.id}</td>
                <td>{row.agency_name || row.agency_code || "-"}</td>
                <td>{row.order_date || "-"} {row.start_time || ""}{row.end_time ? `-${row.end_time}` : ""}</td>
                <td>{shortRoute(row.pickup_location, row.dropoff_location)}</td>
                <td className="font-semibold">{formatCurrency(row.price || 0)}</td>
                <td><SettlementPill status={status} /></td>
                <td>{[row.driver_name, row.vehicle_plate].filter(Boolean).join(" / ") || "-"}</td>
                <td>
                  <div className="flex flex-wrap gap-2">
                    <Button className="h-8 px-3" disabled={saving || ["payment_requested", "receipt_uploaded", "paid", "settled"].includes(status)} onClick={() => onRequest(row)}>请求付款</Button>
                    <Button className="h-8 px-3" variant="secondary" disabled={saving || status === "paid" || status === "settled"} onClick={() => onMarkPaid(row)}>确认收款</Button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function DriverSalaryTable({ rows, loading }: { rows: SalaryRow[]; loading: boolean }) {
  if (loading) return <EmptyState title="正在统计司机工资" />;
  if (!rows.length) return <EmptyState title="暂无司机工资数据" detail="选择月份内有已完成订单后会显示工资试算。" />;
  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <table className="data-table min-w-[900px]">
        <thead>
          <tr>
            <th>司机</th>
            <th>送迎数量</th>
            <th>包车数量</th>
            <th>其他订单</th>
            <th>送迎工资</th>
            <th>包车工资</th>
            <th>应结工资</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.driver_id || row.driver_name}>
              <td className="font-semibold text-slate-950">{row.driver_name || "未派司机"}</td>
              <td>{row.transfer_count}</td>
              <td>{row.charter_count}</td>
              <td>{row.other_count}</td>
              <td>{formatCurrency(row.transfer_amount)}</td>
              <td>{formatCurrency(row.charter_amount)}</td>
              <td className="font-bold text-slate-950">{formatCurrency(row.total_amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DriverCashflowTable({ rows, loading, saving, onUpdate }: { rows: FinanceDriverExpense[]; loading: boolean; saving: boolean; onUpdate: (id: number, payload: Partial<FinanceDriverExpense>) => void }) {
  if (loading) return <EmptyState title="正在读取垫付和代收记录" />;
  if (!rows.length) return <EmptyState title="暂无司机垫付或代收记录" detail="司机在小程序提交后，财务可在这里确认、驳回和查看领収书。" />;
  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <table className="data-table min-w-[1180px]">
        <thead>
          <tr>
            <th>时间</th>
            <th>司机</th>
            <th>订单</th>
            <th>路线</th>
            <th>类型</th>
            <th>金额</th>
            <th>状态</th>
            <th>领収书</th>
            <th>备注</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{row.submitted_at || row.created_at || "-"}</td>
              <td className="font-semibold text-slate-950">{row.driver_name || row.driver_code || "-"}</td>
              <td>{row.oid || row.order_id || "-"}</td>
              <td>{shortRoute(row.pickup_location, row.dropoff_location)}</td>
              <td>{row.expense_kind === "collect" ? "代收上交" : "垫付报销"}</td>
              <td className="font-semibold">{formatCurrency(row.amount || 0)}</td>
              <td><ExpensePill status={row.submit_status} /></td>
              <td>{row.receipt_photo_url ? <a className="font-semibold text-blue-700 hover:underline" href={assetUrl(row.receipt_photo_url)} target="_blank" rel="noreferrer">查看</a> : "-"}</td>
              <td className="max-w-[240px] truncate">{row.note || "-"}</td>
              <td>
                <div className="flex gap-2">
                  <Button type="button" className="h-8 px-3" disabled={saving || row.submit_status === "confirmed"} onClick={() => onUpdate(row.id, { submit_status: "confirmed" })}>确认</Button>
                  <Button type="button" variant="secondary" className="h-8 px-3" disabled={saving || row.submit_status === "rejected"} onClick={() => onUpdate(row.id, { submit_status: "rejected" })}>驳回</Button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type SalaryRow = {
  driver_id?: number;
  driver_name?: string;
  transfer_count: number;
  charter_count: number;
  other_count: number;
  transfer_amount: number;
  charter_amount: number;
  total_amount: number;
};

function buildSalaryRows(rows: DriverSettlementStat[], charterUnit: number, transferUnit: number): SalaryRow[] {
  return rows.map((row) => {
    const transferCount = Number(row.airport_order_count || 0);
    const charterCount = Number(row.charter_order_count || 0);
    const transferAmount = transferCount * transferUnit;
    const charterAmount = charterCount * charterUnit;
    return {
      driver_id: row.driver_id,
      driver_name: row.driver_name,
      transfer_count: transferCount,
      charter_count: charterCount,
      other_count: Number(row.other_order_count || 0),
      transfer_amount: transferAmount,
      charter_amount: charterAmount,
      total_amount: transferAmount + charterAmount,
    };
  });
}

function monthRange(month: string) {
  const safe = /^\d{4}-\d{2}$/.test(month) ? month : new Date().toISOString().slice(0, 7);
  const [year, monthNum] = safe.split("-").map(Number);
  const end = new Date(year, monthNum, 0).getDate();
  return { date_from: `${safe}-01`, date_to: `${safe}-${String(end).padStart(2, "0")}` };
}

function Field({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (value: string) => void; type?: string }) {
  return (
    <label className="grid gap-1 text-sm font-medium text-slate-600">
      {label}
      <input className="h-10 rounded-md border border-border bg-white px-3 text-sm text-slate-900 outline-none focus:border-primary" type={type} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function FinanceRuntimeStat({ label, value, tone }: { label: string; value: string; tone: "blue" | "amber" | "red" }) {
  const toneClass = { blue: "bg-blue-50 text-blue-700", amber: "bg-amber-50 text-amber-700", red: "bg-red-50 text-red-700" }[tone];
  return (
    <div className={`rounded-2xl px-4 py-3 ${toneClass}`}>
      <div className="text-xs font-black">{label}</div>
      <div className="mt-1 truncate text-lg font-black">{value}</div>
    </div>
  );
}

function SettlementPill({ status }: { status?: string }) {
  const labels: Record<string, string> = {
    pending: "未请求",
    unsettled: "未结算",
    payment_requested: "已请求付款",
    receipt_uploaded: "回执待确认",
    paid: "已收款",
    settled: "已结算",
  };
  return <span className="rounded-full bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-700">{labels[status || ""] || status || "-"}</span>;
}

function ExpensePill({ status }: { status?: string }) {
  const labels: Record<string, string> = {
    submitted: "待确认",
    in_hand: "待上交确认",
    confirmed: "已确认",
    rejected: "已驳回",
  };
  const tone = status === "confirmed" ? "bg-emerald-50 text-emerald-700" : status === "rejected" ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700";
  return <span className={`rounded-full px-2 py-1 text-xs font-semibold ${tone}`}>{labels[status || ""] || status || "-"}</span>;
}

function assetUrl(path: string) {
  if (!path) return "#";
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}
