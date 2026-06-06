export type ApiOk<T> = T & { ok?: boolean; success?: boolean };

export type AuthUser = {
  id: number;
  username: string;
  account_login?: string;
  company_code?: string;
  role: "admin" | "dispatcher" | "operations_manager" | "driver";
  display_name?: string;
  phone?: string;
  must_change_password?: boolean;
  profile_type?: string;
  profile_id?: number;
  wx_bind_status?: string;
  tenant_id: number;
  tenant?: {
    id: number;
    name: string;
    slug: string;
  };
};

export type AccountRole = "admin" | "dispatcher" | "operations_manager" | "driver";

export type ManagedAccount = {
  id: number;
  tenant_id?: number;
  username: string;
  account_login?: string;
  display_name?: string;
  phone?: string;
  role: AccountRole;
  role_label?: string;
  profile_type?: "operator" | "driver" | string;
  profile_id?: number;
  profile_label?: string;
  driver_code?: string;
  driver_record_status?: string;
  operator_code?: string;
  is_active: boolean;
  account_status?: "active" | "disabled" | string;
  wx_bind_status?: "bound" | "unbound" | string;
  wx_bound_at?: string;
  last_login_at?: string;
  password_changed_at?: string;
  must_change_password?: boolean;
  created_at?: string;
  updated_at?: string;
};

export type AccountRoleGroup = {
  role: AccountRole;
  label: string;
  total: number;
  active: number;
  disabled: number;
  wechat_bound: number;
  wechat_unbound: number;
  accounts: ManagedAccount[];
};

export type AccountOverview = {
  roles: AccountRoleGroup[];
  accounts: ManagedAccount[];
};

export type AttendanceRow = {
  date: string;
  driver_id: number;
  driver_name?: string;
  driver_code?: string;
  driver_phone?: string;
  vehicle_id?: number;
  vehicle_plate?: string;
  sleep_hours_reported?: number | null;
  depart_call_time?: string | null;
  depart_time?: string | null;
  return_time?: string | null;
  rest_hours_reported?: number | null;
  return_call_time?: string | null;
  constraint_hours?: number | null;
  previous_return_time?: string | null;
  rest_interval_hours?: number | null;
  sleep_risk_level?: "ok" | "warning" | "danger" | string;
  sleep_risk_message?: string;
  report_status?: "reported" | "inferred" | "missing" | string;
  assignment_count?: number;
};

export type AttendanceDaily = {
  date: string;
  summary: {
    total_drivers: number;
    departed: number;
    returned: number;
    sleep_risk: number;
    missing_report: number;
    average_constraint_hours: number;
  };
  rows: AttendanceRow[];
};

export type AttendanceLedger = {
  ok?: boolean;
  date_from: string;
  date_to: string;
  summary: {
    total_rows: number;
    date_from?: string;
    date_to?: string;
    departed: number;
    returned: number;
    sleep_risk: number;
    missing_report: number;
    average_constraint_hours: number;
  };
  rows: AttendanceRow[];
};

export type DashboardSummary = {
  today_orders?: number;
  assigned_orders?: number;
  in_service_orders?: number;
  completed_orders?: number;
  unassigned_orders?: number;
  pending_drafts?: number;
    unreported_orders?: number;
    assigned_unconfirmed_orders?: number;
    confirmed_driver_count?: number;
    pending_settlement_orders?: number;
  failed_drafts?: number;
    available_drivers?: number;
    available_vehicles?: number;
    outbound_vehicles?: number;
    in_service_vehicles?: number;
    returned_vehicles?: number;
    vehicle_status?: Record<string, number>;
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
  flight_number?: string;
  flight_date?: string;
  flight_airline?: string;
  flight_origin?: string;
  flight_destination?: string;
  flight_terminal?: string;
  flight_gate?: string;
  flight_status?: string;
  flight_scheduled_departure?: string;
  flight_scheduled_arrival?: string;
  flight_estimated_departure?: string;
  flight_estimated_arrival?: string;
  flight_actual_departure?: string;
  flight_actual_arrival?: string;
  flight_provider?: string;
  flight_last_checked_at?: string;
  flight_manual_note?: string;
  guest_name?: string;
  guest_contact?: string;
  guide_name?: string;
  guide_phone?: string;
  guide_wechat?: string;
  guide_line?: string;
  guide_whatsapp?: string;
  itinerary_pdf_url?: string;
  itinerary_pdf_name?: string;
  agency_id?: number;
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
  source_channel?: string;
  execution_status?: string;
  agency_settlement_status?: string;
  payment_amount_jpy?: number;
  carrier_payment_requested_at?: string;
  carrier_payment_request_note?: string;
  agency_payment_receipt_url?: string;
  agency_payment_receipt_name?: string;
  agency_payment_uploaded_at?: string;
  carrier_payment_confirmed_at?: string;
  carrier_payment_confirmed_by?: string;
  assignment_id?: number;
  assignment_status?: string;
  assigned_at?: string;
  driver_id?: number;
  driver_name?: string;
  driver_phone?: string;
  assigned_driver_code?: string;
  assigned_driver_name?: string;
  assigned_driver_language?: string;
  vehicle_id?: number;
  plate_number?: string;
  plate_no?: string;
  assigned_vehicle_type?: string;
  seat_count?: number;
  assigned_vehicle_color?: string;
  driver_latitude?: number;
  driver_longitude?: number;
  driver_location_text?: string;
  driver_location_reported_at?: string;
  latest_change_request_id?: number;
  latest_change_request_type?: string;
  latest_change_request_status?: string;
  latest_cancel_fee_percent?: number;
  latest_cancel_fee_amount_jpy?: number;
  latest_change_request_policy?: string;
  auction_listing_id?: number;
  auction_listing_code?: string;
  auction_publish_round?: number;
  auction_status?: "listed" | "bidding" | "claimed" | "expired" | "cancelled" | string;
  auction_start_price_jpy?: number;
  auction_buyout_price_jpy?: number;
  auction_current_bid_jpy?: number;
  auction_bid_count?: number;
  auction_published_at?: string;
  auction_expires_at?: string;
  auction_duration_hours?: number;
  carrier_tenant_id?: number;
  carrier_company_name?: string;
  carrier_company_code?: string;
  carrier_claimed_at?: string;
  carrier_claim_serial?: number;
  created_at?: string;
};

export type AuctionListing = {
  id: number;
  order_id: number;
  owner_tenant_id?: number;
  seller_tenant_id?: number;
  buyer_tenant_id?: number;
  status: "listed" | "bidding" | "claimed" | "cancelled" | "sold" | string;
  start_price_jpy: number;
  buyout_price_jpy: number;
  current_bid_jpy?: number;
  bid_count?: number;
  listing_code?: string;
  publish_round?: number;
  published_by_user_id?: number;
  published_by_name?: string;
  published_at?: string;
  expires_at?: string;
  auction_duration_hours?: number;
  has_itinerary_pdf?: boolean;
  sold_at?: string;
  cancelled_at?: string;
  note?: string;
  oid?: string;
  order_date?: string;
  end_date?: string;
  start_time?: string;
  end_time?: string;
  pickup_location?: string;
  dropoff_location?: string;
  order_type?: string;
  vehicle_type?: string;
  flight_number?: string;
  flight_date?: string;
  flight_airline?: string;
  flight_origin?: string;
  flight_destination?: string;
  flight_terminal?: string;
  flight_gate?: string;
  flight_status?: string;
  flight_scheduled_departure?: string;
  flight_scheduled_arrival?: string;
  flight_estimated_departure?: string;
  flight_estimated_arrival?: string;
  flight_actual_departure?: string;
  flight_actual_arrival?: string;
  flight_provider?: string;
  flight_last_checked_at?: string;
  flight_manual_note?: string;
  agency_name?: string;
  price?: number;
  price_jpy?: number;
  remark?: string;
  seller_company_name?: string;
  seller_company_code?: string;
  buyer_company_name?: string;
  buyer_company_code?: string;
  execution_status?: string;
  settlement_status?: string;
  agency_settlement_status?: string;
  payment_amount_jpy?: number;
  carrier_payment_requested_at?: string;
  carrier_payment_request_note?: string;
  agency_payment_receipt_url?: string;
  agency_payment_receipt_name?: string;
  agency_payment_uploaded_at?: string;
  carrier_payment_confirmed_at?: string;
  carrier_payment_confirmed_by?: string;
};

export type AgencyOrderChangeRequest = {
  id: number;
  tenant_id?: number;
  agency_id?: number;
  agency_name?: string;
  order_id: number;
  oid?: string;
  request_type: "modify" | "cancel" | string;
  status: "pending" | "approved" | "rejected" | string;
  requested_changes_json?: string;
  requested_changes?: Partial<Order>;
  reason?: string;
  force_cancel?: number | boolean;
  fee_percent?: number;
  fee_amount_jpy?: number;
  free_quota_used?: number;
  policy_message?: string;
  carrier_note?: string;
  reviewed_by?: string;
  reviewed_at?: string;
  created_at?: string;
  order_date?: string;
  start_time?: string;
  end_time?: string;
  pickup_location?: string;
  dropoff_location?: string;
  vehicle_type?: string;
  price?: number;
  price_jpy?: number;
  dispatch_status?: string;
  execution_status?: string;
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
  license_file_url?: string;
  health_check_file_url?: string;
  license_expires_at?: string;
  medical_check_expires_at?: string;
  alerts?: ResourceAlert[];
  alert_level?: string;
};

export type Vehicle = {
  id: number;
  plate_number: string;
  plate_no?: string;
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
    vehicle_status?: string;
    price?: number;
  dispatch_status?: string;
  settlement_status?: string;
  execution_status?: string;
  calendar_status?: string;
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
  driver_phone?: string;
  plate_number?: string;
  vehicle_type?: string;
  vehicle_status?: string;
  oid?: string;
  pickup_location?: string;
  dropoff_location?: string;
  order_date?: string;
  start_time?: string;
  end_time?: string;
  dispatch_status?: string;
  settlement_status?: string;
  assignment_status?: string;
  execution_status?: string;
  order_execution_status?: string;
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
  role: AccountRole;
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
  contact_wechat?: string;
  contact_line?: string;
  contact_whatsapp?: string;
  contact_email?: string;
  fax?: string;
  status?: "active" | "inactive" | string;
  remark?: string;
  portal_code?: string;
  is_portal_enabled?: number | boolean;
  created_at?: string;
  updated_at?: string;
};

export type CompanyRegistration = {
  id: number;
  managing_tenant_id?: number;
  company_type: "carrier" | "agency";
  tenant_id?: number;
  agency_id?: number;
  company_code: string;
  company_name: string;
  registered_name?: string;
  corporate_number?: string;
  invoice_registration_number?: string;
  business_license_number?: string;
  representative_name?: string;
  postal_code?: string;
  address?: string;
  contact_name?: string;
  contact_phone?: string;
  contact_email?: string;
  bank_name?: string;
  bank_branch?: string;
  bank_account_type?: string;
  bank_account_number?: string;
  bank_account_holder?: string;
  registry_certificate_url?: string;
  registry_certificate_name?: string;
  business_license_url?: string;
  business_license_name?: string;
  bank_book_url?: string;
  bank_book_name?: string;
  status?: "draft" | "submitted" | "approved" | "rejected" | "inactive" | string;
  review_note?: string;
  tenant_name?: string;
  tenant_slug?: string;
  agency_name?: string;
  agency_code?: string;
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
  driver_expense_pending_count?: number;
  driver_expense_pending_amount?: number;
  driver_expense_confirmed_count?: number;
  driver_expense_confirmed_amount?: number;
  driver_expense_rejected_count?: number;
  driver_expense_rejected_amount?: number;
  driver_advance_pending_amount?: number;
  driver_collect_pending_amount?: number;
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

export type FinanceDriverExpense = {
  id: number;
  driver_id?: number;
  driver_name?: string;
  driver_code?: string;
  assignment_id?: number;
  order_id?: number;
  oid?: string;
  order_date?: string;
  start_time?: string;
  end_time?: string;
  pickup_location?: string;
  dropoff_location?: string;
  order_type?: string;
  vehicle_id?: number;
  vehicle_plate?: string;
  expense_kind: "advance" | "collect" | string;
  kind_label?: string;
  category: string;
  amount: number;
  currency?: string;
  submit_status: string;
  status_label?: string;
  receipt_photo_url?: string;
  note?: string;
  submitted_at?: string;
  confirmed_at?: string;
  created_at?: string;
  is_pending_finance?: boolean;
};

export type FinanceDriverExpenseResponse = {
  expenses: FinanceDriverExpense[];
  summary: Record<string, number>;
  filters?: Record<string, unknown>;
};

export type EvidenceTimelineItem = {
  kind: "report" | "workflow" | "photo" | "expense" | string;
  id?: number;
  assignment_id?: number;
  order_id?: number;
  driver_id?: number;
  label?: string;
  event_time?: string;
  status?: string;
  location_text?: string;
  latitude?: number;
  longitude?: number;
  note?: string;
  file_url?: string;
  amount?: number;
  currency?: string;
};

export type AssignmentEvidenceChain = {
  assignment?: Assignment & {
    guest_name?: string;
    guest_contact?: string;
    remark?: string;
    assignment_status?: string;
  };
  timeline: EvidenceTimelineItem[];
  evidence: Array<{
    id: number;
    evidence_type: string;
    label?: string;
    file_name?: string;
    file_url?: string;
    note?: string;
    uploaded_at?: string;
  }>;
  expenses: FinanceDriverExpense[];
  reports: DriverReport[];
  workflow_events: Array<Record<string, unknown>>;
  download_files: Array<{ id?: number; kind?: string; label?: string; url?: string; file_name?: string }>;
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
  driver_expense_summary?: Record<string, number>;
};
