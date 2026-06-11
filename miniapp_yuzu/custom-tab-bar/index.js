const sessionStore = require('../utils/session');

const ROLE_TABS = {
  admin: [
    { pagePath: '/package_dispatch/pages/home/index', text: '首页' },
    { pagePath: '/package_dispatch/pages/dispatch/index', text: '派车' },
    { pagePath: '/package_dispatch/pages/auction/index', text: '订单大厅' },
    { pagePath: '/package_dispatch/pages/finance/index', text: '财务' },
    { pagePath: '/package_dispatch/pages/profile/index', text: '我的' }
  ],
  operations_manager: [
    { pagePath: '/package_dispatch/pages/home/index', text: '首页' },
    { pagePath: '/package_dispatch/pages/calendar/index', text: '日历' },
    { pagePath: '/package_dispatch/pages/map/index', text: '地图' },
    { pagePath: '/package_dispatch/pages/info/index', text: '司机车辆' },
    { pagePath: '/package_dispatch/pages/profile/index', text: '我的' }
  ],
  dispatcher: [
    { pagePath: '/package_dispatch/pages/home/index', text: '首页' },
    { pagePath: '/package_dispatch/pages/dispatch/index', text: '派车' },
    { pagePath: '/package_dispatch/pages/map/index', text: '地图' },
    { pagePath: '/package_dispatch/pages/profile/index', text: '我的' }
  ],
  driver: [
    { pagePath: '/package_dispatch/pages/home/index', text: '首页' },
    { pagePath: '/package_dispatch/pages/task/index', text: '任务' },
    { pagePath: '/package_dispatch/pages/map/index', text: '地图' },
    { pagePath: '/package_dispatch/pages/expense/index', text: '费用' },
    { pagePath: '/package_dispatch/pages/profile/index', text: '我的' }
  ]
};

Component({
  data: {
    visible: false,
    selected: 0,
    roleClass: '',
    list: []
  },

  lifetimes: {
    attached() {
      this.syncSelected();
    }
  },

  pageLifetimes: {
    show() {
      this.syncSelected();
    }
  },

  methods: {
    currentRoute() {
      const pages = getCurrentPages();
      const current = pages[pages.length - 1];
      return `/${current?.route || ''}`;
    },

    syncSelected() {
      const session = sessionStore.getSession();
      const role = sessionStore.getRole(session);
      const list = session ? (ROLE_TABS[role] || ROLE_TABS.dispatcher) : [];
      const route = this.currentRoute();
      const activePath = list.some((item) => item.pagePath === route)
        ? route
        : wx.getStorageSync('dispatch_active_tab_path');
      const selected = list.findIndex((item) => item.pagePath === activePath);
      this.setData({
        visible: Boolean(session && list.length),
        list,
        selected: selected >= 0 ? selected : 0,
        roleClass: ['driver', 'operations_manager'].indexOf(role) >= 0 ? 'driver-theme' : ''
      });
    },

    refresh() {
      this.syncSelected();
    },

    switchTab(event) {
      const index = Number(event.currentTarget.dataset.index || 0);
      const target = this.data.list[index];
      if (!target) return;
      wx.setStorageSync('dispatch_active_tab_path', target.pagePath);
      this.setData({ selected: index });
      if (target.pagePath === this.currentRoute()) {
        this.syncSelected();
        return;
      }
      wx.reLaunch({
        url: target.pagePath,
        success: () => this.syncSelected(),
        fail: () => wx.redirectTo({
          url: target.pagePath,
          success: () => this.syncSelected()
        })
      });
    }
  }
});
