import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, UserPlus, UserX, Unlink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { ErrorPanel } from "@/components/OperationalState";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/services/apiClient";
import type { AccountRole, ManagedAccount } from "@/types/api";

const roleLabels: Record<AccountRole, string> = {
  admin: "管理账号",
  dispatcher: "调度",
  operations_manager: "运行管理",
  driver: "司机",
};

const roleOptions: AccountRole[] = ["dispatcher", "operations_manager", "driver", "admin"];

type AccountForm = {
  role: AccountRole;
  display_name: string;
  phone: string;
};

const emptyForm: AccountForm = {
  role: "dispatcher",
  display_name: "",
  phone: "",
};

export function AccountManagementPanel() {
  const queryClient = useQueryClient();
  const me = useQuery({ queryKey: ["auth-me"], queryFn: api.me, staleTime: 60_000 });
  const overview = useQuery({
    queryKey: ["account-overview"],
    queryFn: api.accountOverview,
    enabled: me.data?.user.role === "admin",
  });
  const [form, setForm] = useState<AccountForm>(emptyForm);
  const [message, setMessage] = useState("");

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["account-overview"] });
    queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
  };

  const createMutation = useMutation({
    mutationFn: api.createAccount,
    onSuccess: () => {
      setForm(emptyForm);
      setMessage("账号已新增，初始密码为手机号后 4 位。");
      invalidate();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<ManagedAccount> & { confirm_driver_role_change?: boolean } }) => api.updateAccount(id, payload),
    onSuccess: () => {
      setMessage("账号信息已更新。");
      invalidate();
    },
  });

  const disableMutation = useMutation({
    mutationFn: api.disableAccount,
    onSuccess: () => {
      setMessage("账号已停用，历史数据已保留。");
      invalidate();
    },
  });

  const resetMutation = useMutation({
    mutationFn: api.resetAccountPassword,
    onSuccess: () => {
      setMessage("密码已重置为手机号后 4 位。");
      invalidate();
    },
  });

  const unbindMutation = useMutation({
    mutationFn: api.unbindAccountWechat,
    onSuccess: () => {
      setMessage("微信绑定已解除，下次小程序登录会重新绑定。");
      invalidate();
    },
  });

  const error = useMemo(() => {
    const err = createMutation.error || updateMutation.error || disableMutation.error || resetMutation.error || unbindMutation.error;
    return err instanceof Error ? err.message : "";
  }, [createMutation.error, updateMutation.error, disableMutation.error, resetMutation.error, unbindMutation.error]);

  if (me.data && me.data.user.role !== "admin") {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-normal text-blue-600">ACCOUNT CONTROL</p>
            <h2 className="mt-1 text-lg font-black text-slate-950">账号管理</h2>
            <p className="mt-1 text-sm text-slate-500">按角色维护账号；司机台账中已有手机号的司机会自动进入账号列表。</p>
          </div>
          <div className="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700">仅管理员可见</div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="rounded-xl border border-border bg-slate-50 p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-black text-slate-950">
            <UserPlus size={16} />
            新增账号
          </div>
          <div className="grid gap-3 lg:grid-cols-[180px_1fr_1fr_auto]">
            <select
              className="h-10 rounded-lg border border-border bg-white px-3 text-sm font-semibold text-slate-800"
              value={form.role}
              onChange={(event) => setForm({ ...form, role: event.target.value as AccountRole })}
            >
              {roleOptions.map((role) => (
                <option key={role} value={role}>
                  {roleLabels[role]}
                </option>
              ))}
            </select>
            <input
              className="h-10 rounded-lg border border-border bg-white px-3 text-sm outline-none focus:border-blue-500"
              placeholder="姓名"
              value={form.display_name}
              onChange={(event) => setForm({ ...form, display_name: event.target.value })}
            />
            <input
              className="h-10 rounded-lg border border-border bg-white px-3 text-sm outline-none focus:border-blue-500"
              placeholder="手机号"
              value={form.phone}
              onChange={(event) => setForm({ ...form, phone: event.target.value })}
            />
            <Button
              disabled={createMutation.isPending || !form.display_name || !form.phone}
              onClick={() => createMutation.mutate(form)}
            >
              <UserPlus size={16} />
              新增
            </Button>
          </div>
          <p className="mt-2 text-xs text-slate-500">司机账号必须匹配司机台账手机号；非司机账号会建立管理人员资料。初始密码默认手机号后 4 位。</p>
        </div>

        {message ? <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">{message}</div> : null}
        {error ? <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">{error}</div> : null}
        {overview.isError ? (
          <ErrorPanel title="账号列表加载失败" description="请检查后端账号管理 API 是否正常。" requestPath="/api/accounts/overview" onRetry={() => overview.refetch()} />
        ) : null}

        <div className="grid gap-4 2xl:grid-cols-2">
          {(overview.data?.roles || []).map((group) => (
            <section key={group.role} className="overflow-hidden rounded-xl border border-border bg-white">
              <div className="border-b border-border bg-slate-50 px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h3 className="text-base font-black text-slate-950">{group.label}</h3>
                    <p className="mt-1 text-xs text-slate-500">总 {group.total} 人 · 启用 {group.active} · 停用 {group.disabled}</p>
                  </div>
                  <div className="flex gap-2 text-xs font-bold">
                    <span className="rounded-full bg-emerald-50 px-2 py-1 text-emerald-700">已绑微信 {group.wechat_bound}</span>
                    <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-600">未绑 {group.wechat_unbound}</span>
                  </div>
                </div>
              </div>
              <div className="divide-y divide-border">
                {group.accounts.length ? (
                  group.accounts.map((account) => (
                    <AccountRow
                      key={account.id}
                      account={account}
                      onDisable={() => {
                        if (window.confirm(`确认停用 ${account.display_name || account.username}？历史数据会保留。`)) disableMutation.mutate(account.id);
                      }}
                      onReset={() => {
                        if (window.confirm("确认将密码重置为手机号后 4 位？")) resetMutation.mutate(account.id);
                      }}
                      onUnbind={() => {
                        if (window.confirm("确认解除微信绑定？下次小程序登录会重新绑定当前微信。")) unbindMutation.mutate(account.id);
                      }}
                      onRoleChange={(role) => {
                        const confirmDriver = account.role === "driver" && role !== "driver";
                        if (confirmDriver && !window.confirm("司机账号改成管理角色风险较高，确认继续？")) return;
                        updateMutation.mutate({ id: account.id, payload: { role, confirm_driver_role_change: confirmDriver } });
                      }}
                    />
                  ))
                ) : (
                  <div className="px-4 py-8 text-center text-sm text-slate-500">暂无账号</div>
                )}
              </div>
            </section>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function AccountRow({
  account,
  onDisable,
  onReset,
  onUnbind,
  onRoleChange,
}: {
  account: ManagedAccount;
  onDisable: () => void;
  onReset: () => void;
  onUnbind: () => void;
  onRoleChange: (role: AccountRole) => void;
}) {
  return (
    <div className="grid gap-3 px-4 py-4 xl:grid-cols-[1.2fr_1fr_1fr_auto] xl:items-center">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-black text-slate-950">{account.display_name || account.username}</span>
          <StatusBadge status={account.is_active ? "active" : "disabled"} />
          <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${account.wx_bind_status === "bound" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>
            {account.wx_bind_status === "bound" ? "微信已绑定" : "微信未绑定"}
          </span>
        </div>
        <div className="mt-1 text-xs text-slate-500">{account.phone || "-"} · {profileLabel(account.profile_type)} #{account.profile_id || "-"}</div>
      </div>
      <div className="text-xs text-slate-500">
        <div>绑定时间：{formatDate(account.wx_bound_at)}</div>
        <div>最近登录：{formatDate(account.last_login_at)}</div>
      </div>
      <div>
        <select
          className="h-9 w-full rounded-lg border border-border bg-white px-3 text-xs font-bold text-slate-800"
          value={account.role}
          disabled={account.role === "admin"}
          onChange={(event) => onRoleChange(event.target.value as AccountRole)}
        >
          {roleOptions.map((role) => (
            <option key={role} value={role}>
              {roleLabels[role]}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-wrap justify-start gap-2 xl:justify-end">
        <Button variant="secondary" disabled={!account.is_active} onClick={onDisable}>
          <UserX size={15} />
          停用
        </Button>
        <Button variant="secondary" onClick={onReset}>
          <KeyRound size={15} />
          重置
        </Button>
        <Button variant="secondary" disabled={account.wx_bind_status !== "bound"} onClick={onUnbind}>
          <Unlink size={15} />
          解绑微信
        </Button>
      </div>
    </div>
  );
}

function formatDate(value?: string) {
  if (!value) return "-";
  return value.replace("T", " ").slice(0, 16);
}

function profileLabel(value?: string) {
  if (value === "driver") return "司机资料";
  if (value === "operator") return "管理资料";
  return value || "-";
}
