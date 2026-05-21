export type ApiOk<T> = T & { ok?: boolean; success?: boolean };

export type AuthUser = {
  id: number;
  username: string;
  role: "admin" | "dispatcher" | "driver";
  display_name?: string;
  tenant_id: number;
  tenant?: {
    id: number;
    name: string;
    slug: string;
  };
};

export type DashboardSummary = {
  today_orders?: number;
  assigned_orders?: number;
  in_service_orders?: number;
  completed_orders?: number;
  unassigned_orders?: number;
  pending_drafts?: number;
  unreported_orders?: number;
  pending_settlement_orders?: number;
  failed_drafts?: number;
  available_drivers?: number;
  available_vehicles?: number;
  resource_alerts?: number;
  resource_expired_alerts?: number;
  resource_upcoming_alerts?: number;
  resource_maintenance_alerts?: number;
  open_incidents?: number;
  delay_incidents?: number;
  complaint_incidents?: number;
  accident_incidents?: number;
  closed_incidents_today?: number;
  high_priority_incidents?: number;
  recent_incidents?: Incident[];
  execution?: Record<string, number>;
};

export type Order = {
  id: number;
  oid?: string;
  order_date?: string;
  end_date?: string;
  start_time?: string;
  end_time?: string;
  pickup_location?: string;
  dropoff_location?: string;
  order_type?: string;
  vehicle_type?: string;
  order_note_code?: string;
  order_source?: string;
  vehicle_class?: string;
  vehicle_type_code?: string;
  plate_short_code?: string;
  driver_code?: string;
  driver_language?: string;
  vehicle_color?: string;
  snow_tire?: string;
  passenger_count?: number;
  luggage_count?: number;
  guest_name?: string;
  guest_contact?: string;
  agency_name?: string;
  price?: number;
  price_rmb?: number;
  price_jpy?: number;
  fee_remark?: string;
  collection_amount_jpy?: number;
  parking_fee_jpy?: number;
  other_fee_jpy?: number;
  driver_salary_jpy?: number;
  remark?: string;
  dispatch_status?: string;
  settlement_status?: string;
  execution_status?: string;
  created_at?: string;
};

export type Draft = {
  id: number;
  oid?: string;
  raw_text: string;
  source_type?: string;
  parse_status?: string;
  order_date?: string;
  end_date?: string;
  start_time?: string;
  end_time?: string;
  pickup_location?: string;
  dropoff_location?: string;
  order_type?: string;
  vehicle_type?: string;
  order_note_code?: string;
  order_source?: string;
  vehicle_class?: string;
  vehicle_type_code?: string;
  plate_short_code?: string;
  driver_code?: string;
  driver_language?: string;
  vehicle_color?: string;
  snow_tire?: string;
  passenger_count?: number;
  luggage_count?: number;
  guest_name?: string;
  guest_contact?: string;
  agency_name?: string;
  price?: number;
  price_rmb?: number;
  price_jpy?: number;
  fee_remark?: string;
  collection_amount_jpy?: number;
  parking_fee_jpy?: number;
  other_fee_jpy?: number;
  driver_salary_jpy?: number;
  remark?: string;
  confirmed_order_id?: number;
  parse_result?: Record<string, unknown>;
};

export type Driver = {
  id: number;
  name: string;
  phone?: string;
  status?: string;
  driver_status?: string;
  driver_language?: string;
  language?: string;
  driver_code?: string;
  office?: string;
  driver_external_id?: string;
  license_number?: string;
  residence_status?: string;
  residence_due_date?: string;
  health_check_remaining_days?: number;
  wechat?: string;
  line?: string;
  whatsapp?: string;
  email?: string;
  license_due_date?: string;
  health_check_due_date?: string;
  license_expires_at?: string;
  medical_check_expires_at?: string;
  alerts?: ResourceAlert[];
  alert_level?: string;
};

export type Vehicle = {
  id: number;
  plate_number: string;
  vehicle_type?: string;
  seat_count?: number;
  status?: string;
  vehicle_color?: string;
  color?: string;
  snow_tire?: string;
  plate_short_code?: string;
  vehicle_type_code?: string;
  vehicle_group?: string;
  first_registration_date?: string;
  company_registration_date?: string;
  last_inspection_date?: string;
  next_inspection_due_date?: string;
  shaken_due_date?: string;
  insurance_due_date?: string;
  inspection_expires_at?: string;
  insurance_expires_at?: string;
  maintenance_status?: string;
  inspection_records?: VehicleInspectionRecord[];
  alerts?: ResourceAlert[];
  alert_level?: string;
};

export type VehicleInspectionRecord = {
  id?: number;
  vehicle_id?: number;
  inspection_type: "inspection" | "shaken" | string;
  inspection_date: string;
  source?: string;
  note?: string;
  created_at?: string;
};

export type ResourceAlert = {
  type?: "driver" | "vehicle";
  id?: number;
  name?: string;
  field: string;
  label: string;
  status: "expired" | "upcoming" | "maintenance" | "invalid";
  date?: string;
  days_left?: number | null;
  message: string;
};

export type ReminderSettings = {
  vehicle_inspection_days: number;
  vehicle_shaken_days: number;
  driver_health_check_days: number;
  driver_license_days: number;
};

export type DispatchRecommendation = {
  driver: Driver;
  vehicle: Vehicle;
  score: number;
  reasons: string[];
  conflicts?: unknown[];
};

export type Assignment = {
  id?: number;
  assignment_id?: number;
  order_id: number;
  oid?: string;
  order_date?: string;
  end_date?: string;
  start_time?: string;
  end_time?: string;
  pickup_location?: string;
  dropoff_location?: string;
  order_type?: string;
  vehicle_type?: string;
  driver_id?: number;
  driver_name?: string;
  vehicle_id?: number;
  plate_number?: string;
  price?: number;
  dispatch_status?: string;
  settlement_status?: string;
  execution_status?: string;
  latest_report?: string;
  report_time?: string;
  latest_report_type?: string;
  latest_report_time?: string;
  latest_location_text?: string;
  status?: string;
};

export type CalendarItem = Assignment & {
  calendar_color?: string;
  display_title?: string;
  display_subtitle?: string;
};

export type CalendarResponse = {
  ok: boolean;
  view: string;
  date: string;
  start_date?: string;
  end_date?: string;
  items: CalendarItem[];
  vehicles: Vehicle[];
  drivers: Driver[];
  legend?: Array<{ key: string; label: string; color: string }>;
};

export type AuditLog = {
  id: number;
  tenant_id?: number;
  actor?: string;
  action: string;
  entity_type: string;
  entity_id?: string;
  summary?: string;
  source_path?: string;
  created_at?: string;
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
  diff?: Record<string, { before?: unknown; after?: unknown }>;
};

export type DataAnomalyIssue = {
  code: string;
  severity: "low" | "medium" | "high" | string;
  title: string;
  count: number;
  examples: Array<Record<string, unknown>>;
};

export type DataAnomalyScan = {
  id?: number;
  scan_id?: number;
  issue_count: number;
  category_count?: number;
  issues?: DataAnomalyIssue[];
  result?: {
    issue_count?: number;
    category_count?: number;
    issues?: DataAnomalyIssue[];
  };
  created_at?: string;
};

export type DriverReport = {
  id: number;
  assignment_id: number;
  order_id: number;
  driver_id: number;
  report_type: string;
  report_status?: string;
  report_time?: string;
  location_text?: string;
  note?: string;
};

export type LocationLog = {
  id: number;
  driver_id: number;
  vehicle_id?: number;
  assignment_id?: number;
  order_id?: number;
  latitude?: number;
  longitude?: number;
  location_text?: string;
  source?: string;
  reported_at?: string;
  driver_name?: string;
  plate_number?: string;
  vehicle_type?: string;
  oid?: string;
  pickup_location?: string;
  dropoff_location?: string;
  order_date?: string;
  start_time?: string;
  end_time?: string;
  execution_status?: string;
  online_status?: "online" | "stale" | "unknown";
};

export type DriverSafetyAlert = {
  alert_type: "incident" | "stale_location" | string;
  incident_id?: number;
  assignment_id?: number;
  order_id?: number;
  driver_id?: number;
  driver_name?: string;
  plate_number?: string;
  oid?: string;
  incident_type?: string;
  severity?: "low" | "medium" | "high" | "critical" | string;
  title?: string;
  description?: string;
  created_at?: string;
  reported_at?: string;
  location_text?: string;
  pickup_location?: string;
  dropoff_location?: string;
  execution_status?: string;
};

export type Incident = {
  id: number;
  order_id?: number;
  assignment_id?: number;
  incident_type: "exception" | "delay" | "complaint" | "accident" | string;
  severity?: "low" | "medium" | "high" | "critical" | string;
  status?: "open" | "processing" | "closed" | string;
  title: string;
  description?: string;
  owner?: string;
  delay_minutes?: number;
  complaint_contact?: string;
  accident_location?: string;
  resolution?: string;
  created_at?: string;
  closed_at?: string;
  updated_at?: string;
  oid?: string;
  order_date?: string;
  start_time?: string;
  end_time?: string;
  pickup_location?: string;
  dropoff_location?: string;
  dispatch_status?: string;
  execution_status?: string;
  driver_name?: string;
  plate_number?: string;
};

export type IncidentSummary = {
  open_incidents: number;
  delay_incidents: number;
  complaint_incidents: number;
  accident_incidents: number;
  closed_incidents_today: number;
  high_priority_incidents: number;
  recent_incidents: Incident[];
};

export type Plan = {
  id: number;
  code: "free" | "plus" | "pro" | string;
  name: string;
  monthly_price: number;
  features: Record<string, boolean>;
  limits: Record<string, number>;
  status?: string;
};

export type Subscription = {
  id: number;
  tenant_id: number;
  plan_code: string;
  status: string;
  started_at?: string;
  expires_at?: string;
  plan: {
    code: string;
    name: string;
    monthly_price: number;
    features: Record<string, boolean>;
    limits: Record<string, number>;
  };
};

export type UsageSummary = {
  month: string;
  actual: Record<string, number>;
  usage_events: Array<{ feature: string; quantity: number }>;
  limits: Record<string, number>;
  limit_status: Record<string, { value: number; limit: number | null; percent: number; exceeded: boolean }>;
};

export type BillingOverview = {
  subscription: Subscription;
  plans: Plan[];
  usage: UsageSummary;
  feature_flags: Record<string, boolean>;
};

export type Department = {
  id: number;
  tenant_id?: number;
  name: string;
  description?: string;
  status?: string;
  team_count?: number;
  member_count?: number;
};

export type Team = {
  id: number;
  tenant_id?: number;
  department_id?: number;
  department_name?: string;
  name: string;
  description?: string;
  status?: string;
  member_count?: number;
};

export type OrgMember = {
  id: number;
  tenant_id?: number;
  username: string;
  role: "admin" | "dispatcher" | "driver";
  display_name?: string;
  is_active?: number | boolean;
  profile_id?: number;
  department_id?: number;
  department_name?: string;
  team_id?: number;
  team_name?: string;
  title?: string;
  phone?: string;
  invite_status?: string;
  invited_at?: string;
  disabled_at?: string;
  permissions?: string[];
};

export type OrgOverview = {
  departments: Department[];
  teams: Team[];
  members: OrgMember[];
  role_permissions: Record<string, string[]>;
  summary: {
    departments: number;
    teams: number;
    members: number;
    active_members: number;
    disabled_members: number;
  };
};

export type AnalyticsTrendPoint = {
  date: string;
  order_count: number;
  revenue: number;
  assigned_count: number;
  completed_count: number;
};

export type AgencyRevenue = {
  agency_name: string;
  order_count: number;
  revenue: number;
  pending_amount: number;
  assigned_count: number;
};

export type DriverPerformance = {
  driver_id?: number;
  driver_name?: string;
  driver_code?: string;
  rank?: number;
  order_count: number;
  revenue: number;
  driver_income?: number;
  completed_count: number;
  ontime_count?: number;
  incident_count: number;
  complaint_count?: number;
  completion_rate: number;
  ontime_rate?: number;
  incident_rate?: number;
  complaint_rate?: number;
};

export type VehicleUtilization = {
  vehicle_id?: number;
  plate_number?: string;
  vehicle_type?: string;
  order_count: number;
  revenue: number;
  time_ranges?: string;
  busy_hours: number;
  utilization_rate: number;
};

export type AnalyticsSummary = {
  date_from: string;
  date_to: string;
  kpis: {
    order_count: number;
    revenue: number;
    assigned_count: number;
    completed_count: number;
    completion_rate: number;
    incident_count: number;
    open_incident_count: number;
    incident_rate: number;
    driver_count?: number;
    avg_driver_completion_rate?: number;
    avg_driver_ontime_rate?: number;
    unsettled_count: number;
    missing_price_count: number;
  };
  trend: AnalyticsTrendPoint[];
  agency_revenue: AgencyRevenue[];
  driver_performance: DriverPerformance[];
  vehicle_utilization: VehicleUtilization[];
};

export type NotificationItem = {
  id: number;
  notification_type: string;
  title: string;
  body?: string;
  priority?: "low" | "normal" | "high" | "critical" | string;
  status?: "unread" | "read" | string;
  target_role?: string;
  link?: string;
  source_type?: string;
  source_id?: string;
  created_at?: string;
  read_at?: string;
};

export type NotificationSummary = {
  total: number;
  unread: number;
  urgent: number;
  latest: NotificationItem[];
};

export type Agency = {
  id: number;
  tenant_id?: number;
  agency_code?: string;
  company_name?: string;
  name: string;
  address?: string;
  contact_name?: string;
  contact_phone?: string;
  responsible_person?: string;
  contact_email?: string;
  fax?: string;
  status?: "active" | "inactive" | string;
  remark?: string;
  portal_code?: string;
  is_portal_enabled?: number | boolean;
  created_at?: string;
  updated_at?: string;
};

export type AgencyPortalAgency = {
  id: number;
  tenant_id: number;
  name: string;
  contact_name?: string;
  contact_phone?: string;
};

export type AgencyPortalSession = {
  token: string;
  agency: AgencyPortalAgency;
};

export type WorkflowRule = {
  id: number;
  code: string;
  name: string;
  trigger_type: string;
  condition_json: Record<string, unknown>;
  action_type: "notify" | "mark_exception" | "dispatch_suggestion" | string;
  action_json: Record<string, unknown>;
  enabled: boolean;
  created_at?: string;
  updated_at?: string;
};

export type WorkflowRun = {
  id: number;
  rule_id?: number;
  code?: string;
  name?: string;
  action_count: number;
  result_json?: string;
  result?: Record<string, unknown>;
  created_at?: string;
};

export type WorkflowRunResult = {
  success: boolean;
  executed_rules: number;
  total_actions: number;
  results: Array<{ rule_code: string; action_type?: string; action_count: number; items?: unknown[] }>;
};

export type CopilotSuggestion = {
  priority: string;
  title: string;
  text: string;
  reason: string;
  link?: string;
};

export type CopilotSummary = {
  date: string;
  operations_summary: string;
  metrics: Record<string, number>;
  risk_orders: Array<Record<string, unknown>>;
  unassigned_reminders: Array<Record<string, unknown>>;
  driver_exception_summary: Array<Record<string, unknown>>;
  open_incidents: Array<Record<string, unknown>>;
  urgent_notifications: Array<Record<string, unknown>>;
  suggestions: CopilotSuggestion[];
  explainability: string[];
};

export type FinanceGroup = {
  agency_name?: string;
  driver_name?: string;
  plate_number?: string;
  order_count: number;
  total_amount: number;
  pending_amount: number;
  settled_amount?: number;
};

export type FinanceOrder = {
  id: number;
  order_id?: number;
  oid?: string;
  order_date?: string;
  end_date?: string;
  start_time?: string;
  end_time?: string;
  pickup_location?: string;
  dropoff_location?: string;
  agency_name?: string;
  agency_id?: number;
  agency_code?: string;
  driver_id?: number;
  driver_name?: string;
  vehicle_id?: number;
  vehicle_plate?: string;
  plate_number?: string;
  vehicle_type?: string;
  order_type?: string;
  execution_status?: string;
  execution_group?: string;
  price?: number;
  price_jpy?: number;
  driver_advance_amount?: number;
  driver_collect_amount?: number;
  driver_settlement_amount?: number;
  driver_settlement_status?: string;
  driver_settlement_note?: string;
  agency_settlement_status?: string;
  fee_remark?: string;
  guest_name?: string;
  guest_contact?: string;
  remark?: string;
  settlement_status?: string;
  dispatch_status?: string;
};

export type FinanceLedgerSummary = {
  total_orders: number;
  total_amount: number;
  agency_pending_amount: number;
  agency_settled_amount: number;
  driver_pending_amount: number;
  driver_settled_amount: number;
  driver_advance_amount: number;
  driver_collect_amount: number;
};

export type FinanceLedger = {
  orders: FinanceOrder[];
  summary: FinanceLedgerSummary;
  filters?: Record<string, unknown>;
};

export type DriverSettlementStat = {
  driver_id?: number;
  driver_name?: string;
  completed_order_count: number;
  airport_order_count: number;
  charter_order_count: number;
  other_order_count: number;
  total_order_amount: number;
  driver_advance_amount: number;
  driver_collect_amount: number;
  pending_driver_settlement_amount: number;
  settled_driver_settlement_amount: number;
};

export type DriverSettlementStatsResponse = {
  stats: DriverSettlementStat[];
  summary: Record<string, number>;
};

export type FinanceSummary = {
  date: string;
  order_count: number;
  total_amount: number;
  pending_amount: number;
  settled_amount: number;
  today_amount: number;
  missing_price_orders: number;
  by_agency: FinanceGroup[];
  by_driver: FinanceGroup[];
  by_vehicle: FinanceGroup[];
  orders: FinanceOrder[];
  pending_orders: FinanceOrder[];
};
