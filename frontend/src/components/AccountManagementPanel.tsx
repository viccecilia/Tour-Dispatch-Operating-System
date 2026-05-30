import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Unlink, UserCheck, UserPlus, UserX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { ErrorPanel } from "@/components/OperationalState";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/services/apiClient";
import type { AccountRole, AuthUser, ManagedAccount } from "@/types/api";

const roleLabels: Record<AccountRole, string> = {
  admin: "管理员",
  dispatcher: "调度",
  operations_manager: "运行管理",
  driver: "司机",
};

const roleOptions: AccountRole[] = ["admin", "dispatcher", "operations_manager", "driver"];

type AccountForm = {
  role: AccountRole;
  display_name: string;
  phone: string;
  operator_code: string;
};

const emptyForm: AccountForm = {
  role: "dispatcher",
  display_name: "",
  phone: "",
  operator_code: "",
};

export function AccountManagementPanel({ currentUser }: { currentUser: AuthUser }) {
  const queryClient = useQueryClient();
  const overview = useQuery({
    queryKey: ["account-overview"],
    queryFn: api.accountOverview,
    enabled: currentUser.role === "admin",
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
      setMessage("账号已新增，初始密码为手机号后 6 位。");
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

  const enableMutation = useMutation({
    mutationFn: api.enableAccount,
    onSuccess: () => {
      setMessage("账号已启用。");
      invalidate();
    },
  });

  const resetMutation = useMutation({
    mutationFn: api.resetAccountPassword,
    onSuccess: () => {
      setMessage("密码已重置为手机号后 6 位。");
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
    const err = createMutation.error || updateMutation.error || disableMutation.error || enableMutation.error || resetMutation.error || unbindMutation.error;
    return err instanceof Error ? err.message : "";
  }, [createMutation.error, updateMutation.error, disableMutation.error, enableMutation.error, resetMutation.error, unbindMutation.error]);

  if (currentUser.role !== "admin") {
    return (
      <Card>
        <CardHeader>
          <p className="text-xs font-bold uppercase tracking-normal text-blue-600">ACCOUNT CONTROL</p>
          <h2 className="mt-1 text-lg font-black text-slate-950">账号管理</h2>
          <p className="mt-1 text-sm text-slate-500">账号新增、修改、停用、启用和密码重置只允许管理员操作。</p>
        </CardHeader>
        <CardContent>
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-800">
            当前登录角色是 {roleLabels[currentUser.role as AccountRole] || currentUser.role}，没有账号管理权限。请使用管理员账号登录。
          </div>
        </CardContent>
      </Card>
    );
  }

  const isDriver = form.role === "driver";
  const canCreate = Boolean(form.display_name.trim() && form.phone.trim() && (isDriver || form.operator_code.trim()));

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-normal text-blue-600">ACCOUNT CONTROL</p>
            <h2 className="mt-1 text-lg font-black text-slate-950">账号管理</h2>
            <p className="mt-1 text-sm text-slate-500">所有端统一用手机号登录；管理员、调度、运行管理账号需要录入短代码，用于订单来源和操作追踪。</p>
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
          <div className="grid gap-3 xl:grid-cols-[160px_1fr_180px_1fr_auto]">
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
              className="h-10 rounded-lg border border-border bg-white px-3 text-sm uppercase outline-none focus:border-blue-500 disabled:bg-slate-100"
              placeholder={isDriver ? "司机不用填代码" : "账号代码"}
              value={form.operator_code}
              disabled={isDriver}
              onChange={(event) => setForm({ ...form, operator_code: event.target.value.toUpperCase() })}
            />
            <input
              className="h-10 rounded-lg border border-border bg-white px-3 text-sm outline-none focus:border-blue-500"
              placeholder="手机号"
              value={form.phone}
              onChange={(event) => setForm({ ...form, phone: event.target.value })}
            />
            <Button disabled={createMutation.isPending || !canCreate} onClick={() => createMutation.mutate(form)}>
              <UserPlus size={16} />
              新增
            </Button>
          </div>
          <p className="mt-2 text-xs text-slate-500">司机账号必须匹配司机台账手机号；非司机账号会建立管理人员资料。初始密码默认手机号后 6 位，可后台重置。</p>
        </div>

        {message ? <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">{message}</div> : null}
        {error ? <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">{error}</div> : null}
        {overview.isError ? (
          <ErrorPanel title="账号列表加载失败" description="请检查后台账号管理 API 是否正常。" requestPath="/api/accounts/overview" onRetry={() => overview.refetch()} />
        ) : null}
        {overview.isLoading ? (
          <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm font-semibold text-blue-700">正在加载账号列表...</div>
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
                      onEnable={() => {
                        if (window.confirm(`确认启用 ${account.display_name || account.username}？`)) enableMutation.mutate(account.id);
                      }}
                      onReset={() => {
                        if (window.confirm("确认将密码重置为手机号后 6 位？")) resetMutation.mutate(account.id);
                      }}
                      onUnbind={() => {
                        if (window.confirm("确认解除微信绑定？下次小程序登录会重新绑定当前微信。")) unbindMutation.mutate(account.id);
                      }}
                      onCodeChange={(operator_code) => updateMutation.mutate({ id: account.id, payload: { operator_code } })}
                      onProfileChange={(payload) => updateMutation.mutate({ id: account.id, payload })}
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
  onEnable,
  onReset,
  onUnbind,
  onCodeChange,
  onProfileChange,
}: {
  account: ManagedAccount;
  onDisable: () => void;
  onEnable: () => void;
  onReset: () => void;
  onUnbind: () => void;
  onCodeChange: (operatorCode: string) => void;
  onProfileChange: (payload: Pick<ManagedAccount, "display_name" | "phone">) => void;
}) {
  const [codeDraft, setCodeDraft] = useState(account.operator_code || "");
  const [nameDraft, setNameDraft] = useState(account.display_name || account.username || "");
  const [phoneDraft, setPhoneDraft] = useState(account.phone || "");
  const isOperator = account.role !== "driver";

  return (
    <div className="grid gap-3 px-4 py-4 xl:grid-cols-[1.2fr_1fr_1fr_auto] xl:items-center">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            className="h-9 min-w-[180px] rounded-lg border border-border bg-white px-3 text-sm font-black text-slate-950 outline-none focus:border-blue-500"
            value={nameDraft}
            placeholder="姓名"
            onChange={(event) => setNameDraft(event.target.value)}
            onBlur={() => {
              const nextName = nameDraft.trim();
              if ((account.display_name || account.username || "") !== nextName) {
                onProfileChange({ display_name: nextName, phone: phoneDraft.trim() });
              }
            }}
          />
          <StatusBadge status={account.is_active ? "active" : "disabled"} />
          <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${account.wx_bind_status === "bound" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>
            {account.wx_bind_status === "bound" ? "微信已绑定" : "微信未绑定"}
          </span>
        </div>
        <div className="mt-2 grid max-w-[360px] gap-1">
          <label className="text-[11px] font-bold text-slate-500">手机号</label>
          <input
            className="h-9 rounded-lg border border-border bg-white px-3 text-xs font-bold text-slate-800 outline-none focus:border-blue-500"
            value={phoneDraft}
            placeholder="可留空，留空后不能用手机号登录"
            onChange={(event) => setPhoneDraft(event.target.value)}
            onBlur={() => {
              const nextPhone = phoneDraft.trim();
              if ((account.phone || "") !== nextPhone) {
                onProfileChange({ display_name: nameDraft.trim(), phone: nextPhone });
              }
            }}
          />
          <div className="text-xs text-slate-500">{profileLabel(account.profile_type)} #{account.profile_id || "-"}</div>
        </div>
      </div>
      <div className="grid gap-1 text-xs text-slate-500">
        {isOperator ? (
          <label className="grid gap-1">
            <span className="font-bold text-slate-500">账号代码</span>
            <input
              className="h-9 rounded-lg border border-border bg-white px-3 text-xs font-bold uppercase text-slate-800"
              value={codeDraft}
              placeholder="如 OP01"
              onChange={(event) => setCodeDraft(event.target.value.toUpperCase())}
              onBlur={() => {
                if ((account.operator_code || "") !== codeDraft.trim()) onCodeChange(codeDraft.trim());
              }}
            />
          </label>
        ) : (
          <div>司机代码：{account.driver_code || "-"}</div>
        )}
        <div>最近登录：{formatDate(account.last_login_at)}</div>
      </div>
      <div>
        <div className="inline-flex h-9 w-full items-center rounded-lg border border-border bg-slate-50 px-3 text-xs font-bold text-slate-700">
          {roleLabels[account.role] || account.role}
        </div>
      </div>
      <div className="flex flex-wrap justify-start gap-2 xl:justify-end">
        {account.is_active ? (
          <Button variant="secondary" onClick={onDisable}>
            <UserX size={15} />
            停用
          </Button>
        ) : (
          <Button variant="secondary" onClick={onEnable}>
            <UserCheck size={15} />
            启用
          </Button>
        )}
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
