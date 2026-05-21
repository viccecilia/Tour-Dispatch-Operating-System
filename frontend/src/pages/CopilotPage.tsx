import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Bot, CheckCircle2, Lightbulb, Route, UserRound } from "lucide-react";
import { KpiCard } from "@/components/KpiCard";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/services/apiClient";

export function CopilotPage() {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const copilot = useQuery({ queryKey: ["copilot-summary", date], queryFn: () => api.copilotSummary(date) });

  if (copilot.isLoading) {
    return <div className="panel p-8 text-sm text-slate-500">正在加载运营助手摘要...</div>;
  }
  if (copilot.isError || !copilot.data) {
    return <div className="panel p-8 text-sm text-red-600">运营助手接口失败。</div>;
  }

  const data = copilot.data;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-500">运营助手</p>
          <h2 className="mt-1 text-2xl font-bold text-slate-950">运营助手</h2>
          <p className="mt-2 max-w-4xl text-sm text-slate-500">规则生成的可解释建议，不自动派车，不自动修改财务。</p>
        </div>
        <input className="h-10 rounded-md border border-border bg-white px-3 text-sm" type="date" value={date} onChange={(event) => setDate(event.target.value)} />
      </div>

      <Card className="border-blue-200 bg-blue-50/50">
        <CardContent className="flex items-start gap-4 p-5">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white">
            <Bot size={22} />
          </div>
          <div>
            <div className="text-sm font-semibold text-blue-700">今日运营摘要</div>
            <div className="mt-1 text-xl font-bold text-slate-950">{data.operations_summary}</div>
            <div className="mt-3 flex flex-wrap gap-2">
              {data.explainability.map((item) => (
                <span key={item} className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-600">{item}</span>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <KpiCard title="今日订单" value={data.metrics.today_orders} icon={Route} tone="blue" />
        <KpiCard title="未派车" value={data.metrics.unassigned_orders} icon={AlertTriangle} tone={data.metrics.unassigned_orders ? "red" : "green"} />
        <KpiCard title="执行中" value={data.metrics.active_execution} icon={UserRound} tone="violet" />
        <KpiCard title="完成率" value={`${data.metrics.completion_rate}%`} icon={CheckCircle2} tone="green" />
        <KpiCard title="开放异常" value={data.metrics.open_incidents} icon={AlertTriangle} tone={data.metrics.open_incidents ? "red" : "slate"} />
      </section>

      <section className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <Card>
          <CardHeader>
            <h3 className="text-base font-bold text-slate-950">AI 建议文本</h3>
            <p className="mt-1 text-sm text-slate-500">每条建议都附带可解释原因和入口。</p>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.suggestions.map((suggestion) => (
              <div key={suggestion.title} className="rounded-lg border border-border bg-white p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-amber-50 text-amber-700">
                      <Lightbulb size={18} />
                    </div>
                    <div>
                      <div className="font-bold text-slate-950">{suggestion.title}</div>
                      <div className="mt-1 text-sm text-slate-700">{suggestion.text}</div>
                      <div className="mt-2 text-xs text-slate-500">原因：{suggestion.reason}</div>
                    </div>
                  </div>
                  <StatusBadge status={suggestion.priority} />
                </div>
                {suggestion.link ? (
                  <button className="mt-3 text-xs font-bold text-blue-600" onClick={() => { window.location.hash = suggestion.link?.replace("#", "") || "dashboard"; }}>
                    打开相关页面
                  </button>
                ) : null}
              </div>
            ))}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <CompactList title="风险订单摘要" items={data.risk_orders} empty="暂无风险订单" />
          <CompactList title="未派车提醒" items={data.unassigned_reminders} empty="暂无未派车提醒" />
          <CompactList title="司机异常摘要" items={data.driver_exception_summary} empty="暂无司机异常" />
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <CompactList title="开放异常" items={data.open_incidents} empty="暂无开放异常" />
        <CompactList title="紧急通知" items={data.urgent_notifications} empty="暂无紧急通知" />
      </section>
    </div>
  );
}

function CompactList({ title, items, empty }: { title: string; items: Array<Record<string, unknown>>; empty: string }) {
  return (
    <Card>
      <CardHeader>
        <h3 className="text-base font-bold text-slate-950">{title}</h3>
        <p className="mt-1 text-sm text-slate-500">{items.length} items</p>
      </CardHeader>
      <CardContent className="space-y-3">
        {items.length ? items.slice(0, 8).map((item, index) => (
          <div key={`${title}-${index}`} className="rounded-lg border border-border p-3">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-bold text-slate-950">{String(item.title || item.oid || item.driver_name || item.notification_type || item.id || "-")}</div>
                <div className="mt-1 truncate text-xs text-slate-500">
                  {String(item.order_date || item.created_at || "")} {String(item.start_time || "")} {String(item.pickup_location || "")} {item.dropoff_location ? `→ ${String(item.dropoff_location)}` : ""}
                </div>
                {Array.isArray(item.reasons) ? <div className="mt-2 text-xs text-slate-500">{item.reasons.join(" / ")}</div> : null}
                {item.suggested_action ? <div className="mt-2 text-xs font-semibold text-blue-700">{String(item.suggested_action)}</div> : null}
              </div>
              <StatusBadge status={String(item.risk_level || item.severity || item.priority || item.status || "pending")} />
            </div>
          </div>
        )) : <div className="py-8 text-center text-sm text-slate-500">{empty}</div>}
      </CardContent>
    </Card>
  );
}
