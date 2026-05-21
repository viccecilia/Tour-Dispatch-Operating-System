export type Locale = "zh-CN" | "ja-JP" | "en-US";

export const defaultLocale: Locale = "zh-CN";

export const dictionaries: Record<Locale, Record<string, string>> = {
  "zh-CN": {
    "app.brand": "微信调度",
    "app.subtitle": "运营中台",
    "topbar.section": "运营台",
    "topbar.demo": "演示模式",
    "topbar.apiOnline": "接口在线",
    "topbar.apiOffline": "接口离线",
    "topbar.logout": "退出",
    "notifications.title": "通知中心",
    "notifications.unread": "未读",
    "notifications.urgent": "紧急",
    "notifications.markAllRead": "全部已读",
    "notifications.empty": "暂无通知",
    "nav.dashboard": "总览",
    "nav.parser": "订单解析",
    "nav.orders": "订单",
    "nav.dispatch": "派车",
    "nav.calendar": "日历",
    "nav.driver-monitor": "司机监控",
    "nav.map": "车辆地图",
    "nav.vehicles": "车辆/司机",
    "nav.agencies": "旅行社",
    "nav.incidents": "异常",
    "nav.finance": "财务",
    "nav.analytics": "经营分析",
    "nav.automation": "自动化",
    "nav.copilot": "运营助手",
    "nav.audit": "审计",
    "nav.settings": "设置",
    "page.dashboard": "运营总览",
    "page.parser": "订单解析",
    "page.orders": "订单中心",
    "page.dispatch": "派车工作台",
    "page.calendar": "日历排程",
    "page.driver-monitor": "司机执行监控",
    "page.map": "车辆地图",
    "page.vehicles": "车辆与司机管理",
    "page.agencies": "旅行社维护",
    "page.incidents": "异常处理",
    "page.finance": "财务概览",
    "page.analytics": "经营分析",
    "page.automation": "规则自动化",
    "page.copilot": "运营助手",
    "page.audit": "数据审计",
    "page.settings": "系统设置",
  },
  "ja-JP": {
    "app.brand": "配車システム",
    "app.subtitle": "管理コンソール",
  },
  "en-US": {
    "app.brand": "微信调度",
    "app.subtitle": "Admin Console",
  },
};

export function translate(locale: Locale, key: string) {
  return dictionaries[locale]?.[key] || dictionaries[defaultLocale][key] || key;
}
