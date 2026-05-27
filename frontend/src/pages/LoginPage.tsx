import { FormEvent, useState } from "react";
import { CarFront } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, setAuthToken } from "@/services/apiClient";
import type { AuthUser } from "@/types/api";

function looksLikePhone(value: string) {
  return /^\+?[\d\s-]{6,}$/.test(value.trim());
}

export function LoginPage({ onLogin }: { onLogin: (user: AuthUser) => void }) {
  const [account, setAccount] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const loginAccount = account.trim();
      const result = looksLikePhone(loginAccount)
        ? await api.loginPhone(loginAccount, password)
        : await api.login(loginAccount, password);
      setAuthToken(result.token);
      onLogin(result.user);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "登录失败，请检查账号和密码");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-6">
      <form className="w-full max-w-md rounded-xl border border-border bg-white p-8 shadow-panel" onSubmit={submit}>
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary text-white">
            <CarFront size={22} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-950">微信调度</h1>
            <p className="text-sm text-slate-500">管理端 / 调度 / 运行管理登录</p>
          </div>
        </div>
        <div className="grid gap-4">
          <label className="grid gap-1 text-sm font-semibold text-slate-600">
            账号或手机号
            <input className="h-11 rounded-md border border-border px-3 outline-none focus:border-primary" value={account} onChange={(event) => setAccount(event.target.value)} />
          </label>
          <label className="grid gap-1 text-sm font-semibold text-slate-600">
            密码
            <input className="h-11 rounded-md border border-border px-3 outline-none focus:border-primary" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          {error ? <div className="rounded-md bg-red-50 px-3 py-2 text-sm font-medium text-red-700">{error}</div> : null}
          <Button type="submit" className="h-11" disabled={loading}>
            {loading ? "登录中..." : "登录"}
          </Button>
          <p className="text-xs text-slate-500">内部账号由管理员预先创建；手机号账号的重置密码为手机号后 4 位。</p>
        </div>
      </form>
    </div>
  );
}
