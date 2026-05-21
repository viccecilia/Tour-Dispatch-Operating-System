const DEFAULT_LOCALE = 'zh-CN'

const dictionaries = {
  'zh-CN': {
    dashboard: '首页',
    parser: '订单解析',
    orders: '订单',
    dispatch: '派车',
    calendar: '日历',
    vehicles: '车辆',
    finance: '财务',
    driver: '司机端',
    loading: '加载中',
    empty: '暂无数据',
    save: '保存',
    confirm: '确认',
    cancel: '取消',
    assigned: '已派车',
    unassigned: '未派车',
    completed: '已完成',
    pending: '待处理',
  },
  'ja-JP': {
    dashboard: 'ホーム',
    parser: '注文解析',
    orders: '注文',
    dispatch: '配車',
    calendar: 'カレンダー',
    vehicles: '車両',
    finance: '会計',
    driver: 'ドライバー',
  },
  'en-US': {
    dashboard: '首页',
    parser: '订单解析',
    orders: '订单',
    dispatch: '派车',
    calendar: '日历',
    vehicles: '车辆',
    finance: '财务',
    driver: '司机端',
  },
}

function getLocale() {
  return wx.getStorageSync('wx_dispatch_locale') || DEFAULT_LOCALE
}

function setLocale(locale) {
  const next = dictionaries[locale] ? locale : DEFAULT_LOCALE
  wx.setStorageSync('wx_dispatch_locale', next)
  return next
}

function t(key) {
  const locale = getLocale()
  return (dictionaries[locale] && dictionaries[locale][key]) || dictionaries[DEFAULT_LOCALE][key] || key
}

module.exports = {
  DEFAULT_LOCALE,
  dictionaries,
  getLocale,
  setLocale,
  t,
}
