import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarMatrix } from "@/components/CalendarMatrix";
import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { todayIso } from "@/lib/utils";
import { api } from "@/services/apiClient";

type View = "day" | "week" | "month";

export function CalendarPage() {
  const [view, setView] = useState<View>("day");
  const [date, setDate] = useState(todayIso());
  const calendar = useQuery({ queryKey: ["calendar", view, date], queryFn: () => api.calendar(view, date) });

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-bold text-slate-950">车辆矩阵日历</h2>
              <p className="mt-1 text-sm text-slate-500">车辆纵向，时间横向，按订单类型和状态着色。</p>
            </div>
            <div className="flex items-center gap-2">
              <Button variant={view === "day" ? "primary" : "secondary"} onClick={() => setView("day")}>24h</Button>
              <Button variant={view === "week" ? "primary" : "secondary"} onClick={() => setView("week")}>7d</Button>
              <Button variant={view === "month" ? "primary" : "secondary"} onClick={() => setView("month")}>30d</Button>
              <input
                type="date"
                className="h-9 rounded-md border border-border px-3 text-sm"
                value={date}
                onChange={(event) => setDate(event.target.value)}
              />
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {["unassigned", "assigned", "completed", "unsettled", "settled"].map((status) => (
              <StatusBadge key={status} status={status} />
            ))}
          </div>
          {calendar.isLoading ? <div className="text-sm text-slate-500">正在加载日历...</div> : null}
          {calendar.isError ? <div className="text-sm text-red-600">日历 API 加载失败。</div> : null}
          {calendar.data?.items?.length ? (
            <CalendarMatrix vehicles={calendar.data.vehicles || []} items={calendar.data.items} />
          ) : (
            <EmptyState title="当前日期暂无派车" detail="切换日期或运行 demo seed 后查看车辆占用横条。" />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
