import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, FileUp, Plus, Save, Search } from "lucide-react";
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

export function CompanyRegistrationPage() {
  const queryClient = useQueryClient();
  const [keyword, setKeyword] = useState("");
  const [companyType, setCompanyType] = useState("");
  const [status, setStatus] = useState("");
  const [draft, setDraft] = useState<Partial<CompanyRegistration>>(initialDraft);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [message, setMessage] = useState("");

  const registrations = useQuery({
    queryKey: ["company-registrations", keyword, companyType, status],
    queryFn: () => api.companyRegistrations({ keyword, company_type: companyType, status }),
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

  const uploadFile = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: { file_type: "registry_certificate" | "business_license" | "bank_book"; file_name: string; file_base64: string } }) => api.uploadCompanyRegistrationFile(id, payload),
    onSuccess: async () => {
      setMessage("文件已上传。");
      await invalidate();
    },
    onError: (error: Error) => setMessage(`上传失败：${error.message}`),
  });

  const rows = useMemo(() => registrations.data || [], [registrations.data]);
  const saving = createRegistration.isPending || updateRegistration.isPending || uploadFile.isPending;
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
    if (editingId) {
      updateRegistration.mutate({ id: editingId, payload });
      return;
    }
    createRegistration.mutate(payload);
  }

  function beginEdit(row: CompanyRegistration) {
    setEditingId(row.id);
    setDraft({ ...initialDraft, ...row });
    setMessage("");
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-500">公司准入与资料审核</p>
          <h2 className="mt-1 text-2xl font-bold text-slate-950">公司注册</h2>
          <p className="mt-1 text-sm text-slate-500">车公司和旅行社都必须填写缩写代码。藤本信息按 PDF 件上传，银行账户、地址、法人姓名、联络电话为必填资料。</p>
        </div>
      </div>

      {message && <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm font-medium text-blue-700">{message}</div>}

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Building2 size={18} className="text-blue-600" />
            <div>
              <h3 className="text-base font-bold text-slate-950">{editingId ? "编辑公司资料" : "新增公司注册"}</h3>
              <p className="mt-1 text-sm text-slate-500">字段不足时会提示，资料可保存草稿或提交审核。</p>
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
            <Field label="公司缩写代码" required hint="订单号、登录前缀、平台展示使用">
              <input className="field" value={draft.company_code || ""} maxLength={12} onChange={(event) => setDraft({ ...draft, company_code: normalizeCode(event.target.value) })} placeholder="例：SKR / AGT" />
            </Field>
            <Field label="对外显示公司名" required>
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
            <Field label="旅行业/事业许可号">
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
            <Field label="联络电话" required>
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
            <Field label="账户号码" required>
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
              </select>
            </Field>
            <Field label="审核备注">
              <input className="field" value={draft.review_note || ""} onChange={(event) => setDraft({ ...draft, review_note: event.target.value })} />
            </Field>
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <div className="text-sm text-slate-500">{fieldErrors.length ? `还缺：${fieldErrors.join("、")}` : "必填资料已完整，可以保存或提交审核。"}</div>
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
              <p className="mt-1 text-sm text-slate-500">点击编辑资料；藤本 PDF、许可文件、银行资料在列表中上传。</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <div className="flex h-9 items-center gap-2 rounded-md border border-border bg-white px-3">
                <Search size={15} className="text-slate-400" />
                <input className="w-64 bg-transparent text-sm outline-none" value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索代码 / 公司名 / 法人 / 电话" />
              </div>
              <select className="h-9 rounded-md border border-border bg-white px-3 text-sm" value={companyType} onChange={(event) => setCompanyType(event.target.value)}>
                <option value="">全部类型</option>
                <option value="carrier">车公司</option>
                <option value="agency">旅行社</option>
              </select>
              <select className="h-9 rounded-md border border-border bg-white px-3 text-sm" value={status} onChange={(event) => setStatus(event.target.value)}>
                <option value="">全部状态</option>
                <option value="draft">草稿</option>
                <option value="submitted">已提交</option>
                <option value="approved">已通过</option>
                <option value="rejected">已退回</option>
              </select>
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
                  <th className="px-3 py-3">法人/地址</th>
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
                  <tr><td className="px-3 py-8 text-center text-slate-500" colSpan={9}>暂无注册资料</td></tr>
                ) : rows.map((row) => (
                  <tr key={row.id} className="hover:bg-slate-50">
                    <td className="px-3 py-3">{row.company_type === "agency" ? "旅行社" : "车公司"}</td>
                    <td className="px-3 py-3 font-bold text-slate-950">{row.company_code}</td>
                    <td className="px-3 py-3"><div className="font-semibold text-slate-950">{row.company_name}</div><div className="text-xs text-slate-500">{row.registered_name || "-"}</div></td>
                    <td className="px-3 py-3"><div>{row.representative_name || "-"}</div><div className="text-xs text-slate-500">{row.address || "-"}</div></td>
                    <td className="px-3 py-3"><div>{row.contact_name || "-"}</div><div className="text-xs text-slate-500">{row.contact_phone || "-"}</div></td>
                    <td className="px-3 py-3"><div>{row.bank_name || "-"} {row.bank_branch || ""}</div><div className="text-xs text-slate-500">{row.bank_account_holder || "-"}</div></td>
                    <td className="px-3 py-3">{statusBadge(row.status)}</td>
                    <td className="px-3 py-3">
                      <div className="flex flex-wrap gap-2">
                        <UploadButton label={row.registry_certificate_name ? "藤本已传" : "藤本PDF"} disabled={saving} onUpload={(file) => uploadPdf(row.id, "registry_certificate", file, uploadFile.mutate)} />
                        <UploadButton label={row.business_license_name ? "许可已传" : "许可PDF"} disabled={saving} onUpload={(file) => uploadPdf(row.id, "business_license", file, uploadFile.mutate)} />
                        <UploadButton label={row.bank_book_name ? "银行已传" : "银行PDF"} disabled={saving} onUpload={(file) => uploadPdf(row.id, "bank_book", file, uploadFile.mutate)} />
                      </div>
                    </td>
                    <td className="px-3 py-3"><Button type="button" variant="secondary" className="h-8 px-3" onClick={() => beginEdit(row)}>编辑</Button></td>
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

function Field({ label, required, hint, children }: { label: string; required?: boolean; hint?: string; children: React.ReactNode }) {
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
    ["company_code", "公司缩写代码"],
    ["company_name", "公司名"],
    ["representative_name", "法人姓名"],
    ["address", "公司地址"],
    ["contact_name", "业务联系人"],
    ["contact_phone", "联络电话"],
    ["bank_name", "银行名称"],
    ["bank_branch", "支店名"],
    ["bank_account_number", "账户号码"],
    ["bank_account_holder", "账户名义"],
  ];
  return required.filter(([key]) => !String(payload[key] || "").trim()).map(([, label]) => label);
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

function statusBadge(status?: string) {
  const map: Record<string, string> = { draft: "草稿", submitted: "已提交", approved: "已通过", rejected: "已退回", inactive: "停用" };
  const tone = status === "approved" ? "bg-emerald-50 text-emerald-700" : status === "submitted" ? "bg-blue-50 text-blue-700" : status === "rejected" ? "bg-red-50 text-red-700" : "bg-slate-100 text-slate-600";
  return <span className={`rounded-full px-2 py-1 text-xs font-semibold ${tone}`}>{map[status || "draft"] || status || "草稿"}</span>;
}

function cleanPayload<T extends Record<string, unknown>>(payload: T): T {
  return Object.fromEntries(Object.entries(payload).map(([key, value]) => [key, value === "" ? null : value])) as T;
}
