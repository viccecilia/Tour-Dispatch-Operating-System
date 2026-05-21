import type { CalendarItem, Vehicle } from "@/types/api";
import { shortRoute } from "@/lib/utils";

type CalendarView = "day" | "week" | "month";

const hours = Array.from({ length: 24 }, (_, index) => `${String(index).padStart(2, "0")}:00`);

function minutes(time?: string) {
  if (!time) return 0;
  const [h, m] = time.split(":").map(Number);
  return (h || 0) * 60 + (m || 0);
}

function toDate(value?: string) {
  if (!value) return null;
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function addDays(date: Date, days: number) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function isoDate(date: Date) {
  return date.toISOString().slice(0, 10);
}

function dayDiff(a: Date, b: Date) {
  const dayMs = 24 * 60 * 60 * 1000;
  return Math.round((a.getTime() - b.getTime()) / dayMs);
}

function buildDateColumns(startDate?: string, endDate?: string) {
  const start = toDate(startDate) || new Date();
  const end = toDate(endDate) || start;
  const length = Math.max(1, dayDiff(end, start) + 1);
  return Array.from({ length }, (_, index) => {
    const date = addDays(start, index);
    return {
      key: isoDate(date),
      label: `${String(date.getMonth() + 1).padStart(2, "0")}/${String(date.getDate()).padStart(2, "0")}`,
    };
  });
}

function eventStyle(item: CalendarItem, view: CalendarView, startDate?: string, columnCount = 24) {
  const color = item.calendar_color || "#2563eb";
  if (view !== "day") {
    const rangeStart = toDate(startDate) || toDate(item.order_date) || new Date();
    const eventStart = toDate(item.order_date) || rangeStart;
    const eventEnd = toDate(item.end_date || item.order_date) || eventStart;
    const startIndex = Math.max(0, Math.min(columnCount - 1, dayDiff(eventStart, rangeStart)));
    const endIndex = Math.max(startIndex, Math.min(columnCount - 1, dayDiff(eventEnd, rangeStart)));
    const left = (startIndex / columnCount) * 100;
    const width = ((endIndex - startIndex + 1) / columnCount) * 100;
    return {
      left: `${left}%`,
      width: `${Math.min(width, 100 - left)}%`,
      borderColor: color,
      color,
      background: `${color}12`,
    };
  }

  const start = minutes(item.start_time);
  const end = Math.max(minutes(item.end_time), start + 60);
  const left = (start / 1440) * 100;
  const width = Math.max(((end - start) / 1440) * 100, 6);
  return {
    left: `${left}%`,
    width: `${Math.min(width, 100 - left)}%`,
    borderColor: color,
    color,
    background: `${color}12`,
  };
}

export function CalendarMatrix({
  vehicles,
  items,
  view,
  startDate,
  endDate,
}: {
  vehicles: Vehicle[];
  items: CalendarItem[];
  view: CalendarView;
  startDate?: string;
  endDate?: string;
}) {
  const vehicleRows = vehicles.length ? vehicles : uniqueVehiclesFromItems(items);
  const dateColumns = buildDateColumns(startDate, endDate);
  const columns = view === "day" ? hours.map((hour) => ({ key: hour, label: hour })) : dateColumns;
  const gridTemplate = `repeat(${columns.length}, minmax(0, 1fr))`;
  const backgroundSize = `calc(100%/${columns.length}) 100%`;

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[1180px] rounded-lg border border-border bg-white">
        <div className="grid grid-cols-[180px_1fr] border-b border-border">
          <div className="px-4 py-3 text-sm font-bold text-slate-700">车辆</div>
          <div className="grid" style={{ gridTemplateColumns: gridTemplate }}>
            {columns.map((column) => (
              <div key={column.key} className="border-l border-border px-2 py-3 text-xs font-semibold text-slate-500">
                {column.label}
              </div>
            ))}
          </div>
        </div>
        {vehicleRows.map((vehicle) => {
          const rowItems = items
            .filter((item) => item.vehicle_id === vehicle.id || item.plate_number === vehicle.plate_number)
            .sort((a, b) => `${a.order_date || ""}${a.start_time || ""}`.localeCompare(`${b.order_date || ""}${b.start_time || ""}`));
          const rowHeight = Math.max(96, rowItems.length * 58 + 24);
          return (
            <div
              key={vehicle.id || vehicle.plate_number}
              className="grid grid-cols-[180px_1fr] border-b border-border last:border-b-0"
              style={{ minHeight: rowHeight }}
            >
              <div className="border-r border-border px-4 py-4">
                <p className="text-sm font-bold text-slate-950">{vehicle.plate_number}</p>
                <p className="mt-1 text-xs text-slate-500">{vehicle.vehicle_type || "-"} · {vehicle.seat_count || "-"}座</p>
              </div>
              <div
                className="relative bg-[linear-gradient(to_right,#e2e8f0_1px,transparent_1px)]"
                style={{ backgroundSize }}
              >
                {rowItems.map((item, index) => (
                  <div
                    key={`${item.assignment_id || item.id}-${item.order_id}`}
                    className="absolute h-12 overflow-hidden rounded-md border px-3 py-2 text-xs font-semibold shadow-sm"
                    style={{ ...eventStyle(item, view, startDate, columns.length), top: 12 + index * 58 }}
                    title={`${item.start_time}-${item.end_time} ${shortRoute(item.pickup_location, item.dropoff_location)}`}
                  >
                    <p className="truncate">
                      {view === "day" ? item.start_time : `${item.order_date?.slice(5)} ${item.start_time || ""}`} {item.display_title || item.oid || item.order_id}
                    </p>
                    <p className="mt-1 truncate font-medium">{shortRoute(item.pickup_location, item.dropoff_location)}</p>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function uniqueVehiclesFromItems(items: CalendarItem[]): Vehicle[] {
  const map = new Map<string, Vehicle>();
  items.forEach((item) => {
    const key = String(item.vehicle_id || item.plate_number || "unknown");
    if (!map.has(key)) {
      map.set(key, {
        id: item.vehicle_id || Number(key) || 0,
        plate_number: item.plate_number || "未分配车辆",
        vehicle_type: item.vehicle_type,
      });
    }
  });
  return Array.from(map.values());
}
