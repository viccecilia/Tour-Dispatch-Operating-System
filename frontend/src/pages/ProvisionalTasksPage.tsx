import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleDollarSign, History } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/services/apiClient";
import type { ProvisionalFormalOrder, ProvisionalTask } from "@/types/api";

const statuses: Record<string, string> = {
  draft: "司机草稿",
  pending_company_confirmation: "待公司确认",
  needs_information: "需要补充",
  approved_new_order: "已转正式订单",
  approved_linked_order: "已关联正式订单",
  rejected: "已驳回",
};

const money = (value: number | null | undefined) => value == null ? "未定" : `${Number(value).toLocaleString()}円`;
const requestId = (prefix: string) => `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
const dt = (value?: string | null) => value ? value.replace("T", " ").replace("Z", "") : "未填写";

export function ProvisionalTasksPage() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [reason, setReason] = useState("");
  const [linkedOrderId, setLinkedOrderId] = useState("");
  const [pricing, setPricing] = useState({ price_jpy: "", driver_salary_jpy: "", driver_settlement_amount: "", driver_settlement_status: "pending" });

  const list = useQuery({ queryKey: ["company-provisional-tasks", status], queryFn: () => api.companyProvisionalTasks(status), refetchInterval: 15_000 });
  const finance = useQuery({ queryKey: ["company-provisional-finance"], queryFn: api.companyProvisionalFinanceSummary });
  const detail = useQuery({
    queryKey: ["company-provisional-task", selectedId],
    queryFn: () => api.companyProvisionalTask(selectedId),
    enabled: Boolean(selectedId),
  });

  const tasks = list.data?.tasks || [];
  useEffect(() => {
    if (!selectedId && tasks.length) setSelectedId(tasks[0].provisional_task_id);
  }, [selectedId, tasks]);

  useEffect(() => {
    const order = detail.data?.formal_order;
    if (!order) return;
    setPricing({
      price_jpy: order.price_jpy == null ? "" : String(order.price_jpy),
      driver_salary_jpy: order.driver_salary_jpy == null ? "" : String(order.driver_salary_jpy),
      driver_settlement_amount: order.driver_settlement_amount == null ? "" : String(order.driver_settlement_amount),
      driver_settlement_status: order.driver_settlement_status || "pending",
    });
  }, [detail.data?.formal_order]);

  const selected = detail.data?.task;
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["company-provisional-tasks"] }),
      queryClient.invalidateQueries({ queryKey: ["company-provisional-task", selectedId] }),
      queryClient.invalidateQueries({ queryKey: ["company-provisional-finance"] }),
    ]);
  };

  const review = useMutation({
    mutationFn: (action: "approve-create" | "approve-link" | "needs-info" | "reject") => {
      if (!selected) throw new Error("请选择临时订单");
      if (["needs-info", "reject"].includes(action) && !reason.trim()) throw new Error("请填写理由");
      return api.reviewCompanyProvisionalTask(selected.provisional_task_id, action, {
        expected_revision: selected.revision,
        client_request_id: requestId(`web-${action}`),
        reason: reason.trim() || undefined,
        linked_order_id: action === "approve-link" ? linkedOrderId.trim() : undefined,
      });
    },
    onSuccess: async () => { setReason(""); await refresh(); },
  });

  const savePrice = useMutation({
    mutationFn: () => {
      if (!selected) throw new Error("请选择临时订单");
      const payload: Record<string, unknown> = {
        expected_revision: selected.revision,
        client_request_id: requestId("web-pricing"),
        driver_settlement_status: pricing.driver_settlement_status,
        reason: reason.trim() || undefined,
      };
      (["price_jpy", "driver_salary_jpy"] as const).forEach((field) => {
        payload[field] = pricing[field] === "" ? null : Number(pricing[field]);
      });
      if (pricing.driver_settlement_amount !== "") payload.driver_settlement_amount = Number(pricing.driver_settlement_amount);
      return api.priceCompanyProvisionalTask(selected.provisional_task_id, payload);
    },
    onSuccess: refresh,
  });

  const pendingCount = useMemo(() => tasks.filter((item) => item.status === "pending_company_confirmation").length, [tasks]);
  const error = list.error || detail.error || review.error || savePrice.error;

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-4">
        <Metric label="当前列表" value={tasks.length} />
        <Metric label="待公司确认" value={pendingCount} />
        <Metric label="正式订单（唯一计数）" value={finance.data?.company.formal_order_count || 0} />
        <Metric label="金额未定" value={finance.data?.company.unknown_price_count || 0} warn />
      </section>

      <section className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="font-bold text-slate-950">司机临时订单</h2>
                <p className="mt-1 text-sm text-slate-500">仅显示本公司记录。司机登记内容和全部修订历史不会被覆盖。</p>
              </div>
              <select className="h-9 rounded-md border border-border px-3 text-sm" value={status} onChange={(event) => { setStatus(event.target.value); setSelectedId(""); }}>
                <option value="">全部状态</option>
                {Object.entries(statuses).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            {list.isLoading ? <p className="py-8 text-sm text-slate-500">正在加载...</p> : null}
            {!list.isLoading && !tasks.length ? <p className="py-8 text-center text-sm text-slate-500">暂无临时订单</p> : null}
            {tasks.map((item) => (
              <button key={item.provisional_task_id} onClick={() => setSelectedId(item.provisional_task_id)} className={`w-full rounded-xl border p-4 text-left ${selectedId === item.provisional_task_id ? "border-blue-500 bg-blue-50" : "border-border bg-white hover:bg-slate-50"}`}>
                <div className="flex items-start justify-between gap-3">
                  <div><p className="font-bold text-slate-950">{item.display_number}</p><p className="mt-1 text-xs text-slate-500">{item.business_date} · 司机 #{item.driver_id} · 车辆 #{item.vehicle_id}</p></div>
                  <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">{statuses[item.status] || item.status}</span>
                </div>
                <p className="mt-3 text-sm text-slate-700">{item.actual_pickup_location || "未填写上车地"} → {item.actual_dropoff_location || "未填写下车地"}</p>
              </button>
            ))}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader><h2 className="font-bold text-slate-950">确认与追溯</h2></CardHeader>
            <CardContent>
              {!selected ? <p className="py-8 text-sm text-slate-500">请选择一条记录。</p> : <TaskDetail task={selected} formalOrder={detail.data?.formal_order || null} />}
              {selected?.status === "pending_company_confirmation" ? (
                <div className="mt-5 space-y-3 border-t border-border pt-5">
                  <label className="block text-sm font-semibold text-slate-700">理由/备注
                    <textarea className="mt-1 min-h-20 w-full rounded-md border border-border px-3 py-2 text-sm" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="要求补充或驳回时必填" />
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={() => review.mutate("approve-create")} disabled={review.isPending}>转为新正式订单</Button>
                    <input className="h-9 w-40 rounded-md border border-border px-3 text-sm" value={linkedOrderId} onChange={(event) => setLinkedOrderId(event.target.value)} placeholder="已有订单 ID/OID" />
                    <Button variant="secondary" onClick={() => review.mutate("approve-link")} disabled={!linkedOrderId || review.isPending}>关联已有订单</Button>
                    <Button variant="secondary" onClick={() => review.mutate("needs-info")} disabled={review.isPending}>要求补充</Button>
                    <Button variant="danger" onClick={() => review.mutate("reject")} disabled={review.isPending}>驳回</Button>
                  </div>
                </div>
              ) : null}
              {error ? <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{String((error as Error).message)}</p> : null}
            </CardContent>
          </Card>

          {selected && ["approved_new_order", "approved_linked_order"].includes(selected.status) ? (
            <Card>
              <CardHeader><div className="flex items-center gap-2"><CircleDollarSign size={18} /><h2 className="font-bold text-slate-950">正式订单定价与司机结算</h2></div></CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-slate-500">空值表示未知，不自动补 0。收入和完成单量按唯一正式订单统计。</p>
                <div className="grid gap-3 md:grid-cols-3">
                  <MoneyInput label="公司订单金额" value={pricing.price_jpy} onChange={(value) => setPricing({ ...pricing, price_jpy: value })} />
                  <MoneyInput label="司机应得" value={pricing.driver_salary_jpy} onChange={(value) => setPricing({ ...pricing, driver_salary_jpy: value })} />
                  <MoneyInput label="司机结算金额" value={pricing.driver_settlement_amount} onChange={(value) => setPricing({ ...pricing, driver_settlement_amount: value })} />
                </div>
                <select className="h-10 rounded-md border border-border px-3 text-sm" value={pricing.driver_settlement_status} onChange={(event) => setPricing({ ...pricing, driver_settlement_status: event.target.value })}>
                  <option value="pending">待结算</option><option value="unsettled">未结算</option><option value="settled">已结算</option><option value="paid">已支付</option>
                </select>
                <Button onClick={() => savePrice.mutate()} disabled={savePrice.isPending}>{savePrice.isPending ? "保存中..." : "保存定价与结算"}</Button>
              </CardContent>
            </Card>
          ) : null}
        </div>
      </section>

      <Card>
        <CardHeader><h2 className="font-bold text-slate-950">公司与司机统计</h2></CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            <Metric label="已知公司营业额" value={money(finance.data?.company.known_business_amount_jpy)} />
            <Metric label="司机应得合计" value={money(finance.data?.company.driver_salary_jpy)} />
            <Metric label="司机结算合计" value={money(finance.data?.company.driver_settlement_amount_jpy)} />
          </div>
          <p className="mt-4 text-xs text-slate-500">{finance.data?.accounting_note || "仅统计正式订单；不代表现金已到账。"}</p>
        </CardContent>
      </Card>
    </div>
  );
}

function TaskDetail({ task, formalOrder }: { task: ProvisionalTask; formalOrder: ProvisionalFormalOrder | null }) {
  return <div className="space-y-4">
    <div className="flex items-start justify-between gap-3"><div><p className="text-lg font-bold text-slate-950">{task.display_number}</p><p className="text-sm text-slate-500">版本 {task.revision} · {statuses[task.status] || task.status}</p></div>{formalOrder ? <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700">正式订单 {formalOrder.oid || formalOrder.order_id}</span> : null}</div>
    <div className="grid gap-3 rounded-xl bg-slate-50 p-4 md:grid-cols-2">
      <Fact label="上车" value={`${task.actual_pickup_location || "未填写"}\n${dt(task.actual_pickup_at)}`} />
      <Fact label="下车" value={`${task.actual_dropoff_location || "未填写"}\n${dt(task.actual_dropoff_at)}`} />
      <Fact label="来源" value={task.service_source || "未填写"} />
      <Fact label="授权依据" value={task.authorization_source || "未填写"} />
      <Fact label="到着时仪表" value={task.pickup_odometer_km == null ? "未填写" : `${task.pickup_odometer_km} km`} />
      <Fact label="降车时仪表" value={task.dropoff_odometer_km == null ? (task.odometer_km == null ? "未填写" : `${task.odometer_km} km（旧记录）`) : `${task.dropoff_odometer_km} km`} />
      <Fact label="司机备注" value={task.note || "无"} />
    </div>
    <div><div className="mb-2 flex items-center gap-2 text-sm font-bold text-slate-800"><History size={16} />修订历史</div><div className="space-y-2">{(task.events || []).map((event) => <div key={event.id} className="rounded-lg border border-border p-3 text-sm"><p className="font-semibold text-slate-800">{event.event_type}</p><p className="text-xs text-slate-500">{event.actor_name || event.actor_role} · {event.created_at || ""}</p>{event.reason ? <p className="mt-1 text-slate-700">{event.reason}</p> : null}</div>)}</div></div>
  </div>;
}

function Metric({ label, value, warn = false }: { label: string; value: string | number; warn?: boolean }) { return <div className="rounded-xl border border-border bg-white p-4 shadow-sm"><p className="text-xs font-semibold text-slate-500">{label}</p><p className={`mt-2 text-2xl font-black ${warn ? "text-amber-600" : "text-slate-950"}`}>{value}</p></div>; }
function Fact({ label, value }: { label: string; value: string }) { return <div><p className="text-xs font-semibold text-slate-500">{label}</p><p className="mt-1 whitespace-pre-line text-sm text-slate-900">{value}</p></div>; }
function MoneyInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) { return <label className="text-sm font-semibold text-slate-700">{label}<input type="number" min="0" className="mt-1 h-10 w-full rounded-md border border-border px-3 text-sm" value={value} onChange={(event) => onChange(event.target.value)} placeholder="未知则留空" /></label>; }
