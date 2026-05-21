import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Send } from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api, clearAgencyToken, getAgencyToken, setAgencyToken } from "@/services/apiClient";
import type { AgencyPortalAgency, Order } from "@/types/api";

const emptyOrder: Partial<Order> = {
  order_date: new Date().toISOString().slice(0, 10),
  end_date: new Date().toISOString().slice(0, 10),
  start_time: "09:00",
  end_time: "10:00",
  pickup_location: "",
  dropoff_location: "",
  order_type: "charter",
  vehicle_type: "",
  passenger_count: 0,
  luggage_count: 0,
  guest_name: "",
  guest_contact: "",
  price: undefined,
  fee_remark: "",
  remark: "",
};

export function AgencyPortalPage() {
  const queryClient = useQueryClient();
  const [agency, setAgency] = useState<AgencyPortalAgency | null>(null);
  const [agencyId, setAgencyId] = useState<number | "">("");
  const [portalCode, setPortalCode] = useState("");
  const [form, setForm] = useState<Partial<Order>>(emptyOrder);
  const hasToken = Boolean(getAgencyToken());
  const agencies = useQuery({ queryKey: ["agency-portal-agencies"], queryFn: api.agencyPortalAgencies });
  const orders = useQuery({ queryKey: ["agency-portal-orders", hasToken], queryFn: api.agencyPortalOrders, enabled: hasToken });

  const loginMutation = useMutation({
    mutationFn: () => api.agencyPortalLogin(Number(agencyId), portalCode),
    onSuccess: (result) => {
      setAgencyToken(result.token);
      setAgency(result.agency);
      queryClient.invalidateQueries({ queryKey: ["agency-portal-orders"] });
    },
  });

  const createMutation = useMutation({
    mutationFn: api.createAgencyPortalOrder,
    onSuccess: () => {
      setForm(emptyOrder);
      queryClient.invalidateQueries({ queryKey: ["agency-portal-orders"] });
    },
  });

  const loggedIn = hasToken || Boolean(agency);

  return (
    <div className="min-h-screen bg-slate-100 p-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-slate-500">旅行社下单入口</p>
            <h1 className="mt-1 text-3xl font-bold text-slate-950">旅行社下单入口</h1>
          </div>
          {loggedIn ? (
            <Button
              variant="secondary"
              onClick={() => {
                clearAgencyToken();
                setAgency(null);
                queryClient.removeQueries({ queryKey: ["agency-portal-orders"] });
              }}
            >
              退出门户
            </Button>
          ) : null}
        </div>

        {!loggedIn ? (
          <Card className="mx-auto max-w-xl">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-700">
                  <Building2 size={20} />
                </div>
                <div>
                  <h2 className="text-base font-bold text-slate-950">旅行社登录</h2>
                  <p className="text-sm text-slate-500">选择旅行社并输入 portal code。</p>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <select className="h-10 w-full rounded-md border border-border px-3 text-sm" value={agencyId} onChange={(event) => setAgencyId(event.target.value ? Number(event.target.value) : "")}>
                <option value="">选择旅行社</option>
                {(agencies.data || []).map((item) => (
                  <option key={`${item.tenant_id}-${item.id}`} value={item.id}>{item.name}</option>
                ))}
              </select>
              <input className="h-10 w-full rounded-md border border-border px-3 text-sm" placeholder="门户代码" value={portalCode} onChange={(event) => setPortalCode(event.target.value)} />
              {loginMutation.isError ? <div className="text-sm font-semibold text-red-600">{loginMutation.error.message}</div> : null}
              <Button className="w-full" disabled={!agencyId || !portalCode || loginMutation.isPending} onClick={() => loginMutation.mutate()}>
                登录旅行社门户
              </Button>
            </CardContent>
          </Card>
        ) : (
          <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
            <Card>
              <CardHeader>
                <h2 className="text-base font-bold text-slate-950">提交订单</h2>
                <p className="mt-1 text-sm text-slate-500">{agency?.name || "旅行社"} 提交后会进入调度端订单池和派车工作台。</p>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid gap-3 md:grid-cols-2">
                  <Field label="开始日期" type="date" value={form.order_date} onChange={(value) => setForm({ ...form, order_date: value, end_date: form.end_date || value })} />
                  <Field label="结束日期" type="date" value={form.end_date} onChange={(value) => setForm({ ...form, end_date: value })} />
                  <Field label="开始时间" type="time" value={form.start_time} onChange={(value) => setForm({ ...form, start_time: value })} />
                  <Field label="结束时间" type="time" value={form.end_time} onChange={(value) => setForm({ ...form, end_time: value })} />
                </div>
                <Field label="起点" value={form.pickup_location} onChange={(value) => setForm({ ...form, pickup_location: value })} />
                <Field label="终点" value={form.dropoff_location} onChange={(value) => setForm({ ...form, dropoff_location: value })} />
                <div className="grid gap-3 md:grid-cols-2">
                  <Field label="类型" value={form.order_type} onChange={(value) => setForm({ ...form, order_type: value })} />
                  <Field label="车型" value={form.vehicle_type} onChange={(value) => setForm({ ...form, vehicle_type: value })} />
                  <Field label="客人姓名" value={form.guest_name} onChange={(value) => setForm({ ...form, guest_name: value })} />
                  <Field label="联系方式" value={form.guest_contact} onChange={(value) => setForm({ ...form, guest_contact: value })} />
                  <Field label="人数" type="number" value={form.passenger_count} onChange={(value) => setForm({ ...form, passenger_count: Number(value || 0) })} />
                  <Field label="报价 JPY" type="number" value={form.price} onChange={(value) => setForm({ ...form, price: value ? Number(value) : undefined })} />
                </div>
                <textarea className="min-h-24 w-full rounded-md border border-border px-3 py-2 text-sm" placeholder="费用备注 / 特殊要求" value={form.fee_remark || form.remark || ""} onChange={(event) => setForm({ ...form, fee_remark: event.target.value, remark: event.target.value })} />
                {createMutation.isError ? <div className="text-sm font-semibold text-red-600">{createMutation.error.message}</div> : null}
                <Button className="w-full" disabled={createMutation.isPending} onClick={() => createMutation.mutate(form)}>
                  <Send size={16} />
                  提交订单
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <h2 className="text-base font-bold text-slate-950">我的订单</h2>
                <p className="mt-1 text-sm text-slate-500">只显示当前旅行社提交或归属的订单。</p>
              </CardHeader>
              <CardContent className="overflow-x-auto p-0">
                <table className="data-table min-w-[920px]">
                  <thead>
                    <tr>
                      <th>订单号</th>
                      <th>日期时间</th>
                      <th>路线</th>
                      <th>车型</th>
                      <th>报价</th>
                      <th>派车</th>
                      <th>结算</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(orders.data || []).map((order) => (
                      <tr key={order.id}>
                        <td className="font-bold text-slate-950">{order.oid || order.id}</td>
                        <td>{order.order_date} {order.start_time}-{order.end_time}</td>
                        <td>{order.pickup_location} → {order.dropoff_location}</td>
                        <td>{order.vehicle_type || "-"}</td>
                        <td>{order.price_jpy || order.price || "-"}</td>
                        <td><StatusBadge status={order.dispatch_status} /></td>
                        <td><StatusBadge status={order.settlement_status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          </section>
        )}
      </div>
    </div>
  );
}

function Field({ label, value, onChange, type = "text" }: { label: string; value: unknown; onChange: (value: string) => void; type?: string }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-semibold text-slate-700">{label}</span>
      <input className="h-10 w-full rounded-md border border-border px-3 text-sm" type={type} value={String(value ?? "")} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}
