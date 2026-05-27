import type {
  Agency,
  AgencyPortalAgency,
  AgencyPortalSession,
  AccountOverview,
  Assignment,
  AssignmentEvidenceChain,
  AnalyticsSummary,
  AttendanceDaily,
  AuditLog,
  AuthUser,
  BillingOverview,
  CalendarResponse,
  CopilotSummary,
  DataAnomalyScan,
  DashboardSummary,
  DispatchRecommendation,
  Draft,
  Driver,
  DriverSafetyAlert,
  DriverSettlementStatsResponse,
  DriverReport,
  FinanceDriverExpense,
  FinanceDriverExpenseResponse,
  FinanceLedger,
  FinanceOrder,
  FinanceSummary,
  Incident,
  IncidentSummary,
  LocationLog,
  NotificationItem,
  NotificationSummary,
  Order,
  OrgMember,
  OrgOverview,
  ManagedAccount,
  ReminderSettings,
  ResourceAlert,
  Team,
  Vehicle,
  WorkflowRule,
  WorkflowRun,
  WorkflowRunResult,
} from "@/types/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:18765";
const TOKEN_KEY = "wx_dispatch_token";
const AGENCY_TOKEN_KEY = "wx_dispatch_agency_token";

export function getAuthToken() {
  return window.localStorage.getItem(TOKEN_KEY) || "";
}

export function setAuthToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearAuthToken() {
  window.localStorage.removeItem(TOKEN_KEY);
}

export function getAgencyToken() {
  return window.localStorage.getItem(AGENCY_TOKEN_KEY) || "";
}

export function setAgencyToken(token: string) {
  window.localStorage.setItem(AGENCY_TOKEN_KEY, token);
}

export function clearAgencyToken() {
  window.localStorage.removeItem(AGENCY_TOKEN_KEY);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAuthToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
    ...init,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = (await response.clone().json()) as { error?: string; message?: string };
      detail = payload.error || payload.message || detail;
    } catch {
      detail = response.statusText;
    }
    throw new Error(`${response.status} ${detail}`);
  }

  return response.json() as Promise<T>;
}

async function requestText(path: string): Promise<string> {
  const token = getAuthToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.text();
}

function listFrom<T>(payload: unknown, keys: string[]): T[] {
  if (Array.isArray(payload)) return payload as T[];
  if (payload && typeof payload === "object") {
    for (const key of keys) {
      const value = (payload as Record<string, unknown>)[key];
      if (Array.isArray(value)) return value as T[];
    }
  }
  return [];
}

export const api = {
  baseUrl: API_BASE_URL,
  ping: () => request<{ ok: boolean; message?: string }>("/api/ping"),
  agencies: async (params?: { keyword?: string; status?: string }) => {
    const search = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value) search.set(key, value);
    });
    return listFrom<Agency>(await request<unknown>(`/api/agencies${search.toString() ? `?${search}` : ""}`), ["agencies", "items", "data"]);
  },
  createAgency: (payload: Partial<Agency>) =>
    request<{ agency: Agency }>("/api/agencies", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateAgency: (id: number, payload: Partial<Agency>) =>
    request<{ agency: Agency }>(`/api/agencies/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  deleteAgency: (id: number) =>
    request<{ deleted: boolean }>(`/api/agencies/${id}`, {
      method: "DELETE",
    }),
  agencyPortalAgencies: async () =>
    listFrom<AgencyPortalAgency>(await request<unknown>("/api/agency-portal/agencies"), ["agencies", "items", "data"]),
  agencyPortalLogin: (agencyId: number, portalCode: string) =>
    request<AgencyPortalSession>("/api/agency-portal/login", {
      method: "POST",
      body: JSON.stringify({ agency_id: agencyId, portal_code: portalCode }),
    }),
  agencyPortalOrders: async () =>
    listFrom<Order>(
      await request<unknown>("/api/agency-portal/orders", {
        headers: { "X-Agency-Token": getAgencyToken() },
      }),
      ["orders", "items", "data"],
    ),
  createAgencyPortalOrder: (payload: Partial<Order>) =>
    request<{ order: Order }>("/api/agency-portal/orders", {
      method: "POST",
      headers: { "X-Agency-Token": getAgencyToken() },
      body: JSON.stringify(payload),
    }),
  workflowRules: async () =>
    listFrom<WorkflowRule>(await request<unknown>("/api/workflows/rules"), ["rules", "items", "data"]),
  workflowRuns: async () =>
    listFrom<WorkflowRun>(await request<unknown>("/api/workflows/runs"), ["runs", "items", "data"]),
  runWorkflows: (code?: string) =>
    request<WorkflowRunResult>("/api/workflows/run", {
      method: "POST",
      body: JSON.stringify(code ? { code } : {}),
    }),
  updateWorkflowRule: (id: number, payload: Partial<WorkflowRule>) =>
    request<{ rule: WorkflowRule }>(`/api/workflows/rules/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  login: (username: string, password: string) =>
    request<{ token: string; user: AuthUser }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  loginPhone: (phone: string, password: string) =>
    request<{ token: string; user: AuthUser }>("/api/auth/login-phone", {
      method: "POST",
      body: JSON.stringify({ phone, password, client_type: "web" }),
    }),
  me: () => request<{ user: AuthUser }>("/api/auth/me"),
  dashboardSummary: () => request<DashboardSummary>("/api/dashboard/summary"),
  copilotSummary: (date?: string) => request<CopilotSummary>(`/api/copilot/summary${date ? `?date=${date}` : ""}`),
  analyticsSummary: (params?: { date_from?: string; date_to?: string }) => {
    const search = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value) search.set(key, value);
    });
    return request<AnalyticsSummary>(`/api/analytics/summary${search.toString() ? `?${search}` : ""}`);
  },
  attendanceDaily: (date?: string) => request<AttendanceDaily>(`/api/attendance/daily${date ? `?date=${encodeURIComponent(date)}` : ""}`),
  auditLogs: async (params?: { action?: string; entity_type?: string; entity_id?: string; keyword?: string; limit?: number }) => {
    const search = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value !== undefined && value !== "") search.set(key, String(value));
    });
    return listFrom<AuditLog>(await request<unknown>(`/api/audit/logs${search.toString() ? `?${search}` : ""}`), ["logs", "items", "data"]);
  },
  auditHistory: async (entityType: string, entityId: string | number) =>
    listFrom<AuditLog>(
      await request<unknown>(`/api/audit/history?entity_type=${encodeURIComponent(entityType)}&entity_id=${encodeURIComponent(String(entityId))}`),
      ["history", "items", "data"],
    ),
  auditAnomalies: () => request<DataAnomalyScan>("/api/audit/anomalies"),
  runAuditScan: () =>
    request<DataAnomalyScan>("/api/audit/scan", {
      method: "POST",
    }),
  auditScans: async () => listFrom<DataAnomalyScan>(await request<unknown>("/api/audit/scans"), ["scans", "items", "data"]),
  notificationSummary: () => request<NotificationSummary>("/api/notifications/summary"),
  notifications: async (params?: { status?: string; notification_type?: string; limit?: number }) => {
    const search = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value !== undefined && value !== "") search.set(key, String(value));
    });
    return listFrom<NotificationItem>(await request<unknown>(`/api/notifications${search.toString() ? `?${search}` : ""}`), ["notifications", "items", "data"]);
  },
  createNotification: (payload: Partial<NotificationItem>) =>
    request<{ notification: NotificationItem }>("/api/notifications", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  markNotificationRead: (id: number) =>
    request<{ notification: NotificationItem }>(`/api/notifications/${id}/read`, {
      method: "POST",
    }),
  markAllNotificationsRead: () =>
    request<{ updated: number }>("/api/notifications/read-all", {
      method: "POST",
    }),
  billingOverview: () => request<BillingOverview>("/api/billing/overview"),
  updateSubscription: (planCode: string) =>
    request<{ subscription: BillingOverview["subscription"] }>("/api/billing/subscription", {
      method: "POST",
      body: JSON.stringify({ plan_code: planCode, status: "active" }),
    }),
  orgOverview: () => request<OrgOverview>("/api/org/overview"),
  accountOverview: () => request<AccountOverview>("/api/accounts/overview"),
  createAccount: (payload: { role: ManagedAccount["role"]; display_name: string; phone: string; password?: string }) =>
    request<{ account: ManagedAccount }>("/api/accounts", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateAccount: (id: number, payload: Partial<ManagedAccount> & { confirm_driver_role_change?: boolean }) =>
    request<{ account: ManagedAccount }>(`/api/accounts/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  disableAccount: (id: number) =>
    request<{ account: ManagedAccount }>(`/api/accounts/${id}/disable`, {
      method: "POST",
    }),
  resetAccountPassword: (id: number) =>
    request<{ account: ManagedAccount }>(`/api/accounts/${id}/reset-password`, {
      method: "POST",
    }),
  unbindAccountWechat: (id: number) =>
    request<{ account: ManagedAccount }>(`/api/accounts/${id}/unbind-wechat`, {
      method: "POST",
    }),
  inviteMember: (payload: {
    username: string;
    password: string;
    role: OrgMember["role"];
    display_name?: string;
    department_id?: number | "";
    team_id?: number | "";
    title?: string;
    phone?: string;
  }) =>
    request<{ member: OrgMember }>("/api/org/members/invite", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateMember: (id: number, payload: Partial<OrgMember>) =>
    request<{ member: OrgMember }>(`/api/org/members/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  disableMember: (id: number) =>
    request<{ member: OrgMember }>(`/api/org/members/${id}/disable`, {
      method: "POST",
    }),
  createDepartment: (payload: { name: string; description?: string }) =>
    request<{ department: OrgOverview["departments"][number] }>("/api/org/departments", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createTeam: (payload: { name: string; department_id?: number | ""; description?: string }) =>
    request<{ team: Team }>("/api/org/teams", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  incidents: async (params?: { status?: string; incident_type?: string; severity?: string; keyword?: string }) => {
    const search = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value) search.set(key, value);
    });
    return listFrom<Incident>(await request<unknown>(`/api/incidents${search.toString() ? `?${search}` : ""}`), ["incidents", "items", "data"]);
  },
  incidentSummary: () => request<IncidentSummary>("/api/incidents/summary"),
  createIncident: (payload: Partial<Incident>) =>
    request<{ incident: Incident }>("/api/incidents", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  closeIncident: (id: number, payload: { resolution?: string }) =>
    request<{ incident: Incident }>(`/api/incidents/${id}/close`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  financeSummary: (params?: { settlement_status?: string; agency_name?: string; date_from?: string; date_to?: string; driver_id?: string; order_type?: string; execution_status?: string; driver_settlement_status?: string }) => {
    const search = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value) search.set(key, value);
    });
    return request<FinanceSummary>(`/api/finance/summary${search.toString() ? `?${search}` : ""}`);
  },
  financeLedger: (params?: { settlement_status?: string; agency_name?: string; date_from?: string; date_to?: string; driver_id?: string; order_type?: string; execution_status?: string; driver_settlement_status?: string }) => {
    const search = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value) search.set(key, value);
    });
    return request<FinanceLedger>(`/api/finance/ledger${search.toString() ? `?${search}` : ""}`);
  },
  driverSettlementStats: (params?: { start_date?: string; end_date?: string; date_from?: string; date_to?: string; driver_id?: string; order_type?: string }) => {
    const search = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value) search.set(key === "start_date" ? "date_from" : key === "end_date" ? "date_to" : key, value);
    });
    return request<DriverSettlementStatsResponse>(`/api/finance/driver-stats${search.toString() ? `?${search}` : ""}`);
  },
  financeDriverExpenses: (params?: { submit_status?: string; expense_kind?: string; driver_id?: string; date_from?: string; date_to?: string }) => {
    const search = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value) search.set(key, value);
    });
    return request<FinanceDriverExpenseResponse>(`/api/finance/driver-expenses${search.toString() ? `?${search}` : ""}`);
  },
  updateFinanceDriverExpense: (id: number, payload: Partial<FinanceDriverExpense>) =>
    request<{ expense: FinanceDriverExpense }>(`/api/finance/driver-expenses/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  updateSettlement: (id: number, payload: Partial<FinanceOrder>) =>
    request<{ order: Order }>(`/api/finance/orders/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  financeExportCsv: (params?: { settlement_status?: string; agency_name?: string; date_from?: string; date_to?: string }) => {
    const search = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value) search.set(key, value);
    });
    return requestText(`/api/finance/export${search.toString() ? `?${search}` : ""}`);
  },
  orders: async () => listFrom<Order>(await request<unknown>("/api/orders"), ["orders", "items", "data"]),
  drafts: async () => listFrom<Draft>(await request<unknown>("/api/parser/drafts"), ["drafts", "items", "data"]),
  parseText: (text: string) =>
    request<{ draft: Draft; parse_status?: string; parse_result?: unknown }>("/api/parser/text", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  parseBatchText: (text: string) =>
    request<{ drafts: Draft[]; count: number }>("/api/parser/text", {
      method: "POST",
      body: JSON.stringify({ text, batch: true }),
    }),
  updateDraft: (id: number, payload: Partial<Draft>) =>
    request<{ draft: Draft }>(`/api/parser/drafts/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  confirmDraft: (id: number) =>
    request<{ draft: Draft; order_id: number; order?: Order; already_confirmed?: boolean }>(
      `/api/parser/drafts/${id}/confirm`,
      { method: "POST" },
    ),
  unassignedOrders: async () =>
    listFrom<Order>(await request<unknown>("/api/dispatch/unassigned-orders"), ["orders", "items", "data"]),
  assignments: async () =>
    listFrom<Assignment>(await request<unknown>("/api/dispatch/assignments"), ["assignments", "items", "data"]),
  assignmentEvidence: async (assignmentId: number) =>
    request<{ evidence_chain: AssignmentEvidenceChain }>(`/api/assignments/${assignmentId}/evidence`),
  orderEvidence: async (orderId: number) =>
    request<{ evidence_chain: AssignmentEvidenceChain }>(`/api/orders/${orderId}/evidence`),
  drivers: async () => listFrom<Driver>(await request<unknown>("/api/dispatch/drivers"), ["drivers", "items", "data"]),
  vehicles: async () =>
    listFrom<Vehicle>(await request<unknown>("/api/dispatch/vehicles"), ["vehicles", "items", "data"]),
  resourceDrivers: async () =>
    listFrom<Driver>(await request<unknown>("/api/resources/drivers"), ["drivers", "items", "data"]),
  resourceVehicles: async () =>
    listFrom<Vehicle>(await request<unknown>("/api/resources/vehicles"), ["vehicles", "items", "data"]),
  resourceReminders: () =>
    request<{ alerts: ResourceAlert[]; total: number; expired: number; upcoming: number; maintenance: number; settings?: ReminderSettings }>("/api/resources/reminders"),
  reminderSettings: async () => (await request<{ settings: ReminderSettings }>("/api/settings/reminders")).settings,
  updateReminderSettings: (payload: Partial<ReminderSettings>) =>
    request<{ settings: ReminderSettings }>("/api/settings/reminders", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  createDriver: (payload: Partial<Driver>) =>
    request<{ driver: Driver }>("/api/resources/drivers", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateDriver: (id: number, payload: Partial<Driver>) =>
    request<{ driver: Driver }>(`/api/resources/drivers/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  deleteDriver: (id: number) =>
    request<{ deleted: boolean }>(`/api/resources/drivers/${id}`, {
      method: "DELETE",
    }),
  createVehicle: (payload: Partial<Vehicle>) =>
    request<{ vehicle: Vehicle }>("/api/resources/vehicles", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateVehicle: (id: number, payload: Partial<Vehicle>) =>
    request<{ vehicle: Vehicle }>(`/api/resources/vehicles/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  deleteVehicle: (id: number) =>
    request<{ deleted: boolean }>(`/api/resources/vehicles/${id}`, {
      method: "DELETE",
    }),
  assign: (orderIds: number[], driverId: number, vehicleId: number) =>
    request<{ success: boolean; assignment_ids?: number[]; updated_order_ids?: number[]; conflicts?: unknown[]; conflict?: unknown }>("/api/dispatch/assign", {
      method: "POST",
      body: JSON.stringify({ order_ids: orderIds, driver_id: driverId, vehicle_id: vehicleId }),
    }),
  dispatchRecommend: (orderIds: number[]) =>
    request<{ success: boolean; order_ids?: number[]; recommendations: DispatchRecommendation[]; error?: string }>("/api/dispatch/recommend", {
      method: "POST",
      body: JSON.stringify({ order_ids: orderIds }),
    }),
  cancelAssignment: (assignmentId: number) =>
    request<{ success: boolean; cancelled_assignment_id?: number; updated_order_id?: number; error?: string }>("/api/dispatch/cancel", {
      method: "POST",
      body: JSON.stringify({ assignment_id: assignmentId }),
    }),
  reassign: (orderIds: number[], driverId: number, vehicleId: number) =>
    request<{ success: boolean; new_assignment_ids?: number[]; cancelled_old_assignment_ids?: number[]; conflicts?: unknown[] }>(
      "/api/dispatch/reassign",
      {
        method: "POST",
        body: JSON.stringify({ order_ids: orderIds, new_driver_id: driverId, new_vehicle_id: vehicleId }),
      },
    ),
  routeSuggestion: (orderIds: number[]) =>
    request<{ orders: Order[]; links: Array<{ from_order_id: number; to_order_id: number; handoff: string }> }>(
      `/api/dispatch/route-suggestion?order_ids=${orderIds.join(",")}`,
    ),
  calendar: (view: "day" | "week" | "month", date: string) =>
    request<CalendarResponse>(`/api/calendar/dispatch?view=${view}&date=${date}`),
  driverReports: async () =>
    listFrom<DriverReport>(await request<unknown>("/api/driver/reports?driver_id=1"), ["reports", "items", "data"]),
  driverAssignments: async (driverId: number) =>
    listFrom<Assignment>(await request<unknown>(`/api/driver/assignments?driver_id=${driverId}`), ["assignments", "items", "data"]),
  driverDashboard: (driverId: number) =>
    request<{ today_order_count?: number; today_completed_count?: number; today_estimated_amount?: number }>(`/api/driver/dashboard?driver_id=${driverId}`),
  driverIncome: (driverId: number) =>
    request<{ today?: Record<string, number>; monthly?: Record<string, number> }>(`/api/driver/income?driver_id=${driverId}`),
  driverNotifications: async (driverId: number) =>
    listFrom<NotificationItem>(await request<unknown>(`/api/driver/notifications?driver_id=${driverId}`), ["notifications", "items", "data"]),
  driverSafetyAlerts: async () =>
    listFrom<DriverSafetyAlert>(await request<unknown>("/api/driver/safety-alerts"), ["alerts", "items", "data"]),
  fleetLatestLocations: async (params?: { driver_id?: string; online_status?: string; vehicle_status?: string; limit?: number }) => {
    const search = new URLSearchParams();
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value !== undefined && value !== "") search.set(key, String(value));
    });
    return listFrom<LocationLog>(await request<unknown>(`/api/fleet/latest-locations${search.toString() ? `?${search}` : ""}`), ["locations", "items", "data"]);
  },
};
