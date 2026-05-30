import { useState, type MouseEvent } from "react";
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

function eventColor(item: CalendarItem) {
  const status = String(item.calendar_status || item.execution_status || item.dispatch_status || item.status || "").toLowerCase();
  if (status.includes("exception") || status.includes("risk") || status.includes("cancel")) return "#ef4444";
  if (status.includes("unconfirmed")) return "#d97706";
  if (status.includes("unassigned")) return "#dc2626";
  if (status.includes("unsettled") || status.includes("pending")) return "#7c2d12";
  if (status.includes("settled")) return "#059669";
  if (status.includes("completed") || status.includes("returned")) return "#16a34a";
  if (status.includes("in_service") || status.includes("service")) return "#7c3aed";
  if (status.includes("assigned")) return "#2563eb";
  return item.calendar_color || "#2563eb";
}

function eventStyle(item: CalendarItem, view: CalendarView, startDate?: string, columnCount = 24) {
  const color = eventColor(item);
  const startMinute = minutes(item.start_time);
  const endMinute = Math.max(minutes(item.end_time), startMinute + 60);
  const base = {
    background: color,
    boxShadow: `0 8px 18px ${color}30, inset 0 -15px 0 rgba(0, 0, 0, 0.10)`,
  };
  if (view !== "day") {
    const rangeStart = toDate(startDate) || toDate(item.order_date) || new Date();
    const eventStart = toDate(item.order_date) || rangeStart;
    const startIndex = Math.max(0, Math.min(columnCount - 1, dayDiff(eventStart, rangeStart)));
    const dayWidth = 100 / columnCount;
    const left = startIndex * dayWidth + (startMinute / 1440) * dayWidth;
    const width = Math.max(((endMinute - startMinute) / 1440) * dayWidth, Math.min(dayWidth * 0.22, 2.8));
    return {
      ...base,
      left: `${left}%`,
      width: `${Math.min(width, 100 - left)}%`,
    };
  }

  const left = (startMinute / 1440) * 100;
  const width = Math.max(((endMinute - startMinute) / 1440) * 100, 6);
  return {
    ...base,
    left: `${left}%`,
    width: `${Math.min(width, 100 - left)}%`,
  };
}

function eventStatusLabel(item: CalendarItem) {
  const status = String(item.calendar_status || item.execution_status || item.dispatch_status || item.status || "").toLowerCase();
  if (status.includes("unconfirmed")) return "未确认";
  if (status.includes("unassigned")) return "未派车";
  if (status.includes("unsettled") || status.includes("pending")) return "未结算";
  if (status.includes("assigned")) return "已派车";
  if (status.includes("completed")) return "已完成";
  if (status.includes("settled")) return "已结算";
  if (status.includes("exception") || status.includes("risk")) return "异常";
  return status || "订单";
}

function eventTooltip(item: CalendarItem) {
  return [
    `订单：${item.oid || item.order_id || item.id || "-"}`,
    `时间：${item.order_date || "-"} ${item.start_time || "--:--"}-${item.end_time || "--:--"}`,
    `路线：${shortRoute(item.pickup_location, item.dropoff_location)}`,
    `司机：${item.driver_name || "未派司机"}`,
    `车辆：${item.plate_number || "未派车辆"}`,
    `状态：${eventStatusLabel(item)}`,
    item.order_type ? `类型：${item.order_type}` : "",
    item.vehicle_type ? `车型：${item.vehicle_type}` : "",
    item.price ? `金额：${item.price}` : "",
  ].filter(Boolean).join("\n");
}

function tooltipLines(item: CalendarItem) {
  return eventTooltip(item).split("\n");
}

function itemKey(item: CalendarItem) {
  return `${item.assignment_id || item.id || "item"}-${item.order_id || item.oid || ""}-${item.order_date || ""}-${item.start_time || ""}`;
}

function layoutLanes(items: CalendarItem[], view: CalendarView) {
  const lanesByDate = new Map<string, number[]>();
  const laneByKey = new Map<string, number>();
  let maxLane = 0;
  items.forEach((item) => {
    const dateKey = view === "day" ? "day" : item.order_date || "";
    const start = minutes(item.start_time);
    const end = Math.max(minutes(item.end_time), start + 60);
    const lanes = lanesByDate.get(dateKey) || [];
    let lane = lanes.findIndex((lastEnd) => lastEnd <= start);
    if (lane < 0) {
      lane = lanes.length;
      lanes.push(end);
    } else {
      lanes[lane] = end;
    }
    lanesByDate.set(dateKey, lanes);
    laneByKey.set(itemKey(item), lane);
    maxLane = Math.max(maxLane, lane + 1);
  });
  return { laneByKey, laneCount: maxLane };
}

export function CalendarMatrix({
  vehicles,
  items,
  view,
  startDate,
  endDate,
  onEditItem,
  onCreateSlot,
}: {
  vehicles: Vehicle[];
  items: CalendarItem[];
  view: CalendarView;
  startDate?: string;
  endDate?: string;
  onEditItem?: (item: CalendarItem) => void;
  onCreateSlot?: (slot: { vehicle: Vehicle; order_date: string; start_time: string; end_time: string }) => void;
}) {
  const [pinnedItem, setPinnedItem] = useState<CalendarItem | null>(null);
  const vehicleRows = mergeVehicleRows(vehicles, items);
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
          const layout = layoutLanes(rowItems, view);
          const rowHeight = Math.max(view === "day" ? 96 : 118, layout.laneCount * 58 + 34);
          return (
            <div
              key={vehicle.id || vehicle.plate_number}
              className="grid grid-cols-[180px_1fr] border-b border-border last:border-b-0"
              style={{ minHeight: rowHeight }}
            >
              <div className="border-r border-border px-4 py-4">
                <p className="text-sm font-bold text-slate-950">{vehicle.plate_number}</p>
                <p className="mt-1 text-xs text-slate-500">{vehicle.vehicle_type || "-"} / {vehicle.seat_count || "-"}座</p>
              </div>
              <div
                className="relative bg-[linear-gradient(to_right,#e2e8f0_1px,transparent_1px)]"
                style={{ backgroundSize }}
                onClick={(event) => {
                  if (event.detail !== 2) return;
                  if ((event.target as HTMLElement).closest("[data-calendar-event='true']")) return;
                  const slot = slotFromPointer(event, vehicle, view, startDate || dateColumns[0]?.key || "", columns.length);
                  if (slot) onCreateSlot?.(slot);
                }}
                onDoubleClick={(event) => {
                  if ((event.target as HTMLElement).closest("[data-calendar-event='true']")) return;
                  const slot = slotFromPointer(event, vehicle, view, startDate || dateColumns[0]?.key || "", columns.length);
                  if (slot) onCreateSlot?.(slot);
                }}
              >
                {rowItems.map((item) => (
                  <div
                    key={itemKey(item)}
                    data-calendar-event="true"
                    className="group absolute h-12 min-w-24 rounded-md px-3 py-2 text-xs font-semibold text-white shadow-sm"
                    style={{ ...eventStyle(item, view, startDate, columns.length), top: 12 + (layout.laneByKey.get(itemKey(item)) || 0) * 58 }}
                    title={eventTooltip(item)}
                    onClick={(event) => {
                      event.stopPropagation();
                      if (event.detail === 2) {
                        onEditItem?.(item);
                        return;
                      }
                      setPinnedItem(item);
                    }}
                    onDoubleClick={(event) => {
                      event.stopPropagation();
                      onEditItem?.(item);
                    }}
                  >
                    <p className="truncate pr-10">
                      {view === "day" ? item.start_time : `${item.order_date?.slice(5)} ${item.start_time || ""}`} {item.display_title || item.oid || item.order_id}
                    </p>
                    <span className="absolute right-1 top-1 rounded bg-white/20 px-1 text-[10px] font-black text-white">{eventStatusLabel(item)}</span>
                    <p className="mt-1 truncate font-medium text-white/90">{shortRoute(item.pickup_location, item.dropoff_location)}</p>
                    <div className="pointer-events-none absolute left-0 top-[52px] z-20 hidden w-72 whitespace-pre-line rounded-lg bg-slate-950/95 p-3 text-left text-xs font-semibold leading-5 text-white shadow-xl group-hover:block">
                      {eventTooltip(item)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
      {pinnedItem ? (
        <div className="fixed right-8 top-28 z-40 w-80 rounded-xl border border-slate-200 bg-white p-4 text-sm shadow-2xl">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-xs font-black uppercase tracking-wide text-slate-400">订单详情</div>
              <div className="mt-1 text-base font-black text-slate-950">{pinnedItem.oid || pinnedItem.order_id || pinnedItem.id || "-"}</div>
            </div>
            <button type="button" className="rounded-md px-2 py-1 text-xs font-bold text-slate-500 hover:bg-slate-100" onClick={() => setPinnedItem(null)}>
              关闭
            </button>
          </div>
          <div className="mt-3 space-y-2 text-slate-700">
            {tooltipLines(pinnedItem).map((line) => (
              <div key={line} className="rounded-lg bg-slate-50 px-3 py-2 leading-5">{line}</div>
            ))}
          </div>
          <button
            type="button"
            className="mt-3 h-9 w-full rounded-md bg-blue-600 text-sm font-black text-white hover:bg-blue-700"
            onClick={() => onEditItem?.(pinnedItem)}
          >
            编辑订单
          </button>
        </div>
      ) : null}
    </div>
  );
}

function slotFromPointer(
  event: MouseEvent<HTMLDivElement>,
  vehicle: Vehicle,
  view: CalendarView,
  startDate: string,
  columnCount: number,
) {
  const rect = event.currentTarget.getBoundingClientRect();
  if (!rect.width) return null;
  const ratio = Math.max(0, Math.min(0.999, (event.clientX - rect.left) / rect.width));
  const rangeStart = toDate(startDate) || new Date();
  let orderDate = rangeStart;
  let minute = Math.round((ratio * 1440) / 15) * 15;
  if (view !== "day") {
    const dayWidth = 1 / Math.max(columnCount, 1);
    const dayIndex = Math.max(0, Math.min(columnCount - 1, Math.floor(ratio / dayWidth)));
    orderDate = addDays(rangeStart, dayIndex);
    const dayRatio = (ratio - dayIndex * dayWidth) / dayWidth;
    minute = Math.round((dayRatio * 1440) / 15) * 15;
  }
  minute = Math.max(0, Math.min(23 * 60 + 45, minute));
  const endMinute = Math.min(23 * 60 + 59, minute + 60);
  return {
    vehicle,
    order_date: isoDate(orderDate),
    start_time: minuteText(minute),
    end_time: minuteText(endMinute),
  };
}

function minuteText(value: number) {
  const h = Math.floor(value / 60);
  const m = value % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
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

function mergeVehicleRows(vehicles: Vehicle[], items: CalendarItem[]): Vehicle[] {
  const rows = [...vehicles];
  const existing = new Set(rows.map((vehicle) => String(vehicle.id || vehicle.plate_number)));
  uniqueVehiclesFromItems(items).forEach((vehicle) => {
    const key = String(vehicle.id || vehicle.plate_number);
    if (!existing.has(key)) {
      rows.push(vehicle);
      existing.add(key);
    }
  });
  return rows;
}
