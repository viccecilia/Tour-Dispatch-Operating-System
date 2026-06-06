import { useEffect, useMemo, useState, type PointerEvent as ReactPointerEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { formatCurrency, shortRoute } from "@/lib/utils";
import { api } from "@/services/apiClient";
import type { Agency, AssignmentEvidenceChain, Driver, Order, Vehicle } from "@/types/api";

type EditingOrder = Omit<Partial<Order>, "vehicle_id"> & { id: number; date_time?: string; route?: string; vehicle_id?: number | string };
type EditableKey =
  | "date_time"
  | "start_time"
  | "end_time"
  | "route"
  | "order_type"
  | "vehicle_type"
  | "vehicle_id"
  | "driver_code"
  | "price"
  | "agency_name"
  | "fee_remark";

type SelectOption = { value: string; label: string; driver?: Driver; vehicle?: Vehicle };

const ORDER_TYPE_OPTIONS: SelectOption[] = [
  { value: "包车", label: "包车" },
  { value: "接机", label: "接机" },
  { value: "送机", label: "送机" },
];

const VEHICLE_TYPE_OPTIONS: SelectOption[] = [
  { value: "A-3", label: "A-3" },
  { value: "A-4", label: "A-4" },
  { value: "H", label: "H" },
];
export function OrdersPage() {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [agencyFilter, setAgencyFilter] = useState("");
  const [message, setMessage] = useState("");
  const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null);
  const [editing, setEditing] = useState<EditingOrder | null>(null);

  const orders = useQuery({ queryKey: ["orders"], queryFn: api.orders });
  const agencies = useQuery({ queryKey: ["agencies", "active"], queryFn: () => api.agencies({ status: "active" }) });
  const drivers = useQuery({ queryKey: ["resource-drivers"], queryFn: api.resourceDrivers });
  const vehicles = useQuery({ queryKey: ["resource-vehicles"], queryFn: api.resourceVehicles });

  const updateOrder = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<Order> }) => api.updateOrder(id, payload),
    onSuccess: async () => {
      await invalidateOrderViews(queryClient);
    },
    onError: (error: Error) => setMessage(`订单更新失败：${error.message}`),
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

  const driverOptions = useMemo(
    () => (drivers.data || [])
      .filter((driver) => String(driver.status || driver.driver_status || "active").toLowerCase() !== "disabled")
      .map((driver) => ({
        value: driver.driver_code || String(driver.id),
        label: [driver.driver_code, driver.name].filter(Boolean).join(" / ") || String(driver.id),
        driver,
      })),
    [drivers.data],
  );

  const vehicleOptions = useMemo(
    () => (vehicles.data || [])
      .filter((vehicle) => String(vehicle.status || "available").toLowerCase() !== "disabled")
      .map((vehicle) => ({
        value: String(vehicle.id),
        label: [vehicle.plate_number || vehicle.plate_no, vehicle.vehicle_type].filter(Boolean).join(" / ") || String(vehicle.id),
        vehicle,
      })),
    [vehicles.data],
  );

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
        order.remark,
        order.fee_remark,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(term));
    });
  }, [orders.data, query, agencyFilter]);

  useEffect(() => {
    if (!editing) return;
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest("[data-orders-editing-row='true']")) return;
      void commitEditing();
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
    // commitEditing intentionally reads the latest editing state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editing]);

  function beginEdit(order: Order) {
    if (isAgencyHallOrder(order)) {
      setMessage("旅行社大厅接来的订单不能在这里直接修改，请在订单大厅走变更确认流程。");
      return;
    }
    setMessage("");
    setEditing({
      ...order,
      route: shortRoute(order.pickup_location, order.dropoff_location),
      date_time: formatDateTime(order.order_date, order.start_time),
      driver_code: order.driver_code || order.assigned_driver_code || "",
      vehicle_id: order.vehicle_id || "",
    } as EditingOrder);
  }

  async function commitEditing() {
    if (!editing) return;
    const before = (orders.data || []).find((item) => item.id === editing.id);
    setEditing(null);
    if (!before) return;
    const payload = buildUpdatePayload(before, editing);
    if (!Object.keys(payload).length) return;
    await updateOrder.mutateAsync({ id: editing.id, payload });
    setMessage("订单已更新；如该订单已派给司机，司机端会收到变更通知并看到最新订单内容。");
  }

  function onRowPointerDown(event: ReactPointerEvent<HTMLTableRowElement>, order: Order) {
    if (!editing || editing.id === order.id) return;
    const target = event.target as HTMLElement | null;
    if (target?.closest("button,a,input,select,textarea")) return;
    void commitEditing();
  }

  const busy = updateOrder.isPending;

  return (
    <div className="space-y-4">
      {message ? <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm font-medium text-blue-700">{message}</div> : null}

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-bold text-slate-950">订单大表</h2>
              <p className="mt-1 text-sm text-slate-500">
                本公司订单可双击行直接修改；旅行社大厅接来的订单需走变更确认。已派车订单保存后会通知司机。
              </p>
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
          <table className="data-table min-w-[1760px] table-fixed">
            <colgroup>
              <col className="w-[135px]" />
              <col className="w-[74px]" />
              <col className="w-[112px]" />
              <col className="w-[82px]" />
              <col className="w-[300px]" />
              <col className="w-[82px]" />
              <col className="w-[92px]" />
              <col className="w-[130px]" />
              <col className="w-[130px]" />
              <col className="w-[90px]" />
              <col className="w-[165px]" />
              <col className="w-[320px]" />
              <col className="w-[86px]" />
              <col className="w-[86px]" />
              <col className="w-[86px]" />
            </colgroup>
            <thead>
              <tr>
                <th>订单号</th>
                <th>来源编码</th>
                <th>日期/时间</th>
                <th>结束时间</th>
                <th>路线</th>
                <th>类型</th>
                <th>车型</th>
                <th>用车</th>
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
                <tr><td colSpan={15} className="py-10 text-center text-sm text-slate-500">正在加载订单...</td></tr>
              ) : filtered.length ? (
                filtered.slice(0, 80).map((order) => {
                  const active = editing?.id === order.id;
                  const locked = isAgencyHallOrder(order);
                  return (
                    <tr
                      key={order.id}
                      data-orders-editing-row={active ? "true" : undefined}
                      className={active ? "bg-blue-50/50" : locked ? "bg-slate-50/50" : "cursor-text"}
                      onDoubleClick={() => beginEdit(order)}
                      onPointerDown={(event) => onRowPointerDown(event, order)}
                    >
                      <td className="font-semibold text-slate-950">
                        <div>{displayText(order.oid || order.id)}</div>
                        {locked ? <div className="mt-1 text-[11px] font-medium text-slate-400">旅行社订单</div> : null}
                      </td>
                      <td className="break-words">{displayText(formatSourceCode(order))}</td>
                      <EditableCell active={active} field="date_time" value={active ? (editing as EditingOrder & { date_time?: string } | null)?.date_time : formatDateTime(order.order_date, order.start_time)} className="whitespace-nowrap" onChange={patchEditing} />
                      <EditableCell active={active} field="end_time" value={active ? editing?.end_time : order.end_time} className="whitespace-nowrap" onChange={patchEditing} />
                      <EditableCell active={active} field="route" value={active ? (editing as EditingOrder & { route?: string } | null)?.route : shortRoute(order.pickup_location, order.dropoff_location)} className="leading-5" onChange={patchEditing} />
                      <EditableSelectCell active={active} field="order_type" value={active ? editing?.order_type : order.order_type} className="text-center" options={ORDER_TYPE_OPTIONS} onChange={patchEditing} />
                      <EditableSelectCell active={active} field="vehicle_type" value={active ? editing?.vehicle_type : order.vehicle_type} className="whitespace-nowrap" options={VEHICLE_TYPE_OPTIONS} onChange={patchEditing} />
                      <EditableSelectCell active={active} field="vehicle_id" value={active ? editing?.vehicle_id : order.vehicle_id} displayValue={formatVehicleDisplay(order)} className="whitespace-nowrap" options={vehicleOptions} onChange={patchEditing} />
                      <EditableSelectCell active={active} field="driver_code" value={active ? editing?.driver_code : (order.driver_code || order.assigned_driver_code)} displayValue={formatDriverDisplay(order)} className="whitespace-nowrap" options={driverOptions} onChange={patchEditing} />
                      <EditableCell active={active} field="price" value={active ? (editing?.price ?? editing?.price_rmb) : (order.price_rmb ?? order.price)} className="whitespace-nowrap" onChange={patchEditing} />
                      <EditableCell active={active} field="agency_name" value={active ? editing?.agency_name : order.agency_name} className="font-semibold leading-5" onChange={patchEditing} />
                      <EditableCell active={active} field="fee_remark" value={active ? (editing?.fee_remark || editing?.remark) : (order.fee_remark || order.remark)} className="p-2" multiline onChange={patchEditing} />
                      <td className="whitespace-nowrap"><StatusBadge status={order.dispatch_status} /></td>
                      <td className="whitespace-nowrap"><StatusBadge status={order.settlement_status} /></td>
                      <td className="whitespace-nowrap">
                        <button
                          type="button"
                          onClick={() => setSelectedOrderId(order.id)}
                          className="rounded-md border border-blue-200 px-2 py-1 text-xs font-bold text-blue-700 hover:bg-blue-50"
                        >
                          查看证据
                        </button>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={15} className="p-0">
                    <EmptyState title="暂无订单" detail="请调整搜索或旅行社筛选条件。" />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );

  function patchEditing(field: EditableKey, value: string) {
    setEditing((current) => {
      if (!current) return current;
      if (field === "vehicle_id") {
        const selected = vehicleOptions.find((item) => item.value === value)?.vehicle;
        return {
          ...current,
          vehicle_id: value,
          vehicle_type: selected?.vehicle_type || current.vehicle_type,
          plate_short_code: selected?.plate_short_code || selected?.plate_number || current.plate_short_code,
        } as EditingOrder;
      }
      return { ...current, [field]: value } as EditingOrder;
    });
  }
}

function EditableSelectCell({
  active,
  field,
  value,
  displayValue,
  className = "",
  options,
  onChange,
}: {
  active: boolean;
  field: EditableKey;
  value: unknown;
  displayValue?: unknown;
  className?: string;
  options: SelectOption[];
  onChange: (field: EditableKey, value: string) => void;
}) {
  const text = displayText(displayValue ?? value);
  if (!active) {
    return (
      <td className={className}>
        <span className="break-words">{text}</span>
      </td>
    );
  }
  return (
    <td className={className}>
      <select
        className="h-8 w-full rounded-md border border-blue-300 bg-white px-2 text-sm outline-none"
        value={value == null ? "" : String(value)}
        onChange={(event) => onChange(field, event.target.value)}
      >
        <option value="">请选择</option>
        {options.map((option) => (
          <option key={`${field}-${option.value}`} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </td>
  );
}

function EditableCell({
  active,
  field,
  value,
  className = "",
  multiline = false,
  onChange,
}: {
  active: boolean;
  field: EditableKey;
  value: unknown;
  className?: string;
  multiline?: boolean;
  onChange: (field: EditableKey, value: string) => void;
}) {
  const text = displayText(value);
  if (!active) {
    return (
      <td className={className}>
        {multiline ? (
          <div className="max-h-20 overflow-y-auto rounded-md bg-slate-50/70 px-2 py-1.5 text-xs leading-5 text-slate-700">
            {text}
          </div>
        ) : (
          <span className="break-words">{text}</span>
        )}
      </td>
    );
  }
  if (multiline) {
    return (
      <td className={className}>
        <textarea
          className="h-20 w-full resize-none rounded-md border border-blue-300 bg-white px-2 py-1.5 text-xs leading-5 outline-none"
          value={value == null ? "" : String(value)}
          onChange={(event) => onChange(field, event.target.value)}
        />
      </td>
    );
  }
  return (
    <td className={className}>
      <input
        className="h-8 w-full rounded-md border border-blue-300 bg-white px-2 text-sm outline-none"
        value={value == null ? "" : String(value)}
        onChange={(event) => onChange(field, event.target.value)}
      />
    </td>
  );
}

function buildUpdatePayload(before: Order, editing: EditingOrder): Partial<Order> {
  const payload: Partial<Order> = {};
  const routeValue = String((editing as EditingOrder & { route?: string }).route || "").trim();
  const [orderDate, startTime] = splitDateTime(String((editing as EditingOrder & { date_time?: string }).date_time || ""));
  const [pickup, dropoff] = splitRoute(routeValue);

  const next: Partial<Order> = {
    order_date: orderDate,
    start_time: startTime,
    end_time: textOrEmpty(editing.end_time),
    pickup_location: pickup,
    dropoff_location: dropoff,
    order_type: normalizeOrderType(editing.order_type),
    vehicle_type: textOrEmpty(editing.vehicle_type),
    plate_short_code: textOrEmpty(editing.plate_short_code),
    driver_code: textOrEmpty(editing.driver_code),
    agency_name: textOrEmpty(editing.agency_name),
    fee_remark: textOrEmpty(editing.fee_remark),
  };
  const price = toOptionalNumber(editing.price ?? editing.price_rmb);
  if (price !== undefined) {
    next.price = price;
    next.price_rmb = price;
  }

  for (const [key, value] of Object.entries(next) as Array<[keyof Order, unknown]>) {
    if (String(value ?? "") !== String(before[key] ?? "")) {
      (payload as Record<string, unknown>)[key] = value;
    }
  }
  return payload;
}

function formatDateTime(dateValue: unknown, timeValue: unknown) {
  return `${String(dateValue || "").trim()} ${String(timeValue || "").trim()}`.trim();
}

function splitDateTime(value: string) {
  const text = value.trim();
  const match = text.match(/^(\d{4}[/-]\d{1,2}[/-]\d{1,2})(?:\s+(\d{1,2}:\d{2}))?/);
  if (!match) return [text, ""];
  return [match[1].replace(/\//g, "-"), match[2] || ""];
}

function splitRoute(route: string) {
  const parts = route
    .replace(/[→＞]/g, "->")
    .split(/\s*->\s*/)
    .map((item) => item.trim())
    .filter(Boolean);
  if (!parts.length) return ["", ""];
  return [parts[0], parts.length > 1 ? parts[parts.length - 1] : parts[0]];
}

function isAgencyHallOrder(order: Order) {
  return String(order.source_channel || "").toLowerCase() === "agency_portal"
    || String(order.order_source || "").toLowerCase() === "agency_portal";
}

function displayAgencyName(agency: Agency) {
  return String(agency.company_name || agency.name || "").trim();
}

function formatSourceCode(order: Order) {
  const noteCode = String(order.order_note_code || "").trim();
  const sourceCode = String(order.order_source || "").trim();
  if (sourceCode.toLowerCase() === "agency_portal" || order.source_channel === "agency_portal") {
    return noteCode || "A";
  }
  if (noteCode && sourceCode && noteCode.toUpperCase() !== sourceCode.toUpperCase()) {
    return `${noteCode} / ${sourceCode}`;
  }
  return noteCode || sourceCode || "-";
}

function normalizeOrderType(value: unknown) {
  const text = textOrEmpty(value);
  if (["包车", "接机", "送机"].includes(text)) return text;
  if (/pickup|接机|接/.test(text)) return "接机";
  if (/drop|送机|送/.test(text)) return "送机";
  if (/charter|包车|包/.test(text)) return "包车";
  return text;
}

function formatVehicleDisplay(order: Order) {
  return order.plate_number || order.plate_no || order.plate_short_code || "-";
}

function formatDriverDisplay(order: Order) {
  return order.driver_code || order.assigned_driver_code || order.assigned_driver_name || "-";
}

function displayText(value: unknown) {
  const text = String(value ?? "").trim();
  if (!text || text === "undefined" || text === "null") return "-";
  if (/^\?{2,}/.test(text) || /\?{4,}/.test(text)) return "-";
  return text;
}

function textOrEmpty(value: unknown) {
  return String(value ?? "").trim();
}

function toOptionalNumber(value: unknown) {
  if (value === "" || value == null) return undefined;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : undefined;
}

async function invalidateOrderViews(queryClient: ReturnType<typeof useQueryClient>) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["orders"] }),
    queryClient.invalidateQueries({ queryKey: ["calendar"] }),
    queryClient.invalidateQueries({ queryKey: ["finance-summary"] }),
    queryClient.invalidateQueries({ queryKey: ["analytics-summary"] }),
    queryClient.invalidateQueries({ queryKey: ["assignments"] }),
    queryClient.invalidateQueries({ queryKey: ["notifications-page"] }),
    queryClient.invalidateQueries({ queryKey: ["notification-summary"] }),
  ]);
}

function OrderEvidencePanel({ chain, loading }: { chain?: AssignmentEvidenceChain; loading: boolean }) {
  if (loading) return <div className="text-sm text-slate-500">正在加载订单执行证据...</div>;
  if (!chain) return <div className="text-sm text-slate-500">暂无证据数据。</div>;
  const parts = [`照片 ${chain.summary.photo_count || 0}`, `报备 ${chain.summary.report_count || 0}`];
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
