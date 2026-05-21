import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Crown, Save, ShieldCheck, UsersRound, Zap } from "lucide-react";
import { KpiCard } from "@/components/KpiCard";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/services/apiClient";
import type { OrgMember, Plan, ReminderSettings } from "@/types/api";

const featureLabels: Record<string, string> = {
  dashboard: "总览",
  orders: "订单",
  parser: "订单解析",
  dispatch: "派车",
  calendar: "日历",
  driver_monitor: "司机监控",
  vehicles: "车辆/司机",
  finance: "财务",
  incidents: "异常",
  ai_parser_v2: "解析增强",
  fleet_tracking: "车辆位置",
};

const usageLabels: Record<string, string> = {
  orders: "订单",
  parser_drafts: "解析草稿",
  drivers: "司机",
  vehicles: "车辆",
  assignments: "派车记录",
  incidents: "异常",
};

const roleOptions: OrgMember["role"][] = ["admin", "dispatcher", "driver"];
const roleLabels: Record<OrgMember["role"], string> = {
  admin: "管理员",
  dispatcher: "调度员",
  driver: "司机",
};

const subscriptionStatusLabels: Record<string, string> = {
  active: "启用中",
  trialing: "试用中",
  paused: "已暂停",
  cancelled: "已取消",
};

const permissionLabels: Record<string, string> = {
  all: "全部权限",
  dashboard: "总览",
  orders: "订单",
  parser: "订单解析",
  dispatch: "派车",
  calendar: "日历",
  driver_monitor: "司机监控",
  vehicles: "车辆/司机",
  finance: "财务",
  settings: "设置",
  driver_mobile: "司机端",
};

const orgNameLabels: Record<string, string> = {
  Operations: "运营部",
  "Driver Operations": "司机运营部",
  "Back Office": "后台管理部",
  "Dispatch Team": "调度组",
  "Driver Team": "司机组",
  "Admin Team": "管理员组",
  Admin: "管理员",
};

function orgName(name?: string) {
  return name ? orgNameLabels[name] || name : "-";
}

function ReminderSettingsCard({ settings, saving, onSave }: { settings?: ReminderSettings; saving: boolean; onSave: (payload: Partial<ReminderSettings>) => void }) {
  const [draft, setDraft] = useState<ReminderSettings>({
    vehicle_inspection_days: settings?.vehicle_inspection_days ?? 20,
    vehicle_shaken_days: settings?.vehicle_shaken_days ?? 20,
    driver_health_check_days: settings?.driver_health_check_days ?? 30,
    driver_license_days: settings?.driver_license_days ?? 30,
  });

  useEffect(() => {
    if (settings) setDraft(settings);
  }, [settings]);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-slate-950">提醒规则配置</h2>
            <p className="mt-1 text-sm text-slate-500">车辆点检、车检、司机体检和驾照到期提前多少天进入提醒中心。</p>
          </div>
          <Button type="button" disabled={saving} onClick={() => onSave(draft)}>
            <Save size={16} />
            保存规则
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 md:grid-cols-2">
          <SettingNumber label="车辆点检提前天数" value={draft.vehicle_inspection_days} onChange={(value) => setDraft({ ...draft, vehicle_inspection_days: value })} />
          <SettingNumber label="车辆车检提前天数" value={draft.vehicle_shaken_days} onChange={(value) => setDraft({ ...draft, vehicle_shaken_days: value })} />
          <SettingNumber label="司机体检提前天数" value={draft.driver_health_check_days} onChange={(value) => setDraft({ ...draft, driver_health_check_days: value })} />
          <SettingNumber label="驾照到期提前天数" value={draft.driver_license_days} onChange={(value) => setDraft({ ...draft, driver_license_days: value })} />
        </div>
      </CardContent>
    </Card>
  );
}

function SettingNumber({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label className="grid gap-1 text-sm font-medium text-slate-600">
      {label}
      <input className="h-10 rounded-md border border-border bg-white px-3 text-sm text-slate-900 outline-none focus:border-primary" type="number" value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  );
}

type InviteForm = {
  username: string;
  password: string;
  role: OrgMember["role"];
  display_name: string;
  department_id: number | "";
  team_id: number | "";
  title: string;
  phone: string;
};

const emptyInviteForm: InviteForm = {
  username: "",
  password: "",
  role: "dispatcher",
  display_name: "",
  department_id: "",
  team_id: "",
  title: "",
  phone: "",
};

export function SettingsPage() {
  const queryClient = useQueryClient();
  const [inviteForm, setInviteForm] = useState<InviteForm>(emptyInviteForm);
  const overview = useQuery({ queryKey: ["billing-overview"], queryFn: api.billingOverview });
  const org = useQuery({ queryKey: ["org-overview"], queryFn: api.orgOverview });
  const reminderSettings = useQuery({ queryKey: ["reminder-settings"], queryFn: api.reminderSettings });

  const subscriptionMutation = useMutation({
    mutationFn: api.updateSubscription,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["billing-overview"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
  });

  const inviteMutation = useMutation({
    mutationFn: api.inviteMember,
    onSuccess: () => {
      setInviteForm(emptyInviteForm);
      queryClient.invalidateQueries({ queryKey: ["org-overview"] });
    },
  });

  const updateMemberMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<OrgMember> }) => api.updateMember(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["org-overview"] }),
  });

  const disableMemberMutation = useMutation({
    mutationFn: api.disableMember,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["org-overview"] }),
  });

  const updateSettings = useMutation({
    mutationFn: api.updateReminderSettings,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["reminder-settings"] }),
        queryClient.invalidateQueries({ queryKey: ["resource-reminders"] }),
        queryClient.invalidateQueries({ queryKey: ["notification-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] }),
      ]);
    },
  });

  if (overview.isLoading || org.isLoading) {
    return <div className="panel p-8 text-sm text-slate-500">正在加载设置...</div>;
  }
  if (overview.isError || !overview.data) {
    return <div className="panel p-8 text-sm text-red-600">套餐接口加载失败，请检查后端服务。</div>;
  }
  if (org.isError || !org.data) {
    return <div className="panel p-8 text-sm text-red-600">组织接口加载失败，需要管理员登录。</div>;
  }

  const data = overview.data;
  const subscription = data.subscription;
  const currentPlan = subscription.plan;
  const usageItems = Object.entries(data.usage.actual || {});
  const orgData = org.data;

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard title="当前套餐" value={currentPlan.name} icon={Crown} tone="blue" caption={currentPlan.monthly_price === 0 ? "免费" : `JPY ${currentPlan.monthly_price}/月`} />
        <KpiCard title="启用成员" value={orgData.summary.active_members} icon={UsersRound} tone="green" caption={`${orgData.summary.disabled_members} 已停用`} />
        <KpiCard title="已开功能" value={Object.values(data.feature_flags).filter(Boolean).length} icon={Zap} tone="violet" />
        <KpiCard title="订阅状态" value={subscriptionStatusLabels[subscription.status] || subscription.status} icon={ShieldCheck} tone="slate" />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardHeader>
            <h2 className="text-base font-bold text-slate-950">组织与团队</h2>
            <p className="mt-1 text-sm text-slate-500">管理当前公司的成员、部门、团队和角色边界。</p>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid gap-3 md:grid-cols-3">
              {orgData.departments.map((department) => (
                <div key={department.id} className="rounded-lg border border-border bg-slate-50 p-3">
                  <div className="text-sm font-bold text-slate-950">{orgName(department.name)}</div>
                  <div className="mt-1 text-xs text-slate-500">
                    {department.team_count || 0} 个团队 · {department.member_count || 0} 名成员
                  </div>
                </div>
              ))}
            </div>

            <div className="rounded-lg border border-border p-4">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-slate-950">邀请成员</h3>
                  <p className="text-xs text-slate-500">管理员可以创建账号，并分配角色、部门和团队。</p>
                </div>
                {inviteMutation.isError ? <span className="text-xs font-semibold text-red-600">{inviteMutation.error.message}</span> : null}
              </div>
              <div className="grid gap-3 md:grid-cols-4">
                <input className="h-9 rounded-md border border-border px-3 text-sm" placeholder="用户名" value={inviteForm.username} onChange={(event) => setInviteForm({ ...inviteForm, username: event.target.value })} />
                <input className="h-9 rounded-md border border-border px-3 text-sm" placeholder="显示名称" value={inviteForm.display_name} onChange={(event) => setInviteForm({ ...inviteForm, display_name: event.target.value })} />
                <input className="h-9 rounded-md border border-border px-3 text-sm" placeholder="临时密码" type="password" value={inviteForm.password} onChange={(event) => setInviteForm({ ...inviteForm, password: event.target.value })} />
                <select className="h-9 rounded-md border border-border px-3 text-sm" value={inviteForm.role} onChange={(event) => setInviteForm({ ...inviteForm, role: event.target.value as OrgMember["role"] })}>
                  {roleOptions.map((role) => (
                    <option key={role} value={role}>{roleLabels[role]}</option>
                  ))}
                </select>
                <select className="h-9 rounded-md border border-border px-3 text-sm" value={inviteForm.department_id} onChange={(event) => setInviteForm({ ...inviteForm, department_id: event.target.value ? Number(event.target.value) : "" })}>
                  <option value="">部门</option>
                  {orgData.departments.map((department) => (
                    <option key={department.id} value={department.id}>{orgName(department.name)}</option>
                  ))}
                </select>
                <select className="h-9 rounded-md border border-border px-3 text-sm" value={inviteForm.team_id} onChange={(event) => setInviteForm({ ...inviteForm, team_id: event.target.value ? Number(event.target.value) : "" })}>
                  <option value="">团队</option>
                  {orgData.teams.map((team) => (
                    <option key={team.id} value={team.id}>{orgName(team.name)}</option>
                  ))}
                </select>
                <input className="h-9 rounded-md border border-border px-3 text-sm" placeholder="职务" value={inviteForm.title} onChange={(event) => setInviteForm({ ...inviteForm, title: event.target.value })} />
                <input className="h-9 rounded-md border border-border px-3 text-sm" placeholder="电话" value={inviteForm.phone} onChange={(event) => setInviteForm({ ...inviteForm, phone: event.target.value })} />
              </div>
              <Button className="mt-3" disabled={inviteMutation.isPending} onClick={() => inviteMutation.mutate(inviteForm)}>
                邀请成员
              </Button>
            </div>

            <div className="overflow-hidden rounded-lg border border-border">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-normal text-slate-500">
                  <tr>
                    <th className="px-4 py-3">成员</th>
                    <th className="px-4 py-3">角色</th>
                    <th className="px-4 py-3">部门 / 团队</th>
                    <th className="px-4 py-3">状态</th>
                    <th className="px-4 py-3 text-right">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border bg-white">
                  {orgData.members.map((member) => (
                    <tr key={member.id}>
                      <td className="px-4 py-3">
                        <div className="font-bold text-slate-950">{member.display_name || member.username}</div>
                        <div className="text-xs text-slate-500">{member.username} · {orgName(member.title) || "操作员"} {member.phone ? `· ${member.phone}` : ""}</div>
                      </td>
                      <td className="px-4 py-3">
                        <select
                          className="h-8 rounded-md border border-border px-2 text-xs font-semibold"
                          value={member.role}
                          disabled={!member.is_active || updateMemberMutation.isPending}
                          onChange={(event) => updateMemberMutation.mutate({ id: member.id, payload: { role: event.target.value as OrgMember["role"] } })}
                        >
                          {roleOptions.map((role) => (
                            <option key={role} value={role}>{roleLabels[role]}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        <div>{orgName(member.department_name)}</div>
                        <div className="text-xs text-slate-500">{orgName(member.team_name)}</div>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={member.is_active ? "active" : "disabled"} />
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Button variant="secondary" disabled={!member.is_active || disableMemberMutation.isPending} onClick={() => disableMemberMutation.mutate(member.id)}>
                          停用
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <ReminderSettingsCard
            settings={reminderSettings.data}
            saving={updateSettings.isPending}
            onSave={(payload) => updateSettings.mutate(payload)}
          />

          <Card>
            <CardHeader>
              <h2 className="text-base font-bold text-slate-950">角色权限</h2>
              <p className="mt-1 text-sm text-slate-500">当前系统的轻量角色边界。</p>
            </CardHeader>
            <CardContent className="space-y-3">
              {Object.entries(orgData.role_permissions).map(([role, permissions]) => (
                <div key={role} className="rounded-lg border border-border p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-sm font-bold text-slate-950">{roleLabels[role as OrgMember["role"]] || role}</span>
                    <StatusBadge status={role === "admin" ? "active" : role} />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {permissions.map((permission) => (
                      <span key={permission} className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-600">{permissionLabels[permission] || permission}</span>
                    ))}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <h2 className="text-base font-bold text-slate-950">用量</h2>
              <p className="mt-1 text-sm text-slate-500">当前租户限制和本月用量。</p>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {usageItems.map(([key, value]) => {
                  const status = data.usage.limit_status[key];
                  return (
                    <div key={key} className="rounded-md border border-border p-3">
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-semibold text-slate-900">{usageLabels[key] || key}</span>
                        <span className="text-slate-500">{value}{status?.limit ? ` / ${status.limit}` : ""}</span>
                      </div>
                      {status?.limit ? (
                        <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
                          <div className={`h-full ${status.exceeded ? "bg-red-500" : "bg-blue-500"}`} style={{ width: `${Math.min(status.percent, 100)}%` }} />
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardHeader>
            <h2 className="text-base font-bold text-slate-950">套餐</h2>
            <p className="mt-1 text-sm text-slate-500">演示用套餐切换，当前未接入真实支付。</p>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 lg:grid-cols-3">
              {data.plans.map((plan) => (
                <PlanCard
                  key={plan.code}
                  plan={plan}
                  active={plan.code === subscription.plan_code}
                  disabled={subscriptionMutation.isPending}
                  onSelect={() => subscriptionMutation.mutate(plan.code)}
                />
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-base font-bold text-slate-950">功能开关</h2>
            <p className="mt-1 text-sm text-slate-500">功能可用范围跟随当前租户套餐。</p>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 md:grid-cols-2">
              {Object.entries(data.feature_flags).map(([key, enabled]) => (
                <div key={key} className="flex items-center justify-between rounded-md border border-border bg-white px-4 py-3">
                  <span className="text-sm font-semibold text-slate-800">{featureLabels[key] || key}</span>
                  <StatusBadge status={enabled ? "enabled" : "disabled"} />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

function PlanCard({ plan, active, disabled, onSelect }: { plan: Plan; active: boolean; disabled: boolean; onSelect: () => void }) {
  const enabledFeatures = Object.entries(plan.features).filter(([, enabled]) => enabled);
  return (
    <div className={`rounded-lg border p-4 ${active ? "border-blue-300 bg-blue-50/50" : "border-border bg-white"}`}>
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-bold text-slate-950">{plan.name}</h3>
          <p className="mt-1 text-sm text-slate-500">{plan.monthly_price === 0 ? "免费" : `JPY ${plan.monthly_price}/月`}</p>
        </div>
        {active ? <StatusBadge status="active" /> : null}
      </div>
      <div className="mt-4 space-y-2 text-sm text-slate-600">
        {enabledFeatures.slice(0, 6).map(([key]) => (
          <div key={key} className="flex items-center gap-2">
            <CheckCircle2 size={15} className="text-emerald-600" />
            {featureLabels[key] || key}
          </div>
        ))}
      </div>
      <div className="mt-4 text-xs text-slate-500">
        订单 {plan.limits.orders_per_month ?? "-"} / 月 · 司机 {plan.limits.drivers ?? "-"} · 车辆 {plan.limits.vehicles ?? "-"}
      </div>
      <Button className="mt-4 w-full" variant={active ? "secondary" : "primary"} disabled={active || disabled} onClick={onSelect}>
        {active ? "当前套餐" : "切换套餐"}
      </Button>
    </div>
  );
}
