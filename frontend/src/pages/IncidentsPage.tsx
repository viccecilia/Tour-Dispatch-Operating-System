import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Clock3, FileWarning, MessageSquareWarning, ShieldAlert } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { KpiCard } from "@/components/KpiCard";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/services/apiClient";
import type { Incident } from "@/types/api";

const incidentTypes = [
  { value: "exception", label: "异常订单" },
  { value: "delay", label: "延误" },
  { value: "complaint", label: "客诉" },
  { value: "accident", label: "事故" },
];

const severityOptions = [
  { value: "low", label: "低" },
  { value: "medium", label: "中" },
  { value: "high", label: "高" },
  { value: "critical", label: "紧急" },
];

const emptyForm = {
  order_id: "",
  assignment_id: "",
  incident_type: "exception",
  severity: "medium",
  title: "",
  description: "",
  owner: "",
  delay_minutes: "",
  complaint_contact: "",
  accident_location: "",
};

export function IncidentsPage() {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState({ status: "open", incident_type: "", keyword: "" });
  const [form, setForm] = useState(emptyForm);
  const [closeDraft, setCloseDraft] = useState<Record<number, string>>({});

  const summary = useQuery({ queryKey: ["incident-summary"], queryFn: api.incidentSummary, refetchInterval: 5000 });
  const incidents = useQuery({
    queryKey: ["incidents", filters],
    queryFn: () => api.incidents(filters),
    refetchInterval: 5000,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["incident-summary"] });
    queryClient.invalidateQueries({ queryKey: ["incidents"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    queryClient.invalidateQueries({ queryKey: ["orders"] });
  };

  const createMutation = useMutation({
    mutationFn: () =>
      api.createIncident({
        ...form,
        order_id: form.order_id ? Number(form.order_id) : undefined,
        assignment_id: form.assignment_id ? Number(form.assignment_id) : undefined,
        delay_minutes: form.delay_minutes ? Number(form.delay_minutes) : undefined,
      }),
    onSuccess: () => {
      setForm(emptyForm);
      refresh();
    },
  });

  const closeMutation = useMutation({
    mutationFn: ({ id, resolution }: { id: number; resolution?: string }) => api.closeIncident(id, { resolution }),
    onSuccess: () => {
      setCloseDraft({});
      refresh();
    },
  });

  const rows = useMemo(() => incidents.data || [], [incidents.data]);
  const highPriority = useMemo(() => rows.filter((item) => ["high", "critical"].includes(item.severity || "")).length, [rows]);

  function submit(event: FormEvent) {
    event.preventDefault();
    createMutation.mutate();
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <KpiCard title="处理中异常" value={summary.data?.open_incidents} icon={ShieldAlert} tone="red" />
        <KpiCard title="延误" value={summary.data?.delay_incidents} icon={Clock3} tone="amber" />
        <KpiCard title="客诉" value={summary.data?.complaint_incidents} icon={MessageSquareWarning} tone="red" />
        <KpiCard title="事故" value={summary.data?.accident_incidents} icon={FileWarning} tone="red" />
        <KpiCard title="今日关闭" value={summary.data?.closed_incidents_today} icon={CheckCircle2} tone="green" />
      </section>

      <section className="grid gap-6 xl:grid-cols-[0.78fr_1.22fr]">
        <Card>
          <CardHeader>
            <h2 className="text-base font-bold text-slate-950">新建异常</h2>
            <p className="mt-1 text-sm text-slate-500">轻量记录延误、客诉、事故和其他运营异常。</p>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={submit}>
              <div className="grid gap-3 md:grid-cols-2">
                <label className="space-y-1 text-sm font-semibold text-slate-700">
                  订单 ID
                  <input className="h-10 w-full rounded-md border border-border px-3 text-sm" value={form.order_id} onChange={(event) => setForm({ ...form, order_id: event.target.value })} placeholder="可选" />
                </label>
                <label className="space-y-1 text-sm font-semibold text-slate-700">
                  Assignment ID
                  <input className="h-10 w-full rounded-md border border-border px-3 text-sm" value={form.assignment_id} onChange={(event) => setForm({ ...form, assignment_id: event.target.value })} placeholder="可选" />
                </label>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <label className="space-y-1 text-sm font-semibold text-slate-700">
                  类型
                  <select className="h-10 w-full rounded-md border border-border px-3 text-sm" value={form.incident_type} onChange={(event) => setForm({ ...form, incident_type: event.target.value })}>
                    {incidentTypes.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="space-y-1 text-sm font-semibold text-slate-700">
                  等级
                  <select className="h-10 w-full rounded-md border border-border px-3 text-sm" value={form.severity} onChange={(event) => setForm({ ...form, severity: event.target.value })}>
                    {severityOptions.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="space-y-1 text-sm font-semibold text-slate-700">
                标题
                <input className="h-10 w-full rounded-md border border-border px-3 text-sm" required value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder="例如：客人投诉司机迟到" />
              </label>
              <label className="space-y-1 text-sm font-semibold text-slate-700">
                处理人
                <input className="h-10 w-full rounded-md border border-border px-3 text-sm" value={form.owner} onChange={(event) => setForm({ ...form, owner: event.target.value })} placeholder="调度员姓名" />
              </label>
              <div className="grid gap-3 md:grid-cols-3">
                <input className="h-10 rounded-md border border-border px-3 text-sm" value={form.delay_minutes} onChange={(event) => setForm({ ...form, delay_minutes: event.target.value })} placeholder="延误分钟" />
                <input className="h-10 rounded-md border border-border px-3 text-sm" value={form.complaint_contact} onChange={(event) => setForm({ ...form, complaint_contact: event.target.value })} placeholder="客诉联系人" />
                <input className="h-10 rounded-md border border-border px-3 text-sm" value={form.accident_location} onChange={(event) => setForm({ ...form, accident_location: event.target.value })} placeholder="事故地点" />
              </div>
              <label className="space-y-1 text-sm font-semibold text-slate-700">
                说明
                <textarea className="min-h-24 w-full rounded-md border border-border px-3 py-2 text-sm" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="保留现场情况、客户反馈、下一步处理动作。" />
              </label>
              {createMutation.isError ? <p className="text-sm text-red-600">{String(createMutation.error.message)}</p> : null}
              <Button className="w-full" disabled={createMutation.isPending}>
                {createMutation.isPending ? "正在记录..." : "记录异常"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-bold text-slate-950">异常处理池</h2>
                <p className="mt-1 text-sm text-slate-500">高优先级 {highPriority} 条。关闭异常时会写入处理结果并恢复订单派车状态。</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <select className="h-9 rounded-md border border-border px-3 text-sm" value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })}>
                  <option value="">全部状态</option>
                  <option value="open">未处理</option>
                  <option value="processing">处理中</option>
                  <option value="closed">已关闭</option>
                </select>
                <select className="h-9 rounded-md border border-border px-3 text-sm" value={filters.incident_type} onChange={(event) => setFilters({ ...filters, incident_type: event.target.value })}>
                  <option value="">全部类型</option>
                  {incidentTypes.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
                <input className="h-9 rounded-md border border-border px-3 text-sm" value={filters.keyword} onChange={(event) => setFilters({ ...filters, keyword: event.target.value })} placeholder="搜索订单/说明" />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {incidents.isLoading ? <div className="py-10 text-sm text-slate-500">正在加载异常记录...</div> : null}
            {!incidents.isLoading && !rows.length ? <EmptyState detail="当前没有符合条件的异常记录。" /> : null}
            <div className="space-y-3">
              {rows.map((item) => (
                <IncidentRow
                  key={item.id}
                  item={item}
                  closeDraft={closeDraft[item.id] || ""}
                  onChangeCloseDraft={(value) => setCloseDraft({ ...closeDraft, [item.id]: value })}
                  onClose={() => closeMutation.mutate({ id: item.id, resolution: closeDraft[item.id] })}
                  closing={closeMutation.isPending}
                />
              ))}
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

function IncidentRow({
  item,
  closeDraft,
  onChangeCloseDraft,
  onClose,
  closing,
}: {
  item: Incident;
  closeDraft: string;
  onChangeCloseDraft: (value: string) => void;
  onClose: () => void;
  closing: boolean;
}) {
  const route = `${item.pickup_location || "-"} -> ${item.dropoff_location || "-"}`;
  return (
    <div className="rounded-lg border border-border bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <AlertTriangle size={16} className="text-red-600" />
            <p className="font-bold text-slate-950">{item.title}</p>
            <StatusBadge status={item.incident_type} />
            <StatusBadge status={item.severity} />
            <StatusBadge status={item.status} />
          </div>
          <p className="mt-2 text-sm text-slate-600">
            {item.oid || (item.order_id ? `ORDER-${item.order_id}` : "未绑定订单")} · {item.order_date || "-"} {item.start_time || ""} · {route}
          </p>
          <p className="mt-1 text-sm text-slate-500">
            司机 {item.driver_name || "-"} · 车辆 {item.plate_number || "-"} · 处理人 {item.owner || "-"}
          </p>
        </div>
        <p className="text-xs text-slate-400">{item.created_at || ""}</p>
      </div>
      {item.description ? <p className="mt-3 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600">{item.description}</p> : null}
      <div className="mt-3 grid gap-2 text-xs text-slate-500 md:grid-cols-3">
        <span>延误：{item.delay_minutes ?? 0} 分钟</span>
        <span>客诉联系人：{item.complaint_contact || "-"}</span>
        <span>事故地点：{item.accident_location || "-"}</span>
      </div>
      {item.status !== "closed" ? (
        <div className="mt-4 flex flex-wrap gap-2">
          <input className="h-9 min-w-72 flex-1 rounded-md border border-border px-3 text-sm" value={closeDraft} onChange={(event) => onChangeCloseDraft(event.target.value)} placeholder="关闭处理结果，例如：已联系客人并完成补偿说明" />
          <Button variant="secondary" onClick={onClose} disabled={closing}>
            关闭异常
          </Button>
        </div>
      ) : (
        <p className="mt-3 text-sm text-slate-500">处理结果：{item.resolution || "-"}</p>
      )}
    </div>
  );
}
