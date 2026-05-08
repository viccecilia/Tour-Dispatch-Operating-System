export type ApiOk<T> = T & { ok?: boolean; success?: boolean };

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
  execution?: Record<string, number>;
};

export type Order = {
  id: number;
  oid?: string;
  order_date?: string;
  start_time?: string;
  end_time?: string;
  pickup_location?: string;
  dropoff_location?: string;
  order_type?: string;
  vehicle_type?: string;
  passenger_count?: number;
  luggage_count?: number;
  guest_name?: string;
  guest_contact?: string;
  agency_name?: string;
  price?: number;
  remark?: string;
  dispatch_status?: string;
  settlement_status?: string;
  execution_status?: string;
  created_at?: string;
};

export type Draft = {
  id: number;
  raw_text: string;
  source_type?: string;
  parse_status?: string;
  order_date?: string;
  start_time?: string;
  end_time?: string;
  pickup_location?: string;
  dropoff_location?: string;
  order_type?: string;
  vehicle_type?: string;
  guest_name?: string;
  guest_contact?: string;
  agency_name?: string;
  price?: number;
  remark?: string;
};

export type Driver = {
  id: number;
  name: string;
  phone?: string;
  status?: string;
};

export type Vehicle = {
  id: number;
  plate_number: string;
  vehicle_type?: string;
  seat_count?: number;
  status?: string;
};

export type Assignment = {
  id?: number;
  assignment_id?: number;
  order_id: number;
  oid?: string;
  order_date?: string;
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
  items: CalendarItem[];
  vehicles: Vehicle[];
  drivers: Driver[];
  legend?: Array<{ key: string; label: string; color: string }>;
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
