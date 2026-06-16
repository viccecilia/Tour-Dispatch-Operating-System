import type { PageKey } from "@/stores/navigationStore";
import type { AuthUser } from "@/types/api";

export type AccountScope = "platform" | "carrier" | "agency" | "driver";

const PLATFORM_PAGES = new Set<PageKey>([
  "dashboard",
  "notifications",
  "company-registration",
  "agencies",
  "vehicles",
  "driver-monitor",
  "map",
  "finance",
  "analytics",
  "automation",
  "copilot",
  "settings",
]);

const CARRIER_ADMIN_PAGES = new Set<PageKey>([
  "dashboard",
  "notifications",
  "parser",
  "orders",
  "dispatch",
  "auction",
  "calendar",
  "driver-monitor",
  "attendance",
  "map",
  "vehicles",
  "incidents",
  "finance",
  "analytics",
  "automation",
  "copilot",
  "settings",
]);

const CARRIER_DISPATCHER_PAGES = new Set<PageKey>([
  "dashboard",
  "notifications",
  "orders",
  "dispatch",
  "calendar",
  "driver-monitor",
  "attendance",
  "map",
  "vehicles",
  "incidents",
  "automation",
  "copilot",
  "settings",
]);

const CARRIER_OPERATIONS_PAGES = new Set<PageKey>([
  "dashboard",
  "notifications",
  "calendar",
  "driver-monitor",
  "attendance",
  "map",
  "vehicles",
  "incidents",
  "automation",
  "copilot",
  "settings",
]);

const DRIVER_PAGES = new Set<PageKey>(["dashboard", "notifications", "settings"]);

export function accountScope(user: AuthUser): AccountScope {
  return (user.account_scope as AccountScope | undefined) || (user.role === "driver" ? "driver" : "carrier");
}

export function isPlatformUser(user: AuthUser) {
  return accountScope(user) === "platform";
}

export function canAccessPage(user: AuthUser, page: PageKey | string) {
  if (page === "audit" || page === "system") return isPlatformUser(user);
  const pageKey = page as PageKey;
  const scope = accountScope(user);
  if (scope === "platform") return PLATFORM_PAGES.has(pageKey) || page === "audit" || page === "system";
  if (scope === "agency") return false;
  if (scope === "driver") return DRIVER_PAGES.has(pageKey);
  if (user.role === "admin") return CARRIER_ADMIN_PAGES.has(pageKey);
  if (user.role === "dispatcher") return CARRIER_DISPATCHER_PAGES.has(pageKey);
  if (user.role === "operations_manager") return CARRIER_OPERATIONS_PAGES.has(pageKey);
  if (user.role === "driver") return DRIVER_PAGES.has(pageKey);
  return false;
}
