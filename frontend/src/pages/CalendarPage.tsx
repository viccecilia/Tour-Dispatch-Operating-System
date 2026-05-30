import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarMatrix } from "@/components/CalendarMatrix";
import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { todayIso } from "@/lib/utils";
import { api } from "@/services/apiClient";
import type { CalendarItem, Order, Vehicle } from "@/types/api";

type View = "day" | "week" | "month";

type CalendarOrderForm = Partial<Order> & {
  id?: number;
  order_date: string;
  start_time: string;
  end_time: string;
  pickup_location: string;
  dropoff_location: string;
};

const viewMeta: Record<View, { label: string; title: string; stepDays: number }> = {
  day: { label: "24h", title: "24 小时窗口", stepDays: 1 },
  week: { label: "7d", title: "7 日窗口", stepDays: 7 },
  month: { label: "30d", title: "30 日窗口", stepDays: 30 },
};

const blankForm: CalendarOrderForm = {
  order_date: todayIso(),
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
    end_date: item.end_date,
    start_time: item.start_time || "09:00",
    end_time: item.end_time || "10:00",
    pickup_location: item.pickup_location || "",
    dropoff_location: item.dropoff_location || "",
    order_type: item.order_type || "",
    vehicle_type: item.vehicle_type || "",
    price: item.price,
    dispatch_status: item.dispatch_status,
    settlement_status: item.settlement_status,
    execution_status: item.execution_status,
  };
}

function slotToForm(slot: { vehicle: Vehicle; order_date: string; start_time: string; end_time: string }): CalendarOrderForm {
  return {
    ...blankForm,
    order_date: slot.order_date,
    start_time: slot.start_time,
    end_time: slot.end_time,
    vehicle_type: slot.vehicle.vehicle_type || "",
    dispatch_status: "unassigned",
    settlement_status: "pending",
    remark: slot.vehicle.id ? `日历新建，参考车辆：${slot.vehicle.plate_number}` : "",
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

export function CalendarPage() {
  const queryClient = useQueryClient();
  const [view, setView] = useState<View>("day");
  const [date, setDate] = useState(todayIso());
  const [editorMode, setEditorMode] = useState<"create" | "edit" | null>(null);
  const [form, setForm] = useState<CalendarOrderForm>(blankForm);
  const calendar = useQuery({ queryKey: ["calendar", view, date], queryFn: () => api.calendar(view, date), refetchInterval: 5000 });
  const currentMeta = viewMeta[view];

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
    setForm(itemToForm(item));
    setEditorMode("edit");
  }

  function openCreate(slot: { vehicle: Vehicle; order_date: string; start_time: string; end_time: string }) {
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

  return (
    <div className="space-y-6">
      <section className="runtime-strip">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="runtime-eyebrow">FLEET TIMELINE</p>
            <h2 className="runtime-title">车辆班组日历</h2>
            <p className="runtime-subtitle">双击订单条编辑订单，双击空白位置新建订单；保存后同步订单中心和派车状态。</p>
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
              <h2 className="text-base font-bold text-slate-950">车辆班组日历</h2>
              <p className="mt-1 text-sm text-slate-500">状态强调版：黄=未确认/未派车，蓝=已派车，紫=运行中，绿=完成，红=异常。</p>
            </div>
            <div className="flex items-center gap-2">
              {(Object.keys(viewMeta) as View[]).map((item) => (
                <Button key={item} variant={view === item ? "primary" : "secondary"} onClick={() => setView(item)}>
                  {viewMeta[item].label}
                </Button>
              ))}
              <Button variant="secondary" onClick={() => setDate(shiftDate(date, -currentMeta.stepDays))}>上一窗口</Button>
              <input
                type="date"
                className="h-9 rounded-md border border-border px-3 text-sm"
                value={date}
                onChange={(event) => setDate(event.target.value)}
              />
              <Button variant="secondary" onClick={() => setDate(shiftDate(date, currentMeta.stepDays))}>下一窗口</Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-2">
              {["unconfirmed", "unassigned", "assigned", "completed", "unsettled", "settled"].map((status) => (
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
              onEditItem={openEdit}
              onCreateSlot={openCreate}
            />
          ) : null}
          {calendar.data && !calendar.data.items?.length ? (
            <EmptyState title="当前日期暂无派车" detail="双击车辆行的空白位置可以新建订单。" />
          ) : null}
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
        />
      ) : null}
    </div>
  );
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
}: {
  mode: "create" | "edit";
  form: CalendarOrderForm;
  saving: boolean;
  canSave: boolean;
  error?: string;
  onChange: (form: CalendarOrderForm) => void;
  onClose: () => void;
  onSave: () => void;
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
            <p className="mt-1 text-sm text-slate-500">日期、时间、路线会直接写入订单库，并联动刷新日历和订单中心。</p>
          </div>
          <button className="rounded-md px-3 py-1 text-sm font-bold text-slate-500 hover:bg-slate-100" type="button" onClick={onClose}>关闭</button>
        </div>
        <div className="grid gap-4 px-6 py-5 md:grid-cols-4">
          <Field label="日期" required><input type="date" value={form.order_date} onChange={(e) => update("order_date", e.target.value)} /></Field>
          <Field label="开始时间"><input type="time" value={form.start_time} onChange={(e) => update("start_time", e.target.value)} /></Field>
          <Field label="结束时间"><input type="time" value={form.end_time} onChange={(e) => update("end_time", e.target.value)} /></Field>
          <Field label="类型"><input value={form.order_type || ""} onChange={(e) => update("order_type", e.target.value)} placeholder="接机 / 送机 / 包车" /></Field>
          <Field label="上车地" required wide><input value={form.pickup_location} onChange={(e) => update("pickup_location", e.target.value)} placeholder="KIX / 大阪市内" /></Field>
          <Field label="目的地" required wide><input value={form.dropoff_location} onChange={(e) => update("dropoff_location", e.target.value)} placeholder="京都市内 / ITM" /></Field>
          <Field label="车型"><input value={form.vehicle_type || ""} onChange={(e) => update("vehicle_type", e.target.value)} placeholder="3代 / 10座" /></Field>
          <Field label="旅行社"><input value={form.agency_name || ""} onChange={(e) => update("agency_name", e.target.value)} placeholder="旅行社名称" /></Field>
          <Field label="客人"><input value={form.guest_name || ""} onChange={(e) => update("guest_name", e.target.value)} placeholder="客人姓名" /></Field>
          <Field label="电话"><input value={form.guest_contact || ""} onChange={(e) => update("guest_contact", e.target.value)} placeholder="手机号 / 微信" /></Field>
          <Field label="金额"><input type="number" value={form.price ?? ""} onChange={(e) => update("price", e.target.value ? Number(e.target.value) : undefined)} placeholder="JPY / RMB" /></Field>
          <Field label="备注" wide><textarea value={form.remark || ""} onChange={(e) => update("remark", e.target.value)} placeholder="儿童座椅、举牌、费用备注等" /></Field>
        </div>
        {error ? <div className="mx-6 rounded-lg bg-red-50 px-3 py-2 text-sm font-bold text-red-700">{error}</div> : null}
        <div className="flex justify-end gap-2 border-t border-border px-6 py-4">
          <Button type="button" variant="secondary" onClick={onClose} disabled={saving}>取消</Button>
          <Button type="button" onClick={onSave} disabled={!canSave || saving}>{saving ? "保存中..." : "保存订单"}</Button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, required, wide, children }: { label: string; required?: boolean; wide?: boolean; children: ReactNode }) {
  return (
    <label className={`space-y-1 ${wide ? "md:col-span-2" : ""}`}>
      <span className="text-xs font-black text-slate-500">{label}{required ? <span className="text-red-500"> *</span> : null}</span>
      <div className="[&>input]:h-10 [&>input]:w-full [&>input]:rounded-md [&>input]:border [&>input]:border-border [&>input]:px-3 [&>input]:text-sm [&>textarea]:min-h-20 [&>textarea]:w-full [&>textarea]:rounded-md [&>textarea]:border [&>textarea]:border-border [&>textarea]:px-3 [&>textarea]:py-2 [&>textarea]:text-sm">
        {children}
      </div>
    </label>
  );
}
