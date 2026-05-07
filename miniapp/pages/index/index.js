const api = require('../../utils/api');

Page({
  data: {
    summary: {
      today_orders: 0,
      unassigned_orders: 0,
      assigned_orders: 0,
      pending_drafts: 0,
      failed_drafts: 0,
      today_parsed_drafts: 0,
      today_in_service_orders: 0,
      today_completed_orders: 0,
      today_returned_orders: 0,
      unreported_assignments: 0
    },
    nav: [
      { label: '首页', path: '/pages/index/index' },
      { label: '订单', path: '/pages/orders/index' },
      { label: '派车', path: '/pages/dispatch/index' },
      { label: '日历', path: '/pages/calendar/index' },
      { label: '解析', path: '/pages/parser/index' },
      { label: '司机', path: '/pages/driver/index' },
      { label: '车辆', path: '/pages/vehicles/index' },
      { label: '财务', path: '/pages/finance/index' }
    ]
  },

  onLoad() {
    api.dashboardSummary().then((summary) => {
      this.setData({
        summary,
        nav: this.buildNav(summary.nav)
      });
    });
  },

  buildNav(labels = []) {
    const defaults = this.data.nav;
    if (!labels.length) {
      return defaults;
    }
    return labels.map((label) => defaults.find((item) => item.label === label) || { label, path: '/pages/index/index' });
  },

  onNavigate(event) {
    const path = event.currentTarget.dataset.path;
    if (!path || path === '/pages/index/index') {
      return;
    }
    wx.navigateTo({ url: path });
  }
});
