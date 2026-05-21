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

const viewMeta: Record<View, { label: string; title: string; stepDays: number }> = {
  day: { label: "24h", title: "24 小时窗口", stepDays: 1 },
  week: { label: "7d", title: "7 日窗口", stepDays: 7 },
  month: { label: "30d", title: "30 日窗口", stepDays: 30 },
};

function shiftDate(value: string, days: number) {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return todayIso();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

export function CalendarPage() {
  const [view, setView] = useState<View>("day");
  const [date, setDate] = useState(todayIso());
  const calendar = useQuery({ queryKey: ["calendar", view, date], queryFn: () => api.calendar(view, date), refetchInterval: 5000 });
  const currentMeta = viewMeta[view];

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
              {(Object.keys(viewMeta) as View[]).map((item) => (
                <Button key={item} variant={view === item ? "primary" : "secondary"} onClick={() => setView(item)}>
                  {viewMeta[item].label}
                </Button>
              ))}
              <Button variant="secondary" onClick={() => setDate(shiftDate(date, -currentMeta.stepDays))}>上一窗口</Button>
              <input
                type="date"
                className="h-9 rounded-md border border-border px-3 text-sm"
                value={date}
                onChange={(event) => setDate(event.target.value)}
              />
              <Button variant="secondary" onClick={() => setDate(shiftDate(date, currentMeta.stepDays))}>下一窗口</Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-2">
              {["unassigned", "assigned", "completed", "unsettled", "settled"].map((status) => (
                <StatusBadge key={status} status={status} />
              ))}
            </div>
            <div className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600">
              {currentMeta.title}：{calendar.data?.start_date || date} 至 {calendar.data?.end_date || date}
            </div>
          </div>
          {calendar.isLoading ? <div className="text-sm text-slate-500">正在加载日历...</div> : null}
          {calendar.isError ? <div className="text-sm text-red-600">日历接口加载失败。</div> : null}
          {calendar.data ? (
            <CalendarMatrix
              vehicles={calendar.data.vehicles || []}
              items={calendar.data.items}
              view={view}
              startDate={calendar.data.start_date}
              endDate={calendar.data.end_date}
            />
          ) : null}
          {calendar.data && !calendar.data.items?.length ? (
            <EmptyState title="当前日期暂无派车" detail="切换日期或运行 demo seed 后查看车辆占用横条。" />
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
