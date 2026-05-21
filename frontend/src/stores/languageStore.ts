import { create } from "zustand";
import type { Locale } from "@/i18n/dictionaries";
import { defaultLocale, translate } from "@/i18n/dictionaries";

const STORAGE_KEY = "wx_dispatch_locale";

type LanguageState = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string) => string;
};

function initialLocale(): Locale {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === "ja-JP" || stored === "en-US" || stored === "zh-CN" ? stored : defaultLocale;
}

export const useLanguageStore = create<LanguageState>((set, get) => ({
  locale: initialLocale(),
  setLocale: (locale) => {
    window.localStorage.setItem(STORAGE_KEY, locale);
    set({ locale });
  },
  t: (key) => translate(get().locale, key),
}));
