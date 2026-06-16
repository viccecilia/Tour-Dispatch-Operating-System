import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/apiClient";

type Props = {
  value: string;
  onChange: (value: string) => void;
  allLabel?: string;
  className?: string;
};

export function CompanyScopeFilter({ value, onChange, allLabel = "全部公司", className = "" }: Props) {
  const me = useQuery({ queryKey: ["auth-me"], queryFn: api.me, staleTime: 60_000 });
  const isPlatform = me.data?.user?.account_scope === "platform";
  const tenants = useQuery({
    queryKey: ["platform-tenants"],
    queryFn: api.platformTenants,
    enabled: isPlatform,
    staleTime: 60_000,
  });

  useEffect(() => {
    if (!isPlatform && value !== "") onChange("");
  }, [isPlatform, onChange, value]);

  if (!isPlatform) return null;

  return (
    <label className={`inline-flex h-10 items-center gap-2 rounded-xl border border-border bg-white px-3 text-sm font-semibold text-slate-700 ${className}`}>
      <span className="whitespace-nowrap text-xs font-bold text-slate-500">公司</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-8 min-w-44 bg-transparent text-sm font-semibold outline-none"
      >
        <option value="all">{allLabel}</option>
        {(tenants.data || []).map((tenant) => (
          <option key={tenant.id} value={tenant.id}>
            {tenant.name}
          </option>
        ))}
      </select>
    </label>
  );
}

export function isAllCompanyScope(value: string) {
  return !value || value === "all";
}
