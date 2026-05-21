import { useMemo, useState, type FocusEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Plus, Search } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/services/apiClient";
import type { Agency } from "@/types/api";

const agencyInitial: Partial<Agency> = {
  agency_code: "D",
  company_name: "",
  name: "",
  address: "",
  contact_phone: "",
  contact_name: "",
  responsible_person: "",
  contact_email: "",
  fax: "",
  status: "active",
  portal_code: "",
  is_portal_enabled: true,
  remark: "",
};

export function AgenciesPage() {
  const queryClient = useQueryClient();
  const [keyword, setKeyword] = useState("");
  const [status, setStatus] = useState("");
  const [message, setMessage] = useState("");

  const agencies = useQuery({
    queryKey: ["agencies", keyword, status],
    queryFn: () => api.agencies({ keyword, status }),
  });

  const createAgency = useMutation({
    mutationFn: api.createAgency,
    onSuccess: async () => {
      setMessage("旅行社已新增。");
      await invalidate();
    },
    onError: (error: Error) => setMessage(`新增旅行社失败：${error.message}`),
  });

  const updateAgency = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<Agency> }) => api.updateAgency(id, payload),
    onSuccess: async () => {
      setMessage("旅行社信息已更新。");
      await invalidate();
    },
    onError: (error: Error) => setMessage(`更新旅行社失败：${error.message}`),
  });

  const rows = useMemo(() => agencies.data || [], [agencies.data]);

  function invalidate() {
    return Promise.all([
      queryClient.invalidateQueries({ queryKey: ["agencies"] }),
      queryClient.invalidateQueries({ queryKey: ["agency-portal-agencies"] }),
      queryClient.invalidateQueries({ queryKey: ["finance-summary"] }),
      queryClient.invalidateQueries({ queryKey: ["analytics-summary"] }),
    ]);
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-500">客户公司台账</p>
          <h2 className="mt-1 text-2xl font-bold text-slate-950">旅行社维护</h2>
          <p className="mt-1 text-sm text-slate-500">直接在表格中新增和修改旅行社资料。双击已有行编辑，回车或点击表格外保存。</p>
        </div>
      </div>

      {message && <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm font-medium text-blue-700">{message}</div>}

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Building2 size={18} className="text-blue-600" />
              <div>
                <h3 className="text-base font-bold text-slate-950">旅行社资料表</h3>
                <p className="mt-1 text-sm text-slate-500">第一行用于新增；已有行双击修改。</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <div className="flex h-9 items-center gap-2 rounded-md border border-border bg-white px-3">
                <Search size={15} className="text-slate-400" />
                <input className="w-64 bg-transparent text-sm outline-none" value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索代码 / 公司名 / 联系人 / 电话" />
              </div>
              <select className="h-9 rounded-md border border-border bg-white px-3 text-sm" value={status} onChange={(event) => setStatus(event.target.value)}>
                <option value="">全部状态</option>
                <option value="active">启用</option>
                <option value="inactive">停用</option>
              </select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {agencies.isLoading ? (
            <div className="py-10 text-center text-sm text-slate-500">正在加载旅行社资料...</div>
          ) : rows.length === 0 ? (
            <div className="space-y-3">
              <AgencyCreateRow saving={createAgency.isPending} onCreate={(payload) => createAgency.mutate(payload)} />
              <EmptyState title="暂无旅行社资料" detail="直接在上方新增行录入旅行社。" />
            </div>
          ) : (
            <AgencyInlineTable rows={rows} saving={createAgency.isPending || updateAgency.isPending} onCreate={(payload) => createAgency.mutate(payload)} onUpdate={(id, payload) => updateAgency.mutate({ id, payload })} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function AgencyInlineTable({ rows, saving, onCreate, onUpdate }: { rows: Agency[]; saving: boolean; onCreate: (payload: Partial<Agency>) => void; onUpdate: (id: number, payload: Partial<Agency>) => void }) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Partial<Agency>>(agencyInitial);

  function beginEdit(row: Agency) {
    setEditingId(row.id);
    setDraft({ ...row, company_name: row.company_name || row.name, is_portal_enabled: row.is_portal_enabled === true || row.is_portal_enabled === 1 });
  }

  function cancel() {
    setEditingId(null);
    setDraft(agencyInitial);
  }

  function save(id: number) {
    const payload = normalizeAgencyPayload(draft);
    if (!payload.company_name && !payload.name) return;
    onUpdate(id, payload);
    cancel();
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full min-w-[1180px] text-left text-sm">
        <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500">
          <tr>
            <th className="px-3 py-3">代码</th>
            <th className="px-3 py-3">会社名</th>
            <th className="px-3 py-3">地址</th>
            <th className="px-3 py-3">联系方式</th>
            <th className="px-3 py-3">联系人</th>
            <th className="px-3 py-3">责任担当</th>
            <th className="px-3 py-3">邮箱</th>
            <th className="px-3 py-3">传真</th>
            <th className="px-3 py-3">门户代码</th>
            <th className="px-3 py-3">状态</th>
            <th className="px-3 py-3">备注/操作</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          <AgencyCreateRow saving={saving} onCreate={onCreate} />
          {rows.map((agency) => {
            const isEditing = editingId === agency.id;
            return (
              <tr key={agency.id} className={isEditing ? "bg-blue-50/40" : "hover:bg-slate-50 cursor-text"} title="双击本行编辑，回车或点击表格外保存" onDoubleClick={() => !isEditing && beginEdit(agency)} onKeyDown={(event) => handleRowKey(event, () => save(agency.id), cancel)} onBlur={(event) => handleRowBlur(event, isEditing, () => save(agency.id))}>
                <td className="px-3 py-3 font-bold text-slate-950">{isEditing ? <InlineInput value={String(draft.agency_code || "")} onChange={(value) => setDraft({ ...draft, agency_code: value.toUpperCase() })} /> : agency.agency_code || "-"}</td>
                <td className="px-3 py-3">{isEditing ? <InlineInput value={String(draft.company_name || draft.name || "")} onChange={(value) => setDraft({ ...draft, company_name: value, name: value })} /> : <div className="font-semibold text-slate-950">{agency.company_name || agency.name}</div>}</td>
                <td className="px-3 py-3">{isEditing ? <InlineInput value={String(draft.address || "")} onChange={(value) => setDraft({ ...draft, address: value })} /> : agency.address || "-"}</td>
                <td className="px-3 py-3">{isEditing ? <InlineInput value={String(draft.contact_phone || "")} onChange={(value) => setDraft({ ...draft, contact_phone: value })} /> : agency.contact_phone || "-"}</td>
                <td className="px-3 py-3">{isEditing ? <InlineInput value={String(draft.contact_name || "")} onChange={(value) => setDraft({ ...draft, contact_name: value })} /> : agency.contact_name || "-"}</td>
                <td className="px-3 py-3">{isEditing ? <InlineInput value={String(draft.responsible_person || "")} onChange={(value) => setDraft({ ...draft, responsible_person: value })} /> : agency.responsible_person || "-"}</td>
                <td className="px-3 py-3">{isEditing ? <InlineInput value={String(draft.contact_email || "")} onChange={(value) => setDraft({ ...draft, contact_email: value })} /> : agency.contact_email || "-"}</td>
                <td className="px-3 py-3">{isEditing ? <InlineInput value={String(draft.fax || "")} onChange={(value) => setDraft({ ...draft, fax: value })} /> : agency.fax || "-"}</td>
                <td className="px-3 py-3">{isEditing ? <InlineInput value={String(draft.portal_code || "")} onChange={(value) => setDraft({ ...draft, portal_code: value })} /> : agency.portal_code || "未设置"}</td>
                <td className="px-3 py-3">{isEditing ? <InlineSelect value={String(draft.status || "active")} onChange={(value) => setDraft({ ...draft, status: value })} options={[["active", "启用"], ["inactive", "停用"]]} /> : statusBadge(agency.status, agency.is_portal_enabled)}</td>
                <td className="px-3 py-3">{isEditing ? <InlineStack><InlineInput value={String(draft.remark || "")} onChange={(value) => setDraft({ ...draft, remark: value })} placeholder="备注" /><span className="text-xs text-slate-400">回车/点击外面保存，Esc 取消</span></InlineStack> : <span className="text-xs text-slate-400">双击编辑</span>}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function AgencyCreateRow({ saving, onCreate }: { saving: boolean; onCreate: (payload: Partial<Agency>) => void }) {
  const [draft, setDraft] = useState<Partial<Agency>>(agencyInitial);

  function save() {
    const payload = normalizeAgencyPayload(draft);
    if (!payload.company_name && !payload.name) return;
    onCreate(payload);
    setDraft(agencyInitial);
  }

  return (
    <tr className="bg-emerald-50/40" onKeyDown={(event) => handleRowKey(event, save, () => setDraft(agencyInitial))}>
      <td className="px-3 py-3"><InlineInput value={String(draft.agency_code || "")} onChange={(value) => setDraft({ ...draft, agency_code: value.toUpperCase() })} /></td>
      <td className="px-3 py-3"><InlineInput value={String(draft.company_name || "")} onChange={(value) => setDraft({ ...draft, company_name: value, name: value })} placeholder="会社名" /></td>
      <td className="px-3 py-3"><InlineInput value={String(draft.address || "")} onChange={(value) => setDraft({ ...draft, address: value })} placeholder="地址" /></td>
      <td className="px-3 py-3"><InlineInput value={String(draft.contact_phone || "")} onChange={(value) => setDraft({ ...draft, contact_phone: value })} placeholder="电话" /></td>
      <td className="px-3 py-3"><InlineInput value={String(draft.contact_name || "")} onChange={(value) => setDraft({ ...draft, contact_name: value })} placeholder="联系人" /></td>
      <td className="px-3 py-3"><InlineInput value={String(draft.responsible_person || "")} onChange={(value) => setDraft({ ...draft, responsible_person: value })} placeholder="担当" /></td>
      <td className="px-3 py-3"><InlineInput value={String(draft.contact_email || "")} onChange={(value) => setDraft({ ...draft, contact_email: value })} placeholder="邮箱" /></td>
      <td className="px-3 py-3"><InlineInput value={String(draft.fax || "")} onChange={(value) => setDraft({ ...draft, fax: value })} placeholder="传真" /></td>
      <td className="px-3 py-3"><InlineInput value={String(draft.portal_code || "")} onChange={(value) => setDraft({ ...draft, portal_code: value })} placeholder="门户代码" /></td>
      <td className="px-3 py-3"><InlineSelect value={String(draft.status || "active")} onChange={(value) => setDraft({ ...draft, status: value })} options={[["active", "启用"], ["inactive", "停用"]]} /></td>
      <td className="px-3 py-3"><Button type="button" className="h-8 px-2" disabled={saving} onClick={save}><Plus size={14} />新增</Button></td>
    </tr>
  );
}

function InlineInput({ value, onChange, placeholder, type = "text" }: { value: string; onChange: (value: string) => void; placeholder?: string; type?: string }) {
  return <input className="h-8 min-w-28 rounded-md border border-border bg-white px-2 text-xs font-medium text-slate-900 outline-none focus:border-blue-400" type={type} value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />;
}

function InlineSelect({ value, onChange, options }: { value: string; onChange: (value: string) => void; options: Array<[string, string]> }) {
  return <select className="h-8 min-w-24 rounded-md border border-border bg-white px-2 text-xs font-medium text-slate-900 outline-none focus:border-blue-400" value={value} onChange={(event) => onChange(event.target.value)}>{options.map(([option, label]) => <option key={option} value={option}>{label}</option>)}</select>;
}

function InlineStack({ children }: { children: React.ReactNode }) {
  return <div className="grid min-w-36 gap-1">{children}</div>;
}

function handleRowKey(event: React.KeyboardEvent, onEnter: () => void, onEscape: () => void) {
  if (event.key === "Enter") {
    event.preventDefault();
    onEnter();
  }
  if (event.key === "Escape") {
    event.preventDefault();
    onEscape();
  }
}

function handleRowBlur(event: FocusEvent<HTMLTableRowElement>, active: boolean, onBlurSave: () => void) {
  if (active && !event.currentTarget.contains(event.relatedTarget as Node | null)) onBlurSave();
}

function normalizeAgencyPayload(payload: Partial<Agency>) {
  const companyName = payload.company_name || payload.name || "";
  return cleanPayload({ ...payload, company_name: companyName, name: companyName, is_portal_enabled: payload.is_portal_enabled ? 1 : 0 });
}

function statusBadge(status?: string, portalEnabled?: number | boolean) {
  const active = status !== "inactive";
  return <span className={`rounded-full px-2 py-1 text-xs font-semibold ${active ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>{active ? "启用" : "停用"}{portalEnabled ? " / 门户" : ""}</span>;
}

function cleanPayload<T extends Record<string, unknown>>(payload: T): T {
  return Object.fromEntries(Object.entries(payload).map(([key, value]) => [key, value === "" ? null : value])) as T;
}
