import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { DatabaseBackup, HeartPulse, Power, RefreshCw, ServerCog, TerminalSquare } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/services/apiClient";

export function SystemMaintenancePage() {
  const [message, setMessage] = useState("");
  const status = useQuery({ queryKey: ["system-status"], queryFn: api.systemStatus, refetchInterval: 30_000 });
  const health = useQuery({ queryKey: ["system-health"], queryFn: api.systemHealth, enabled: false });
  const logs = useQuery({ queryKey: ["system-logs"], queryFn: () => api.systemLogs(160), enabled: false });
  const backup = useMutation({
    mutationFn: api.systemBackup,
    onSuccess: (data) => {
      setMessage(`数据库备份已完成：${data.backup_name}`);
      status.refetch();
    },
    onError: (error: Error) => setMessage(`数据库备份失败：${error.message}`),
  });
  const restart = useMutation({
    mutationFn: api.systemRestartApi,
    onSuccess: () => setMessage("软重启 API 已提交，约 3-5 秒后刷新状态。"),
    onError: (error: Error) => setMessage(`软重启失败：${error.message}`),
  });

  return (
    <div className="space-y-5">
      <section className="runtime-strip">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="runtime-eyebrow">SYSTEM OPS</p>
            <h2 className="runtime-title">后台控制</h2>
            <p className="runtime-subtitle">仅管理员可用：状态刷新、系统自检、数据库备份、最近日志和软重启 API。</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="runtime-pill runtime-pill-blue">{String(status.data?.environment || "-")}</span>
            <span className="runtime-pill runtime-pill-green">{String((status.data?.service as Record<string, unknown> | undefined)?.active || "-")}</span>
          </div>
        </div>
      </section>

      {message ? <div className="rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm font-semibold text-blue-800">{message}</div> : null}

      <div className="grid gap-4 xl:grid-cols-4">
        <ActionCard icon={RefreshCw} title="状态刷新" caption="确认 API、数据库和前端包状态" onClick={() => status.refetch()} loading={status.isFetching} />
        <ActionCard icon={HeartPulse} title="系统自检" caption="执行一组只读健康检查" onClick={() => health.refetch()} loading={health.isFetching} />
        <ActionCard icon={DatabaseBackup} title="数据库备份" caption="生成一份 trial DB 备份" onClick={() => backup.mutate()} loading={backup.isPending} />
        <ActionCard
          icon={Power}
          title="软重启 API"
          caption="重启后自动检查服务状态"
          tone="danger"
          onClick={() => window.confirm("确认软重启云端 API？") && restart.mutate()}
          loading={restart.isPending}
        />
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2 text-base font-bold text-slate-950">
            <ServerCog size={18} />
            当前状态
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            <Info label="环境" value={status.data?.environment} />
            <Info label="API PID" value={status.data?.pid} />
            <Info label="端口" value={status.data?.port} />
            <Info label="数据库" value={status.data?.database} wide />
            <Info label="数据库大小" value={`${status.data?.database_size_mb ?? "-"} MB`} />
            <Info label="前端包" value={status.data?.frontend_asset} />
          </div>
        </CardContent>
      </Card>

      {health.data ? (
        <Card>
          <CardHeader>
            <h3 className="text-base font-bold text-slate-950">系统自检结果</h3>
          </CardHeader>
          <CardContent className="grid gap-2 md:grid-cols-2">
            {health.data.checks.map((item) => (
              <div key={item.name} className="rounded-lg border border-border p-3">
                <div className={`text-sm font-bold ${item.ok ? "text-emerald-700" : "text-red-700"}`}>{item.ok ? "正常" : "异常"} · {item.name}</div>
                <div className="mt-1 break-all text-xs text-slate-500">{item.detail || "-"}</div>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-base font-bold text-slate-950">
              <TerminalSquare size={18} />
              最近日志
            </div>
            <Button type="button" variant="secondary" onClick={() => logs.refetch()} disabled={logs.isFetching}>读取日志</Button>
          </div>
        </CardHeader>
        <CardContent>
          <pre className="max-h-[420px] overflow-auto rounded-xl bg-slate-950 p-4 text-xs leading-5 text-slate-100">
            {(logs.data?.lines || ["点击“读取日志”查看最近 API 日志。"]).join("\n")}
          </pre>
        </CardContent>
      </Card>
    </div>
  );
}

function ActionCard({
  icon: Icon,
  title,
  caption,
  tone,
  loading,
  onClick,
}: {
  icon: LucideIcon;
  title: string;
  caption: string;
  tone?: "danger";
  loading?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={`rounded-xl border p-4 text-left shadow-sm transition hover:-translate-y-0.5 ${tone === "danger" ? "border-red-100 bg-red-50 text-red-900" : "border-border bg-white text-slate-900"}`}
      onClick={onClick}
      disabled={loading}
    >
      <Icon size={22} />
      <div className="mt-3 text-sm font-black">{loading ? "处理中..." : title}</div>
      <div className="mt-1 text-xs font-semibold opacity-70">{caption}</div>
    </button>
  );
}

function Info({ label, value, wide }: { label: string; value: unknown; wide?: boolean }) {
  return (
    <div className={`rounded-lg border border-border bg-slate-50 p-3 ${wide ? "xl:col-span-2" : ""}`}>
      <div className="text-xs font-bold text-slate-500">{label}</div>
      <div className="mt-1 break-all text-sm font-semibold text-slate-950">{String(value || "-")}</div>
    </div>
  );
}
