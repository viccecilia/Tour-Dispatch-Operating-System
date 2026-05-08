import type { CalendarItem, Vehicle } from "@/types/api";
import { shortRoute } from "@/lib/utils";

const hours = Array.from({ length: 24 }, (_, index) => `${String(index).padStart(2, "0")}:00`);

function minutes(time?: string) {
  if (!time) return 0;
  const [h, m] = time.split(":").map(Number);
  return (h || 0) * 60 + (m || 0);
}

function eventStyle(item: CalendarItem) {
  const start = minutes(item.start_time);
  const end = Math.max(minutes(item.end_time), start + 60);
  const left = (start / 1440) * 100;
  const width = Math.max(((end - start) / 1440) * 100, 6);
  const color = item.calendar_color || "#2563eb";
  return {
    left: `${left}%`,
    width: `${Math.min(width, 100 - left)}%`,
    borderColor: color,
    color,
    background: `${color}12`,
  };
}

export function CalendarMatrix({ vehicles, items }: { vehicles: Vehicle[]; items: CalendarItem[] }) {
  const vehicleRows = vehicles.length ? vehicles : uniqueVehiclesFromItems(items);

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[1180px] rounded-lg border border-border bg-white">
        <div className="grid grid-cols-[180px_1fr] border-b border-border">
          <div className="px-4 py-3 text-sm font-bold text-slate-700">车辆</div>
          <div className="grid" style={{ gridTemplateColumns: "repeat(24, minmax(0, 1fr))" }}>
            {hours.map((hour) => (
              <div key={hour} className="border-l border-border px-2 py-3 text-xs font-semibold text-slate-500">
                {hour}
              </div>
            ))}
          </div>
        </div>
        {vehicleRows.map((vehicle) => {
          const rowItems = items.filter((item) => item.vehicle_id === vehicle.id || item.plate_number === vehicle.plate_number);
          return (
            <div key={vehicle.id || vehicle.plate_number} className="grid min-h-24 grid-cols-[180px_1fr] border-b border-border last:border-b-0">
              <div className="border-r border-border px-4 py-4">
                <p className="text-sm font-bold text-slate-950">{vehicle.plate_number}</p>
                <p className="mt-1 text-xs text-slate-500">{vehicle.vehicle_type || "-"} · {vehicle.seat_count || "-"}座</p>
              </div>
              <div className="relative bg-[linear-gradient(to_right,#e2e8f0_1px,transparent_1px)] bg-[length:calc(100%/24)_100%]">
                {rowItems.map((item) => (
                  <div
                    key={`${item.assignment_id || item.id}-${item.order_id}`}
                    className="absolute top-3 h-16 overflow-hidden rounded-md border px-3 py-2 text-xs font-semibold shadow-sm"
                    style={eventStyle(item)}
                    title={`${item.start_time}-${item.end_time} ${shortRoute(item.pickup_location, item.dropoff_location)}`}
                  >
                    <p className="truncate">{item.start_time} {item.display_title || item.oid || item.order_id}</p>
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
