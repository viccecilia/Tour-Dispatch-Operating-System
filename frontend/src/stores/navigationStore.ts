import { create } from "zustand";

export type PageKey =
  | "dashboard"
  | "notifications"
  | "parser"
  | "orders"
  | "dispatch"
  | "calendar"
  | "driver-monitor"
  | "map"
  | "vehicles"
  | "agencies"
  | "incidents"
  | "finance"
  | "analytics"
  | "automation"
  | "copilot"
  | "audit"
  | "settings";

type NavigationState = {
  activePage: PageKey;
  setActivePage: (page: PageKey) => void;
};

function pageFromHash(): PageKey {
  const hash = window.location.hash.replace("#", "");
  const known: PageKey[] = [
    "dashboard",
    "notifications",
    "parser",
    "orders",
    "dispatch",
    "calendar",
    "driver-monitor",
    "map",
    "vehicles",
    "agencies",
    "incidents",
    "finance",
    "analytics",
    "automation",
    "copilot",
    "audit",
    "settings",
  ];
  return known.includes(hash as PageKey) ? (hash as PageKey) : "dashboard";
}

export const useNavigationStore = create<NavigationState>((set) => ({
  activePage: pageFromHash(),
  setActivePage: (page) => {
    window.location.hash = page;
    set({ activePage: page });
  },
}));
