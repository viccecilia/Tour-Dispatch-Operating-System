import { useQuery } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/services/apiClient";

export function ParserPage() {
  const drafts = useQuery({ queryKey: ["drafts"], queryFn: api.drafts });

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-700">
              <FileText size={20} />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-950">批量订单解析入口</h2>
              <p className="mt-1 text-sm text-slate-500">粘贴中文订单文本，生成可人工确认的草稿。</p>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <textarea
            className="min-h-36 w-full resize-y rounded-lg border border-border bg-white p-4 text-sm outline-none ring-primary/20 focus:ring-4"
            placeholder="例：5月20日 08:00 首都机场 -> 国贸酒店 4人 2箱 丰田埃尔法 张先生 138****8888"
          />
          <div className="mt-3 flex justify-end gap-2">
            <Button variant="secondary">清空</Button>
            <Button>解析为草稿</Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="text-base font-bold text-slate-950">待确认草稿</h2>
        </CardHeader>
        <CardContent>
          {drafts.data?.length ? (
            <div className="grid gap-3 xl:grid-cols-2">
              {drafts.data.map((draft) => (
                <div key={draft.id} className="rounded-lg border border-border bg-white p-4">
                  <div className="flex items-start justify-between gap-3">
                    <p className="line-clamp-2 text-sm font-semibold text-slate-900">{draft.raw_text}</p>
                    <StatusBadge status={draft.parse_status} />
                  </div>
                  <p className="mt-3 text-xs text-slate-500">
                    {draft.order_date || "-"} {draft.start_time || ""} · {draft.pickup_location || "-"} {"->"} {draft.dropoff_location || "-"}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState detail="暂无草稿。" />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
