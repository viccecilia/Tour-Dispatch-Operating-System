import { KeyboardEvent, ReactNode, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CarFront, ChevronDown, ChevronRight, Download, FolderDown, Plus, RefreshCw, Search, Trash2, UserRound } from "lucide-react";
import { CompanyScopeFilter, isAllCompanyScope } from "@/components/CompanyScopeFilter";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api, downloadApiFile } from "@/services/apiClient";
import type { Driver, ResourceAlert, ResourceLibraryFile, ResourceLibraryResponse, ResourceLibraryVehicle, Vehicle, VehicleInspectionRecord } from "@/types/api";

type ResourceTab = "vehicles" | "drivers" | "maintenance";
type EditingCell = { id: number; key: string; value: string } | null;
type LifecycleFilter = "active" | "archived" | "all";
type HealthFilter = "all" | "expired" | "attention" | "30" | "90" | "normal" | "unknown";
type HealthBucket = Exclude<HealthFilter, "all" | "attention">;
type DriverQuickFilter = "active" | "archived" | "available" | "expired" | "attention" | "duplicate" | null;
type ResourceLibraryQuickFilter = "vehicles" | "pdf" | "categories" | "drivers";
type ResourceStat<T extends string = string> = { value: number; label: string; tone: string; filterKey?: T };
type ResourceUploadPayload = {
  vehicle_key: string;
  category: string;
  document_date?: string;
  custom_title?: string;
  file_name: string;
  content_type?: string;
  file_base64: string;
};

const driverInitial: Partial<Driver> = {
  driver_external_id: "",
  office: "",
  name: "",
  driver_code: "",
  driver_language: "中文",
  note: "",
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
  ["maintenance", "维修"],
  ["retired", "减车"],
];

export function VehiclesPage() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<ResourceTab>("vehicles");
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState("");
  const [tenantScope, setTenantScope] = useState("all");
  const [lifecycleFilter, setLifecycleFilter] = useState<LifecycleFilter>("active");
  const [officeFilter, setOfficeFilter] = useState("all");
  const [healthFilter, setHealthFilter] = useState<HealthFilter>("all");
  const [vehicleStatusFilter, setVehicleStatusFilter] = useState("all");
  const [driverQuickFilter, setDriverQuickFilter] = useState<DriverQuickFilter>("active");

  const drivers = useQuery({ queryKey: ["resource-drivers", tenantScope], queryFn: () => api.resourceDrivers({ tenant_id: tenantScope }) });
  const retiredDrivers = useQuery({
    queryKey: ["resource-drivers", tenantScope, "retired"],
    queryFn: () => api.resourceDrivers({ tenant_id: tenantScope, status: "retired" }),
  });
  const vehicles = useQuery({ queryKey: ["resource-vehicles", tenantScope], queryFn: () => api.resourceVehicles({ tenant_id: tenantScope }) });
  const retiredVehicles = useQuery({
    queryKey: ["resource-vehicles", tenantScope, "retired"],
    queryFn: () => api.resourceVehicles({ tenant_id: tenantScope, status: "retired" }),
  });
  const reminders = useQuery({ queryKey: ["resource-reminders"], queryFn: api.resourceReminders });
  const resourceLibrary = useQuery({ queryKey: ["dispatch-resource-library"], queryFn: api.resourceLibrary });

  async function refreshResources() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["resource-drivers"] }),
      queryClient.invalidateQueries({ queryKey: ["resource-vehicles"] }),
      queryClient.invalidateQueries({ queryKey: ["resource-reminders"] }),
      queryClient.invalidateQueries({ queryKey: ["dispatch-resource-library"] }),
      queryClient.invalidateQueries({ queryKey: ["notification-summary"] }),
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] }),
      queryClient.invalidateQueries({ queryKey: ["drivers"] }),
      queryClient.invalidateQueries({ queryKey: ["vehicles"] }),
    ]);
  }

  function withTenantScope<T extends { tenant_id?: number }>(payload: T): T {
    return isAllCompanyScope(tenantScope) ? payload : { ...payload, tenant_id: Number(tenantScope) };
  }

  function requireTenantForCreate() {
    if (isAllCompanyScope(tenantScope)) {
      setMessage("总后台新增车辆或司机时，请先选择一个具体公司。");
      return false;
    }
    return true;
  }

  const createDriver = useMutation({
    mutationFn: (payload: Partial<Driver>) => api.createDriver(withTenantScope(payload)),
    onSuccess: async () => {
      setMessage("司机已新增。");
      await refreshResources();
    },
    onError: (error: Error) => setMessage(`新增司机失败：${error.message}`),
  });

  const updateDriver = useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: Partial<Driver> }) => {
      if (payload.health_check_due_date) {
        const driver = [...(drivers.data || []), ...(retiredDrivers.data || [])].find((item) => item.id === id);
        const driverKey = driver?.driver_external_id || driver?.driver_code || driver?.name;
        if (!driverKey) throw new Error("缺少司机编号或姓名，无法同步健康诊断日期");
        await api.updateDriverResourceHealth(driverKey, payload.health_check_due_date);
      }
      return api.updateDriver(id, payload);
    },
    onSuccess: async () => {
      setMessage("司机信息已保存。");
      await refreshResources();
    },
    onError: (error: Error) => setMessage(`保存司机失败：${error.message}`),
  });

  const changeDriverEmployment = useMutation({
    mutationFn: async ({
      id,
      driverKey,
      tenantId,
      retired,
    }: {
      id: number;
      driverKey: string;
      tenantId?: number;
      retired: boolean;
    }) => {
      const status = retired ? "retired" : "available";
      await api.updateDriverResourceStatus(driverKey, retired ? "离职" : "運転可");
      await api.updateDriver(id, { tenant_id: tenantId, status, driver_status: status });
    },
    onSuccess: async (_, variables) => {
      setMessage(variables.retired ? "司机已归档到离职人员。" : "司机已恢复为在职人员。");
      await refreshResources();
    },
    onError: (error: Error) => setMessage(`更新司机在职状态失败：${error.message}`),
  });

  const deleteDriver = useMutation({
    mutationFn: ({ id, tenantId }: { id: number; tenantId?: number }) => api.deleteDriver(id, tenantId),
    onSuccess: async () => {
      setMessage("司机已从台账中移除。");
      await refreshResources();
    },
    onError: (error: Error) => setMessage(`删除司机失败：${error.message}`),
  });

  const createVehicle = useMutation({
    mutationFn: (payload: Partial<Vehicle>) => api.createVehicle(withTenantScope(payload)),
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
    mutationFn: ({ id, tenantId }: { id: number; tenantId?: number }) => api.deleteVehicle(id, tenantId),
    onSuccess: async () => {
      setMessage("车辆已从台账中移除。");
      await refreshResources();
    },
    onError: (error: Error) => setMessage(`删除车辆失败：${error.message}`),
  });

  const uploadResourceDocument = useMutation({
    mutationFn: (payload: ResourceUploadPayload) => api.uploadResourceDocument(payload),
    onSuccess: async () => {
      setMessage("车辆 PDF 已上传入库。");
      await refreshResources();
    },
    onError: (error: Error) => setMessage(`上传车辆资料失败：${error.message}`),
  });

  const createVehicleInspectionRecord = useMutation({
    mutationFn: ({ vehicleId, payload }: { vehicleId: number; payload: Partial<VehicleInspectionRecord> }) => api.createVehicleInspectionRecord(vehicleId, payload),
    onSuccess: async () => {
      setMessage("维护记录已添加。");
      await refreshResources();
    },
    onError: (error: Error) => setMessage(`添加维护记录失败：${error.message}`),
  });

  const updateVehicleInspectionRecord = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<VehicleInspectionRecord> }) => api.updateVehicleInspectionRecord(id, payload),
    onSuccess: async () => {
      setMessage("维护记录已更新。");
      await refreshResources();
    },
    onError: (error: Error) => setMessage(`更新维护记录失败：${error.message}`),
  });

  const deleteVehicleInspectionRecord = useMutation({
    mutationFn: api.deleteVehicleInspectionRecord,
    onSuccess: async () => {
      setMessage("维护记录已删除。");
      await refreshResources();
    },
    onError: (error: Error) => setMessage(`删除维护记录失败：${error.message}`),
  });

  const libraryDriverByName = useMemo(() => {
    const entries = (resourceLibrary.data?.drivers || [])
      .map((item) => [libraryDriverName(item), item] as const)
      .filter(([name]) => Boolean(name));
    return new Map(entries);
  }, [resourceLibrary.data?.drivers]);

  const onlineRetiredDriverNames = useMemo(
    () =>
      new Set(
        (resourceLibrary.data?.drivers || [])
          .filter(isLibraryDriverRetired)
          .map(libraryDriverName)
          .filter(Boolean),
      ),
    [resourceLibrary.data?.drivers],
  );

  const activeDrivers = useMemo(
    () =>
      (drivers.data || [])
        .filter((item) => !onlineRetiredDriverNames.has(item.name))
        .map((item) => mergeDriverFromLibrary(item, libraryDriverByName.get(item.name))),
    [drivers.data, libraryDriverByName, onlineRetiredDriverNames],
  );

  const archivedDrivers = useMemo(() => {
    const reconciled = new Map<number, Driver>();
    [...(retiredDrivers.data || []), ...(drivers.data || []).filter((item) => onlineRetiredDriverNames.has(item.name))].forEach((item) => {
      reconciled.set(item.id, mergeDriverFromLibrary(item, libraryDriverByName.get(item.name)));
    });
    return Array.from(reconciled.values());
  }, [drivers.data, libraryDriverByName, onlineRetiredDriverNames, retiredDrivers.data]);

  const driverPool = useMemo(() => {
    if (lifecycleFilter === "archived") return archivedDrivers;
    if (lifecycleFilter === "all") return [...activeDrivers, ...archivedDrivers];
    return activeDrivers;
  }, [activeDrivers, archivedDrivers, lifecycleFilter]);

  const vehiclePool = useMemo(() => {
    if (lifecycleFilter === "archived") return retiredVehicles.data || [];
    if (lifecycleFilter === "all") return [...(vehicles.data || []), ...(retiredVehicles.data || [])];
    return vehicles.data || [];
  }, [lifecycleFilter, retiredVehicles.data, vehicles.data]);

  const officeOptions = useMemo(
    () =>
      Array.from(
        new Set(
          [...activeDrivers, ...archivedDrivers]
            .map((item) => item.office)
            .filter((office): office is string => Boolean(office)),
        ),
      ).sort(),
    [activeDrivers, archivedDrivers],
  );

  const duplicateDriverIds = useMemo(() => {
    const libraryRows = resourceLibrary.data?.drivers || [];
    const ids = (libraryRows.length
      ? libraryRows.filter((item) => !isLibraryDriverRetired(item)).map((item) => libraryDriverValue(item, "運転手ID"))
      : (drivers.data || []).map((item) => item.driver_external_id))
      .map((value) => String(value || "").trim())
      .filter(Boolean);
    const counts = new Map<string, number>();
    ids.forEach((id) => counts.set(id, (counts.get(id) || 0) + 1));
    return new Set(Array.from(counts.entries()).filter(([, count]) => count > 1).map(([id]) => id));
  }, [drivers.data, resourceLibrary.data?.drivers]);

  const filteredDrivers = useMemo(() => {
    const term = query.trim().toLowerCase();
    return driverPool.filter((item) => {
      const matchesQuery = [
          item.driver_external_id,
          item.tenant_name,
          item.tenant_slug,
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
          .includes(term);
      const matchesOffice = officeFilter === "all" || item.office === officeFilter;
      const healthBucket = driverHealthBucket(item);
      const matchesHealth =
        healthFilter === "all" ||
        (healthFilter === "attention" ? ["30", "90"].includes(healthBucket) : healthBucket === healthFilter);
      const matchesAvailable =
        driverQuickFilter !== "available" || isDriverOperational(item, libraryDriverByName.get(item.name));
      const matchesDuplicate =
        driverQuickFilter !== "duplicate" || duplicateDriverIds.has(String(item.driver_external_id || "").trim());
      return matchesQuery && matchesOffice && matchesHealth && matchesAvailable && matchesDuplicate;
    });
  }, [driverPool, driverQuickFilter, duplicateDriverIds, healthFilter, libraryDriverByName, officeFilter, query]);

  const filteredVehicles = useMemo(() => {
    const term = query.trim().toLowerCase();
    return vehiclePool.filter((item) => {
      const matchesQuery = [
          item.plate_number,
          item.tenant_name,
          item.tenant_slug,
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
          .includes(term);
      return matchesQuery && (vehicleStatusFilter === "all" || item.status === vehicleStatusFilter);
    });
  }, [query, vehiclePool, vehicleStatusFilter]);

  const driverStats = useMemo(() => {
    const libraryRows = resourceLibrary.data?.drivers || [];
    const activeLibraryRows = libraryRows.filter((item) => !isLibraryDriverRetired(item));
    return [
      { value: activeDrivers.length, label: "在职记录", tone: "blue", filterKey: "active" },
      {
        value: archivedDrivers.length,
        label: "离职人员",
        tone: "slate",
        filterKey: "archived",
      },
      {
        value: activeDrivers
          .filter((item) => isDriverOperational(item, libraryDriverByName.get(item.name))).length,
        label: "運転可",
        tone: "emerald",
        filterKey: "available",
      },
      {
        value: libraryRows.length
          ? activeLibraryRows.filter((item) => libraryDriverHealthBucket(item) === "expired").length
          : (drivers.data || []).filter((item) => driverHealthBucket(item) === "expired").length,
        label: "健康诊断过期",
        tone: "red",
        filterKey: "expired",
      },
      {
        value: libraryRows.length
          ? activeLibraryRows.filter((item) => ["30", "90"].includes(libraryDriverHealthBucket(item))).length
          : (drivers.data || []).filter((item) => ["30", "90"].includes(driverHealthBucket(item))).length,
        label: "90天内需关注",
        tone: "amber",
        filterKey: "attention",
      },
      {
        value: duplicateDriverIds.size,
        label: "重复運転手ID",
        tone: duplicateDriverIds.size ? "red" : "slate",
        filterKey: "duplicate",
      },
    ] satisfies ResourceStat<Exclude<DriverQuickFilter, null>>[];
  }, [activeDrivers, archivedDrivers.length, drivers.data, duplicateDriverIds, libraryDriverByName, resourceLibrary.data?.drivers]);

  const vehicleStats = useMemo(() => {
    const active = vehicles.data || [];
    const vehicleAlerts = (reminders.data?.alerts || []).filter((item) => item.type === "vehicle");
    return [
      { value: active.length, label: "在用车辆", tone: "blue" },
      { value: retiredVehicles.data?.length || 0, label: "退役车辆", tone: "slate" },
      { value: active.filter((item) => item.status === "available").length, label: "可派车辆", tone: "emerald" },
      { value: active.filter((item) => item.status === "maintenance").length, label: "维修车辆", tone: "amber" },
      { value: vehicleAlerts.filter((item) => item.status === "expired" || item.status === "invalid").length, label: "资料已过期", tone: "red" },
      { value: vehicleAlerts.filter((item) => item.status === "upcoming").length, label: "即将到期", tone: "amber" },
    ];
  }, [reminders.data?.alerts, retiredVehicles.data, vehicles.data]);

  const vehicleTenantId = (id: number) => vehicles.data?.find((item) => item.id === id)?.tenant_id;
  const driverTenantId = (id: number) => drivers.data?.find((item) => item.id === id)?.tenant_id;

  const pageSaving =
    createVehicle.isPending ||
    updateVehicle.isPending ||
    uploadResourceDocument.isPending ||
    deleteVehicle.isPending ||
    createDriver.isPending ||
    updateDriver.isPending ||
    changeDriverEmployment.isPending ||
    deleteDriver.isPending;

  function switchTab(nextTab: ResourceTab) {
    setTab(nextTab);
    setQuery("");
    setLifecycleFilter("active");
    setOfficeFilter("all");
    setHealthFilter("all");
    setVehicleStatusFilter("all");
    setDriverQuickFilter(nextTab === "drivers" ? "active" : null);
  }

  function applyDriverQuickFilter(filter: Exclude<DriverQuickFilter, null>) {
    const nextFilter = driverQuickFilter === filter ? null : filter;
    setDriverQuickFilter(nextFilter);
    setQuery("");
    setOfficeFilter("all");
    setVehicleStatusFilter("all");
    if (!nextFilter) {
      setLifecycleFilter("all");
      setHealthFilter("all");
      return;
    }
    setLifecycleFilter(nextFilter === "archived" ? "archived" : "active");
    setHealthFilter(
      nextFilter === "expired"
        ? "expired"
        : nextFilter === "attention"
          ? "attention"
          : "all",
    );
  }

  function focusQuickCreate() {
    const input = document.querySelector<HTMLInputElement>(`[data-quick-create="${tab}"] input`);
    input?.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
    window.setTimeout(() => input?.focus(), 250);
  }

  return (
    <div className="space-y-5">
      <Card className="overflow-hidden">
        <CardHeader className="border-b border-border bg-white">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-bold tracking-[0.18em] text-blue-600">资源管理</p>
              <h2 className="mt-1 text-xl font-bold text-slate-950">
                {tab === "drivers" ? "司机信息表" : tab === "maintenance" ? "车辆维护台账" : "车辆资料检索"}
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                {tab === "vehicles" ? "按车辆和资料类别检索已入库 PDF，点击资料卡即可下载。" : "在线维护现有数据库资料；双击单元格后，回车或点击空白处即保存。"}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" variant={tab === "vehicles" ? "primary" : "secondary"} onClick={() => switchTab("vehicles")}>
                <FolderDown size={16} />
                车辆资料
              </Button>
              <Button type="button" variant={tab === "drivers" ? "primary" : "secondary"} onClick={() => switchTab("drivers")}>
                <UserRound size={16} />
                司机台账
              </Button>
              <Button type="button" variant={tab === "maintenance" ? "primary" : "secondary"} onClick={() => switchTab("maintenance")}>
                <CarFront size={16} />
                维护台账
              </Button>
              <CompanyScopeFilter value={tenantScope} onChange={setTenantScope} />
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4 bg-slate-50/50 py-5">
          {tab === "vehicles" ? (
            <ResourceDownloadView
              data={resourceLibrary.data}
              loading={resourceLibrary.isLoading}
              uploading={uploadResourceDocument.isPending}
              onUpload={(payload) => uploadResourceDocument.mutateAsync(payload)}
              onShowDrivers={() => switchTab("drivers")}
            />
          ) : (
            <>
          <ResourceStatGrid
            stats={tab === "drivers" ? driverStats : vehicleStats}
            loading={tab === "drivers" ? drivers.isLoading || resourceLibrary.isLoading : vehicles.isLoading}
            activeKey={tab === "drivers" ? driverQuickFilter : null}
            onSelect={tab === "drivers" ? applyDriverQuickFilter : undefined}
          />

          <div className="rounded-xl border border-border bg-white p-3 shadow-sm">
            <div className="flex flex-wrap items-center gap-2">
              <label className="flex h-9 min-w-[260px] flex-1 items-center gap-2 rounded-md border border-border bg-white px-3 text-sm xl:max-w-[420px]">
                <Search size={15} className="text-slate-400" />
                <input
                  className="w-full bg-transparent outline-none"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder={tab === "drivers" ? "搜索 ID / 姓名 / 电话 / 备注" : "搜索车牌 / 车型 / 车辆简码 / 状态"}
                />
              </label>

              {tab === "drivers" ? (
                <>
                  <CompactSelect value={officeFilter} onChange={setOfficeFilter}>
                    <option value="all">全部营业所</option>
                    {officeOptions.map((office) => <option key={office} value={office}>{office}</option>)}
                  </CompactSelect>
                  <CompactSelect
                    value={lifecycleFilter}
                    onChange={(value) => {
                      setLifecycleFilter(value as LifecycleFilter);
                      setDriverQuickFilter(null);
                    }}
                  >
                    <option value="active">在职人员</option>
                    <option value="archived">离职人员</option>
                    <option value="all">全部人员</option>
                  </CompactSelect>
                  <CompactSelect
                    value={healthFilter}
                    onChange={(value) => {
                      setHealthFilter(value as HealthFilter);
                      setDriverQuickFilter(null);
                    }}
                  >
                    <option value="all">全部健康诊断状态</option>
                    <option value="expired">过期</option>
                    <option value="attention">90天内需关注</option>
                    <option value="30">30天内</option>
                    <option value="90">31-90天</option>
                    <option value="normal">正常</option>
                    <option value="unknown">无法计算</option>
                  </CompactSelect>
                </>
              ) : (
                <>
                  <CompactSelect value={lifecycleFilter} onChange={(value) => setLifecycleFilter(value as LifecycleFilter)}>
                    <option value="active">在用车辆</option>
                    <option value="archived">退役车辆</option>
                    <option value="all">全部车辆</option>
                  </CompactSelect>
                  <CompactSelect value={vehicleStatusFilter} onChange={setVehicleStatusFilter}>
                    <option value="all">全部车辆状态</option>
                    <option value="available">正常</option>
                    <option value="maintenance">维修</option>
                    <option value="retired">退役</option>
                  </CompactSelect>
                </>
              )}

              <button
                type="button"
                onClick={focusQuickCreate}
                className="inline-flex h-9 items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 text-sm font-bold text-slate-700 transition hover:border-blue-300 hover:text-blue-700"
              >
                <Plus size={15} />
                新增一行
              </button>
              <button
                type="button"
                disabled={pageSaving}
                onClick={() => {
                  void refreshResources().then(() => setMessage("修改已自动保存，当前资料已刷新。"));
                }}
                className="inline-flex h-9 items-center gap-1.5 rounded-md bg-blue-600 px-3 text-sm font-bold text-white transition hover:bg-blue-700 disabled:opacity-50"
              >
                <RefreshCw size={15} className={pageSaving ? "animate-spin" : ""} />
                保存并刷新
              </button>
            </div>
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
              <span>已有单元格双击编辑；删除操作为软归档，历史订单和派车记录不会被删除。</span>
              <span>当前显示 {tab === "drivers" ? filteredDrivers.length : filteredVehicles.length} 条</span>
            </div>
          </div>

          {message ? <div className="rounded-md border border-blue-100 bg-blue-50 px-3 py-2 text-sm text-blue-700">{message}</div> : null}
          <ResourceReminderStrip alerts={reminders.data?.alerts || []} loading={reminders.isLoading} />

          {tab === "maintenance" ? (
            <div className="space-y-4">
              <VehicleTable
                rows={filteredVehicles}
                loading={vehicles.isLoading}
                saving={createVehicle.isPending || updateVehicle.isPending || deleteVehicle.isPending}
                onCreate={(payload) => {
                  if (requireTenantForCreate()) createVehicle.mutate(payload);
                }}
                onSave={(id, payload) => updateVehicle.mutate({ id, payload: { ...payload, tenant_id: vehicleTenantId(id) } })}
                onDelete={(id) => {
                  if (window.confirm("确认删除这台车辆？历史派车记录会保留。")) deleteVehicle.mutate({ id, tenantId: vehicleTenantId(id) });
                }}
              />
              <VehicleMaintenanceTable
                rows={filteredVehicles}
                loading={vehicles.isLoading}
                saving={updateVehicle.isPending || createVehicleInspectionRecord.isPending || updateVehicleInspectionRecord.isPending || deleteVehicleInspectionRecord.isPending}
                onSave={(id, payload) => updateVehicle.mutate({ id, payload: { ...payload, tenant_id: vehicleTenantId(id) } })}
                onCreateRecord={(vehicleId, payload) => createVehicleInspectionRecord.mutate({ vehicleId, payload })}
                onUpdateRecord={(id, payload) => updateVehicleInspectionRecord.mutate({ id, payload })}
                onDeleteRecord={(id) => deleteVehicleInspectionRecord.mutate(id)}
              />
            </div>
          ) : (
            <div className="space-y-4">
              <DriverTable
                rows={filteredDrivers}
                libraryRowsByName={libraryDriverByName}
                loading={drivers.isLoading}
                saving={createDriver.isPending || updateDriver.isPending || changeDriverEmployment.isPending || deleteDriver.isPending}
                onCreate={(payload) => {
                  if (requireTenantForCreate()) createDriver.mutate(payload);
                }}
                onSave={(id, payload) => updateDriver.mutate({ id, payload: { ...payload, tenant_id: driverTenantId(id) } })}
                onEmploymentChange={(row, retired) => {
                  const driverKey = row.driver_external_id || row.driver_code || row.name;
                  const action = retired ? "离职归档" : "恢复在职";
                  if (window.confirm(`确认将 ${row.name} ${action}？`)) {
                    changeDriverEmployment.mutate({
                      id: row.id,
                      driverKey,
                      tenantId: driverTenantId(row.id),
                      retired,
                    });
                  }
                }}
                onDelete={(id) => {
                  if (window.confirm("确认从当前资料台账移除这名司机？历史派车和报备记录会保留。")) deleteDriver.mutate({ id, tenantId: driverTenantId(id) });
                }}
              />
              </div>
          )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function ResourceDownloadView({
  data,
  loading,
  uploading,
  onUpload,
  onShowDrivers,
}: {
  data?: ResourceLibraryResponse;
  loading: boolean;
  uploading: boolean;
  onUpload: (payload: ResourceUploadPayload) => Promise<unknown>;
  onShowDrivers: () => void;
}) {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [sort, setSort] = useState<"plate" | "files">("plate");
  const [selectedId, setSelectedId] = useState("");
  const [downloadError, setDownloadError] = useState("");
  const [uploadVehicleKey, setUploadVehicleKey] = useState("");
  const [uploadCategory, setUploadCategory] = useState("");
  const [uploadDate, setUploadDate] = useState("");
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadMessage, setUploadMessage] = useState("");
  const [quickFilter, setQuickFilter] = useState<Exclude<ResourceLibraryQuickFilter, "drivers">>("vehicles");
  const [categoryPanelOpen, setCategoryPanelOpen] = useState(false);
  const vehicles = useMemo(() => data?.vehicles || [], [data?.vehicles]);
  const categories = useMemo(
    () =>
      Array.from(
        new Set(
          vehicles
            .flatMap((vehicle) => vehicle.docs?.map((file) => file.category) || [])
            .filter((value): value is string => Boolean(value)),
        ),
      ).sort(),
    [vehicles],
  );
  const filteredVehicles = useMemo(() => {
    const term = search.trim().toLowerCase();
    const rows = vehicles.filter((vehicle) => {
      const vehicleText = [vehicle.plate_number, vehicle.suffix, vehicle.chassis_number, vehicle.model_code, vehicle.vehicle_type]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      const matchingFiles = (vehicle.docs || []).filter((file) => {
        const matchesCategory = category === "all" || file.category === category;
        const matchesTerm = !term || [file.name, file.category, file.date].filter(Boolean).join(" ").toLowerCase().includes(term);
        return matchesCategory && matchesTerm;
      });
      const vehicleMatches = !term || vehicleText.includes(term);
      const categoryMatches = category === "all" || (vehicle.docs || []).some((file) => file.category === category);
      const quickFilterMatches = quickFilter !== "pdf" || (vehicle.docs || []).length > 0;
      return quickFilterMatches && ((vehicleMatches && categoryMatches) || matchingFiles.length > 0);
    });
    return [...rows].sort((a, b) => {
      if (sort === "files") return Number(b.file_count || 0) - Number(a.file_count || 0);
      return String(a.suffix || a.plate_number || "").localeCompare(String(b.suffix || b.plate_number || ""), "ja");
    });
  }, [category, quickFilter, search, sort, vehicles]);

  useEffect(() => {
    if (!filteredVehicles.length) {
      setSelectedId("");
      return;
    }
    if (!filteredVehicles.some((vehicle) => resourceVehicleId(vehicle) === selectedId)) {
      setSelectedId(resourceVehicleId(filteredVehicles[0]));
    }
  }, [filteredVehicles, selectedId]);

  useEffect(() => {
    if (!uploadVehicleKey && vehicles.length) setUploadVehicleKey(resourceVehicleId(vehicles[0]));
    if (!uploadCategory && categories.length) setUploadCategory(categories[0] || "其他");
  }, [categories, uploadCategory, uploadVehicleKey, vehicles]);

  const selectedVehicle = filteredVehicles.find((vehicle) => resourceVehicleId(vehicle) === selectedId) || filteredVehicles[0];
  const selectedDocs = useMemo(() => {
    if (!selectedVehicle) return [];
    const term = search.trim().toLowerCase();
    const vehicleText = [selectedVehicle.plate_number, selectedVehicle.suffix, selectedVehicle.chassis_number, selectedVehicle.model_code]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return (selectedVehicle.docs || []).filter((file) => {
      const matchesCategory = category === "all" || file.category === category;
      const matchesTerm =
        !term ||
        vehicleText.includes(term) ||
        [file.name, file.category, file.date].filter(Boolean).join(" ").toLowerCase().includes(term);
      return matchesCategory && matchesTerm;
    });
  }, [category, search, selectedVehicle]);
  const groupedDocs = useMemo(() => {
    const groups = new Map<string, ResourceLibraryFile[]>();
    selectedDocs.forEach((file) => {
      const key = file.category || "其他";
      groups.set(key, [...(groups.get(key) || []), file]);
    });
    return Array.from(groups.entries());
  }, [selectedDocs]);

  if (loading) return <EmptyState title="正在读取资料库" detail="正在加载车辆和 PDF 资料。" />;

  async function submitUpload() {
    if (!uploadVehicleKey || !uploadCategory || !uploadFile) {
      setUploadMessage("请选择车辆、资料类别和 PDF 文件。");
      return;
    }
    if (uploadFile.type && uploadFile.type !== "application/pdf") {
      setUploadMessage("只能上传 PDF 文件。");
      return;
    }
    setUploadMessage("");
    try {
      await onUpload({
        vehicle_key: uploadVehicleKey,
        category: uploadCategory,
        document_date: uploadDate.trim(),
        custom_title: uploadTitle.trim(),
        file_name: uploadFile.name,
        content_type: uploadFile.type,
        file_base64: await readFileDataUrl(uploadFile),
      });
      setUploadMessage("上传成功，资料列表已刷新。");
      setUploadTitle("");
      setUploadDate("");
      setUploadFile(null);
    } catch (error) {
      setUploadMessage(error instanceof Error ? error.message : "上传失败");
    }
  }

  function applyResourceQuickFilter(filter: ResourceLibraryQuickFilter) {
    if (filter === "drivers") {
      onShowDrivers();
      return;
    }
    setQuickFilter(filter);
    if (filter === "vehicles") {
      setSearch("");
      setCategory("all");
      setSort("plate");
      setCategoryPanelOpen(false);
      return;
    }
    if (filter === "pdf") {
      setSearch("");
      setCategory("all");
      setSort("files");
      setCategoryPanelOpen(false);
      return;
    }
    setCategoryPanelOpen((open) => !open);
  }

  return (
    <div className="w-full space-y-4">
      <div className="rounded-xl border border-border bg-white p-4 shadow-sm">
        <div>
          <p className="text-sm font-bold text-slate-950">上传新资料入库</p>
          <p className="mt-0.5 text-xs text-slate-500">选择车辆、资料类别和 PDF；上传后自动加入下方资料列表。</p>
        </div>
        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-12">
          <label className="grid min-w-0 gap-1 text-xs font-bold text-slate-600 xl:col-span-3">
            车辆
            <select className="h-10 min-w-0 w-full rounded-md border border-border bg-white px-3 text-sm font-medium text-slate-800" value={uploadVehicleKey} onChange={(event) => setUploadVehicleKey(event.target.value)}>
              {vehicles.map((vehicle) => (
                <option key={resourceVehicleId(vehicle)} value={resourceVehicleId(vehicle)}>
                  {vehicle.suffix || "-"} ｜ {vehicle.plate_number || "-"} ｜ {vehicle.chassis_number || vehicle.model_code || "-"}
                </option>
              ))}
            </select>
          </label>
          <label className="grid min-w-0 gap-1 text-xs font-bold text-slate-600 xl:col-span-3">
            资料类别
            <select className="h-10 min-w-0 w-full rounded-md border border-border bg-white px-3 text-sm font-medium text-slate-800" value={uploadCategory} onChange={(event) => setUploadCategory(event.target.value)}>
              {categories.map((item) => <option key={item} value={item}>{item}</option>)}
              <option value="其他">其他</option>
            </select>
          </label>
          <label className="grid min-w-0 gap-1 text-xs font-bold text-slate-600 xl:col-span-1">
            日期
            <input className="h-10 min-w-0 w-full rounded-md border border-border px-3 text-sm outline-none focus:border-blue-400" value={uploadDate} onChange={(event) => setUploadDate(event.target.value)} placeholder="R80519" />
          </label>
          <label className="grid min-w-0 gap-1 text-xs font-bold text-slate-600 xl:col-span-2">
            自定义标题
            <input className="h-10 min-w-0 w-full rounded-md border border-border px-3 text-sm outline-none focus:border-blue-400" value={uploadTitle} onChange={(event) => setUploadTitle(event.target.value)} placeholder="可留空" />
          </label>
          <label className="grid min-w-0 gap-1 text-xs font-bold text-slate-600 xl:col-span-2">
            PDF
            <input
              key={uploadFile?.name || "empty-upload"}
              className="h-10 min-w-0 w-full rounded-md border border-border bg-white px-2 py-1.5 text-xs file:mr-2 file:rounded file:border-0 file:bg-slate-100 file:px-2 file:py-1 file:font-bold"
              type="file"
              accept="application/pdf,.pdf"
              onChange={(event) => setUploadFile(event.target.files?.[0] || null)}
            />
          </label>
          <button
            type="button"
            disabled={uploading || !uploadVehicleKey || !uploadCategory || !uploadFile}
            className="h-10 self-end rounded-md bg-blue-600 px-3 text-sm font-bold text-white transition hover:bg-blue-700 disabled:opacity-40 xl:col-span-1"
            onClick={() => void submitUpload()}
          >
            {uploading ? "上传中..." : "上传入库"}
          </button>
        </div>
        {uploadMessage ? (
          <p className={`mt-2 text-xs font-semibold ${uploadMessage.includes("成功") ? "text-emerald-700" : "text-red-600"}`}>{uploadMessage}</p>
        ) : null}
      </div>

      <ResourceStatGrid
        stats={[
          { value: data?.summary?.vehicles || vehicles.length, label: "车辆", tone: "blue", filterKey: "vehicles" },
          { value: data?.summary?.pdf_files || 0, label: "PDF资料", tone: "emerald", filterKey: "pdf" },
          { value: data?.summary?.categories || categories.length, label: "资料类别", tone: "amber", filterKey: "categories" },
          { value: data?.summary?.drivers || 0, label: "司机信息", tone: "slate", filterKey: "drivers" },
        ] satisfies ResourceStat<ResourceLibraryQuickFilter>[]}
        loading={false}
        activeKey={quickFilter}
        onSelect={applyResourceQuickFilter}
        gridClassName="grid-cols-2 md:grid-cols-4"
      />

      {categoryPanelOpen ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50/40 p-3 shadow-sm">
          <div className="mb-2 flex items-center justify-between gap-3">
            <p className="text-xs font-bold text-slate-700">选择资料类别</p>
            <span className="text-xs text-slate-500">{categories.length} 类</span>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className={`rounded-full border px-3 py-1.5 text-xs font-bold ${category === "all" ? "border-blue-500 bg-blue-600 text-white" : "border-slate-200 bg-white text-slate-600 hover:border-blue-300"}`}
              onClick={() => setCategory("all")}
            >
              全部类别
            </button>
            {categories.map((item) => (
              <button
                key={item}
                type="button"
                className={`rounded-full border px-3 py-1.5 text-xs font-bold ${category === item ? "border-blue-500 bg-blue-600 text-white" : "border-slate-200 bg-white text-slate-600 hover:border-blue-300"}`}
                onClick={() => setCategory(item)}
              >
                {item}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="grid gap-2 lg:grid-cols-[minmax(300px,1fr)_200px_170px_120px]">
        <label className="flex h-10 items-center gap-2 rounded-md border border-border bg-white px-3 text-sm">
          <Search size={15} className="text-slate-400" />
          <input
            className="w-full bg-transparent outline-none"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="搜索车牌、后四位、车台番号、文件名"
          />
        </label>
        <CompactSelect
          value={category}
          onChange={(value) => {
            setCategory(value);
            setQuickFilter(value === "all" ? "vehicles" : "categories");
          }}
        >
          <option value="all">全部资料类别</option>
          {categories.map((item) => <option key={item} value={item}>{item}</option>)}
        </CompactSelect>
        <CompactSelect value={sort} onChange={(value) => setSort(value as "plate" | "files")}>
          <option value="plate">按车牌排序</option>
          <option value="files">资料多到少</option>
        </CompactSelect>
        <button
          type="button"
          className="h-10 rounded-md bg-blue-600 px-3 text-sm font-bold text-white hover:bg-blue-700"
          onClick={() => {
            setSearch("");
            setCategory("all");
            setSort("plate");
            setQuickFilter("vehicles");
            setCategoryPanelOpen(false);
          }}
        >
          清除筛选
        </button>
      </div>
      {downloadError ? <div className="rounded-md border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-700">{downloadError}</div> : null}

      <div className="grid min-h-[620px] gap-3 lg:grid-cols-[310px_minmax(0,1fr)]">
        <aside className="overflow-hidden rounded-lg border border-border bg-white shadow-sm">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <h3 className="text-sm font-bold text-slate-950">车辆列表</h3>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-bold text-slate-600">{filteredVehicles.length}</span>
          </div>
          <div className="max-h-[650px] overflow-auto">
            {filteredVehicles.map((vehicle) => {
              const id = resourceVehicleId(vehicle);
              const active = id === resourceVehicleId(selectedVehicle || {});
              return (
                <button
                  key={id}
                  type="button"
                  className={`block w-full border-b border-slate-100 px-4 py-3 text-left transition ${active ? "bg-blue-50" : "hover:bg-slate-50"}`}
                  onClick={() => setSelectedId(id)}
                >
                  <strong className="block text-sm text-slate-950">{vehicle.plate_number || vehicle.suffix || "未命名车辆"}</strong>
                  <span className="mt-1 block text-xs text-slate-500">后四位 {vehicle.suffix || "-"} ｜ {vehicle.chassis_number || vehicle.model_code || "-"}</span>
                  <span className="mt-1 inline-flex rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-bold text-blue-700">{vehicle.file_count || vehicle.docs?.length || 0} PDF</span>
                </button>
              );
            })}
            {!filteredVehicles.length ? <div className="px-4 py-10 text-center text-sm text-slate-400">没有符合条件的车辆</div> : null}
          </div>
        </aside>

        <section className="overflow-hidden rounded-lg border border-border bg-white shadow-sm">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <h3 className="text-sm font-bold text-slate-950">资料下载</h3>
            <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-bold text-blue-700">{selectedDocs.length} PDF</span>
          </div>
          {selectedVehicle ? (
            <div className="max-h-[650px] overflow-auto p-4">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <h4 className="text-lg font-black text-slate-950">{selectedVehicle.plate_number || selectedVehicle.suffix}</h4>
                <span className="rounded-full bg-blue-50 px-2 py-1 text-xs font-bold text-blue-700">后四位 {selectedVehicle.suffix || "-"}</span>
                <span className="rounded-full bg-emerald-50 px-2 py-1 text-xs font-bold text-emerald-700">{selectedVehicle.chassis_number || selectedVehicle.model_code || "-"}</span>
              </div>
              <div className="space-y-3">
                {groupedDocs.map(([group, files]) => (
                  <div key={group} className="rounded-lg border border-slate-200 bg-slate-50/50 p-3">
                    <div className="mb-2 flex items-center gap-2">
                      <h5 className="text-sm font-black text-slate-950">{group}</h5>
                      <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[11px] font-bold text-slate-600">{files.length}</span>
                    </div>
                    <div className="grid gap-2 xl:grid-cols-3">
                      {files.map((file, index) => {
                        const url = normalizeResourceFileUrl(file.download_url || file.download_path || file.file_key || "");
                        return (
                          <button
                            key={`${file.file_key || file.name}-${index}`}
                            type="button"
                            className="group rounded-lg border border-slate-200 bg-white p-3 text-left transition hover:border-blue-400 hover:bg-blue-50"
                            onClick={() => {
                              setDownloadError("");
                              void downloadApiFile(url, file.name || "document.pdf").catch((error: Error) => setDownloadError(error.message));
                            }}
                          >
                            <span className="block break-words text-xs font-bold leading-5 text-slate-900">{file.name || "未命名 PDF"}</span>
                            <span className="mt-2 inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-1 text-[11px] font-bold text-blue-700 group-hover:bg-white">
                              <Download size={12} />
                              {resourceFileDate(file) || "点击下载 PDF"}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
                {!groupedDocs.length ? <EmptyState title="暂无资料" detail="当前车辆在所选类别下没有 PDF。" /> : null}
              </div>
            </div>
          ) : (
            <EmptyState title="未选择车辆" detail="请从左侧车辆列表选择一台车辆。" />
          )}
        </section>
      </div>
    </div>
  );
}

function ResourceStatGrid<T extends string = string>({
  stats,
  loading,
  activeKey,
  onSelect,
  gridClassName,
}: {
  stats: ResourceStat<T>[];
  loading: boolean;
  activeKey?: T | null;
  onSelect?: (key: T) => void;
  gridClassName?: string;
}) {
  const toneClasses: Record<string, string> = {
    blue: "border-blue-100 bg-blue-50/40 text-blue-700",
    emerald: "border-emerald-100 bg-emerald-50/40 text-emerald-700",
    amber: "border-amber-100 bg-amber-50/40 text-amber-700",
    red: "border-red-100 bg-red-50/40 text-red-700",
    slate: "border-slate-200 bg-white text-slate-700",
  };
  return (
    <div className={`grid gap-2 ${gridClassName || "grid-cols-2 sm:grid-cols-3 xl:grid-cols-6"}`}>
      {stats.map((stat) => {
        const filterKey = stat.filterKey;
        const interactive = Boolean(filterKey && onSelect);
        const active = Boolean(filterKey && activeKey === filterKey);
        const className = [
          "rounded-lg border px-3 py-3 text-left shadow-sm transition",
          toneClasses[stat.tone] || toneClasses.slate,
          interactive ? "cursor-pointer hover:-translate-y-0.5 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-400" : "",
          active ? "border-blue-500 ring-2 ring-blue-500 ring-offset-1" : "",
        ].join(" ");
        const content = (
          <>
            <div className="flex items-start justify-between gap-2">
              <strong className="block text-2xl font-black leading-none text-slate-950">{loading ? "-" : stat.value}</strong>
              {active ? <span className="rounded-full bg-blue-600 px-2 py-0.5 text-[10px] font-bold text-white">筛选中</span> : null}
            </div>
            <span className="mt-2 block text-xs font-semibold">{stat.label}</span>
          </>
        );
        return onSelect && filterKey ? (
          <button
            key={stat.label}
            type="button"
            aria-pressed={active}
            title="点击筛选，再次点击清除"
            className={className}
            onClick={() => onSelect(filterKey)}
          >
            {content}
          </button>
        ) : (
          <div key={stat.label} className={className}>
            {content}
          </div>
        );
      })}
    </div>
  );
}

function CompactSelect({
  value,
  onChange,
  children,
}: {
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <select
      className="h-9 min-w-[142px] rounded-md border border-border bg-white px-3 text-sm font-medium text-slate-700 outline-none transition focus:border-blue-400"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    >
      {children}
    </select>
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
    <section className="overflow-hidden rounded-xl border border-border bg-white shadow-sm">
      <div className="border-b border-border px-4 py-3">
        <h3 className="text-base font-bold text-slate-950">车辆基础信息</h3>
        <p className="text-xs text-slate-500">第一行快速新增；已有单元格双击修改，回车或点击空白处保存。</p>
      </div>
      <div className="max-h-[72vh] overflow-auto">
        <table className="w-full min-w-[1160px] border-collapse text-center text-sm">
          <thead className="sticky top-0 z-20 bg-slate-100 text-xs font-bold text-slate-600 shadow-[0_1px_0_0_#dbe2ea]">
            <tr>
              <th className="border-r border-slate-200 px-3 py-2 text-center">序号</th>
              {cols.map((col) => <th key={col.key} className="border-r border-slate-200 px-3 py-2 text-center">{col.label}</th>)}
              <th className="border-r border-slate-200 px-3 py-2 text-center">PDF</th>
              <th className="px-3 py-2 text-center">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            <VehicleQuickCreateRow draft={draft} saving={saving} onChange={setDraft} onSave={saveDraft} />
            {rows.map((row, index) => (
              <tr key={row.id} className="hover:bg-slate-50">
                <td className="border-r border-slate-100 px-3 py-2 align-middle text-slate-500">{index + 1}</td>
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
                <td className="border-r border-slate-100 px-3 py-2 align-middle">
                  <ResourceFileLinks row={row} />
                </td>
                <td className="px-3 py-2 align-middle">
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
    <tr className="bg-emerald-50/60" data-quick-create="vehicles">
      <td className="px-4 py-3 text-xs font-bold text-emerald-700">新增</td>
      <td className="px-2 py-2"><QuickInput value={draft.vehicle_type || ""} placeholder="ハイエース" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, vehicle_type: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.plate_number || ""} placeholder="なにわ300あ1001" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, plate_number: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.plate_short_code || ""} placeholder="1001" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, plate_short_code: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.vehicle_type_code || ""} placeholder="H/A" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, vehicle_type_code: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.vehicle_color || ""} placeholder="白/黑" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, vehicle_color: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.snow_tire || ""} placeholder="普通/雪胎" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, snow_tire: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={statusLabel(draft.status)} placeholder="正常" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, status: parseStatus(value, "vehicle") })} /></td>
      <td className="px-4 py-3 text-xs text-slate-400">-</td>
      <td className="px-4 py-3">
        <button type="button" disabled={saving || !draft.plate_number?.trim()} onClick={onSave} className="inline-flex h-8 items-center rounded-full bg-emerald-600 px-3 text-xs font-bold text-white disabled:opacity-40">
          新增
        </button>
      </td>
    </tr>
  );
}

function VehicleMaintenanceTable({
  rows,
  loading,
}: {
  rows: Vehicle[];
  loading: boolean;
  saving: boolean;
  onSave: (id: number, payload: Partial<Vehicle>) => void;
  onCreateRecord: (vehicleId: number, payload: Partial<VehicleInspectionRecord>) => void;
  onUpdateRecord: (id: number, payload: Partial<VehicleInspectionRecord>) => void;
  onDeleteRecord: (id: number) => void;
}) {
  const [open, setOpen] = useState(true);
  if (loading || !rows.length) return null;
  return (
    <section className="overflow-hidden rounded-xl border border-border bg-white shadow-sm">
      <button type="button" className="flex w-full items-center justify-between px-4 py-3 text-left" onClick={() => setOpen((value) => !value)}>
        <div>
          <h3 className="text-base font-bold text-slate-950">车辆维护记录</h3>
          <p className="text-xs text-slate-500">只读日期汇总；资料上传、PDF 下载和分类管理请在“车辆资料”页完成。</p>
        </div>
        {open ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
      </button>
      {open ? (
        <div className="max-h-[72vh] overflow-auto border-t border-border">
          <table className="w-full min-w-[980px] text-center text-sm">
            <thead className="sticky top-0 z-20 bg-slate-50 text-xs font-bold text-slate-500 shadow-[0_1px_0_0_#e5e7eb]">
              <tr>
                <th className="px-4 py-3 text-center">车辆</th>
                <th className="px-4 py-3 text-center">初登录日</th>
                <th className="px-4 py-3 text-center">到社日期</th>
                <th className="px-4 py-3 text-center">最近点检日</th>
                <th className="px-4 py-3 text-center">点检到期日</th>
                <th className="px-4 py-3 text-center">车检到期日</th>
                <th className="px-4 py-3 text-center">历次点检日期</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((row) => {
                const historyDates = Array.from(
                  new Set((row.inspection_records || []).map((record) => dateOnly(record.inspection_date)).filter((value) => value !== "-")),
                ).sort((left, right) => right.localeCompare(left));
                return (
                  <tr key={row.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 text-center font-semibold text-slate-900">{row.plate_number}</td>
                    <td className="px-4 py-3 text-center text-slate-700">{dateOnly(row.first_registration_date)}</td>
                    <td className="px-4 py-3 text-center text-slate-700">{dateOnly(row.company_registration_date)}</td>
                    <td className="px-4 py-3 text-center text-slate-700">{dateOnly(row.last_inspection_date)}</td>
                    <td className="px-4 py-3 text-center text-slate-700">
                      {dateOnly(addDays(row.last_inspection_date, 90) || row.next_inspection_due_date)}
                    </td>
                    <td className="px-4 py-3 text-center text-slate-700">{dateOnly(row.shaken_due_date)}</td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex flex-wrap justify-center gap-1.5">
                        {historyDates.length ? historyDates.map((date) => (
                          <span key={date} className="inline-flex h-6 items-center rounded-full border border-slate-200 bg-white px-2 text-[11px] font-semibold text-slate-700">
                            {date}
                          </span>
                        )) : <span className="text-xs text-slate-400">-</span>}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

function DriverTable({
  rows,
  libraryRowsByName,
  loading,
  saving,
  onCreate,
  onSave,
  onEmploymentChange,
  onDelete,
}: {
  rows: Driver[];
  libraryRowsByName: Map<string, Record<string, string>>;
  loading: boolean;
  saving: boolean;
  onCreate: (payload: Partial<Driver>) => void;
  onSave: (id: number, payload: Partial<Driver>) => void;
  onEmploymentChange: (row: Driver, retired: boolean) => void;
  onDelete: (id: number) => void;
}) {
  const [editing, setEditing] = useState<EditingCell>(null);
  const [draft, setDraft] = useState<Partial<Driver>>(driverInitial);
  const cols: Array<{ key: keyof Driver; label: string; render?: (value: string, row: Driver) => ReactNode }> = [
    { key: "driver_external_id", label: "運転手ID" },
    { key: "office", label: "所属営業所" },
    { key: "name", label: "運転手名" },
    { key: "license_due_date", label: "免许有效期限" },
    { key: "license_number", label: "免許番号" },
    { key: "residence_status", label: "在留资格" },
    { key: "residence_due_date", label: "再留期限有效日期" },
    { key: "health_check_due_date", label: "健康诊断日期", render: healthCheckDateValue },
    { key: "phone", label: "携帯電話番号" },
    { key: "email", label: "メールアドレス" },
    { key: "status", label: "状態" },
  ];
  if (loading) return <EmptyState title="正在加载司机" detail="正在读取司机台账。" />;
  function saveDraft() {
    if (!draft.name?.trim()) return;
    onCreate(cleanPayload({ ...normalizeDateFields(draft), status: draft.status || "available", driver_status: draft.status || draft.driver_status || "available" }));
    setDraft(driverInitial);
  }
  return (
    <section className="overflow-hidden rounded-xl border border-border bg-white shadow-sm">
      <div className="max-h-[72vh] overflow-auto">
        <table className="w-full min-w-[1780px] border-collapse text-center text-xs">
          <thead className="sticky top-0 z-20 bg-slate-100 text-xs font-bold text-slate-600 shadow-[0_1px_0_0_#dbe2ea]">
            <tr>
              <th className="sticky left-0 z-30 min-w-[112px] border-r border-slate-200 bg-slate-100 px-2 py-2 text-center">操作</th>
              <th className="min-w-[96px] border-r border-slate-200 px-2 py-2 text-center">健康诊断状态</th>
              {cols.map((col) => <th key={col.key} className="border-r border-slate-200 px-3 py-2 text-center">{col.label}</th>)}
              <th className="min-w-[118px] border-r border-slate-200 px-2 py-2 text-center">健康诊断剩余有效天数</th>
              <th className="min-w-[120px] border-r border-slate-200 px-2 py-2 text-center">特长</th>
              <th className="min-w-[260px] px-3 py-2 text-center">备注</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            <DriverQuickCreateRow draft={draft} saving={saving} onChange={setDraft} onSave={saveDraft} />
            {rows.map((row) => {
              const libraryRow = libraryRowsByName.get(row.name);
              const retired = row.status === "retired" || isLibraryDriverRetired(libraryRow);
              return (
                <tr key={row.id} className="hover:bg-slate-50">
                  <td className="sticky left-0 z-10 border-r border-slate-200 bg-white px-2 py-1.5 align-middle">
                    <div className="flex items-center justify-center gap-1">
                      <button
                        type="button"
                        disabled={saving}
                        className={`h-7 rounded-md border px-2 text-[11px] font-bold disabled:opacity-50 ${
                          retired
                            ? "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                            : "border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100"
                        }`}
                        onClick={() => onEmploymentChange(row, !retired)}
                      >
                        {retired ? "复职" : "离职"}
                      </button>
                      <button
                        type="button"
                        disabled={saving}
                        className="h-7 rounded-md border border-red-200 bg-red-50 px-2 text-[11px] font-bold text-red-600 hover:bg-red-100 disabled:opacity-50"
                        onClick={() => onDelete(row.id)}
                      >
                        移除
                      </button>
                    </div>
                  </td>
                  <td className="border-r border-slate-100 px-2 py-1.5 align-middle">{driverHealthStatusBadge(row, libraryRow)}</td>
                  {cols.map((col) => (
                    <EditableTd
                      key={`${row.id}-${col.key}`}
                      rowId={row.id}
                      field={col.key}
                      value={displayDriverValue(row, col.key)}
                      editing={editing}
                      saving={saving}
                      onStart={setEditing}
                      onSave={(id, field, value) => onSave(id, normalizeDriverPatch(field, value))}
                      render={(value) =>
                        col.key === "status"
                          ? driverOperationalStatusBadge(value, libraryRow)
                          : col.render
                            ? col.render(value, row)
                            : fieldLooksDate(String(col.key))
                              ? dateWithStatus(value)
                              : value || "-"
                      }
                    />
                  ))}
                  <td className="border-r border-slate-100 px-2 py-1.5 align-middle">{driverHealthRemainingBadge(row, libraryRow)}</td>
                  <td className="border-r border-slate-100 px-2 py-1.5 align-middle text-slate-700">{libraryDriverValue(libraryRow, "特长") || "-"}</td>
                  <EditableTd
                    rowId={row.id}
                    field="note"
                    value={String(row.note || libraryDriverValue(libraryRow, "来源/备注") || "")}
                    editing={editing}
                    saving={saving}
                    onStart={setEditing}
                    onSave={(id, field, value) => onSave(id, normalizeDriverPatch(field, value))}
                    render={(value) => <span className="block max-w-[360px] whitespace-pre-wrap text-left leading-5 text-slate-600">{value || "-"}</span>}
                  />
                </tr>
              );
            })}
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
    <tr className="bg-emerald-50/60" data-quick-create="drivers">
      <td className="sticky left-0 z-10 bg-emerald-50 px-2 py-2">
        <button type="button" disabled={saving || !draft.name?.trim()} onClick={onSave} className="inline-flex h-8 items-center rounded-md bg-emerald-600 px-3 text-xs font-bold text-white disabled:opacity-40">
          新增
        </button>
      </td>
      <td className="px-2 py-2 text-xs font-bold text-slate-400">自动</td>
      <td className="px-2 py-2"><QuickInput value={draft.driver_external_id || ""} placeholder="ID" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, driver_external_id: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.office || ""} placeholder="本社" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, office: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.name || ""} placeholder="司机姓名" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, name: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.license_due_date || ""} placeholder="驾照到期" onBlurDate={(value) => onChange({ ...draft, license_due_date: value })} onKeyDown={keySave} onChange={(value) => onChange({ ...draft, license_due_date: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.license_number || ""} placeholder="驾照号" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, license_number: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.residence_status || ""} placeholder="在留" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, residence_status: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.residence_due_date || ""} placeholder="在留到期" onBlurDate={(value) => onChange({ ...draft, residence_due_date: value })} onKeyDown={keySave} onChange={(value) => onChange({ ...draft, residence_due_date: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.health_check_due_date || ""} placeholder="体检日期" onBlurDate={(value) => onChange({ ...draft, health_check_due_date: value })} onKeyDown={keySave} onChange={(value) => onChange({ ...draft, health_check_due_date: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.phone || ""} placeholder="电话" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, phone: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={draft.email || ""} placeholder="mail" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, email: value })} /></td>
      <td className="px-2 py-2"><QuickInput value={statusLabel(draft.status)} placeholder="運転可" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, status: parseStatus(value, "driver"), driver_status: parseStatus(value, "driver") })} /></td>
      <td className="px-2 py-2 text-xs font-bold text-slate-400">自动</td>
      <td className="px-2 py-2 text-xs text-slate-400">-</td>
      <td className="px-2 py-2"><QuickInput value={draft.note || ""} placeholder="备注" onKeyDown={keySave} onChange={(value) => onChange({ ...draft, note: value })} /></td>
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
    <td className="border-r border-slate-100 px-3 py-2 align-middle text-center" onDoubleClick={() => onStart({ id: rowId, key: field, value })}>
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

function libraryDriverValue(row: Record<string, string> | undefined, ...keys: string[]) {
  if (!row) return "";
  for (const key of keys) {
    const value = String(row[key] || "").trim();
    if (value) return value;
  }
  return "";
}

function libraryDriverName(row: Record<string, string>) {
  return libraryDriverValue(row, "運転手名", "司机姓名", "姓名", "name", "driver_name");
}

function isLibraryDriverRetired(row?: Record<string, string>) {
  return ["状態", "状态", "status", "driver_status", "来源/备注"].some((key) =>
    /离职|離職|退職|retired|deleted/i.test(String(row?.[key] || "")),
  );
}

function isDriverOperational(driver: Driver, libraryRow?: Record<string, string>) {
  if (libraryRow && isLibraryDriverRetired(libraryRow)) return false;
  const source = libraryDriverValue(libraryRow, "状態", "状态", "status", "driver_status");
  if (source) return /運転可|available|正常/i.test(source);
  return driver.driver_status === "available" || driver.status === "available";
}

function libraryDriverHealthBucket(row?: Record<string, string>): HealthBucket {
  const explicit = libraryDriverValue(row, "健康诊断状态", "健康診断状態").toLowerCase();
  if (/expired|overdue|已过期|期限切れ/.test(explicit)) return "expired";
  if (/soon|30天内|30日以内/.test(explicit)) return "30";
  if (/31-90|90天内|90日以内/.test(explicit)) return "90";
  if (/ok|normal|正常/.test(explicit)) return "normal";
  const remainingText = libraryDriverValue(row, "健康诊断剩余有效天数", "健康診断残日数");
  if (!remainingText || !/^-?\d+$/.test(remainingText)) return "unknown";
  const remaining = Number(remainingText);
  if (remaining < 0) return "expired";
  if (remaining <= 30) return "30";
  if (remaining <= 90) return "90";
  return "normal";
}

function mergeDriverFromLibrary(driver: Driver, row?: Record<string, string>): Driver {
  if (!row) return driver;
  const statusText = libraryDriverValue(row, "状態", "状态", "status", "driver_status");
  const locallyRetired = driver.status === "retired" || driver.driver_status === "retired";
  const status = locallyRetired || isLibraryDriverRetired(row)
    ? "retired"
    : /運転可|available|正常/i.test(statusText)
      ? "available"
      : driver.status;
  const remainingText = libraryDriverValue(row, "健康诊断剩余有效天数", "健康診断残日数");
  return {
    ...driver,
    driver_external_id: libraryDriverValue(row, "運転手ID", "司机编号") || driver.driver_external_id,
    office: libraryDriverValue(row, "所属営業所", "营业所") || driver.office,
    name: libraryDriverName(row) || driver.name,
    license_due_date: libraryDriverValue(row, "免许有効期限", "免許有効期限") || driver.license_due_date,
    license_number: libraryDriverValue(row, "免許番号", "驾照号码") || driver.license_number,
    residence_status: libraryDriverValue(row, "在留資格", "在留资格") || driver.residence_status,
    residence_due_date: libraryDriverValue(row, "再留期限有效日期", "在留期限有效日期") || driver.residence_due_date,
    health_check_due_date: libraryDriverValue(row, "健康诊断日期", "健康診断日") || driver.health_check_due_date,
    health_check_remaining_days: /^-?\d+$/.test(remainingText) ? Number(remainingText) : driver.health_check_remaining_days,
    phone: libraryDriverValue(row, "携帯電話番号", "电话") || driver.phone,
    email: libraryDriverValue(row, "メールアドレス", "邮箱") || driver.email,
    note: driver.note || libraryDriverValue(row, "来源/备注"),
    status,
    driver_status: status,
  };
}

function displayDriverValue(row: Driver, key: keyof Driver) {
  if (key === "status") return String(row.status || row.driver_status || "");
  return String(row[key] || "");
}

function driverHealthStatusBadge(row: Driver, libraryRow?: Record<string, string>) {
  const bucket = libraryRow ? libraryDriverHealthBucket(libraryRow) : driverHealthBucket(row);
  const styles: Record<HealthBucket, string> = {
    expired: "bg-red-50 text-red-600",
    "30": "bg-amber-50 text-amber-700",
    "90": "bg-emerald-50 text-emerald-700",
    normal: "bg-blue-50 text-blue-700",
    unknown: "bg-slate-100 text-slate-500",
  };
  const labels: Record<HealthBucket, string> = {
    expired: "已过期",
    "30": "30天内",
    "90": "31-90天",
    normal: "正常",
    unknown: "无法计算",
  };
  return <span className={`inline-flex rounded-full px-2 py-1 text-[11px] font-bold ${styles[bucket]}`}>{labels[bucket]}</span>;
}

function driverHealthRemainingBadge(row: Driver, libraryRow?: Record<string, string>) {
  const sourceValue = libraryDriverValue(libraryRow, "健康诊断剩余有效天数", "健康診断残日数");
  const remaining = /^-?\d+$/.test(sourceValue)
    ? Number(sourceValue)
    : typeof row.health_check_remaining_days === "number"
      ? row.health_check_remaining_days
      : daysUntil(addDays(row.health_check_due_date, 365));
  if (remaining === null) return <span className="text-slate-400">-</span>;
  const className = remaining < 0 ? "bg-red-50 text-red-600" : remaining <= 30 ? "bg-amber-50 text-amber-700" : remaining <= 90 ? "bg-emerald-50 text-emerald-700" : "bg-blue-50 text-blue-700";
  return <span className={`inline-flex rounded-full px-2 py-1 text-[11px] font-bold ${className}`}>{remaining}</span>;
}

function driverOperationalStatusBadge(value: string, libraryRow?: Record<string, string>) {
  const source = libraryDriverValue(libraryRow, "状態", "状态", "status", "driver_status");
  const retired = isLibraryDriverRetired(libraryRow) || value === "retired";
  const label = retired ? "离职" : source || (value === "available" ? "運転可" : statusLabel(value));
  return (
    <span className={`inline-flex rounded-full px-2 py-1 text-[11px] font-bold ${retired ? "bg-slate-100 text-slate-600" : /待补/.test(label) ? "bg-amber-50 text-amber-700" : "bg-emerald-50 text-emerald-700"}`}>
      {label}
    </span>
  );
}

function resourceVehicleId(vehicle: Partial<ResourceLibraryVehicle>) {
  return String(vehicle.id || vehicle.suffix || vehicle.plate_number || "");
}

function resourceFileDate(file: ResourceLibraryFile) {
  if (file.date) return file.date;
  const match = String(file.name || "").match(/(?:R\d{5,6}|\d{8})/i);
  return match?.[0] || "";
}

function readFileDataUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("读取 PDF 文件失败"));
    reader.readAsDataURL(file);
  });
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
  if (field === "status") return { status: parseStatus(value, "vehicle") };
  if (fieldLooksDate(field)) return { [field]: normalizeFlexibleDate(value) } as Partial<Vehicle>;
  return { [field]: value } as Partial<Vehicle>;
}

function normalizeDriverPatch(field: string, value: string): Partial<Driver> {
  if (field === "status") {
    const status = parseStatus(value, "driver");
    return { status, driver_status: status };
  }
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
  if (kind === "vehicle" && (raw.includes("减") || raw.includes("retired"))) return "retired";
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

function daysUntil(value?: string) {
  if (!value) return null;
  const target = new Date(value);
  if (Number.isNaN(target.getTime())) return null;
  const today = new Date();
  target.setHours(0, 0, 0, 0);
  today.setHours(0, 0, 0, 0);
  return Math.ceil((target.getTime() - today.getTime()) / 86400000);
}

function dateOnly(value?: string) {
  return value || "-";
}

type ResourceFileLink = {
  label: string;
  url: string;
};

function ResourceFileLinks({ row }: { row: Vehicle | Driver }) {
  const files = resourceFiles(row);
  if (!files.length) return <span className="text-xs text-slate-400">-</span>;
  return (
    <div className="flex max-w-[360px] flex-wrap justify-center gap-1.5">
      {files.map((file, index) => (
        <a
          key={`${file.url}-${index}`}
          className="inline-flex max-w-[170px] items-center rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-bold text-blue-700 transition hover:bg-blue-100 hover:underline"
          href={file.url}
          target="_blank"
          rel="noreferrer"
          download
          title={file.label}
        >
          <span className="truncate">{shortFileLabel(file.label)}</span>
        </a>
      ))}
    </div>
  );
}

function resourceFiles(row: Vehicle | Driver): ResourceFileLink[] {
  const raw = row as Record<string, unknown>;
  const output: ResourceFileLink[] = [];
  const lists = [raw.docs, raw.pdf_files, raw.files, raw.documents];
  for (const list of lists) {
    if (!Array.isArray(list)) continue;
    list.forEach((file, index) => {
      if (typeof file === "string") {
        const url = normalizeResourceFileUrl(file);
        if (url) output.push({ label: `PDF ${index + 1}`, url });
        return;
      }
      if (!file || typeof file !== "object") return;
      const item = file as Record<string, unknown>;
      const url = normalizeResourceFileUrl(
        stringValue(item.download_url) ||
        stringValue(item.download_path) ||
        stringValue(item.url) ||
        stringValue(item.href) ||
        stringValue(item.file_url) ||
        stringValue(item.file_key) ||
        stringValue(item.file_name) ||
        stringValue(item.name),
      );
      if (!url) return;
      const name = stringValue(item.title) || stringValue(item.file_name) || stringValue(item.name) || `PDF ${index + 1}`;
      const prefix = [stringValue(item.date), stringValue(item.category)].filter(Boolean).join(" ");
      output.push({ label: prefix ? `${prefix} ${name}` : name, url });
    });
  }
  [
    ["免许", raw.license_file_url],
    ["体检", raw.health_check_file_url],
    ["PDF", raw.pdf_url],
    ["资料", raw.file_url],
    ["下载", raw.download_url],
  ].forEach(([label, value]) => {
    const url = normalizeResourceFileUrl(stringValue(value));
    if (url) output.push({ label: String(label), url });
  });
  const seen = new Set<string>();
  return output.filter((file) => {
    if (seen.has(file.url)) return false;
    seen.add(file.url);
    return true;
  });
}

function normalizeResourceFileUrl(value: string) {
  const raw = stringValue(value);
  if (!raw || raw === "-") return "";
  if (/^(https?:|blob:|data:)/i.test(raw) || raw.startsWith("/api/")) return raw;
  if (raw.startsWith("/")) return raw;
  return `/api/dispatch-mobile/resource-library/file?file=${encodeURIComponent(raw)}`;
}

function stringValue(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function shortFileLabel(label: string) {
  return label.length > 24 ? `${label.slice(0, 23)}...` : label;
}

function addDays(value: unknown, days: number) {
  if (!value) return "";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return "";
  date.setDate(date.getDate() + days);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function driverHealthBucket(row: Driver): HealthBucket {
  const remaining =
    typeof row.health_check_remaining_days === "number"
      ? row.health_check_remaining_days
      : daysUntil(addDays(row.health_check_due_date, 365));
  if (remaining === null) return "unknown";
  if (remaining < 0) return "expired";
  if (remaining <= 30) return "30";
  if (remaining <= 90) return "90";
  return "normal";
}

function healthCheckDateValue(value?: string, row?: Driver) {
  if (!value) return "-";
  const expiry = addDays(value, 365);
  const remaining = typeof row?.health_check_remaining_days === "number" ? row.health_check_remaining_days : daysUntil(expiry);
  if (remaining !== null) {
    return (
      <span className="block text-center">
        <span className="block">{dateOnly(value)}</span>
        <span
          className={`mt-0.5 block text-[11px] font-semibold leading-tight ${
            remaining < 0 ? "text-red-600" : remaining <= 90 ? "text-emerald-700" : "text-slate-500"
          }`}
        >
          {remaining < 0 ? `已过期 ${Math.abs(remaining)} 天` : `剩余 ${remaining} 天`}
        </span>
      </span>
    );
  }
  return (
    <span className="block text-center">
      <span className="block">{dateOnly(value)}</span>
      {expiry ? (
        <span className="mt-0.5 block text-[11px] leading-tight text-slate-500">
          有效至 {dateWithStatus(expiry)}
        </span>
      ) : null}
    </span>
  );
}
