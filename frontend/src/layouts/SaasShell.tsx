import {
  AlertTriangle,
  BarChart3,
  Bell,
  Bot,
  Building2,
  CalendarDays,
  CarFront,
  ClipboardList,
  FileCheck2,
  FileText,
  Gavel,
  LayoutDashboard,
  LucideIcon,
  MapPinned,
  MonitorCog,
  Receipt,
  Route,
  Settings,
  TimerReset,
  Truck,
} from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/apiClient";
import { PageKey, useNavigationStore } from "@/stores/navigationStore";
import { useLanguageStore } from "@/stores/languageStore";
import { cn } from "@/lib/utils";
import { accountScope, canAccessPage } from "@/auth/permissions";
import type { AuthUser } from "@/types/api";
import type { Locale } from "@/i18n/dictionaries";

const navItems: Array<{ key: PageKey; label: string; labelKey?: string; icon: LucideIcon }> = [
  { key: "dashboard", label: "总览", labelKey: "nav.dashboard", icon: LayoutDashboard },
  { key: "notifications", label: "通知中心", labelKey: "notifications.title", icon: Bell },
  { key: "parser", label: "订单解析", labelKey: "nav.parser", icon: FileText },
  { key: "orders", label: "订单", labelKey: "nav.orders", icon: ClipboardList },
  { key: "dispatch", label: "派车", labelKey: "nav.dispatch", icon: Route },
  { key: "auction", label: "订单大厅", icon: Gavel },
  { key: "calendar", label: "日历", labelKey: "nav.calendar", icon: CalendarDays },
  { key: "driver-monitor", label: "司机监控", labelKey: "nav.driver-monitor", icon: MonitorCog },
  { key: "attendance", label: "出勤台账", icon: TimerReset },
  { key: "map", label: "车辆地图", labelKey: "nav.map", icon: MapPinned },
  { key: "vehicles", label: "车辆/司机", labelKey: "nav.vehicles", icon: Truck },
  { key: "company-registration", label: "公司注册", icon: FileCheck2 },
  { key: "agencies", label: "旅行社", labelKey: "nav.agencies", icon: Building2 },
  { key: "incidents", label: "异常", labelKey: "nav.incidents", icon: AlertTriangle },
  { key: "finance", label: "财务", labelKey: "nav.finance", icon: Receipt },
  { key: "analytics", label: "经营分析", labelKey: "nav.analytics", icon: BarChart3 },
  { key: "automation", label: "自动化", labelKey: "nav.automation", icon: Bot },
  { key: "copilot", label: "运营助手", labelKey: "nav.copilot", icon: Bot },
  { key: "settings", label: "设置", labelKey: "nav.settings", icon: Settings },
];

const pageTitles: Record<PageKey, string> = {
  dashboard: "总览",
  notifications: "通知中心",
  parser: "订单解析",
  orders: "订单",
  dispatch: "派车",
  auction: "订单大厅",
  calendar: "日历",
  "driver-monitor": "司机监控",
  attendance: "出勤台账",
  map: "车辆地图",
  vehicles: "车辆/司机",
  "company-registration": "公司注册",
  agencies: "旅行社",
  incidents: "异常",
  finance: "财务",
  analytics: "经营分析",
  automation: "自动化",
  copilot: "运营助手",
  audit: "审计",
  system: "系统维护",
  settings: "设置",
};

const localeLabels: Record<Locale, string> = {
  "zh-CN": "中文",
  "ja-JP": "日本語",
  "en-US": "English",
};

export function SaasShell({ children, user, onLogout }: { children: ReactNode; user: AuthUser; onLogout: () => void }) {
  const { activePage, setActivePage } = useNavigationStore();
  const { locale, setLocale, t } = useLanguageStore();
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const notifications = useQuery({
    queryKey: ["notification-summary"],
    queryFn: api.notificationSummary,
    refetchInterval: 20_000,
  });
  const scope = accountScope(user);

  return (
    <div className="min-h-screen bg-[#eef3f8]">
      <aside className="fixed inset-y-0 left-0 z-30 flex w-64 flex-col border-r border-slate-200 bg-white text-slate-900 shadow-sm">
        <div className="flex h-16 items-center gap-3 border-b border-white/10 px-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-600 text-white shadow-sm">
            <CarFront size={20} />
          </div>
          <div>
            <p className="text-sm font-black text-slate-950">{t("app.brand")}</p>
            <p className="text-xs font-semibold text-slate-500">{scopeLabel(scope)}</p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-4">
          {navItems.filter((item) => canAccessPage(user, item.key)).map((item) => {
            const Icon = item.icon;
            const active = item.key === activePage;
            return (
              <button
                key={item.key}
                className={cn(
                  "focus-runtime flex h-10 w-full items-center gap-3 rounded-xl px-3 text-sm font-bold text-slate-600 transition",
                  active ? "bg-blue-50 text-blue-700 shadow-sm" : "micro-press hover:bg-slate-50 hover:text-slate-950",
                )}
                onClick={() => setActivePage(item.key)}
              >
                <Icon size={18} />
                {item.labelKey ? t(item.labelKey) : item.label}
              </button>
            );
          })}
        </nav>

        <div className="border-t border-slate-200 p-4 text-xs text-slate-500">
          <p className="font-bold text-slate-950">{user.display_name || user.username}</p>
          <p className="mt-1">{user.tenant?.name || `租户 ${user.tenant_id}`}</p>
          <p>{scopeLabel(scope)}</p>
        </div>
      </aside>

      <div className="pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-slate-200 bg-white/90 px-8 backdrop-blur-xl">
          <div>
            <p className="text-xs font-semibold uppercase tracking-normal text-slate-500">{scopeLabel(scope)}</p>
            <h1 className="text-xl font-bold text-slate-950">{pageTitles[activePage]}</h1>
          </div>
          <div className="flex items-center gap-3">
            <select
              className="h-9 rounded-full border border-border bg-white px-3 text-xs font-semibold text-slate-700"
              value={locale}
              onChange={(event) => setLocale(event.target.value as Locale)}
              title="语言"
            >
              {(Object.keys(localeLabels) as Locale[]).map((item) => (
                <option key={item} value={item}>
                  {localeLabels[item]}
                </option>
              ))}
            </select>
            <div className="relative">
              <button
                className="micro-press focus-runtime relative flex h-9 w-9 items-center justify-center rounded-full border border-border bg-white text-slate-700 hover:bg-slate-50"
                onClick={() => setNotificationsOpen((value) => !value)}
                title="通知中心"
              >
                <Bell size={17} />
                {(notifications.data?.unread || 0) > 0 ? (
                  <span className="runtime-pulse-dot absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
                    {notifications.data?.unread}
                  </span>
                ) : null}
              </button>
              {notificationsOpen ? (
                <div className="absolute right-0 top-11 z-50 w-96 overflow-hidden rounded-xl border border-border bg-white shadow-xl">
                  <div className="flex items-center justify-between border-b border-border px-4 py-3">
                    <div>
                      <div className="text-sm font-bold text-slate-950">通知中心</div>
                      <div className="text-xs text-slate-500">
                        {notifications.data?.unread || 0} 未读 · {notifications.data?.urgent || 0} 紧急
                      </div>
                    </div>
                    <button
                      className="text-xs font-semibold text-blue-600"
                      onClick={() => api.markAllNotificationsRead().then(() => notifications.refetch())}
                    >
                      全部已读
                    </button>
                  </div>
                  <div className="max-h-96 overflow-auto">
                    {(notifications.data?.latest || []).length ? (
                      notifications.data?.latest.map((item) => (
                        <button
                          key={item.id}
                          className="micro-press block w-full border-b border-border px-4 py-3 text-left hover:bg-slate-50"
                          onClick={() => {
                            api.markNotificationRead(item.id).then(() => notifications.refetch());
                            if (item.link) window.location.hash = item.link.replace("#", "");
                          }}
                        >
                          <div className="flex items-center justify-between gap-3">
                            <span className="truncate text-sm font-bold text-slate-950">{item.title}</span>
                            <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${item.priority === "critical" || item.priority === "high" ? "bg-red-50 text-red-700" : "bg-slate-100 text-slate-600"}`}>
                              {priorityLabel(item.priority)}
                            </span>
                          </div>
                          <div className="mt-1 line-clamp-2 text-xs text-slate-500">{item.body || notificationTypeLabel(item.notification_type)}</div>
                          <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
                            <span>{notificationTypeLabel(item.notification_type)}</span>
                            <span>{item.status === "read" ? "已读" : "未读"}</span>
                          </div>
                        </button>
                      ))
                    ) : (
                      <div className="px-4 py-8 text-center text-sm text-slate-500">暂无通知</div>
                    )}
                  </div>
                </div>
              ) : null}
            </div>
            <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">{scopeLabel(scope)}</span>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">{roleLabel(user.role)}</span>
            <button className="micro-press focus-runtime rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white" onClick={onLogout}>
              退出
            </button>
          </div>
        </header>

        <main className="runtime-page p-6 2xl:p-8">{children}</main>
      </div>
    </div>
  );
}

function scopeLabel(scope: string) {
  return { platform: "平台总后台", carrier: "车公司后台", agency: "旅行社端", driver: "司机端" }[scope] || scope;
}

function roleLabel(role: string) {
  return { admin: "管理员", dispatcher: "调度员", operations_manager: "运行管理", driver: "司机" }[role] || role;
}

function priorityLabel(priority?: string) {
  return { critical: "严重", high: "高", normal: "普通", low: "低" }[priority || ""] || "普通";
}

function notificationTypeLabel(type?: string) {
  return {
    resource_reminder: "资源提醒",
    dispatch_assigned: "派车通知",
    driver_report: "司机报备",
    incident: "异常通知",
    workflow_reminder: "规则提醒",
    workflow_suggestion: "规则建议",
  }[type || ""] || type || "系统通知";
}
