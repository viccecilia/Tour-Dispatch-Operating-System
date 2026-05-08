import { useEffect } from "react";
import { SaasShell } from "@/layouts/SaasShell";
import { useNavigationStore } from "@/stores/navigationStore";
import { CalendarPage } from "@/pages/CalendarPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { DispatchPage } from "@/pages/DispatchPage";
import { DriverMonitorPage } from "@/pages/DriverMonitorPage";
import { OrdersPage } from "@/pages/OrdersPage";
import { ParserPage } from "@/pages/ParserPage";
import { PlaceholderPage } from "@/pages/PlaceholderPage";

export function App() {
  const { activePage, setActivePage } = useNavigationStore();

  useEffect(() => {
    const onHashChange = () => {
      const page = (window.location.hash.replace("#", "") || "dashboard") as typeof activePage;
      setActivePage(page);
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, [setActivePage]);

  const page = {
    dashboard: <DashboardPage />,
    parser: <ParserPage />,
    orders: <OrdersPage />,
    dispatch: <DispatchPage />,
    calendar: <CalendarPage />,
    "driver-monitor": <DriverMonitorPage />,
    vehicles: <PlaceholderPage title="车辆资源" description="车辆基础管理继续沿用现有 API，本轮先完成 SaaS 外壳。" />,
    finance: <PlaceholderPage title="财务概览" description="本 MVP 只展示订单价格，不做复杂财务计算。" />,
    settings: <PlaceholderPage title="系统设置" description="运行配置由 .env 与 backend/config.py 管理。" />,
  }[activePage];

  return <SaasShell>{page}</SaasShell>;
}
