import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save, ShieldCheck, UsersRound } from "lucide-react";
import { AccountManagementPanel } from "@/components/AccountManagementPanel";
import { KpiCard } from "@/components/KpiCard";
import { ErrorPanel } from "@/components/OperationalState";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/services/apiClient";
import type { OrgMember, OrgOverview, ReminderSettings } from "@/types/api";

const roleOptions: OrgMember["role"][] = ["admin", "dispatcher", "operations_manager", "driver"];
const roleLabels: Record<OrgMember["role"], string> = {
  admin: "管理员",
  dispatcher: "调度",
  operations_manager: "运行管理",
  driver: "司机",
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
  Operations: "运行部",
  "Driver Operations": "司机运行部",
  "Back Office": "后台管理部",
  "Dispatch Team": "调度组",
  "Driver Team": "司机组",
  "Admin Team": "管理组",
  Admin: "管理员",
};

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

function orgName(name?: string) {
  return name ? orgNameLabels[name] || name : "-";
}

function fallbackOrg(): OrgOverview {
  return {
    departments: [{ id: 0, name: "运行团队", member_count: 0, team_count: 0 }],
    teams: [{ id: 0, name: "调度组", department_id: 0, member_count: 0 }],
    members: [],
    role_permissions: {
      admin: ["all"],
      dispatcher: ["dashboard", "orders", "parser", "dispatch", "calendar", "driver_monitor"],
      operations_manager: ["dashboard", "dispatch", "calendar", "driver_monitor", "vehicles"],
      driver: ["driver_mobile"],
    },
    summary: { departments: 1, teams: 1, members: 0, active_members: 0, disabled_members: 0 },
  };
}

export function SettingsPage() {
  const queryClient = useQueryClient();
  const [inviteForm, setInviteForm] = useState<InviteForm>(emptyInviteForm);
  const org = useQuery({ queryKey: ["org-overview"], queryFn: api.orgOverview });
  const reminderSettings = useQuery({ queryKey: ["reminder-settings"], queryFn: api.reminderSettings });

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

  const orgData = org.data ?? fallbackOrg();

  return (
    <div className="space-y-6">
      <section className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <Card>
          <CardHeader>
            <h2 className="text-base font-bold text-slate-950">系统信息</h2>
            <p className="mt-1 text-sm text-slate-500">当前内部运营版只显示账号、角色、提醒和基础组织设置。</p>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2">
            <Info label="租户" value="Demo Travel Company" />
            <Info label="默认语言" value="中文" />
            <Info label="演示模式" value="已开启" />
            <Info label="API 状态" value={org.isError || reminderSettings.isError ? "局部异常" : "在线"} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <h2 className="text-base font-bold text-slate-950">账号策略</h2>
            <p className="mt-1 text-sm text-slate-500">手机号登录，密码不明文展示，只允许管理员重置为手机号后 4 位。</p>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-3">
            <Info label="司机端" value="强制微信绑定" />
            <Info label="调度小程序" value="强制微信绑定" />
            <Info label="Web 管理端" value="角色权限控制" />
          </CardContent>
        </Card>
      </section>

      {org.isError || !org.data ? (
        <ErrorPanel title="组织接口读取失败" description="成员管理区域保留结构，管理员登录或后端恢复后可继续维护团队。" requestPath="/api/org/overview" onRetry={() => org.refetch()} />
      ) : null}

      <AccountManagementPanel />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard title="启用成员" value={orgData.summary.active_members} icon={UsersRound} tone="green" caption={`${orgData.summary.disabled_members} 已停用`} />
        <KpiCard title="角色数量" value={Object.keys(orgData.role_permissions).length} icon={ShieldCheck} tone="blue" caption="按角色控制权限" />
        <KpiCard title="组织部门" value={orgData.summary.departments} icon={UsersRound} tone="slate" caption={`${orgData.summary.teams} 个团队`} />
        <KpiCard title="提醒规则" value="已配置" icon={ShieldCheck} tone="violet" caption="车辆、司机到期提醒" />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardHeader>
            <h2 className="text-base font-bold text-slate-950">组织成员</h2>
            <p className="mt-1 text-sm text-slate-500">这里保留轻量组织维护；正式账号、微信绑定和密码重置请使用上方账号管理。</p>
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
                  <p className="text-xs text-slate-500">用于维护内部组织结构；账号登录请优先使用账号管理板块。</p>
                </div>
                {inviteMutation.isError ? <span className="text-xs font-semibold text-red-600">{inviteMutation.error.message}</span> : null}
              </div>
              <div className="grid gap-3 md:grid-cols-4">
                <input className="h-9 rounded-md border border-border px-3 text-sm" placeholder="用户名" value={inviteForm.username} onChange={(event) => setInviteForm({ ...inviteForm, username: event.target.value })} />
                <input className="h-9 rounded-md border border-border px-3 text-sm" placeholder="显示姓名" value={inviteForm.display_name} onChange={(event) => setInviteForm({ ...inviteForm, display_name: event.target.value })} />
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

          {reminderSettings.isError ? (
            <ErrorPanel title="提醒规则接口读取失败" description="可先使用默认提醒规则，后端恢复后再保存配置。" requestPath="/api/settings/reminders" onRetry={() => reminderSettings.refetch()} />
          ) : null}

          <Card>
            <CardHeader>
              <h2 className="text-base font-bold text-slate-950">角色权限</h2>
              <p className="mt-1 text-sm text-slate-500">财务和账号管理只对管理员开放，运行管理不显示财务入口。</p>
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
        </div>
      </section>
    </div>
  );
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
            <p className="mt-1 text-sm text-slate-500">点检、车检、体检和驾照到期提前提醒，不写死在代码里。</p>
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

function Info({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-border bg-white p-3">
      <div className="text-xs font-semibold text-slate-500">{label}</div>
      <div className="mt-1 text-sm font-bold text-slate-950">{value}</div>
    </div>
  );
}
