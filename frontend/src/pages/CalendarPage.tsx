import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { accountScope } from "@/auth/permissions";
import { CalendarMatrix } from "@/components/CalendarMatrix";
import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { shortRoute, todayIso } from "@/lib/utils";
import { api } from "@/services/apiClient";
import type { AuthUser, CalendarItem, CalendarResponse, Order, Vehicle } from "@/types/api";

type View = "day" | "week" | "month";

type CalendarOrderForm = Partial<Order> & {
  id?: number;
  order_date: string;
  end_date: string;
  start_time: string;
  end_time: string;
  pickup_location: string;
  dropoff_location: string;
};

const viewMeta: Record<View, { label: string; title: string; stepDays: number }> = {
  day: { label: "24h", title: "日视图", stepDays: 1 },
  week: { label: "7d", title: "周视图", stepDays: 7 },
  month: { label: "30d", title: "30日视图", stepDays: 30 },
};

const blankForm: CalendarOrderForm = {
  order_date: todayIso(),
  end_date: todayIso(),
  start_time: "09:00",
  end_time: "10:00",
  pickup_location: "",
  dropoff_location: "",
  order_type: "",
  vehicle_type: "",
  agency_name: "",
  guest_name: "",
  guest_contact: "",
  price: undefined,
  remark: "",
};

function shiftDate(value: string, days: number) {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return todayIso();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function itemToForm(item: CalendarItem): CalendarOrderForm {
  return {
    ...blankForm,
    id: Number(item.order_id || item.id || 0) || undefined,
    order_date: item.order_date || todayIso(),
    end_date: item.end_date || item.order_date || todayIso(),
    start_time: item.start_time || "09:00",
    end_time: item.end_time || "10:00",
    pickup_location: item.pickup_location || "",
    dropoff_location: item.dropoff_location || "",
    order_type: item.order_type || "",
    vehicle_type: item.vehicle_type || "",
    agency_name: item.agency_name || "",
    guest_name: item.guest_name || "",
    guest_contact: item.guest_contact || "",
    price: item.price,
    remark: item.remark || "",
    dispatch_status: item.dispatch_status,
    settlement_status: item.settlement_status,
    execution_status: item.execution_status,
  };
}

function slotToForm(slot: { vehicle: Vehicle; order_date: string; start_time: string; end_time: string }): CalendarOrderForm {
  return {
    ...blankForm,
    order_date: slot.order_date,
    end_date: slot.order_date,
    start_time: slot.start_time,
    end_time: slot.end_time,
    vehicle_type: slot.vehicle.vehicle_type || "",
    dispatch_status: "unassigned",
    settlement_status: "pending",
    remark: slot.vehicle.plate_number ? `日历空档新建，建议车辆：${slot.vehicle.plate_number}` : "",
  };
}

function compactPayload(form: CalendarOrderForm): Partial<Order> {
  const payload: Partial<Order> = {
    order_date: form.order_date,
    end_date: form.end_date || form.order_date,
    start_time: form.start_time,
    end_time: form.end_time,
    pickup_location: form.pickup_location.trim(),
    dropoff_location: form.dropoff_location.trim(),
    order_type: form.order_type?.trim(),
    vehicle_type: form.vehicle_type?.trim(),
    agency_name: form.agency_name?.trim(),
    guest_name: form.guest_name?.trim(),
    guest_contact: form.guest_contact?.trim(),
    price: form.price === undefined || form.price === null || String(form.price) === "" ? undefined : Number(form.price),
    remark: form.remark?.trim(),
    dispatch_status: form.dispatch_status || "unassigned",
    settlement_status: form.settlement_status || "pending",
  };
  Object.keys(payload).forEach((key) => {
    const value = payload[key as keyof Order];
    if (value === "" || value === undefined) delete payload[key as keyof Order];
  });
  return payload;
}

export function CalendarPage({ currentUser }: { currentUser: AuthUser }) {
  const queryClient = useQueryClient();
  const scope = accountScope(currentUser);
  const isPlatform = scope === "platform";
  const isOperationsManager = currentUser.role === "operations_manager";
  const canEdit = !isPlatform && (currentUser.role === "admin" || currentUser.role === "dispatcher");
  const showPrice = !isOperationsManager;
  const includeUnassigned = !isOperationsManager;

  const [view, setView] = useState<View>("month");
  const [date, setDate] = useState(todayIso());
  const [selectedDay, setSelectedDay] = useState(todayIso());
  const [selectedDriver, setSelectedDriver] = useState<string>("all");
  const [editorMode, setEditorMode] = useState<"create" | "edit" | null>(null);
  const [form, setForm] = useState<CalendarOrderForm>(blankForm);

  const calendar = useQuery({
    queryKey: ["calendar", view, date, includeUnassigned],
    queryFn: () => api.calendar(view, date, { include_unassigned: includeUnassigned }),
    refetchInterval: 5000,
  });
  const currentMeta = viewMeta[view];

  useEffect(() => {
    if (view !== "month") {
      setSelectedDay(date);
      setSelectedDriver("all");
      return;
    }
    if (!calendar.data?.month_summary?.some((item) => item.date === selectedDay)) {
      setSelectedDay(calendar.data?.month_summary?.[0]?.date || date);
      setSelectedDriver("all");
    }
  }, [calendar.data, date, selectedDay, view]);

  const refreshLinkedData = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["calendar"] }),
      queryClient.invalidateQueries({ queryKey: ["orders"] }),
      queryClient.invalidateQueries({ queryKey: ["assignments"] }),
      queryClient.invalidateQueries({ queryKey: ["unassigned-orders"] }),
      queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
    ]);
  };

  const createOrder = useMutation({
    mutationFn: (payload: Partial<Order>) => api.createOrder(payload),
    onSuccess: refreshLinkedData,
  });

  const updateOrder = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<Order> }) => api.updateOrder(id, payload),
    onSuccess: refreshLinkedData,
  });

  const saving = createOrder.isPending || updateOrder.isPending;
  const saveError = createOrder.error || updateOrder.error;

  function openEdit(item: CalendarItem) {
    if (!canEdit) return;
    setForm(itemToForm(item));
    setEditorMode("edit");
  }

  function openCreate(slot: { vehicle: Vehicle; order_date: string; start_time: string; end_time: string }) {
    if (!canEdit) return;
    setForm(slotToForm(slot));
    setEditorMode("create");
  }

  function closeEditor() {
    if (saving) return;
    setEditorMode(null);
    setForm(blankForm);
  }

  function saveEditor() {
    const payload = compactPayload(form);
    if (!payload.order_date || !payload.pickup_location || !payload.dropoff_location) return;
    if (editorMode === "edit" && form.id) {
      updateOrder.mutate({ id: form.id, payload }, { onSuccess: closeEditor });
    } else {
      createOrder.mutate(payload, { onSuccess: closeEditor });
    }
  }

  const canSave = Boolean(form.order_date && form.pickup_location.trim() && form.dropoff_location.trim());
  const statusLegend = useMemo(
    () => (isOperationsManager ? ["unconfirmed", "assigned", "completed"] : ["unconfirmed", "unassigned", "assigned", "completed", "unsettled", "settled"]),
    [isOperationsManager],
  );

  const effectiveDay = view === "month" ? selectedDay : date;

  const selectedDayRows = useMemo(
    () => (calendar.data?.items || []).filter((item) => (item.order_date || "").slice(0, 10) === effectiveDay),
    [calendar.data?.items, effectiveDay],
  );

  const selectedDriverRows = useMemo(() => {
    if (selectedDriver === "all") return selectedDayRows;
    return selectedDayRows.filter((item) => driverKey(item) === selectedDriver);
  }, [selectedDayRows, selectedDriver]);

  const driverGroups = useMemo(() => groupByDriver(selectedDayRows), [selectedDayRows]);
  const resourceSummary = useMemo(() => buildResourceSummary(calendar.data, selectedDayRows), [calendar.data, selectedDayRows]);

  return (
    <div className="space-y-6">
      <section className="runtime-strip">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="runtime-eyebrow">{isPlatform ? "MANAGEMENT CALENDAR" : "FLEET TIMELINE"}</p>
            <h2 className="runtime-title">{isPlatform ? "管理端任务日历" : "车队任务日历"}</h2>
            <p className="runtime-subtitle">
              {isPlatform
                ? "按月总览每日订单量，再下钻到当天司机与任务明细。"
                : isOperationsManager
                  ? "运行管理只看执行任务，不显示大厅订单，不显示价格和财务信息。"
                  : "调度与管理可查看时间轴、司机占用、车辆负载，并可直接处理订单。"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="runtime-pill runtime-pill-blue">{viewMeta[view].label}</span>
            <span className="runtime-pill runtime-pill-green">{calendar.data?.items?.length || 0} 条订单</span>
            <span className="runtime-pill runtime-pill-amber">{calendar.data?.vehicles?.length || 0} 台车辆</span>
          </div>
        </div>
      </section>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-bold text-slate-950">{isPlatform ? "全局日历视图" : "排班日历"}</h2>
              <p className="mt-1 text-sm text-slate-500">
                {isPlatform ? "管理端看月总览和司机分布。点击某一天，可查看当天司机与任务聚合。" : "双击空白时间格可新建任务，双击任务卡可打开编辑。"}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {(Object.keys(viewMeta) as View[]).map((item) => (
                <Button key={item} variant={view === item ? "primary" : "secondary"} onClick={() => setView(item)}>
                  {viewMeta[item].label}
                </Button>
              ))}
              <Button variant="secondary" onClick={() => setDate(shiftDate(date, -currentMeta.stepDays))}>
                上一段
              </Button>
              <input
                type="date"
                className="h-9 rounded-md border border-border px-3 text-sm"
                value={date}
                onChange={(event) => setDate(event.target.value)}
              />
              <Button variant="secondary" onClick={() => setDate(shiftDate(date, currentMeta.stepDays))}>
                下一段
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-2">
              {statusLegend.map((status) => (
                <StatusBadge key={status} status={status} />
              ))}
            </div>
            <div className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600">
              {currentMeta.title}：{calendar.data?.start_date || date} 至 {calendar.data?.end_date || date}
            </div>
          </div>

          {calendar.isLoading ? <div className="text-sm text-slate-500">正在加载日历...</div> : null}
          {calendar.isError ? <div className="text-sm text-red-600">日历接口加载失败。</div> : null}

          {calendar.data ? (
            <CalendarMatrix
              vehicles={calendar.data.vehicles || []}
              items={calendar.data.items}
              view={view}
              startDate={calendar.data.start_date}
              endDate={calendar.data.end_date}
              onEditItem={canEdit ? openEdit : undefined}
              onCreateSlot={canEdit ? openCreate : undefined}
              showPrice={showPrice}
              showEdit={canEdit}
            />
          ) : null}

          {calendar.data && !calendar.data.items?.length ? <EmptyState title="当前没有任务日历" detail="可以切换日期范围，或等待订单和派车数据同步进来。" /> : null}
        </CardContent>
      </Card>

      {view === "month" ? (
        <MonthSummaryPanel
          summary={calendar.data?.month_summary || []}
          selectedDay={selectedDay}
          onSelectDay={(value) => {
            setSelectedDay(value);
            setSelectedDriver("all");
          }}
        />
      ) : null}

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-bold text-slate-950">{effectiveDay} 司机任务视图</h2>
              <p className="mt-1 text-sm text-slate-500">先看当天任务总量和空闲资源，再按司机下钻查看每个人的任务卡片。</p>
            </div>
            <div className="flex flex-wrap gap-2 text-xs font-bold">
              <span className="rounded-full bg-blue-50 px-3 py-1 text-blue-700">任务 {resourceSummary.orderCount}</span>
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-emerald-700">在岗司机 {resourceSummary.activeDriverCount}</span>
              <span className="rounded-full bg-amber-50 px-3 py-1 text-amber-700">空闲司机 {resourceSummary.idleDriverCount}</span>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-700">空闲车辆 {resourceSummary.idleVehicleCount}</span>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {driverGroups.length ? (
            <>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {driverGroups.map((group) => (
                  <button
                    key={group.key}
                    type="button"
                    onClick={() => setSelectedDriver(group.key)}
                    className={`rounded-xl border p-4 text-left transition ${
                      selectedDriver === group.key ? "border-blue-500 bg-blue-50 shadow-sm" : "border-border bg-white hover:bg-slate-50"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-black text-slate-950">{group.label}</div>
                        <div className="mt-1 text-xs text-slate-500">{group.items.length} 单任务</div>
                      </div>
                      <span className="rounded-full bg-white px-3 py-1 text-xs font-black text-slate-700">{group.items.length}</span>
                    </div>
                    <div className="mt-3 text-xs text-slate-600">
                      {group.items.slice(0, 2).map((item) => (
                        <div key={`${group.key}-${item.assignment_id || item.order_id}`} className="truncate">
                          {item.start_time || "--:--"} · {shortRoute(item.pickup_location, item.dropoff_location)}
                        </div>
                      ))}
                    </div>
                  </button>
                ))}
              </div>

              <div className="rounded-2xl border border-border bg-white p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="text-base font-black text-slate-950">
                      {selectedDriver === "all" ? "全部司机任务" : driverGroups.find((item) => item.key === selectedDriver)?.label || "司机任务"}
                    </h3>
                    <p className="mt-1 text-sm text-slate-500">这里展示当前司机名下的全部订单内容。运管只看执行信息，不显示价格。</p>
                  </div>
                  <div className="flex gap-2">
                    <Button variant={selectedDriver === "all" ? "primary" : "secondary"} onClick={() => setSelectedDriver("all")}>
                      所有司机
                    </Button>
                    <Button variant="secondary" onClick={() => { window.location.hash = "map"; }}>
                      打开地图
                    </Button>
                  </div>
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  {selectedDriverRows.map((item) => (
                    <DriverTaskCard key={`${item.assignment_id || item.order_id}-${item.start_time || ""}`} item={item} showPrice={showPrice} />
                  ))}
                </div>

                {!selectedDriverRows.length ? <div className="mt-4 text-sm text-slate-500">当前筛选下没有任务。</div> : null}
              </div>
            </>
          ) : (
            <EmptyState title="当天没有司机任务" detail="可以切换日期，或者等待订单派车后再查看。" />
          )}
        </CardContent>
      </Card>

      {editorMode ? (
        <CalendarOrderEditor
          mode={editorMode}
          form={form}
          saving={saving}
          canSave={canSave}
          error={saveError instanceof Error ? saveError.message : ""}
          onChange={setForm}
          onClose={closeEditor}
          onSave={saveEditor}
          showPrice={showPrice}
        />
      ) : null}
    </div>
  );
}

function MonthSummaryPanel({
  summary,
  selectedDay,
  onSelectDay,
}: {
  summary: NonNullable<CalendarResponse["month_summary"]>;
  selectedDay: string;
  onSelectDay: (value: string) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <div>
          <h2 className="text-base font-bold text-slate-950">30日任务总览</h2>
          <p className="mt-1 text-sm text-slate-500">以当前选中日期为起点，向后滚动 30 天，再点击某一天进入司机分组和任务明细。</p>
        </div>
      </CardHeader>
      <CardContent>
        {summary.length ? (
          <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
            {summary.map((item) => (
              <button
                key={item.date}
                type="button"
                onClick={() => onSelectDay(item.date)}
                className={`rounded-xl border p-4 text-left transition ${
                  selectedDay === item.date ? "border-blue-500 bg-blue-50 shadow-sm" : "border-border bg-white hover:bg-slate-50"
                }`}
              >
                <div className="text-xs font-bold text-slate-500">{item.date}</div>
                <div className="mt-2 text-2xl font-black text-slate-950">{item.order_count}</div>
                <div className="mt-1 text-xs text-slate-600">单任务</div>
                <div className="mt-3 flex flex-wrap gap-2 text-[11px] font-bold">
                  <span className="rounded-full bg-red-50 px-2 py-1 text-red-700">异常 {item.exception_count || 0}</span>
                  <span className="rounded-full bg-amber-50 px-2 py-1 text-amber-700">待结算 {item.pending_settlement_count || 0}</span>
                </div>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState detail="当前月份还没有形成日度汇总。" />
        )}
      </CardContent>
    </Card>
  );
}

function DriverTaskCard({ item, showPrice }: { item: CalendarItem; showPrice: boolean }) {
  return (
    <div className="rounded-xl border border-border bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-black text-slate-950">{item.driver_name || "未分配司机"}</div>
          <div className="mt-1 text-xs text-slate-500">
            {item.plate_number || "未分配车辆"} · {item.oid || item.order_id}
          </div>
        </div>
        <StatusBadge status={item.calendar_status || item.execution_status || item.dispatch_status || item.status} />
      </div>

      <div className="mt-3 text-sm font-bold text-slate-900">
        {item.order_date || "-"} {item.start_time || "--:--"} - {item.end_time || "--:--"}
      </div>
      <div className="mt-2 text-sm text-slate-700">{shortRoute(item.pickup_location, item.dropoff_location)}</div>

      {item.guest_name || item.guest_contact ? (
        <div className="mt-3 grid gap-1 text-xs text-slate-600">
          {item.guest_name ? <div>客人：{item.guest_name}</div> : null}
          {item.guest_contact ? <div>联系方式：{item.guest_contact}</div> : null}
        </div>
      ) : null}

      <div className="mt-3 grid gap-2 text-xs text-slate-600 md:grid-cols-2">
        {item.agency_name ? <div>旅行社：{item.agency_name}</div> : null}
        {item.passenger_count !== undefined ? <div>人数：{item.passenger_count || 0}</div> : null}
        {item.luggage_count !== undefined ? <div>行李：{item.luggage_count || 0}</div> : null}
        {showPrice && item.price !== undefined ? <div>价格：¥{Number(item.price || 0).toLocaleString()}</div> : null}
      </div>

      {item.remark ? <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">{item.remark}</div> : null}
    </div>
  );
}

function groupByDriver(items: CalendarItem[]) {
  const map = new Map<string, { key: string; label: string; items: CalendarItem[] }>();
  items.forEach((item) => {
    const key = driverKey(item);
    const label = item.driver_name || "未分配司机";
    const current = map.get(key) || { key, label, items: [] };
    current.items.push(item);
    map.set(key, current);
  });
  return Array.from(map.values()).sort((a, b) => b.items.length - a.items.length || a.label.localeCompare(b.label, "zh-Hans-CN"));
}

function buildResourceSummary(calendar: CalendarResponse | undefined, items: CalendarItem[]) {
  const activeDriverSet = new Set(items.map((item) => item.driver_id || item.driver_name).filter(Boolean));
  const activeVehicleSet = new Set(items.map((item) => item.vehicle_id || item.plate_number).filter(Boolean));
  const totalDrivers = (calendar?.drivers || []).filter((item) => !isRetiredStatus(item.status)).length;
  const totalVehicles = (calendar?.vehicles || []).filter((item) => !isRetiredStatus(item.status)).length;
  return {
    orderCount: items.length,
    activeDriverCount: activeDriverSet.size,
    idleDriverCount: Math.max(0, totalDrivers - activeDriverSet.size),
    idleVehicleCount: Math.max(0, totalVehicles - activeVehicleSet.size),
  };
}

function driverKey(item: CalendarItem) {
  return String(item.driver_id || item.driver_name || "unassigned");
}

function isRetiredStatus(status?: string) {
  const text = String(status || "").toLowerCase();
  return text.includes("retired") || text.includes("deleted") || text.includes("removed");
}

function CalendarOrderEditor({
  mode,
  form,
  saving,
  canSave,
  error,
  onChange,
  onClose,
  onSave,
  showPrice,
}: {
  mode: "create" | "edit";
  form: CalendarOrderForm;
  saving: boolean;
  canSave: boolean;
  error?: string;
  onChange: (form: CalendarOrderForm) => void;
  onClose: () => void;
  onSave: () => void;
  showPrice: boolean;
}) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const update = (key: keyof CalendarOrderForm, value: string | number | undefined) => onChange({ ...form, [key]: value });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-6" onMouseDown={onClose}>
      <div className="w-full max-w-4xl rounded-2xl bg-white shadow-2xl" onMouseDown={(event) => event.stopPropagation()}>
        <div className="flex items-start justify-between gap-4 border-b border-border px-6 py-4">
          <div>
            <h3 className="text-lg font-black text-slate-950">{mode === "edit" ? "编辑订单" : "新建订单"}</h3>
            <p className="mt-1 text-sm text-slate-500">在日历上直接补录或修正订单，保存后会同步回任务池与排班视图。</p>
          </div>
          <button className="rounded-md px-3 py-1 text-sm font-bold text-slate-500 hover:bg-slate-100" type="button" onClick={onClose}>
            关闭
          </button>
        </div>

        <div className="grid gap-4 px-6 py-5 md:grid-cols-4">
          <Field label="开始日期" required>
            <input type="date" value={form.order_date} onChange={(e) => onChange({ ...form, order_date: e.target.value, end_date: form.end_date || e.target.value })} />
          </Field>
          <Field label="结束日期">
            <input type="date" value={form.end_date || form.order_date} onChange={(e) => update("end_date", e.target.value)} />
          </Field>
          <Field label="开始时间">
            <input type="time" value={form.start_time} onChange={(e) => update("start_time", e.target.value)} />
          </Field>
          <Field label="结束时间">
            <input type="time" value={form.end_time} onChange={(e) => update("end_time", e.target.value)} />
          </Field>

          <Field label="类型">
            <input value={form.order_type || ""} onChange={(e) => update("order_type", e.target.value)} placeholder="接机 / 送机 / 包车" />
          </Field>
          <Field label="起点" required wide>
            <input value={form.pickup_location} onChange={(e) => update("pickup_location", e.target.value)} placeholder="KIX / 大阪市内 / 酒店地址" />
          </Field>
          <Field label="终点" required wide>
            <input value={form.dropoff_location} onChange={(e) => update("dropoff_location", e.target.value)} placeholder="京都站 / ITM / 酒店地址" />
          </Field>
          <Field label="车型">
            <input value={form.vehicle_type || ""} onChange={(e) => update("vehicle_type", e.target.value)} placeholder="A-3 / Hiace / 10座" />
          </Field>

          <Field label="旅行社">
            <input value={form.agency_name || ""} onChange={(e) => update("agency_name", e.target.value)} placeholder="旅行社名称" />
          </Field>
          <Field label="客人姓名">
            <input value={form.guest_name || ""} onChange={(e) => update("guest_name", e.target.value)} placeholder="客人姓名" />
          </Field>
          <Field label="联系方式">
            <input value={form.guest_contact || ""} onChange={(e) => update("guest_contact", e.target.value)} placeholder="电话 / 微信 / LINE" />
          </Field>
          {showPrice ? (
            <Field label="价格">
              <input type="number" value={form.price ?? ""} onChange={(e) => update("price", e.target.value ? Number(e.target.value) : undefined)} placeholder="JPY / RMB" />
            </Field>
          ) : null}

          <Field label="备注" wide>
            <textarea value={form.remark || ""} onChange={(e) => update("remark", e.target.value)} placeholder="儿童座椅、费用备注、特殊要求等" />
          </Field>
        </div>

        {error ? <div className="mx-6 rounded-lg bg-red-50 px-3 py-2 text-sm font-bold text-red-700">{error}</div> : null}

        <div className="flex justify-end gap-2 border-t border-border px-6 py-4">
          <Button type="button" variant="secondary" onClick={onClose} disabled={saving}>
            取消
          </Button>
          <Button type="button" onClick={onSave} disabled={!canSave || saving}>
            {saving ? "保存中..." : "保存订单"}
          </Button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, required, wide, children }: { label: string; required?: boolean; wide?: boolean; children: ReactNode }) {
  return (
    <label className={`space-y-1 ${wide ? "md:col-span-2" : ""}`}>
      <span className="text-xs font-black text-slate-500">
        {label}
        {required ? <span className="text-red-500"> *</span> : null}
      </span>
      <div className="[&>input]:h-10 [&>input]:w-full [&>input]:rounded-md [&>input]:border [&>input]:border-border [&>input]:px-3 [&>input]:text-sm [&>textarea]:min-h-20 [&>textarea]:w-full [&>textarea]:rounded-md [&>textarea]:border [&>textarea]:border-border [&>textarea]:px-3 [&>textarea]:py-2 [&>textarea]:text-sm">
        {children}
      </div>
    </label>
  );
}
