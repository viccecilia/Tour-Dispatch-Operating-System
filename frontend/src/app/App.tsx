import { useEffect, useState } from "react";
import { SaasShell } from "@/layouts/SaasShell";
import { useNavigationStore } from "@/stores/navigationStore";
import { AgenciesPage } from "@/pages/AgenciesPage";
import { AgencyPortalPage } from "@/pages/AgencyPortalPage";
import { AutomationPage } from "@/pages/AutomationPage";
import { AuditPage } from "@/pages/AuditPage";
import { CopilotPage } from "@/pages/CopilotPage";
import { CalendarPage } from "@/pages/CalendarPage";
import { AnalyticsPage } from "@/pages/AnalyticsPage";
import { AttendancePage } from "@/pages/AttendancePage";
import { DashboardPage } from "@/pages/DashboardPage";
import { DispatchPage } from "@/pages/DispatchPage";
import { DriverAppPreviewPage } from "@/pages/DriverAppPreviewPage";
import { DriverMonitorPage } from "@/pages/DriverMonitorPage";
import { FinancePage } from "@/pages/FinancePage";
import { IncidentsPage } from "@/pages/IncidentsPage";
import { LoginPage } from "@/pages/LoginPage";
import { MapPage } from "@/pages/MapPage";
import { NotificationsPage } from "@/pages/NotificationsPage";
import { OrdersPage } from "@/pages/OrdersPage";
import { ParserPage } from "@/pages/ParserPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { SystemMaintenancePage } from "@/pages/SystemMaintenancePage";
import { VehiclesPage } from "@/pages/VehiclesPage";
import { api, clearAuthToken, getAuthToken } from "@/services/apiClient";
import type { AuthUser } from "@/types/api";

export function App() {
  const { activePage, setActivePage } = useNavigationStore();
  const isAgencyPortal = window.location.hash.replace("#", "") === "agency-portal";
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checkingAuth, setCheckingAuth] = useState(true);

  useEffect(() => {
    const token = getAuthToken();
    if (!token) {
      setCheckingAuth(false);
      return;
    }
    api
      .me()
      .then((result) => setUser(result.user))
      .catch(() => {
        clearAuthToken();
        setUser(null);
      })
      .finally(() => setCheckingAuth(false));
  }, []);

  useEffect(() => {
    const onHashChange = () => {
      const page = (window.location.hash.replace("#", "") || "dashboard") as typeof activePage;
      setActivePage(page);
    };
    onHashChange();
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, [setActivePage]);

  if (isAgencyPortal) {
    return <AgencyPortalPage />;
  }

  if (window.location.hash.replace("#", "") === "driver-app") {
    return <DriverAppPreviewPage />;
  }

  if (checkingAuth) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-100 text-sm font-semibold text-slate-500">正在校验登录态...</div>;
  }

  if (!user) {
    return <LoginPage onLogin={setUser} />;
  }

  const page = {
    dashboard: <DashboardPage />,
    notifications: <NotificationsPage />,
    parser: <ParserPage />,
    orders: <OrdersPage />,
    dispatch: <DispatchPage />,
    calendar: <CalendarPage />,
    "driver-monitor": <DriverMonitorPage />,
    attendance: <AttendancePage />,
    map: <MapPage />,
    vehicles: <VehiclesPage />,
    agencies: <AgenciesPage />,
    incidents: <IncidentsPage />,
    finance: <FinancePage />,
    analytics: <AnalyticsPage />,
    automation: <AutomationPage />,
    copilot: <CopilotPage />,
    audit: <AuditPage />,
    system: <SystemMaintenancePage />,
    settings: <SettingsPage currentUser={user} />,
  }[canAccessPage(user.role, activePage) ? activePage : "dashboard"];

  return (
    <SaasShell user={user} onLogout={() => {
      clearAuthToken();
      setUser(null);
    }}>
      {page}
    </SaasShell>
  );
}

function canAccessPage(role: string, page: string) {
  if (page === "system") return role === "admin";
  if (page === "finance") return role === "admin";
  if (page === "analytics") return role === "admin";
  if (role === "operations_manager") return !["parser", "orders", "dispatch", "finance", "analytics", "system"].includes(page);
  if (role === "dispatcher") return !["finance", "analytics", "system"].includes(page);
  return true;
}
