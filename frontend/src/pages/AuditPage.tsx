import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, DatabaseZap, FileClock, Search, ShieldCheck } from "lucide-react";
import { KpiCard } from "@/components/KpiCard";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/services/apiClient";
import type { AuditLog, DataAnomalyIssue } from "@/types/api";

function severityClass(severity?: string) {
  if (severity === "high") return "bg-red-50 text-red-700 ring-red-100";
  if (severity === "medium") return "bg-amber-50 text-amber-700 ring-amber-100";
  return "bg-slate-100 text-slate-700 ring-slate-200";
}

function severityLabel(severity?: string) {
  return { high: "高风险", medium: "中风险", low: "低风险" }[severity || ""] || "普通";
}

function entityLabel(value?: string) {
  return { order: "订单", assignment: "派车记录", governance: "数据治理", finance: "财务" }[value || ""] || value || "-";
}

const issueTitleLabels: Record<string, string> = {
  missing_price: "订单缺少价格",
  assigned_without_active_assignment: "已派车订单缺少有效派车记录",
  assignment_without_order: "派车记录缺少订单",
  active_assignment_order_not_assigned: "有效派车记录对应订单状态异常",
  active_assignment_missing_resource: "有效派车记录缺少司机或车辆",
  driver_report_without_assignment: "司机报备缺少派车记录",
  finance_unsettled_old_orders: "长期未结算订单",
  open_incidents: "待处理异常仍需跟进",
  failed_parser_drafts: "解析失败草稿待复核",
};

const actionLabels: Record<string, string> = {
  create: "新增",
  update: "修改",
  delete: "删除",
  soft_delete: "软删除",
  assign: "派车",
  cancel_assignment: "取消派车",
  reassign: "重新派车",
  driver_report: "司机报备",
  finance_update: "财务修改",
  audit_scan: "审计扫描",
  parser_confirm: "草稿确认",
};

function formatDiff(log: AuditLog) {
  const keys = Object.keys(log.diff || {});
  if (!keys.length) return "-";
  return keys.slice(0, 4).join(", ") + (keys.length > 4 ? ` +${keys.length - 4}` : "");
}

export function AuditPage() {
  const queryClient = useQueryClient();
  const [keyword, setKeyword] = useState("");
  const [entityType, setEntityType] = useState("");
  const auditLogs = useQuery({
    queryKey: ["audit-logs", keyword, entityType],
    queryFn: () => api.auditLogs({ keyword, entity_type: entityType, limit: 120 }),
  });
  const scans = useQuery({ queryKey: ["audit-scans"], queryFn: api.auditScans });
  const anomalyScan = useQuery({ queryKey: ["audit-anomalies-preview"], queryFn: api.auditAnomalies });
  const runScan = useMutation({
    mutationFn: api.runAuditScan,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
      queryClient.invalidateQueries({ queryKey: ["audit-scans"] });
      queryClient.invalidateQueries({ queryKey: ["audit-anomalies-preview"] });
    },
  });

  const latestScan = runScan.data || anomalyScan.data || scans.data?.[0];
  const issues: DataAnomalyIssue[] = useMemo(() => latestScan?.issues || latestScan?.result?.issues || [], [latestScan]);
  const highIssues = issues.filter((issue) => issue.severity === "high").reduce((sum, issue) => sum + issue.count, 0);
  const operationCount = auditLogs.data?.length || 0;
  const changedEntities = new Set((auditLogs.data || []).map((log) => `${log.entity_type}:${log.entity_id}`)).size;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-500">数据治理</p>
          <h2 className="mt-1 text-2xl font-bold text-slate-950">审计追踪</h2>
          <p className="mt-1 text-sm text-slate-500">记录订单、派车、司机报备和财务修改，确保关键操作可追溯。</p>
        </div>
        <button
          className="inline-flex h-10 items-center gap-2 rounded-lg bg-slate-950 px-4 text-sm font-bold text-white shadow-sm hover:bg-slate-800 disabled:opacity-60"
          onClick={() => runScan.mutate()}
          disabled={runScan.isPending}
        >
          <DatabaseZap size={16} />
          {runScan.isPending ? "扫描中..." : "执行数据扫描"}
        </button>
      </div>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard title="审计记录" value={operationCount} icon={FileClock} tone="blue" caption="最近 120 条" />
        <KpiCard title="变更对象" value={changedEntities} icon={ShieldCheck} tone="violet" caption="订单 / 派车 / 财务" />
        <KpiCard title="数据问题" value={latestScan?.issue_count || 0} icon={AlertTriangle} tone={(latestScan?.issue_count || 0) > 0 ? "amber" : "green"} caption="只读扫描" />
        <KpiCard title="高风险" value={highIssues} icon={AlertTriangle} tone={highIssues ? "red" : "green"} caption="需要人工复核" />
      </section>

      <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-base font-bold text-slate-950">数据异常扫描</h3>
                <p className="mt-1 text-sm text-slate-500">扫描只报告风险，不自动修复，也不会删除历史数据。</p>
              </div>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600">
                {latestScan?.created_at || (runScan.data ? "刚刚" : "预览")}
              </span>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {issues.length ? (
              issues.map((issue) => (
                <div key={issue.code} className="rounded-lg border border-border p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="font-bold text-slate-950">{issueTitleLabels[issue.code] || issue.title}</div>
                      <div className="mt-1 text-xs text-slate-500">需要人工复核的数据项</div>
                    </div>
                    <span className={`rounded-full px-2.5 py-1 text-xs font-bold ring-1 ${severityClass(issue.severity)}`}>
                      {severityLabel(issue.severity)} · {issue.count}
                    </span>
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-slate-500">
                当前扫描未发现数据治理问题。
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-base font-bold text-slate-950">操作记录</h3>
                <p className="mt-1 text-sm text-slate-500">展示关键操作、操作人、对象和字段差异。</p>
              </div>
              <div className="flex items-center gap-2">
                <select className="h-9 rounded-md border border-border px-3 text-sm" value={entityType} onChange={(event) => setEntityType(event.target.value)}>
                  <option value="">全部对象</option>
                  <option value="order">订单</option>
                  <option value="assignment">派车记录</option>
                  <option value="governance">数据治理</option>
                </select>
                <div className="relative">
                  <Search className="absolute left-3 top-2.5 text-slate-400" size={15} />
                  <input
                    className="h-9 w-56 rounded-md border border-border pl-9 pr-3 text-sm"
                    value={keyword}
                    onChange={(event) => setKeyword(event.target.value)}
                    placeholder="搜索操作人/动作/摘要"
                  />
                </div>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {auditLogs.isLoading ? (
              <div className="p-8 text-sm text-slate-500">正在加载审计记录...</div>
            ) : auditLogs.isError ? (
              <div className="p-8 text-sm text-red-600">审计接口加载失败，请检查后端服务。</div>
            ) : (
              <div className="overflow-hidden rounded-lg border border-border">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-3">时间</th>
                      <th className="px-3 py-3">操作人</th>
                      <th className="px-3 py-3">动作</th>
                      <th className="px-3 py-3">对象</th>
                      <th className="px-3 py-3">变更字段</th>
                      <th className="px-3 py-3">摘要</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border bg-white">
                    {(auditLogs.data || []).map((log) => (
                      <tr key={log.id} className="hover:bg-slate-50">
                        <td className="whitespace-nowrap px-3 py-3 text-xs text-slate-500">{log.created_at || "-"}</td>
                        <td className="px-3 py-3 font-semibold text-slate-900">{log.actor || "系统"}</td>
                        <td className="px-3 py-3">
                          <span className="rounded-full bg-blue-50 px-2 py-1 text-xs font-bold text-blue-700">{actionLabels[log.action] || log.action}</span>
                        </td>
                        <td className="px-3 py-3 text-slate-600">
                          {entityLabel(log.entity_type)}
                          {log.entity_id ? <span className="ml-1 text-slate-400">#{log.entity_id}</span> : null}
                        </td>
                        <td className="max-w-52 truncate px-3 py-3 text-slate-600">{formatDiff(log)}</td>
                        <td className="max-w-80 truncate px-3 py-3 text-slate-500">{log.summary || "-"}</td>
                      </tr>
                    ))}
                    {!(auditLogs.data || []).length ? (
                      <tr>
                        <td className="px-3 py-8 text-center text-sm text-slate-500" colSpan={6}>
                          暂无审计记录。新增、修改、派车或结算订单后会生成记录。
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
