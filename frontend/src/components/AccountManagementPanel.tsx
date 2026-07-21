import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Check, KeyRound, Pencil, Save, Unlink, UserCheck, UserPlus, UserX, X } from "lucide-react";
import { isPlatformUser } from "@/auth/permissions";
import { ErrorPanel } from "@/components/OperationalState";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
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
  const platform = isPlatformUser(currentUser);
  const [selectedTenantId, setSelectedTenantId] = useState<string>(platform ? "all" : "");
  const tenantParam = platform ? selectedTenantId : undefined;
  const selectedTenantNumber = selectedTenantId && selectedTenantId !== "all" ? Number(selectedTenantId) : undefined;
  const [form, setForm] = useState<AccountForm>(emptyForm);
  const [message, setMessage] = useState("");

  const tenants = useQuery({
    queryKey: ["platform-tenants"],
    queryFn: api.platformTenants,
    enabled: platform,
    staleTime: 60_000,
  });

  const overview = useQuery({
    queryKey: ["account-overview", tenantParam || "self"],
    queryFn: () => api.accountOverview({ tenant_id: tenantParam }),
    enabled: currentUser.role === "admin",
  });

  const currentTenant = tenants.data?.find((tenant) => String(tenant.id) === selectedTenantId);
  const companyCode = platform ? currentTenant?.slug || "请选择公司" : currentUser.company_code || currentUser.tenant?.slug || "公司代码";
  const allCompanyView = platform && selectedTenantId === "all";

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["account-overview"] });
    queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
  };

  const scopedCreatePayload = () => ({
    ...form,
    ...(platform ? { tenant_id: selectedTenantNumber } : {}),
  });

  const scopedTenantParam = () => (platform ? selectedTenantNumber : undefined);

  const createMutation = useMutation({
    mutationFn: () => api.createAccount(scopedCreatePayload()),
    onSuccess: () => {
      setForm(emptyForm);
      setMessage("账号已新增。登录名统一使用手机号数字，初始密码为手机号后 6 位。");
      invalidate();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<ManagedAccount> & { confirm_driver_role_change?: boolean } }) =>
      api.updateAccount(id, { ...payload, tenant_id: payload.tenant_id || scopedTenantParam() }),
    onSuccess: () => {
      setMessage("账号信息已更新。");
      invalidate();
    },
  });

  const disableMutation = useMutation({
    mutationFn: (account: ManagedAccount) => api.disableAccount(account.id, account.tenant_id),
    onSuccess: () => {
      setMessage("账号已停用。");
      invalidate();
    },
  });

  const enableMutation = useMutation({
    mutationFn: (account: ManagedAccount) => api.enableAccount(account.id, account.tenant_id),
    onSuccess: () => {
      setMessage("账号已启用。");
      invalidate();
    },
  });

  const resetMutation = useMutation({
    mutationFn: (account: ManagedAccount) => api.resetAccountPassword(account.id, account.tenant_id),
    onSuccess: () => {
      setMessage("密码已重置为手机号后 6 位。");
      invalidate();
    },
  });

  const unbindMutation = useMutation({
    mutationFn: (account: ManagedAccount) => api.unbindAccountWechat(account.id, account.tenant_id),
    onSuccess: () => {
      setMessage("微信绑定已解除。");
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
          <p className="mt-1 text-sm text-slate-500">只有管理员可以维护账号、密码和微信绑定。</p>
        </CardHeader>
      </Card>
    );
  }

  const isDriver = form.role === "driver";
  const canCreate = Boolean(form.display_name.trim() && form.phone.trim() && (isDriver || form.operator_code.trim()) && (!platform || selectedTenantNumber));

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-normal text-blue-600">ACCOUNT CONTROL</p>
            <h2 className="mt-1 text-lg font-black text-slate-950">{platform ? "平台账号管理" : "账号管理"}</h2>
            <p className="mt-1 text-sm text-slate-500">
              {platform
                ? "平台管理员可按公司查看、启停、重置和解绑账号。新增账号前请先选择具体公司。"
                : `统一使用本公司手机号登录，初始密码为手机号后 6 位。`}
            </p>
          </div>
          <div className="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700">
            {platform ? "平台管理员可见" : "仅管理员可见"}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {platform ? (
          <div className="rounded-xl border border-blue-100 bg-blue-50/70 p-3">
            <div className="grid gap-3 md:grid-cols-[180px_minmax(260px,360px)_1fr] md:items-center">
              <div className="flex items-center gap-2 text-sm font-black text-slate-950">
                <Building2 size={16} />
                公司筛选
              </div>
              <select
                className="h-9 rounded-lg border border-border bg-white px-3 text-sm font-semibold text-slate-800"
                value={selectedTenantId}
                onChange={(event) => {
                  setSelectedTenantId(event.target.value);
                  setMessage("");
                }}
              >
                <option value="all">全部公司</option>
                {(tenants.data || []).map((tenant) => (
                  <option key={tenant.id} value={tenant.id}>
                    {tenant.name} {tenant.slug ? `(${tenant.slug})` : ""}
                  </option>
                ))}
              </select>
              <p className="text-xs font-semibold text-slate-600">
                {allCompanyView ? "当前查看全部公司账号；新增账号和资料修改需要先选择具体公司。" : `正在维护 ${currentTenant?.name || "所选公司"} 的账号。`}
              </p>
            </div>
          </div>
        ) : null}

        <div className="rounded-xl border border-border bg-slate-50 p-3">
          <div className="mb-3 flex items-center gap-2 text-sm font-black text-slate-950">
            <UserPlus size={16} />
            新增账号
          </div>
          <div className="grid gap-2 xl:grid-cols-[140px_1fr_170px_210px_auto]">
            <select className="h-9 rounded-lg border border-border bg-white px-3 text-sm font-semibold text-slate-800" value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value as AccountRole })}>
              {roleOptions.map((role) => (
                <option key={role} value={role}>{roleLabels[role]}</option>
              ))}
            </select>
            <input className="h-9 rounded-lg border border-border bg-white px-3 text-sm outline-none focus:border-blue-500" placeholder="姓名" value={form.display_name} onChange={(event) => setForm({ ...form, display_name: event.target.value })} />
            <input className="h-9 rounded-lg border border-border bg-white px-3 text-sm uppercase outline-none focus:border-blue-500 disabled:bg-slate-100" placeholder={isDriver ? "司机使用台账资料" : "账号代码"} value={form.operator_code} disabled={isDriver} onChange={(event) => setForm({ ...form, operator_code: event.target.value.toUpperCase() })} />
            <input className="h-9 rounded-lg border border-border bg-white px-3 text-sm outline-none focus:border-blue-500" placeholder="手机号" value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} />
            <Button disabled={createMutation.isPending || !canCreate || allCompanyView} onClick={() => createMutation.mutate()} className="h-9">
              <UserPlus size={16} />
              新增
            </Button>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            {allCompanyView ? "请先在公司筛选中选择具体公司，再新增账号。" : `登录名会按 ${companyCode}-手机号 生成；司机账号必须匹配该公司已录入司机手机号。`}
          </p>
        </div>

        {message ? <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">{message}</div> : null}
        {error ? <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">{error}</div> : null}
        {overview.isError ? <ErrorPanel title="账号列表加载失败" description="请检查账号管理 API 是否正常。" requestPath="/api/accounts/overview" onRetry={() => overview.refetch()} /> : null}
        {overview.isLoading ? <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm font-semibold text-blue-700">正在加载账号列表...</div> : null}

        <div className="grid gap-3 2xl:grid-cols-2">
          {(overview.data?.roles || []).map((group) => (
            <section key={group.role} className="overflow-hidden rounded-xl border border-border bg-white">
              <div className="border-b border-border bg-slate-50 px-4 py-2.5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h3 className="text-base font-black text-slate-950">{roleLabels[group.role] || group.label}</h3>
                    <p className="mt-0.5 text-xs text-slate-500">总 {group.total} 人 · 启用 {group.active} · 停用 {group.disabled}</p>
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
                      platform={platform}
                      allCompanyView={allCompanyView}
                      saving={updateMutation.isPending}
                      onDisable={() => {
                        if (window.confirm(`确认停用 ${account.display_name || account.username}？`)) disableMutation.mutate(account);
                      }}
                      onEnable={() => {
                        if (window.confirm(`确认启用 ${account.display_name || account.username}？`)) enableMutation.mutate(account);
                      }}
                      onReset={() => {
                        if (window.confirm("确认将密码重置为手机号后 6 位？")) resetMutation.mutate(account);
                      }}
                      onUnbind={() => {
                        if (window.confirm("确认解除微信绑定？")) unbindMutation.mutate(account);
                      }}
                      onCodeChange={(operator_code) => updateMutation.mutate({ id: account.id, payload: { operator_code, tenant_id: account.tenant_id } })}
                      onDisplayNameChange={(display_name) => updateMutation.mutate({ id: account.id, payload: { display_name, tenant_id: account.tenant_id } })}
                      onPhoneChange={(phone) => updateMutation.mutate({ id: account.id, payload: { phone, tenant_id: account.tenant_id } })}
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
  platform,
  allCompanyView,
  saving,
  onDisable,
  onEnable,
  onReset,
  onUnbind,
  onCodeChange,
  onDisplayNameChange,
  onPhoneChange,
}: {
  account: ManagedAccount;
  platform: boolean;
  allCompanyView: boolean;
  saving: boolean;
  onDisable: () => void;
  onEnable: () => void;
  onReset: () => void;
  onUnbind: () => void;
  onCodeChange: (operatorCode: string) => void;
  onDisplayNameChange: (displayName: string) => void;
  onPhoneChange: (phone: string) => void;
}) {
  const [codeDraft, setCodeDraft] = useState(account.operator_code || "");
  const [nameDraft, setNameDraft] = useState(account.display_name || account.username || "");
  const [phoneDraft, setPhoneDraft] = useState(account.phone || "");
  const [editingName, setEditingName] = useState(false);
  const isDriver = account.role === "driver";
  const isOperator = !isDriver;
  const readOnly = allCompanyView;
  const phoneChanged = phoneDraft.trim() !== (account.phone || "");
  const nameChanged = nameDraft.trim() !== (account.display_name || account.username || "");
  const codeChanged = codeDraft.trim() !== (account.operator_code || "");

  useEffect(() => {
    setCodeDraft(account.operator_code || "");
    setNameDraft(account.display_name || account.username || "");
    setPhoneDraft(account.phone || "");
    setEditingName(false);
  }, [account.id, account.operator_code, account.display_name, account.username, account.phone]);

  const confirmPhoneChange = () => {
    const nextPhone = phoneDraft.trim();
    if (!phoneChanged) return;
    const message = [
      `确认把 ${account.display_name || account.username} 的手机号改为 ${nextPhone || "空"}？`,
      "手机号会影响登录名规则、密码重置和微信绑定判断。",
    ].join("\n");
    if (window.confirm(message)) onPhoneChange(nextPhone);
  };

  const saveName = () => {
    const nextName = nameDraft.trim();
    if (!nextName || !nameChanged) {
      setEditingName(false);
      setNameDraft(account.display_name || account.username || "");
      return;
    }
    onDisplayNameChange(nextName);
    setEditingName(false);
  };

  return (
    <div className="grid gap-3 px-4 py-3 xl:grid-cols-[minmax(280px,1.25fr)_minmax(260px,0.9fr)_minmax(170px,0.55fr)_auto] xl:items-center">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          {isDriver || readOnly || !editingName ? (
            <div className="min-w-[160px] max-w-full truncate rounded-lg border border-transparent px-0 py-1 text-sm font-black text-slate-950">
              {account.display_name || account.username}
            </div>
          ) : (
            <div className="flex min-w-[220px] items-center gap-1">
              <input
                className="h-8 min-w-0 flex-1 rounded-lg border border-border bg-white px-3 text-sm font-black text-slate-950 outline-none focus:border-blue-500"
                value={nameDraft}
                onChange={(event) => setNameDraft(event.target.value)}
              />
              <button className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700" onClick={saveName} title="保存姓名" type="button">
                <Check size={15} />
              </button>
              <button
                className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-600"
                onClick={() => {
                  setEditingName(false);
                  setNameDraft(account.display_name || account.username || "");
                }}
                title="取消"
                type="button"
              >
                <X size={15} />
              </button>
            </div>
          )}
          {isOperator && !readOnly && !editingName ? (
            <button className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-100 text-slate-500 hover:bg-slate-200" onClick={() => setEditingName(true)} title="修改姓名" type="button">
              <Pencil size={13} />
            </button>
          ) : null}
          <StatusBadge status={account.is_active ? "active" : "disabled"} />
          <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${account.wx_bind_status === "bound" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>
            {account.wx_bind_status === "bound" ? "微信已绑定" : "微信未绑定"}
          </span>
          {account.must_change_password ? <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-bold text-amber-700">需改密码</span> : null}
          {platform ? <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-bold text-blue-700">{account.tenant_name || account.tenant_slug || `公司 #${account.tenant_id}`}</span> : null}
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs font-semibold text-slate-500">
          <span className="font-bold text-slate-700">登录名：{account.account_login || account.username}</span>
          <span>{profileLabel(account.profile_type)} #{account.profile_id || "-"}</span>
          <span>最近登录：{formatDate(account.last_login_at)}</span>
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-[1fr_auto] sm:items-end">
        <label className="grid gap-1">
          <span className="text-[11px] font-bold text-slate-500">手机号</span>
          <input
            className="h-8 rounded-lg border border-border bg-white px-3 text-xs font-bold text-slate-800 outline-none focus:border-blue-500 disabled:bg-slate-50"
            value={phoneDraft}
            disabled={readOnly}
            placeholder="手机号可修改或清空"
            onChange={(event) => setPhoneDraft(event.target.value)}
          />
        </label>
        {phoneChanged ? (
          <div className="flex gap-1">
            <Button className="h-8 px-2 text-xs" disabled={saving || readOnly} onClick={confirmPhoneChange}>
              <Save size={14} />
              确认
            </Button>
            <Button className="h-8 px-2 text-xs" variant="secondary" disabled={saving} onClick={() => setPhoneDraft(account.phone || "")}>
              取消
            </Button>
          </div>
        ) : null}
      </div>

      <div className="grid gap-1 text-xs text-slate-500">
        {isOperator ? (
          <label className="grid gap-1">
            <span className="font-bold text-slate-500">账号代码</span>
            <input
              className="h-8 rounded-lg border border-border bg-white px-3 text-xs font-bold uppercase text-slate-800 disabled:bg-slate-50"
              value={codeDraft}
              disabled={readOnly}
              placeholder="如 OP01"
              onChange={(event) => setCodeDraft(event.target.value.toUpperCase())}
              onBlur={() => {
                if (codeChanged) onCodeChange(codeDraft.trim());
              }}
            />
          </label>
        ) : (
          <div className="rounded-lg bg-slate-50 px-3 py-2">
            <div className="text-[11px] font-bold text-slate-500">司机代码</div>
            <div className="mt-1 font-black text-slate-800">{account.driver_code || "-"}</div>
          </div>
        )}
      </div>

      <div className="flex flex-wrap justify-start gap-2 xl:justify-end">
        <div className="inline-flex h-8 items-center rounded-lg border border-border bg-slate-50 px-3 text-xs font-bold text-slate-700">
          {roleLabels[account.role] || account.role}
        </div>
        {account.is_active ? (
          <Button className="h-8 px-2 text-xs" variant="secondary" disabled={readOnly} onClick={onDisable}>
            <UserX size={14} />
            停用
          </Button>
        ) : (
          <Button className="h-8 px-2 text-xs" variant="secondary" disabled={readOnly} onClick={onEnable}>
            <UserCheck size={14} />
            启用
          </Button>
        )}
        <Button className="h-8 px-2 text-xs" variant="secondary" disabled={readOnly} onClick={onReset}>
          <KeyRound size={14} />
          重置
        </Button>
        <Button className="h-8 px-2 text-xs" variant="secondary" disabled={readOnly || account.wx_bind_status !== "bound"} onClick={onUnbind}>
          <Unlink size={14} />
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
