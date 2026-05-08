import {
  CalendarDays,
  CarFront,
  ClipboardList,
  FileText,
  LayoutDashboard,
  LucideIcon,
  MonitorCog,
  Receipt,
  Route,
  Settings,
  Truck,
} from "lucide-react";
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/apiClient";
import { PageKey, useNavigationStore } from "@/stores/navigationStore";
import { cn } from "@/lib/utils";

const navItems: Array<{ key: PageKey; label: string; icon: LucideIcon }> = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "parser", label: "Parser", icon: FileText },
  { key: "orders", label: "Orders", icon: ClipboardList },
  { key: "dispatch", label: "Dispatch", icon: Route },
  { key: "calendar", label: "Calendar", icon: CalendarDays },
  { key: "driver-monitor", label: "Driver Monitor", icon: MonitorCog },
  { key: "vehicles", label: "Vehicles", icon: Truck },
  { key: "finance", label: "Finance", icon: Receipt },
  { key: "settings", label: "Settings", icon: Settings },
];

const titles: Record<PageKey, string> = {
  dashboard: "运营总览",
  parser: "订单解析",
  orders: "订单中心",
  dispatch: "派车工作台",
  calendar: "日历排程",
  "driver-monitor": "司机执行监控",
  vehicles: "车辆资源",
  finance: "财务概览",
  settings: "系统设置",
};

export function SaasShell({ children }: { children: ReactNode }) {
  const { activePage, setActivePage } = useNavigationStore();
  const ping = useQuery({ queryKey: ["ping"], queryFn: api.ping, refetchInterval: 30_000 });

  return (
    <div className="min-h-screen bg-slate-100">
      <aside className="fixed inset-y-0 left-0 z-30 flex w-64 flex-col border-r border-slate-900 bg-slate-950 text-white">
        <div className="flex h-16 items-center gap-3 border-b border-white/10 px-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-500">
            <CarFront size={20} />
          </div>
          <div>
            <p className="text-sm font-semibold text-white">WX Dispatch</p>
            <p className="text-xs text-slate-400">Admin Console</p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-4">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = item.key === activePage;
            return (
              <button
                key={item.key}
                className={cn(
                  "flex h-10 w-full items-center gap-3 rounded-md px-3 text-sm font-medium text-slate-300 transition",
                  active ? "bg-white/10 text-white" : "hover:bg-white/5 hover:text-white",
                )}
                onClick={() => setActivePage(item.key)}
              >
                <Icon size={18} />
                {item.label}
              </button>
            );
          })}
        </nav>

        <div className="border-t border-white/10 p-4 text-xs text-slate-400">
          <p>Demo Runtime</p>
          <p className="mt-1 truncate">{api.baseUrl}</p>
        </div>
      </aside>

      <div className="pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-border bg-white/90 px-8 backdrop-blur">
          <div>
            <p className="text-xs font-semibold uppercase tracking-normal text-slate-500">SaaS Operations</p>
            <h1 className="text-xl font-bold text-slate-950">{titles[activePage]}</h1>
          </div>
          <div className="flex items-center gap-3">
            <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">Demo Mode</span>
            <span
              className={cn(
                "rounded-full px-3 py-1 text-xs font-semibold",
                ping.isError ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700",
              )}
            >
              API {ping.isError ? "offline" : "online"}
            </span>
          </div>
        </header>

        <main className="p-8">{children}</main>
      </div>
    </div>
  );
}
