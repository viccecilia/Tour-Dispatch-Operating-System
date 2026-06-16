import { useMemo, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, Building2, CheckCircle2, FileUp, Plus, RotateCcw, Save, Search, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/services/apiClient";
import type { CompanyRegistration } from "@/types/api";

const initialDraft: Partial<CompanyRegistration> = {
  company_type: "carrier",
  company_code: "",
  company_name: "",
  registered_name: "",
  corporate_number: "",
  invoice_registration_number: "",
  business_license_number: "",
  representative_name: "",
  postal_code: "",
  address: "",
  contact_name: "",
  contact_phone: "",
  contact_email: "",
  bank_name: "",
  bank_branch: "",
  bank_account_type: "ordinary",
  bank_account_number: "",
  bank_account_holder: "",
  status: "draft",
  review_note: "",
};

type StatusView = "active" | "archived";

export function CompanyRegistrationPage() {
  const queryClient = useQueryClient();
  const [keyword, setKeyword] = useState("");
  const [companyType, setCompanyType] = useState("");
  const [statusView, setStatusView] = useState<StatusView>("active");
  const [status, setStatus] = useState("");
  const [draft, setDraft] = useState<Partial<CompanyRegistration>>(initialDraft);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [message, setMessage] = useState("");

  const queryStatus = statusView === "archived" ? "archived" : status;
  const registrations = useQuery({
    queryKey: ["company-registrations", keyword, companyType, queryStatus],
    queryFn: () => api.companyRegistrations({ keyword, company_type: companyType, status: queryStatus }),
  });

  const createRegistration = useMutation({
    mutationFn: api.createCompanyRegistration,
    onSuccess: async () => {
      setMessage("公司注册资料已新增。");
      setDraft(initialDraft);
      await invalidate();
    },
    onError: (error: Error) => setMessage(`新增失败：${error.message}`),
  });

  const updateRegistration = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<CompanyRegistration> }) => api.updateCompanyRegistration(id, payload),
    onSuccess: async () => {
      setMessage("公司注册资料已更新。");
      setEditingId(null);
      setDraft(initialDraft);
      await invalidate();
    },
    onError: (error: Error) => setMessage(`更新失败：${error.message}`),
  });

  const archiveRegistration = useMutation({
    mutationFn: api.deleteCompanyRegistration,
    onSuccess: async () => {
      setMessage("公司注册记录已归档，可在“显示范围：归档记录”中恢复。");
      setEditingId(null);
      setDraft(initialDraft);
      await invalidate();
    },
    onError: (error: Error) => setMessage(`归档失败：${error.message}`),
  });

  const uploadFile = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: { file_type: "registry_certificate" | "business_license" | "bank_book"; file_name: string; file_base64: string } }) => api.uploadCompanyRegistrationFile(id, payload),
    onSuccess: async () => {
      setMessage("文件已上传。");
      await invalidate();
    },
    onError: (error: Error) => setMessage(`上传失败：${error.message}`),
  });

  const rows = useMemo(() => registrations.data || [], [registrations.data]);
  const saving = createRegistration.isPending || updateRegistration.isPending || archiveRegistration.isPending || uploadFile.isPending;
  const fieldErrors = validateDraft(draft);

  function invalidate() {
    return Promise.all([
      queryClient.invalidateQueries({ queryKey: ["company-registrations"] }),
      queryClient.invalidateQueries({ queryKey: ["agencies"] }),
      queryClient.invalidateQueries({ queryKey: ["agency-portal-agencies"] }),
    ]);
  }

  function submitDraft(nextStatus?: CompanyRegistration["status"]) {
    const payload = normalizeRegistration({ ...draft, status: nextStatus || draft.status || "draft" });
    const errors = validateDraft(payload);
    if (errors.length) {
      setMessage(`请先补全：${errors.join("、")}`);
      return;
    }
    const unreadableFields = validateReadableText(payload);
    if (unreadableFields.length) {
      setMessage(`资料中疑似出现乱码：${unreadableFields.join("、")}。请重新输入中文或日文后再提交。`);
      return;
    }
    if (editingId) {
      updateRegistration.mutate({ id: editingId, payload });
      return;
    }
    createRegistration.mutate(payload);
  }

  function beginEdit(row: CompanyRegistration) {
    setEditingId(row.id);
    setDraft({ ...initialDraft, ...cleanUnreadableRegistration(row) });
    setMessage("");
  }

  function reviewRegistration(row: CompanyRegistration, nextStatus: "approved" | "rejected") {
    const actionText = nextStatus === "approved" ? "通过" : "退回";
    if (nextStatus === "approved") {
      const unreadableFields = validateReadableText(row);
      if (unreadableFields.length) {
        setMessage(`${row.company_code || row.company_name} 资料疑似乱码：${unreadableFields.join("、")}。请先退回或编辑修正，不能直接通过。`);
        return;
      }
    }
    const ok = window.confirm(`确认${actionText} ${row.company_name || row.company_code} 的公司注册资料吗？`);
    if (!ok) return;
    updateRegistration.mutate({
      id: row.id,
      payload: {
        status: nextStatus,
        review_note: nextStatus === "approved" ? row.review_note || "平台审核通过" : row.review_note || "平台退回修改",
      },
    });
  }

  function archiveRow(row: CompanyRegistration) {
    const ok = window.confirm(`确认归档 ${row.company_code || row.company_name || row.id} 的公司注册记录吗？归档后会从默认列表隐藏，但不会删除已建好的公司、账号、司机或车辆。`);
    if (!ok) return;
    archiveRegistration.mutate(row.id);
  }

  function restoreRegistration(row: CompanyRegistration) {
    const ok = window.confirm(`确认恢复 ${row.company_code || row.company_name || row.id} 到默认列表吗？`);
    if (!ok) return;
    updateRegistration.mutate({
      id: row.id,
      payload: {
        status: "draft",
        review_note: "从归档恢复",
      },
    });
  }

  function changeStatusView(nextView: StatusView) {
    setStatusView(nextView);
    setStatus("");
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-500">运营台</p>
          <h2 className="mt-1 text-2xl font-bold text-slate-950">公司注册</h2>
          <p className="mt-1 text-sm text-slate-500">登记车公司和旅行社资料，上传藤本 PDF、许可文件和银行资料。</p>
        </div>
      </div>

      {message && <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm font-medium text-blue-700">{message}</div>}

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Building2 size={18} className="text-blue-600" />
            <div>
              <h3 className="text-base font-bold text-slate-950">{editingId ? "编辑公司资料" : "新增公司注册"}</h3>
              <p className="mt-1 text-sm text-slate-500">资料可先保存草稿，也可以提交审核。</p>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 xl:grid-cols-4">
            <Field label="公司类型" required>
              <select className="field" value={draft.company_type || "carrier"} onChange={(event) => setDraft({ ...draft, company_type: event.target.value as CompanyRegistration["company_type"] })}>
                <option value="carrier">车公司</option>
                <option value="agency">旅行社</option>
              </select>
            </Field>
            <Field label="公司代码" required hint="订单号、登录前缀和平台展示使用">
              <input className="field" value={draft.company_code || ""} maxLength={12} onChange={(event) => setDraft({ ...draft, company_code: normalizeCode(event.target.value) })} placeholder="例如 SKR / AGT" />
            </Field>
            <Field label="公司名" required>
              <input className="field" value={draft.company_name || ""} onChange={(event) => setDraft({ ...draft, company_name: event.target.value })} />
            </Field>
            <Field label="登记会社名">
              <input className="field" value={draft.registered_name || ""} onChange={(event) => setDraft({ ...draft, registered_name: event.target.value })} placeholder="与藤本一致" />
            </Field>
            <Field label="法人姓名" required>
              <input className="field" value={draft.representative_name || ""} onChange={(event) => setDraft({ ...draft, representative_name: event.target.value })} />
            </Field>
            <Field label="法人番号">
              <input className="field" value={draft.corporate_number || ""} onChange={(event) => setDraft({ ...draft, corporate_number: event.target.value })} />
            </Field>
            <Field label="发票登记号">
              <input className="field" value={draft.invoice_registration_number || ""} onChange={(event) => setDraft({ ...draft, invoice_registration_number: event.target.value })} placeholder="T 开头编号" />
            </Field>
            <Field label="营业许可号">
              <input className="field" value={draft.business_license_number || ""} onChange={(event) => setDraft({ ...draft, business_license_number: event.target.value })} />
            </Field>
            <Field label="邮编">
              <input className="field" value={draft.postal_code || ""} onChange={(event) => setDraft({ ...draft, postal_code: event.target.value })} />
            </Field>
            <Field label="公司地址" required>
              <input className="field" value={draft.address || ""} onChange={(event) => setDraft({ ...draft, address: event.target.value })} />
            </Field>
            <Field label="业务联系人" required>
              <input className="field" value={draft.contact_name || ""} onChange={(event) => setDraft({ ...draft, contact_name: event.target.value })} />
            </Field>
            <Field label="联系电话" required>
              <input className="field" value={draft.contact_phone || ""} onChange={(event) => setDraft({ ...draft, contact_phone: event.target.value })} />
            </Field>
            <Field label="邮箱">
              <input className="field" value={draft.contact_email || ""} onChange={(event) => setDraft({ ...draft, contact_email: event.target.value })} />
            </Field>
            <Field label="银行名称" required>
              <input className="field" value={draft.bank_name || ""} onChange={(event) => setDraft({ ...draft, bank_name: event.target.value })} />
            </Field>
            <Field label="支店名" required>
              <input className="field" value={draft.bank_branch || ""} onChange={(event) => setDraft({ ...draft, bank_branch: event.target.value })} />
            </Field>
            <Field label="账户类型">
              <select className="field" value={draft.bank_account_type || "ordinary"} onChange={(event) => setDraft({ ...draft, bank_account_type: event.target.value })}>
                <option value="ordinary">普通</option>
                <option value="current">当座</option>
                <option value="savings">储蓄</option>
              </select>
            </Field>
            <Field label="账号号码" required>
              <input className="field" value={draft.bank_account_number || ""} onChange={(event) => setDraft({ ...draft, bank_account_number: event.target.value })} />
            </Field>
            <Field label="账户名义" required>
              <input className="field" value={draft.bank_account_holder || ""} onChange={(event) => setDraft({ ...draft, bank_account_holder: event.target.value })} />
            </Field>
            <Field label="审核状态">
              <select className="field" value={draft.status || "draft"} onChange={(event) => setDraft({ ...draft, status: event.target.value })}>
                <option value="draft">草稿</option>
                <option value="submitted">已提交</option>
                <option value="approved">已通过</option>
                <option value="rejected">已退回</option>
                <option value="inactive">停用</option>
                <option value="archived">已归档</option>
              </select>
            </Field>
            <Field label="审核备注">
              <input className="field" value={draft.review_note || ""} onChange={(event) => setDraft({ ...draft, review_note: event.target.value })} />
            </Field>
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <div className="text-sm text-slate-500">{fieldErrors.length ? `还缺：${fieldErrors.join("、")}` : "必填资料已完成，可以保存草稿或提交审核。"}</div>
            <div className="flex flex-wrap gap-2">
              {editingId && <Button type="button" variant="secondary" onClick={() => { setEditingId(null); setDraft(initialDraft); }}>取消编辑</Button>}
              <Button type="button" variant="secondary" disabled={saving} onClick={() => submitDraft("draft")}><Save size={15} />保存草稿</Button>
              <Button type="button" disabled={saving} onClick={() => submitDraft("submitted")}><Plus size={15} />提交审核</Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-bold text-slate-950">注册公司列表</h3>
              <p className="mt-1 text-sm text-slate-500">默认列表不显示归档记录；切换到归档记录后可以恢复。</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <div className="inline-flex h-9 rounded-md border border-border bg-slate-50 p-1">
                <button type="button" className={`rounded px-3 text-sm font-semibold ${statusView === "active" ? "bg-white text-blue-700 shadow-sm" : "text-slate-500"}`} onClick={() => changeStatusView("active")}>默认列表</button>
                <button type="button" className={`rounded px-3 text-sm font-semibold ${statusView === "archived" ? "bg-white text-blue-700 shadow-sm" : "text-slate-500"}`} onClick={() => changeStatusView("archived")}>归档记录</button>
              </div>
              <div className="flex h-9 items-center gap-2 rounded-md border border-border bg-white px-3">
                <Search size={15} className="text-slate-400" />
                <input className="w-64 bg-transparent text-sm outline-none" value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索代码 / 公司名 / 法人 / 电话" />
              </div>
              <select className="h-9 rounded-md border border-border bg-white px-3 text-sm" value={companyType} onChange={(event) => setCompanyType(event.target.value)}>
                <option value="">全部类型</option>
                <option value="carrier">车公司</option>
                <option value="agency">旅行社</option>
              </select>
              {statusView === "active" ? (
                <select className="h-9 rounded-md border border-border bg-white px-3 text-sm" value={status} onChange={(event) => setStatus(event.target.value)}>
                  <option value="">全部未归档状态</option>
                  <option value="draft">草稿</option>
                  <option value="submitted">已提交</option>
                  <option value="approved">已通过</option>
                  <option value="rejected">已退回</option>
                  <option value="inactive">停用</option>
                </select>
              ) : (
                <div className="flex h-9 items-center rounded-md border border-slate-200 bg-slate-50 px-3 text-sm font-semibold text-slate-600">只看已归档</div>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[1320px] text-left text-sm">
              <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-3">类型</th>
                  <th className="px-3 py-3">代码</th>
                  <th className="px-3 py-3">公司名</th>
                  <th className="px-3 py-3">法人 / 地址</th>
                  <th className="px-3 py-3">联系</th>
                  <th className="px-3 py-3">银行</th>
                  <th className="px-3 py-3">状态</th>
                  <th className="px-3 py-3">文件</th>
                  <th className="px-3 py-3">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {registrations.isLoading ? (
                  <tr><td className="px-3 py-8 text-center text-slate-500" colSpan={9}>正在加载公司注册资料...</td></tr>
                ) : rows.length === 0 ? (
                  <tr><td className="px-3 py-8 text-center text-slate-500" colSpan={9}>{statusView === "archived" ? "暂无归档记录" : "暂无公司注册资料"}</td></tr>
                ) : rows.map((row) => (
                  <tr key={row.id} className="hover:bg-slate-50">
                    <td className="px-3 py-3">{row.company_type === "agency" ? "旅行社" : "车公司"}</td>
                    <td className="px-3 py-3 font-bold text-slate-950">{row.company_code}</td>
                    <td className="px-3 py-3"><div className="font-semibold text-slate-950">{safeText(row.company_name, "待补录公司名")}</div><div className="text-xs text-slate-500">{safeText(row.registered_name, "-")}</div></td>
                    <td className="px-3 py-3"><div>{safeText(row.representative_name, "-")}</div><div className="text-xs text-slate-500">{safeText(row.address, "-")}</div></td>
                    <td className="px-3 py-3"><div>{safeText(row.contact_name, "-")}</div><div className="text-xs text-slate-500">{row.contact_phone || "-"}</div></td>
                    <td className="px-3 py-3"><div>{safeText(row.bank_name, "-")} {safeText(row.bank_branch, "")}</div><div className="text-xs text-slate-500">{safeText(row.bank_account_holder, "-")}</div></td>
                    <td className="px-3 py-3">
                      {statusBadge(row.status)}
                      {validateReadableText(row).length ? <div className="mt-1 text-xs font-semibold text-red-500">疑似乱码</div> : null}
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex flex-wrap gap-2">
                        <UploadButton label={row.registry_certificate_name ? "藤本已传" : "藤本PDF"} disabled={saving} onUpload={(file) => uploadPdf(row.id, "registry_certificate", file, uploadFile.mutate)} />
                        <UploadButton label={row.business_license_name ? "许可已传" : "许可PDF"} disabled={saving} onUpload={(file) => uploadPdf(row.id, "business_license", file, uploadFile.mutate)} />
                        <UploadButton label={row.bank_book_name ? "银行已传" : "银行PDF"} disabled={saving} onUpload={(file) => uploadPdf(row.id, "bank_book", file, uploadFile.mutate)} />
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex flex-wrap gap-2">
                        {normalizeRegistrationStatus(row.status) === "archived" ? (
                          <Button type="button" variant="secondary" className="h-8 px-3 text-emerald-700 hover:text-emerald-800" disabled={saving} onClick={() => restoreRegistration(row)}>
                            <RotateCcw size={14} />
                            恢复
                          </Button>
                        ) : isSubmittedRegistration(row.status) ? (
                          <>
                            <Button type="button" className="h-8 px-3 bg-emerald-600 hover:bg-emerald-700" disabled={saving} onClick={() => reviewRegistration(row, "approved")}>
                              <CheckCircle2 size={14} />
                              通过
                            </Button>
                            <Button type="button" variant="secondary" className="h-8 px-3 text-red-600 hover:text-red-700" disabled={saving} onClick={() => reviewRegistration(row, "rejected")}>
                              <XCircle size={14} />
                              退回
                            </Button>
                          </>
                        ) : null}
                        <Button type="button" variant="secondary" className="h-8 px-3" onClick={() => beginEdit(row)}>编辑</Button>
                        {normalizeRegistrationStatus(row.status) !== "archived" ? (
                          <Button type="button" variant="secondary" className="h-8 px-3 text-red-600 hover:text-red-700" disabled={saving} onClick={() => archiveRow(row)}>
                            <Archive size={14} />
                            归档
                          </Button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function Field({ label, required, hint, children }: { label: string; required?: boolean; hint?: string; children: ReactNode }) {
  return (
    <label className="grid gap-1 text-sm">
      <span className="font-semibold text-slate-700">{label}{required ? <span className="text-red-500"> *</span> : null}</span>
      {children}
      {hint ? <span className="text-xs text-slate-400">{hint}</span> : null}
    </label>
  );
}

function UploadButton({ label, disabled, onUpload }: { label: string; disabled: boolean; onUpload: (file: File) => void }) {
  return (
    <label className={`inline-flex h-8 cursor-pointer items-center gap-1 rounded-md border border-border bg-white px-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 ${disabled ? "pointer-events-none opacity-50" : ""}`}>
      <FileUp size={13} />
      {label}
      <input className="hidden" type="file" accept="application/pdf,.pdf" disabled={disabled} onChange={(event) => {
        const file = event.target.files?.[0];
        if (file) onUpload(file);
        event.currentTarget.value = "";
      }} />
    </label>
  );
}

function uploadPdf(id: number, file_type: "registry_certificate" | "business_license" | "bank_book", file: File, mutate: (variables: { id: number; payload: { file_type: "registry_certificate" | "business_license" | "bank_book"; file_name: string; file_base64: string } }) => void) {
  if (file.type && file.type !== "application/pdf") {
    window.alert("请上传 PDF 文件。");
    return;
  }
  const reader = new FileReader();
  reader.onload = () => mutate({ id, payload: { file_type, file_name: file.name, file_base64: String(reader.result || "") } });
  reader.readAsDataURL(file);
}

function validateDraft(payload: Partial<CompanyRegistration>) {
  const required: Array<[keyof CompanyRegistration, string]> = [
    ["company_code", "公司代码"],
    ["company_name", "公司名"],
    ["representative_name", "法人姓名"],
    ["address", "公司地址"],
    ["contact_name", "业务联系人"],
    ["contact_phone", "联系电话"],
    ["bank_name", "银行名称"],
    ["bank_branch", "支店名"],
    ["bank_account_number", "账号号码"],
    ["bank_account_holder", "账户名义"],
  ];
  return required.filter(([key]) => !String(payload[key] || "").trim()).map(([, label]) => label);
}

const readableTextFields: Array<[keyof CompanyRegistration, string]> = [
  ["company_name", "公司名"],
  ["registered_name", "登记会社名"],
  ["representative_name", "法人姓名"],
  ["address", "公司地址"],
  ["contact_name", "业务联系人"],
  ["bank_name", "银行名称"],
  ["bank_branch", "支店名"],
  ["bank_account_holder", "账户名义"],
];

function validateReadableText(payload: Partial<CompanyRegistration>) {
  const status = normalizeRegistrationStatus(payload.status);
  if (!["submitted", "已提交", "pending", "pending_review", "reviewing", "approved", "已通过"].includes(status)) {
    return [];
  }
  return readableTextFields.filter(([key]) => looksUnreadable(payload[key])).map(([, label]) => label);
}

function cleanUnreadableRegistration(row: CompanyRegistration) {
  const cleaned: Partial<CompanyRegistration> = { ...row };
  readableTextFields.forEach(([key]) => {
    if (looksUnreadable(cleaned[key])) {
      (cleaned as Record<string, unknown>)[key] = "";
    }
  });
  return cleaned;
}

function safeText(value: unknown, fallback = "-") {
  if (looksUnreadable(value)) return fallback;
  const text = String(value || "").trim();
  return text || fallback;
}

function looksUnreadable(value: unknown) {
  const text = String(value || "").trim();
  if (!text) return false;
  const compact = text.replace(/\s+/g, "");
  const questionCount = (compact.match(/\?/g) || []).length;
  return questionCount >= 2 && questionCount / Math.max(compact.length, 1) >= 0.25;
}

function normalizeRegistration(payload: Partial<CompanyRegistration>) {
  return cleanPayload({
    ...payload,
    company_code: normalizeCode(payload.company_code || ""),
    registered_name: payload.registered_name || payload.company_name || "",
  });
}

function normalizeCode(value: string) {
  return value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 12);
}

function normalizeRegistrationStatus(status?: string) {
  return String(status || "draft").trim();
}

function isSubmittedRegistration(status?: string) {
  return ["submitted", "已提交", "pending", "pending_review", "reviewing"].includes(normalizeRegistrationStatus(status));
}

function statusBadge(status?: string) {
  const normalized = normalizeRegistrationStatus(status);
  const map: Record<string, string> = {
    draft: "草稿",
    submitted: "已提交",
    "已提交": "已提交",
    pending: "已提交",
    pending_review: "已提交",
    reviewing: "已提交",
    approved: "已通过",
    "已通过": "已通过",
    rejected: "已退回",
    "已退回": "已退回",
    inactive: "停用",
    archived: "已归档",
  };
  const tone = normalized === "approved" || normalized === "已通过"
    ? "bg-emerald-50 text-emerald-700"
    : isSubmittedRegistration(normalized)
      ? "bg-blue-50 text-blue-700"
      : normalized === "rejected" || normalized === "已退回"
        ? "bg-red-50 text-red-700"
        : normalized === "archived"
          ? "bg-slate-200 text-slate-700"
          : "bg-slate-100 text-slate-600";
  return <span className={`rounded-full px-2 py-1 text-xs font-semibold ${tone}`}>{map[normalized] || normalized || "草稿"}</span>;
}

function cleanPayload<T extends Record<string, unknown>>(payload: T): T {
  return Object.fromEntries(Object.entries(payload).map(([key, value]) => [key, value === "" ? null : value])) as T;
}
