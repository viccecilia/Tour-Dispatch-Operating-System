import { KeyboardEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CarFront, ChevronDown, ChevronRight, Search, Trash2, UserRound } from "lucide-react";
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

  const deleteDriver = useMutation({
    mutationFn: api.deleteDriver,
    onSuccess: async () => {
      setMessage("司机已从台账中移除。");
      await refreshResources();
    },
    onError: (error: Error) => setMessage(`删除司机失败：${error.message}`),
  });

  const createVehicle = useMutation({
    mutationFn: api.createVehicle,
    onSuccess: async () => {
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

  const deleteVehicle = useMutation({
    mutationFn: api.deleteVehicle,
    onSuccess: async () => {
      setMessage("车辆已从台账中移除。");
      await refreshResources();
    },
    onError: (error: Error) => setMessage(`删除车辆失败：${error.message}`),
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
              <VehicleTable
                rows={filteredVehicles}
                loading={vehicles.isLoading}
                saving={createVehicle.isPending || updateVehicle.isPending || deleteVehicle.isPending}
                onCreate={(payload) => createVehicle.mutate(payload)}
                onSave={(id, payload) => updateVehicle.mutate({ id, payload })}
                onDelete={(id) => {
                  if (window.confirm("确认删除这台车辆？历史派车记录会保留。")) deleteVehicle.mutate(id);
                }}
              />
              <VehicleMaintenanceTable rows={filteredVehicles} loading={vehicles.isLoading} saving={updateVehicle.isPending} onSave={(id, payload) => updateVehicle.mutate({ id, payload })} />
            </div>
          ) : (
            <div className="space-y-4">
              <DriverTable
                rows={filteredDrivers}
                loading={drivers.isLoading}
                saving={createDriver.isPending || updateDriver.isPending || deleteDriver.isPending}
                onCreate={(payload) => createDriver.mutate(payload)}
                onSave={(id, payload) => updateDriver.mutate({ id, payload })}
                onDelete={(id) => {
                  if (window.confirm("确认删除这名司机？历史派车和报备记录会保留。")) deleteDriver.mutate(id);
                }}
              />
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

function VehicleTable({
  rows,
  loading,
  saving,
  onCreate,
  onSave,
  onDelete,
}: {
  rows: Vehicle[];
  loading: boolean;
  saving: boolean;
  onCreate: (payload: Partial<Vehicle>) => void;
  onSave: (id: number, payload: Partial<Vehicle>) => void;
  onDelete: (id: number) => void;
}) {
  const [editing, setEditing] = useState<EditingCell>(null);
  const [draft, setDraft] = useState<Partial<Vehicle>>(vehicleInitial);
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
  function saveDraft() {
    if (!draft.plate_number?.trim()) return;
    onCreate(cleanPayload({ ...normalizeDateFields(draft), status: draft.status || "available" }));
    setDraft(vehicleInitial);
  }
  return (
    <section className="rounded-xl border border-border bg-white">
      <div className="border-b border-border px-4 py-3">
        <h3 className="text-base font-bold text-slate-950">车辆基础信息</h3>
        <p className="text-xs text-slate-500">第一行快速新增；已有单元格双击修改，回车或点击空白处保存。</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[980px] text-center text-sm">
          <thead className="bg-slate-50 text-xs font-bold text-slate-500">
            <tr>
              <th className="px-4 py-3 text-center">序号</th>
              {cols.map((col) => <th key={col.key} className="px-4 py-3 text-center">{col.label}</th>)}
              <th className="px-4 py-3 text-center">删除</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            <VehicleQuickCreateRow draft={draft} saving={saving} onChange={setDraft} onSave={saveDraft} />
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
                <td className="px-4 py-3 align-middle">
                  <button
                    type="button"
                    disabled={saving}
                    className="mx-auto inline-flex h-8 w-8 items-center justify-center rounded-full text-slate-400 transition hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                    title="删除车辆"
                    onClick={() => onDelete(row.id)}
                  >
                    <Trash2 size={15} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length ? <div className="border-t border-border py-8"><EmptyState title="暂无车辆" detail="在表格第一行录入车牌后按回车新增。" /></div> : null}
      </div>
    </section>
  );
}

function VehicleQuickCreateRow({
  draft,
  saving,
  onChange,
  onSave,
}: {
  draft: Partial<Vehicle>;
  saving: boolean;
  onChange: (payload: Partial<Vehicle>) => void;
  onSave: () => void;
}) {
  function keySave(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") onSave();
  }
  return (
    <tr className="bg-emerald-50/50">
      <td className="px-4 py-3 text-xs font-bold text-emerald-700">新增</td>
      <td className="px-2 py-2"><QuickInput value={draft.vehicle_type || ""} placeholder="ハイエース" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, vehicle_type: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.plate_number || ""} placeholder="なにわ300あ1001" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, plate_number: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.plate_short_code || ""} placeholder="1001" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, plate_short_code: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.vehicle_type_code || ""} placeholder="H/A" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, vehicle_type_code: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.vehicle_color || ""} placeholder="白/黑" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, vehicle_color: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.snow_tire || ""} placeholder="普通/雪胎" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, snow_tire: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={statusLabel(draft.status)} placeholder="正常" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, status: parseStatus(value, "vehicle") })} /></td>
      <td className="px-4 py-3">
        <button type="button" disabled={saving || !draft.plate_number?.trim()} onClick={onSave} className="inline-flex h-8 items-center rounded-full bg-emerald-600 px-3 text-xs font-bold text-white disabled:opacity-40">
          新增
        </button>
      </td>
    </tr>
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

function DriverTable({
  rows,
  loading,
  saving,
  onCreate,
  onSave,
  onDelete,
}: {
  rows: Driver[];
  loading: boolean;
  saving: boolean;
  onCreate: (payload: Partial<Driver>) => void;
  onSave: (id: number, payload: Partial<Driver>) => void;
  onDelete: (id: number) => void;
}) {
  const [editing, setEditing] = useState<EditingCell>(null);
  const [draft, setDraft] = useState<Partial<Driver>>(driverInitial);
  const cols: Array<{ key: keyof Driver; label: string }> = [
    { key: "driver_external_id", label: "運転手ID" },
    { key: "office", label: "所属営業所" },
    { key: "name", label: "運転手名" },
    { key: "driver_code", label: "司机代码" },
    { key: "driver_language", label: "语言" },
    { key: "phone", label: "电话" },
    { key: "license_due_date", label: "免许有效期限" },
    { key: "license_number", label: "免許番号" },
    { key: "residence_status", label: "在留资格" },
    { key: "residence_due_date", label: "再留期限有效日期" },
    { key: "health_check_due_date", label: "健康诊断日期" },
    { key: "wechat", label: "wechat" },
    { key: "line", label: "line" },
    { key: "whatsapp", label: "WhatsApp" },
    { key: "email", label: "mail" },
    { key: "status", label: "状态" },
  ];
  if (loading) return <EmptyState title="正在加载司机" detail="正在读取司机台账。" />;
  function saveDraft() {
    if (!draft.name?.trim()) return;
    onCreate(cleanPayload({ ...normalizeDateFields(draft), status: draft.status || "available", driver_status: draft.status || draft.driver_status || "available" }));
    setDraft(driverInitial);
  }
  return (
    <section className="rounded-xl border border-border bg-white">
      <div className="border-b border-border px-4 py-3">
        <h3 className="text-base font-bold text-slate-950">司机明细</h3>
        <p className="text-xs text-slate-500">第一行快速新增；已有单元格双击修改，回车或点击空白处保存。</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1680px] text-center text-sm">
          <thead className="bg-slate-50 text-xs font-bold text-slate-500">
            <tr>
              <th className="px-4 py-3 text-center">序号</th>
              {cols.map((col) => <th key={col.key} className="px-4 py-3 text-center">{col.label}</th>)}
              <th className="px-4 py-3 text-center">删除</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            <DriverQuickCreateRow draft={draft} saving={saving} onChange={setDraft} onSave={saveDraft} />
            {rows.map((row, index) => (
              <tr key={row.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 align-middle text-slate-500">{index + 1}</td>
                {cols.map((col) => (
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
                ))}
                <td className="px-4 py-3 align-middle">
                  <button
                    type="button"
                    disabled={saving}
                    className="mx-auto inline-flex h-8 w-8 items-center justify-center rounded-full text-slate-400 transition hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                    title="删除司机"
                    onClick={() => onDelete(row.id)}
                  >
                    <Trash2 size={15} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length ? <div className="border-t border-border py-8"><EmptyState title="暂无司机" detail="在表格第一行录入姓名后按回车新增。" /></div> : null}
      </div>
    </section>
  );
}

function DriverQuickCreateRow({
  draft,
  saving,
  onChange,
  onSave,
}: {
  draft: Partial<Driver>;
  saving: boolean;
  onChange: (payload: Partial<Driver>) => void;
  onSave: () => void;
}) {
  function keySave(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") onSave();
  }
  return (
    <tr className="bg-emerald-50/50">
      <td className="px-4 py-3 text-xs font-bold text-emerald-700">新增</td>
      <td className="px-2 py-2"><QuickInput value={draft.driver_external_id || ""} placeholder="ID" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, driver_external_id: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.office || ""} placeholder="本社" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, office: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.name || ""} placeholder="司机姓名" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, name: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.driver_code || ""} placeholder="代码" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, driver_code: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.driver_language || ""} placeholder="中文/日文" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, driver_language: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.phone || ""} placeholder="电话" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, phone: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.license_due_date || ""} placeholder="驾照到期" onBlurDate={(value) => onChange({ ...draft, license_due_date: value })} onKeyDown={keySave} onChange={(value) => onChange({ ...draft, license_due_date: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.license_number || ""} placeholder="驾照号" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, license_number: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.residence_status || ""} placeholder="在留" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, residence_status: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.residence_due_date || ""} placeholder="在留到期" onBlurDate={(value) => onChange({ ...draft, residence_due_date: value })} onKeyDown={keySave} onChange={(value) => onChange({ ...draft, residence_due_date: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.health_check_due_date || ""} placeholder="体检日期" onBlurDate={(value) => onChange({ ...draft, health_check_due_date: value })} onKeyDown={keySave} onChange={(value) => onChange({ ...draft, health_check_due_date: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.wechat || ""} placeholder="wechat" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, wechat: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.line || ""} placeholder="line" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, line: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.whatsapp || ""} placeholder="WhatsApp" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, whatsapp: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.email || ""} placeholder="mail" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, email: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={statusLabel(draft.status)} placeholder="正常" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, status: parseStatus(value, "driver"), driver_status: parseStatus(value, "driver") })} /></td>
      <td className="px-4 py-3">
        <button type="button" disabled={saving || !draft.name?.trim()} onClick={onSave} className="inline-flex h-8 items-center rounded-full bg-emerald-600 px-3 text-xs font-bold text-white disabled:opacity-40">
          新增
        </button>
      </td>
    </tr>
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

function QuickInput({
  value,
  placeholder,
  onChange,
  onKeyDown,
  onBlurDate,
}: {
  value: string;
  placeholder?: string;
  onChange: (value: string) => void;
  onKeyDown?: (event: KeyboardEvent<HTMLInputElement>) => void;
  onBlurDate?: (value: string) => void;
}) {
  return (
    <input
      className="h-8 w-full min-w-24 rounded-md border border-emerald-100 bg-white px-2 text-center text-xs font-semibold text-slate-900 outline-none transition focus:border-emerald-400"
      value={value}
      placeholder={placeholder}
      onChange={(event) => onChange(event.target.value)}
      onBlur={(event) => onBlurDate?.(normalizeFlexibleDate(event.target.value))}
      onKeyDown={onKeyDown}
    />
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

function parseStatus(value: string, kind: "driver" | "vehicle") {
  const raw = value.trim().toLowerCase();
  const options = kind === "driver" ? driverStatusOptions : vehicleStatusOptions;
  const direct = options.find(([status, label]) => status.toLowerCase() === raw || label === value.trim());
  if (direct) return direct[0];
  if (raw.includes("休")) return "inactive";
  if (raw.includes("运行") || raw.includes("busy")) return "busy";
  if (raw.includes("修")) return kind === "vehicle" ? "maintenance" : "inactive";
  return "available";
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

function formatInspectionRecords(records?: VehicleInspectionRecord[]) {
  if (!records?.length) return "-";
  return records
    .slice(0, 3)
    .map((record) => `${record.inspection_date} ${record.inspection_type === "shaken" ? "车检" : "点检"}`)
    .join(" / ");
}
