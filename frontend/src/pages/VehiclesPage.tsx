import { Fragment, FormEvent, KeyboardEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CarFront, ChevronDown, ChevronRight, Plus, Search, UserRound } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/services/apiClient";
import type { Driver, ResourceAlert, Vehicle, VehicleInspectionRecord } from "@/types/api";

type ResourceTab = "vehicles" | "drivers";
type EditingCell = { id: number; key: string; value: string } | null;

const driverInitial: Partial<Driver> = {
  driver_external_id: "",
  office: "",
  name: "",
  driver_code: "",
  driver_language: "中文",
  license_due_date: "",
  license_number: "",
  residence_status: "",
  residence_due_date: "",
  health_check_due_date: "",
  phone: "",
  wechat: "",
  line: "",
  whatsapp: "",
  email: "",
  status: "available",
  driver_status: "available",
};

const vehicleInitial: Partial<Vehicle> = {
  plate_number: "",
  plate_short_code: "",
  vehicle_type: "",
  vehicle_type_code: "",
  vehicle_color: "",
  snow_tire: "no",
  status: "available",
  first_registration_date: "",
  company_registration_date: "",
  last_inspection_date: "",
  next_inspection_due_date: "",
  shaken_due_date: "",
  insurance_due_date: "",
  maintenance_status: "",
};

const driverStatusOptions = [
  ["available", "正常"],
  ["busy", "运行中"],
  ["inactive", "休假"],
  ["leave", "休假"],
];

const vehicleStatusOptions = [
  ["available", "正常"],
  ["busy", "运行中"],
  ["maintenance", "维修"],
  ["inactive", "休假"],
];

export function VehiclesPage() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<ResourceTab>("vehicles");
  const [query, setQuery] = useState("");
  const [vehicleForm, setVehicleForm] = useState<Partial<Vehicle>>(vehicleInitial);
  const [showVehicleForm, setShowVehicleForm] = useState(false);
  const [vehicleRecordsText, setVehicleRecordsText] = useState("");
  const [message, setMessage] = useState("");

  const drivers = useQuery({ queryKey: ["resource-drivers"], queryFn: api.resourceDrivers });
  const vehicles = useQuery({ queryKey: ["resource-vehicles"], queryFn: api.resourceVehicles });
  const reminders = useQuery({ queryKey: ["resource-reminders"], queryFn: api.resourceReminders });

  async function refreshResources() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["resource-drivers"] }),
      queryClient.invalidateQueries({ queryKey: ["resource-vehicles"] }),
      queryClient.invalidateQueries({ queryKey: ["resource-reminders"] }),
      queryClient.invalidateQueries({ queryKey: ["notification-summary"] }),
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] }),
      queryClient.invalidateQueries({ queryKey: ["drivers"] }),
      queryClient.invalidateQueries({ queryKey: ["vehicles"] }),
    ]);
  }

  const createDriver = useMutation({
    mutationFn: api.createDriver,
    onSuccess: async () => {
      setMessage("司机已新增。");
      await refreshResources();
    },
    onError: (error: Error) => setMessage(`新增司机失败：${error.message}`),
  });

  const updateDriver = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<Driver> }) => api.updateDriver(id, payload),
    onSuccess: async () => {
      setMessage("司机信息已保存。");
      await refreshResources();
    },
    onError: (error: Error) => setMessage(`保存司机失败：${error.message}`),
  });

  const createVehicle = useMutation({
    mutationFn: api.createVehicle,
    onSuccess: async () => {
      setVehicleForm(vehicleInitial);
      setVehicleRecordsText("");
      setShowVehicleForm(false);
      setMessage("车辆已新增。");
      await refreshResources();
    },
    onError: (error: Error) => setMessage(`新增车辆失败：${error.message}`),
  });

  const updateVehicle = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<Vehicle> }) => api.updateVehicle(id, payload),
    onSuccess: async () => {
      setMessage("车辆信息已保存。");
      await refreshResources();
    },
    onError: (error: Error) => setMessage(`保存车辆失败：${error.message}`),
  });

  const filteredDrivers = useMemo(() => {
    const term = query.trim().toLowerCase();
    return (drivers.data || []).filter((item) =>
      [
        item.driver_external_id,
        item.office,
        item.name,
        item.driver_code,
        item.driver_language,
        item.license_due_date,
        item.license_number,
        item.residence_status,
        item.residence_due_date,
        item.health_check_due_date,
        item.phone,
        item.wechat,
        item.line,
        item.whatsapp,
        item.email,
        item.status,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(term),
    );
  }, [drivers.data, query]);

  const filteredVehicles = useMemo(() => {
    const term = query.trim().toLowerCase();
    return (vehicles.data || []).filter((item) =>
      [
        item.plate_number,
        item.plate_short_code,
        item.vehicle_type,
        item.vehicle_type_code,
        item.vehicle_color,
        item.snow_tire,
        item.first_registration_date,
        item.company_registration_date,
        item.last_inspection_date,
        item.next_inspection_due_date,
        item.shaken_due_date,
        item.insurance_due_date,
        item.maintenance_status,
        item.status,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(term),
    );
  }, [query, vehicles.data]);

  function submitVehicle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!vehicleForm.plate_number?.trim()) {
      setMessage("请填写车辆号码。");
      return;
    }
    createVehicle.mutate(
      cleanPayload({
        ...normalizeDateFields(vehicleForm),
        inspection_records: parseInspectionRecords(vehicleRecordsText, vehicleForm),
        inspection_expires_at: normalizeFlexibleDate(vehicleForm.next_inspection_due_date),
        insurance_expires_at: normalizeFlexibleDate(vehicleForm.insurance_due_date),
      }),
    );
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-bold tracking-[0.18em] text-blue-600">资源管理</p>
              <h2 className="mt-1 text-xl font-bold text-slate-950">车辆与司机管理</h2>
              <p className="mt-1 text-sm text-slate-500">按 Excel 台账字段维护车辆、司机和到期提醒，提醒规则请到设置页调整。</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant={tab === "vehicles" ? "primary" : "secondary"} onClick={() => setTab("vehicles")}>
                <CarFront size={16} />
                车辆台账
              </Button>
              <Button type="button" variant={tab === "drivers" ? "primary" : "secondary"} onClick={() => setTab("drivers")}>
                <UserRound size={16} />
                司机台账
              </Button>
              {tab === "vehicles" ? (
                <Button type="button" variant="secondary" onClick={() => setShowVehicleForm((value) => !value)}>
                  <Plus size={16} />
                  添加车辆
                </Button>
              ) : null}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          <ResourceReminderStrip alerts={reminders.data?.alerts || []} loading={reminders.isLoading} />

          <div className="flex flex-wrap items-center justify-between gap-3">
            <label className="flex h-10 min-w-[320px] items-center gap-2 rounded-md border border-border bg-white px-3 text-sm">
              <Search size={16} className="text-slate-400" />
              <input
                className="w-full bg-transparent outline-none"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索车牌、车型、司机、电话、到期日期或状态"
              />
            </label>
            {message ? <div className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600">{message}</div> : null}
          </div>

          {tab === "vehicles" ? (
            <div className="space-y-4">
              {showVehicleForm ? (
                <VehicleCreatePanel
                  form={vehicleForm}
                  recordsText={vehicleRecordsText}
                  saving={createVehicle.isPending}
                  onChange={setVehicleForm}
                  onRecordsChange={setVehicleRecordsText}
                  onCancel={() => setShowVehicleForm(false)}
                  onSubmit={submitVehicle}
                />
              ) : null}
              <VehicleTable rows={filteredVehicles} loading={vehicles.isLoading} saving={updateVehicle.isPending} onSave={(id, payload) => updateVehicle.mutate({ id, payload })} />
              <VehicleMaintenanceTable rows={filteredVehicles} loading={vehicles.isLoading} saving={updateVehicle.isPending} onSave={(id, payload) => updateVehicle.mutate({ id, payload })} />
            </div>
          ) : (
            <div className="space-y-4">
              <DriverCreatePanel saving={createDriver.isPending} onCreate={(payload) => createDriver.mutate(payload)} />
              <DriverTable rows={filteredDrivers} loading={drivers.isLoading} saving={updateDriver.isPending} onSave={(id, payload) => updateDriver.mutate({ id, payload })} />
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function ResourceReminderStrip({ alerts, loading }: { alerts: ResourceAlert[]; loading: boolean }) {
  const stats = {
    expired: alerts.filter((item) => item.status === "expired" || item.status === "invalid").length,
    upcoming: alerts.filter((item) => item.status === "upcoming").length,
    maintenance: alerts.filter((item) => item.status === "maintenance").length,
  };
  const firstAlert = alerts[0];
  return (
    <div className="rounded-xl border border-amber-100 bg-amber-50/70 px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <AlertTriangle size={18} className="text-amber-600" />
          <div>
            <p className="text-sm font-bold text-slate-950">提醒摘要</p>
            <p className="text-xs text-slate-500">完整提醒列表已同步到通知中心；提前提醒天数在设置页维护。</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 text-xs font-semibold">
          <span className="rounded-full bg-red-100 px-3 py-1 text-red-700">已过期 {loading ? "-" : stats.expired}</span>
          <span className="rounded-full bg-amber-100 px-3 py-1 text-amber-700">即将到期 {loading ? "-" : stats.upcoming}</span>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-700">维修 {loading ? "-" : stats.maintenance}</span>
        </div>
      </div>
      {firstAlert ? <p className="mt-2 text-xs text-slate-600">最近提醒：{firstAlert.name}，{firstAlert.label}，{firstAlert.message}</p> : null}
    </div>
  );
}

function VehicleCreatePanel({
  form,
  recordsText,
  saving,
  onChange,
  onRecordsChange,
  onCancel,
  onSubmit,
}: {
  form: Partial<Vehicle>;
  recordsText: string;
  saving: boolean;
  onChange: (value: Partial<Vehicle>) => void;
  onRecordsChange: (value: string) => void;
  onCancel: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <form className="rounded-lg border border-border bg-slate-50 p-4" onSubmit={onSubmit}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-bold text-slate-950">新增车辆</h3>
          <p className="text-sm text-slate-500">常用基础字段进入车辆基础表，低频维护日期进入维护表。</p>
        </div>
        <Button type="button" variant="ghost" onClick={onCancel}>收起</Button>
      </div>
      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-4">
        <Field label="车种名" value={form.vehicle_type || ""} onChange={(value) => onChange({ ...form, vehicle_type: value })} />
        <Field label="车両ナンバー" value={form.plate_number || ""} onChange={(value) => onChange({ ...form, plate_number: value })} />
        <Field label="车辆简码" value={form.plate_short_code || ""} onChange={(value) => onChange({ ...form, plate_short_code: value })} />
        <Field label="车辆类型代码" value={form.vehicle_type_code || ""} onChange={(value) => onChange({ ...form, vehicle_type_code: value })} />
        <Field label="色" value={form.vehicle_color || ""} onChange={(value) => onChange({ ...form, vehicle_color: value })} />
        <SelectField label="轮胎" value={form.snow_tire || "no"} onChange={(value) => onChange({ ...form, snow_tire: value })} options={[["no", "普通"], ["yes", "雪胎"]]} />
        <SelectField label="状态" value={form.status || "available"} onChange={(value) => onChange({ ...form, status: value })} options={vehicleStatusOptions} />
        <Field label="初登录日" type="date" value={form.first_registration_date || ""} onChange={(value) => onChange({ ...form, first_registration_date: value })} />
        <Field label="到社登录日" type="date" value={form.company_registration_date || ""} onChange={(value) => onChange({ ...form, company_registration_date: value })} />
        <Field label="最近点检日" type="date" value={form.last_inspection_date || ""} onChange={(value) => onChange({ ...form, last_inspection_date: value })} />
        <Field label="下次点检到期日" type="date" value={form.next_inspection_due_date || ""} onChange={(value) => onChange({ ...form, next_inspection_due_date: value })} />
        <Field label="车检到期日" type="date" value={form.shaken_due_date || ""} onChange={(value) => onChange({ ...form, shaken_due_date: value })} />
        <Field label="保险到期日" type="date" value={form.insurance_due_date || ""} onChange={(value) => onChange({ ...form, insurance_due_date: value })} />
        <Field label="维修状态" value={form.maintenance_status || ""} onChange={(value) => onChange({ ...form, maintenance_status: value })} />
        <label className="grid gap-1 text-sm font-medium text-slate-600 md:col-span-3 xl:col-span-4">
          历次点检/车检记录
          <textarea
            className="min-h-24 rounded-md border border-border bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-primary"
            value={recordsText}
            placeholder={"每行一条，例如：\n2025-04-24 点检\n2026-01-26 车检"}
            onChange={(event) => onRecordsChange(event.target.value)}
          />
        </label>
        <Button type="submit" disabled={saving}>
          <Plus size={16} />
          新增车辆
        </Button>
      </div>
    </form>
  );
}

function VehicleTable({ rows, loading, saving, onSave }: { rows: Vehicle[]; loading: boolean; saving: boolean; onSave: (id: number, payload: Partial<Vehicle>) => void }) {
  const [editing, setEditing] = useState<EditingCell>(null);
  const cols: Array<{ key: keyof Vehicle; label: string; width?: string }> = [
    { key: "vehicle_type", label: "车种名" },
    { key: "plate_number", label: "车牌号码" },
    { key: "plate_short_code", label: "车辆简码" },
    { key: "vehicle_type_code", label: "车型代码" },
    { key: "vehicle_color", label: "颜色" },
    { key: "snow_tire", label: "轮胎" },
    { key: "status", label: "状态" },
  ];
  if (loading) return <EmptyState title="正在加载车辆" detail="正在读取车辆基础信息。" />;
  if (!rows.length) return <EmptyState title="暂无车辆" detail="新增车辆后会同步到派车工作台。" />;
  return (
    <section className="rounded-xl border border-border bg-white">
      <div className="border-b border-border px-4 py-3">
        <h3 className="text-base font-bold text-slate-950">车辆基础信息</h3>
        <p className="text-xs text-slate-500">双击单元格可修改，回车或点击空白处保存。</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[980px] text-center text-sm">
          <thead className="bg-slate-50 text-xs font-bold text-slate-500">
            <tr>
              <th className="px-4 py-3 text-center">序号</th>
              {cols.map((col) => <th key={col.key} className="px-4 py-3 text-center">{col.label}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((row, index) => (
              <tr key={row.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 align-middle text-slate-500">{index + 1}</td>
                {cols.map((col) => (
                  <EditableTd
                    key={`${row.id}-${col.key}`}
                    rowId={row.id}
                    field={col.key}
                    value={displayVehicleValue(row, col.key)}
                    editing={editing}
                    saving={saving}
                    onStart={setEditing}
                    onSave={(id, field, value) => onSave(id, normalizeVehiclePatch(field, value))}
                  />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function VehicleMaintenanceTable({ rows, loading, saving, onSave }: { rows: Vehicle[]; loading: boolean; saving: boolean; onSave: (id: number, payload: Partial<Vehicle>) => void }) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<EditingCell>(null);
  const cols: Array<{ key: keyof Vehicle; label: string }> = [
    { key: "first_registration_date", label: "初登录日" },
    { key: "company_registration_date", label: "到社时间" },
    { key: "last_inspection_date", label: "最近点检" },
    { key: "next_inspection_due_date", label: "点检到期" },
    { key: "shaken_due_date", label: "车检到期" },
    { key: "insurance_due_date", label: "保险到期" },
    { key: "maintenance_status", label: "维修状态" },
  ];
  if (loading || !rows.length) return null;
  return (
    <section className="rounded-xl border border-border bg-white">
      <button type="button" className="flex w-full items-center justify-between px-4 py-3 text-left" onClick={() => setOpen((value) => !value)}>
        <div>
          <h3 className="text-base font-bold text-slate-950">车辆维护记录</h3>
          <p className="text-xs text-slate-500">点检、车检和保险等低频字段默认折叠，偶尔查询时展开。</p>
        </div>
        {open ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
      </button>
      {open ? (
        <div className="overflow-x-auto border-t border-border">
          <table className="w-full min-w-[1120px] text-left text-sm">
            <thead className="bg-slate-50 text-xs font-bold text-slate-500">
              <tr>
                <th className="px-4 py-3">车辆</th>
                {cols.map((col) => <th key={col.key} className="px-4 py-3">{col.label}</th>)}
                <th className="px-4 py-3">历次记录</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((row) => (
                <tr key={row.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-semibold text-slate-900">{row.plate_number}</td>
                  {cols.map((col) => (
                    <EditableTd
                      key={`${row.id}-${col.key}`}
                      rowId={row.id}
                      field={col.key}
                      value={String(row[col.key] || "")}
                      editing={editing}
                      saving={saving}
                      onStart={setEditing}
                      onSave={(id, field, value) => onSave(id, { [field]: value })}
                      render={(value) => dateWithStatus(value)}
                    />
                  ))}
                  <td className="px-4 py-3 text-xs text-slate-600">{formatInspectionRecords(row.inspection_records)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

function DriverCreatePanel({ saving, onCreate }: { saving: boolean; onCreate: (payload: Partial<Driver>) => void }) {
  const [draft, setDraft] = useState<Partial<Driver>>(driverInitial);
  const [open, setOpen] = useState(false);
  function save() {
    if (!draft.name?.trim()) return;
    onCreate(cleanPayload({ ...normalizeDateFields(draft), driver_status: draft.status || draft.driver_status }));
    setDraft(driverInitial);
    setOpen(false);
  }
  return (
    <section className="rounded-xl border border-emerald-100 bg-white">
      <button type="button" className="flex w-full items-center justify-between px-4 py-3 text-left" onClick={() => setOpen((value) => !value)}>
        <div>
          <h3 className="text-base font-bold text-slate-950">新增人员</h3>
          <p className="text-sm text-slate-500">点击展开录入司机，保存后进入下方司机明细表。</p>
        </div>
        <div className="flex items-center gap-2 text-sm font-bold text-emerald-700">
          {open ? "收起" : "展开新增"}
          {open ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
        </div>
      </button>
      {open ? (
        <div className="border-t border-emerald-100 bg-emerald-50/50 p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <p className="text-sm text-slate-500">日期可手写：2.05、2-5、2/5、2026/02/05，保存时会自动标准化。</p>
            <Button type="button" className="h-8 px-3" disabled={saving || !draft.name?.trim()} onClick={save}>新增</Button>
          </div>
          <div className="grid gap-3 md:grid-cols-4 xl:grid-cols-6">
            <Field label="運転手ID" value={draft.driver_external_id || ""} onChange={(value) => setDraft({ ...draft, driver_external_id: value })} />
            <Field label="所属営業所" value={draft.office || ""} onChange={(value) => setDraft({ ...draft, office: value })} />
            <Field label="運転手名" value={draft.name || ""} onChange={(value) => setDraft({ ...draft, name: value })} />
            <Field label="司机代码" value={draft.driver_code || ""} onChange={(value) => setDraft({ ...draft, driver_code: value })} />
            <Field label="语言" value={draft.driver_language || ""} onChange={(value) => setDraft({ ...draft, driver_language: value })} />
            <Field label="免许有效期限" type="date" value={draft.license_due_date || ""} onChange={(value) => setDraft({ ...draft, license_due_date: value })} />
            <Field label="免許番号" value={draft.license_number || ""} onChange={(value) => setDraft({ ...draft, license_number: value })} />
            <Field label="在留资格" value={draft.residence_status || ""} onChange={(value) => setDraft({ ...draft, residence_status: value })} />
            <Field label="再留期限有效日期" type="date" value={draft.residence_due_date || ""} onChange={(value) => setDraft({ ...draft, residence_due_date: value })} />
            <Field label="健康诊断日期" type="date" value={draft.health_check_due_date || ""} onChange={(value) => setDraft({ ...draft, health_check_due_date: value })} />
            <Field label="携帯電話番号" value={draft.phone || ""} onChange={(value) => setDraft({ ...draft, phone: value })} />
            <SelectField label="状态" value={draft.status || "available"} onChange={(value) => setDraft({ ...draft, status: value, driver_status: value })} options={driverStatusOptions} />
            <Field label="wechat" value={draft.wechat || ""} onChange={(value) => setDraft({ ...draft, wechat: value })} />
            <Field label="line" value={draft.line || ""} onChange={(value) => setDraft({ ...draft, line: value })} />
            <Field label="WhatsApp" value={draft.whatsapp || ""} onChange={(value) => setDraft({ ...draft, whatsapp: value })} />
            <Field label="mail" value={draft.email || ""} onChange={(value) => setDraft({ ...draft, email: value })} />
          </div>
        </div>
      ) : null}
    </section>
  );
}

function DriverTable({ rows, loading, saving, onSave }: { rows: Driver[]; loading: boolean; saving: boolean; onSave: (id: number, payload: Partial<Driver>) => void }) {
  const [editing, setEditing] = useState<EditingCell>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const cols: Array<{ key: keyof Driver | "health_remaining"; label: string }> = [
    { key: "name", label: "運転手名" },
    { key: "driver_code", label: "司机代码" },
    { key: "driver_language", label: "语言" },
    { key: "phone", label: "电话" },
    { key: "license_due_date", label: "免许有效期限" },
    { key: "health_check_due_date", label: "健康诊断日期" },
    { key: "health_remaining", label: "健康诊断剩余有效天数" },
    { key: "status", label: "状态" },
  ];
  const detailCols: Array<{ key: keyof Driver; label: string }> = [
    { key: "driver_external_id", label: "運転手ID" },
    { key: "office", label: "所属営業所" },
    { key: "license_number", label: "免許番号" },
    { key: "residence_status", label: "在留资格" },
    { key: "residence_due_date", label: "再留期限有效日期" },
    { key: "wechat", label: "wechat" },
    { key: "line", label: "line" },
    { key: "whatsapp", label: "WhatsApp" },
    { key: "email", label: "mail" },
  ];
  function toggle(rowId: number) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(rowId)) next.delete(rowId);
      else next.add(rowId);
      return next;
    });
  }
  if (loading) return <EmptyState title="正在加载司机" detail="正在读取司机台账。" />;
  if (!rows.length) return <EmptyState title="暂无司机" detail="新增司机后会同步到派车工作台。" />;
  return (
    <section className="rounded-xl border border-border bg-white">
      <div className="border-b border-border px-4 py-3">
        <h3 className="text-base font-bold text-slate-950">司机明细</h3>
        <p className="text-xs text-slate-500">双击单元格可修改，回车或点击空白处保存。</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1120px] text-center text-sm">
          <thead className="bg-slate-50 text-xs font-bold text-slate-500">
            <tr>
              <th className="px-4 py-3 text-center">序号</th>
              <th className="px-4 py-3 text-center">详情</th>
              {cols.map((col) => <th key={col.key} className="px-4 py-3 text-center">{col.label}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((row, index) => {
              const isOpen = expanded.has(row.id);
              return (
                <Fragment key={row.id}>
                  <tr className="hover:bg-slate-50">
                    <td className="px-4 py-3 align-middle text-slate-500">{index + 1}</td>
                    <td className="px-4 py-3 align-middle">
                      <button
                        type="button"
                        className="mx-auto inline-flex items-center gap-1 rounded-full border border-border px-2 py-1 text-xs font-bold text-slate-600 hover:border-blue-300 hover:text-blue-700"
                        onClick={() => toggle(row.id)}
                      >
                        {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                        {isOpen ? "收起" : "展开"}
                      </button>
                    </td>
                    {cols.map((col) => {
                      if (col.key === "health_remaining") {
                        return <td key={`${row.id}-${col.key}`} className="px-4 py-3 text-center align-middle">{remainBadge(healthCheckRemain(row))}</td>;
                      }
                      return (
                        <EditableTd
                          key={`${row.id}-${col.key}`}
                          rowId={row.id}
                          field={col.key}
                          value={String(row[col.key] || "")}
                          editing={editing}
                          saving={saving}
                          onStart={setEditing}
                          onSave={(id, field, value) => onSave(id, normalizeDriverPatch(field, value))}
                          render={(value) => fieldLooksDate(String(col.key)) ? dateWithStatus(value) : value || "-"}
                        />
                      );
                    })}
                  </tr>
                  {isOpen ? (
                    <tr>
                      <td colSpan={cols.length + 2} className="bg-slate-50 px-5 py-4">
                        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                          {detailCols.map((col) => (
                            <EditableDetailItem
                              key={`${row.id}-${col.key}`}
                              rowId={row.id}
                              field={col.key}
                              label={col.label}
                              value={String(row[col.key] || "")}
                              editing={editing}
                              saving={saving}
                              onStart={setEditing}
                              onSave={(id, field, value) => onSave(id, normalizeDriverPatch(field, value))}
                              render={(value) => fieldLooksDate(String(col.key)) ? dateWithStatus(value) : value || "-"}
                            />
                          ))}
                        </div>
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function EditableDetailItem({
  rowId,
  field,
  label,
  value,
  editing,
  saving,
  onStart,
  onSave,
  render,
}: {
  rowId: number;
  field: string;
  label: string;
  value: string;
  editing: EditingCell;
  saving: boolean;
  onStart: (cell: EditingCell) => void;
  onSave: (id: number, field: string, value: string) => void;
  render?: (value: string) => React.ReactNode;
}) {
  const active = editing?.id === rowId && editing.key === field;
  function commit(nextValue = editing?.value || "") {
    if (!active) return;
    const normalizedValue = fieldLooksDate(field) ? normalizeFlexibleDate(nextValue) : nextValue;
    onStart(null);
    if (normalizedValue !== value) onSave(rowId, field, normalizedValue);
  }
  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") commit((event.currentTarget as HTMLInputElement).value);
    if (event.key === "Escape") onStart(null);
  }
  return (
    <div className="rounded-lg border border-border bg-white p-3 text-left" onDoubleClick={() => onStart({ id: rowId, key: field, value })}>
      <div className="text-xs font-bold text-slate-500">{label}</div>
      {active ? (
        <input
          autoFocus
          disabled={saving}
          className="mt-2 h-8 w-full rounded-md border border-blue-300 bg-white px-2 text-sm outline-none"
          value={editing.value}
          onChange={(event) => onStart({ id: rowId, key: field, value: event.target.value })}
          onBlur={(event) => commit(event.target.value)}
          onKeyDown={onKeyDown}
        />
      ) : (
        <div className="mt-2 min-h-5 text-sm font-semibold text-slate-900">{render ? render(value) : value || "-"}</div>
      )}
    </div>
  );
}

function EditableTd({
  rowId,
  field,
  value,
  editing,
  saving,
  onStart,
  onSave,
  render,
}: {
  rowId: number;
  field: string;
  value: string;
  editing: EditingCell;
  saving: boolean;
  onStart: (cell: EditingCell) => void;
  onSave: (id: number, field: string, value: string) => void;
  render?: (value: string) => React.ReactNode;
}) {
  const active = editing?.id === rowId && editing.key === field;
  function commit(nextValue = editing?.value || "") {
    if (!active) return;
    const normalizedValue = fieldLooksDate(field) ? normalizeFlexibleDate(nextValue) : nextValue;
    onStart(null);
    if (normalizedValue !== value) onSave(rowId, field, normalizedValue);
  }
  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") commit((event.currentTarget as HTMLInputElement).value);
    if (event.key === "Escape") onStart(null);
  }
  return (
    <td className="px-4 py-3 align-middle text-center" onDoubleClick={() => onStart({ id: rowId, key: field, value })}>
      {active ? (
        <input
          autoFocus
          disabled={saving}
          className="mx-auto h-8 w-full min-w-24 rounded-md border border-blue-300 bg-white px-2 text-center text-sm outline-none"
          value={editing.value}
          onChange={(event) => onStart({ id: rowId, key: field, value: event.target.value })}
          onBlur={(event) => commit(event.target.value)}
          onKeyDown={onKeyDown}
        />
      ) : (
        <span className="block min-h-5 whitespace-pre-line text-center text-slate-800">{render ? render(value) : value || "-"}</span>
      )}
    </td>
  );
}

function Field({ label, value, onChange, type = "text", placeholder }: { label: string; value: string; onChange: (value: string) => void; type?: string; placeholder?: string }) {
  const isDate = type === "date";
  return (
    <label className="grid gap-1 text-sm font-medium text-slate-600">
      {label}
      <input
        className="h-10 rounded-md border border-border bg-white px-3 text-sm text-slate-900 outline-none focus:border-primary"
        type={isDate ? "text" : type}
        inputMode={isDate ? "numeric" : undefined}
        value={value}
        placeholder={isDate ? "例：2026-05-20 / 2.05 / 2-5 / 260520" : placeholder}
        onChange={(event) => onChange(event.target.value)}
        onBlur={(event) => {
          if (isDate) onChange(normalizeFlexibleDate(event.target.value));
        }}
      />
      {isDate ? <span className="text-[11px] font-normal text-slate-400">可手写：2.05、2-5、2/5、2 05、260520</span> : null}
    </label>
  );
}

function SelectField({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: string[][] }) {
  return (
    <label className="grid gap-1 text-sm font-medium text-slate-600">
      {label}
      <select className="h-10 rounded-md border border-border bg-white px-3 text-sm text-slate-900 outline-none focus:border-primary" value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map(([optionValue, labelText]) => <option key={optionValue} value={optionValue}>{labelText}</option>)}
      </select>
    </label>
  );
}

function cleanPayload<T extends Record<string, unknown>>(payload: T): T {
  return Object.fromEntries(Object.entries(payload).filter(([, value]) => value !== "" && value !== undefined && value !== null)) as T;
}

function normalizeDateFields<T extends Record<string, unknown>>(payload: T): T {
  return Object.fromEntries(
    Object.entries(payload).map(([key, value]) => [
      key,
      fieldLooksDate(key) && typeof value === "string" ? normalizeFlexibleDate(value) : value,
    ]),
  ) as T;
}

function parseInspectionRecords(text: string, vehicle: Partial<Vehicle>): VehicleInspectionRecord[] {
  const rows = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const match = line.match(/(\d{2,4}[-/.\s]?\d{1,2}[-/.\s]?\d{1,2}|\d{1,2}[-/.\s]\d{1,2})\s*(.*)/);
      const date = normalizeFlexibleDate(match?.[1] || line.slice(0, 10));
      const note = match?.[2] || line;
      const inspectionType = /车检|車検|shaken/i.test(note) ? "shaken" : "inspection";
      return { inspection_date: date, inspection_type: inspectionType, note, source: "manual" };
    });
  if (!rows.length && vehicle.last_inspection_date) {
    rows.push({ inspection_date: vehicle.last_inspection_date, inspection_type: "inspection", note: "最近点检", source: "manual" });
  }
  return rows;
}

function displayVehicleValue(row: Vehicle, key: keyof Vehicle) {
  if (key === "snow_tire") return row.snow_tire === "yes" || row.snow_tire === "雪" || row.snow_tire === "雪胎" ? "雪胎" : "普通";
  if (key === "status") return statusLabel(row.status);
  return String(row[key] || "");
}

function normalizeVehiclePatch(field: string, value: string): Partial<Vehicle> {
  if (field === "snow_tire") {
    return { snow_tire: value.includes("雪") || value.toLowerCase() === "yes" ? "yes" : "no" };
  }
  if (field === "status") return { status: value };
  if (fieldLooksDate(field)) return { [field]: normalizeFlexibleDate(value) } as Partial<Vehicle>;
  return { [field]: value } as Partial<Vehicle>;
}

function normalizeDriverPatch(field: string, value: string): Partial<Driver> {
  if (field === "status") return { status: value, driver_status: value };
  if (fieldLooksDate(field)) return { [field]: normalizeFlexibleDate(value) } as Partial<Driver>;
  return { [field]: value } as Partial<Driver>;
}

function statusLabel(status?: string) {
  const found = [...driverStatusOptions, ...vehicleStatusOptions].find(([value]) => value === status);
  return found?.[1] || status || "-";
}

function fieldLooksDate(field: string) {
  return field.includes("date") || field.includes("due");
}

function normalizeFlexibleDate(input?: string) {
  const raw = String(input || "").trim();
  if (!raw) return "";
  const currentYear = new Date().getFullYear();
  const normalized = raw.replace(/[年月]/g, "-").replace(/[日号]/g, "").replace(/[./\s]+/g, "-");
  const parts = normalized.split("-").filter(Boolean);

  if (/^\d{8}$/.test(raw)) {
    return `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`;
  }
  if (/^\d{6}$/.test(raw)) {
    const yy = Number(raw.slice(0, 2));
    return `${2000 + yy}-${raw.slice(2, 4)}-${raw.slice(4, 6)}`;
  }
  if (parts.length === 3) {
    const [yearText, monthText, dayText] = parts;
    const year = yearText.length === 2 ? 2000 + Number(yearText) : Number(yearText);
    return formatDateParts(year, Number(monthText), Number(dayText)) || raw;
  }
  if (parts.length === 2) {
    const [monthText, dayText] = parts;
    return formatDateParts(currentYear, Number(monthText), Number(dayText)) || raw;
  }
  return raw;
}

function formatDateParts(year: number, month: number, day: number) {
  if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) return "";
  if (year < 1900 || month < 1 || month > 12 || day < 1 || day > 31) return "";
  const date = new Date(year, month - 1, day);
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return "";
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function dateWithStatus(value?: string) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const diff = Math.ceil((date.getTime() - Date.now()) / 86400000);
  return (
    <span className="inline-flex flex-col items-center leading-5">
      <span>{value}</span>
      <span className={diff < 0 ? "text-xs font-semibold text-red-600" : diff <= 30 ? "text-xs font-semibold text-amber-600" : "text-xs text-slate-400"}>
        {diff < 0 ? `已过期 ${Math.abs(diff)} 天` : diff <= 30 ? `剩余 ${diff} 天` : ""}
      </span>
    </span>
  );
}

function remainBadge(days: number | null) {
  if (days === null) return "-";
  const expired = days < 0;
  return (
    <span className={expired ? "font-semibold text-red-600" : days <= 30 ? "font-semibold text-amber-600" : "text-slate-700"}>
      {expired ? `已过期 ${Math.abs(days)} 天` : `${days} 天`}
    </span>
  );
}

function healthCheckRemain(row: Driver) {
  if (typeof row.health_check_remaining_days === "number") return row.health_check_remaining_days;
  if (!row.health_check_due_date) return null;
  const date = new Date(row.health_check_due_date);
  if (Number.isNaN(date.getTime())) return null;
  return Math.ceil((date.getTime() - Date.now()) / 86400000);
}

function formatInspectionRecords(records?: VehicleInspectionRecord[]) {
  if (!records?.length) return "-";
  return records
    .slice(0, 3)
    .map((record) => `${record.inspection_date} ${record.inspection_type === "shaken" ? "车检" : "点检"}`)
    .join(" / ");
}
