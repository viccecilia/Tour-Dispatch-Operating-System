import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowUpRight,
  Bot,
  CalendarDays,
  CheckCircle2,
  Clock3,
  FileWarning,
  Lightbulb,
  ListChecks,
  Route,
  ShieldCheck,
  Sparkles,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import { EmptyPanel, ErrorPanel, SkeletonCard } from "@/components/OperationalState";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/services/apiClient";
import type { CopilotSummary } from "@/types/api";

type Tone = "blue" | "green" | "red" | "violet" | "amber";

function emptyCopilot(date: string): CopilotSummary {
  return {
    date,
    operations_summary: "当前没有需要处理的运营建议。",
    metrics: {
      today_orders: 0,
      unassigned_orders: 0,
      active_execution: 0,
      completed_orders: 0,
      completion_rate: 0,
      open_incidents: 0,
    },
    risk_orders: [],
    unassigned_reminders: [],
    driver_exception_summary: [],
    open_incidents: [],
    urgent_notifications: [],
    suggestions: [],
    explainability: ["基于当前订单、派车、司机上报、异常和通知生成", "只解释风险和建议下一步", "不会自动派车或修改财务记录"],
  };
}

export function CopilotPage() {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const copilot = useQuery({
    queryKey: ["copilot-summary", date],
    queryFn: () => api.copilotSummary(date),
  });
  const data = copilot.data ?? emptyCopilot(date);
  const metrics = normalizeMetrics(data.metrics);

  const workQueue = useMemo(
    () => [
      { title: "风险订单", count: data.risk_orders.length, tone: "red" as const, icon: AlertTriangle },
      { title: "未派车提醒", count: data.unassigned_reminders.length, tone: "amber" as const, icon: Clock3 },
      { title: "司机异常", count: data.driver_exception_summary.length, tone: "violet" as const, icon: UserRound },
      { title: "紧急通知", count: data.urgent_notifications.length, tone: "blue" as const, icon: FileWarning },
    ],
    [data.driver_exception_summary.length, data.risk_orders.length, data.unassigned_reminders.length, data.urgent_notifications.length],
  );

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-500">运营助手</p>
          <h2 className="mt-1 text-2xl font-black text-slate-950">运营助手</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-500">
            汇总订单、派车、司机上报、异常和通知，给出可追溯的下一步建议。这里只做提示，不自动改变业务状态。
          </p>
        </div>
        <label className="inline-flex h-10 items-center gap-2 rounded-xl border border-border bg-white px-3 text-sm font-semibold text-slate-700 shadow-sm">
          <CalendarDays size={16} className="text-slate-400" />
          <input className="bg-transparent outline-none" type="date" value={date} onChange={(event) => setDate(event.target.value)} />
        </label>
      </div>

      {copilot.isError ? (
        <ErrorPanel
          title="运营助手暂时无法读取数据"
          description="请确认后端接口可用。页面会保留空状态，终端恢复后会自动显示真实建议。"
          onRetry={() => copilot.refetch()}
        />
      ) : null}

      <section className="grid gap-5 xl:grid-cols-[1.35fr_0.65fr]">
        <Card className="overflow-hidden border-blue-100 bg-gradient-to-br from-white via-blue-50/60 to-white">
          <CardContent className="p-0">
            <div className="grid gap-0 lg:grid-cols-[1fr_340px]">
              <div className="p-6">
                <div className="flex items-start gap-4">
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-sm">
                    <Bot size={24} />
                  </div>
                  <div className="min-w-0">
                    <div className="inline-flex rounded-full bg-blue-100 px-3 py-1 text-xs font-black text-blue-700">今日运营摘要</div>
                    <h3 className="mt-3 text-2xl font-black leading-snug text-slate-950">{data.operations_summary}</h3>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {data.explainability.map((text) => (
                        <span key={text} className="rounded-full border border-blue-100 bg-white px-3 py-1 text-xs font-bold text-slate-600">
                          {text}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
              <div className="border-t border-blue-100 bg-white/70 p-5 lg:border-l lg:border-t-0">
                <div className="flex items-center gap-2 text-sm font-black text-slate-950">
                  <ShieldCheck size={18} className="text-emerald-600" />
                  规则边界
                </div>
                <div className="mt-4 space-y-3">
                  {["不自动派车", "不自动修改财务", "所有建议可追溯原因"].map((text) => (
                    <div key={text} className="flex items-center gap-2 rounded-xl border border-slate-100 bg-white px-3 py-2 text-sm font-bold text-slate-700">
                      <CheckCircle2 size={16} className="text-emerald-600" />
                      {text}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <ListChecks size={18} className="text-blue-600" />
              <div>
                <h3 className="text-base font-black text-slate-950">待处理队列</h3>
                <p className="text-xs font-semibold text-slate-500">先处理红色和橙色项目。</p>
              </div>
            </div>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3">
            {workQueue.map((item) => (
              <QueueTile key={item.title} {...item} />
            ))}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {copilot.isLoading ? (
          Array.from({ length: 4 }).map((_, index) => <SkeletonCard key={index} rows={2} />)
        ) : (
          <>
            <MetricCard title="今日订单" value={metrics.todayOrders} caption={`完成 ${metrics.completedOrders} 单`} icon={Route} tone="blue" />
            <MetricCard title="未派车" value={metrics.unassignedOrders} caption="需要人工检查" icon={AlertTriangle} tone={metrics.unassignedOrders ? "red" : "green"} />
            <MetricCard title="执行中" value={metrics.activeExecution} caption="司机正在服务" icon={UserRound} tone="violet" />
            <MetricCard title="完成率" value={`${metrics.completionRate}%`} caption={`未关闭异常 ${metrics.openIncidents} 个`} icon={CheckCircle2} tone={metrics.openIncidents ? "amber" : "green"} />
          </>
        )}
      </section>

      <section className="grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Sparkles size={18} className="text-blue-600" />
              <div>
                <h3 className="text-base font-black text-slate-950">建议队列</h3>
                <p className="text-xs font-semibold text-slate-500">按优先级查看下一步动作。</p>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.suggestions.length ? (
              data.suggestions.map((suggestion, index) => (
                <div key={`${suggestion.title}-${index}`} className="rounded-2xl border border-border bg-white p-4 shadow-sm">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex min-w-0 gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-700">
                        <Lightbulb size={18} />
                      </div>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h4 className="text-sm font-black text-slate-950">{suggestion.title}</h4>
                          <StatusBadge status={suggestion.priority} />
                        </div>
                        <p className="mt-2 text-sm leading-6 text-slate-600">{suggestion.text}</p>
                        <div className="mt-3 rounded-xl bg-slate-50 px-3 py-2 text-xs font-semibold leading-5 text-slate-500">
                          原因：{suggestion.reason}
                        </div>
                      </div>
                    </div>
                    {suggestion.link ? (
                      <button
                        type="button"
                        className="inline-flex h-8 shrink-0 items-center gap-1 rounded-full bg-slate-900 px-3 text-xs font-black text-white"
                        onClick={() => {
                          window.location.hash = suggestion.link?.replace("#", "") || "dashboard";
                        }}
                      >
                        打开
                        <ArrowUpRight size={14} />
                      </button>
                    ) : null}
                  </div>
                </div>
              ))
            ) : (
              <EmptyPanel title="暂无建议" description="当前没有需要运营助手提醒的动作。" />
            )}
          </CardContent>
        </Card>

        <div className="grid gap-5">
          <CompactList title="风险订单" icon={AlertTriangle} items={data.risk_orders} empty="暂无风险订单" />
          <CompactList title="未派车提醒" icon={Clock3} items={data.unassigned_reminders} empty="暂无未派车提醒" />
          <CompactList title="司机异常摘要" icon={UserRound} items={data.driver_exception_summary} empty="暂无司机异常" />
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <CompactList title="开放异常" icon={FileWarning} items={data.open_incidents} empty="暂无开放异常" />
        <CompactList title="紧急通知" icon={Sparkles} items={data.urgent_notifications} empty="暂无紧急通知" />
      </section>
    </div>
  );
}

function normalizeMetrics(metrics: Record<string, number>) {
  return {
    todayOrders: Number(metrics.today_orders || 0),
    unassignedOrders: Number(metrics.unassigned_orders || 0),
    activeExecution: Number(metrics.active_execution || 0),
    completedOrders: Number(metrics.completed_orders || metrics.completed || 0),
    completionRate: Number(metrics.completion_rate || 0),
    openIncidents: Number(metrics.open_incidents || 0),
  };
}

function MetricCard({ title, value, caption, icon: Icon, tone }: { title: string; value: number | string; caption: string; icon: LucideIcon; tone: Tone }) {
  const toneClass = {
    blue: "bg-blue-50 text-blue-700 border-blue-100",
    green: "bg-emerald-50 text-emerald-700 border-emerald-100",
    red: "bg-red-50 text-red-700 border-red-100",
    violet: "bg-violet-50 text-violet-700 border-violet-100",
    amber: "bg-amber-50 text-amber-700 border-amber-100",
  }[tone];

  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-xs font-black uppercase tracking-wide text-slate-500">{title}</div>
            <div className="mt-3 text-3xl font-black text-slate-950">{value}</div>
            <div className="mt-1 text-xs font-semibold text-slate-500">{caption}</div>
          </div>
          <div className={`flex h-10 w-10 items-center justify-center rounded-xl border ${toneClass}`}>
            <Icon size={18} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function QueueTile({ title, count, tone, icon: Icon }: { title: string; count: number; tone: Exclude<Tone, "green">; icon: LucideIcon }) {
  const toneClass = {
    red: "bg-red-50 text-red-700 border-red-100",
    amber: "bg-amber-50 text-amber-700 border-amber-100",
    violet: "bg-violet-50 text-violet-700 border-violet-100",
    blue: "bg-blue-50 text-blue-700 border-blue-100",
  }[tone];

  return (
    <div className={`rounded-xl border p-3 ${toneClass}`}>
      <div className="flex items-center justify-between gap-2">
        <Icon size={17} />
        <span className="text-xl font-black">{count}</span>
      </div>
      <div className="mt-2 text-xs font-black">{title}</div>
    </div>
  );
}

function CompactList({ title, icon: Icon, items, empty }: { title: string; icon: LucideIcon; items: Array<Record<string, unknown>>; empty: string }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Icon size={18} className="text-slate-500" />
            <h3 className="text-base font-black text-slate-950">{title}</h3>
          </div>
          <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-black text-slate-600">{items.length}</span>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {items.length ? (
          items.slice(0, 8).map((item, index) => (
            <div key={`${title}-${index}`} className="rounded-xl border border-border bg-white p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-black text-slate-950">{itemTitle(item)}</div>
                  <div className="mt-1 truncate text-xs font-semibold text-slate-500">{itemSubtitle(item)}</div>
                  {Array.isArray(item.reasons) ? <div className="mt-2 text-xs text-slate-500">{item.reasons.join(" / ")}</div> : null}
                  {item.suggested_action ? <div className="mt-2 text-xs font-bold text-blue-700">{String(item.suggested_action)}</div> : null}
                </div>
                <StatusBadge status={String(item.risk_level || item.severity || item.priority || item.status || "pending")} />
              </div>
            </div>
          ))
        ) : (
          <div className="rounded-xl border border-dashed border-slate-200 py-8 text-center text-sm font-semibold text-slate-500">{empty}</div>
        )}
      </CardContent>
    </Card>
  );
}

function itemTitle(item: Record<string, unknown>) {
  return String(item.title || item.oid || item.driver_name || item.notification_type || item.id || "-");
}

function itemSubtitle(item: Record<string, unknown>) {
  const date = String(item.order_date || item.created_at || "");
  const time = String(item.start_time || "");
  const route = [item.pickup_location, item.dropoff_location].filter(Boolean).join(" -> ");
  return [date, time, route].filter(Boolean).join(" · ") || String(item.message || item.summary || "-");
}
