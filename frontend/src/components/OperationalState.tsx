import { AlertTriangle, Database, RefreshCw, Server, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type PanelProps = {
  title: string;
  description?: string;
  requestPath?: string;
  onRetry?: () => void;
  onCheckBackend?: () => void;
  className?: string;
};

export function RetryButton({ onClick, label = "重试" }: { onClick?: () => void; label?: string }) {
  return (
    <Button type="button" variant="secondary" className="rounded-xl" onClick={onClick}>
      <RefreshCw size={15} />
      {label}
    </Button>
  );
}

export function ErrorPanel({ title, description, requestPath, onRetry, onCheckBackend, className }: PanelProps) {
  return (
    <div className={cn("runtime-card runtime-page border-amber-200 bg-amber-50/70 p-5", className)}>
      <div className="flex items-start gap-4">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white text-amber-700 shadow-sm">
          <AlertTriangle size={21} />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-bold text-slate-950">{title}</h3>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            {description || "当前模块暂时无法读取实时数据，页面仍可保持基础结构，请检查后端服务或稍后重试。"}
          </p>
          {requestPath ? (
            <div className="mt-3 inline-flex max-w-full items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-500 ring-1 ring-amber-200">
              <Server size={13} />
              <span className="truncate">{requestPath}</span>
            </div>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-2">
            {onRetry ? <RetryButton onClick={onRetry} /> : null}
            <Button type="button" variant="secondary" className="rounded-xl" onClick={onCheckBackend || (() => { window.location.hash = "settings"; })}>
              <Database size={15} />
              检查后端
            </Button>
            <Button type="button" variant="secondary" className="rounded-xl" onClick={() => { window.location.hash = "dashboard"; }}>
              <Sparkles size={15} />
              查看演示数据
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function EmptyPanel({ title, description, requestPath, onRetry, className }: PanelProps) {
  return (
    <div className={cn("runtime-page rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-center", className)}>
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 text-slate-500">
        <Sparkles size={21} />
      </div>
      <h3 className="mt-3 text-sm font-bold text-slate-950">{title}</h3>
      <p className="mx-auto mt-1 max-w-md text-sm leading-6 text-slate-500">{description || "当前没有可展示的数据。"}</p>
      {requestPath ? <p className="mt-2 text-xs font-semibold text-slate-400">{requestPath}</p> : null}
      {onRetry ? <div className="mt-4 flex justify-center"><RetryButton onClick={onRetry} /></div> : null}
    </div>
  );
}

export function SkeletonCard({ title = "数据加载中", rows = 3, className }: { title?: string; rows?: number; className?: string }) {
  return (
    <div className={cn("runtime-page rounded-2xl border border-border bg-white p-5 shadow-sm", className)}>
      <div className="runtime-skeleton h-4 w-32 rounded-full" />
      <div className="mt-2 text-xs font-semibold text-slate-400">{title}</div>
      <div className="mt-5 space-y-3">
        {Array.from({ length: rows }).map((_, index) => (
          <div key={index} className="runtime-skeleton h-3 rounded-full" style={{ width: `${95 - index * 14}%` }} />
        ))}
      </div>
    </div>
  );
}
