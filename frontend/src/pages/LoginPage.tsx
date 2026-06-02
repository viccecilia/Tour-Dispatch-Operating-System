import { FormEvent, useState } from "react";
import type { ReactNode } from "react";
import { CarFront, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, setAuthToken } from "@/services/apiClient";
import type { AuthUser } from "@/types/api";

export function LoginPage({ onLogin }: { onLogin: (user: AuthUser) => void }) {
  const [account, setAccount] = useState("");
  const [password, setPassword] = useState("");
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [pendingUser, setPendingUser] = useState<AuthUser | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const loginAccount = normalizeLoginAccount(account);
      const result = await api.loginPhone(loginAccount, password);
      setAuthToken(result.token);
      if (result.user.must_change_password) {
        setPendingUser(result.user);
        setOldPassword(password);
        setPassword("");
        return;
      }
      onLogin(result.user);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "登录失败，请检查账号密码。");
    } finally {
      setLoading(false);
    }
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (newPassword.length < 6) throw new Error("新密码至少 6 位。");
      if (newPassword !== confirmPassword) throw new Error("两次输入的新密码不一致。");
      const result = await api.changePassword(oldPassword, newPassword);
      onLogin(result.user);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "密码修改失败。");
    } finally {
      setLoading(false);
    }
  }

  if (pendingUser) {
    return (
      <Shell title="首次登录需要修改密码" subtitle={`${pendingUser.account_login || pendingUser.username} · ${roleLabel(pendingUser.role)}`}>
        <form className="grid gap-4" onSubmit={changePassword}>
          <label className="grid gap-1 text-sm font-semibold text-slate-600">
            新密码
            <input className="h-12 rounded-md border border-border px-3 text-base outline-none focus:border-primary" type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
          </label>
          <label className="grid gap-1 text-sm font-semibold text-slate-600">
            再输入一次
            <input className="h-12 rounded-md border border-border px-3 text-base outline-none focus:border-primary" type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} />
          </label>
          {error ? <div className="rounded-md bg-red-50 px-3 py-2 text-sm font-medium text-red-700">{error}</div> : null}
          <Button type="submit" className="h-12" disabled={loading}>
            <KeyRound size={17} />
            {loading ? "保存中..." : "修改密码并进入"}
          </Button>
        </form>
      </Shell>
    );
  }

  return (
    <Shell title="TourFlow 登录" subtitle="统一账号入口，按后台权限进入对应功能。">
      <form className="grid gap-4" onSubmit={submit}>
        <label className="grid gap-1 text-sm font-semibold text-slate-600">
          公司账号
          <input className="h-12 rounded-md border border-border px-3 text-base outline-none focus:border-primary" value={account} onChange={(event) => setAccount(event.target.value)} placeholder="SKR-08070010000" />
        </label>
        <label className="grid gap-1 text-sm font-semibold text-slate-600">
          密码
          <input className="h-12 rounded-md border border-border px-3 text-base outline-none focus:border-primary" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
        </label>
        {error ? <div className="rounded-md bg-red-50 px-3 py-2 text-sm font-medium text-red-700">{error}</div> : null}
        <Button type="submit" className="h-12" disabled={loading}>
          {loading ? "登录中..." : "登录"}
        </Button>
        <p className="text-xs text-slate-500">账号格式为公司代码-手机号数字，例如 SKR-08070010000。初始密码为手机号后 6 位，Web 首次登录后必须修改。</p>
      </form>
    </Shell>
  );
}

function Shell({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-6">
      <div className="w-full max-w-md rounded-xl border border-border bg-white p-8 shadow-panel">
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary text-white">
            <CarFront size={22} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-950">{title}</h1>
            <p className="text-sm text-slate-500">{subtitle}</p>
          </div>
        </div>
        {children}
      </div>
    </div>
  );
}

function normalizeLoginAccount(value: string) {
  const text = value.trim();
  if (!text || text.includes("-")) return text;
  if (/^\+?[\d\s-]{6,}$/.test(text)) return `DAITORA-${text.replace(/[^\d]/g, "")}`;
  return text;
}

function roleLabel(role: string) {
  return { admin: "管理员", dispatcher: "调度", operations_manager: "运行管理", driver: "司机" }[role] || role;
}
