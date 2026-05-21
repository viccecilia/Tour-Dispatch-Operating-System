import { FormEvent, useState } from "react";
import { CarFront } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, setAuthToken } from "@/services/apiClient";
import type { AuthUser } from "@/types/api";

export function LoginPage({ onLogin }: { onLogin: (user: AuthUser) => void }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const result = await api.login(username, password);
      setAuthToken(result.token);
      onLogin(result.user);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "登录失败");
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
            <p className="text-sm text-slate-500">登录调度控制台</p>
          </div>
        </div>
        <div className="grid gap-4">
          <label className="grid gap-1 text-sm font-semibold text-slate-600">
            用户名
            <input className="h-11 rounded-md border border-border px-3 outline-none focus:border-primary" value={username} onChange={(event) => setUsername(event.target.value)} />
          </label>
          <label className="grid gap-1 text-sm font-semibold text-slate-600">
            密码
            <input className="h-11 rounded-md border border-border px-3 outline-none focus:border-primary" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          {error ? <div className="rounded-md bg-red-50 px-3 py-2 text-sm font-medium text-red-700">{error}</div> : null}
          <Button type="submit" className="h-11" disabled={loading}>
            {loading ? "登录中..." : "登录"}
          </Button>
          <p className="text-xs text-slate-500">演示账号：admin / admin123。不同租户账号会看到隔离后的数据。</p>
        </div>
      </form>
    </div>
  );
}
