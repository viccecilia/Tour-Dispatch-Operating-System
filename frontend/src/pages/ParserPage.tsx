import { Fragment, type ReactNode, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, FileText, Loader2, RotateCcw, Save, Search } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/services/apiClient";
import type { Draft } from "@/types/api";

type DraftEdit = Partial<
  Pick<
    Draft,
    | "oid"
    | "order_date"
    | "end_date"
    | "start_time"
    | "end_time"
    | "pickup_location"
    | "dropoff_location"
    | "order_type"
    | "vehicle_type"
    | "price"
    | "guest_name"
    | "guest_contact"
    | "agency_name"
    | "passenger_count"
    | "luggage_count"
    | "fee_remark"
    | "remark"
  >
>;

const sampleText = `Ashwin Arora
5.09 11:00 大阪往返天桥立美山 包车 3代 绿 1900
5.10 11:00 大阪-奈良-宇治-京都 包车 3代 绿 1500
5.12 10:00 铃鹿-京都 包车 10座绿牌 儿童座椅*2 2000
3.29 14:10 关西接机大阪 10座600`;

const editFields: Array<{ key: keyof DraftEdit; label: string; type?: string; wide?: boolean }> = [
  { key: "oid", label: "编号" },
  { key: "order_date", label: "开始日期", type: "date" },
  { key: "start_time", label: "开始时间", type: "time" },
  { key: "end_date", label: "结束日期", type: "date" },
  { key: "end_time", label: "结束时间", type: "time" },
  { key: "pickup_location", label: "起点" },
  { key: "dropoff_location", label: "终点" },
  { key: "order_type", label: "类型" },
  { key: "vehicle_type", label: "车型" },
  { key: "price", label: "价格", type: "number" },
  { key: "guest_name", label: "客人" },
  { key: "guest_contact", label: "联系方式" },
  { key: "agency_name", label: "来源" },
  { key: "passenger_count", label: "人数", type: "number" },
  { key: "luggage_count", label: "行李", type: "number" },
  { key: "fee_remark", label: "费用备注", wide: true },
  { key: "remark", label: "备注", wide: true },
];

function shortOid(draft: Draft) {
  const value = draft.oid || String(draft.id).padStart(3, "0");
  return value.replace(/^20(\d{6})/, "$1").replace(/^D-?20/, "D-");
}

function routeText(draft: Draft) {
  const pickup = draft.pickup_location || "-";
  const dropoff = draft.dropoff_location || "-";
  return `${pickup} -> ${dropoff}`;
}

function compactText(value?: string | number | null) {
  return String(value ?? "-").replace(/\s+/g, " ").trim();
}

function parseMeta(draft: Draft) {
  const result = (draft.parse_result || {}) as Record<string, unknown>;
  const confidence = Number(result.confidence ?? 0);
  return {
    confidence,
    confidenceLevel: String(result.confidence_level || (confidence >= 0.82 ? "high" : confidence >= 0.62 ? "medium" : "low")),
    lowConfidence: Boolean(result.low_confidence ?? confidence < 0.62),
    missingFields: Array.isArray(result.missing_fields) ? (result.missing_fields as string[]) : [],
    warnings: Array.isArray(result.warnings) ? (result.warnings as string[]) : [],
    diffPreview: Array.isArray(result.diff_preview) ? (result.diff_preview as Array<Record<string, unknown>>) : [],
  };
}

function confidenceClass(level: string) {
  if (level === "high") return "bg-emerald-50 text-emerald-700 ring-emerald-200";
  if (level === "medium") return "bg-amber-50 text-amber-700 ring-amber-200";
  return "bg-red-50 text-red-700 ring-red-200";
}

function ConfidenceBadge({ draft }: { draft: Draft }) {
  const meta = parseMeta(draft);
  const pct = meta.confidence ? Math.round(meta.confidence * 100) : 0;
  return (
    <span className={`inline-flex h-6 items-center gap-1 rounded-full px-2 text-xs font-semibold ring-1 ${confidenceClass(meta.confidenceLevel)}`}>
      {meta.lowConfidence ? <AlertTriangle size={13} /> : null}
      {pct}%
    </span>
  );
}

function toDraftEdit(draft: Draft): DraftEdit {
  return {
    oid: draft.oid,
    order_date: draft.order_date,
    end_date: draft.end_date || draft.order_date,
    start_time: draft.start_time,
    end_time: draft.end_time,
    pickup_location: draft.pickup_location,
    dropoff_location: draft.dropoff_location,
    order_type: draft.order_type,
    vehicle_type: draft.vehicle_type,
    price: draft.price,
    guest_name: draft.guest_name,
    guest_contact: draft.guest_contact,
    agency_name: draft.agency_name,
    passenger_count: draft.passenger_count,
    luggage_count: draft.luggage_count,
    fee_remark: draft.fee_remark,
    remark: draft.remark,
  };
}

export function ParserPage() {
  const queryClient = useQueryClient();
  const draftsQuery = useQuery({ queryKey: ["drafts"], queryFn: api.drafts });
  const [text, setText] = useState("");
  const [keyword, setKeyword] = useState("");
  const [status, setStatus] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<DraftEdit>({});
  const [currentBatchIds, setCurrentBatchIds] = useState<Set<number>>(new Set());
  const [message, setMessage] = useState("");

  const draftRows = useMemo(() => {
    const rows = (draftsQuery.data || []).filter((draft) => draft.parse_status !== "confirmed");
    return rows.filter((draft) => {
      const searchable = [
        draft.oid,
        draft.raw_text,
        draft.guest_name,
        draft.guest_contact,
        draft.pickup_location,
        draft.dropoff_location,
      ]
        .filter(Boolean)
        .join(" ");
      if (keyword && !searchable.toLowerCase().includes(keyword.toLowerCase())) return false;
      if (status && draft.parse_status !== status) return false;
      if (startDate && (draft.order_date || "") < startDate) return false;
      if (endDate && (draft.order_date || "") > endDate) return false;
      return true;
    }).sort((left, right) => {
      const leftKey = `${left.order_date || ""} ${left.start_time || ""} ${left.pickup_location || ""}`;
      const rightKey = `${right.order_date || ""} ${right.start_time || ""} ${right.pickup_location || ""}`;
      return leftKey.localeCompare(rightKey);
    });
  }, [draftsQuery.data, endDate, keyword, startDate, status]);

  const selectedDrafts = draftRows.filter((draft) => selectedIds.has(draft.id));
  const lowConfidenceCount = draftRows.filter((draft) => parseMeta(draft).lowConfidence).length;

  const parseMutation = useMutation({
    mutationFn: api.parseBatchText,
    onSuccess: async (result) => {
      const ids = new Set(result.drafts.map((draft) => draft.id));
      setCurrentBatchIds(ids);
      setSelectedIds(ids);
      setMessage(`已拆分并生成 ${result.count} 条待确认草稿。`);
      setText("");
      await queryClient.invalidateQueries({ queryKey: ["drafts"] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: DraftEdit }) => api.updateDraft(id, payload),
    onSuccess: async () => {
      setEditingId(null);
      setMessage("草稿已保存。");
      await queryClient.invalidateQueries({ queryKey: ["drafts"] });
    },
  });

  const confirmMutation = useMutation({
    mutationFn: (id: number) => api.confirmDraft(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["drafts"] });
      await queryClient.invalidateQueries({ queryKey: ["orders"] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
  });

  function toggleSelected(id: number) {
    setSelectedIds((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleExpanded(id: number) {
    setExpandedIds((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function startEdit(draft: Draft) {
    setEditingId(draft.id);
    setExpandedIds((previous) => new Set(previous).add(draft.id));
    setEditDraft(toDraftEdit(draft));
  }

  function setEditValue(key: keyof DraftEdit, value: string) {
    setEditDraft((previous) => ({
      ...previous,
      [key]: key === "price" || key === "passenger_count" || key === "luggage_count" ? (value === "" ? undefined : Number(value)) : value,
    }));
  }

  async function confirmSelected() {
    if (!selectedDrafts.length) {
      setMessage("请先选择待确认草稿。");
      return;
    }
    if (!window.confirm(`确认将 ${selectedDrafts.length} 条草稿写入订单池？`)) return;
    for (const draft of selectedDrafts) {
      await confirmMutation.mutateAsync(draft.id);
    }
    setSelectedIds(new Set());
    setMessage(`已确认 ${selectedDrafts.length} 条草稿，订单已进入 Orders 页面。`);
  }

  function chainSelected() {
    const ids = draftRows.map((draft) => draft.id);
    setSelectedIds(new Set(ids));
    setMessage(`已按日期、时间、起点生成接龙顺序，并选中 ${ids.length} 条；请检查后原地确认。`);
  }

  async function confirmOne(id: number) {
    if (!window.confirm("确认将这条草稿写入订单池？")) return;
    await confirmMutation.mutateAsync(id);
    setSelectedIds((previous) => {
      const next = new Set(previous);
      next.delete(id);
      return next;
    });
    setMessage("草稿已确认入库。");
  }

  function clearCurrentBatch() {
    setText("");
    setCurrentBatchIds(new Set());
    setSelectedIds(new Set());
    setMessage("已清空当前导入批次选择，历史草稿仍保留。");
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-700">
                <FileText size={20} />
              </div>
              <div>
                <h2 className="text-base font-bold text-slate-950">真实订单批量解析</h2>
                <p className="mt-1 text-sm text-slate-500">支持微信大段文本、客户名夹在订单之间、包车/送迎混合录入。</p>
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setText(sampleText)}>
                填入示例
              </Button>
              <Button variant="secondary" onClick={clearCurrentBatch}>
                <RotateCcw size={15} />
                清空当前批次
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <textarea
            className="min-h-40 w-full resize-y rounded-lg border border-border bg-white p-4 text-sm leading-6 outline-none ring-primary/20 focus:ring-4"
            placeholder="把微信或 Excel 中复制出来的大段订单文本粘贴到这里。每条订单可以一行；客户名可以单独一行。"
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-slate-500">
              当前批次：{currentBatchIds.size ? `${currentBatchIds.size} 条` : "未导入"} · 已选择：{selectedDrafts.length} 条 · 低置信度：{lowConfidenceCount} 条
            </p>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setText("")}>
                清空输入
              </Button>
              <Button disabled={!text.trim() || parseMutation.isPending} onClick={() => parseMutation.mutate(text)}>
                {parseMutation.isPending ? <Loader2 className="animate-spin" size={15} /> : <FileText size={15} />}
                批量解析为草稿
              </Button>
            </div>
          </div>
          {(message || parseMutation.error) && (
            <div className="mt-3 rounded-md border border-blue-100 bg-blue-50 px-3 py-2 text-sm text-blue-800">
              {parseMutation.error instanceof Error ? parseMutation.error.message : message}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-bold text-slate-950">待确认订单表</h2>
              <p className="mt-1 text-sm text-slate-500">默认是普通文本表格，展开或编辑后再修改字段。</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <input className="h-9 rounded-md border border-border px-3 text-sm" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
              <input className="h-9 rounded-md border border-border px-3 text-sm" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
              <label className="flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm">
                <Search size={15} className="text-slate-400" />
                <input
                  className="w-44 outline-none"
                  value={keyword}
                  onChange={(event) => setKeyword(event.target.value)}
                  placeholder="订单号/客户/手机号"
                />
              </label>
              <select className="h-9 rounded-md border border-border px-3 text-sm" value={status} onChange={(event) => setStatus(event.target.value)}>
                <option value="">全部状态</option>
                <option value="parsed">已解析</option>
                <option value="failed">解析失败</option>
                <option value="pending">待处理</option>
              </select>
              <Button variant="secondary" onClick={chainSelected}>
                一键排单（智能接龙）
              </Button>
              <Button onClick={confirmSelected} disabled={!selectedDrafts.length || confirmMutation.isPending}>
                <CheckCircle2 size={15} />
                原地确认
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <Button variant="secondary" onClick={() => setSelectedIds(new Set(draftRows.map((draft) => draft.id)))}>
              全选
            </Button>
            <Button variant="secondary" onClick={() => setSelectedIds(new Set())}>
              清空选择
            </Button>
            <span className="text-sm text-slate-500">显示 {draftRows.length} 条，已选择 {selectedDrafts.length} 条</span>
          </div>

          {draftsQuery.isLoading ? (
            <EmptyState detail="正在加载草稿。" />
          ) : draftRows.length ? (
            <div className="overflow-hidden rounded-lg border border-border">
              <div className="max-h-[640px] overflow-auto">
                <table className="min-w-[1180px] w-full border-collapse text-left text-sm">
                  <thead className="sticky top-0 z-10 bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="w-12 px-3 py-3">选择</th>
                      <th className="w-32 px-3 py-3">编号</th>
                      <th className="w-36 px-3 py-3">开始日期/时间</th>
                      <th className="w-36 px-3 py-3">结束日期/时间</th>
                      <th className="px-3 py-3">路线</th>
                      <th className="w-24 px-3 py-3">类型</th>
                      <th className="w-32 px-3 py-3">车型</th>
                      <th className="w-24 px-3 py-3">价格</th>
                      <th className="px-3 py-3">备注</th>
                      <th className="w-24 px-3 py-3">置信度</th>
                      <th className="w-36 px-3 py-3">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {draftRows.map((draft) => {
                      const isCurrentBatch = currentBatchIds.has(draft.id);
                      const isExpanded = expandedIds.has(draft.id);
                      const isEditing = editingId === draft.id;
                      return (
                        <Fragment key={draft.id}>
                          <tr
                            className={`h-12 border-t border-border bg-white align-middle hover:bg-slate-50 ${isCurrentBatch ? "bg-blue-50/40" : ""}`}
                          >
                            <td className="px-3 py-2">
                              <input
                                type="checkbox"
                                checked={selectedIds.has(draft.id)}
                                onChange={() => toggleSelected(draft.id)}
                                className="h-4 w-4 rounded border-slate-300"
                              />
                            </td>
                            <td className="px-3 py-2 font-semibold text-slate-950">{shortOid(draft)}</td>
                            <td className="px-3 py-2 text-slate-700">
                              {compactText(draft.order_date)}
                              <span className="ml-1 text-slate-500">{compactText(draft.start_time)}</span>
                            </td>
                            <td className="px-3 py-2 text-slate-700">
                              {compactText(draft.end_date || draft.order_date)}
                              <span className="ml-1 text-slate-500">{compactText(draft.end_time)}</span>
                            </td>
                            <td className="max-w-[260px] px-3 py-2 font-medium text-slate-900">
                              <span className="block truncate">{routeText(draft)}</span>
                            </td>
                            <td className="px-3 py-2 text-slate-700">{compactText(draft.order_type)}</td>
                            <td className="px-3 py-2 text-slate-700">{compactText(draft.vehicle_type)}</td>
                            <td className="px-3 py-2 font-semibold text-slate-900">{draft.price ? `¥${draft.price}` : "-"}</td>
                            <td className="max-w-[260px] px-3 py-2 text-slate-600">
                              <span className="block truncate">{compactText(draft.fee_remark || draft.remark || draft.raw_text)}</span>
                            </td>
                            <td className="px-3 py-2">
                              <ConfidenceBadge draft={draft} />
                            </td>
                            <td className="px-3 py-2">
                              <div className="flex items-center gap-1">
                                <button className="text-sm font-semibold text-blue-700 hover:text-blue-900" onClick={() => toggleExpanded(draft.id)}>
                                  {isExpanded ? "收起" : "展开"}
                                </button>
                                <button className="text-sm font-semibold text-emerald-700 hover:text-emerald-900" onClick={() => confirmOne(draft.id)}>
                                  确认
                                </button>
                                <button className="text-sm font-semibold text-slate-700 hover:text-slate-950" onClick={() => startEdit(draft)}>
                                  编辑
                                </button>
                              </div>
                            </td>
                          </tr>
                          {isExpanded && (
                            <tr key={`${draft.id}-detail`} className="border-t border-border bg-slate-50/70">
                              <td colSpan={11} className="px-4 py-4">
                                {isEditing ? (
                                  <div className="grid gap-3 md:grid-cols-4">
                                    {editFields.map((field) => (
                                      <label key={field.key} className={field.wide ? "md:col-span-2" : ""}>
                                        <span className="mb-1 block text-xs font-semibold text-slate-500">{field.label}</span>
                                        {field.key === "remark" || field.key === "fee_remark" ? (
                                          <textarea
                                            className="min-h-20 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-100"
                                            value={String(editDraft[field.key] ?? "")}
                                            onChange={(event) => setEditValue(field.key, event.target.value)}
                                          />
                                        ) : (
                                          <input
                                            className="h-9 w-full rounded-md border border-border px-3 text-sm outline-none focus:ring-2 focus:ring-blue-100"
                                            type={field.type || "text"}
                                            value={String(editDraft[field.key] ?? "")}
                                            onChange={(event) => setEditValue(field.key, event.target.value)}
                                          />
                                        )}
                                      </label>
                                    ))}
                                    <div className="flex items-end gap-2 md:col-span-4">
                                      <Button onClick={() => updateMutation.mutate({ id: draft.id, payload: editDraft })} disabled={updateMutation.isPending}>
                                        <Save size={15} />
                                        保存修改
                                      </Button>
                                      <Button variant="secondary" onClick={() => setEditingId(null)}>
                                        取消
                                      </Button>
                                    </div>
                                  </div>
                                ) : (
                                  <div className="grid gap-3 text-sm text-slate-700 md:grid-cols-4">
                                    <Detail label="解析状态" value={<StatusBadge status={draft.parse_status} />} />
                                    <Detail label="解析置信度" value={<ConfidenceDetail draft={draft} />} />
                                    <Detail label="客人" value={draft.guest_name || "-"} />
                                    <Detail label="联系方式" value={draft.guest_contact || "-"} />
                                    <Detail label="人数/行李" value={`${draft.passenger_count ?? "-"} / ${draft.luggage_count ?? "-"}`} />
                                    <Detail label="旅行社来源" value={draft.agency_name || draft.order_source || "-"} />
                                    <Detail label="费用备注" value={draft.fee_remark || "-"} />
                                    <Detail label="字段预览" value={<DiffPreview draft={draft} />} wide />
                                    <Detail label="原始文本" value={draft.raw_text} wide />
                                    <Detail label="完整备注" value={draft.remark || "-"} wide />
                                  </div>
                                )}
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <EmptyState detail="暂无待确认草稿。粘贴大段订单文本后点击批量解析。" />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Detail({ label, value, wide = false }: { label: string; value: ReactNode; wide?: boolean }) {
  return (
    <div className={wide ? "md:col-span-2" : ""}>
      <div className="text-xs font-semibold text-slate-500">{label}</div>
      <div className="mt-1 whitespace-pre-wrap rounded-md border border-border bg-white px-3 py-2 text-slate-900">{value}</div>
    </div>
  );
}

function ConfidenceDetail({ draft }: { draft: Draft }) {
  const meta = parseMeta(draft);
  const pct = meta.confidence ? Math.round(meta.confidence * 100) : 0;
  return (
    <div className="space-y-2">
      <ConfidenceBadge draft={draft} />
      <div className="text-xs text-slate-500">
        {pct}% · {meta.confidenceLevel}
        {meta.lowConfidence ? " · 需要人工重点确认" : " · 可正常人工确认"}
      </div>
      {meta.missingFields.length ? <div className="text-xs text-red-600">缺失：{meta.missingFields.join(", ")}</div> : null}
      {meta.warnings.length ? <div className="text-xs text-amber-700">提醒：{meta.warnings.join(", ")}</div> : null}
    </div>
  );
}

function DiffPreview({ draft }: { draft: Draft }) {
  const meta = parseMeta(draft);
  if (!meta.diffPreview.length) return <span className="text-slate-500">暂无字段预览</span>;
  return (
    <div className="grid gap-2 md:grid-cols-2">
      {meta.diffPreview.map((item) => {
        const label = String(item.label || item.field || "-");
        const parsed = compactText(item.parsed as string | number | null | undefined);
        const needsReview = Boolean(item.needs_review);
        const confidence = Math.round(Number(item.confidence || 0) * 100);
        return (
          <div key={`${draft.id}-${label}`} className={`rounded-md border px-2 py-1 text-xs ${needsReview ? "border-amber-200 bg-amber-50 text-amber-800" : "border-slate-200 bg-slate-50 text-slate-600"}`}>
            <span className="font-semibold">{label}</span>
            <span className="mx-1">=</span>
            <span>{parsed}</span>
            <span className="ml-2 text-slate-400">{confidence}%</span>
          </div>
        );
      })}
    </div>
  );
}
