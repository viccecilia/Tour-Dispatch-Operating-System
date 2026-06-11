const session = require('./session');

const DISPATCH_TABS = {
  admin: [
    { key: 'home', label: '首页', url: '/package_dispatch/pages/home/index' },
    { key: 'dispatch', label: '派车', url: '/package_dispatch/pages/dispatch/index' },
    { key: 'auction', label: '订单大厅', url: '/package_dispatch/pages/auction/index' },
    { key: 'map', label: '地图', url: '/package_dispatch/pages/map/index' },
    { key: 'finance', label: '财务', url: '/package_dispatch/pages/finance/index' },
    { key: 'profile', label: '我的', url: '/package_dispatch/pages/profile/index' }
  ],
  dispatcher: [
    { key: 'home', label: '首页', url: '/package_dispatch/pages/home/index' },
    { key: 'dispatch', label: '派车', url: '/package_dispatch/pages/dispatch/index' },
    { key: 'map', label: '地图', url: '/package_dispatch/pages/map/index' },
    { key: 'profile', label: '我的', url: '/package_dispatch/pages/profile/index' }
  ],
  ops: [
    { key: 'home', label: '首页', url: '/package_dispatch/pages/home/index' },
    { key: 'dispatch', label: '车辆', url: '/package_dispatch/pages/dispatch/index' },
    { key: 'map', label: '地图', url: '/package_dispatch/pages/map/index' },
    { key: 'profile', label: '我的', url: '/package_dispatch/pages/profile/index' }
  ],
  driver: [
    { key: 'home', label: '首页', url: '/package_dispatch/pages/home/index' },
    { key: 'task', label: '任务', url: '/package_dispatch/pages/task/index' },
    { key: 'map', label: '地图', url: '/package_dispatch/pages/map/index' },
    { key: 'expense', label: '费用', url: '/package_dispatch/pages/expense/index' },
    { key: 'profile', label: '我的', url: '/package_dispatch/pages/profile/index' }
  ]
};

const AGENCY_TABS = {
  manager: [
    { key: 'home', label: '首页', url: '/package_agency/pages/home/index' },
    { key: 'orders', label: '入单', url: '/package_agency/pages/orders/index' },
    { key: 'hall', label: '大厅', url: '/package_agency/pages/hall/index' },
    { key: 'tracking', label: '跟踪', url: '/package_agency/pages/tracking/index' },
    { key: 'calendar', label: '日历', url: '/package_agency/pages/calendar/index' },
    { key: 'profile', label: '我的', url: '/package_agency/pages/profile/index' }
  ],
  customer_service: [
    { key: 'home', label: '首页', url: '/package_agency/pages/home/index' },
    { key: 'orders', label: '入单', url: '/package_agency/pages/orders/index' },
    { key: 'tracking', label: '跟踪', url: '/package_agency/pages/tracking/index' },
    { key: 'calendar', label: '日历', url: '/package_agency/pages/calendar/index' },
    { key: 'profile', label: '我的', url: '/package_agency/pages/profile/index' }
  ],
  guide: [
    { key: 'home', label: '首页', url: '/package_agency/pages/home/index' },
    { key: 'tracking', label: '任务', url: '/package_agency/pages/tracking/index' },
    { key: 'calendar', label: '日历', url: '/package_agency/pages/calendar/index' },
    { key: 'profile', label: '我的', url: '/package_agency/pages/profile/index' }
  ]
};

function normalizeDispatchRole(rawRole) {
  const role = String(rawRole || '').toLowerCase();
  if (role.includes('driver') || role === '司机') return 'driver';
  if (role.includes('dispatch') || role.includes('dispatcher') || role === '调度') return 'dispatcher';
  if (role.includes('ops') || role.includes('operation') || role.includes('运行')) return 'ops';
  return 'admin';
}

function normalizeAgencyRole(rawRole) {
  const role = String(rawRole || '').toLowerCase();
  if (role.includes('guide') || role.includes('导游')) return 'guide';
  if (role.includes('customer') || role.includes('service') || role.includes('客服')) return 'customer_service';
  return 'manager';
}

function tabsForCurrent(activeKey) {
  const current = session.getSession();
  if (!current) return [];
  const rawRole = session.getRole(current);
  const tabs = current.port === 'agency'
    ? AGENCY_TABS[normalizeAgencyRole(rawRole)]
    : DISPATCH_TABS[normalizeDispatchRole(rawRole)];
  return (tabs || []).map((tab) => ({
    ...tab,
    active: tab.key === activeKey
  }));
}

function switchTab(event) {
  const url = event.currentTarget.dataset.url;
  if (!url) return;
  wx.redirectTo({ url });
}

module.exports = {
  normalizeDispatchRole,
  normalizeAgencyRole,
  tabsForCurrent,
  switchTab
};
