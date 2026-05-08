export function EmptyState({ title = "暂无数据", detail }: { title?: string; detail?: string }) {
  return (
    <div className="flex min-h-32 flex-col items-center justify-center rounded-md border border-dashed border-border bg-slate-50 px-4 py-8 text-center">
      <p className="text-sm font-semibold text-slate-700">{title}</p>
      {detail ? <p className="mt-1 text-xs text-slate-500">{detail}</p> : null}
    </div>
  );
}
