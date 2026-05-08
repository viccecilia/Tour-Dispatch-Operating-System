import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(value?: number | string | null) {
  const amount = Number(value || 0);
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "JPY",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

export function shortRoute(from?: string | null, to?: string | null) {
  return `${from || "-"} -> ${to || "-"}`;
}
