const api = require('../utils/api');

const ROLE_TABS = {
  admin: [
    { pagePath: '/pages/index/index', text: '首页' },
    { pagePath: '/pages/dispatch/index', text: '派车' },
    { pagePath: '/pages/auction/index', text: '订单大厅' },
    { pagePath: '/pages/map/index', text: '地图' },
    { pagePath: '/pages/profile/index', text: '我的' }
  ],
  operations_manager: [
    { pagePath: '/pages/index/index', text: '首页' },
    { pagePath: '/pages/calendar/index', text: '日历' },
    { pagePath: '/pages/map/index', text: '地图' },
    { pagePath: '/pages/info/index', text: '司机车辆' },
    { pagePath: '/pages/profile/index', text: '我的' }
  ],
  dispatcher: [
    { pagePath: '/pages/index/index', text: '首页' },
    { pagePath: '/pages/dispatch/index', text: '派车' },
    { pagePath: '/pages/map/index', text: '地图' },
    { pagePath: '/pages/profile/index', text: '我的' }
  ],
  driver: [
    { pagePath: '/pages/index/index', text: '首页' },
    { pagePath: '/pages/task/index', text: '任务' },
    { pagePath: '/pages/map/index', text: '地图' },
    { pagePath: '/pages/expense/index', text: '费用' },
    { pagePath: '/pages/profile/index', text: '我的' }
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
      const session = api.getSession();
      const role = api.getRole(session);
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
      api.setActiveTab(target.pagePath);
      this.setData({ selected: index });
      if (target.pagePath === this.currentRoute()) {
        this.syncSelected();
        return;
      }
      wx.reLaunch({
        url: target.pagePath,
        success: () => this.syncSelected(),
        fail: () => wx.switchTab({
          url: target.pagePath,
          success: () => this.syncSelected()
        })
      });
    }
  }
});
