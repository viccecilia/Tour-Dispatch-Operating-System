import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, PlayCircle, ToggleLeft, ToggleRight } from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyPanel, ErrorPanel, SkeletonCard } from "@/components/OperationalState";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/services/apiClient";
import type { WorkflowRule } from "@/types/api";

const triggerLabels: Record<string, string> = {
  order_created: "订单创建",
  order_updated: "订单更新",
  assignment_created: "派车完成",
  driver_report: "司机报备",
  resource_due: "资源到期",
  manual: "手动触发",
  schedule_check: "定时检查",
  daily_check: "每日检查",
  data_check: "数据检查",
};

const actionLabels: Record<string, string> = {
  notification: "生成通知",
  mark_incident: "标记异常",
  dispatch_suggestion: "生成派车建议",
  reminder: "提醒",
  notify: "生成通知",
  mark_exception: "标记异常",
};

const ruleNameLabels: Record<string, string> = {
  "unassigned_due_soon": "临近开始仍未派车",
  "driver_report_overdue": "司机未按时报备",
  "resource_due_reminder": "车辆/司机证件到期提醒",
  "high_value_order_review": "高金额订单人工复核",
  "incident_follow_up": "异常订单跟进提醒",
  "missing_price": "订单价格缺失提醒",
  "driver_unreported": "司机未报备提醒",
  "resource_due": "资源到期提醒",
  "dispatch_conflict": "派车冲突提示",
  "overdue_unassigned_exception": "超时未派车自动标记异常",
  "dispatch_suggestion": "未派车池派车建议",
};

const priorityLabels: Record<string, string> = {
  high: "高",
  medium: "中",
  low: "低",
  normal: "普通",
};

function ruleDisplayName(rule: WorkflowRule) {
  return ruleNameLabels[rule.code] || rule.name || rule.code;
}

function renderJsonSummary(value: unknown) {
  if (!value || typeof value !== "object") return "无额外条件";
  const labels: Record<string, string> = {
    minutes_before_start: "开始前分钟数",
    hours_without_report: "未报备小时数",
    days_before_due: "到期提前天数",
    threshold: "阈值",
    severity: "严重程度",
    priority: "优先级",
    status: "状态",
    window_hours: "检查未来小时数",
    limit: "数量上限",
  };
  return Object.entries(value as Record<string, unknown>)
    .map(([key, item]) => `${labels[key] || key}: ${String(item)}`)
    .join("，") || "无额外条件";
}

export function AutomationPage() {
  const queryClient = useQueryClient();
  const rules = useQuery({ queryKey: ["workflow-rules"], queryFn: api.workflowRules });
  const runs = useQuery({ queryKey: ["workflow-runs"], queryFn: api.workflowRuns });
  const runMutation = useMutation({
    mutationFn: api.runWorkflows,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workflow-runs"] });
      queryClient.invalidateQueries({ queryKey: ["notification-summary"] });
    },
  });
  const updateMutation = useMutation({
    mutationFn: ({ rule, enabled }: { rule: WorkflowRule; enabled: boolean }) => api.updateWorkflowRule(rule.id, { enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workflow-rules"] }),
  });

  const ruleList = rules.data || [];
  const runList = runs.data || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-500">规则自动化</p>
          <h2 className="mt-1 text-2xl font-bold text-slate-950">自动化规则引擎</h2>
          <p className="mt-2 text-sm text-slate-500">当前仅生成提醒、异常标记和派车建议，不会自动执行高风险派车，也不会删除数据。</p>
        </div>
        <Button disabled={runMutation.isPending} onClick={() => runMutation.mutate(undefined)}>
          <PlayCircle size={16} />
          运行全部规则
        </Button>
      </div>

      {runMutation.data ? (
        <Card className="border-blue-200 bg-blue-50/40">
          <CardContent className="flex flex-wrap items-center gap-4 p-4 text-sm">
            <span className="font-bold text-blue-900">本次执行</span>
            <span>{runMutation.data.executed_rules} 条规则</span>
            <span>{runMutation.data.total_actions} 个动作</span>
            {runMutation.data.results.map((item) => (
              <span key={item.rule_code} className="rounded-full bg-white px-2 py-1 text-xs font-semibold text-blue-700">
                {item.rule_code}: {item.action_count}
              </span>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {rules.isError ? (
        <ErrorPanel
          title="自动化规则接口暂时不可用"
          description="规则列表、触发条件、动作和执行日志结构仍保留，后端恢复后可继续操作。"
          requestPath="/api/workflows/rules"
          onRetry={() => rules.refetch()}
        />
      ) : null}

      <section className="grid gap-4 xl:grid-cols-2">
        {rules.isLoading ? (
          Array.from({ length: 4 }).map((_, index) => <SkeletonCard key={index} title="规则列表加载中" rows={4} />)
        ) : ruleList.length ? ruleList.map((rule) => (
          <Card key={rule.id}>
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-violet-50 text-violet-700">
                    <Bot size={20} />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-slate-950">{ruleDisplayName(rule)}</h3>
                    <p className="mt-1 text-xs font-semibold text-slate-500">系统规则</p>
                  </div>
                </div>
                <StatusBadge status={rule.enabled ? "enabled" : "disabled"} />
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 md:grid-cols-3">
                <Meta label="触发条件" value={triggerLabels[rule.trigger_type] || rule.trigger_type} />
                <Meta label="执行动作" value={actionLabels[rule.action_type] || rule.action_type} />
                <Meta label="优先级" value={priorityLabels[String(rule.action_json?.priority || rule.action_json?.severity || "normal")] || String(rule.action_json?.priority || rule.action_json?.severity || "普通")} />
              </div>
              <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
                <div className="font-bold text-slate-800">规则条件</div>
                <div className="mt-1 leading-5">{renderJsonSummary(rule.condition_json)}</div>
              </div>
              <div className="flex items-center justify-between">
                <Button variant="secondary" disabled={runMutation.isPending} onClick={() => runMutation.mutate(rule.code)}>
                  <PlayCircle size={16} />
                  运行此规则
                </Button>
                <button
                  className="inline-flex items-center gap-2 text-sm font-semibold text-slate-700"
                  disabled={updateMutation.isPending}
                  onClick={() => updateMutation.mutate({ rule, enabled: !rule.enabled })}
                >
                  {rule.enabled ? <ToggleRight className="text-emerald-600" /> : <ToggleLeft className="text-slate-400" />}
                  {rule.enabled ? "已启用" : "已停用"}
                </button>
              </div>
            </CardContent>
          </Card>
        )) : (
          <>
            <RulePlaceholder title="规则列表区域" desc="展示自动提醒、异常标记和派车建议规则。" />
            <RulePlaceholder title="触发条件区域" desc="展示订单、司机报备、资源到期等触发源。" />
            <RulePlaceholder title="动作区域" desc="展示生成通知、标记异常、生成建议等动作。" />
            <RulePlaceholder title="执行策略区域" desc="显示规则优先级、启停状态和人工运行入口。" />
          </>
        )}
      </section>

      <Card>
        <CardHeader>
          <h3 className="text-base font-bold text-slate-950">最近执行记录</h3>
          <p className="mt-1 text-sm text-slate-500">用于确认规则是否触发，以及生成了多少通知或建议。</p>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          <table className="data-table min-w-[920px]">
            <thead>
              <tr>
                <th>时间</th>
                <th>规则</th>
                <th>动作数</th>
                <th>结果</th>
              </tr>
            </thead>
            <tbody>
              {runList.slice(0, 20).map((run) => (
                <tr key={run.id}>
                  <td>{run.created_at || "-"}</td>
                  <td>
                    <div className="font-bold text-slate-950">{run.code ? ruleNameLabels[run.code] || run.name || run.code : run.name || run.rule_id}</div>
                    <div className="text-xs text-slate-500">{run.code}</div>
                  </td>
                  <td>{run.action_count}</td>
                  <td className="max-w-xl truncate">{JSON.stringify(run.result || {})}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {runs.isError ? (
            <div className="p-4">
              <ErrorPanel title="最近执行日志读取失败" requestPath="/api/workflows/runs" onRetry={() => runs.refetch()} />
            </div>
          ) : null}
          {!runs.isLoading && !runs.isError && !runList.length ? (
            <div className="p-4">
              <EmptyPanel title="暂无执行日志" description="手动运行规则或定时任务触发后，这里会出现最近执行记录。" />
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

function RulePlaceholder({ title, desc }: { title: string; desc: string }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-violet-50 text-violet-700">
            <Bot size={20} />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-950">{title}</h3>
            <p className="mt-1 text-sm text-slate-500">{desc}</p>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 md:grid-cols-3">
          <Meta label="触发条件" value="待后端同步" />
          <Meta label="执行动作" value="生成提醒 / 建议" />
          <Meta label="状态" value="离线模式" />
        </div>
      </CardContent>
    </Card>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border p-3">
      <div className="text-xs font-semibold text-slate-500">{label}</div>
      <div className="mt-1 text-sm font-bold text-slate-950">{value}</div>
    </div>
  );
}
