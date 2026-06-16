import { useEffect, useState } from "react";
import { SaasShell } from "@/layouts/SaasShell";
import { useNavigationStore } from "@/stores/navigationStore";
import { AgenciesPage } from "@/pages/AgenciesPage";
import { AgencyPortalPage } from "@/pages/AgencyPortalPage";
import { AutomationPage } from "@/pages/AutomationPage";
import { AuditPage } from "@/pages/AuditPage";
import { AuctionHallPage } from "@/pages/AuctionHallPage";
import { CopilotPage } from "@/pages/CopilotPage";
import { CalendarPage } from "@/pages/CalendarPage";
import { AnalyticsPage } from "@/pages/AnalyticsPage";
import { AttendancePage } from "@/pages/AttendancePage";
import { CompanyRegistrationPage } from "@/pages/CompanyRegistrationPage";
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
import { canAccessPage } from "@/auth/permissions";
import type { AuthUser } from "@/types/api";
import type { PageKey } from "@/stores/navigationStore";

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
      .then((result) => {
        if (result.user.must_change_password) {
          clearAuthToken();
          setUser(null);
          return;
        }
        setUser(result.user);
      })
      .catch(() => {
        clearAuthToken();
        setUser(null);
      })
      .finally(() => setCheckingAuth(false));
  }, []);

  useEffect(() => {
    const onHashChange = () => {
      const page = (window.location.hash.replace("#", "") || "dashboard") as PageKey;
      setActivePage(page);
    };
    onHashChange();
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, [setActivePage]);

  useEffect(() => {
    if (user && !canAccessPage(user, activePage) && activePage !== "dashboard") {
      setActivePage("dashboard");
    }
  }, [activePage, setActivePage, user]);

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

  const activeAllowed = canAccessPage(user, activePage);

  const page = {
    dashboard: <DashboardPage />,
    notifications: <NotificationsPage />,
    parser: <ParserPage />,
    orders: <OrdersPage />,
    dispatch: <DispatchPage />,
    auction: <AuctionHallPage />,
    calendar: <CalendarPage />,
    "driver-monitor": <DriverMonitorPage />,
    attendance: <AttendancePage />,
    map: <MapPage />,
    vehicles: <VehiclesPage />,
    "company-registration": <CompanyRegistrationPage />,
    agencies: <AgenciesPage />,
    incidents: <IncidentsPage />,
    finance: <FinancePage />,
    analytics: <AnalyticsPage />,
    automation: <AutomationPage />,
    copilot: <CopilotPage />,
    audit: <AuditPage />,
    system: <SystemMaintenancePage />,
    settings: <SettingsPage currentUser={user} />,
  }[activeAllowed ? activePage : "dashboard"];

  return (
    <SaasShell user={user} onLogout={() => {
      clearAuthToken();
      setUser(null);
    }}>
      {page}
    </SaasShell>
  );
}
