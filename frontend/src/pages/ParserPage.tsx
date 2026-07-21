import { Fragment, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
/* eslint-disable @typescript-eslint/no-unused-vars -- parser payloads intentionally omit UI-only fields during serialization */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CalendarDays, CheckCircle2, Clock3, FileText, Loader2, RotateCcw, Save, Search, Upload } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { PilotFeedbackNote } from "@/components/PilotFeedbackNote";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { todayIso } from "@/lib/utils";
import { api } from "@/services/apiClient";
import type { Draft, Order } from "@/types/api";

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
    | "driver_language"
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

type DraftEditState = DraftEdit & {
  start_datetime?: string;
  end_datetime?: string;
  route_text?: string;
};

type SingleOrderForm = Partial<Order> & {
  order_date: string;
  end_date: string;
  start_time: string;
  end_time: string;
  pickup_location: string;
  dropoff_location: string;
  itinerary_pdf_file?: File | null;
};

function isIsoDate(value?: string | null) {
  return /^\d{4}-\d{2}-\d{2}$/.test(String(value || "").trim());
}

function sanitizePassengerCount(value: unknown) {
  const num = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(num)) return undefined;
  if (num <= 0 || num > 20) return undefined;
  return num;
}

function normalizeSingleLocation(value?: string | null) {
  const text = String(value || "").trim();
  if (!text) return "";
  if (/関西国際空港\s*T?1/i.test(text)) return "KIX-T1";
  if (/関西国際空港\s*T?2/i.test(text)) return "KIX-T2";
  if (/(関西国際空港|KIX)/i.test(text)) return "KIX";
  return text;
}

function extractSingleOrderHints(raw: string, fallbackDate?: string) {
  const text = String(raw || "").trim();
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.replace(/：/g, ":").trim())
    .filter(Boolean);
  const metadataPattern =
    /^(?:姓名|客人姓名|客人|电话|手機|手机|联系方式|人数|行李|价格|料金|price|旅行社|来源)\s*:/i;
  const structuredHints: Partial<SingleOrderForm> = {};

  const dateMatch =
    text.match(/(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]/) ||
    text.match(/(\d{4})[./-](\d{1,2})[./-](\d{1,2})/) ||
    text.match(/(\d{1,2})[./-](\d{1,2})/);
  if (dateMatch) {
    if (dateMatch[3] && dateMatch[1].length === 4) {
      structuredHints.order_date = `${dateMatch[1]}-${String(Number(dateMatch[2])).padStart(2, "0")}-${String(Number(dateMatch[3])).padStart(2, "0")}`;
    } else {
      const year = Number((fallbackDate || todayIso()).slice(0, 4));
      const month = Number(dateMatch[1]);
      const day = Number(dateMatch[2]);
      structuredHints.order_date = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    }
  }

  const timeMatch = text.match(/(\d{1,2}:\d{2})/);
  if (timeMatch) structuredHints.start_time = timeMatch[1];

  for (const line of lines) {
    const guestMatch = line.match(/^(?:姓名|客人姓名|客人|name|guest)\s*:\s*(.+)$/i);
    if (guestMatch?.[1]) {
      structuredHints.guest_name = guestMatch[1].trim();
      break;
    }
  }
  for (const line of lines) {
    const phoneMatch = line.match(/^(?:电话|手機|手机|联系方式|phone|contact)\s*:\s*(.+)$/i);
    if (phoneMatch?.[1]) {
      structuredHints.guest_contact = phoneMatch[1].trim();
      break;
    }
  }
  if (!structuredHints.guest_contact) {
    const loosePhone = text.match(/(?:\+?\d[\d -]{7,}\d)/);
    if (loosePhone) structuredHints.guest_contact = loosePhone[0].trim();
  }
  for (const line of lines) {
    const paxMatch = line.match(/^(?:人数|乘客数|pax|passengers?)\s*:\s*(\d{1,2})\b/i);
    if (paxMatch) {
      structuredHints.passenger_count = Number(paxMatch[1]);
      break;
    }
  }
  if (structuredHints.passenger_count == null) {
    const inlinePax = text.match(/(?<!\d)(\d{1,2})\s*(?:人|位)\b/);
    if (inlinePax) structuredHints.passenger_count = Number(inlinePax[1]);
  }

  const hasExplicitPrice = /(价格|料金|price)\s*:|[¥￥]\s*\d{3,6}|\d{3,6}\s*(?:円|JPY|RMB|元)\b/i.test(text);
  if (hasExplicitPrice) {
    const priceMatch =
      text.match(/(?:价格|料金|price)\s*[:：]?\s*[¥￥]?\s*(\d{3,6})/i) ||
      text.match(/[¥￥]\s*(\d{3,6})/) ||
      text.match(/(\d{3,6})\s*(?:円|JPY|RMB|元)\b/i);
    if (priceMatch) structuredHints.price = Number(priceMatch[1]);
  }

  const locationLines = lines.filter((line) => {
    if (metadataPattern.test(line)) return false;
    if (/\d{1,2}\s*月\s*\d{1,2}\s*[日号].*\d{1,2}:\d{2}/.test(line)) return false;
    if (/^(?:片道送迎|往返|包车|接机|送机)/.test(line)) return false;
    return true;
  });
  if (locationLines.length >= 2) {
    structuredHints.pickup_location = normalizeSingleLocation(locationLines[0]);
    structuredHints.dropoff_location = normalizeSingleLocation(locationLines[1]);
  }

  if (/空港行き|送机|送機/i.test(text)) structuredHints.order_type = "送机";
  else if (/接机|接機|airport pickup/i.test(text)) structuredHints.order_type = "接机";

  return structuredHints;
}

function draftToSingleOrder(draft: Draft, previous?: SingleOrderForm): SingleOrderForm {
  const clean = blankSingleOrder();
  const hints = extractSingleOrderHints(draft.raw_text || "", draft.order_date || clean.order_date);
  const orderDate = hints.order_date || draft.order_date || clean.order_date;
  const orderType = hints.order_type || draft.order_type || clean.order_type;
  const startTime = hints.start_time || draft.start_time || "";
  const passengerCount =
    sanitizePassengerCount(hints.passenger_count) ??
    sanitizePassengerCount(draft.passenger_count) ??
    undefined;
  const derivedAirportEnd = isAirportTransferOrder(orderType) && startTime ? addHoursToDateTime(orderDate, startTime, 2) : null;
  const normalizedDraftEndDate = isIsoDate(draft.end_date) ? String(draft.end_date) : "";
  const normalizedDraftEndTime = /^\d{1,2}:\d{2}$/.test(String(draft.end_time || "").trim())
    ? normalizeFlexibleTimeInput(String(draft.end_time || ""))
    : "";
  const finalEndDate = derivedAirportEnd?.end_date || normalizedDraftEndDate || orderDate;
  const finalEndTime = derivedAirportEnd?.end_time || normalizedDraftEndTime || draft.end_time || "";
  return {
    ...clean,
    order_date: orderDate,
    end_date: finalEndDate,
    start_time: startTime,
    end_time: finalEndTime,
    pickup_location: hints.pickup_location || draft.pickup_location || "",
    dropoff_location: hints.dropoff_location || draft.dropoff_location || "",
    order_type: orderType,
    vehicle_type: draft.vehicle_type || clean.vehicle_type,
    agency_name: draft.agency_name || "",
    guest_name: hints.guest_name || draft.guest_name || "",
    guest_contact: hints.guest_contact || draft.guest_contact || "",
    passenger_count: passengerCount,
    luggage_count: draft.luggage_count ?? undefined,
    price: hints.price !== undefined ? hints.price : undefined,
    remark: cleanSingleParseRemark(draft),
    itinerary_pdf_file: previous?.itinerary_pdf_file || null,
    itinerary_pdf_name: previous?.itinerary_pdf_name,
    itinerary_pdf_url: previous?.itinerary_pdf_url,
  };
}

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
  { key: "guest_name", label: "客人姓名" },
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
  const fullRoute = fullRouteText(draft);
  if (fullRoute) return fullRoute;
  const pickup = draft.pickup_location || "-";
  const dropoff = draft.dropoff_location || "-";
  return `${pickup} -> ${dropoff}`;
}

function dateTimeText(date?: string | null, time?: string | null) {
  return [date, time].filter(Boolean).join(" ").trim();
}

function pad2(value: number) {
  return String(value).padStart(2, "0");
}

function normalizeFlexibleDateInput(value: string, fallbackYear = new Date().getFullYear()) {
  const text = String(value || "").trim();
  if (!text) return "";
  const normalized = text
    .replace(/[年月]/g, "-")
    .replace(/[日号]/g, "")
    .replace(/[./]/g, "-")
    .replace(/\s+/g, "");
  let match = normalized.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (match) {
    return `${match[1]}-${pad2(Number(match[2]))}-${pad2(Number(match[3]))}`;
  }
  match = normalized.match(/^(\d{1,2})-(\d{1,2})$/);
  if (match) {
    return `${fallbackYear}-${pad2(Number(match[1]))}-${pad2(Number(match[2]))}`;
  }
  match = normalized.match(/^(\d{4})(\d{2})(\d{2})$/);
  if (match) {
    return `${match[1]}-${match[2]}-${match[3]}`;
  }
  return text;
}

function normalizeFlexibleTimeInput(value: string) {
  const text = String(value || "").trim();
  if (!text) return "";
  const normalized = text
    .toLowerCase()
    .replace(/[：.]/g, ":")
    .replace(/[时點点]/g, ":")
    .replace(/分/g, "")
    .replace(/\s+/g, "");
  let match = normalized.match(/^(\d{1,2}):(\d{1,2})$/);
  if (match) {
    return `${pad2(Number(match[1]))}:${pad2(Number(match[2]))}`;
  }
  match = normalized.match(/^(\d{1,2})(\d{2})$/);
  if (match) {
    return `${pad2(Number(match[1]))}:${match[2]}`;
  }
  match = normalized.match(/^(\d{1,2})$/);
  if (match) {
    return `${pad2(Number(match[1]))}:00`;
  }
  return text;
}

function addHoursToDateTime(date: string, time: string, hours: number) {
  if (!isIsoDate(date)) return { end_date: date, end_time: time };
  const normalizedTime = normalizeFlexibleTimeInput(time);
  if (!/^\d{2}:\d{2}$/.test(normalizedTime)) return { end_date: date, end_time: time };
  const [hour, minute] = normalizedTime.split(":").map(Number);
  const dt = new Date(`${date}T${pad2(hour)}:${pad2(minute)}:00`);
  if (Number.isNaN(dt.getTime())) return { end_date: date, end_time: normalizedTime };
  dt.setHours(dt.getHours() + hours);
  return {
    end_date: `${dt.getFullYear()}-${pad2(dt.getMonth() + 1)}-${pad2(dt.getDate())}`,
    end_time: `${pad2(dt.getHours())}:${pad2(dt.getMinutes())}`,
  };
}

function isAirportTransferOrder(orderType?: string | null) {
  const text = String(orderType || "").trim();
  return text === "接机" || text === "送机";
}

function parseDateTimeText(value: string) {
  const text = String(value || "").trim();
  const dateMatch =
    text.match(/(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})/) ||
    text.match(/(\d{1,2}[-/.]\d{1,2})/) ||
    text.match(/(\d{1,2}\s*月\s*\d{1,2}\s*[日号]?)/);
  const timeMatch =
    text.match(/(\d{1,2}:\d{2})/) ||
    text.match(/(\d{3,4})(?!\d)/) ||
    text.match(/(\d{1,2}\s*[点時时]\s*\d{0,2})/);
  return {
    date: dateMatch ? normalizeFlexibleDateInput(dateMatch[1]) : undefined,
    time: timeMatch ? normalizeFlexibleTimeInput(timeMatch[1]) : undefined,
  };
}

function splitRouteText(value: string) {
  const parts = String(value || "")
    .split(/\s*(?:->|→|>|-|－|—)\s*/)
    .map((item) => item.trim())
    .filter(Boolean);
  if (!parts.length) return { pickup: "", dropoff: "" };
  return { pickup: parts[0], dropoff: parts[parts.length - 1] };
}

function fullRouteText(draft: Draft) {
  const source = `${draft.remark || ""} ${draft.fee_remark || ""}`;
  const match = source.match(/完整路线[:：]\s*([^；;\n]+)/);
  return match?.[1]?.trim() || "";
}

function compactText(value?: string | number | null) {
  return String(value ?? "-").replace(/\s+/g, " ").trim();
}

function detectPhoneRegion(value?: string | null) {
  const text = String(value || "").trim();
  if (!text.startsWith("+")) return "";
  const mapping: Array<[RegExp, string]> = [
    [/^\+86\b/, "中国"],
    [/^\+81\b/, "日本"],
    [/^\+852\b/, "香港"],
    [/^\+853\b/, "澳门"],
    [/^\+886\b/, "台湾"],
    [/^\+971\b/, "阿联酋"],
    [/^\+60\b/, "马来西亚"],
    [/^\+91\b/, "印度"],
    [/^\+65\b/, "新加坡"],
    [/^\+66\b/, "泰国"],
    [/^\+82\b/, "韩国"],
    [/^\+1\b/, "美国/加拿大"],
    [/^\+44\b/, "英国"],
    [/^\+33\b/, "法国"],
    [/^\+49\b/, "德国"],
  ];
  const matched = mapping.find(([pattern]) => pattern.test(text));
  return matched?.[1] || "";
}

function cleanSingleParseRemark(draft: Draft) {
  const parts = [draft.fee_remark, unparsedRemarkText(draft)]
    .map((item) => String(item || "").trim())
    .filter(Boolean);
  return parts.join("\n");
}

function blankSingleOrder(): SingleOrderForm {
  const date = todayIso();
  return {
    order_date: date,
    end_date: date,
    start_time: "09:00",
    end_time: "",
    pickup_location: "",
    dropoff_location: "",
    order_type: "包车",
    vehicle_type: "A-3",
    agency_name: "",
    guest_name: "",
    guest_contact: "",
    passenger_count: undefined,
    luggage_count: undefined,
    price: undefined,
    remark: "",
    itinerary_pdf_file: null,
  };
}

function fileToDataUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(reader.error || new Error("file_read_failed"));
    reader.readAsDataURL(file);
  });
}

function unparsedRemarkText(draft: Draft) {
  const source = [draft.fee_remark, draft.remark]
    .map((item) => String(item || "").trim())
    .filter(Boolean)
    .filter((item, index, list) => list.indexOf(item) === index)
    .join("\n");
  const hidden = [
    /完整路线[:：][^；;\n]+[；;]?/g,
    /路线链[:：][^；;\n]+[；;]?/g,
    /原始(?:解析)?文本[:：].*/g,
    /备注标签[:：]?/g,
    /绿牌/g,
    /白牌/g,
  ];
  const cleaned = hidden.reduce((value, pattern) => value.replace(pattern, " "), source).replace(/[；;\s]+/g, " ").trim();
  return cleaned || "-";
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

function toDraftEdit(draft: Draft): DraftEditState {
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
    start_datetime: dateTimeText(draft.order_date, draft.start_time),
    end_datetime: dateTimeText(draft.end_date || draft.order_date, draft.end_time),
    route_text: routeText(draft),
  };
}

export function ParserPage() {
  const queryClient = useQueryClient();
  const draftsQuery = useQuery({ queryKey: ["drafts"], queryFn: api.drafts });
  const [singleOrder, setSingleOrder] = useState<SingleOrderForm>(() => blankSingleOrder());
  const [singleParseText, setSingleParseText] = useState("");
  const [text, setText] = useState("");
  const [keyword, setKeyword] = useState("");
  const [status, setStatus] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<DraftEditState>({});
  const [currentBatchIds, setCurrentBatchIds] = useState<Set<number>>(new Set());
  const [message, setMessage] = useState("");
  const editingRowRef = useRef<HTMLTableRowElement | null>(null);

  const draftRows = useMemo(() => {
    const rows = (draftsQuery.data || []).filter((draft) => !["confirmed", "discarded"].includes(draft.parse_status || ""));
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
  const selectedCount = selectedIds.size;
  const lowConfidenceCount = draftRows.filter((draft) => parseMeta(draft).lowConfidence).length;

  useEffect(() => {
    const visibleIds = new Set(draftRows.map((draft) => draft.id));
    setSelectedIds((previous) => {
      const next = new Set([...previous].filter((id) => visibleIds.has(id)));
      return next.size === previous.size ? previous : next;
    });
  }, [draftRows]);

  useEffect(() => {
    if (!editingId) return;
    const activeEditingId = editingId;
    function handlePointerDown(event: PointerEvent) {
      const target = event.target as Node | null;
      if (target && editingRowRef.current?.contains(target)) return;
      saveEdit(activeEditingId);
    }
    document.addEventListener("pointerdown", handlePointerDown, true);
    return () => document.removeEventListener("pointerdown", handlePointerDown, true);
  }, [editingId, editDraft]);

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

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteDraft(id),
    onSuccess: async (_data, id) => {
      setEditingId((previous) => (previous === id ? null : previous));
      setSelectedIds((previous) => {
        const next = new Set(previous);
        next.delete(id);
        return next;
      });
      setCurrentBatchIds((previous) => {
        const next = new Set(previous);
        next.delete(id);
        return next;
      });
      queryClient.setQueryData<Draft[]>(["drafts"], (old) => old?.filter((draft) => draft.id !== id) || old);
      setMessage("草稿已删除。");
      await queryClient.invalidateQueries({ queryKey: ["drafts"] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
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

  const createSingleOrderMutation = useMutation({
    mutationFn: async (form: SingleOrderForm) => {
      const file = form.itinerary_pdf_file;
      const itineraryPdfUrl = file ? await fileToDataUrl(file) : form.itinerary_pdf_url;
      const { itinerary_pdf_file: _file, ...rest } = form;
      return api.createOrder({
        ...rest,
        end_date: rest.end_date || rest.order_date,
        dispatch_status: "unassigned",
        settlement_status: "pending",
        source_channel: "manual_single",
        itinerary_pdf_name: file?.name || rest.itinerary_pdf_name,
        itinerary_pdf_url: itineraryPdfUrl,
        price: rest.price === undefined || rest.price === null || String(rest.price) === "" ? undefined : Number(rest.price),
      });
    },
    onSuccess: async () => {
      setSingleOrder(blankSingleOrder());
      setMessage("单个订单已保存到订单池，可继续派车或放入订单大厅。");
      await queryClient.invalidateQueries({ queryKey: ["orders"] });
      await queryClient.invalidateQueries({ queryKey: ["unassigned-orders"] });
      await queryClient.invalidateQueries({ queryKey: ["calendar"] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
  });

  const parseSingleMutation = useMutation({
    mutationFn: async (raw: string) => {
      const result = await api.parseText(raw);
      try {
        if (result.draft?.id) await api.deleteDraft(result.draft.id);
      } catch {
        // Best-effort cleanup: single-form parse should not leave extra drafts behind.
      }
      return result;
    },
    onSuccess: async (result) => {
      if (!result.draft) return;
      setSingleOrder((previous) => draftToSingleOrder(result.draft, previous));
      setMessage("已解析并回填到单条录入表格，请确认后保存。");
      setSingleParseText("");
      await queryClient.invalidateQueries({ queryKey: ["drafts"] });
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
    setExpandedIds((previous) => {
      const next = new Set(previous);
      next.delete(draft.id);
      return next;
    });
    setEditDraft(toDraftEdit(draft));
  }

  function saveEdit(id: number) {
    if (editingId !== id || updateMutation.isPending) return;
    const { start_datetime, end_datetime, route_text, ...payload } = editDraft;
    updateMutation.mutate({ id, payload });
  }

  function setEditValue(key: keyof DraftEdit, value: string) {
    setEditDraft((previous) => ({
      ...previous,
      [key]: key === "price" || key === "passenger_count" || key === "luggage_count" ? (value === "" ? undefined : Number(value)) : value,
    }));
  }

  function setStartDateTime(value: string) {
    const parsed = parseDateTimeText(value);
    setEditDraft((previous) => ({
      ...previous,
      start_datetime: value,
      ...(parsed.date ? { order_date: parsed.date } : {}),
      ...(parsed.time ? { start_time: parsed.time } : {}),
    }));
  }

  function setEndDateTime(value: string) {
    const parsed = parseDateTimeText(value);
    setEditDraft((previous) => ({
      ...previous,
      end_datetime: value,
      ...(parsed.date ? { end_date: parsed.date } : {}),
      ...(parsed.time ? { end_time: parsed.time } : {}),
    }));
  }

  function setRouteValue(value: string) {
    const route = splitRouteText(value);
    const previousFeeRemark = String(editDraft.fee_remark || "").replace(/完整路线[:：][^；;\n]+[；;]?/g, "").trim();
    setEditDraft((previous) => ({
      ...previous,
      route_text: value,
      pickup_location: route.pickup || previous.pickup_location,
      dropoff_location: route.dropoff || previous.dropoff_location,
      fee_remark: value ? [`完整路线：${value}`, previousFeeRemark].filter(Boolean).join("；") : previous.fee_remark,
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

  async function deleteSelected() {
    const visibleIds = new Set(draftRows.map((draft) => draft.id));
    const ids = Array.from(selectedIds).filter((id) => visibleIds.has(id));
    if (!ids.length) {
      setMessage("请先选择要删除的解析草稿。");
      return;
    }
    if (!window.confirm(`确认删除 ${ids.length} 条解析草稿？删除后不会进入订单。`)) return;
    for (const id of ids) {
      await deleteMutation.mutateAsync(id);
    }
    setSelectedIds(new Set());
    setMessage(`已删除 ${ids.length} 条解析草稿。`);
  }

  function clearCurrentBatch() {
    setText("");
    setCurrentBatchIds(new Set());
    setSelectedIds(new Set());
    setMessage("已清空当前导入批次选择，历史草稿仍保留。");
  }

  function setSingleOrderValue(key: keyof SingleOrderForm, value: string | number | File | null | undefined) {
    setSingleOrder((previous) => ({
      ...previous,
      [key]: ["price", "passenger_count", "luggage_count"].includes(String(key))
        ? value === "" || value === undefined || value === null
          ? undefined
          : Number(value)
        : value,
    }));
  }

  function submitSingleOrder() {
    const payload = {
      ...singleOrder,
      order_date: normalizeFlexibleDateInput(singleOrder.order_date || "") || singleOrder.order_date,
      end_date: normalizeFlexibleDateInput(singleOrder.end_date || "") || singleOrder.end_date,
      start_time: normalizeFlexibleTimeInput(singleOrder.start_time || "") || singleOrder.start_time,
      end_time: normalizeFlexibleTimeInput(singleOrder.end_time || "") || singleOrder.end_time,
    };
    if (!payload.order_date || !payload.pickup_location.trim() || !payload.dropoff_location.trim()) {
      setMessage("单个订单请至少填写开始日期、起点和终点。");
      return;
    }
    setSingleOrder(payload);
    createSingleOrderMutation.mutate(payload);
  }

  function submitSingleParse() {
    if (!singleParseText.trim()) {
      setMessage("请先粘贴一条完整订单文本。");
      return;
    }
    parseSingleMutation.mutate(singleParseText);
  }

  return (
    <div className="space-y-5">
      <PilotFeedbackNote
        title="试运营反馈记录点"
        tone="amber"
        items={["解析失败先保留原文", "低置信度必须人工确认", "把经常改的字段记下来", "确认后再进订单池"]}
      />

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-base font-bold text-slate-950">单个订单详细录入</h2>
              <p className="mt-1 text-sm text-slate-500">适合临时追加、电话确认后的订单。保存后直接进入订单池，PDF 会随订单保存。</p>
            </div>
            <Button variant="secondary" onClick={() => setSingleOrder(blankSingleOrder())}>
              清空
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="mb-4 space-y-3 rounded-lg border border-blue-100 bg-blue-50/50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900">单条文本解析回填</h3>
                <p className="mt-1 text-xs text-slate-500">适合单送、单接、单条包车文本。解析后直接填入下方表格，不进入批量草稿池。</p>
              </div>
              <div className="flex gap-2">
                <Button variant="secondary" onClick={() => setSingleParseText("")}>
                  清空文本
                </Button>
                <Button onClick={submitSingleParse} disabled={!singleParseText.trim() || parseSingleMutation.isPending}>
                  {parseSingleMutation.isPending ? <Loader2 className="animate-spin" size={15} /> : <FileText size={15} />}
                  解析并回填
                </Button>
              </div>
            </div>
            <textarea
              className="min-h-28 w-full resize-y rounded-lg border border-border bg-white p-3 text-sm leading-6 outline-none ring-primary/20 focus:ring-4"
              placeholder="把一条完整订单贴在这里，例如日期、时间、酒店、机场、客人姓名、电话、人数。"
              value={singleParseText}
              onChange={(event) => setSingleParseText(event.target.value)}
            />
            {parseSingleMutation.error instanceof Error ? (
              <div className="rounded-md bg-red-50 px-3 py-2 text-sm font-bold text-red-700">{parseSingleMutation.error.message}</div>
            ) : null}
          </div>

          <div className="grid gap-3 md:grid-cols-6">
            <SingleField label="开始日期" required>
              <FlexibleTemporalInput mode="date" value={singleOrder.order_date} onChange={(value) => setSingleOrderValue("order_date", value)} placeholder="2026-06-20 / 6-20 / 6.20" />
            </SingleField>
            <SingleField label="结束日期">
              <FlexibleTemporalInput mode="date" value={singleOrder.end_date} onChange={(value) => setSingleOrderValue("end_date", value)} placeholder="2026-06-20 / 6/20" />
            </SingleField>
            <SingleField label="开始时间">
              <FlexibleTemporalInput mode="time" value={singleOrder.start_time} onChange={(value) => setSingleOrderValue("start_time", value)} placeholder="10:30 / 1030 / 10点30" />
            </SingleField>
            <SingleField label="结束时间">
              <FlexibleTemporalInput mode="time" value={singleOrder.end_time} onChange={(value) => setSingleOrderValue("end_time", value)} placeholder="12:30 / 1230" />
            </SingleField>
            <SingleField label="类型">
              <select value={singleOrder.order_type || ""} onChange={(event) => setSingleOrderValue("order_type", event.target.value)}>
                <option value="包车">包车</option>
                <option value="接机">接机</option>
                <option value="送机">送机</option>
              </select>
            </SingleField>
            <SingleField label="车型">
              <select value={singleOrder.vehicle_type || ""} onChange={(event) => setSingleOrderValue("vehicle_type", event.target.value)}>
                <option value="A-3">A-3</option>
                <option value="A-4">A-4</option>
                <option value="H">H</option>
              </select>
            </SingleField>
            <SingleField label="起点" required wide>
              <input value={singleOrder.pickup_location} onChange={(event) => setSingleOrderValue("pickup_location", event.target.value)} placeholder="例：大阪市内 / KIX" />
            </SingleField>
            <SingleField label="终点" required wide>
              <input value={singleOrder.dropoff_location} onChange={(event) => setSingleOrderValue("dropoff_location", event.target.value)} placeholder="例：京都站 / 关西机场" />
            </SingleField>
            <SingleField label="旅行社">
              <input value={singleOrder.agency_name || ""} onChange={(event) => setSingleOrderValue("agency_name", event.target.value)} />
            </SingleField>
            <SingleField label="客人姓名">
              <input value={singleOrder.guest_name || ""} onChange={(event) => setSingleOrderValue("guest_name", event.target.value)} />
            </SingleField>
            <SingleField label="联系方式">
              <div className="w-full space-y-1">
                <input
                  className="h-10 w-full rounded-md border border-border px-3 text-sm"
                  value={singleOrder.guest_contact || ""}
                  onChange={(event) => setSingleOrderValue("guest_contact", event.target.value)}
                />
                {detectPhoneRegion(singleOrder.guest_contact) ? <p className="text-xs text-slate-500">国家/地区：{detectPhoneRegion(singleOrder.guest_contact)}</p> : null}
              </div>
            </SingleField>
            <SingleField label="人数">
              <input type="number" value={singleOrder.passenger_count ?? ""} onChange={(event) => setSingleOrderValue("passenger_count", event.target.value)} />
            </SingleField>
            <SingleField label="行李">
              <input type="number" value={singleOrder.luggage_count ?? ""} onChange={(event) => setSingleOrderValue("luggage_count", event.target.value)} />
            </SingleField>
            <SingleField label="价格">
              <input type="number" value={singleOrder.price ?? ""} onChange={(event) => setSingleOrderValue("price", event.target.value)} />
            </SingleField>
            <SingleField label="行程 PDF" wide>
              <label className="flex h-10 cursor-pointer items-center justify-center gap-2 rounded-md border border-blue-200 bg-blue-50 px-3 text-sm font-bold text-blue-700 hover:bg-blue-100">
                <Upload size={15} />
                {singleOrder.itinerary_pdf_file?.name || singleOrder.itinerary_pdf_name || "上传 PDF"}
                <input
                  className="hidden"
                  type="file"
                  accept="application/pdf,.pdf"
                  onChange={(event) => setSingleOrderValue("itinerary_pdf_file", event.target.files?.[0] || null)}
                />
              </label>
            </SingleField>
            <SingleField label="备注" wide>
              <textarea value={singleOrder.remark || ""} onChange={(event) => setSingleOrderValue("remark", event.target.value)} placeholder="儿童座椅、举牌、费用备注等" />
            </SingleField>
          </div>
          {createSingleOrderMutation.error instanceof Error ? (
            <div className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm font-bold text-red-700">{createSingleOrderMutation.error.message}</div>
          ) : null}
          <div className="mt-4 flex justify-end">
            <Button onClick={submitSingleOrder} disabled={createSingleOrderMutation.isPending}>
              {createSingleOrderMutation.isPending ? <Loader2 className="animate-spin" size={15} /> : <Save size={15} />}
              保存到订单池
            </Button>
          </div>
        </CardContent>
      </Card>

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
            data-testid="parser-input"
            className="min-h-40 w-full resize-y rounded-lg border border-border bg-white p-4 text-sm leading-6 outline-none ring-primary/20 focus:ring-4"
            placeholder="把微信或 Excel 中复制出来的大段订单文本粘贴到这里。每条订单可以一行；客户名可以单独一行。"
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-slate-500">
              当前批次：{currentBatchIds.size ? `${currentBatchIds.size} 条` : "未导入"} · 已选择：{selectedCount} 条 · 低置信度：{lowConfidenceCount} 条
            </p>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setText("")}>
                清空输入
              </Button>
              <Button data-testid="parser-parse-button" disabled={!text.trim() || parseMutation.isPending} onClick={() => parseMutation.mutate(text)}>
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
              <p className="mt-1 text-sm text-slate-500">默认只显示确认表；双击行可直接编辑字段，点击行外自动保存。</p>
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
              <Button data-testid="parser-confirm-selected-button" onClick={confirmSelected} disabled={!selectedDrafts.length || confirmMutation.isPending}>
                <CheckCircle2 size={15} />
                原地确认
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <Button className="min-w-20" variant="secondary" onClick={() => setSelectedIds(new Set(draftRows.map((draft) => draft.id)))}>
              全选
            </Button>
            <Button className="min-w-20" variant="secondary" onClick={() => setSelectedIds(new Set())}>
              清空选择
            </Button>
            <Button
              className="min-w-20"
              variant="secondary"
              disabled={!selectedCount || deleteMutation.isPending}
              onClick={deleteSelected}
            >
              删除
            </Button>
            <span className="text-sm text-slate-500">显示 {draftRows.length} 条，已选择 {selectedCount} 条</span>
          </div>

          {draftsQuery.isLoading ? (
            <EmptyState detail="正在加载草稿。" />
          ) : draftRows.length ? (
            <div className="overflow-hidden rounded-lg border border-border">
              <div className="max-h-[640px] overflow-auto">
                <table className="min-w-[1560px] w-full border-collapse text-left text-sm">
                  <thead className="sticky top-0 z-10 bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="w-16 px-3 py-3">选择</th>
                      <th className="w-32 px-3 py-3">编号</th>
                      <th className="w-36 px-3 py-3">开始日期/时间</th>
                      <th className="w-36 px-3 py-3">结束日期/时间</th>
                      <th className="px-3 py-3">路线</th>
                      <th className="w-24 px-3 py-3">类型</th>
                      <th className="w-32 px-3 py-3">客人姓名</th>
                      <th className="w-40 px-3 py-3">联系方式</th>
                      <th className="w-20 px-3 py-3">人数</th>
                      <th className="w-20 px-3 py-3">行李</th>
                      <th className="w-32 px-3 py-3">车型</th>
                      <th className="w-24 px-3 py-3">语言</th>
                      <th className="w-24 px-3 py-3">价格</th>
                      <th className="px-3 py-3">备注</th>
                      <th className="w-24 px-3 py-3">置信度</th>
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
                            data-testid="parser-draft-row"
                            data-draft-id={draft.id}
                            ref={isEditing ? editingRowRef : undefined}
                            onDoubleClick={() => startEdit(draft)}
                            className={`h-12 border-t border-border bg-white align-middle hover:bg-slate-50 ${isCurrentBatch ? "bg-blue-50/40" : ""}`}
                          >
                            <td className="px-3 py-2">
                              <input
                                type="checkbox"
                                checked={selectedIds.has(draft.id)}
                                onChange={() => toggleSelected(draft.id)}
                                onDoubleClick={(event) => event.stopPropagation()}
                                className="h-4 w-4 rounded border-slate-300"
                              />
                            </td>
                            <td className="px-3 py-2 font-semibold text-slate-950">
                              {isEditing ? (
                                <input className="h-8 w-full rounded-md border border-border px-2 text-sm" value={String(editDraft.oid ?? "")} onChange={(event) => setEditValue("oid", event.target.value)} />
                              ) : shortOid(draft)}
                            </td>
                            <td className="px-3 py-2 text-slate-700">
                              {isEditing ? (
                                <input className="h-8 w-full rounded-md border border-border px-2 text-sm" value={String(editDraft.start_datetime ?? "")} onChange={(event) => setStartDateTime(event.target.value)} />
                              ) : (
                                dateTimeText(draft.order_date, draft.start_time) || "-"
                              )}
                            </td>
                            <td className="px-3 py-2 text-slate-700">
                              {isEditing ? (
                                <input className="h-8 w-full rounded-md border border-border px-2 text-sm" value={String(editDraft.end_datetime ?? "")} onChange={(event) => setEndDateTime(event.target.value)} />
                              ) : (
                                dateTimeText(draft.end_date || draft.order_date, draft.end_time) || "-"
                              )}
                            </td>
                            <td className="max-w-[260px] px-3 py-2 font-medium text-slate-900">
                              {isEditing ? (
                                <input className="h-8 w-full rounded-md border border-border px-2 text-sm" value={String(editDraft.route_text ?? "")} onChange={(event) => setRouteValue(event.target.value)} />
                              ) : (
                                <span className="block truncate">{routeText(draft)}</span>
                              )}
                            </td>
                            <td className="px-3 py-2 text-slate-700">
                              {isEditing ? <input className="h-8 w-full rounded-md border border-border px-2 text-sm" value={String(editDraft.order_type ?? "")} onChange={(event) => setEditValue("order_type", event.target.value)} /> : compactText(draft.order_type)}
                            </td>
                            <td className="px-3 py-2 text-slate-700">
                              {isEditing ? <input className="h-8 w-full rounded-md border border-border px-2 text-sm" value={String(editDraft.guest_name ?? "")} onChange={(event) => setEditValue("guest_name", event.target.value)} /> : compactText(draft.guest_name)}
                            </td>
                            <td className="px-3 py-2 text-slate-700">
                              {isEditing ? <input className="h-8 w-full rounded-md border border-border px-2 text-sm" value={String(editDraft.guest_contact ?? "")} onChange={(event) => setEditValue("guest_contact", event.target.value)} /> : compactText(draft.guest_contact ? `${draft.guest_contact}${detectPhoneRegion(draft.guest_contact) ? ` (${detectPhoneRegion(draft.guest_contact)})` : ""}` : "-")}
                            </td>
                            <td className="px-3 py-2 text-slate-700">
                              {isEditing ? <input className="h-8 w-full rounded-md border border-border px-2 text-sm" type="number" value={String(editDraft.passenger_count ?? "")} onChange={(event) => setEditValue("passenger_count", event.target.value)} /> : compactText(draft.passenger_count)}
                            </td>
                            <td className="px-3 py-2 text-slate-700">
                              {isEditing ? <input className="h-8 w-full rounded-md border border-border px-2 text-sm" type="number" value={String(editDraft.luggage_count ?? "")} onChange={(event) => setEditValue("luggage_count", event.target.value)} /> : compactText(draft.luggage_count)}
                            </td>
                            <td className="px-3 py-2 text-slate-700">
                              {isEditing ? <input className="h-8 w-full rounded-md border border-border px-2 text-sm" value={String(editDraft.vehicle_type ?? "")} onChange={(event) => setEditValue("vehicle_type", event.target.value)} /> : compactText(draft.vehicle_type)}
                            </td>
                            <td className="px-3 py-2 text-slate-700">
                              {isEditing ? <input className="h-8 w-full rounded-md border border-border px-2 text-sm" value={String(editDraft.driver_language ?? "")} onChange={(event) => setEditValue("driver_language", event.target.value)} /> : compactText(draft.driver_language)}
                            </td>
                            <td className="px-3 py-2 font-semibold text-slate-900">
                              {isEditing ? <input className="h-8 w-full rounded-md border border-border px-2 text-sm" type="number" value={String(editDraft.price ?? "")} onChange={(event) => setEditValue("price", event.target.value)} /> : draft.price ? `¥${draft.price}` : "-"}
                            </td>
                            <td className="max-w-[260px] px-3 py-2 text-slate-600">
                              {isEditing ? (
                                <input className="h-8 w-full rounded-md border border-border px-2 text-sm" value={String(editDraft.remark ?? "")} onChange={(event) => setEditValue("remark", event.target.value)} />
                              ) : (
                                <span className="block truncate">{unparsedRemarkText(draft)}</span>
                              )}
                            </td>
                            <td className="px-3 py-2">
                              <ConfidenceBadge draft={draft} />
                            </td>
                          </tr>
                          {isExpanded && (
                            <tr key={`${draft.id}-detail`} className="border-t border-border bg-slate-50/70">
                              <td colSpan={15} className="px-4 py-4">
                                {isEditing ? (
                                  <div className="grid gap-3 md:grid-cols-4">
                                    {editFields.map((field) => (
                                      <label key={field.key} className={field.wide ? "md:col-span-2" : ""}>
                                        <span className="mb-1 block text-xs font-semibold text-slate-500">{field.label}</span>
                                        {field.key === "remark" || field.key === "fee_remark" ? (
                                          <textarea
                                            data-testid={`parser-edit-${field.key}`}
                                            className="min-h-20 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-100"
                                            value={String(editDraft[field.key] ?? "")}
                                            onChange={(event) => setEditValue(field.key, event.target.value)}
                                          />
                                        ) : field.type === "date" || field.type === "time" ? (
                                          <FlexibleTemporalInput
                                            mode={field.type}
                                            value={String(editDraft[field.key] ?? "")}
                                            onChange={(value) => setEditValue(field.key, value)}
                                            compact
                                            placeholder={field.type === "date" ? "2026-06-20 / 6-20" : "10:30 / 1030"}
                                          />
                                        ) : (
                                          <input
                                            data-testid={`parser-edit-${field.key}`}
                                            className="h-9 w-full rounded-md border border-border px-3 text-sm outline-none focus:ring-2 focus:ring-blue-100"
                                            type={field.type || "text"}
                                            value={String(editDraft[field.key] ?? "")}
                                            onChange={(event) => setEditValue(field.key, event.target.value)}
                                          />
                                        )}
                                      </label>
                                    ))}
                                    <div className="flex items-end gap-2 md:col-span-4">
                                      <Button data-testid="parser-save-draft-button" onClick={() => updateMutation.mutate({ id: draft.id, payload: editDraft })} disabled={updateMutation.isPending}>
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
                                    <Detail label="客人姓名" value={draft.guest_name || "-"} />
                                    <Detail label="联系方式" value={draft.guest_contact ? `${draft.guest_contact}${detectPhoneRegion(draft.guest_contact) ? ` (${detectPhoneRegion(draft.guest_contact)})` : ""}` : "-"} />
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

function FlexibleTemporalInput({
  mode,
  value,
  onChange,
  placeholder,
  compact = false,
}: {
  mode: "date" | "time";
  value?: string | null;
  onChange: (value: string) => void;
  placeholder?: string;
  compact?: boolean;
}) {
  const [draftValue, setDraftValue] = useState(String(value || ""));
  const nativeRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    setDraftValue(String(value || ""));
  }, [value]);
  const normalize = (raw: string) => (mode === "date" ? normalizeFlexibleDateInput(raw) : normalizeFlexibleTimeInput(raw));
  const nativeValue = (() => {
    const normalized = normalize(draftValue);
    if (mode === "date") return /^\d{4}-\d{2}-\d{2}$/.test(normalized) ? normalized : "";
    return /^\d{2}:\d{2}$/.test(normalized) ? normalized : "";
  })();
  const commit = (raw: string) => {
    const normalized = normalize(raw);
    setDraftValue(normalized);
    onChange(normalized);
  };
  const Icon = mode === "date" ? CalendarDays : Clock3;
  return (
    <div className="flex items-center gap-2">
      <input
        value={draftValue}
        onChange={(event) => {
          const next = event.target.value;
          setDraftValue(next);
          onChange(next);
        }}
        onBlur={(event) => commit(event.target.value)}
        placeholder={placeholder}
        className={`${compact ? "h-9" : "h-10"} w-full rounded-md border border-border px-3 text-sm outline-none focus:ring-2 focus:ring-blue-100`}
      />
      <button
        type="button"
        className={`${compact ? "h-9 w-9" : "h-10 w-10"} inline-flex shrink-0 items-center justify-center rounded-md border border-border bg-slate-50 text-slate-500 transition hover:bg-slate-100`}
        onClick={() => {
          const input = nativeRef.current;
          if (!input) return;
          if (typeof input.showPicker === "function") input.showPicker();
          else input.click();
        }}
      >
        <Icon size={16} />
      </button>
      <input
        ref={nativeRef}
        tabIndex={-1}
        type={mode}
        value={nativeValue}
        onChange={(event) => commit(event.target.value)}
        className="sr-only"
        aria-hidden="true"
      />
    </div>
  );
}

function SingleField({ label, required, wide, children }: { label: string; required?: boolean; wide?: boolean; children: ReactNode }) {
  return (
    <label className={`space-y-1 ${wide ? "md:col-span-2" : ""}`}>
      <span className="text-xs font-black text-slate-500">
        {label}
        {required ? <span className="text-red-500"> *</span> : null}
      </span>
      <div className="[&>input]:h-10 [&>input]:w-full [&>input]:rounded-md [&>input]:border [&>input]:border-border [&>input]:px-3 [&>input]:text-sm [&>select]:h-10 [&>select]:w-full [&>select]:rounded-md [&>select]:border [&>select]:border-border [&>select]:px-3 [&>select]:text-sm [&>textarea]:min-h-20 [&>textarea]:w-full [&>textarea]:rounded-md [&>textarea]:border [&>textarea]:border-border [&>textarea]:px-3 [&>textarea]:py-2 [&>textarea]:text-sm [&_input]:rounded-md [&_input]:border [&_input]:border-border [&_input]:px-3 [&_input]:text-sm">
        {children}
      </div>
    </label>
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
