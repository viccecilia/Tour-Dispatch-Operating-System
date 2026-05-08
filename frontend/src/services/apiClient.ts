import type {
  Assignment,
  CalendarResponse,
  DashboardSummary,
  Draft,
  Driver,
  DriverReport,
  Order,
  Vehicle,
} from "@/types/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:18765";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    ...init,
  });

  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
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
  dashboardSummary: () => request<DashboardSummary>("/api/dashboard/summary"),
  orders: async () => listFrom<Order>(await request<unknown>("/api/orders"), ["orders", "items", "data"]),
  drafts: async () => listFrom<Draft>(await request<unknown>("/api/parser/drafts"), ["drafts", "items", "data"]),
  unassignedOrders: async () =>
    listFrom<Order>(await request<unknown>("/api/dispatch/unassigned-orders"), ["orders", "items", "data"]),
  assignments: async () =>
    listFrom<Assignment>(await request<unknown>("/api/dispatch/assignments"), ["assignments", "items", "data"]),
  drivers: async () => listFrom<Driver>(await request<unknown>("/api/dispatch/drivers"), ["drivers", "items", "data"]),
  vehicles: async () =>
    listFrom<Vehicle>(await request<unknown>("/api/dispatch/vehicles"), ["vehicles", "items", "data"]),
  assign: (orderIds: number[], driverId: number, vehicleId: number) =>
    request<{ success: boolean; assignment_ids?: number[]; conflict?: unknown }>("/api/dispatch/assign", {
      method: "POST",
      body: JSON.stringify({ order_ids: orderIds, driver_id: driverId, vehicle_id: vehicleId }),
    }),
  calendar: (view: "day" | "week" | "month", date: string) =>
    request<CalendarResponse>(`/api/calendar/dispatch?view=${view}&date=${date}`),
  driverReports: async () =>
    listFrom<DriverReport>(await request<unknown>("/api/driver/reports?driver_id=1"), ["reports", "items", "data"]),
};
