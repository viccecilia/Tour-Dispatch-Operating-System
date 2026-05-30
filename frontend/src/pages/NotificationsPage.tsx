import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCheck, CircleAlert } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { PilotFeedbackNote } from "@/components/PilotFeedbackNote";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/services/apiClient";

const typeLabels: Record<string, string> = {
  unconfirmed_order: "未确认订单",
  not_departed: "未出库",
  not_arrived: "未到达",
  missing_photo: "未上传照片",
  pending_driver_expense: "司机待处理记录",
  not_returned: "未入库",
  resource_reminder: "资源提醒",
  dispatch_assigned: "派车通知",
  driver_report: "司机报备",
  incident: "异常通知",
};

const priorityLabels: Record<string, string> = {
  critical: "紧急",
  high: "高",
  normal: "普通",
  low: "低",
};

export function NotificationsPage() {
  const queryClient = useQueryClient();
  const notifications = useQuery({
    queryKey: ["notifications-page"],
    queryFn: () => api.notifications({ limit: 100 }),
    refetchInterval: 20_000,
  });
  const summary = useQuery({ queryKey: ["notification-summary"], queryFn: api.notificationSummary, refetchInterval: 20_000 });
  const markRead = useMutation({
    mutationFn: (id: number) => api.markNotificationRead(id),
    onSuccess: () => invalidate(queryClient),
  });
  const markAll = useMutation({
    mutationFn: api.markAllNotificationsRead,
    onSuccess: () => invalidate(queryClient),
  });
  const rows = notifications.data || [];
  const unreadRows = rows.filter((item) => item.status !== "read");

  return (
    <div className="space-y-5">
      <PilotFeedbackNote
        title="提醒试运营规则"
        tone="amber"
        items={["高优先级先处理", "处理后标记已读", "观察是否过度提醒", "记录误报和漏报"]}
      />
      <section className="grid gap-4 md:grid-cols-3">
        <Metric title="未读提醒" value={summary.data?.unread || 0} tone="blue" />
        <Metric title="高优先级" value={summary.data?.urgent || 0} tone="red" />
        <Metric title="提醒总数" value={summary.data?.total || 0} tone="slate" />
      </section>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-bold tracking-[0.18em] text-blue-600">NOTIFICATION RUNTIME</p>
              <h2 className="mt-1 text-xl font-bold text-slate-950">运营提醒中心</h2>
              <p className="mt-1 text-sm text-slate-500">自动汇总未确认、未出库、未到达、未上传照片、未入库等关键提醒。</p>
            </div>
            <Button disabled={markAll.isPending || unreadRows.length === 0} onClick={() => markAll.mutate()}>
              <CheckCheck size={16} />
              全部已读
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {notifications.isLoading ? (
            <EmptyState title="正在读取提醒" />
          ) : rows.length === 0 ? (
            <EmptyState title="暂无提醒" detail="关键运营节点出现异常时，会自动生成系统内提醒。" />
          ) : (
            <div className="overflow-hidden rounded-lg border border-border">
              <table className="data-table min-w-[980px]">
                <thead>
                  <tr>
                    <th>状态</th>
                    <th>优先级</th>
                    <th>类型</th>
                    <th>提醒内容</th>
                    <th>生成时间</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((item) => (
                    <tr key={item.id} className={item.status === "read" ? "bg-white" : "bg-blue-50/40"}>
                      <td>{item.status === "read" ? "已读" : "未读"}</td>
                      <td><PriorityBadge value={item.priority || "normal"} /></td>
                      <td>{typeLabels[item.notification_type] || item.notification_type || "系统提醒"}</td>
                      <td>
                        <div className="max-w-[520px]">
                          <p className="font-semibold text-slate-950">{item.title}</p>
                          <p className="mt-1 line-clamp-2 text-xs text-slate-500">{item.body || "-"}</p>
                        </div>
                      </td>
                      <td>{item.created_at || "-"}</td>
                      <td>
                        <Button variant="secondary" className="h-8 px-3" disabled={item.status === "read" || markRead.isPending} onClick={() => markRead.mutate(item.id)}>
                          标记已读
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function invalidate(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ["notifications-page"] });
  queryClient.invalidateQueries({ queryKey: ["notification-summary"] });
}

function Metric({ title, value, tone }: { title: string; value: number; tone: "blue" | "red" | "slate" }) {
  const toneClass = {
    blue: "bg-blue-50 text-blue-700",
    red: "bg-red-50 text-red-700",
    slate: "bg-slate-50 text-slate-700",
  }[tone];
  return (
    <div className={`rounded-xl border border-border p-4 ${toneClass}`}>
      <div className="flex items-center gap-2 text-sm font-semibold">
        <Bell size={16} />
        {title}
      </div>
      <div className="mt-3 text-3xl font-black">{value}</div>
    </div>
  );
}

function PriorityBadge({ value }: { value: string }) {
  const urgent = value === "critical" || value === "high";
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-semibold ${urgent ? "bg-red-50 text-red-700" : "bg-slate-100 text-slate-700"}`}>
      {urgent ? <CircleAlert size={12} /> : null}
      {priorityLabels[value] || value}
    </span>
  );
}
